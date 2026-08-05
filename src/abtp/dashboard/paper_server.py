"""Standard-library local HTTP server for the ABTP paper dashboard."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from abtp.dashboard.paper_app import (
    DashboardAction,
    PaperDashboardActionError,
    PaperDashboardController,
    build_default_paper_dashboard_controller,
    dispatch_dashboard_action,
)
from abtp.domain.models import JsonValue

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def make_handler(
    controller: PaperDashboardController,
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to one paper-only controller."""

    class PaperDashboardRequestHandler(BaseHTTPRequestHandler):
        server_version = "ABTPPaperDashboard/0.1"

        def do_GET(self) -> None:
            response = handle_dashboard_request("GET", self.path, b"", controller)
            self._send(response)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            response = handle_dashboard_request("POST", self.path, body, controller)
            self._send(response)

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send(self, response: DashboardHttpResponse) -> None:
            payload = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

    return PaperDashboardRequestHandler


class DashboardHttpResponse:
    """Small HTTP response object for testable routing."""

    def __init__(
        self,
        *,
        status: int,
        body: str,
        content_type: str = "application/json; charset=utf-8",
    ) -> None:
        self.status = status
        self.body = body
        self.content_type = content_type


def handle_dashboard_request(
    method: str,
    path: str,
    body: bytes,
    controller: PaperDashboardController,
) -> DashboardHttpResponse:
    """Route one paper dashboard HTTP request without live execution authority."""

    parsed_url = urlparse(path)
    route = parsed_url.path
    try:
        if method == "GET" and route == "/":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=DASHBOARD_HTML,
                content_type="text/html; charset=utf-8",
            )
        if method == "GET" and route == "/api/status":
            query = parse_qs(parsed_url.query)
            mode = query.get("ui_mode", [None])[0]
            return _json_response(controller.state(ui_mode=mode))
        if method == "GET" and route == "/api/readiness":
            return _json_response(_mapping_field(controller.state(), "readiness"))
        if method == "GET" and route == "/api/activity":
            query = parse_qs(parsed_url.query)
            limit = _optional_int(query.get("limit", [None])[0])
            return _json_response(controller.activity_state(limit=limit))
        if method == "GET" and route == "/paper-report":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=_paper_report(controller),
                content_type="text/plain; charset=utf-8",
            )
        if method == "GET" and route == "/trader-handoff.md":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=_trader_handoff(controller),
                content_type="text/markdown; charset=utf-8",
            )
        if method == "GET" and route == "/trader-evidence.json":
            return _json_response(_trader_evidence_bundle(controller))
        if method == "GET" and route == "/paper-transactions.csv":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=_transactions_csv(controller),
                content_type="text/csv; charset=utf-8",
            )
        if method == "GET" and route == "/trader-feedback.csv":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=_trader_feedback_csv(controller),
                content_type="text/csv; charset=utf-8",
            )
        if method == "POST" and route == "/api/ui-mode":
            payload = _json_body(body)
            mode = str(payload.get("ui_mode", ""))
            return _json_response(controller.set_ui_mode(mode))
        if method == "POST" and route == "/api/ui-shell":
            payload = _json_body(body)
            return _json_response(
                controller.set_ui_shell_preferences(
                    sidebar_collapsed=_optional_bool(payload, "sidebar_collapsed"),
                )
            )
        if method == "POST" and route == "/api/mark-notifications-read":
            return _json_response(controller.mark_notifications_read())
        if method == "POST" and route == "/api/strategy-lab-selection":
            payload = _json_body(body)
            return _json_response(
                controller.set_strategy_lab_selection(
                    strategy=_optional_text(payload, "strategy"),
                    symbol=_optional_text(payload, "symbol"),
                    timeframe=_optional_text(payload, "timeframe"),
                    run_mode=_optional_text(payload, "run_mode"),
                    parameter_profile=_optional_text(payload, "parameter_profile"),
                )
            )
        if method == "POST" and route == "/api/watchlist-symbol":
            payload = _json_body(body)
            return _json_response(controller.set_watchlist_symbol(str(payload.get("symbol", ""))))
        if method == "POST" and route == "/api/alert-rule":
            payload = _json_body(body)
            return _json_response(
                controller.add_alert_rule(
                    alert_type=str(payload.get("alert_type", "")),
                    symbol=str(payload.get("symbol", "")),
                    threshold=_optional_text(payload, "threshold"),
                    expected_value=_optional_text(payload, "expected_value"),
                )
            )
        if method == "POST" and route == "/api/delete-alert-rule":
            payload = _json_body(body)
            return _json_response(
                controller.delete_alert_rule(alert_id=str(payload.get("alert_id", "")))
            )
        if method == "POST" and route == "/api/journal-entry":
            payload = _json_body(body)
            return _json_response(
                controller.save_journal_entry(
                    trade_ref=_optional_text(payload, "trade_ref"),
                    symbol=_optional_text(payload, "symbol"),
                    setup_type=_optional_text(payload, "setup_type"),
                    tags=_optional_text(payload, "tags"),
                    notes=_optional_text(payload, "notes"),
                    mistake_review=_optional_text(payload, "mistake_review"),
                    lesson=_optional_text(payload, "lesson"),
                    chart_context=_optional_text(payload, "chart_context"),
                )
            )
        if method == "POST" and route == "/api/delete-journal-entry":
            payload = _json_body(body)
            return _json_response(
                controller.delete_journal_entry(journal_id=str(payload.get("journal_id", "")))
            )
        if method == "POST" and route == "/api/trader-feedback":
            payload = _json_body(body)
            return _json_response(
                controller.save_trader_feedback(
                    reviewer_role=_optional_text(payload, "reviewer_role"),
                    category=_optional_text(payload, "category"),
                    severity=_optional_text(payload, "severity"),
                    summary=_optional_text(payload, "summary"),
                    recommendation=_optional_text(payload, "recommendation"),
                )
            )
        if method == "POST" and route == "/api/close-trader-feedback":
            payload = _json_body(body)
            return _json_response(
                controller.close_trader_feedback(
                    feedback_id=str(payload.get("feedback_id", "")),
                    resolution=_optional_text(payload, "resolution"),
                )
            )
        if method == "POST" and route == "/api/chart-drawing":
            payload = _json_body(body)
            return _json_response(
                controller.save_chart_drawing(
                    drawing_type=str(payload.get("drawing_type", "")),
                    symbol=_optional_text(payload, "symbol"),
                    timeframe=_optional_text(payload, "timeframe"),
                    start_time=_optional_text(payload, "start_time"),
                    end_time=_optional_text(payload, "end_time"),
                    start_price=_optional_text(payload, "start_price"),
                    end_price=_optional_text(payload, "end_price"),
                    text=_optional_text(payload, "text"),
                    color=_optional_text(payload, "color"),
                )
            )
        if method == "POST" and route == "/api/delete-chart-drawing":
            payload = _json_body(body)
            return _json_response(
                controller.delete_chart_drawing(drawing_id=str(payload.get("drawing_id", "")))
            )
        if method == "POST" and route == "/api/paper-order-ticket":
            payload = _json_body(body)
            return _json_response(
                controller.submit_paper_order_ticket(
                    order_type=str(payload.get("order_type", "")),
                    side=str(payload.get("side", "")),
                    quantity=str(payload.get("quantity", "")),
                    limit_price=_optional_text(payload, "limit_price"),
                    stop_price=_optional_text(payload, "stop_price"),
                    take_profit_price=_optional_text(payload, "take_profit_price"),
                    reason=str(payload.get("reason", "")),
                )
            )
        if method == "POST" and route == "/api/cancel-paper-order":
            payload = _json_body(body)
            return _json_response(
                controller.cancel_paper_order(
                    order_id=str(payload.get("order_id", "")),
                    reason=str(payload.get("reason", "")),
                )
            )
        if method == "POST" and route == "/api/stage-close-position":
            payload = _json_body(body)
            return _json_response(
                controller.stage_close_position(reason=str(payload.get("reason", "")))
            )
        if method == "POST" and route == "/api/stage-reduce-position":
            payload = _json_body(body)
            return _json_response(
                controller.stage_reduce_position(reason=str(payload.get("reason", "")))
            )
        if method == "POST" and route.startswith("/api/"):
            action = _action_from_route(route)
            payload = _json_body(body)
            reason = str(payload.get("reason", ""))
            return _json_response(dispatch_dashboard_action(controller, action, reason=reason))
    except (PaperDashboardActionError, ValueError) as exc:
        return _json_response(
            {"error": str(exc), "live_trading_enabled": False},
            HTTPStatus.BAD_REQUEST,
        )
    return _json_response({"error": f"not found: {method} {route}"}, HTTPStatus.NOT_FOUND)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Start the local paper dashboard server."""

    controller = build_default_paper_dashboard_controller(
        state_path=os.getenv("ABTP_PAPER_STATE_PATH", "docs/paper_dashboard_state.json"),
        db_path=os.getenv("ABTP_PAPER_DB_PATH", "docs/paper_dashboard.sqlite"),
    )
    server = ThreadingHTTPServer((host, port), make_handler(controller))
    print(f"ABTP paper dashboard: http://{host}:{port}")
    print("Press Ctrl+C to stop. Live trading remains disabled.")
    server.serve_forever()


def smoke_test() -> dict[str, JsonValue]:
    """Run a lightweight local dashboard smoke test without binding a socket."""

    controller = build_default_paper_dashboard_controller()
    status = handle_dashboard_request("GET", "/api/status", b"", controller)
    approve = handle_dashboard_request(
        "POST",
        "/api/approve-paper-trade",
        b'{"reason":"smoke approval"}',
        controller,
    )
    emergency = handle_dashboard_request(
        "POST",
        "/api/emergency-stop",
        b'{"reason":"smoke emergency stop"}',
        controller,
    )
    return {
        "status_code": str(status.status),
        "approve_status_code": str(approve.status),
        "emergency_status_code": str(emergency.status),
        "live_trading_enabled": "False",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the ABTP paper trading dashboard.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        print(json.dumps(smoke_test(), indent=2, sort_keys=True))
        return
    run_server(host=args.host, port=args.port)


def _action_from_route(route: str) -> DashboardAction:
    routes = {
        "/api/approve-paper-trade": DashboardAction.APPROVE_PAPER_TRADE,
        "/api/reject-recommendation": DashboardAction.REJECT_RECOMMENDATION,
        "/api/pause-paper-bot": DashboardAction.PAUSE_PAPER_BOT,
        "/api/resume-paper-bot": DashboardAction.RESUME_PAPER_BOT,
        "/api/emergency-stop": DashboardAction.EMERGENCY_STOP,
        "/api/reset-emergency-stop": DashboardAction.RESET_EMERGENCY_STOP,
    }
    if route not in routes:
        raise ValueError(f"unsupported paper dashboard action: {route}")
    return routes[route]


def _json_body(body: bytes) -> Mapping[str, Any]:
    if not body:
        return {}
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError("request body must be a JSON object")
    return parsed


def _json_response(
    payload: Mapping[str, JsonValue],
    status: HTTPStatus = HTTPStatus.OK,
) -> DashboardHttpResponse:
    return DashboardHttpResponse(
        status=status,
        body=json.dumps(payload, indent=2, sort_keys=True),
    )


def _optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(payload: Mapping[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "collapsed"}
    return bool(value)


def _paper_report(controller: PaperDashboardController) -> str:
    state = controller.state()
    market = _mapping_field(state, "market")
    strategy = _mapping_field(state, "strategy")
    portfolio = _mapping_field(state, "portfolio")
    controls = _mapping_field(state, "controls")
    readiness = _mapping_field(state, "readiness")
    trader_verdict = _mapping_field(readiness, "trader_verdict")
    logs = _list_field(state, "logs")
    transactions = _list_field(state, "transactions")
    risk_halts = _list_field(portfolio, "risk_halts")
    log_lines = _report_log_lines(logs)
    transaction_lines = _report_transaction_lines(transactions)
    proof_lines = _report_list_lines(_list_field(trader_verdict, "proof_points"))
    blocker_lines = _report_list_lines(_list_field(trader_verdict, "blockers"))
    warning_lines = _report_list_lines(_list_field(trader_verdict, "warnings"))
    next_step_lines = _report_list_lines(_list_field(trader_verdict, "next_steps"))
    return "\n".join(
        (
            "# Paper Trading Status Report",
            "",
            f"Generated from current local dashboard state on {_text_field(market, 'updated_at')}.",
            "",
            "## Current Setup",
            "",
            f"- Mode: `{_text_field(state, 'mode')}`",
            "- Safe mode: `true`",
            "- Live trading enabled: `false`",
            "- Runtime can execute live: `false`",
            f"- Market data: `{_text_field(market, 'source')}`",
            f"- Asset focus: `{_text_field(market, 'symbol')}`",
            f"- Current price: `{_text_field(market, 'current_price')}`",
            f"- Spread: `{_text_field(market, 'spread')}`",
            f"- Data freshness: `{_text_field(market, 'data_freshness')}`",
            "",
            "## Paper Portfolio",
            "",
            f"- Starting balance: `{_text_field(portfolio, 'starting_balance')}`",
            f"- Cash: `{_text_field(portfolio, 'cash')}`",
            f"- Current equity: `{_text_field(portfolio, 'current_equity')}`",
            f"- Open BTC: `{_text_field(portfolio, 'open_btc')}`",
            f"- Realized P/L: `{_text_field(portfolio, 'realized_pnl')}`",
            f"- Unrealized P/L: `{_text_field(portfolio, 'unrealized_pnl')}`",
            f"- Drawdown: `{_text_field(portfolio, 'drawdown')}`",
            f"- Risk halts: `{', '.join(str(item) for item in risk_halts)}`",
            "",
            "## Current Recommendation",
            "",
            f"- Recommendation: `{_text_field(strategy, 'recommendation')}`",
            f"- AI confidence: `{_text_field(strategy, 'ai_confidence')}`",
            f"- Risk decision: `{_text_field(strategy, 'risk_decision')}`",
            f"- Explanation: {_text_field(strategy, 'explanation')}",
            "- Can approve paper trade now: "
            f"`{str(controls.get('can_approve_paper_trade')).lower()}`",
            f"- Approval status: {_text_field(controls, 'approval_block_reason')}",
            "",
            "## Trader Readiness Verdict",
            "",
            f"- Paper demo ready: `{_text_field(trader_verdict, 'paper_demo_ready')}`",
            f"- Live capital ready: `{_text_field(trader_verdict, 'live_capital_ready')}`",
            f"- Shareable scope: `{_text_field(trader_verdict, 'shareable_scope')}`",
            f"- Profitability claim: `{_text_field(trader_verdict, 'profitability_claim')}`",
            f"- Reconstructability: `{_text_field(trader_verdict, 'reconstructability_status')}`",
            "",
            "Proof points:",
            *proof_lines,
            "",
            "Blockers:",
            *blocker_lines,
            "",
            "Warnings:",
            *warning_lines,
            "",
            "Next steps:",
            *next_step_lines,
            "",
            "## Paper Transactions",
            "",
            *transaction_lines,
            "",
            "## Recent Logs",
            "",
            *log_lines,
            "",
            "## Safety",
            "",
            "- This dashboard remains paper-only.",
            "- No real exchange orders, withdrawals, transfers, leverage, margin, "
            "futures, or options are enabled.",
            "- Binance spot, when connected, is used as read-only market data for paper trading.",
        )
    )


def _trader_handoff(controller: PaperDashboardController) -> str:
    state = controller.state()
    market = _mapping_field(state, "market")
    portfolio = _mapping_field(state, "portfolio")
    readiness = _mapping_field(state, "readiness")
    trader_verdict = _mapping_field(readiness, "trader_verdict")
    views = _mapping_field(state, "views")
    advanced = _mapping_field(views, "advanced_trader")
    strategy_lab = _mapping_field(views, "strategy_lab")
    trader_feedback = _mapping_field(advanced, "trader_feedback")
    proof_lines = _report_list_lines(_list_field(trader_verdict, "proof_points"))
    blocker_lines = _report_list_lines(_list_field(trader_verdict, "blockers"))
    warning_lines = _report_list_lines(_list_field(trader_verdict, "warnings"))
    next_step_lines = _report_list_lines(_list_field(trader_verdict, "next_steps"))
    return "\n".join(
        (
            "# ABTP Trader Review Handoff",
            "",
            "This packet is for paper-mode trader review only. It is not a live "
            "trading approval, investment advice, or a profitability claim.",
            "",
            "## Current Verdict",
            "",
            f"- Paper demo ready: `{_text_field(trader_verdict, 'paper_demo_ready')}`",
            f"- Live capital ready: `{_text_field(trader_verdict, 'live_capital_ready')}`",
            f"- Shareable scope: `{_text_field(trader_verdict, 'shareable_scope')}`",
            f"- Profitability claim: `{_text_field(trader_verdict, 'profitability_claim')}`",
            f"- Reconstructability: `{_text_field(trader_verdict, 'reconstructability_status')}`",
            "",
            "## What To Review",
            "",
            "- Beginner view: command wording, plain-language reasons, portfolio clarity.",
            "- Advanced Trader view: chart, order book, order flow, alerts, journal, "
            "paper order ticket, position panel, risk and safety evidence.",
            "- Strategy Lab: required evidence, module routing, parameter profiles, "
            "compare-run rows, and actionability blockers.",
            "- Exports: Paper Report, Transactions CSV, and this handoff packet.",
            "",
            "## Current Paper State",
            "",
            f"- Symbol: `{_text_field(market, 'symbol')}`",
            f"- Market data source: `{_text_field(market, 'source')}`",
            f"- Data freshness: `{_text_field(market, 'data_freshness')}`",
            f"- Cash: `{_text_field(portfolio, 'cash')}`",
            f"- Current equity: `{_text_field(portfolio, 'current_equity')}`",
            f"- Open BTC: `{_text_field(portfolio, 'open_btc')}`",
            f"- Drawdown: `{_text_field(portfolio, 'drawdown')}`",
            "",
            "## Available Advanced Evidence",
            "",
            f"- Chart enabled: `{str('chart' in advanced).lower()}`",
            f"- Order book enabled: `{str('order_book' in advanced).lower()}`",
            f"- Order flow enabled: `{str('order_flow' in advanced).lower()}`",
            f"- Paper order ticket enabled: `{str('order_ticket' in advanced).lower()}`",
            f"- Trade journal enabled: `{str('trade_journal' in advanced).lower()}`",
            f"- Trader feedback items: "
            f"`{_text_field(_mapping_field(trader_feedback, 'summary'), 'total')}`",
            f"- Risk safety panel enabled: `{str('risk_safety' in advanced).lower()}`",
            f"- Strategy Lab selected strategy: `{_text_field(strategy_lab, 'selected_strategy')}`",
            "",
            "## Proof Points",
            "",
            *proof_lines,
            "",
            "## Blockers",
            "",
            *blocker_lines,
            "",
            "## Warnings",
            "",
            *warning_lines,
            "",
            "## Suggested Trader Questions",
            "",
            "- Is the recommendation explanation enough to accept or reject a paper trade?",
            "- Are stop, target, sizing, and risk/reward visible before approval?",
            "- Does the order ticket behave like a paper-only tool and avoid live ambiguity?",
            "- Does Strategy Lab clearly show why a strategy is actionable or blocked?",
            "- What additional market data or analytics would be required before any live review?",
            "",
            "## Next Steps",
            "",
            *next_step_lines,
        )
    )


def _trader_evidence_bundle(controller: PaperDashboardController) -> dict[str, JsonValue]:
    state = controller.state()
    views = _dict_field(state, "views")
    advanced = _dict_field(views, "advanced_trader")
    strategy_lab = _dict_field(views, "strategy_lab")
    alerts = _dict_field(advanced, "alerts")
    order_book = _dict_field(advanced, "order_book")
    order_flow = _dict_field(advanced, "order_flow")
    risk_safety = _dict_field(advanced, "risk_safety")
    market = _dict_field(state, "market")
    trade_journal = _dict_field(advanced, "trade_journal")
    trader_feedback = _dict_field(advanced, "trader_feedback")
    return {
        "export_kind": "trader_evidence_bundle",
        "generated_at": _text_field(market, "updated_at"),
        "live_trading_enabled": False,
        "safe_mode": True,
        "warning": _text_field(state, "warning"),
        "readiness": _dict_field(state, "readiness"),
        "market": market,
        "portfolio": _dict_field(state, "portfolio"),
        "strategy": _dict_field(state, "strategy"),
        "suggested_paper_trade": _dict_field(state, "suggested_paper_trade"),
        "transactions": _list_field(state, "transactions"),
        "paper_controls": _dict_field(state, "controls"),
        "advanced_evidence": {
            "chart": _dict_field(advanced, "chart"),
            "order_book_summary": _dict_field(order_book, "summary"),
            "order_flow_summary": _dict_field(order_flow, "summary"),
            "risk_safety_summary": _dict_field(risk_safety, "summary"),
            "backtest_summary": _dict_field(advanced, "backtest_summary"),
            "performance": _dict_field(advanced, "performance"),
            "exit_review": _dict_field(advanced, "exit_review"),
            "triggered_alerts": _list_field(alerts, "triggered"),
            "open_paper_orders": _list_field(advanced, "open_paper_orders"),
            "journal_summary": _dict_field(trade_journal, "summary"),
            "trader_feedback_summary": _dict_field(trader_feedback, "summary"),
            "trader_feedback_items": _list_field(trader_feedback, "items"),
        },
        "strategy_lab_evidence": {
            "selected_strategy": _text_field(strategy_lab, "selected_strategy"),
            "selection": _dict_field(strategy_lab, "selection"),
            "evidence_request": _dict_field(strategy_lab, "evidence_request"),
            "routing_decision": _dict_field(strategy_lab, "routing_decision"),
            "evidence_matrix": _list_field(strategy_lab, "evidence_matrix"),
            "module_routing": _list_field(strategy_lab, "module_routing"),
            "compare_runs": _list_field(strategy_lab, "compare_runs"),
            "missing_evidence": _list_field(strategy_lab, "missing_evidence"),
            "recommendation_actionable": bool(strategy_lab.get("recommendation_actionable", False)),
        },
        "logs": _list_field(state, "logs"),
    }


def _transactions_csv(controller: PaperDashboardController) -> str:
    transactions = _list_field(controller.state(), "transactions")
    rows = ["time,side,quantity,price,fee,notional"]
    for item in transactions:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            ",".join(
                (
                    _csv_cell(_text_field(item, "time")),
                    _csv_cell(_text_field(item, "side")),
                    _csv_cell(_text_field(item, "quantity")),
                    _csv_cell(_text_field(item, "price")),
                    _csv_cell(_text_field(item, "fee")),
                    _csv_cell(_text_field(item, "notional")),
                )
            )
        )
    return "\n".join(rows) + "\n"


def _trader_feedback_csv(controller: PaperDashboardController) -> str:
    state = controller.state()
    views = _mapping_field(state, "views")
    advanced = _mapping_field(views, "advanced_trader")
    feedback = _mapping_field(advanced, "trader_feedback")
    items = _list_field(feedback, "items")
    rows = [
        "feedback_id,created_at,resolved_at,reviewer_role,category,severity,status,"
        "summary,recommendation,resolution"
    ]
    for item in items:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            ",".join(
                (
                    _csv_cell(_text_field(item, "feedback_id")),
                    _csv_cell(_text_field(item, "created_at")),
                    _csv_cell(_text_field(item, "resolved_at")),
                    _csv_cell(_text_field(item, "reviewer_role")),
                    _csv_cell(_text_field(item, "category")),
                    _csv_cell(_text_field(item, "severity")),
                    _csv_cell(_text_field(item, "status")),
                    _csv_cell(_text_field(item, "summary")),
                    _csv_cell(_text_field(item, "recommendation")),
                    _csv_cell(_text_field(item, "resolution")),
                )
            )
        )
    return "\n".join(rows) + "\n"


def _mapping_field(payload: Mapping[str, JsonValue], key: str) -> Mapping[str, JsonValue]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


def _dict_field(payload: Mapping[str, JsonValue], key: str) -> dict[str, JsonValue]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def _list_field(payload: Mapping[str, JsonValue], key: str) -> list[JsonValue]:
    value = payload.get(key)
    return value if isinstance(value, list) else []


def _text_field(payload: Mapping[str, JsonValue], key: str) -> str:
    value = payload.get(key)
    return "not_available" if value is None else str(value)


def _csv_cell(value: str) -> str:
    if any(char in value for char in (",", '"', "\n")):
        return '"' + value.replace('"', '""') + '"'
    return value


def _report_log_lines(logs: list[JsonValue]) -> tuple[str, ...]:
    if not logs:
        return ("- No paper dashboard events recorded.",)
    lines: list[str] = []
    for item in logs[:8]:
        if not isinstance(item, Mapping):
            continue
        occurred_at = _text_field(item, "occurred_at")
        event_type = _text_field(item, "event_type")
        message = _text_field(item, "message")
        reason = _text_field(item, "reason")
        suffix = f" Reason: {reason}" if reason else ""
        lines.append(f"- `{occurred_at}` `{event_type}`: {message}{suffix}")
    return tuple(lines) or ("- No paper dashboard events recorded.",)


def _report_transaction_lines(transactions: list[JsonValue]) -> tuple[str, ...]:
    if not transactions:
        return ("- No saved paper transactions yet.",)
    lines: list[str] = []
    for item in transactions[:20]:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            "- "
            f"`{_text_field(item, 'time')}` "
            f"{_text_field(item, 'side')} "
            f"{_text_field(item, 'quantity')} BTC "
            f"at `{_text_field(item, 'price')}`; "
            f"fee `{_text_field(item, 'fee')}`"
        )
    return tuple(lines) or ("- No saved paper transactions yet.",)


def _report_list_lines(items: list[JsonValue]) -> tuple[str, ...]:
    if not items:
        return ("- none",)
    return tuple(f"- {item}" for item in items)


DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ABTP Paper Trading Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #04101a;
      --bg-2: #061522;
      --header-bg: #04111c;
      --sidebar-bg: #061522;
      --panel: #081927;
      --panel-soft: #0b2030;
      --panel-elevated: #0d2434;
      --panel-hover: #102a3d;
      --text: #edf5ff;
      --text-soft: #c7d4e2;
      --muted: #8297aa;
      --muted-2: #60778c;
      --line: #173448;
      --line-soft: rgba(83, 121, 150, 0.28);
      --line-strong: #255675;
      --good: #2fd078;
      --warn: #f6ad2f;
      --bad: #f0444f;
      --accent: #2388ff;
      --accent-bright: #339cff;
      --accent-soft: rgba(35, 136, 255, 0.14);
      --accent-2: #7c5cff;
      --teal: #20c7b5;
      --gold: #f2b84b;
      --orange: #f7931a;
      --good-bg: rgba(47, 208, 120, 0.12);
      --warn-bg: rgba(246, 173, 47, 0.13);
      --bad-bg: rgba(240, 68, 79, 0.13);
      --accent-bg: var(--accent-soft);
      --shadow: 0 14px 34px rgba(0, 0, 0, 0.24);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background:
        radial-gradient(circle at 10% 0%, rgba(35, 136, 255, 0.10), transparent 360px),
        linear-gradient(180deg, #04111c 0%, var(--bg-2) 48%, #03101a 100%);
      color: var(--text);
      min-width: 320px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      min-height: 92px;
      padding: 14px 26px;
      border-bottom: 1px solid var(--line);
      background: rgba(5, 16, 24, 0.96);
      backdrop-filter: blur(16px);
      position: sticky;
      top: 0;
      z-index: 10;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.26);
    }
    h1 { font-size: 27px; margin: 0; letter-spacing: 0; line-height: 1; }
    .app-title {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }
    .app-mark {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: inline-grid;
      place-items: center;
      flex: 0 0 auto;
      color: white;
      font-weight: 900;
      background:
        linear-gradient(135deg, rgba(47, 129, 255, 0.95), rgba(32, 199, 181, 0.75));
      box-shadow: 0 8px 18px rgba(18, 100, 163, 0.2);
    }
    .app-kicker {
      color: var(--muted);
      font-size: 0.68rem;
      font-weight: 800;
      line-height: 1.2;
      text-transform: uppercase;
    }
    .header-tools {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
    }
    .mode-selector {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: rgba(14, 34, 48, 0.86);
      padding: 5px 8px;
    }
    .mode-select-label {
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 800;
      text-transform: uppercase;
    }
    .mode-select {
      min-width: 178px;
      min-height: 32px;
      border: 0;
      border-radius: 6px;
      background: #112737;
      color: var(--text);
      font-weight: 800;
      padding: 5px 30px 5px 9px;
    }
    .mode-button {
      min-height: 34px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      color: var(--text);
      padding: 7px 10px;
      font-weight: 750;
    }
    .mode-button:last-child { border-right: 0; }
    .mode-button.active {
      background: linear-gradient(135deg, var(--accent), var(--teal));
      color: white;
    }
    .market-strip {
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 10px;
      max-width: 1640px;
      margin: 0 auto 14px;
      padding: 0 16px;
    }
    .market-pill {
      display: grid;
      gap: 3px;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: linear-gradient(180deg, rgba(14, 34, 48, 0.96), rgba(9, 24, 35, 0.96));
      padding: 9px 11px;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
    }
    .market-pill span:first-child {
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 800;
      text-transform: uppercase;
    }
    .market-pill strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 0.98rem;
    }
    .dashboard-shell {
      display: grid;
      grid-template-columns: 178px minmax(0, 1fr);
      min-height: calc(100vh - 92px);
    }
    .sidebar {
      position: sticky;
      top: 92px;
      align-self: start;
      height: calc(100vh - 92px);
      border-right: 1px solid var(--line);
      background: rgba(5, 16, 24, 0.9);
      padding: 16px 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .side-nav {
      display: grid;
      gap: 8px;
      padding: 0 8px;
    }
    .side-link {
      min-height: 56px;
      width: 100%;
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      border: 1px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: var(--muted);
      text-align: left;
      padding: 10px 12px;
      box-shadow: none;
    }
    .side-link.active {
      color: #d8eaff;
      border-color: rgba(47, 129, 255, 0.5);
      background: linear-gradient(90deg, rgba(47, 129, 255, 0.32), rgba(47, 129, 255, 0.08));
      box-shadow: inset 3px 0 0 var(--accent);
    }
    .side-icon {
      width: 28px;
      height: 28px;
      border-radius: 7px;
      display: inline-grid;
      place-items: center;
      border: 1px solid var(--line-strong);
      color: #9ecbff;
      font-weight: 900;
      font-size: 0.8rem;
    }
    .side-copy {
      display: grid;
      gap: 2px;
      min-width: 0;
    }
    .side-copy strong,
    .side-copy span {
      overflow: visible;
      text-overflow: clip;
      white-space: normal;
    }
    .side-copy strong { color: inherit; font-size: 0.94rem; }
    .side-copy span { color: var(--muted); font-size: 0.78rem; }
    .collapse-note {
      color: var(--muted);
      padding: 10px 22px;
      font-size: 0.86rem;
    }
    .dashboard-content {
      min-width: 0;
      padding: 16px 0 0;
    }
    main {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      grid-auto-flow: dense;
      gap: 14px;
      padding: 0 16px 18px;
      max-width: 1640px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-width: 0;
      box-shadow: var(--shadow);
      overflow: auto;
      scrollbar-gutter: stable;
    }
    section[data-view~="advanced_trader"] {
      border-top: 3px solid color-mix(in srgb, var(--accent) 70%, white);
    }
    section[data-view~="beginner"] {
      border-top: 3px solid color-mix(in srgb, var(--good) 72%, white);
    }
    section[data-view~="strategy_lab"] {
      border-top: 3px solid color-mix(in srgb, var(--accent-2) 72%, white);
    }
    h2 {
      margin: 0 0 12px;
      font-size: 15px;
      letter-spacing: 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    h2::before {
      content: "";
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-bg);
      flex: 0 0 auto;
    }
    section[data-view~="beginner"] h2::before {
      background: var(--good);
      box-shadow: 0 0 0 4px var(--good-bg);
    }
    section[data-view~="strategy_lab"] h2::before {
      background: var(--accent-2);
      box-shadow: 0 0 0 4px #efe9ff;
    }
    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-5 { grid-column: span 5; }
    .span-6 { grid-column: span 6; }
    .span-7 { grid-column: span 7; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .badges { display: flex; gap: 8px; flex-wrap: wrap; }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      font-weight: 700;
      font-size: 13px;
      background: var(--panel-soft);
    }
    .good { color: var(--good); }
    .warn { color: var(--warn); }
    .bad { color: var(--bad); }
    dl {
      display: grid;
      grid-template-columns: minmax(108px, 0.75fr) minmax(0, 1.25fr);
      gap: 8px 12px;
      margin: 0;
    }
    dt { color: var(--muted); min-width: 0; }
    dd {
      margin: 0;
      font-weight: 700;
      text-align: right;
      overflow-wrap: anywhere;
      min-width: 0;
      line-height: 1.35;
    }
    .value-chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      max-width: 100%;
      min-width: 0;
      min-height: 24px;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 2px 8px;
      background: #102433;
      color: var(--text);
      font-size: 0.88rem;
      font-weight: 800;
      overflow-wrap: anywhere;
      text-align: center;
      white-space: normal;
    }
    .value-good { background: var(--good-bg); border-color: #b8e4cf; color: var(--good); }
    .value-warn { background: var(--warn-bg); border-color: #f3d48a; color: var(--warn); }
    .value-bad { background: var(--bad-bg); border-color: #f2bbb4; color: var(--bad); }
    .value-accent { background: var(--accent-bg); border-color: #bfd8f3; color: var(--accent); }
    .value-muted { color: var(--muted); font-weight: 700; }
    .metric-negative { color: var(--bad); }
    .metric-positive { color: var(--good); }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; }
    button, a.button {
      min-height: 36px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: white;
      padding: 8px 11px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      box-shadow: 0 4px 12px rgba(18, 100, 163, 0.12);
    }
    button.secondary { background: transparent; color: #9ecbff; box-shadow: none; }
    button.danger { background: var(--bad); border-color: var(--bad); }
    button:disabled {
      background: #1c2b36;
      border-color: #263a49;
      color: #718697;
      cursor: not-allowed;
    }
    button.side-link,
    a.side-link {
      min-height: 56px;
      width: 100%;
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      border: 1px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: var(--muted);
      text-align: left;
      padding: 10px 12px;
      box-shadow: none;
      text-decoration: none;
    }
    button.side-link.active,
    a.side-link.active {
      color: #d8eaff;
      border-color: rgba(47, 129, 255, 0.5);
      background: linear-gradient(90deg, rgba(47, 129, 255, 0.32), rgba(47, 129, 255, 0.08));
      box-shadow: inset 3px 0 0 var(--accent);
    }
    ul { margin: 0; padding-left: 18px; }
    li { margin-bottom: 6px; }
    .log {
      max-height: 260px;
      overflow: auto;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    section:has(table) {
      max-height: min(72vh, 760px);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
      min-width: 560px;
    }
    .depth-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 12px;
    }
    .depth-side h3 {
      margin: 0 0 6px;
      font-size: 0.86rem;
      color: var(--muted);
      text-transform: uppercase;
    }
    .depth-table td,
    .depth-table th {
      padding: 7px 6px;
      font-size: 0.86rem;
    }
    .depth-price-bid { color: var(--good); font-weight: 700; }
    .depth-price-ask { color: var(--bad); font-weight: 700; }
    .watchlist-row {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #0d202e;
      color: var(--text);
      margin-bottom: 8px;
      text-align: left;
    }
    .watchlist-row.active {
      border-color: var(--accent);
      background: rgba(47, 129, 255, 0.16);
    }
    .watchlist-symbol { font-weight: 800; }
    .watchlist-note {
      color: var(--muted);
      font-size: 0.82rem;
      grid-column: 1 / -1;
    }
    .alert-list {
      display: grid;
      gap: 8px;
      margin-bottom: 12px;
    }
    .alert-item {
      border: 1px solid var(--line);
      border-left: 4px solid var(--warn);
      border-radius: 6px;
      padding: 8px 10px;
      background: var(--warn-bg);
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 8px 7px;
      text-align: left;
      overflow-wrap: anywhere;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
      background: #102433;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    .empty {
      color: var(--muted);
      margin: 0;
    }
    .warning {
      color: var(--bad);
      font-weight: 700;
      background: var(--bad-bg);
      border-color: rgba(255, 92, 92, 0.4);
    }
    .command-label {
      font-size: 1.45rem;
      font-weight: 800;
      margin-bottom: 10px;
      color: var(--good);
    }
    .chart-canvas {
      display: block;
      width: 100%;
      height: 360px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: linear-gradient(180deg, #071722 0, #091e2a 100%);
    }
    .chart-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .segmented {
      display: inline-flex;
      flex-wrap: wrap;
      border: 1px solid var(--line);
      border-radius: 6px;
      overflow: hidden;
      background: #0d202e;
    }
    .chart-tool {
      min-height: 32px;
      min-width: 36px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      color: var(--text);
      padding: 6px 9px;
      font-size: 0.85rem;
      box-shadow: none;
    }
    .chart-tool:last-child { border-right: 0; }
    .chart-tool.active {
      background: var(--accent);
      color: white;
    }
    .chart-wrap {
      position: relative;
    }
    .chart-tooltip {
      position: absolute;
      display: none;
      pointer-events: none;
      min-width: 184px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: rgba(8, 24, 35, 0.96);
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.24);
      padding: 8px 10px;
      font-size: 0.82rem;
      line-height: 1.45;
      color: var(--text);
      z-index: 2;
    }
    .chart-readout {
      min-height: 24px;
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.86rem;
    }
    .selector-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(128px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    body.mode-strategy_lab .selector-grid {
      grid-template-columns: repeat(5, minmax(0, 1fr));
      align-items: end;
    }
    body.mode-strategy_lab .selector-grid label {
      min-width: 0;
    }
    body.mode-strategy_lab .selector-grid select {
      width: 100%;
      min-width: 0;
    }
    body.mode-strategy_lab #strategy_lab {
      grid-template-columns: minmax(140px, 0.42fr) minmax(0, 0.58fr);
      align-items: start;
    }
    body.mode-strategy_lab #strategy_lab_evidence > dl {
      display: grid;
      grid-template-columns: 1fr;
      gap: 4px;
      margin: 0;
    }
    body.mode-strategy_lab #strategy_lab dt,
    body.mode-strategy_lab #strategy_lab_evidence dt {
      text-align: left;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    body.mode-strategy_lab #strategy_lab_evidence dt {
      margin-top: 8px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }
    body.mode-strategy_lab #strategy_lab dd,
    body.mode-strategy_lab #strategy_lab_evidence dd {
      line-height: 1.25;
      overflow-wrap: anywhere;
    }
    body.mode-strategy_lab #strategy_lab dd {
      text-align: right;
    }
    body.mode-strategy_lab #strategy_lab_evidence dd {
      margin: 0;
      text-align: left;
    }
    body.mode-strategy_lab #strategy_lab_evidence .value-chip {
      justify-content: flex-start;
      width: 100%;
      line-height: 1.25;
      text-align: left;
    }
    body.mode-strategy_lab section:has(#strategy_lab),
    body.mode-strategy_lab section:has(#strategy_lab_evidence),
    body.mode-strategy_lab section:has(#strategy_lab_compare) {
      overflow: hidden;
    }
    body.mode-strategy_lab #strategy_lab_evidence,
    body.mode-strategy_lab #strategy_lab_compare {
      max-height: 560px;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    body.mode-strategy_lab #strategy_lab_evidence h3 {
      margin: 14px 0 8px;
      color: var(--text);
      font-size: 12px;
      text-transform: uppercase;
    }
    body.mode-strategy_lab #strategy_lab_evidence table,
    body.mode-strategy_lab #strategy_lab_compare table {
      min-width: 760px;
      width: 100%;
      table-layout: fixed;
    }
    body.mode-strategy_lab #strategy_lab_evidence th,
    body.mode-strategy_lab #strategy_lab_evidence td,
    body.mode-strategy_lab #strategy_lab_compare th,
    body.mode-strategy_lab #strategy_lab_compare td {
      white-space: normal;
      overflow-wrap: anywhere;
      line-height: 1.25;
    }
    .ticket-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    label {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 0.8rem;
      font-weight: 700;
    }
    select, input, textarea {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #0d202e;
      color: var(--text);
      padding: 6px 8px;
      font: inherit;
    }
    select:focus, input:focus, textarea:focus, button:focus-visible, a.button:focus-visible {
      outline: 3px solid rgba(18, 100, 163, 0.2);
      outline-offset: 2px;
    }
    textarea {
      min-height: 76px;
      resize: vertical;
    }
    [hidden] { display: none !important; }
    body.mode-advanced_trader section:has(#price_chart),
    body.mode-strategy_lab section:has(#price_chart) { order: 20; }
    body.mode-advanced_trader section[data-view~="advanced_trader"],
    body.mode-strategy_lab section[data-view~="advanced_trader"] { order: 24; }
    body.mode-advanced_trader section:has(#warning),
    body.mode-strategy_lab section:has(#warning) { order: 80; }
    .status-footer {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 0;
      min-height: 88px;
      border-top: 1px solid var(--line-soft);
      background: var(--header-bg);
      margin-top: 2px;
    }
    .footer-item {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      min-height: 88px;
      padding: 10px 18px;
      border-right: 1px solid var(--line-soft);
    }
    .footer-item:last-child { border-right: 0; }
    .footer-icon {
      width: 28px;
      height: 28px;
      border: 1px solid var(--line-strong);
      border-radius: 7px;
      display: inline-grid;
      place-items: center;
      color: #9ecbff;
      font-weight: 900;
    }
    .footer-item strong {
      display: block;
      color: var(--text);
      font-size: 0.84rem;
      text-transform: uppercase;
    }
    .footer-item span {
      color: var(--muted);
      font-size: 0.84rem;
    }
    /* Reference UI ready pass */
    .topbar {
      display: grid;
      grid-template-columns:
        minmax(176px, 190px) minmax(168px, 184px) minmax(176px, 204px)
        minmax(188px, 210px) minmax(214px, 250px) minmax(144px, 162px)
        minmax(138px, 156px) 64px;
      gap: 0;
      align-items: stretch;
      min-height: 91px;
      padding: 0;
      background: var(--header-bg);
    }
    .brand-cluster,
    .pair-tile,
    .top-metric,
    .notification-bell {
      min-width: 0;
      border-right: 1px solid var(--line-soft);
      padding: 14px 18px;
      display: flex;
      align-items: center;
    }
    .brand-cluster {
      gap: 12px;
    }
    .brand-cluster .app-mark {
      width: 44px;
      height: 44px;
      border-radius: 0;
      font-size: 0;
      position: relative;
      background: transparent;
      box-shadow: none;
      clip-path: polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0 50%);
      border: 0;
    }
    .brand-cluster .app-mark::before {
      content: "";
      width: 34px;
      height: 34px;
      display: block;
      background:
        linear-gradient(30deg, transparent 34%, var(--accent) 35% 48%, transparent 49%),
        linear-gradient(150deg, transparent 34%, var(--accent-bright) 35% 48%, transparent 49%),
        linear-gradient(270deg, transparent 34%, #1b63d7 35% 48%, transparent 49%);
      clip-path: polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0 50%);
    }
    .brand-cluster .app-mark::after {
      content: "";
      position: absolute;
      inset: 13px;
      border: 3px solid #6cb6ff;
      clip-path: polygon(25% 5%, 75% 5%, 100% 50%, 75% 95%, 25% 95%, 0 50%);
    }
    .brand-cluster h1 {
      font-size: 31px;
      line-height: 0.92;
    }
    .brand-cluster .app-kicker {
      margin-top: 6px;
      font-size: 9px;
      color: #c5d4e7;
    }
    .pair-tile {
      gap: 14px;
    }
    .coin-mark {
      width: 42px;
      height: 42px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      background: linear-gradient(135deg, #ffb13d, var(--orange));
      color: white;
      font-weight: 900;
      box-shadow: 0 0 0 6px rgba(247, 147, 26, 0.12);
    }
    .coin-mark {
      font-size: 0;
    }
    .coin-mark::before {
      content: "\\20BF";
      font-size: 23px;
    }
    .pair-tile strong {
      display: block;
      font-size: 16px;
      line-height: 1.15;
    }
    .pair-tile span {
      color: var(--muted);
      font-size: 13px;
    }
    .top-metric {
      flex-direction: column;
      align-items: flex-start;
      justify-content: center;
      gap: 5px;
    }
    .top-metric > span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .top-metric > strong {
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 15px;
      line-height: 1.15;
    }
    .price-metric strong {
      font-size: 25px;
      color: #f6fbff;
    }
    .top-metric small {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
    }
    .top-metric small.good,
    .top-metric small .good {
      color: var(--good);
    }
    .status-pill,
    .connection-pill,
    .mode-select {
      min-height: 34px;
      border-radius: 8px;
      padding: 6px 12px;
      border: 1px solid rgba(47, 129, 255, 0.34);
      background: rgba(47, 129, 255, 0.2);
      color: #dfefff;
      font-weight: 900;
      text-transform: uppercase;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      max-width: 100%;
    }
    .status-pill::before {
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: currentColor;
      flex: 0 0 auto;
    }
    .status-pill.good {
      border-color: rgba(50, 213, 131, 0.5);
      background: rgba(50, 213, 131, 0.16);
      color: var(--good);
    }
    .status-pill.bad {
      border-color: rgba(255, 92, 92, 0.5);
      background: rgba(255, 92, 92, 0.16);
      color: var(--bad);
    }
    .status-pill.warn {
      border-color: rgba(255, 184, 77, 0.5);
      background: rgba(255, 184, 77, 0.16);
      color: var(--warn);
    }
    .connection-pill {
      border-color: rgba(50, 213, 131, 0.28);
      background: rgba(50, 213, 131, 0.12);
      color: var(--good);
      font-size: 13px;
    }
    .connection-pill.good {
      border-color: rgba(50, 213, 131, 0.5);
      background: rgba(50, 213, 131, 0.16);
      color: var(--good);
    }
    .connection-pill.warn {
      border-color: rgba(255, 184, 77, 0.5);
      background: rgba(255, 184, 77, 0.16);
      color: var(--warn);
    }
    .mode-select {
      min-width: 0;
      width: 100%;
      border: 0;
      background: linear-gradient(180deg, #145ddf, #0c3d97);
      color: white;
      cursor: pointer;
      text-transform: none;
      font-size: 15px;
    }
    .mode-metric small {
      display: flex;
      gap: 5px;
      flex-wrap: wrap;
    }
    .mode-metric small b {
      font-size: 9px;
      color: var(--muted);
    }
    .mode-metric small b:first-child {
      color: #79bdff;
    }
    .notification-bell {
      justify-content: center;
      position: relative;
      background: transparent;
      border-top: 0;
      border-bottom: 0;
      border-left: 0;
      border-radius: 0;
      box-shadow: none;
      color: #dce8f7;
      padding: 0;
    }
    .notification-bell span {
      width: 44px;
      height: 44px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line-strong);
      border-radius: 999px;
      background: rgba(14, 34, 48, 0.72);
      font-weight: 900;
    }
    .notification-bell strong {
      position: absolute;
      top: 26px;
      right: 17px;
      min-width: 18px;
      height: 18px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: var(--accent);
      color: white;
      font-size: 10px;
      line-height: 1;
    }
    .dashboard-shell {
      grid-template-columns: 184px minmax(0, 1fr);
    }
    body.sidebar-collapsed .dashboard-shell {
      grid-template-columns: 76px minmax(0, 1fr);
    }
    body.sidebar-collapsed .side-copy,
    body.sidebar-collapsed .collapse-note {
      font-size: 0;
    }
    body.sidebar-collapsed .side-link {
      grid-template-columns: 1fr;
      justify-items: center;
      padding-inline: 8px;
    }
    .sidebar {
      top: 91px;
      height: calc(100vh - 91px);
      padding: 14px 0 18px;
      background: var(--sidebar-bg);
    }
    .side-nav {
      gap: 10px;
      padding: 0 10px;
    }
    button.side-link,
    a.side-link {
      min-height: 56px;
      height: auto;
      border-radius: 8px;
      color: #a9b8cb;
    }
    .side-icon {
      border: 0;
      background: transparent;
      color: #9db7d6;
      font-size: 0.76rem;
    }
    button.side-link.active,
    a.side-link.active {
      background: linear-gradient(90deg, rgba(47, 129, 255, 0.42), rgba(47, 129, 255, 0.13));
      border-color: rgba(47, 129, 255, 0.36);
      color: #7fbdff;
    }
    .collapse-note {
      min-height: 38px;
      margin: 0 10px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      box-shadow: none;
      text-align: left;
    }
    .dashboard-content {
      padding-top: 14px;
      overflow-x: hidden;
    }
    main {
      max-width: 1680px;
      min-width: 0;
      width: 100%;
      gap: 12px;
      padding: 0 20px 18px;
    }
    section {
      background: var(--panel);
      border-color: var(--line);
      border-radius: 9px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    section[data-view~="beginner"],
    section[data-view~="advanced_trader"],
    section[data-view~="strategy_lab"] {
      border-top: 1px solid #223747;
    }
    h2 {
      justify-content: space-between;
      text-transform: uppercase;
      letter-spacing: 0;
      color: #f2f7ff;
    }
    h2::before {
      display: none;
    }
    .recommendation-card {
      min-height: 274px;
      border-color: rgba(47, 129, 255, 0.86);
      box-shadow: inset 0 0 0 1px rgba(47, 129, 255, 0.2);
    }
    .recommendation-card .command-label {
      margin: 14px 0 10px;
      text-align: center;
      font-size: clamp(60px, 5.2vw, 78px);
      line-height: 0.95;
      color: #2f8cff;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    .confidence-pill {
      width: max-content;
      max-width: 100%;
      margin: 0 auto 14px;
      border: 1px solid rgba(47, 129, 255, 0.8);
      border-radius: 999px;
      padding: 8px 18px;
      color: #79bdff;
      background: rgba(47, 129, 255, 0.08);
      font-weight: 900;
      font-size: 17px;
    }
    .command-summary {
      display: grid;
      grid-template-columns: 1fr 136px;
      gap: 18px;
      border-top: 1px solid var(--line);
      padding-top: 14px;
    }
    .command-summary > div + div {
      border-left: 1px solid var(--line);
      padding-left: 18px;
    }
    .command-summary span {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      font-size: 12px;
      font-weight: 800;
    }
    .command-summary p {
      margin: 0;
      color: #f4f8ff;
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .command-summary strong {
      color: #69b7ff;
      font-size: 23px;
    }
    .detail-dl {
      display: none;
    }
    .why-card {
      grid-column: span 3;
      min-height: 274px;
      padding: 0;
    }
    .why-card h2 {
      min-height: 44px;
      margin: 0;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      align-items: center;
    }
    .why-list {
      display: grid;
      max-height: calc(100% - 44px);
      overflow-y: auto;
      scrollbar-gutter: stable;
    }
    .why-row {
      display: grid;
      grid-template-columns: 26px minmax(0, 1fr) 20px;
      gap: 10px;
      align-items: center;
      min-height: 46px;
      padding: 6px 14px;
      border-bottom: 1px solid var(--line);
      line-height: 1.25;
    }
    .why-row:last-child {
      border-bottom: 0;
    }
    .why-icon,
    .why-info {
      width: 25px;
      height: 25px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 900;
    }
    .why-icon.good { background: rgba(50, 213, 131, 0.18); color: var(--good); }
    .why-icon.warn { background: rgba(255, 184, 77, 0.18); color: var(--warn); }
    .why-info {
      border: 1px solid var(--line-strong);
      color: var(--muted);
      font-size: 11px;
    }
    .portfolio-card {
      min-height: 274px;
    }
    .portfolio-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .portfolio-grid article {
      position: relative;
      min-height: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(14, 34, 48, 0.68);
      padding: 12px;
      display: grid;
      align-content: start;
      gap: 6px;
      overflow: hidden;
    }
    .portfolio-grid article::after {
      position: absolute;
      top: 12px;
      right: 10px;
      width: 20px;
      height: 20px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      font-size: 13px;
      font-weight: 900;
      background: var(--accent-bg);
      color: var(--accent);
    }
    .portfolio-grid article:nth-child(1)::after { content: "\\25A6"; }
    .portfolio-grid article:nth-child(2)::after {
      content: "$";
      background: var(--good-bg);
      color: var(--good);
    }
    .portfolio-grid article:nth-child(3)::after {
      content: "\\20BF";
      background: rgba(247, 147, 26, 0.16);
      color: #f7931a;
    }
    .portfolio-grid article:nth-child(4)::after {
      content: "\\2197";
      background: var(--good-bg);
      color: var(--good);
    }
    .portfolio-grid span {
      color: var(--muted);
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
      max-width: calc(100% - 26px);
    }
    .portfolio-grid strong {
      color: #f4f8ff;
      font-size: clamp(15px, 1.18vw, 21px);
      line-height: 1.1;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .portfolio-grid small {
      color: var(--muted);
      font-size: 10px;
      line-height: 1.25;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .portfolio-grid i {
      height: 16px;
      border-radius: 999px;
      opacity: 0.8;
      background:
        linear-gradient(
          135deg,
          transparent 0 18%,
          rgba(50, 213, 131, 0.5) 18% 22%,
          transparent 22% 42%,
          rgba(50, 213, 131, 0.45) 42% 47%,
          transparent 47% 65%,
          rgba(50, 213, 131, 0.55) 65% 70%,
          transparent 70%
        );
    }
    .controls-card {
      min-height: 176px;
    }
    .control-tiles {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .action-tile {
      min-height: 56px;
      display: grid;
      grid-template-columns: 24px minmax(0, 1fr);
      align-items: center;
      gap: 2px 9px;
      border-radius: 8px;
      padding: 9px 12px;
      background: rgba(14, 34, 48, 0.8);
      box-shadow: none;
      text-align: left;
    }
    .action-tile::before {
      grid-row: 1 / 3;
      width: 22px;
      height: 22px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      font-weight: 900;
      font-size: 11px;
      background: currentColor;
      box-shadow: inset 0 0 0 26px rgba(0, 0, 0, 0.55);
      color: inherit;
    }
    .approve-tile::before { content: "\\2713"; }
    .reject-tile::before { content: "\\2715"; }
    .pause-tile::before { content: "\\275A\\275A"; font-size: 10px; }
    .danger-tile::before { content: "\\26A0"; }
    .action-tile strong {
      font-size: 14px;
      text-transform: uppercase;
      line-height: 1.1;
    }
    .action-tile span {
      color: #f2f7ff;
      font-size: 12px;
      font-weight: 500;
      line-height: 1.15;
    }
    .approve-tile {
      border-color: rgba(50, 213, 131, 0.5);
      color: var(--good);
      background: rgba(50, 213, 131, 0.11);
    }
    .reject-tile {
      border-color: rgba(255, 92, 92, 0.5);
      color: var(--bad);
      background: rgba(255, 92, 92, 0.11);
    }
    .pause-tile {
      border-color: rgba(255, 184, 77, 0.5);
      color: var(--warn);
      background: rgba(255, 184, 77, 0.11);
    }
    .danger-tile {
      border-color: rgba(255, 92, 92, 0.56);
      color: #ff6b72;
      background: rgba(255, 92, 92, 0.13);
    }
    .compact-action {
      min-height: 30px;
      justify-content: center;
      padding: 5px 8px;
      font-size: 12px;
    }
    #approval_reason {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.2;
    }
    .ai-card {
      grid-column: span 7;
      min-height: 148px;
    }
    .ai-body {
      display: grid;
      grid-template-columns: 112px minmax(0, 1fr);
      gap: 18px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 16px;
    }
    .bot-avatar {
      width: 72px;
      height: 72px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      justify-self: center;
      border: 1px solid var(--line-strong);
      background: radial-gradient(circle, #1a74dc, #0d2638);
      color: #dff0ff;
      font-weight: 900;
    }
    .ai-card ul {
      padding-left: 0;
      list-style: none;
      line-height: 1.55;
    }
    .ai-meta {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }
    .ai-meta b {
      border-radius: 999px;
      padding: 2px 9px;
      background: rgba(50, 213, 131, 0.14);
      color: var(--good);
    }
    .activity-card {
      grid-column: span 5;
      min-height: 334px;
    }
    .text-link {
      min-height: 0;
      border: 0;
      background: transparent;
      color: #62adff;
      padding: 0;
      box-shadow: none;
      font-size: 13px;
    }
    .activity-timeline ul {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 12px;
    }
    .activity-card .activity-timeline {
      max-height: 268px;
      overflow: hidden;
    }
    .activity-row {
      display: grid;
      grid-template-columns: 86px 28px minmax(0, 1fr) auto;
      gap: 10px;
      align-items: start;
      color: #d9e5f5;
    }
    .activity-time {
      color: var(--muted);
      font-size: 12px;
      padding-top: 4px;
    }
    .activity-dot {
      width: 24px;
      height: 24px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line-strong);
      color: #62adff;
      font-size: 12px;
      font-weight: 900;
    }
    .activity-copy strong {
      display: block;
      margin-bottom: 3px;
    }
    .activity-copy span {
      color: var(--muted);
      font-size: 12px;
    }
    .activity-tag {
      border-radius: 5px;
      padding: 5px 8px;
      background: rgba(47, 129, 255, 0.16);
      color: #69b7ff;
      font-size: 11px;
      font-weight: 900;
    }
    .activity-tag.action { background: rgba(255, 92, 92, 0.16); color: #ff6b72; }
    .activity-tag.system { background: rgba(50, 213, 131, 0.14); color: var(--good); }
    .activity-tag.warning { background: rgba(255, 184, 77, 0.14); color: var(--warn); }
    body.mode-beginner section,
    body.mode-advanced_trader section,
    body.mode-strategy_lab section {
      order: 30;
    }
    body.mode-beginner main,
    body.mode-advanced_trader main,
    body.mode-strategy_lab main {
      grid-template-columns: repeat(15, minmax(0, 1fr));
      grid-template-areas:
        "r r r r r w w w w p p p p p p"
        "c c c c c c c c c a a a a a a"
        "x x x x x x x x x a a a a a a"
        "k k k t t t n n n n d d g g g"
        "z z z z z z z z z z z z z z z";
      align-items: stretch;
      gap: 12px;
      max-width: 1680px;
      padding: 0 20px 18px;
    }
    body.mode-beginner main {
      grid-template-areas:
        "r r r r r w w w w p p p p p p"
        "c c c c c c c c c a a a a a a"
        "x x x x x x x x x a a a a a a"
        "k k k k k k k n n n n n n n n"
        "z z z z z z z z z z z z z z z";
    }
    body.mode-beginner section[data-view~="beginner"],
    body.mode-advanced_trader section[data-view~="beginner"],
    body.mode-strategy_lab section[data-view~="beginner"] {
      width: 100%;
      min-width: 0;
      padding: 16px;
      font-size: 0.92rem;
    }
    body.mode-beginner .recommendation-card,
    body.mode-advanced_trader .recommendation-card,
    body.mode-strategy_lab .recommendation-card {
      order: 1;
      grid-area: r;
      height: 274px;
    }
    body.mode-beginner .why-card,
    body.mode-advanced_trader .why-card,
    body.mode-strategy_lab .why-card {
      order: 2;
      grid-area: w;
      height: 274px;
    }
    body.mode-beginner .portfolio-card,
    body.mode-advanced_trader .portfolio-card,
    body.mode-strategy_lab .portfolio-card {
      order: 3;
      grid-area: p;
      height: 274px;
    }
    body.mode-beginner .controls-card,
    body.mode-advanced_trader .controls-card,
    body.mode-strategy_lab .controls-card {
      order: 4;
      grid-area: c;
      height: 176px;
    }
    body.mode-beginner .activity-card,
    body.mode-advanced_trader .activity-card,
    body.mode-strategy_lab .activity-card {
      order: 5;
      grid-area: a;
      height: 334px;
    }
    body.mode-beginner .ai-card,
    body.mode-advanced_trader .ai-card,
    body.mode-strategy_lab .ai-card {
      order: 6;
      grid-area: x;
      height: 148px;
    }
    body.mode-beginner section:has(#risk_safety_summary),
    body.mode-advanced_trader section:has(#risk_safety_summary),
    body.mode-strategy_lab section:has(#risk_safety_summary) {
      order: 8;
      grid-area: k;
      height: 192px;
    }
    body.mode-beginner section:has(#risk_safety_summary) {
      grid-column: auto / auto;
    }
    body.mode-beginner section:has(#runtime_telemetry),
    body.mode-advanced_trader section:has(#runtime_telemetry),
    body.mode-strategy_lab section:has(#runtime_telemetry) {
      order: 9;
      grid-area: t;
      height: 192px;
    }
    body.mode-beginner section:has(#transactions),
    body.mode-advanced_trader section:has(#transactions),
    body.mode-strategy_lab section:has(#transactions) {
      order: 10;
      grid-area: n;
      height: 192px;
    }
    body.mode-beginner section:has(#transactions) {
      grid-column: auto / auto;
    }
    body.mode-beginner section:has(#readiness_gate),
    body.mode-advanced_trader section:has(#readiness_gate),
    body.mode-strategy_lab section:has(#readiness_gate) {
      order: 11;
      grid-area: d;
      height: 192px;
    }
    body.mode-beginner section:has(#glossary),
    body.mode-advanced_trader section:has(#glossary),
    body.mode-strategy_lab section:has(#glossary) {
      order: 12;
      grid-area: g;
      height: 192px;
    }
    body.mode-beginner #warning,
    body.mode-advanced_trader #warning,
    body.mode-strategy_lab #warning {
      grid-area: z;
    }
    body.mode-advanced_trader section[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab section[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab section[data-view~="strategy_lab"]:not([data-view~="beginner"]) {
      grid-area: auto;
    }
    body.mode-advanced_trader .span-8[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab .span-8[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab .span-8[data-view~="strategy_lab"]:not([data-view~="beginner"]) {
      grid-column: span 10;
    }
    body.mode-advanced_trader .span-4[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab .span-4[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab .span-4[data-view~="strategy_lab"]:not([data-view~="beginner"]) {
      grid-column: span 5;
    }
    body.mode-advanced_trader .span-6[data-view~="advanced_trader"]:not([data-view~="beginner"]),
    body.mode-strategy_lab .span-6[data-view~="advanced_trader"]:not([data-view~="beginner"]) {
      grid-column: span 5;
    }
    body.mode-strategy_lab .span-6[data-view~="strategy_lab"]:not([data-view~="beginner"]) {
      grid-column: 1 / -1;
    }
    .status-footer {
      grid-template-columns: repeat(6, minmax(120px, 1fr));
    }
    body.mode-strategy_lab section[data-view~="strategy_lab"] {
      max-height: min(72vh, 740px);
    }
    @media (max-width: 1180px) {
      .topbar {
        position: static;
        grid-template-columns:
          172px 174px minmax(160px, 1fr) minmax(220px, 1.05fr)
          150px 168px 146px 56px;
        min-width: 1120px;
      }
      .brand-cluster,
      .pair-tile,
      .top-metric,
      .notification-bell {
        min-height: 86px;
      }
      main {
        grid-template-columns: repeat(12, minmax(0, 1fr));
        min-width: 1120px;
        padding: 12px;
      }
      .market-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); padding: 0 12px; }
      .dashboard-shell { grid-template-columns: 196px minmax(0, 1fr); }
      .side-link { grid-template-columns: 28px minmax(0, 1fr); justify-items: stretch; }
      .side-copy { display: grid; }
      .collapse-note { display: block; }
      .span-3, .span-4, .span-5,
      .span-6 { grid-column: span 3; }
      .span-7, .span-8, .span-12 { grid-column: span 6; }
      body.mode-beginner main {
        grid-template-columns: repeat(12, minmax(0, 1fr));
      }
      body.mode-advanced_trader section:has(#beginner_command),
      body.mode-advanced_trader section:has(#strategy),
      body.mode-advanced_trader section:has(#portfolio),
      body.mode-advanced_trader section:has(#approval_reason),
      body.mode-advanced_trader section:has(#transactions),
      body.mode-advanced_trader section:has(#explanation),
      body.mode-advanced_trader section:has(#readiness_gate),
      body.mode-advanced_trader section:has(#glossary),
      body.mode-strategy_lab section:has(#beginner_command),
      body.mode-strategy_lab section:has(#strategy),
      body.mode-strategy_lab section:has(#portfolio),
      body.mode-strategy_lab section:has(#approval_reason),
      body.mode-strategy_lab section:has(#transactions),
      body.mode-strategy_lab section:has(#explanation),
      body.mode-strategy_lab section:has(#readiness_gate),
      body.mode-strategy_lab section:has(#glossary) { min-height: auto; }
      .selector-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .status-footer { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      body.mode-beginner .activity-card { grid-row: auto; }
    }
    @media (max-width: 760px) {
      .topbar {
        grid-template-columns:
          172px 174px minmax(160px, 1fr) minmax(220px, 1.05fr)
          150px 168px 146px 56px;
      }
      .brand-cluster,
      .pair-tile,
      .top-metric,
      .notification-bell {
        min-height: 76px;
        padding: 12px;
      }
      .price-metric strong {
        font-size: 20px;
      }
      main {
        grid-template-columns: repeat(12, minmax(0, 1fr));
        min-width: 1120px;
        padding: 10px;
      }
      .market-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); padding: 0 10px; }
      .dashboard-shell { grid-template-columns: 196px minmax(0, 1fr); }
      .sidebar {
        position: sticky;
        height: calc(100vh - 106px);
        border-right: 1px solid var(--line);
        border-bottom: 0;
      }
      .side-nav {
        grid-template-columns: 1fr;
      }
      .side-link {
        min-height: 48px;
      }
      .span-3, .span-4, .span-5,
      .span-6, .span-7, .span-8,
      .span-12 { grid-column: span 12; }
      header { align-items: stretch; }
      h1 { font-size: 18px; }
      .header-tools { width: 100%; }
      .mode-selector { width: 100%; }
      .mode-select { flex: 1; min-width: 0; }
      .mode-button { border-right: 0; border-bottom: 1px solid var(--line); }
      .mode-button:last-child { border-bottom: 0; }
      .selector-grid { grid-template-columns: 1fr; }
      .ticket-grid { grid-template-columns: 1fr; }
      .depth-grid { grid-template-columns: 1fr; }
      section { max-height: none; }
      body.mode-beginner section[data-view~="beginner"] { max-height: none; }
      dl { grid-template-columns: 1fr; }
      dd { text-align: left; }
      table { min-width: 520px; }
      .status-footer { grid-template-columns: 1fr; }
      .footer-item { border-right: 0; border-bottom: 1px solid var(--line); }
    }
    @media (max-width: 460px) {
      .topbar {
        grid-template-columns: 1fr;
      }
      .market-strip { grid-template-columns: 1fr; }
      .badges { width: 100%; }
      .badge { flex: 1 1 92px; justify-content: center; }
    }
    body.mode-beginner main {
      grid-template-columns: repeat(15, minmax(0, 1fr)) !important;
      grid-template-areas:
        "r r r r r w w w w p p p p p p"
        "c c c c c c c c c a a a a a a"
        "x x x x x x x x x a a a a a a"
        "k k k k k k k n n n n n n n n"
        "z z z z z z z z z z z z z z z" !important;
    }
    body.mode-advanced_trader main,
    body.mode-strategy_lab main {
      grid-template-columns: repeat(15, minmax(0, 1fr)) !important;
      grid-template-areas:
        "r r r r r w w w w p p p p p p"
        "c c c c c c c c c a a a a a a"
        "x x x x x x x x x a a a a a a"
        "k k k k k k k n n n n n n n n"
        "t t t t t t t d d d d d d d d"
        "z z z z z z z z z z z z z z z" !important;
    }
    body.mode-beginner section:has(#risk_safety_summary),
    body.mode-advanced_trader section:has(#risk_safety_summary),
    body.mode-strategy_lab section:has(#risk_safety_summary) {
      grid-area: k !important;
      grid-column: 1 / 8 !important;
      height: 192px;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    body.mode-beginner section:has(#transactions),
    body.mode-advanced_trader section:has(#transactions),
    body.mode-strategy_lab section:has(#transactions) {
      grid-area: n !important;
      grid-column: 8 / 16 !important;
      height: 192px;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    body.mode-advanced_trader section:has(#runtime_telemetry),
    body.mode-strategy_lab section:has(#runtime_telemetry) {
      grid-area: t !important;
      grid-column: 1 / 8 !important;
      height: 192px;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    body.mode-advanced_trader section:has(#readiness_gate),
    body.mode-strategy_lab section:has(#readiness_gate) {
      grid-area: d !important;
      grid-column: 8 / 16 !important;
      height: 192px;
      overflow: auto;
      scrollbar-gutter: stable;
    }
    body.mode-advanced_trader section:has(#glossary),
    body.mode-strategy_lab section:has(#glossary) {
      grid-column: 1 / -1 !important;
      height: 192px;
      overflow: auto;
      scrollbar-gutter: stable;
    }
  </style>
</head>
<body data-dashboard-build="shared-lower-cards-v1">
  <header class="topbar">
    <div class="brand-cluster">
      <span class="app-mark" aria-hidden="true">A</span>
      <div>
        <h1>ABTP</h1>
        <div class="app-kicker">AI Backtesting<br>Trading Platform</div>
      </div>
    </div>
    <div class="pair-tile">
      <span class="coin-mark" aria-hidden="true">B</span>
      <div>
        <strong id="strip_symbol">BTC/USDT</strong>
        <span id="header_source">Binance</span>
      </div>
    </div>
    <div class="top-metric price-metric">
      <span>Current Price</span>
      <strong id="strip_price">not_available</strong>
      <small id="strip_change_24h">not_available</small>
    </div>
    <div class="top-metric status-metric">
      <span>Market Status</span>
      <strong class="status-pill" id="strip_signal">not_available</strong>
      <small>Trend Strength: <b id="strip_trend_strength">not_available</b></small>
    </div>
    <div class="top-metric mode-metric">
      <span>Mode</span>
      <select class="mode-select" id="trading_mode_select" aria-label="Trading mode">
        <option value="paper">Paper Trading</option>
        <option value="live">Live Trading</option>
      </select>
      <small>
        <b id="mode">PAPER MODE</b> <b id="safe">SAFE MODE</b>
        <b id="live">LIVE OFF</b>
      </small>
    </div>
    <div class="top-metric connection-metric">
      <span>Connection</span>
      <strong class="connection-pill" id="strip_connection">not_configured</strong>
      <small id="strip_latency">not_available ms</small>
    </div>
    <div class="top-metric updated-metric">
      <span>Last Updated</span>
      <strong id="strip_updated">not_available</strong>
      <small id="strip_next_check">not_available</small>
    </div>
    <button
      class="notification-bell"
      id="notification_bell"
      type="button"
      title="Mark notifications read"
    >
      <span aria-hidden="true">!</span>
      <strong id="strip_notifications">0</strong>
    </button>
  </header>
  <div class="dashboard-shell">
    <aside class="sidebar" aria-label="Dashboard navigation">
      <nav class="side-nav">
        <button class="side-link mode-button" data-ui-mode="beginner">
          <span class="side-icon">DB</span>
          <span class="side-copy"><strong>Beginner</strong><span>Simple paper view</span></span>
        </button>
        <button class="side-link mode-button" data-ui-mode="advanced_trader">
          <span class="side-icon">AT</span>
          <span class="side-copy">
            <strong>Advanced</strong><span>Charts &amp; evidence</span>
          </span>
        </button>
        <button class="side-link mode-button" data-ui-mode="strategy_lab">
          <span class="side-icon">SL</span>
          <span class="side-copy">
            <strong>Strategy Mode</strong><span>Research workspace</span>
          </span>
        </button>
        <button
          class="side-link panel-jump"
          data-ui-mode="advanced_trader"
          data-panel-target="backtest_summary"
        >
          <span class="side-icon">BT</span>
          <span class="side-copy"><strong>Backtesting</strong><span>Embedded panel</span></span>
        </button>
        <a class="side-link" href="/paper-report" target="_blank" rel="noreferrer">
          <span class="side-icon">R</span>
          <span class="side-copy"><strong>Reports</strong><span>Paper status</span></span>
        </a>
        <button
          class="side-link panel-jump"
          data-ui-mode="advanced_trader"
          data-panel-target="triggered_alerts"
        >
          <span class="side-icon">AL</span>
          <span class="side-copy"><strong>Alerts</strong><span>Local rules</span></span>
        </button>
        <button class="side-link panel-jump" data-ui-mode="beginner" data-panel-target="logs">
          <span class="side-icon">LG</span>
          <span class="side-copy"><strong>Logs</strong><span>Activity timeline</span></span>
        </button>
        <button
          class="side-link panel-jump"
          data-ui-mode="beginner"
          data-panel-target="readiness_gate"
        >
          <span class="side-icon">ST</span>
          <span class="side-copy">
            <strong>Settings</strong><span>Preferences &amp; API keys</span>
          </span>
        </button>
      </nav>
      <button class="collapse-note" id="sidebar_toggle" type="button">Collapse</button>
    </aside>
    <div class="dashboard-content">
      <main>
    <section class="span-8" data-view="advanced_trader">
      <h2>Price Chart</h2>
      <div class="chart-toolbar">
        <div class="segmented" id="chart_timeframes" aria-label="Chart timeframe"></div>
        <div class="segmented" id="chart_indicators" aria-label="Chart overlays">
          <button class="chart-tool active" data-chart-overlay="sma_3">SMA</button>
          <button class="chart-tool active" data-chart-overlay="risk_lines">Risk</button>
          <button class="chart-tool active" data-chart-overlay="markers">Signals</button>
        </div>
        <div class="segmented" aria-label="Chart navigation">
          <button
            class="chart-tool"
            id="chart_pan_left"
            title="Pan left"
            aria-label="Pan left"
          >&larr;</button>
          <button class="chart-tool" id="chart_zoom_out" title="Zoom out">-</button>
          <button class="chart-tool" id="chart_zoom_in" title="Zoom in">+</button>
          <button
            class="chart-tool"
            id="chart_pan_right"
            title="Pan right"
            aria-label="Pan right"
          >&rarr;</button>
        </div>
      </div>
      <div class="ticket-grid">
        <label>Drawing<select id="drawing_type"></select></label>
        <label>Color<select id="drawing_color">
          <option value="#1264a3">Blue</option>
          <option value="#0f7b52">Green</option>
          <option value="#b42318">Red</option>
          <option value="#9a6700">Gold</option>
          <option value="#6941c6">Violet</option>
          <option value="#172026">Black</option>
        </select></label>
        <label>Start price<input id="drawing_start_price" inputmode="decimal"></label>
        <label>End price<input id="drawing_end_price" inputmode="decimal"></label>
        <label>Text<input id="drawing_text"></label>
      </div>
      <div class="controls">
        <button id="save_chart_drawing">Save Drawing</button>
      </div>
      <p id="drawing_message"></p>
      <div class="chart-wrap">
        <canvas class="chart-canvas" id="price_chart"></canvas>
        <div class="chart-tooltip" id="chart_tooltip"></div>
      </div>
      <div class="chart-readout" id="chart_readout"></div>
      <div id="chart_drawings"></div>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Backtest Summary</h2><dl id="backtest_summary"></dl>
    </section>
    <section class="span-4 recommendation-card" data-view="beginner advanced_trader strategy_lab">
      <h2>Current Recommendation</h2>
      <div class="command-label" id="beginner_command_label">Do nothing now</div>
      <div class="confidence-pill" id="command_confidence">CONFIDENCE: not_available</div>
      <div class="command-summary">
        <div>
          <span>Reason</span>
          <p id="command_reason">Waiting for paper dashboard state.</p>
        </div>
        <div>
          <span>Next Check In</span>
          <strong id="command_next_check">not_available</strong>
        </div>
      </div>
      <dl class="detail-dl" id="beginner_command"></dl>
    </section>
    <section class="span-4" data-view="advanced_trader strategy_lab">
      <h2>Market</h2><dl id="market"></dl>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Watchlist</h2><div id="watchlist"></div>
    </section>
    <section class="span-8" data-view="advanced_trader">
      <h2>Alerts</h2>
      <div class="ticket-grid">
        <label>Type<select id="alert_type"></select></label>
        <label>Symbol<select id="alert_symbol"></select></label>
        <label>Price threshold<input id="alert_threshold" inputmode="decimal"></label>
        <label>Recommendation<select id="alert_expected_value">
          <option value="">Any matching event</option>
          <option value="BUY">BUY</option>
          <option value="HOLD">HOLD</option>
          <option value="REJECTED">REJECTED</option>
          <option value="submit_paper_order_ticket">Paper order staged</option>
          <option value="cancel_paper_order">Paper order canceled</option>
        </select></label>
      </div>
      <div class="controls">
        <button id="add_alert_rule">Add Alert</button>
      </div>
      <p id="alert_message"></p>
      <div id="triggered_alerts"></div>
      <div id="alert_rules"></div>
    </section>
    <section class="span-8" data-view="beginner advanced_trader strategy_lab">
      <h2>Risk & Safety</h2>
      <dl id="risk_safety_summary"></dl>
      <div id="risk_safety_checks"></div>
      <div id="risk_safety_exchange"></div>
      <div id="risk_safety_reconciliation"></div>
    </section>
    <section class="span-8" data-view="advanced_trader">
      <h2>Order Book / Market Depth</h2><div id="order_book"></div>
    </section>
    <section class="span-8" data-view="advanced_trader">
      <h2>Order Flow / Recent Trades</h2><div id="order_flow"></div>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Paper Order Ticket</h2>
      <div class="ticket-grid">
        <label>Type<select id="ticket_order_type"></select></label>
        <label>Side<select id="ticket_side"></select></label>
        <label>BTC qty<input id="ticket_quantity" inputmode="decimal" value="0.01"></label>
        <label>Limit price<input id="ticket_limit_price" inputmode="decimal"></label>
        <label>Stop price<input id="ticket_stop_price" inputmode="decimal"></label>
        <label>Take profit<input id="ticket_take_profit_price" inputmode="decimal"></label>
      </div>
      <div class="controls">
        <button id="submit_paper_order">Stage Paper Order</button>
      </div>
      <p id="ticket_message"></p>
      <dl id="ticket_filters"></dl>
    </section>
    <section class="span-8" data-view="advanced_trader">
      <h2>Open Paper Orders</h2><div id="open_orders"></div>
    </section>
    <section class="span-8" data-view="advanced_trader">
      <h2>Trade Journal Analytics</h2>
      <dl id="journal_summary"></dl>
      <div class="ticket-grid">
        <label>Trade ref<select id="journal_trade_ref"></select></label>
        <label>Setup<select id="journal_setup_type"></select></label>
        <label>Tags<input id="journal_tags" placeholder="entry, patience, review"></label>
        <label>Chart context<input id="journal_chart_context"></label>
        <label>Notes<textarea id="journal_notes"></textarea></label>
        <label>Mistake review<textarea id="journal_mistake_review"></textarea></label>
        <label>Lesson<textarea id="journal_lesson"></textarea></label>
      </div>
      <div class="controls">
        <button id="save_journal_entry">Save Journal Entry</button>
      </div>
      <p id="journal_message"></p>
      <div id="journal_analytics"></div>
      <div id="journal_entries"></div>
    </section>
    <section class="span-8" data-view="advanced_trader strategy_lab">
      <h2>Trader Feedback</h2>
      <dl id="trader_feedback_summary"></dl>
      <div class="ticket-grid">
        <label>Reviewer<select id="feedback_reviewer_role"></select></label>
        <label>Category<select id="feedback_category"></select></label>
        <label>Severity<select id="feedback_severity"></select></label>
        <label>Summary<textarea id="feedback_summary"></textarea></label>
        <label>Recommendation<textarea id="feedback_recommendation"></textarea></label>
        <label>Resolution<textarea id="feedback_resolution"></textarea></label>
      </div>
      <div class="controls">
        <button id="save_trader_feedback">Save Feedback</button>
      </div>
      <p id="feedback_message"></p>
      <div id="trader_feedback_breakdown"></div>
      <div id="trader_feedback_items"></div>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Paper Position</h2>
      <dl id="position"></dl>
      <div class="controls" style="margin-top: 12px;">
        <button id="stage_close_position">Stage Close</button>
        <button class="secondary" id="stage_reduce_position">Stage Reduce</button>
      </div>
      <p id="position_message"></p>
    </section>
    <section class="span-4 why-card" data-view="beginner advanced_trader strategy_lab">
      <h2>Why?</h2>
      <div class="why-list" id="why_list"></div>
      <dl class="detail-dl" id="strategy"></dl>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Suggested Paper Trade</h2><dl id="trade"></dl>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Performance</h2><dl id="performance"></dl>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Exit Review</h2><dl id="exit_review"></dl>
    </section>
    <section class="span-4" data-view="advanced_trader">
      <h2>Exports</h2><div class="controls">
        <a class="button" href="/paper-transactions.csv" target="_blank" rel="noreferrer">
          Transactions CSV
        </a>
        <a class="button" href="/trader-feedback.csv" target="_blank" rel="noreferrer">
          Feedback CSV
        </a>
        <a class="button" href="/paper-report" target="_blank" rel="noreferrer">Paper Report</a>
        <a class="button" href="/trader-handoff.md" target="_blank" rel="noreferrer">
          Trader Handoff
        </a>
        <a class="button" href="/trader-evidence.json" target="_blank" rel="noreferrer">
          Evidence JSON
        </a>
      </div>
    </section>
    <section class="span-5 portfolio-card" data-view="beginner advanced_trader strategy_lab">
      <h2>Portfolio Overview</h2>
      <div class="portfolio-grid">
        <article>
          <span>Portfolio Value</span>
          <strong id="strip_equity">not_available</strong>
          <i data-spark="portfolio"></i>
        </article>
        <article>
          <span>Cash</span>
          <strong id="portfolio_cash_card">not_available</strong>
          <i data-spark="cash"></i>
        </article>
        <article>
          <span>BTC Holdings</span>
          <strong id="portfolio_btc_card">not_available</strong>
          <small id="portfolio_btc_value">not_available</small>
        </article>
        <article>
          <span>Today's P/L</span>
          <strong id="strip_today_pnl">not_available</strong>
          <small id="portfolio_today_pct">not_available</small>
        </article>
      </div>
      <dl class="detail-dl" id="portfolio"></dl>
    </section>
    <section class="span-7" data-view="advanced_trader strategy_lab">
      <h2>Runtime Telemetry</h2>
      <dl id="runtime_telemetry"></dl>
      <div id="portfolio_sparkline"></div>
    </section>
    <section class="span-7 controls-card" data-view="beginner advanced_trader strategy_lab">
      <h2>
        Controls
        <button
          class="text-link panel-jump"
          data-ui-mode="advanced_trader"
          data-panel-target="ticket_order_type"
          type="button"
        >Advanced</button>
      </h2>
      <div class="control-tiles">
        <button class="action-tile approve-tile" id="approve">
          <strong>Approve</strong><span>Execute Signal</span>
        </button>
        <button class="action-tile reject-tile" id="reject">
          <strong>Reject</strong><span>Skip Signal</span>
        </button>
        <button class="action-tile pause-tile" id="pause">
          <strong>Pause</strong><span>Pause Trading</span>
        </button>
        <button class="action-tile danger-tile" id="emergency">
          <strong>Emergency Stop</strong><span>Stop All Activity</span>
        </button>
        <button class="secondary compact-action" id="resume">Resume Paper Bot</button>
        <button class="secondary compact-action" id="reset_emergency">Reset Emergency Stop</button>
        <a
          class="button compact-action"
          href="/paper-report"
          target="_blank"
          rel="noreferrer"
        >Daily Report</a>
      </div>
      <p id="approval_reason"></p>
    </section>
    <section class="span-6 ai-card" data-view="beginner advanced_trader strategy_lab">
      <h2>AI Explanation</h2>
      <div class="ai-body">
        <div class="bot-avatar" aria-hidden="true">AI</div>
        <ul id="explanation"></ul>
      </div>
      <div class="ai-meta">
        <span>Model: GPT-4o</span>
        <b>Verified</b>
        <span id="explanation_confidence">Explanation Confidence: not_available</span>
      </div>
    </section>
    <section class="span-6" data-view="beginner advanced_trader strategy_lab">
      <h2>Paper Transactions</h2><div id="transactions"></div>
    </section>
    <section class="span-6" data-view="advanced_trader strategy_lab">
      <h2>Readiness Gate</h2><div id="readiness_gate"></div>
    </section>
    <section class="span-6" data-view="advanced_trader strategy_lab">
      <h2>Glossary</h2><div class="log"><dl id="glossary"></dl></div>
    </section>
    <section class="span-6 activity-card" data-view="beginner advanced_trader strategy_lab">
      <h2>
        Recent Activity
        <button class="text-link" id="view_all_activity" type="button">View All</button>
      </h2>
      <div class="activity-timeline"><ul id="logs"></ul></div>
    </section>
    <section class="span-8" data-view="strategy_lab">
      <h2>Strategy Lab</h2>
      <div class="selector-grid">
        <label>Strategy<select id="lab_strategy"></select></label>
        <label>Symbol<select id="lab_symbol"></select></label>
        <label>Timeframe<select id="lab_timeframe"></select></label>
        <label>Mode<select id="lab_run_mode"></select></label>
        <label>Parameters<select id="lab_parameter_profile"></select></label>
      </div>
      <dl id="strategy_lab"></dl>
    </section>
    <section class="span-4" data-view="strategy_lab">
      <h2>Required Evidence</h2><div id="strategy_lab_evidence"></div>
    </section>
    <section class="span-6" data-view="strategy_lab">
      <h2>Compare Runs</h2><div id="strategy_lab_compare"></div>
    </section>
      <section class="span-12 warning" id="warning"></section>
      </main>
      <footer class="status-footer" aria-label="System status">
        <div class="footer-item">
          <span class="footer-icon">P</span>
          <div><strong>Paper Mode</strong><span>Simulated Trading</span></div>
        </div>
        <div class="footer-item">
          <span class="footer-icon">D</span>
          <div><strong>Data Status</strong><span id="footer_data_status">Waiting</span></div>
        </div>
        <div class="footer-item">
          <span class="footer-icon">T</span>
          <div>
            <strong>Latency</strong><span id="footer_latency_status">not_available ms</span>
          </div>
        </div>
        <div class="footer-item">
          <span class="footer-icon">X</span>
          <div>
            <strong>Exchange</strong><span id="footer_exchange_status">not_configured</span>
          </div>
        </div>
        <div class="footer-item">
          <span class="footer-icon">S</span>
          <div>
            <strong>Risk Status</strong><span class="good" id="footer_risk_status">Safe Mode</span>
          </div>
        </div>
        <div class="footer-item">
          <span class="footer-icon">V</span>
          <div><strong>Version</strong><span id="strip_version">not_available</span></div>
        </div>
      </footer>
    </div>
  </div>
  <script>
    const UI_MODE_KEY = "abtp.paperDashboard.uiMode";
    const DEFAULT_UI_MODE = "beginner";
    let activeUiMode = localStorage.getItem(UI_MODE_KEY) || DEFAULT_UI_MODE;
    const fields = {
      market: document.getElementById("market"),
      watchlist: document.getElementById("watchlist"),
      triggeredAlerts: document.getElementById("triggered_alerts"),
      alertRules: document.getElementById("alert_rules"),
      alertType: document.getElementById("alert_type"),
      alertSymbol: document.getElementById("alert_symbol"),
      alertThreshold: document.getElementById("alert_threshold"),
      alertExpectedValue: document.getElementById("alert_expected_value"),
      alertMessage: document.getElementById("alert_message"),
      addAlertRule: document.getElementById("add_alert_rule"),
      riskSafetySummary: document.getElementById("risk_safety_summary"),
      riskSafetyChecks: document.getElementById("risk_safety_checks"),
      riskSafetyExchange: document.getElementById("risk_safety_exchange"),
      riskSafetyReconciliation: document.getElementById("risk_safety_reconciliation"),
      orderBook: document.getElementById("order_book"),
      orderFlow: document.getElementById("order_flow"),
      openOrders: document.getElementById("open_orders"),
      journalSummary: document.getElementById("journal_summary"),
      journalTradeRef: document.getElementById("journal_trade_ref"),
      journalSetupType: document.getElementById("journal_setup_type"),
      journalTags: document.getElementById("journal_tags"),
      journalChartContext: document.getElementById("journal_chart_context"),
      journalNotes: document.getElementById("journal_notes"),
      journalMistakeReview: document.getElementById("journal_mistake_review"),
      journalLesson: document.getElementById("journal_lesson"),
      journalMessage: document.getElementById("journal_message"),
      journalAnalytics: document.getElementById("journal_analytics"),
      journalEntries: document.getElementById("journal_entries"),
      saveJournalEntry: document.getElementById("save_journal_entry"),
      traderFeedbackSummary: document.getElementById("trader_feedback_summary"),
      feedbackReviewerRole: document.getElementById("feedback_reviewer_role"),
      feedbackCategory: document.getElementById("feedback_category"),
      feedbackSeverity: document.getElementById("feedback_severity"),
      feedbackSummary: document.getElementById("feedback_summary"),
      feedbackRecommendation: document.getElementById("feedback_recommendation"),
      feedbackResolution: document.getElementById("feedback_resolution"),
      feedbackMessage: document.getElementById("feedback_message"),
      traderFeedbackBreakdown: document.getElementById("trader_feedback_breakdown"),
      traderFeedbackItems: document.getElementById("trader_feedback_items"),
      saveTraderFeedback: document.getElementById("save_trader_feedback"),
      position: document.getElementById("position"),
      positionMessage: document.getElementById("position_message"),
      stageClosePosition: document.getElementById("stage_close_position"),
      stageReducePosition: document.getElementById("stage_reduce_position"),
      ticketOrderType: document.getElementById("ticket_order_type"),
      ticketSide: document.getElementById("ticket_side"),
      ticketQuantity: document.getElementById("ticket_quantity"),
      ticketLimitPrice: document.getElementById("ticket_limit_price"),
      ticketStopPrice: document.getElementById("ticket_stop_price"),
      ticketTakeProfitPrice: document.getElementById("ticket_take_profit_price"),
      ticketMessage: document.getElementById("ticket_message"),
      ticketFilters: document.getElementById("ticket_filters"),
      submitPaperOrder: document.getElementById("submit_paper_order"),
      strategy: document.getElementById("strategy"),
      trade: document.getElementById("trade"),
      portfolio: document.getElementById("portfolio"),
      beginnerCommand: document.getElementById("beginner_command"),
      strategyLab: document.getElementById("strategy_lab"),
      strategyLabEvidence: document.getElementById("strategy_lab_evidence"),
      strategyLabCompare: document.getElementById("strategy_lab_compare"),
      labStrategy: document.getElementById("lab_strategy"),
      labSymbol: document.getElementById("lab_symbol"),
      labTimeframe: document.getElementById("lab_timeframe"),
      labRunMode: document.getElementById("lab_run_mode"),
      labParameterProfile: document.getElementById("lab_parameter_profile"),
      beginnerCommandLabel: document.getElementById("beginner_command_label"),
      priceChart: document.getElementById("price_chart"),
      chartTimeframes: document.getElementById("chart_timeframes"),
      chartIndicators: document.getElementById("chart_indicators"),
      chartTooltip: document.getElementById("chart_tooltip"),
      chartReadout: document.getElementById("chart_readout"),
      chartDrawings: document.getElementById("chart_drawings"),
      drawingType: document.getElementById("drawing_type"),
      drawingColor: document.getElementById("drawing_color"),
      drawingStartPrice: document.getElementById("drawing_start_price"),
      drawingEndPrice: document.getElementById("drawing_end_price"),
      drawingText: document.getElementById("drawing_text"),
      drawingMessage: document.getElementById("drawing_message"),
      saveChartDrawing: document.getElementById("save_chart_drawing"),
      chartPanLeft: document.getElementById("chart_pan_left"),
      chartPanRight: document.getElementById("chart_pan_right"),
      chartZoomIn: document.getElementById("chart_zoom_in"),
      chartZoomOut: document.getElementById("chart_zoom_out"),
      backtestSummary: document.getElementById("backtest_summary"),
      performance: document.getElementById("performance"),
      exitReview: document.getElementById("exit_review"),
      glossary: document.getElementById("glossary"),
      transactions: document.getElementById("transactions"),
      readinessGate: document.getElementById("readiness_gate"),
      logs: document.getElementById("logs"),
      explanation: document.getElementById("explanation"),
      warning: document.getElementById("warning"),
      approvalReason: document.getElementById("approval_reason"),
      approve: document.getElementById("approve"),
      headerSource: document.getElementById("header_source"),
      commandConfidence: document.getElementById("command_confidence"),
      commandReason: document.getElementById("command_reason"),
      commandNextCheck: document.getElementById("command_next_check"),
      whyList: document.getElementById("why_list"),
      portfolioCashCard: document.getElementById("portfolio_cash_card"),
      portfolioBtcCard: document.getElementById("portfolio_btc_card"),
      portfolioBtcValue: document.getElementById("portfolio_btc_value"),
      portfolioTodayPct: document.getElementById("portfolio_today_pct"),
      stripSymbol: document.getElementById("strip_symbol"),
      stripPrice: document.getElementById("strip_price"),
      stripChange24h: document.getElementById("strip_change_24h"),
      stripTrendStrength: document.getElementById("strip_trend_strength"),
      stripSignal: document.getElementById("strip_signal"),
      stripEquity: document.getElementById("strip_equity"),
      stripTodayPnl: document.getElementById("strip_today_pnl"),
      stripConnection: document.getElementById("strip_connection"),
      stripLatency: document.getElementById("strip_latency"),
      stripNotifications: document.getElementById("strip_notifications"),
      stripVersion: document.getElementById("strip_version"),
      stripNextCheck: document.getElementById("strip_next_check"),
      stripUpdated: document.getElementById("strip_updated"),
      runtimeTelemetry: document.getElementById("runtime_telemetry"),
      portfolioSparkline: document.getElementById("portfolio_sparkline"),
      footerDataStatus: document.getElementById("footer_data_status"),
      footerLatencyStatus: document.getElementById("footer_latency_status"),
      footerExchangeStatus: document.getElementById("footer_exchange_status"),
      footerRiskStatus: document.getElementById("footer_risk_status"),
      notificationBell: document.getElementById("notification_bell"),
      sidebarToggle: document.getElementById("sidebar_toggle"),
      viewAllActivity: document.getElementById("view_all_activity"),
      explanationConfidence: document.getElementById("explanation_confidence"),
      tradingModeSelect: document.getElementById("trading_mode_select"),
      modeButtons: Array.from(document.querySelectorAll(".mode-button")),
      panelJumps: Array.from(document.querySelectorAll(".panel-jump"))
    };
    let nextCheckClientDeadline = null;
    const chartState = {
      timeframe: "1h",
      visibleCount: null,
      startIndex: 0,
      hoverIndex: null,
      overlays: {sma_3: true, risk_lines: true, markers: true},
      lastChart: null,
      layout: null,
      drawingStartTime: "",
      drawingEndTime: ""
    };
    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }
    function normalizedValue(value) {
      if (Array.isArray(value)) {
        return value.join(", ");
      }
      if (value === true) {
        return "true";
      }
      if (value === false) {
        return "false";
      }
      if (value === null || value === undefined || value === "") {
        return "not_available";
      }
      if (typeof value === "object") {
        return JSON.stringify(value);
      }
      return String(value);
    }
    function valueToneClass(value) {
      const text = normalizedValue(value).toLowerCase();
      if (["buy", "approved", "clear", "healthy", "true", "ready", "paper"].includes(text)) {
        return " value-good";
      }
      if (
        ["rejected", "false", "blocked", "bad", "emergency", "stale", "degraded"].some(
          (token) => text.includes(token)
        )
      ) {
        return " value-bad";
      }
      if (
        ["hold", "warning", "warn", "paused", "review", "not_available", "none"].some(
          (token) => text.includes(token)
        )
      ) {
        return " value-warn";
      }
      if (text.includes("paper") || text.includes("btc") || text.includes("usdt")) {
        return " value-accent";
      }
      return "";
    }
    function valueMarkup(value) {
      const text = normalizedValue(value);
      const numeric = Number(text);
      const numericTone = Number.isFinite(numeric)
        ? numeric > 0
          ? " metric-positive"
          : numeric < 0
            ? " metric-negative"
            : ""
        : "";
      return `<span class="value-chip${valueToneClass(value)}${numericTone}">`
        + `${escapeHtml(text)}</span>`;
    }
    function row(label, value) {
      return `<dt>${escapeHtml(label)}</dt><dd>${valueMarkup(value)}</dd>`;
    }
    function percentText(value) {
      if (value === null || value === undefined || value === "" || value === "not_available") {
        return "not_available";
      }
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return "not_available";
      }
      return `${numeric.toFixed(2).replace(/\\.00$/, "")}%`;
    }
    function compactMarketStatus(value) {
      const text = normalizedValue(value).replaceAll("_", " ");
      if (text === "not_available") {
        return text;
      }
      if (text.length <= 12) {
        return text;
      }
      return text
        .split(" ")
        .filter(Boolean)
        .map((word) => word.slice(0, 4))
        .join(" ");
    }
    function fill(id, data) {
      fields[id].innerHTML = Object.entries(data)
        .map(([k, v]) => row(k.replaceAll("_", " "), v))
        .join("");
    }
    function formatClock(value) {
      const timestamp = Date.parse(value || "");
      if (!Number.isFinite(timestamp)) {
        return "not_available";
      }
      return new Intl.DateTimeFormat([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      }).format(new Date(timestamp));
    }
    function formatCountdown(seconds) {
      const activeSeconds = Math.max(0, Number(seconds) || 0);
      const minutes = Math.floor(activeSeconds / 60);
      const remainder = activeSeconds % 60;
      if (minutes > 0) {
        return `${minutes}m ${String(remainder).padStart(2, "0")}s`;
      }
      return `${remainder}s`;
    }
    function asPercentFromConfidence(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return "not_available";
      }
      return `${Math.round(numeric * 100)}%`;
    }
    function fixedNumber(value, digits) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return "not_available";
      }
      return numeric.toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits
      });
    }
    function moneyText(value) {
      const text = fixedNumber(value, 2);
      return text === "not_available" ? text : `$${text}`;
    }
    function signedMoneyText(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return "not_available";
      }
      const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
      return `${sign}$${Math.abs(numeric).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}`;
    }
    function compactSignedMoneyText(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return "not_available";
      }
      const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
      const abs = Math.abs(numeric);
      if (abs >= 1000000) {
        return `${sign}$${(abs / 1000000).toFixed(2)}M`;
      }
      if (abs >= 10000) {
        return `${sign}$${(abs / 1000).toFixed(1)}K`;
      }
      return signedMoneyText(value);
    }
    function compactPercentText(value) {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        return "not_available";
      }
      return `${numeric.toFixed(Math.abs(numeric) >= 10 ? 1 : 2).replace(/\\.0$/, "")}%`;
    }
    function renderCommandCard(command, strategy, refresh) {
      const rawLabel = (command && command.label) || "WAIT";
      const label = /do nothing|hold/i.test(rawLabel) ? "WAIT" : rawLabel;
      const confidence = asPercentFromConfidence(strategy && strategy.ai_confidence);
      const reason =
        (strategy && strategy.explanation)
        || (command && command.plain_status)
        || "Waiting for paper dashboard state.";
      fields.beginnerCommandLabel.textContent = label;
      fields.commandConfidence.textContent = `CONFIDENCE: ${confidence}`;
      fields.commandReason.textContent = reason;
      fields.commandNextCheck.textContent = formatCountdown(
        refresh && refresh.next_check_in_seconds
      );
      fields.beginnerCommandLabel.classList.toggle("metric-positive", label === "BUY");
      fields.beginnerCommandLabel.classList.toggle("metric-negative", label === "REJECTED");
    }
    function renderWhyList(strategy, command) {
      const reasons = [
        ...((strategy && strategy.indicator_reasons) || []),
        (strategy && strategy.risk_decision) ? `Risk decision: ${strategy.risk_decision}` : "",
        (strategy && strategy.data_quality) ? `Data quality: ${strategy.data_quality}` : "",
        (command && command.actionable === false) ? "Recommendation is not actionable" : ""
      ].filter(Boolean);
      const rows = (reasons.length ? reasons : ["No extra evidence available yet."]).slice(0, 5);
      fields.whyList.innerHTML = rows.map((item, index) => {
        const tone = /approved|trusted|passed|normal|healthy/i.test(item)
          ? "good"
          : /not|below|weak|blocked|rejected|unavailable|missing/i.test(item)
            ? "warn"
            : index === 0
              ? "warn"
              : "good";
        const icon = tone === "good" ? "OK" : "!";
        return `
          <div class="why-row">
            <span class="why-icon ${tone}">${icon}</span>
            <span>${escapeHtml(item)}</span>
            <span class="why-info">i</span>
          </div>`;
      }).join("");
    }
    function renderPortfolioCards(portfolio) {
      fields.stripEquity.textContent = moneyText(
        portfolio.current_equity || portfolio.paper_equity
      );
      fields.portfolioCashCard.textContent = moneyText(portfolio.cash || portfolio.paper_cash);
      const btc = fixedNumber(portfolio.open_btc, 4);
      fields.portfolioBtcCard.textContent = btc === "not_available" ? btc : `${btc} BTC`;
      fields.portfolioBtcValue.textContent =
        portfolio.unrealized_pnl
          ? `Unrealized ${compactSignedMoneyText(portfolio.unrealized_pnl)}`
          : "not_available";
      fields.stripTodayPnl.textContent = signedMoneyText(portfolio.today_pnl);
      fields.portfolioTodayPct.textContent = compactPercentText(portfolio.today_pnl_pct);
      fields.stripTodayPnl.classList.toggle(
        "metric-positive",
        Number(portfolio.today_pnl || 0) > 0
      );
      fields.stripTodayPnl.classList.toggle(
        "metric-negative",
        Number(portfolio.today_pnl || 0) < 0
      );
    }
    function activityTime(value) {
      const text = formatClock(value);
      return text === "not_available" ? "--:--:--" : text;
    }
    function renderActivityTimeline(activity, fallbackLogs) {
      const items = (activity && activity.items && activity.items.length)
        ? activity.items
        : (fallbackLogs || []).map((item) => ({
            event_type: item.event_type,
            message: item.message,
            reason: item.reason,
            occurred_at: item.occurred_at,
            severity: "info",
            status_label: "INFO"
          }));
      if (!items.length) {
        fields.logs.innerHTML = '<li class="empty">No recent paper activity yet.</li>';
        return;
      }
      fields.logs.innerHTML = items.slice(0, 5).map((item) => {
        const severity = item.severity || "info";
        return `
          <li class="activity-row">
            <span class="activity-time">${escapeHtml(activityTime(item.occurred_at))}</span>
            <span class="activity-dot">${severity === "action" ? "!" : "OK"}</span>
            <span class="activity-copy">
              <strong>${escapeHtml((item.event_type || "activity").replaceAll("_", " "))}</strong>
              <span>${escapeHtml(item.message || item.reason || "Paper dashboard activity")}</span>
            </span>
            <span class="activity-tag ${escapeHtml(severity)}">
              ${escapeHtml(item.status_label || "INFO")}
            </span>
          </li>`;
      }).join("");
    }
    function applyShellPreferences(ui) {
      const collapsed = Boolean(ui && ui.sidebar_collapsed);
      document.body.classList.toggle("sidebar-collapsed", collapsed);
      fields.sidebarToggle.textContent = collapsed ? "Expand" : "Collapse";
    }
    function updateMarketStrip(data) {
      const market = data.market || {};
      const strategy = data.strategy || {};
      const portfolio = data.portfolio || {};
      const notifications = data.notifications || {};
      const app = data.app || {};
      fields.stripSymbol.textContent = market.symbol || "BTC/USDT";
      fields.headerSource.textContent = market.source || "demo";
      fields.stripPrice.textContent = moneyText(market.current_price);
      fields.stripChange24h.textContent = percentText(market.price_change_24h_pct);
      fields.stripTrendStrength.textContent = percentText(market.trend_strength_pct);
      fields.stripSignal.textContent =
        compactMarketStatus(market.market_regime || strategy.recommendation || "not_available");
      fields.stripConnection.textContent = market.exchange_connection || "not_configured";
      const latencyText = `${market.latency_ms || "not_available"} ms`;
      fields.stripLatency.textContent = latencyText;
      fields.footerLatencyStatus.textContent = latencyText;
      fields.stripNotifications.textContent =
        notifications.unread_count || notifications.count || 0;
      fields.notificationBell.classList.toggle("attention", (notifications.unread_count || 0) > 0);
      fields.stripVersion.textContent = app.version || "not_available";
      fields.stripUpdated.textContent = formatClock(market.updated_at);
      fields.footerDataStatus.textContent =
        (market.data_freshness || "unknown").replaceAll("_", " ");
      fields.footerExchangeStatus.textContent = market.exchange_connection || "not_configured";
      fields.footerRiskStatus.textContent =
        data.safe_mode && !data.live_trading_enabled ? "Safe Mode" : "Review";
      fields.tradingModeSelect.value = data.live_trading_enabled ? "live" : "paper";
      const marketTone = (market.market_regime || strategy.recommendation || "").toLowerCase();
      fields.stripSignal.className = "status-pill " + (
        marketTone.includes("bull") || marketTone.includes("buy")
          ? "good"
          : marketTone.includes("bear") || marketTone.includes("rejected")
            ? "bad"
            : "warn"
      );
      fields.stripConnection.className = "connection-pill " +
        ((market.exchange_connection || "").toLowerCase() === "connected" ? "good" : "warn");
      fields.footerRiskStatus.className =
        data.safe_mode && !data.live_trading_enabled ? "good" : "warn";
    }
    function setNextCheckCountdown(refresh) {
      if (!refresh || !refresh.server_time || !refresh.next_check_at) {
        nextCheckClientDeadline = null;
        fields.stripNextCheck.textContent = "not_available";
        fields.commandNextCheck.textContent = "not_available";
        return;
      }
      const serverNow = Date.parse(refresh.server_time);
      const nextAt = Date.parse(refresh.next_check_at);
      if (!Number.isFinite(serverNow) || !Number.isFinite(nextAt)) {
        nextCheckClientDeadline = null;
        return;
      }
      nextCheckClientDeadline = Date.now() + Math.max(0, nextAt - serverNow);
      updateNextCheckCountdown();
    }
    function updateNextCheckCountdown() {
      if (!nextCheckClientDeadline) {
        return;
      }
      const seconds = Math.max(0, Math.ceil((nextCheckClientDeadline - Date.now()) / 1000));
      const text = formatCountdown(seconds);
      fields.stripNextCheck.textContent = text;
      fields.commandNextCheck.textContent = text;
    }
    function visibleViewNames(mode) {
      if (mode === "strategy_lab") {
        return ["beginner", "advanced_trader", "strategy_lab"];
      }
      if (mode === "advanced_trader") {
        return ["beginner", "advanced_trader"];
      }
      return ["beginner"];
    }
    function setModeShell(mode) {
      activeUiMode = mode;
      localStorage.setItem(UI_MODE_KEY, mode);
      document.body.classList.remove("mode-beginner", "mode-advanced_trader", "mode-strategy_lab");
      document.body.classList.add(`mode-${mode}`);
      fields.modeButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.uiMode === mode);
      });
      const visibleModes = visibleViewNames(mode);
      document.querySelectorAll("[data-view]").forEach((section) => {
        const sectionModes = section.dataset.view.split(" ");
        section.hidden = !sectionModes.some((sectionMode) => visibleModes.includes(sectionMode));
      });
    }
    function renderTransactions(items, isBeginner) {
      if (!items.length) {
        fields.transactions.innerHTML = '<p class="empty">No saved paper transactions yet.</p>';
        return;
      }
      const headers = isBeginner
        ? "<th>Time</th><th>Paper action</th><th>BTC amount</th>"
          + "<th>Paper price</th><th>Paper value</th>"
        : "<th>Time</th><th>Side</th><th>Qty</th><th>Price</th><th>Fee</th><th>Notional</th>";
      const rows = items.map((item) => {
        if (isBeginner) {
          return `
              <tr>
                <td>${item.time}</td>
                <td>${item.paper_action}</td>
                <td>${item.btc_amount}</td>
                <td>${item.paper_price}</td>
                <td>${item.paper_value}</td>
              </tr>`;
        }
        return `
              <tr>
                <td>${item.time}</td>
                <td>${item.side}</td>
                <td>${item.quantity}</td>
                <td>${item.price}</td>
                <td>${item.fee}</td>
                <td>${item.notional}</td>
              </tr>`;
      }).join("");
      fields.transactions.innerHTML = `
        <table>
          <thead>
            <tr>${headers}</tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>`;
    }
    function renderGlossary(items) {
      fields.glossary.innerHTML = items
        .map((item) => row(item.term, item.meaning))
        .join("");
    }
    function renderPortfolioSparkline(points) {
      if (!points || !points.length) {
        fields.portfolioSparkline.innerHTML =
          '<p class="empty">No portfolio sparkline points yet.</p>';
        return;
      }
      const values = points.map((item) => Number(item.equity)).filter(Number.isFinite);
      if (!values.length) {
        fields.portfolioSparkline.innerHTML =
          '<p class="empty">No portfolio sparkline points yet.</p>';
        return;
      }
      const min = Math.min(...values);
      const max = Math.max(...values);
      const width = 240;
      const height = 48;
      const xStep = values.length > 1 ? width / (values.length - 1) : width;
      const y = (value) => {
        if (max === min) {
          return height / 2;
        }
        return height - ((value - min) / (max - min)) * height;
      };
      const path = values.map((value, index) => {
        const command = index === 0 ? "M" : "L";
        return `${command}${(index * xStep).toFixed(1)},${y(value).toFixed(1)}`;
      }).join(" ");
      fields.portfolioSparkline.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" width="100%" height="52" role="img"
          aria-label="Portfolio equity sparkline">
          <path d="${path}" fill="none" stroke="currentColor" stroke-width="2"></path>
        </svg>`;
    }
    function renderRuntimeTelemetry(runtime, portfolio) {
      fill("runtimeTelemetry", {
        "1_24h_price_change_pct": runtime.price_change_24h_pct || "not_available",
        "2_trend_strength_pct": runtime.trend_strength_pct || "not_available",
        "3_exchange_connection": runtime.exchange_connection || "not_configured",
        "4_notification_bell":
          `${runtime.notification_count || 0} ${runtime.bell_state || "clear"}`,
        "5_latency_ms": runtime.latency_ms || "not_available",
        "6_app_version": runtime.app_version || "not_available",
        "7_sparkline_points": (runtime.portfolio_sparkline || []).length,
        "8_today_pnl": runtime.today_pnl || "not_available",
        "9_next_check_in_seconds": runtime.next_check_in_seconds ?? "not_available"
      });
      renderPortfolioSparkline((runtime.portfolio_sparkline || portfolio.equity_sparkline) || []);
    }
    function renderReadinessGate(readiness) {
      const items = (readiness && readiness.checklist) || [];
      if (!items.length) {
        fields.readinessGate.innerHTML = '<p class="empty">Readiness gate unavailable.</p>';
        return;
      }
      const verdict = readiness.trader_verdict || {};
      fields.readinessGate.innerHTML = `
        <dl>
          ${row("paper demo ready", verdict.paper_demo_ready || false)}
          ${row("live capital ready", verdict.live_capital_ready || false)}
          ${row("shareable scope", verdict.shareable_scope || "not_available")}
          ${row("profitability claim", verdict.profitability_claim || "none")}
          ${row("reconstructability", verdict.reconstructability_status || "not_available")}
        </dl>
        <h3>Proof Points</h3>
        <ul>${(verdict.proof_points || []).map((item) => `<li>${item}</li>`).join("")}</ul>
        <h3>Blockers</h3>
        <ul>${(verdict.blockers || ["none"]).map((item) => `<li>${item}</li>`).join("")}</ul>
        <h3>Warnings</h3>
        <ul>${(verdict.warnings || []).map((item) => `<li>${item}</li>`).join("")}</ul>
        <table>
          <thead>
            <tr><th>Check</th><th>Status</th><th>Detail</th></tr>
          </thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${item.label}</td>
                <td class="${item.passed ? "good" : "bad"}">${item.status}</td>
                <td>${item.detail}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
    }
    function renderDepthTable(title, rows, sideClass) {
      if (!rows.length) {
        return `<div class="depth-side"><h3>${title}</h3><p class="empty">No levels.</p></div>`;
      }
      return `
        <div class="depth-side">
          <h3>${title}</h3>
          <table class="depth-table">
            <thead><tr><th>Price</th><th>Qty</th><th>Total</th></tr></thead>
            <tbody>
              ${rows.map((item) => `
                <tr>
                  <td class="${sideClass}">${item.price}</td>
                  <td>${item.quantity}</td>
                  <td>${item.total}</td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>`;
    }
    function renderOrderBook(orderBook) {
      if (!orderBook || !orderBook.summary) {
        fields.orderBook.innerHTML = '<p class="empty">Order book unavailable.</p>';
        return;
      }
      fields.orderBook.innerHTML = `
        <dl>
          ${row("best bid", orderBook.summary.best_bid)}
          ${row("best ask", orderBook.summary.best_ask)}
          ${row("spread", orderBook.summary.spread)}
          ${row("spread bps", orderBook.summary.spread_bps)}
          ${row("bid depth", orderBook.summary.bid_depth)}
          ${row("ask depth", orderBook.summary.ask_depth)}
          ${row("imbalance", orderBook.summary.imbalance)}
          ${row("bias", orderBook.summary.bias)}
        </dl>
        <div class="depth-grid">
          ${renderDepthTable("Bids", orderBook.bids || [], "depth-price-bid")}
          ${renderDepthTable("Asks", orderBook.asks || [], "depth-price-ask")}
        </div>`;
    }
    function renderOrderFlow(orderFlow) {
      if (!orderFlow || !orderFlow.summary) {
        fields.orderFlow.innerHTML = '<p class="empty">Order flow unavailable.</p>';
        return;
      }
      fields.orderFlow.innerHTML = `
        <dl>
          ${row("trade count", orderFlow.summary.trade_count)}
          ${row("buy volume", orderFlow.summary.buy_volume)}
          ${row("sell volume", orderFlow.summary.sell_volume)}
          ${row("buy pressure", orderFlow.summary.buy_pressure_pct)}
          ${row("dominant side", orderFlow.summary.dominant_side)}
          ${row("latest price", orderFlow.summary.latest_price)}
        </dl>
        <h3>Recent Trades</h3>
        ${renderRecentTrades(orderFlow.recent_trades || [])}
        <h3>Liquidity Heatmap</h3>
        ${renderLiquidityHeatmap(orderFlow.liquidity_heatmap || [])}`;
    }
    function renderRecentTrades(items) {
      if (!items.length) {
        return '<p class="empty">No recent trades available.</p>';
      }
      return `
        <table>
          <thead><tr><th>Time</th><th>Side</th><th>Price</th><th>Qty</th><th>Notional</th></tr></thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${item.time}</td>
                <td class="${item.side === "BUY" ? "depth-price-bid" : "depth-price-ask"}">
                  ${item.side}
                </td>
                <td>${item.price}</td>
                <td>${item.quantity}</td>
                <td>${item.notional}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
    }
    function renderLiquidityHeatmap(items) {
      if (!items.length) {
        return '<p class="empty">No heatmap rows available.</p>';
      }
      return `
        <table>
          <thead><tr><th>Side</th><th>Price</th><th>Qty</th><th>Intensity</th></tr></thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td class="${item.side === "bid" ? "depth-price-bid" : "depth-price-ask"}">
                  ${item.side}
                </td>
                <td>${item.price}</td>
                <td>${item.quantity}</td>
                <td>${item.intensity_pct}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
    }
    function renderOrderTicket(ticket) {
      setOptions(fields.ticketOrderType, ticket.supported_order_types || [], "limit");
      setOptions(fields.ticketSide, ticket.supported_sides || [], "buy");
      fields.ticketQuantity.value = ticket.default_quantity || "0.01";
      fields.ticketMessage.textContent = ticket.safety_note || "Paper ticket only.";
      const filters = ticket.symbol_filters || {};
      fields.ticketFilters.innerHTML = [
        row("tick size", filters.tick_size || "not_available"),
        row("step size", filters.step_size || "not_available"),
        row("min quantity", filters.min_quantity || "not_available"),
        row("min notional", filters.min_notional || "not_available"),
        row("mark price", ticket.reference_price || "not_available")
      ].join("");
    }
    function renderOpenOrders(items) {
      if (!items.length) {
        fields.openOrders.innerHTML = '<p class="empty">No open paper orders.</p>';
        return;
      }
      fields.openOrders.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Created</th><th>Type</th><th>Side</th><th>Qty</th>
              <th>Limit</th><th>Stop</th><th>Take Profit</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${item.created_at}</td>
                <td>${item.order_type}</td>
                <td>${item.side}</td>
                <td>${item.quantity}</td>
                <td>${item.limit_price}</td>
                <td>${item.stop_price}</td>
                <td>${item.take_profit_price}</td>
                <td>${item.status}</td>
                <td>
                  <button class="secondary" data-cancel-paper-order="${item.order_id}">
                    Cancel
                  </button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      Array.from(fields.openOrders.querySelectorAll("[data-cancel-paper-order]")).forEach(
        (button) => {
          button.onclick = () => cancelPaperOrder(button.dataset.cancelPaperOrder);
        }
      );
    }
    function renderJournalAnalytics(journal, transactions) {
      if (!journal) {
        fields.journalSummary.innerHTML = "";
        fields.journalAnalytics.innerHTML = '<p class="empty">Journal unavailable.</p>';
        fields.journalEntries.innerHTML = "";
        return;
      }
      setOptions(
        fields.journalSetupType,
        journal.supported_setup_types || [],
        fields.journalSetupType.value || "manual_review"
      );
      const tradeOptions = [{value: "", label: "latest / no trade ref"}].concat(
        (transactions || []).map((item) => ({
          value: item.trade_ref || "",
          label: `${item.side} ${item.quantity} @ ${item.price}`
        }))
      );
      setOptions(fields.journalTradeRef, tradeOptions, fields.journalTradeRef.value || "");
      if (!fields.journalChartContext.value) {
        fields.journalChartContext.value = journal.chart_context_hint || "";
      }
      fill("journalSummary", journal.summary || {});
      const strategyRows = journal.pnl_by_strategy || [];
      const regimeRows = journal.pnl_by_regime || [];
      const tagRows = journal.tag_breakdown || [];
      fields.journalAnalytics.innerHTML = `
        <h3>P/L By Strategy</h3>
        ${renderSimpleRows(strategyRows, ["strategy", "paper_pnl", "transactions", "scope"])}
        <h3>P/L By Regime</h3>
        ${renderSimpleRows(regimeRows, ["regime", "paper_pnl", "transactions", "scope"])}
        <h3>Tags</h3>
        ${renderSimpleRows(tagRows, ["tag", "count"])}`;
      const entries = journal.entries || [];
      if (!entries.length) {
        fields.journalEntries.innerHTML = '<p class="empty">No journal entries yet.</p>';
        return;
      }
      fields.journalEntries.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Updated</th><th>Setup</th><th>Tags</th><th>Notes</th>
              <th>Mistake</th><th>Lesson</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${entries.map((item) => `
              <tr>
                <td>${item.updated_at}</td>
                <td>${item.setup_type}</td>
                <td>${(item.tags || []).join(", ")}</td>
                <td>${item.notes}</td>
                <td>${item.mistake_review}</td>
                <td>${item.lesson}</td>
                <td>
                  <button class="secondary" data-delete-journal-entry="${item.journal_id}">
                    Delete
                  </button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      Array.from(fields.journalEntries.querySelectorAll("[data-delete-journal-entry]")).forEach(
        (button) => {
          button.onclick = () => deleteJournalEntry(button.dataset.deleteJournalEntry);
        }
      );
    }
    function renderTraderFeedback(feedback) {
      if (!feedback) {
        fields.traderFeedbackSummary.innerHTML = "";
        fields.traderFeedbackBreakdown.innerHTML = '<p class="empty">Feedback unavailable.</p>';
        fields.traderFeedbackItems.innerHTML = "";
        return;
      }
      setOptions(
        fields.feedbackReviewerRole,
        feedback.supported_reviewer_roles || [],
        fields.feedbackReviewerRole.value || "trader"
      );
      setOptions(
        fields.feedbackCategory,
        feedback.supported_categories || [],
        fields.feedbackCategory.value || "ui"
      );
      setOptions(
        fields.feedbackSeverity,
        feedback.supported_severities || [],
        fields.feedbackSeverity.value || "medium"
      );
      fill("traderFeedbackSummary", feedback.summary || {});
      fields.traderFeedbackBreakdown.innerHTML = `
        <h3>Categories</h3>
        ${renderSimpleRows(feedback.category_breakdown || [], ["category", "count"])}
        <h3>Open Severity</h3>
        ${renderSimpleRows(feedback.severity_breakdown || [], ["severity", "count"])}`;
      const items = feedback.items || [];
      if (!items.length) {
        fields.traderFeedbackItems.innerHTML = '<p class="empty">No trader feedback yet.</p>';
        return;
      }
      fields.traderFeedbackItems.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Created</th><th>Reviewer</th><th>Category</th><th>Severity</th>
              <th>Status</th><th>Summary</th><th>Recommendation</th><th>Resolution</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${item.created_at}</td>
                <td>${item.reviewer_role}</td>
                <td>${item.category}</td>
                <td>${item.severity}</td>
                <td>${item.status}</td>
                <td>${item.summary}</td>
                <td>${item.recommendation}</td>
                <td>${item.resolution || ""}</td>
                <td>
                  <button class="secondary" data-close-trader-feedback="${item.feedback_id}">
                    Close
                  </button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      Array.from(
        fields.traderFeedbackItems.querySelectorAll("[data-close-trader-feedback]")
      ).forEach((button) => {
        button.onclick = () => closeTraderFeedback(button.dataset.closeTraderFeedback);
      });
    }
    function renderSimpleRows(items, keys) {
      if (!items.length) {
        return '<p class="empty">No rows yet.</p>';
      }
      const headerRows = keys
        .map((key) => `<th>${key.replaceAll("_", " ")}</th>`)
        .join("");
      return `
        <table>
          <thead><tr>${headerRows}</tr></thead>
          <tbody>
            ${items.map((item) => `
              <tr>${keys.map((key) => `<td>${item[key] || ""}</td>`).join("")}</tr>
            `).join("")}
          </tbody>
        </table>`;
    }
    function renderPosition(position) {
      if (!position) {
        fields.position.innerHTML = "";
        fields.stageClosePosition.disabled = true;
        fields.stageReducePosition.disabled = true;
        fields.positionMessage.textContent = "Position unavailable.";
        return;
      }
      fill("position", {
        symbol: position.symbol,
        open_btc: position.open_btc,
        average_entry: position.average_entry,
        mark_price: position.mark_price,
        market_value: position.market_value,
        unrealized_pnl: position.unrealized_pnl,
        unrealized_pnl_pct: position.unrealized_pnl_pct,
        stop_loss: position.stop_loss,
        target: position.target,
        close_quantity: position.close_quantity,
        reduce_quantity: position.reduce_quantity
      });
      fields.stageClosePosition.disabled = !position.can_stage_close;
      fields.stageReducePosition.disabled = !position.can_stage_reduce;
      fields.positionMessage.textContent = position.has_open_position
        ? "Close/reduce stages a paper-only sell order for review."
        : "No open paper position.";
    }
    function renderWatchlist(watchlist) {
      const items = (watchlist && watchlist.symbols) || [];
      if (!items.length) {
        fields.watchlist.innerHTML = '<p class="empty">Watchlist unavailable.</p>';
        return;
      }
      fields.watchlist.innerHTML = `
        ${items.map((item) => `
          <button class="watchlist-row${item.selected ? " active" : ""}"
            data-watchlist-symbol="${item.symbol}">
            <span class="watchlist-symbol">${item.symbol}</span>
            <span>${item.price}</span>
            <span class="${item.paper_tradable ? "good" : "warn"}">
              ${item.paper_tradable ? "paper" : "read-only"}
            </span>
            <span class="watchlist-note">${item.note}</span>
          </button>`).join("")}
        <p class="empty">${watchlist.note || ""}</p>`;
      Array.from(fields.watchlist.querySelectorAll("[data-watchlist-symbol]")).forEach(
        (button) => {
          button.onclick = () => saveWatchlistSymbol(button.dataset.watchlistSymbol);
        }
      );
    }
    function renderAlerts(alerts, rules, watchlist) {
      const alertTypes = (alerts && alerts.supported_alert_types) || [];
      const symbols = ((watchlist && watchlist.symbols) || []).map((item) => item.symbol);
      setOptions(fields.alertType, alertTypes, fields.alertType.value || "price_above");
      setOptions(
        fields.alertSymbol,
        symbols,
        fields.alertSymbol.value || watchlist.selected_symbol
      );
      const triggered = (alerts && alerts.triggered) || [];
      fields.triggeredAlerts.innerHTML = triggered.length
        ? `<div class="alert-list">${triggered.map((item) => `
            <div class="alert-item">
              <strong>${item.alert_type}</strong> ${item.symbol}<br>${item.message}
            </div>`).join("")}</div>`
        : '<p class="empty">No alerts triggered.</p>';
      if (!rules.length) {
        fields.alertRules.innerHTML = '<p class="empty">No saved alert rules.</p>';
        return;
      }
      fields.alertRules.innerHTML = `
        <table>
          <thead>
            <tr><th>Type</th><th>Symbol</th><th>Threshold</th><th>Expected</th><th></th></tr>
          </thead>
          <tbody>
            ${rules.map((item) => `
              <tr>
                <td>${item.alert_type}</td>
                <td>${item.symbol}</td>
                <td>${item.threshold}</td>
                <td>${item.expected_value}</td>
                <td>
                  <button class="secondary" data-delete-alert-rule="${item.alert_id}">
                    Delete
                  </button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      Array.from(fields.alertRules.querySelectorAll("[data-delete-alert-rule]")).forEach(
        (button) => {
          button.onclick = () => deleteAlertRule(button.dataset.deleteAlertRule);
        }
      );
    }
    function renderRiskSafety(riskSafety) {
      if (!riskSafety || !riskSafety.summary) {
        fields.riskSafetySummary.innerHTML = "";
        fields.riskSafetyChecks.innerHTML = '<p class="empty">Risk safety unavailable.</p>';
        fields.riskSafetyExchange.innerHTML = "";
        fields.riskSafetyReconciliation.innerHTML = "";
        return;
      }
      fill("riskSafetySummary", riskSafety.summary || {});
      fields.riskSafetyChecks.innerHTML = `
        <h3>Risk Checks</h3>
        ${renderSimpleRows(riskSafety.risk_checks || [], ["check", "status", "detail"])}`;
      fields.riskSafetyExchange.innerHTML = `
        <h3>Exchange / Data Health</h3>
        ${renderSimpleRows(riskSafety.exchange_health || [], ["check", "status", "detail"])}`;
      fields.riskSafetyReconciliation.innerHTML = `
        <h3>Reconciliation</h3>
        ${renderSimpleRows(riskSafety.reconciliation || [], ["check", "status", "detail"])}`;
    }
    function setOptions(select, values, selected) {
      const options = values.map((item) => {
        const value = typeof item === "string" ? item : item.value;
        const label = typeof item === "string" ? item : item.label;
        const active = value === selected ? " selected" : "";
        return `<option value="${value}"${active}>${label}</option>`;
      });
      select.innerHTML = options.join("");
    }
    function renderStrategyLab(strategyLab) {
      const selection = strategyLab.selection || {};
      const selectors = strategyLab.selectors || {};
      setOptions(fields.labStrategy, selectors.strategies || [], selection.strategy);
      setOptions(fields.labSymbol, selectors.symbols || [], selection.symbol);
      setOptions(fields.labTimeframe, selectors.timeframes || [], selection.timeframe);
      setOptions(fields.labRunMode, selectors.run_modes || [], selection.run_mode);
      setOptions(
        fields.labParameterProfile,
        selectors.parameter_profiles || [],
        selection.parameter_profile
      );
      fill("strategyLab", {
        selected_strategy: strategyLab.selected_strategy || "not_available",
        strategy_family: strategyLab.strategy_family || "not_available",
        strategy_status: strategyLab.strategy_status || "not_available",
        evidence_status: strategyLab.evidence_status || "not_available",
        recommendation_actionable: strategyLab.recommendation_actionable || false,
        paper_approval_allowed: strategyLab.paper_approval_allowed || false,
        routing_scope: (strategyLab.routing_decision || {}).scope || "paper_evidence_only",
        limitations: strategyLab.limitations || []
      });
      fields.strategyLabEvidence.innerHTML = `
        <dl>
          ${row("market data", (strategyLab.required_market_data || []).join(", "))}
          ${row("indicators", (strategyLab.required_indicators || []).join(", "))}
          ${row(
            "AI/context",
            (strategyLab.required_ai_context_modules || []).join(", ")
          )}
          ${row("risk checks", (strategyLab.required_risk_checks || []).join(", "))}
          ${row(
            "explanation fields",
            (strategyLab.required_explanation_fields || []).join(", ")
          )}
          ${row("missing evidence", (strategyLab.missing_evidence || []).join(", ") || "none")}
        </dl>
        <h3>Evidence Matrix</h3>
        ${renderSimpleRows(
          strategyLab.evidence_matrix || [],
          ["evidence", "required", "status", "module", "detail"]
        )}
        <h3>Module Routing</h3>
        ${renderSimpleRows(
          strategyLab.module_routing || [],
          ["module", "status", "scope", "purpose"]
        )}
        <h3>Parameter Config</h3>
        <dl>${Object.entries(strategyLab.parameter_config || {})
          .map(([key, value]) => row(key.replaceAll("_", " "), value))
          .join("")}</dl>`;
      renderCompareRuns(strategyLab.compare_runs || []);
    }
    function renderCompareRuns(items) {
      if (!items.length) {
        fields.strategyLabCompare.innerHTML = '<p class="empty">No strategy runs to compare.</p>';
        return;
      }
      fields.strategyLabCompare.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Run</th><th>Strategy</th><th>Parameters</th><th>Mode</th>
              <th>Sample</th><th>Expectancy</th><th>Drawdown</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${item.run_id}${item.selected ? " *" : ""}</td>
                <td>${item.strategy}</td>
                <td>${item.parameter_profile}</td>
                <td>${item.mode}</td>
                <td>${item.sample_size || "not_available"}</td>
                <td>${item.expectancy || "not_available"}</td>
                <td>${item.max_drawdown || "not_available"}</td>
                <td>${item.status}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
    }
    function renderChartControls(chart) {
      const timeframes = chart.available_timeframes || [chart.timeframe || "1h"];
      if (!timeframes.includes(chartState.timeframe)) {
        chartState.timeframe = chart.timeframe || timeframes[0] || "1h";
      }
      const drawingTools = (chart && chart.drawing_tools) || {};
      setOptions(
        fields.drawingType,
        drawingTools.supported_types || [],
        fields.drawingType.value || "horizontal_level"
      );
      fields.chartTimeframes.innerHTML = timeframes.map((timeframe) => {
        const active = timeframe === chartState.timeframe ? " active" : "";
        return `
          <button class="chart-tool${active}" data-chart-timeframe="${timeframe}">
            ${timeframe}
          </button>`;
      }).join("");
      Array.from(fields.chartTimeframes.querySelectorAll("[data-chart-timeframe]")).forEach(
        (button) => {
          button.onclick = () => {
            chartState.timeframe = button.dataset.chartTimeframe;
            chartState.visibleCount = null;
            chartState.startIndex = 0;
            renderChart(chartState.lastChart || chart);
          };
        }
      );
      Array.from(fields.chartIndicators.querySelectorAll("[data-chart-overlay]")).forEach(
        (button) => {
          const overlay = button.dataset.chartOverlay;
          button.classList.toggle("active", chartState.overlays[overlay]);
          button.onclick = () => {
            chartState.overlays[overlay] = !chartState.overlays[overlay];
            button.classList.toggle("active", chartState.overlays[overlay]);
            renderChart(chartState.lastChart || chart);
          };
        }
      );
    }
    function renderChartDrawingsTable(drawings) {
      if (!drawings.length) {
        fields.chartDrawings.innerHTML = '<p class="empty">No saved chart drawings.</p>';
        return;
      }
      fields.chartDrawings.innerHTML = `
        <table>
          <thead>
            <tr><th>Type</th><th>Price</th><th>End</th><th>Text</th><th></th></tr>
          </thead>
          <tbody>
            ${drawings.map((item) => `
              <tr>
                <td>${item.drawing_type}</td>
                <td>${item.start_price}</td>
                <td>${item.end_price}</td>
                <td>${item.text}</td>
                <td>
                  <button class="secondary" data-delete-chart-drawing="${item.drawing_id}">
                    Delete
                  </button>
                </td>
              </tr>`).join("")}
          </tbody>
        </table>`;
      Array.from(fields.chartDrawings.querySelectorAll("[data-delete-chart-drawing]")).forEach(
        (button) => {
          button.onclick = () => deleteChartDrawing(button.dataset.deleteChartDrawing);
        }
      );
    }
    function toChartCandle(item) {
      return {
        time: item.time,
        open: Number(item.open),
        high: Number(item.high),
        low: Number(item.low),
        close: Number(item.close),
        volume: Number(item.volume || 0)
      };
    }
    function timeframeBucketSize(timeframe) {
      return { "1h": 1, "4h": 4, "1d": 24 }[timeframe] || 1;
    }
    function aggregateCandles(candles, timeframe) {
      const bucketSize = timeframeBucketSize(timeframe);
      if (bucketSize <= 1) {
        return candles;
      }
      const output = [];
      for (let index = 0; index < candles.length; index += bucketSize) {
        const bucket = candles.slice(index, index + bucketSize);
        if (!bucket.length) {
          continue;
        }
        output.push({
          time: bucket[bucket.length - 1].time,
          open: bucket[0].open,
          high: Math.max(...bucket.map((item) => item.high)),
          low: Math.min(...bucket.map((item) => item.low)),
          close: bucket[bucket.length - 1].close,
          volume: bucket.reduce((total, item) => total + item.volume, 0)
        });
      }
      return output;
    }
    function smaPoints(candles, period) {
      return candles.map((item, index) => {
        const window = candles.slice(Math.max(0, index - period + 1), index + 1);
        const value = window.reduce((total, candle) => total + candle.close, 0) / window.length;
        return {...item, value};
      });
    }
    function visibleCandles(candles) {
      const count = chartState.visibleCount || Math.min(80, candles.length);
      chartState.visibleCount = Math.max(1, Math.min(count, candles.length));
      const maxStart = Math.max(0, candles.length - chartState.visibleCount);
      chartState.startIndex = Math.max(0, Math.min(chartState.startIndex, maxStart));
      return candles.slice(chartState.startIndex, chartState.startIndex + chartState.visibleCount);
    }
    function priceFormatter(value) {
      if (!Number.isFinite(value)) {
        return "n/a";
      }
      return value.toFixed(value >= 1000 ? 2 : 3);
    }
    function drawingPrices(drawings) {
      return drawings
        .flatMap((item) => [Number(item.start_price), Number(item.end_price)])
        .filter((value) => Number.isFinite(value));
    }
    function drawingTimeIndex(visible, time, fallback) {
      const index = visible.findIndex((item) => item.time === time);
      return index >= 0 ? index : fallback;
    }
    function drawChartDrawings(ctx, chart, visible, x, y, left, right) {
      const drawings = ((chart && chart.drawings) || []).filter((item) => {
        return item.enabled !== false
          && item.symbol === (chart.symbol || "BTC/USDT")
          && item.timeframe === chartState.timeframe;
      });
      drawings.forEach((item) => {
        const startPrice = Number(item.start_price);
        const endPrice = Number(item.end_price);
        if (!Number.isFinite(startPrice)) {
          return;
        }
        const startIndex = drawingTimeIndex(visible, item.start_time, 0);
        const endIndex = drawingTimeIndex(visible, item.end_time, visible.length - 1);
        const startX = x(startIndex);
        const endX = x(endIndex);
        const startY = y(startPrice);
        const endY = Number.isFinite(endPrice) ? y(endPrice) : startY;
        ctx.save();
        ctx.strokeStyle = item.color || "#1264a3";
        ctx.fillStyle = item.color || "#1264a3";
        ctx.lineWidth = 2;
        if (item.drawing_type === "horizontal_level") {
          ctx.beginPath();
          ctx.moveTo(left, startY);
          ctx.lineTo(ctx.canvas.width - right, startY);
          ctx.stroke();
          ctx.fillText(item.text || priceFormatter(startPrice), left + 8, startY - 6);
        } else if (item.drawing_type === "trendline") {
          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(endX, endY);
          ctx.stroke();
        } else if (item.drawing_type === "box") {
          ctx.globalAlpha = 0.15;
          ctx.fillRect(startX, Math.min(startY, endY), endX - startX, Math.abs(endY - startY));
          ctx.globalAlpha = 1;
          ctx.strokeRect(startX, Math.min(startY, endY), endX - startX, Math.abs(endY - startY));
        } else if (item.drawing_type === "fibonacci") {
          [0, 0.382, 0.5, 0.618, 1].forEach((level) => {
            const price = startPrice + (endPrice - startPrice) * level;
            const lineY = y(price);
            ctx.beginPath();
            ctx.moveTo(startX, lineY);
            ctx.lineTo(endX, lineY);
            ctx.stroke();
            ctx.fillText(`${Math.round(level * 100)}%`, startX + 6, lineY - 4);
          });
        } else if (item.drawing_type === "note") {
          const text = item.text || "note";
          ctx.fillStyle = "#ffffff";
          ctx.strokeStyle = item.color || "#1264a3";
          ctx.fillRect(startX, startY - 24, Math.min(180, 24 + text.length * 7), 24);
          ctx.strokeRect(startX, startY - 24, Math.min(180, 24 + text.length * 7), 24);
          ctx.fillStyle = item.color || "#1264a3";
          ctx.fillText(text, startX + 8, startY - 8);
        }
        ctx.restore();
      });
    }
    function renderChart(chart) {
      chartState.lastChart = chart;
      renderChartControls(chart || {});
      const canvas = fields.priceChart;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(320, Math.floor(rect.width));
      canvas.height = Math.max(320, Math.floor(rect.height));
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const sourceCandles = ((chart && chart.candles) || []).map(toChartCandle);
      const candles = aggregateCandles(sourceCandles, chartState.timeframe);
      if (!candles.length) {
        fields.chartTooltip.style.display = "none";
        fields.chartReadout.textContent = "No chart data available.";
        ctx.fillStyle = "#62717a";
        ctx.fillText("No chart data available", 18, 28);
        return;
      }
      const visible = visibleCandles(candles);
      const left = 58;
      const right = 18;
      const top = 26;
      const bottom = 34;
      const width = canvas.width - left - right;
      const height = canvas.height - top - bottom;
      const riskLines = (chart && chart.risk_lines) || {};
      const riskPrices = Object.values(riskLines)
        .map(Number)
        .filter((value) => Number.isFinite(value));
      const drawings = (chart && chart.drawings) || [];
      const prices = visible
        .flatMap((item) => [item.high, item.low, item.close])
        .concat(riskPrices)
        .concat(drawingPrices(drawings));
      const minPrice = Math.min(...prices);
      const maxPrice = Math.max(...prices);
      const margin = Math.max((maxPrice - minPrice) * 0.08, 0.01);
      const min = minPrice - margin;
      const max = maxPrice + margin;
      const slot = width / Math.max(visible.length, 1);
      const bodyWidth = Math.max(5, Math.min(18, slot * 0.58));
      const y = (price) => {
        if (max === min) {
          return top + height / 2;
        }
        return top + height - ((price - min) / (max - min)) * height;
      };
      const x = (index) => left + slot * index + slot / 2;
      ctx.strokeStyle = "#e4ebef";
      ctx.lineWidth = 1;
      ctx.font = "12px system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      for (let grid = 0; grid <= 4; grid += 1) {
        const gridY = top + (height / 4) * grid;
        const price = max - ((max - min) / 4) * grid;
        ctx.beginPath();
        ctx.moveTo(left, gridY);
        ctx.lineTo(canvas.width - right, gridY);
        ctx.stroke();
        ctx.fillStyle = "#62717a";
        ctx.fillText(priceFormatter(price), 8, gridY + 4);
      }
      visible.forEach((item, index) => {
        const itemX = x(index);
        const openY = y(item.open);
        const closeY = y(item.close);
        const highY = y(item.high);
        const lowY = y(item.low);
        const rising = item.close >= item.open;
        ctx.strokeStyle = rising ? "#0f7b52" : "#b42318";
        ctx.fillStyle = rising ? "#e3f4ed" : "#fae5e2";
        ctx.beginPath();
        ctx.moveTo(itemX, highY);
        ctx.lineTo(itemX, lowY);
        ctx.stroke();
        const bodyTop = Math.min(openY, closeY);
        const bodyHeight = Math.max(2, Math.abs(closeY - openY));
        ctx.fillRect(itemX - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight);
        ctx.strokeRect(itemX - bodyWidth / 2, bodyTop, bodyWidth, bodyHeight);
      });
      if (chartState.overlays.sma_3) {
        const sma = smaPoints(visible, 3);
        ctx.strokeStyle = "#9a6700";
        ctx.lineWidth = 2;
        ctx.beginPath();
        sma.forEach((item, index) => {
          const pointX = x(index);
          const pointY = y(item.value);
          if (index === 0) {
            ctx.moveTo(pointX, pointY);
          } else {
            ctx.lineTo(pointX, pointY);
          }
        });
        ctx.stroke();
      }
      if (chartState.overlays.risk_lines) {
        const lineStyles = {
          entry: ["#1264a3", "Entry"],
          stop_loss: ["#b42318", "Stop"],
          target: ["#0f7b52", "Target"]
        };
        Object.entries(lineStyles).forEach(([key, config]) => {
          const price = Number(riskLines[key]);
          if (!Number.isFinite(price)) {
            return;
          }
          const lineY = y(price);
          ctx.strokeStyle = config[0];
          ctx.setLineDash([6, 4]);
          ctx.beginPath();
          ctx.moveTo(left, lineY);
          ctx.lineTo(canvas.width - right, lineY);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.fillStyle = config[0];
          ctx.fillText(`${config[1]} ${priceFormatter(price)}`, left + 8, lineY - 5);
        });
      }
      if (chartState.overlays.markers) {
        const markerByTime = new Map(
          ((chart && chart.markers) || []).map((item) => [item.time, item])
        );
        visible.forEach((item, index) => {
          const marker = markerByTime.get(item.time);
          if (!marker) {
            return;
          }
          const markerX = x(index);
          const markerY = y(Number(marker.price));
          ctx.fillStyle = marker.signal === "BUY" ? "#0f7b52" : "#62717a";
          ctx.beginPath();
          ctx.arc(markerX, markerY, 5, 0, Math.PI * 2);
          ctx.fill();
        });
      }
      drawChartDrawings(ctx, chart, visible, x, y, left, right);
      if (chartState.hoverIndex !== null && chartState.hoverIndex < visible.length) {
        const item = visible[chartState.hoverIndex];
        const hoverX = x(chartState.hoverIndex);
        ctx.strokeStyle = "#62717a";
        ctx.setLineDash([3, 4]);
        ctx.beginPath();
        ctx.moveTo(hoverX, top);
        ctx.lineTo(hoverX, top + height);
        ctx.moveTo(left, y(item.close));
        ctx.lineTo(canvas.width - right, y(item.close));
        ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.fillStyle = "#172026";
      ctx.font = "13px system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      ctx.fillText(`${chart.symbol || "BTC/USDT"} ${chartState.timeframe}`, left, 18);
      const latest = visible[visible.length - 1];
      if (!fields.drawingStartPrice.value) {
        fields.drawingStartPrice.value = priceFormatter(latest.close);
      }
      if (!fields.drawingEndPrice.value) {
        fields.drawingEndPrice.value = priceFormatter(visible[0].close);
      }
      chartState.drawingStartTime = visible[0].time;
      chartState.drawingEndTime = latest.time;
      fields.chartReadout.textContent =
        `Showing ${visible.length} of ${candles.length} candles. Latest close `
        + `${priceFormatter(latest.close)}. Overlays: `
        + Object.entries(chartState.overlays)
          .filter(([, enabled]) => enabled)
          .map(([name]) => name.replaceAll("_", " "))
          .join(", ");
      chartState.layout = {left, right, top, bottom, width, height, slot, visible};
      renderChartDrawingsTable(drawings);
    }
    function zoomChart(delta) {
      if (!chartState.lastChart) {
        return;
      }
      const sourceCandles = ((chartState.lastChart && chartState.lastChart.candles) || [])
        .map(toChartCandle);
      const candles = aggregateCandles(sourceCandles, chartState.timeframe);
      const current = chartState.visibleCount || candles.length;
      chartState.visibleCount = Math.max(1, Math.min(candles.length, current + delta));
      chartState.startIndex = Math.max(0, candles.length - chartState.visibleCount);
      renderChart(chartState.lastChart);
    }
    function panChart(delta) {
      if (!chartState.lastChart) {
        return;
      }
      chartState.startIndex += delta;
      renderChart(chartState.lastChart);
    }
    function updateChartTooltip(event) {
      const layout = chartState.layout;
      if (!layout) {
        return;
      }
      const rect = fields.priceChart.getBoundingClientRect();
      const pointerX = event.clientX - rect.left;
      const pointerY = event.clientY - rect.top;
      if (
        pointerX < layout.left
        || pointerX > fields.priceChart.width - layout.right
        || pointerY < layout.top
        || pointerY > fields.priceChart.height - layout.bottom
      ) {
        chartState.hoverIndex = null;
        fields.chartTooltip.style.display = "none";
        renderChart(chartState.lastChart);
        return;
      }
      const index = Math.max(
        0,
        Math.min(layout.visible.length - 1, Math.floor((pointerX - layout.left) / layout.slot))
      );
      const item = layout.visible[index];
      chartState.hoverIndex = index;
      fields.chartTooltip.style.display = "block";
      fields.chartTooltip.style.left = `${Math.min(pointerX + 12, rect.width - 212)}px`;
      fields.chartTooltip.style.top = `${Math.max(8, pointerY - 18)}px`;
      fields.chartTooltip.innerHTML = `
        <strong>${item.time}</strong><br>
        O ${priceFormatter(item.open)} H ${priceFormatter(item.high)}<br>
        L ${priceFormatter(item.low)} C ${priceFormatter(item.close)}<br>
        Volume ${priceFormatter(item.volume)}
      `;
      renderChart(chartState.lastChart);
    }
    async function load() {
      setModeShell(activeUiMode);
      const params = new URLSearchParams({ui_mode: activeUiMode});
      const response = await fetch(`/api/status?${params}`, {cache: "no-store"});
      const data = await response.json();
      const views = data.views || {};
      const beginner = views.beginner || {};
      const advanced = views.advanced_trader || {};
      const strategyLab = views.strategy_lab || {};
      const beginnerMode = activeUiMode === "beginner";
      applyShellPreferences(data.ui || {});
      updateMarketStrip(data);
      setNextCheckCountdown(data.refresh || {});
      fill("market", data.market);
      renderRuntimeTelemetry(data.runtime_telemetry || {}, data.portfolio || {});
      renderWatchlist(advanced.watchlist || {});
      renderAlerts(advanced.alerts || {}, advanced.alert_rules || [], advanced.watchlist || {});
      renderRiskSafety(advanced.risk_safety || {});
      renderOrderBook(advanced.order_book || {});
      renderOrderFlow(advanced.order_flow || {});
      renderOrderTicket(advanced.order_ticket || {});
      renderOpenOrders(advanced.open_paper_orders || []);
      renderJournalAnalytics(advanced.trade_journal || {}, data.transactions || []);
      renderTraderFeedback(advanced.trader_feedback || {});
      renderPosition(advanced.position || {});
      renderCommandCard(beginner.command || {}, data.strategy || {}, data.refresh || {});
      renderWhyList(data.strategy || {}, beginner.command || {});
      renderPortfolioCards(data.portfolio || {});
      fill("strategy", data.strategy);
      fill("trade", data.suggested_paper_trade);
      fill("portfolio", beginnerMode ? beginner.portfolio_summary || {} : data.portfolio);
      fill("beginnerCommand", beginner.command || {});
      renderStrategyLab(strategyLab);
      fill("backtestSummary", advanced.backtest_summary || {});
      fill("performance", advanced.performance || {});
      fill("exitReview", advanced.exit_review || {});
      renderChart(advanced.chart || {});
      const transactionRows = beginnerMode ? beginner.transactions || [] : data.transactions;
      renderTransactions(transactionRows, beginnerMode);
      renderGlossary(beginner.glossary || []);
      renderReadinessGate(data.readiness || {});
      const explanationRows = beginnerMode ? beginner.reasons : data.strategy.indicator_reasons;
      fields.explanation.innerHTML = (explanationRows || [])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
      fields.explanationConfidence.textContent =
        `Explanation Confidence: ${asPercentFromConfidence(data.strategy.ai_confidence)}`;
      renderActivityTimeline(data.activity || {}, data.logs || []);
      fields.warning.textContent = data.warning;
      fields.approvalReason.textContent = data.controls.approval_block_reason;
      fields.approve.disabled = !data.controls.can_approve_paper_trade;
      document.getElementById("mode").textContent = data.mode;
      document.getElementById("safe").textContent = data.safe_mode ? "SAFE MODE" : "SAFE MODE OFF";
      document.getElementById("live").textContent =
        data.live_trading_enabled ? "LIVE ON" : "LIVE OFF";
    }
    function setTradingModeSelection() {
      const wantsLive = fields.tradingModeSelect.value === "live";
      const liveEnabled = document.getElementById("live").textContent === "LIVE ON";
      if (wantsLive && !liveEnabled) {
        fields.tradingModeSelect.value = "paper";
        fields.warning.textContent =
          "Live Trading is disabled by backend safety settings. Paper Trading remains active.";
      }
    }
    async function saveUiMode(mode) {
      setModeShell(mode);
      await fetch("/api/ui-mode", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ui_mode: mode})
      });
      await load();
    }
    async function saveSidebarPreference(collapsed) {
      document.body.classList.toggle("sidebar-collapsed", collapsed);
      await fetch("/api/ui-shell", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({sidebar_collapsed: collapsed})
      });
      await load();
    }
    async function markNotificationsRead() {
      await fetch("/api/mark-notifications-read", {method: "POST"});
      await load();
    }
    async function openPanel(mode, targetId) {
      await saveUiMode(mode);
      const target = document.getElementById(targetId);
      if (target) {
        target.closest("section").scrollIntoView({behavior: "smooth", block: "start"});
      }
    }
    async function viewAllActivity() {
      const response = await fetch("/api/activity", {cache: "no-store"});
      const activity = await response.json();
      renderActivityTimeline(activity, []);
    }
    async function saveStrategyLabSelection() {
      await fetch("/api/strategy-lab-selection", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          strategy: fields.labStrategy.value,
          symbol: fields.labSymbol.value,
          timeframe: fields.labTimeframe.value,
          run_mode: fields.labRunMode.value,
          parameter_profile: fields.labParameterProfile.value
        })
      });
      await load();
    }
    async function saveWatchlistSymbol(symbol) {
      await fetch("/api/watchlist-symbol", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({symbol})
      });
      await load();
    }
    async function addAlertRule() {
      const response = await fetch("/api/alert-rule", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          alert_type: fields.alertType.value,
          symbol: fields.alertSymbol.value,
          threshold: fields.alertThreshold.value,
          expected_value: fields.alertExpectedValue.value
        })
      });
      if (!response.ok) {
        const err = await response.json();
        fields.alertMessage.textContent = err.error;
        return;
      }
      fields.alertThreshold.value = "";
      await load();
    }
    async function deleteAlertRule(alertId) {
      await fetch("/api/delete-alert-rule", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({alert_id: alertId})
      });
      await load();
    }
    async function saveJournalEntry() {
      const response = await fetch("/api/journal-entry", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          trade_ref: fields.journalTradeRef.value,
          symbol: fields.alertSymbol.value || "BTC/USDT",
          setup_type: fields.journalSetupType.value,
          tags: fields.journalTags.value,
          notes: fields.journalNotes.value,
          mistake_review: fields.journalMistakeReview.value,
          lesson: fields.journalLesson.value,
          chart_context: fields.journalChartContext.value
        })
      });
      if (!response.ok) {
        const err = await response.json();
        fields.journalMessage.textContent = err.error;
        return;
      }
      fields.journalTags.value = "";
      fields.journalNotes.value = "";
      fields.journalMistakeReview.value = "";
      fields.journalLesson.value = "";
      fields.journalMessage.textContent = "";
      await load();
    }
    async function deleteJournalEntry(journalId) {
      await fetch("/api/delete-journal-entry", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({journal_id: journalId})
      });
      await load();
    }
    async function saveTraderFeedback() {
      const response = await fetch("/api/trader-feedback", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          reviewer_role: fields.feedbackReviewerRole.value,
          category: fields.feedbackCategory.value,
          severity: fields.feedbackSeverity.value,
          summary: fields.feedbackSummary.value,
          recommendation: fields.feedbackRecommendation.value
        })
      });
      if (!response.ok) {
        const err = await response.json();
        fields.feedbackMessage.textContent = err.error;
        return;
      }
      fields.feedbackSummary.value = "";
      fields.feedbackRecommendation.value = "";
      fields.feedbackResolution.value = "";
      fields.feedbackMessage.textContent = "";
      await load();
    }
    async function closeTraderFeedback(feedbackId) {
      const response = await fetch("/api/close-trader-feedback", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          feedback_id: feedbackId,
          resolution: fields.feedbackResolution.value
        })
      });
      if (!response.ok) {
        const err = await response.json();
        fields.feedbackMessage.textContent = err.error;
        return;
      }
      fields.feedbackResolution.value = "";
      await load();
    }
    async function saveChartDrawing() {
      const chart = chartState.lastChart || {};
      const response = await fetch("/api/chart-drawing", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          drawing_type: fields.drawingType.value,
          symbol: chart.symbol || "BTC/USDT",
          timeframe: chartState.timeframe,
          start_time: chartState.drawingStartTime,
          end_time: chartState.drawingEndTime,
          start_price: fields.drawingStartPrice.value,
          end_price: fields.drawingEndPrice.value,
          text: fields.drawingText.value,
          color: fields.drawingColor.value
        })
      });
      if (!response.ok) {
        const err = await response.json();
        fields.drawingMessage.textContent = err.error;
        return;
      }
      fields.drawingText.value = "";
      fields.drawingMessage.textContent = "";
      await load();
    }
    async function deleteChartDrawing(drawingId) {
      await fetch("/api/delete-chart-drawing", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({drawing_id: drawingId})
      });
      await load();
    }
    async function submitPaperOrderTicket() {
      const response = await fetch("/api/paper-order-ticket", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          order_type: fields.ticketOrderType.value,
          side: fields.ticketSide.value,
          quantity: fields.ticketQuantity.value,
          limit_price: fields.ticketLimitPrice.value,
          stop_price: fields.ticketStopPrice.value,
          take_profit_price: fields.ticketTakeProfitPrice.value,
          reason: "operator staged paper-only order ticket"
        })
      });
      if (!response.ok) {
        const err = await response.json();
        fields.ticketMessage.textContent = err.error;
        return;
      }
      fields.ticketLimitPrice.value = "";
      fields.ticketStopPrice.value = "";
      fields.ticketTakeProfitPrice.value = "";
      await load();
    }
    async function cancelPaperOrder(orderId) {
      await fetch("/api/cancel-paper-order", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          order_id: orderId,
          reason: "operator canceled paper-only staged order"
        })
      });
      await load();
    }
    async function stagePosition(path, reason) {
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason})
      });
      if (!response.ok) {
        const err = await response.json();
        fields.positionMessage.textContent = err.error;
        return;
      }
      await load();
    }
    async function post(path, reason) {
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason})
      });
      if (!response.ok) {
        const err = await response.json();
        alert(err.error);
      }
      await load();
    }
    document.getElementById("approve").onclick = () =>
      post("/api/approve-paper-trade", "operator approved paper-only simulated trade");
    document.getElementById("reject").onclick = () =>
      post("/api/reject-recommendation", "operator rejected current paper recommendation");
    document.getElementById("pause").onclick = () =>
      post("/api/pause-paper-bot", "operator paused paper bot");
    document.getElementById("resume").onclick = () =>
      post("/api/resume-paper-bot", "operator resumed paper bot");
    document.getElementById("emergency").onclick = () =>
      post("/api/emergency-stop", "operator emergency stop");
    document.getElementById("reset_emergency").onclick = () =>
      post("/api/reset-emergency-stop", "operator reset emergency stop");
    fields.addAlertRule.onclick = addAlertRule;
    fields.saveJournalEntry.onclick = saveJournalEntry;
    fields.saveTraderFeedback.onclick = saveTraderFeedback;
    fields.saveChartDrawing.onclick = saveChartDrawing;
    fields.submitPaperOrder.onclick = submitPaperOrderTicket;
    fields.stageClosePosition.onclick = () =>
      stagePosition("/api/stage-close-position", "operator staged paper close review");
    fields.stageReducePosition.onclick = () =>
      stagePosition("/api/stage-reduce-position", "operator staged paper reduce review");
    fields.chartZoomIn.onclick = () => zoomChart(-4);
    fields.chartZoomOut.onclick = () => zoomChart(4);
    fields.chartPanLeft.onclick = () => panChart(-4);
    fields.chartPanRight.onclick = () => panChart(4);
    fields.priceChart.onmousemove = updateChartTooltip;
    fields.priceChart.onmouseleave = () => {
      chartState.hoverIndex = null;
      fields.chartTooltip.style.display = "none";
      renderChart(chartState.lastChart || {});
    };
    window.onresize = () => renderChart(chartState.lastChart || {});
    fields.modeButtons.forEach((button) => {
      button.onclick = () => saveUiMode(button.dataset.uiMode);
    });
    fields.panelJumps.forEach((button) => {
      button.onclick = () => openPanel(button.dataset.uiMode, button.dataset.panelTarget);
    });
    fields.sidebarToggle.onclick = () =>
      saveSidebarPreference(!document.body.classList.contains("sidebar-collapsed"));
    fields.notificationBell.onclick = markNotificationsRead;
    fields.viewAllActivity.onclick = viewAllActivity;
    fields.tradingModeSelect.onchange = setTradingModeSelection;
    [
      fields.labStrategy,
      fields.labSymbol,
      fields.labTimeframe,
      fields.labRunMode,
      fields.labParameterProfile
    ].forEach((select) => {
      select.onchange = saveStrategyLabSelection;
    });
    load();
    setInterval(load, 15000);
    setInterval(updateNextCheckCountdown, 1000);
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
