from dataclasses import asdict, dataclass, field
from typing import Any

MATCH_EXACT = "exact"
MATCH_WILDCARD = "wildcard"
MATCH_DEVELOPMENT_LOOPBACK = "development_loopback"
MATCH_NONE = "none"

SOURCE_ORIGIN_HEADER = "origin_header"
SOURCE_REFERER_FALLBACK = "referer_fallback"
SOURCE_POLICY_EXCEPTION = "policy_exception"
SOURCE_MISSING = "missing"

VALID_MATCH_TYPES = {MATCH_EXACT, MATCH_WILDCARD, MATCH_DEVELOPMENT_LOOPBACK, MATCH_NONE}
VALID_DECISION_SOURCES = {SOURCE_ORIGIN_HEADER, SOURCE_REFERER_FALLBACK, SOURCE_POLICY_EXCEPTION, SOURCE_MISSING}


@dataclass(frozen=True)
class CanonicalOrigin:
    scheme: str
    hostname: str
    effective_port: int
    serialised: str
    is_loopback: bool
    is_ip_address: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AllowedOriginRecord:
    origin_id: str
    credential_id: str
    scheme: str
    hostname: str
    port: int | None
    wildcard_subdomains: bool
    environment: str
    active: bool = True

    @property
    def effective_port(self) -> int:
        if self.port is not None:
            return self.port
        return 443 if self.scheme == "https" else 80


@dataclass(frozen=True)
class OriginValidationRequest:
    credential_id: str
    credential_environment: str
    policy_profile: Any
    origin_header: str | None
    referer_header: str | None
    request_method: str
    channel: str
    request_id: str
    trace_id: str
    trusted_proxy_context: dict[str, str | int | bool | None] | None = None
    credential_type: str = "widget_public_key"

    def __post_init__(self) -> None:
        for value in (self.credential_id, self.credential_environment, self.request_method, self.channel, self.request_id, self.trace_id):
            if not value:
                raise ValueError("Origin validation requests require stable identifiers.")


@dataclass(frozen=True)
class OriginValidationResult:
    allowed: bool
    canonical_origin: CanonicalOrigin | None
    matched_origin_id: str | None
    match_type: str
    decision_source: str
    reason_code: str
    environment: str
    safe_metadata: dict[str, str | int | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.match_type not in VALID_MATCH_TYPES:
            raise ValueError("Unsupported origin match type.")
        if self.decision_source not in VALID_DECISION_SOURCES:
            raise ValueError("Unsupported origin decision source.")

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "canonical_origin": self.canonical_origin.to_dict() if self.canonical_origin else None,
            "matched_origin_id": self.matched_origin_id,
            "match_type": self.match_type,
            "decision_source": self.decision_source,
            "reason_code": self.reason_code,
            "environment": self.environment,
            "safe_metadata": self.safe_metadata,
        }
