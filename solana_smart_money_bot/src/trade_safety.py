from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import settings
from src.models import Position, PendingTrade, Token, Trade
from src.system_controls import load_state


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TradeIntent:
    intent_id: str
    side: str
    token_mint: str
    amount_inr: float = 0.0
    amount_sol: float = 0.0
    sell_percent: float = 0.0
    token_amount: float = 0.0
    position_id: int | None = None
    reason: str = ""
    wallet_score: float = 0.0
    risk_score: float = 0.0
    confirming_wallets: list[str] = field(default_factory=list)
    token_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: _utcnow().isoformat(timespec="seconds"))

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True, default=str)


@dataclass
class GateResult:
    allowed: bool
    reason: str
    manual_approval_required: bool = False
    pending_intent_id: str = ""


def build_trade_intent(
    *,
    side: str,
    token_mint: str,
    amount_inr: float = 0.0,
    amount_sol: float = 0.0,
    sell_percent: float = 0.0,
    token_amount: float = 0.0,
    position_id: int | None = None,
    reason: str = "",
    wallet_score: float = 0.0,
    risk_score: float = 0.0,
    confirming_wallets: list[str] | None = None,
    token_snapshot: dict[str, Any] | None = None,
) -> TradeIntent:
    return TradeIntent(
        intent_id=uuid4().hex,
        side=side,
        token_mint=token_mint,
        amount_inr=amount_inr,
        amount_sol=amount_sol,
        sell_percent=sell_percent,
        token_amount=token_amount,
        position_id=position_id,
        reason=reason,
        wallet_score=wallet_score,
        risk_score=risk_score,
        confirming_wallets=confirming_wallets or [],
        token_snapshot=token_snapshot or {},
    )


def _open_position_cap_hit(db: Session) -> bool:
    open_positions = db.query(func.count(Position.id)).filter(Position.status == "open").scalar() or 0
    return open_positions >= settings.MAX_OPEN_POSITIONS


def _daily_trade_cap_hit(db: Session) -> bool:
    day_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_buys = db.query(func.count(Trade.id)).filter(Trade.side == "buy", Trade.timestamp >= day_start).scalar() or 0
    return daily_buys >= settings.MAX_TRADES_PER_DAY


def _wallet_exposure_hit(db: Session, trade_amount_inr: float) -> bool:
    open_amount = db.query(func.sum(Position.amount_inr)).filter(Position.status == "open").scalar() or 0.0
    return (float(open_amount) + float(trade_amount_inr)) > settings.MAX_WALLET_EXPOSURE_INR


def evaluate_buy_gate(
    db: Session,
    token: Token,
    *,
    trade_amount_inr: float,
    combined_wallet_score: float,
) -> GateResult:
    state = load_state()
    if settings.EMERGENCY_STOP or state.emergency_stop:
        return GateResult(False, "Emergency stop is active")
    if state.sell_all_requested:
        return GateResult(False, "Sell-all is in progress")

    if _open_position_cap_hit(db):
        return GateResult(False, "Max open positions reached")

    if _daily_trade_cap_hit(db):
        return GateResult(False, "Daily trade cap reached")

    if _wallet_exposure_hit(db, trade_amount_inr):
        return GateResult(False, "Wallet exposure limit reached")

    if token.liquidity_usd < settings.MIN_LIQUIDITY_USD:
        return GateResult(False, "Liquidity below minimum")

    if token.token_age_minutes < settings.MIN_TOKEN_AGE_MINUTES:
        return GateResult(False, "Token too new")

    if settings.REQUIRE_MINT_AUTHORITY_DISABLED and not token.mint_revoked:
        return GateResult(False, "Mint authority still active")

    if settings.REQUIRE_FREEZE_AUTHORITY_DISABLED and not token.freeze_revoked:
        return GateResult(False, "Freeze authority still active")

    if token.top_holder_percent > settings.MAX_TOP_HOLDER_PERCENT:
        return GateResult(False, "Top holder concentration too high")

    if token.top_10_holder_percent > settings.MAX_TOP_10_HOLDER_PERCENT:
        return GateResult(False, "Top 10 holder concentration too high")

    if combined_wallet_score < settings.MIN_COMBINED_WALLET_SCORE:
        return GateResult(False, "Combined wallet score below threshold")

    return GateResult(True, "Gate passed")


def requires_manual_approval() -> bool:
    return settings.EXECUTION_MODE != "paper" and settings.MANUAL_APPROVAL_REQUIRED


def validate_live_trade_startup() -> None:
    if settings.EXECUTION_MODE == "jupiter_live" and not settings.LIVE_TRADING_ENABLED:
        raise RuntimeError("EXECUTION_MODE=jupiter_live requires LIVE_TRADING_ENABLED=true")
    if settings.EXECUTION_MODE != "paper" and settings.EMERGENCY_STOP:
        raise RuntimeError("EMERGENCY_STOP=true blocks live execution")
    if settings.EXECUTION_MODE != "paper" and not settings.PRIVATE_KEY.strip():
        raise RuntimeError("Live execution requires PRIVATE_KEY")


def store_pending_trade(db: Session, intent: TradeIntent, *, expires_in_minutes: int = 15) -> PendingTrade:
    pending = PendingTrade(
        intent_id=intent.intent_id,
        side=intent.side,
        token_mint=intent.token_mint,
        amount_inr=intent.amount_inr,
        amount_sol=intent.amount_sol,
        sell_percent=intent.sell_percent,
        token_amount=intent.token_amount,
        position_id=intent.position_id,
        reason=intent.reason,
        status="pending",
        payload_json=intent.to_json(),
        expires_at=_utcnow() + timedelta(minutes=expires_in_minutes),
    )
    db.add(pending)
    return pending
