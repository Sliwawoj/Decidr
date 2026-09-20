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


def test_normalize_draft_newlines_unescapes_literal_backslash_n():
    from app.services.analyzer import _normalize_draft_newlines

    literal = r"Dzień dobry,\n\nWyrażam zgodę.\n\nPozdrawiam"
    assert _normalize_draft_newlines(literal) == "Dzień dobry,\n\nWyrażam zgodę.\n\nPozdrawiam"
    already = "Dzień dobry,\n\nWyrażam zgodę.\n\nPozdrawiam"
    assert _normalize_draft_newlines(already) == already
    # Mixed: real newlines already present and dominate — leave alone
    mixed = "Linia 1\nLinia 2 z \\n w środku"
    assert _normalize_draft_newlines(mixed) == mixed


def test_strip_llm_closing_removes_farewell_and_name_placeholder():
    from app.services.drafts import append_signature, strip_llm_closing
    from types import SimpleNamespace

    raw = (
        "Cześć Tomasz,\n\n"
        "Dzięki za podsumowanie. W kwestii uruchomienia nowego systemu CRM, "
        "proszę o kontynuowanie prac zgodnie z opcją: [WPISZ SWOJĄ DECYZJĘ].\n\n"
        "Pozdrawiam,\n"
        "[Twoje imię]"
    )
    stripped = strip_llm_closing(raw)
    assert stripped.endswith("[WPISZ SWOJĄ DECYZJĘ].")
    assert "Pozdrawiam" not in stripped
    assert "[Twoje imię]" not in stripped

    settings = SimpleNamespace(email_signature="Z poważaniem,\nRyba z Łodzi")
    drafted = append_signature(raw, settings)
    assert drafted.count("Z poważaniem") == 1
    assert drafted.endswith("Ryba z Łodzi")
    assert "Pozdrawiam" not in drafted
    assert "[Twoje imię]" not in drafted


def test_suggest_draft_unescapes_literal_newlines(settings):
    from app.services.analyzer import ReplyDraft

    message, analysis = next(fixtures())
    analyzer = LLMAnalyzer(settings.model_copy(update={"gemini_api_key": "test-key"}))
    with patch("app.services.analyzer.genai.Client") as sdk:
        client = sdk.return_value
        client.models.generate_content.return_value = SimpleNamespace(
            parsed=ReplyDraft(draft=r"Dzień dobry,\n\nPotwierdzam.\n\nPozdrawiam")
        )
        draft = analyzer.suggest_draft(analysis, "approve")
        assert "\n\n" in draft
        assert "\\n" not in draft
        assert draft.startswith("Dzień dobry")


def test_two_step_llm_gate_and_extract(settings):
    from app.services.analyzer import DecisionGate, ExtractedDecision

    message, analysis = next(fixtures())
    analyzer = LLMAnalyzer(settings.model_copy(update={"gemini_api_key": "test-key"}))
    extracted = ExtractedDecision(
        decision_type=analysis.decision_type,
        summary=analysis.summary,
        request_text=analysis.request_text,
        push_text=analysis.push_text,
        amount=analysis.amount,
        currency=analysis.currency,
        deadline=analysis.deadline,
        conditions=analysis.conditions,
        missing_fields=analysis.missing_fields,
        risk_flags=analysis.risk_flags,
        warnings=analysis.warnings,
        confidence=analysis.confidence,
        is_binary=analysis.is_binary,
    )
    with patch("app.services.analyzer.genai.Client") as sdk:
        client = sdk.return_value
        client.models.generate_content.side_effect = [
            SimpleNamespace(parsed=DecisionGate(needs_decision=True, reason="Jest pytanie o zgodę")),
            SimpleNamespace(parsed=extracted),
        ]
        result = analyzer.analyze(message)
        assert result.classification == "needs_reply"
        assert result.push_text == analysis.push_text
        assert result.request_text == analysis.request_text
        assert result.summary == analysis.summary
        assert client.models.generate_content.call_count == 2
        gate_args, extract_args = client.models.generate_content.call_args_list
        assert gate_args.kwargs["config"].response_schema.__name__ == "DecisionGate"
        assert extract_args.kwargs["config"].response_schema.__name__ == "ExtractedDecision"


