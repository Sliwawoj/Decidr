from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Decision
from app.main import create_app
from app.services.fixtures import fixtures


def pending(client):
    response = client.get("/api/decisions")
    rows = response.json()
    if not isinstance(rows, list):
        login = client.post("/api/session", json={"password": client.app.state.settings.app_password})
        assert login.status_code == 200
        rows = client.get("/api/decisions").json()
    if not rows:
        state = client.app.state
        with state.sessions() as session:
            from app.services.fixtures import load_fixture_rows

            load_fixture_rows(session, state.ingestion)
        rows = client.get("/api/decisions").json()
    return next(row for row in rows if row["status"] == "pending")


def draft(client, choice="approve"):
    row = pending(client)
    response = client.post(
        f"/api/decisions/{row['id']}/choice", json={"choice": choice, "version": row["version"]}
    )
    assert response.status_code == 200
    return response.json()


def test_health_status_and_live_capsules(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/status").json()["mode"] == "live"
    assert client.get("/api/decisions").status_code == 200


def test_email_signature_is_configurable_and_appended_to_drafts(client):
    status = client.get("/api/status").json()
    assert status["email_signature"] == "Z poważaniem"

    row = draft(client)
    assert row["draft"].rstrip().endswith("Z poważaniem")

    response = client.patch("/api/settings", json={"email_signature": "Pozdrawiam serdecznie,\nAnna Nowak"})
    assert response.status_code == 200
    assert response.json()["email_signature"] == "Pozdrawiam serdecznie,\nAnna Nowak"

    updated = client.get("/api/status").json()
    assert updated["email_signature"] == "Pozdrawiam serdecznie,\nAnna Nowak"

    row2 = draft(client)
    assert row2["draft"].rstrip().endswith("Anna Nowak")


def test_idempotent_ingestion_and_failed_push(client):
    state = client.app.state
    message, analysis = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "unique-message"})
    state.push.notify = Mock(side_effect=RuntimeError("no push"))
    with state.sessions() as session:
        one, created = state.ingestion.ingest(session, message, fixture_analysis=analysis)
        assert created and one.status == "pending"
        two, created = state.ingestion.ingest(session, message, fixture_analysis=analysis)
        assert not created and two.id == one.id


def test_llm_failure_raises_without_fallback(client):
    state = client.app.state
    state.ingestion.analyzer.analyze = Mock(side_effect=TimeoutError())
    message, _ = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "live-failure"})
    with state.sessions() as session:
        with pytest.raises(TimeoutError):
            state.ingestion.ingest(session, message)


def test_high_stakes_and_skips_via_ingest(client, settings):
    state = client.app.state
    legal = list(fixtures())[2]
    message, analysis = legal
    message = message.model_copy(update={"gmail_message_id": "legal-live"})
    with state.sessions() as session:
        row, queued = state.ingestion.ingest(session, message, fixture_analysis=analysis)
        assert queued and row.status == "pending" and row.classification == "needs_reply"
        assert row.safety_reasons  # warnings from fixture / model
    skip_mail = message.model_copy(
        update={
            "gmail_message_id": "skip-newsletter",
            "subject": "Newsletter",
            "body": "Flash sale. Unsubscribe.",
            "sender_email": "promo@shop.example",
        }
    )
    with state.sessions() as session:
        row, queued = state.ingestion.ingest(
            session, skip_mail, True, analysis.model_copy(update={"classification": "skip", "push_text": ""})
        )
        assert not queued and row.status == "skipped"
    assert all(row["gmail_message_id"] != "skip-newsletter" for row in client.get("/api/decisions").json())


def test_push_uses_short_decision_blurb(client, settings):
    state = client.app.state
    message, analysis = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "push-blurb"})
    state.push.notify = Mock()
    with state.sessions() as session:
        row, queued = state.ingestion.ingest(session, message, fixture_analysis=analysis)
        assert queued
    state.push.notify.assert_called_once()
    assert state.push.notify.call_args.args[0] == row.id
    assert "249" in state.push.notify.call_args.args[1]


@pytest.mark.parametrize("choice,word", [("approve", "Wyrażam zgodę"), ("reject", "Nie wyrażam zgody")])
def test_choice_only_creates_draft(client, choice, word):
    client.app.state.gmail.send_reply = Mock(side_effect=AssertionError("Must never send"))
    row = draft(client, choice)
    assert row["status"] == "draft_ready"
    assert row["sent_at"] is None and word in row["draft"]
    assert not client.app.state.gmail.send_reply.called


