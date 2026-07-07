from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OrganisationScopedMixin:
    @declared_attr
    def organisation_id(cls) -> Mapped[str]:
        return mapped_column(
            String(36),
            ForeignKey("organisations.id"),
            nullable=False,
            index=True,
        )


class WorkspaceScopedMixin(OrganisationScopedMixin):
    @declared_attr
    def workspace_id(cls) -> Mapped[str]:
        return mapped_column(
            String(36),
            ForeignKey("workspaces.id"),
            nullable=False,
            index=True,
        )
