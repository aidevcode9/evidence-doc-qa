from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from typing import Generator, Iterable

from sqlalchemy import Boolean, Float, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    doc_sha256: Mapped[str] = mapped_column(String, nullable=False)
    doc_name: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_sha256: Mapped[str] = mapped_column(String, nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    parse_mode: Mapped[str] = mapped_column(String, nullable=False)


class IndexRecord(Base):
    __tablename__ = "index_records"

    chunk_id: Mapped[str] = mapped_column(String, primary_key=True)
    docs_snapshot_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_id: Mapped[str] = mapped_column(String, nullable=False)
    doc_name: Mapped[str] = mapped_column(String, nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    index_version: Mapped[str] = mapped_column(String, nullable=False)
    retrieval_version: Mapped[str] = mapped_column(String, nullable=False)


class Telemetry(Base):
    __tablename__ = "telemetry"

    request_id: Mapped[str] = mapped_column(String, primary_key=True)
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


def _engine():
    if not DATABASE_URL:
        raise RuntimeError("DB_DATABASE_URL is required.")
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


def get_latest_docs_snapshot_id() -> str | None:
    with session_scope() as session:
        stmt = select(Document.docs_snapshot_id).order_by(Document.ingested_at_utc.desc())
        row = session.execute(stmt).first()
        return row[0] if row else None


def get_doc_name(doc_id: str) -> str | None:
    with session_scope() as session:
        stmt = select(Document.doc_name).where(Document.doc_id == doc_id)
        row = session.execute(stmt).first()
        return row[0] if row else None


def load_chunks(docs_snapshot_id: str | None) -> list[Chunk]:
    with session_scope() as session:
        stmt = select(Chunk)
        if docs_snapshot_id:
            stmt = stmt.where(Chunk.docs_snapshot_id == docs_snapshot_id)
        return list(session.scalars(stmt).all())


def load_index_records(docs_snapshot_id: str | None) -> list[IndexRecord]:
    with session_scope() as session:
        stmt = select(IndexRecord)
        if docs_snapshot_id:
            stmt = stmt.where(IndexRecord.docs_snapshot_id == docs_snapshot_id)
        return list(session.scalars(stmt).all())


def load_telemetry(hours: int = 24, limit: int = 500) -> list[Telemetry]:
    with session_scope() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = (
            select(Telemetry)
            .where(Telemetry.timestamp_utc >= cutoff.isoformat())
            .order_by(Telemetry.timestamp_utc.desc())
            .limit(limit)
        )
        rows = list(session.scalars(stmt).all())
        return rows
