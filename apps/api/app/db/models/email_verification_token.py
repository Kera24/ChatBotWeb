from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmailVerificationToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mirrors PasswordResetToken exactly (same hashed-token/expires_at/used_at
    shape) - see app.db.models.password_reset_token."""

    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        Index("ix_email_verification_tokens_token_hash", "token_hash", unique=True),
        Index("ix_email_verification_tokens_user_expires", "user_id", "expires_at"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
