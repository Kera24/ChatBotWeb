from dataclasses import dataclass, field
from time import monotonic


@dataclass
class RateLimitBucket:
    attempts: list[float] = field(default_factory=list)


class LocalRateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._buckets: dict[str, RateLimitBucket] = {}

    def check(self, key: str) -> bool:
        now = monotonic()
        bucket = self._buckets.setdefault(key, RateLimitBucket())
        bucket.attempts = [item for item in bucket.attempts if now - item < self.window_seconds]
        if len(bucket.attempts) >= self.max_attempts:
            return False
        bucket.attempts.append(now)
        return True


auth_rate_limiter = LocalRateLimiter(max_attempts=12, window_seconds=60)
