from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, SuperAdminDependency
from app.repositories.organisation_repository import (
    create_organisation,
    list_active_organisations,
)
from app.schemas.common import success_response
from app.schemas.organisation import OrganisationCreate, OrganisationRead

router = APIRouter()


@router.get("/organisations")
def list_organisations(
    db: DbSession,
    _current_user: SuperAdminDependency,
) -> dict[str, object]:
    organisations = list_active_organisations(db)
    data = [
        OrganisationRead.model_validate(organisation).model_dump(mode="json")
        for organisation in organisations
    ]
    return success_response(data)


@router.post("/organisations", status_code=status.HTTP_201_CREATED)
def create_organisation_endpoint(
    payload: OrganisationCreate,
    db: DbSession,
    _current_user: SuperAdminDependency,
) -> dict[str, object]:
    try:
        organisation = create_organisation(db, name=payload.name, slug=payload.slug)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organisation slug already exists.",
        ) from exc

    data = OrganisationRead.model_validate(organisation).model_dump(mode="json")
    return success_response(data)
