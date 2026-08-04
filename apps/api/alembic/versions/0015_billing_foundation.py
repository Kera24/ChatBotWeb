"""add subscriptions and invoices tables for Stripe billing

Revision ID: 0015_billing_foundation
Revises: 0014_assistant_scoping
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0015_billing_foundation"
down_revision: str | None = "0014_assistant_scoping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("plan_key", sa.String(length=80), nullable=False, server_default="starter"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="trialing"),
        sa.Column("stripe_customer_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=120), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organisation_id", name="uq_subscriptions_organisation_id"),
        sa.UniqueConstraint("stripe_subscription_id", name="uq_subscriptions_stripe_subscription_id"),
    )
    op.create_index("ix_subscriptions_organisation_id", "subscriptions", ["organisation_id"])
    op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])
    if dialect != "sqlite":
        op.create_foreign_key(
            "fk_subscriptions_organisation_id_organisations",
            "subscriptions",
            "organisations",
            ["organisation_id"],
            ["id"],
        )

    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_invoice_id", sa.String(length=120), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
        sa.Column("amount_due_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_paid_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="usd"),
        sa.Column("hosted_invoice_url", sa.String(length=500), nullable=True),
        sa.Column("invoice_pdf_url", sa.String(length=500), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("stripe_invoice_id", name="uq_invoices_stripe_invoice_id"),
    )
    op.create_index("ix_invoices_organisation_id", "invoices", ["organisation_id"])
    op.create_index("ix_invoices_organisation_created", "invoices", ["organisation_id", "created_at"])
    if dialect != "sqlite":
        op.create_foreign_key(
            "fk_invoices_organisation_id_organisations",
            "invoices",
            "organisations",
            ["organisation_id"],
            ["id"],
        )


def downgrade() -> None:
    op.drop_index("ix_invoices_organisation_created", table_name="invoices")
    op.drop_index("ix_invoices_organisation_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_organisation_id", table_name="subscriptions")
    op.drop_table("subscriptions")
