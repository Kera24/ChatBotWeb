from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class PlanTier:
    key: str
    name: str
    price_display: str
    cadence: str
    max_assistants: int | None
    features: tuple[str, ...]


PLAN_CATALOG: dict[str, PlanTier] = {
    "starter": PlanTier(
        key="starter",
        name="Starter",
        price_display="$0",
        cadence="to validate your first assistant",
        max_assistants=1,
        features=("1 assistant", "Knowledge uploads", "Chatbot testing", "Basic analytics"),
    ),
    "professional": PlanTier(
        key="professional",
        name="Professional",
        price_display="$249",
        cadence="per month",
        max_assistants=10,
        features=("Up to 10 assistants", "Conversation review", "Advanced analytics", "Team access controls"),
    ),
    "enterprise": PlanTier(
        key="enterprise",
        name="Enterprise",
        price_display="Custom",
        cadence="for governed organisations",
        max_assistants=None,
        features=("Unlimited assistants", "Security review", "Priority support", "Workspace governance"),
    ),
}

PLAN_ORDER: tuple[str, ...] = ("starter", "professional", "enterprise")

# Older/interim plan_key values that predate the Stripe billing feature. Organisations
# already seeded with these values are treated as an equivalent catalog plan so existing
# data keeps working without a backfill migration.
LEGACY_PLAN_ALIASES: dict[str, str] = {
    "mvp": "starter",
    "pilot": "professional",
}


def resolve_plan_key(plan_key: str | None) -> str:
    if plan_key in PLAN_CATALOG:
        return plan_key
    if plan_key in LEGACY_PLAN_ALIASES:
        return LEGACY_PLAN_ALIASES[plan_key]
    return "starter"


def get_plan(plan_key: str | None) -> PlanTier:
    return PLAN_CATALOG[resolve_plan_key(plan_key)]


def stripe_price_id_for_plan(plan_key: str) -> str | None:
    resolved = resolve_plan_key(plan_key)
    price_by_plan = {
        "starter": settings.STRIPE_PRICE_STARTER,
        "professional": settings.STRIPE_PRICE_PROFESSIONAL,
        "enterprise": settings.STRIPE_PRICE_ENTERPRISE,
    }
    price_id = price_by_plan.get(resolved)
    return price_id or None


def plan_key_for_stripe_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None
    price_by_plan = {
        settings.STRIPE_PRICE_STARTER: "starter",
        settings.STRIPE_PRICE_PROFESSIONAL: "professional",
        settings.STRIPE_PRICE_ENTERPRISE: "enterprise",
    }
    price_by_plan.pop("", None)
    return price_by_plan.get(price_id)