def test_needs_review_adds_open_draft_llm_call(settings):
    from app.services.analyzer import DECISION_PLACEHOLDER, DecisionGate, ExtractedDecision, ReplyDraft

    message, analysis = next(fixtures())
    analyzer = LLMAnalyzer(settings.model_copy(update={"gemini_api_key": "test-key"}))
    extracted = ExtractedDecision(
        decision_type=analysis.decision_type,
        summary=analysis.summary,
        request_text=analysis.request_text,
        push_text=analysis.push_text,
        amount=analysis.amount,
        currency=analysis.currency,
        deadline=analysis.deadline,
        conditions=analysis.conditions,
        missing_fields=analysis.missing_fields,
        risk_flags=analysis.risk_flags,
        warnings=analysis.warnings,
        confidence=analysis.confidence,
        is_binary=False,
    )
    draft_text = (
        "Cześć Anno,\n\n"
        "Dziękuję za przygotowanie materiałów.\n\n"
        f"Moja decyzja: {DECISION_PLACEHOLDER}\n\n"
        "Pozdrawiam,"
    )
    with patch("app.services.analyzer.genai.Client") as sdk:
        client = sdk.return_value
        client.models.generate_content.side_effect = [
            SimpleNamespace(parsed=DecisionGate(needs_decision=True, reason="Wymaga odpowiedzi")),
            SimpleNamespace(parsed=extracted),
            SimpleNamespace(parsed=ReplyDraft(draft=draft_text)),
        ]
        result = analyzer.analyze(message)
        assert result.classification == "needs_review"
        assert "Pozdrawiam" not in result.draft
        assert result.draft.endswith("Z poważaniem")
        assert DECISION_PLACEHOLDER in result.draft
        assert "Dziękuję za przygotowanie materiałów." in result.draft
        assert client.models.generate_content.call_count == 3
        review_call = client.models.generate_content.call_args_list[2]
        assert review_call.kwargs["config"].response_schema.__name__ == "ReplyDraft"
        assert review_call.kwargs["config"].temperature == 0.4


def test_gate_skip_skips_second_llm_call(settings):
    from app.services.analyzer import DecisionGate

    message, _ = next(fixtures())
    analyzer = LLMAnalyzer(settings.model_copy(update={"gemini_api_key": "test-key"}))
    with patch("app.services.analyzer.genai.Client") as sdk:
        client = sdk.return_value
        client.models.generate_content.return_value = SimpleNamespace(
            parsed=DecisionGate(needs_decision=False, reason="Newsletter")
        )
        result = analyzer.analyze(message)
        assert result.classification == "skip"
        assert client.models.generate_content.call_count == 1


def test_classification_uses_gate_and_binary_flags():
    from app.services.analyzer import classify_message

    assert classify_message(False, True) == "skip"
    assert classify_message(True, False) == "needs_review"
    assert classify_message(True, True) == "needs_reply"


def test_llm_failure_raises_without_fallback(settings):
    message, _ = next(fixtures())
    analyzer = LLMAnalyzer(settings.model_copy(update={"gemini_api_key": "test-key"}))
    with patch("app.services.analyzer.genai.Client") as sdk:
        sdk.return_value.models.generate_content.side_effect = TimeoutError()
        with pytest.raises(RuntimeError, match="Błąd analizy AI"):
            analyzer.analyze(message)


def test_missing_llm_key_raises_without_fallback(settings):
    message, _ = next(fixtures())
    with patch("app.services.analyzer.genai.Client") as sdk:
        with pytest.raises(RuntimeError, match="Gemini API key"):
            LLMAnalyzer(settings).analyze(message)
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


def test_gmail_rate_limit_maps_to_domain_error_with_backoff(client, settings):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.errors import DomainError
    from app.services.gmail import map_gmail_http_error
    from googleapiclient.errors import HttpError

    content = (
        b'{"error":{"code":429,"message":'
        b'"User-rate limit exceeded.  Retry after 2026-09-20T10:14:54.735Z"}}'
    )
    exc = HttpError(SimpleNamespace(status=429, reason="Too Many Requests"), content)
    mapped = map_gmail_http_error(exc)
    assert isinstance(mapped, DomainError)
    assert mapped.status_code == 429
    assert mapped.retry_after == datetime(2026, 9, 20, 10, 14, 54, 735000, tzinfo=timezone.utc)
    assert "ograniczył zapytania" in mapped.message

    live = settings.model_copy(update={"app_mode": "live", "scheduler_enabled": False})
    state = client.app.state
    state.settings = live
    state.ingestion.settings = live
    state.ingestion.gmail.fetch_messages = Mock(side_effect=mapped)
    with pytest.raises(DomainError) as raised:
        state.ingestion.sync()
    assert raised.value.status_code == 429
    assert state.ingestion.rate_limited_until == mapped.retry_after
    assert "ograniczył zapytania" in state.ingestion.last_sync_error

    # While backing off, sync must not hit Gmail again.
    state.ingestion.gmail.fetch_messages.reset_mock()
    with pytest.raises(DomainError) as waiting:
        state.ingestion.sync()
    assert waiting.value.status_code == 429
    state.ingestion.gmail.fetch_messages.assert_not_called()
