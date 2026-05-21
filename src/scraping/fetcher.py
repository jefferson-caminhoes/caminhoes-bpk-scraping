from dataclasses import dataclass
from pymongo.database import Database
from src.scraping.adapters.registry import get_adapter


@dataclass
class ScrapingTarget:
    job_id: str
    protocol_id: str
    stakeholder_id: str
    protocol_number: str
    cnpj: str | None
    stakeholder_name: str
    stakeholder_type: str
    requires_javascript: bool
    has_captcha: bool
    resolved_url: str
    registry_office_number: str | None = None


def fetch_scraping_target(
    db: Database,
    protocol_id: str,
    stakeholder_id: str,
    job_id: str = "",
) -> ScrapingTarget:
    protocol = db["protocols"].find_one({"_id": protocol_id})
    if not protocol:
        raise ValueError(f"Protocol {protocol_id} not found")

    if (
        not protocol.get("monitoring_enabled", True)
        or protocol.get("closed_manually", False)
        or not protocol.get("active", True)
    ):
        raise ValueError(f"Protocol {protocol_id} is not monitorable")

    stakeholder = db["stakeholders"].find_one({"_id": stakeholder_id})
    if not stakeholder:
        raise ValueError(f"Stakeholder {stakeholder_id} not found")

    if not stakeholder.get("active", True):
        raise ValueError(f"Cannot scrape: inactive stakeholder {stakeholder_id}")

    template = stakeholder.get("query_url_template", "")
    if not template:
        raise ValueError(f"Stakeholder {stakeholder_id} has no query_url_template")

    adapter = get_adapter(stakeholder.get("type", "default"))
    resolved_url = adapter.resolve_url(
        template=template,
        protocol_number=protocol.get("protocol_number", ""),
        cnpj=protocol.get("cnpj"),
        registry_office_number=protocol.get("registry_office_number"),
    )

    return ScrapingTarget(
        job_id=job_id,
        protocol_id=protocol_id,
        stakeholder_id=stakeholder_id,
        protocol_number=protocol.get("protocol_number", ""),
        cnpj=protocol.get("cnpj"),
        stakeholder_name=stakeholder.get("name", ""),
        stakeholder_type=stakeholder.get("type", "default"),
        requires_javascript=stakeholder.get("requires_javascript", False),
        has_captcha=stakeholder.get("has_captcha", False),
        resolved_url=resolved_url,
        registry_office_number=protocol.get("registry_office_number"),
    )
