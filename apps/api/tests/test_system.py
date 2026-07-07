from fastapi.testclient import TestClient

from app.main import create_app


client = TestClient(create_app())


def test_system_info_endpoint_returns_foundation_metadata() -> None:
    response = client.get("/api/v1/system/info")

    assert response.status_code == 200
    assert response.json() == {
        "name": "ChatBotWeb / Yoranix AI Platform",
        "version": "0.1.0",
        "phase": "mvp-foundation",
        "service": "chatbotweb-api",
    }
