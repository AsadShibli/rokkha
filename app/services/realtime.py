"""Live incident updates over Redis pub/sub.

Every API worker publishes to `incident:{id}`; every worker holding a WebSocket for that
incident is subscribed, so updates reach the client whichever Uvicorn worker it is attached to.
Publishing is best-effort: the database is the source of truth and clients can always re-fetch
GET /incidents/{id}, so a Redis hiccup never fails the request that changed the data.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Protocol

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def incident_channel(incident_id: int) -> str:
    return f"incident:{incident_id}"


class EventPublisher(Protocol):
    async def publish(self, incident_id: int, message: dict[str, Any]) -> None: ...


class RedisPublisher:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish(self, incident_id: int, message: dict[str, Any]) -> None:
        payload = json.dumps({**message, "sent_at": datetime.now(UTC).isoformat()}, default=str)
        try:
            await self.redis.publish(incident_channel(incident_id), payload)
        except Exception:
            logger.warning("Could not publish update for incident %s", incident_id, exc_info=True)


class NullPublisher:
    """Used when Redis isn't configured (e.g. unit tests without the app lifespan)."""

    async def publish(self, incident_id: int, message: dict[str, Any]) -> None:
        return None
