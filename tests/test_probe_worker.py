# tests/test_probe_worker.py
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
                "step": 1, "type": "get",
                "url": "{base_url}/consulta?p={protocol_number}",
                "headers": {}, "form_data": {}, "json_body": None,
                "extract": [], "result_selector": None, "is_result_step": True,
            }
        ],
        "confidence": 0.9,
        "notes": "test probe",
        "analyzed_at": "2026-05-21T00:00:00+00:00",
    }


def _make_method():
    m = MagicMock()
    m.delivery_tag = 1
    return m


@patch("src.workers.probe_worker.get_channel")
@patch("src.workers.probe_worker.analyze_url")
@patch("src.workers.probe_worker.get_db")
def test_handle_probe_job_success(mock_get_db, mock_analyze, mock_get_channel):
    from src.scraping.probe_schema import SiteProbe
    mock_analyze.return_value = SiteProbe(**_valid_probe_dict())

    mock_stakeholders = MagicMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_stakeholders
    mock_get_db.return_value = mock_db

    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    from src.workers.probe_worker import handle_probe_job
    handle_probe_job({"stakeholder_id": "stake_1", "url": "https://portal.com"}, _make_method())

    mock_analyze.assert_called_once_with("https://portal.com")
    mock_stakeholders.update_one.assert_called_once()
    update_call = mock_stakeholders.update_one.call_args
    assert "site_probe" in str(update_call)
    mock_channel.basic_ack.assert_called_once()


@patch("src.workers.probe_worker.get_channel")
@patch("src.workers.probe_worker.get_db")
def test_handle_probe_job_missing_url(mock_get_db, mock_get_channel):
    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    from src.workers.probe_worker import handle_probe_job
    handle_probe_job({"stakeholder_id": "stake_1"}, _make_method())

    mock_channel.basic_ack.assert_called_once()


@patch("src.workers.probe_worker.get_channel")
@patch("src.workers.probe_worker.analyze_url")
@patch("src.workers.probe_worker.get_db")
def test_handle_probe_job_analysis_failure_gives_ack(mock_get_db, mock_analyze, mock_get_channel):
    mock_analyze.side_effect = ValueError("JSON inválido")
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = MagicMock()
    mock_get_db.return_value = mock_db

    mock_channel = MagicMock()
    mock_get_channel.return_value = mock_channel

    from src.workers.probe_worker import handle_probe_job
    handle_probe_job({"stakeholder_id": "s1", "url": "https://broken.com"}, _make_method())

    mock_channel.basic_ack.assert_called_once()
