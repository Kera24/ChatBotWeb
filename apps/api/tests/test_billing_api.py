from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.billing.gateway import CheckoutSessionResult, PortalSessionResult, StripeSignatureError
from app.core.config import settings as real_settings
from app.db.base import Base
from app.db.models import Invoice, Membership, Organisation, Subscription, User, Workspace
from app.db.session import get_db
from app.main import create_app

TEST_STRIPE_SETTINGS = dataclasses.replace(
    real_settings,
    STRIPE_WEBHOOK_SECRET="whsec_test_secret",
    STRIPE_PRICE_STARTER="price_starter_test",
    STRIPE_PRICE_PROFESSIONAL="price_professional_test",
    STRIPE_PRICE_ENTERPRISE="price_enterprise_test",
)


class FakeBillingGateway:
    """Stand-in for the real Stripe SDK wrapper so tests never perform network calls,
    mirroring the codebase's MockAIProvider technique for substituting external services."""

    def __init__(self) -> None:
        self.customers_created: list[dict[str, object]] = []
        self.checkout_sessions_created: list[dict[str, object]] = []
        self.portal_sessions_created: list[dict[str, object]] = []
        self.cancelled: list[dict[str, object]] = []
        self.resumed: list[dict[str, object]] = []
        self.next_customer_id = "cus_fake_1"
        self.next_checkout_url = "https://checkout.stripe.com/fake-session"
        self.next_portal_url = "https://billing.stripe.com/fake-portal"
        self.next_event: dict | None = None
        self.raise_signature_error = False

    def ensure_customer(self, *, organisation_id, email, existing_customer_id):
        if existing_customer_id:
            return existing_customer_id
        self.customers_created.append({"organisation_id": organisation_id, "email": email})
        return self.next_customer_id

    def create_checkout_session(self, *, customer_id, price_id, success_url, cancel_url, trial_period_days, organisation_id):
        self.checkout_sessions_created.append({
            "customer_id": customer_id,
            "price_id": price_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "trial_period_days": trial_period_days,
            "organisation_id": organisation_id,
        })
        return CheckoutSessionResult(checkout_url=self.next_checkout_url, stripe_session_id="cs_fake_1")

    def create_portal_session(self, *, customer_id, return_url):
        self.portal_sessions_created.append({"customer_id": customer_id, "return_url": return_url})
        return PortalSessionResult(portal_url=self.next_portal_url)

    def cancel_subscription(self, *, subscription_id, at_period_end):
        self.cancelled.append({"subscription_id": subscription_id, "at_period_end": at_period_end})
        return {}

    def resume_subscription(self, *, subscription_id):
        self.resumed.append({"subscription_id": subscription_id})
        return {}

    def construct_event(self, *, payload, signature):
        if self.raise_signature_error:
            raise StripeSignatureError("bad signature")
        return self.next_event


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession
    app.state.billing_gateway = FakeBillingGateway()

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def headers(email: str, role: str = "org_owner") -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def seed_tenant(client: TestClient, *, slug: str, email: str, role: str = "org_owner", with_subscription: bool = True) -> tuple[str, str]:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active", plan_key="starter")
        user = User(email=email, full_name="Test User")
        workspace = Workspace(organisation=org, name="Primary", slug=f"{slug}-workspace-{unique}", status="active", default_language="en")
        membership = Membership(organisation=org, user=user, role=role, status="active")
        db.add_all([org, user, workspace, membership])
        db.flush()
        if with_subscription:
            db.add(Subscription(
                organisation_id=org.id,
                plan_key="starter",
                status="trialing",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            ))
        db.commit()
        return org.id, workspace.id


def create_widget_api(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, display_name: str = "Assistant"):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets",
        params={"organisation_id": organisation_id},
        headers=headers(email, "client_admin"),
        json={"display_name": display_name, "environment": "development"},
    )


def configure_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.billing.plans.settings", TEST_STRIPE_SETTINGS)
    monkeypatch.setattr("app.api.v1.billing_webhook.settings", TEST_STRIPE_SETTINGS)


