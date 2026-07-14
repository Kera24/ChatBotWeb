from app.access.errors import PublicAccessError, raise_public_error


class OriginNormalisationError(ValueError):
    def __init__(self, reason_code: str, message: str = "Origin is not valid.") -> None:
        super().__init__(message)
        self.reason_code = reason_code


def raise_origin_error(reason_code: str) -> None:
    raise_public_error(reason_code)


__all__ = ["OriginNormalisationError", "PublicAccessError", "raise_origin_error"]
