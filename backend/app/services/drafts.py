from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from app.core.errors import DomainError
from app.db.models import Decision, utcnow


def get_decision(session, decision_id, settings):
    decision = session.scalar(
        select(Decision).where(Decision.id == decision_id, Decision.is_demo.is_(settings.app_mode == "demo"))
    )
    if decision is None:
        raise DomainError("Nie znaleziono sprawy.", 404)
    return decision


def writable(decision, status, version):
    if decision.classification != "microdecision" or decision.status != status:
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


def choose(session, decision, choice, version):
    writable(decision, "pending", version)
    answer = (
        "Wyrażam zgodę na poniższą prośbę."
        if choice == "approve"
        else "Nie wyrażam zgody na poniższą prośbę."
    )
    # Deterministic drafting: no new facts or promises invented by a second model call.
    draft = f"Dzień dobry,\n\n{answer}\n\n{decision.request_text}"
    if decision.conditions:
        draft += "\n\nWarunki opisane w prośbie:\n" + "\n".join(f"• {c}" for c in decision.conditions)
    draft += "\n\nPozdrawiam"
    return update_versioned(session, decision, version, user_choice=choice, draft=draft, status="draft_ready")


def edit(session, decision, draft, version):
    writable(decision, "draft_ready", version)
    return update_versioned(session, decision, version, draft=draft)


def send(session, decision, confirmed, version, settings, gmail):
    if confirmed is not True:
        raise DomainError("Wymagane jest osobne potwierdzenie wysyłki.", 422)
    writable(decision, "draft_ready", version)
    if not decision.draft or not decision.draft.strip():
        raise DomainError("Draft nie może być pusty.")
    if (
        decision.deadline
        and date.fromisoformat(decision.deadline) < datetime.now(ZoneInfo("Europe/Warsaw")).date()
    ):
        raise DomainError("Termin już minął. Sprawdź oryginalną wiadomość zamiast wysyłać odpowiedź.")
    if decision.amount is not None and (
        decision.amount > settings.max_amount or decision.currency != settings.allowed_currency
    ):
        raise DomainError("Sprawa przekracza aktualny limit kwoty lub waluty.")
    if not decision.is_demo and decision.sender_email.lower() not in settings.senders:
        raise DomainError("Nadawca nie znajduje się już na liście znanych nadawców.")
    if decision.is_demo:
        # Deliberately before any Gmail access. sent_at remains NULL.
        return update_versioned(session, decision, version, status="demo_completed")
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
