# tests/test_probe_schema.py
from src.scraping.probe_schema import SiteProbe, ProbeStep, ExtractRule, PortalType, StepType


def test_site_probe_minimal_valid():
    probe = SiteProbe(
        portal_type="simple_get",
        original_url="https://portal.gov.br/consulta",
        base_url="https://portal.gov.br",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/api/protocolo?numero={protocol_number}",
                is_result_step=True,
            )
        ],
        confidence=0.9,
        notes="Portal REST simples",
    )
    assert probe.portal_type == "simple_get"
    assert probe.auth_required is False
    assert len(probe.steps) == 1
    assert probe.steps[0].is_result_step is True


def test_site_probe_jsf_with_extract():
    probe = SiteProbe(
        portal_type="jsf_form",
        original_url="https://jsf.portal.com/inicio.jsf",
        base_url="https://jsf.portal.com",
        auth_required=False,
        captcha_detected=False,
        steps=[
            ProbeStep(
                step=1,
                type="get",
                url="{base_url}/inicio.jsf",
                extract=[
                    ExtractRule(name="viewstate", selector="viewstate", attribute="value"),
                ],
            ),
            ProbeStep(
                step=2,
                type="post",
                url="{base_url}/inicio.jsf",
                form_data={
                    "formPrincipal:protocolo": "{protocol_number}",
                    "javax.faces.ViewState": "{var_viewstate}",
                },
                is_result_step=True,
                result_selector="div#resultado",
            ),
        ],
        confidence=0.85,
        notes="Portal JSF com ViewState",
    )
    assert probe.portal_type == "jsf_form"
    assert probe.steps[0].extract[0].selector == "viewstate"
    assert "{var_viewstate}" in probe.steps[1].form_data.values()


def test_probe_step_requires_step_number():
    import pytest
    with pytest.raises(Exception):
        ProbeStep(type="get", url="https://example.com")  # step ausente


def test_site_probe_with_auth():
    probe = SiteProbe(
        portal_type="post_form",
        original_url="https://sistema.com/login",
        base_url="https://sistema.com",
        auth_required=True,
        captcha_detected=False,
        login_url="https://sistema.com/login",
        steps=[
            ProbeStep(
                step=1,
                type="post",
                url="{base_url}/login",
                form_data={"user": "{credential_username}", "pass": "{credential_password}"},
            ),
            ProbeStep(
                step=2,
                type="get",
                url="{base_url}/protocolo?numero={protocol_number}",
                is_result_step=True,
            ),
        ],
        confidence=0.7,
        notes="Portal com login obrigatório",
    )
    assert probe.auth_required is True
    assert probe.login_url == "https://sistema.com/login"
    assert "{credential_username}" in probe.steps[0].form_data.values()
