from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.automation import (
    AutomationHealthSnapshot,
    CircuitBreakerConfig,
    evaluate_circuit_breakers,
)


def test_circuit_breakers_allow_healthy_snapshot() -> None:
    decision = evaluate_circuit_breakers(AutomationHealthSnapshot())

    assert not decision.stop_required
    assert decision.reasons == ()


def test_circuit_breakers_stop_on_loss_drawdown_data_exchange_and_errors() -> None:
    decision = evaluate_circuit_breakers(
        AutomationHealthSnapshot(
            daily_pnl_pct=Decimal("-0.03"),
            weekly_pnl_pct=Decimal("-0.07"),
            drawdown_pct=Decimal("0.10"),
            consecutive_losses=3,
            stale_data=True,
            exchange_outage=True,
            abnormal_spread_bps=Decimal("100"),
            volatility_shock=True,
            model_error=True,
            risk_error=True,
            operator_present=False,
        )
    )

    assert decision.stop_required
    assert decision.reasons == (
        "daily loss limit breached",
        "weekly loss limit breached",
        "max drawdown breached",
        "stale data",
        "exchange outage",
        "abnormal spread",
        "consecutive loss limit breached",
        "volatility shock",
        "model error",
        "risk error",
        "operator presence required",
    )
    with pytest.raises(RuntimeError, match="daily loss"):
        decision.require_running_allowed()


def test_circuit_breaker_config_validates_thresholds() -> None:
    with pytest.raises(ValueError, match="max_daily_loss_pct"):
        CircuitBreakerConfig(max_daily_loss_pct=Decimal("1.5"))
