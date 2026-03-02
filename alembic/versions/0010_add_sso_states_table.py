"""Add sso_states table for SSO CSRF protection (FR-051).

Revision ID: 0010_add_sso_states_table
Revises: 0009_add_retention_policies_table
Create Date: 2026-02-08

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0010_add_sso_states_table"
down_revision = "0009_add_retention_policies_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create sso_states table for CSRF protection during SSO flows."""
    op.create_table(
        "sso_states",
        sa.Column("state_token", sa.String(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("code_verifier", sa.String(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("expires_at_utc", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.String(), nullable=False),
    )
    # Index for cleanup queries (expired states)
    op.create_index(
        "ix_sso_states_expires_at",
        "sso_states",
        ["expires_at_utc"],
    )


def downgrade() -> None:
    """Drop sso_states table."""
    op.drop_index("ix_sso_states_expires_at", table_name="sso_states")
    op.drop_table("sso_states")
