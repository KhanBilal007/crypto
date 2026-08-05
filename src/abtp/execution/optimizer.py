"""Advisory institutional execution optimizer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.data.order_book import OrderBookMetrics
from abtp.domain import OrderSide
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
BPS = Decimal("10000")
SCORE_QUANT = Decimal("0.0001")


class ExecutionTimingAction(StrEnum):
    """Advisory timing labels for large or illiquid orders."""

    EXECUTE_REVIEW = "execute_review"
    SPLIT_OVER_TIME = "split_over_time"
    WAIT_FOR_SPREAD = "wait_for_spread"
    MANUAL_REVIEW = "manual_review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class InstitutionalExecutionPolicy:
    """Conservative Stage 067 execution-planning thresholds."""

    max_slice_count: int = 10
    max_participation_rate: Decimal = Decimal("0.20")
    max_expected_cost_bps: Decimal = Decimal("75")
    max_spread_bps: Decimal = Decimal("40")
    fee_bps: Decimal = Decimal("20")
    min_quality_score: Decimal = Decimal("0.50")
    base_slice_delay_seconds: int = 60
    policy_version: str = "stage-067.v1"

    def __post_init__(self) -> None:
        if self.max_slice_count < 1:
            raise ValueError("max_slice_count must be positive")
        if self.base_slice_delay_seconds < 0:
            raise ValueError("base_slice_delay_seconds cannot be negative")
        for name, value in (
            ("max_participation_rate", self.max_participation_rate),
            ("min_quality_score", self.min_quality_score),
        ):
            if not DECIMAL_ZERO < value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_expected_cost_bps < DECIMAL_ZERO or self.max_spread_bps < DECIMAL_ZERO:
            raise ValueError("cost and spread thresholds cannot be negative")
        if self.fee_bps < DECIMAL_ZERO:
            raise ValueError("fee_bps cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ExecutionOptimizationInput:
    """Supplied order and liquidity context for advisory planning."""

    symbol: str
    side: OrderSide
    quantity: Decimal
    reference_price: Decimal
    order_book_metrics: OrderBookMetrics
    volatility_score: Decimal
    urgency_score: Decimal
    quality: DataQualityStatus
    observed_at: datetime
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("execution optimization symbol is required")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", OrderSide(self.side))
        if self.quantity <= DECIMAL_ZERO:
            raise ValueError("quantity must be positive")
        if self.reference_price <= DECIMAL_ZERO:
            raise ValueError("reference_price must be positive")
        for name, value in (
            ("volatility_score", self.volatility_score),
            ("urgency_score", self.urgency_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def relevant_depth(self) -> Decimal:
        return (
            self.order_book_metrics.ask_depth
            if self.side is OrderSide.BUY
            else self.order_book_metrics.bid_depth
        )


@dataclass(frozen=True, slots=True)
class ExecutionPlanSlice:
    """One advisory execution slice."""

    slice_index: int
    quantity: Decimal
    notional: Decimal
    participation_rate: Decimal
    delay_seconds: int
    rationale: str

    def __post_init__(self) -> None:
        if self.slice_index < 1:
            raise ValueError("slice_index must be positive")
        if self.quantity <= DECIMAL_ZERO or self.notional <= DECIMAL_ZERO:
            raise ValueError("slice quantity and notional must be positive")
        if not DECIMAL_ZERO <= self.participation_rate <= DECIMAL_ONE:
            raise ValueError("participation_rate must be between 0 and 1")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        if not self.rationale.strip():
            raise ValueError("slice rationale is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "slice_index": self.slice_index,
            "quantity": str(self.quantity),
            "notional": str(self.notional),
            "participation_rate": str(self.participation_rate),
            "delay_seconds": self.delay_seconds,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class InstitutionalExecutionPlan:
    """Advisory execution plan with no submission authority."""

    generated_at: datetime
    symbol: str
    side: OrderSide
    total_quantity: Decimal
    reference_price: Decimal
    slices: tuple[ExecutionPlanSlice, ...]
    timing_action: ExecutionTimingAction
    expected_cost_bps: Decimal
    slippage_estimate_bps: Decimal
    spread_bps: Decimal
    market_impact_bps: Decimal
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Institutional execution optimization is advisory planning context only.",
        "Execution plans cannot create order intents, risk approvals, or execution.",
        "Smart slices are recommendations and must pass the Risk Management Engine later.",
        "No exchange, router, or live trading calls are made by the optimizer.",
        "No profit or fill quality is guaranteed by execution optimization.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "side", OrderSide(self.side))
        object.__setattr__(self, "timing_action", ExecutionTimingAction(self.timing_action))
        if self.total_quantity <= DECIMAL_ZERO or self.reference_price <= DECIMAL_ZERO:
            raise ValueError("execution plan quantity and reference price must be positive")
        for name, value in (
            ("expected_cost_bps", self.expected_cost_bps),
            ("slippage_estimate_bps", self.slippage_estimate_bps),
            ("spread_bps", self.spread_bps),
            ("market_impact_bps", self.market_impact_bps),
        ):
            if value < DECIMAL_ZERO:
                raise ValueError(f"{name} cannot be negative")
        if not self.reasons:
            raise ValueError("execution plan requires reasons")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("execution plan limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def acceptable_for_execution_review(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional execution optimizer cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional execution optimizer cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional execution optimizer cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "symbol": self.symbol,
            "side": self.side.value,
            "total_quantity": str(self.total_quantity),
            "reference_price": str(self.reference_price),
            "slices": [item.as_dict() for item in self.slices],
            "timing_action": self.timing_action.value,
            "expected_cost_bps": str(self.expected_cost_bps),
            "slippage_estimate_bps": str(self.slippage_estimate_bps),
            "spread_bps": str(self.spread_bps),
            "market_impact_bps": str(self.market_impact_bps),
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "acceptable_for_execution_review": self.acceptable_for_execution_review,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "symbol": self.symbol,
            "side": self.side.value,
            "slice_count": len(self.slices),
            "timing_action": self.timing_action.value,
            "expected_cost_bps": str(self.expected_cost_bps),
            "slippage_estimate_bps": str(self.slippage_estimate_bps),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def optimize_institutional_execution(
    optimization_input: ExecutionOptimizationInput,
    *,
    policy: InstitutionalExecutionPolicy | None = None,
    generated_at: datetime | None = None,
) -> InstitutionalExecutionPlan:
    """Build an advisory execution plan without routing or order creation."""

    active_policy = policy or InstitutionalExecutionPolicy()
    checked_at = normalize_timestamp(generated_at or datetime.now(UTC))
    spread_bps = _spread_bps(optimization_input.order_book_metrics)
    participation_rate = _participation_rate(optimization_input)
    market_impact = _market_impact_bps(participation_rate, optimization_input)
    slippage = _slippage_estimate_bps(spread_bps, market_impact, optimization_input)
    expected_cost = (slippage + active_policy.fee_bps).quantize(SCORE_QUANT)
    rejection_reasons = _rejection_reasons(
        optimization_input,
        spread_bps=spread_bps,
        expected_cost_bps=expected_cost,
        participation_rate=participation_rate,
        policy=active_policy,
    )
    quality = _quality(
        optimization_input,
        rejection_reasons=rejection_reasons,
        spread_bps=spread_bps,
        participation_rate=participation_rate,
        policy=active_policy,
        checked_at=checked_at,
    )
    timing = _timing_action(rejection_reasons, spread_bps, participation_rate, active_policy)
    slices = _slices(
        optimization_input,
        participation_rate=participation_rate,
        policy=active_policy,
        timing_action=timing,
    )
    return InstitutionalExecutionPlan(
        generated_at=checked_at,
        symbol=optimization_input.symbol,
        side=optimization_input.side,
        total_quantity=optimization_input.quantity,
        reference_price=optimization_input.reference_price,
        slices=slices,
        timing_action=timing,
        expected_cost_bps=expected_cost,
        slippage_estimate_bps=slippage,
        spread_bps=spread_bps,
        market_impact_bps=market_impact,
        reasons=_reasons(optimization_input, slices, timing, expected_cost),
        rejection_reasons=rejection_reasons,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=optimization_input.source_refs,
    )


def _spread_bps(metrics: OrderBookMetrics) -> Decimal:
    mid_price = (metrics.best_bid + metrics.best_ask) / Decimal("2")
    if mid_price <= DECIMAL_ZERO:
        return BPS
    return (metrics.spread / mid_price * BPS).quantize(SCORE_QUANT)


def _participation_rate(optimization_input: ExecutionOptimizationInput) -> Decimal:
    if optimization_input.relevant_depth <= DECIMAL_ZERO:
        return DECIMAL_ONE
    return min(
        DECIMAL_ONE, optimization_input.quantity / optimization_input.relevant_depth
    ).quantize(SCORE_QUANT)


def _market_impact_bps(
    participation_rate: Decimal,
    optimization_input: ExecutionOptimizationInput,
) -> Decimal:
    return (
        participation_rate * Decimal("100") * (DECIMAL_ONE + optimization_input.urgency_score)
    ).quantize(SCORE_QUANT)


def _slippage_estimate_bps(
    spread_bps: Decimal,
    market_impact_bps: Decimal,
    optimization_input: ExecutionOptimizationInput,
) -> Decimal:
    volatility_cost = (
        optimization_input.volatility_score * optimization_input.urgency_score * Decimal("50")
    )
    return (spread_bps / Decimal("2") + market_impact_bps + volatility_cost).quantize(SCORE_QUANT)


def _rejection_reasons(
    optimization_input: ExecutionOptimizationInput,
    *,
    spread_bps: Decimal,
    expected_cost_bps: Decimal,
    participation_rate: Decimal,
    policy: InstitutionalExecutionPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if optimization_input.quality.is_rejected:
        reasons.append("execution optimization input quality is rejected")
    if optimization_input.stale:
        reasons.append("execution optimization input is stale")
    if optimization_input.relevant_depth <= DECIMAL_ZERO:
        reasons.append("relevant order-book depth is unavailable")
    if expected_cost_bps > policy.max_expected_cost_bps:
        reasons.append(
            f"expected cost {expected_cost_bps} bps exceeds {policy.max_expected_cost_bps}"
        )
    if spread_bps > policy.max_spread_bps * Decimal("2"):
        reasons.append(f"spread {spread_bps} bps is too wide for planning")
    if participation_rate > DECIMAL_ONE:
        reasons.append("participation rate exceeds available depth")
    return tuple(reasons)


def _quality(
    optimization_input: ExecutionOptimizationInput,
    *,
    rejection_reasons: tuple[str, ...],
    spread_bps: Decimal,
    participation_rate: Decimal,
    policy: InstitutionalExecutionPolicy,
    checked_at: datetime,
) -> DataQualityStatus:
    issues = list(optimization_input.quality.issues)
    for reason in rejection_reasons:
        issues.append(
            DataQualityIssue(
                flag="execution_optimization_rejection",
                severity=DataTrustLevel.REJECTED,
                reason=reason,
            )
        )
    if not rejection_reasons and spread_bps > policy.max_spread_bps:
        issues.append(
            DataQualityIssue(
                flag="wide_spread_execution_plan",
                severity=DataTrustLevel.DEGRADED,
                reason="spread is above the optimization comfort threshold",
            )
        )
    if not rejection_reasons and participation_rate > policy.max_participation_rate:
        issues.append(
            DataQualityIssue(
                flag="large_participation_execution_plan",
                severity=DataTrustLevel.DEGRADED,
                reason="order size requires participation above single-slice threshold",
            )
        )
    if optimization_input.quality.is_rejected or any(
        issue.severity is DataTrustLevel.REJECTED for issue in issues
    ):
        trust_level = DataTrustLevel.REJECTED
    elif optimization_input.quality.is_degraded or issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="execution:institutional_optimizer",
        checked_at=normalize_timestamp(checked_at),
    )


def _timing_action(
    rejection_reasons: tuple[str, ...],
    spread_bps: Decimal,
    participation_rate: Decimal,
    policy: InstitutionalExecutionPolicy,
) -> ExecutionTimingAction:
    if rejection_reasons:
        return ExecutionTimingAction.BLOCKED
    if spread_bps > policy.max_spread_bps:
        return ExecutionTimingAction.WAIT_FOR_SPREAD
    if participation_rate > policy.max_participation_rate:
        return ExecutionTimingAction.SPLIT_OVER_TIME
    return ExecutionTimingAction.EXECUTE_REVIEW


def _slices(
    optimization_input: ExecutionOptimizationInput,
    *,
    participation_rate: Decimal,
    policy: InstitutionalExecutionPolicy,
    timing_action: ExecutionTimingAction,
) -> tuple[ExecutionPlanSlice, ...]:
    if timing_action is ExecutionTimingAction.BLOCKED:
        slice_count = 1
    else:
        raw_count = (
            participation_rate / policy.max_participation_rate
            if policy.max_participation_rate > DECIMAL_ZERO
            else DECIMAL_ONE
        )
        slice_count = max(1, int(raw_count.to_integral_value(rounding=ROUND_CEILING)))
    slice_count = min(policy.max_slice_count, slice_count)
    quantity = (optimization_input.quantity / Decimal(slice_count)).quantize(SCORE_QUANT)
    slices: list[ExecutionPlanSlice] = []
    for index in range(1, slice_count + 1):
        slices.append(
            ExecutionPlanSlice(
                slice_index=index,
                quantity=quantity,
                notional=(quantity * optimization_input.reference_price).quantize(SCORE_QUANT),
                participation_rate=(
                    DECIMAL_ZERO
                    if optimization_input.relevant_depth <= DECIMAL_ZERO
                    else (quantity / optimization_input.relevant_depth).quantize(SCORE_QUANT)
                ),
                delay_seconds=(index - 1) * policy.base_slice_delay_seconds,
                rationale=(
                    "blocked advisory slice for manual review"
                    if timing_action is ExecutionTimingAction.BLOCKED
                    else "slice limits participation and expected market impact"
                ),
            )
        )
    return tuple(slices)


def _reasons(
    optimization_input: ExecutionOptimizationInput,
    slices: tuple[ExecutionPlanSlice, ...],
    timing: ExecutionTimingAction,
    expected_cost: Decimal,
) -> tuple[str, ...]:
    slice_reason = (
        f"{optimization_input.symbol} {optimization_input.side.value} plan "
        f"uses {len(slices)} slices"
    )
    return (
        slice_reason,
        f"timing_action={timing.value}",
        f"expected_cost_bps={expected_cost}",
        "plan is advisory and requires later risk-approved execution workflow",
    )
