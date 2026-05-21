# tests/test_worker.py
from unittest.mock import patch, MagicMock


def _valid_probe_dict():
    return {
        "portal_type": "simple_get",
        "original_url": "https://portal.com",
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": False,
        "login_url": None,
        "steps": [
            {
                "step": 1,
                "type": "get",
                "url": "{base_url}/consulta?p={protocol_number}",
                "headers": {},
                "form_data": {},
                "json_body": None,
                "extract": [],
                "result_selector": None,
                "is_result_step": True,
            }
        ],
        "confidence": 0.9,
        "notes": "test probe",
        "analyzed_at": "2026-05-21T00:00:00+00:00",
    }


def _make_method():
    m = MagicMock()
    m.delivery_tag = 42
    return m


@patch("src.scraping.worker.scrape_url")
@patch("src.scraping.worker.DynamicAdapter")
@patch("src.scraping.worker.fetch_scraping_target")
@patch("src.scraping.worker.get_db")
@patch("src.scraping.worker.publish_message")
@patch("src.scraping.worker.publish_failure")
@patch("src.queues.connection.get_channel")
def test_worker_uses_dynamic_adapter_when_probe_present(
    mock_get_channel,
    mock_publish_failure,
    mock_publish_message,
    mock_get_db,
    mock_fetch,
    mock_dynamic_cls,
    mock_scrape_url,
):
    from src.scraping.probe_schema import SiteProbe

    probe = SiteProbe(**_valid_probe_dict())

    mock_target = MagicMock()
    mock_target.adapter_type = "dynamic"
    mock_target.site_probe = probe
    mock_target.stakeholder_name = "Test Stakeholder"
    mock_target.resolved_url = "https://portal.com/consulta?p=12345"
    mock_fetch.return_value = mock_target

    # Adapter returns a failed result so we don't need to set up the full
    # success path (contents repo, publish, etc.) — we only care that
    # DynamicAdapter was instantiated with the probe.
    mock_adapter_instance = MagicMock()
    mock_adapter_instance.scrape.return_value = MagicMock(
        success=False,
        error_type="PROTOCOL_NOT_FOUND",
        error_message="Not found",
    )
    mock_dynamic_cls.return_value = mock_adapter_instance

    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    # Set up db mocks for jobs_repo and contents_repo
    mock_collection = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    mock_get_db.return_value = mock_db

    payload = {
        "job_id": "job_1",
        "protocol_id": "prot_1",
        "stakeholder_id": "stake_1",
    }

    from src.scraping.worker import handle_scraping_job

    handle_scraping_job(payload, _make_method())

    # The DynamicAdapter must have been called with the probe
    mock_dynamic_cls.assert_called_once_with(probe)
    mock_adapter_instance.scrape.assert_called_once_with(mock_target)
    # Channel ack must always be called
    mock_channel.basic_ack.assert_called_once()
