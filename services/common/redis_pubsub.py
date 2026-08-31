import json
import logging
import asyncio
from typing import AsyncGenerator, Callable, Dict, Set
from services.common.config import settings

logger = logging.getLogger(__name__)

class EventBus:
    """
    Unified Event Bus using Redis Pub/Sub with in-memory fallback for local dev.
    """
    def __init__(self):
        self._redis = None
        self._in_memory_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        if settings.REDIS_ENABLED:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                await self._redis.ping()
                logger.info(f"Connected to Redis at {settings.REDIS_URL}")
            except Exception as e:
                logger.warning(f"Redis connection failed ({e}). Falling back to in-memory event bus.")
                self._redis = None
        self._initialized = True

    async def publish(self, channel: str, message: dict):
        if not self._initialized:
            await self.initialize()

        payload = json.dumps(message)
        if self._redis:
            try:
                await self._redis.publish(channel, payload)
                return
            except Exception as e:
                logger.error(f"Failed to publish to Redis: {e}")

        # In-memory distribution
        if channel in self._in_memory_subscribers:
            for queue in list(self._in_memory_subscribers[channel]):
                try:
                    await queue.put(payload)
                except Exception:
                    pass

    async def subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        if not self._initialized:
            await self.initialize()

        if self._redis:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(channel)
            try:
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        try:
                            yield json.loads(msg["data"])
                        except Exception as e:
                            logger.error(f"Error decoding Redis message: {e}")
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
        else:
            queue = asyncio.Queue()
            if channel not in self._in_memory_subscribers:
                self._in_memory_subscribers[channel] = set()
            self._in_memory_subscribers[channel].add(queue)
            try:
                while True:
                    data = await queue.get()
                    yield json.loads(data)
            finally:
                self._in_memory_subscribers[channel].remove(queue)
                if not self._in_memory_subscribers[channel]:
                    del self._in_memory_subscribers[channel]

event_bus = EventBus()
