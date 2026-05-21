import json
from typing import Callable
from src.queues.connection import get_channel
from src.shared.logger import get_logger

logger = get_logger(__name__)


def consume(queue: str, handler: Callable[[dict, object], None]) -> None:
    channel = get_channel()

    def _callback(ch, method, properties, body):
        try:
            payload = json.loads(body)
            handler(payload, method)
        except Exception as e:
            logger.error(f"Unhandled error in {queue} handler: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue, on_message_callback=_callback)
    logger.info(f"Consuming {queue} ...")
    channel.start_consuming()
