"""SQLite persistence for the local paper dashboard ledger."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from sqlite3 import Connection
from uuid import uuid4

from abtp.db.models import Tables
from abtp.domain.models import JsonValue


class PaperDashboardRepository:
    """Persist paper dashboard state in SQLite while keeping JSON compatibility."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def save_state_payload(
        self,
        payload: Mapping[str, JsonValue],
        *,
        strategy_evaluations: Sequence[Mapping[str, JsonValue]] = (),
        risk_decisions: Sequence[Mapping[str, JsonValue]] = (),
        simulated_fills: Sequence[Mapping[str, JsonValue]] = (),
        operator_actions: Sequence[Mapping[str, JsonValue]] = (),
    ) -> None:
        """Persist a full paper dashboard snapshot plus append-only evidence rows."""

        account = _mapping(payload.get("account"))
        updated_at = _text(payload.get("updated_at"))
        market_data_source = _text(payload.get("market_data_source"))
        snapshot_id = str(uuid4())
        self._connection.execute(
            f"""
            INSERT INTO {Tables.PAPER_ACCOUNT_SNAPSHOTS} (
                id, captured_at, market_data_source, cash, base_quantity,
                average_entry_price, realized_pnl, fees_paid, equity_history_json,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                updated_at,
                market_data_source,
                _text(account.get("cash")),
                _text(account.get("base_quantity")),
                _text(account.get("average_entry_price")),
                _text(account.get("realized_pnl")),
                _text(account.get("fees_paid")),
                json.dumps(account.get("equity_history", []), sort_keys=True),
                _dumps(payload),
            ),
        )
        self._save_preferences(_mapping(payload.get("ui_preferences")), updated_at=updated_at)
        self._save_transactions(_sequence(payload.get("trades")))
        self._save_open_orders(_sequence(payload.get("open_paper_orders")), snapshot_id=snapshot_id)
        self._save_alert_rules(_sequence(payload.get("alert_rules")), snapshot_id=snapshot_id)
        self._save_journal_entries(
            _sequence(payload.get("journal_entries")),
            snapshot_id=snapshot_id,
        )
        self._save_trader_feedback(
            _sequence(payload.get("trader_feedback")),
            snapshot_id=snapshot_id,
        )
        self._save_chart_drawings(
            _sequence(payload.get("chart_drawings")),
            snapshot_id=snapshot_id,
        )
        self._save_strategy_evaluations(strategy_evaluations)
        self._save_risk_decisions(risk_decisions)
        self._save_simulated_fills(simulated_fills)
        self._save_operator_actions(operator_actions)
        self._connection.commit()

    def load_latest_state_payload(self) -> Mapping[str, JsonValue] | None:
        """Return the latest JSON-compatible state payload, if present."""

        row = self._connection.execute(
            f"""
            SELECT payload_json
            FROM {Tables.PAPER_ACCOUNT_SNAPSHOTS}
            ORDER BY captured_at DESC, created_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, Mapping):
            raise ValueError("paper dashboard payload must be a JSON object")
        return payload

    def list_transactions(self) -> tuple[Mapping[str, JsonValue], ...]:
        """Return persisted paper transaction payloads newest first."""

        rows = self._connection.execute(
            f"""
            SELECT payload_json
            FROM {Tables.PAPER_TRANSACTIONS}
            ORDER BY occurred_at DESC, created_at DESC
            """
        ).fetchall()
        return tuple(_loaded_mapping(str(row["payload_json"])) for row in rows)

    def _save_preferences(
        self,
        preferences: Mapping[str, JsonValue],
        *,
        updated_at: str,
    ) -> None:
        flattened = _flatten_preferences(preferences)
        for key, value in flattened.items():
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_PREFERENCES} (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, _dumps({"value": value}), updated_at),
            )

    def _save_transactions(self, trades: Sequence[JsonValue]) -> None:
        for item in trades:
            trade = _mapping(item)
            self._connection.execute(
                f"""
                INSERT OR IGNORE INTO {Tables.PAPER_TRANSACTIONS} (
                    id, order_intent_id, side, quantity, price, fee_paid,
                    occurred_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    _text(trade.get("order_intent_id")),
                    _text(trade.get("side")),
                    _text(trade.get("quantity")),
                    _text(trade.get("price")),
                    _text(trade.get("fee_paid")),
                    _text(trade.get("occurred_at")),
                    _dumps(trade),
                ),
            )

    def _save_open_orders(self, orders: Sequence[JsonValue], *, snapshot_id: str) -> None:
        for item in orders:
            order = _mapping(item)
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_OPEN_ORDERS} (
                    id, snapshot_id, order_id, symbol, order_type, side,
                    quantity, status, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    snapshot_id,
                    _text(order.get("order_id")),
                    _text(order.get("symbol")),
                    _text(order.get("order_type")),
                    _text(order.get("side")),
                    _text(order.get("quantity")),
                    _text(order.get("status")),
                    _text(order.get("created_at")),
                    _dumps(order),
                ),
            )

    def _save_alert_rules(self, rules: Sequence[JsonValue], *, snapshot_id: str) -> None:
        for item in rules:
            rule = _mapping(item)
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_ALERT_RULES} (
                    id, snapshot_id, alert_id, alert_type, symbol, threshold,
                    expected_value, enabled, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    snapshot_id,
                    _text(rule.get("alert_id")),
                    _text(rule.get("alert_type")),
                    _text(rule.get("symbol")),
                    _text(rule.get("threshold")),
                    _text(rule.get("expected_value")),
                    _text(rule.get("enabled")),
                    _text(rule.get("created_at")),
                    _dumps(rule),
                ),
            )

    def _save_journal_entries(self, entries: Sequence[JsonValue], *, snapshot_id: str) -> None:
        for item in entries:
            entry = _mapping(item)
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_JOURNAL_ENTRIES} (
                    id, snapshot_id, journal_id, trade_ref, symbol, setup_type,
                    tags_json, created_at, updated_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    snapshot_id,
                    _text(entry.get("journal_id")),
                    _text(entry.get("trade_ref")),
                    _text(entry.get("symbol")),
                    _text(entry.get("setup_type")),
                    json.dumps(entry.get("tags", []), sort_keys=True),
                    _text(entry.get("created_at")),
                    _text(entry.get("updated_at")),
                    _dumps(entry),
                ),
            )

    def _save_chart_drawings(self, drawings: Sequence[JsonValue], *, snapshot_id: str) -> None:
        for item in drawings:
            drawing = _mapping(item)
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_CHART_DRAWINGS} (
                    id, snapshot_id, drawing_id, drawing_type, symbol, timeframe,
                    start_time, start_price, created_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    snapshot_id,
                    _text(drawing.get("drawing_id")),
                    _text(drawing.get("drawing_type")),
                    _text(drawing.get("symbol")),
                    _text(drawing.get("timeframe")),
                    _text(drawing.get("start_time")),
                    _text(drawing.get("start_price")),
                    _text(drawing.get("created_at")),
                    _dumps(drawing),
                ),
            )

    def _save_trader_feedback(self, items: Sequence[JsonValue], *, snapshot_id: str) -> None:
        for item in items:
            feedback = _mapping(item)
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_TRADER_FEEDBACK} (
                    id, snapshot_id, feedback_id, reviewer_role, category,
                    severity, status, summary, recommendation, resolution,
                    created_at, resolved_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    snapshot_id,
                    _text(feedback.get("feedback_id")),
                    _text(feedback.get("reviewer_role")),
                    _text(feedback.get("category")),
                    _text(feedback.get("severity")),
                    _text(feedback.get("status")),
                    _text(feedback.get("summary")),
                    _text(feedback.get("recommendation")),
                    _text(feedback.get("resolution")),
                    _text(feedback.get("created_at")),
                    _text(feedback.get("resolved_at")),
                    _dumps(feedback),
                ),
            )

    def _save_strategy_evaluations(self, evaluations: Sequence[Mapping[str, JsonValue]]) -> None:
        for evaluation in evaluations:
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_STRATEGY_EVALUATIONS} (
                    id, strategy_name, strategy_version, signal_direction,
                    generated_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    _text(evaluation.get("strategy_name")),
                    _text(evaluation.get("strategy_version")),
                    _text(evaluation.get("signal_direction")),
                    _text(evaluation.get("generated_at")),
                    _dumps(evaluation),
                ),
            )

    def _save_risk_decisions(self, decisions: Sequence[Mapping[str, JsonValue]]) -> None:
        for decision in decisions:
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_RISK_DECISIONS} (
                    id, order_intent_id, status, evaluated_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    _optional_text(decision.get("order_intent_id")),
                    _text(decision.get("status")),
                    _text(decision.get("evaluated_at")),
                    _dumps(decision),
                ),
            )

    def _save_simulated_fills(self, fills: Sequence[Mapping[str, JsonValue]]) -> None:
        for fill in fills:
            self._connection.execute(
                f"""
                INSERT OR IGNORE INTO {Tables.PAPER_SIMULATED_FILLS} (
                    id, order_intent_id, side, quantity, price, fee_paid,
                    occurred_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    _text(fill.get("order_intent_id")),
                    _text(fill.get("side")),
                    _text(fill.get("quantity")),
                    _text(fill.get("price")),
                    _text(fill.get("fee_paid")),
                    _text(fill.get("occurred_at")),
                    _dumps(fill),
                ),
            )

    def _save_operator_actions(self, actions: Sequence[Mapping[str, JsonValue]]) -> None:
        for action in actions:
            self._connection.execute(
                f"""
                INSERT INTO {Tables.PAPER_OPERATOR_ACTIONS} (
                    id, event_type, message, reason, occurred_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    _text(action.get("event_type")),
                    _text(action.get("message")),
                    _text(action.get("reason")),
                    _text(action.get("occurred_at")),
                    _dumps(action),
                ),
            )


def _flatten_preferences(preferences: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    flattened: dict[str, JsonValue] = {}
    for key, value in preferences.items():
        if isinstance(value, Mapping):
            for nested_key, nested_value in value.items():
                flattened[f"{key}.{nested_key}"] = nested_value
        else:
            flattened[key] = value
    return flattened


def _loaded_mapping(raw: str) -> Mapping[str, JsonValue]:
    parsed = json.loads(raw)
    if not isinstance(parsed, Mapping):
        raise ValueError("stored paper payload must be a JSON object")
    return parsed


def _mapping(value: JsonValue | object) -> Mapping[str, JsonValue]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: JsonValue | object) -> Sequence[JsonValue]:
    return value if isinstance(value, list) else ()


def _text(value: JsonValue | object) -> str:
    return "not_available" if value is None else str(value)


def _optional_text(value: JsonValue | object) -> str | None:
    return None if value is None else str(value)


def _dumps(payload: Mapping[str, JsonValue]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
