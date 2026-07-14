from dataclasses import dataclass
from datetime import datetime, timezone
import math

from app.access.rate_limit.contracts import RateLimitRule

SCRIPT_VERSION = "token_bucket_v1"


@dataclass(frozen=True)
class TokenBucketState:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    reset_after_seconds: int
    ttl_seconds: int


def evaluate_token_bucket(
    *,
    current_tokens: float | None,
    updated_at_seconds: float | None,
    now_seconds: float,
    rule: RateLimitRule,
    request_cost: int | None = None,
) -> TokenBucketState:
    cost = request_cost or rule.request_cost
    previous_tokens = float(rule.capacity if current_tokens is None else current_tokens)
    previous_updated = now_seconds if updated_at_seconds is None else float(updated_at_seconds)
    elapsed = max(0.0, now_seconds - previous_updated)
    refill_per_second = rule.refill_tokens / rule.refill_period_seconds
    tokens = min(float(rule.capacity), previous_tokens + (elapsed * refill_per_second))
    allowed = tokens >= cost
    if allowed:
        tokens -= cost
        retry_after = 0
    else:
        missing = cost - tokens
        retry_after = math.ceil(missing / refill_per_second) if refill_per_second > 0 else rule.retry_after_cap_seconds
        retry_after = min(retry_after, rule.retry_after_cap_seconds) if rule.retry_after_cap_seconds else retry_after
    reset_after = math.ceil((rule.capacity - tokens) / refill_per_second) if refill_per_second > 0 else rule.refill_period_seconds
    ttl = max(rule.refill_period_seconds * 2, reset_after + rule.refill_period_seconds, 1)
    return TokenBucketState(
        allowed=allowed,
        remaining=max(0, math.floor(tokens)),
        retry_after_seconds=max(0, retry_after),
        reset_after_seconds=max(0, reset_after),
        ttl_seconds=ttl,
    )


def reset_at_from_now(now: datetime, reset_after_seconds: int) -> datetime:
    return datetime.fromtimestamp(now.timestamp() + reset_after_seconds, tz=timezone.utc)


def parse_redis_bucket_result(values: list[object] | tuple[object, ...]) -> TokenBucketState:
    if len(values) != 5:
        raise ValueError("Unexpected token bucket result shape.")
    return TokenBucketState(
        allowed=bool(int(values[0])),
        remaining=int(values[1]),
        retry_after_seconds=int(values[2]),
        reset_after_seconds=int(values[3]),
        ttl_seconds=int(values[4]),
    )
