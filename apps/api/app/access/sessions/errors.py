from app.access.errors import PublicAccessError, error_detail


class PublicSessionError(PublicAccessError):
    pass


def raise_session_error(code: str) -> None:
    raise PublicSessionError(error_detail(code))

