import pytest
from unittest.mock import MagicMock
from src.scraping.fetcher import fetch_scraping_target, ScrapingTarget
from src.scraping.adapters.default_http import DefaultHttpAdapter


def _make_mock_db(protocol: dict, stakeholder: dict):
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda key: {
        "protocols": MagicMock(find_one=MagicMock(return_value=protocol)),
        "stakeholders": MagicMock(find_one=MagicMock(return_value=stakeholder)),
    }[key]
    return mock_db


def test_fetch_scraping_target_returns_target():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "12345",
            "cnpj": "12.345.678/0001-99",
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={
            "_id": "stake_1",
            "name": "Prefeitura",
            "query_url_template": "https://prefeitura.gov.br/consulta?prot={protocol_number}",
            "requires_javascript": False,
            "has_captcha": False,
            "type": "prefeitura",
            "active": True,
        },
    )

    target = fetch_scraping_target(mock_db, "prot_1", "stake_1")

    assert target.protocol_number == "12345"
    assert target.cnpj == "12.345.678/0001-99"
    assert "12345" in target.resolved_url


def test_fetch_scraping_target_infers_copel_adapter_from_url():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "20245757138534",
            "cnpj": "57.740.735/0001-79",
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={
            "_id": "stake_1",
            "name": "copel",
            "query_url_template": "https://www.copel.com/slwweb/publico/acompanhamento/inicio.jsf",
            "requires_javascript": False,
            "has_captcha": False,
            "type": "empresa",
            "active": True,
        },
    )

    target = fetch_scraping_target(mock_db, "prot_1", "stake_1")

    assert target.adapter_type == "copel"


def test_fetch_raises_if_protocol_not_monitorable():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "12345",
            "monitoring_enabled": False,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={"_id": "stake_1", "active": True},
    )

    with pytest.raises(ValueError, match="not monitorable"):
        fetch_scraping_target(mock_db, "prot_1", "stake_1")


def test_fetch_raises_if_stakeholder_inactive():
    mock_db = _make_mock_db(
        protocol={
            "_id": "prot_1",
            "protocol_number": "12345",
            "monitoring_enabled": True,
            "active": True,
            "closed_manually": False,
            "stakeholder_id": "stake_1",
        },
        stakeholder={"_id": "stake_1", "active": False},
    )

    with pytest.raises(ValueError, match="inactive stakeholder"):
        fetch_scraping_target(mock_db, "prot_1", "stake_1")


def test_default_http_adapter_resolves_url():
    adapter = DefaultHttpAdapter()
    url = adapter.resolve_url(
        template="https://example.com?prot={protocol_number}&cnpj={cnpj}",
        protocol_number="12345",
        cnpj="12.345.678/0001-99",
        registry_office_number=None,
    )
    assert "12345" in url
    assert "12.345.678" in url
