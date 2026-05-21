from dataclasses import dataclass, field
from bson import ObjectId
from pymongo.database import Database
from src.scraping.adapters.registry import get_adapter
from src.scraping.probe_schema import SiteProbe
from src.shared.secrets import decrypt_secret


def _oid(val):
    """Aceita string ou ObjectId — a API envia IDs como string no payload RabbitMQ."""
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(str(val))
    except Exception:
        return val


@dataclass
class ScrapingTarget:
    job_id: str
    protocol_id: str
    stakeholder_id: str
    protocol_number: str
    cnpj: str | None
    stakeholder_name: str
    stakeholder_type: str
    adapter_type: str
    requires_javascript: bool
    has_captcha: bool
    resolved_url: str
    registry_office_number: str | None = None
    site_probe: SiteProbe | None = None
    credential_username: str | None = None
    credential_password: str | None = None


def _infer_adapter_key(stakeholder: dict) -> str:
    explicit = stakeholder.get("adapter_type")
    if explicit:
        return explicit

    fallback = stakeholder.get("type", "default")
    haystack = " ".join(
        str(stakeholder.get(key) or "")
        for key in ("name", "query_url_template", "type")
    ).lower()
    if "copel" in haystack:
        return "copel"
    return fallback


def fetch_scraping_target(
    db: Database,
    protocol_id: str,
    stakeholder_id: str,
    job_id: str = "",
) -> ScrapingTarget:
    protocol = db["protocols"].find_one({"_id": _oid(protocol_id)})
    if not protocol:
        raise ValueError(f"Protocol {protocol_id} not found")

    if (
        not protocol.get("monitoring_enabled", True)
        or protocol.get("closed_manually", False)
        or not protocol.get("active", True)
    ):
        raise ValueError(f"Protocol {protocol_id} is not monitorable")

    stakeholder = db["stakeholders"].find_one({"_id": _oid(stakeholder_id)})
    if not stakeholder:
        raise ValueError(f"Stakeholder {stakeholder_id} not found")

    if not stakeholder.get("active", True):
        raise ValueError(f"Cannot scrape: inactive stakeholder {stakeholder_id}")

    template = stakeholder.get("query_url_template", "")
    if not template:
        raise ValueError(f"Stakeholder {stakeholder_id} has no query_url_template")

    site_probe: SiteProbe | None = None
    probe_raw = stakeholder.get("site_probe")
    if probe_raw and isinstance(probe_raw, dict):
        try:
            site_probe = SiteProbe(**probe_raw)
        except Exception:
            pass  # invalid probe — continue without it

    adapter_key = _infer_adapter_key(stakeholder)
    adapter = get_adapter(adapter_key)
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
        adapter_type=adapter_key,
        requires_javascript=stakeholder.get("requires_javascript", False),
        has_captcha=stakeholder.get("has_captcha", False),
        resolved_url=resolved_url,
        registry_office_number=(
            protocol.get("registry_office_number")
            or protocol.get("serventia")
            or protocol.get("oficio")
        ),
        site_probe=site_probe,
        credential_username=(stakeholder.get("auth") or {}).get("username"),
        credential_password=decrypt_secret(
            ((stakeholder.get("auth") or {}).get("password_encrypted"))
        ),
    )
