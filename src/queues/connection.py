import time
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

_MAX_RETRIES = 10
_RETRY_DELAY = 5  # segundos


def get_channel():
    global _channel
    if _channel is None or _channel.is_closed:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                connection = pika.BlockingConnection(
                    pika.URLParameters(settings.rabbitmq_url)
                )
                _channel = connection.channel()
                for queue in QUEUES:
                    _channel.queue_declare(queue=queue, durable=True)
                logger.info("RabbitMQ channel ready")
                return _channel
            except pika.exceptions.AMQPConnectionError as e:
                if attempt == _MAX_RETRIES:
                    raise
                logger.warning(f"RabbitMQ não disponível (tentativa {attempt}/{_MAX_RETRIES}), aguardando {_RETRY_DELAY}s...")
                time.sleep(_RETRY_DELAY)
    return _channel
