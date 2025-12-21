"""create core tables

Revision ID: 0001_create_tables
Revises: 
Create Date: 2025-12-21 00:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("doc_id", sa.String(), primary_key=True),
        sa.Column("doc_sha256", sa.String(), nullable=False),
        sa.Column("doc_name", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("ingested_at_utc", sa.String(), nullable=False),
        sa.Column("docs_snapshot_id", sa.String(), nullable=False),
    )
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column("docs_snapshot_id", sa.String(), nullable=False),
        sa.Column("doc_id", sa.String(), nullable=False),
        sa.Column("doc_sha256", sa.String(), nullable=False),
        sa.Column("page_num", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("parse_mode", sa.String(), nullable=False),
    )
    op.create_table(
        "index_records",
        sa.Column("chunk_id", sa.String(), primary_key=True),
        sa.Column("docs_snapshot_id", sa.String(), nullable=False),
        sa.Column("doc_id", sa.String(), nullable=False),
        sa.Column("doc_name", sa.String(), nullable=False),
        sa.Column("page_num", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("indexed_at_utc", sa.String(), nullable=False),
        sa.Column("index_version", sa.String(), nullable=False),
        sa.Column("retrieval_version", sa.String(), nullable=False),
    )
    op.create_table(
        "telemetry",
        sa.Column("request_id", sa.String(), primary_key=True),
        sa.Column("docs_snapshot_id", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("retrieval_version", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("parser_mode", sa.String(), nullable=False),
        sa.Column("timestamp_utc", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_est", sa.Float(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("refusal_code", sa.String(), nullable=True),
        sa.Column("failure_label", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("telemetry")
    op.drop_table("index_records")
    op.drop_table("chunks")
    op.drop_table("documents")
