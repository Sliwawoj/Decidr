import logging
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.db.models import Decision, utcnow
from app.services.gmail import RATE_LIMIT_FALLBACK

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
        self.rate_limited_until = None

    def ingest(self, session, message, is_demo=False, fixture_analysis=None):
        existing = session.scalar(
            select(Decision).where(Decision.gmail_message_id == message.gmail_message_id)
        )
        if existing:
            return existing, False
        analysis = fixture_analysis if is_demo else self.analyzer.analyze(message)
        if analysis is None:
            raise ValueError("Missing extraction")

        queued = analysis.classification in {"needs_reply", "needs_review"}
        notes = list(dict.fromkeys([*analysis.warnings, *analysis.risk_flags]))
        values = analysis.model_dump(
            exclude={"classification", "sender_name", "is_binary", "warnings", "push_text", "draft"}
        )
        draft = (analysis.draft or "").strip()
        if analysis.classification == "needs_review" and not draft:
            draft = self.analyzer.suggest_review_draft(
                analysis, original_body=message.body, subject=message.subject
            )
        if analysis.classification == "needs_review":
            status = "draft_ready"
        elif queued:
            status = "pending"
        else:
            status = "skipped"
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
            classification=analysis.classification,
            safety_reasons=notes,
            is_demo=is_demo,
            status=status,
            draft=draft or None,
        )
        session.add(decision)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(Decision).where(Decision.gmail_message_id == message.gmail_message_id)
            )
            if existing is None:
                raise
            return existing, False
        if queued:
            try:
                blurb = (analysis.push_text or analysis.request_text or decision.subject or "").strip()
                self.push.notify(decision.id, blurb[:120] or None)
            except Exception as exc:
                logger.warning("Push failed without affecting ingestion: %s", type(exc).__name__)
        return decision, queued

    def _still_rate_limited(self):
        if self.rate_limited_until is None:
            return False
        return utcnow() < self.rate_limited_until

    def sync(self):
        if self.settings.app_mode != "live":
            raise DomainError("Synchronizacja Gmaila jest wyłączona w demo.", 400)
        if self._still_rate_limited():
            raise DomainError(
                self.last_sync_error
                or "Gmail ograniczył zapytania (limit). Synchronizacja wznowi się automatycznie za kilka minut.",
                429,
                retry_after=self.rate_limited_until,
            )
        if not self.sync_lock.acquire(blocking=False):
            raise DomainError("Synchronizacja już trwa.")
        try:
            imported = 0
            with self.sessions() as session:
                for message in self.gmail.fetch_messages(session):
                    _, queued = self.ingest(session, message)
                    imported += int(queued)
            self.last_sync_at = utcnow().isoformat()
            self.last_sync_error = None
            self.rate_limited_until = None
            return {"imported": imported, "synced_at": self.last_sync_at}
        except DomainError as exc:
            self.last_sync_error = exc.message
            if exc.status_code == 429:
                self.rate_limited_until = exc.retry_after or (utcnow() + RATE_LIMIT_FALLBACK)
            raise
        except Exception as exc:
            logger.warning("Sync failed: %s: %s", type(exc).__name__, str(exc)[:300])
            self.last_sync_error = "Synchronizacja nie powiodła się. Sprawdź połączenie z Gmail."
            raise DomainError(self.last_sync_error, 502) from exc
        finally:
            self.sync_lock.release()
