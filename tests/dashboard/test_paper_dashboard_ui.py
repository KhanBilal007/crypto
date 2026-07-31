from __future__ import annotations

from decimal import Decimal
from http import HTTPStatus
from pathlib import Path

import pytest

from abtp.dashboard import (
    DashboardAction,
    DashboardUIMode,
    PaperDashboardActionError,
    build_default_paper_dashboard_controller,
    dispatch_dashboard_action,
    paper_app,
)
from abtp.dashboard.paper_server import handle_dashboard_request, smoke_test
from abtp.db import connect_database
from abtp.domain import Asset, AssetPair, Exchange, OrderBookLevel, OrderBookSnapshot
from abtp.exchanges import Ticker
from abtp.risk import RiskPolicy


def test_local_dashboard_state_is_paper_safe_and_operator_readable() -> None:
    controller = build_default_paper_dashboard_controller()

    state = controller.state()

    assert state["mode"] == "PAPER MODE"
    assert state["safe_mode"] is True
    assert state["live_trading_enabled"] is False
    assert state["market"]["symbol"] == "BTC/USDT"  # type: ignore[index]
    assert state["strategy"]["recommendation"] == "BUY"  # type: ignore[index]
    assert state["strategy"]["risk_decision"] == "approved"  # type: ignore[index]
    assert state["suggested_paper_trade"]["side"] == "BUY"  # type: ignore[index]
    assert state["suggested_paper_trade"]["reward_to_risk"] == "2"  # type: ignore[index]
    assert state["portfolio"]["starting_balance"] == "10000"  # type: ignore[index]
    assert state["controls"]["can_approve_paper_trade"] is True  # type: ignore[index]
    assert "not financial advice" in state["warning"]


