"""Deterministic exchange/database reconciliation checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import normalize_timestamp
from abtp.domain import Asset, OrderStatus
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")


class ReconciliationEntity(StrEnum):
    """State families reconciled between database and exchange snapshots."""

    BALANCE = "balance"
    POSITION = "position"
    ORDER = "order"
    FILL = "fill"
    ADAPTER_STATE = "adapter_state"


class MismatchSeverity(StrEnum):
    """Fail-safe severity for reconciliation differences."""

    INFO = "info"
    REVIEW = "review"
    BLOCKER = "blocker"


@dataclass(frozen=True, slots=True)
class BalanceRecord:
    """Non-secret balance state from database or exchange snapshots."""

    asset: Asset
    total: Decimal
    available: Decimal | None = None
    held: Decimal = DECIMAL_ZERO
    source_ref: str = "balance:unknown"

    def __post_init__(self) -> None:
        if self.total < DECIMAL_ZERO:
            raise ValueError("balance total cannot be negative")
        if self.available is not None and self.available < DECIMAL_ZERO:
            raise ValueError("balance available cannot be negative")
        if self.held < DECIMAL_ZERO:
            raise ValueError("balance held cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("balance source_ref is required")

    @property
    def key(self) -> str:
        return self.asset.symbol

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "asset": self.asset.symbol,
            "total": str(self.total),
            "available": str(self.available) if self.available is not None else None,
            "held": str(self.held),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class PositionRecord:
    """Non-secret position state from database or exchange snapshots."""

    asset: Asset
    quantity: Decimal
    valuation: Decimal = DECIMAL_ZERO
    source_ref: str = "position:unknown"

    def __post_init__(self) -> None:
        if self.quantity < DECIMAL_ZERO:
            raise ValueError("position quantity cannot be negative")
        if self.valuation < DECIMAL_ZERO:
            raise ValueError("position valuation cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("position source_ref is required")

    @property
    def key(self) -> str:
        return self.asset.symbol

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "asset": self.asset.symbol,
            "quantity": str(self.quantity),
            "valuation": str(self.valuation),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class OrderRecord:
    """Order lifecycle state without exchange credentials or raw API payloads."""

    order_intent_id: str
    status: OrderStatus
    filled_quantity: Decimal = DECIMAL_ZERO
    exchange_order_id: str | None = None
    source_ref: str = "order:unknown"

    def __post_init__(self) -> None:
        if not self.order_intent_id.strip():
            raise ValueError("order_intent_id is required")
        if self.exchange_order_id is not None and not self.exchange_order_id.strip():
            raise ValueError("exchange_order_id cannot be blank")
        if self.filled_quantity < DECIMAL_ZERO:
            raise ValueError("filled_quantity cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("order source_ref is required")

    @property
    def key(self) -> str:
        return self.exchange_order_id or self.order_intent_id

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "order_intent_id": self.order_intent_id,
            "exchange_order_id": self.exchange_order_id,
            "status": self.status.value,
            "filled_quantity": str(self.filled_quantity),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class FillRecord:
    """Aggregated fill state used for reconciliation."""

    order_intent_id: str
    exchange_order_id: str
    filled_quantity: Decimal
    average_fill_price: Decimal
    fee_paid: Decimal = DECIMAL_ZERO
    source_ref: str = "fill:unknown"

    def __post_init__(self) -> None:
        if not self.order_intent_id.strip():
            raise ValueError("order_intent_id is required")
        if not self.exchange_order_id.strip():
            raise ValueError("exchange_order_id is required")
        if self.filled_quantity < DECIMAL_ZERO:
            raise ValueError("filled_quantity cannot be negative")
        if self.average_fill_price <= DECIMAL_ZERO:
            raise ValueError("average_fill_price must be positive")
        if self.fee_paid < DECIMAL_ZERO:
            raise ValueError("fee_paid cannot be negative")
        if not self.source_ref.strip():
            raise ValueError("fill source_ref is required")

    @property
    def key(self) -> str:
        return f"{self.exchange_order_id}:{self.order_intent_id}"

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "order_intent_id": self.order_intent_id,
            "exchange_order_id": self.exchange_order_id,
            "filled_quantity": str(self.filled_quantity),
            "average_fill_price": str(self.average_fill_price),
            "fee_paid": str(self.fee_paid),
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationSnapshot:
    """Database or adapter-provided state snapshot for reconciliation."""

    source_name: str
    captured_at: datetime
    balances: tuple[BalanceRecord, ...] = ()
    positions: tuple[PositionRecord, ...] = ()
    orders: tuple[OrderRecord, ...] = ()
    fills: tuple[FillRecord, ...] = ()
    adapter_stale: bool = False
    outage: bool = False
    restart_marker: str | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ValueError("snapshot source_name is required")
        object.__setattr__(self, "captured_at", normalize_timestamp(self.captured_at))
        if self.restart_marker is not None and not self.restart_marker.strip():
            raise ValueError("restart_marker cannot be blank")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "captured_at": self.captured_at.isoformat(),
            "balances": [record.as_dict() for record in self.balances],
            "positions": [record.as_dict() for record in self.positions],
            "orders": [record.as_dict() for record in self.orders],
            "fills": [record.as_dict() for record in self.fills],
            "adapter_stale": self.adapter_stale,
            "outage": self.outage,
            "restart_marker": self.restart_marker,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationTolerance:
    """Allowed deterministic differences before review/block recommendations."""

    balance_quantity: Decimal = Decimal("0.00000001")
    position_quantity: Decimal = Decimal("0.00000001")
    fill_quantity: Decimal = Decimal("0.00000001")
    valuation: Decimal = Decimal("0.01")

    def __post_init__(self) -> None:
        for name, value in (
            ("balance_quantity", self.balance_quantity),
            ("position_quantity", self.position_quantity),
            ("fill_quantity", self.fill_quantity),
            ("valuation", self.valuation),
        ):
            if value < DECIMAL_ZERO:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class ReconciliationMismatch:
    """One explainable database/exchange mismatch."""

    entity: ReconciliationEntity
    key: str
    expected: JsonValue
    observed: JsonValue
    difference: Decimal | None
    severity: MismatchSeverity
    reason: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("mismatch key is required")
        if not self.reason.strip():
            raise ValueError("mismatch reason is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def blocks_continuation(self) -> bool:
        return self.severity is MismatchSeverity.BLOCKER

    def as_dict(self) -> dict[str, object]:
        return {
            "entity": self.entity.value,
            "key": self.key,
            "expected": self.expected,
            "observed": self.observed,
            "difference": str(self.difference) if self.difference is not None else None,
            "severity": self.severity.value,
            "reason": self.reason,
            "source_refs": dict(self.source_refs),
        }


def compare_snapshots(
    database: ReconciliationSnapshot,
    exchange: ReconciliationSnapshot,
    *,
    tolerance: ReconciliationTolerance | None = None,
) -> tuple[ReconciliationMismatch, ...]:
    """Compare stored database state with adapter-provided exchange state."""

    active_tolerance = tolerance or ReconciliationTolerance()
    mismatches: list[ReconciliationMismatch] = []
    mismatches.extend(_adapter_state_mismatches(exchange))
    mismatches.extend(_compare_balances(database, exchange, active_tolerance))
    mismatches.extend(_compare_positions(database, exchange, active_tolerance))
    mismatches.extend(_compare_orders(database, exchange))
    mismatches.extend(_compare_fills(database, exchange, active_tolerance))
    return tuple(mismatches)


def _adapter_state_mismatches(
    exchange: ReconciliationSnapshot,
) -> tuple[ReconciliationMismatch, ...]:
    mismatches: list[ReconciliationMismatch] = []
    if exchange.outage:
        mismatches.append(
            _mismatch(
                ReconciliationEntity.ADAPTER_STATE,
                "exchange_outage",
                expected="available",
                observed="outage",
                difference=None,
                severity=MismatchSeverity.BLOCKER,
                reason="exchange adapter snapshot reports an outage",
                source_refs=exchange.source_refs,
            )
        )
    if exchange.adapter_stale:
        mismatches.append(
            _mismatch(
                ReconciliationEntity.ADAPTER_STATE,
                "stale_adapter_state",
                expected="fresh",
                observed="stale",
                difference=None,
                severity=MismatchSeverity.BLOCKER,
                reason="exchange adapter snapshot is stale",
                source_refs=exchange.source_refs,
            )
        )
    return tuple(mismatches)


def _compare_balances(
    database: ReconciliationSnapshot,
    exchange: ReconciliationSnapshot,
    tolerance: ReconciliationTolerance,
) -> tuple[ReconciliationMismatch, ...]:
    database_by_key = {record.key: record for record in database.balances}
    exchange_by_key = {record.key: record for record in exchange.balances}
    mismatches: list[ReconciliationMismatch] = []
    for key in sorted(set(database_by_key) | set(exchange_by_key)):
        db_record = database_by_key.get(key)
        ex_record = exchange_by_key.get(key)
        if db_record is None or ex_record is None:
            mismatches.append(
                _missing_mismatch(
                    ReconciliationEntity.BALANCE,
                    key,
                    db_record.as_dict() if db_record else None,
                    ex_record.as_dict() if ex_record else None,
                    "balance exists on one side only",
                    {**database.source_refs, **exchange.source_refs},
                )
            )
            continue
        difference = abs(db_record.total - ex_record.total)
        if difference > tolerance.balance_quantity:
            mismatches.append(
                _mismatch(
                    ReconciliationEntity.BALANCE,
                    key,
                    expected=str(db_record.total),
                    observed=str(ex_record.total),
                    difference=difference,
                    severity=MismatchSeverity.BLOCKER,
                    reason="database and exchange balance totals differ",
                    source_refs={
                        "database_balance": db_record.source_ref,
                        "exchange_balance": ex_record.source_ref,
                    },
                )
            )
    return tuple(mismatches)


def _compare_positions(
    database: ReconciliationSnapshot,
    exchange: ReconciliationSnapshot,
    tolerance: ReconciliationTolerance,
) -> tuple[ReconciliationMismatch, ...]:
    database_by_key = {record.key: record for record in database.positions}
    exchange_by_key = {record.key: record for record in exchange.positions}
    mismatches: list[ReconciliationMismatch] = []
    for key in sorted(set(database_by_key) | set(exchange_by_key)):
        db_record = database_by_key.get(key)
        ex_record = exchange_by_key.get(key)
        if db_record is None or ex_record is None:
            mismatches.append(
                _missing_mismatch(
                    ReconciliationEntity.POSITION,
                    key,
                    db_record.as_dict() if db_record else None,
                    ex_record.as_dict() if ex_record else None,
                    "position exists on one side only",
                    {**database.source_refs, **exchange.source_refs},
                )
            )
            continue
        quantity_difference = abs(db_record.quantity - ex_record.quantity)
        valuation_difference = abs(db_record.valuation - ex_record.valuation)
        if (
            quantity_difference > tolerance.position_quantity
            or valuation_difference > tolerance.valuation
        ):
            mismatches.append(
                _mismatch(
                    ReconciliationEntity.POSITION,
                    key,
                    expected=db_record.as_dict(),
                    observed=ex_record.as_dict(),
                    difference=max(quantity_difference, valuation_difference),
                    severity=MismatchSeverity.BLOCKER,
                    reason="database and exchange position state differs",
                    source_refs={
                        "database_position": db_record.source_ref,
                        "exchange_position": ex_record.source_ref,
                    },
                )
            )
    return tuple(mismatches)


def _compare_orders(
    database: ReconciliationSnapshot,
    exchange: ReconciliationSnapshot,
) -> tuple[ReconciliationMismatch, ...]:
    database_by_key = {record.key: record for record in database.orders}
    exchange_by_key = {record.key: record for record in exchange.orders}
    mismatches: list[ReconciliationMismatch] = []
    for key in sorted(set(database_by_key) | set(exchange_by_key)):
        db_record = database_by_key.get(key)
        ex_record = exchange_by_key.get(key)
        if db_record is None or ex_record is None:
            mismatches.append(
                _missing_mismatch(
                    ReconciliationEntity.ORDER,
                    key,
                    db_record.as_dict() if db_record else None,
                    ex_record.as_dict() if ex_record else None,
                    "order exists on one side only",
                    {**database.source_refs, **exchange.source_refs},
                )
            )
            continue
        if db_record.status is not ex_record.status:
            mismatches.append(
                _mismatch(
                    ReconciliationEntity.ORDER,
                    key,
                    expected=db_record.status.value,
                    observed=ex_record.status.value,
                    difference=None,
                    severity=MismatchSeverity.BLOCKER,
                    reason="database and exchange order status differs",
                    source_refs={
                        "database_order": db_record.source_ref,
                        "exchange_order": ex_record.source_ref,
                    },
                )
            )
    return tuple(mismatches)


def _compare_fills(
    database: ReconciliationSnapshot,
    exchange: ReconciliationSnapshot,
    tolerance: ReconciliationTolerance,
) -> tuple[ReconciliationMismatch, ...]:
    database_by_key = {record.key: record for record in database.fills}
    exchange_by_key = {record.key: record for record in exchange.fills}
    mismatches: list[ReconciliationMismatch] = []
    for key in sorted(set(database_by_key) | set(exchange_by_key)):
        db_record = database_by_key.get(key)
        ex_record = exchange_by_key.get(key)
        if db_record is None or ex_record is None:
            mismatches.append(
                _missing_mismatch(
                    ReconciliationEntity.FILL,
                    key,
                    db_record.as_dict() if db_record else None,
                    ex_record.as_dict() if ex_record else None,
                    "fill exists on one side only",
                    {**database.source_refs, **exchange.source_refs},
                )
            )
            continue
        difference = abs(db_record.filled_quantity - ex_record.filled_quantity)
        if difference > tolerance.fill_quantity:
            mismatches.append(
                _mismatch(
                    ReconciliationEntity.FILL,
                    key,
                    expected=db_record.as_dict(),
                    observed=ex_record.as_dict(),
                    difference=difference,
                    severity=MismatchSeverity.BLOCKER,
                    reason="database and exchange fill quantity differs",
                    source_refs={
                        "database_fill": db_record.source_ref,
                        "exchange_fill": ex_record.source_ref,
                    },
                )
            )
    return tuple(mismatches)


def _missing_mismatch(
    entity: ReconciliationEntity,
    key: str,
    expected: JsonValue,
    observed: JsonValue,
    reason: str,
    source_refs: Mapping[str, str],
) -> ReconciliationMismatch:
    return _mismatch(
        entity,
        key,
        expected=expected,
        observed=observed,
        difference=None,
        severity=MismatchSeverity.BLOCKER,
        reason=reason,
        source_refs=source_refs,
    )


def _mismatch(
    entity: ReconciliationEntity,
    key: str,
    *,
    expected: JsonValue,
    observed: JsonValue,
    difference: Decimal | None,
    severity: MismatchSeverity,
    reason: str,
    source_refs: Mapping[str, str],
) -> ReconciliationMismatch:
    return ReconciliationMismatch(
        entity=entity,
        key=key,
        expected=expected,
        observed=observed,
        difference=difference,
        severity=severity,
        reason=reason,
        source_refs=source_refs,
    )
