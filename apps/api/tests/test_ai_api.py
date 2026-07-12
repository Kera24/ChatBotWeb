from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.ai.health import ProviderHealthStatus
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
    assert response.json()["detail"]["code"] == "AI_PROVIDER_TIMEOUT_EXHAUSTED"


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


def test_ai_usage_endpoint_lists_recent_records_for_super_admin(client: TestClient) -> None:
    generate_response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(),
        headers=dev_headers("super@example.test", "super_admin"),
    )
    assert generate_response.status_code == 200

    response = client.get(
        "/api/v1/ai/usage",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["outcome"] == "success"
    assert data[0]["provider_key"] == "mock"
    assert data[0]["model_key"] == "mock-grounded-answer"
    assert data[0]["prompt_key"] == "grounded_rag_answer"
    assert data[0]["prompt_version"] == "v1"
    assert data[0]["prompt_hash"]
    assert data[0]["total_tokens"] > 0
    assert Decimal(data[0]["total_estimated_cost"]) == Decimal("0")


def test_ai_usage_endpoint_records_failed_and_timed_out_executions(client: TestClient) -> None:
    failure_response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(simulate_failure=True),
        headers=dev_headers("super@example.test", "super_admin"),
    )
    timeout_response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(simulate_timeout=True),
        headers=dev_headers("super@example.test", "super_admin"),
    )
    assert failure_response.status_code == 502
    assert timeout_response.status_code == 504

    response = client.get(
        "/api/v1/ai/usage?limit=10",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    outcomes = [record["outcome"] for record in response.json()["data"]]
    assert outcomes == ["timeout", "failed"]
    assert response.json()["data"][0]["error_code"] == "AI_PROVIDER_TIMEOUT_EXHAUSTED"
    assert response.json()["data"][1]["error_code"] == "AI_PROVIDER_ERROR"


def test_ai_usage_endpoint_denies_non_super_admin(client: TestClient) -> None:
    seed_member(client, email="admin@example.test", role="client_admin")

    response = client.get(
        "/api/v1/ai/usage",
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert response.status_code == 403


def test_ai_providers_endpoint_lists_provider_health_and_models(client: TestClient) -> None:
    response = client.get(
        "/api/v1/ai/providers",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["provider_key"] == "mock"
    assert data[0]["capabilities"]["streaming"] is False
    assert data[0]["current_health"]["status"] == "unknown"
    assert data[0]["registered_models"][0]["model_key"] == "mock-grounded-answer"


def test_ai_provider_health_endpoint_and_health_check_for_super_admin(client: TestClient) -> None:
    health_response = client.get(
        "/api/v1/ai/providers/mock/health",
        headers=dev_headers("super@example.test", "super_admin"),
    )
    check_response = client.post(
        "/api/v1/ai/providers/mock/health-check",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert health_response.status_code == 200
    assert health_response.json()["data"]["status"] == "unknown"
    assert check_response.status_code == 200
    assert check_response.json()["data"]["status"] == "healthy"
    assert check_response.json()["data"]["provider_key"] == "mock"


def test_ai_provider_health_endpoint_reports_degraded_state(client: TestClient) -> None:
    provider = client.app.state.ai_core.provider_registry.get("mock")
    provider.set_health_status(ProviderHealthStatus.DEGRADED)

    response = client.post(
        "/api/v1/ai/providers/mock/health-check",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "degraded"


def test_ai_provider_health_endpoint_reports_unavailable_state(client: TestClient) -> None:
    provider = client.app.state.ai_core.provider_registry.get("mock")
    provider.set_health_status(ProviderHealthStatus.UNAVAILABLE)

    response = client.post(
        "/api/v1/ai/providers/mock/health-check",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "unavailable"


def test_ai_provider_health_unknown_provider_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/ai/providers/missing/health",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROVIDER_NOT_FOUND"


def test_ai_provider_endpoints_deny_non_super_admin(client: TestClient) -> None:
    seed_member(client, email="admin@example.test", role="client_admin")

    providers_response = client.get(
        "/api/v1/ai/providers",
        headers=dev_headers("admin@example.test", "client_admin"),
    )
    health_response = client.get(
        "/api/v1/ai/providers/mock/health",
        headers=dev_headers("admin@example.test", "client_admin"),
    )
    check_response = client.post(
        "/api/v1/ai/providers/mock/health-check",
        headers=dev_headers("admin@example.test", "client_admin"),
    )

    assert providers_response.status_code == 403
    assert health_response.status_code == 403
    assert check_response.status_code == 403


def test_ai_generate_transient_failure_then_success_accounting_via_endpoint(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/generate",
        json=generate_payload(simulate_transient_failures=1),
        headers=dev_headers("super@example.test", "super_admin"),
    )
    usage_response = client.get(
        "/api/v1/ai/usage",
        headers=dev_headers("super@example.test", "super_admin"),
    )

    assert response.status_code == 200
    record = usage_response.json()["data"][0]
    assert record["attempt_count"] == 2
    assert record["final_attempt_number"] == 2
    assert record["retry_performed"] is True
    assert record["provider_health_at_start"] == "unknown"
    assert record["provider_health_at_end"] == "healthy"
