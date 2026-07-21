from app.access.policies.models import (
    AccessPolicyProfile,
    internal_test_policy,
    planned_partner_api_policy,
    planned_widget_policy,
)


class DuplicatePolicyError(ValueError):
    pass


class PolicyNotFoundError(LookupError):
    pass


class AccessPolicyRegistry:
    def __init__(self, profiles: list[AccessPolicyProfile] | None = None) -> None:
        self._profiles: dict[str, AccessPolicyProfile] = {}
        for profile in profiles or []:
            self.register(profile)

    def register(self, profile: AccessPolicyProfile) -> None:
        if profile.policy_key in self._profiles:
            raise DuplicatePolicyError("Policy profile already registered.")
        self._profiles[profile.policy_key] = profile

    def resolve(self, policy_key: str) -> AccessPolicyProfile:
        try:
            return self._profiles[policy_key]
        except KeyError as exc:
            raise PolicyNotFoundError("Policy profile not found.") from exc


def default_policy_registry() -> AccessPolicyRegistry:
    return AccessPolicyRegistry([internal_test_policy(), planned_widget_policy(), planned_partner_api_policy()])
