"""Pure risk rules for the mandatory Risk Management Engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from abtp.data import DataQualityStatus
from abtp.domain import OrderIntent, RiskCheck, RiskDecisionStatus, SignalDirection
from abtp.risk.position_sizing import PositionSizeResult, calculate_position_size

if TYPE_CHECKING:
    from abtp.risk.engine import RiskEvaluationRequest, RiskPolicy


@dataclass(frozen=True, slots=True)
class RiskPortfolioContext:
    """Portfolio and account inputs required for Stage 022 risk checks."""

    total_equity: Decimal
    available_cash: Decimal
    current_exposure: Decimal
    correlated_exposure: Decimal
    current_drawdown_pct: Decimal
    daily_pnl: Decimal
    weekly_pnl: Decimal
    data_quality: DataQualityStatus

    def __post_init__(self) -> None:
        if self.total_equity <= Decimal("0"):
            raise ValueError("total_equity must be positive")
        for value, field_name in (
            (self.available_cash, "available_cash"),
            (self.current_exposure, "current_exposure"),
            (self.correlated_exposure, "correlated_exposure"),
            (self.current_drawdown_pct, "current_drawdown_pct"),
        ):
            if value < Decimal("0"):
                raise ValueError(f"{field_name} cannot be negative")


def evaluate_risk_checks(
    *,
    request: RiskEvaluationRequest,
    policy: RiskPolicy,
    position_size: PositionSizeResult | None,
) -> tuple[RiskCheck, ...]:
    """Evaluate deterministic risk checks for one strategy signal."""

    evaluation = request.strategy_evaluation
    portfolio = request.portfolio
    checks = [
        _check(
            "kill-switch",
            not policy.kill_switch_active,
            "kill switch is inactive",
            "kill switch is active",
        ),
        _check(
            "directional-signal",
            evaluation.signal.direction is not SignalDirection.HOLD,
            "signal is directional",
            "hold signal cannot become an order",
        ),
        _check(
            "spot-buy-only",
            evaluation.signal.direction is SignalDirection.BUY,
            "spot buy signal is supported",
            "only spot buy signals are supported in Stage 022",
        ),
        _check(
            "signal-confidence",
            evaluation.signal.confidence >= policy.min_signal_confidence,
            "signal confidence meets threshold",
            "signal confidence is below threshold",
            observed=evaluation.signal.confidence,
            limit=policy.min_signal_confidence,
        ),
        _check(
            "stop-loss",
            not policy.require_stop_loss or evaluation.plan.stop_suggestion is not None,
            "stop-loss suggestion is present",
            "missing stop-loss suggestion",
        ),
        _stop_distance_check(request),
        _check(
            "data-quality",
            portfolio.data_quality.is_trusted,
            "risk input data quality is trusted",
            "risk input data quality is not trusted",
        ),
        _check(
            "drawdown",
            portfolio.current_drawdown_pct <= policy.max_drawdown_pct,
            "drawdown is within limit",
            "drawdown breach",
            observed=portfolio.current_drawdown_pct,
            limit=policy.max_drawdown_pct,
        ),
        _loss_check(
            "daily-loss",
            portfolio.daily_pnl,
            portfolio.total_equity * policy.max_daily_loss_pct,
            "daily loss limit is not breached",
            "daily loss breach",
        ),
        _loss_check(
            "weekly-loss",
            portfolio.weekly_pnl,
            portfolio.total_equity * policy.max_weekly_loss_pct,
            "weekly loss limit is not breached",
            "weekly loss breach",
        ),
        _check(
            "spread",
            request.spread_bps <= policy.max_spread_bps,
            "spread is within ceiling",
            "excessive spread",
            observed=request.spread_bps,
            limit=policy.max_spread_bps,
        ),
        _check(
            "slippage",
            request.estimated_slippage_bps <= policy.max_slippage_bps,
            "slippage is within ceiling",
            "excessive slippage",
            observed=request.estimated_slippage_bps,
            limit=policy.max_slippage_bps,
        ),
        _check(
            "exposure-capacity",
            position_size is not None and position_size.approved_capacity,
            "position capacity is available",
            "no risk-approved position capacity is available",
            observed=position_size.max_notional if position_size is not None else Decimal("0"),
            limit=portfolio.total_equity * policy.max_position_pct,
        ),
    ]
    return tuple(checks)


def assert_order_intent_has_approved_risk(intent: OrderIntent) -> None:
    """Fail if an order intent lacks a matching approved risk decision."""

    if intent.risk_decision is None:
        raise ValueError("order intent cannot bypass risk decision")
    if intent.risk_decision.order_intent_id != intent.id:
        raise ValueError("risk decision must reference this order intent")
    if intent.risk_decision.status is not RiskDecisionStatus.APPROVED:
        raise ValueError("order intent requires an approved risk decision")


def _stop_distance_check(request: RiskEvaluationRequest) -> RiskCheck:
    stop = request.strategy_evaluation.plan.stop_suggestion
    entry = request.entry_price
    if stop is None or entry is None:
        return RiskCheck("stop-distance", False, "stop distance cannot be evaluated")
    passed = stop < entry
    return RiskCheck(
        name="stop-distance",
        passed=passed,
        reason="stop is below entry" if passed else "stop must be below entry for spot buys",
        observed_value=entry - stop,
        limit_value=Decimal("0"),
    )


def _loss_check(
    name: str,
    pnl: Decimal,
    max_loss_amount: Decimal,
    passed_reason: str,
    failed_reason: str,
) -> RiskCheck:
    return RiskCheck(
        name=name,
        passed=pnl >= -max_loss_amount,
        reason=passed_reason if pnl >= -max_loss_amount else failed_reason,
        observed_value=pnl,
        limit_value=-max_loss_amount,
    )


def _check(
    name: str,
    passed: bool,
    passed_reason: str,
    failed_reason: str,
    *,
    observed: Decimal | None = None,
    limit: Decimal | None = None,
) -> RiskCheck:
    return RiskCheck(
        name=name,
        passed=passed,
        reason=passed_reason if passed else failed_reason,
        observed_value=observed,
        limit_value=limit,
    )


def position_size_for_request(
    *,
    request: RiskEvaluationRequest,
    policy: RiskPolicy,
) -> PositionSizeResult | None:
    """Calculate position size only when entry and stop are available."""

    stop = request.strategy_evaluation.plan.stop_suggestion
    if request.entry_price is None or stop is None:
        return None
    return calculate_position_size(
        total_equity=request.portfolio.total_equity,
        available_cash=request.portfolio.available_cash,
        current_exposure=request.portfolio.current_exposure + request.portfolio.correlated_exposure,
        entry_price=request.entry_price,
        stop_price=stop,
        max_risk_per_trade_pct=policy.max_risk_per_trade_pct,
        max_position_pct=policy.max_position_pct,
        min_cash_reserve_pct=policy.min_cash_reserve_pct,
        fee_bps=policy.fee_bps,
        slippage_bps=request.estimated_slippage_bps,
    )
