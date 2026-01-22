from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from typing import Generator, Iterable

from sqlalchemy import Boolean, Float, Integer, String, Text, create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass
class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    doc_sha256: Mapped[str] = mapped_column(String, nullable=False)
    doc_name: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_sha256: Mapped[str] = mapped_column(String, nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str] = mapped_column(String, nullable=False)


class IndexRecord(Base):
    __tablename__ = "index_records"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_name: Mapped[str] = mapped_column(String, nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    index_version: Mapped[str] = mapped_column(String, nullable=False)
    retrieval_version: Mapped[str] = mapped_column(String, nullable=False)


class Telemetry(Base):
    __tablename__ = "telemetry"

    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    retrieval_version: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    parser_mode: Mapped[str] = mapped_column(String, nullable=False)
    timestamp_utc: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_est: Mapped[float] = mapped_column(Float, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    refusal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_label: Mapped[str | None] = mapped_column(String, nullable=True)
    trace_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)


class QASession(Base):
    """Q&A session for tracking conversation history (FR-032)."""

    __tablename__ = "qa_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)


class QAMessage(Base):
    """Q&A message within a session (FR-032)."""

    __tablename__ = "qa_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    refusal_code: Mapped[str | None] = mapped_column(String, nullable=True)
    version_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)


def init_db() -> None:
    engine = _engine()
    Base.metadata.create_all(bind=engine)

    # Auto-migration: Check if trace_metadata exists, if not add it
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('telemetry')]
    if 'trace_metadata' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE telemetry ADD COLUMN trace_metadata TEXT"))
            conn.commit()


def _engine() -> Engine:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL or DB_DATABASE_URL is required.")
    return create_engine(DATABASE_URL, poolclass=NullPool)


SessionLocal = sessionmaker(bind=_engine(), class_=Session, expire_on_commit=False)


@contextlib.contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def insert_document(document: Document) -> None:
    with session_scope() as session:
        session.add(document)


def insert_chunks(chunks: Iterable[Chunk]) -> None:
    with session_scope() as session:
        session.add_all(list(chunks))


def insert_index_records(records: Iterable[IndexRecord]) -> None:
    with session_scope() as session:
        session.add_all(list(records))


def insert_telemetry(record: Telemetry) -> None:
    with session_scope() as session:
        session.add(record)


def get_latest_docs_snapshot_id(tenant_id: str) -> str | None:
    """Get the most recent docs_snapshot_id for a tenant (FR-001 isolation).

    Args:
        tenant_id: Tenant ID to filter by (required for isolation)

    Returns:
        The most recent docs_snapshot_id or None if no documents exist
    """
    with session_scope() as session:
        stmt = (
            select(Document.docs_snapshot_id)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.ingested_at_utc.desc())
        )
        row = session.execute(stmt).first()
        return row[0] if row else None


def get_doc_name(doc_id: str, tenant_id: str) -> str | None:
    """Get document name by ID with tenant isolation (FR-001).

    Args:
        doc_id: Document ID
        tenant_id: Tenant ID to filter by (required for isolation)

    Returns:
        Document name or None if not found or wrong tenant
    """
    with session_scope() as session:
        stmt = select(Document.doc_name).where(
            Document.doc_id == doc_id,
            Document.tenant_id == tenant_id,
        )
        row = session.execute(stmt).first()
        return row[0] if row else None


def get_document(doc_id: str, tenant_id: str) -> Document | None:
    """Get a document by ID with tenant isolation (FR-001).

    Args:
        doc_id: Document ID
        tenant_id: Tenant ID to filter by (required for isolation)

    Returns:
        Document or None if not found or wrong tenant
    """
    with session_scope() as session:
        stmt = select(Document).where(
            Document.doc_id == doc_id,
            Document.tenant_id == tenant_id,
        )
        return session.scalars(stmt).first()


def load_chunks(
    docs_snapshot_id: str | None,
    tenant_id: str,
    matter_id: str,
) -> list[Chunk]:
    """Load chunks with REQUIRED tenant/matter isolation (FR-001, FR-002).

    Args:
        docs_snapshot_id: Filter by document snapshot ID (optional)
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)
        matter_id: Matter ID (REQUIRED for FR-002 isolation)

    Returns:
        List of chunks matching the filters
    """
    with session_scope() as session:
        stmt = select(Chunk).where(
            Chunk.tenant_id == tenant_id,
            Chunk.matter_id == matter_id,
        )
        if docs_snapshot_id:
            stmt = stmt.where(Chunk.docs_snapshot_id == docs_snapshot_id)
        return list(session.scalars(stmt).all())


