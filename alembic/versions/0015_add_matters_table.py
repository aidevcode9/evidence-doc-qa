"""Add matters table for case display names.

Stores matter display_name and created_at_utc. Auto-populated on first
document upload with name derived from filename. Supports rename via API.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"


def upgrade() -> None:
    op.create_table(
        "matters",
        sa.Column("matter_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("matter_id", "tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("matters")
