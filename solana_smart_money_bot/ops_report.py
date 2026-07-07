from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from config import settings
from src.database import SessionLocal, init_db
from src.models import Position, Trade, Wallet, WhaleSignal


def pct(n: int, d: int) -> float:
    return (n / d * 100.0) if d else 0.0


def inr(v: float) -> str:
    return f"₹{v:,.2f}"


def main() -> None:
    init_db()

    now = datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(hours=24)

    with SessionLocal() as db:
        total_wallets = db.query(func.count(Wallet.id)).scalar() or 0
        active_wallets = db.query(func.count(Wallet.id)).filter(Wallet.status == "active").scalar() or 0
        standby_wallets = db.query(func.count(Wallet.id)).filter(Wallet.status == "standby").scalar() or 0
        disabled_wallets = db.query(func.count(Wallet.id)).filter(Wallet.status == "disabled").scalar() or 0

        avg_wallet_score = db.query(func.avg(Wallet.score)).scalar() or 0.0
        low_score_wallets = db.query(func.count(Wallet.id)).filter(Wallet.score < settings.MIN_COMBINED_WALLET_SCORE).scalar() or 0

        signals_24h = db.query(func.count(WhaleSignal.id)).filter(WhaleSignal.timestamp >= last_24h).scalar() or 0

        open_positions = db.query(func.count(Position.id)).filter(Position.status == "open").scalar() or 0
        closed_today = db.query(Position).filter(Position.status == "closed", Position.closed_at >= day_start).all()
        closed_count_today = len(closed_today)
        pnl_today = sum(p.pnl_inr for p in closed_today)

        buy_trades_24h = db.query(func.count(Trade.id)).filter(Trade.side == "buy", Trade.timestamp >= last_24h).scalar() or 0
        sell_trades_24h = db.query(func.count(Trade.id)).filter(Trade.side == "sell", Trade.timestamp >= last_24h).scalar() or 0

        trades_24h = db.query(Trade).filter(Trade.timestamp >= last_24h).all()
        relay_like_failures = len([t for t in trades_24h if t.status in {"rejected", "failed", "error"}])

        daily_halt = pnl_today <= -settings.DAILY_LOSS_LIMIT_INR

        print("=== Solana Smart Money Bot: Ops Report ===")
        print(f"Generated (UTC): {now.isoformat(timespec='seconds')}")
        print()

        print("Wallet Universe")
        print(f"- Total wallets: {total_wallets}")
        print(f"- Active: {active_wallets} / cap {settings.MAX_TRACKED_WALLETS}")
        print(f"- Standby: {standby_wallets}")
        print(f"- Disabled: {disabled_wallets}")
        print(f"- Avg wallet score: {avg_wallet_score:.2f}")
        print(f"- Wallets below score threshold ({settings.MIN_COMBINED_WALLET_SCORE}): {low_score_wallets}")
        print()

        print("Signal + Trade Activity (last 24h)")
        print(f"- Whale signals: {signals_24h}")
        print(f"- Buy trades: {buy_trades_24h}")
        print(f"- Sell trades: {sell_trades_24h}")
        print(f"- Trade fill ratio (sell/buy): {pct(sell_trades_24h, buy_trades_24h):.2f}%")
        print(f"- Relay-like failures: {relay_like_failures}")
        print()

        print("Risk + PnL")
        print(f"- Open positions: {open_positions} / cap {settings.MAX_OPEN_POSITIONS}")
        print(f"- Closed positions today: {closed_count_today}")
        print(f"- PnL today: {inr(pnl_today)}")
        print(f"- Daily loss limit: {inr(settings.DAILY_LOSS_LIMIT_INR)}")
        print(f"- Daily trading halt status: {'ON' if daily_halt else 'OFF'}")
        print()

        print("Config Snapshot")
        print(f"- Monitor mode: {settings.MONITOR_MODE}")
        print(f"- Execution mode: {settings.EXECUTION_MODE}")
        print(f"- Live trading enabled: {settings.LIVE_TRADING_ENABLED}")
        print(f"- Manual approval required: {settings.MANUAL_APPROVAL_REQUIRED}")
        print(f"- Emergency stop: {settings.EMERGENCY_STOP}")
        print(f"- Executor: {settings.EXECUTOR}")
        print(f"- Paper trading: {settings.PAPER_TRADING}")
        print(f"- Min confirmations: {settings.MIN_WHALE_CONFIRMATIONS} in {settings.CONFIRMATION_WINDOW_MINUTES}m")
        print(f"- Cooldowns: wallet={settings.WALLET_TRADE_COOLDOWN_MINUTES}m token={settings.TOKEN_TRADE_COOLDOWN_MINUTES}m")
        print(f"- SL/TP: {settings.STOP_LOSS_PERCENT}% / {settings.TAKE_PROFIT_PERCENT}% (+TP2 {settings.TAKE_PROFIT_PERCENT_2}%)")


if __name__ == "__main__":
    main()
