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
    analyzer = LLMAnalyzer(settings.model_copy(update={"openai_api_key": "test-key"}))
    with patch("app.services.analyzer.OpenAI") as sdk:
        client = sdk.return_value.__enter__.return_value
        client.responses.parse.return_value = SimpleNamespace(output_parsed=analysis, status="completed")
        assert analyzer.analyze(message) == analysis
        args = client.responses.parse.call_args.kwargs
        assert args["text_format"].__name__ == "Analysis" and args["store"] is False
        assert "UNTRUSTED DATA" in args["input"][0]["content"]
        client.responses.parse.return_value = SimpleNamespace(output_parsed=None, status="completed")
        assert analyzer.analyze(message).classification == "review_required"
        client.responses.parse.side_effect = TimeoutError()
        assert analyzer.analyze(message).confidence == 0


def test_missing_llm_key_never_uses_demo_analysis(settings):
    message, _ = next(fixtures())
    with patch("app.services.analyzer.OpenAI") as sdk:
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
