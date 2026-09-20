import base64
import json
import os
import re
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses

from bs4 import BeautifulSoup
from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import Http
from sqlalchemy import select

from app.core.errors import DomainError
from app.db.models import Decision, GmailConnection, utcnow
from app.schemas.decision import NormalizedMessage

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]
MAX_BODY = 24000


def map_gmail_http_error(exc: HttpError) -> DomainError:
    status = getattr(exc.resp, "status", None)
    detail = (exc.content or b"").decode("utf-8", errors="replace")[:240]
    if status == 429:
        return DomainError(
            "Gmail ograniczył zapytania (limit). Spróbuj ponownie za kilka minut.",
            429,
        )
    if status in {401, 403}:
        if "accessNotConfigured" in detail or "has not been used" in detail or "disabled" in detail.lower():
            return DomainError(
                "Włącz Gmail API w Google Cloud Console dla tego projektu OAuth.",
                503,
            )
        return DomainError("Połączenie z Gmail wygasło lub brak uprawnień. Połącz konto ponownie.", 503)
    return DomainError("Synchronizacja nie powiodła się. Sprawdź połączenie z Gmail.", 502)


def header(value):
    return re.sub(r"[\r\n]+", " ", str(value or "")).strip()


def parse_message(resource: dict) -> NormalizedMessage:
    raw = base64.urlsafe_b64decode(resource["raw"] + "=" * (-len(resource["raw"]) % 4))
    mail = BytesParser(policy=policy.default).parsebytes(raw)
    addresses = getaddresses(mail.get_all("From", []))
    name, address = addresses[0] if addresses else ("", "")
    flags = []
    if len(addresses) != 1 or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", address):
        flags.append("Niejednoznaczny adres nadawcy")
    # Fail closed when Gmail did not authenticate the sender domain.
    domain = address.rsplit("@", 1)[-1].lower()
    auth_results = [
        header(value).lower()
        for value in mail.get_all("Authentication-Results", [])
        if header(value).lower().startswith("mx.google.com;")
    ]
    authenticated = any(
        re.search(r"\bdmarc=pass\b", result)
        and re.search(r"\bheader\.from=" + re.escape(domain) + r"(?:\s|;|$)", result)
        for result in auth_results
    )
    if not authenticated:
        flags.append("Brak potwierdzenia domeny nadawcy przez Gmail (DMARC)")
    reply_to = getaddresses(mail.get_all("Reply-To", []))
    if reply_to and (len(reply_to) != 1 or reply_to[0][1].lower() != address.lower()):
        flags.append("Adres odpowiedzi różni się od nadawcy")
    if len(mail.get_all("Message-ID", [])) != 1:
        flags.append("Brak jednoznacznego Message-ID")
    rfc_id = header(mail.get("Message-ID"))
    if not re.fullmatch(r"<[^<>\s]+@[^<>\s]+>", rfc_id):
        rfc_id = None
    parts = list(mail.walk()) if mail.is_multipart() else [mail]
    attachments = any(p.get_content_disposition() == "attachment" or p.get_filename() for p in parts)
    plain, html = [], []
    for part in parts:
        if part.is_multipart() or part.get_filename() or part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() not in {"text/plain", "text/html"}:
            continue
        try:
            text = part.get_content()
        except (LookupError, UnicodeError):
            text = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
            flags.append("Niepewne kodowanie wiadomości")
        if isinstance(text, str):
            (plain if part.get_content_type() == "text/plain" else html).append(text)
    if plain:
        body = "\n".join(plain)
    else:
        soup = BeautifulSoup("\n".join(html), "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        body = soup.get_text(separator="\n", strip=True)
    body = body.replace("\r\n", "\n").replace("\x00", "").strip()
    if len(body) > MAX_BODY:
        flags.append("Wiadomość jest zbyt długa do uproszczenia")
    if mail.defects:
        flags.append("Uszkodzona struktura wiadomości")
    return NormalizedMessage(
        gmail_message_id=resource["id"],
        gmail_thread_id=resource.get("threadId", ""),
        rfc_message_id=rfc_id,
        references=header(mail.get("References")),
        sender_name=header(name) or header(address),
        sender_email=header(address).lower(),
        subject=header(mail.get("Subject")) or "(bez tematu)",
        received_at=datetime.fromtimestamp(int(resource["internalDate"]) / 1000, timezone.utc),
        body=body[:MAX_BODY],
        has_attachments=attachments,
        normalization_flags=flags,
    )


def reply_body(decision):
    message = EmailMessage()
    message["To"] = header(decision.sender_email)
    # Gmail requires matching subjects in addition to threadId and RFC reply headers.
    subject = header(decision.subject)
    message["Subject"] = subject if subject.lower().startswith("re:") else "Re: " + subject
    if decision.rfc_message_id:
        message["In-Reply-To"] = header(decision.rfc_message_id)
        refs = (header(decision.references) + " " + header(decision.rfc_message_id)).strip()
        message["References"] = refs
    message.set_content(decision.draft)
    return {
        "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
        "threadId": decision.gmail_thread_id,
    }


class GmailService:
    def __init__(self, settings, sessions):
        self.settings = settings
        self.sessions = sessions

    def flow(self, state=None, code_verifier=None, redirect_uri=None):
        if not self.settings.gmail_configured:
            raise DomainError("Uzupełnij konfigurację OAuth Gmaila.", 503)
        redirect = redirect_uri or self.settings.google_redirect_uri
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect],
                }
            },
            scopes=SCOPES,
            state=state,
            redirect_uri=redirect,
            code_verifier=code_verifier,
            autogenerate_code_verifier=code_verifier is None,
        )
        # Library may drop redirect_uri when forwarding kwargs into OAuth2Session.
        flow.redirect_uri = redirect
        return flow

    def cipher(self):
        return Fernet(self.settings.token_encryption_key.encode())

    def save_credentials(self, session, credentials, email):
        record = session.get(GmailConnection, 1)
        # One mailbox per database prevents account-switch collisions/leaking old drafts.
        if record and record.email != email:
            raise DomainError("Ta baza jest przypisana do innej skrzynki. Użyj nowej bazy dla nowego konta.")
        encrypted = self.cipher().encrypt(credentials.to_json().encode()).decode()
        if record:
            record.encrypted_credentials = encrypted
            if record.connected_at is None:
                record.connected_at = utcnow()
        else:
            session.add(
                GmailConnection(
                    id=1,
                    email=email,
                    encrypted_credentials=encrypted,
                    connected_at=utcnow(),
                )
            )
        session.commit()

    def sync_cutoff(self, session):
        record = session.get(GmailConnection, 1)
        if not record:
            return None
        if record.connected_at is None:
            record.connected_at = utcnow()
            session.commit()
        connected = record.connected_at
        return connected if connected.tzinfo else connected.replace(tzinfo=timezone.utc)

    def list_query(self, cutoff):
        query = self.settings.gmail_query.strip() or "in:inbox -from:me"
        if cutoff is None:
            return query
        # Gmail after: is exclusive of the given day; step back one day, then filter by connected_at.
        from datetime import timedelta

        day = (cutoff.astimezone(timezone.utc) - timedelta(days=1)).strftime("%Y/%m/%d")
        return f"({query}) after:{day}"

    def complete_oauth(self, session, code, state, verifier, redirect_uri=None):
        # include_granted_scopes can widen the granted set; oauthlib otherwise aborts.
        os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
        flow = self.flow(state, verifier, redirect_uri=redirect_uri)
        flow.fetch_token(code=code, timeout=20)
        email = self._email_from_credentials(flow.credentials)
        self.save_credentials(session, flow.credentials, email)

    def _email_from_credentials(self, credentials) -> str:
        """Prefer OAuth userinfo (separate quota) over Gmail getProfile — avoids 429 during connect."""
        http = AuthorizedHttp(credentials, http=Http(timeout=25))
        try:
            _, content = http.request(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                method="GET",
            )
            info = json.loads(content.decode() if isinstance(content, bytes) else content)
            email = (info.get("email") or "").strip()
            if email:
                return email
        except Exception:
            pass
        try:
            client = build(
                "gmail", "v1", http=AuthorizedHttp(credentials, http=Http(timeout=25)), cache_discovery=False
            )
            profile = client.users().getProfile(userId="me").execute(num_retries=0)
            email = (profile.get("emailAddress") or "").strip()
            if email:
                return email
        except Exception as exc:
            raise DomainError("Nie udało się odczytać adresu Gmail po OAuth.", 502) from exc
        raise DomainError("Nie udało się odczytać adresu Gmail po OAuth.", 502)

    def client(self, session):
        if self.settings.app_mode != "live":
            raise DomainError("Gmail jest wyłączony w trybie live.", 403)
        record = session.get(GmailConnection, 1)
        if not record:
            raise DomainError("Najpierw połącz konto Gmail.", 503)
        try:
            info = json.loads(self.cipher().decrypt(record.encrypted_credentials.encode()))
            credentials = Credentials.from_authorized_user_info(info, SCOPES)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self.save_credentials(session, credentials, record.email)
            if not credentials.valid:
                raise ValueError("Expired credentials")
            return build(
                "gmail", "v1", http=AuthorizedHttp(credentials, http=Http(timeout=25)), cache_discovery=False
            )
        except Exception as exc:
            raise DomainError("Połączenie z Gmail wygasło. Połącz konto ponownie.", 503) from exc

    def fetch_messages(self, session):
        client = self.client(session)
        cutoff = self.sync_cutoff(session)
        query = self.list_query(cutoff)
        page = None
        # Bounded hackathon sync. Persisted IDs, not UNREAD flags, are our processing checkpoint.
        try:
            for _ in range(10):
                result = (
                    client.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        maxResults=50,
                        pageToken=page,
                    )
                    .execute(num_retries=0)
                )
                for item in result.get("messages", []):
                    if session.scalar(select(Decision.id).where(Decision.gmail_message_id == item["id"])):
                        continue
                    resource = (
                        client.users()
                        .messages()
                        .get(userId="me", id=item["id"], format="raw")
                        .execute(num_retries=0)
                    )
                    message = parse_message(resource)
                    # Gmail after: is day-granular; drop anything received before connect time.
                    if cutoff is not None and message.received_at < cutoff:
                        continue
                    yield message
                page = result.get("nextPageToken")
                if not page:
                    break
        except HttpError as exc:
            raise map_gmail_http_error(exc) from exc

    def send_reply(self, client, decision):
        response = (
            client.users().messages().send(userId="me", body=reply_body(decision)).execute(num_retries=0)
        )
        return response["id"]
