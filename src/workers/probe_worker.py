# src/workers/probe_worker.py
from bson import ObjectId
from src.database.client import get_db
from src.queues.consumer import consume
from src.queues.connection import get_channel
from src.scraping.url_analyzer import analyze_url
from src.shared.logger import get_logger

logger = get_logger(__name__)


def _oid(val):
    try:
        return ObjectId(str(val))
    except Exception:
        return val


def handle_probe_job(payload: dict, method) -> None:
    stakeholder_id = payload.get("stakeholder_id", "")
    url = payload.get("url", "")

    if not stakeholder_id or not url:
        logger.error(f"probe.jobs payload inválido: {payload}")
        get_channel().basic_ack(delivery_tag=method.delivery_tag)
        return

    db = get_db()
    stakeholders = db["stakeholders"]

    try:
        logger.info(f"Analisando URL '{url}' para stakeholder {stakeholder_id}")
        probe = analyze_url(url)

        stakeholders.update_one(
            {"_id": _oid(stakeholder_id)},
            {"$set": {"site_probe": probe.model_dump(), "adapter_type": "dynamic"}},
        )
        logger.info(
            f"Probe salvo para stakeholder {stakeholder_id}: "
            f"type={probe.portal_type}, confidence={probe.confidence:.2f}"
        )

    except Exception as e:
        logger.exception(f"Erro ao analisar URL para stakeholder {stakeholder_id}: {e}")
        try:
            stakeholders.update_one(
                {"_id": _oid(stakeholder_id)},
                {"$set": {"probe_error": str(e)}},
            )
        except Exception:
            pass

    finally:
        get_channel().basic_ack(delivery_tag=method.delivery_tag)


def run():
    logger.info("Starting probe worker")
    consume("probe.jobs", handle_probe_job)
