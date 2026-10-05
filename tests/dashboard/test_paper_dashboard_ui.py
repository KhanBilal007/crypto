from __future__ import annotations

import json
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
    assert state["portfolio"]["today_pnl"] == "0.01381588"  # type: ignore[index]
    assert state["portfolio"]["today_pnl_status"] == "calculated"  # type: ignore[index]
    assert len(state["portfolio"]["equity_sparkline"]) >= 4  # type: ignore[index]
    assert state["market"]["price_change_24h_pct"] == "4.00"  # type: ignore[index]
    assert state["market"]["trend_strength_pct"] == "4.00"  # type: ignore[index]
    assert state["market"]["exchange_connection"] == "not_configured"  # type: ignore[index]
    assert state["market"]["latency_ms"] == "10"  # type: ignore[index]
    assert state["notifications"]["count"] == 0  # type: ignore[index]
    assert state["notifications"]["bell_state"] == "clear"  # type: ignore[index]
    assert "version" in state["app"]  # type: ignore[operator]
    assert state["refresh"]["next_check_in_seconds"] >= 0  # type: ignore[index,operator]
    telemetry = state["runtime_telemetry"]  # type: ignore[assignment]
    assert telemetry["module_numbers"] == [  # type: ignore[index]
        "1_24h_price_change_pct",
        "2_trend_strength_pct",
        "3_exchange_connection_status",
        "4_notification_bell_state",
        "5_latency_ms",
        "6_backend_app_version",
        "7_portfolio_sparkline",
        "8_today_pnl",
        "9_next_check_countdown",
    ]
    assert state["controls"]["can_approve_paper_trade"] is True  # type: ignore[index]
    assert "not financial advice" in state["warning"]


def test_dashboard_initial_cash_can_be_overridden_for_fresh_paper_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABTP_PAPER_INITIAL_CASH", "1000")
    monkeypatch.delenv("ABTP_PAPER_STATE_PATH", raising=False)
    monkeypatch.delenv("ABTP_PAPER_DB_PATH", raising=False)

    controller = build_default_paper_dashboard_controller()
    state = controller.state()

    assert state["portfolio"]["starting_balance"] == "1000"  # type: ignore[index]
    assert state["safe_mode"] is True
    assert state["live_trading_enabled"] is False


