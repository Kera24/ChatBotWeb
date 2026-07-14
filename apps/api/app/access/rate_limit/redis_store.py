from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.access.rate_limit.contracts import RateLimitRule
from app.access.rate_limit.errors import RateLimitStoreError, RateLimitStoreTimeout
from app.access.rate_limit.token_bucket import TokenBucketState, evaluate_token_bucket, parse_redis_bucket_result

TOKEN_BUCKET_LUA = """
-- token_bucket_v1
local tokens_key = KEYS[1]
local updated_key = KEYS[2]
local capacity = tonumber(ARGV[1])
local refill_tokens = tonumber(ARGV[2])
local refill_period = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local now = tonumber(ARGV[5])
local ttl = tonumber(ARGV[6])
local current = tonumber(redis.call('GET', tokens_key))
local updated = tonumber(redis.call('GET', updated_key))
if current == nil then current = capacity end
if updated == nil then updated = now end
local elapsed = math.max(0, now - updated)
local refill_per_second = refill_tokens / refill_period
local tokens = math.min(capacity, current + (elapsed * refill_per_second))
local allowed = 0
local retry_after = 0
if tokens >= cost then
  allowed = 1
  tokens = tokens - cost
else
  local missing = cost - tokens
  retry_after = math.ceil(missing / refill_per_second)
end
local reset_after = math.ceil((capacity - tokens) / refill_per_second)
redis.call('SET', tokens_key, tokens, 'EX', ttl)
redis.call('SET', updated_key, now, 'EX', ttl)
return {allowed, math.floor(tokens), retry_after, reset_after, ttl}
"""


class RateLimitStore(Protocol):
    def consume(self, *, key: str, rule: RateLimitRule, request_cost: int, now: datetime) -> TokenBucketState:
        ...

    def health_check(self) -> bool:
        ...


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._state: dict[str, tuple[float, float]] = {}

    def consume(self, *, key: str, rule: RateLimitRule, request_cost: int, now: datetime) -> TokenBucketState:
        now_seconds = now.timestamp()
        current = self._state.get(key)
        result = evaluate_token_bucket(
            current_tokens=current[0] if current else None,
            updated_at_seconds=current[1] if current else None,
            now_seconds=now_seconds,
            rule=rule,
            request_cost=request_cost,
        )
        self._state[key] = (float(result.remaining), now_seconds)
        return result

    def health_check(self) -> bool:
        return True


class RedisRateLimitStore:
    def __init__(self, redis_client) -> None:
        self.redis_client = redis_client

    def consume(self, *, key: str, rule: RateLimitRule, request_cost: int, now: datetime) -> TokenBucketState:
        ttl = max(rule.refill_period_seconds * 2, 1)
        try:
            result = self.redis_client.eval(
                TOKEN_BUCKET_LUA,
                2,
                f"{key}:tokens",
                f"{key}:updated",
                rule.capacity,
                rule.refill_tokens,
                rule.refill_period_seconds,
                request_cost,
                now.timestamp(),
                ttl,
            )
            return parse_redis_bucket_result(result)
        except TimeoutError as exc:
            raise RateLimitStoreTimeout("Redis rate-limit operation timed out.") from exc
        except Exception as exc:
            raise RateLimitStoreError("Redis rate-limit operation failed.") from exc

    def health_check(self) -> bool:
        try:
            return bool(self.redis_client.ping())
        except Exception:
            return False


def create_redis_client(*, redis_url: str, timeout_seconds: float):
    try:
        import redis
    except ImportError as exc:
        raise RateLimitStoreError("redis package is not installed.") from exc
    return redis.Redis.from_url(
        redis_url,
        socket_timeout=timeout_seconds,
        socket_connect_timeout=timeout_seconds,
        health_check_interval=30,
        decode_responses=False,
    )


def create_redis_rate_limit_store(*, redis_url: str, timeout_seconds: float) -> RedisRateLimitStore:
    return RedisRateLimitStore(create_redis_client(redis_url=redis_url, timeout_seconds=timeout_seconds))
