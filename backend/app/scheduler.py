import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


def start_scheduler(settings, ingestion):
    if not settings.scheduler_enabled or settings.app_mode != "live":
        return None
    scheduler = BackgroundScheduler(timezone="UTC")

    def sync():
        try:
            ingestion.sync()
        except Exception as exc:
            logger.warning("Scheduled sync did not complete: %s", type(exc).__name__)

    # First run immediately so a reconnect does not wait a full interval.
    scheduler.add_job(
        sync,
        "interval",
        seconds=max(15, settings.sync_interval_seconds),
        id="gmail-sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
        next_run_time=datetime.now(timezone.utc),
    )
    scheduler.start()
    return scheduler
