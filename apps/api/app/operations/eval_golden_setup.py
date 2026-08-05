"""CLI: create/seed (or tear down) the persistent local golden-dataset fixture
used for the full evaluation cycle - baseline, improve, rerun, compare.

Unlike `eval_launch.py` (which seeds a fresh throwaway database for a single
self-contained smoke run), this script seeds a **persistent** local SQLite
database so the same dataset/run history can be reused across multiple
`eval_run`/`eval_report` invocations while iterating on an improvement.

    python -m app.operations.eval_golden_setup [--database-url URL] [--teardown]
    python -m app.operations.eval_golden_setup --real [--database-url URL] [--teardown]

`--real` seeds the fixture with a genuine semantic embedding provider
(EVAL_EMBEDDING_PROVIDER/MODEL/BASE_URL/DIMENSION - see
docs/04_Engineering/Evaluation_Real_Embedding_Provider.md) instead of the
deterministic mock, and defaults to a SEPARATE database file
(golden-eval-real.db) so the mock-embedding and real-embedding fixtures never
collide or get silently mixed. Fails clearly (no silent fallback to mock) if
the requested real provider/runtime/model is not available.

Idempotent: re-running without `--teardown` reuses the existing seeded
organisation/workspace/dataset instead of creating a duplicate, so it is safe
to run again if you forget whether you already set the fixture up.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.embedding_config import build_real_eval_embedding_provider
from app.evaluation.fixtures.loader import seed_golden_dataset
from app.repositories import evaluation_repository
from app.services.embeddings import EmbeddingProviderError, build_embedding_provider

_GOLDEN_ORG_SLUG = "golden-eval-org"
_GOLDEN_REAL_ORG_SLUG = "golden-eval-real-org"
_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "golden-eval.db"
_DEFAULT_REAL_DB_PATH = Path(__file__).resolve().parents[2] / "golden-eval-real.db"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up or tear down the persistent golden-dataset evaluation fixture.")
    parser.add_argument("--database-url", default=None, help=f"Defaults to a local SQLite file (mock: {_DEFAULT_DB_PATH}, real: {_DEFAULT_REAL_DB_PATH}).")
    parser.add_argument("--teardown", action="store_true", help="Delete the local SQLite fixture file instead of seeding it (no-op for a non-SQLite --database-url).")
    parser.add_argument("--real", action="store_true", help="Seed with a real semantic embedding provider (EVAL_EMBEDDING_*) instead of the deterministic mock.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    default_db_path = _DEFAULT_REAL_DB_PATH if args.real else _DEFAULT_DB_PATH
    database_url = args.database_url or f"sqlite:///{default_db_path}"

    if args.teardown:
        return _teardown(database_url)

    if args.real:
        try:
            embedding_provider = build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            print(f"Cannot seed a real-embedding fixture: {exc}", file=sys.stderr)
            return 2
        org_slug = _GOLDEN_REAL_ORG_SLUG
        print(f"Using real embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name} (dimension {embedding_provider.dimension}).")
    else:
        # Deliberately does NOT override settings.EMBEDDING_PROVIDER/MODEL/DIMENSION:
        # chunks are seeded with whatever embedding config is ambient right now
        # (the "local-mock"/"local-mock-v1"/1536 defaults unless overridden), so a
        # later, separate `eval_run.py` process invocation - which reads the exact
        # same settings defaults - retrieves them correctly. `_search_sqlite`
        # filters candidate chunks by an exact match on
        # (embedding_provider, embedding_model, embedding_dimension); seeding with
        # a value that differs from what `eval_run.py` will use is a silent,
        # total-retrieval-failure footgun across separate process invocations
        # (unlike `eval_launch.py`, which seeds and runs in the same process and
        # can safely use a private, self-contained override).
        embedding_provider = build_embedding_provider(
            provider_name=settings.EMBEDDING_PROVIDER, model_name=settings.EMBEDDING_MODEL, dimension=settings.EMBEDDING_DIMENSION
        )
        org_slug = _GOLDEN_ORG_SLUG

    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        existing_organisation = db.execute(select(Organisation).where(Organisation.slug == org_slug)).scalar_one_or_none()
        if existing_organisation is not None:
            workspace = db.execute(select(Workspace).where(Workspace.organisation_id == existing_organisation.id)).scalars().first()
            datasets = evaluation_repository.list_datasets(db, organisation_id=existing_organisation.id, workspace_id=workspace.id)
            dataset = datasets[0]
            print("Golden fixture already seeded - reusing existing organisation/workspace/dataset.")
        else:
            organisation = Organisation(name="Golden Evaluation Organisation", slug=org_slug, status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Golden Evaluation Workspace", slug=f"{org_slug}-workspace", status="active", default_language="en")
            user = User(email="golden-eval@example.test", full_name="Golden Evaluation")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            try:
                loaded = seed_golden_dataset(db, organisation=organisation, workspace=workspace, embedding_provider=embedding_provider, actor_user_id=user.id)
            except EmbeddingProviderError as exc:
                print(f"Embedding failed while seeding the corpus: {exc}", file=sys.stderr)
                return 2
            existing_organisation = organisation
            dataset = loaded.dataset
            print("Golden fixture seeded.")

        print(f"database-url:    {database_url}")
        print(f"organisation_id: {existing_organisation.id}")
        print(f"workspace_id:    {workspace.id}")
        print(f"dataset_id:      {dataset.id}")
        print(f"assistant_id:    {dataset.widget_id}")
        print()
        print("Set DATABASE_URL to the value above, then run the baseline with (see")
        print("docs/04_Engineering/Evaluation_Framework.md for the exact PowerShell/bash syntax):")
        real_flag = " --real" if args.real else ""
        print(
            f"  python -m app.operations.eval_run --dataset {dataset.id} --assistant {dataset.widget_id} "
            f"--organisation {existing_organisation.id} --workspace {workspace.id} --format json{real_flag}"
        )

    engine.dispose()
    return 0


def _teardown(database_url: str) -> int:
    if not database_url.startswith("sqlite"):
        print("--teardown only deletes a local SQLite fixture file; nothing to do for a non-SQLite --database-url.")
        return 0
    path = Path(database_url.replace("sqlite:///", "", 1))
    if path.exists():
        path.unlink()
        print(f"Removed golden fixture database at {path}.")
    else:
        print(f"No golden fixture database found at {path}; nothing to do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
