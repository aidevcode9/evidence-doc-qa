"""add tenant_id and matter_id columns for FR-001 and FR-002

Revision ID: 0004_add_tenant_matter_isolation
Revises: 0003_add_qa_session_tables
Create Date: 2026-01-21

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_tenant_matter_isolation"
down_revision = "0003_add_qa_session_tables"
branch_labels = None
depends_on = None

# Default values for existing data during migration
DEFAULT_TENANT_ID = "default-tenant"
DEFAULT_MATTER_ID = "default-matter"


def upgrade() -> None:
    # Add tenant_id and matter_id to documents table
    op.add_column("documents", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("matter_id", sa.String(), nullable=True))
    op.execute(
        f"UPDATE documents SET tenant_id = '{DEFAULT_TENANT_ID}', "
        f"matter_id = '{DEFAULT_MATTER_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("documents", "tenant_id", nullable=False)
    op.alter_column("documents", "matter_id", nullable=False)
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_documents_matter_id", "documents", ["matter_id"])

    # Add tenant_id and matter_id to chunks table
    op.add_column("chunks", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("chunks", sa.Column("matter_id", sa.String(), nullable=True))
    op.execute(
        f"UPDATE chunks SET tenant_id = '{DEFAULT_TENANT_ID}', "
        f"matter_id = '{DEFAULT_MATTER_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("chunks", "tenant_id", nullable=False)
    op.alter_column("chunks", "matter_id", nullable=False)
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])
    op.create_index("ix_chunks_matter_id", "chunks", ["matter_id"])

    # Add tenant_id and matter_id to index_records table
    op.add_column("index_records", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("index_records", sa.Column("matter_id", sa.String(), nullable=True))
    op.execute(
        f"UPDATE index_records SET tenant_id = '{DEFAULT_TENANT_ID}', "
        f"matter_id = '{DEFAULT_MATTER_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("index_records", "tenant_id", nullable=False)
    op.alter_column("index_records", "matter_id", nullable=False)
    op.create_index("ix_index_records_tenant_id", "index_records", ["tenant_id"])
    op.create_index("ix_index_records_matter_id", "index_records", ["matter_id"])

    # Add tenant_id and matter_id to telemetry table
    op.add_column("telemetry", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("telemetry", sa.Column("matter_id", sa.String(), nullable=True))
    op.execute(
        f"UPDATE telemetry SET tenant_id = '{DEFAULT_TENANT_ID}', "
        f"matter_id = '{DEFAULT_MATTER_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("telemetry", "tenant_id", nullable=False)
    op.alter_column("telemetry", "matter_id", nullable=False)
    op.create_index("ix_telemetry_tenant_id", "telemetry", ["tenant_id"])
    op.create_index("ix_telemetry_matter_id", "telemetry", ["matter_id"])

    # Add tenant_id and matter_id to qa_sessions table
    op.add_column("qa_sessions", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("qa_sessions", sa.Column("matter_id", sa.String(), nullable=True))
    op.execute(
        f"UPDATE qa_sessions SET tenant_id = '{DEFAULT_TENANT_ID}', "
        f"matter_id = '{DEFAULT_MATTER_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("qa_sessions", "tenant_id", nullable=False)
    op.alter_column("qa_sessions", "matter_id", nullable=False)
    op.create_index("ix_qa_sessions_tenant_id", "qa_sessions", ["tenant_id"])
    op.create_index("ix_qa_sessions_matter_id", "qa_sessions", ["matter_id"])

    # Add tenant_id and matter_id to qa_messages table
    op.add_column("qa_messages", sa.Column("tenant_id", sa.String(), nullable=True))
    op.add_column("qa_messages", sa.Column("matter_id", sa.String(), nullable=True))
    op.execute(
        f"UPDATE qa_messages SET tenant_id = '{DEFAULT_TENANT_ID}', "
        f"matter_id = '{DEFAULT_MATTER_ID}' WHERE tenant_id IS NULL"
    )
    op.alter_column("qa_messages", "tenant_id", nullable=False)
    op.alter_column("qa_messages", "matter_id", nullable=False)
    op.create_index("ix_qa_messages_tenant_id", "qa_messages", ["tenant_id"])
    op.create_index("ix_qa_messages_matter_id", "qa_messages", ["matter_id"])


def downgrade() -> None:
    # Drop indexes and columns from qa_messages
    op.drop_index("ix_qa_messages_matter_id", table_name="qa_messages")
    op.drop_index("ix_qa_messages_tenant_id", table_name="qa_messages")
    op.drop_column("qa_messages", "matter_id")
    op.drop_column("qa_messages", "tenant_id")

    # Drop indexes and columns from qa_sessions
    op.drop_index("ix_qa_sessions_matter_id", table_name="qa_sessions")
    op.drop_index("ix_qa_sessions_tenant_id", table_name="qa_sessions")
    op.drop_column("qa_sessions", "matter_id")
    op.drop_column("qa_sessions", "tenant_id")

    # Drop indexes and columns from telemetry
    op.drop_index("ix_telemetry_matter_id", table_name="telemetry")
    op.drop_index("ix_telemetry_tenant_id", table_name="telemetry")
    op.drop_column("telemetry", "matter_id")
    op.drop_column("telemetry", "tenant_id")

    # Drop indexes and columns from index_records
    op.drop_index("ix_index_records_matter_id", table_name="index_records")
    op.drop_index("ix_index_records_tenant_id", table_name="index_records")
    op.drop_column("index_records", "matter_id")
    op.drop_column("index_records", "tenant_id")

    # Drop indexes and columns from chunks
    op.drop_index("ix_chunks_matter_id", table_name="chunks")
    op.drop_index("ix_chunks_tenant_id", table_name="chunks")
    op.drop_column("chunks", "matter_id")
    op.drop_column("chunks", "tenant_id")

    # Drop indexes and columns from documents
    op.drop_index("ix_documents_matter_id", table_name="documents")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_column("documents", "matter_id")
    op.drop_column("documents", "tenant_id")
