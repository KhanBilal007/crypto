from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from config import settings
from src.models import Position, Trade, Wallet, WhaleSignal


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def collect_metrics(db) -> dict:
    now = _utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(hours=24)

    total_wallets = db.query(func.count(Wallet.id)).scalar() or 0
    active_wallets = db.query(func.count(Wallet.id)).filter(Wallet.status == "active").scalar() or 0
    standby_wallets = db.query(func.count(Wallet.id)).filter(Wallet.status == "standby").scalar() or 0
    disabled_wallets = db.query(func.count(Wallet.id)).filter(Wallet.status == "disabled").scalar() or 0

    avg_wallet_score = float(db.query(func.avg(Wallet.score)).scalar() or 0.0)
    low_score_wallets = db.query(func.count(Wallet.id)).filter(Wallet.score < settings.MIN_COMBINED_WALLET_SCORE).scalar() or 0

    signals_24h = db.query(func.count(WhaleSignal.id)).filter(WhaleSignal.timestamp >= last_24h).scalar() or 0

    open_positions = db.query(func.count(Position.id)).filter(Position.status == "open").scalar() or 0
    closed_today = db.query(Position).filter(Position.status == "closed", Position.closed_at >= day_start).all()
    pnl_today = float(sum(p.pnl_inr for p in closed_today))

    buy_trades_24h = db.query(func.count(Trade.id)).filter(Trade.side == "buy", Trade.timestamp >= last_24h).scalar() or 0
    sell_trades_24h = db.query(func.count(Trade.id)).filter(Trade.side == "sell", Trade.timestamp >= last_24h).scalar() or 0

    daily_halt = pnl_today <= -settings.DAILY_LOSS_LIMIT_INR

    return {
        "generated_at_utc": now.isoformat(timespec="seconds"),
        "wallets": {
            "total": total_wallets,
            "active": active_wallets,
            "standby": standby_wallets,
            "disabled": disabled_wallets,
            "avg_score": round(avg_wallet_score, 2),
            "below_threshold": low_score_wallets,
        },
        "activity_24h": {
            "signals": signals_24h,
            "buy_trades": buy_trades_24h,
            "sell_trades": sell_trades_24h,
        },
        "risk": {
            "open_positions": open_positions,
            "pnl_today_inr": round(pnl_today, 2),
            "daily_loss_limit_inr": settings.DAILY_LOSS_LIMIT_INR,
            "daily_halt": daily_halt,
        },
        "config": {
            "monitor_mode": settings.MONITOR_MODE,
            "execution_mode": settings.EXECUTION_MODE,
            "executor": settings.EXECUTOR,
            "paper_trading": settings.PAPER_TRADING,
            "forward_testing_mode": settings.FORWARD_TESTING_MODE,
            "live_trading_enabled": settings.LIVE_TRADING_ENABLED,
            "manual_approval_required": settings.MANUAL_APPROVAL_REQUIRED,
            "emergency_stop": settings.EMERGENCY_STOP,
            "confirmations": settings.MIN_WHALE_CONFIRMATIONS,
            "confirmation_window_minutes": settings.CONFIRMATION_WINDOW_MINUTES,
        },
    }
