# Database Migrations

> Alembic for reproducible schema changes across environments.

## Directory Structure

```
alembic/
├── alembic.ini          # Configuration
├── env.py               # Migration environment
└── versions/            # Migration scripts
    ├── 0001_create_tables.py
    ├── 0002_add_page_char_offsets.py
    └── ...
```

## Common Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Show migration history
alembic history

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 0002_add_page_char_offsets

# Create new migration
alembic revision -m "add_new_table"
```

## Naming Convention

```
NNNN_description.py

Examples:
0001_create_tables.py
0002_add_page_char_offsets.py
0003_add_qa_session_tables.py
```

## Auto-create vs Alembic

The app calls `Base.metadata.create_all()` on startup via `init_db()`:
- Creates missing tables automatically
- Does NOT modify existing tables

**Use Alembic when:**
- Adding columns to existing tables
- Modifying column types
- Adding indexes
- Any schema change to production

## Migration Template

```python
"""description of change

Revision ID: NNNN_description
Revises: previous_revision
"""

from alembic import op
import sqlalchemy as sa

revision = "NNNN_description"
down_revision = "previous_revision"


def upgrade() -> None:
    op.add_column('table', sa.Column('new_col', sa.String()))


def downgrade() -> None:
    op.drop_column('table', 'new_col')
```

## Environment

Alembic reads `DATABASE_URL` from environment:

```ini
# alembic.ini
sqlalchemy.url = ${DATABASE_URL}
```
