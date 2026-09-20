import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.errors import DomainError

logger = logging.getLogger(__name__)


def start_scheduler(settings, ingestion):
    if not settings.scheduler_enabled or settings.app_mode != "live":
        return None
    scheduler = BackgroundScheduler(timezone="UTC")

    def sync():
        try:
            ingestion.sync()
        except DomainError as exc:
            logger.warning("Scheduled sync did not complete: %s", exc.message)
        except Exception as exc:
            logger.warning("Scheduled sync did not complete: %s", type(exc).__name__)

    scheduler.add_job(
        sync,
        "interval",
        seconds=settings.sync_interval_seconds,
        id="gmail-sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    scheduler.start()
    return scheduler
