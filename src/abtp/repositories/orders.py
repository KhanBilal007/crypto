"""Repositories for append-only order intent and lifecycle records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from sqlite3 import Connection
from uuid import UUID, uuid4

from abtp.db.models import Tables
from abtp.domain import OrderIntent, OrderStatus
from abtp.domain.models import JsonValue
from abtp.repositories.serialization import (
    dumps_json,
    dumps_model,
    lifecycle_payload,
    order_intent_from_payload,
    pair_symbol,
)


@dataclass(frozen=True, slots=True)
class OrderLifecycleEvent:
    """Append-only order status/P&L event."""

    order_intent_id: UUID
    status: OrderStatus
    occurred_at: datetime
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    payload: dict[str, JsonValue] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


class OrderRepository:
    """Append and read order intents and lifecycle events."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append_intent(self, intent: OrderIntent) -> str:
        payload = intent.to_json_dict()
        self._connection.execute(
            """
            INSERT INTO order_intents (
                id, pair, side, order_type, quantity, limit_price, status,
                client_order_ref, created_at, signal_json, risk_decision_json, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(intent.id),
                pair_symbol(intent.pair),
                intent.side.value,
                intent.order_type.value,
                str(intent.quantity),
                str(intent.limit_price) if intent.limit_price is not None else None,
                intent.status.value,
                intent.client_order_ref,
                intent.created_at.isoformat(),
                dumps_json({"signal": payload["signal"]}),
                dumps_json({"risk_decision": payload["risk_decision"]})
                if payload["risk_decision"]
                else None,
                dumps_model(intent),
            ),
        )
        self._connection.commit()
        return str(intent.id)

    def get_intent(self, order_intent_id: str) -> OrderIntent | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.ORDER_INTENTS} WHERE id = ?",
            (order_intent_id,),
        ).fetchone()
        return order_intent_from_payload(str(row["payload_json"])) if row else None

    def append_lifecycle_event(self, event: OrderLifecycleEvent) -> str:
        payload = lifecycle_payload(
            order_intent_id=event.order_intent_id,
            status=event.status,
            occurred_at=event.occurred_at,
            realized_pnl=event.realized_pnl,
            unrealized_pnl=event.unrealized_pnl,
            payload=event.payload,
        )
        self._connection.execute(
            """
            INSERT INTO order_lifecycle_events (
                id, order_intent_id, status, occurred_at, realized_pnl,
                unrealized_pnl, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(event.id),
                str(event.order_intent_id),
                event.status.value,
                event.occurred_at.isoformat(),
                str(event.realized_pnl) if event.realized_pnl is not None else None,
                str(event.unrealized_pnl) if event.unrealized_pnl is not None else None,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ),
        )
        self._connection.commit()
        return str(event.id)

    def list_lifecycle_events(self, order_intent_id: str) -> tuple[OrderLifecycleEvent, ...]:
        rows = self._connection.execute(
            f"""
            SELECT id, status, occurred_at, realized_pnl, unrealized_pnl, payload_json
            FROM {Tables.ORDER_LIFECYCLE_EVENTS}
            WHERE order_intent_id = ?
            ORDER BY occurred_at, created_at
            """,
            (order_intent_id,),
        ).fetchall()
        return tuple(
            OrderLifecycleEvent(
                id=UUID(str(row["id"])),
                order_intent_id=UUID(order_intent_id),
                status=OrderStatus(str(row["status"])),
                occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
                realized_pnl=Decimal(str(row["realized_pnl"]))
                if row["realized_pnl"] is not None
                else None,
                unrealized_pnl=Decimal(str(row["unrealized_pnl"]))
                if row["unrealized_pnl"] is not None
                else None,
                payload={},
            )
            for row in rows
        )
