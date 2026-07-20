from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import InMemoryCredentialRegistry
from app.access.policies.registry import AccessPolicyRegistry, default_policy_registry
from app.db.models import CredentialAllowedOrigin, PublicCredential, WidgetConfiguration
from app.repositories.audit_repository import add_audit_event
from app.repositories.workspace_repository import get_workspace_for_organisation

VALID_CREDENTIAL_TYPES = {"widget_public_key", "partner_api_key", "channel_installation", "webhook_secret"}
VALID_STATUSES = {"draft", "active", "disabled", "revoked", "expired"}
VALID_ENVIRONMENTS = {"development", "staging", "production"}
SECRET_BEARING_TYPES = {"partner_api_key", "webhook_secret"}
VALID_TRANSITIONS = {
    "draft": {"active", "revoked"},
    "active": {"disabled", "revoked", "expired"},
    "disabled": {"active", "revoked", "expired"},
    "revoked": set(),
    "expired": set(),
}
VALID_CAPABILITIES = {
    "widget_public_key": {"widget_config", "widget_chat"},
    "partner_api_key": {"api_chat", "api_config"},
    "channel_installation": {"channel_chat"},
    "webhook_secret": {"webhook_receive"},
}
DEFAULT_CAPABILITIES = {
    "widget_public_key": ["widget_config"],
    "partner_api_key": ["api_chat"],
    "channel_installation": ["channel_chat"],
    "webhook_secret": ["webhook_receive"],
}


class CredentialValidationError(ValueError):
    pass


class CredentialNotFound(LookupError):
    pass


class OriginValidationError(ValueError):
    pass


class OriginNotFound(LookupError):
    pass


class WidgetConfigurationValidationError(ValueError):
    pass


