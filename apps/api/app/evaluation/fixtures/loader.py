"""Seed a synthetic evaluation dataset (documents, chunks, assistant, dataset,
cases) into a workspace. Two fixtures ship today: `launch_dataset.json` (the
minimal launch-critical smoke suite used by `eval:launch`/`eval:test`) and
`golden_dataset.json` (the larger, deliberately-constructed golden dataset
used for the full baseline/improve/rerun evaluation cycle - see
docs/04_Engineering/Evaluation_Task_Specification.md).

Documents are hand-inserted the same way `tests/test_rag_orchestrator.py`
seeds chunks for tests - short-circuiting the real upload/extract/chunk
pipeline (which needs files on disk) in favour of directly creating
Document/DocumentVersion/Chunk rows. `embedding_vector` is only populated on
Postgres, mirroring `embed_document_version_chunks`'s own guard, since on
SQLite retrieval recomputes embeddings from `chunk.content` at query time
(see app.services.vector_search._search_sqlite).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.access.widget_admin.service import create_widget
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, Membership, Organisation, User, Workspace
from app.services.embeddings import EmbeddingProvider

FIXTURE_PATH = Path(__file__).parent / "launch_dataset.json"
GOLDEN_FIXTURE_PATH = Path(__file__).parent / "golden_dataset.json"

_PLACEHOLDER_KEYS = {
    "workspace_id": "__foreign_workspace_id__",
    "widget_id": "__foreign_widget_id__",
}


@dataclass(frozen=True)
class LoadedLaunchDataset:
    dataset: EvaluationDataset
    widget_id: str
    document_ids: dict[str, str]
    foreign_organisation_id: str
    foreign_workspace_id: str
    foreign_widget_id: str


def _seed_foreign_tenant(db: Session, *, suffix: str) -> tuple[str, str, str]:
    """A second, unrelated organisation/workspace/assistant used only as the
    attempted (and expected-to-be-rejected) target of cross-tenant leakage
    cases. It intentionally has no evaluation dataset of its own.

    Leakage cases keep the caller's own organisation_id and only swap in this
    tenant's workspace_id/widget_id (see launch_dataset.json), so the attempt
    is a genuine cross-tenant IDOR - the (organisation_id, workspace_id,
    widget_id) triple `get_widget` checks never matches a real widget - rather
    than a self-consistent, and therefore legitimate, request to the foreign
    tenant's own assistant."""
    organisation = Organisation(name=f"Foreign Org {suffix}", slug=f"foreign-org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Foreign Workspace", slug=f"foreign-workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"foreign-owner-{suffix}@example.test", full_name="Foreign Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()

    widget = create_widget(
        db,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        display_name="Foreign Assistant",
        environment="development",
        actor_user_id=user.id,
    )
    return organisation.id, workspace.id, widget.id


def load_fixture_definition() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def load_golden_fixture_definition() -> dict:
    return json.loads(GOLDEN_FIXTURE_PATH.read_text(encoding="utf-8"))


_CASE_METADATA_PASSTHROUGH_KEYS = ("notes", "expected_clarification", "forbidden_answer_points", "citation_required")


def _build_case_metadata(case: dict, *, placeholder_values: dict[str, str]) -> dict | None:
    """Merge the optional, non-schema case attributes a fixture may declare
    (isolation-attempt target, authoring notes, clarification expectation,
    forbidden answer content, an explicit citation requirement independent of
    category) into the single `metadata_json` column, rather than adding a new
    migration column per attribute. These are dataset-authoring/reporting
    signals; only `cross_tenant_attempt` and `citation_required` currently
    feed automatic scoring (see app.evaluation.engine/scoring) - the rest are
    surfaced for human review in the admin UI and reports."""
    metadata: dict = {}
    if "cross_tenant_attempt" in case:
        metadata["cross_tenant_attempt"] = {field: placeholder_values.get(value, value) for field, value in case["cross_tenant_attempt"].items()}
    for key in _CASE_METADATA_PASSTHROUGH_KEYS:
        if key in case:
            metadata[key] = case[key]
    return metadata or None


def seed_launch_dataset(
    db: Session,
    *,
    organisation: Organisation,
    workspace: Workspace,
    embedding_provider: EmbeddingProvider,
    actor_user_id: str | None = None,
    fixture: dict | None = None,
) -> LoadedLaunchDataset:
    fixture = fixture or load_fixture_definition()
    can_store_vector = db.bind is not None and db.bind.dialect.name == "postgresql"
    now = datetime.now(timezone.utc)

    document_ids: dict[str, str] = {}
    for doc in fixture["documents"]:
        document = Document(
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            title=doc["title"],
            source_type="txt",
            source_key=f"{doc['key']}.txt",
            status="ready",
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            document_id=document.id,
            version_number=1,
            checksum=f"checksum-{doc['key']}",
            processing_status="ready",
        )
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id

        chunk = Chunk(
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=0,
            content=doc["content"],
            content_hash=f"hash-{doc['key']}",
            token_count=len(doc["content"].split()),
            source_type="txt",
            source_title=doc["title"],
            status="ready",
            embedding_provider=embedding_provider.provider_name,
            embedding_model=embedding_provider.model_name,
            embedding_dimension=embedding_provider.dimension,
            embedding_created_at=now,
        )
        if can_store_vector:
            chunk.embedding_vector = embedding_provider.embed(doc["content"])
        db.add(chunk)
        document_ids[doc["key"]] = document.id

    db.commit()

    widget = create_widget(
        db,
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        display_name=fixture["assistant"]["display_name"],
        environment="development",
        actor_user_id=actor_user_id,
        initial_configuration={"knowledge_scope_json": list(document_ids.values())},
    )

    dataset = EvaluationDataset(
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        widget_id=widget.id,
        name=fixture["dataset"]["name"],
        description=fixture["dataset"].get("description"),
        version=fixture["dataset"].get("version", "1"),
        status="active",
        created_by=actor_user_id,
    )
    db.add(dataset)
    db.flush()

    foreign_organisation_id, foreign_workspace_id, foreign_widget_id = _seed_foreign_tenant(db, suffix=workspace.id[:8])
    placeholder_values = {
        _PLACEHOLDER_KEYS["workspace_id"]: foreign_workspace_id,
        _PLACEHOLDER_KEYS["widget_id"]: foreign_widget_id,
    }

    for case in fixture["cases"]:
        expected_document_ids = [document_ids[key] for key in case.get("expected_document_keys", [])] or None
        metadata_json = _build_case_metadata(case, placeholder_values=placeholder_values)
        db.add(EvaluationCase(
            dataset_id=dataset.id,
            organisation_id=organisation.id,
            workspace_id=workspace.id,
            question=case["question"],
            reference_answer=case.get("reference_answer"),
            expected_document_ids=expected_document_ids,
            expected_source_labels=case.get("expected_source_labels"),
            expected_answerability=case["expected_answerability"],
            category=case["category"],
            tags=case.get("tags"),
            metadata_json=metadata_json,
        ))
    db.commit()
    db.refresh(dataset)

    return LoadedLaunchDataset(
        dataset=dataset,
        widget_id=widget.id,
        document_ids=document_ids,
        foreign_organisation_id=foreign_organisation_id,
        foreign_workspace_id=foreign_workspace_id,
        foreign_widget_id=foreign_widget_id,
    )


def seed_golden_dataset(
    db: Session,
    *,
    organisation: Organisation,
    workspace: Workspace,
    embedding_provider: EmbeddingProvider,
    actor_user_id: str | None = None,
    fixture: dict | None = None,
) -> LoadedLaunchDataset:
    """Seed the larger, deliberately-constructed golden dataset
    (golden_dataset.json) used for the full evaluation cycle. Shares every
    seeding mechanic with `seed_launch_dataset` - only the fixture JSON
    differs - so there is exactly one place tenant isolation, chunk seeding,
    and case-metadata handling are implemented."""
    return seed_launch_dataset(
        db,
        organisation=organisation,
        workspace=workspace,
        embedding_provider=embedding_provider,
        actor_user_id=actor_user_id,
        fixture=fixture or load_golden_fixture_definition(),
    )
