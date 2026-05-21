import json
import pika
from src.queues.connection import get_channel
from src.shared.logger import get_logger

logger = get_logger(__name__)


def publish_message(queue: str, payload: dict) -> None:
    channel = get_channel()
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            delivery_mode=pika.DeliveryMode.Persistent
        ),
    )
    logger.info(f"Published to {queue}: job_id={payload.get('job_id')}")