class WidgetConfigurationNotFound(LookupError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_public_identifier(*, credential_type: str, environment: str) -> str:
    if credential_type == "widget_public_key":
        env_prefix = {"development": "dev", "staging": "stg", "production": "live"}[environment]
        return f"wpk_{env_prefix}_{secrets.token_urlsafe(24)}"
    if credential_type == "partner_api_key":
        env_prefix = {"development": "dev", "staging": "stg", "production": "live"}[environment]
        return f"pak_{env_prefix}_{secrets.token_urlsafe(18)}"
    if credential_type == "channel_installation":
        return f"chi_{environment[:3]}_{secrets.token_urlsafe(18)}"
    if credential_type == "webhook_secret":
        return f"whs_{environment[:3]}_{secrets.token_urlsafe(18)}"
    raise CredentialValidationError("Unsupported credential type.")


def generate_unique_public_identifier(db: Session, *, credential_type: str, environment: str, attempts: int = 10) -> str:
    from app.access.credentials.repository import resolve_credential_by_public_identifier

    for _ in range(attempts):
        public_identifier = generate_public_identifier(credential_type=credential_type, environment=environment)
        if resolve_credential_by_public_identifier(db, public_identifier=public_identifier) is None:
            return public_identifier
    raise CredentialValidationError("Could not generate a unique public identifier.")


def validate_credential_input(
    *,
    credential_type: str,
    environment: str,
    policy_profile: str,
    display_name: str,
    capabilities: list[str] | None,
    expires_at: datetime | None,
    policy_registry: AccessPolicyRegistry | None = None,
) -> list[str]:
    if credential_type not in VALID_CREDENTIAL_TYPES:
        raise CredentialValidationError("Unsupported credential type.")
    if environment not in VALID_ENVIRONMENTS:
        raise CredentialValidationError("Unsupported credential environment.")
    registry = policy_registry or default_policy_registry()
    registry.resolve(policy_profile)
    safe_display_name = display_name.strip()
    if not safe_display_name or len(safe_display_name) > 160 or _contains_html(safe_display_name):
        raise CredentialValidationError("Display name is not valid.")
    if expires_at is not None and expires_at <= utc_now():
        raise CredentialValidationError("Credential expiration must be in the future.")
    requested = capabilities or DEFAULT_CAPABILITIES[credential_type]
    allowed = VALID_CAPABILITIES[credential_type]
    if not requested or any(item not in allowed for item in requested):
        raise CredentialValidationError("Credential capabilities are not valid for this type.")
    return requested


def validate_transition(current: str, target: str) -> None:
    if target not in VALID_STATUSES:
        raise CredentialValidationError("Unsupported credential status.")
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise CredentialValidationError(f"Cannot transition credential from {current} to {target}.")


def create_credential(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    credential_type: str,
    display_name: str,
    environment: str,
    policy_profile: str,
    capabilities: list[str] | None = None,
    expires_at: datetime | None = None,
    created_by_user_id: str | None = None,
    metadata_json: dict | None = None,
    public_identifier: str | None = None,
    status: str = "draft",
    parent_credential_id: str | None = None,
    rotation_group_id: str | None = None,
    secret_hash: str | None = None,
) -> PublicCredential:
    if status != "draft":
        raise CredentialValidationError("Credentials must be created as draft before activation.")
    safe_capabilities = validate_credential_input(
        credential_type=credential_type,
        environment=environment,
        policy_profile=policy_profile,
        display_name=display_name,
        capabilities=capabilities,
        expires_at=expires_at,
    )
    if credential_type == "widget_public_key" and secret_hash is not None:
        raise CredentialValidationError("Widget public keys must not store secret material.")
    if credential_type in SECRET_BEARING_TYPES and secret_hash is None:
        raise CredentialValidationError("Secret-bearing credentials require a secret hash. One-time secret generation is out of scope for this task.")

    public_identifier = public_identifier or generate_unique_public_identifier(db, credential_type=credential_type, environment=environment)
    credential = PublicCredential(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        credential_type=credential_type,
        public_identifier=public_identifier,
        secret_hash=secret_hash,
        display_name=display_name.strip(),
        status=status,
        environment=environment,
        policy_profile=policy_profile,
        capabilities_json=safe_capabilities,
        created_by_user_id=created_by_user_id,
        parent_credential_id=parent_credential_id,
        rotation_group_id=rotation_group_id,
        expires_at=expires_at,
        metadata_json=metadata_json,
    )
    db.add(credential)
    db.flush()
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=created_by_user_id,
        action="public_credential.created",
        entity_type="public_credential",
        entity_id=credential.id,
        new_status=credential.status,
        metadata_json={"credential_type": credential_type, "environment": environment, "policy_profile": policy_profile},
    )
    db.commit()
    db.refresh(credential)
    return credential


def list_credentials(db: Session, *, organisation_id: str, workspace_id: str) -> list[PublicCredential]:
    from app.access.credentials.repository import list_workspace_credentials

    return list_workspace_credentials(db, organisation_id=organisation_id, workspace_id=workspace_id)


def get_credential(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str) -> PublicCredential:
    from app.access.credentials.repository import get_credential_for_workspace

    credential = get_credential_for_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if credential is None:
        raise CredentialNotFound("Credential not found for workspace.")
    return credential


def update_credential(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    credential_id: str,
    actor_user_id: str | None,
    display_name: str | None = None,
    policy_profile: str | None = None,
    capabilities: list[str] | None = None,
    expires_at: datetime | None = None,
) -> PublicCredential:
    credential = get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if credential.status in {"revoked", "expired"}:
        raise CredentialValidationError("Terminal credentials cannot be updated.")
    new_display = display_name if display_name is not None else credential.display_name
    new_policy = policy_profile if policy_profile is not None else credential.policy_profile
    new_capabilities = capabilities if capabilities is not None else list(credential.capabilities_json or [])
    validate_credential_input(
        credential_type=credential.credential_type,
        environment=credential.environment,
        policy_profile=new_policy,
        display_name=new_display,
        capabilities=new_capabilities,
        expires_at=expires_at,
    )
    previous = {"display_name": credential.display_name, "policy_profile": credential.policy_profile, "capabilities": credential.capabilities_json}
    credential.display_name = new_display.strip()
    credential.policy_profile = new_policy
    credential.capabilities_json = new_capabilities
    if expires_at is not None:
        credential.expires_at = expires_at
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="public_credential.updated",
        entity_type="public_credential",
        entity_id=credential.id,
        previous_status=credential.status,
        new_status=credential.status,
        metadata_json={"before": previous, "after": {"display_name": credential.display_name, "policy_profile": credential.policy_profile, "capabilities": credential.capabilities_json}},
    )
    db.commit()
    db.refresh(credential)
    return credential


