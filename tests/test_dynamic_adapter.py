# tests/test_dynamic_adapter.py
import pytest
from unittest.mock import patch, MagicMock
from src.scraping.adapters.dynamic import DynamicAdapter, _interpolate, _execute_step
from src.scraping.probe_schema import SiteProbe, ProbeStep, ExtractRule
from src.scraping.fetcher import ScrapingTarget
from src.scraping.http_scraper import _HEADERS


def _make_target(protocol_number="12345", cnpj="12.345.678/0001-99"):
    return ScrapingTarget(
        job_id="job_1",
        protocol_id="prot_1",
        stakeholder_id="stake_1",
        protocol_number=protocol_number,
        cnpj=cnpj,
        stakeholder_name="Portal Test",
        stakeholder_type="dynamic",
        adapter_type="dynamic",
        requires_javascript=False,
        has_captcha=False,
        resolved_url="https://portal.com",
    )


def _make_simple_probe():
    return SiteProbe(
        portal_type="simple_get",
        original_url="https://portal.com/consulta",
        base_url="https://portal.com",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/consulta?protocolo={protocol_number}",
                is_result_step=True,
                result_selector="div#resultado",
            )
        ],
        confidence=0.9,
        notes="Simple GET",
    )


def test_interpolate_replaces_protocol_number():
    result = _interpolate("{base_url}/api?p={protocol_number}", {"base_url": "https://portal.com", "protocol_number": "12345"})
    assert result == "https://portal.com/api?p=12345"


def test_interpolate_leaves_unknown_placeholders():
    result = _interpolate("{base_url}/{unknown}", {"base_url": "https://portal.com"})
    assert result == "https://portal.com/{unknown}"


def test_interpolate_handles_extracted_vars():
    result = _interpolate("{var_viewstate}", {"var_viewstate": "abc123"})
    assert result == "abc123"


def test_dynamic_adapter_resolve_url():
    probe = _make_simple_probe()
    adapter = DynamicAdapter(probe)
    assert adapter.resolve_url("", "12345", None, None) == "https://portal.com"


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_scrape_simple_get(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = '<html><body><div id="resultado">Protocolo 12345 - Status: Concluído</div></body></html>'
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    probe = _make_simple_probe()
    adapter = DynamicAdapter(probe)
    target = _make_target()

    result = adapter.scrape(target)

    assert result.success is True
    assert "Concluído" in result.raw_html
    mock_client.get.assert_called_once_with(
        "https://portal.com/consulta?protocolo=12345",
        headers=_HEADERS,
    )


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_scrape_returns_failure_on_empty_result(mock_client_cls):
    mock_response = MagicMock()
    mock_response.text = "<html><body><div id='resultado'></div></body></html>"
    mock_response.status_code = 200

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    probe = _make_simple_probe()
    adapter = DynamicAdapter(probe)
    result = adapter.scrape(_make_target())

    assert result.success is False
    assert result.error_type == "PROTOCOL_NOT_FOUND"


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_blocks_captcha_portals(mock_client_cls):
    probe = SiteProbe(
        portal_type="post_form",
        original_url="https://portal.com",
        base_url="https://portal.com",
        auth_required=False,
        captcha_detected=True,
        steps=[
            ProbeStep(step=1, type="get", url="{base_url}/form", is_result_step=True)
        ],
        confidence=0.5,
        notes="CAPTCHA detectado",
    )
    adapter = DynamicAdapter(probe)
    result = adapter.scrape(_make_target())

    assert result.success is False
    assert result.error_type == "CAPTCHA_BLOCKED"
    mock_client_cls.assert_not_called()


@patch("src.scraping.adapters.dynamic.httpx.Client")
def test_dynamic_adapter_two_step_with_viewstate(mock_client_cls):
    probe = SiteProbe(
        portal_type="jsf_form",
        original_url="https://jsf.portal.com",
        base_url="https://jsf.portal.com",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/inicio.jsf",
                extract=[ExtractRule(name="viewstate", selector="viewstate", attribute="value")],
            ),
            ProbeStep(
                step=2,
                type="post",
                url="{base_url}/inicio.jsf",
                form_data={
                    "form:protocolo": "{protocol_number}",
                    "javax.faces.ViewState": "{var_viewstate}",
                },
                is_result_step=True,
                result_selector="div#painel",
            ),
        ],
        confidence=0.85,
        notes="JSF",
    )

    step1_html = '<html><body><input name="javax.faces.ViewState" value="VS_TOKEN_XYZ"/></body></html>'
    step2_html = '<html><body><div id="painel">Status: Em análise. Protocolo 12345.</div></body></html>'

    mock_resp1 = MagicMock(text=step1_html, status_code=200)
    mock_resp2 = MagicMock(text=step2_html, status_code=200)

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp1
    mock_client.post.return_value = mock_resp2
    mock_client_cls.return_value = mock_client

    adapter = DynamicAdapter(probe)
    result = adapter.scrape(_make_target())

    assert result.success is True
    assert "Em análise" in result.raw_html

    post_call = mock_client.post.call_args
    assert post_call[1]["data"]["javax.faces.ViewState"] == "VS_TOKEN_XYZ"
