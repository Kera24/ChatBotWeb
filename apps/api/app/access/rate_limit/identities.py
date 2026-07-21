from __future__ import annotations

import hashlib
import hmac

from app.access.rate_limit.contracts import RateLimitRule


def stable_hmac_identity(value: str, *, secret: str, purpose: str) -> str:
    if not secret:
        raise ValueError("Rate-limit identity secret is required.")
    digest = hmac.new(secret.encode("utf-8"), f"{purpose}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:32]


def redis_rate_key(*, prefix: str, environment: str, dimension: str, identity: str, category: str) -> str:
    safe_prefix = prefix.strip(":") or "rate"
    return f"{safe_prefix}:{environment}:{dimension}:{identity}:{category}"


def identity_for_rule(rule: RateLimitRule, *, request, secret: str) -> str | None:
    dimension = rule.dimension
    if dimension == "global":
        return "platform"
    if dimension == "channel":
        return stable_hmac_identity(request.channel, secret=secret, purpose="channel")
    if dimension == "credential":
        return stable_hmac_identity(request.credential_id, secret=secret, purpose="credential")
    if dimension == "workspace":
        return stable_hmac_identity(request.workspace_id, secret=secret, purpose="workspace")
    if dimension == "organisation":
        return stable_hmac_identity(request.organisation_id, secret=secret, purpose="organisation")
    if dimension == "ip":
        if request.client_ip_identity is None:
            return None
        return stable_hmac_identity(request.client_ip_identity, secret=secret, purpose="ip")
    if dimension == "session":
        if request.session_id is None:
            return None
        return stable_hmac_identity(request.session_id, secret=secret, purpose="session")
    if dimension == "endpoint_category":
        return stable_hmac_identity(request.category, secret=secret, purpose="category")
    return None
