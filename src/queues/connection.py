import pika
from src.config.settings import settings
from src.shared.logger import get_logger

logger = get_logger(__name__)
_channel = None

QUEUES = [
    "scraping.jobs",
    "ai.extraction.jobs",
    "ai.extraction.results",
    "failed.jobs",
]


def get_channel():
    global _channel
    if _channel is None or _channel.is_closed:
        connection = pika.BlockingConnection(
            pika.URLParameters(settings.rabbitmq_url)
        )
        _channel = connection.channel()
        for queue in QUEUES:
            _channel.queue_declare(queue=queue, durable=True)
        logger.info("RabbitMQ channel ready")
    return _channel
