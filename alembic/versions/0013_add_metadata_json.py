"""Add metadata_json column to documents table (FR-014).

Stores extracted PDF metadata (title, author, page_count) as JSON.
Nullable for backward compatibility with existing documents.

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "metadata_json")
