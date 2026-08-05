"""Backtesting reports and acceptance gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from abtp.backtesting.engine import BacktestResult
from abtp.backtesting.metrics import PerformanceMetrics, metrics_from_backtest


@dataclass(frozen=True, slots=True)
class AcceptanceGate:
    """Risk-first thresholds for paper-trading eligibility reviews."""

    max_drawdown: Decimal = Decimal("0.10")
    max_tail_loss: Decimal = Decimal("0.05")
    min_net_return: Decimal = Decimal("0")
    min_profit_factor: Decimal = Decimal("1")
    min_trade_count: int = 1
    require_costs_included: bool = True

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.max_drawdown <= Decimal("1"):
            raise ValueError("max_drawdown must be between 0 and 1")
        if not Decimal("0") <= self.max_tail_loss <= Decimal("1"):
            raise ValueError("max_tail_loss must be between 0 and 1")
        if self.min_trade_count < 0:
            raise ValueError("min_trade_count cannot be negative")


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    """One acceptance gate result."""

    name: str
    passed: bool
    observed: str
    limit: str
    reason: str

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "passed": self.passed,
            "observed": self.observed,
            "limit": self.limit,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class BacktestReport:
    """Auditable backtest report for strategy validation."""

    strategy_name: str
    generated_at: datetime
    metrics: PerformanceMetrics
    acceptance_checks: tuple[AcceptanceCheck, ...]
    eligible_for_paper_trading: bool
    summary: str
    limitations: tuple[str, ...]
    source_refs: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-friendly report representation."""

        return {
            "strategy_name": self.strategy_name,
            "generated_at": self.generated_at.isoformat(),
            "metrics": self.metrics.as_dict(),
            "acceptance_checks": [check.as_dict() for check in self.acceptance_checks],
            "eligible_for_paper_trading": self.eligible_for_paper_trading,
            "summary": self.summary,
            "limitations": list(self.limitations),
            "source_refs": dict(self.source_refs),
        }


def evaluate_acceptance(
    metrics: PerformanceMetrics,
    gate: AcceptanceGate | None = None,
) -> tuple[AcceptanceCheck, ...]:
    """Evaluate risk-first paper-trading eligibility checks."""

    active_gate = gate or AcceptanceGate()
    checks = (
        AcceptanceCheck(
            name="costs_included",
            passed=(metrics.costs_included or not active_gate.require_costs_included),
            observed=str(metrics.costs_included),
            limit=str(active_gate.require_costs_included),
            reason=(
                "fees and slippage are included"
                if metrics.costs_included
                else "fees and slippage must be included before paper eligibility"
            ),
        ),
        AcceptanceCheck(
            name="max_drawdown",
            passed=metrics.max_drawdown <= active_gate.max_drawdown,
            observed=str(metrics.max_drawdown),
            limit=f"<= {active_gate.max_drawdown}",
            reason=(
                "drawdown is within acceptance limit"
                if metrics.max_drawdown <= active_gate.max_drawdown
                else "drawdown exceeds acceptance limit even if net return is positive"
            ),
        ),
        AcceptanceCheck(
            name="tail_loss",
            passed=metrics.tail_loss >= -active_gate.max_tail_loss,
            observed=str(metrics.tail_loss),
            limit=f">= -{active_gate.max_tail_loss}",
            reason=(
                "worst period loss is within acceptance limit"
                if metrics.tail_loss >= -active_gate.max_tail_loss
                else "tail loss exceeds acceptance limit"
            ),
        ),
        AcceptanceCheck(
            name="net_return",
            passed=metrics.net_return >= active_gate.min_net_return,
            observed=str(metrics.net_return),
            limit=f">= {active_gate.min_net_return}",
            reason=(
                "net return meets minimum acceptance threshold"
                if metrics.net_return >= active_gate.min_net_return
                else "net return is below acceptance threshold"
            ),
        ),
        AcceptanceCheck(
            name="profit_factor",
            passed=metrics.profit_factor >= active_gate.min_profit_factor,
            observed=str(metrics.profit_factor),
            limit=f">= {active_gate.min_profit_factor}",
            reason=(
                "profit factor meets acceptance threshold"
                if metrics.profit_factor >= active_gate.min_profit_factor
                else "losses are too large relative to gains"
            ),
        ),
        AcceptanceCheck(
            name="trade_count",
            passed=metrics.trade_count >= active_gate.min_trade_count,
            observed=str(metrics.trade_count),
            limit=f">= {active_gate.min_trade_count}",
            reason=(
                "trade sample meets minimum count"
                if metrics.trade_count >= active_gate.min_trade_count
                else "trade sample is too small for paper eligibility"
            ),
        ),
    )
    return checks


def build_backtest_report(
    result: BacktestResult,
    *,
    strategy_name: str,
    gate: AcceptanceGate | None = None,
    generated_at: datetime | None = None,
    source_refs: dict[str, str] | None = None,
) -> BacktestReport:
    """Create a report from a completed Stage 025 backtest result."""

    return build_performance_report(
        metrics_from_backtest(result),
        strategy_name=strategy_name,
        gate=gate,
        generated_at=generated_at,
        source_refs=source_refs,
    )


def build_performance_report(
    metrics: PerformanceMetrics,
    *,
    strategy_name: str,
    gate: AcceptanceGate | None = None,
    generated_at: datetime | None = None,
    source_refs: dict[str, str] | None = None,
) -> BacktestReport:
    """Create an auditable report from already calculated metrics."""

    if not strategy_name.strip():
        raise ValueError("strategy_name is required")
    checks = evaluate_acceptance(metrics, gate)
    eligible = all(check.passed for check in checks)
    return BacktestReport(
        strategy_name=strategy_name,
        generated_at=generated_at or datetime.now(UTC),
        metrics=metrics,
        acceptance_checks=checks,
        eligible_for_paper_trading=eligible,
        summary=_summary(eligible),
        limitations=(
            "Backtests are deterministic simulations, not live execution.",
            "Eligibility means the configured risk gates passed; it is not a profit guarantee.",
            "Results depend on fixture quality, slippage assumptions, fees, and selected "
            "candle history.",
        ),
        source_refs=source_refs or {},
    )


def _summary(eligible: bool) -> str:
    if eligible:
        return "Backtest passed configured risk-first paper-trading eligibility gates."
    return "Backtest failed one or more risk-first paper-trading eligibility gates."
