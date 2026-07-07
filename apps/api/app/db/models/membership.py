from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organisation_id", "user_id", name="uq_memberships_organisation_user"),
    )

    organisation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="active",
        server_default="active",
    )

    organisation = relationship("Organisation", back_populates="memberships")
    user = relationship("User", back_populates="memberships")
