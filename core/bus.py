import json
import logging
import threading
import queue
from typing import Callable, Any, Dict, List
from datetime import datetime, timezone
import base64

from .schemas import BaseEvent

logger = logging.getLogger(__name__)

class InMemoryBus:
    """Fallback in-memory pub/sub when Redis is not available."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[dict], None]]] = {}
        self._queue = queue.Queue()
        self._running = False
        self._thread = None

    def publish(self, channel: str, payload_str: str):
        self._queue.put((channel, payload_str))

    def subscribe(self, channel: str, callback: Callable[[dict], None]):
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(callback)

    def start_listening(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop_listening(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._queue.put((None, None))
            self._thread.join(timeout=1.0)

    def _worker(self):
        while self._running:
            try:
                channel, payload_str = self._queue.get(timeout=0.1)
                if channel is None:
                    break
                callbacks = self._subscribers.get(channel, [])
                data = json.loads(payload_str)
                for cb in callbacks:
                    try:
                        cb(data)
                    except Exception as e:
                        logger.error(f"Error in in-memory subscriber callback: {e}")
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in in-memory worker: {e}")


class EventBus:
    """Event Bus with Redis Pub/Sub and automatic in-memory fallback"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.use_fallback = False
        self.in_memory_bus: InMemoryBus = InMemoryBus()
        self.redis_client = None
        self.pubsub = None

        try:
            import redis
            client = redis.from_url(redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)
            client.ping()
            self.redis_client = client
            self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            logger.info("Connected successfully to Redis EventBus")
        except Exception as e:
            self.use_fallback = True
            logger.warning(f"Redis not reachable at {redis_url} ({e}). Falling back to internal InMemoryBus.")

    def publish(self, channel: str, event: BaseEvent):
        """Publish an event to a channel"""
        try:
            data = event.model_dump()

            def custom_serializer(obj):
                if isinstance(obj, bytes):
                    return base64.b64encode(obj).decode('utf-8')
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            payload = json.dumps(data, default=custom_serializer)

            if self.use_fallback:
                self.in_memory_bus.publish(channel, payload)
            else:
                self.redis_client.publish(channel, payload)
            logger.debug(f"Published to {channel}: {event.id}")
        except Exception as e:
            logger.error(f"Error publishing to {channel}: {e}")

    def subscribe(self, channel: str, callback: Callable[[dict], None]):
        """Subscribe to a channel with a callback function"""
        if self.use_fallback:
            self.in_memory_bus.subscribe(channel, callback)
            logger.info(f"Subscribed (in-memory) to {channel}")
        else:
            self.pubsub.subscribe(**{channel: self._create_handler(callback)})
            logger.info(f"Subscribed (Redis) to {channel}")

    def _create_handler(self, callback: Callable[[dict], None]):
        def handler(message):
            try:
                data = json.loads(message['data'])
                callback(data)
            except Exception as e:
                logger.error(f"Error processing Redis message: {e}")
        return handler

    def start_listening(self):
        """Start listening for messages in a separate thread"""
        if self.use_fallback:
            self.in_memory_bus.start_listening()
            logger.info("InMemory EventBus listener started")
        else:
            self.thread = self.pubsub.run_in_thread(sleep_time=0.01)
            logger.info("Redis EventBus listener started")

    def stop_listening(self):
        """Stop listening thread"""
        if self.use_fallback:
            self.in_memory_bus.stop_listening()
            logger.info("InMemory EventBus listener stopped")
        else:
            if hasattr(self, 'thread') and self.thread:
                self.thread.stop()
                logger.info("Redis EventBus listener stopped")
