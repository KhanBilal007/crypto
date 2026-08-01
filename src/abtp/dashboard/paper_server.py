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
      color-scheme: light;
      --bg: #f4f7f8;
      --panel: #ffffff;
      --text: #172026;
      --muted: #62717a;
      --line: #d8e0e4;
      --good: #0f7b52;
      --warn: #9a5b00;
      --bad: #b3261e;
      --accent: #1264a3;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 { font-size: 22px; margin: 0; letter-spacing: 0; }
    .header-tools {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
    }
    .mode-selector {
      display: inline-grid;
      grid-template-columns: repeat(3, minmax(112px, 1fr));
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #eef3f5;
    }
    .mode-button {
      min-height: 34px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      color: var(--text);
      padding: 7px 10px;
    }
    .mode-button:last-child { border-right: 0; }
    .mode-button.active {
      background: var(--accent);
      color: white;
    }
    main {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 16px;
      padding: 18px;
      max-width: 1440px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-width: 0;
    }
    h2 { margin: 0 0 12px; font-size: 16px; letter-spacing: 0; }
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
    }
    .good { color: var(--good); }
    .warn { color: var(--warn); }
    .bad { color: var(--bad); }
    dl { display: grid; grid-template-columns: 1fr auto; gap: 8px 12px; margin: 0; }
    dt { color: var(--muted); }
    dd { margin: 0; font-weight: 650; text-align: right; overflow-wrap: anywhere; }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; }
    button, a.button {
      min-height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: white;
      padding: 8px 12px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
    }
    button.secondary { background: white; color: var(--accent); }
    button.danger { background: var(--bad); border-color: var(--bad); }
    button:disabled {
      background: #d9dee2;
      border-color: #c7ced3;
      color: #69757d;
      cursor: not-allowed;
    }
    ul { margin: 0; padding-left: 18px; }
    li { margin-bottom: 6px; }
    .log {
      max-height: 260px;
      overflow: auto;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
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
      background: white;
      color: var(--text);
      margin-bottom: 8px;
      text-align: left;
    }
    .watchlist-row.active {
      border-color: var(--accent);
      background: #eef7fc;
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
      background: #fffaf0;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      overflow-wrap: anywhere;
    }
    th {
      color: var(--muted);
      font-size: 0.8rem;
      text-transform: uppercase;
    }
    .empty {
      color: var(--muted);
      margin: 0;
    }
    .warning {
      color: var(--bad);
      font-weight: 700;
    }
    .command-label {
      font-size: 1.35rem;
      font-weight: 800;
      margin-bottom: 10px;
    }
    .chart-canvas {
      display: block;
      width: 100%;
      height: 320px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
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
      background: #eef3f5;
    }
    .chart-tool {
      min-height: 32px;
      border: 0;
      border-right: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      color: var(--text);
      padding: 6px 9px;
      font-size: 0.85rem;
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
      background: rgba(255, 255, 255, 0.96);
      box-shadow: 0 6px 16px rgba(23, 32, 38, 0.12);
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
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
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
      background: white;
      color: var(--text);
      padding: 6px 8px;
      font: inherit;
    }
    textarea {
      min-height: 76px;
      resize: vertical;
    }
    [hidden] { display: none !important; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; padding: 12px; }
      .span-3, .span-4, .span-5,
      .span-6, .span-7, .span-8,
      .span-12 { grid-column: span 1; }
      header { align-items: flex-start; flex-direction: column; }
      .mode-selector { grid-template-columns: 1fr; width: 100%; }
      .mode-button { border-right: 0; border-bottom: 1px solid var(--line); }
      .mode-button:last-child { border-bottom: 0; }
      .selector-grid { grid-template-columns: 1fr; }
      .ticket-grid { grid-template-columns: 1fr; }
      .depth-grid { grid-template-columns: 1fr; }
      dl { grid-template-columns: 1fr; }
      dd { text-align: left; }
    }
  </style>