def transition_credential(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    credential_id: str,
    target_status: str,
    actor_user_id: str | None,
) -> PublicCredential:
    credential = get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if credential.deleted_at is not None and target_status == "active":
        raise CredentialValidationError("Deleted credentials cannot be activated.")
    validate_transition(credential.status, target_status)
    if target_status == "active":
        workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
        if workspace is None:
            raise CredentialValidationError("Inactive organisation or workspace prevents activation.")
    now = utc_now()
    previous_status = credential.status
    credential.status = target_status
    if target_status == "active" and credential.activated_at is None:
        credential.activated_at = now
    if target_status == "revoked":
        credential.revoked_at = now
    if target_status == "expired":
        credential.expires_at = credential.expires_at or now
    action = f"public_credential.{target_status if target_status != 'active' else 'activated'}"
    if target_status == "disabled":
        action = "public_credential.disabled"
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type="public_credential",
        entity_id=credential.id,
        previous_status=previous_status,
        new_status=target_status,
    )
    db.commit()
    db.refresh(credential)
    return credential


def rotate_credential(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    credential_id: str,
    actor_user_id: str | None,
    display_name: str | None = None,
) -> PublicCredential:
    old = get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if old.status not in {"active", "disabled", "draft"}:
        raise CredentialValidationError("Only non-terminal credentials can be rotated.")
    group_id = old.rotation_group_id or str(uuid4())
    old.rotation_group_id = group_id
    old.rotated_at = utc_now()
    replacement = PublicCredential(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        credential_type=old.credential_type,
        public_identifier=generate_unique_public_identifier(db, credential_type=old.credential_type, environment=old.environment),
        secret_hash=old.secret_hash if old.credential_type in SECRET_BEARING_TYPES else None,
        display_name=display_name or f"{old.display_name} replacement",
        status="draft",
        environment=old.environment,
        policy_profile=old.policy_profile,
        capabilities_json=old.capabilities_json,
        created_by_user_id=actor_user_id,
        rotation_group_id=group_id,
        parent_credential_id=old.id,
        expires_at=old.expires_at,
        metadata_json={"rotation": "replacement"},
    )
    db.add(replacement)
    db.flush()
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="public_credential.rotated",
        entity_type="public_credential",
        entity_id=old.id,
        previous_status=old.status,
        new_status=old.status,
        metadata_json={"replacement_credential_id": replacement.id, "rotation_group_id": group_id},
    )
    db.commit()
    db.refresh(replacement)
    return replacement


def update_last_used(db: Session, *, public_identifier: str, used_at: datetime | None = None) -> PublicCredential | None:
    from app.access.credentials.repository import resolve_credential_by_public_identifier

    credential = resolve_credential_by_public_identifier(db, public_identifier=public_identifier)
    if credential is None:
        return None
    credential.last_used_at = used_at or utc_now()
    db.commit()
    db.refresh(credential)
    return credential


