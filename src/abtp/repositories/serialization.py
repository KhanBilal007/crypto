"""Serialization helpers shared by SQLite repositories."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from abtp.domain import (
    Asset,
    AssetPair,
    AuditEvent,
    AuditEventType,
    Candle,
    Exchange,
    FeatureVector,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioPosition,
    PortfolioSnapshot,
    Prediction,
    PredictionHorizon,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
    Trade,
)
from abtp.domain.models import JsonObject, JsonValue, SerializableModel

_SECRET_KEY_PARTS = ("secret", "api_key", "password", "passphrase", "token", "credential")


def pair_symbol(pair: AssetPair) -> str:
    return pair.symbol


def dumps_model(model: SerializableModel) -> str:
    payload = model.to_json_dict()
    ensure_no_secret_keys(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def dumps_json(payload: Mapping[str, JsonValue]) -> str:
    ensure_no_secret_keys(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def loads_object(raw: str) -> Mapping[str, JsonValue]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("stored payload must be a JSON object")
    return cast(Mapping[str, JsonValue], data)


def ensure_no_secret_keys(payload: Mapping[str, JsonValue]) -> None:
    for key, value in payload.items():
        lowered = key.lower()
        if any(part in lowered for part in _SECRET_KEY_PARTS):
            raise ValueError(f"secret-like key is not allowed in database payloads: {key}")
        if isinstance(value, dict):
            ensure_no_secret_keys(cast(Mapping[str, JsonValue], value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    ensure_no_secret_keys(cast(Mapping[str, JsonValue], item))


def candle_from_payload(raw: str) -> Candle:
    return Candle.from_json_dict(loads_object(raw))


def order_book_from_payload(raw: str) -> OrderBookSnapshot:
    data = loads_object(raw)
    return OrderBookSnapshot(
        exchange=Exchange.from_json_dict(_object(data["exchange"])),
        pair=AssetPair.from_json_dict(_object(data["pair"])),
        captured_at=_datetime(data["captured_at"]),
        bids=tuple(_order_book_level(item) for item in _list(data["bids"])),
        asks=tuple(_order_book_level(item) for item in _list(data["asks"])),
        source_ref=_text(data["source_ref"]),
    )


def trade_from_payload(raw: str) -> Trade:
    data = loads_object(raw)
    return Trade(
        exchange=Exchange.from_json_dict(_object(data["exchange"])),
        pair=AssetPair.from_json_dict(_object(data["pair"])),
        traded_at=_datetime(data["traded_at"]),
        price=_decimal(data["price"]),
        quantity=_decimal(data["quantity"]),
        side=OrderSide(_text(data["side"])),
        trade_id=_text(data["trade_id"]),
    )


def feature_vector_from_payload(raw: str) -> FeatureVector:
    data = loads_object(raw)
    values = {key: _decimal(value) for key, value in _object(data["values"]).items()}
    return FeatureVector(
        pair=AssetPair.from_json_dict(_object(data["pair"])),
        generated_at=_datetime(data["generated_at"]),
        values=values,
        inputs_ref=_text(data["inputs_ref"]),
        feature_version=_text(data["feature_version"]),
    )


def prediction_from_payload(raw: str) -> Prediction:
    data = loads_object(raw)
    return Prediction(
        pair=AssetPair.from_json_dict(_object(data["pair"])),
        generated_at=_datetime(data["generated_at"]),
        horizon=PredictionHorizon(_text(data["horizon"])),
        expected_return=_decimal(data["expected_return"]),
        confidence=_decimal(data["confidence"]),
        model_version=_text(data["model_version"]),
        features_ref=_text(data["features_ref"]),
        rationale=_text(data["rationale"]),
    )


def signal_from_payload(raw: str) -> Signal:
    return _signal_from_object(loads_object(raw))


def risk_decision_from_payload(raw: str) -> RiskDecision:
    return _risk_decision_from_object(loads_object(raw))


def order_intent_from_payload(raw: str) -> OrderIntent:
    data = loads_object(raw)
    risk_raw = data.get("risk_decision")
    return OrderIntent(
        pair=AssetPair.from_json_dict(_object(data["pair"])),
        side=OrderSide(_text(data["side"])),
        order_type=OrderType(_text(data["order_type"])),
        quantity=_decimal(data["quantity"]),
        created_at=_datetime(data["created_at"]),
        signal=_signal_from_object(_object(data["signal"])),
        risk_decision=_risk_decision_from_object(_object(risk_raw)) if risk_raw else None,
        limit_price=_decimal(data["limit_price"]) if data.get("limit_price") else None,
        id=UUID(_text(data["id"])),
        status=OrderStatus(_text(data["status"])),
        client_order_ref=_optional_text(data.get("client_order_ref")),
    )


def portfolio_snapshot_from_payload(raw: str) -> PortfolioSnapshot:
    data = loads_object(raw)
    return PortfolioSnapshot(
        captured_at=_datetime(data["captured_at"]),
        positions=tuple(_portfolio_position(item) for item in _list(data["positions"])),
        source_ref=_text(data["source_ref"]),
    )


def audit_event_from_payload(raw: str) -> AuditEvent:
    data = loads_object(raw)
    event_value = data["event_type"]
    try:
        event_type: AuditEventType | str = AuditEventType(_text(event_value))
    except ValueError:
        event_type = _text(event_value)
    return AuditEvent(
        event_type=event_type,
        occurred_at=_datetime(data["occurred_at"]),
        payload={key: _text(value) for key, value in _object(data["payload"]).items()},
        id=UUID(_text(data["id"])),
        causation_id=_optional_uuid(data.get("causation_id")),
        correlation_id=_optional_uuid(data.get("correlation_id")),
    )


def lifecycle_payload(
    *,
    order_intent_id: UUID,
    status: OrderStatus,
    occurred_at: datetime,
    realized_pnl: Decimal | None,
    unrealized_pnl: Decimal | None,
    payload: Mapping[str, JsonValue],
) -> JsonObject:
    result: JsonObject = {
        "order_intent_id": str(order_intent_id),
        "status": status.value,
        "occurred_at": occurred_at.isoformat(),
        "realized_pnl": str(realized_pnl) if realized_pnl is not None else None,
        "unrealized_pnl": str(unrealized_pnl) if unrealized_pnl is not None else None,
        "payload": dict(payload),
    }
    ensure_no_secret_keys(result)
    return result


def _signal_from_object(data: Mapping[str, JsonValue]) -> Signal:
    return Signal(
        source=_text(data["source"]),
        pair=AssetPair.from_json_dict(_object(data["pair"])),
        generated_at=_datetime(data["generated_at"]),
        direction=SignalDirection(_text(data["direction"])),
        confidence=_decimal(data["confidence"]),
        inputs_ref=_text(data["inputs_ref"]),
        rationale=_text(data["rationale"]),
        prediction_ref=_optional_text(data.get("prediction_ref")),
    )


def _risk_decision_from_object(data: Mapping[str, JsonValue]) -> RiskDecision:
    return RiskDecision(
        order_intent_id=UUID(_text(data["order_intent_id"])),
        status=RiskDecisionStatus(_text(data["status"])),
        checks=tuple(_risk_check(item) for item in _list(data["checks"])),
        evaluated_at=_datetime(data["evaluated_at"]),
        policy_version=_text(data["policy_version"]),
        rationale=_text(data["rationale"]),
        max_position_size=_decimal(data["max_position_size"]),
        stop_loss_required=_bool(data["stop_loss_required"]),
        kill_switch_active=_bool(data["kill_switch_active"]),
        reasons=tuple(_text(item) for item in _list(data["reasons"])),
        allow=_bool(data["allow"]),
        reject=_bool(data["reject"]),
    )


def _risk_check(value: JsonValue) -> RiskCheck:
    data = _object(value)
    return RiskCheck(
        name=_text(data["name"]),
        passed=_bool(data["passed"]),
        reason=_text(data["reason"]),
        observed_value=_decimal(data["observed_value"]) if data.get("observed_value") else None,
        limit_value=_decimal(data["limit_value"]) if data.get("limit_value") else None,
    )


def _order_book_level(value: JsonValue) -> OrderBookLevel:
    data = _object(value)
    return OrderBookLevel(price=_decimal(data["price"]), quantity=_decimal(data["quantity"]))


def _portfolio_position(value: JsonValue) -> PortfolioPosition:
    data = _object(value)
    return PortfolioPosition(
        asset=Asset.from_json_dict(_object(data["asset"])),
        quantity=_decimal(data["quantity"]),
        valuation_quote=Asset.from_json_dict(_object(data["valuation_quote"])),
        valuation=_decimal(data["valuation"]),
    )


def _object(value: JsonValue | None) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return cast(Mapping[str, JsonValue], value)


def _list(value: JsonValue | None) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ValueError("expected JSON list")
    return value


def _text(value: JsonValue) -> str:
    if value is None:
        raise ValueError("expected text value")
    return str(value)


def _optional_text(value: JsonValue | None) -> str | None:
    return str(value) if value is not None else None


def _optional_uuid(value: JsonValue | None) -> UUID | None:
    return UUID(str(value)) if value else None


def _datetime(value: JsonValue) -> datetime:
    return datetime.fromisoformat(_text(value))


def _decimal(value: JsonValue) -> Decimal:
    return Decimal(_text(value))


def _bool(value: JsonValue) -> bool:
    if not isinstance(value, bool):
        raise ValueError("expected boolean value")
    return value
