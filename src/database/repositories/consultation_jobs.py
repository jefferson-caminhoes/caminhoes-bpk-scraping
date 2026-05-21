from datetime import datetime, timezone
from pymongo.collection import Collection


class ConsultationJobsRepository:
    def __init__(self, collection: Collection):
        self._col = collection

    def update_status(self, job_id: str, status: str) -> None:
        self._col.update_one(
            {"_id": job_id},
            {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
        )

    def get_by_id(self, job_id: str) -> dict | None:
        return self._col.find_one({"_id": job_id})
