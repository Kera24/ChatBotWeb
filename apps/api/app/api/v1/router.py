from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.audit_events import router as audit_events_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.memberships import router as memberships_router
from app.api.v1.orgs import router as orgs_router
from app.api.v1.public_credentials import router as public_credentials_router
from app.api.v1.public_widget import router as public_widget_router
from app.api.v1.review import router as review_router
from app.api.v1.settings import router as settings_router
from app.api.v1.system import router as system_router
from app.api.v1.workspaces import router as workspaces_router
from app.api.v1.widgets import router as widgets_router

API_V1_ROUTER_REGISTRATIONS = (
    (admin_router, "/admin", ["admin"]),
    (ai_router, "/ai", ["ai-internal"]),
    (orgs_router, "/orgs", ["orgs"]),
    (system_router, "/system", ["system"]),
    (workspaces_router, "/workspaces", ["workspaces"]),
    (audit_events_router, "/workspaces", ["audit-events"]),
    (documents_router, "/workspaces", ["documents"]),
    (memberships_router, "/workspaces", ["memberships"]),
    (settings_router, "/workspaces", ["settings"]),
    (public_credentials_router, "/workspaces", ["public-credentials"]),
    (widgets_router, "/workspaces", ["widgets"]),
    (public_widget_router, "", ["public-widget"]),
    (conversations_router, "/workspaces", ["conversations"]),
    (review_router, "/workspaces", ["review"]),
)


def build_api_v1_router() -> APIRouter:
    router = APIRouter()
    for child_router, prefix, tags in API_V1_ROUTER_REGISTRATIONS:
        router.include_router(child_router, prefix=prefix, tags=tags)
    return router


api_v1_router = build_api_v1_router()
