"""Standard-library local HTTP server for the ABTP paper dashboard."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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

    route = path.split("?", 1)[0]
    try:
        if method == "GET" and route == "/":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=DASHBOARD_HTML,
                content_type="text/html; charset=utf-8",
            )
        if method == "GET" and route == "/api/status":
            return _json_response(controller.state())
        if method == "GET" and route == "/paper-report":
            return DashboardHttpResponse(
                status=HTTPStatus.OK,
                body=_paper_report(controller.report_path),
                content_type="text/plain; charset=utf-8",
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

    controller = build_default_paper_dashboard_controller()
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


def _paper_report(path: str) -> str:
    report = Path(path)
    if report.exists():
        return report.read_text(encoding="utf-8")
    return "No paper-trading status report has been generated yet."


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
    .warning {
      color: var(--bad);
      font-weight: 700;
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; padding: 12px; }
      .span-3, .span-4, .span-5,
      .span-6, .span-7, .span-8,
      .span-12 { grid-column: span 1; }
      header { align-items: flex-start; flex-direction: column; }
      dl { grid-template-columns: 1fr; }
      dd { text-align: left; }
    }
  </style>
</head>
<body>
  <header>
    <h1>ABTP Paper Trading Dashboard</h1>
    <div class="badges">
      <span class="badge good" id="mode">PAPER MODE</span>
      <span class="badge good" id="safe">SAFE MODE</span>
      <span class="badge bad" id="live">LIVE OFF</span>
    </div>
  </header>
  <main>
    <section class="span-4"><h2>Market</h2><dl id="market"></dl></section>
    <section class="span-4"><h2>Recommendation</h2><dl id="strategy"></dl></section>
    <section class="span-4"><h2>Suggested Paper Trade</h2><dl id="trade"></dl></section>
    <section class="span-5"><h2>Paper Portfolio</h2><dl id="portfolio"></dl></section>
    <section class="span-7"><h2>Controls</h2><div class="controls">
      <button id="approve">Approve Paper Trade</button>
      <button class="secondary" id="reject">Reject Recommendation</button>
      <button class="secondary" id="pause">Pause Paper Bot</button>
      <button class="secondary" id="resume">Resume Paper Bot</button>
      <button class="danger" id="emergency">Emergency Stop</button>
      <a class="button" href="/paper-report" target="_blank" rel="noreferrer">Daily Report</a>
    </div><p id="approval_reason"></p></section>
    <section class="span-6"><h2>Explanation</h2><ul id="explanation"></ul></section>
    <section class="span-6"><h2>Logs</h2><div class="log"><ul id="logs"></ul></div></section>
    <section class="span-12 warning" id="warning"></section>
  </main>
  <script>
    const fields = {
      market: document.getElementById("market"),
      strategy: document.getElementById("strategy"),
      trade: document.getElementById("trade"),
      portfolio: document.getElementById("portfolio"),
      logs: document.getElementById("logs"),
      explanation: document.getElementById("explanation"),
      warning: document.getElementById("warning"),
      approvalReason: document.getElementById("approval_reason"),
      approve: document.getElementById("approve")
    };
    function row(label, value) { return `<dt>${label}</dt><dd>${value}</dd>`; }
    function fill(id, data) {
      fields[id].innerHTML = Object.entries(data)
        .map(([k, v]) => row(k.replaceAll("_", " "), v))
        .join("");
    }
    async function load() {
      const response = await fetch("/api/status", {cache: "no-store"});
      const data = await response.json();
      fill("market", data.market);
      fill("strategy", data.strategy);
      fill("trade", data.suggested_paper_trade);
      fill("portfolio", data.portfolio);
      fields.explanation.innerHTML = data.strategy.indicator_reasons
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
    load();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
