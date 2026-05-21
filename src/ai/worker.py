from src.database.client import get_db
from src.database.repositories.scraped_contents import ScrapedContentsRepository
from src.database.repositories.consultation_jobs import ConsultationJobsRepository
from src.queues.consumer import consume
from src.queues.publisher import publish_message
from src.cleaner.html_cleaner import clean_html
from src.cleaner.sufficiency_checker import is_sufficient
from src.ai.ollama_client import call_ollama
from src.ai.prompts import build_extraction_prompt, build_correction_prompt
from src.ai.json_validator import extract_json_from_text, validate_extraction_result
from src.ai.deterministic_extractors import try_extract_deterministic
from src.shared.api_client import deliver_extraction_result
from src.shared.errors import publish_failure
from src.shared.logger import get_logger

logger = get_logger(__name__)


def handle_ai_extraction_job(payload: dict, method) -> None:
    from src.queues.connection import get_channel

    job_id = payload.get("job_id", "")
    protocol_id = payload.get("protocol_id", "")
    stakeholder_id = payload.get("stakeholder_id", "")
    content_id = payload.get("content_id", "")

    if not all([job_id, protocol_id, stakeholder_id, content_id]):
        publish_failure(
            job_id=job_id, protocol_id=protocol_id,
            stage="ai_extraction", error_type="VALIDATION_FAILED",
            error_message=f"Missing fields: {payload}",
        )
        get_channel().basic_ack(delivery_tag=method.delivery_tag)
        return

    db = get_db()
    jobs_repo = ConsultationJobsRepository(db["consultation_jobs"])
    contents_repo = ScrapedContentsRepository(db["scraped_contents"])

    try:
        jobs_repo.update_status(job_id, "ai_running")

        content = contents_repo.get_by_id(content_id)
        if not content:
            raise ValueError(f"Content {content_id} not found")

        clean_text = content.get("clean_text")
        if not clean_text:
            clean_text = clean_html(content.get("raw_html", ""))
            if clean_text:
                contents_repo.update_clean_text(content_id, clean_text, "generic_html_text_extractor")

        if not is_sufficient(clean_text):
            raise ValueError("Clean text is insufficient for extraction")

        protocol = db["protocols"].find_one({"_id": protocol_id}) or {}
        stakeholder = db["stakeholders"].find_one({"_id": stakeholder_id}) or {}

        data = try_extract_deterministic(
            stakeholder=stakeholder,
            clean_text=clean_text,
            protocol_number=protocol.get("protocol_number", ""),
            cnpj=protocol.get("cnpj"),
        )
        if data is None:
            prompt = build_extraction_prompt(
                clean_text=clean_text,
                protocol_number=protocol.get("protocol_number", ""),
                cnpj=protocol.get("cnpj"),
                stakeholder_name=stakeholder.get("name", ""),
            )

            raw_response = call_ollama(prompt)

            # Try to parse, with one correction retry
            try:
                data = extract_json_from_text(raw_response)
            except ValueError:
                logger.warning(f"First parse failed for job {job_id}, retrying with correction prompt")
                correction_prompt = build_correction_prompt(raw_response)
                raw_response = call_ollama(correction_prompt)
                data = extract_json_from_text(raw_response)  # Raises if still fails

        result = validate_extraction_result(data)
        jobs_repo.update_status(job_id, "ai_completed")

        result_payload = {
            "job_id": job_id,
            "protocol_id": protocol_id,
            "stakeholder_id": stakeholder_id,
            **result.model_dump(),
        }

        publish_message("ai.extraction.results", result_payload)

        try:
            deliver_extraction_result(result_payload)
        except Exception as e:
            logger.error(f"API delivery failed for job {job_id}: {e}")
            publish_failure(
                job_id=job_id, protocol_id=protocol_id,
                stage="api_delivery", error_type="API_DELIVERY_FAILED",
                error_message=str(e),
            )

        jobs_repo.update_status(job_id, "completed")

    except Exception as e:
        logger.exception(f"AI extraction failed for job {job_id}: {e}")
        jobs_repo.update_status(job_id, "failed")
        publish_failure(
            job_id=job_id, protocol_id=protocol_id,
            stage="ai_extraction", error_type="AI_EXTRACTION_FAILED",
            error_message=str(e),
        )
    finally:
        get_channel().basic_ack(delivery_tag=method.delivery_tag)


def run():
    logger.info("Starting AI extraction worker")
    consume("ai.extraction.jobs", handle_ai_extraction_job)
