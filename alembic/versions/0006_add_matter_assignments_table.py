"""Add matter_assignments table for FR-004

Revision ID: 0006_add_matter_assignments
Revises: 0005_add_users_table
Create Date: 2026-01-22

"""

from alembic import op
import sqlalchemy as sa

revision = "0006_add_matter_assignments"
down_revision = "0005_add_users_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create matter_assignments table for FR-004."""
    op.create_table(
        "matter_assignments",
        sa.Column("assignment_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("matter_id", sa.String(), nullable=False, index=True),
        sa.Column("granted_by", sa.String(), nullable=False),
        sa.Column("granted_at_utc", sa.String(), nullable=False),
    )
    # Create composite index for efficient lookups
    op.create_index(
        "ix_matter_assignments_user_tenant_matter",
        "matter_assignments",
        ["user_id", "tenant_id", "matter_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop matter_assignments table."""
    op.drop_index("ix_matter_assignments_user_tenant_matter", table_name="matter_assignments")
    op.drop_table("matter_assignments")
