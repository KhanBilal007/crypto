"""Deterministic execution quality calculations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from abtp.data import OrderBookMetrics
from abtp.domain import OrderIntent, OrderSide, OrderStatus
from abtp.execution.engine import ExecutionResult
from abtp.execution.fills import FillSummary
from abtp.execution.latency import ExecutionLatencyRecord, latency_ms

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
TEN_THOUSAND = Decimal("10000")


@dataclass(frozen=True, slots=True)
class ExecutionQualityPolicy:
    """Conservative reporting thresholds for execution quality."""

    max_slippage_bps: Decimal = Decimal("25")
    max_market_impact_bps: Decimal = Decimal("35")
    max_fee_bps: Decimal = Decimal("30")
    min_fill_ratio: Decimal = Decimal("0.95")
    max_ack_latency_ms: int = 1000
    max_fill_latency_ms: int = 5000
    min_quality_score: Decimal = Decimal("0.70")
    policy_version: str = "stage-041.v1"

    def __post_init__(self) -> None:
        if min(self.max_slippage_bps, self.max_market_impact_bps, self.max_fee_bps) < DECIMAL_ZERO:
            raise ValueError("basis point thresholds cannot be negative")
        if not DECIMAL_ZERO <= self.min_fill_ratio <= DECIMAL_ONE:
            raise ValueError("min_fill_ratio must be between 0 and 1")
        if self.max_ack_latency_ms < 0 or self.max_fill_latency_ms < 0:
            raise ValueError("latency thresholds cannot be negative")
        if not DECIMAL_ZERO <= self.min_quality_score <= DECIMAL_ONE:
            raise ValueError("min_quality_score must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    """Stored or fixture execution context used for quality analysis."""

    result: ExecutionResult
    expected_price: Decimal
    latency: ExecutionLatencyRecord
    order_book_metrics: OrderBookMetrics | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.expected_price <= DECIMAL_ZERO:
            raise ValueError("expected_price must be positive")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def intent(self) -> OrderIntent:
        return self.result.intent

    @property
    def fill_summary(self) -> FillSummary | None:
        return self.result.fill_summary


@dataclass(frozen=True, slots=True)
class ExecutionQualityScore:
    """Explainable execution quality score and component values."""

    order_intent_id: str
    status: OrderStatus
    quality_score: Decimal
    fill_ratio: Decimal
    slippage_bps: Decimal
    absolute_slippage_bps: Decimal
    fee_bps: Decimal
    market_impact_bps: Decimal
    acknowledgement_latency_ms: int | None
    fill_latency_ms: int | None
    warning_reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    policy_version: str
    source_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.quality_score <= DECIMAL_ONE:
            raise ValueError("quality_score must be between 0 and 1")
        if self.fill_ratio < DECIMAL_ZERO:
            raise ValueError("fill_ratio cannot be negative")
        if not self.evidence:
            raise ValueError("execution quality score requires evidence")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def acceptable(self) -> bool:
        return not self.rejection_reasons

    def as_dict(self) -> dict[str, object]:
        return {
            "order_intent_id": self.order_intent_id,
            "status": self.status.value,
            "quality_score": str(self.quality_score),
            "fill_ratio": str(self.fill_ratio),
            "slippage_bps": str(self.slippage_bps),
            "absolute_slippage_bps": str(self.absolute_slippage_bps),
            "fee_bps": str(self.fee_bps),
            "market_impact_bps": str(self.market_impact_bps),
            "acknowledgement_latency_ms": self.acknowledgement_latency_ms,
            "fill_latency_ms": self.fill_latency_ms,
            "warning_reasons": list(self.warning_reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "evidence": list(self.evidence),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }


def analyze_execution_quality(
    observation: ExecutionObservation,
    *,
    policy: ExecutionQualityPolicy | None = None,
) -> ExecutionQualityScore:
    """Build deterministic quality metrics from stored execution records."""

    active_policy = policy or ExecutionQualityPolicy()
    fill_summary = observation.fill_summary
    fill_ratio = _fill_ratio(fill_summary)
    average_fill_price = (
        fill_summary.average_fill_price
        if fill_summary is not None and fill_summary.average_fill_price is not None
        else None
    )
    slippage = (
        calculate_slippage_bps(
            expected_price=observation.expected_price,
            fill_price=average_fill_price,
            side=observation.intent.side,
        )
        if average_fill_price is not None
        else DECIMAL_ZERO
    )
    fee_bps = calculate_fee_bps(fill_summary)
    market_impact = estimate_market_impact_bps(
        observation.intent,
        fill_summary=fill_summary,
        order_book_metrics=observation.order_book_metrics,
    )
    ack_ms = latency_ms(observation.latency.acknowledgement_latency)
    fill_ms = latency_ms(observation.latency.fill_latency)
    warnings = _warning_reasons(
        fill_ratio=fill_ratio,
        slippage_bps=slippage,
        fee_bps=fee_bps,
        market_impact_bps=market_impact,
        ack_latency_ms=ack_ms,
        fill_latency_ms=fill_ms,
        policy=active_policy,
    )
    rejections = _rejection_reasons(
        observation,
        fill_ratio=fill_ratio,
        score=_quality_score(
            fill_ratio=fill_ratio,
            slippage_bps=abs(slippage),
            fee_bps=fee_bps,
            market_impact_bps=market_impact,
            ack_latency_ms=ack_ms,
            fill_latency_ms=fill_ms,
            policy=active_policy,
        ),
        warnings=warnings,
        policy=active_policy,
    )
    score = _quality_score(
        fill_ratio=fill_ratio,
        slippage_bps=abs(slippage),
        fee_bps=fee_bps,
        market_impact_bps=market_impact,
        ack_latency_ms=ack_ms,
        fill_latency_ms=fill_ms,
        policy=active_policy,
    )
    return ExecutionQualityScore(
        order_intent_id=str(observation.intent.id),
        status=observation.result.status,
        quality_score=score,
        fill_ratio=fill_ratio,
        slippage_bps=slippage,
        absolute_slippage_bps=abs(slippage),
        fee_bps=fee_bps,
        market_impact_bps=market_impact,
        acknowledgement_latency_ms=ack_ms,
        fill_latency_ms=fill_ms,
        warning_reasons=warnings,
        rejection_reasons=rejections,
        evidence=_evidence(observation, fill_ratio, slippage, fee_bps, market_impact),
        policy_version=active_policy.policy_version,
        source_refs=observation.source_refs,
    )


def calculate_slippage_bps(
    *,
    expected_price: Decimal,
    fill_price: Decimal,
    side: OrderSide,
) -> Decimal:
    """Return adverse slippage in basis points; negative means favorable."""

    if expected_price <= DECIMAL_ZERO or fill_price <= DECIMAL_ZERO:
        raise ValueError("prices must be positive")
    raw = (fill_price - expected_price) / expected_price * TEN_THOUSAND
    if side is OrderSide.SELL:
        raw = -raw
    return raw


def calculate_fee_bps(fill_summary: FillSummary | None) -> Decimal:
    """Return fee impact in basis points of filled notional."""

    if fill_summary is None or fill_summary.average_fill_price is None:
        return DECIMAL_ZERO
    notional = fill_summary.filled_quantity * fill_summary.average_fill_price
    if notional <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return fill_summary.fee_paid / notional * TEN_THOUSAND


def estimate_market_impact_bps(
    intent: OrderIntent,
    *,
    fill_summary: FillSummary | None,
    order_book_metrics: OrderBookMetrics | None,
) -> Decimal:
    """Conservatively estimate market impact from order-book depth and spread."""

    if order_book_metrics is None or fill_summary is None:
        return DECIMAL_ZERO
    relevant_depth = (
        order_book_metrics.ask_depth
        if intent.side is OrderSide.BUY
        else order_book_metrics.bid_depth
    )
    if relevant_depth <= DECIMAL_ZERO:
        return TEN_THOUSAND
    fill_ratio_of_depth = fill_summary.filled_quantity / relevant_depth
    mid_price = (order_book_metrics.best_bid + order_book_metrics.best_ask) / Decimal("2")
    spread_bps = (
        DECIMAL_ZERO
        if mid_price <= DECIMAL_ZERO
        else order_book_metrics.spread / mid_price * TEN_THOUSAND
    )
    return max(DECIMAL_ZERO, spread_bps + fill_ratio_of_depth * Decimal("100"))


def _fill_ratio(fill_summary: FillSummary | None) -> Decimal:
    if fill_summary is None or fill_summary.requested_quantity <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return fill_summary.filled_quantity / fill_summary.requested_quantity


def _warning_reasons(
    *,
    fill_ratio: Decimal,
    slippage_bps: Decimal,
    fee_bps: Decimal,
    market_impact_bps: Decimal,
    ack_latency_ms: int | None,
    fill_latency_ms: int | None,
    policy: ExecutionQualityPolicy,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if fill_ratio < policy.min_fill_ratio:
        warnings.append("partial fill ratio is below threshold")
    if abs(slippage_bps) > policy.max_slippage_bps:
        warnings.append("slippage exceeds threshold")
    if fee_bps > policy.max_fee_bps:
        warnings.append("fee impact exceeds threshold")
    if market_impact_bps > policy.max_market_impact_bps:
        warnings.append("estimated market impact exceeds threshold")
    if ack_latency_ms is None:
        warnings.append("acknowledgement latency is missing")
    elif ack_latency_ms > policy.max_ack_latency_ms:
        warnings.append("acknowledgement latency exceeds threshold")
    if fill_latency_ms is None:
        warnings.append("fill latency is missing")
    elif fill_latency_ms > policy.max_fill_latency_ms:
        warnings.append("fill latency exceeds threshold")
    return tuple(warnings)


def _rejection_reasons(
    observation: ExecutionObservation,
    *,
    fill_ratio: Decimal,
    score: Decimal,
    warnings: tuple[str, ...],
    policy: ExecutionQualityPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if observation.result.status in {
        OrderStatus.FAILED,
        OrderStatus.CANCELED,
        OrderStatus.RISK_REJECTED,
    }:
        reasons.append(f"order status is {observation.result.status.value}")
    if fill_ratio <= DECIMAL_ZERO:
        reasons.append("order has no fills")
    if score < policy.min_quality_score:
        reasons.append("execution quality score is below threshold")
    if len(warnings) >= 3:
        reasons.append("multiple execution quality warnings require review")
    return tuple(dict.fromkeys(reasons))


def _quality_score(
    *,
    fill_ratio: Decimal,
    slippage_bps: Decimal,
    fee_bps: Decimal,
    market_impact_bps: Decimal,
    ack_latency_ms: int | None,
    fill_latency_ms: int | None,
    policy: ExecutionQualityPolicy,
) -> Decimal:
    components = (
        _clamp(fill_ratio),
        DECIMAL_ONE - _ratio(slippage_bps, policy.max_slippage_bps),
        DECIMAL_ONE - _ratio(fee_bps, policy.max_fee_bps),
        DECIMAL_ONE - _ratio(market_impact_bps, policy.max_market_impact_bps),
        _latency_score(ack_latency_ms, policy.max_ack_latency_ms),
        _latency_score(fill_latency_ms, policy.max_fill_latency_ms),
    )
    return _clamp(sum(components, DECIMAL_ZERO) / Decimal(len(components)))


def _latency_score(value_ms: int | None, max_ms: int) -> Decimal:
    if value_ms is None:
        return DECIMAL_ZERO
    if max_ms == 0:
        return DECIMAL_ONE if value_ms == 0 else DECIMAL_ZERO
    return DECIMAL_ONE - _ratio(Decimal(value_ms), Decimal(max_ms))


def _ratio(value: Decimal, cap: Decimal) -> Decimal:
    if cap <= DECIMAL_ZERO:
        return DECIMAL_ONE if value > DECIMAL_ZERO else DECIMAL_ZERO
    return _clamp(value / cap)


def _evidence(
    observation: ExecutionObservation,
    fill_ratio: Decimal,
    slippage_bps: Decimal,
    fee_bps: Decimal,
    market_impact_bps: Decimal,
) -> tuple[str, ...]:
    risk_decision = (
        observation.intent.risk_decision.status.value
        if observation.intent.risk_decision is not None
        else "missing"
    )
    return (
        f"order_intent_id={observation.intent.id}",
        f"status={observation.result.status.value}",
        f"side={observation.intent.side.value}",
        f"expected_price={observation.expected_price}",
        f"fill_ratio={fill_ratio}",
        f"slippage_bps={slippage_bps}",
        f"fee_bps={fee_bps}",
        f"market_impact_bps={market_impact_bps}",
        f"risk_decision={risk_decision}",
    )


def _clamp(value: Decimal) -> Decimal:
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, value))
