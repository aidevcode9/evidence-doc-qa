"""Add users table for RBAC (FR-003)

Revision ID: 0005_add_users_table
Revises: 0004_add_tenant_matter_isolation
Create Date: 2026-01-22

"""

from alembic import op
import sqlalchemy as sa

revision = "0005_add_users_table"
down_revision = "0004_add_tenant_matter_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users table for RBAC (FR-003)."""
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),  # admin, attorney, paralegal, viewer
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("created_at_utc", sa.String(), nullable=False),
    )


def downgrade() -> None:
    """Drop users table."""
    op.drop_table("users")
