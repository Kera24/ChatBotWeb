from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.access.contracts import PublicAccessRequest, PublicAccessResponse, PublicCredentialReference
from app.access.errors import PublicAccessErrorDetail


@dataclass(frozen=True)
class ChannelCapabilities:
    supports_sessions: bool = False
    supports_streaming: bool = False
    supports_markdown: bool = False
    max_client_metadata_items: int = 20


class PublicChannelAdapter(ABC):
    channel_key: str
    display_name: str
    capabilities: ChannelCapabilities = ChannelCapabilities()
    default_policy_profile: str = "internal_test"

    @abstractmethod
    def parse_request(self, raw_request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def extract_public_credential(self, parsed_request: dict[str, Any]) -> PublicCredentialReference:
        raise NotImplementedError

    @abstractmethod
    def extract_origin(self, parsed_request: dict[str, Any]) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def extract_session_token(self, parsed_request: dict[str, Any]) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def validate_request_shape(self, parsed_request: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def normalise_message(self, parsed_request: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def format_response(self, response: PublicAccessResponse) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def format_error(self, error: PublicAccessErrorDetail) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class DevelopmentTestChannelAdapter(PublicChannelAdapter):
    channel_key: str = "internal_test"
    display_name: str = "Internal Test Channel"
    capabilities: ChannelCapabilities = field(default_factory=lambda: ChannelCapabilities(supports_sessions=False))
    default_policy_profile: str = "internal_test"

    def parse_request(self, raw_request: dict[str, Any]) -> dict[str, Any]:
        return dict(raw_request)

    def extract_public_credential(self, parsed_request: dict[str, Any]) -> PublicCredentialReference:
        credential = parsed_request.get("public_credential")
        if isinstance(credential, PublicCredentialReference):
            return credential
        if isinstance(credential, dict):
            return PublicCredentialReference(
                credential_type=str(credential.get("credential_type", "")),
                public_identifier=str(credential.get("public_identifier", "")),
            )
        return PublicCredentialReference(
            credential_type=str(parsed_request.get("credential_type", "")),
            public_identifier=str(parsed_request.get("public_identifier", "")),
        )

    def extract_origin(self, parsed_request: dict[str, Any]) -> str | None:
        origin = parsed_request.get("origin")
        return str(origin) if origin else None

    def extract_session_token(self, parsed_request: dict[str, Any]) -> str | None:
        token = parsed_request.get("public_session_token")
        return str(token) if token else None

    def validate_request_shape(self, parsed_request: dict[str, Any]) -> None:
        forbidden_headers = {"x-development-user-email", "x-development-role", "authorization"}
        headers = parsed_request.get("headers", {})
        if isinstance(headers, dict):
            lowered = {str(key).lower() for key in headers}
            if forbidden_headers.intersection(lowered):
                from app.access.errors import raise_public_error

                raise_public_error("unsafe_request")
        if "message" not in parsed_request:
            raise ValueError("message is required")

    def normalise_message(self, parsed_request: dict[str, Any]) -> str:
        return str(parsed_request.get("message", ""))

    def format_response(self, response: PublicAccessResponse) -> dict[str, Any]:
        return response.to_dict()

    def format_error(self, error: PublicAccessErrorDetail) -> dict[str, Any]:
        return {"error": error.to_public_dict()}
