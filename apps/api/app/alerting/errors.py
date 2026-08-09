class AlertProviderError(Exception):
    code = "ALERT_PROVIDER_ERROR"

    def __init__(self, message: str = "Alert provider error.") -> None:
        super().__init__(message)
        self.message = message


class AlertProviderConfigurationError(AlertProviderError):
    code = "ALERT_PROVIDER_CONFIGURATION_ERROR"


class AlertProviderInvalidRequestError(AlertProviderError):
    code = "ALERT_PROVIDER_INVALID_REQUEST"


class AlertProviderUnavailableError(AlertProviderError):
    code = "ALERT_PROVIDER_UNAVAILABLE"
