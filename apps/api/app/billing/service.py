from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.billing.plans import get_plan, plan_key_for_stripe_price_id
from app.core.config import settings
from app.db.models import Organisation, Subscription
from app.repositories.billing_repository import (
    count_active_assistants_for_organisation,
    create_trial_subscription,
    get_subscription_by_stripe_customer_id,
    get_subscription_by_stripe_subscription_id,
    get_subscription_for_organisation,
    upsert_invoice,
)
from app.schemas.billing import PlanRead, SubscriptionRead, UsageRead


class PlanLimitExceeded(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def ensure_subscription(db: Session, *, organisation: Organisation) -> Subscription:
    """Return the organisation's subscription row, lazily provisioning a free trial
    for organisations that predate the billing feature (or were seeded in tests)."""
    subscription = get_subscription_for_organisation(db, organisation_id=organisation.id)
    if subscription is not None:
        return subscription
    return start_trial(db, organisation=organisation)


def start_trial(db: Session, *, organisation: Organisation, plan_key: str = "starter") -> Subscription:
    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=settings.BILLING_TRIAL_PERIOD_DAYS)
    return create_trial_subscription(
        db,
        organisation_id=organisation.id,
        plan_key=plan_key,
        trial_ends_at=trial_ends_at,
    )


def enforce_assistant_creation_limit(db: Session, *, organisation_id: str) -> None:
    """Reject creating another assistant once an organisation with an active billing
    record has reached its plan's limit. Organisations with no subscription row yet
    (legacy data, or tests that never touch billing) are treated as unrestricted."""
    subscription = get_subscription_for_organisation(db, organisation_id=organisation_id)
    if subscription is None:
        return
    plan = get_plan(subscription.plan_key)
    if plan.max_assistants is None:
        return
    current_count = count_active_assistants_for_organisation(db, organisation_id=organisation_id)
    if current_count >= plan.max_assistants:
        raise PlanLimitExceeded(
            f"The {plan.name} plan allows up to {plan.max_assistants} assistant(s). "
            "Upgrade your plan from Billing to create more."
        )


def build_subscription_view(db: Session, *, organisation: Organisation, subscription: Subscription) -> SubscriptionRead:
    plan = get_plan(subscription.plan_key)
    now = datetime.now(timezone.utc)
    trial_days_remaining: int | None = None
    if subscription.status == "trialing" and subscription.trial_ends_at is not None:
        trial_ends_at = _as_aware(subscription.trial_ends_at)
        remaining_seconds = (trial_ends_at - now).total_seconds()
        trial_days_remaining = max(0, math.ceil(remaining_seconds / 86400))

    assistants_used = count_active_assistants_for_organisation(db, organisation_id=organisation.id)

    return SubscriptionRead(
        organisation_id=organisation.id,
        plan_key=plan.key,
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        trial_days_remaining=trial_days_remaining,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        canceled_at=subscription.canceled_at,
        has_payment_method=subscription.stripe_subscription_id is not None,
        plan=PlanRead(
            key=plan.key,
            name=plan.name,
            price_display=plan.price_display,
            cadence=plan.cadence,
            max_assistants=plan.max_assistants,
            features=list(plan.features),
        ),
        usage=UsageRead(assistants_used=assistants_used, assistants_limit=plan.max_assistants),
    )


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _as_datetime(epoch_seconds: int | None) -> datetime | None:
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)


def apply_stripe_subscription_event(db: Session, *, event_object: dict[str, Any]) -> None:
    """Sync local Subscription state from a Stripe `customer.subscription.*` event object."""
    stripe_subscription_id = event_object.get("id")
    stripe_customer_id = event_object.get("customer")
    metadata = event_object.get("metadata") or {}
    organisation_id = metadata.get("organisation_id")

    subscription = None
    if stripe_subscription_id:
        subscription = get_subscription_by_stripe_subscription_id(db, stripe_subscription_id=stripe_subscription_id)
    if subscription is None and stripe_customer_id:
        subscription = get_subscription_by_stripe_customer_id(db, stripe_customer_id=stripe_customer_id)
    if subscription is None and organisation_id:
        subscription = get_subscription_for_organisation(db, organisation_id=organisation_id)
    if subscription is None:
        return

    items = (event_object.get("items") or {}).get("data") or []
    price_id = items[0]["price"]["id"] if items and items[0].get("price") else None
    resolved_plan_key = plan_key_for_stripe_price_id(price_id)

    subscription.stripe_subscription_id = stripe_subscription_id or subscription.stripe_subscription_id
    subscription.stripe_customer_id = stripe_customer_id or subscription.stripe_customer_id
    subscription.stripe_price_id = price_id or subscription.stripe_price_id
    if resolved_plan_key:
        subscription.plan_key = resolved_plan_key
    subscription.status = event_object.get("status") or subscription.status
    subscription.cancel_at_period_end = bool(event_object.get("cancel_at_period_end"))
    subscription.current_period_start = _as_datetime(event_object.get("current_period_start"))
    subscription.current_period_end = _as_datetime(event_object.get("current_period_end"))
    trial_end = event_object.get("trial_end")
    if trial_end is not None:
        subscription.trial_ends_at = _as_datetime(trial_end)
    canceled_at = event_object.get("canceled_at")
    subscription.canceled_at = _as_datetime(canceled_at) if canceled_at else None

    db.commit()


def apply_stripe_invoice_event(db: Session, *, event_object: dict[str, Any]) -> None:
    """Upsert the local Invoice cache from a Stripe `invoice.*` event object."""
    metadata = (event_object.get("subscription_details") or {}).get("metadata") or {}
    organisation_id = metadata.get("organisation_id")
    stripe_customer_id = event_object.get("customer")

    if not organisation_id and stripe_customer_id:
        subscription = get_subscription_by_stripe_customer_id(db, stripe_customer_id=stripe_customer_id)
        organisation_id = subscription.organisation_id if subscription is not None else None
    if not organisation_id:
        return

    upsert_invoice(
        db,
        organisation_id=organisation_id,
        stripe_invoice_id=event_object["id"],
        stripe_customer_id=stripe_customer_id,
        status=event_object.get("status") or "open",
        amount_due_cents=int(event_object.get("amount_due") or 0),
        amount_paid_cents=int(event_object.get("amount_paid") or 0),
        currency=event_object.get("currency") or "usd",
        hosted_invoice_url=event_object.get("hosted_invoice_url"),
        invoice_pdf_url=event_object.get("invoice_pdf"),
        period_start=_as_datetime((event_object.get("lines", {}).get("data") or [{}])[0].get("period", {}).get("start")),
        period_end=_as_datetime((event_object.get("lines", {}).get("data") or [{}])[0].get("period", {}).get("end")),
    )
