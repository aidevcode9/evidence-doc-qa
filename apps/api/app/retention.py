"""Retention policy cleanup functions (FR-042).

Provides functions to clean up expired data based on retention policies.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import (
    DEFAULT_QA_RETENTION_DAYS,
    DEFAULT_TELEMETRY_RETENTION_DAYS,
)
from app.db import (
    QAMessage,
    QASession,
    Telemetry,
    get_retention_policy,
    session_scope,
)


def cleanup_expired_qa_messages(
    tenant_id: str,
    retention_days: int | None = None,
) -> int:
    """Delete QA messages older than retention period (FR-042).

    Args:
        tenant_id: Tenant ID
        retention_days: Days to retain (uses policy or default if not provided)

    Returns:
        Number of messages deleted
    """
    if retention_days is None:
        policy = get_retention_policy(tenant_id, "qa_messages")
        retention_days = policy.retention_days if policy else DEFAULT_QA_RETENTION_DAYS

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat()

    with session_scope() as session:
        stmt = delete(QAMessage).where(
            QAMessage.tenant_id == tenant_id,
            QAMessage.created_at_utc < cutoff_str,
        )
        result = session.execute(stmt)
        return result.rowcount if result.rowcount else 0


def cleanup_expired_qa_sessions(
    tenant_id: str,
    retention_days: int | None = None,
) -> int:
    """Delete QA sessions older than retention period (FR-042).

    Args:
        tenant_id: Tenant ID
        retention_days: Days to retain (uses policy or default if not provided)

    Returns:
        Number of sessions deleted
    """
    if retention_days is None:
        policy = get_retention_policy(tenant_id, "qa_sessions")
        retention_days = policy.retention_days if policy else DEFAULT_QA_RETENTION_DAYS

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat()

    with session_scope() as session:
        stmt = delete(QASession).where(
            QASession.tenant_id == tenant_id,
            QASession.created_at_utc < cutoff_str,
        )
        result = session.execute(stmt)
        return result.rowcount if result.rowcount else 0


def cleanup_expired_telemetry(
    tenant_id: str,
    retention_days: int | None = None,
) -> int:
    """Delete telemetry records older than retention period (FR-042).

    Args:
        tenant_id: Tenant ID
        retention_days: Days to retain (uses policy or default if not provided)

    Returns:
        Number of telemetry records deleted
    """
    if retention_days is None:
        policy = get_retention_policy(tenant_id, "telemetry")
        retention_days = policy.retention_days if policy else DEFAULT_TELEMETRY_RETENTION_DAYS

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat()

    with session_scope() as session:
        stmt = delete(Telemetry).where(
            Telemetry.tenant_id == tenant_id,
            Telemetry.timestamp_utc < cutoff_str,
        )
        result = session.execute(stmt)
        return result.rowcount if result.rowcount else 0


def run_retention_cleanup(tenant_id: str) -> dict[str, int]:
    """Run all retention cleanup jobs for a tenant (FR-042).

    Applies retention policies for all resource types.
    Uses tenant-specific policies if configured, otherwise defaults.

    Note: Audit events are NOT cleaned up by this function.
    They have a 7-year retention (legal requirement) and are only
    deleted via hard_delete_matter (FR-043).

    Args:
        tenant_id: Tenant ID

    Returns:
        Dict with counts of deleted items per resource type
    """
    results: dict[str, int] = {}

    # Clean up QA messages first (depends on sessions)
    results["qa_messages"] = cleanup_expired_qa_messages(tenant_id)

    # Clean up QA sessions (only after messages are gone)
    results["qa_sessions"] = cleanup_expired_qa_sessions(tenant_id)

    # Clean up telemetry
    results["telemetry"] = cleanup_expired_telemetry(tenant_id)

    # NOTE: Audit events are NOT cleaned up automatically
    # They have a 7-year legal retention requirement (DEFAULT_AUDIT_RETENTION_DAYS)
    # Only hard_delete_matter (FR-043) removes them

    return results
