import logging
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.db.models import Decision, utcnow
from app.services import safety
from app.services.analyzer import fallback
from app.services.demo import DEMO_SENDERS

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, settings, sessions, analyzer, gmail, push):
        self.settings = settings
        self.sessions = sessions
        self.analyzer = analyzer
        self.gmail = gmail
        self.push = push
        self.sync_lock = Lock()
        self.last_sync_at = None
        self.last_sync_error = None

    def ingest(self, session, message, is_demo=False, fixture_analysis=None):
        existing = session.scalar(
            select(Decision).where(Decision.gmail_message_id == message.gmail_message_id)
        )
        if existing:
            return existing, False
        # Fixture extraction is used ONLY for explicit demo messages, never for live email.
        try:
            analysis = fixture_analysis if is_demo else self.analyzer.analyze(message)
            if analysis is None:
                raise ValueError("Missing extraction")
        except Exception:
            analysis = fallback(message, "Błąd analizy AI")
        classification, reasons = safety.evaluate(
            analysis, message, self.settings, DEMO_SENDERS if is_demo else None
        )
        values = analysis.model_dump(exclude={"classification", "sender_name", "is_binary"})
        decision = Decision(
            **values,
            gmail_message_id=message.gmail_message_id,
            gmail_thread_id=message.gmail_thread_id,
            rfc_message_id=message.rfc_message_id,
            references=message.references,
            sender_name=message.sender_name,
            sender_email=message.sender_email,
            subject=message.subject,
            received_at=message.received_at,
            original_body=message.body,
            classification=classification,
            safety_reasons=reasons,
            is_demo=is_demo,
            status="analyzed",
        )
        decision.status = "pending" if classification == "microdecision" else "review_required"
        session.add(decision)
        try:
            session.commit()  # Persist the unique message ID before any notification.
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(Decision).where(Decision.gmail_message_id == message.gmail_message_id)
            )
            if existing is None:
                raise
            return existing, False
        if decision.status == "pending":
            try:
                self.push.notify(decision.id)
            except Exception as exc:
                logger.warning("Push failed without affecting ingestion: %s", type(exc).__name__)
        return decision, True

    def sync(self):
        if self.settings.app_mode != "live":
            raise DomainError("Synchronizacja Gmaila jest wyłączona w demo.", 400)
        if not self.sync_lock.acquire(blocking=False):
            raise DomainError("Synchronizacja już trwa.")
        try:
            imported = 0
            with self.sessions() as session:
                for message in self.gmail.fetch_messages(session):
                    _, is_new = self.ingest(session, message)
                    imported += int(is_new)
            self.last_sync_at = utcnow().isoformat()
            self.last_sync_error = None
            return {"imported": imported, "synced_at": self.last_sync_at}
        except DomainError as exc:
            self.last_sync_error = exc.message
            raise
        except Exception as exc:
            logger.warning("Sync failed: %s", type(exc).__name__)
            self.last_sync_error = "Synchronizacja nie powiodła się. Sprawdź połączenie z Gmail."
            raise DomainError(self.last_sync_error, 502) from exc
        finally:
            self.sync_lock.release()
