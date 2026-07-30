from __future__ import annotations

from http import HTTPStatus

import pytest

from abtp.dashboard import (
    DashboardAction,
    PaperDashboardActionError,
    build_default_paper_dashboard_controller,
    dispatch_dashboard_action,
)
from abtp.dashboard.paper_server import handle_dashboard_request, smoke_test
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


def test_approve_button_records_paper_only_operator_approval() -> None:
    controller = build_default_paper_dashboard_controller()

    updated = dispatch_dashboard_action(
        controller,
        DashboardAction.APPROVE_PAPER_TRADE,
        reason="fixture approval",
    )

    assert updated["logs"][0]["event_type"] == "approve_paper_trade"  # type: ignore[index]
    assert "simulated paper trade only" in updated["logs"][0]["message"]  # type: ignore[index]
    assert updated["live_trading_enabled"] is False


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

    assert paused["controls"]["paused"] is True  # type: ignore[index]
    assert resumed["controls"]["paused"] is False  # type: ignore[index]
    assert stopped["controls"]["kill_switch_active"] is True  # type: ignore[index]
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

    assert page.status == HTTPStatus.OK
    assert "ABTP Paper Trading Dashboard" in page.body
    assert status.status == HTTPStatus.OK
    assert '"mode": "PAPER MODE"' in status.body
    assert report.status == HTTPStatus.OK
    assert approve.status == HTTPStatus.OK
    assert "approve_paper_trade" in approve.body


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
