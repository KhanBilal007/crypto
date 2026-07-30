"""Backtesting engine exports."""

from abtp.backtesting.broker import (
    BacktestAccount,
    BacktestBroker,
    BacktestBrokerConfig,
    BacktestTrade,
)
from abtp.backtesting.engine import (
    BacktestConfig,
    BacktestingEngine,
    BacktestResult,
    BacktestStepResult,
)
from abtp.backtesting.metrics import (
    NO_LOSS_PROFIT_FACTOR,
    PerformanceMetrics,
    RegimePerformance,
    calculate_average_win_loss,
    calculate_expectancy,
    calculate_max_drawdown,
    calculate_net_return,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_tail_loss,
    calculate_win_rate,
    metrics_from_backtest,
    returns_from_equity,
)
from abtp.backtesting.reports import (
    AcceptanceCheck,
    AcceptanceGate,
    BacktestReport,
    build_backtest_report,
    build_performance_report,
    evaluate_acceptance,
)
from abtp.backtesting.slippage import (
    SlippageModelConfig,
    estimate_execution_price,
    total_cost_bps,
)

__all__ = [
    "BacktestAccount",
    "BacktestBroker",
    "BacktestBrokerConfig",
    "BacktestConfig",
    "BacktestReport",
    "BacktestResult",
    "BacktestStepResult",
    "BacktestTrade",
    "BacktestingEngine",
    "AcceptanceCheck",
    "AcceptanceGate",
    "NO_LOSS_PROFIT_FACTOR",
    "PerformanceMetrics",
    "RegimePerformance",
    "SlippageModelConfig",
    "build_backtest_report",
    "build_performance_report",
    "calculate_average_win_loss",
    "calculate_expectancy",
    "calculate_max_drawdown",
    "calculate_net_return",
    "calculate_profit_factor",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_tail_loss",
    "calculate_win_rate",
    "evaluate_acceptance",
    "estimate_execution_price",
    "metrics_from_backtest",
    "returns_from_equity",
    "total_cost_bps",
]
