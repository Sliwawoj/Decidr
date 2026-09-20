from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Decision
from app.main import create_app
from app.services.demo import fixtures


def pending(client):
    return next(row for row in client.get("/api/decisions").json() if row["status"] == "pending")


def draft(client, choice="approve"):
    row = pending(client)
    response = client.post(
        f"/api/decisions/{row['id']}/choice", json={"choice": choice, "version": row["version"]}
    )
    assert response.status_code == 200
    return response.json()


def test_health_status_and_idempotent_demo(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/status").json()["mode"] == "demo"
    for _ in range(3):
        assert client.post("/api/demo/load").json() == {"created": 0}
    assert len(client.get("/api/decisions").json()) == 4


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
        one, created = state.ingestion.ingest(session, message, True, analysis)
        assert created and one.status == "pending"
        two, created = state.ingestion.ingest(session, message, True, analysis)
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
        row, queued = state.ingestion.ingest(session, message, True, analysis)
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


def test_needs_review_skips_choice_and_opens_editable_draft(client):
    state = client.app.state
    message, analysis = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "review-open-draft"})
    review = analysis.model_copy(
        update={
            "classification": "needs_review",
            "is_binary": False,
            "draft": "DzieÅ„ dobry,\n\nPropozycja LLM.\n\nPozdrawiam",
        }
    )
    with state.sessions() as session:
        row, queued = state.ingestion.ingest(session, message, True, review)
        assert queued and row.status == "draft_ready"
        assert row.classification == "needs_review"
        assert row.user_choice is None
        assert "Propozycja LLM" in (row.draft or "")
        decision_id, version = row.id, row.version
    assert (
        client.post(
            f"/api/decisions/{decision_id}/choice",
            json={"choice": "approve", "version": version},
        ).status_code
        == 409
    )
    edited = client.patch(
        f"/api/decisions/{decision_id}/draft",
        json={"draft": "DzieÅ„ dobry,\n\nPoprawiona odpowiedÅº.\n\nPozdrawiam", "version": version},
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["draft"].startswith("DzieÅ„ dobry")
    assert "Poprawiona" in body["draft"]
    sent = client.post(
        f"/api/decisions/{decision_id}/send",
        json={"confirmed": True, "version": body["version"]},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "demo_completed"

def test_push_uses_short_decision_blurb(client, settings):
    state = client.app.state
    message, analysis = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "push-blurb"})
    state.push.notify = Mock()
    with state.sessions() as session:
        row, queued = state.ingestion.ingest(session, message, True, analysis)
        assert queued
    state.push.notify.assert_called_once()
    assert state.push.notify.call_args.args[0] == row.id
    assert "249" in state.push.notify.call_args.args[1]


@pytest.mark.parametrize("choice,word", [("approve", "WyraÅ¼am zgodÄ™"), ("reject", "Nie wyraÅ¼am zgody")])
def test_choice_only_creates_draft(client, choice, word):
    client.app.state.gmail.send_reply = Mock(side_effect=AssertionError("Must never send"))
    row = draft(client, choice)
    assert row["status"] == "draft_ready"
    assert row["sent_at"] is None and word in row["draft"]
    assert not client.app.state.gmail.send_reply.called


def test_dismiss_removes_from_queue_without_reply(client):
    row = pending(client)
    decision_id = row["id"]
    response = client.post(
        f"/api/decisions/{decision_id}/dismiss", json={"version": row["version"]}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    assert all(item["id"] != decision_id for item in client.get("/api/decisions").json())
    assert client.get(f"/api/decisions/{decision_id}").status_code == 404
    assert (
        client.post(
            f"/api/decisions/{decision_id}/dismiss", json={"version": row["version"]}
        ).status_code
        == 404
    )


def test_dismiss_from_draft_ready(client):
    row = draft(client)
    response = client.post(
        f"/api/decisions/{row['id']}/dismiss", json={"version": row["version"]}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    assert client.get(f"/api/decisions/{row['id']}").status_code == 404


def test_dismiss_rejects_stale_version(client):
    row = pending(client)
    assert (
        client.post(
            f"/api/decisions/{row['id']}/dismiss", json={"version": row["version"] + 1}
        ).status_code
        == 409
    )


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


def test_full_demo_flow_and_repeat_send(client):
    client.app.state.gmail.client = Mock(side_effect=AssertionError("No Gmail in demo"))
    row = draft(client)
    url = f"/api/decisions/{row['id']}"
    response = client.patch(
        url + "/draft", json={"draft": "DziÄ™kujÄ™, potwierdzam warunki.", "version": row["version"]}
    )
    assert response.status_code == 200
    edited = response.json()
    assert edited["draft"] == "DziÄ™kujÄ™, potwierdzam warunki."
    # A confirmation from before the edit cannot send newer, unseen text.
    assert client.post(url + "/send", json={"confirmed": True, "version": row["version"]}).status_code == 409
    response = client.post(url + "/send", json={"confirmed": True, "version": edited["version"]})
    assert response.status_code == 200
    final = response.json()
    assert final["status"] == "demo_completed"
    assert final["sent_at"] is None and final["send_attempted_at"] is None
    assert not client.app.state.gmail.client.called
    assert client.get(url).json()["draft"] == edited["draft"]
    assert (
        client.post(url + "/send", json={"confirmed": True, "version": final["version"]}).status_code == 409
    )
    assert (
        client.post(url + "/choice", json={"choice": "reject", "version": final["version"]}).status_code
        == 409
    )


def test_empty_draft_and_wrong_version(client):
    row = draft(client)
    url = f"/api/decisions/{row['id']}/draft"
    assert client.patch(url, json={"draft": "  ", "version": row["version"]}).status_code == 422
    assert client.patch(url, json={"draft": "Hello", "version": 1}).status_code == 409


def test_reset_only_removes_demo(client):
    state = client.app.state
    message, analysis = next(fixtures())
    message = message.model_copy(update={"gmail_message_id": "actual-email"})
    state.ingestion.analyzer.analyze = Mock(return_value=analysis)
    with state.sessions() as session:
        real, _ = state.ingestion.ingest(session, message)
        real_id = real.id
    assert client.get(f"/api/decisions/{real_id}").status_code == 404
    assert client.post("/api/demo/reset").json()["created"] == 4
    with state.sessions() as session:
        assert session.get(Decision, real_id)
        assert len(session.scalars(select(Decision)).all()) == 5


def test_demo_blocks_gmail_oauth_and_unconfigured_push(client):
    assert client.post("/api/gmail/sync").status_code == 400
    assert client.post("/api/oauth/gmail/start").status_code == 400
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
    assert client.post("/api/demo/reset", headers={"X-Decidr-Client": ""}).status_code == 403
    assert client.post("/api/demo/reset", headers={"Origin": "https://evil.example"}).status_code == 403
    # Same Host the request hit is allowed even when FRONTEND_URL differs (ngrok / tunnel).
    assert (
        client.post(
            "/api/demo/reset",
            headers={"Origin": "http://testserver", "Host": "testserver"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/demo/reset",
            headers={
                "Origin": "https://tunnel.example",
                "Host": "tunnel.example",
                "X-Forwarded-Proto": "https",
            },
        ).status_code
        == 200
    )


def test_parallel_confirmations_complete_once(client):
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
        assert client.post("/api/demo/reset").status_code == 400
        assert client.get("/api/oauth/gmail/callback?state=forged&code=fake").status_code == 400
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
            row.is_demo = False
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
