from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from config import settings
from src.audit import record_audit_event
from src.database import SessionLocal, init_db
from src.metrics import collect_metrics
from src.models import PendingTrade, Position
from src.system_controls import (
    approve_intent,
    clear_sell_all_request,
    load_state,
    reject_intent,
    request_sell_all,
    set_emergency_stop,
)
from src.wallet_activity_state import load_wallet_activity_snapshot

app = FastAPI(title="Solana Smart Money Bot Dashboard")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/metrics")
def api_metrics() -> dict:
    with SessionLocal() as db:
        return collect_metrics(db)


@app.get("/api/wallet-activity")
def api_wallet_activity() -> dict:
    return load_wallet_activity_snapshot().__dict__


def _wallet_activity_panel() -> str:
    snap = load_wallet_activity_snapshot()
    wallets = snap.wallets[:5]
    wallet_rows = "".join(
        f"<li><code>{row.get('short_wallet') or row.get('wallet', '')}</code> "
        f"score={row.get('score', 0):.2f} "
        f"recent_txs={row.get('recent_txs', 0)} "
        f"parser_hits={row.get('parser_hits', 0)} "
        f"buy_like={row.get('buy_like', 0)} "
        f"last_seen={row.get('last_seen') or 'n/a'}</li>"
        for row in wallets
    ) or "<li class='muted'>No wallet diagnostics yet</li>"

    return f"""
    <div class="panel accent">
      <div class="panel-head">
        <div>
          <h2>Wallet Activity / Zero-Signal Diagnosis</h2>
          <div class="muted">Latest snapshot: {snap.generated_at_utc or 'n/a'} | Source: {snap.source}</div>
        </div>
        <a class="btn secondary" href="/api/wallet-activity">JSON</a>
      </div>
      <div class="grid mini">
        <div class="card"><b>Active wallets</b><br/>{snap.total_active_wallets}</div>
        <div class="card"><b>Recent txs</b><br/>{snap.total_recent_transactions}</div>
        <div class="card"><b>Parser hits</b><br/>{snap.buy_signals}</div>
        <div class="card"><b>Buy-like misses</b><br/>{snap.buy_like_transactions}</div>
        <div class="card"><b>Zero-signal cause</b><br/>{snap.zero_signals_cause}</div>
      </div>
      <div class="meta">
        <span class="pill">Wallets with activity: {snap.wallets_with_recent_transactions}</span>
        <span class="pill">No recent activity: {snap.wallets_with_zero_recent_transactions}</span>
        <span class="pill">Parser attempted: {snap.parser_attempted}</span>
        <span class="pill">Parser failed: {snap.parser_failed}</span>
        <span class="pill">API errors: {snap.api_errors}</span>
        <span class="pill">Rate limits: {snap.rate_limit_errors}</span>
      </div>
      <div class="muted" style="margin-top:12px">Top wallets</div>
      <ul class="wallet-list">{wallet_rows}</ul>
    </div>
    """


