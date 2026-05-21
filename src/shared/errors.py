# Error type constants
SCRAPING_TIMEOUT = "SCRAPING_TIMEOUT"
SITE_UNAVAILABLE = "SITE_UNAVAILABLE"
PROTOCOL_NOT_FOUND = "PROTOCOL_NOT_FOUND"
HTML_EMPTY = "HTML_EMPTY"
AI_EXTRACTION_FAILED = "AI_EXTRACTION_FAILED"
INVALID_JSON = "INVALID_JSON"
VALIDATION_FAILED = "VALIDATION_FAILED"
API_DELIVERY_FAILED = "API_DELIVERY_FAILED"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


def publish_failure(
    job_id: str,
    protocol_id: str,
    stage: str,
    error_type: str,
    error_message: str,
) -> None:
    from src.queues.publisher import publish_message
    from datetime import datetime, timezone

    publish_message(
        "failed.jobs",
        {
            "job_id": job_id,
            "protocol_id": protocol_id,
            "stage": stage,
            "error_type": error_type,
            "error_message": error_message,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
