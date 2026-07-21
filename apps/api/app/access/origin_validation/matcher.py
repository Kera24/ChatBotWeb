from app.access.origin_validation.contracts import (
    MATCH_DEVELOPMENT_LOOPBACK,
    MATCH_EXACT,
    MATCH_NONE,
    MATCH_WILDCARD,
    AllowedOriginRecord,
    CanonicalOrigin,
)

COMMON_PUBLIC_SUFFIXES = {
    "com",
    "net",
    "org",
    "edu",
    "gov",
    "co.uk",
    "org.uk",
    "ac.uk",
    "com.au",
    "net.au",
    "org.au",
    "co.nz",
}


def match_origin(canonical: CanonicalOrigin, origins: list[AllowedOriginRecord], *, environment: str) -> tuple[str, AllowedOriginRecord | None]:
    for record in origins:
        if _record_is_eligible(record, environment=environment) and _exact_matches(canonical, record):
            if canonical.is_loopback and environment == "development":
                return MATCH_DEVELOPMENT_LOOPBACK, record
            return MATCH_EXACT, record
    for record in origins:
        if _record_is_eligible(record, environment=environment) and _wildcard_matches(canonical, record):
            return MATCH_WILDCARD, record
    return MATCH_NONE, None


def _record_is_eligible(record: AllowedOriginRecord, *, environment: str) -> bool:
    return record.active and record.environment == environment and record.scheme in {"http", "https"}


def _exact_matches(canonical: CanonicalOrigin, record: AllowedOriginRecord) -> bool:
    return (
        not record.wildcard_subdomains
        and canonical.scheme == record.scheme
        and canonical.hostname == record.hostname
        and canonical.effective_port == record.effective_port
    )


def _wildcard_matches(canonical: CanonicalOrigin, record: AllowedOriginRecord) -> bool:
    if not record.wildcard_subdomains:
        return False
    if canonical.scheme != record.scheme or canonical.effective_port != record.effective_port:
        return False
    if canonical.is_ip_address or canonical.hostname == "localhost":
        return False
    if _is_forbidden_wildcard_base(record.hostname):
        return False
    suffix = f".{record.hostname}"
    if not canonical.hostname.endswith(suffix):
        return False
    prefix = canonical.hostname[: -len(suffix)]
    return bool(prefix) and "." not in prefix


def _is_forbidden_wildcard_base(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    labels = hostname.split(".")
    if len(labels) < 2:
        return True
    if hostname in COMMON_PUBLIC_SUFFIXES:
        return True
    try:
        import ipaddress

        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False
