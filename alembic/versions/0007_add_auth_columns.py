"""Add authentication columns and refresh_tokens table (FR-050).

Revision ID: 0007_add_auth_columns
Revises: 0006_add_matter_assignments
Create Date: 2026-01-22

"""

from alembic import op
import sqlalchemy as sa

revision = "0007_add_auth_columns"
down_revision = "0006_add_matter_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add auth columns to users table and create refresh_tokens table."""
    # Add new columns to users table
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(), nullable=False, server_default="local"),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "users",
        sa.Column("last_login_utc", sa.String(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("locked_until_utc", sa.String(), nullable=True),
    )

    # Create index for email + tenant_id lookups during login
    op.create_index(
        "ix_users_email_tenant",
        "users",
        ["email", "tenant_id"],
        unique=True,
    )

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("token_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at_utc", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.String(), nullable=False),
        sa.Column("revoked_at_utc", sa.String(), nullable=True),
    )

    # Index for token lookups
    op.create_index(
        "ix_refresh_tokens_user_tenant",
        "refresh_tokens",
        ["user_id", "tenant_id"],
    )


def downgrade() -> None:
    """Remove auth columns and refresh_tokens table."""
    # Drop refresh_tokens table
    op.drop_index("ix_refresh_tokens_user_tenant", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # Drop users columns
    op.drop_index("ix_users_email_tenant", table_name="users")
    op.drop_column("users", "locked_until_utc")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "last_login_utc")
    op.drop_column("users", "is_active")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "password_hash")
