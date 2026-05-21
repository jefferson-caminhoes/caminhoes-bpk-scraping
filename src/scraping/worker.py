from src.config.settings import settings
from src.database.client import get_db
from src.database.repositories.scraped_contents import ScrapedContentsRepository
from src.database.repositories.consultation_jobs import ConsultationJobsRepository
from src.queues.consumer import consume
from src.queues.publisher import publish_message
from src.scraping.adapters.dynamic import DynamicAdapter
from src.scraping.adapters.registry import get_adapter
from src.scraping.fetcher import fetch_scraping_target
from src.scraping.http_scraper import scrape_url
from src.shared.errors import publish_failure
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handle_scraping_job(payload: dict, method) -> None:
    from src.queues.connection import get_channel

    job_id = payload.get("job_id", "")
    protocol_id = payload.get("protocol_id", "")
    stakeholder_id = payload.get("stakeholder_id", "")

    if not all([job_id, protocol_id, stakeholder_id]):
        logger.error(f"Invalid scraping job payload: {payload}")
        publish_failure(
            job_id=job_id,
            protocol_id=protocol_id,
            stage="scraping",
            error_type="VALIDATION_FAILED",
            error_message=f"Missing required fields in payload: {payload}",
        )
        get_channel().basic_ack(delivery_tag=method.delivery_tag)
        return

    db = get_db()
    jobs_repo = ConsultationJobsRepository(db["consultation_jobs"])
    contents_repo = ScrapedContentsRepository(db["scraped_contents"])

    try:
        jobs_repo.update_status(job_id, "scraping_running")

        target = fetch_scraping_target(db, protocol_id, stakeholder_id, job_id)
        logger.info(f"Scraping {target.resolved_url} for job {job_id}")

        if target.adapter_type == "dynamic" and target.site_probe is not None:
            adapter = DynamicAdapter(target.site_probe)
        else:
            adapter = get_adapter(target.adapter_type)
        result = adapter.scrape(target) or scrape_url(target.resolved_url)

        if not result.success:
            jobs_repo.update_status(job_id, "failed")
            publish_failure(
                job_id=job_id,
                protocol_id=protocol_id,
                stage="scraping",
                error_type=result.error_type or "UNKNOWN_ERROR",
                error_message=result.error_message or "Scraping failed",
            )
            get_channel().basic_ack(delivery_tag=method.delivery_tag)
            return

        content_id = contents_repo.save_raw_content(
            job_id=job_id,
            protocol_id=protocol_id,
            stakeholder_id=stakeholder_id,
            raw_html=result.raw_html,
            http_status=result.http_status,
            request_url=target.resolved_url,
        )

        jobs_repo.update_status(job_id, "scraping_completed")
        logger.info(f"HTML saved as content {content_id} for job {job_id}")

        publish_message(
            "ai.extraction.jobs",
            {
                "job_id": job_id,
                "protocol_id": protocol_id,
                "stakeholder_id": stakeholder_id,
                "content_id": content_id,
            },
        )
        jobs_repo.update_status(job_id, "ai_pending")

    except ValueError as e:
        logger.warning(f"Business rule violation for job {job_id}: {e}")
        jobs_repo.update_status(job_id, "ignored")
        publish_failure(
            job_id=job_id,
            protocol_id=protocol_id,
            stage="scraping",
            error_type="VALIDATION_FAILED",
            error_message=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error in scraping job {job_id}")
        jobs_repo.update_status(job_id, "failed")
        publish_failure(
            job_id=job_id,
            protocol_id=protocol_id,
            stage="scraping",
            error_type="UNKNOWN_ERROR",
            error_message=str(e),
        )
    finally:
        get_channel().basic_ack(delivery_tag=method.delivery_tag)


def run():
    logger.info("Starting scraping worker")
    consume("scraping.jobs", handle_scraping_job)
