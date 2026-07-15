from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PublicAccessErrorDetail:
    code: str
    message: str
    retryable: bool
    http_status: int
    retry_after_seconds: int | None = None

    def to_public_dict(self) -> dict[str, object]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


class PublicAccessError(Exception):
    detail: PublicAccessErrorDetail

    def __init__(self, detail: PublicAccessErrorDetail) -> None:
        super().__init__(detail.message)
        self.detail = detail

    @property
    def code(self) -> str:
        return self.detail.code

    def to_public_dict(self) -> dict[str, object]:
        return self.detail.to_public_dict()


def error_detail(code: str, retry_after_seconds: int | None = None) -> PublicAccessErrorDetail:
    try:
        base = ERROR_CATALOG[code]
    except KeyError as exc:
        base = ERROR_CATALOG["safe_internal_error"]
        raise PublicAccessError(base) from exc
    if retry_after_seconds is None:
        return base
    return PublicAccessErrorDetail(
        code=base.code,
        message=base.message,
        retryable=base.retryable,
        http_status=base.http_status,
        retry_after_seconds=retry_after_seconds,
    )


def raise_public_error(code: str, retry_after_seconds: int | None = None) -> None:
    raise PublicAccessError(error_detail(code, retry_after_seconds=retry_after_seconds))


ERROR_CATALOG: dict[str, PublicAccessErrorDetail] = {
    "invalid_widget": PublicAccessErrorDetail("invalid_widget", "The widget is not available.", False, 404),
    "widget_not_published": PublicAccessErrorDetail("widget_not_published", "The widget is not available.", False, 404),
    "invalid_request": PublicAccessErrorDetail("invalid_request", "The request could not be accepted.", False, 400),
    "invalid_credential": PublicAccessErrorDetail("invalid_credential", "The public access credential is not valid.", False, 401),
    "disabled_credential": PublicAccessErrorDetail("disabled_credential", "This public access credential is disabled.", False, 403),
    "expired_credential": PublicAccessErrorDetail("expired_credential", "This public access credential has expired.", False, 401),
    "origin_not_allowed": PublicAccessErrorDetail("origin_not_allowed", "This origin is not allowed.", False, 403),
    "origin_required": PublicAccessErrorDetail("origin_required", "A valid request origin is required.", False, 403),
    "malformed_origin": PublicAccessErrorDetail("malformed_origin", "The request origin is not valid.", False, 400),
    "insecure_origin": PublicAccessErrorDetail("insecure_origin", "The request origin is not secure enough for this public access credential.", False, 403),
    "unsupported_origin_scheme": PublicAccessErrorDetail("unsupported_origin_scheme", "The request origin scheme is not supported.", False, 400),
    "invalid_session": PublicAccessErrorDetail("invalid_session", "The public access session is not valid.", False, 401),
    "expired_session": PublicAccessErrorDetail("expired_session", "The public access session has expired.", False, 401),
    "revoked_session": PublicAccessErrorDetail("revoked_session", "The public access session is not valid.", False, 401),
    "blocked_session": PublicAccessErrorDetail("blocked_session", "The public access session is not valid.", False, 403),
    "completed_session": PublicAccessErrorDetail("completed_session", "The public access session has ended.", False, 401),
    "session_limit_reached": PublicAccessErrorDetail("session_limit_reached", "The public access session limit has been reached.", False, 429),
    "session_origin_mismatch": PublicAccessErrorDetail("session_origin_mismatch", "The public access session is not valid for this site.", False, 401),
    "session_credential_mismatch": PublicAccessErrorDetail("session_credential_mismatch", "The public access session is not valid.", False, 401),
    "session_channel_mismatch": PublicAccessErrorDetail("session_channel_mismatch", "The public access session is not valid.", False, 401),
    "request_too_large": PublicAccessErrorDetail("request_too_large", "The request is too large.", False, 413),
    "message_too_large": PublicAccessErrorDetail("message_too_large", "The message is too large.", False, 413),
    "rate_limited": PublicAccessErrorDetail("rate_limited", "Too many requests. Try again later.", True, 429),
    "quota_exceeded": PublicAccessErrorDetail("quota_exceeded", "The public access quota has been exceeded.", True, 429),
    "unsupported_channel": PublicAccessErrorDetail("unsupported_channel", "This public access channel is not supported.", False, 400),
    "unsafe_request": PublicAccessErrorDetail("unsafe_request", "The request could not be accepted.", False, 400),
    "temporarily_unavailable": PublicAccessErrorDetail("temporarily_unavailable", "Public access is temporarily unavailable.", True, 503),
    "safe_internal_error": PublicAccessErrorDetail("safe_internal_error", "The request could not be completed.", False, 500),
}
