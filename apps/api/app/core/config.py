from dataclasses import dataclass
from os import getenv


def _get_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


def _get_float(name: str, default: float) -> float:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    return float(raw_value)


@dataclass(frozen=True)
class Settings:
    APP_ENV: str = getenv("APP_ENV", getenv("NODE_ENV", "development"))
    PROJECT_NAME: str = getenv("PROJECT_NAME", "ChatBotWeb / Yoranix AI Platform")
    PROJECT_DESCRIPTION: str = getenv(
        "PROJECT_DESCRIPTION",
        "Multi-tenant AI knowledge platform API",
    )
    VERSION: str = getenv("VERSION", "0.1.0")
    PHASE: str = getenv("PHASE", "mvp-foundation")
    SERVICE_NAME: str = getenv("SERVICE_NAME", "chatbotweb-api")
    API_V1_PREFIX: str = getenv("API_V1_PREFIX", "/api/v1")
    WEB_ORIGIN: str = getenv("WEB_ORIGIN", "http://localhost:3000")
    AUTH_SESSION_COOKIE_NAME: str = getenv("AUTH_SESSION_COOKIE_NAME", "yoranix_session")
    AUTH_SESSION_HASH_SECRET: str = getenv("AUTH_SESSION_HASH_SECRET", getenv("PUBLIC_SESSION_TOKEN_HASH_SECRET", "dev-auth-session-secret-change-me"))
    AUTH_SESSION_DAYS: int = _get_int("AUTH_SESSION_DAYS", 7)
    AUTH_REMEMBER_SESSION_DAYS: int = _get_int("AUTH_REMEMBER_SESSION_DAYS", 30)
    AUTH_PASSWORD_RESET_MINUTES: int = _get_int("AUTH_PASSWORD_RESET_MINUTES", 30)
    AUTH_EMAIL_VERIFICATION_MINUTES: int = _get_int("AUTH_EMAIL_VERIFICATION_MINUTES", 1440)

    # Development-header auth opt-in (app.api.deps.get_development_current_user,
    # P1-2 of the launch-readiness review). Defaults to false ("fail closed")
    # so a missing/mistaken APP_ENV can never, by itself, expose the
    # X-Development-User-Email/X-Development-Role bypass - APP_ENV being
    # development/test/testing is necessary but no longer sufficient; this
    # flag must also be explicitly enabled. See
    # app.api.deps.assert_dev_auth_policy_safe for the matching startup guard.
    ALLOW_DEV_AUTH: bool = getenv("ALLOW_DEV_AUTH", "false").lower() in {"1", "true", "yes"}

    # Transactional email provider selection (app.email.dependencies.build_email_provider).
    # Only "dev" and "resend" are recognised today - see the P0-2
    # launch-readiness task for the provider-abstraction rationale (mirrors
    # AI_PROVIDER's shape in app.ai.dependencies.create_ai_core).
    TRANSACTIONAL_EMAIL_PROVIDER: str = getenv("TRANSACTIONAL_EMAIL_PROVIDER", "dev")
    RESEND_API_KEY: str = getenv("RESEND_API_KEY", "")
    EMAIL_FROM_ADDRESS: str = getenv("EMAIL_FROM_ADDRESS", "")
    EMAIL_FROM_NAME: str = getenv("EMAIL_FROM_NAME", "Conversa")

    DATABASE_URL: str = getenv("DATABASE_URL", "sqlite:///./local.db")
    REDIS_URL: str = getenv("REDIS_URL", "redis://localhost:6379/0")
    RATE_LIMIT_IDENTITY_SECRET: str = getenv("RATE_LIMIT_IDENTITY_SECRET", "dev-rate-limit-identity-secret-change-me")
    RATE_LIMIT_REDIS_PREFIX: str = getenv("RATE_LIMIT_REDIS_PREFIX", "rate")
    RATE_LIMIT_REDIS_TIMEOUT_SECONDS: float = float(getenv("RATE_LIMIT_REDIS_TIMEOUT_SECONDS", "0.2"))
    RATE_LIMIT_LOCAL_FALLBACK_ENABLED: bool = getenv("RATE_LIMIT_LOCAL_FALLBACK_ENABLED", "false").lower() in {"1", "true", "yes"}
    PUBLIC_SESSION_TOKEN_HASH_SECRET: str = getenv("PUBLIC_SESSION_TOKEN_HASH_SECRET", "dev-public-session-token-secret-change-me")
    PUBLIC_SESSION_TOKEN_VERSION: str = getenv("PUBLIC_SESSION_TOKEN_VERSION", "v1")
    PUBLIC_SESSION_TOKEN_ID_BYTES: int = _get_int("PUBLIC_SESSION_TOKEN_ID_BYTES", 16)
    PUBLIC_SESSION_SECRET_BYTES: int = _get_int("PUBLIC_SESSION_SECRET_BYTES", 32)
    TRUSTED_PROXY_NETWORKS: str = getenv("TRUSTED_PROXY_NETWORKS", "")
    PUBLIC_WIDGET_ASSET_BASE_URL: str = getenv("PUBLIC_WIDGET_ASSET_BASE_URL", "")
    PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET: str = getenv("PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET", "dev-public-message-idempotency-secret-change-me")
    PUBLIC_MESSAGE_IDEMPOTENCY_TTL_SECONDS: int = _get_int("PUBLIC_MESSAGE_IDEMPOTENCY_TTL_SECONDS", 86400)
    PUBLIC_MESSAGE_IDEMPOTENCY_KEY_MIN_LENGTH: int = _get_int("PUBLIC_MESSAGE_IDEMPOTENCY_KEY_MIN_LENGTH", 16)
    PUBLIC_MESSAGE_IDEMPOTENCY_KEY_MAX_LENGTH: int = _get_int("PUBLIC_MESSAGE_IDEMPOTENCY_KEY_MAX_LENGTH", 160)
    PUBLIC_MESSAGE_MAX_CHARACTERS: int = _get_int("PUBLIC_MESSAGE_MAX_CHARACTERS", 4000)
    PUBLIC_MESSAGE_MAX_BYTES: int = _get_int("PUBLIC_MESSAGE_MAX_BYTES", 12288)
    PUBLIC_MESSAGE_METADATA_MAX_ITEMS: int = _get_int("PUBLIC_MESSAGE_METADATA_MAX_ITEMS", 10)
    PUBLIC_MESSAGE_METADATA_KEY_MAX_LENGTH: int = _get_int("PUBLIC_MESSAGE_METADATA_KEY_MAX_LENGTH", 60)
    PUBLIC_MESSAGE_METADATA_VALUE_MAX_LENGTH: int = _get_int("PUBLIC_MESSAGE_METADATA_VALUE_MAX_LENGTH", 240)
    PUBLIC_MESSAGE_DAILY_COST_QUOTA: str = getenv("PUBLIC_MESSAGE_DAILY_COST_QUOTA", "")
    PUBLIC_MESSAGE_DAILY_TOKEN_QUOTA: int = _get_int("PUBLIC_MESSAGE_DAILY_TOKEN_QUOTA", 0)
    PUBLIC_MESSAGE_DAILY_MESSAGE_QUOTA: int = _get_int("PUBLIC_MESSAGE_DAILY_MESSAGE_QUOTA", 0)
    PUBLIC_MESSAGE_RESTRICTED_OUTPUT_TOKENS: int = _get_int("PUBLIC_MESSAGE_RESTRICTED_OUTPUT_TOKENS", 250)
    PUBLIC_MESSAGE_RESTRICTED_CONTEXT_CHARACTERS: int = _get_int("PUBLIC_MESSAGE_RESTRICTED_CONTEXT_CHARACTERS", 4000)
    PUBLIC_MESSAGE_RESTRICTED_RETRIEVAL_LIMIT: int = _get_int("PUBLIC_MESSAGE_RESTRICTED_RETRIEVAL_LIMIT", 2)
    PUBLIC_MESSAGE_REPEATED_LOOKBACK_COUNT: int = _get_int("PUBLIC_MESSAGE_REPEATED_LOOKBACK_COUNT", 20)
    PUBLIC_MESSAGE_DEFAULT_MODEL_KEY: str = getenv("PUBLIC_MESSAGE_DEFAULT_MODEL_KEY", getenv("DEFAULT_AI_MODEL_KEY", "mock-grounded-answer"))
    PUBLIC_MESSAGE_MAX_INPUT_TOKENS: int = _get_int("PUBLIC_MESSAGE_MAX_INPUT_TOKENS", 1200)
    LOCAL_UPLOAD_ROOT: str = getenv("LOCAL_UPLOAD_ROOT", "./local_uploads")
    MAX_UPLOAD_BYTES: int = _get_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    CHUNK_SIZE_WORDS: int = _get_int("CHUNK_SIZE_WORDS", 300)
    CHUNK_OVERLAP_WORDS: int = _get_int("CHUNK_OVERLAP_WORDS", 50)
    # Knowledge Pipeline V2 (app.services.chunking_strategies). "fixed_word"
    # (the current production baseline) is the default and stays the default
    # until a bake-off (app.operations.eval_chunking_bakeoff) shows a
    # candidate is non-regressive - see docs/engineering/chunking.md. Set to
    # "structure_aware" or "structure_semantic" to opt a deployment in;
    # setting it back to "fixed_word" is the entire rollback procedure, no
    # code change required.
    # Promoted from "fixed_word" to "structure_aware" per the Knowledge
    # Pipeline V2 chunking-corpus bake-off (docs/engineering/chunking.md,
    # ADR-0031): non-regressive-to-improved on every measured axis (hit
    # rate, recall@k, pass rate, hard failures, citation coverage, token
    # cost) across two independent corpora and two embedding-provider
    # configurations. Still a one-line rollback via this env var.
    CHUNKING_STRATEGY: str = getenv("CHUNKING_STRATEGY", "structure_aware")
    CHUNKING_MIN_CHUNK_SIZE_WORDS: int = _get_int("CHUNKING_MIN_CHUNK_SIZE_WORDS", 40)
    CHUNKING_MAX_CHUNK_SIZE_WORDS: int = _get_int("CHUNKING_MAX_CHUNK_SIZE_WORDS", 500)
    # None (unset) means "use the per-embedding-model calibrated default" -
    # see app.services.chunking_strategies.semantic.recommended_semantic_similarity_threshold
    # for how that default was measured (never hardcoded without evidence).
    CHUNKING_SEMANTIC_SIMILARITY_THRESHOLD: float | None = (
        _get_float("CHUNKING_SEMANTIC_SIMILARITY_THRESHOLD", -1.0) if getenv("CHUNKING_SEMANTIC_SIMILARITY_THRESHOLD") else None
    )
    CHUNKING_SEMANTIC_MIN_UNIT_WORDS: int = _get_int("CHUNKING_SEMANTIC_MIN_UNIT_WORDS", 12)
    EMBEDDING_PROVIDER: str = getenv("EMBEDDING_PROVIDER", "local-mock")
    EMBEDDING_MODEL: str = getenv("EMBEDDING_MODEL", "local-mock-v1")
    EMBEDDING_DIMENSION: int = _get_int("EMBEDDING_DIMENSION", 1536)
    RETRIEVAL_MAX_CONTEXT_CHUNKS: int = _get_int("RETRIEVAL_MAX_CONTEXT_CHUNKS", 10)
    RETRIEVAL_MAX_CONTEXT_CHARS: int = _get_int("RETRIEVAL_MAX_CONTEXT_CHARS", 12000)
    # Defaults to 0.0 (no-op / off) rather than a positive floor: the bundled
    # "local-mock" embedding provider hashes text with no semantic content, so
    # its cosine-similarity scores are empirically uncorrelated with true
    # relevance (see docs/04_Engineering/Evaluation_Task_Specification.md,
    # Phase 8 finding) - a nonzero default here would filter retrieval
    # essentially at random until a real/semantic embedding provider exists.
    # Set this explicitly once one does.
    RETRIEVAL_MIN_SIMILARITY_SCORE: float = _get_float("RETRIEVAL_MIN_SIMILARITY_SCORE", 0.0)
    PROMPT_VERSION: str = getenv("PROMPT_VERSION", "grounded-answer-v1")

    # Generation provider selection (app.ai.dependencies.create_ai_core). Only
    # "mock" and "openrouter" are recognised today - see
    # docs/engineering/ai-system-design.md for the provider-abstraction
    # rationale. DEFAULT_AI_PROVIDER_KEY/DEFAULT_AI_MODEL_KEY below default
    # from AI_PROVIDER so existing readers of those two settings (e.g.
    # app.api.v1.settings) automatically reflect whichever provider is
    # actually wired in, without duplicating the selection concept.
    AI_PROVIDER: str = getenv("AI_PROVIDER", "mock")
    OPENROUTER_API_KEY: str = getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = getenv("OPENROUTER_MODEL", "")
    OPENROUTER_BASE_URL: str = getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    LLM_TEMPERATURE: float = _get_float("LLM_TEMPERATURE", 0.0)
    LLM_MAX_TOKENS: int = _get_int("LLM_MAX_TOKENS", 512)
    LLM_TIMEOUT_SECONDS: float = _get_float("LLM_TIMEOUT_SECONDS", 30.0)
    DEFAULT_AI_PROVIDER_KEY: str = getenv("DEFAULT_AI_PROVIDER_KEY", AI_PROVIDER)
    DEFAULT_AI_MODEL_KEY: str = getenv("DEFAULT_AI_MODEL_KEY", "openrouter-default" if AI_PROVIDER == "openrouter" else "mock-grounded-answer")
    AI_REQUEST_TIMEOUT_SECONDS: float = float(getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
    MOCK_PROVIDER_FAILURE_MODE: str = getenv("MOCK_PROVIDER_FAILURE_MODE", "disabled")
    PUBLIC_WIDGETS_ENABLED: str = getenv("PUBLIC_WIDGETS_ENABLED", "true")
    PUBLIC_WIDGET_MESSAGES_ENABLED: str = getenv("PUBLIC_WIDGET_MESSAGES_ENABLED", "true")
    PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED: str = getenv("PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED", "false")
    PUBLIC_WIDGET_PILOT_ALLOWLIST: str = getenv("PUBLIC_WIDGET_PILOT_ALLOWLIST", "")
    PUBLIC_WIDGET_DISABLED_WIDGETS: str = getenv("PUBLIC_WIDGET_DISABLED_WIDGETS", "")
    STRIPE_SECRET_KEY: str = getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_STARTER: str = getenv("STRIPE_PRICE_STARTER", "")
    STRIPE_PRICE_PROFESSIONAL: str = getenv("STRIPE_PRICE_PROFESSIONAL", "")
    STRIPE_PRICE_ENTERPRISE: str = getenv("STRIPE_PRICE_ENTERPRISE", "")
    BILLING_TRIAL_PERIOD_DAYS: int = _get_int("BILLING_TRIAL_PERIOD_DAYS", 14)
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    AZURE_MONITOR_OPEN_TELEMETRY_ENABLED: str = getenv("AZURE_MONITOR_OPEN_TELEMETRY_ENABLED", "false")
    AZURE_MONITOR_REQUIRE_CONNECTION_STRING: str = getenv("AZURE_MONITOR_REQUIRE_CONNECTION_STRING", "false")
    AZURE_MONITOR_SAMPLING_RATIO: float = float(getenv("AZURE_MONITOR_SAMPLING_RATIO", "1.0"))

    # Vendor-neutral OpenTelemetry export - an alternative to (never both at
    # once with) the Azure Monitor OTel Distro above. See
    # app.operations.telemetry.configure_observability for precedence rules.
    OTEL_ENABLED: str = getenv("OTEL_ENABLED", "false")
    OTEL_EXPORTER_OTLP_ENDPOINT: str = getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    OTEL_SERVICE_NAME: str = getenv("OTEL_SERVICE_NAME", "")
    OTEL_RESOURCE_ATTRIBUTES: str = getenv("OTEL_RESOURCE_ATTRIBUTES", "")
    OTEL_CONSOLE_EXPORT: str = getenv("OTEL_CONSOLE_EXPORT", "false")

    # AI observability trace persistence (app.observability.*).
    AI_TRACE_ENABLED: str = getenv("AI_TRACE_ENABLED", "true")
    AI_TRACE_RETENTION_DAYS: int = _get_int("AI_TRACE_RETENTION_DAYS", 90)
    AI_TRACE_CONTENT_MODE: str = getenv("AI_TRACE_CONTENT_MODE", "metadata_only")
    AI_TRACE_CUSTOM_REDACTION_PATTERNS: str = getenv("AI_TRACE_CUSTOM_REDACTION_PATTERNS", "")

    # AI observability alert thresholds (app.observability.alerts). All
    # percentages are 0-100. Evaluated over a trailing window (see
    # evaluate_alerts's `window_hours` parameter, default 1h).
    AI_ALERT_P95_LATENCY_MS: int = _get_int("AI_ALERT_P95_LATENCY_MS", 8000)
    AI_ALERT_PROVIDER_ERROR_RATE_PCT: float = _get_float("AI_ALERT_PROVIDER_ERROR_RATE_PCT", 10.0)
    AI_ALERT_FALLBACK_RATE_PCT: float = _get_float("AI_ALERT_FALLBACK_RATE_PCT", 40.0)
    AI_ALERT_EVIDENCE_INSUFFICIENT_RATE_PCT: float = _get_float("AI_ALERT_EVIDENCE_INSUFFICIENT_RATE_PCT", 30.0)
    AI_ALERT_GUARDRAIL_BLOCK_RATE_PCT: float = _get_float("AI_ALERT_GUARDRAIL_BLOCK_RATE_PCT", 20.0)
    AI_ALERT_COST_PER_REQUEST_USD: float = _get_float("AI_ALERT_COST_PER_REQUEST_USD", 0.0)
    AI_ALERT_ZERO_TRAFFIC_MINUTES: int = _get_int("AI_ALERT_ZERO_TRAFFIC_MINUTES", 60)
    AI_ALERT_MIN_SAMPLE_SIZE: int = _get_int("AI_ALERT_MIN_SAMPLE_SIZE", 5)

    # Proactive alert delivery (app.alerting.*). Only "dev", "email", and
    # "slack" are recognised today - see app.alerting.dependencies.build_alert_provider
    # for the provider-abstraction rationale (mirrors AI_PROVIDER/
    # TRANSACTIONAL_EMAIL_PROVIDER's shape). "dev" (the default) never makes
    # an external call, matching the "no external notifications from
    # dev/test unless explicitly enabled" requirement.
    ALERT_PROVIDER: str = getenv("ALERT_PROVIDER", "dev")
    ALERT_EMAIL_TO: str = getenv("ALERT_EMAIL_TO", "")
    SLACK_WEBHOOK_URL: str = getenv("SLACK_WEBHOOK_URL", "")
    # Alerts below this severity are evaluated but never delivered. One of
    # "info"/"warning"/"critical" (app.alerting.contracts.AlertSeverity).
    ALERT_MIN_SEVERITY: str = getenv("ALERT_MIN_SEVERITY", "warning")
    # Minimum seconds between two deliveries of the same alert for the same
    # tenant/assistant scope (app.alerting.cooldown.AlertCooldownStore) -
    # prevents a still-triggering condition from re-notifying on every CLI
    # run within the cooldown window.
    ALERT_COOLDOWN_SECONDS: int = _get_int("ALERT_COOLDOWN_SECONDS", 1800)
    ALERT_COOLDOWN_STATE_PATH: str = getenv("ALERT_COOLDOWN_STATE_PATH", "./local_alert_cooldown_state.json")


settings = Settings()
