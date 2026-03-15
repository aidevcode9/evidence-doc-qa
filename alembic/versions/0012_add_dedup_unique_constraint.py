"""Add unique constraint for document deduplication (FR-011).

Prevents duplicate documents within the same matter by enforcing
uniqueness on (tenant_id, matter_id, doc_sha256).

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"


def upgrade() -> None:
    op.create_index(
        "uq_documents_tenant_matter_sha256",
        "documents",
        ["tenant_id", "matter_id", "doc_sha256"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_documents_tenant_matter_sha256", table_name="documents")
