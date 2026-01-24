"""Audit logging helpers (FR-040).

Provides convenience functions for logging specific event types with proper
PII redaction. All functions use the immutable create_audit_event() in db.py.

Event Types:
- query: User asked a question (question text redacted)
- upload: Document uploaded
- export: Q&A session exported
- delete: Document or matter deleted
- login: User logged in
- logout: User logged out
- user_create: Admin created a user
- user_update: Admin updated a user
- user_deactivate: Admin deactivated a user
- matter_access_grant: Admin granted matter access
- matter_access_revoke: Admin revoked matter access
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db import AuditEvent

from app.db import create_audit_event


def _hash_text(text: str) -> str:
    """Hash text for audit logging (non-reversible).

    Used to track queries without storing PII.
    """
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def create_query_audit_event(
    tenant_id: str,
    matter_id: str,
    user_id: str,
    question: str,
    doc_ids: list[str],
    response_id: str,
    model: str,
    latency_ms: int,
    confidence: float | None = None,
    refusal_code: str | None = None,
) -> "AuditEvent":
    """Log a Q&A query event (FR-040).

    Question text is hashed, not stored in plain text (PII protection).

    Args:
        tenant_id: Tenant ID
        matter_id: Matter ID
        user_id: User who asked the question
        question: The question text (will be hashed)
        doc_ids: List of document IDs that were retrieved
        response_id: ID of the response/message
        model: LLM model used
        latency_ms: Query latency in milliseconds
        confidence: Confidence score if available
        refusal_code: Refusal code if query was refused

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        event_type="query",
        event_json={
            "question_hash": _hash_text(question),
            "question_length": len(question),
            "question_redacted": True,
            "doc_ids": doc_ids,
            "doc_count": len(doc_ids),
            "model": model,
            "latency_ms": latency_ms,
            "confidence": confidence,
            "refusal_code": refusal_code,
        },
        response_id=response_id,
    )


def create_upload_audit_event(
    tenant_id: str,
    matter_id: str,
    user_id: str,
    doc_id: str,
    doc_name: str,
    page_count: int,
    file_size_bytes: int,
) -> "AuditEvent":
    """Log a document upload event (FR-040).

    Args:
        tenant_id: Tenant ID
        matter_id: Matter ID
        user_id: User who uploaded
        doc_id: Document ID
        doc_name: Document filename
        page_count: Number of pages
        file_size_bytes: File size in bytes

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        event_type="upload",
        event_json={
            "doc_id": doc_id,
            "doc_name": doc_name,
            "page_count": page_count,
            "file_size_bytes": file_size_bytes,
        },
    )


def create_export_audit_event(
    tenant_id: str,
    matter_id: str,
    user_id: str,
    session_id: str,
    export_format: str,
    message_count: int,
) -> "AuditEvent":
    """Log a Q&A export event (FR-040).

    Args:
        tenant_id: Tenant ID
        matter_id: Matter ID
        user_id: User who exported
        session_id: Session ID that was exported
        export_format: Format (pdf, docx)
        message_count: Number of messages exported

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        event_type="export",
        event_json={
            "session_id": session_id,
            "export_format": export_format,
            "message_count": message_count,
        },
    )


def create_delete_audit_event(
    tenant_id: str,
    user_id: str,
    target_type: str,
    target_id: str,
    matter_id: str | None = None,
) -> "AuditEvent":
    """Log a delete event (FR-040).

    Args:
        tenant_id: Tenant ID
        user_id: User who deleted
        target_type: Type of deleted item (document, matter)
        target_id: ID of deleted item
        matter_id: Matter ID if applicable

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        event_type="delete",
        event_json={
            "target_type": target_type,
            "target_id": target_id,
        },
    )


def create_login_audit_event(
    tenant_id: str,
    user_id: str,
    method: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
) -> "AuditEvent":
    """Log a login event (FR-040).

    Args:
        tenant_id: Tenant ID
        user_id: User who logged in
        method: Login method (password, microsoft_sso, google_sso)
        ip_address: Client IP address (optional, for security)
        user_agent: Client user agent (optional)
        success: Whether login was successful

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type="login",
        event_json={
            "method": method,
            "ip_address": ip_address,
            "user_agent_hash": _hash_text(user_agent) if user_agent else None,
            "success": success,
        },
    )


def create_logout_audit_event(
    tenant_id: str,
    user_id: str,
) -> "AuditEvent":
    """Log a logout event (FR-040).

    Args:
        tenant_id: Tenant ID
        user_id: User who logged out

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type="logout",
        event_json={},
    )


def create_user_create_audit_event(
    tenant_id: str,
    admin_user_id: str,
    new_user_id: str,
    new_user_email: str,
    new_user_role: str,
) -> "AuditEvent":
    """Log a user creation event (FR-040).

    Args:
        tenant_id: Tenant ID
        admin_user_id: Admin who created the user
        new_user_id: ID of newly created user
        new_user_email: Email of newly created user
        new_user_role: Role assigned to new user

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        user_id=admin_user_id,
        event_type="user_create",
        event_json={
            "target_user_id": new_user_id,
            "target_user_email": new_user_email,
            "target_user_role": new_user_role,
        },
    )


def create_user_update_audit_event(
    tenant_id: str,
    admin_user_id: str,
    target_user_id: str,
    changes: dict[str, str | bool | None],
) -> "AuditEvent":
    """Log a user update event (FR-040).

    Args:
        tenant_id: Tenant ID
        admin_user_id: Admin who updated the user
        target_user_id: ID of updated user
        changes: Dict of changed fields and new values

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        user_id=admin_user_id,
        event_type="user_update",
        event_json={
            "target_user_id": target_user_id,
            "changes": changes,
        },
    )


def create_user_deactivate_audit_event(
    tenant_id: str,
    admin_user_id: str,
    target_user_id: str,
) -> "AuditEvent":
    """Log a user deactivation event (FR-040).

    Args:
        tenant_id: Tenant ID
        admin_user_id: Admin who deactivated the user
        target_user_id: ID of deactivated user

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        user_id=admin_user_id,
        event_type="user_deactivate",
        event_json={
            "target_user_id": target_user_id,
        },
    )


def create_matter_access_grant_audit_event(
    tenant_id: str,
    admin_user_id: str,
    target_user_id: str,
    matter_id: str,
) -> "AuditEvent":
    """Log a matter access grant event (FR-040).

    Args:
        tenant_id: Tenant ID
        admin_user_id: Admin who granted access
        target_user_id: User who received access
        matter_id: Matter ID access was granted to

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=admin_user_id,
        event_type="matter_access_grant",
        event_json={
            "target_user_id": target_user_id,
        },
    )


def create_matter_access_revoke_audit_event(
    tenant_id: str,
    admin_user_id: str,
    target_user_id: str,
    matter_id: str,
) -> "AuditEvent":
    """Log a matter access revoke event (FR-040).

    Args:
        tenant_id: Tenant ID
        admin_user_id: Admin who revoked access
        target_user_id: User who lost access
        matter_id: Matter ID access was revoked from

    Returns:
        The created AuditEvent
    """
    return create_audit_event(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=admin_user_id,
        event_type="matter_access_revoke",
        event_json={
            "target_user_id": target_user_id,
        },
    )
