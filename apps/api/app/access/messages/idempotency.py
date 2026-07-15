from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.errors import raise_public_error
from app.access.messages.contracts import IdempotencyResolution
from app.core.config import settings
from app.db.models import PublicMessageRequest
from app.access.messages import repository

_KEY_RE = re.compile(r"^[A-Za-z0-9._~:-]+$")
_REQUEST_SCHEMA_VERSION = "public_widget_message_preparation.v1"


def validate_idempotency_key(key: str | None) -> str:
    if key is None:
        raise_public_error("idempotency_key_required")
    safe = key.strip()
    if not safe:
        raise_public_error("invalid_idempotency_key")
    if len(safe) < settings.PUBLIC_MESSAGE_IDEMPOTENCY_KEY_MIN_LENGTH or len(safe) > settings.PUBLIC_MESSAGE_IDEMPOTENCY_KEY_MAX_LENGTH:
        raise_public_error("invalid_idempotency_key")
    if not _KEY_RE.fullmatch(safe):
        raise_public_error("invalid_idempotency_key")
    return safe


def hash_idempotency_key(key: str, *, secret: str = settings.PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), key.encode("utf-8"), hashlib.sha256).hexdigest()


def canonical_request_hash(*, canonical_message: str, metadata: dict[str, Any], public_session_id: str) -> str:
    payload = {
        "schema": _REQUEST_SCHEMA_VERSION,
        "message": canonical_message,
        "metadata": metadata,
        "public_session_id": public_session_id,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PublicMessageIdempotencyService:
    def __init__(self, *, db: Session, ttl_seconds: int = settings.PUBLIC_MESSAGE_IDEMPOTENCY_TTL_SECONDS) -> None:
        self.db = db
        self.ttl_seconds = ttl_seconds

    def begin_request(
        self,
        *,
        organisation_id: str,
        workspace_id: str,
        credential_id: str,
        public_session_id: str,
        idempotency_key: str,
        request_hash: str,
        metadata: dict[str, Any] | None,
        now: datetime,
    ) -> IdempotencyResolution:
        safe_key = validate_idempotency_key(idempotency_key)
        key_hash = hash_idempotency_key(safe_key)
        existing = repository.get_by_session_and_key_hash(self.db, public_session_id=public_session_id, idempotency_key_hash=key_hash)
        if existing is not None:
            return self.resolve_duplicate(existing, request_hash=request_hash)
        record = PublicMessageRequest(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
            public_session_id=public_session_id,
            idempotency_key_hash=key_hash,
            request_hash=request_hash,
            status="received",
            expires_at=now + timedelta(seconds=self.ttl_seconds),
            metadata_json=dict(metadata or {}),
        )
        try:
            repository.create_received(self.db, record)
            return IdempotencyResolution(state="new", record_id=record.id)
        except IntegrityError:
            self.db.rollback()
            existing = repository.get_by_session_and_key_hash(self.db, public_session_id=public_session_id, idempotency_key_hash=key_hash)
            if existing is None:
                raise_public_error("temporarily_unavailable")
            return self.resolve_duplicate(existing, request_hash=request_hash)

    def mark_processing(self, *, record_id: str, organisation_id: str, workspace_id: str, now: datetime) -> IdempotencyResolution:
        record = repository.transition_received_to_processing(self.db, organisation_id=organisation_id, workspace_id=workspace_id, record_id=record_id, now=now)
        if record is None:
            record = repository.get_by_tenant_record_id(self.db, organisation_id=organisation_id, workspace_id=workspace_id, record_id=record_id)
            if record is None:
                raise_public_error("temporarily_unavailable")
            return self.resolve_duplicate(record, request_hash=record.request_hash)
        return IdempotencyResolution(state="new", record_id=record.id)

    def mark_completed(self, *, record_id: str, organisation_id: str, workspace_id: str, response_snapshot: dict[str, Any], user_message_id: str | None = None, assistant_message_id: str | None = None, now: datetime | None = None) -> IdempotencyResolution:
        when = now or datetime.now(timezone.utc)
        record = repository.transition_processing_to_completed(
            self.db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            record_id=record_id,
            response_snapshot=response_snapshot,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            now=when,
        )
        if record is None:
            raise_public_error("temporarily_unavailable")
        return IdempotencyResolution(state="completed", record_id=record.id, stored_response=record.response_snapshot_json)

    def mark_failed(self, *, record_id: str, organisation_id: str, workspace_id: str, error_code: str, now: datetime | None = None) -> IdempotencyResolution:
        when = now or datetime.now(timezone.utc)
        record = repository.transition_processing_to_failed(self.db, organisation_id=organisation_id, workspace_id=workspace_id, record_id=record_id, error_code=error_code, now=when)
        if record is None:
            raise_public_error("temporarily_unavailable")
        return IdempotencyResolution(state="failed", record_id=record.id, safe_error_code=error_code)

    def resolve_duplicate(self, record: PublicMessageRequest, *, request_hash: str) -> IdempotencyResolution:
        if record.request_hash != request_hash:
            return IdempotencyResolution(state="conflict", record_id=record.id, safe_error_code="idempotency_conflict")
        if record.status == "completed":
            return IdempotencyResolution(state="completed", record_id=record.id, stored_response=record.response_snapshot_json)
        if record.status == "processing":
            return IdempotencyResolution(state="processing", record_id=record.id, safe_error_code="request_in_progress")
        if record.status == "failed":
            return IdempotencyResolution(state="failed", record_id=record.id, safe_error_code=record.error_code or "safe_internal_error")
        return IdempotencyResolution(state="processing", record_id=record.id, safe_error_code="request_in_progress")
