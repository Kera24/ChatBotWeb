from datetime import datetime

from app.access.rate_limit.contracts import RateLimitRule
from app.access.rate_limit.redis_store import InMemoryRateLimitStore
from app.access.rate_limit.token_bucket import TokenBucketState


class LocalFallbackLimiter:
    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled
        self._store = InMemoryRateLimitStore()

    def consume(self, *, key: str, rule: RateLimitRule, request_cost: int, now: datetime) -> TokenBucketState | None:
        if not self.enabled:
            return None
        conservative = RateLimitRule(
            rule_key=f"local_{rule.rule_key}",
            category=rule.category,
            dimension=rule.dimension,
            capacity=max(1, min(rule.capacity, 10)),
            refill_tokens=max(1, min(rule.refill_tokens, 10)),
            refill_period_seconds=max(rule.refill_period_seconds, 60),
            request_cost=request_cost,
            enabled=True,
            fail_mode=rule.fail_mode,
            priority=rule.priority,
            retry_after_cap_seconds=rule.retry_after_cap_seconds,
        )
        return self._store.consume(key=key, rule=conservative, request_cost=request_cost, now=now)
