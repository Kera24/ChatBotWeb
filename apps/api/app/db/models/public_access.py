from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PublicCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "public_credentials"
    __table_args__ = (
        UniqueConstraint("public_identifier", name="uq_public_credentials_public_identifier"),
        Index("ix_public_credentials_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_public_credentials_workspace_type_environment", "workspace_id", "credential_type", "environment"),
        Index("ix_public_credentials_status", "status"),
        Index("ix_public_credentials_type_environment_status", "credential_type", "environment", "status"),
        Index("ix_public_credentials_expires_at", "expires_at"),
        Index("ix_public_credentials_deleted_at", "deleted_at"),
        Index("ix_public_credentials_rotation_group", "rotation_group_id"),
        Index("ix_public_credentials_parent", "parent_credential_id"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    credential_type: Mapped[str] = mapped_column(String(60), nullable=False)
    public_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_profile: Mapped[str] = mapped_column(String(80), nullable=False)
    capabilities_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    rotation_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parent_credential_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("public_credentials.id"), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rotated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    origins = relationship("CredentialAllowedOrigin", back_populates="credential", cascade="all, delete-orphan")
    widget_configuration = relationship("WidgetConfiguration", back_populates="credential", uselist=False, cascade="all, delete-orphan")
    public_sessions = relationship("PublicSession", back_populates="credential")
    parent_credential = relationship("PublicCredential", remote_side="PublicCredential.id")


class CredentialAllowedOrigin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credential_allowed_origins"
    __table_args__ = (
        UniqueConstraint(
            "credential_id",
            "scheme",
            "hostname",
            "port",
            "wildcard_subdomains",
            "environment",
            name="uq_credential_allowed_origins_normalised",
        ),
        Index("ix_credential_allowed_origins_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_credential_allowed_origins_credential_active", "credential_id", "active"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(36), ForeignKey("public_credentials.id"), nullable=False, index=True)
    scheme: Mapped[str] = mapped_column(String(12), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wildcard_subdomains: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    credential = relationship("PublicCredential", back_populates="origins")


class WidgetConfiguration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "widget_configurations"
    __table_args__ = (
        UniqueConstraint("credential_id", name="uq_widget_configurations_credential"),
        Index("ix_widget_configurations_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_widget_configurations_credential_status", "credential_id", "status"),
        Index("ix_widget_configurations_workspace_status", "workspace_id", "status"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(36), ForeignKey("public_credentials.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    bot_name: Mapped[str] = mapped_column(String(120), nullable=False)
    welcome_message: Mapped[str] = mapped_column(Text, nullable=False)
    launcher_label: Mapped[str] = mapped_column(String(80), nullable=False)
    primary_colour: Mapped[str] = mapped_column(String(16), nullable=False)
    secondary_colour: Mapped[str | None] = mapped_column(String(16), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    position: Mapped[str] = mapped_column(String(40), nullable=False)
    theme_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    suggested_questions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fallback_contact_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    privacy_notice_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    privacy_notice_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    terms_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", server_default="en")
    show_citations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    allow_conversation_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    max_initial_suggestions: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)

    credential = relationship("PublicCredential", back_populates="widget_configuration")


class PublicSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "public_sessions"
    __table_args__ = (
        UniqueConstraint("public_token_id", name="uq_public_sessions_public_token_id"),
        CheckConstraint("status in ('active', 'completed', 'expired', 'revoked', 'blocked')", name="ck_public_sessions_status"),
        CheckConstraint("message_count >= 0", name="ck_public_sessions_message_count_nonnegative"),
        Index("ix_public_sessions_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_public_sessions_tenant_credential", "organisation_id", "workspace_id", "credential_id"),
        Index("ix_public_sessions_credential_status", "credential_id", "status"),
        Index("ix_public_sessions_status_expires_at", "status", "expires_at"),
        Index("ix_public_sessions_last_activity_at", "last_activity_at"),
        Index("ix_public_sessions_conversation_id", "conversation_id"),
        Index("ix_public_sessions_deleted_at", "deleted_at"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(36), ForeignKey("public_credentials.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(80), nullable=False)
    environment: Mapped[str] = mapped_column(String(40), nullable=False)
    public_token_id: Mapped[str] = mapped_column(String(120), nullable=False)
    token_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", server_default="active")
    policy_profile: Mapped[str] = mapped_column(String(80), nullable=False)
    origin_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("credential_allowed_origins.id"), nullable=True)
    canonical_origin_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=True)
    anonymous_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_activity_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    credential = relationship("PublicCredential", back_populates="public_sessions")
    origin = relationship("CredentialAllowedOrigin")
    conversation = relationship("ChatSession")
