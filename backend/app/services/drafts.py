from datetime import date, datetime
from zoneinfo import ZoneInfo
import re

from sqlalchemy import select, update

from app.core.errors import DomainError
from app.db.models import Decision, utcnow

# Soft-hidden: analyzer noise + user "don't reply". Kept so Gmail sync won't re-import.
HIDDEN_STATUSES = ("skipped", "dismissed")

_CLOSING_HEAD = re.compile(
    r"^(?:"
    r"pozdrawiam(?:\s+serdecznie)?"
    r"|z\s+poważaniem"
    r"|serdecznie\s+pozdrawiam"
    r"|z\s+serdecznymi\s+pozdrowieniami"
    r"|best\s+regards"
    r"|kind\s+regards"
    r"|sincerely"
    r")\s*,?\s*$",
    re.IGNORECASE,
)
_NAME_PLACEHOLDER = re.compile(r"^\[(?:[^\]]{0,80})\]\s*$")
_SHORT_NAME_LINE = re.compile(
    r"^[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż'’.\-]{0,40}"
    r"(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż'’.\-]{0,40}){0,3}\s*$"
)


def strip_llm_closing(draft: str) -> str:
    """Remove LLM farewell / name placeholders so the configured signature can be appended once."""
    text = draft.strip()
    while text:
        parts = re.split(r"\n\s*\n", text)
        if len(parts) < 2:
            # Single trailing line: Pozdrawiam, / [Twoje imię]
            lines = text.rsplit("\n", 1)
            if len(lines) == 2 and (
                _CLOSING_HEAD.match(lines[1].strip()) or _NAME_PLACEHOLDER.match(lines[1].strip())
            ):
                text = lines[0].rstrip()
                continue
            break
        tail = parts[-1].strip()
        tail_lines = [line.strip() for line in tail.splitlines() if line.strip()]
        if not tail_lines:
            text = "\n\n".join(parts[:-1]).rstrip()
            continue
        head = tail_lines[0]
        rest = tail_lines[1:]
        if _CLOSING_HEAD.match(head) and (
            not rest
            or (
                len(rest) == 1
                and (_NAME_PLACEHOLDER.match(rest[0]) or _SHORT_NAME_LINE.match(rest[0]))
            )
        ):
            text = "\n\n".join(parts[:-1]).rstrip()
            continue
        if len(tail_lines) == 1 and _NAME_PLACEHOLDER.match(tail_lines[0]):
            text = "\n\n".join(parts[:-1]).rstrip()
            continue
        break
    return text


def append_signature(draft: str, settings) -> str:
    signature = (settings.email_signature or "Z poważaniem").strip()
    text = strip_llm_closing(draft)
    if not signature or text.endswith(signature):
        return text
    return f"{text}\n\n{signature}"


def visible_filter():
    return Decision.status.notin_(HIDDEN_STATUSES)


def get_decision(session, decision_id, settings):
    decision = session.scalar(
        select(Decision).where(
            Decision.id == decision_id,
            Decision.is_demo.is_(settings.app_mode == "demo"),
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
        draft = append_signature(draft, settings)
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
            "Nie udało się potwierdzić wysyłki. Otwórz Gmail i sprawdź ten wątek — "
            "Decidr nie ponawia wysyłki automatycznie."
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
