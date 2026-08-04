from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.billing.gateway import BillingGateway, get_billing_gateway
from app.billing.plans import stripe_price_id_for_plan
from app.billing.service import ensure_subscription, build_subscription_view
from app.core.config import settings
from app.repositories.billing_repository import list_invoices_for_organisation
from app.repositories.organisation_repository import get_active_organisation
from app.repositories.user_repository import get_active_user_by_email
from app.schemas.billing import (
    CheckoutSessionCreate,
    CheckoutSessionRead,
    InvoiceRead,
    PortalSessionRead,
)
from app.schemas.common import success_response

router = APIRouter()

BillingViewerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]
BillingManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner"})),
]


def _get_organisation_or_404(db: DbSession, organisation_id: str):
    organisation = get_active_organisation(db, organisation_id=organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found.")
    return organisation


@router.get("/{organisation_id}/billing/subscription")
def get_subscription(
    organisation_id: str,
    db: DbSession,
    _current_user: BillingViewerDependency,
) -> dict[str, object]:
    organisation = _get_organisation_or_404(db, organisation_id)
    subscription = ensure_subscription(db, organisation=organisation)
    view = build_subscription_view(db, organisation=organisation, subscription=subscription)
    return success_response(view.model_dump(mode="json"))


@router.get("/{organisation_id}/billing/invoices")
def list_invoices(
    organisation_id: str,
    db: DbSession,
    _current_user: BillingViewerDependency,
    limit: int = 50,
) -> dict[str, object]:
    _get_organisation_or_404(db, organisation_id)
    bounded_limit = min(max(limit, 1), 200)
    invoices = list_invoices_for_organisation(db, organisation_id=organisation_id, limit=bounded_limit)
    data = [InvoiceRead.model_validate(invoice).model_dump(mode="json") for invoice in invoices]
    return success_response(data, meta={"limit": bounded_limit})


@router.post("/{organisation_id}/billing/checkout-session", status_code=status.HTTP_201_CREATED)
def create_checkout_session(
    organisation_id: str,
    payload: CheckoutSessionCreate,
    db: DbSession,
    current_user: BillingManagerDependency,
    gateway: Annotated[BillingGateway, Depends(get_billing_gateway)],
) -> dict[str, object]:
    organisation = _get_organisation_or_404(db, organisation_id)
    price_id = stripe_price_id_for_plan(payload.plan_key)
    if price_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown or unconfigured plan.")

    subscription = ensure_subscription(db, organisation=organisation)
    actor = get_active_user_by_email(db, email=current_user.email)
    customer_email = actor.email if actor is not None else current_user.email
    customer_id = gateway.ensure_customer(
        organisation_id=organisation.id,
        email=customer_email,
        existing_customer_id=subscription.stripe_customer_id,
    )
    if subscription.stripe_customer_id != customer_id:
        subscription.stripe_customer_id = customer_id
        db.commit()

    trial_period_days = settings.BILLING_TRIAL_PERIOD_DAYS if subscription.stripe_subscription_id is None else None
    result = gateway.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=f"{settings.WEB_ORIGIN}/billing?checkout=success",
        cancel_url=f"{settings.WEB_ORIGIN}/billing?checkout=cancelled",
        trial_period_days=trial_period_days,
        organisation_id=organisation.id,
    )
    return success_response(CheckoutSessionRead(checkout_url=result.checkout_url).model_dump(mode="json"))


@router.post("/{organisation_id}/billing/portal-session", status_code=status.HTTP_201_CREATED)
def create_portal_session(
    organisation_id: str,
    db: DbSession,
    _current_user: BillingManagerDependency,
    gateway: Annotated[BillingGateway, Depends(get_billing_gateway)],
) -> dict[str, object]:
    organisation = _get_organisation_or_404(db, organisation_id)
    subscription = ensure_subscription(db, organisation=organisation)
    if subscription.stripe_customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start a paid plan before opening the billing portal.",
        )
    result = gateway.create_portal_session(
        customer_id=subscription.stripe_customer_id,
        return_url=f"{settings.WEB_ORIGIN}/billing",
    )
    return success_response(PortalSessionRead(portal_url=result.portal_url).model_dump(mode="json"))


@router.post("/{organisation_id}/billing/cancel")
def cancel_subscription(
    organisation_id: str,
    db: DbSession,
    _current_user: BillingManagerDependency,
    gateway: Annotated[BillingGateway, Depends(get_billing_gateway)],
) -> dict[str, object]:
    organisation = _get_organisation_or_404(db, organisation_id)
    subscription = ensure_subscription(db, organisation=organisation)
    if subscription.stripe_subscription_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active paid subscription to cancel.")

    gateway.cancel_subscription(subscription_id=subscription.stripe_subscription_id, at_period_end=True)
    subscription.cancel_at_period_end = True
    db.commit()
    view = build_subscription_view(db, organisation=organisation, subscription=subscription)
    return success_response(view.model_dump(mode="json"))


@router.post("/{organisation_id}/billing/resume")
def resume_subscription(
    organisation_id: str,
    db: DbSession,
    _current_user: BillingManagerDependency,
    gateway: Annotated[BillingGateway, Depends(get_billing_gateway)],
) -> dict[str, object]:
    organisation = _get_organisation_or_404(db, organisation_id)
    subscription = ensure_subscription(db, organisation=organisation)
    if subscription.stripe_subscription_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No paid subscription to resume.")
    if not subscription.cancel_at_period_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subscription is not scheduled for cancellation.")

    gateway.resume_subscription(subscription_id=subscription.stripe_subscription_id)
    subscription.cancel_at_period_end = False
    db.commit()
    view = build_subscription_view(db, organisation=organisation, subscription=subscription)
    return success_response(view.model_dump(mode="json"))
