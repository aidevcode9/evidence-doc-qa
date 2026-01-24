from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Generator, Iterable

from sqlalchemy import Boolean, Float, Integer, String, Text, create_engine, select, text

if TYPE_CHECKING:
    from app.rbac import Role
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


class User(Base):
    """User model for RBAC (FR-003) and Authentication (FR-050)."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # admin, attorney, paralegal, viewer
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    # Authentication columns (FR-050)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # None for SSO users
    auth_provider: Mapped[str] = mapped_column(String, nullable=False, default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_utc: Mapped[str | None] = mapped_column(String, nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until_utc: Mapped[str | None] = mapped_column(String, nullable=True)


class MatterAssignment(Base):
    """Matter-level permission assignment (FR-004).

    Links users to matters they can access within a tenant.
    Users can only access matters they are explicitly assigned to,
    except admins who can access all matters in their tenant.
    """

    __tablename__ = "matter_assignments"

    assignment_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    granted_by: Mapped[str] = mapped_column(String, nullable=False)
    granted_at_utc: Mapped[str] = mapped_column(String, nullable=False)


class RefreshToken(Base):
    """Refresh token storage for JWT authentication (FR-050).

    Stores hashed refresh tokens to enable token refresh and revocation.
    Only the hash is stored, not the actual token.
    """

    __tablename__ = "refresh_tokens"

    token_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)  # SHA256 of token
    expires_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    revoked_at_utc: Mapped[str | None] = mapped_column(String, nullable=True)


class SSOState(Base):
    """SSO state storage for CSRF protection (FR-051).

    Stores pending SSO login states in database instead of memory.
    This enables multi-instance deployments and survives restarts.
    """

    __tablename__ = "sso_states"

    state_token: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # microsoft, google
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    code_verifier: Mapped[str] = mapped_column(String, nullable=False)  # PKCE verifier
    nonce: Mapped[str] = mapped_column(String, nullable=False)  # For ID token validation
    expires_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)


class AuditEvent(Base):
    """Immutable audit event log (FR-040).

    Stores all user actions for compliance and debugging.
    No UPDATE or DELETE functions provided (immutability).
    """

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    matter_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded details
    response_id: Mapped[str | None] = mapped_column(String, nullable=True)  # Links to Q&A
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False, index=True)


class RetentionPolicy(Base):
    """Configurable retention policy per tenant and resource type (FR-042).

    Defines how long data is retained before cleanup.
    Supports different retention periods for different resource types.
    """

    __tablename__ = "retention_policies"

    policy_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)  # qa_messages, telemetry, etc.
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)
    updated_at_utc: Mapped[str] = mapped_column(String, nullable=False)


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


# Matter Assignment CRUD functions (FR-004)


def user_has_matter_access(
    user_id: str,
    tenant_id: str,
    matter_id: str,
    user_role: "Role | None" = None,
) -> bool:
    """Check if user has access to a specific matter (FR-004).

    Admins bypass this check and have access to all matters in their tenant.
    Other users must have an explicit MatterAssignment record.

    Args:
        user_id: User ID to check
        tenant_id: Tenant ID (required for isolation)
        matter_id: Matter ID to check access for
        user_role: Optional role to check for admin bypass

    Returns:
        True if user has access, False otherwise
    """
    from app.rbac import Role

    # Admin bypass: admins can access all matters in their tenant
    if user_role == Role.ADMIN:
        return True

    with session_scope() as session:
        stmt = select(MatterAssignment).where(
            MatterAssignment.user_id == user_id,
            MatterAssignment.tenant_id == tenant_id,
            MatterAssignment.matter_id == matter_id,
        )
        assignment = session.scalars(stmt).first()
        return assignment is not None


def grant_matter_access(
    user_id: str,
    tenant_id: str,
    matter_id: str,
    granted_by: str,
) -> MatterAssignment:
    """Grant a user access to a matter (FR-004).

    Args:
        user_id: User to grant access to
        tenant_id: Tenant ID
        matter_id: Matter to grant access to
        granted_by: User ID of the admin granting access

    Returns:
        The created MatterAssignment
    """
    import uuid

    assignment = MatterAssignment(
        assignment_id=str(uuid.uuid4()),
        user_id=user_id,
        tenant_id=tenant_id,
        matter_id=matter_id,
        granted_by=granted_by,
        granted_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with session_scope() as session:
        session.add(assignment)
    return assignment


def revoke_matter_access(
    user_id: str,
    tenant_id: str,
    matter_id: str,
) -> bool:
    """Revoke a user's access to a matter (FR-004).

    Args:
        user_id: User to revoke access from
        tenant_id: Tenant ID
        matter_id: Matter to revoke access to

    Returns:
        True if an assignment was deleted, False if none existed
    """
    from sqlalchemy import delete

    with session_scope() as session:
        stmt = delete(MatterAssignment).where(
            MatterAssignment.user_id == user_id,
            MatterAssignment.tenant_id == tenant_id,
            MatterAssignment.matter_id == matter_id,
        )
        result = session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)


def get_user_matters(user_id: str, tenant_id: str) -> list[str]:
    """Get all matters a user has access to (FR-004).

    Args:
        user_id: User ID
        tenant_id: Tenant ID

    Returns:
        List of matter IDs the user can access
    """
    with session_scope() as session:
        stmt = select(MatterAssignment.matter_id).where(
            MatterAssignment.user_id == user_id,
            MatterAssignment.tenant_id == tenant_id,
        )
        rows = session.execute(stmt).all()
        return [row[0] for row in rows]


# Authentication CRUD functions (FR-050)


def get_user_by_email(email: str, tenant_id: str) -> User | None:
    """Get a user by email within a tenant (FR-050).

    Args:
        email: User email address
        tenant_id: Tenant ID (REQUIRED for isolation)

    Returns:
        User or None if not found
    """
    with session_scope() as session:
        stmt = select(User).where(
            User.email == email,
            User.tenant_id == tenant_id,
        )
        return session.scalars(stmt).first()


def get_user_by_id(user_id: str, tenant_id: str) -> User | None:
    """Get a user by ID within a tenant (FR-050).

    Args:
        user_id: User ID
        tenant_id: Tenant ID (REQUIRED for isolation)

    Returns:
        User or None if not found
    """
    with session_scope() as session:
        stmt = select(User).where(
            User.user_id == user_id,
            User.tenant_id == tenant_id,
        )
        return session.scalars(stmt).first()


def update_user_login_success(user_id: str, tenant_id: str) -> None:
    """Update user record on successful login (FR-050).

    Resets failed_login_count and sets last_login_utc.

    Args:
        user_id: User ID
        tenant_id: Tenant ID
    """
    from sqlalchemy import update

    with session_scope() as session:
        stmt = (
            update(User)
            .where(User.user_id == user_id, User.tenant_id == tenant_id)
            .values(
                failed_login_count=0,
                locked_until_utc=None,
                last_login_utc=datetime.now(timezone.utc).isoformat(),
            )
        )
        session.execute(stmt)


def increment_user_failed_login(user_id: str, tenant_id: str) -> int:
    """Atomically increment failed login count and return new count (FR-050).

    Uses atomic SQL (failed_login_count + 1) to prevent race conditions
    where concurrent login attempts could exceed MAX_FAILED_LOGIN_ATTEMPTS
    before lockout triggers.

    Args:
        user_id: User ID
        tenant_id: Tenant ID

    Returns:
        New failed_login_count after increment

    Security:
        Uses atomic increment to prevent TOCTOU race conditions.
    """
    from sqlalchemy import update

    with session_scope() as session:
        # Atomic increment: UPDATE ... SET failed_login_count = failed_login_count + 1
        update_stmt = (
            update(User)
            .where(User.user_id == user_id, User.tenant_id == tenant_id)
            .values(failed_login_count=User.failed_login_count + 1)
        )
        session.execute(update_stmt)

        # Fetch the new count after atomic update
        stmt = select(User.failed_login_count).where(
            User.user_id == user_id,
            User.tenant_id == tenant_id,
        )
        row = session.execute(stmt).first()
        return row[0] if row else 0


def lock_user_account(user_id: str, tenant_id: str, lock_minutes: int) -> None:
    """Lock a user account for a specified duration (FR-050).

    Args:
        user_id: User ID
        tenant_id: Tenant ID
        lock_minutes: Number of minutes to lock the account
    """
    from sqlalchemy import update

    locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
    with session_scope() as session:
        stmt = (
            update(User)
            .where(User.user_id == user_id, User.tenant_id == tenant_id)
            .values(locked_until_utc=locked_until.isoformat())
        )
        session.execute(stmt)


def create_user(
    user_id: str,
    tenant_id: str,
    email: str,
    role: str,
    password_hash: str | None = None,
    display_name: str | None = None,
    auth_provider: str = "local",
) -> User:
    """Create a new user (FR-050).

    Args:
        user_id: Unique user ID
        tenant_id: Tenant ID
        email: User email
        role: User role (admin, attorney, paralegal, viewer)
        password_hash: Hashed password (None for SSO users)
        display_name: Optional display name
        auth_provider: Authentication provider (local, oidc_azure, etc.)

    Returns:
        The created User
    """
    user = User(
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
        role=role,
        password_hash=password_hash,
        display_name=display_name,
        auth_provider=auth_provider,
        is_active=True,
        failed_login_count=0,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with session_scope() as session:
        session.add(user)
    return user


# Refresh Token CRUD functions (FR-050)


def store_refresh_token(
    token_id: str,
    user_id: str,
    tenant_id: str,
    token_hash: str,
    expires_at_utc: str,
) -> RefreshToken:
    """Store a refresh token hash (FR-050).

    Args:
        token_id: Unique token ID (JTI from JWT)
        user_id: User ID the token belongs to
        tenant_id: Tenant ID
        token_hash: SHA256 hash of the refresh token
        expires_at_utc: Token expiration timestamp

    Returns:
        The created RefreshToken record
    """
    token = RefreshToken(
        token_id=token_id,
        user_id=user_id,
        tenant_id=tenant_id,
        token_hash=token_hash,
        expires_at_utc=expires_at_utc,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with session_scope() as session:
        session.add(token)
    return token


def get_refresh_token(token_id: str, tenant_id: str) -> RefreshToken | None:
    """Get a refresh token by ID with tenant isolation (FR-050).

    Args:
        token_id: Token ID (JTI)
        tenant_id: Tenant ID (REQUIRED for isolation - prevents cross-tenant token probing)

    Returns:
        RefreshToken or None if not found or wrong tenant

    Security:
        Validates tenant_id to prevent cross-tenant token discovery.
    """
    with session_scope() as session:
        stmt = select(RefreshToken).where(
            RefreshToken.token_id == token_id,
            RefreshToken.tenant_id == tenant_id,
        )
        return session.scalars(stmt).first()


def revoke_refresh_token(token_id: str) -> bool:
    """Revoke a refresh token (FR-050).

    Args:
        token_id: Token ID to revoke

    Returns:
        True if token was revoked, False if not found
    """
    from sqlalchemy import update

    with session_scope() as session:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token_id == token_id, RefreshToken.revoked_at_utc.is_(None))
            .values(revoked_at_utc=datetime.now(timezone.utc).isoformat())
        )
        result = session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)


def revoke_user_refresh_tokens(user_id: str, tenant_id: str) -> int:
    """Revoke all refresh tokens for a user (FR-050).

    Used on password change or security events.

    Args:
        user_id: User ID
        tenant_id: Tenant ID

    Returns:
        Number of tokens revoked
    """
    from sqlalchemy import update

    with session_scope() as session:
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.tenant_id == tenant_id,
                RefreshToken.revoked_at_utc.is_(None),
            )
            .values(revoked_at_utc=datetime.now(timezone.utc).isoformat())
        )
        result = session.execute(stmt)
        return result.rowcount if result.rowcount else 0


def cleanup_expired_refresh_tokens() -> int:
    """Delete expired refresh tokens (FR-050).

    Called periodically to clean up old tokens.

    Returns:
        Number of tokens deleted
    """
    from sqlalchemy import delete

    now = datetime.now(timezone.utc).isoformat()
    with session_scope() as session:
        stmt = delete(RefreshToken).where(RefreshToken.expires_at_utc < now)
        result = session.execute(stmt)
        return result.rowcount if result.rowcount else 0


# Admin CRUD functions (FR-052)


def _escape_sql_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards to prevent pattern injection.

    Args:
        value: The search term to escape

    Returns:
        Escaped search term safe for LIKE patterns
    """
    # Escape special LIKE characters: % _ \ [ ]
    # Order matters: escape backslash first
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def list_users(
    tenant_id: str,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
) -> tuple[list[User], int]:
    """List users with pagination and search (FR-052).

    Args:
        tenant_id: Tenant ID (REQUIRED for isolation)
        offset: Number of records to skip
        limit: Maximum number of records to return
        search: Optional search term for email/display_name

    Returns:
        Tuple of (list of users, total count)

    Security:
        Search term wildcards are escaped to prevent pattern injection.
    """
    from sqlalchemy import func, or_

    with session_scope() as session:
        # Base query with tenant isolation
        base_query = select(User).where(User.tenant_id == tenant_id)

        # Apply search filter if provided
        if search:
            # Escape SQL wildcards to prevent pattern injection
            escaped_search = _escape_sql_like(search)
            search_pattern = f"%{escaped_search}%"
            base_query = base_query.where(
                or_(
                    User.email.ilike(search_pattern),
                    User.display_name.ilike(search_pattern),
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = session.scalar(count_query) or 0

        # Apply pagination
        paginated_query = base_query.offset(offset).limit(limit)
        users = list(session.scalars(paginated_query).all())

        return users, total


def update_user(
    user_id: str,
    tenant_id: str,
    role: str | None = None,
    display_name: str | None = None,
    is_active: bool | None = None,
) -> User | None:
    """Update user fields (FR-052).

    Args:
        user_id: User ID
        tenant_id: Tenant ID (REQUIRED for isolation)
        role: New role (if provided)
        display_name: New display name (if provided)
        is_active: New active status (if provided)

    Returns:
        Updated User or None if not found
    """
    from sqlalchemy import update

    with session_scope() as session:
        # Build update values
        values: dict[str, Any] = {}
        if role is not None:
            values["role"] = role
        if display_name is not None:
            values["display_name"] = display_name
        if is_active is not None:
            values["is_active"] = is_active

        if not values:
            # Nothing to update
            return get_user_by_id(user_id, tenant_id)

        stmt = (
            update(User)
            .where(User.user_id == user_id, User.tenant_id == tenant_id)
            .values(**values)
        )
        session.execute(stmt)

    # Return updated user
    return get_user_by_id(user_id, tenant_id)


def deactivate_user(user_id: str, tenant_id: str) -> bool:
    """Deactivate a user (soft delete) (FR-052).

    Args:
        user_id: User ID
        tenant_id: Tenant ID (REQUIRED for isolation)

    Returns:
        True if user was deactivated, False if not found
    """
    from sqlalchemy import update

    with session_scope() as session:
        stmt = (
            update(User)
            .where(User.user_id == user_id, User.tenant_id == tenant_id)
            .values(is_active=False)
        )
        result = session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)


# SSO State CRUD functions (FR-051)


def store_sso_state(
    state_token: str,
    provider: str,
    tenant_id: str,
    code_verifier: str,
    nonce: str,
    expires_at_utc: str,
) -> SSOState:
    """Store SSO state for CSRF protection (FR-051).

    Args:
        state_token: Opaque state token (random, not containing data)
        provider: SSO provider (microsoft, google)
        tenant_id: Application tenant ID
        code_verifier: PKCE code verifier
        nonce: Nonce for ID token validation
        expires_at_utc: Expiration timestamp

    Returns:
        The created SSOState record
    """
    state = SSOState(
        state_token=state_token,
        provider=provider,
        tenant_id=tenant_id,
        code_verifier=code_verifier,
        nonce=nonce,
        expires_at_utc=expires_at_utc,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with session_scope() as session:
        session.add(state)
    return state


def get_and_delete_sso_state(state_token: str) -> SSOState | None:
    """Get and atomically delete SSO state (consume once).

    Args:
        state_token: The state token to look up

    Returns:
        SSOState if found and not expired, None otherwise
    """
    from sqlalchemy import delete

    with session_scope() as session:
        # First get the state
        stmt = select(SSOState).where(SSOState.state_token == state_token)
        state = session.scalars(stmt).first()

        if state is None:
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(state.expires_at_utc)
        if datetime.now(timezone.utc) > expires_at:
            # Expired - delete and return None
            del_stmt = delete(SSOState).where(SSOState.state_token == state_token)
            session.execute(del_stmt)
            return None

        # Delete the state (consume once)
        del_stmt = delete(SSOState).where(SSOState.state_token == state_token)
        session.execute(del_stmt)

        return state


def cleanup_expired_sso_states() -> int:
    """Delete expired SSO states (FR-051).

    Called periodically to clean up abandoned login flows.

    Returns:
        Number of states deleted
    """
    from sqlalchemy import delete

    now = datetime.now(timezone.utc).isoformat()
    with session_scope() as session:
        stmt = delete(SSOState).where(SSOState.expires_at_utc < now)
        result = session.execute(stmt)
        return result.rowcount if result.rowcount else 0


# Audit Event CRUD functions (FR-040)


def create_audit_event(
    tenant_id: str,
    user_id: str,
    event_type: str,
    event_json: dict[str, Any],
    matter_id: str | None = None,
    response_id: str | None = None,
) -> AuditEvent:
    """Create an immutable audit event (FR-040).

    Args:
        tenant_id: Tenant ID
        user_id: User ID who performed the action
        event_type: Type of event (query, upload, export, delete, login, etc.)
        event_json: JSON-serializable dict with event details (no PII)
        matter_id: Matter ID if action is matter-specific
        response_id: Links to Q&A response if applicable

    Returns:
        The created AuditEvent record
    """
    import json
    import uuid

    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        event_type=event_type,
        event_json=json.dumps(event_json),
        response_id=response_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    with session_scope() as session:
        session.add(event)
    return event


def list_audit_events(
    tenant_id: str,
    matter_id: str | None = None,
    event_type: str | None = None,
    user_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[AuditEvent]:
    """List audit events with filters (FR-040, FR-041).

    Args:
        tenant_id: Tenant ID (REQUIRED for isolation)
        matter_id: Filter by matter ID
        event_type: Filter by event type
        user_id: Filter by user ID
        start_date: Filter by created_at >= start_date (ISO format)
        end_date: Filter by created_at <= end_date (ISO format)
        offset: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of AuditEvent records
    """
    with session_scope() as session:
        query = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)

        if matter_id:
            query = query.where(AuditEvent.matter_id == matter_id)
        if event_type:
            query = query.where(AuditEvent.event_type == event_type)
        if user_id:
            query = query.where(AuditEvent.user_id == user_id)
        if start_date:
            query = query.where(AuditEvent.created_at_utc >= start_date)
        if end_date:
            query = query.where(AuditEvent.created_at_utc <= end_date)

        query = query.order_by(AuditEvent.created_at_utc.desc())
        query = query.offset(offset).limit(limit)

        events = session.scalars(query).all()
        return list(events)


def count_audit_events(
    tenant_id: str,
    matter_id: str | None = None,
    event_type: str | None = None,
    user_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> int:
    """Count audit events with filters (FR-041).

    Args:
        tenant_id: Tenant ID (REQUIRED for isolation)
        matter_id: Filter by matter ID
        event_type: Filter by event type
        user_id: Filter by user ID
        start_date: Filter by created_at >= start_date (ISO format)
        end_date: Filter by created_at <= end_date (ISO format)

    Returns:
        Count of matching audit events
    """
    from sqlalchemy import func

    with session_scope() as session:
        query = select(func.count()).select_from(AuditEvent).where(
            AuditEvent.tenant_id == tenant_id
        )

        if matter_id:
            query = query.where(AuditEvent.matter_id == matter_id)
        if event_type:
            query = query.where(AuditEvent.event_type == event_type)
        if user_id:
            query = query.where(AuditEvent.user_id == user_id)
        if start_date:
            query = query.where(AuditEvent.created_at_utc >= start_date)
        if end_date:
            query = query.where(AuditEvent.created_at_utc <= end_date)

        count = session.scalar(query)
        return count or 0


# Retention Policy CRUD functions (FR-042)


def create_retention_policy(
    tenant_id: str,
    resource_type: str,
    retention_days: int,
) -> RetentionPolicy:
    """Create a retention policy for a tenant and resource type (FR-042).

    Args:
        tenant_id: Tenant ID
        resource_type: Type of resource (qa_messages, qa_sessions, audit_events, etc.)
        retention_days: Number of days to retain data

    Returns:
        The created RetentionPolicy record
    """
    import uuid

    now = datetime.now(timezone.utc).isoformat()
    policy = RetentionPolicy(
        policy_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        resource_type=resource_type,
        retention_days=retention_days,
        created_at_utc=now,
        updated_at_utc=now,
    )
    with session_scope() as session:
        session.add(policy)
    return policy


def get_retention_policy(
    tenant_id: str,
    resource_type: str,
) -> RetentionPolicy | None:
    """Get retention policy for a tenant and resource type (FR-042).

    Args:
        tenant_id: Tenant ID
        resource_type: Type of resource

    Returns:
        RetentionPolicy or None if not found
    """
    with session_scope() as session:
        stmt = select(RetentionPolicy).where(
            RetentionPolicy.tenant_id == tenant_id,
            RetentionPolicy.resource_type == resource_type,
        )
        return session.scalars(stmt).first()


def update_retention_policy(
    tenant_id: str,
    resource_type: str,
    retention_days: int,
) -> bool:
    """Update retention days for a policy (FR-042).

    Args:
        tenant_id: Tenant ID
        resource_type: Type of resource
        retention_days: New retention days value

    Returns:
        True if policy was updated, False if not found
    """
    from sqlalchemy import update

    with session_scope() as session:
        stmt = (
            update(RetentionPolicy)
            .where(
                RetentionPolicy.tenant_id == tenant_id,
                RetentionPolicy.resource_type == resource_type,
            )
            .values(
                retention_days=retention_days,
                updated_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        )
        result = session.execute(stmt)
        return bool(result.rowcount and result.rowcount > 0)
