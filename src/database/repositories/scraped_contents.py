from datetime import datetime, timezone
from typing import Any
from bson import ObjectId
from pymongo.collection import Collection


def _oid(val):
    """Converte string para ObjectId se necessário."""
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(str(val))
    except Exception:
        return val


class ScrapedContentsRepository:
    def __init__(self, collection: Collection):
        self._col = collection

    def save_raw_content(
        self,
        job_id: str,
        protocol_id: str,
        stakeholder_id: str,
        raw_html: str,
        http_status: int,
        request_url: str,
    ) -> str:
        doc = {
            "job_id": job_id,
            "protocol_id": protocol_id,
            "stakeholder_id": stakeholder_id,
            "request_url": request_url,
            "http_status": http_status,
            "raw_html": raw_html,
            "clean_text": None,
            "cleaning_strategy": None,
            "cleaned_at": None,
            "scraped_at": datetime.now(timezone.utc),
            "error": None,
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    def get_by_id(self, content_id: str) -> dict[str, Any] | None:
        return self._col.find_one({"_id": _oid(content_id)})

    def update_clean_text(
        self, content_id: str, clean_text: str, strategy: str
    ) -> None:
        self._col.update_one(
            {"_id": _oid(content_id)},
            {
                "$set": {
                    "clean_text": clean_text,
                    "cleaning_strategy": strategy,
                    "cleaned_at": datetime.now(timezone.utc),
                }
            },
        )
