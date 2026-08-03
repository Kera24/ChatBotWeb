"""add assistant scoped conversation ownership

Revision ID: 0014_assistant_scoping
Revises: 0013_customer_auth
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0014_assistant_scoping"
down_revision: str | None = "0013_customer_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("widget_id", sa.String(length=36), nullable=True))
    op.add_column("chat_messages", sa.Column("widget_id", sa.String(length=36), nullable=True))
    op.add_column("citations", sa.Column("widget_id", sa.String(length=36), nullable=True))
    op.add_column("review_annotations", sa.Column("widget_id", sa.String(length=36), nullable=True))

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "sqlite":
        op.create_foreign_key("fk_chat_sessions_widget_id_widgets", "chat_sessions", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key("fk_chat_messages_widget_id_widgets", "chat_messages", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key("fk_citations_widget_id_widgets", "citations", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key("fk_review_annotations_widget_id_widgets", "review_annotations", "widgets", ["widget_id"], ["id"])
    op.create_index("ix_chat_sessions_widget_id", "chat_sessions", ["widget_id"])
    op.create_index("ix_chat_sessions_widget_recent", "chat_sessions", ["organisation_id", "workspace_id", "widget_id", "last_message_at"])
    op.create_index("ix_chat_messages_widget_id", "chat_messages", ["widget_id"])
    op.create_index("ix_chat_messages_widget", "chat_messages", ["organisation_id", "workspace_id", "widget_id"])
    op.create_index("ix_citations_widget_id", "citations", ["widget_id"])
    op.create_index("ix_citations_widget", "citations", ["organisation_id", "workspace_id", "widget_id"])
    op.create_index("ix_review_annotations_widget_id", "review_annotations", ["widget_id"])
    op.create_index("ix_review_annotations_widget_status", "review_annotations", ["organisation_id", "workspace_id", "widget_id", "review_status"])

    if dialect == "postgresql":
        bind.execute(sa.text("""
            WITH single_widget_workspaces AS (
                SELECT organisation_id, workspace_id, MIN(id) AS widget_id, COUNT(*) AS widget_count
                FROM widgets
                WHERE archived_at IS NULL
                GROUP BY organisation_id, workspace_id
                HAVING COUNT(*) = 1
            )
            UPDATE chat_sessions cs
            SET widget_id = s.widget_id
            FROM single_widget_workspaces s
            WHERE cs.organisation_id = s.organisation_id
              AND cs.workspace_id = s.workspace_id
              AND cs.widget_id IS NULL
        """))
        bind.execute(sa.text("""
            UPDATE chat_messages cm
            SET widget_id = cs.widget_id
            FROM chat_sessions cs
            WHERE cm.conversation_id = cs.id
              AND cm.widget_id IS NULL
              AND cs.widget_id IS NOT NULL
        """))
        bind.execute(sa.text("""
            UPDATE citations c
            SET widget_id = cm.widget_id
            FROM chat_messages cm
            WHERE c.message_id = cm.id
              AND c.widget_id IS NULL
              AND cm.widget_id IS NOT NULL
        """))
        bind.execute(sa.text("""
            UPDATE review_annotations ra
            SET widget_id = cm.widget_id
            FROM chat_messages cm
            WHERE ra.assistant_message_id = cm.id
              AND ra.widget_id IS NULL
              AND cm.widget_id IS NOT NULL
        """))
    else:
        rows = bind.execute(sa.text("""
            SELECT organisation_id, workspace_id, MIN(id) AS widget_id
            FROM widgets
            WHERE archived_at IS NULL
            GROUP BY organisation_id, workspace_id
            HAVING COUNT(*) = 1
        """)).mappings().all()
        for row in rows:
            bind.execute(sa.text("UPDATE chat_sessions SET widget_id = :widget_id WHERE organisation_id = :organisation_id AND workspace_id = :workspace_id AND widget_id IS NULL"), dict(row))
        bind.execute(sa.text("UPDATE chat_messages SET widget_id = (SELECT widget_id FROM chat_sessions WHERE chat_sessions.id = chat_messages.conversation_id) WHERE widget_id IS NULL"))
        bind.execute(sa.text("UPDATE citations SET widget_id = (SELECT widget_id FROM chat_messages WHERE chat_messages.id = citations.message_id) WHERE widget_id IS NULL"))
        bind.execute(sa.text("UPDATE review_annotations SET widget_id = (SELECT widget_id FROM chat_messages WHERE chat_messages.id = review_annotations.assistant_message_id) WHERE widget_id IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_review_annotations_widget_status", table_name="review_annotations")
    op.drop_index("ix_review_annotations_widget_id", table_name="review_annotations")
    op.drop_index("ix_citations_widget", table_name="citations")
    op.drop_index("ix_citations_widget_id", table_name="citations")
    op.drop_index("ix_chat_messages_widget", table_name="chat_messages")
    op.drop_index("ix_chat_messages_widget_id", table_name="chat_messages")
    op.drop_index("ix_chat_sessions_widget_recent", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_widget_id", table_name="chat_sessions")

    op.drop_constraint("fk_review_annotations_widget_id_widgets", "review_annotations", type_="foreignkey")
    op.drop_constraint("fk_citations_widget_id_widgets", "citations", type_="foreignkey")
    op.drop_constraint("fk_chat_messages_widget_id_widgets", "chat_messages", type_="foreignkey")
    op.drop_constraint("fk_chat_sessions_widget_id_widgets", "chat_sessions", type_="foreignkey")

    op.drop_column("review_annotations", "widget_id")
    op.drop_column("citations", "widget_id")
    op.drop_column("chat_messages", "widget_id")
    op.drop_column("chat_sessions", "widget_id")




