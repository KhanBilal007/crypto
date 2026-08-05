"""Risk-adjusted backtesting performance metrics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from abtp.backtesting.engine import BacktestResult


DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
NO_LOSS_PROFIT_FACTOR = Decimal("999")


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    """Performance slice for one market regime label."""

    regime_label: str
    period_count: int
    net_return: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    expectancy: Decimal

    def __post_init__(self) -> None:
        if not self.regime_label.strip():
            raise ValueError("regime_label is required")
        if self.period_count < 0:
            raise ValueError("period_count cannot be negative")

    def as_dict(self) -> dict[str, str | int]:
        return {
            "regime_label": self.regime_label,
            "period_count": self.period_count,
            "net_return": str(self.net_return),
            "max_drawdown": str(self.max_drawdown),
            "win_rate": str(self.win_rate),
            "expectancy": str(self.expectancy),
        }


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Backtest metrics used for reporting and paper-trading eligibility gates."""

    net_return: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    win_rate: Decimal
    expectancy: Decimal
    average_win: Decimal
    average_loss: Decimal
    exposure_time_pct: Decimal
    tail_loss: Decimal
    total_fees: Decimal
    trade_count: int
    costs_included: bool
    regime_performance: tuple[RegimePerformance, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return JSON-friendly metric values without losing Decimal precision."""

        return {
            "net_return": str(self.net_return),
            "max_drawdown": str(self.max_drawdown),
            "profit_factor": str(self.profit_factor),
            "sharpe_ratio": str(self.sharpe_ratio),
            "sortino_ratio": str(self.sortino_ratio),
            "win_rate": str(self.win_rate),
            "expectancy": str(self.expectancy),
            "average_win": str(self.average_win),
            "average_loss": str(self.average_loss),
            "exposure_time_pct": str(self.exposure_time_pct),
            "tail_loss": str(self.tail_loss),
            "total_fees": str(self.total_fees),
            "trade_count": self.trade_count,
            "costs_included": self.costs_included,
            "regime_performance": [item.as_dict() for item in self.regime_performance],
        }


def returns_from_equity(equity_curve: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
    """Calculate period returns from an ordered equity curve."""

    returns: list[Decimal] = []
    for previous, current in zip(equity_curve, equity_curve[1:], strict=False):
        if previous <= DECIMAL_ZERO:
            returns.append(DECIMAL_ZERO)
        else:
            returns.append(current / previous - DECIMAL_ONE)
    return tuple(returns)


def calculate_net_return(starting_equity: Decimal, ending_equity: Decimal) -> Decimal:
    """Return total net return from starting and ending equity."""

    if starting_equity <= DECIMAL_ZERO:
        raise ValueError("starting_equity must be positive")
    return ending_equity / starting_equity - DECIMAL_ONE


def calculate_max_drawdown(equity_curve: tuple[Decimal, ...]) -> Decimal:
    """Return maximum peak-to-trough drawdown for an equity curve."""

    if not equity_curve:
        return DECIMAL_ZERO
    peak = equity_curve[0]
    max_drawdown = DECIMAL_ZERO
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > DECIMAL_ZERO:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def calculate_profit_factor(values: tuple[Decimal, ...]) -> Decimal:
    """Return gross positive result divided by gross negative result."""

    gross_profit = sum((value for value in values if value > DECIMAL_ZERO), DECIMAL_ZERO)
    gross_loss = abs(sum((value for value in values if value < DECIMAL_ZERO), DECIMAL_ZERO))
    if gross_profit == DECIMAL_ZERO and gross_loss == DECIMAL_ZERO:
        return DECIMAL_ZERO
    if gross_loss == DECIMAL_ZERO:
        return NO_LOSS_PROFIT_FACTOR
    return gross_profit / gross_loss


def calculate_win_rate(values: tuple[Decimal, ...]) -> Decimal:
    """Return the fraction of non-zero periods or trades that were positive."""

    actionable = tuple(value for value in values if value != DECIMAL_ZERO)
    if not actionable:
        return DECIMAL_ZERO
    wins = sum(1 for value in actionable if value > DECIMAL_ZERO)
    return Decimal(wins) / Decimal(len(actionable))


def calculate_expectancy(values: tuple[Decimal, ...]) -> Decimal:
    """Return average expected result per period or trade."""

    if not values:
        return DECIMAL_ZERO
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))


def calculate_average_win_loss(values: tuple[Decimal, ...]) -> tuple[Decimal, Decimal]:
    """Return average positive and average negative values."""

    wins = tuple(value for value in values if value > DECIMAL_ZERO)
    losses = tuple(value for value in values if value < DECIMAL_ZERO)
    average_win = sum(wins, DECIMAL_ZERO) / Decimal(len(wins)) if wins else DECIMAL_ZERO
    average_loss = sum(losses, DECIMAL_ZERO) / Decimal(len(losses)) if losses else DECIMAL_ZERO
    return average_win, average_loss


def calculate_sharpe_ratio(returns: tuple[Decimal, ...]) -> Decimal:
    """Return a simple unannualized Sharpe ratio for deterministic tests."""

    if len(returns) < 2:
        return DECIMAL_ZERO
    deviation = _standard_deviation(returns)
    if deviation == DECIMAL_ZERO:
        return DECIMAL_ZERO
    return calculate_expectancy(returns) / deviation


def calculate_sortino_ratio(returns: tuple[Decimal, ...]) -> Decimal:
    """Return a simple unannualized Sortino ratio using downside deviation."""

    if len(returns) < 2:
        return DECIMAL_ZERO
    downside = tuple(min(value, DECIMAL_ZERO) for value in returns)
    deviation = _standard_deviation(downside)
    if deviation == DECIMAL_ZERO:
        return DECIMAL_ZERO
    return calculate_expectancy(returns) / deviation


def calculate_tail_loss(returns: tuple[Decimal, ...]) -> Decimal:
    """Return the worst observed period return as a conservative tail-loss proxy."""

    if not returns:
        return DECIMAL_ZERO
    return min(returns)


def metrics_from_backtest(result: BacktestResult) -> PerformanceMetrics:
    """Build performance metrics from a Stage 025 backtest result."""

    equity_curve = tuple(step.equity for step in result.steps)
    if result.starting_equity not in equity_curve[:1]:
        equity_curve = (result.starting_equity, *equity_curve)
    returns = returns_from_equity(equity_curve)
    average_win, average_loss = calculate_average_win_loss(returns)
    return PerformanceMetrics(
        net_return=result.net_return,
        max_drawdown=max(result.max_drawdown, calculate_max_drawdown(equity_curve)),
        profit_factor=calculate_profit_factor(returns),
        sharpe_ratio=calculate_sharpe_ratio(returns),
        sortino_ratio=calculate_sortino_ratio(returns),
        win_rate=calculate_win_rate(returns),
        expectancy=calculate_expectancy(returns),
        average_win=average_win,
        average_loss=average_loss,
        exposure_time_pct=_exposure_time_pct(result),
        tail_loss=calculate_tail_loss(returns),
        total_fees=result.total_fees,
        trade_count=len(result.trades),
        costs_included=result.costs_included,
        regime_performance=_regime_performance(result),
    )


def _standard_deviation(values: tuple[Decimal, ...]) -> Decimal:
    mean = calculate_expectancy(values)
    variance = sum(((value - mean) ** 2 for value in values), DECIMAL_ZERO) / Decimal(len(values))
    return variance.sqrt()


def _exposure_time_pct(result: BacktestResult) -> Decimal:
    if not result.steps:
        return DECIMAL_ZERO
    exposed_steps = sum(
        1
        for step in result.steps
        if step.execution_result is not None and step.execution_result.accepted
    )
    return Decimal(exposed_steps) / Decimal(len(result.steps))


def _regime_performance(result: BacktestResult) -> tuple[RegimePerformance, ...]:
    grouped_returns: dict[str, list[Decimal]] = {}
    grouped_equity: dict[str, list[Decimal]] = {}
    previous_equity = result.starting_equity
    for step in result.steps:
        label = step.strategy_evaluation.plan.regime_label or "unknown"
        period_return = (
            step.equity / previous_equity - DECIMAL_ONE
            if previous_equity > DECIMAL_ZERO
            else DECIMAL_ZERO
        )
        grouped_returns.setdefault(label, []).append(period_return)
        grouped_equity.setdefault(label, []).append(step.equity)
        previous_equity = step.equity
    return tuple(
        RegimePerformance(
            regime_label=label,
            period_count=len(values),
            net_return=_compound_return(tuple(values)),
            max_drawdown=calculate_max_drawdown(tuple(grouped_equity[label])),
            win_rate=calculate_win_rate(tuple(values)),
            expectancy=calculate_expectancy(tuple(values)),
        )
        for label, values in sorted(grouped_returns.items())
    )


def _compound_return(returns: tuple[Decimal, ...]) -> Decimal:
    compounded = DECIMAL_ONE
    for value in returns:
        compounded *= DECIMAL_ONE + value
    return compounded - DECIMAL_ONE
