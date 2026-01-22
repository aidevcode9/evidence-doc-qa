"""add qa_sessions and qa_messages tables for FR-032

Revision ID: 0003_add_qa_session_tables
Revises: 0002_add_page_char_offsets
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_qa_session_tables"
down_revision = "0002_add_page_char_offsets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create qa_sessions table
    op.create_table(
        "qa_sessions",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("docs_snapshot_id", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.String(), nullable=False),
    )

    # Create qa_messages table
    op.create_table(
        "qa_messages",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("refusal_code", sa.String(), nullable=True),
        sa.Column("version_snapshot_json", sa.Text(), nullable=True),
        sa.Column("created_at_utc", sa.String(), nullable=False),
    )

    # Add index on session_id for faster message lookups
    op.create_index(
        "ix_qa_messages_session_id",
        "qa_messages",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_qa_messages_session_id", table_name="qa_messages")
    op.drop_table("qa_messages")
    op.drop_table("qa_sessions")
