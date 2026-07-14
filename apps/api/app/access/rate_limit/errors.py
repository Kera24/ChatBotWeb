class RateLimitStoreError(RuntimeError):
    pass


class RateLimitStoreTimeout(RateLimitStoreError):
    pass


class RateLimitInvalidPolicy(ValueError):
    pass