def load_index_records(
    docs_snapshot_id: str | None,
    tenant_id: str,
    matter_id: str,
) -> list[IndexRecord]:
    """Load index records with REQUIRED tenant/matter isolation (FR-001, FR-002).

    Args:
        docs_snapshot_id: Filter by document snapshot ID (optional)
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)
        matter_id: Matter ID (REQUIRED for FR-002 isolation)

    Returns:
        List of index records matching the filters
    """
    with session_scope() as session:
        stmt = select(IndexRecord).where(
            IndexRecord.tenant_id == tenant_id,
            IndexRecord.matter_id == matter_id,
        )
        if docs_snapshot_id:
            stmt = stmt.where(IndexRecord.docs_snapshot_id == docs_snapshot_id)
        return list(session.scalars(stmt).all())


def load_telemetry(
    hours: int = 24,
    limit: int = 500,
    tenant_id: str | None = None,
) -> list[Telemetry]:
    """Load telemetry records with optional tenant filter.

    Args:
        hours: Number of hours of history to load
        limit: Maximum number of records to return
        tenant_id: Optional tenant ID filter (for non-admin use)

    Returns:
        List of telemetry records
    """
    with session_scope() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = (
            select(Telemetry)
            .where(Telemetry.timestamp_utc >= cutoff.isoformat())
            .order_by(Telemetry.timestamp_utc.desc())
            .limit(limit)
        )
        if tenant_id:
            stmt = stmt.where(Telemetry.tenant_id == tenant_id)
        rows = list(session.scalars(stmt).all())
        return rows


# QA Session CRUD functions (FR-032)


def create_qa_session(
    session_id: str,
    docs_snapshot_id: str,
    tenant_id: str,
    matter_id: str,
) -> QASession:
    """Create a new QA session with tenant/matter isolation (FR-001, FR-002).

    Args:
        session_id: Unique session identifier
        docs_snapshot_id: Document snapshot ID for this session
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)
        matter_id: Matter ID (REQUIRED for FR-002 isolation)

    Returns:
        The created QASession
    """
    qa_session = QASession(
        session_id=session_id,
        tenant_id=tenant_id,
        matter_id=matter_id,
        docs_snapshot_id=docs_snapshot_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with session_scope() as session:
        session.add(qa_session)
    return qa_session


def get_qa_session(session_id: str, tenant_id: str) -> QASession | None:
    """Get a QA session by ID with tenant isolation (FR-001).

    Args:
        session_id: Session ID to look up
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)

    Returns:
        QASession or None if not found or wrong tenant
    """
    with session_scope() as session:
        stmt = select(QASession).where(
            QASession.session_id == session_id,
            QASession.tenant_id == tenant_id,
        )
        return session.scalars(stmt).first()


def get_or_create_session(
    session_id: str,
    docs_snapshot_id: str,
    tenant_id: str,
    matter_id: str,
) -> QASession:
    """Get existing session or create a new one with tenant/matter isolation.

    Handles race conditions where two requests try to create the same session
    simultaneously by catching IntegrityError and retrying the get.

    Args:
        session_id: Session ID
        docs_snapshot_id: Document snapshot ID
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)
        matter_id: Matter ID (REQUIRED for FR-002 isolation)

    Returns:
        The existing or newly created QASession
    """
    from sqlalchemy.exc import IntegrityError

    existing = get_qa_session(session_id, tenant_id)
    if existing:
        return existing

    try:
        return create_qa_session(session_id, docs_snapshot_id, tenant_id, matter_id)
    except IntegrityError:
        # Race condition: another request created the session first
        # Fetch the existing session that was created by the other request
        existing = get_qa_session(session_id, tenant_id)
        if existing:
            return existing
        # Should not happen, but re-raise if session still not found
        raise


def insert_qa_message(message: QAMessage) -> None:
    """Insert a QA message into the database."""
    with session_scope() as session:
        session.add(message)


def get_session_messages(session_id: str, tenant_id: str) -> list[QAMessage]:
    """Get all messages for a session with tenant isolation (FR-001).

    Args:
        session_id: Session ID to get messages for
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)

    Returns:
        List of QAMessages ordered by creation time
    """
    with session_scope() as session:
        stmt = (
            select(QAMessage)
            .where(
                QAMessage.session_id == session_id,
                QAMessage.tenant_id == tenant_id,
            )
            .order_by(QAMessage.created_at_utc.asc())
        )
        return list(session.scalars(stmt).all())
