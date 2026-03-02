"""Add langfuse_trace_id column to telemetry table (NFR-045).

Enables cross-referencing telemetry DB records with Langfuse Cloud traces.

Revision ID: 0011_add_langfuse_trace_id
Revises: 0010_add_sso_states_table
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0011_add_langfuse_trace_id"
down_revision = "0010_add_sso_states_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add langfuse_trace_id column to telemetry table."""
    op.add_column(
        "telemetry",
        sa.Column("langfuse_trace_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove langfuse_trace_id column from telemetry table."""
    op.drop_column("telemetry", "langfuse_trace_id")
