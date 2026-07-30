from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.domain import Asset
from abtp.portfolio import (
    Balance,
    OpenOrderReservation,
    PortfolioManager,
    PortfolioManagerConfig,
    PortfolioManagerState,
    PositionCostBasis,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_manager_builds_snapshot_and_risk_context() -> None:
    manager = _manager()

    snapshot = manager.snapshot(NOW)
    context = manager.risk_context(NOW)

    assert snapshot.captured_at == NOW
    assert snapshot.positions[0].asset.symbol == "BTC"
    assert snapshot.positions[0].valuation == Decimal("3000.0")
    assert manager.total_equity() == Decimal("10000.0")
    assert context.total_equity == Decimal("10000.0")
    assert context.available_cash == Decimal("6499.5")
    assert context.current_exposure == Decimal("3000.0")
    assert context.current_drawdown_pct == Decimal("0.09090909090909090909090909091")
    assert context.data_quality.is_trusted


def test_manager_constraints_block_new_positions_on_breaches() -> None:
    manager = _manager(
        balance_free=Decimal("1500"),
        btc_quantity=Decimal("0.35"),
        equity_history=(Decimal("12000"), Decimal("9000")),
        config=PortfolioManagerConfig(
            min_cash_reserve_pct=Decimal("0.20"),
            max_gross_exposure_pct=Decimal("0.80"),
            max_drawdown_pct=Decimal("0.10"),
        ),
    )

    status = manager.constraints(NOW)

    assert not status.can_open_new_positions
    assert "minimum cash reserve is breached" in status.reasons
    assert "gross exposure limit is breached" in status.reasons
    assert "drawdown limit is breached" in status.reasons


def test_manager_accounts_for_open_order_reservations() -> None:
    manager = _manager(
        reservations=(
            OpenOrderReservation(
                order_ref="risk-approved-order",
                quote_asset=Asset("USDT"),
                order_notional=Decimal("1000"),
                fee_buffer=Decimal("1"),
            ),
        )
    )

    assert manager.available_cash() == Decimal("5999")
    assert manager.constraints(NOW).can_open_new_positions


def _manager(
    *,
    balance_free: Decimal = Decimal("7000"),
    btc_quantity: Decimal = Decimal("0.1"),
    equity_history: tuple[Decimal, ...] = (Decimal("11000"), Decimal("10000")),
    reservations: tuple[OpenOrderReservation, ...] | None = None,
    config: PortfolioManagerConfig | None = None,
) -> PortfolioManager:
    return PortfolioManager(
        state=PortfolioManagerState(
            balances=(Balance(Asset("USDT"), free=balance_free),),
            positions=(
                PositionCostBasis(
                    asset=Asset("BTC"),
                    quantity=btc_quantity,
                    average_entry_price=Decimal("25000"),
                    quote_asset=Asset("USDT"),
                ),
            ),
            prices={"BTC": Decimal("30000")},
            equity_history=equity_history,
            open_order_reservations=reservations if reservations is not None else _reservations(),
        ),
        config=config,
    )


def _reservations() -> tuple[OpenOrderReservation, ...]:
    return (
        OpenOrderReservation(
            order_ref="open-order-1",
            quote_asset=Asset("USDT"),
            order_notional=Decimal("500"),
            fee_buffer=Decimal("0.5"),
        ),
    )
