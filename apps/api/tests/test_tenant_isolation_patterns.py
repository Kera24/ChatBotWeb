import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.repositories.membership_repository import get_membership_for_organisation
from app.repositories.workspace_repository import (
    get_workspace_for_organisation,
    list_workspaces_for_organisation,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)


def seed_two_tenants(db_session: Session) -> tuple[Organisation, Organisation, Workspace, User]:
    org_a = Organisation(name="Alpha College", slug="alpha")
    org_b = Organisation(name="Beta Clinic", slug="beta")
    user = User(email="owner@example.test")
    workspace_a = Workspace(organisation=org_a, name="Admissions", slug="admissions")
    workspace_b = Workspace(organisation=org_b, name="Patient Help", slug="patient-help")
    membership_a = Membership(organisation=org_a, user=user, role="org_owner")

    db_session.add_all([org_a, org_b, user, workspace_a, workspace_b, membership_a])
    db_session.commit()

    return org_a, org_b, workspace_a, user


def test_workspace_lookup_requires_matching_organisation_context(db_session: Session) -> None:
    org_a, org_b, workspace_a, _user = seed_two_tenants(db_session)

    correct_scope_result = get_workspace_for_organisation(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
    )
    wrong_scope_result = get_workspace_for_organisation(
        db_session,
        organisation_id=org_b.id,
        workspace_id=workspace_a.id,
    )

    assert correct_scope_result is not None
    assert correct_scope_result.id == workspace_a.id
    assert wrong_scope_result is None


def test_workspace_list_stays_inside_organisation_scope(db_session: Session) -> None:
    org_a, org_b, workspace_a, _user = seed_two_tenants(db_session)

    org_a_workspaces = list_workspaces_for_organisation(db_session, organisation_id=org_a.id)
    org_b_workspaces = list_workspaces_for_organisation(db_session, organisation_id=org_b.id)

    assert [workspace.id for workspace in org_a_workspaces] == [workspace_a.id]
    assert all(workspace.organisation_id == org_b.id for workspace in org_b_workspaces)


def test_membership_lookup_requires_organisation_context(db_session: Session) -> None:
    org_a, org_b, _workspace_a, user = seed_two_tenants(db_session)

    correct_scope_result = get_membership_for_organisation(
        db_session,
        organisation_id=org_a.id,
        user_id=user.id,
    )
    wrong_scope_result = get_membership_for_organisation(
        db_session,
        organisation_id=org_b.id,
        user_id=user.id,
    )

    assert correct_scope_result is not None
    assert correct_scope_result.role == "org_owner"
    assert wrong_scope_result is None
