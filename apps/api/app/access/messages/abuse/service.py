from __future__ import annotations

from app.access.messages.abuse.contracts import AbuseCheckRequest, AbuseDecision, AbusePolicy, AbuseReasonCode
from app.access.messages.abuse.rules import DEFAULT_ABUSE_RULES, AbuseRule

_RESTRICTION_REASONS = {"repeated_message", "excessive_repetition", "excessive_urls", "suspicious_automation"}
_BLOCK_REASONS = {"policy_violation"}


def default_abuse_policy(policy_profile: str) -> AbusePolicy:
    if policy_profile == "internal_test":
        return AbusePolicy(policy_key="internal_test", max_urls_per_message=8, repeated_message_limit=3, suspicious_pattern_action="allow_with_restrictions")
    if policy_profile == "partner_api":
        return AbusePolicy(policy_key="partner_api", max_urls_per_message=8, repeated_message_limit=3)
    return AbusePolicy(policy_key="widget")


class PublicMessageAbuseService:
    def __init__(self, *, rules: tuple[AbuseRule, ...] = DEFAULT_ABUSE_RULES, policy: AbusePolicy | None = None) -> None:
        self.rules = rules
        self.policy = policy

    def evaluate(self, request: AbuseCheckRequest) -> AbuseDecision:
        policy = self.policy or default_abuse_policy(request.policy_profile)
        reasons: list[AbuseReasonCode] = []
        metadata_reasons: list[str] = []
        evaluated: list[str] = []
        for rule in self.rules:
            evaluated.append(rule.stable_id)
            reason, metadata_reason = rule.evaluate(request.canonical_message, policy, request.recent_session_message_fingerprints, request.message_hash)
            if reason is not None and reason not in reasons:
                reasons.append(reason)
            if metadata_reason is not None:
                metadata_reasons.append(metadata_reason)
        if not reasons:
            return AbuseDecision(status="allow", reason_codes=("none",), safe_metadata={"reason_count": 0}, evaluated_rules=tuple(evaluated))

        should_block = any(reason in _BLOCK_REASONS for reason in reasons)
        if should_block:
            return AbuseDecision(
                status="block_session",
                reason_codes=tuple(reasons),
                should_block_session=True,
                safe_public_error_code="unsafe_request",
                safe_metadata={"reason_count": len(reasons)},
                evaluated_rules=tuple(evaluated),
            )
        severe = {"encoded_payload", "system_prompt_extraction", "instruction_override", "cross_tenant_probe", "unsupported_payload", "unsafe_control_pattern"}
        if any(reason in severe for reason in reasons):
            return AbuseDecision(
                status="reject",
                reason_codes=tuple(reasons),
                safe_public_error_code="unsafe_request",
                safe_metadata={"reason_count": len(reasons)},
                evaluated_rules=tuple(evaluated),
            )
        if any(reason in _RESTRICTION_REASONS for reason in reasons):
            return AbuseDecision(
                status="allow_with_restrictions",
                reason_codes=tuple(reasons),
                restriction_profile="conservative_public_answer",
                safe_metadata={"reason_count": len(reasons)},
                evaluated_rules=tuple(evaluated),
            )
        return AbuseDecision(status="reject", reason_codes=tuple(reasons), safe_public_error_code="unsafe_request", safe_metadata={"reason_count": len(reasons)}, evaluated_rules=tuple(evaluated))
