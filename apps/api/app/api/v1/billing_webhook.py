from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import DbSession
from app.billing.gateway import BillingGateway, StripeSignatureError, get_billing_gateway
from app.billing.service import apply_stripe_invoice_event, apply_stripe_subscription_event
from app.core.config import settings
from app.repositories.billing_repository import get_subscription_by_stripe_customer_id, get_subscription_for_organisation

router = APIRouter()
logger = logging.getLogger(__name__)

_SUBSCRIPTION_EVENT_TYPES = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}
_INVOICE_EVENT_TYPES = {
    "invoice.paid",
    "invoice.payment_failed",
    "invoice.finalized",
}

# Maximum raw request body accepted from Stripe. Stripe's own payloads are well under
# this size; the bound just prevents an unbounded read on a spoofed request.
_MAX_WEBHOOK_BODY_BYTES = 512 * 1024


@router.post("/billing/webhook")
async def receive_stripe_webhook(
    request: Request,
    db: DbSession,
    gateway: Annotated[BillingGateway, Depends(get_billing_gateway)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Billing webhook is not configured.")
    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header.")

    payload = await request.body()
    if len(payload) > _MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Webhook payload too large.")

    try:
        event = gateway.construct_event(payload=payload, signature=stripe_signature)
    except StripeSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.") from exc

    event_type = event.get("type", "")
    event_object = (event.get("data") or {}).get("object") or {}

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, event_object=event_object)
        elif event_type in _SUBSCRIPTION_EVENT_TYPES:
            apply_stripe_subscription_event(db, event_object=event_object)
        elif event_type in _INVOICE_EVENT_TYPES:
            apply_stripe_invoice_event(db, event_object=event_object)
    except Exception:
        db.rollback()
        logger.exception("Failed to process Stripe webhook event %s", event_type)
        # Return 200 regardless so Stripe does not retry indefinitely on a data issue
        # that a retry cannot fix; the event body is already logged for investigation.

    return {"status": "received"}


def _handle_checkout_completed(db: DbSession, *, event_object: dict) -> None:
    subscription_id = event_object.get("subscription")
    if not subscription_id:
        return
    # The full subscription payload (plan, period, trial) arrives moments later via
    # customer.subscription.created/updated, so this event only needs to ensure the
    # customer id is linked before that event lands.
    organisation_id = (event_object.get("metadata") or {}).get("organisation_id") or event_object.get("client_reference_id")
    customer_id = event_object.get("customer")
    subscription = None
    if organisation_id:
        subscription = get_subscription_for_organisation(db, organisation_id=organisation_id)
    if subscription is None and customer_id:
        subscription = get_subscription_by_stripe_customer_id(db, stripe_customer_id=customer_id)
    if subscription is None:
        return
    subscription.stripe_customer_id = customer_id or subscription.stripe_customer_id
    subscription.stripe_subscription_id = subscription_id
    db.commit()
