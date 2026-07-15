from sqlalchemy.orm import Session

from app.access.observability.events import InMemoryAccessEventSink
from app.access.sessions.service import PublicSessionChecks, PublicSessionService


def create_public_session_service(
    *,
    db: Session,
    checks: PublicSessionChecks,
    event_sink: InMemoryAccessEventSink | None = None,
) -> PublicSessionService:
    return PublicSessionService(db=db, checks=checks, event_sink=event_sink)
