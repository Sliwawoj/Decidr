import hmac
import logging
import secrets
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.csrf import public_base_url
from app.core.errors import DomainError
from app.db.models import Decision, GmailConnection
from app.schemas.decision import ChoiceIn, DecisionOut, DismissIn, DraftIn, PushIn, SendIn
from app.services import drafts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def session_db(request: Request):
    with request.app.state.sessions() as session:
        yield session


def authorized(request: Request):
    if request.app.state.settings.app_mode == "live" and not request.session.get("authenticated"):
        raise DomainError("Zaloguj się do swojej przestrzeni Decidr.", 401)


def live_only(request):
    if request.app.state.settings.app_mode != "live":
        raise DomainError("Ta integracja jest dostępna tylko w trybie live.", 400)


@router.get("/health")
def health():
    return {"status": "ok"}


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class SettingsIn(BaseModel):
    email_signature: str = Field(default="Z poważaniem", max_length=1000)


@router.post("/session")
def login(data: LoginIn, request: Request):
    settings = request.app.state.settings
    key = request.client.host if request.client else "unknown"
    attempts = request.app.state.login_attempts
    now = time.monotonic()
    # A small bounded, in-memory limit is sufficient for this single-process MVP.
    for host in list(attempts):
        attempts[host] = [t for t in attempts[host] if now - t < 300]
        if not attempts[host]:
            del attempts[host]
    if len(attempts.get(key, [])) >= 5:
        raise DomainError("Zbyt wiele prób. Spróbuj ponownie za 5 minut.", 429)
    if settings.app_mode == "live" and not hmac.compare_digest(
        data.password.encode(), settings.app_password.encode()
    ):
        attempts.setdefault(key, []).append(now)
        raise DomainError("Nieprawidłowe hasło.", 401)
    request.session.clear()
    request.session["authenticated"] = True
    attempts.pop(key, None)
    return {"authenticated": True}


@router.delete("/session")
def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}


@router.get("/status")
def status(request: Request, session=Depends(session_db)):
    state = request.app.state
    settings = state.settings
    authenticated = settings.app_mode == "live" and request.session.get("authenticated", False)
    connection = session.get(GmailConnection, 1) if authenticated else None
    return {
        "mode": settings.app_mode,
        "authenticated": authenticated,
        "gmail": {
            "configured": settings.gmail_configured,
            "connected": bool(connection),
            "email": connection.email if connection else None,
        },
        "llm": {"configured": settings.llm_configured, "model": settings.gemini_model},
        "push": {
            "configured": settings.push_configured,
            "public_key": settings.vapid_public_key if settings.push_configured else None,
        },
        "email_signature": settings.email_signature,
        "last_sync_at": state.ingestion.last_sync_at if authenticated else None,
        "last_sync_error": state.ingestion.last_sync_error if authenticated else None,
    }


@router.patch("/settings", dependencies=[Depends(authorized)])
def update_settings(data: SettingsIn, request: Request):
    request.app.state.settings.email_signature = data.email_signature.strip() or "Z poważaniem"
    return {"email_signature": request.app.state.settings.email_signature}


@router.get("/decisions", response_model=list[DecisionOut], dependencies=[Depends(authorized)])
def list_decisions(request: Request, session=Depends(session_db)):
    return session.scalars(
        select(Decision).where(drafts.visible_filter()).order_by(Decision.received_at.desc())
    ).all()


@router.get("/decisions/{decision_id}", response_model=DecisionOut, dependencies=[Depends(authorized)])
def detail(decision_id: str, request: Request, session=Depends(session_db)):
    return drafts.get_decision(session, decision_id, request.app.state.settings)


@router.post("/gmail/sync", dependencies=[Depends(authorized)])
def sync_gmail(request: Request):
    return request.app.state.ingestion.sync()


@router.post(
    "/decisions/{decision_id}/choice", response_model=DecisionOut, dependencies=[Depends(authorized)]
)
def choose(decision_id: str, data: ChoiceIn, request: Request, session=Depends(session_db)):
    decision = drafts.get_decision(session, decision_id, request.app.state.settings)
    return drafts.choose(
        session,
        decision,
        data.choice,
        data.version,
        analyzer=request.app.state.ingestion.analyzer,
        settings=request.app.state.settings,
    )


