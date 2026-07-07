import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)


def test_can_create_tenant_foundation_models(db_session: Session) -> None:
    organisation = Organisation(name="Example College", slug="example-college")
    user = User(email="admin@example.test", full_name="Admin User")
    workspace = Workspace(
        organisation=organisation,
        name="Admissions Assistant",
        slug="admissions",
    )
    membership = Membership(
        organisation=organisation,
        user=user,
        role="client_admin",
    )

    db_session.add_all([organisation, user, workspace, membership])
    db_session.commit()

    assert organisation.id is not None
    assert workspace.organisation_id == organisation.id
    assert membership.organisation_id == organisation.id
    assert membership.user_id == user.id
    assert workspace.status == "active"
    assert user.status == "active"
