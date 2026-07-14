from app.access.credentials.contracts import CredentialRecord
from app.access.errors import raise_public_error


class DuplicateCredentialError(ValueError):
    pass


class InMemoryCredentialRegistry:
    def __init__(self, records: list[CredentialRecord] | None = None) -> None:
        self._records: dict[str, CredentialRecord] = {}
        for record in records or []:
            self.register(record)

    def register(self, record: CredentialRecord) -> None:
        if record.public_identifier in self._records:
            raise DuplicateCredentialError("Public credential identifier already registered.")
        self._records[record.public_identifier] = record

    def resolve(self, public_identifier: str) -> CredentialRecord:
        record = self._records.get(public_identifier)
        if record is None:
            raise_public_error("invalid_credential")
        self.validate_usable(record)
        return record

    def validate_usable(self, record: CredentialRecord) -> None:
        if record.status == "active" and not record.is_expired():
            return
        if record.status == "disabled":
            raise_public_error("disabled_credential")
        if record.status in {"revoked", "draft"}:
            raise_public_error("invalid_credential")
        if record.status == "expired" or record.is_expired():
            raise_public_error("expired_credential")
        raise_public_error("invalid_credential")
