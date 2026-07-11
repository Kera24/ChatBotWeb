import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def dev_headers(email: str, role: str) -> dict[str, str]:
    return {
        "X-Development-User-Email": email,
        "X-Development-Role": role,
    }


def seed_member(client: TestClient, *, email: str, role: str) -> None:
    with client.app.state.testing_session() as db:
        organisation = Organisation(name="Example College", slug="example-college")
        workspace = Workspace(organisation=organisation, name="Admissions", slug="admissions")
        user = User(email=email)
        membership = Membership(organisation=organisation, user=user, role=role)
        db.add_all([organisation, workspace, user, membership])
        db.commit()


def generate_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "prompt_key": "grounded_rag_answer",
        "model_key": "mock-grounded-answer",
        "variables": {
            "question": "What is Yoranix?",
            "context": "[1] Yoranix is a source-grounded AI platform.",
        },
    }
    payload.update(overrides)
    return payload


def test_ai_generate_endpoint_allows_super_admin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(),
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["text"].startswith("[mock:")
    assert data["provider_key"] == "mock"
    assert data["model_key"] == "mock-grounded-answer"
    assert data["prompt_key"] == "grounded_rag_answer"
    assert data["prompt_hash"]
    assert data["token_usage"]["total_tokens"] > 0


def test_ai_generate_endpoint_denies_non_super_admin(client: TestClient) -> None:
    seed_member(client, email="admin@example.test", role="client_admin")

    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(),
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 403


def test_ai_generate_endpoint_returns_structured_provider_failure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(simulate_failure=True),
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "AI_PROVIDER_ERROR",
        "message": "Mock provider failure simulation requested.",
    }


def test_ai_generate_endpoint_returns_structured_provider_timeout(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(simulate_timeout=True),
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "AI_PROVIDER_TIMEOUT"


def test_ai_generate_endpoint_returns_prompt_variable_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(variables={"question": "Missing context"}),
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "PROMPT_VALIDATION_ERROR"


def test_ai_generate_endpoint_returns_missing_model_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(model_key="missing-model"),
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "MODEL_NOT_FOUND"
