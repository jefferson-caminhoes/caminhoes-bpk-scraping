import pytest
from unittest.mock import patch, MagicMock
from src.scraping.http_scraper import scrape_url, ScrapeResult


def _mock_response(status: int, html: str):
    r = MagicMock()
    r.status_code = status
    r.text = html
    if status >= 400:
        import httpx
        r.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status}", request=MagicMock(), response=MagicMock(status_code=status)
        )
    else:
        r.raise_for_status = MagicMock()
    return r


def test_scrape_success_returns_html():
    mock_resp = _mock_response(200, "<html><body>Protocolo 12345</body></html>")
    with patch("httpx.get", return_value=mock_resp):
        result = scrape_url("https://example.com")

    assert result.success is True
    assert "Protocolo 12345" in result.raw_html
    assert result.http_status == 200
    assert result.error_type is None


def test_scrape_empty_response_returns_error():
    mock_resp = _mock_response(200, "")
    with patch("httpx.get", return_value=mock_resp):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "HTML_EMPTY"


def test_scrape_404_returns_site_unavailable():
    mock_resp = _mock_response(404, "Not Found")
    with patch("httpx.get", return_value=mock_resp):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "SITE_UNAVAILABLE"


def test_scrape_timeout_returns_timeout_error():
    import httpx
    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "SCRAPING_TIMEOUT"


def test_scrape_connection_error_returns_site_unavailable():
    import httpx
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = scrape_url("https://example.com")

    assert result.success is False
    assert result.error_type == "SITE_UNAVAILABLE"
