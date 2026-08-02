from uuid import uuid4

from sqlalchemy import select

from app.db.models import AuditEvent, Document, DocumentVersion, Widget
from test_customer_auth_api import build_client


def test_registered_owner_can_create_publish_first_assistant_and_complete_onboarding() -> None:
    with build_client() as client:
        registered = client.post("/api/v1/auth/register", json={
            "full_name": "Mira Chen",
            "email": "mira@example.com",
            "password": "SecurePass123",
            "confirm_password": "SecurePass123",
            "organisation_name": "Acme Support",
        })
        assert registered.status_code == 201
        context = registered.json()["data"]
        organisation_id = context["organisation_id"]
        workspace_id = context["workspace_id"]

        with client.app.state.testing_session() as db:
            document = Document(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                title="Support Handbook",
                source_type="txt",
                source_key=f"support-handbook-{uuid4().hex}.txt",
                status="ready",
                visibility="workspace",
            )
            db.add(document)
            db.flush()
            version = DocumentVersion(
                organisation_id=organisation_id,
                workspace_id=workspace_id,
                document_id=document.id,
                version_number=1,
                checksum=uuid4().hex,
                processing_status="ready",
            )
            db.add(version)
            db.flush()
            document.active_document_version_id = version.id
            db.commit()
            document_id = document.id

        created = client.post(
            f"/api/v1/workspaces/{workspace_id}/widgets",
            params={"organisation_id": organisation_id},
            json={
                "display_name": "Support Assistant",
                "environment": "production",
                "initial_configuration": {
                    "bot_name": "Support Assistant",
                    "welcome_message": "Ask questions about approved support knowledge.",
                    "launcher_label": "Ask AI",
                    "primary_colour": "#1B2A4A",
                    "secondary_colour": "#F7F5F0",
                    "language": "en",
                    "show_citations": True,
                    "allow_conversation_history": True,
                    "suggested_questions_json": ["How can you help?"],
                    "max_initial_suggestions": 1,
                },
            },
        )
        assert created.status_code == 201
        widget = created.json()["data"]

        scoped = client.patch(
            f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/draft/knowledge",
            params={"organisation_id": organisation_id},
            json={"document_ids": [document_id], "expected_concurrency_version": widget["draft"]["concurrency_version"]},
        )
        assert scoped.status_code == 200
        draft = scoped.json()["data"]
        assert draft["configuration"]["knowledge_scope_json"] == [document_id]

        origin = client.post(
            f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/origins",
            params={"organisation_id": organisation_id},
            json={"origin": "https://example.com"},
        )
        assert origin.status_code == 201

        activated = client.post(
            f"/api/v1/workspaces/{workspace_id}/public-credentials/{widget['public_credential_id']}/activate",
            params={"organisation_id": organisation_id},
        )
        assert activated.status_code == 200

        validated = client.post(
            f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/validate-publish",
            params={"organisation_id": organisation_id},
            json={"draft_revision_id": draft["id"], "expected_concurrency_version": draft["concurrency_version"]},
        )
        assert validated.status_code == 200
        assert validated.json()["data"]["publishable"] is True

        published = client.post(
            f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/publish",
            params={"organisation_id": organisation_id},
            json={"draft_revision_id": draft["id"], "expected_concurrency_version": draft["concurrency_version"]},
        )
        assert published.status_code == 200
        assert published.json()["data"]["published_revision"]["configuration"]["primary_colour"].lower() == "#1b2a4a"

        embed = client.get(
            f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/embed",
            params={"organisation_id": organisation_id},
        )
        assert embed.status_code == 200
        assert embed.json()["data"]["published"] is True
        assert "data-widget-key" in embed.json()["data"]["snippet"]

        completed = client.post("/api/v1/auth/onboarding/complete")
        assert completed.status_code == 200
        assert completed.json()["data"]["onboarding_complete"] is True

        with client.app.state.testing_session() as db:
            stored_widget = db.execute(select(Widget).where(Widget.id == widget["id"])).scalar_one()
            assert stored_widget.active_published_revision_id is not None
            actions = {event.action for event in db.execute(select(AuditEvent)).scalars().all()}
            assert {"widget.created", "widget_knowledge_scope.changed", "public_credential.origin.added", "public_credential.activated", "widget.published"}.issubset(actions)