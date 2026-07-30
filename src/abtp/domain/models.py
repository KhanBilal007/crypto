"""Serializable ABTP domain models.

The models in this module are immutable, validation-oriented data contracts.
They intentionally do not know about databases, exchange clients, model
runtime, or order execution implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self
from uuid import UUID, uuid4

from abtp.domain.enums import (
    AuditEventType,
    MarketType,
    OrderSide,
    OrderStatus,
    OrderType,
    PredictionHorizon,
    RiskDecisionStatus,
    SignalDirection,
)

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


def _decimal(value: Decimal | str | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")
    return cleaned


def _model_to_json(value: Any) -> JsonValue:
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _model_to_json(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple | list | frozenset):
        return [_model_to_json(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _model_to_json(item) for key, item in value.items()}
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


@dataclass(frozen=True, slots=True)
class SerializableModel:
    """Mixin for JSON-compatible snapshots."""

    def to_json_dict(self) -> JsonObject:
        return {field.name: _model_to_json(getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class Asset(SerializableModel):
    """A tradeable asset symbol such as BTC or USDT."""

    symbol: str
    name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", _require_text(self.symbol, "asset symbol").upper())

    @classmethod
    def from_json_dict(cls, data: Mapping[str, JsonValue]) -> Self:
        raw_name = data.get("name")
        return cls(symbol=str(data["symbol"]), name=str(raw_name) if raw_name else None)


@dataclass(frozen=True, slots=True)
class AssetPair(SerializableModel):
    """Base and quote asset pair."""

    base: Asset
    quote: Asset

    @property
    def symbol(self) -> str:
        return f"{self.base.symbol}/{self.quote.symbol}"

    @classmethod
    def from_json_dict(cls, data: Mapping[str, JsonValue]) -> Self:
        return cls(
            base=Asset.from_json_dict(_as_mapping(data["base"])),
            quote=Asset.from_json_dict(_as_mapping(data["quote"])),
        )


TradingPair = AssetPair


@dataclass(frozen=True, slots=True)
class Exchange(SerializableModel):
    """Exchange identity without credentials or API behavior."""

    name: str
    market_types: frozenset[MarketType] = frozenset({MarketType.SPOT})

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "exchange name").lower())
        unsupported = self.market_types - {MarketType.SPOT}
        if unsupported:
            raise ValueError("Stage 007 supports spot vocabulary only")

    @classmethod
    def from_json_dict(cls, data: Mapping[str, JsonValue]) -> Self:
        market_values = data.get("market_types") or [MarketType.SPOT.value]
        if not isinstance(market_values, list):
            raise ValueError("exchange market_types must be a list")
        return cls(
            name=str(data["name"]),
            market_types=frozenset(MarketType(str(value)) for value in market_values),
        )


@dataclass(frozen=True, slots=True)
class Candle(SerializableModel):
    """OHLCV data for a fixed interval."""

    exchange: Exchange
    pair: AssetPair
    interval: str
    opened_at: datetime
    closed_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.closed_at <= self.opened_at:
            raise ValueError("candle closed_at must be after opened_at")
        if min(self.open, self.high, self.low, self.close, self.volume) < Decimal("0"):
            raise ValueError("candle prices and volume must be non-negative")
        object.__setattr__(self, "interval", _require_text(self.interval, "candle interval"))

    @classmethod
    def from_json_dict(cls, data: Mapping[str, JsonValue]) -> Self:
        return cls(
            exchange=Exchange.from_json_dict(_as_mapping(data["exchange"])),
            pair=AssetPair.from_json_dict(_as_mapping(data["pair"])),
            interval=str(data["interval"]),
            opened_at=datetime.fromisoformat(str(data["opened_at"])),
            closed_at=datetime.fromisoformat(str(data["closed_at"])),
            open=_decimal(str(data["open"])),
            high=_decimal(str(data["high"])),
            low=_decimal(str(data["low"])),
            close=_decimal(str(data["close"])),
            volume=_decimal(str(data["volume"])),
        )


@dataclass(frozen=True, slots=True)
class OrderBookLevel(SerializableModel):
    """Single price level in an order book."""

    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        if self.price <= Decimal("0"):
            raise ValueError("order book price must be positive")
        if self.quantity < Decimal("0"):
            raise ValueError("order book quantity must be non-negative")


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot(SerializableModel):
    """Order book snapshot for one pair and exchange."""

    exchange: Exchange
    pair: AssetPair
    captured_at: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    source_ref: str

    def __post_init__(self) -> None:
        if not self.bids or not self.asks:
            raise ValueError("order book requires at least one bid and one ask")
        object.__setattr__(self, "source_ref", _require_text(self.source_ref, "source_ref"))


@dataclass(frozen=True, slots=True)
class Trade(SerializableModel):
    """Observed market trade."""

    exchange: Exchange
    pair: AssetPair
    traded_at: datetime
    price: Decimal
    quantity: Decimal
    side: OrderSide
    trade_id: str

    def __post_init__(self) -> None:
        if self.price <= Decimal("0"):
            raise ValueError("trade price must be positive")
        if self.quantity <= Decimal("0"):
            raise ValueError("trade quantity must be positive")
        object.__setattr__(self, "trade_id", _require_text(self.trade_id, "trade_id"))


@dataclass(frozen=True, slots=True)
class FeatureVector(SerializableModel):
    """Features produced from stored market inputs."""

    pair: AssetPair
    generated_at: datetime
    values: Mapping[str, Decimal]
    inputs_ref: str
    feature_version: str

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("feature vector values are required")
        object.__setattr__(self, "inputs_ref", _require_text(self.inputs_ref, "inputs_ref"))
        object.__setattr__(
            self, "feature_version", _require_text(self.feature_version, "feature_version")
        )


@dataclass(frozen=True, slots=True)
class Prediction(SerializableModel):
    """Prediction emitted by a future AI module."""

    pair: AssetPair
    generated_at: datetime
    horizon: PredictionHorizon
    expected_return: Decimal
    confidence: Decimal
    model_version: str
    features_ref: str
    rationale: str

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("prediction confidence must be between 0 and 1")
        object.__setattr__(
            self, "model_version", _require_text(self.model_version, "model_version")
        )
        object.__setattr__(self, "features_ref", _require_text(self.features_ref, "features_ref"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))


@dataclass(frozen=True, slots=True)
class Signal(SerializableModel):
    """Explainable generated signal."""

    source: str
    pair: AssetPair
    generated_at: datetime
    direction: SignalDirection
    confidence: Decimal
    inputs_ref: str
    rationale: str
    prediction_ref: str | None = None

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("signal confidence must be between 0 and 1")
        object.__setattr__(self, "source", _require_text(self.source, "signal source"))
        object.__setattr__(self, "inputs_ref", _require_text(self.inputs_ref, "inputs_ref"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))


@dataclass(frozen=True, slots=True)
class RiskCheck(SerializableModel):
    """Single risk policy check."""

    name: str
    passed: bool
    reason: str
    observed_value: Decimal | None = None
    limit_value: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "risk check name"))
        object.__setattr__(self, "reason", _require_text(self.reason, "risk check reason"))


@dataclass(frozen=True, slots=True)
class RiskDecision(SerializableModel):
    """Risk Management Engine verdict for an order intent."""

    order_intent_id: UUID
    status: RiskDecisionStatus
    checks: tuple[RiskCheck, ...]
    evaluated_at: datetime
    policy_version: str
    rationale: str
    max_position_size: Decimal = Decimal("0")
    stop_loss_required: bool = True
    kill_switch_active: bool = False
    reasons: tuple[str, ...] = ()
    allow: bool | None = None
    reject: bool | None = None

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValueError("risk decision requires at least one check")
        if self.status is RiskDecisionStatus.APPROVED and not all(
            check.passed for check in self.checks
        ):
            raise ValueError("approved risk decisions require all checks to pass")
        if self.kill_switch_active and self.status is RiskDecisionStatus.APPROVED:
            raise ValueError("kill-switch-active decisions cannot be approved")
        if self.max_position_size < Decimal("0"):
            raise ValueError("max_position_size must be non-negative")
        expected_allow = self.status is RiskDecisionStatus.APPROVED and not self.kill_switch_active
        expected_reject = not expected_allow
        if self.allow is not None and self.allow is not expected_allow:
            raise ValueError("risk decision allow flag must match status and kill-switch state")
        if self.reject is not None and self.reject is not expected_reject:
            raise ValueError("risk decision reject flag must match status and kill-switch state")
        object.__setattr__(self, "allow", expected_allow)
        object.__setattr__(self, "reject", expected_reject)
        object.__setattr__(
            self, "policy_version", _require_text(self.policy_version, "policy_version")
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        if not self.reasons:
            object.__setattr__(self, "reasons", tuple(check.reason for check in self.checks))

    @property
    def allowed(self) -> bool:
        return bool(self.allow)

    @property
    def rejected(self) -> bool:
        return bool(self.reject)


@dataclass(frozen=True, slots=True)
class OrderIntent(SerializableModel):
    """Proposed order before execution."""

    pair: AssetPair
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    created_at: datetime
    signal: Signal
    risk_decision: RiskDecision | None = None
    limit_price: Decimal | None = None
    id: UUID = field(default_factory=uuid4)
    status: OrderStatus = OrderStatus.CREATED
    client_order_ref: str | None = None

    def __post_init__(self) -> None:
        if self.quantity <= Decimal("0"):
            raise ValueError("order quantity must be positive")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit orders require limit_price")
        if self.limit_price is not None and self.limit_price <= Decimal("0"):
            raise ValueError("limit_price must be positive")
        if self.risk_decision is not None and self.risk_decision.order_intent_id != self.id:
            raise ValueError("risk decision must reference this order intent")


@dataclass(frozen=True, slots=True)
class PortfolioPosition(SerializableModel):
    """Position quantity and valuation input for one asset."""

    asset: Asset
    quantity: Decimal
    valuation_quote: Asset
    valuation: Decimal

    def __post_init__(self) -> None:
        if self.quantity < Decimal("0"):
            raise ValueError("portfolio quantity must be non-negative")
        if self.valuation < Decimal("0"):
            raise ValueError("portfolio valuation must be non-negative")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot(SerializableModel):
    """Portfolio state captured for explainability."""

    captured_at: datetime
    positions: tuple[PortfolioPosition, ...]
    source_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_ref", _require_text(self.source_ref, "source_ref"))


@dataclass(frozen=True, slots=True)
class AuditEvent(SerializableModel):
    """Immutable audit record for traceable decisions."""

    event_type: AuditEventType | str
    occurred_at: datetime
    payload: Mapping[str, str]
    id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    correlation_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.payload:
            raise ValueError("audit event payload is required")


def _as_mapping(value: JsonValue) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError("expected object mapping")
    return value