def test_dismiss_hides_from_queue(client):
    row = pending(client)
    response = client.post(
        f"/api/decisions/{row['id']}/dismiss", json={"version": row["version"]}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    assert all(item["id"] != row["id"] for item in client.get("/api/decisions").json())
    assert client.get(f"/api/decisions/{row['id']}").status_code == 404


@pytest.mark.parametrize("confirmation", [False, "true", 1, None])
def test_send_requires_strict_confirmation(client, confirmation):
    row = draft(client)
    assert (
        client.post(
            f"/api/decisions/{row['id']}/send", json={"confirmed": confirmation, "version": row["version"]}
        ).status_code
        == 422
    )


def test_send_missing_confirmation(client):
    row = draft(client)
    assert (
        client.post(f"/api/decisions/{row['id']}/send", json={"version": row["version"]}).status_code == 422
    )


def test_live_send_flow_and_repeat_send(client):
    client.app.state.gmail.client = Mock(return_value=Mock())
    client.app.state.gmail.send_reply = Mock(return_value="reply-id")
    row = draft(client)
    url = f"/api/decisions/{row['id']}"
    response = client.patch(
        url + "/draft", json={"draft": "Dziękuję, potwierdzam warunki.", "version": row["version"]}
    )
    assert response.status_code == 200
    edited = response.json()
    assert edited["draft"] == "Dziękuję, potwierdzam warunki."
    assert client.post(url + "/send", json={"confirmed": True, "version": row["version"]}).status_code == 409
    response = client.post(url + "/send", json={"confirmed": True, "version": edited["version"]})
    assert response.status_code == 200
    final = response.json()
    assert final["status"] == "sent"
    assert final["sent_at"] is not None and final["gmail_reply_id"] == "reply-id"
    assert client.app.state.gmail.send_reply.called
    assert client.get(url).json()["draft"] == edited["draft"]
    assert client.post(url + "/send", json={"confirmed": True, "version": final["version"]}).status_code == 409
    assert client.post(url + "/choice", json={"choice": "reject", "version": final["version"]}).status_code == 409


def test_empty_draft_and_wrong_version(client):
    row = draft(client)
    url = f"/api/decisions/{row['id']}/draft"
    assert client.patch(url, json={"draft": "  ", "version": row["version"]}).status_code == 422
    assert client.patch(url, json={"draft": "Hello", "version": 1}).status_code == 409


def test_live_ingest_stores_real_messages(client):
    state = client.app.state
    message, analysis = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "actual-email"})
    state.ingestion.analyzer.analyze = Mock(return_value=analysis)
    with state.sessions() as session:
        real, _ = state.ingestion.ingest(session, message)
        real_id = real.id
    assert client.get(f"/api/decisions/{real_id}").status_code == 200
    with state.sessions() as session:
        assert session.get(Decision, real_id)
        assert len(session.scalars(select(Decision)).all()) == 1


def test_live_blocks_gmail_oauth_and_unconfigured_push(client):
    assert client.post("/api/gmail/sync").status_code == 503
    assert client.post("/api/oauth/gmail/start").status_code == 503
    assert (
        client.post(
            "/api/push/subscriptions",
            json={
                "endpoint": "https://fcm.googleapis.com/push/id",
                "keys": {"p256dh": "a" * 50, "auth": "a" * 20},
            },
        ).status_code
        == 503
    )


def test_csrf_guard(client):
    assert client.post("/api/gmail/sync", headers={"X-Decidr-Client": ""}).status_code == 403
    assert client.post("/api/gmail/sync", headers={"Origin": "https://evil.example"}).status_code == 403
    # Same Host the request hit is allowed even when FRONTEND_URL differs (ngrok / tunnel).
    assert (
        client.post(
            "/api/gmail/sync",
            headers={"Origin": "http://testserver", "Host": "testserver"},
        ).status_code
        != 403
    )
    assert (
        client.post(
            "/api/gmail/sync",
            headers={
                "Origin": "https://tunnel.example",
                "Host": "tunnel.example",
                "X-Forwarded-Proto": "https",
            },
        ).status_code
        != 403
    )


def test_parallel_confirmations_complete_once(client):
    client.app.state.gmail.client = Mock(return_value=Mock())
    client.app.state.gmail.send_reply = Mock(return_value="reply-id")
    row = draft(client)

    def send():
        return client.post(
            f"/api/decisions/{row['id']}/send", json={"confirmed": True, "version": row["version"]}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: send(), range(2)))
    assert sorted(results) == [200, 409]


def test_live_session_protects_data(settings):
    from cryptography.fernet import Fernet

    live = settings.model_copy(
        update={
            "app_mode": "live",
            "app_password": "test-password-123",
            "session_secret": "s" * 32,
            "token_encryption_key": Fernet.generate_key().decode(),
        }
    )
    with TestClient(create_app(live), headers={"X-Decidr-Client": "web"}) as client:
        assert client.get("/api/decisions").status_code == 401
        assert client.post("/api/session", json={"password": "incorrect"}).status_code == 401
        assert client.post("/api/session", json={"password": live.app_password}).status_code == 200
        assert client.get("/api/decisions").status_code == 200
        assert client.post("/api/gmail/sync").status_code == 503
        callback = client.get(
            "/api/oauth/gmail/callback?state=forged&code=fake", follow_redirects=False
        )
        assert callback.status_code == 303
        assert "oauth=error" in callback.headers["location"]
        assert client.delete("/api/session").status_code == 200
        assert client.get("/api/decisions").status_code == 401


def test_live_send_success_and_uncertain_failure(client, settings):
    from app.services import drafts

    state = client.app.state
    for suffix, fail in [("success", False), ("uncertain", True)]:
        message, analysis = next(fixtures())
        with state.sessions() as session:
            row, _ = state.ingestion.ingest(
                session, message.model_copy(update={"gmail_message_id": suffix}), True, analysis
            )
            row = drafts.choose(session, row, "approve", 1)
            row.send_error = None
            session.commit()
            gmail = Mock()
            gmail.send_reply = Mock(side_effect=TimeoutError()) if fail else Mock(return_value="reply-id")
            live = settings.model_copy(update={"app_mode": "live"})
            if fail:
                from app.core.errors import DomainError

                with pytest.raises(DomainError):
                    drafts.send(session, row, True, row.version, live, gmail)
                session.refresh(row)
                assert row.send_attempted_at and row.sent_at is None and row.send_error
                with pytest.raises(DomainError):
                    drafts.send(session, row, True, row.version, live, gmail)
                assert gmail.send_reply.call_count == 1
            else:
                sent = drafts.send(session, row, True, row.version, live, gmail)
                assert sent.status == "sent" and sent.sent_at and sent.gmail_reply_id == "reply-id"
