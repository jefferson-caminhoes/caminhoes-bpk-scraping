import json
from unittest.mock import MagicMock, patch
from src.queues.schemas import (
    ScrapingJobMessage,
    AiExtractionJobMessage,
    FailedJobMessage,
)
from src.queues.publisher import publish_message


def test_scraping_job_message_schema():
    msg = ScrapingJobMessage(
        job_id="job_1",
        protocol_id="prot_1",
        stakeholder_id="stake_1",
    )
    assert msg.job_id == "job_1"
    d = msg.model_dump()
    assert set(d.keys()) == {"job_id", "protocol_id", "stakeholder_id"}


def test_ai_extraction_job_message_schema():
    msg = AiExtractionJobMessage(
        job_id="job_1",
        protocol_id="prot_1",
        stakeholder_id="stake_1",
        content_id="content_1",
    )
    assert msg.content_id == "content_1"


def test_failed_job_message_has_required_fields():
    msg = FailedJobMessage(
        job_id="job_1",
        protocol_id="prot_1",
        stage="scraping",
        error_type="SCRAPING_TIMEOUT",
        error_message="Timeout ao consultar site",
    )
    assert msg.stage == "scraping"
    assert msg.error_type == "SCRAPING_TIMEOUT"


def test_publish_message_calls_basic_publish():
    mock_channel = MagicMock()
    with patch("src.queues.publisher.get_channel", return_value=mock_channel):
        publish_message("scraping.jobs", {"job_id": "j1"})

    mock_channel.basic_publish.assert_called_once()
    args = mock_channel.basic_publish.call_args[1]
    assert args["routing_key"] == "scraping.jobs"
    body = json.loads(args["body"])
    assert body["job_id"] == "j1"


def test_publish_failure_sends_to_failed_jobs():
    import json
    from unittest.mock import MagicMock, patch
    mock_channel = MagicMock()
    with patch("src.queues.publisher.get_channel", return_value=mock_channel):
        from src.shared.errors import publish_failure
        publish_failure(
            job_id="job_1",
            protocol_id="prot_1",
            stage="scraping",
            error_type="SCRAPING_TIMEOUT",
            error_message="Timeout ao consultar site",
        )

    mock_channel.basic_publish.assert_called_once()
    args = mock_channel.basic_publish.call_args[1]
    assert args["routing_key"] == "failed.jobs"
    body = json.loads(args["body"])
    assert body["error_type"] == "SCRAPING_TIMEOUT"
    assert body["stage"] == "scraping"
