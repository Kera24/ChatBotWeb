from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organisation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organisations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="active",
        server_default="active",
    )
    plan_key: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="mvp",
        server_default="mvp",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    workspaces = relationship("Workspace", back_populates="organisation")
    memberships = relationship("Membership", back_populates="organisation")
