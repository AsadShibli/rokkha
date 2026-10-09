from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after: int  # seconds until the window resets (0 when allowed)


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision: ...


class RedisRateLimiter:
    """Fixed window counter: INCR the key, start its TTL on the first hit.

    Shared by every API worker, unlike an in-process counter.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            pipe.ttl(key)
            count, _, ttl = await pipe.execute()
        if count > limit:
            return RateDecision(allowed=False, retry_after=max(int(ttl), 1))
        return RateDecision(allowed=True, retry_after=0)


class NoopRateLimiter:
    """Used when Redis isn't configured (unit tests without the app lifespan)."""

    async def hit(self, key: str, limit: int, window_seconds: int) -> RateDecision:
        return RateDecision(allowed=True, retry_after=0)
