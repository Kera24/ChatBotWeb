from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Invoice, Subscription, Widget


def get_subscription_for_organisation(db: Session, *, organisation_id: str) -> Subscription | None:
    statement = select(Subscription).where(Subscription.organisation_id == organisation_id)
    return db.execute(statement).scalar_one_or_none()


def get_subscription_by_stripe_customer_id(db: Session, *, stripe_customer_id: str) -> Subscription | None:
    statement = select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
    return db.execute(statement).scalar_one_or_none()


def get_subscription_by_stripe_subscription_id(db: Session, *, stripe_subscription_id: str) -> Subscription | None:
    statement = select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
    return db.execute(statement).scalar_one_or_none()


def create_trial_subscription(
    db: Session,
    *,
    organisation_id: str,
    plan_key: str,
    trial_ends_at: datetime,
) -> Subscription:
    subscription = Subscription(
        organisation_id=organisation_id,
        plan_key=plan_key,
        status="trialing",
        trial_ends_at=trial_ends_at,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def upsert_invoice(
    db: Session,
    *,
    organisation_id: str,
    stripe_invoice_id: str,
    stripe_customer_id: str | None,
    status: str,
    amount_due_cents: int,
    amount_paid_cents: int,
    currency: str,
    hosted_invoice_url: str | None,
    invoice_pdf_url: str | None,
    period_start: datetime | None,
    period_end: datetime | None,
) -> Invoice:
    existing = db.execute(select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id)).scalar_one_or_none()
    if existing is None:
        existing = Invoice(organisation_id=organisation_id, stripe_invoice_id=stripe_invoice_id)
        db.add(existing)

    existing.stripe_customer_id = stripe_customer_id
    existing.status = status
    existing.amount_due_cents = amount_due_cents
    existing.amount_paid_cents = amount_paid_cents
    existing.currency = currency
    existing.hosted_invoice_url = hosted_invoice_url
    existing.invoice_pdf_url = invoice_pdf_url
    existing.period_start = period_start
    existing.period_end = period_end
    db.commit()
    db.refresh(existing)
    return existing


def list_invoices_for_organisation(db: Session, *, organisation_id: str, limit: int = 50) -> list[Invoice]:
    statement = (
        select(Invoice)
        .where(Invoice.organisation_id == organisation_id)
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def count_active_assistants_for_organisation(db: Session, *, organisation_id: str) -> int:
    statement = select(func.count(Widget.id)).where(
        Widget.organisation_id == organisation_id,
        Widget.archived_at.is_(None),
    )
    return int(db.execute(statement).scalar_one())
