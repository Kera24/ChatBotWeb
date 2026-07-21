"""Origin validation foundation for browser-based public access channels."""

from app.access.origin_validation.contracts import (
    AllowedOriginRecord,
    CanonicalOrigin,
    OriginValidationRequest,
    OriginValidationResult,
)
from app.access.origin_validation.service import OriginValidationService

__all__ = [
    "AllowedOriginRecord",
    "CanonicalOrigin",
    "OriginValidationRequest",
    "OriginValidationResult",
    "OriginValidationService",
]