@router.post(
    "/decisions/{decision_id}/dismiss", response_model=DecisionOut, dependencies=[Depends(authorized)]
)
def dismiss(decision_id: str, data: DismissIn, request: Request, session=Depends(session_db)):
    decision = drafts.get_decision(session, decision_id, request.app.state.settings)
    return drafts.dismiss(session, decision, data.version)


@router.patch(
    "/decisions/{decision_id}/draft", response_model=DecisionOut, dependencies=[Depends(authorized)]
)
def edit_draft(decision_id: str, data: DraftIn, request: Request, session=Depends(session_db)):
    decision = drafts.get_decision(session, decision_id, request.app.state.settings)
    return drafts.edit(session, decision, data.draft, data.version)


@router.post("/decisions/{decision_id}/send", response_model=DecisionOut, dependencies=[Depends(authorized)])
def send(decision_id: str, data: SendIn, request: Request, session=Depends(session_db)):
    state = request.app.state
    decision = drafts.get_decision(session, decision_id, state.settings)
    return drafts.send(session, decision, data.confirmed, data.version, state.settings, state.gmail)


@router.post("/push/subscriptions", dependencies=[Depends(authorized)])
def subscribe(data: PushIn, request: Request, session=Depends(session_db)):
    if not request.app.state.settings.push_configured:
        raise DomainError("Web Push nie jest skonfigurowany. Kolejka działa bez powiadomień.", 503)
    request.app.state.push.subscribe(session, data)
    return {"subscribed": True}


@router.delete("/push/subscriptions", dependencies=[Depends(authorized)])
def unsubscribe(endpoint: str, request: Request, session=Depends(session_db)):
    if not endpoint or len(endpoint) > 2048:
        raise DomainError("Nieprawidłowy endpoint powiadomień.", 400)
    request.app.state.push.unsubscribe(session, endpoint)
    return {"subscribed": False}


@router.delete("/gmail/connection", dependencies=[Depends(authorized)])
def disconnect_gmail(request: Request, session=Depends(session_db)):
    live_only(request)
    connection = session.get(GmailConnection, 1)
    if connection:
        session.delete(connection)
        session.commit()
    return {"connected": False}


@router.post("/oauth/gmail/start", dependencies=[Depends(authorized)])
def oauth_start(request: Request):
    live_only(request)
    settings = request.app.state.settings
    # Must match an authorized redirect URI in Google Cloud and the URL the user opened.
    redirect_uri = settings.google_redirect_uri
    flow = request.app.state.gmail.flow(redirect_uri=redirect_uri)
    url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    request.session["oauth"] = {
        "state": state,
        "verifier": flow.code_verifier,
        "created": time.time(),
        "redirect_uri": redirect_uri,
    }
    return {"url": url}


@router.get("/oauth/gmail/callback")
def oauth_callback(request: Request, session=Depends(session_db)):
    """Browser return from Google — always redirect to the SPA, never raw JSON."""
    settings = request.app.state.settings
    base = public_base_url(request, settings.frontend_url) + "/settings"
    if settings.app_mode != "live":
        return RedirectResponse(base + "?oauth=error", status_code=303)
    if not request.session.get("authenticated"):
        return RedirectResponse(base + "?oauth=error", status_code=303)
    oauth = request.session.pop("oauth", None)
    supplied_state = request.query_params.get("state", "")
    if (
        not oauth
        or time.time() - oauth["created"] > 600
        or not secrets.compare_digest(supplied_state, oauth["state"])
    ):
        return RedirectResponse(base + "?oauth=error", status_code=303)
    code = request.query_params.get("code")
    if not code or request.query_params.get("error"):
        return RedirectResponse(base + "?oauth=cancelled", status_code=303)
    try:
        request.app.state.gmail.complete_oauth(
            session,
            code,
            supplied_state,
            oauth["verifier"],
            redirect_uri=oauth.get("redirect_uri") or settings.google_redirect_uri,
        )
    except DomainError as exc:
        logger.warning("Gmail OAuth failed: %s", exc.message)
        kind = "rate_limited" if exc.status_code == 429 else "error"
        return RedirectResponse(base + f"?oauth={kind}", status_code=303)
    except Exception:
        logger.exception("Gmail OAuth token exchange failed")
        return RedirectResponse(base + "?oauth=error", status_code=303)
    return RedirectResponse(base + "?oauth=connected", status_code=303)
