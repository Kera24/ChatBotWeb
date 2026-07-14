from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from app.access.contracts import CostLimits, NormalisedAccessContext, PublicAccessRequest
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import CredentialResolver
from app.access.errors import raise_public_error
from app.access.policies.registry import AccessPolicyRegistry

ActiveCheck = Callable[[str], bool]
WorkspaceBelongsCheck = Callable[[str, str], bool]


@dataclass(frozen=True)
class TenantResolutionChecks:
    organisation_is_active: ActiveCheck
    workspace_is_active: ActiveCheck
    workspace_belongs_to_organisation: WorkspaceBelongsCheck


class PublicTenantResolutionService:
    def __init__(
        self,
        *,
        credential_registry: CredentialResolver,
        policy_registry: AccessPolicyRegistry,
        checks: TenantResolutionChecks,
    ) -> None:
        self.credential_registry = credential_registry
        self.policy_registry = policy_registry
        self.checks = checks

    def resolve(self, request: PublicAccessRequest) -> tuple[NormalisedAccessContext, CredentialRecord]:
        credential = self.credential_registry.resolve(request.public_credential.public_identifier)
        if credential.credential_type != request.public_credential.credential_type:
            raise_public_error("invalid_credential")
        if not self.checks.organisation_is_active(credential.organisation_id):
            raise_public_error("disabled_credential")
        if not self.checks.workspace_is_active(credential.workspace_id):
            raise_public_error("disabled_credential")
        if not self.checks.workspace_belongs_to_organisation(credential.workspace_id, credential.organisation_id):
            raise_public_error("invalid_credential")
        policy = self.policy_registry.resolve(credential.policy_profile)
        context = NormalisedAccessContext(
            request_id=request.request_id,
            trace_id=f"trace_{uuid4()}",
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            channel=request.channel,
            credential_id=credential.credential_id,
            session_id=None,
            policy_profile=policy.policy_key,
            rate_limit_identity=credential.public_identifier,
            cost_limits=CostLimits(
                max_output_tokens=policy.max_output_tokens,
                request_timeout_seconds=policy.request_timeout_seconds,
            ),
            received_at=request.received_at,
        )
        return context, credential
