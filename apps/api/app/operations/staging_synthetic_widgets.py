from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.credentials.service import transition_credential
from app.access.widget_admin.service import add_widget_origin, get_current_draft, publish_widget, update_draft, update_draft_knowledge_scope
from app.core.config import settings
from app.db.models import Chunk, Document, DocumentVersion, Organisation, PublicCredential, User, Widget, Workspace
from app.db.session import SessionLocal
from app.access.widget_admin.service import create_widget

REPORT_PATH = Path("artifacts/azure-staging-validation/synthetic-widgets.json")
SYNTHETIC_MARKER = "azure-staging-synthetic-widget"
ALLOWED_ENVIRONMENTS = {"staging"}
FORBIDDEN_ENVIRONMENTS = {"production", "pilot", "prod"}


@dataclass(frozen=True)
class FixtureSpec:
    key: str
    tenant_name: str
    tenant_slug: str
    workspace_name: str
    workspace_slug: str
    widget_name: str
    user_email: str
    origin: str
    bot_name: str
    welcome_message: str
    primary_colour: str
    fact_label: str
    source_title: str


ALPHA = FixtureSpec(
    key="alpha",
    tenant_name="Synthetic Tenant Alpha",
    tenant_slug="synthetic-tenant-alpha",
    workspace_name="Synthetic Workspace Alpha",
    workspace_slug="synthetic-workspace-alpha",
    widget_name="Synthetic Widget Alpha",
    user_email="synthetic-widget-alpha@example.invalid",
    origin="https://alpha.synthetic.staging.example.invalid",
    bot_name="Synthetic Alpha Assistant",
    welcome_message="Synthetic Alpha staging widget is ready.",
    primary_colour="#0f766e",
    fact_label="Alpha synthetic staging knowledge label",
    source_title="Synthetic Alpha Staging Knowledge",
)

BETA = FixtureSpec(
    key="beta",
    tenant_name="Synthetic Tenant Beta",
    tenant_slug="synthetic-tenant-beta",
    workspace_name="Synthetic Workspace Beta",
    workspace_slug="synthetic-workspace-beta",
    widget_name="Synthetic Widget Beta",
    user_email="synthetic-widget-beta@example.invalid",
    origin="https://beta.synthetic.staging.example.invalid",
    bot_name="Synthetic Beta Assistant",
    welcome_message="Synthetic Beta staging widget is ready.",
    primary_colour="#1d4ed8",
    fact_label="Beta synthetic staging knowledge label",
    source_title="Synthetic Beta Staging Knowledge",
)


def assert_staging_bootstrap_allowed(env: dict[str, str] | None = None) -> None:
    candidate = env or os.environ
    app_env = (candidate.get("APP_ENV") or "").strip().lower()
    if app_env in FORBIDDEN_ENVIRONMENTS:
        raise RuntimeError("Synthetic widget bootstrap refuses production, pilot, or prod environments.")
    if app_env not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError("Synthetic widget bootstrap only runs when APP_ENV=staging.")
    if candidate.get("WIDGET_STAGING_SYNTHETIC_BOOTSTRAP") != "1":
        raise RuntimeError("WIDGET_STAGING_SYNTHETIC_BOOTSTRAP=1 is required before staging synthetic widgets are created.")


