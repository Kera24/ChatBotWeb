from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.orgs import router as orgs_router
from app.api.v1.system import router as system_router
from app.api.v1.workspaces import router as workspaces_router

api_v1_router = APIRouter()
api_v1_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_v1_router.include_router(orgs_router, prefix="/orgs", tags=["orgs"])
api_v1_router.include_router(system_router, prefix="/system", tags=["system"])
api_v1_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
