"""Repository for portfolio snapshots and positions."""

from __future__ import annotations

from sqlite3 import Connection
from uuid import uuid4

from abtp.db.models import Tables
from abtp.domain import PortfolioSnapshot
from abtp.repositories.serialization import dumps_model, portfolio_snapshot_from_payload


class PortfolioSnapshotRepository:
    """Persist portfolio snapshots without account credential storage."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def add_snapshot(self, snapshot: PortfolioSnapshot) -> str:
        snapshot_id = str(uuid4())
        self._connection.execute(
            """
            INSERT INTO portfolio_snapshots (id, captured_at, source_ref, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot_id,
                snapshot.captured_at.isoformat(),
                snapshot.source_ref,
                dumps_model(snapshot),
            ),
        )
        for position in snapshot.positions:
            self._connection.execute(
                """
                INSERT INTO positions (
                    snapshot_id, asset, quantity, valuation_quote, valuation,
                    captured_at, source_ref
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    position.asset.symbol,
                    str(position.quantity),
                    position.valuation_quote.symbol,
                    str(position.valuation),
                    snapshot.captured_at.isoformat(),
                    snapshot.source_ref,
                ),
            )
        self._connection.commit()
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> PortfolioSnapshot | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.PORTFOLIO_SNAPSHOTS} WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        return portfolio_snapshot_from_payload(str(row["payload_json"])) if row else None
