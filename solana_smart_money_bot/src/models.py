from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String, default="manual")
    score: Mapped[float] = mapped_column(Float, default=75.0)
    win_rate: Mapped[float] = mapped_column(Float, default=50.0)
    avg_roi: Mapped[float] = mapped_column(Float, default=0.0)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    successful_signals: Mapped[int] = mapped_column(Integer, default=0)
    failed_signals: Mapped[int] = mapped_column(Integer, default=0)
    bad_streak: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="active")
    disabled_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class WhaleSignal(Base):
    __tablename__ = "whale_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, index=True, nullable=False)
    token_mint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String, default="buy")
    sol_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tx_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class WalletSignal(Base):
    __tablename__ = "wallet_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, index=True, nullable=False)
    token_mint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String, default="buy")
    amount_sol: Mapped[float] = mapped_column(Float, default=0.0)
    tx_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_mint: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    token_age_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    holder_count: Mapped[int] = mapped_column(Integer, default=0)
    top_holder_percent: Mapped[float] = mapped_column(Float, default=100.0)
    top_10_holder_percent: Mapped[float] = mapped_column(Float, default=100.0)
    mint_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_mint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount_inr: Mapped[float] = mapped_column(Float, nullable=False)
    amount_sol: Mapped[float] = mapped_column(Float, nullable=False)
    token_amount: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_price: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_price: Mapped[float] = mapped_column(Float, nullable=False)
    tp1_done: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="open")
    buy_tx_hash: Mapped[str] = mapped_column(String, nullable=False)
    sell_tx_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    pnl_inr: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_percent: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PositionWalletLink(Base):
    __tablename__ = "position_wallet_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    position_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    wallet_address: Mapped[str] = mapped_column(String, index=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    position_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    side: Mapped[str] = mapped_column(String, nullable=False)
    token_mint: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount_inr: Mapped[float] = mapped_column(Float, nullable=False)
    tx_hash: Mapped[str] = mapped_column(String, nullable=False)
    executor: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="filled")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PendingTrade(Base):
    __tablename__ = "pending_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    intent_id: Mapped[str] = mapped_column(String, unique=True, index=True, default=lambda: uuid.uuid4().hex)
    side: Mapped[str] = mapped_column(String, nullable=False)
    token_mint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    amount_inr: Mapped[float] = mapped_column(Float, default=0.0)
    amount_sol: Mapped[float] = mapped_column(Float, default=0.0)
    sell_percent: Mapped[float] = mapped_column(Float, default=0.0)
    token_amount: Mapped[float] = mapped_column(Float, default=0.0)
    position_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TradeAuditLog(Base):
    __tablename__ = "trade_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    intent_id: Mapped[str] = mapped_column(String, index=True, default="")
    event_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    side: Mapped[str] = mapped_column(String, default="")
    token_mint: Mapped[str] = mapped_column(String, index=True, default="")
    message: Mapped[str] = mapped_column(String, default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class HistoricalWalletTransaction(Base):
    __tablename__ = "historical_wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, index=True, nullable=False)
    signature: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    tx_timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, default="helius")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class HistoricalTokenSnapshot(Base):
    __tablename__ = "historical_token_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_mint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, index=True, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_usd: Mapped[float] = mapped_column(Float, default=0.0)
    token_age_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    holder_count: Mapped[int] = mapped_column(Integer, default=0)
    top_holder_percent: Mapped[float] = mapped_column(Float, default=100.0)
    top_10_holder_percent: Mapped[float] = mapped_column(Float, default=100.0)
    mint_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class HistoricalPricePoint(Base):
    __tablename__ = "historical_price_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_mint: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String, index=True, nullable=False)
    unix_timestamp: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