</head>
<body>
  <header>
    <h1>ABTP Paper Trading Dashboard</h1>
    <div class="header-tools">
      <div class="mode-selector" aria-label="Dashboard workspace">
        <button class="mode-button" data-ui-mode="beginner">Beginner</button>
        <button class="mode-button" data-ui-mode="advanced_trader">Advanced Trader</button>
        <button class="mode-button" data-ui-mode="strategy_lab">Strategy Lab</button>
      </div>
      <div class="badges">
        <span class="badge good" id="mode">PAPER MODE</span>
        <span class="badge good" id="safe">SAFE MODE</span>
        <span class="badge bad" id="live">LIVE OFF</span>
      </div>
    </div>
  </header>
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
          <button class="chart-tool" id="chart_pan_left" title="Pan left">Left</button>
          <button class="chart-tool" id="chart_zoom_out" title="Zoom out">-</button>
          <button class="chart-tool" id="chart_zoom_in" title="Zoom in">+</button>
          <button class="chart-tool" id="chart_pan_right" title="Pan right">Right</button>
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
    <section class="span-4" data-view="beginner">
      <h2>Beginner Command</h2>
      <div class="command-label" id="beginner_command_label">Do nothing now</div>
      <dl id="beginner_command"></dl>
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
    <section class="span-8" data-view="advanced_trader">
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
    <section class="span-4" data-view="beginner advanced_trader strategy_lab">
      <h2>Recommendation</h2><dl id="strategy"></dl>
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
    <section class="span-5" data-view="beginner advanced_trader">
      <h2>Paper Portfolio</h2><dl id="portfolio"></dl>
    </section>
    <section class="span-7" data-view="beginner advanced_trader">
      <h2>Controls</h2><div class="controls">
      <button id="approve">Approve Paper Trade</button>
      <button class="secondary" id="reject">Reject Recommendation</button>
      <button class="secondary" id="pause">Pause Paper Bot</button>
      <button class="secondary" id="resume">Resume Paper Bot</button>
      <button class="danger" id="emergency">Emergency Stop</button>
      <button class="secondary" id="reset_emergency">Reset Emergency Stop</button>
      <a class="button" href="/paper-report" target="_blank" rel="noreferrer">Daily Report</a>
    </div><p id="approval_reason"></p></section>
    <section class="span-6" data-view="beginner advanced_trader">
      <h2>Explanation</h2><ul id="explanation"></ul>
    </section>
    <section class="span-6" data-view="beginner advanced_trader">
      <h2>Paper Transactions</h2><div id="transactions"></div>
    </section>
    <section class="span-6" data-view="beginner advanced_trader strategy_lab">
      <h2>Readiness Gate</h2><div id="readiness_gate"></div>
    </section>
    <section class="span-6" data-view="beginner">
      <h2>Glossary</h2><div class="log"><dl id="glossary"></dl></div>
    </section>
    <section class="span-6" data-view="advanced_trader">
      <h2>Logs</h2><div class="log"><ul id="logs"></ul></div>
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
      <h2>Required Evidence</h2><dl id="strategy_lab_evidence"></dl>
    </section>
    <section class="span-6" data-view="strategy_lab">
      <h2>Compare Runs</h2><div id="strategy_lab_compare"></div>
    </section>
    <section class="span-12 warning" id="warning"></section>
  </main>
  <script>
    const UI_MODE_KEY = "abtp.paperDashboard.uiMode";
    const DEFAULT_UI_MODE = "advanced_trader";
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
      modeButtons: Array.from(document.querySelectorAll("[data-ui-mode]"))
    };
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
    function row(label, value) { return `<dt>${label}</dt><dd>${value}</dd>`; }
    function fill(id, data) {
      fields[id].innerHTML = Object.entries(data)
        .map(([k, v]) => row(k.replaceAll("_", " "), Array.isArray(v) ? v.join(", ") : v))
        .join("");
    }
    function setModeShell(mode) {
      activeUiMode = mode;
      localStorage.setItem(UI_MODE_KEY, mode);
      fields.modeButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.uiMode === mode);
      });
      document.querySelectorAll("[data-view]").forEach((section) => {
        section.hidden = !section.dataset.view.split(" ").includes(mode);
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
      canvas.width = Math.max(640, Math.floor(rect.width));
      canvas.height = 320;
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
      fill("market", data.market);
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
      fill("strategy", data.strategy);
      fill("trade", data.suggested_paper_trade);
      fill("portfolio", beginnerMode ? beginner.portfolio_summary || {} : data.portfolio);
      fields.beginnerCommandLabel.textContent =
        (beginner.command && beginner.command.label) || "Do nothing now";
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
      fields.explanation.innerHTML = explanationRows
        .map((item) => `<li>${item}</li>`)
        .join("");
      fields.logs.innerHTML = data.logs
        .map((item) => {
          return `<li><strong>${item.event_type}</strong>: ${item.message} ${item.reason}</li>`;
        })
        .join("");
      fields.warning.textContent = data.warning;
      fields.approvalReason.textContent = data.controls.approval_block_reason;
      fields.approve.disabled = !data.controls.can_approve_paper_trade;
      document.getElementById("mode").textContent = data.mode;
      document.getElementById("safe").textContent = data.safe_mode ? "SAFE MODE" : "SAFE MODE OFF";
      document.getElementById("live").textContent =
        data.live_trading_enabled ? "LIVE ON" : "LIVE OFF";
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
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