def test_adaptive_view_shell_splits_status_into_role_sections() -> None:
    controller = build_default_paper_dashboard_controller()

    state = controller.state(ui_mode=DashboardUIMode.BEGINNER)

    assert state["ui_mode"] == "beginner"
    assert state["ui"]["trading_mode"] == "paper"  # type: ignore[index]
    assert state["ui"]["live_trading_enabled"] is False  # type: ignore[index]
    views = state["views"]  # type: ignore[assignment]
    assert views["beginner"]["command"]["label"] == "BUY"  # type: ignore[index]
    assert "risk_engine" in views["beginner"]["enabled_modules"]  # type: ignore[index]
    assert "paper_cash" in views["beginner"]["portfolio_summary"]  # type: ignore[index]
    assert views["beginner"]["glossary"][0]["term"] == "Paper mode"  # type: ignore[index]
    assert "backtest_summary" in views["advanced_trader"]  # type: ignore[index]
    assert views["strategy_lab"]["selected_strategy"] == "MinRiskSpotStrategyV1"  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_advanced_trader_view_has_chart_metrics_exit_review_and_exports(tmp_path: Path) -> None:
    controller = build_default_paper_dashboard_controller(
        state_path=str(tmp_path / "paper_dashboard_state.json")
    )

    state = controller.state(ui_mode=DashboardUIMode.ADVANCED_TRADER)
    advanced = state["views"]["advanced_trader"]  # type: ignore[index]

    assert advanced["chart"]["symbol"] == "BTC/USDT"  # type: ignore[index]
    assert len(advanced["chart"]["candles"]) == 4  # type: ignore[index]
    assert advanced["chart"]["risk_lines"]["stop_loss"] != "not_available"  # type: ignore[index]
    assert advanced["backtest_summary"]["sample_size"] == "4"  # type: ignore[index]
    assert "Very small sample" in advanced["backtest_summary"]["sample_size_warning"]  # type: ignore[index]
    assert int(advanced["performance"]["trades"]) >= 1  # type: ignore[arg-type,index]
    assert "recommendation" in advanced["exit_review"]  # type: ignore[index]
    assert advanced["exports"]["transactions_csv"] == "/paper-transactions.csv"  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_adaptive_ui_mode_preference_can_be_saved_locally(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    updated = controller.set_ui_mode(DashboardUIMode.STRATEGY_LAB)
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    assert updated["ui_mode"] == "strategy_lab"
    assert restored["ui_mode"] == "strategy_lab"
    assert restored["live_trading_enabled"] is False


def test_strategy_lab_profile_routes_strategy_specific_evidence(tmp_path: Path) -> None:
    controller = build_default_paper_dashboard_controller(
        state_path=str(tmp_path / "paper_dashboard_state.json")
    )

    state = controller.state(ui_mode=DashboardUIMode.STRATEGY_LAB)
    strategy_lab = state["views"]["strategy_lab"]  # type: ignore[index]

    assert strategy_lab["selection"]["strategy"] == "min_risk_spot_v1"  # type: ignore[index]
    assert strategy_lab["selected_strategy"] == "MinRiskSpotStrategyV1"  # type: ignore[index]
    assert "paper_evaluation_gate" in strategy_lab["enabled_modules"]  # type: ignore[index]
    assert "RSI" in strategy_lab["required_indicators"]  # type: ignore[index]
    assert strategy_lab["recommendation_actionable"] is True  # type: ignore[index]
    assert strategy_lab["compare_runs"][0]["run_id"] == "current_paper"  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_strategy_lab_selection_can_be_saved_without_live_permissions(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    updated = controller.set_strategy_lab_selection(
        strategy="min_risk_spot_v1",
        symbol="BTC/USDT",
        timeframe="4h",
        run_mode="backtest",
        parameter_profile="defensive",
    )
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state(
        ui_mode=DashboardUIMode.STRATEGY_LAB
    )

    updated_lab = updated["views"]["strategy_lab"]  # type: ignore[index]
    restored_lab = restored["views"]["strategy_lab"]  # type: ignore[index]
    assert updated_lab["selection"]["timeframe"] == "4h"  # type: ignore[index]
    assert updated_lab["selection"]["run_mode"] == "backtest"  # type: ignore[index]
    assert updated_lab["recommendation_actionable"] is False  # type: ignore[index]
    assert restored_lab["selection"]["parameter_profile"] == "defensive"  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


def test_local_dashboard_can_use_binance_market_data(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    class FixtureBinanceAdapter:
        def ticker(self, _pair: AssetPair) -> Ticker:
            return Ticker(
                pair=pair,
                price=Decimal("64784.79"),
                captured_at=paper_app.DEFAULT_NOW,
                source_ref="fixture",
            )

        def order_book(self, _pair: AssetPair) -> OrderBookSnapshot:
            return OrderBookSnapshot(
                exchange=Exchange("binance"),
                pair=pair,
                captured_at=paper_app.DEFAULT_NOW,
                bids=(OrderBookLevel(Decimal("64783.99"), Decimal("0.18")),),
                asks=(OrderBookLevel(Decimal("64784.00"), Decimal("5.64")),),
                source_ref="fixture",
            )

        def candles(
            self, _pair: AssetPair, interval: str, _limit: int
        ) -> tuple[paper_app.Candle, ...]:
            closes = ("62841.24", "63813.01", "64460.67", "64784.79")
            return tuple(
                paper_app.Candle(
                    exchange=Exchange("binance"),
                    pair=pair,
                    interval=interval,
                    opened_at=paper_app.DEFAULT_NOW + paper_app.timedelta(hours=index),
                    closed_at=paper_app.DEFAULT_NOW + paper_app.timedelta(hours=index + 1),
                    open=Decimal(close),
                    high=Decimal(close) * Decimal("1.005"),
                    low=Decimal(close) * Decimal("0.995"),
                    close=Decimal(close),
                    volume=Decimal("10"),
                )
                for index, close in enumerate(closes)
            )

    monkeypatch.setattr(paper_app, "BinanceSpotMarketDataAdapter", FixtureBinanceAdapter)

    controller = build_default_paper_dashboard_controller(market_data_source="binance")
    state = controller.state()

    assert state["market"]["source"] == "binance spot"  # type: ignore[index]
    assert state["market"]["current_price"] == "64784.79"  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_binance_daily_trend_blocks_hourly_buy(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    class FixtureBinanceAdapter:
        def order_book(self, _pair: AssetPair) -> OrderBookSnapshot:
            return OrderBookSnapshot(
                exchange=Exchange("binance"),
                pair=pair,
                captured_at=paper_app.DEFAULT_NOW,
                bids=(OrderBookLevel(Decimal("103.99"), Decimal("1")),),
                asks=(OrderBookLevel(Decimal("104.00"), Decimal("1")),),
                source_ref="fixture",
            )

        def candles(
            self, _pair: AssetPair, interval: str, _limit: int
        ) -> tuple[paper_app.Candle, ...]:
            closes = (
                ("100", "101", "102", "104") if interval == "1h" else ("110", "109", "108", "107")
            )
            return tuple(
                paper_app.Candle(
                    exchange=Exchange("binance"),
                    pair=pair,
                    interval=interval,
                    opened_at=paper_app.DEFAULT_NOW + paper_app.timedelta(hours=index),
                    closed_at=paper_app.DEFAULT_NOW + paper_app.timedelta(hours=index + 1),
                    open=Decimal(close),
                    high=Decimal(close) * Decimal("1.005"),
                    low=Decimal(close) * Decimal("0.995"),
                    close=Decimal(close),
                    volume=Decimal("10"),
                )
                for index, close in enumerate(closes)
            )

    monkeypatch.setattr(paper_app, "BinanceSpotMarketDataAdapter", FixtureBinanceAdapter)

    controller = build_default_paper_dashboard_controller(market_data_source="binance")
    state = controller.state()

    assert state["strategy"]["recommendation"] == "HOLD"  # type: ignore[index]
    assert state["strategy"]["risk_decision"] == "not_evaluated"  # type: ignore[index]
    assert state["controls"]["can_approve_paper_trade"] is False  # type: ignore[index]
    assert "1d trend blocks paper buy" in state["strategy"]["explanation"]  # type: ignore[index]
    beginner = state["views"]["beginner"]  # type: ignore[index]
    assert beginner["command"]["label"] == "Do nothing now"  # type: ignore[index]
    assert beginner["command"]["approval_enabled"] is False  # type: ignore[index]
    assert "safest action is to wait" in beginner["reasons"][0]  # type: ignore[index]


def test_approve_button_records_paper_only_operator_approval() -> None:
    controller = build_default_paper_dashboard_controller()
    before = controller.state()

    updated = dispatch_dashboard_action(
        controller,
        DashboardAction.APPROVE_PAPER_TRADE,
        reason="fixture approval",
    )

    assert updated["logs"][0]["event_type"] == "approve_paper_trade"  # type: ignore[index]
    assert "simulated paper trade only" in updated["logs"][0]["message"]  # type: ignore[index]
    assert updated["portfolio"]["open_btc"] != before["portfolio"]["open_btc"]  # type: ignore[index]
    assert updated["portfolio"]["cash"] != before["portfolio"]["cash"]  # type: ignore[index]
    assert updated["transactions"][0]["side"] == "BUY"  # type: ignore[index]
    assert updated["transactions"][0]["quantity"] == "0.01"  # type: ignore[index]
    assert updated["live_trading_enabled"] is False


def test_approved_paper_wallet_can_be_restored(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    updated = dispatch_dashboard_action(
        controller,
        DashboardAction.APPROVE_PAPER_TRADE,
        reason="save fixture approval",
    )
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    assert state_path.exists()
    assert restored["portfolio"]["cash"] == updated["portfolio"]["cash"]  # type: ignore[index]
    assert restored["portfolio"]["open_btc"] == updated["portfolio"]["open_btc"]  # type: ignore[index]
    assert restored["transactions"] == updated["transactions"]
    assert restored["logs"][0]["event_type"] == "paper_state_restored"  # type: ignore[index]


def test_approved_paper_wallet_can_be_restored_from_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "paper_dashboard.sqlite"
    controller = build_default_paper_dashboard_controller(db_path=str(db_path))

    updated = dispatch_dashboard_action(
        controller,
        DashboardAction.APPROVE_PAPER_TRADE,
        reason="sqlite fixture approval",
    )
    restored = build_default_paper_dashboard_controller(db_path=str(db_path)).state()

    connection = connect_database(db_path)
    try:
        snapshot_count = connection.execute(
            "SELECT COUNT(*) FROM paper_account_snapshots"
        ).fetchone()[0]
        transaction_count = connection.execute(
            "SELECT COUNT(*) FROM paper_transactions"
        ).fetchone()[0]
    finally:
        connection.close()

    assert restored["portfolio"]["cash"] == updated["portfolio"]["cash"]  # type: ignore[index]
    assert restored["portfolio"]["open_btc"] == updated["portfolio"]["open_btc"]  # type: ignore[index]
    assert restored["transactions"] == updated["transactions"]
    assert restored["logs"][0]["event_type"] == "paper_state_restored"  # type: ignore[index]
    assert snapshot_count >= 1
    assert transaction_count >= 1
    assert restored["live_trading_enabled"] is False


def test_trader_readiness_gate_checks_views_routes_and_trade_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "paper_dashboard.sqlite"
    controller = build_default_paper_dashboard_controller(db_path=str(db_path))

    state = controller.state(ui_mode=DashboardUIMode.STRATEGY_LAB)
    readiness = state["readiness"]  # type: ignore[assignment]
    checklist = readiness["checklist"]  # type: ignore[index]
    checklist_ids = {item["id"] for item in checklist}  # type: ignore[index]
    routes = readiness["routes"]  # type: ignore[index]
    reconstructability = readiness["trade_reconstructability"]  # type: ignore[index]

    assert readiness["ready"] is True  # type: ignore[index]
    assert readiness["live_trading_enabled"] is False  # type: ignore[index]
    assert readiness["paper_safe"] is True  # type: ignore[index]
    assert readiness["views_checked"] == ["beginner", "advanced_trader", "strategy_lab"]  # type: ignore[index]
    assert {
        "beginner_view_tested",
        "advanced_view_tested",
        "strategy_lab_view_tested",
        "backend_routes_paper_safe",
        "paper_trade_reconstructability",
        "persistence_configured",
    }.issubset(checklist_ids)
    assert all(route["paper_safe"] is True for route in routes)  # type: ignore[index]
    assert all(route["live_order_capability"] is False for route in routes)  # type: ignore[index]
    assert "POST /api/approve-paper-trade" in {route["route"] for route in routes}  # type: ignore[index]
    assert reconstructability["reconstructable"] is True  # type: ignore[index]
    assert {
        "market_data",
        "features",
        "strategy_signal",
        "risk_decision",
        "simulated_fill",
        "account_update",
        "operator_or_audit_action",
    } == {item["id"] for item in reconstructability["checks"]}  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_risk_rejected_recommendation_cannot_be_approved() -> None:
    controller = build_default_paper_dashboard_controller(
        risk_policy=RiskPolicy(kill_switch_active=True)
    )

    state = controller.state()

    assert state["strategy"]["recommendation"] == "REJECTED"  # type: ignore[index]
    assert state["controls"]["can_approve_paper_trade"] is False  # type: ignore[index]
    with pytest.raises(PaperDashboardActionError, match="Risk Management Engine rejected"):
        controller.approve_paper_trade(reason="should fail")


def test_pause_resume_and_emergency_stop_are_paper_controls_only() -> None:
    controller = build_default_paper_dashboard_controller()

    paused = dispatch_dashboard_action(controller, DashboardAction.PAUSE_PAPER_BOT)
    resumed = dispatch_dashboard_action(controller, DashboardAction.RESUME_PAPER_BOT)
    stopped = dispatch_dashboard_action(controller, DashboardAction.EMERGENCY_STOP)
    resume_after_stop = dispatch_dashboard_action(controller, DashboardAction.RESUME_PAPER_BOT)
    reset = dispatch_dashboard_action(controller, DashboardAction.RESET_EMERGENCY_STOP)

    assert paused["controls"]["paused"] is True  # type: ignore[index]
    assert resumed["controls"]["paused"] is False  # type: ignore[index]
    assert stopped["controls"]["kill_switch_active"] is True  # type: ignore[index]
    assert resume_after_stop["controls"]["kill_switch_active"] is True  # type: ignore[index]
    assert "kill switch active:" in resume_after_stop["portfolio"]["risk_halts"][0]  # type: ignore[index]
    assert "operator resumed paper bot" not in resume_after_stop["portfolio"]["risk_halts"][0]  # type: ignore[index]
    assert resume_after_stop["logs"][0]["event_type"] == "resume_blocked"  # type: ignore[index]
    assert reset["controls"]["kill_switch_active"] is False  # type: ignore[index]
    assert "paper kill switch active" not in reset["portfolio"]["risk_halts"]  # type: ignore[index]
    with pytest.raises(PaperDashboardActionError, match="cannot enable live trading"):
        controller.enable_live_trading()


def test_http_adapter_serves_ui_status_report_and_safe_actions() -> None:
    controller = build_default_paper_dashboard_controller()

    page = handle_dashboard_request("GET", "/", b"", controller)
    status = handle_dashboard_request("GET", "/api/status", b"", controller)
    report = handle_dashboard_request("GET", "/paper-report", b"", controller)
    approve = handle_dashboard_request(
        "POST",
        "/api/approve-paper-trade",
        b'{"reason":"fixture approval"}',
        controller,
    )
    reset = handle_dashboard_request(
        "POST",
        "/api/reset-emergency-stop",
        b'{"reason":"fixture reset"}',
        controller,
    )
    csv = handle_dashboard_request("GET", "/paper-transactions.csv", b"", controller)
    strategy_lab = handle_dashboard_request(
        "POST",
        "/api/strategy-lab-selection",
        b'{"strategy":"min_risk_spot_v1","symbol":"BTC/USDT","timeframe":"4h",'
        b'"run_mode":"backtest","parameter_profile":"defensive"}',
        controller,
    )

    assert page.status == HTTPStatus.OK
    assert "ABTP Paper Trading Dashboard" in page.body
    assert 'data-ui-mode="beginner"' in page.body
    assert "localStorage" in page.body
    assert "Paper Transactions" in page.body
    assert "Glossary" in page.body
    assert "beginner_command_label" in page.body
    assert "price_chart" in page.body
    assert "Backtest Summary" in page.body
    assert "Transactions CSV" in page.body
    assert "lab_strategy" in page.body
    assert "Required Evidence" in page.body
    assert "Compare Runs" in page.body
    assert "Readiness Gate" in page.body
    assert status.status == HTTPStatus.OK
    assert '"mode": "PAPER MODE"' in status.body
    assert '"views": {' in status.body
    readiness = handle_dashboard_request("GET", "/api/readiness", b"", controller)
    assert readiness.status == HTTPStatus.OK
    assert '"live_trading_enabled": false' in readiness.body
    assert '"backend_routes_paper_safe"' in readiness.body
    assert '"POST /api/approve-paper-trade"' in readiness.body
    assert report.status == HTTPStatus.OK
    assert "Generated from current local dashboard state" in report.body
    assert "deterministic sandbox fixture" not in report.body
    assert approve.status == HTTPStatus.OK
    assert "approve_paper_trade" in approve.body
    transaction_report = handle_dashboard_request("GET", "/paper-report", b"", controller)
    assert "## Paper Transactions" in transaction_report.body
    assert "0.01 BTC" in transaction_report.body
    assert reset.status == HTTPStatus.OK
    assert csv.status == HTTPStatus.OK
    assert csv.body.startswith("time,side,quantity,price,fee,notional")
    assert strategy_lab.status == HTTPStatus.OK
    assert '"run_mode": "backtest"' in strategy_lab.body
    assert '"live_trading_enabled": false' in strategy_lab.body


def test_http_adapter_saves_adaptive_ui_mode_without_live_trading() -> None:
    controller = build_default_paper_dashboard_controller()

    response = handle_dashboard_request(
        "POST",
        "/api/ui-mode",
        b'{"ui_mode":"strategy_lab"}',
        controller,
    )
    status = handle_dashboard_request("GET", "/api/status", b"", controller)

    assert response.status == HTTPStatus.OK
    assert '"ui_mode": "strategy_lab"' in response.body
    assert '"live_trading_enabled": false' in response.body
    assert '"ui_mode": "strategy_lab"' in status.body


def test_http_adapter_blocks_unsafe_approval_when_risk_rejects() -> None:
    controller = build_default_paper_dashboard_controller(
        risk_policy=RiskPolicy(kill_switch_active=True)
    )

    response = handle_dashboard_request(
        "POST",
        "/api/approve-paper-trade",
        b'{"reason":"fixture approval"}',
        controller,
    )

    assert response.status == HTTPStatus.BAD_REQUEST
    assert "Risk Management Engine rejected" in response.body
    assert '"live_trading_enabled": false' in response.body


def test_dashboard_smoke_command_contract() -> None:
    result = smoke_test()

    assert result["status_code"] == "200"
    assert result["approve_status_code"] == "200"
    assert result["emergency_status_code"] == "200"
    assert result["live_trading_enabled"] == "False"
