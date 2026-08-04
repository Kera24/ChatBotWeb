from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("organisation_id", name="uq_subscriptions_organisation_id"),
    )

    organisation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    plan_key: Mapped[str] = mapped_column(String(80), nullable=False, default="starter", server_default="starter")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="trialing", server_default="trialing")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    canceled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    organisation = relationship("Organisation", back_populates="subscription")


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("stripe_invoice_id", name="uq_invoices_stripe_invoice_id"),
    )

    organisation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(120), nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", server_default="open")
    amount_due_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    amount_paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="usd", server_default="usd")
    hosted_invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(nullable=True)

    organisation = relationship("Organisation")
