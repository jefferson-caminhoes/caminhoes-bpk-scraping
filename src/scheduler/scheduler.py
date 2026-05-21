from apscheduler.schedulers.blocking import BlockingScheduler
from src.config.settings import settings
from src.database.client import get_db
from src.queues.publisher import publish_message
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _create_scraping_jobs() -> None:
    db = get_db()
    protocols = list(
        db["protocols"].find(
            {
                "monitoring_enabled": True,
                "active": True,
                "closed_manually": {"$ne": True},
            },
            {"_id": 1, "stakeholder_id": 1},
        )
    )

    if not protocols:
        logger.info("No monitorable protocols found")
        return

    published = 0
    for protocol in protocols:
        stakeholder_id = protocol.get("stakeholder_id")
        if not stakeholder_id:
            continue

        stakeholder = db["stakeholders"].find_one(
            {"_id": stakeholder_id, "active": True}, {"_id": 1}
        )
        if not stakeholder:
            continue

        from datetime import datetime, timezone
        job_id = f"auto_{protocol['_id']}_{int(datetime.now(timezone.utc).timestamp())}"

        publish_message(
            "scraping.jobs",
            {
                "job_id": job_id,
                "protocol_id": str(protocol["_id"]),
                "stakeholder_id": str(stakeholder_id),
            },
        )
        published += 1

    logger.info(f"Scheduler published {published} scraping jobs")


def run():
    logger.info(f"Starting scheduler with cron: {settings.scraping_cron}")
    scheduler = BlockingScheduler()
    parts = settings.scraping_cron.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "*/30", "*", "*", "*", "*"

    scheduler.add_job(
        _create_scraping_jobs,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
