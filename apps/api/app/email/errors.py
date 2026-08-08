class EmailProviderError(Exception):
    code = "EMAIL_PROVIDER_ERROR"

    def __init__(self, message: str = "Email provider error.") -> None:
        super().__init__(message)
        self.message = message


class EmailProviderConfigurationError(EmailProviderError):
    code = "EMAIL_PROVIDER_CONFIGURATION_ERROR"


class EmailProviderAuthenticationError(EmailProviderError):
    code = "EMAIL_PROVIDER_AUTHENTICATION_FAILED"


class EmailProviderRateLimitedError(EmailProviderError):
    code = "EMAIL_PROVIDER_RATE_LIMITED"


class EmailProviderInvalidRequestError(EmailProviderError):
    code = "EMAIL_PROVIDER_INVALID_REQUEST"


class EmailProviderUnavailableError(EmailProviderError):
    code = "EMAIL_PROVIDER_UNAVAILABLE"
