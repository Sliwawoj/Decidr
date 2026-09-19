import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import PushSubscription

logger = logging.getLogger(__name__)


class PushService:
    def __init__(self, settings, sessions):
        self.settings = settings
        self.sessions = sessions

    def subscribe(self, session, subscription):
        existing = session.scalar(
            select(PushSubscription).where(PushSubscription.endpoint == subscription.endpoint)
        )
        if existing:
            existing.keys = subscription.keys.model_dump()
        else:
            session.add(PushSubscription(endpoint=subscription.endpoint, keys=subscription.keys.model_dump()))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()  # Another tab may have just saved the same subscription.

    def notify(self, decision_id, body: str | None = None):
        if not self.settings.push_configured:
            return
        # Short decision blurb only — no sender address or full email body on the lock screen.
        text = (body or "").strip() or "Nowa sprawa czeka na Twój wybór."
        payload = json.dumps(
            {
                "title": "Decidr · nowa decyzja",
                "body": text[:120],
                "url": f"/decisions/{decision_id}",
            }
        )
        with self.sessions() as session:
            for subscription in session.scalars(select(PushSubscription)).all():
                try:
                    webpush(
                        subscription_info={"endpoint": subscription.endpoint, "keys": subscription.keys},
                        data=payload,
                        vapid_private_key=self.settings.vapid_private_key,
                        vapid_claims={"sub": self.settings.vapid_subject},
                        timeout=8,
                        ttl=300,
                    )
                except WebPushException as exc:
                    status = exc.response.status_code if exc.response is not None else None
                    if status in (404, 410):
                        session.delete(subscription)
                    else:
                        logger.warning("Push delivery failed (HTTP %s): %s", status, exc)
                except Exception as exc:
                    logger.warning("Push configuration or delivery failed: %s", exc)
            session.commit()
