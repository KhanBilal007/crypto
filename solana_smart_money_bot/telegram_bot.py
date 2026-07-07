from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from src.audit import record_audit_event
from config import settings
from src.database import SessionLocal, init_db
from src.metrics import collect_metrics
from src.models import PendingTrade
from src.system_controls import approve_intent, reject_intent, request_sell_all, set_emergency_stop
from src.wallet_activity_state import load_wallet_activity_snapshot


async def send_message(chat_id: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )


def render_status() -> str:
    with SessionLocal() as db:
        m = collect_metrics(db)
    snap = load_wallet_activity_snapshot()
    return (
        "Smart Money Bot Status\n"
        f"Execution mode: {m['config']['execution_mode']}\n"
        f"Live enabled: {m['config']['live_trading_enabled']}\n"
        f"Forward testing: {m['config']['forward_testing_mode']}\n"
        f"Emergency stop: {m['config']['emergency_stop']}\n"
        f"Manual approval: {m['config']['manual_approval_required']}\n"
        f"Active wallets: {m['wallets']['active']}\n"
        f"Signals 24h: {m['activity_24h']['signals']}\n"
        f"Zero-signal cause: {snap.zero_signals_cause}\n"
        f"Open positions: {m['risk']['open_positions']}\n"
        f"PnL today: ₹{m['risk']['pnl_today_inr']}\n"
        f"Daily halt: {m['risk']['daily_halt']}"
    )


async def run_bot() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

    init_db()
    offset = 0

    while True:
        async with httpx.AsyncClient(timeout=35) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getUpdates",
                params={"timeout": 30, "offset": offset},
            )
            data = resp.json()

        for update in data.get("result", []):
            offset = max(offset, update["update_id"] + 1)
            msg = update.get("message", {})
            text = (msg.get("text") or "").strip().lower()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            if not chat_id:
                continue

            if text in {"/start", "/help"}:
                await send_message(
                    chat_id,
                    "Commands: /status, /wallets, /positions, /pending, /approve <id>, /reject <id>, /emergency_on, /emergency_off, /sellall",
                )
            elif text == "/status":
                await send_message(chat_id, render_status())
            elif text == "/wallets":
                with SessionLocal() as db:
                    m = collect_metrics(db)
                await send_message(
                    chat_id,
                    f"Wallets total={m['wallets']['total']} active={m['wallets']['active']} standby={m['wallets']['standby']} disabled={m['wallets']['disabled']}",
                )
            elif text == "/positions":
                with SessionLocal() as db:
                    m = collect_metrics(db)
                await send_message(chat_id, f"Open positions={m['risk']['open_positions']} PnL today=₹{m['risk']['pnl_today_inr']}")
            elif text == "/pending":
                with SessionLocal() as db:
                    pending = db.query(PendingTrade).filter(PendingTrade.status.in_(["pending", "approved"])).order_by(PendingTrade.created_at.desc()).limit(10).all()
                if not pending:
                    await send_message(chat_id, "No pending trades.")
                else:
                    lines = ["Pending trades:"]
                    for item in pending:
                        lines.append(
                            f"{item.intent_id} | {item.side} | {item.token_mint} | {item.status} | INR {item.amount_inr:.2f} | expires {item.expires_at.isoformat() if item.expires_at else 'n/a'}"
                        )
                    await send_message(chat_id, "\n".join(lines))
            elif text.startswith("/approve "):
                intent_id = text.split(maxsplit=1)[1].strip()
                with SessionLocal() as db:
                    item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).first()
                    if item:
                        item.status = "approved"
                        item.approved_at = item.approved_at or datetime.utcnow()
                        record_audit_event(
                            db,
                            event_type="telegram_approve",
                            intent_id=intent_id,
                            side=item.side,
                            token_mint=item.token_mint,
                            message="Approved from Telegram",
                        )
                        db.commit()
                approve_intent(intent_id)
                await send_message(chat_id, f"Approved {intent_id}")
            elif text.startswith("/reject "):
                intent_id = text.split(maxsplit=1)[1].strip()
                with SessionLocal() as db:
                    item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).first()
                    if item:
                        item.status = "rejected"
                        item.rejected_at = item.rejected_at or datetime.utcnow()
                        record_audit_event(
                            db,
                            event_type="telegram_reject",
                            intent_id=intent_id,
                            side=item.side,
                            token_mint=item.token_mint,
                            message="Rejected from Telegram",
                        )
                        db.commit()
                reject_intent(intent_id)
                await send_message(chat_id, f"Rejected {intent_id}")
            elif text == "/emergency_on":
                with SessionLocal() as db:
                    record_audit_event(db, event_type="telegram_emergency_on", message="Emergency stop enabled from Telegram")
                    db.commit()
                set_emergency_stop(True)
                await send_message(chat_id, "Emergency stop enabled.")
            elif text == "/emergency_off":
                with SessionLocal() as db:
                    record_audit_event(db, event_type="telegram_emergency_off", message="Emergency stop disabled from Telegram")
                    db.commit()
                set_emergency_stop(False)
                await send_message(chat_id, "Emergency stop disabled.")
            elif text == "/sellall":
                with SessionLocal() as db:
                    record_audit_event(db, event_type="telegram_sell_all", message="Sell-all requested from Telegram")
                    db.commit()
                request_sell_all()
                await send_message(chat_id, "Sell-all requested.")

        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_bot())
