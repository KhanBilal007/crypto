"""Paper trading evaluation metrics for Stage 073."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from abtp.backtesting.metrics import calculate_max_drawdown, calculate_profit_factor
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import OrderSide
from abtp.domain.models import JsonValue
from abtp.paper.account import PaperTrade
from abtp.paper.summary import PaperTradingSessionSummary

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class PaperEvaluationPolicy:
    """Conservative thresholds for reviewing a paper-trading period."""

    min_paper_trading_days: int = 14
    min_completed_trades: int = 3
    max_drawdown: Decimal = Decimal("0.10")
    max_daily_loss_events: int = 0
    max_weekly_loss_events: int = 0
    min_expectancy: Decimal = Decimal("0")
    min_profit_factor: Decimal = Decimal("1")
    max_fee_impact_pct: Decimal = Decimal("0.01")
    max_blocked_cycle_rate: Decimal = Decimal("0.50")
    max_confidence_calibration_error: Decimal = Decimal("0.20")
    require_stop_loss_compliance: bool = True
    require_complete_audit: bool = True
    policy_version: str = "stage-073.v1"

    def __post_init__(self) -> None:
        if self.min_paper_trading_days < 1:
            raise ValueError("min_paper_trading_days must be positive")
        if self.min_completed_trades < 1:
            raise ValueError("min_completed_trades must be positive")
        for name, value in (
            ("max_drawdown", self.max_drawdown),
            ("max_fee_impact_pct", self.max_fee_impact_pct),
            ("max_blocked_cycle_rate", self.max_blocked_cycle_rate),
            ("max_confidence_calibration_error", self.max_confidence_calibration_error),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_daily_loss_events < 0 or self.max_weekly_loss_events < 0:
            raise ValueError("loss event thresholds cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "min_paper_trading_days": self.min_paper_trading_days,
            "min_completed_trades": self.min_completed_trades,
            "max_drawdown": str(self.max_drawdown),
            "max_daily_loss_events": self.max_daily_loss_events,
            "max_weekly_loss_events": self.max_weekly_loss_events,
            "min_expectancy": str(self.min_expectancy),
            "min_profit_factor": str(self.min_profit_factor),
            "max_fee_impact_pct": str(self.max_fee_impact_pct),
            "max_blocked_cycle_rate": str(self.max_blocked_cycle_rate),
            "max_confidence_calibration_error": str(self.max_confidence_calibration_error),
            "require_stop_loss_compliance": self.require_stop_loss_compliance,
            "require_complete_audit": self.require_complete_audit,
            "policy_version": self.policy_version,
        }


@dataclass(frozen=True, slots=True)
class PaperEvaluationInput:
    """Evidence supplied to the Stage 073 paper evaluation gate."""

    sessions: Sequence[PaperTradingSessionSummary]
    completed_trades: Sequence[PaperTrade]
    evaluation_start: datetime
    evaluation_end: datetime
    generated_at: datetime
    daily_loss_events: int = 0
    weekly_loss_events: int = 0
    stop_loss_violations: int = 0
    confidence_calibration_error: Decimal | None = None
    capital_preservation_events: int = 0
    governance_violations: int = 0
    audit_refs: tuple[str, ...] = ()
    quality: DataQualityStatus | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sessions", tuple(self.sessions))
        object.__setattr__(self, "completed_trades", tuple(self.completed_trades))
        object.__setattr__(self, "evaluation_start", normalize_timestamp(self.evaluation_start))
        object.__setattr__(self, "evaluation_end", normalize_timestamp(self.evaluation_end))
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if self.evaluation_end <= self.evaluation_start:
            raise ValueError("evaluation_end must be after evaluation_start")
        for name, value in (
            ("daily_loss_events", self.daily_loss_events),
            ("weekly_loss_events", self.weekly_loss_events),
            ("stop_loss_violations", self.stop_loss_violations),
            ("capital_preservation_events", self.capital_preservation_events),
            ("governance_violations", self.governance_violations),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.confidence_calibration_error is not None and not (
            DECIMAL_ZERO <= self.confidence_calibration_error <= DECIMAL_ONE
        ):
            raise ValueError("confidence_calibration_error must be between 0 and 1")
        object.__setattr__(self, "audit_refs", tuple(ref for ref in self.audit_refs if ref))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def review_quality(self) -> DataQualityStatus:
        return self.quality or DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="paper_evaluation:input",
            checked_at=self.generated_at,
        )


@dataclass(frozen=True, slots=True)
class PaperEvaluationMetrics:
    """Deterministic paper-trading performance metrics."""

    evaluation_days: int
    session_count: int
    cycle_count: int
    completed_trade_count: int
    net_return: Decimal
    win_rate: Decimal
    average_win: Decimal
    average_loss: Decimal
    expectancy: Decimal
    profit_factor: Decimal
    max_drawdown: Decimal
    daily_loss_events: int
    weekly_loss_events: int
    blocked_cycle_count: int
    blocked_cycle_rate: Decimal
    risk_rejected_count: int
    total_fees: Decimal
    fee_impact_pct: Decimal
    stop_loss_violations: int
    confidence_calibration_error: Decimal | None
    capital_preservation_events: int
    governance_violations: int
    audit_complete: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("evaluation_days", self.evaluation_days),
            ("session_count", self.session_count),
            ("cycle_count", self.cycle_count),
            ("completed_trade_count", self.completed_trade_count),
            ("daily_loss_events", self.daily_loss_events),
            ("weekly_loss_events", self.weekly_loss_events),
            ("blocked_cycle_count", self.blocked_cycle_count),
            ("risk_rejected_count", self.risk_rejected_count),
            ("stop_loss_violations", self.stop_loss_violations),
            ("capital_preservation_events", self.capital_preservation_events),
            ("governance_violations", self.governance_violations),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.max_drawdown < DECIMAL_ZERO or self.total_fees < DECIMAL_ZERO:
            raise ValueError("drawdown and fees cannot be negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluation_days": self.evaluation_days,
            "session_count": self.session_count,
            "cycle_count": self.cycle_count,
            "completed_trade_count": self.completed_trade_count,
            "net_return": str(self.net_return),
            "win_rate": str(self.win_rate),
            "average_win": str(self.average_win),
            "average_loss": str(self.average_loss),
            "expectancy": str(self.expectancy),
            "profit_factor": str(self.profit_factor),
            "max_drawdown": str(self.max_drawdown),
            "daily_loss_events": self.daily_loss_events,
            "weekly_loss_events": self.weekly_loss_events,
            "blocked_cycle_count": self.blocked_cycle_count,
            "blocked_cycle_rate": str(self.blocked_cycle_rate),
            "risk_rejected_count": self.risk_rejected_count,
            "total_fees": str(self.total_fees),
            "fee_impact_pct": str(self.fee_impact_pct),
            "stop_loss_violations": self.stop_loss_violations,
            "confidence_calibration_error": None
            if self.confidence_calibration_error is None
            else str(self.confidence_calibration_error),
            "capital_preservation_events": self.capital_preservation_events,
            "governance_violations": self.governance_violations,
            "audit_complete": self.audit_complete,
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "evaluation_days": str(self.evaluation_days),
            "completed_trade_count": str(self.completed_trade_count),
            "net_return": str(self.net_return),
            "max_drawdown": str(self.max_drawdown),
            "expectancy": str(self.expectancy),
            "profit_factor": str(self.profit_factor),
            "blocked_cycle_rate": str(self.blocked_cycle_rate),
            "fee_impact_pct": str(self.fee_impact_pct),
            "audit_complete": str(self.audit_complete),
        }


def build_paper_evaluation_metrics(
    evaluation_input: PaperEvaluationInput,
) -> PaperEvaluationMetrics:
    """Build deterministic metrics from paper sessions and completed trades."""

    sessions = tuple(sorted(evaluation_input.sessions, key=lambda item: item.started_at))
    trade_results = _closed_trade_results(tuple(evaluation_input.completed_trades))
    cycle_count = sum(session.cycle_count for session in sessions)
    blocked = sum(session.blocked_count for session in sessions)
    total_fees = sum((trade.fee_paid for trade in evaluation_input.completed_trades), DECIMAL_ZERO)
    equity_curve = _equity_curve(sessions)
    starting = sessions[0].starting_equity if sessions else DECIMAL_ONE
    ending = sessions[-1].ending_equity if sessions else DECIMAL_ONE
    return PaperEvaluationMetrics(
        evaluation_days=max(
            1, (evaluation_input.evaluation_end - evaluation_input.evaluation_start).days
        ),
        session_count=len(sessions),
        cycle_count=cycle_count,
        completed_trade_count=len(trade_results),
        net_return=_net_return(starting, ending),
        win_rate=_win_rate(trade_results),
        average_win=_average_win(trade_results),
        average_loss=_average_loss(trade_results),
        expectancy=_expectancy(trade_results),
        profit_factor=calculate_profit_factor(trade_results),
        max_drawdown=calculate_max_drawdown(equity_curve),
        daily_loss_events=evaluation_input.daily_loss_events,
        weekly_loss_events=evaluation_input.weekly_loss_events,
        blocked_cycle_count=blocked,
        blocked_cycle_rate=_ratio(blocked, cycle_count),
        risk_rejected_count=sum(session.risk_rejected_count for session in sessions),
        total_fees=total_fees,
        fee_impact_pct=_fee_impact(total_fees, starting),
        stop_loss_violations=evaluation_input.stop_loss_violations,
        confidence_calibration_error=evaluation_input.confidence_calibration_error,
        capital_preservation_events=evaluation_input.capital_preservation_events,
        governance_violations=evaluation_input.governance_violations,
        audit_complete=_audit_complete(evaluation_input, sessions),
    )


def paper_evaluation_quality(
    evaluation_input: PaperEvaluationInput,
    metrics: PaperEvaluationMetrics,
    policy: PaperEvaluationPolicy,
    rejection_reasons: Sequence[str],
) -> DataQualityStatus:
    """Return fail-closed quality for the evaluation evidence."""

    issues = list(evaluation_input.review_quality.issues)
    for reason in rejection_reasons:
        severity = DataTrustLevel.REJECTED if _blocking_reason(reason) else DataTrustLevel.DEGRADED
        issues.append(
            DataQualityIssue(
                flag=f"paper_evaluation_{_flag(reason)}",
                severity=severity,
                reason=reason,
            )
        )
    if evaluation_input.review_quality.is_rejected:
        issues.append(
            DataQualityIssue(
                flag="paper_evaluation_rejected_input_quality",
                severity=DataTrustLevel.REJECTED,
                reason="paper evaluation input quality is rejected",
            )
        )
    if metrics.completed_trade_count < policy.min_completed_trades:
        issues.append(
            DataQualityIssue(
                flag="paper_evaluation_insufficient_trade_sample",
                severity=DataTrustLevel.DEGRADED,
                reason="completed paper trade sample is below policy minimum",
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="paper_evaluation:gate",
        checked_at=evaluation_input.generated_at,
    )


def _closed_trade_results(trades: tuple[PaperTrade, ...]) -> tuple[Decimal, ...]:
    lots: list[tuple[Decimal, Decimal]] = []
    results: list[Decimal] = []
    for trade in sorted(trades, key=lambda item: item.occurred_at):
        if trade.side is OrderSide.BUY:
            lots.append((trade.quantity, trade.price))
            continue
        remaining = trade.quantity
        realized = -trade.fee_paid
        while remaining > DECIMAL_ZERO and lots:
            lot_qty, lot_price = lots.pop(0)
            matched = min(remaining, lot_qty)
            realized += (trade.price - lot_price) * matched
            remaining -= matched
            leftover = lot_qty - matched
            if leftover > DECIMAL_ZERO:
                lots.insert(0, (leftover, lot_price))
        if realized != -trade.fee_paid or trade.quantity > remaining:
            results.append(realized)
    return tuple(results)


def _equity_curve(sessions: tuple[PaperTradingSessionSummary, ...]) -> tuple[Decimal, ...]:
    if not sessions:
        return (DECIMAL_ONE,)
    values: list[Decimal] = [sessions[0].starting_equity]
    for session in sessions:
        for cycle in session.cycles:
            equity = cycle.metrics.get("equity")
            if isinstance(equity, Decimal):
                values.append(equity)
        values.append(session.ending_equity)
    return tuple(values)


def _net_return(starting: Decimal, ending: Decimal) -> Decimal:
    if starting <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return ((ending / starting) - DECIMAL_ONE).quantize(SCORE_QUANT)


def _win_rate(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return (
        Decimal(sum(1 for value in values if value > DECIMAL_ZERO)) / Decimal(len(values))
    ).quantize(SCORE_QUANT)


def _average_win(values: tuple[Decimal, ...]) -> Decimal:
    winners = tuple(value for value in values if value > DECIMAL_ZERO)
    if not winners:
        return DECIMAL_ZERO
    return (sum(winners, DECIMAL_ZERO) / Decimal(len(winners))).quantize(SCORE_QUANT)


def _average_loss(values: tuple[Decimal, ...]) -> Decimal:
    losers = tuple(value for value in values if value < DECIMAL_ZERO)
    if not losers:
        return DECIMAL_ZERO
    return (sum(losers, DECIMAL_ZERO) / Decimal(len(losers))).quantize(SCORE_QUANT)


def _expectancy(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return (sum(values, DECIMAL_ZERO) / Decimal(len(values))).quantize(SCORE_QUANT)


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return DECIMAL_ZERO
    return (Decimal(numerator) / Decimal(denominator)).quantize(SCORE_QUANT)


def _fee_impact(fees: Decimal, starting: Decimal) -> Decimal:
    if starting <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return (fees / starting).quantize(SCORE_QUANT)


def _audit_complete(
    evaluation_input: PaperEvaluationInput,
    sessions: tuple[PaperTradingSessionSummary, ...],
) -> bool:
    if evaluation_input.audit_refs:
        return True
    return bool(sessions) and all(
        all(cycle.audit_events for cycle in session.cycles) for session in sessions
    )


def _blocking_reason(reason: str) -> bool:
    return any(
        term in reason
        for term in (
            "stop-loss violation",
            "capital-preservation event",
            "governance violation",
            "daily loss events",
            "weekly loss events",
            "input quality is rejected",
        )
    )


def _flag(reason: str) -> str:
    return "_".join(reason.lower().replace("/", " ").replace("-", " ").split())[:80]