def test_restored_paper_wallet_uses_restored_equity_as_today_pnl_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ABTP_PAPER_INITIAL_CASH", raising=False)
    monkeypatch.delenv("ABTP_PAPER_DB_PATH", raising=False)
    state_path = tmp_path / "paper_dashboard_state.json"
    state_path.write_text(
        json.dumps(
            {
                "account": {
                    "average_entry_price": "0",
                    "base_quantity": "0",
                    "cash": "1000",
                    "equity_history": ["1000"],
                    "fees_paid": "0",
                    "realized_pnl": "0",
                },
                "trades": [],
            }
        ),
        encoding="utf-8",
    )

    controller = build_default_paper_dashboard_controller(state_path=str(state_path))
    state = controller.state()

    assert state["portfolio"]["starting_balance"] == "1000"  # type: ignore[index]
    assert state["portfolio"]["today_pnl"] == "0"  # type: ignore[index]
    assert state["runtime_telemetry"]["today_pnl"] == "0"  # type: ignore[index]


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
    assert advanced["chart"]["available_timeframes"] == ["1h", "4h", "1d"]  # type: ignore[index]
    assert advanced["chart"]["overlays"] == ["sma_3", "risk_lines", "markers"]  # type: ignore[index]
    assert "horizontal_level" in advanced["chart"]["drawing_tools"]["supported_types"]  # type: ignore[index]
    assert advanced["chart"]["drawing_tools"]["paper_only"] is True  # type: ignore[index]
    assert advanced["chart"]["drawings"] == []  # type: ignore[index]
    assert advanced["chart_drawings"] == []  # type: ignore[index]
    assert {
        "zoom",
        "pan",
        "crosshair",
        "ohlc_tooltip",
        "timeframe_switching",
        "indicator_toggles",
        "responsive_resize",
        "local_drawing_tools",
    }.issubset(set(advanced["chart"]["interaction_features"]))  # type: ignore[index]
    assert advanced["chart"]["risk_lines"]["stop_loss"] != "not_available"  # type: ignore[index]
    assert advanced["backtest_summary"]["sample_size"] == "4"  # type: ignore[index]
    assert "Very small sample" in advanced["backtest_summary"]["sample_size_warning"]  # type: ignore[index]
    assert advanced["backtest_summary"]["status"] == "calculated_paper_sample"  # type: ignore[index]
    assert advanced["backtest_summary"]["metric_status"] == "calculated"  # type: ignore[index]
    assert advanced["backtest_summary"]["win_rate"] == "not_available"  # type: ignore[index]
    assert advanced["backtest_summary"]["expectancy"] == "not_available"  # type: ignore[index]
    assert advanced["backtest_summary"]["closed_trades"] == "0"  # type: ignore[index]
    assert Decimal(str(advanced["backtest_summary"]["sharpe"])) > Decimal("0")  # type: ignore[index]
    assert Decimal(str(advanced["backtest_summary"]["sortino"])) > Decimal("0")  # type: ignore[index]
    assert advanced["backtest_summary"]["profit_factor"] == "not_available"  # type: ignore[index]
    assert advanced["backtest_summary"]["latest_signal_ref"] == "no_signal_ref"  # type: ignore[index]
    assert advanced["performance"]["daily"] == "0.000138158800"  # type: ignore[index]
    assert advanced["performance"]["weekly"] == "0.000138158800"  # type: ignore[index]
    assert advanced["performance"]["monthly"] == "0.000138158800"  # type: ignore[index]
    assert advanced["performance"]["long_term"] == "0.000138158800"  # type: ignore[index]
    assert advanced["performance"]["period_analytics_status"] == "calculated"  # type: ignore[index]
    assert int(advanced["performance"]["trades"]) >= 1  # type: ignore[arg-type,index]
    assert "recommendation" in advanced["exit_review"]  # type: ignore[index]
    assert advanced["exports"]["transactions_csv"] == "/paper-transactions.csv"  # type: ignore[index]
    assert advanced["exports"]["trader_feedback_csv"] == "/trader-feedback.csv"  # type: ignore[index]
    assert advanced["exports"]["trader_handoff"] == "/trader-handoff.md"  # type: ignore[index]
    assert advanced["exports"]["trader_evidence_json"] == "/trader-evidence.json"  # type: ignore[index]
    assert advanced["order_book"]["summary"]["best_bid"] == "103.99"  # type: ignore[index]
    assert advanced["order_book"]["summary"]["best_ask"] == "104.01"  # type: ignore[index]
    assert advanced["order_book"]["summary"]["spread_bps"] == "1.9231"  # type: ignore[index]
    assert advanced["order_book"]["summary"]["bias"] == "balanced"  # type: ignore[index]
    assert len(advanced["order_book"]["bids"]) == 5  # type: ignore[index]
    assert len(advanced["order_book"]["asks"]) == 5  # type: ignore[index]
    assert advanced["order_flow"]["summary"]["trade_count"] == "8"  # type: ignore[index]
    assert advanced["order_flow"]["summary"]["paper_safe"] is True  # type: ignore[index]
    assert advanced["order_flow"]["summary"]["live_order_capability"] is False  # type: ignore[index]
    assert len(advanced["order_flow"]["recent_trades"]) == 8  # type: ignore[index]
    assert len(advanced["order_flow"]["liquidity_heatmap"]) == 10  # type: ignore[index]
    assert advanced["order_ticket"]["paper_only"] is True  # type: ignore[index]
    assert advanced["order_ticket"]["live_order_capability"] is False  # type: ignore[index]
    assert "oco" in advanced["order_ticket"]["supported_order_types"]  # type: ignore[index]
    assert advanced["order_ticket"]["symbol_filters"]["tick_size"] == "0.01"  # type: ignore[index]
    assert advanced["order_ticket"]["symbol_filters"]["step_size"] == "0.0001"  # type: ignore[index]
    assert advanced["order_ticket"]["symbol_filters"]["min_notional"] == "1"  # type: ignore[index]
    assert advanced["watchlist"]["selected_symbol"] == "BTC/USDT"  # type: ignore[index]
    assert advanced["watchlist"]["paper_strategy_symbol"] == "BTC/USDT"  # type: ignore[index]
    assert advanced["watchlist"]["can_paper_trade_selected"] is True  # type: ignore[index]
    assert {item["symbol"] for item in advanced["watchlist"]["symbols"]} == {  # type: ignore[index]
        "BTC/USDT",
        "ETH/USDT",
        "SOL/USDT",
    }
    assert "price_above" in advanced["alerts"]["supported_alert_types"]  # type: ignore[index]
    assert "indicator_confidence" in advanced["alerts"]["supported_alert_types"]  # type: ignore[index]
    assert "drawdown_above" in advanced["alerts"]["supported_alert_types"]  # type: ignore[index]
    assert "stale_data" in advanced["alerts"]["supported_alert_types"]  # type: ignore[index]
    assert "paper_order_event" in advanced["alerts"]["supported_alert_types"]  # type: ignore[index]
    assert advanced["alerts"]["notification_scope"] == "local_dashboard_only"  # type: ignore[index]
    assert advanced["alert_rules"] == []  # type: ignore[index]
    assert advanced["risk_safety"]["paper_only"] is True  # type: ignore[index]
    assert advanced["risk_safety"]["live_order_capability"] is False  # type: ignore[index]
    assert advanced["risk_safety"]["summary"]["safety_state"] == "clear"  # type: ignore[index]
    assert advanced["risk_safety"]["summary"]["latest_risk_decision"] == "approved"  # type: ignore[index]
    assert advanced["risk_safety"]["unsupported_markets"]["live_trading"] is False  # type: ignore[index]
    assert {item["check"] for item in advanced["risk_safety"]["risk_checks"]} >= {  # type: ignore[index]
        "risk_decision",
        "drawdown_halt",
        "data_quality",
        "spread",
    }
    assert {item["check"] for item in advanced["risk_safety"]["exchange_health"]} >= {  # type: ignore[index]
        "market_data_source",
        "order_book",
        "recent_trades",
        "live_execution",
    }
    assert {item["check"] for item in advanced["risk_safety"]["reconciliation"]} >= {  # type: ignore[index]
        "transaction_count",
        "paper_fill_audit",
        "cash_non_negative",
        "open_order_rows",
    }
    assert advanced["trade_journal"]["paper_only"] is True  # type: ignore[index]
    assert advanced["trade_journal"]["summary"]["transactions"] == "2"  # type: ignore[index]
    assert advanced["trade_journal"]["summary"]["journal_entries"] == "0"  # type: ignore[index]
    assert "manual_review" in advanced["trade_journal"]["supported_setup_types"]  # type: ignore[index]
    assert advanced["trade_journal"]["pnl_by_strategy"][0]["strategy"]  # type: ignore[index]
    assert advanced["trade_journal"]["pnl_by_regime"][0]["regime"]  # type: ignore[index]
    assert advanced["trader_feedback"]["summary"]["total"] == "0"  # type: ignore[index]
    assert "order_ticket" in advanced["trader_feedback"]["supported_categories"]  # type: ignore[index]
    assert advanced["open_paper_orders"] == []  # type: ignore[index]
    assert advanced["position"]["has_open_position"] is True  # type: ignore[index]
    assert advanced["position"]["open_btc"] == "0.02"  # type: ignore[index]
    assert advanced["position"]["close_quantity"] == "0.02"  # type: ignore[index]
    assert advanced["position"]["reduce_quantity"] == "0.01"  # type: ignore[index]
    assert advanced["position"]["can_stage_close"] is True  # type: ignore[index]
    assert advanced["position"]["live_order_capability"] is False  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_adaptive_ui_mode_preference_can_be_saved_locally(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    updated = controller.set_ui_mode(DashboardUIMode.STRATEGY_LAB)
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    assert updated["ui_mode"] == "strategy_lab"
    assert restored["ui_mode"] == "strategy_lab"
    assert restored["live_trading_enabled"] is False


def test_reference_ui_shell_backend_metadata_and_preferences_are_paper_safe(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    state = controller.state(ui_mode=DashboardUIMode.BEGINNER)
    navigation = state["ui"]["navigation"]  # type: ignore[index]

    assert {item["key"] for item in navigation} >= {  # type: ignore[index]
        "dashboard",
        "advanced_trader",
        "strategy_lab",
        "backtesting",
        "reports",
        "alerts",
        "logs",
        "settings",
    }
    assert all(item["paper_safe"] is True for item in navigation)  # type: ignore[index]
    assert state["ui"]["sidebar_collapsed"] is False  # type: ignore[index]
    assert state["activity"]["view_all_route"] == "/api/activity"  # type: ignore[index]

    updated = controller.set_ui_shell_preferences(sidebar_collapsed=True)
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    assert updated["ui"]["sidebar_collapsed"] is True  # type: ignore[index]
    assert restored["ui"]["sidebar_collapsed"] is True  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


def test_notification_bell_unread_state_can_be_marked_read() -> None:
    controller = build_default_paper_dashboard_controller()
    controller.add_alert_rule(
        alert_type="price_below",
        symbol="BTC/USDT",
        threshold="105",
    )

    unread = controller.state()
    read = controller.mark_notifications_read()

    assert unread["notifications"]["count"] == 1  # type: ignore[index]
    assert unread["notifications"]["unread_count"] == 1  # type: ignore[index]
    assert unread["notifications"]["bell_state"] == "attention"  # type: ignore[index]
    assert read["notifications"]["count"] == 1  # type: ignore[index]
    assert read["notifications"]["unread_count"] == 0  # type: ignore[index]
    assert read["notifications"]["bell_state"] == "clear"  # type: ignore[index]
    assert read["live_trading_enabled"] is False


def test_activity_read_model_supports_compact_and_view_all_logs() -> None:
    controller = build_default_paper_dashboard_controller()

    initial = controller.activity_state()

    controller.set_ui_mode(DashboardUIMode.STRATEGY_LAB)
    controller.add_alert_rule(alert_type="price_above", symbol="BTC/USDT", threshold="120")
    dispatch_dashboard_action(controller, DashboardAction.REJECT_RECOMMENDATION)
    dispatch_dashboard_action(controller, DashboardAction.PAUSE_PAPER_BOT)

    compact = controller.activity_state(limit=2)
    full = controller.activity_state()

    assert compact["visible_count"] == 2
    assert compact["has_more"] is True
    assert compact["view_all_route"] == "/api/activity"
    assert full["total_count"] >= 3
    assert full["visible_count"] == full["total_count"]
    assert {
        item["event_type"]
        for item in initial["items"]  # type: ignore[index]
    } == {"paper_fill", "latest_signal"}
    assert "smoke" not in " ".join(
        str(item["message"]).lower()
        for item in initial["items"]  # type: ignore[index]
    )
    assert {item["status_label"] for item in full["items"]} >= {"WARN", "INFO"}  # type: ignore[index]
    assert full["paper_only"] is True


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
    assert "confidence_engine" in strategy_lab["required_ai_context_modules"]  # type: ignore[index]
    assert strategy_lab["recommendation_actionable"] is True  # type: ignore[index]
    assert strategy_lab["evidence_request"]["ui_profile"] == "strategy_lab"  # type: ignore[index]
    assert strategy_lab["evidence_request"]["live_execution_requested"] is False  # type: ignore[index]
    assert strategy_lab["routing_decision"]["scope"] == "paper_evidence_only"  # type: ignore[index]
    assert strategy_lab["routing_decision"]["live_execution_enabled"] is False  # type: ignore[index]
    assert strategy_lab["parameter_config"]["minimum_reward_to_risk"] == "2.0"  # type: ignore[index]
    assert {item["evidence"] for item in strategy_lab["evidence_matrix"]} >= {  # type: ignore[index]
        "market_data",
        "indicator_features",
        "risk_decision",
        "order_book_depth",
        "recent_public_trades",
        "backtest_metrics",
    }
    assert all(
        item["status"] == "available"
        for item in strategy_lab["evidence_matrix"]
        if item["required"]
    )  # type: ignore[index]
    assert {item["module"] for item in strategy_lab["module_routing"]} >= {  # type: ignore[index]
        "strategy_profile_registry",
        "paper_trading_engine",
        "risk_engine",
        "paper_evaluation_gate",
    }
    assert len(strategy_lab["compare_runs"]) == 4  # type: ignore[index]
    assert {row["mode"] for row in strategy_lab["compare_runs"]} == {"shadow_paper"}  # type: ignore[index]
    assert {row["strategy_key"] for row in strategy_lab["compare_runs"]} == {  # type: ignore[index]
        "min_risk_spot_v1",
        "trend_pullback_v1",
        "breakout_v1",
        "support_resistance_rebound_v1",
    }
    assert all("sample_size" in row for row in strategy_lab["compare_runs"])  # type: ignore[index]
    assert all(row["completed_backtest"] is False for row in strategy_lab["compare_runs"])  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_strategy_lab_lists_four_shadow_test_strategies(tmp_path: Path) -> None:
    controller = build_default_paper_dashboard_controller(
        state_path=str(tmp_path / "paper_dashboard_state.json")
    )

    state = controller.state(ui_mode=DashboardUIMode.STRATEGY_LAB)
    strategy_lab = state["views"]["strategy_lab"]  # type: ignore[index]
    selectors = strategy_lab["selectors"]  # type: ignore[index]
    strategy_values = {item["value"] for item in selectors["strategies"]}  # type: ignore[index]
    compare_runs = strategy_lab["compare_runs"]  # type: ignore[index]

    assert strategy_values == {
        "min_risk_spot_v1",
        "trend_pullback_v1",
        "breakout_v1",
        "support_resistance_rebound_v1",
    }
    assert strategy_lab["shadow_test"]["account_count"] == "4"  # type: ignore[index]
    assert {row["strategy_key"] for row in compare_runs} == strategy_values  # type: ignore[index]
    assert all(row["mode"] == "shadow_paper" for row in compare_runs)  # type: ignore[index]
    assert all("risk_score" in row for row in compare_runs)  # type: ignore[index]
    assert [row["strategy_key"] for row in compare_runs if row["selected"]] == [  # type: ignore[index]
        "min_risk_spot_v1"
    ]


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
    assert all(row["selected"] is False for row in updated_lab["compare_runs"])  # type: ignore[index]
    assert updated_lab["parameter_config"]["minimum_reward_to_risk"] == "2.5"  # type: ignore[index]
    assert restored_lab["selection"]["parameter_profile"] == "defensive"  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


def test_watchlist_symbol_selection_is_read_only_and_persistent(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    updated = controller.set_watchlist_symbol("ETH/USDT")
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state(
        ui_mode=DashboardUIMode.ADVANCED_TRADER
    )

    advanced = updated["views"]["advanced_trader"]  # type: ignore[index]
    restored_advanced = restored["views"]["advanced_trader"]  # type: ignore[index]
    assert updated["market"]["symbol"] == "ETH/USDT"  # type: ignore[index]
    assert updated["market"]["paper_strategy_symbol"] == "BTC/USDT"  # type: ignore[index]
    assert updated["market"]["paper_tradable"] is False  # type: ignore[index]
    assert updated["portfolio"]["mark_symbol"] == "BTC/USDT"  # type: ignore[index]
    assert updated["portfolio"]["mark_price"] == "104"  # type: ignore[index]
    assert updated["portfolio"]["current_equity"] == str(  # type: ignore[index]
        controller.engine.account.equity(Decimal("104"))
    )
    assert updated["portfolio"]["unrealized_pnl"] == str(  # type: ignore[index]
        (Decimal("104") - controller.engine.account.state.average_entry_price)
        * controller.engine.account.state.base_quantity
    )
    assert advanced["watchlist"]["selected_symbol"] == "ETH/USDT"  # type: ignore[index]
    assert advanced["watchlist"]["can_paper_trade_selected"] is False  # type: ignore[index]
    assert advanced["watchlist"]["active_paper_symbols"] == ["BTC/USDT"]  # type: ignore[index]
    assert "ETH/USDT" in advanced["watchlist"]["read_only_symbols"]  # type: ignore[index]
    assert restored_advanced["watchlist"]["selected_symbol"] == "ETH/USDT"  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


def test_local_alert_rules_trigger_and_restore(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    price_alert = controller.add_alert_rule(
        alert_type="price_above",
        symbol="BTC/USDT",
        threshold="103",
    )
    recommendation_alert = controller.add_alert_rule(
        alert_type="recommendation",
        symbol="BTC/USDT",
        expected_value="BUY",
    )
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state(
        ui_mode=DashboardUIMode.ADVANCED_TRADER
    )

    triggered = price_alert["views"]["advanced_trader"]["alerts"]["triggered"]  # type: ignore[index]
    rec_triggered = recommendation_alert["views"]["advanced_trader"]["alerts"]["triggered"]  # type: ignore[index]
    restored_rules = restored["views"]["advanced_trader"]["alert_rules"]  # type: ignore[index]
    assert triggered[0]["alert_type"] == "price_above"  # type: ignore[index]
    assert any(item["alert_type"] == "recommendation" for item in rec_triggered)  # type: ignore[index]
    assert len(restored_rules) == 2
    assert restored["live_trading_enabled"] is False


def test_local_alert_rule_can_be_deleted() -> None:
    controller = build_default_paper_dashboard_controller()
    state = controller.add_alert_rule(
        alert_type="price_below",
        symbol="BTC/USDT",
        threshold="105",
    )
    rule = state["views"]["advanced_trader"]["alert_rules"][0]  # type: ignore[index]

    updated = controller.delete_alert_rule(alert_id=str(rule["alert_id"]))  # type: ignore[index]

    assert updated["views"]["advanced_trader"]["alert_rules"] == []  # type: ignore[index]
    assert updated["logs"][0]["event_type"] == "delete_alert_rule"  # type: ignore[index]
    assert updated["live_trading_enabled"] is False


def test_advanced_alert_types_trigger_for_dashboard_evidence() -> None:
    controller = build_default_paper_dashboard_controller()
    controller.watchlist = (
        paper_app.DashboardWatchlistItem(
            symbol="BTC/USDT",
            price=Decimal("104"),
            source="fixture",
            updated_at=paper_app.DEFAULT_NOW,
            data_health="degraded",
            paper_tradable=True,
            note="fixture degraded data",
        ),
    )

    controller.add_alert_rule(
        alert_type="indicator_confidence",
        symbol="BTC/USDT",
        threshold="0.50",
    )
    controller.add_alert_rule(
        alert_type="drawdown_above",
        symbol="BTC/USDT",
        threshold="0",
    )
    controller.add_alert_rule(alert_type="stale_data", symbol="BTC/USDT")
    controller.add_alert_rule(
        alert_type="paper_order_event",
        symbol="BTC/USDT",
        expected_value="submit_paper_order_ticket",
    )
    state = controller.submit_paper_order_ticket(
        order_type="limit",
        side="buy",
        quantity="0.01",
        limit_price="101",
    )

    triggered = state["views"]["advanced_trader"]["alerts"]["triggered"]  # type: ignore[index]
    triggered_types = {item["alert_type"] for item in triggered}  # type: ignore[index]
    assert {
        "indicator_confidence",
        "drawdown_above",
        "stale_data",
        "paper_order_event",
    }.issubset(triggered_types)
    assert state["views"]["advanced_trader"]["alerts"]["notification_scope"] == (  # type: ignore[index]
        "local_dashboard_only"
    )
    assert state["live_trading_enabled"] is False


def test_trade_journal_entries_update_analytics_and_restore(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))
    transaction = controller.state()["transactions"][0]  # type: ignore[index]

    updated = controller.save_journal_entry(
        trade_ref=str(transaction["trade_ref"]),  # type: ignore[index]
        symbol="BTC/USDT",
        setup_type="pullback",
        tags="patience, good entry",
        notes="Waited for confirmation.",
        mistake_review="No execution mistake.",
        lesson="Keep the confirmation checklist visible.",
        chart_context="BTC/USDT 1h close above SMA",
    )
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    journal = updated["views"]["advanced_trader"]["trade_journal"]  # type: ignore[index]
    restored_journal = restored["views"]["advanced_trader"]["trade_journal"]  # type: ignore[index]
    assert journal["summary"]["journal_entries"] == "1"  # type: ignore[index]
    assert journal["summary"]["mistakes_logged"] == "1"  # type: ignore[index]
    assert journal["tag_breakdown"][0]["tag"] == "good_entry"  # type: ignore[index]
    assert journal["entries"][0]["setup_type"] == "pullback"  # type: ignore[index]
    assert journal["entries"][0]["paper_only"] is True  # type: ignore[index]
    assert restored_journal["summary"]["journal_entries"] == "1"  # type: ignore[index]
    assert restored_journal["entries"][0]["notes"] == "Waited for confirmation."  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


def test_trade_journal_entry_can_be_deleted() -> None:
    controller = build_default_paper_dashboard_controller()
    updated = controller.save_journal_entry(
        symbol="BTC/USDT",
        setup_type="manual_review",
        tags="review",
        notes="Quick note.",
    )
    entry = updated["views"]["advanced_trader"]["trade_journal"]["entries"][0]  # type: ignore[index]

    deleted = controller.delete_journal_entry(journal_id=str(entry["journal_id"]))  # type: ignore[index]

    journal = deleted["views"]["advanced_trader"]["trade_journal"]  # type: ignore[index]
    assert journal["entries"] == []  # type: ignore[index]
    assert journal["summary"]["journal_entries"] == "0"  # type: ignore[index]
    assert deleted["logs"][0]["event_type"] == "delete_journal_entry"  # type: ignore[index]


def test_trader_feedback_updates_summary_closes_and_restores(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    updated = controller.save_trader_feedback(
        reviewer_role="trader",
        category="order_ticket",
        severity="high",
        summary="Make paper-only status impossible to miss.",
        recommendation="Repeat paper-only wording inside the submit area.",
    )
    feedback = updated["views"]["advanced_trader"]["trader_feedback"]  # type: ignore[index]
    feedback_id = feedback["items"][0]["feedback_id"]  # type: ignore[index]
    closed = controller.close_trader_feedback(
        feedback_id=str(feedback_id),
        resolution="Added stronger paper-only copy near submit.",
    )
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    assert feedback["summary"]["total"] == "1"  # type: ignore[index]
    assert feedback["summary"]["open"] == "1"  # type: ignore[index]
    assert feedback["items"][0]["category"] == "order_ticket"  # type: ignore[index]
    assert closed["views"]["advanced_trader"]["trader_feedback"]["summary"]["closed"] == "1"  # type: ignore[index]
    assert restored["views"]["advanced_trader"]["trader_feedback"]["items"][0]["status"] == "closed"  # type: ignore[index]
    assert restored["views"]["advanced_trader"]["trader_feedback"]["items"][0]["resolution"]  # type: ignore[index]
    assert restored["logs"][0]["event_type"] == "paper_state_restored"  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


def test_chart_drawings_save_delete_and_restore(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))
    chart = controller.state()["views"]["advanced_trader"]["chart"]  # type: ignore[index]
    candles = chart["candles"]  # type: ignore[index]

    updated = controller.save_chart_drawing(
        drawing_type="trendline",
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=str(candles[0]["time"]),  # type: ignore[index]
        end_time=str(candles[-1]["time"]),  # type: ignore[index]
        start_price="101",
        end_price="104",
        text="trend support",
        color="#0f7b52",
    )
    drawing = updated["views"]["advanced_trader"]["chart"]["drawings"][0]  # type: ignore[index]
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    assert drawing["drawing_type"] == "trendline"  # type: ignore[index]
    assert drawing["paper_only"] is True  # type: ignore[index]
    assert restored["views"]["advanced_trader"]["chart"]["drawings"][0]["text"] == "trend support"  # type: ignore[index]
    deleted = controller.delete_chart_drawing(drawing_id=str(drawing["drawing_id"]))  # type: ignore[index]
    assert deleted["views"]["advanced_trader"]["chart"]["drawings"] == []  # type: ignore[index]
    assert deleted["logs"][0]["event_type"] == "delete_chart_drawing"  # type: ignore[index]


def test_local_dashboard_can_use_binance_market_data(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    class FixtureBinanceAdapter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def ticker(self, _pair: AssetPair) -> Ticker:
            return Ticker(
                pair=pair,
                price=Decimal("64784.79"),
                captured_at=paper_app.DEFAULT_NOW,
                source_ref="fixture",
            )

        def price_change_24h_pct(self, _pair: AssetPair) -> Decimal:
            return Decimal("1.23")

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
    assert state["market"]["price_change_24h_pct"] == "1.23"  # type: ignore[index]
    assert state["market"]["exchange_connection"] == "connected"  # type: ignore[index]
    assert state["live_trading_enabled"] is False


def test_binance_market_data_refreshes_while_dashboard_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    class RefreshingFixtureBinanceAdapter:
        ticker_call_count = 0

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def ticker(self, active_pair: AssetPair) -> Ticker:
            type(self).ticker_call_count += 1
            offset = Decimal(type(self).ticker_call_count)
            captured_at = paper_app.DEFAULT_NOW + paper_app.timedelta(
                seconds=type(self).ticker_call_count
            )
            return Ticker(
                pair=active_pair,
                price=Decimal("64784.79") + offset,
                captured_at=captured_at,
                source_ref="fixture-refresh",
            )

        def price_change_24h_pct(self, _pair: AssetPair) -> Decimal:
            return Decimal("2.50")

        def order_book(self, _pair: AssetPair) -> OrderBookSnapshot:
            return OrderBookSnapshot(
                exchange=Exchange("binance"),
                pair=pair,
                captured_at=paper_app.DEFAULT_NOW,
                bids=(OrderBookLevel(Decimal("64783.99"), Decimal("0.18")),),
                asks=(OrderBookLevel(Decimal("64784.00"), Decimal("5.64")),),
                source_ref="fixture-refresh",
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

    monkeypatch.setattr(paper_app, "BinanceSpotMarketDataAdapter", RefreshingFixtureBinanceAdapter)

    controller = build_default_paper_dashboard_controller(market_data_source="binance")
    controller.market_refresh_interval_seconds = 0
    first = controller.state()
    second = controller.state()

    assert first["market"]["source"] == "binance spot"  # type: ignore[index]
    assert first["market"]["current_price"] != second["market"]["current_price"]  # type: ignore[index]
    assert first["market"]["updated_at"] != second["market"]["updated_at"]  # type: ignore[index]
    assert second["live_trading_enabled"] is False


def test_binance_daily_trend_blocks_hourly_buy(monkeypatch: pytest.MonkeyPatch) -> None:
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    class FixtureBinanceAdapter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

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
    assert state["suggested_paper_trade"]["stop_loss"] == "not_executable"  # type: ignore[index]
    assert state["suggested_paper_trade"]["target"] == "not_executable"  # type: ignore[index]
    assert state["suggested_paper_trade"]["reward_to_risk"] == "not_executable"  # type: ignore[index]
    assert "observation only" in state["strategy"]["explanation"]  # type: ignore[index]
    latest = controller.engine.cycles[-1]
    evaluation = controller.engine.strategy.evaluate(
        paper_app.StrategyContext(
            features=latest.features,
            generated_at=latest.snapshot.received_at,
            timeframe="1h",
            regime=latest.regime,
        )
    )
    assert "1d trend blocks paper buy" in evaluation.reasons[0]
    assert not controller.engine.account.trades
    assert all(not engine.account.trades for engine in controller.shadow_engines.values())
    advanced = state["views"]["advanced_trader"]  # type: ignore[index]
    assert advanced["chart"]["risk_lines"]["stop_loss"] == "not_available"  # type: ignore[index]
    assert advanced["chart"]["risk_lines"]["target"] == "not_available"  # type: ignore[index]
    assert advanced["position"]["stop_loss"] == "not_available"  # type: ignore[index]
    assert advanced["position"]["target"] == "not_available"  # type: ignore[index]
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


def test_advanced_paper_order_ticket_stages_and_cancels_without_changing_cash() -> None:
    controller = build_default_paper_dashboard_controller()
    before = controller.state()

    staged = controller.submit_paper_order_ticket(
        order_type="limit",
        side="buy",
        quantity="0.02",
        limit_price="101.50",
        reason="fixture staged limit",
    )
    advanced = staged["views"]["advanced_trader"]  # type: ignore[index]
    open_order = advanced["open_paper_orders"][0]  # type: ignore[index]
    canceled = controller.cancel_paper_order(
        order_id=str(open_order["order_id"]),  # type: ignore[index]
        reason="fixture cancel",
    )

    assert staged["portfolio"]["cash"] == before["portfolio"]["cash"]  # type: ignore[index]
    assert open_order["order_type"] == "limit"  # type: ignore[index]
    assert open_order["side"] == "buy"  # type: ignore[index]
    assert open_order["quantity"] == "0.02"  # type: ignore[index]
    assert open_order["limit_price"] == "101.50"  # type: ignore[index]
    assert open_order["paper_only"] is True  # type: ignore[index]
    assert staged["logs"][0]["event_type"] == "submit_paper_order_ticket"  # type: ignore[index]
    assert canceled["views"]["advanced_trader"]["open_paper_orders"] == []  # type: ignore[index]
    assert canceled["portfolio"]["cash"] == before["portfolio"]["cash"]  # type: ignore[index]
    assert canceled["logs"][0]["event_type"] == "cancel_paper_order"  # type: ignore[index]
    assert canceled["live_trading_enabled"] is False


def test_paper_order_ticket_validates_required_prices() -> None:
    controller = build_default_paper_dashboard_controller()

    with pytest.raises(PaperDashboardActionError, match="limit paper order requires limit price"):
        controller.submit_paper_order_ticket(
            order_type="limit",
            side="buy",
            quantity="0.01",
        )
    with pytest.raises(PaperDashboardActionError, match="OCO paper order requires"):
        controller.submit_paper_order_ticket(
            order_type="oco",
            side="sell",
            quantity="0.01",
            stop_price="100",
        )


def test_paper_order_ticket_validates_binance_style_filters() -> None:
    controller = build_default_paper_dashboard_controller()

    with pytest.raises(PaperDashboardActionError, match="step_size"):
        controller.submit_paper_order_ticket(
            order_type="limit",
            side="buy",
            quantity="0.01005",
            limit_price="101.50",
        )
    with pytest.raises(PaperDashboardActionError, match="tick_size"):
        controller.submit_paper_order_ticket(
            order_type="limit",
            side="buy",
            quantity="0.02",
            limit_price="101.505",
        )
    with pytest.raises(PaperDashboardActionError, match="min_notional"):
        controller.submit_paper_order_ticket(
            order_type="market",
            side="buy",
            quantity="0.001",
        )


def test_position_panel_stages_close_and_reduce_as_paper_sell_orders() -> None:
    controller = build_default_paper_dashboard_controller()
    before = controller.state()

    close_state = controller.stage_close_position(reason="fixture close review")
    close_order = close_state["views"]["advanced_trader"]["open_paper_orders"][0]  # type: ignore[index]
    reduce_state = controller.stage_reduce_position(reason="fixture reduce review")
    reduce_order = reduce_state["views"]["advanced_trader"]["open_paper_orders"][0]  # type: ignore[index]

    assert close_order["order_type"] == "market"  # type: ignore[index]
    assert close_order["side"] == "sell"  # type: ignore[index]
    assert close_order["quantity"] == "0.02"  # type: ignore[index]
    assert reduce_order["order_type"] == "market"  # type: ignore[index]
    assert reduce_order["side"] == "sell"  # type: ignore[index]
    assert reduce_order["quantity"] == "0.01"  # type: ignore[index]
    assert reduce_state["portfolio"]["cash"] == before["portfolio"]["cash"]  # type: ignore[index]
    assert reduce_state["portfolio"]["open_btc"] == before["portfolio"]["open_btc"]  # type: ignore[index]
    assert reduce_state["logs"][0]["event_type"] == "submit_paper_order_ticket"  # type: ignore[index]
    assert reduce_state["live_trading_enabled"] is False


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


def test_staged_paper_orders_can_be_restored(tmp_path: Path) -> None:
    state_path = tmp_path / "paper_dashboard_state.json"
    controller = build_default_paper_dashboard_controller(state_path=str(state_path))

    staged = controller.submit_paper_order_ticket(
        order_type="oco",
        side="sell",
        quantity="0.02",
        stop_price="99",
        take_profit_price="110",
        reason="fixture staged oco",
    )
    restored = build_default_paper_dashboard_controller(state_path=str(state_path)).state()

    staged_orders = staged["views"]["advanced_trader"]["open_paper_orders"]  # type: ignore[index]
    restored_orders = restored["views"]["advanced_trader"]["open_paper_orders"]  # type: ignore[index]
    assert restored_orders == staged_orders
    assert restored_orders[0]["order_type"] == "oco"  # type: ignore[index]
    assert restored["live_trading_enabled"] is False


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
    verdict = readiness["trader_verdict"]  # type: ignore[index]

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
    assert "GET /api/activity" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/ui-shell" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/mark-notifications-read" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/approve-paper-trade" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/paper-order-ticket" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/cancel-paper-order" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/stage-close-position" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/stage-reduce-position" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/watchlist-symbol" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/alert-rule" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/delete-alert-rule" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/journal-entry" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/delete-journal-entry" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/trader-feedback" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/close-trader-feedback" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/chart-drawing" in {route["route"] for route in routes}  # type: ignore[index]
    assert "POST /api/delete-chart-drawing" in {route["route"] for route in routes}  # type: ignore[index]
    assert "GET /trader-handoff.md" in {route["route"] for route in routes}  # type: ignore[index]
    assert "GET /trader-evidence.json" in {route["route"] for route in routes}  # type: ignore[index]
    assert "GET /trader-feedback.csv" in {route["route"] for route in routes}  # type: ignore[index]
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
    assert verdict["paper_demo_ready"] is True
    assert verdict["live_capital_ready"] is False
    assert verdict["profitability_claim"] == "none"
    assert verdict["shareable_scope"] == "paper-mode trader review only"
    assert verdict["blockers"] == []
    assert "Strategy Lab exposes required evidence" in " ".join(verdict["proof_points"])
    assert "does not prove profitability" in " ".join(verdict["warnings"])
    assert state["live_trading_enabled"] is False


def test_open_blocker_trader_feedback_blocks_paper_demo_readiness(tmp_path: Path) -> None:
    db_path = tmp_path / "paper_dashboard.sqlite"
    controller = build_default_paper_dashboard_controller(db_path=str(db_path))

    blocked = controller.save_trader_feedback(
        reviewer_role="trader",
        category="risk",
        severity="blocker",
        summary="Risk panel needs clearer halt wording.",
        recommendation="Clarify halt state before sharing the demo.",
    )
    feedback_id = blocked["views"]["advanced_trader"]["trader_feedback"]["items"][0][  # type: ignore[index]
        "feedback_id"
    ]
    with pytest.raises(PaperDashboardActionError, match="requires a resolution note"):
        controller.close_trader_feedback(feedback_id=str(feedback_id))

    closed = controller.close_trader_feedback(
        feedback_id=str(feedback_id),
        resolution="Updated halt wording in the risk panel.",
    )

    blocked_readiness = blocked["readiness"]  # type: ignore[assignment]
    blocked_verdict = blocked_readiness["trader_verdict"]  # type: ignore[index]
    closed_readiness = closed["readiness"]  # type: ignore[assignment]
    closed_verdict = closed_readiness["trader_verdict"]  # type: ignore[index]

    assert blocked_readiness["ready"] is False  # type: ignore[index]
    assert blocked_verdict["paper_demo_ready"] is False
    assert blocked_verdict["shareable_scope"] == "internal testing until blockers are fixed"
    assert "Open trader feedback blocker" in " ".join(blocked_verdict["blockers"])
    assert "open_trader_feedback_blockers" in {
        item["id"]
        for item in blocked_readiness["checklist"]  # type: ignore[index]
    }
    assert closed_readiness["ready"] is True  # type: ignore[index]
    assert closed_verdict["paper_demo_ready"] is True
    assert closed_verdict["blockers"] == []
    assert closed["live_trading_enabled"] is False


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
    handoff = handle_dashboard_request("GET", "/trader-handoff.md", b"", controller)
    evidence = handle_dashboard_request("GET", "/trader-evidence.json", b"", controller)
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
    feedback_csv_before = handle_dashboard_request("GET", "/trader-feedback.csv", b"", controller)
    strategy_lab = handle_dashboard_request(
        "POST",
        "/api/strategy-lab-selection",
        b'{"strategy":"min_risk_spot_v1","symbol":"BTC/USDT","timeframe":"4h",'
        b'"run_mode":"backtest","parameter_profile":"defensive"}',
        controller,
    )
    watchlist_symbol = handle_dashboard_request(
        "POST",
        "/api/watchlist-symbol",
        b'{"symbol":"SOL/USDT"}',
        controller,
    )
    alert_rule = handle_dashboard_request(
        "POST",
        "/api/alert-rule",
        b'{"alert_type":"price_above","symbol":"BTC/USDT","threshold":"103"}',
        controller,
    )
    journal_entry = handle_dashboard_request(
        "POST",
        "/api/journal-entry",
        b'{"symbol":"BTC/USDT","setup_type":"pullback","tags":"review","notes":"fixture journal"}',
        controller,
    )
    trader_feedback = handle_dashboard_request(
        "POST",
        "/api/trader-feedback",
        b'{"reviewer_role":"trader","category":"order_ticket","severity":"high",'
        b'"summary":"paper ticket needs clearer label","recommendation":"repeat paper-only"}',
        controller,
    )
    feedback_state = json.loads(trader_feedback.body)
    feedback_id = feedback_state["views"]["advanced_trader"]["trader_feedback"]["items"][0][
        "feedback_id"
    ]
    close_feedback = handle_dashboard_request(
        "POST",
        "/api/close-trader-feedback",
        json.dumps(
            {
                "feedback_id": feedback_id,
                "resolution": "Added paper-only submit copy.",
            }
        ).encode("utf-8"),
        controller,
    )
    feedback_csv_after = handle_dashboard_request("GET", "/trader-feedback.csv", b"", controller)
    chart_drawing = handle_dashboard_request(
        "POST",
        "/api/chart-drawing",
        b'{"drawing_type":"horizontal_level","symbol":"BTC/USDT","timeframe":"1h",'
        b'"start_price":"104","text":"fixture level","color":"#1264a3"}',
        controller,
    )
    paper_order = handle_dashboard_request(
        "POST",
        "/api/paper-order-ticket",
        b'{"order_type":"limit","side":"buy","quantity":"0.01","limit_price":"101"}',
        controller,
    )
    close_position = handle_dashboard_request(
        "POST",
        "/api/stage-close-position",
        b'{"reason":"fixture close"}',
        controller,
    )
    ui_shell = handle_dashboard_request(
        "POST",
        "/api/ui-shell",
        b'{"sidebar_collapsed":true}',
        controller,
    )
    activity = handle_dashboard_request("GET", "/api/activity?limit=2", b"", controller)
    notifications_read = handle_dashboard_request(
        "POST",
        "/api/mark-notifications-read",
        b"",
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
    assert "chart_timeframes" in page.body
    assert "chart_indicators" in page.body
    assert "chart_tooltip" in page.body
    assert "chart_readout" in page.body
    assert 'data-chart-overlay="sma_3"' in page.body
    assert "updateChartTooltip" in page.body
    assert "aggregateCandles" in page.body
    assert "drawing_type" in page.body
    assert "saveChartDrawing" in page.body
    assert "deleteChartDrawing" in page.body
    assert "Order Book / Market Depth" in page.body
    assert "order_book" in page.body
    assert "renderOrderBook" in page.body
    assert "depth-price-bid" in page.body
    assert "Order Flow / Recent Trades" in page.body
    assert "order_flow" in page.body
    assert "renderOrderFlow" in page.body
    assert "renderLiquidityHeatmap" in page.body
    assert "Paper Order Ticket" in page.body
    assert "Open Paper Orders" in page.body
    assert "ticket_order_type" in page.body
    assert "ticket_filters" in page.body
    assert "submitPaperOrderTicket" in page.body
    assert "setInterval(load, 15000)" in page.body
    assert "cancelPaperOrder" in page.body
    assert "Paper Position" in page.body
    assert "stage_close_position" in page.body
    assert "stage_reduce_position" in page.body
    assert "Watchlist" in page.body
    assert "watchlist" in page.body
    assert "saveWatchlistSymbol" in page.body
    assert "Alerts" in page.body
    assert "alert_type" in page.body
    assert "addAlertRule" in page.body
    assert "deleteAlertRule" in page.body
    assert "Risk &amp; Safety" in page.body or "Risk & Safety" in page.body
    assert "risk_safety_summary" in page.body
    assert "renderRiskSafety" in page.body
    assert "Trade Journal Analytics" in page.body
    assert "journal_setup_type" in page.body
    assert "saveJournalEntry" in page.body
    assert "deleteJournalEntry" in page.body
    assert "Trader Feedback" in page.body
    assert "saveTraderFeedback" in page.body
    assert "closeTraderFeedback" in page.body
    assert "Backtest Summary" in page.body
    assert "Transactions CSV" in page.body
    assert "Feedback CSV" in page.body
    assert "Trader Handoff" in page.body
    assert "Evidence JSON" in page.body
    assert "lab_strategy" in page.body
    assert "Required Evidence" in page.body
    assert "Evidence Matrix" in page.body
    assert "Module Routing" in page.body
    assert "Parameter Config" in page.body
    assert "Compare Runs" in page.body
    assert "Paper P/L" in page.body
    assert "Latest Signal" in page.body
    assert "Risk Score" in page.body
    assert "Max Drawdown" in page.body
    assert "Readiness Gate" in page.body
    assert "paper demo ready" in page.body
    assert "live capital ready" in page.body
    assert "Proof Points" in page.body
    assert "profitability claim" in page.body
    assert "Runtime Telemetry" in page.body
    assert 'class="topbar"' in page.body
    assert "notification_bell" in page.body
    assert "why_list" in page.body
    assert "portfolio-grid" in page.body
    assert "control-tiles" in page.body
    assert "activity-timeline" in page.body
    assert "strip_change_24h" in page.body
    assert "strip_trend_strength" in page.body
    assert "strip_connection" in page.body
    assert "strip_notifications" in page.body
    assert "strip_next_check" in page.body
    assert status.status == HTTPStatus.OK
    assert '"mode": "PAPER MODE"' in status.body
    assert '"views": {' in status.body
    assert '"runtime_telemetry": {' in status.body
    assert '"price_change_24h_pct": "4.00"' in status.body
    assert '"navigation": [' in status.body
    assert '"activity": {' in status.body
    readiness = handle_dashboard_request("GET", "/api/readiness", b"", controller)
    assert readiness.status == HTTPStatus.OK
    assert '"live_trading_enabled": false' in readiness.body
    assert '"backend_routes_paper_safe"' in readiness.body
    assert '"GET /api/activity"' in readiness.body
    assert '"POST /api/ui-shell"' in readiness.body
    assert '"POST /api/mark-notifications-read"' in readiness.body
    assert '"POST /api/approve-paper-trade"' in readiness.body
    assert report.status == HTTPStatus.OK
    assert "Generated from current local dashboard state" in report.body
    assert "deterministic sandbox fixture" not in report.body
    assert "## Trader Readiness Verdict" in report.body
    assert "Paper demo ready" in report.body
    assert "Live capital ready" in report.body
    assert "Profitability claim" in report.body
    assert "internal testing until blockers are fixed" in report.body
    assert handoff.status == HTTPStatus.OK
    assert handoff.content_type == "text/markdown; charset=utf-8"
    assert "# ABTP Trader Review Handoff" in handoff.body
    assert "paper-mode trader review only" in handoff.body
    assert "Suggested Trader Questions" in handoff.body
    assert "Live capital ready" in handoff.body
    assert evidence.status == HTTPStatus.OK
    assert evidence.content_type == "application/json; charset=utf-8"
    evidence_payload = json.loads(evidence.body)
    assert evidence_payload["export_kind"] == "trader_evidence_bundle"
    assert evidence_payload["live_trading_enabled"] is False
    assert evidence_payload["readiness"]["trader_verdict"]["live_capital_ready"] is False
    assert "order_book_summary" in evidence_payload["advanced_evidence"]
    assert "trader_feedback_summary" in evidence_payload["advanced_evidence"]
    assert "trader_feedback_items" in evidence_payload["advanced_evidence"]
    assert "evidence_matrix" in evidence_payload["strategy_lab_evidence"]
    assert evidence_payload["strategy_lab_evidence"]["selected_strategy"] == "MinRiskSpotStrategyV1"
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
    assert watchlist_symbol.status == HTTPStatus.OK
    assert '"symbol": "SOL/USDT"' in watchlist_symbol.body
    assert '"paper_strategy_symbol": "BTC/USDT"' in watchlist_symbol.body
    assert alert_rule.status == HTTPStatus.OK
    assert "price_above" in alert_rule.body
    assert "local_dashboard_only" in alert_rule.body
    assert journal_entry.status == HTTPStatus.OK
    assert "trade_journal" in journal_entry.body
    assert "fixture journal" in journal_entry.body
    assert trader_feedback.status == HTTPStatus.OK
    assert "paper ticket needs clearer label" in trader_feedback.body
    assert close_feedback.status == HTTPStatus.OK
    assert '"status": "closed"' in close_feedback.body
    assert feedback_csv_before.status == HTTPStatus.OK
    assert feedback_csv_before.body.startswith(
        "feedback_id,created_at,resolved_at,reviewer_role,category,severity,status,"
        "summary,recommendation,resolution"
    )
    assert feedback_csv_after.status == HTTPStatus.OK
    assert "paper ticket needs clearer label" in feedback_csv_after.body
    assert "repeat paper-only" in feedback_csv_after.body
    assert "Added paper-only submit copy." in feedback_csv_after.body
    assert chart_drawing.status == HTTPStatus.OK
    assert "fixture level" in chart_drawing.body
    assert "chart_drawings" in chart_drawing.body
    assert paper_order.status == HTTPStatus.OK
    assert "submit_paper_order_ticket" in paper_order.body
    assert '"open_paper_orders": [' in paper_order.body
    assert close_position.status == HTTPStatus.OK
    assert '"side": "sell"' in close_position.body
    assert '"order_type": "market"' in close_position.body
    assert ui_shell.status == HTTPStatus.OK
    assert '"sidebar_collapsed": true' in ui_shell.body
    assert activity.status == HTTPStatus.OK
    assert '"view_all_route": "/api/activity"' in activity.body
    assert '"visible_count": 2' in activity.body
    assert notifications_read.status == HTTPStatus.OK
    assert '"bell_state": "clear"' in notifications_read.body


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