def _admin_page(message: str = "") -> str:
    with SessionLocal() as db:
        m = collect_metrics(db)
        pending = db.query(PendingTrade).order_by(PendingTrade.created_at.desc()).limit(20).all()
        open_positions = db.query(Position).filter(Position.status == "open").order_by(Position.created_at.desc()).limit(10).all()
        state = load_state()

    pending_rows = "".join(
        f"""
        <tr>
          <td><code>{item.intent_id}</code></td>
          <td>{item.side}</td>
          <td>{item.token_mint}</td>
          <td>{item.status}</td>
          <td>{item.amount_inr:.2f}</td>
          <td>{item.reason}</td>
          <td>
            <a class="btn" href="/admin/approve/{item.intent_id}">Approve</a>
            <a class="btn secondary" href="/admin/reject/{item.intent_id}">Reject</a>
          </td>
        </tr>
        """
        for item in pending
    ) or "<tr><td colspan='7' class='muted'>No pending trades</td></tr>"

    open_rows = "".join(
        f"""
        <tr>
          <td>{p.token_mint}</td>
          <td>{p.amount_inr:.2f}</td>
          <td>{p.entry_price:.6f}</td>
          <td>{p.status}</td>
          <td>{p.tp1_done}</td>
        </tr>
        """
        for p in open_positions
    ) or "<tr><td colspan='5' class='muted'>No open positions</td></tr>"

    return f"""
    <html>
      <head>
        <title>Smart Money Bot Admin</title>
        <meta http-equiv=\"refresh\" content=\"10\" />
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; background: linear-gradient(180deg,#0f172a,#1e293b 45%,#f8fafc 45%); color:#0f172a; }}
          .wrap {{ max-width: 1200px; margin: 0 auto; }}
          h1, h2 {{ color: #f8fafc; }}
          .sub {{ color: #cbd5e1; margin-bottom: 18px; }}
          .grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-top:16px; }}
          .grid.mini {{ grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); }}
          .card {{ background:white; border-radius:16px; padding:16px; box-shadow:0 12px 30px rgba(15,23,42,0.18); }}
          .panel {{ background: rgba(255,255,255,0.96); border-radius:16px; padding:16px; box-shadow:0 12px 30px rgba(15,23,42,0.18); margin-top:16px; }}
          .panel.accent {{ border: 1px solid #38bdf8; box-shadow:0 12px 30px rgba(56,189,248,0.18); }}
          .panel-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
          .btn {{ display:inline-block; padding:8px 12px; border-radius:999px; background:#0f766e; color:white; text-decoration:none; margin-right:8px; font-size:13px; }}
          .btn.secondary {{ background:#475569; }}
          .btn.warn {{ background:#b91c1c; }}
          table {{ width:100%; border-collapse: collapse; }}
          th, td {{ text-align:left; padding:10px 8px; border-bottom:1px solid #e2e8f0; vertical-align: top; }}
          th {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:#475569; }}
          .meta {{ display:flex; gap:12px; flex-wrap: wrap; margin-top: 8px; }}
          .pill {{ background:#e2e8f0; border-radius:999px; padding:6px 10px; font-size:13px; }}
          .muted {{ color:#64748b; }}
          .controls {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:12px; }}
          .message {{ background:#dcfce7; color:#14532d; padding:10px 12px; border-radius:10px; margin:12px 0; }}
          .wallet-list {{ margin:12px 0 0; padding-left:18px; color:#0f172a; }}
          .wallet-list li {{ margin: 6px 0; }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <h1>Admin Control Center</h1>
          <div class="sub">Generated UTC: {m['generated_at_utc']}</div>
          {f'<div class="message">{message}</div>' if message else ''}
          <div class="controls">
            <a class="btn warn" href="/admin/emergency/on">Emergency On</a>
            <a class="btn secondary" href="/admin/emergency/off">Emergency Off</a>
            <a class="btn warn" href="/admin/sellall">Request Sell-All</a>
            <a class="btn secondary" href="/admin/sellall/clear">Clear Sell-All</a>
            <a class="btn" href="/">Dashboard</a>
          </div>
          <div class="meta">
            <span class="pill">Execution mode: {m['config']['execution_mode']}</span>
            <span class="pill">Live enabled: {m['config']['live_trading_enabled']}</span>
            <span class="pill">Forward testing: {m['config']['forward_testing_mode']}</span>
            <span class="pill">Emergency stop: {state.emergency_stop}</span>
            <span class="pill">Sell-all requested: {state.sell_all_requested}</span>
            <span class="pill">Manual approval: {m['config']['manual_approval_required']}</span>
          </div>
          <div class="grid">
            <div class="card"><b>Wallets</b><br/>Total: {m['wallets']['total']}<br/>Active: {m['wallets']['active']}<br/>Standby: {m['wallets']['standby']}<br/>Disabled: {m['wallets']['disabled']}</div>
            <div class="card"><b>Activity</b><br/>Signals: {m['activity_24h']['signals']}<br/>Buys: {m['activity_24h']['buy_trades']}<br/>Sells: {m['activity_24h']['sell_trades']}</div>
            <div class="card"><b>Risk</b><br/>Open positions: {m['risk']['open_positions']}<br/>PnL today: ₹{m['risk']['pnl_today_inr']}<br/>Daily halt: {m['risk']['daily_halt']}</div>
            <div class="card"><b>Paper Capital</b><br/>Starting capital: ₹{settings.STARTING_CAPITAL_INR:.0f}<br/>Max trade size: ₹{settings.MAX_TRADE_SIZE_INR:.0f}<br/>Min trade size: ₹{settings.MIN_TRADE_INR:.0f}</div>
          </div>
          {_wallet_activity_panel()}
          <div class="panel">
            <h2>Pending Trades</h2>
            <table>
              <thead>
                <tr><th>Intent</th><th>Side</th><th>Token</th><th>Status</th><th>INR</th><th>Reason</th><th>Actions</th></tr>
              </thead>
              <tbody>{pending_rows}</tbody>
            </table>
          </div>
          <div class="panel">
            <h2>Open Positions</h2>
            <table>
              <thead>
                <tr><th>Token</th><th>INR</th><th>Entry</th><th>Status</th><th>TP1</th></tr>
              </thead>
              <tbody>{open_rows}</tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    with SessionLocal() as db:
        m = collect_metrics(db)

    return f"""
    <html>
      <head>
        <title>Smart Money Bot Dashboard</title>
        <meta http-equiv=\"refresh\" content=\"8\" />
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; background: #f7fafc; color:#1a202c; }}
          .grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(240px,1fr)); gap:16px; }}
          .card {{ background:white; border-radius:14px; padding:16px; box-shadow:0 2px 10px rgba(0,0,0,0.06); }}
          h1 {{ margin-top:0; }}
          .muted {{ color:#4a5568; font-size:14px; }}
        </style>
      </head>
      <body>
        <h1>Solana Smart Money Bot</h1>
        <div class=\"muted\">Generated UTC: {m['generated_at_utc']}</div>
        <div class=\"grid\" style=\"margin-top:16px\">
          <div class=\"card\"><b>Wallets</b><br/>Total: {m['wallets']['total']}<br/>Active: {m['wallets']['active']}<br/>Standby: {m['wallets']['standby']}<br/>Disabled: {m['wallets']['disabled']}<br/>Avg Score: {m['wallets']['avg_score']}</div>
          <div class=\"card\"><b>24h Activity</b><br/>Signals: {m['activity_24h']['signals']}<br/>Buy Trades: {m['activity_24h']['buy_trades']}<br/>Sell Trades: {m['activity_24h']['sell_trades']}</div>
          <div class=\"card\"><b>Risk</b><br/>Open Positions: {m['risk']['open_positions']}<br/>PnL Today: ₹{m['risk']['pnl_today_inr']}<br/>Daily Halt: {m['risk']['daily_halt']}</div>
          <div class=\"card\"><b>Paper Capital</b><br/>Starting capital: ₹{settings.STARTING_CAPITAL_INR:.0f}<br/>Max trade size: ₹{settings.MAX_TRADE_SIZE_INR:.0f}<br/>Min trade size: ₹{settings.MIN_TRADE_INR:.0f}</div>
          <div class=\"card\"><b>Config</b><br/>Mode: {m['config']['execution_mode']}<br/>Live: {m['config']['live_trading_enabled']}<br/>Forward: {m['config']['forward_testing_mode']}<br/>Emergency Stop: {m['config']['emergency_stop']}<br/>Manual Approval: {m['config']['manual_approval_required']}<br/>Confirmations: {m['config']['confirmations']} in {m['config']['confirmation_window_minutes']}m</div>
        </div>
        {_wallet_activity_panel()}
        <p class=\"muted\" style=\"margin-top:18px\">API: <code>/api/metrics</code></p>
      </body>
    </html>
    """


@app.get("/admin", response_class=HTMLResponse)
def admin_home(message: str = "") -> str:
    return _admin_page(message=message)


@app.get("/admin/approve/{intent_id}")
def admin_approve(intent_id: str) -> RedirectResponse:
    with SessionLocal() as db:
        item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).first()
        if item:
            item.status = "approved"
            item.approved_at = item.approved_at or _utcnow()
            record_audit_event(
                db,
                event_type="admin_approve",
                intent_id=intent_id,
                side=item.side,
                token_mint=item.token_mint,
                message="Approved from dashboard",
            )
            db.commit()
    approve_intent(intent_id)
    return RedirectResponse(url=f"/admin?message=Approved+{intent_id}", status_code=303)


@app.get("/admin/reject/{intent_id}")
def admin_reject(intent_id: str) -> RedirectResponse:
    with SessionLocal() as db:
        item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).first()
        if item:
            item.status = "rejected"
            item.rejected_at = item.rejected_at or _utcnow()
            record_audit_event(
                db,
                event_type="admin_reject",
                intent_id=intent_id,
                side=item.side,
                token_mint=item.token_mint,
                message="Rejected from dashboard",
            )
            db.commit()
    reject_intent(intent_id)
    return RedirectResponse(url=f"/admin?message=Rejected+{intent_id}", status_code=303)


@app.get("/admin/emergency/on")
def admin_emergency_on() -> RedirectResponse:
    with SessionLocal() as db:
        record_audit_event(db, event_type="admin_emergency_on", message="Emergency stop enabled from dashboard")
        db.commit()
    set_emergency_stop(True)
    return RedirectResponse(url="/admin?message=Emergency+stop+enabled", status_code=303)


@app.get("/admin/emergency/off")
def admin_emergency_off() -> RedirectResponse:
    with SessionLocal() as db:
        record_audit_event(db, event_type="admin_emergency_off", message="Emergency stop disabled from dashboard")
        db.commit()
    set_emergency_stop(False)
    return RedirectResponse(url="/admin?message=Emergency+stop+disabled", status_code=303)


@app.get("/admin/sellall")
def admin_sell_all() -> RedirectResponse:
    with SessionLocal() as db:
        record_audit_event(db, event_type="admin_sell_all", message="Sell-all requested from dashboard")
        db.commit()
    request_sell_all()
    return RedirectResponse(url="/admin?message=Sell-all+requested", status_code=303)


@app.get("/admin/sellall/clear")
def admin_clear_sell_all() -> RedirectResponse:
    with SessionLocal() as db:
        record_audit_event(db, event_type="admin_sell_all_clear", message="Sell-all cleared from dashboard")
        db.commit()
    clear_sell_all_request()
    return RedirectResponse(url="/admin?message=Sell-all+cleared", status_code=303)