def bootstrap_synthetic_widgets(db: Session, *, env: dict[str, str] | None = None, report_path: Path = REPORT_PATH) -> dict[str, Any]:
    assert_staging_bootstrap_allowed(env)
    alpha = _reconcile_fixture(db, ALPHA)
    beta = _reconcile_fixture(db, BETA)
    if alpha["public_key"] == beta["public_key"]:
        raise RuntimeError("Synthetic widgets must have distinct public keys.")
    if alpha["allowed_origin"] == beta["allowed_origin"]:
        raise RuntimeError("Synthetic widgets must have distinct allowed origins.")
    api_validation = _validate_public_api_if_configured(alpha, beta, env or os.environ)
    report = {
        "schema_version": "1.0",
        "environment": "staging",
        "alpha": alpha,
        "beta": beta,
        "overall_status": "ready" if alpha["knowledge_ready"] and beta["knowledge_ready"] and api_validation.get("status") != "failed" else "not_ready",
        "api_validation": api_validation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _validate_public_api_if_configured(alpha: dict[str, Any], beta: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    base_url = (env.get("STAGING_API_URL") or "").rstrip("/")
    if not base_url:
        return {"status": "not_configured"}
    if not base_url.startswith("https://"):
        raise RuntimeError("STAGING_API_URL must be an HTTPS staging API URL.")
    checks = {
        "alpha_allowed": _fetch_config_status(base_url, alpha["public_key"], alpha["allowed_origin"]),
        "beta_allowed": _fetch_config_status(base_url, beta["public_key"], beta["allowed_origin"]),
        "alpha_beta_origin_rejected": _fetch_config_status(base_url, alpha["public_key"], beta["allowed_origin"]),
        "beta_alpha_origin_rejected": _fetch_config_status(base_url, beta["public_key"], alpha["allowed_origin"]),
    }
    allowed_ok = checks["alpha_allowed"]["status_code"] == 200 and checks["beta_allowed"]["status_code"] == 200
    rejected_ok = checks["alpha_beta_origin_rejected"]["status_code"] == 403 and checks["beta_alpha_origin_rejected"]["status_code"] == 403
    published_ok = all((checks[key].get("configuration_version") or 0) > 0 and checks[key].get("published_at") for key in ("alpha_allowed", "beta_allowed"))
    return {"status": "passed" if allowed_ok and rejected_ok and published_ok else "failed", "checks": checks}


def _fetch_config_status(base_url: str, public_key: str, origin: str) -> dict[str, Any]:
    request = urllib.request.Request(f"{base_url}/api/v1/widget/{public_key}/config", headers={"Origin": origin, "X-Request-ID": "staging-synthetic-bootstrap"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
            return {"status_code": response.status, "configuration_version": body.get("configuration_version"), "published_at": body.get("published_at")}
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code}

def _reconcile_fixture(db: Session, spec: FixtureSpec) -> dict[str, Any]:
    org = _get_or_create_org(db, spec)
    user = _get_or_create_user(db, spec)
    workspace = _get_or_create_workspace(db, spec, org)
    widget = _get_or_create_widget(db, spec, org, workspace, user)
    credential = db.get(PublicCredential, widget.public_credential_id)
    if credential is None:
        raise RuntimeError(f"Synthetic widget {spec.key} is missing a public credential.")
    if credential.status != "active":
        credential = transition_credential(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, target_status="active", actor_user_id=user.id)
    _ensure_origin(db, spec, widget, user)
    document = _ensure_knowledge_document(db, spec, org, workspace, user)
    draft = get_current_draft(db, widget=widget)
    desired_config = _configuration(spec)
    needs_publish = widget.active_published_revision_id is None
    if _draft_needs_update(draft, desired_config):
        draft = update_draft(db, widget=widget, actor_user_id=user.id, payload=desired_config, expected_concurrency_version=draft.concurrency_version)
        needs_publish = True
    if list(draft.knowledge_scope_json or []) != [document.id]:
        draft = update_draft_knowledge_scope(db, widget=widget, actor_user_id=user.id, document_ids=[document.id], expected_concurrency_version=draft.concurrency_version)
        needs_publish = True
    widget.operational_status = "enabled"
    widget.pilot_status = "approved"
    widget.release_channel = "pilot"
    db.commit()
    db.refresh(widget)
    active = widget.active_published_revision_id
    if needs_publish:
        draft = get_current_draft(db, widget=widget)
        published = publish_widget(db, widget=widget, actor_user_id=user.id, draft_revision_id=draft.id, expected_concurrency_version=draft.concurrency_version)
        active = published.id
    credential = db.get(PublicCredential, widget.public_credential_id)
    return {
        "tenant_id": org.id,
        "workspace_id": workspace.id,
        "widget_id": widget.id,
        "public_key": credential.public_identifier if credential else "",
        "allowed_origin": spec.origin,
        "published_revision": active,
        "knowledge_ready": _knowledge_ready(db, document),
    }


def _get_or_create_org(db: Session, spec: FixtureSpec) -> Organisation:
    org = db.execute(select(Organisation).where(Organisation.slug == spec.tenant_slug)).scalar_one_or_none()
    if org is None:
        org = Organisation(name=spec.tenant_name, slug=spec.tenant_slug, status="active", plan_key="mvp")
        db.add(org)
        db.commit()
        db.refresh(org)
    else:
        org.name = spec.tenant_name
        org.status = "active"
        db.commit()
    return org


def _get_or_create_user(db: Session, spec: FixtureSpec) -> User:
    user = db.execute(select(User).where(User.email == spec.user_email)).scalar_one_or_none()
    if user is None:
        user = User(email=spec.user_email, full_name=f"{spec.widget_name} Bootstrap", status="active")
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.status = "active"
        db.commit()
    return user


def _get_or_create_workspace(db: Session, spec: FixtureSpec, org: Organisation) -> Workspace:
    workspace = db.execute(select(Workspace).where(Workspace.organisation_id == org.id, Workspace.slug == spec.workspace_slug)).scalar_one_or_none()
    if workspace is None:
        workspace = Workspace(organisation_id=org.id, name=spec.workspace_name, slug=spec.workspace_slug, status="active")
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
    else:
        workspace.name = spec.workspace_name
        workspace.status = "active"
        db.commit()
    return workspace


def _get_or_create_widget(db: Session, spec: FixtureSpec, org: Organisation, workspace: Workspace, user: User) -> Widget:
    widget = db.execute(select(Widget).where(Widget.organisation_id == org.id, Widget.workspace_id == workspace.id, Widget.display_name == spec.widget_name, Widget.archived_at.is_(None))).scalar_one_or_none()
    if widget is None:
        widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name=spec.widget_name, environment="staging", actor_user_id=user.id, initial_configuration=_configuration(spec))
    return widget


def _ensure_origin(db: Session, spec: FixtureSpec, widget: Widget, user: User) -> None:
    origins = { _origin_to_string(origin) for origin in widget.public_credential.origins if origin.active }
    if spec.origin in origins:
        return
    add_widget_origin(db, widget=widget, origin=spec.origin, actor_user_id=user.id)


def _ensure_knowledge_document(db: Session, spec: FixtureSpec, org: Organisation, workspace: Workspace, user: User) -> Document:
    source_key = f"{SYNTHETIC_MARKER}-{spec.key}.txt"
    document = db.execute(select(Document).where(Document.organisation_id == org.id, Document.workspace_id == workspace.id, Document.source_type == "synthetic", Document.source_key == source_key)).scalar_one_or_none()
    if document is None:
        document = Document(organisation_id=org.id, workspace_id=workspace.id, title=spec.source_title, source_type="synthetic", source_key=source_key, status="ready", category="synthetic", visibility="workspace", created_by_user_id=user.id, metadata_json={"synthetic_label": spec.key})
        db.add(document)
        db.flush()
    document.title = spec.source_title
    document.status = "ready"
    version = db.execute(select(DocumentVersion).where(DocumentVersion.document_id == document.id, DocumentVersion.version_number == 1)).scalar_one_or_none()
    if version is None:
        version = DocumentVersion(organisation_id=org.id, workspace_id=workspace.id, document_id=document.id, version_number=1, checksum=f"{SYNTHETIC_MARKER}-{spec.key}-checksum", processing_status="ready", created_by_user_id=user.id, metadata_json={"synthetic_label": spec.key})
        db.add(version)
        db.flush()
    version.processing_status = "ready"
    document.active_document_version_id = version.id
    chunk = db.execute(select(Chunk).where(Chunk.document_version_id == version.id, Chunk.chunk_index == 0)).scalar_one_or_none()
    if chunk is None:
        chunk = Chunk(organisation_id=org.id, workspace_id=workspace.id, document_id=document.id, document_version_id=version.id, chunk_index=0, content=spec.fact_label, content_hash=f"{SYNTHETIC_MARKER}-{spec.key}-chunk", token_count=len(spec.fact_label.split()), source_type="synthetic", source_title=spec.source_title, section_title=f"{spec.key.title()} synthetic staging section", page_number=1, status="ready", embedding_provider="synthetic-staging", embedding_model=settings.EMBEDDING_MODEL, embedding_dimension=settings.EMBEDDING_DIMENSION, embedding_created_at=datetime.now(timezone.utc), metadata_json={"synthetic_label": spec.key})
        db.add(chunk)
    else:
        chunk.content = spec.fact_label
        chunk.source_title = spec.source_title
        chunk.status = "ready"
        chunk.embedding_provider = chunk.embedding_provider or "synthetic-staging"
        chunk.embedding_model = chunk.embedding_model or settings.EMBEDDING_MODEL
        chunk.embedding_dimension = chunk.embedding_dimension or settings.EMBEDDING_DIMENSION
        chunk.embedding_created_at = chunk.embedding_created_at or datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)
    return document


def _configuration(spec: FixtureSpec) -> dict[str, Any]:
    return {
        "bot_name": spec.bot_name,
        "welcome_message": spec.welcome_message,
        "launcher_label": f"{spec.key.title()} synthetic chat",
        "primary_colour": spec.primary_colour,
        "secondary_colour": "#111827",
        "show_citations": True,
        "allow_conversation_history": True,
        "suggested_questions_json": [spec.fact_label, f"What does synthetic {spec.key} know?"],
        "max_initial_suggestions": 2,
        "privacy_notice_text": "Synthetic staging verification data only.",
        "privacy_notice_url": "https://example.com/privacy",
        "terms_url": "https://example.com/terms",
        "fallback_contact_text": "Synthetic staging support is unavailable.",
    }


def _draft_needs_update(draft: Any, desired: dict[str, Any]) -> bool:
    return any(getattr(draft, key) != value for key, value in desired.items())


def _knowledge_ready(db: Session, document: Document) -> bool:
    version = db.get(DocumentVersion, document.active_document_version_id) if document.active_document_version_id else None
    if document.status != "ready" or version is None or version.processing_status != "ready":
        return False
    chunk = db.execute(select(Chunk).where(Chunk.document_version_id == version.id, Chunk.status == "ready")).scalar_one_or_none()
    return chunk is not None


def _origin_to_string(origin: Any) -> str:
    host = f"*.{origin.hostname}" if origin.wildcard_subdomains else origin.hostname
    port = f":{origin.port}" if origin.port is not None else ""
    return f"{origin.scheme}://{host}{port}"


def main() -> int:
    with SessionLocal() as db:
        report = bootstrap_synthetic_widgets(db)
    print(json.dumps({"overall_status": report["overall_status"], "report": str(REPORT_PATH)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
