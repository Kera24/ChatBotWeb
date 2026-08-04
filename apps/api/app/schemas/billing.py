from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanRead(BaseModel):
    key: str
    name: str
    price_display: str
    cadence: str
    max_assistants: int | None
    features: list[str]


class UsageRead(BaseModel):
    assistants_used: int
    assistants_limit: int | None


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organisation_id: str
    plan_key: str
    status: str
    trial_ends_at: datetime | None
    trial_days_remaining: int | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    canceled_at: datetime | None
    has_payment_method: bool
    plan: PlanRead
    usage: UsageRead


class CheckoutSessionCreate(BaseModel):
    plan_key: str = Field(min_length=1, max_length=80)


class CheckoutSessionRead(BaseModel):
    checkout_url: str


class PortalSessionRead(BaseModel):
    portal_url: str


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    amount_due_cents: int
    amount_paid_cents: int
    currency: str
    hosted_invoice_url: str | None
    invoice_pdf_url: str | None
    period_start: datetime | None
    period_end: datetime | None
    created_at: datetime
