from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.api.v1.audit_events import router as audit_events_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.orgs import router as orgs_router
from app.api.v1.review import router as review_router
from app.api.v1.system import router as system_router
from app.api.v1.workspaces import router as workspaces_router

api_v1_router = APIRouter()
api_v1_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_v1_router.include_router(ai_router, prefix="/ai", tags=["ai-internal"])
api_v1_router.include_router(orgs_router, prefix="/orgs", tags=["orgs"])
api_v1_router.include_router(system_router, prefix="/system", tags=["system"])
api_v1_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_v1_router.include_router(audit_events_router, prefix="/workspaces", tags=["audit-events"])
api_v1_router.include_router(documents_router, prefix="/workspaces", tags=["documents"])
api_v1_router.include_router(conversations_router, prefix="/workspaces", tags=["conversations"])
api_v1_router.include_router(review_router, prefix="/workspaces", tags=["review"])
