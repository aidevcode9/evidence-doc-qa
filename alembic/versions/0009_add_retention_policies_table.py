"""Add retention_policies table for FR-042.

Revision ID: 0009_add_retention_policies_table
Revises: 0008_add_audit_events_table
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0009_add_retention_policies_table"
down_revision = "0008_add_audit_events_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create retention_policies table."""
    op.create_table(
        "retention_policies",
        sa.Column("policy_id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", sa.String(), nullable=False),
        sa.Column("updated_at_utc", sa.String(), nullable=False),
    )
    # Unique constraint on tenant_id + resource_type
    op.create_unique_constraint(
        "uq_retention_policies_tenant_resource",
        "retention_policies",
        ["tenant_id", "resource_type"],
    )


def downgrade() -> None:
    """Drop retention_policies table."""
    op.drop_table("retention_policies")
