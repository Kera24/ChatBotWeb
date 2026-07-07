from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("auth_provider", "external_auth_id", name="uq_users_auth_identity"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    auth_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    external_auth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="active",
        server_default="active",
    )

    memberships = relationship("Membership", back_populates="user")
