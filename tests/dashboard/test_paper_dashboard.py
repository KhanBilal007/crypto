from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.api import PaperParameterHealth, PaperPortfolioStatus, PaperStatusResponse
from abtp.dashboard import build_paper_dashboard, render_paper_dashboard


def test_dashboard_renders_operator_state_without_mutating_api_status() -> None:
    status = _status()

    rendered = render_paper_dashboard(status)

    assert "[Paper State]" in rendered
    assert "BTC price: 104" in rendered
    assert "Regime: trend_up" in rendered
    assert "Blocked: not blocked" in rendered
    assert "Kill switch: False" in rendered
    assert "market.close: trusted (104)" in rendered


def test_dashboard_view_has_expected_panels() -> None:
    view = build_paper_dashboard(_status(paused=True, kill_switch_active=True))

    titles = tuple(panel.title for panel in view.panels)

    assert titles == ("Paper State", "Controls", "Portfolio", "Parameter Health")
    assert "Paused: True" in view.render_text()
    assert "Kill switch: True" in view.render_text()


def _status(
    *,
    paused: bool = False,
    kill_switch_active: bool = False,
) -> PaperStatusResponse:
    return PaperStatusResponse(
        current_btc_price=Decimal("104"),
        active_regime="trend_up",
        latest_signal="buy",
        latest_risk_decision="approved",
        blocked_reason="not blocked",
        data_health="healthy",
        portfolio=PaperPortfolioStatus(
            cash=Decimal("9998"),
            base_quantity=Decimal("0.01"),
            average_entry_price=Decimal("104.104"),
            realized_pnl=Decimal("0"),
            fees_paid=Decimal("0.20"),
            equity=Decimal("9999.04"),
            drawdown_pct=Decimal("0.0001"),
        ),
        parameter_health=(
            PaperParameterHealth(
                key="market.close",
                value="104",
                status="trusted",
                reason="fixture",
            ),
        ),
        paused=paused,
        kill_switch_active=kill_switch_active,
        cycles_count=4,
        trades_count=1,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
