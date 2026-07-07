from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slug", name="uq_workspaces_organisation_slug"),
    )

    organisation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="active",
        server_default="active",
    )
    default_language: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="en",
        server_default="en",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    organisation = relationship("Organisation", back_populates="workspaces")
