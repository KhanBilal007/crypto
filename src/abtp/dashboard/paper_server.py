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
        if method == "GET" and route == "/paper-transactions.csv":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=_transactions_csv(controller),
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
    logs = _list_field(state, "logs")
    transactions = _list_field(state, "transactions")
    risk_halts = _list_field(portfolio, "risk_halts")
    log_lines = _report_log_lines(logs)
    transaction_lines = _report_transaction_lines(transactions)
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


def _mapping_field(payload: Mapping[str, JsonValue], key: str) -> Mapping[str, JsonValue]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


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
    .selector-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    label {
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 0.8rem;
      font-weight: 700;
    }
    select {
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--text);
      padding: 6px 8px;
      font: inherit;
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
      <h2>Price Chart</h2><canvas class="chart-canvas" id="price_chart"></canvas>
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
        <a class="button" href="/paper-report" target="_blank" rel="noreferrer">Paper Report</a>
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
      fields.readinessGate.innerHTML = `
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
        evidence_status: strategyLab.evidence_status || "not_available",
        recommendation_actionable: strategyLab.recommendation_actionable || false,
        paper_approval_allowed: strategyLab.paper_approval_allowed || false,
        limitations: strategyLab.limitations || []
      });
      fill("strategyLabEvidence", {
        market_data: strategyLab.required_market_data || [],
        indicators: strategyLab.required_indicators || [],
        risk_checks: strategyLab.required_risk_checks || [],
        explanation_fields: strategyLab.required_explanation_fields || [],
        missing_evidence: strategyLab.missing_evidence || []
      });
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
            <tr><th>Run</th><th>Strategy</th><th>Parameters</th><th>Mode</th><th>Status</th></tr>
          </thead>
          <tbody>
            ${items.map((item) => `
              <tr>
                <td>${item.run_id}</td>
                <td>${item.strategy}</td>
                <td>${item.parameter_profile}</td>
                <td>${item.mode}</td>
                <td>${item.status}</td>
              </tr>`).join("")}
          </tbody>
        </table>`;
    }
    function renderChart(chart) {
      const canvas = fields.priceChart;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(640, Math.floor(rect.width));
      canvas.height = 320;
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const candles = (chart && chart.candles) || [];
      if (!candles.length) {
        ctx.fillStyle = "#62717a";
        ctx.fillText("No chart data available", 18, 28);
        return;
      }
      const prices = candles.flatMap((item) => [
        Number(item.high),
        Number(item.low),
        Number(item.close)
      ]);
      const min = Math.min(...prices);
      const max = Math.max(...prices);
      const pad = 24;
      const xStep = candles.length > 1 ? (canvas.width - pad * 2) / (candles.length - 1) : 1;
      const y = (price) => {
        if (max === min) {
          return canvas.height / 2;
        }
        return canvas.height - pad - ((price - min) / (max - min)) * (canvas.height - pad * 2);
      };
      ctx.strokeStyle = "#1264a3";
      ctx.lineWidth = 2;
      ctx.beginPath();
      candles.forEach((item, index) => {
        const x = pad + index * xStep;
        const closeY = y(Number(item.close));
        if (index === 0) {
          ctx.moveTo(x, closeY);
        } else {
          ctx.lineTo(x, closeY);
        }
      });
      ctx.stroke();
      ctx.fillStyle = "#0f7b52";
      ((chart && chart.markers) || []).forEach((marker) => {
        const index = candles.findIndex((item) => item.time === marker.time);
        if (index < 0) {
          return;
        }
        const x = pad + index * xStep;
        const markerY = y(Number(marker.price));
        ctx.beginPath();
        ctx.arc(x, markerY, 5, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.fillStyle = "#172026";
      ctx.fillText(`${chart.symbol} ${chart.timeframe}`, 18, 22);
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
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
