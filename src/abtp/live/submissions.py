"""Durable, single-use submission reservations shared by gateway instances."""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime
from pathlib import Path
from sqlite3 import Connection, connect
from uuid import UUID

from abtp.data import normalize_timestamp
from abtp.db import connect_database
from abtp.domain import OrderIntent


class LiveSubmissionConflict(ValueError):
    """An intent/approval was consumed, or an earlier attempt needs reconciliation."""


class LiveSubmissionLedger:
    """Dedicated on-disk safety ledger; never delete or rotate it between restarts."""

    def __init__(self, path: Path) -> None:
        if str(path) in {"", ".", ":memory:"}:
            raise ValueError("live submission ledger requires a persistent file")
        self._path = path.expanduser().resolve()
        with closing(connect_database(self._path)) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS live_submission_attempts (
                    intent_id TEXT PRIMARY KEY,
                    approval_id TEXT UNIQUE,
                    exchange_name TEXT NOT NULL,
                    reserved_at TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending_reconciliation',
                    exchange_order_id TEXT,
                    outcome TEXT,
                    completed_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS execution_control "
                "(id INTEGER PRIMARY KEY CHECK (id = 1), halt_reason TEXT NOT NULL)"
            )
            connection.execute("INSERT OR IGNORE INTO execution_control VALUES (1, '')")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS execution_control_events "
                "(id INTEGER PRIMARY KEY, action TEXT NOT NULL, reason TEXT NOT NULL, "
                "occurred_at TEXT NOT NULL)"
            )

    def halt_reason(self) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT halt_reason FROM execution_control WHERE id = 1"
            ).fetchone()
            if row is None:
                raise ValueError("execution control state is missing")
            return str(row[0])

    def set_halt(self, *, reason: str, occurred_at: datetime) -> None:
        self._set_control("halt", reason, occurred_at)

    def resume_after_review(self, *, reason: str, occurred_at: datetime) -> None:
        self._set_control("resume", reason, occurred_at)

    def _set_control(self, action: str, reason: str, occurred_at: datetime) -> None:
        if not reason.strip():
            raise ValueError("operator control reason is required")
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE execution_control SET halt_reason = ? WHERE id = 1",
                (reason if action == "halt" else "",),
            )
            if cursor.rowcount != 1:
                raise ValueError("execution control state is missing")
            connection.execute(
                "INSERT INTO execution_control_events (action, reason, occurred_at) "
                "VALUES (?, ?, ?)",
                (action, reason, normalize_timestamp(occurred_at).isoformat()),
            )

    def _connect(self) -> Connection:
        # Missing/deleted storage must not silently become a fresh empty ledger.
        connection = connect(self._path.as_uri() + "?mode=rw", uri=True)
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def reserve(
        self,
        intent: OrderIntent,
        *,
        approval_id: UUID | None,
        exchange_name: str,
        reserved_at: datetime,
    ) -> None:
        """Commit consumption before any exchange call, including ambiguous failures."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            control = connection.execute(
                "SELECT halt_reason FROM execution_control WHERE id = 1"
            ).fetchone()
            if control is None or control[0]:
                raise LiveSubmissionConflict("execution is halted or control state is missing")
            duplicate = connection.execute(
                "SELECT 1 FROM live_submission_attempts WHERE intent_id = ? OR approval_id = ?",
                (str(intent.id), str(approval_id) if approval_id is not None else None),
            ).fetchone()
            if duplicate:
                raise LiveSubmissionConflict("order intent or approval has already been consumed")
            pending = connection.execute(
                "SELECT 1 FROM live_submission_attempts WHERE state = 'pending_reconciliation'"
            ).fetchone()
            if pending:
                raise LiveSubmissionConflict("previous submission requires reconciliation")
            connection.execute(
                """
                INSERT INTO live_submission_attempts
                    (intent_id, approval_id, exchange_name, reserved_at, intent_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(intent.id),
                    str(approval_id) if approval_id is not None else None,
                    exchange_name,
                    normalize_timestamp(reserved_at).isoformat(),
                    json.dumps(intent.to_json_dict(), sort_keys=True),
                ),
            )

    def record_outcome(
        self,
        intent_id: UUID,
        *,
        exchange_order_id: str | None,
        outcome: str,
        completed_at: datetime,
    ) -> None:
        """Record a known response without releasing either single-use identifier."""
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE live_submission_attempts
                SET state = 'acknowledged', exchange_order_id = ?, outcome = ?, completed_at = ?
                WHERE intent_id = ? AND state = 'pending_reconciliation'
                """,
                (
                    exchange_order_id,
                    outcome,
                    normalize_timestamp(completed_at).isoformat(),
                    str(intent_id),
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("submission reservation is missing or already acknowledged")
