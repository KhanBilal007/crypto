"""Append-only audit event repository."""

from __future__ import annotations

from sqlite3 import Connection

from abtp.db.models import Tables
from abtp.domain import AuditEvent
from abtp.repositories.serialization import audit_event_from_payload, dumps_model


class AuditRepository:
    """Append and read audit events."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, event: AuditEvent) -> str:
        self._connection.execute(
            """
            INSERT INTO audit_events (
                id, event_type, occurred_at, payload_json, causation_id, correlation_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(event.id),
                str(event.event_type),
                event.occurred_at.isoformat(),
                dumps_model(event),
                str(event.causation_id) if event.causation_id else None,
                str(event.correlation_id) if event.correlation_id else None,
            ),
        )
        self._connection.commit()
        return str(event.id)

    def get(self, event_id: str) -> AuditEvent | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.AUDIT_EVENTS} WHERE id = ?",
            (event_id,),
        ).fetchone()
        return audit_event_from_payload(str(row["payload_json"])) if row else None

    def list_by_correlation(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        rows = self._connection.execute(
            f"""
            SELECT payload_json FROM {Tables.AUDIT_EVENTS}
            WHERE correlation_id = ?
            ORDER BY occurred_at, created_at
            """,
            (correlation_id,),
        ).fetchall()
        return tuple(audit_event_from_payload(str(row["payload_json"])) for row in rows)
