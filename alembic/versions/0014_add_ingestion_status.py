"""Add ingestion status columns to documents table (FR-015).

Tracks async ingestion state: queued → processing → ready | failed.
Supports retry with error tracking.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
    )
    op.add_column(
        "documents",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    # Backfill existing documents as 'ready' (they were already processed)
    op.execute("UPDATE documents SET status = 'ready' WHERE status = 'queued'")


def downgrade() -> None:
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_column("documents", "retry_count")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")
