from pymongo import MongoClient
from pymongo.database import Database
from src.config.settings import settings
from src.shared.logger import get_logger

logger = get_logger(__name__)
_client: MongoClient | None = None


def get_db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri)
        logger.info("MongoDB connected")
    return _client.get_default_database()
