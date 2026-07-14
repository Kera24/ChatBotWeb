from app.access.rate_limit.contracts import RateLimitRule


def validate_rate_limit_rules(rules: tuple[RateLimitRule, ...]) -> tuple[RateLimitRule, ...]:
    seen: set[str] = set()
    for rule in rules:
        if rule.rule_key in seen:
            raise ValueError("Duplicate rate-limit rule key.")
        seen.add(rule.rule_key)
    return rules


def rules_for_category(policy_profile: object, category: str) -> list[RateLimitRule]:
    rules = getattr(policy_profile, "rate_limit_rules", ())
    return sorted(
        [rule for rule in rules if rule.enabled and rule.category == category],
        key=lambda rule: (rule.priority, rule.rule_key),
    )


def internal_test_rate_limit_rules() -> tuple[RateLimitRule, ...]:
    return validate_rate_limit_rules(
        (
            RateLimitRule("internal_test_global", "internal_test", "global", capacity=1000, refill_tokens=1000, refill_period_seconds=60, fail_mode="fail_closed", priority=10),
        )
    )


def widget_rate_limit_rules() -> tuple[RateLimitRule, ...]:
    return validate_rate_limit_rules(
        (
            RateLimitRule("widget_config_global", "widget_config_read", "global", capacity=1000, refill_tokens=1000, refill_period_seconds=60, fail_mode="constrained_fail_open", priority=10),
            RateLimitRule("widget_config_credential", "widget_config_read", "credential", capacity=120, refill_tokens=120, refill_period_seconds=60, fail_mode="constrained_fail_open", priority=20),
            RateLimitRule("widget_config_ip", "widget_config_read", "ip", capacity=60, refill_tokens=60, refill_period_seconds=60, fail_mode="constrained_fail_open", priority=30),
            RateLimitRule("widget_session_credential", "widget_session_create", "credential", capacity=20, refill_tokens=20, refill_period_seconds=60, fail_mode="fail_closed", priority=10),
            RateLimitRule("widget_session_workspace", "widget_session_create", "workspace", capacity=200, refill_tokens=200, refill_period_seconds=3600, fail_mode="fail_closed", priority=20),
            RateLimitRule("widget_session_ip", "widget_session_create", "ip", capacity=10, refill_tokens=10, refill_period_seconds=60, fail_mode="fail_closed", priority=30),
            RateLimitRule("widget_message_credential", "widget_message_send", "credential", capacity=30, refill_tokens=30, refill_period_seconds=60, fail_mode="fail_closed", priority=10),
            RateLimitRule("widget_message_workspace", "widget_message_send", "workspace", capacity=300, refill_tokens=300, refill_period_seconds=3600, fail_mode="fail_closed", priority=20),
            RateLimitRule("widget_message_ip", "widget_message_send", "ip", capacity=10, refill_tokens=10, refill_period_seconds=60, fail_mode="fail_closed", priority=30),
        )
    )


def partner_api_rate_limit_rules() -> tuple[RateLimitRule, ...]:
    return validate_rate_limit_rules(
        (
            RateLimitRule("partner_api_credential", "partner_api_request", "credential", capacity=120, refill_tokens=120, refill_period_seconds=60, fail_mode="fail_closed", priority=10),
            RateLimitRule("partner_api_workspace", "partner_api_request", "workspace", capacity=1000, refill_tokens=1000, refill_period_seconds=3600, fail_mode="fail_closed", priority=20),
            RateLimitRule("partner_api_ip", "partner_api_request", "ip", capacity=240, refill_tokens=240, refill_period_seconds=60, fail_mode="fail_closed", priority=30),
        )
    )
