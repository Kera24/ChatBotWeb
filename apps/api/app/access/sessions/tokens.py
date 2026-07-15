import hmac
import re
import secrets
from dataclasses import dataclass
from hashlib import sha256

ENVIRONMENT_TOKEN_PREFIXES = {
    "development": "dev",
    "staging": "stg",
    "production": "live",
}
TOKEN_PREFIX_ENVIRONMENTS = {value: key for key, value in ENVIRONMENT_TOKEN_PREFIXES.items()}
TOKEN_RE = re.compile(r"^pss_(?P<environment>dev|stg|live)_(?P<token_id>[A-Za-z0-9_-]{12,120})\.(?P<secret>[A-Za-z0-9_-]{24,180})$")
MAX_PUBLIC_SESSION_TOKEN_LENGTH = 220


@dataclass(frozen=True)
class PublicSessionTokenParts:
    environment: str
    token_id: str
    secret: str


@dataclass(frozen=True)
class GeneratedPublicSessionToken:
    token: str
    token_id: str
    secret: str
    environment: str


def generate_public_session_token(*, environment: str, token_id_bytes: int, secret_bytes: int) -> GeneratedPublicSessionToken:
    prefix = ENVIRONMENT_TOKEN_PREFIXES.get(environment)
    if prefix is None:
        raise ValueError("Unsupported public session environment.")
    if token_id_bytes < 12 or secret_bytes < 24:
        raise ValueError("Public session token entropy settings are too low.")
    token_id = secrets.token_urlsafe(token_id_bytes)
    secret = secrets.token_urlsafe(secret_bytes)
    token = f"pss_{prefix}_{token_id}.{secret}"
    if len(token) > MAX_PUBLIC_SESSION_TOKEN_LENGTH:
        raise ValueError("Public session token is too long.")
    return GeneratedPublicSessionToken(token=token, token_id=token_id, secret=secret, environment=environment)


def parse_public_session_token(token: str) -> PublicSessionTokenParts:
    if len(token) > MAX_PUBLIC_SESSION_TOKEN_LENGTH:
        raise ValueError("Public session token is too long.")
    match = TOKEN_RE.fullmatch(token)
    if match is None:
        raise ValueError("Malformed public session token.")
    prefix = match.group("environment")
    environment = TOKEN_PREFIX_ENVIRONMENTS[prefix]
    return PublicSessionTokenParts(
        environment=environment,
        token_id=match.group("token_id"),
        secret=match.group("secret"),
    )


def hash_public_session_secret(*, token_id: str, secret: str, hash_secret: str, version: str) -> str:
    if not hash_secret:
        raise ValueError("A public session token hash secret is required.")
    payload = f"public-session-token:{version}:{token_id}:{secret}".encode("utf-8")
    digest = hmac.new(hash_secret.encode("utf-8"), payload, sha256).hexdigest()
    return f"{version}:{digest}"


def verify_public_session_secret(*, token_id: str, secret: str, stored_hash: str, hash_secret: str, version: str) -> bool:
    expected = hash_public_session_secret(token_id=token_id, secret=secret, hash_secret=hash_secret, version=version)
    return hmac.compare_digest(expected, stored_hash)


def hash_canonical_origin(*, canonical_origin: str, hash_secret: str, version: str) -> str:
    if not hash_secret:
        raise ValueError("A public session token hash secret is required.")
    payload = f"public-session-origin:{version}:{canonical_origin}".encode("utf-8")
    return hmac.new(hash_secret.encode("utf-8"), payload, sha256).hexdigest()


def safe_token_id_fingerprint(*, token_id: str, hash_secret: str) -> str:
    payload = f"public-session-token-id:{token_id}".encode("utf-8")
    return hmac.new(hash_secret.encode("utf-8"), payload, sha256).hexdigest()[:16]

