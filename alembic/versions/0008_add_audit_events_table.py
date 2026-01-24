"""Add audit_events table for FR-040.

Revision ID: 0008_add_audit_events_table
Revises: 0007_add_auth_columns
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0008_add_audit_events_table"
down_revision = "0007_add_auth_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_events table."""
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("matter_id", sa.String(), nullable=True, index=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("event_type", sa.String(), nullable=False, index=True),
        sa.Column("event_json", sa.Text(), nullable=False),
        sa.Column("response_id", sa.String(), nullable=True),
        sa.Column("created_at_utc", sa.String(), nullable=False, index=True),
    )


def downgrade() -> None:
    """Drop audit_events table."""
    op.drop_table("audit_events")
