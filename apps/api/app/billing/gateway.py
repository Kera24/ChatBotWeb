from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import stripe
from fastapi import Request

from app.core.config import settings


class StripeSignatureError(Exception):
    """Raised when an inbound webhook payload fails signature verification."""


@dataclass(frozen=True)
class CheckoutSessionResult:
    checkout_url: str
    stripe_session_id: str


@dataclass(frozen=True)
class PortalSessionResult:
    portal_url: str


class BillingGateway(Protocol):
    def ensure_customer(self, *, organisation_id: str, email: str, existing_customer_id: str | None) -> str: ...

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_period_days: int | None,
        organisation_id: str,
    ) -> CheckoutSessionResult: ...

    def create_portal_session(self, *, customer_id: str, return_url: str) -> PortalSessionResult: ...

    def cancel_subscription(self, *, subscription_id: str, at_period_end: bool) -> dict[str, Any]: ...

    def resume_subscription(self, *, subscription_id: str) -> dict[str, Any]: ...

    def construct_event(self, *, payload: bytes, signature: str) -> dict[str, Any]: ...


class LiveBillingGateway:
    """Thin wrapper around the Stripe SDK so routers/services depend on a narrow interface
    instead of the `stripe` module directly, keeping tests free of real network calls."""

    def __init__(self) -> None:
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def ensure_customer(self, *, organisation_id: str, email: str, existing_customer_id: str | None) -> str:
        if existing_customer_id:
            return existing_customer_id
        customer = stripe.Customer.create(email=email, metadata={"organisation_id": organisation_id})
        return customer["id"]

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_period_days: int | None,
        organisation_id: str,
    ) -> CheckoutSessionResult:
        subscription_data: dict[str, Any] = {"metadata": {"organisation_id": organisation_id}}
        if trial_period_days:
            subscription_data["trial_period_days"] = trial_period_days
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data=subscription_data,
            client_reference_id=organisation_id,
        )
        return CheckoutSessionResult(checkout_url=session["url"], stripe_session_id=session["id"])

    def create_portal_session(self, *, customer_id: str, return_url: str) -> PortalSessionResult:
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        return PortalSessionResult(portal_url=session["url"])

    def cancel_subscription(self, *, subscription_id: str, at_period_end: bool) -> dict[str, Any]:
        if at_period_end:
            return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        return stripe.Subscription.cancel(subscription_id)

    def resume_subscription(self, *, subscription_id: str) -> dict[str, Any]:
        return stripe.Subscription.modify(subscription_id, cancel_at_period_end=False)

    def construct_event(self, *, payload: bytes, signature: str) -> dict[str, Any]:
        try:
            return stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        except (stripe.error.SignatureVerificationError, ValueError) as exc:
            raise StripeSignatureError(str(exc)) from exc


def create_billing_gateway() -> BillingGateway:
    return LiveBillingGateway()


def get_billing_gateway(request: Request) -> BillingGateway:
    return request.app.state.billing_gateway
