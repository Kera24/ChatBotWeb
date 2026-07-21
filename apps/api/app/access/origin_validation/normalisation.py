from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.access.origin_validation.contracts import CanonicalOrigin
from app.access.origin_validation.errors import OriginNormalisationError

DEFAULT_PORTS = {"http": 80, "https": 443}


def normalise_origin_header(value: str) -> CanonicalOrigin:
    raw = (value or "").strip()
    if not raw:
        raise OriginNormalisationError("malformed_origin", "Origin is empty.")
    try:
        parsed = urlsplit(raw)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError, UnicodeError) as exc:
        raise OriginNormalisationError("malformed_origin", "Origin could not be parsed.") from exc

    if scheme not in DEFAULT_PORTS:
        raise OriginNormalisationError("unsupported_origin_scheme", "Origin scheme is not supported.")
    if parsed.username or parsed.password:
        raise OriginNormalisationError("malformed_origin", "Origin must not contain userinfo.")
    if parsed.path not in {"", "/"}:
        raise OriginNormalisationError("malformed_origin", "Origin must not contain a path.")
    if parsed.query:
        raise OriginNormalisationError("malformed_origin", "Origin must not contain a query string.")
    if parsed.fragment:
        raise OriginNormalisationError("malformed_origin", "Origin must not contain a fragment.")
    if not hostname:
        raise OriginNormalisationError("malformed_origin", "Origin hostname is required.")

    canonical_host = _normalise_hostname(hostname)
    effective_port = port or DEFAULT_PORTS[scheme]
    if effective_port < 1 or effective_port > 65535:
        raise OriginNormalisationError("malformed_origin", "Origin port is not valid.")

    is_ip_address = _is_ip_address(canonical_host)
    is_loopback = _is_loopback(canonical_host)
    serialised_host = f"[{canonical_host}]" if ":" in canonical_host and is_ip_address else canonical_host
    return CanonicalOrigin(
        scheme=scheme,
        hostname=canonical_host,
        effective_port=effective_port,
        serialised=f"{scheme}://{serialised_host}:{effective_port}",
        is_loopback=is_loopback,
        is_ip_address=is_ip_address,
    )


def _normalise_hostname(hostname: str) -> str:
    host = hostname.strip().rstrip(".").lower()
    if not host:
        raise OriginNormalisationError("malformed_origin", "Origin hostname is required.")
    if "%" in host:
        raise OriginNormalisationError("malformed_origin", "Origin hostname is not valid.")
    try:
        ip = ipaddress.ip_address(host)
        return ip.compressed.lower()
    except ValueError:
        pass
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise OriginNormalisationError("malformed_origin", "Origin hostname is not valid.") from exc
    if not ascii_host or ".." in ascii_host:
        raise OriginNormalisationError("malformed_origin", "Origin hostname is not valid.")
    labels = ascii_host.split(".")
    if any(not label or len(label) > 63 for label in labels):
        raise OriginNormalisationError("malformed_origin", "Origin hostname is not valid.")
    return ascii_host


def _is_ip_address(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def _is_loopback(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
