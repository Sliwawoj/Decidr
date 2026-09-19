import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet
from pywebpush import WebPushException
from sqlalchemy import select

from app.db.models import GmailConnection, PushSubscription
from app.schemas.decision import PushIn
from app.services.analyzer import LLMAnalyzer
from app.services.demo import fixtures
from app.services.gmail import GmailService


def test_structured_output_and_refusal_fallback(settings):
    message, analysis = next(fixtures())
    analyzer = LLMAnalyzer(settings.model_copy(update={"gemini_api_key": "test-key"}))
    with patch("app.services.analyzer.genai.Client") as sdk:
        client = sdk.return_value
        client.models.generate_content.return_value = SimpleNamespace(parsed=analysis)
        assert analyzer.analyze(message) == analysis
        args = client.models.generate_content.call_args.kwargs
        assert args["model"] == settings.gemini_model
        assert args["config"].response_schema.__name__ == "Analysis"
        assert "UNTRUSTED DATA" in args["config"].system_instruction
        client.models.generate_content.return_value = SimpleNamespace(parsed=None)
        assert analyzer.analyze(message).classification == "review_required"
        client.models.generate_content.side_effect = TimeoutError()
        assert analyzer.analyze(message).confidence == 0


def test_missing_llm_key_never_uses_demo_analysis(settings):
    message, _ = next(fixtures())
    with patch("app.services.analyzer.genai.Client") as sdk:
        assert LLMAnalyzer(settings).analyze(message).classification == "review_required"
        sdk.assert_not_called()


def test_credentials_are_encrypted_and_mailbox_is_pinned(client, settings):
    from app.core.errors import DomainError

    live = settings.model_copy(
        update={"app_mode": "live", "token_encryption_key": Fernet.generate_key().decode()}
    )
    gmail = GmailService(live, client.app.state.sessions)
    credentials = Mock()
    credentials.to_json.return_value = json.dumps({"refresh_token": "sensitive-test-token"})
    with client.app.state.sessions() as session:
        gmail.save_credentials(session, credentials, "owner@example.com")
        record = session.get(GmailConnection, 1)
        assert record.connected_at is not None
        assert "sensitive-test-token" not in record.encrypted_credentials
        assert (
            json.loads(gmail.cipher().decrypt(record.encrypted_credentials.encode()))["refresh_token"]
            == "sensitive-test-token"
        )
        with pytest.raises(DomainError):
            gmail.save_credentials(session, credentials, "other@example.com")


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/id",
        "https://127.0.0.1/internal",
        "https://evil.example/",
        "https://fcm.googleapis.com.evil.example/id",
        "https://fcm.googleapis.com:123/id",
    ],
)
def test_push_cannot_target_arbitrary_servers(endpoint):
    with pytest.raises(ValueError):
        PushIn(endpoint=endpoint, keys={"p256dh": "x" * 50, "auth": "x" * 20})


def test_expired_push_removed_and_other_failure_does_not_break(client):
    state = client.app.state
    state.push.settings = state.settings.model_copy(
        update={
            "vapid_public_key": "configured",
            "vapid_private_key": "configured",
        }
    )
    with state.sessions() as session:
        state.push.subscribe(
            session,
            PushIn(endpoint="https://fcm.googleapis.com/id", keys={"p256dh": "x" * 50, "auth": "x" * 20}),
        )
    with patch("app.services.push.webpush") as send:
        send.side_effect = WebPushException("gone", response=SimpleNamespace(status_code=410))
        state.push.notify("id")
        payload = json.loads(send.call_args.kwargs["data"])
        assert set(payload) == {"title", "body", "url"}
    with state.sessions() as session:
        assert not session.scalars(select(PushSubscription)).all()


def test_gmail_fetch_skips_processed_and_paginates(client, settings):
    from email.message import EmailMessage

    gmail = GmailService(settings, client.app.state.sessions)
    provider = Mock()
    messages = provider.users.return_value.messages.return_value
    messages.list.return_value.execute.side_effect = [
        {"messages": [{"id": "demo-1"}, {"id": "real-1"}], "nextPageToken": "next"},
        {"messages": []},
    ]
    mail = EmailMessage()
    mail["From"] = "anna@example.com"
    mail["Message-ID"] = "<new@example.com>"
    mail["Subject"] = "Czy potwierdzasz?"
    mail.set_content("Czy potwierdzasz odbiór?")
    messages.get.return_value.execute.return_value = {
        "id": "real-1",
        "threadId": "thread-1",
        "internalDate": "1789812000000",
        "raw": base64.urlsafe_b64encode(mail.as_bytes()).decode(),
    }
    gmail.client = Mock(return_value=provider)
    with client.app.state.sessions() as session:
        rows = list(gmail.fetch_messages(session))
    assert len(rows) == 1 and rows[0].gmail_message_id == "real-1"
    assert messages.get.call_count == 1 and messages.list.call_count == 2
    assert messages.list.call_args.kwargs["pageToken"] == "next"

def test_gmail_fetch_skips_mail_before_connect(client, settings):
    from datetime import datetime, timedelta, timezone
    from email.message import EmailMessage

    from cryptography.fernet import Fernet

    live = settings.model_copy(
        update={"app_mode": "live", "token_encryption_key": Fernet.generate_key().decode()}
    )
    gmail = GmailService(live, client.app.state.sessions)
    provider = Mock()
    messages = provider.users.return_value.messages.return_value
    messages.list.return_value.execute.return_value = {"messages": [{"id": "old-1"}, {"id": "new-1"}]}
    old_mail = EmailMessage()
    old_mail["From"] = "anna@example.com"
    old_mail["Message-ID"] = "<old@example.com>"
    old_mail["Subject"] = "Stary"
    old_mail.set_content("Stara prośba")
    new_mail = EmailMessage()
    new_mail["From"] = "anna@example.com"
    new_mail["Message-ID"] = "<new@example.com>"
    new_mail["Subject"] = "Nowy"
    new_mail.set_content("Nowa prośba")
    connected = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    messages.get.return_value.execute.side_effect = [
        {
            "id": "old-1",
            "threadId": "t1",
            "internalDate": str(int((connected - timedelta(hours=2)).timestamp() * 1000)),
            "raw": base64.urlsafe_b64encode(old_mail.as_bytes()).decode(),
        },
        {
            "id": "new-1",
            "threadId": "t2",
            "internalDate": str(int((connected + timedelta(hours=1)).timestamp() * 1000)),
            "raw": base64.urlsafe_b64encode(new_mail.as_bytes()).decode(),
        },
    ]
    gmail.client = Mock(return_value=provider)
    with client.app.state.sessions() as session:
        session.add(
            GmailConnection(
                id=1,
                email="owner@example.com",
                encrypted_credentials=gmail.cipher().encrypt(b'{"token":"x"}').decode(),
                connected_at=connected,
            )
        )
        session.commit()
        rows = list(gmail.fetch_messages(session))
    assert [row.gmail_message_id for row in rows] == ["new-1"]
    assert "after:2026/01/09" in messages.list.call_args.kwargs["q"]
