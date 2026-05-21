from datetime import datetime, timezone
from bson import ObjectId
from pymongo.collection import Collection


def _oid(val):
    """Converte string para ObjectId se necessário (IDs vêm da API como strings)."""
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(str(val))
    except Exception:
        return val


class ConsultationJobsRepository:
    def __init__(self, collection: Collection):
        self._col = collection

    def update_status(self, job_id: str, status: str) -> None:
        self._col.update_one(
            {"_id": _oid(job_id)},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )

    def get_by_id(self, job_id: str) -> dict | None:
        return self._col.find_one({"_id": _oid(job_id)})
