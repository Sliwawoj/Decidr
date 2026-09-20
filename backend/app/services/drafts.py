from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from app.core.errors import DomainError
from app.db.models import Decision, utcnow

# Soft-hidden: analyzer noise + user "don't reply". Kept so Gmail sync won't re-import.
HIDDEN_STATUSES = ("skipped", "dismissed")


def visible_filter():
    return Decision.status.notin_(HIDDEN_STATUSES)


def get_decision(session, decision_id, settings):
    decision = session.scalar(
        select(Decision).where(
            Decision.id == decision_id,
            visible_filter(),
        )
    )
    if decision is None:
        raise DomainError("Nie znaleziono sprawy.", 404)
    return decision


def writable(decision, status, version, *, classifications=("needs_reply",)):
    if decision.classification not in classifications or decision.status != status:
        raise DomainError("Ta sprawa nie pozwala na taką zmianę stanu.")
    if decision.version != version:
        raise DomainError("Sprawa zmieniła się w innej karcie. Odśwież widok.")
    if decision.send_attempted_at:
        raise DomainError("Wysyłka była już rozpoczęta. Sprawdź oryginalny wątek w Gmail.")


def update_versioned(session, decision, version, **values):
    result = session.execute(
        update(Decision)
        .where(Decision.id == decision.id, Decision.version == version, Decision.send_attempted_at.is_(None))
        .values(**values, version=version + 1, updated_at=utcnow())
    )
    if result.rowcount != 1:
        session.rollback()
        raise DomainError("Sprawa zmieniła się w innej karcie. Odśwież widok.")
    session.commit()
    session.refresh(decision)
    return decision


def _append_signature(draft: str, settings) -> str:
    signature = (settings.email_signature or "Z poważaniem").strip()
    if not signature:
        return draft.strip()
    return f"{draft.strip()}\n\n{signature}".strip()


def choose(session, decision, choice, version, analyzer=None, settings=None):
    writable(decision, "pending", version, classifications=("needs_reply",))
    if analyzer is not None:
        draft = analyzer.suggest_draft(decision, choice)
    else:
        answer = (
            "Wyrażam zgodę na poniższą prośbę."
            if choice == "approve"
            else "Nie wyrażam zgody na poniższą prośbę."
        )
        draft = f"Dzień dobry,\n\n{answer}\n\n{decision.request_text}"
    if settings is not None:
        draft = _append_signature(draft, settings)
    return update_versioned(session, decision, version, user_choice=choice, draft=draft, status="draft_ready")


def dismiss(session, decision, version):
    """Remove from queue without sending a reply. Distinct from reject (which drafts a refusal)."""
    if decision.classification not in ("needs_reply", "needs_review"):
        raise DomainError("Ta sprawa nie pozwala na taką zmianę stanu.")
    if decision.status not in ("pending", "draft_ready"):
        raise DomainError("Ta sprawa nie pozwala na taką zmianę stanu.")
    if decision.version != version:
        raise DomainError("Sprawa zmieniła się w innej karcie. Odśwież widok.")
    if decision.send_attempted_at:
        raise DomainError("Wysyłka była już rozpoczęta. Sprawdź oryginalny wątek w Gmail.")
    return update_versioned(session, decision, version, status="dismissed")


def edit(session, decision, draft, version):
    writable(decision, "draft_ready", version, classifications=("needs_reply", "needs_review"))
    return update_versioned(session, decision, version, draft=draft)


def send(session, decision, confirmed, version, settings, gmail):
    if confirmed is not True:
        raise DomainError("Wymagane jest osobne potwierdzenie wysyłki.", 422)
    writable(decision, "draft_ready", version, classifications=("needs_reply", "needs_review"))
    if not decision.draft or not decision.draft.strip():
        raise DomainError("Draft nie może być pusty.")
    if decision.deadline and date.fromisoformat(decision.deadline) < datetime.now(
        ZoneInfo("Europe/Warsaw")
    ).date():
        raise DomainError("Termin już minął. Sprawdź oryginalną wiadomość zamiast wysyłać odpowiedź.")
    if settings.app_mode != "live":
        raise DomainError("Prawdziwa wysyłka jest wyłączona.", 403)

    # Persist an atomic claim before the network call. A second click/restart cannot resend.
    # A timeout may mean Google accepted the mail: never retry automatically.
    client = gmail.client(session)
    update_versioned(session, decision, version, send_attempted_at=utcnow())
    try:
        reply_id = gmail.send_reply(client, decision)
    except Exception as exc:
        decision.send_error = (
            "Nie można potwierdzić wyniku wysyłki. Sprawdź wątek w Gmail; nie ponawiamy automatycznie."
        )
        session.commit()
        raise DomainError(decision.send_error, 502) from exc
    decision.status = "sent"
    decision.sent_at = utcnow()
    decision.gmail_reply_id = reply_id
    decision.version += 1
    session.commit()
    session.refresh(decision)
    return decision
