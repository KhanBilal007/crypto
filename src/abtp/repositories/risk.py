"""Repository for append-only risk decisions."""

from __future__ import annotations

from sqlite3 import Connection

from abtp.db.models import Tables
from abtp.domain import RiskDecision
from abtp.repositories.serialization import dumps_json, dumps_model, risk_decision_from_payload


class RiskDecisionRepository:
    """Append and read risk decisions."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, decision: RiskDecision) -> int:
        payload = decision.to_json_dict()
        cursor = self._connection.execute(
            """
            INSERT INTO risk_decisions (
                order_intent_id, status, allow, reject, max_position_size,
                stop_loss_required, kill_switch_active, evaluated_at, policy_version,
                reasons_json, checks_json, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(decision.order_intent_id),
                decision.status.value,
                int(decision.allowed),
                int(decision.rejected),
                str(decision.max_position_size),
                int(decision.stop_loss_required),
                int(decision.kill_switch_active),
                decision.evaluated_at.isoformat(),
                decision.policy_version,
                dumps_json({"reasons": payload["reasons"]}),
                dumps_json({"checks": payload["checks"]}),
                dumps_model(decision),
            ),
        )
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("risk decision insert did not return a row id")
        return cursor.lastrowid

    def list_for_order(self, order_intent_id: str) -> tuple[RiskDecision, ...]:
        rows = self._connection.execute(
            f"""
            SELECT payload_json FROM {Tables.RISK_DECISIONS}
            WHERE order_intent_id = ?
            ORDER BY evaluated_at, id
            """,
            (order_intent_id,),
        ).fetchall()
        return tuple(risk_decision_from_payload(str(row["payload_json"])) for row in rows)