def normalise_origin(origin: str, *, environment: str, wildcard_subdomains: bool = False) -> dict[str, object]:
    parsed = urlparse(origin.strip())
    if not parsed.scheme or not parsed.netloc:
        raise OriginValidationError("Origin must include scheme and hostname.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise OriginValidationError("Origin must not include path, query, fragment, or credentials.")
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise OriginValidationError("Origin scheme must be http or https.")
    hostname = (parsed.hostname or "").lower().strip(".")
    if hostname.startswith("*."):
        wildcard_subdomains = True
        hostname = hostname[2:]
    if not hostname:
        raise OriginValidationError("Origin hostname is required.")
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise OriginValidationError("Origin hostname is not valid.") from exc
    is_localhost = hostname == "localhost" or hostname.startswith("127.") or hostname == "::1"
    if is_localhost and environment != "development":
        raise OriginValidationError("Localhost origins are only allowed for development credentials.")
    if environment != "development" and scheme != "https":
        raise OriginValidationError("Non-development origins must use https.")
    if wildcard_subdomains:
        labels = hostname.split(".")
        if len(labels) < 2 or is_localhost:
            raise OriginValidationError("Wildcard origins require a concrete registrable domain.")
        if environment == "production" and len(labels) < 2:
            raise OriginValidationError("Broad production wildcards are not allowed.")
    port = parsed.port
    if (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        port = None
    return {"scheme": scheme, "hostname": hostname, "port": port, "wildcard_subdomains": bool(wildcard_subdomains), "environment": environment}


def add_origin(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    credential_id: str,
    origin: str,
    wildcard_subdomains: bool,
    actor_user_id: str | None,
) -> CredentialAllowedOrigin:
    credential = get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    values = normalise_origin(origin, environment=credential.environment, wildcard_subdomains=wildcard_subdomains)
    existing = list_origins(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, active_only=False)
    for item in existing:
        if item.active and item.scheme == values["scheme"] and item.hostname == values["hostname"] and item.port == values["port"] and item.wildcard_subdomains == values["wildcard_subdomains"] and item.environment == values["environment"]:
            raise OriginValidationError("Origin already exists for this credential.")
    row = CredentialAllowedOrigin(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        credential_id=credential_id,
        **values,
        active=True,
    )
    db.add(row)
    db.flush()
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="public_credential.origin.added",
        entity_type="credential_allowed_origin",
        entity_id=row.id,
        metadata_json={"credential_id": credential_id, "scheme": row.scheme, "hostname": row.hostname, "port": row.port, "wildcard_subdomains": row.wildcard_subdomains},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OriginValidationError("Origin already exists for this credential.") from exc
    db.refresh(row)
    return row


def list_origins(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, active_only: bool = True) -> list[CredentialAllowedOrigin]:
    from app.access.credentials.repository import list_credential_origins

    return list_credential_origins(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, active_only=active_only)


def deactivate_origin(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, origin_id: str, actor_user_id: str | None) -> CredentialAllowedOrigin:
    from app.access.credentials.repository import get_origin_for_credential

    row = get_origin_for_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, origin_id=origin_id)
    if row is None:
        raise OriginNotFound("Origin not found for credential.")
    row.active = False
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="public_credential.origin.removed",
        entity_type="credential_allowed_origin",
        entity_id=row.id,
        previous_status="active",
        new_status="inactive",
        metadata_json={"credential_id": credential_id},
    )
    db.commit()
    db.refresh(row)
    return row


def _contains_html(value: str) -> bool:
    return bool(re.search(r"<\s*/?\s*[a-zA-Z!]|<|>", value))


def public_credential_to_record(credential: PublicCredential, origins: list[CredentialAllowedOrigin] | None = None) -> CredentialRecord:
    return CredentialRecord(
        credential_id=credential.id,
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        credential_type=credential.credential_type,
        public_identifier=credential.public_identifier,
        secret_hash=credential.secret_hash,
        status=credential.status,
        environment=credential.environment,
        allowed_origins=tuple(_origin_to_string(origin) for origin in origins or [] if origin.active),
        capabilities=tuple(credential.capabilities_json or []),
        policy_profile=credential.policy_profile,
        created_at=credential.created_at,
        rotated_at=credential.rotated_at,
        revoked_at=credential.revoked_at,
        expires_at=credential.expires_at,
    )


def _origin_to_string(origin: CredentialAllowedOrigin) -> str:
    host = f"*.{origin.hostname}" if origin.wildcard_subdomains else origin.hostname
    port = f":{origin.port}" if origin.port is not None else ""
    return f"{origin.scheme}://{host}{port}"
