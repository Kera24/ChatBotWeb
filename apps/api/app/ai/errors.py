class AIProviderError(Exception):
    code = "AI_PROVIDER_ERROR"

    def __init__(self, message: str = "AI provider error.") -> None:
        super().__init__(message)
        self.message = message


class AIProviderTimeoutError(AIProviderError):
    code = "AI_PROVIDER_TIMEOUT"


class AIProviderTimeoutExhaustedError(AIProviderTimeoutError):
    code = "AI_PROVIDER_TIMEOUT_EXHAUSTED"

    def __init__(self, message: str, *, last_error_code: str | None = None) -> None:
        super().__init__(message)
        self.last_error_code = last_error_code


class AIProviderUnavailableError(AIProviderError):
    code = "AI_PROVIDER_UNAVAILABLE"


class AIProviderDegradedError(AIProviderError):
    code = "AI_PROVIDER_DEGRADED"


class AIProviderRetryExhaustedError(AIProviderError):
    code = "AI_PROVIDER_RETRY_EXHAUSTED"

    def __init__(self, message: str, *, last_error_code: str | None = None) -> None:
        super().__init__(message)
        self.last_error_code = last_error_code


class AIProviderHealthCheckError(AIProviderError):
    code = "AI_PROVIDER_HEALTH_CHECK_FAILED"


class InvalidExecutionPolicyError(ValueError):
    code = "INVALID_EXECUTION_POLICY"

    def __init__(self, message: str = "Invalid provider execution policy.") -> None:
        super().__init__(message)
        self.message = message


class PromptValidationError(ValueError):
    code = "PROMPT_VALIDATION_ERROR"

    def __init__(self, message: str = "Prompt validation error.") -> None:
        super().__init__(message)
        self.message = message


class PromptNotFoundError(PromptValidationError):
    code = "PROMPT_NOT_FOUND"


class ModelNotFoundError(LookupError):
    code = "MODEL_NOT_FOUND"

    def __init__(self, message: str = "Model not found.") -> None:
        super().__init__(message)
        self.message = message


class ModelDisabledError(ModelNotFoundError):
    code = "MODEL_DISABLED"


class ProviderNotFoundError(LookupError):
    code = "PROVIDER_NOT_FOUND"

    def __init__(self, message: str = "Provider not found.") -> None:
        super().__init__(message)
        self.message = message
