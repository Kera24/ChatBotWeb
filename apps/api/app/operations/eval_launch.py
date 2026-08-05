"""CLI: run the launch-critical evaluation suite end to end and exit non-zero
if the release gate fails.

    python -m app.operations.eval_launch [--format text|json] [--database-url URL] [--keep-db]

Self-contained by default: seeds a throwaway SQLite database with the
synthetic "Riverside Community College" fixture (see
app/evaluation/fixtures/launch_dataset.json), runs it with the deterministic
mock provider, prints a report, and exits 1 if the regression gate fails.
No external provider credentials are required. Pass --database-url to run
against a real (e.g. staging) database instead of a temp file.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import seed_launch_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.report import render_json_report, render_text_report
from app.evaluation.summary_builder import build_run_summary
from app.services.embeddings import build_embedding_provider

_KNOWN_RETRIEVAL_LIMITATION_NOTE = (
    "Note: 'unanswerable'/'fallback_expected' hard failures above reflect a known,\n"
    "pre-existing retrieval-pipeline characteristic - there is no similarity-confidence\n"
    "threshold today, so the assistant will attempt an answer whenever ANY document is\n"
    "in scope, even for off-topic questions. This is the launch gate correctly surfacing\n"
    "a real product gap, not a defect in the evaluation harness. See docs/04_Engineering/Evaluation_Framework.md."
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the launch-critical evaluation suite with the deterministic mock provider and gate on the result."
    )
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--database-url", default=None, help="Use an existing database instead of a throwaway temp SQLite file.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the temp database file afterwards (ignored with --database-url).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    temp_db_path: Path | None = None
    if args.database_url:
        database_url = args.database_url
    else:
        temp_db_path = Path(tempfile.gettempdir()) / f"conversa-eval-launch-{os.getpid()}.db"
        database_url = f"sqlite:///{temp_db_path}"

    # Mirrors the technique tests/test_rag_orchestrator.py uses to force
    # deterministic, dependency-free embeddings for the mock run.
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "eval-launch")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    try:
        with session_factory() as db:
            organisation = Organisation(name="Launch Gate Organisation", slug=f"launch-gate-org-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Launch Gate Workspace", slug="launch-gate-workspace", status="active", default_language="en")
            user = User(email="launch-gate@example.test", full_name="Launch Gate")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            embedding_provider = build_embedding_provider(provider_name="local-mock", model_name="eval-launch", dimension=8)
            loaded = seed_launch_dataset(
                db,
                organisation=organisation,
                workspace=workspace,
                embedding_provider=embedding_provider,
                actor_user_id=user.id,
            )

            run = run_evaluation(
                db,
                dataset=loaded.dataset,
                organisation_id=organisation.id,
                workspace_id=workspace.id,
                widget_id=loaded.widget_id,
                options=EvaluationRunOptions(mode="mock", policy=load_policy_from_env(), shadow_database_url=database_url),
            )
            summary = build_run_summary(db, run_id=run.id)
            gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)

        if args.format == "json":
            print(json.dumps(render_json_report(run, summary, gate), indent=2, default=str))
        else:
            print(render_text_report(run, summary, gate))
            if not gate.passed:
                print()
                print(_KNOWN_RETRIEVAL_LIMITATION_NOTE)

        return 0 if gate.passed else 1
    finally:
        engine.dispose()
        if temp_db_path is not None and temp_db_path.exists() and not args.keep_db:
            temp_db_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
