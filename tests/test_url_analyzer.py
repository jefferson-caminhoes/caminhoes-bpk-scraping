# tests/test_url_analyzer.py
import json
import pytest
from unittest.mock import patch, MagicMock
from src.scraping.url_analyzer import analyze_url, _clean_html_for_llm, _extract_base_url


def _valid_probe_json(original_url="https://portal.com", actual_url="https://portal.com"):
    return json.dumps({
        "portal_type": "simple_get",
        "original_url": original_url,
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": False,
        "login_url": None,
        "steps": [
            {
                "step": 1,
                "type": "get",
                "url": "{base_url}/consulta?protocolo={protocol_number}",
                "headers": {},
                "form_data": {},
                "json_body": None,
                "extract": [],
                "result_selector": "div.resultado",
                "is_result_step": True,
            }
        ],
        "confidence": 0.9,
        "notes": "Simple GET with protocol number",
    })


def test_clean_html_for_llm_removes_scripts():
    html = "<html><head><script>alert('xss')</script></head><body><form><input name='prot'/></form></body></html>"
    result = _clean_html_for_llm(html)
    assert "alert" not in result
    assert "input" in result


def test_clean_html_for_llm_truncates_to_4000():
    html = "<p>" + "x" * 10000 + "</p>"
    result = _clean_html_for_llm(html)
    assert len(result) <= 4000


def test_extract_base_url():
    assert _extract_base_url("https://portal.com/path/page.jsf") == "https://portal.com"
    assert _extract_base_url("https://sub.portal.gov.br/api/v1/") == "https://sub.portal.gov.br"
    assert _extract_base_url("https://portal.com") == "https://portal.com"


@patch("src.scraping.url_analyzer.call_ollama")
@patch("src.scraping.url_analyzer.httpx.Client")
def test_analyze_url_returns_site_probe(mock_client_cls, mock_ollama):
    mock_response = MagicMock()
    mock_response.text = "<html><body><form><input name='protocolo'/></form></body></html>"
    mock_response.url = "https://portal.com/consulta"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    mock_ollama.return_value = _valid_probe_json(
        original_url="https://portal.com/consulta",
        actual_url="https://portal.com/consulta",
    )

    from src.scraping.probe_schema import SiteProbe
    probe = analyze_url("https://portal.com/consulta")

    assert isinstance(probe, SiteProbe)
    assert probe.portal_type == "simple_get"
    assert probe.auth_required is False
    assert len(probe.steps) == 1
    mock_ollama.assert_called_once()


@patch("src.scraping.url_analyzer.call_ollama")
@patch("src.scraping.url_analyzer.httpx.Client")
def test_analyze_url_detects_captcha(mock_client_cls, mock_ollama):
    mock_response = MagicMock()
    mock_response.text = "<html><body><div class='g-recaptcha'></div><form/></body></html>"
    mock_response.url = "https://portal.com/form"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    probe_with_captcha = json.dumps({
        "portal_type": "post_form",
        "original_url": "https://portal.com/form",
        "base_url": "https://portal.com",
        "auth_required": False,
        "captcha_detected": True,
        "login_url": None,
        "steps": [
            {"step": 1, "type": "post", "url": "{base_url}/form",
             "headers": {}, "form_data": {"protocolo": "{protocol_number}"},
             "json_body": None, "extract": [], "result_selector": None, "is_result_step": True}
        ],
        "confidence": 0.6,
        "notes": "Detectado reCAPTCHA",
    })
    mock_ollama.return_value = probe_with_captcha

    probe = analyze_url("https://portal.com/form")
    assert probe.captcha_detected is True


@patch("src.scraping.url_analyzer.call_ollama")
@patch("src.scraping.url_analyzer.httpx.Client")
def test_analyze_url_raises_on_invalid_llm_response(mock_client_cls, mock_ollama):
    mock_response = MagicMock()
    mock_response.text = "<html><body>Portal</body></html>"
    mock_response.url = "https://portal.com"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    mock_ollama.return_value = "resposta inválida sem JSON"

    with pytest.raises(ValueError, match="JSON"):
        analyze_url("https://portal.com")