def gateway(client: TestClient) -> FakeBillingGateway:
    return client.app.state.billing_gateway


# ---------------------------------------------------------------------------
# Free trial + subscription status
# ---------------------------------------------------------------------------


def test_registration_provisions_a_trialing_starter_subscription(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Ari Patel",
        "email": "ari@example.com",
        "password": "SecurePass123",
        "confirm_password": "SecurePass123",
        "organisation_name": "Acme Support",
    })
    assert response.status_code == 201
    organisation_id = response.json()["data"]["organisation_id"]

    subscription = client.get(
        f"/api/v1/orgs/{organisation_id}/billing/subscription",
        headers=headers("ari@example.com"),
    )
    assert subscription.status_code == 200
    data = subscription.json()["data"]
    assert data["plan_key"] == "starter"
    assert data["status"] == "trialing"
    assert data["trial_days_remaining"] in (13, 14)
    assert data["usage"]["assistants_limit"] == 1
    assert data["usage"]["assistants_used"] == 0


def test_billing_subscription_lazily_provisions_trial_for_legacy_organisation(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="legacy", email="owner@legacy.test", with_subscription=False)

    response = client.get(f"/api/v1/orgs/{org_id}/billing/subscription", headers=headers("owner@legacy.test"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "trialing"
    assert data["plan_key"] == "starter"

    with client.app.state.testing_session() as db:
        assert db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()


def test_viewer_role_can_read_subscription_but_contributor_cannot(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="roles", email="owner@roles.test")
    with client.app.state.testing_session() as db:
        org = db.execute(select(Organisation).where(Organisation.id == org_id)).scalar_one()
        db.add_all([
            User(email="admin@roles.test", full_name="Admin"),
            User(email="contributor@roles.test", full_name="Contributor"),
        ])
        db.flush()
        admin = db.execute(select(User).where(User.email == "admin@roles.test")).scalar_one()
        contributor = db.execute(select(User).where(User.email == "contributor@roles.test")).scalar_one()
        db.add_all([
            Membership(organisation=org, user=admin, role="client_admin", status="active"),
            Membership(organisation=org, user=contributor, role="contributor", status="active"),
        ])
        db.commit()

    ok = client.get(f"/api/v1/orgs/{org_id}/billing/subscription", headers=headers("admin@roles.test", "client_admin"))
    assert ok.status_code == 200

    forbidden = client.get(f"/api/v1/orgs/{org_id}/billing/subscription", headers=headers("contributor@roles.test", "contributor"))
    assert forbidden.status_code == 403


def test_billing_endpoints_reject_users_without_membership_in_target_organisation(client: TestClient) -> None:
    org_a, _ = seed_tenant(client, slug="tenant-a", email="owner-a@example.test")
    _org_b, _ = seed_tenant(client, slug="tenant-b", email="owner-b@example.test")

    response = client.get(f"/api/v1/orgs/{org_a}/billing/subscription", headers=headers("owner-b@example.test"))

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Checkout session
# ---------------------------------------------------------------------------


def test_checkout_session_requires_org_owner_role(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="checkout-role", email="owner@checkout-role.test")
    with client.app.state.testing_session() as db:
        org = db.execute(select(Organisation).where(Organisation.id == org_id)).scalar_one()
        db.add(User(email="admin@checkout-role.test", full_name="Admin"))
        db.flush()
        admin = db.execute(select(User).where(User.email == "admin@checkout-role.test")).scalar_one()
        db.add(Membership(organisation=org, user=admin, role="client_admin", status="active"))
        db.commit()

    response = client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout-session",
        headers=headers("admin@checkout-role.test", "client_admin"),
        json={"plan_key": "professional"},
    )

    assert response.status_code == 403


def test_checkout_session_creates_customer_and_returns_checkout_url(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="checkout", email="owner@checkout.test")

    response = client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout-session",
        headers=headers("owner@checkout.test"),
        json={"plan_key": "professional"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["checkout_url"] == "https://checkout.stripe.com/fake-session"

    fake = gateway(client)
    assert fake.customers_created == [{"organisation_id": org_id, "email": "owner@checkout.test"}]
    created_session = fake.checkout_sessions_created[0]
    assert created_session["price_id"] == "price_professional_test"
    assert created_session["organisation_id"] == org_id
    assert created_session["trial_period_days"] == 14  # first checkout, no stripe subscription yet

    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        assert subscription.stripe_customer_id == "cus_fake_1"


def test_checkout_session_omits_trial_once_a_stripe_subscription_already_exists(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="checkout-existing", email="owner@checkout-existing.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_customer_id = "cus_existing"
        subscription.stripe_subscription_id = "sub_existing"
        db.commit()

    response = client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout-session",
        headers=headers("owner@checkout-existing.test"),
        json={"plan_key": "professional"},
    )

    assert response.status_code == 201
    fake = gateway(client)
    assert fake.customers_created == []  # existing customer id reused, no new customer created
    assert fake.checkout_sessions_created[0]["trial_period_days"] is None
    assert fake.checkout_sessions_created[0]["customer_id"] == "cus_existing"


def test_checkout_session_rejects_unknown_or_unconfigured_plan(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="badplan", email="owner@badplan.test")

    response = client.post(
        f"/api/v1/orgs/{org_id}/billing/checkout-session",
        headers=headers("owner@badplan.test"),
        json={"plan_key": "professional"},
    )

    assert response.status_code == 400  # STRIPE_PRICE_PROFESSIONAL not configured in this test's env


# ---------------------------------------------------------------------------
# Customer portal
# ---------------------------------------------------------------------------


def test_portal_session_requires_existing_stripe_customer(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="portal-none", email="owner@portal-none.test")

    response = client.post(f"/api/v1/orgs/{org_id}/billing/portal-session", headers=headers("owner@portal-none.test"))

    assert response.status_code == 400


def test_portal_session_returns_portal_url_for_existing_customer(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="portal", email="owner@portal.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_customer_id = "cus_portal"
        db.commit()

    response = client.post(f"/api/v1/orgs/{org_id}/billing/portal-session", headers=headers("owner@portal.test"))

    assert response.status_code == 201
    assert response.json()["data"]["portal_url"] == "https://billing.stripe.com/fake-portal"
    assert gateway(client).portal_sessions_created == [{"customer_id": "cus_portal", "return_url": f"{real_settings.WEB_ORIGIN}/billing"}]


# ---------------------------------------------------------------------------
# Cancel / resume
# ---------------------------------------------------------------------------


def test_cancel_subscription_requires_an_active_paid_subscription(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="cancel-none", email="owner@cancel-none.test")

    response = client.post(f"/api/v1/orgs/{org_id}/billing/cancel", headers=headers("owner@cancel-none.test"))

    assert response.status_code == 400


def test_cancel_subscription_schedules_cancellation_at_period_end(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="cancel", email="owner@cancel.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_customer_id = "cus_cancel"
        subscription.stripe_subscription_id = "sub_cancel"
        subscription.status = "active"
        db.commit()

    response = client.post(f"/api/v1/orgs/{org_id}/billing/cancel", headers=headers("owner@cancel.test"))

    assert response.status_code == 200
    assert response.json()["data"]["cancel_at_period_end"] is True
    assert gateway(client).cancelled == [{"subscription_id": "sub_cancel", "at_period_end": True}]

    with client.app.state.testing_session() as db:
        assert db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one().cancel_at_period_end is True


def test_resume_subscription_requires_a_pending_cancellation(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="resume-none", email="owner@resume-none.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_subscription_id = "sub_resume_none"
        db.commit()

    response = client.post(f"/api/v1/orgs/{org_id}/billing/resume", headers=headers("owner@resume-none.test"))

    assert response.status_code == 400


def test_resume_subscription_clears_scheduled_cancellation(client: TestClient) -> None:
    org_id, _workspace_id = seed_tenant(client, slug="resume", email="owner@resume.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_subscription_id = "sub_resume"
        subscription.cancel_at_period_end = True
        db.commit()

    response = client.post(f"/api/v1/orgs/{org_id}/billing/resume", headers=headers("owner@resume.test"))

    assert response.status_code == 200
    assert response.json()["data"]["cancel_at_period_end"] is False
    assert gateway(client).resumed == [{"subscription_id": "sub_resume"}]


# ---------------------------------------------------------------------------
# Invoice history + multi-tenant isolation
# ---------------------------------------------------------------------------


def test_invoice_history_is_scoped_to_the_requesting_organisation(client: TestClient) -> None:
    org_a, _ = seed_tenant(client, slug="invoices-a", email="owner-a@invoices.test")
    org_b, _ = seed_tenant(client, slug="invoices-b", email="owner-b@invoices.test")
    with client.app.state.testing_session() as db:
        db.add_all([
            Invoice(organisation_id=org_a, stripe_invoice_id="in_a1", status="paid", amount_due_cents=1000, amount_paid_cents=1000, currency="usd"),
            Invoice(organisation_id=org_b, stripe_invoice_id="in_b1", status="paid", amount_due_cents=2000, amount_paid_cents=2000, currency="usd"),
        ])
        db.commit()

    response_a = client.get(f"/api/v1/orgs/{org_a}/billing/invoices", headers=headers("owner-a@invoices.test"))
    assert response_a.status_code == 200
    invoice_ids_a = [invoice["id"] for invoice in response_a.json()["data"]]
    with client.app.state.testing_session() as db:
        stored_a = db.execute(select(Invoice).where(Invoice.stripe_invoice_id == "in_a1")).scalar_one()
    assert invoice_ids_a == [stored_a.id]

    cross_tenant = client.get(f"/api/v1/orgs/{org_a}/billing/invoices", headers=headers("owner-b@invoices.test"))
    assert cross_tenant.status_code == 403


# ---------------------------------------------------------------------------
# Webhook signature verification + event handling
# ---------------------------------------------------------------------------


def test_webhook_rejects_missing_signature_header(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    response = client.post("/api/v1/billing/webhook", content=b"{}")
    assert response.status_code == 400


def test_webhook_is_unavailable_when_no_webhook_secret_is_configured(client: TestClient) -> None:
    # Default test settings leave STRIPE_WEBHOOK_SECRET unset, matching a real
    # deployment that has not configured Stripe yet.
    response = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=abc"})
    assert response.status_code == 503


def test_webhook_rejects_invalid_signature(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    gateway(client).raise_signature_error = True

    response = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=bad"})

    assert response.status_code == 400


def test_webhook_checkout_completed_links_stripe_subscription_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="webhook-checkout", email="owner@webhook-checkout.test")
    gateway(client).next_event = {
        "type": "checkout.session.completed",
        "data": {"object": {
            "customer": "cus_webhook_1",
            "subscription": "sub_webhook_1",
            "client_reference_id": org_id,
            "metadata": {"organisation_id": org_id},
        }},
    }

    response = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=ok"})

    assert response.status_code == 200
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        assert subscription.stripe_customer_id == "cus_webhook_1"
        assert subscription.stripe_subscription_id == "sub_webhook_1"


def test_webhook_subscription_updated_syncs_plan_status_and_period(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="webhook-sub", email="owner@webhook-sub.test")
    period_start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    period_end = int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp())
    gateway(client).next_event = {
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_updated_1",
            "customer": "cus_updated_1",
            "status": "active",
            "cancel_at_period_end": False,
            "current_period_start": period_start,
            "current_period_end": period_end,
            "trial_end": None,
            "canceled_at": None,
            "items": {"data": [{"price": {"id": "price_professional_test"}}]},
            "metadata": {"organisation_id": org_id},
        }},
    }

    response = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=ok"})

    assert response.status_code == 200
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        assert subscription.status == "active"
        assert subscription.plan_key == "professional"
        assert subscription.stripe_subscription_id == "sub_updated_1"
        assert subscription.current_period_end is not None


def test_webhook_subscription_deleted_marks_subscription_canceled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="webhook-del", email="owner@webhook-del.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_subscription_id = "sub_deleted_1"
        subscription.stripe_customer_id = "cus_deleted_1"
        db.commit()

    canceled_at = int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())
    gateway(client).next_event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {
            "id": "sub_deleted_1",
            "customer": "cus_deleted_1",
            "status": "canceled",
            "cancel_at_period_end": False,
            "canceled_at": canceled_at,
            "items": {"data": []},
            "metadata": {},
        }},
    }

    response = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=ok"})

    assert response.status_code == 200
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        assert subscription.status == "canceled"
        assert subscription.canceled_at is not None


def test_webhook_invoice_paid_upserts_invoice_and_is_idempotent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_stripe(monkeypatch)
    org_id, _workspace_id = seed_tenant(client, slug="webhook-invoice", email="owner@webhook-invoice.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.stripe_customer_id = "cus_invoice_1"
        db.commit()

    invoice_event_object = {
        "id": "in_webhook_1",
        "customer": "cus_invoice_1",
        "status": "paid",
        "amount_due": 24900,
        "amount_paid": 24900,
        "currency": "usd",
        "hosted_invoice_url": "https://invoice.stripe.com/fake",
        "invoice_pdf": "https://invoice.stripe.com/fake.pdf",
        "lines": {"data": [{"period": {"start": 1735689600, "end": 1738368000}}]},
        "subscription_details": {"metadata": {"organisation_id": org_id}},
    }
    gateway(client).next_event = {"type": "invoice.paid", "data": {"object": invoice_event_object}}

    first = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=ok"})
    second = client.post("/api/v1/billing/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=ok"})

    assert first.status_code == 200
    assert second.status_code == 200
    with client.app.state.testing_session() as db:
        invoices = list(db.execute(select(Invoice).where(Invoice.stripe_invoice_id == "in_webhook_1")).scalars().all())
        assert len(invoices) == 1
        assert invoices[0].status == "paid"
        assert invoices[0].amount_paid_cents == 24900

    listing = client.get(f"/api/v1/orgs/{org_id}/billing/invoices", headers=headers("owner@webhook-invoice.test"))
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Plan enforcement on assistant (widget) creation
# ---------------------------------------------------------------------------


def test_plan_enforcement_allows_creation_for_organisations_without_a_billing_record(client: TestClient) -> None:
    org_id, workspace_id = seed_tenant(client, slug="no-billing", email="owner@no-billing.test", with_subscription=False)

    first = create_widget_api(client, organisation_id=org_id, workspace_id=workspace_id, email="owner@no-billing.test", display_name="Assistant One")
    second = create_widget_api(client, organisation_id=org_id, workspace_id=workspace_id, email="owner@no-billing.test", display_name="Assistant Two")

    assert first.status_code == 201
    assert second.status_code == 201  # no Subscription row -> legacy/unrestricted


def test_plan_enforcement_blocks_creation_beyond_the_starter_plan_limit(client: TestClient) -> None:
    org_id, workspace_id = seed_tenant(client, slug="limited", email="owner@limited.test")  # starter plan, max 1 assistant

    first = create_widget_api(client, organisation_id=org_id, workspace_id=workspace_id, email="owner@limited.test", display_name="Assistant One")
    second = create_widget_api(client, organisation_id=org_id, workspace_id=workspace_id, email="owner@limited.test", display_name="Assistant Two")

    assert first.status_code == 201
    assert second.status_code == 402
    assert "starter" in second.json()["detail"].lower()


def test_plan_enforcement_allows_unlimited_assistants_on_the_enterprise_plan(client: TestClient) -> None:
    org_id, workspace_id = seed_tenant(client, slug="enterprise", email="owner@enterprise.test")
    with client.app.state.testing_session() as db:
        subscription = db.execute(select(Subscription).where(Subscription.organisation_id == org_id)).scalar_one()
        subscription.plan_key = "enterprise"
        subscription.status = "active"
        db.commit()

    first = create_widget_api(client, organisation_id=org_id, workspace_id=workspace_id, email="owner@enterprise.test", display_name="Assistant One")
    second = create_widget_api(client, organisation_id=org_id, workspace_id=workspace_id, email="owner@enterprise.test", display_name="Assistant Two")

    assert first.status_code == 201
    assert second.status_code == 201
