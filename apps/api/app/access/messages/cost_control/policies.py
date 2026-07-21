from __future__ import annotations

from decimal import Decimal

from app.access.messages.cost_control.contracts import PublicCostPolicy
from app.access.policies.models import AccessPolicyProfile
from app.core.config import settings


def public_cost_policy_from_access_policy(policy: AccessPolicyProfile) -> PublicCostPolicy:
    return PublicCostPolicy(
        policy_key=policy.policy_key,
        selected_model_key=settings.PUBLIC_MESSAGE_DEFAULT_MODEL_KEY,
        max_message_tokens=settings.PUBLIC_MESSAGE_MAX_INPUT_TOKENS,
        retrieval_limit=policy.retrieval_limit,
        max_context_characters=policy.max_context_characters,
        max_output_tokens=policy.max_output_tokens,
        provider_timeout_seconds=policy.request_timeout_seconds,
        allowed_model_keys=tuple(policy.allowed_model_keys),
        session_message_cap=policy.max_messages_per_session,
        daily_message_quota=settings.PUBLIC_MESSAGE_DAILY_MESSAGE_QUOTA or None,
        daily_token_quota=settings.PUBLIC_MESSAGE_DAILY_TOKEN_QUOTA or None,
        daily_cost_quota=Decimal(str(settings.PUBLIC_MESSAGE_DAILY_COST_QUOTA)) if settings.PUBLIC_MESSAGE_DAILY_COST_QUOTA else None,
    )


def conservative_restricted_policy(policy: PublicCostPolicy) -> PublicCostPolicy:
    return PublicCostPolicy(
        policy_key=policy.policy_key,
        selected_model_key=policy.selected_model_key,
        max_message_tokens=policy.max_message_tokens,
        retrieval_limit=max(1, min(policy.retrieval_limit, settings.PUBLIC_MESSAGE_RESTRICTED_RETRIEVAL_LIMIT)),
        max_context_characters=max(1000, min(policy.max_context_characters, settings.PUBLIC_MESSAGE_RESTRICTED_CONTEXT_CHARACTERS)),
        max_output_tokens=max(100, min(policy.max_output_tokens, settings.PUBLIC_MESSAGE_RESTRICTED_OUTPUT_TOKENS)),
        provider_timeout_seconds=policy.provider_timeout_seconds,
        allowed_model_keys=policy.allowed_model_keys,
        session_message_cap=policy.session_message_cap,
        daily_message_quota=policy.daily_message_quota,
        daily_token_quota=policy.daily_token_quota,
        daily_cost_quota=policy.daily_cost_quota,
    )
