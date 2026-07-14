from app.access.channels.base import DevelopmentTestChannelAdapter
from app.access.credentials.registry import InMemoryCredentialRegistry
from app.access.gateway import ChannelRegistry, PublicAccessGateway
from app.access.observability.events import InMemoryAccessEventSink
from app.access.policies.registry import default_policy_registry
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks


def create_channel_registry() -> ChannelRegistry:
    return ChannelRegistry([DevelopmentTestChannelAdapter()])


def create_credential_registry() -> InMemoryCredentialRegistry:
    return InMemoryCredentialRegistry()


def create_policy_registry():
    return default_policy_registry()


def create_event_sink() -> InMemoryAccessEventSink:
    return InMemoryAccessEventSink()


def create_tenant_resolution_service(
    *,
    credential_registry: InMemoryCredentialRegistry,
    policy_registry,
    checks: TenantResolutionChecks,
) -> PublicTenantResolutionService:
    return PublicTenantResolutionService(
        credential_registry=credential_registry,
        policy_registry=policy_registry,
        checks=checks,
    )


def create_public_access_gateway(
    *,
    channel_registry: ChannelRegistry,
    tenant_resolution_service: PublicTenantResolutionService,
    policy_registry,
    event_sink: InMemoryAccessEventSink,
) -> PublicAccessGateway:
    return PublicAccessGateway(
        channel_registry=channel_registry,
        tenant_resolution_service=tenant_resolution_service,
        policy_registry=policy_registry,
        event_sink=event_sink,
    )
