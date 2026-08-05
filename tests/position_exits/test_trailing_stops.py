from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.domain import Asset
from abtp.risk import (
    TrailingStopPolicy,
    TrailingStopState,
    initial_stop_price,
    update_atr_trailing_stop,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_initial_stop_uses_more_conservative_atr_distance() -> None:
    stop = initial_stop_price(
        entry_price=Decimal("100"),
        atr=Decimal("4"),
        policy=TrailingStopPolicy(
            base_stop_loss_pct=Decimal("0.03"), atr_stop_multiplier=Decimal("2")
        ),
    )

    assert stop == Decimal("92")


def test_atr_trailing_stop_moves_up_without_loosening() -> None:
    state = TrailingStopState(
        asset=Asset("BTC"),
        entry_price=Decimal("100"),
        highest_price=Decimal("110"),
        stop_price=Decimal("100"),
        atr=Decimal("3"),
        updated_at=NOW,
    )

    raised = update_atr_trailing_stop(
        state,
        current_price=Decimal("120"),
        atr=Decimal("4"),
        updated_at=NOW + timedelta(minutes=1),
        policy=TrailingStopPolicy(atr_trailing_multiplier=Decimal("3")),
    )
    lower_price = update_atr_trailing_stop(
        raised,
        current_price=Decimal("105"),
        atr=Decimal("4"),
        updated_at=NOW + timedelta(minutes=2),
    )

    assert raised.highest_price == Decimal("120")
    assert raised.stop_price == Decimal("108")
    assert lower_price.stop_price == raised.stop_price
