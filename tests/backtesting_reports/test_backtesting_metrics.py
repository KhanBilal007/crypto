from __future__ import annotations

from decimal import Decimal

from abtp.backtesting import (
    NO_LOSS_PROFIT_FACTOR,
    calculate_average_win_loss,
    calculate_expectancy,
    calculate_max_drawdown,
    calculate_net_return,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_tail_loss,
    calculate_win_rate,
    returns_from_equity,
)


def test_returns_from_equity_are_ordered_period_returns() -> None:
    returns = returns_from_equity((Decimal("100"), Decimal("110"), Decimal("99"), Decimal("118.8")))

    assert returns == (Decimal("0.1"), Decimal("-0.1"), Decimal("0.2"))


def test_profit_factor_and_win_loss_metrics_use_signed_results() -> None:
    values = (Decimal("10"), Decimal("-5"), Decimal("15"), Decimal("-10"))

    assert calculate_profit_factor(values) == Decimal("1.666666666666666666666666667")
    assert calculate_win_rate(values) == Decimal("0.5")
    assert calculate_expectancy(values) == Decimal("2.5")
    assert calculate_average_win_loss(values) == (Decimal("12.5"), Decimal("-7.5"))


def test_profit_factor_caps_no_loss_series_for_json_safe_reports() -> None:
    assert calculate_profit_factor((Decimal("1"), Decimal("2"))) == NO_LOSS_PROFIT_FACTOR


def test_drawdown_tail_loss_and_return_metrics_are_deterministic() -> None:
    equity_curve = (Decimal("100"), Decimal("120"), Decimal("90"), Decimal("108"))
    returns = returns_from_equity(equity_curve)

    assert calculate_net_return(Decimal("100"), Decimal("108")) == Decimal("0.08")
    assert calculate_max_drawdown(equity_curve) == Decimal("0.25")
    assert calculate_tail_loss(returns) == Decimal("-0.25")
    assert calculate_sharpe_ratio(returns) != Decimal("0")
    assert calculate_sortino_ratio(returns) != Decimal("0")
