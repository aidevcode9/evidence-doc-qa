"""add page_end and char offsets for FR-013

Revision ID: 0002_add_page_char_offsets
Revises: 0001_create_tables
Create Date: 2026-01-18

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_page_char_offsets"
down_revision = "0001_create_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add page_end to chunks table (default to page_num for existing data)
    op.add_column("chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.execute("UPDATE chunks SET page_end = page_num WHERE page_end IS NULL")
    op.alter_column("chunks", "page_end", nullable=False)

    # Add page_end, char_start, char_end to index_records table
    op.add_column("index_records", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("index_records", sa.Column("char_start", sa.Integer(), nullable=True))
    op.add_column("index_records", sa.Column("char_end", sa.Integer(), nullable=True))

    # Default page_end = page_num, char_start/end = 0 for existing records
    op.execute(
        "UPDATE index_records SET page_end = page_num, char_start = 0, char_end = 0 "
        "WHERE page_end IS NULL"
    )
    op.alter_column("index_records", "page_end", nullable=False)
    op.alter_column("index_records", "char_start", nullable=False)
    op.alter_column("index_records", "char_end", nullable=False)


def downgrade() -> None:
    op.drop_column("index_records", "char_end")
    op.drop_column("index_records", "char_start")
    op.drop_column("index_records", "page_end")
    op.drop_column("chunks", "page_end")
