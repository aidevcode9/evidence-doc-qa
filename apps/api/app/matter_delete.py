"""Matter hard delete workflow (FR-043).

Provides functions to permanently delete all data for a matter.
This is an irreversible operation and requires admin privileges.

SECURITY: All deletions happen in a SINGLE ATOMIC TRANSACTION.
If any deletion fails, all changes are rolled back to prevent
inconsistent state.
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import (
    AuditEvent,
    Chunk,
    Document,
    IndexRecord,
    Matter,
    MatterAssignment,
    QAMessage,
    QASession,
    create_audit_event,
    session_scope,
)


def _delete_matter_documents(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all documents for a matter (internal, uses provided session).

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of documents deleted
    """
    stmt = delete(Document).where(
        Document.tenant_id == tenant_id,
        Document.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def _delete_matter_chunks(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all chunks for a matter (internal, uses provided session).

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of chunks deleted
    """
    stmt = delete(Chunk).where(
        Chunk.tenant_id == tenant_id,
        Chunk.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def _delete_matter_index_records(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all index records for a matter (internal, uses provided session).

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of index records deleted
    """
    stmt = delete(IndexRecord).where(
        IndexRecord.tenant_id == tenant_id,
        IndexRecord.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def _delete_matter_qa_messages(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all QA messages for a matter (internal, uses provided session).

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of messages deleted
    """
    stmt = delete(QAMessage).where(
        QAMessage.tenant_id == tenant_id,
        QAMessage.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def _delete_matter_qa_sessions(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all QA sessions for a matter (internal, uses provided session).

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of sessions deleted
    """
    stmt = delete(QASession).where(
        QASession.tenant_id == tenant_id,
        QASession.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def _delete_matter_audit_events(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all audit events for a matter (internal, uses provided session).

    NOTE: This is the ONLY way audit events can be deleted.
    This is an exception to the normal audit immutability rule
    for legal "right to be forgotten" compliance.

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of audit events deleted
    """
    stmt = delete(AuditEvent).where(
        AuditEvent.tenant_id == tenant_id,
        AuditEvent.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def _delete_matter_assignments(
    session: Session, tenant_id: str, matter_id: str
) -> int:
    """Delete all matter assignments for a matter (internal, uses provided session).

    Args:
        session: Database session (for atomic transaction)
        tenant_id: Tenant ID
        matter_id: Matter ID

    Returns:
        Number of assignments deleted
    """
    stmt = delete(MatterAssignment).where(
        MatterAssignment.tenant_id == tenant_id,
        MatterAssignment.matter_id == matter_id,
    )
    result = session.execute(stmt)
    return result.rowcount if result.rowcount else 0


def hard_delete_matter(
    tenant_id: str,
    matter_id: str,
    deleted_by: str,
) -> dict[str, int]:
    """Hard delete all data for a matter (FR-043).

    This is an irreversible operation that permanently removes:
    - All documents and their content
    - All chunks and index records
    - All QA sessions and messages
    - All audit events for the matter
    - All matter assignments

    SECURITY: All deletions happen in a SINGLE ATOMIC TRANSACTION.
    If any deletion fails, all changes are rolled back to prevent
    the matter from being left in an inconsistent state.

    An audit event is logged BEFORE deletion for the deletion action itself.
    This audit event is NOT deleted because it has matter_id=None.

    Args:
        tenant_id: Tenant ID
        matter_id: Matter ID to delete
        deleted_by: User ID performing the deletion (for audit)

    Returns:
        Dict with counts of deleted items per resource type
    """
    # Log the deletion action FIRST (with matter_id=None so it's not deleted)
    # This provides an audit trail that the matter existed and was deleted
    # This is in a SEPARATE transaction so it persists even if deletion fails
    create_audit_event(
        tenant_id=tenant_id,
        user_id=deleted_by,
        event_type="matter_hard_delete",
        event_json={
            "matter_id": matter_id,
            "action": "hard_delete",
        },
        matter_id=None,  # Not associated with the matter being deleted
    )

    stats: dict[str, int] = {}

    # ALL deletions in ONE atomic transaction
    # If any fails, everything rolls back - no partial deletes
    with session_scope() as session:
        # Delete in order: dependencies first, then parent objects
        # 1. Delete QA messages (depends on sessions)
        stats["qa_messages"] = _delete_matter_qa_messages(
            session, tenant_id, matter_id
        )

        # 2. Delete QA sessions
        stats["qa_sessions"] = _delete_matter_qa_sessions(
            session, tenant_id, matter_id
        )

        # 3. Delete index records
        stats["index_records"] = _delete_matter_index_records(
            session, tenant_id, matter_id
        )

        # 4. Delete chunks
        stats["chunks"] = _delete_matter_chunks(session, tenant_id, matter_id)

        # 5. Delete documents
        stats["documents"] = _delete_matter_documents(session, tenant_id, matter_id)

        # 6. Delete audit events for the matter
        stats["audit_events"] = _delete_matter_audit_events(
            session, tenant_id, matter_id
        )

        # 7. Delete matter assignments
        stats["matter_assignments"] = _delete_matter_assignments(
            session, tenant_id, matter_id
        )

        # 8. Delete the matter row itself
        result = session.execute(
            delete(Matter).where(
                Matter.tenant_id == tenant_id,
                Matter.matter_id == matter_id,
            )
        )
        stats["matters"] = result.rowcount  # type: ignore[assignment]

    # If we reach here, all deletions succeeded and committed together
    return stats
