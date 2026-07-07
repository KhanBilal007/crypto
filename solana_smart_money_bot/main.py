
from __future__ import annotations

import asyncio
import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from config import settings
from src.database import SessionLocal, init_db
from src.audit import record_audit_event
from src.execution.base import BaseExecutor
from src.execution.jupiter_executor import JupiterExecutor
from src.execution.paper_executor import PaperExecutor
from src.execution.trojan_executor import TrojanExecutor
from src.models import PendingTrade, Position, Token, Trade, Wallet, WalletSignal, WhaleSignal
from src.price_monitor import PriceMonitor
from src.exit_rules import evaluate_exit_rule
from src.strategy import StrategyEngine
from src.token_data import TokenDataService
from src.telegram_notifier import TelegramNotifier
from src.tx_parser import TxParser
from src.forward_profile import apply_forward_testing_profile
from src.trade_safety import (
    build_trade_intent,
    evaluate_buy_gate,
    requires_manual_approval,
    validate_live_trade_startup,
    store_pending_trade,
)
from src.system_controls import clear_sell_all_request, consume_approval, load_state, set_emergency_stop
from src.wallet_activity_state import save_wallet_activity_snapshot
from src.signal_coverage import classify_transaction, shorten_address
from src.utils.logger import setup_logger
from src.wallet_monitor import WalletMonitor
from src.wallet_qualifier import WalletQualifier
from src.wallet_validation import is_valid_solana_address


def get_executor() -> BaseExecutor:
    if settings.EXECUTION_MODE == "jupiter_live":
        return JupiterExecutor()
    if settings.EXECUTION_MODE == "trojan":
        return TrojanExecutor()
    return PaperExecutor()


def seed_wallets() -> None:
    primary = [w.strip() for w in settings.WHALE_WALLETS.split(",") if w.strip()]
    candidates = [w.strip() for w in settings.CANDIDATE_WALLETS.split(",") if w.strip()]
    seed_list = primary if primary else candidates

    if not seed_list:
        logger.warning("No seed wallets provided yet. Add WHALE_WALLETS or CANDIDATE_WALLETS in .env")
        return

    with SessionLocal() as db:
        for idx, address in enumerate(seed_list):
            if not is_valid_solana_address(address):
                logger.warning(f"Skipping invalid wallet address during seed: {shorten_address(address)}")
                continue
            existing = db.query(Wallet).filter(Wallet.wallet_address == address).first()
            if existing:
                continue
            status = "active" if idx < settings.MAX_TRACKED_WALLETS else "standby"
            db.add(
                Wallet(
                    wallet_address=address,
                    label="seed",
                    score=75.0,
                    win_rate=55.0,
                    avg_roi=8.0,
                    status=status,
                )
            )
        db.commit()


def rebalance_wallet_universe(db) -> list[Wallet]:
    strategy = StrategyEngine()

    all_wallets = db.query(Wallet).all()
    if not all_wallets:
        return []

    for w in all_wallets:
        strategy.recover_wallet_if_due(w)
        if w.status != "disabled":
            w.score = strategy.calculate_wallet_score(w)

    eligible = [w for w in all_wallets if w.status != "disabled"]
    eligible.sort(key=lambda x: x.score, reverse=True)
    active_set = set([w.wallet_address for w in eligible[: settings.MAX_TRACKED_WALLETS]])

    for w in all_wallets:
        if w.status == "disabled":
            continue
        w.status = "active" if w.wallet_address in active_set else "standby"

    db.commit()
    return [w for w in all_wallets if w.status == "active"]


async def refill_wallet_universe(db, qualifier: WalletQualifier) -> None:
    if not settings.REPLACE_DISABLED_WALLETS:
        return
    candidates = [w.strip() for w in settings.CANDIDATE_WALLETS.split(",") if w.strip()]
    if not candidates:
        return

    existing = {w.wallet_address for w in db.query(Wallet).all()}
    for c in candidates:
        if not is_valid_solana_address(c):
            logger.warning(f"Skipping invalid candidate wallet={shorten_address(c)}")
            continue
        if c in existing:
            continue
        q = await qualifier.qualify_wallet(c)
        if not q.qualified:
            logger.info(f"Candidate rejected wallet={c} rounds={q.total_round_trips} win_rate={q.win_rate} avg_roi={q.avg_roi}")
            continue
        db.add(
            Wallet(
                wallet_address=c,
                label="candidate",
                score=q.score_seed,
                win_rate=q.win_rate,
                avg_roi=q.avg_roi,
                status="standby",
            )
        )
        existing.add(c)
        logger.info(f"Candidate accepted wallet={c} seed_score={q.score_seed} win_rate={q.win_rate} avg_roi={q.avg_roi}")
    db.commit()


def record_startup_recovery_state() -> None:
    state = load_state()
    with SessionLocal() as db:
        pending = db.query(PendingTrade).filter(PendingTrade.status == "approved").count()
        open_positions = db.query(Position).filter(Position.status == "open").count()
        if state.emergency_stop or state.sell_all_requested or pending or open_positions:
            record_audit_event(
                db,
                event_type="startup_recovery",
                message="Startup recovery state loaded",
                details={
                    "emergency_stop": state.emergency_stop,
                    "sell_all_requested": state.sell_all_requested,
                    "pending_approved": pending,
                    "open_positions": open_positions,
                },
            )
            db.commit()


async def upsert_token(db, token_mint: str, token_data_service: TokenDataService) -> Token:
    snapshot = await token_data_service.fetch_token_snapshot(token_mint)

    token = db.query(Token).filter(Token.token_mint == token_mint).first()
    if token is None:
        token = Token(token_mint=token_mint)
        db.add(token)

    token.liquidity_usd = float(snapshot["liquidity_usd"])
    token.token_age_minutes = float(snapshot["token_age_minutes"])
    token.holder_count = int(snapshot["holder_count"])
    token.top_holder_percent = float(snapshot["top_holder_percent"])
    token.top_10_holder_percent = float(snapshot["top_10_holder_percent"])
    token.mint_revoked = bool(snapshot["mint_revoked"])
    token.freeze_revoked = bool(snapshot["freeze_revoked"])

    db.commit()
    db.refresh(token)
    return token




def _signal_too_old(signal_ts: datetime) -> bool:
    age = (datetime.utcnow() - signal_ts).total_seconds()
    return age > settings.MAX_SIGNAL_AGE_SECONDS


def _throughput_limit_hit(db) -> tuple[bool, str]:
    now = datetime.utcnow()
    h_start = now - timedelta(hours=1)
    d_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    hourly = db.query(func.count(Trade.id)).filter(Trade.side == "buy", Trade.timestamp >= h_start).scalar() or 0
    daily = db.query(func.count(Trade.id)).filter(Trade.side == "buy", Trade.timestamp >= d_start).scalar() or 0
    capped_daily = db.query(func.count(Trade.id)).filter(Trade.side == "buy", Trade.timestamp >= d_start).scalar() or 0

    if hourly >= settings.MAX_NEW_TRADES_PER_HOUR:
        return True, f"Hourly new-trade cap hit ({hourly})"
    if daily >= settings.MAX_NEW_TRADES_PER_DAY:
        return True, f"Daily new-trade cap hit ({daily})"
    if capped_daily >= settings.MAX_TRADES_PER_DAY:
        return True, f"Strict daily trade cap hit ({capped_daily})"
    return False, ""


def _consecutive_loss_limit_hit(db) -> bool:
    sells = db.query(Trade).filter(Trade.side == "sell").order_by(Trade.timestamp.desc()).limit(settings.MAX_LOSS_STREAK).all()
    if len(sells) < settings.MAX_LOSS_STREAK:
        return False

    pos_ids = [t.position_id for t in sells if t.position_id is not None]
    if len(pos_ids) < settings.MAX_LOSS_STREAK:
        return False

    positions = {p.id: p for p in db.query(Position).filter(Position.id.in_(pos_ids)).all()}
    losses = 0
    for t in sells:
        p = positions.get(t.position_id)
        if p and p.pnl_inr < 0:
            losses += 1

    return losses >= settings.MAX_LOSS_STREAK


def _create_buy_position(
    db,
    *,
    token: Token,
    trade_inr: float,
    amount_sol: float,
    result,
    confirming_wallets: list[str],
    wallet_score: float,
    risk: float,
    executor_name: str,
    intent_id: str = "",
) -> Position:
    entry = result.price if result.price > 0 else 1.0
    stop_loss = entry * (1 - settings.STOP_LOSS_PERCENT / 100.0)
    take_profit = entry * (1 + settings.TAKE_PROFIT_PERCENT / 100.0)

    position = Position(
        token_mint=token.token_mint,
        entry_price=entry,
        amount_inr=trade_inr,
        amount_sol=amount_sol,
        token_amount=max(result.token_amount, 1.0),
        stop_loss_price=stop_loss,
        take_profit_price=take_profit,
        status="open",
        buy_tx_hash=result.tx_hash,
    )
    db.add(position)
    db.flush()
    strategy = StrategyEngine()
    strategy.link_position_wallets(db, position.id, confirming_wallets)
    db.add(
        Trade(
            position_id=position.id,
            side="buy",
            token_mint=token.token_mint,
            price=entry,
            amount_inr=trade_inr,
            tx_hash=result.tx_hash,
            executor=executor_name,
            status="filled",
        )
    )
    record_audit_event(
        db,
        event_type="buy_filled",
        intent_id=intent_id,
        side="buy",
        token_mint=token.token_mint,
        message="Buy execution filled",
        details={
            "trade_inr": trade_inr,
            "amount_sol": amount_sol,
            "wallet_score": wallet_score,
            "risk_score": risk,
            "confirming_wallets": confirming_wallets,
            "executor": executor_name,
            "tx_hash": result.tx_hash,
        },
    )
    return position


def _sell_quote_is_acceptable(quote: dict | None) -> tuple[bool, str]:
    if not quote:
        return False, "missing_quote"
    try:
        price_impact_pct = float(quote.get("priceImpactPct") or 0.0)
        out_amount = float(quote.get("outAmount") or 0.0)
    except (TypeError, ValueError):
        return False, "bad_quote_payload"
    if out_amount <= 0:
        return False, "no_out_amount"
    if price_impact_pct * 10_000 > settings.MAX_PRICE_IMPACT_BPS:
        return False, "price_impact_too_high"
    return True, "ok"


async def _execute_buy(
    db,
    *,
    token: Token,
    trade_inr: float,
    amount_sol: float,
    executor: BaseExecutor,
    confirming_wallets: list[str],
    wallet_score: float,
    risk: float,
    notifier: TelegramNotifier,
    intent_id: str = "",
    token_last_trade_at: dict[str, datetime] | None = None,
    wallet_last_trade_at: dict[str, datetime] | None = None,
) -> bool:
    record_audit_event(
        db,
        event_type="buy_sent",
        intent_id=intent_id,
        side="buy",
        token_mint=token.token_mint,
        message="Submitting live buy",
        details={"amount_sol": amount_sol, "executor": executor.name},
    )
    result = await executor.buy(token.token_mint, amount_sol)
    if result.confirmation_status in {"unknown", "timeout", "expired"}:
        logger.warning(
            f"Buy confirmation not final token={token.token_mint} status={result.confirmation_status}; pausing new buys"
        )
        await notifier.send(
            f"BUY confirmation not final\nToken: {token.token_mint}\nStatus: {result.confirmation_status}\nPausing new buys."
        )
        set_emergency_stop(True)
        record_audit_event(
            db,
            event_type="buy_unknown_confirmation",
            intent_id=intent_id,
            side="buy",
            token_mint=token.token_mint,
            message=f"Buy confirmation {result.confirmation_status}; new buys paused",
            details={
                "tx_hash": result.tx_hash,
                "executor": executor.name,
                "confirmation_status": result.confirmation_status,
                "retries": result.retries,
            },
        )
        db.commit()
        return False
    if not result.success:
        logger.error(f"Buy failed token={token.token_mint} msg={result.message}")
        record_audit_event(
            db,
            event_type="buy_failed",
            intent_id=intent_id,
            side="buy",
            token_mint=token.token_mint,
            message=result.message,
            details={"amount_sol": amount_sol, "executor": executor.name, "retries": result.retries},
        )
        db.commit()
        return False

    if result.retries > 0:
        record_audit_event(
            db,
            event_type="buy_retry",
            intent_id=intent_id,
            side="buy",
            token_mint=token.token_mint,
            message="Buy executed after retry",
            details={"retries": result.retries, "tx_hash": result.tx_hash, "executor": executor.name},
        )

    now = datetime.utcnow()
    if token_last_trade_at is not None:
        token_last_trade_at[token.token_mint] = now
    if wallet_last_trade_at is not None:
        for w in confirming_wallets:
            wallet_last_trade_at[w] = now

    _create_buy_position(
        db,
        token=token,
        trade_inr=trade_inr,
        amount_sol=amount_sol,
        result=result,
        confirming_wallets=confirming_wallets,
        wallet_score=wallet_score,
        risk=risk,
        executor_name=executor.name,
        intent_id=intent_id,
    )
    db.commit()
    logger.info(f"Opened position token={token.token_mint} inr={trade_inr:.2f}")
    record_audit_event(
        db,
        event_type="buy_confirmed",
        intent_id=intent_id,
        side="buy",
        token_mint=token.token_mint,
        message="Buy confirmed and position opened",
        details={"tx_hash": result.tx_hash, "executor": executor.name, "confirmation_status": result.confirmation_status},
    )
    db.commit()
    await notifier.send(
        f"BUY opened\nToken: {token.token_mint}\nINR: {trade_inr:.2f}\nWallet score: {wallet_score:.2f}\nRisk: {risk:.2f}"
    )
    return True


def _store_manual_buy_intent(
    db,
    *,
    token: Token,
    trade_inr: float,
    amount_sol: float,
    reason: str,
    wallet_score: float,
    risk: float,
    confirming_wallets: list[str],
) -> str:
    intent = build_trade_intent(
        side="buy",
        token_mint=token.token_mint,
        amount_inr=trade_inr,
        amount_sol=amount_sol,
        reason=reason,
        wallet_score=wallet_score,
        risk_score=risk,
        confirming_wallets=confirming_wallets,
        token_snapshot={
            "liquidity_usd": token.liquidity_usd,
            "token_age_minutes": token.token_age_minutes,
            "holder_count": token.holder_count,
            "top_holder_percent": token.top_holder_percent,
            "top_10_holder_percent": token.top_10_holder_percent,
            "mint_revoked": token.mint_revoked,
            "freeze_revoked": token.freeze_revoked,
        },
    )
    store_pending_trade(db, intent)
    record_audit_event(
        db,
        event_type="buy_pending_approval",
        intent_id=intent.intent_id,
        side="buy",
        token_mint=token.token_mint,
        message="Manual approval required before live buy",
        details={
            "trade_inr": trade_inr,
            "amount_sol": amount_sol,
            "wallet_score": wallet_score,
            "risk_score": risk,
            "confirming_wallets": confirming_wallets,
        },
    )
    return intent.intent_id


async def process_pending_trades(
    executor: BaseExecutor,
    strategy: StrategyEngine,
    notifier: TelegramNotifier,
    token_data_service: TokenDataService,
    wallet_last_trade_at: dict[str, datetime],
    token_last_trade_at: dict[str, datetime],
) -> None:
    with SessionLocal() as db:
        pending = (
            db.query(PendingTrade)
            .filter(PendingTrade.status == "approved")
            .order_by(PendingTrade.created_at.asc())
            .all()
        )
        if not pending:
            return

        for item in pending:
            if item.expires_at and item.expires_at < datetime.utcnow():
                item.status = "expired"
                consume_approval(item.intent_id)
                record_audit_event(
                    db,
                    event_type="pending_expired",
                    intent_id=item.intent_id,
                    side=item.side,
                    token_mint=item.token_mint,
                    message="Approved intent expired before execution",
                )
                record_audit_event(
                    db,
                    event_type="approval_expired",
                    intent_id=item.intent_id,
                    side=item.side,
                    token_mint=item.token_mint,
                    message="Approval expired",
                )
                record_audit_event(
                    db,
                    event_type="approval_consumed",
                    intent_id=item.intent_id,
                    side=item.side,
                    token_mint=item.token_mint,
                    message="Approval consumed after expiration",
                )
                continue

            if item.side != "buy":
                continue

            payload = json.loads(item.payload_json or "{}")
            try:
                token = await upsert_token(db, item.token_mint, token_data_service)
            except Exception as exc:
                item.status = "failed"
                item.rejected_at = datetime.utcnow()
                consume_approval(item.intent_id)
                set_emergency_stop(True)
                record_audit_event(
                    db,
                    event_type="approval_failed",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message="Token data unavailable during approved execution",
                    details={"error": str(exc)},
                )
                record_audit_event(
                    db,
                    event_type="approval_consumed",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message="Approval consumed after failure",
                )
                await notifier.send(
                    f"APPROVAL FAILED\nToken: {item.token_mint}\nReason: token data unavailable\nNew buys paused."
                )
                continue
            confirming_wallets = list(payload.get("confirming_wallets") or [])
            wallet_score = float(payload.get("wallet_score") or 0.0)
            risk_score = float(payload.get("risk_score") or 0.0)
            trade_inr = float(item.amount_inr or 0.0)
            amount_sol = float(item.amount_sol or 0.0)
            record_audit_event(
                db,
                event_type="approval_accepted",
                intent_id=item.intent_id,
                side="buy",
                token_mint=item.token_mint,
                message="Approved trade is being revalidated",
            )
            gate = evaluate_buy_gate(db, token, trade_amount_inr=trade_inr, combined_wallet_score=wallet_score)
            if not gate.allowed:
                item.status = "rejected"
                item.rejected_at = datetime.utcnow()
                consume_approval(item.intent_id)
                record_audit_event(
                    db,
                    event_type="pending_rejected",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message=gate.reason,
                )
                record_audit_event(
                    db,
                    event_type="approval_rejected",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message=gate.reason,
                )
                record_audit_event(
                    db,
                    event_type="approval_consumed",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message="Approval consumed after rejection",
                )
                continue

            ok = await _execute_buy(
                db,
                token=token,
                trade_inr=trade_inr,
                amount_sol=amount_sol,
                executor=executor,
                confirming_wallets=confirming_wallets,
                wallet_score=wallet_score,
                risk=risk_score,
                notifier=notifier,
                intent_id=item.intent_id,
                token_last_trade_at=token_last_trade_at,
                wallet_last_trade_at=wallet_last_trade_at,
            )
            if ok:
                item.status = "executed"
                item.executed_at = datetime.utcnow()
                consume_approval(item.intent_id)
                item.payload_json = json.dumps({**payload, "executed_at": item.executed_at.isoformat()}, sort_keys=True)
                record_audit_event(
                    db,
                    event_type="approval_consumed",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message="Approval consumed after execution",
                )
            else:
                item.status = "failed"
                item.rejected_at = datetime.utcnow()
                consume_approval(item.intent_id)
                record_audit_event(
                    db,
                    event_type="approval_failed",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message="Approved trade did not execute",
                )
                record_audit_event(
                    db,
                    event_type="approval_consumed",
                    intent_id=item.intent_id,
                    side="buy",
                    token_mint=item.token_mint,
                    message="Approval consumed after failed execution",
                )
        db.commit()


async def _sell_open_position(
    db,
    *,
    pos: Position,
    executor: BaseExecutor,
    strategy: StrategyEngine,
    notifier: TelegramNotifier,
    status: str,
    current_price: float,
    amount_percent: float = 100.0,
) -> bool:
    quote_status = "skipped"
    if executor.name == "jupiter":
        quote = await executor.quote_sell(pos.token_mint, amount_percent, pos.token_amount)
        acceptable, quote_reason = _sell_quote_is_acceptable(quote)
        quote_status = quote_reason
        record_audit_event(
            db,
            event_type="sell_quote_checked",
            side="sell",
            token_mint=pos.token_mint,
            message="Sell quote checked before execution",
            details={
                "executor": executor.name,
                "amount_percent": amount_percent,
                "quote_reason": quote_reason,
                "quote_ok": acceptable,
                "price_impact_pct": quote.get("priceImpactPct") if quote else None,
                "out_amount": quote.get("outAmount") if quote else None,
            },
        )
        if not acceptable:
            logger.warning(f"Sell quote rejected token={pos.token_mint} reason={quote_reason}")
            record_audit_event(
                db,
                event_type="sell_quote_rejected",
                side="sell",
                token_mint=pos.token_mint,
                message="Sell quote rejected before execution",
                details={"executor": executor.name, "quote_reason": quote_reason, "amount_percent": amount_percent},
            )
            return False

    record_audit_event(
        db,
        event_type="sell_sent",
        side="sell",
        token_mint=pos.token_mint,
        message="Submitting live sell",
        details={
            "status": status,
            "current_price": current_price,
            "amount_percent": amount_percent,
            "executor": executor.name,
            "quote_status": quote_status,
        },
    )
    result = await executor.sell(pos.token_mint, amount_percent, pos.token_amount)
    if result.confirmation_status in {"unknown", "timeout", "expired"}:
        set_emergency_stop(True)
        record_audit_event(
            db,
            event_type="sell_unknown_confirmation",
            side="sell",
            token_mint=pos.token_mint,
            message=f"Sell confirmation {result.confirmation_status}; new buys paused",
            details={"executor": executor.name, "retries": result.retries},
        )
        await notifier.send(
            f"SELL confirmation not final\nToken: {pos.token_mint}\nStatus: {result.confirmation_status}\nPausing new buys."
        )
        if not result.success:
            logger.error(f"Sell failed token={pos.token_mint} msg={result.message}")
            record_audit_event(
                db,
                event_type="sell_failed",
                side="sell",
                token_mint=pos.token_mint,
                message=result.message,
                details={"status": status, "executor": executor.name},
            )
        return False
    if not result.success:
        if result.retries > 0:
            record_audit_event(
                db,
                event_type="sell_retry",
                side="sell",
                token_mint=pos.token_mint,
                message="Sell failed after retry",
                details={"retries": result.retries, "executor": executor.name, "status": status},
            )
        logger.error(f"Sell failed token={pos.token_mint} msg={result.message}")
        record_audit_event(
            db,
            event_type="sell_failed",
            side="sell",
            token_mint=pos.token_mint,
            message=result.message,
            details={"status": status, "executor": executor.name},
        )
        return False

    if result.retries > 0:
        record_audit_event(
            db,
            event_type="sell_retry",
            side="sell",
            token_mint=pos.token_mint,
            message="Sell executed after retry",
            details={"retries": result.retries, "tx_hash": result.tx_hash, "executor": executor.name},
        )

    pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
    pnl_inr = pos.amount_inr * (pnl_pct / 100.0)
    pos.status = "closed"
    pos.closed_at = datetime.utcnow()
    pos.sell_tx_hash = result.tx_hash
    pos.pnl_percent = pnl_pct
    pos.pnl_inr = pnl_inr
    strategy.apply_position_outcome_to_wallets(db, position_id=pos.id, pnl_percent=pnl_pct)
    db.add(
        Trade(
            position_id=pos.id,
            side="sell",
            token_mint=pos.token_mint,
            price=current_price,
            amount_inr=pos.amount_inr * (amount_percent / 100.0),
            tx_hash=result.tx_hash,
            executor=executor.name,
            status=status,
        )
    )
    record_audit_event(
        db,
        event_type="sell_confirmed",
        side="sell",
        token_mint=pos.token_mint,
        message=f"Sell execution filled with status={status}",
        details={
            "status": status,
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "pnl_inr": pnl_inr,
            "tx_hash": result.tx_hash,
            "executor": executor.name,
        },
    )
    logger.info(f"Sell exit token={pos.token_mint} pnl={pnl_inr:.2f}")
    record_audit_event(
        db,
        event_type="position_closed",
        side="sell",
        token_mint=pos.token_mint,
        message="Position closed",
        details={"position_id": pos.id, "pnl_inr": pnl_inr, "pnl_pct": pnl_pct, "status": status},
    )
    await notifier.send(f"SELL exit\nToken: {pos.token_mint}\nPnL INR: {pnl_inr:.2f}\nPnL %: {pnl_pct:.2f}")
    return True

async def process_signal(
    signal: WhaleSignal,
    executor: BaseExecutor,
    strategy: StrategyEngine,
    token_data_service: TokenDataService,
    wallet_last_trade_at: dict[str, datetime],
    token_last_trade_at: dict[str, datetime],
    notifier: TelegramNotifier,
) -> None:
    with SessionLocal() as db:
        state = load_state()
        if state.emergency_stop or state.sell_all_requested:
            logger.warning("Emergency stop active; buy processing paused.")
            return

        if _signal_too_old(signal.timestamp):
            logger.info(f"Skipped stale signal token={signal.token_mint} age_s={(datetime.utcnow()-signal.timestamp).total_seconds():.1f}")
            return

        if _consecutive_loss_limit_hit(db):
            logger.warning("Consecutive-loss breaker triggered. Trading paused.")
            await notifier.send("Consecutive-loss breaker triggered. Trading paused.")
            return

        hit, why = _throughput_limit_hit(db)
        if hit:
            logger.warning(f"{why}. Trading paused for current interval.")
            return

        if strategy.daily_loss_hit(db):
            logger.warning("Daily loss limit reached. Trading paused for today.")
            await notifier.send("Daily loss limit reached. Trading paused for today.")
            return

        token = await upsert_token(db, signal.token_mint, token_data_service)
        record_audit_event(
            db,
            event_type="signal_received",
            side=signal.action,
            token_mint=signal.token_mint,
            message="Whale signal received",
            details={"wallet_address": signal.wallet_address, "sol_amount": signal.sol_amount, "tx_hash": signal.tx_hash},
        )
        logger.info(
            f"Token snapshot mint={token.token_mint} liquidity_usd={token.liquidity_usd:.2f} age_min={token.token_age_minutes:.1f} holders={token.holder_count} top_holder_pct={token.top_holder_percent:.2f} mint_revoked={token.mint_revoked} freeze_revoked={token.freeze_revoked}"
        )
        should, reason, risk, wallet_score, confirming_wallets = strategy.should_trade(db, token)
        strategy.log_decision(token.token_mint, reason, risk, wallet_score)
        record_audit_event(
            db,
            event_type="wallet_score_updated",
            side="buy" if should else "hold",
            token_mint=token.token_mint,
            message="Wallet score evaluated",
            details={"wallet_score": wallet_score, "risk_score": risk, "confirming_wallets": confirming_wallets},
        )
        if should:
            record_audit_event(
                db,
                event_type="trade_approved_by_strategy",
                side="buy",
                token_mint=token.token_mint,
                message="Strategy approved trade",
                details={"wallet_score": wallet_score, "risk_score": risk, "reason": reason},
            )
        else:
            record_audit_event(
                db,
                event_type="trade_rejected_by_strategy",
                side="buy",
                token_mint=token.token_mint,
                message="Strategy rejected trade",
                details={"wallet_score": wallet_score, "risk_score": risk, "reason": reason},
            )
        db.commit()

        if not should:
            return

        now = datetime.utcnow()
        token_cooldown = token_last_trade_at.get(token.token_mint)
        if token_cooldown and now - token_cooldown < timedelta(minutes=settings.TOKEN_TRADE_COOLDOWN_MINUTES):
            logger.info(f"Skipped token={token.token_mint} due token cooldown")
            return

        for w in confirming_wallets:
            wt = wallet_last_trade_at.get(w)
            if wt and now - wt < timedelta(minutes=settings.WALLET_TRADE_COOLDOWN_MINUTES):
                logger.info(f"Skipped token={token.token_mint} due wallet cooldown wallet={w}")
                return

        open_capital = settings.STARTING_CAPITAL_INR
        for pos in db.query(Position).filter(Position.status == "open").all():
            open_capital -= pos.amount_inr

        trade_inr = strategy.calculate_trade_size_inr(open_capital, wallet_score)
        if trade_inr <= 0:
            logger.info("Trade skipped due to low available capital")
            return

        gate = evaluate_buy_gate(db, token, trade_amount_inr=trade_inr, combined_wallet_score=wallet_score)
        if not gate.allowed:
            logger.info(f"Trade blocked by safety gate token={token.token_mint} reason={gate.reason}")
            record_audit_event(
                db,
                event_type="buy_blocked",
                side="buy",
                token_mint=token.token_mint,
                message=gate.reason,
                details={
                    "trade_inr": trade_inr,
                    "wallet_score": wallet_score,
                    "risk_score": risk,
                    "confirming_wallets": confirming_wallets,
                },
            )
            db.commit()
            return

        amount_sol = trade_inr / settings.SOL_INR_PRICE
        signal_detected_at = signal.timestamp
        latency_ms = (datetime.utcnow() - signal_detected_at).total_seconds() * 1000.0
        logger.info(f"Execution latency token={token.token_mint} signal_to_buy_ms={latency_ms:.1f}")

        if requires_manual_approval():
            intent_id = _store_manual_buy_intent(
                db,
                token=token,
                trade_inr=trade_inr,
                amount_sol=amount_sol,
                reason=gate.reason,
                wallet_score=wallet_score,
                risk=risk,
                confirming_wallets=confirming_wallets,
            )
            db.commit()
            logger.info(f"Manual approval required for token={token.token_mint} intent_id={intent_id}")
            await notifier.send(
                f"BUY pending approval\nToken: {token.token_mint}\nIntent: {intent_id}\nINR: {trade_inr:.2f}\nReason: {gate.reason}"
            )
            return

        ok = await _execute_buy(
            db,
            token=token,
            trade_inr=trade_inr,
            amount_sol=amount_sol,
            executor=executor,
            confirming_wallets=confirming_wallets,
            wallet_score=wallet_score,
            risk=risk,
            notifier=notifier,
            token_last_trade_at=token_last_trade_at,
            wallet_last_trade_at=wallet_last_trade_at,
        )
        if ok:
            db.commit()


async def wallet_loop(executor: BaseExecutor, strategy: StrategyEngine, token_data_service: TokenDataService, notifier: TelegramNotifier, qualifier: WalletQualifier) -> None:
    monitor = WalletMonitor(mode=settings.MONITOR_MODE)
    parser = TxParser()
    wallet_last_trade_at: dict[str, datetime] = {}
    token_last_trade_at: dict[str, datetime] = {}
    cycle_counter = 0

    with SessionLocal() as db:
        total_wallets = db.query(Wallet).count()
        active_wallets = db.query(Wallet).filter(Wallet.status == "active").count()
        standby_wallets = db.query(Wallet).filter(Wallet.status == "standby").count()
        disabled_wallets = db.query(Wallet).filter(Wallet.status == "disabled").count()
        active_records = db.query(Wallet).filter(Wallet.status == "active").order_by(Wallet.score.desc()).all()
        logger.info(
            "Forward wallet snapshot "
            f"helius_configured={bool(settings.HELIUS_API_KEY)} "
            f"wallet_monitor_started={True} "
            f"polling_enabled={settings.MONITOR_MODE == 'polling'} "
            f"websocket_enabled={settings.MONITOR_MODE == 'websocket'} "
            f"total_wallets={total_wallets} active_wallets={active_wallets} "
            f"standby_wallets={standby_wallets} disabled_wallets={disabled_wallets}"
        )
        for wallet in active_records[: settings.MAX_TRACKED_WALLETS]:
            logger.info(
                "Active wallet detail "
                f"wallet={shorten_address(wallet.wallet_address)} "
                f"score={wallet.score:.2f} "
                f"status={wallet.status} "
                f"last_seen_signature={'set' if wallet.wallet_address in monitor.last_seen_signature else 'unset'}"
            )

    while True:
        cycle_counter += 1
        cycle_stats: Counter[str] = Counter()
        await process_pending_trades(
            executor,
            strategy,
            notifier,
            token_data_service,
            wallet_last_trade_at,
            token_last_trade_at,
        )

        with SessionLocal() as db:
            await refill_wallet_universe(db, qualifier)
            active_wallets = rebalance_wallet_universe(db)

        for wallet in active_wallets:
            txs = await monitor.poll_wallet(wallet.wallet_address)
            cycle_stats["wallets_polled"] += 1
            cycle_stats["raw_tx_fetched"] += len(txs)
            for tx in txs:
                cycle_stats["parser_attempted"] += 1
                classification = classify_transaction(wallet.wallet_address, tx, parser)
                cycle_stats[classification.category] += 1
                parsed = classification.parsed_signal
                if parsed is None:
                    cycle_stats["parser_failed"] += 1
                    continue
                cycle_stats["parser_succeeded"] += 1

                with SessionLocal() as db:
                    signal = WhaleSignal(
                        wallet_address=parsed.wallet_address,
                        token_mint=parsed.token_mint,
                        action=parsed.action,
                        sol_amount=parsed.sol_amount,
                        tx_hash=parsed.tx_hash,
                        timestamp=parsed.timestamp,
                    )
                    db.add(signal)
                    db.add(
                        WalletSignal(
                            wallet_address=parsed.wallet_address,
                            token_mint=parsed.token_mint,
                            action=parsed.action,
                            amount_sol=parsed.sol_amount,
                            tx_hash=parsed.tx_hash,
                            timestamp=parsed.timestamp,
                        )
                    )
                    try:
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        continue
                    logger.info(
                        f"Saved signal wallet={parsed.wallet_address} token={parsed.token_mint} sol_amount={parsed.sol_amount:.6f} tx={parsed.tx_hash}"
                    )
                    record_audit_event(
                        db,
                        event_type="signal_received",
                        side=parsed.action,
                        token_mint=parsed.token_mint,
                        message="Whale signal received",
                        details={"wallet_address": parsed.wallet_address, "sol_amount": parsed.sol_amount, "tx_hash": parsed.tx_hash},
                    )

                await process_signal(
                    signal,
                    executor,
                    strategy,
                    token_data_service,
                    wallet_last_trade_at,
                    token_last_trade_at,
                    notifier,
                )

        if cycle_stats["wallets_polled"] or cycle_stats["raw_tx_fetched"]:
            logger.info(
                "Forward cycle summary "
                f"cycle={cycle_counter} "
                f"wallets_polled={cycle_stats['wallets_polled']} "
                f"raw_tx_fetched={cycle_stats['raw_tx_fetched']} "
                f"parser_attempted={cycle_stats['parser_attempted']} "
                f"parser_succeeded={cycle_stats['parser_succeeded']} "
                f"buy_signals={cycle_stats['parsed_buy_signal']} "
                f"buy_like={cycle_stats['parser_not_detecting_buys']} "
                f"transfer_only={cycle_stats['ignored_transfer_only']} "
                f"sell={cycle_stats['ignored_sell']} "
                f"unsupported_dex={cycle_stats['ignored_unsupported_dex_program']} "
                f"missing_token_mint={cycle_stats['ignored_missing_token_mint']} "
                f"not_swap={cycle_stats['ignored_not_swap']} "
                f"parser_error={cycle_stats['parser_error']}"
            )
            with SessionLocal() as db:
                active_snapshot_wallets = db.query(Wallet).filter(Wallet.status == "active").order_by(Wallet.score.desc()).all()
                save_wallet_activity_snapshot(
                    {
                        "generated_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
                        "source": "forward",
                        "total_active_wallets": len(active_snapshot_wallets),
                        "total_recent_transactions": cycle_stats["raw_tx_fetched"],
                        "wallets_with_recent_transactions": sum(1 for wallet in active_snapshot_wallets if monitor.last_poll_tx_count.get(wallet.wallet_address, 0) > 0),
                        "wallets_with_zero_recent_transactions": sum(1 for wallet in active_snapshot_wallets if monitor.last_poll_tx_count.get(wallet.wallet_address, 0) == 0),
                        "parser_attempted": cycle_stats["parser_attempted"],
                        "parser_succeeded": cycle_stats["parser_succeeded"],
                        "parser_failed": cycle_stats["parser_failed"],
                        "buy_like_transactions": cycle_stats["parser_not_detecting_buys"],
                        "buy_signals": cycle_stats["parsed_buy_signal"],
                        "api_errors": sum(1 for state in monitor.last_poll_result.values() if state == "error"),
                        "rate_limit_errors": 0,
                        "forward_signals": 0,
                        "zero_signals_cause": "insufficient_runtime_window" if cycle_stats["parser_succeeded"] == 0 else "unknown",
                        "rejection_breakdown": {
                            "ignored_transfer_only": cycle_stats["ignored_transfer_only"],
                            "ignored_sell": cycle_stats["ignored_sell"],
                            "ignored_unsupported_dex_program": cycle_stats["ignored_unsupported_dex_program"],
                            "ignored_missing_token_mint": cycle_stats["ignored_missing_token_mint"],
                            "ignored_not_swap": cycle_stats["ignored_not_swap"],
                            "parser_not_detecting_buys": cycle_stats["parser_not_detecting_buys"],
                            "parsed_buy_signal": cycle_stats["parsed_buy_signal"],
                        },
                        "wallets": [
                            {
                                "wallet": wallet.wallet_address,
                                "short_wallet": shorten_address(wallet.wallet_address),
                                "score": round(wallet.score, 2),
                                "status": wallet.status,
                                "last_seen": monitor.last_poll_at.get(wallet.wallet_address, datetime.utcnow()).isoformat() if monitor.last_poll_at.get(wallet.wallet_address) else "",
                                "recent_txs": monitor.last_poll_tx_count.get(wallet.wallet_address, 0),
                                "parser_hits": 0,
                                "buy_like": 0,
                            }
                            for wallet in active_snapshot_wallets[:5]
                        ],
                    }
                )

        await monitor.monitor_delay()


async def process_sell_all_request(
    db,
    *,
    executor: BaseExecutor,
    strategy: StrategyEngine,
    notifier: TelegramNotifier,
    price_monitor: PriceMonitor,
) -> bool:
    state = load_state()
    if not state.sell_all_requested:
        return False

    open_positions = db.query(Position).filter(Position.status == "open").all()
    record_audit_event(
        db,
        event_type="sell_all_started",
        side="sell",
        message="Sell-all requested by operator",
        details={"open_positions": len(open_positions)},
    )
    any_failures = False
    for pos in open_positions:
        current_price = await price_monitor.get_price(pos.token_mint, pos.entry_price)
        sold = await _sell_open_position(
            db,
            pos=pos,
            executor=executor,
            strategy=strategy,
            notifier=notifier,
            status="sell_all",
            current_price=current_price,
            amount_percent=100.0,
        )
        if not sold:
            any_failures = True
    db.commit()
    remaining = db.query(Position).filter(Position.status == "open").count()
    if any_failures or remaining > 0:
        set_emergency_stop(True)
        record_audit_event(
            db,
            event_type="sell_all_incomplete",
            side="sell",
            message="Sell-all finished with remaining open positions",
            details={"remaining_open_positions": remaining},
        )
        db.commit()
        logger.warning("Sell-all request incomplete; keeping request active and pausing buys")
        await notifier.send("Sell-all request incomplete. Buys paused until all positions are closed.")
        return False

    clear_sell_all_request()
    record_audit_event(
        db,
        event_type="sell_all_completed",
        side="sell",
        message="Sell-all request completed",
    )
    db.commit()
    logger.warning("Sell-all request completed and cleared")
    await notifier.send("Sell-all request completed.")
    return True


async def position_loop(
    executor: BaseExecutor,
    strategy: StrategyEngine,
    notifier: TelegramNotifier,
    token_data_service: TokenDataService,
) -> None:
    price_monitor = PriceMonitor()
    peak_price_by_position: dict[int, float] = {}

    while True:
        with SessionLocal() as db:
            open_positions = db.query(Position).filter(Position.status == "open").all()

            if load_state().sell_all_requested:
                await process_sell_all_request(
                    db,
                    executor=executor,
                    strategy=strategy,
                    notifier=notifier,
                    price_monitor=price_monitor,
                )
                await asyncio.sleep(settings.POSITION_POLL_SECONDS)
                continue

            for pos in open_positions:
                now = datetime.now(timezone.utc)
                window_start = pos.created_at
                if window_start.tzinfo is None:
                    window_start = window_start.replace(tzinfo=timezone.utc)
                if (now - window_start).total_seconds() > 48 * 3600:
                    window_start = now - timedelta(hours=48)

                candles = await token_data_service.fetch_ohlcv_candles(
                    pos.token_mint,
                    int(window_start.timestamp()),
                    int(now.timestamp()),
                    interval="1m",
                )
                if candles:
                    current_price = candles[-1].close
                    peak = max(
                        peak_price_by_position.get(pos.id, pos.entry_price),
                        max((c.high for c in candles if c.high > 0), default=current_price),
                        current_price,
                    )
                    peak_price_by_position[pos.id] = peak
                    exit_decision = evaluate_exit_rule(
                        candles,
                        entry_price=pos.entry_price,
                        stop_loss_price=pos.stop_loss_price,
                        take_profit_price=pos.take_profit_price,
                        peak_price=peak,
                        trailing_stop_percent=settings.TRAILING_STOP_PERCENT,
                    )
                    record_audit_event(
                        db,
                        event_type="sell_signal",
                        side="sell",
                        token_mint=pos.token_mint,
                        message="Exit rules evaluated",
                        details={
                            "reason": exit_decision.reason,
                            "should_exit": exit_decision.should_exit,
                            "current_price": current_price,
                            "ema": exit_decision.ema,
                            "vwap": exit_decision.vwap,
                            "latest_volume": exit_decision.latest_volume,
                            "average_volume": exit_decision.average_volume,
                        },
                    )
                    if exit_decision.should_exit:
                        amount_percent = settings.TP1_SELL_PERCENT if exit_decision.reason == "take_profit" and not pos.tp1_done else 100.0
                        status = "tp1" if amount_percent < 100.0 else "filled"
                        sold = await _sell_open_position(
                            db,
                            pos=pos,
                            executor=executor,
                            strategy=strategy,
                            notifier=notifier,
                            status=status,
                            current_price=current_price,
                            amount_percent=amount_percent,
                        )
                        if sold and amount_percent < 100.0:
                            pos.tp1_done = True
                            pos.stop_loss_price = max(pos.stop_loss_price, pos.entry_price)
                        continue

                current_price = await price_monitor.get_price(pos.token_mint, pos.entry_price)
                peak = max(peak_price_by_position.get(pos.id, pos.entry_price), current_price)
                peak_price_by_position[pos.id] = peak

                sell_count = db.query(Trade).filter(Trade.position_id == pos.id, Trade.side == "sell").count()

                if pos.tp1_done:
                    trailing_stop = peak * (1 - settings.TRAILING_STOP_PERCENT / 100.0)
                    if trailing_stop > pos.stop_loss_price:
                        pos.stop_loss_price = trailing_stop

                if current_price <= pos.stop_loss_price:
                    await _sell_open_position(
                        db,
                        pos=pos,
                        executor=executor,
                        strategy=strategy,
                        notifier=notifier,
                        status="filled",
                        current_price=current_price,
                        amount_percent=100.0,
                    )

                elif current_price >= pos.take_profit_price and not pos.tp1_done:
                    result = await executor.sell(pos.token_mint, settings.TP1_SELL_PERCENT, pos.token_amount)
                    if result.success:
                        pos.tp1_done = True
                        pos.stop_loss_price = max(pos.stop_loss_price, pos.entry_price)
                        pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
                        db.add(
                            Trade(
                                position_id=pos.id,
                                side="sell",
                                token_mint=pos.token_mint,
                                price=current_price,
                                amount_inr=pos.amount_inr * (settings.TP1_SELL_PERCENT / 100.0),
                                tx_hash=result.tx_hash,
                                executor=executor.name,
                                status="tp1",
                            )
                        )
                        record_audit_event(
                            db,
                            event_type="sell_tp1",
                            side="sell",
                            token_mint=pos.token_mint,
                            message="TP1 target reached",
                            details={"current_price": current_price, "tx_hash": result.tx_hash, "pnl_pct": pnl_pct},
                        )
                        logger.info(f"TP1 hit token={pos.token_mint}; sold {settings.TP1_SELL_PERCENT}%")
                        await notifier.send(f"TP1 hit\nToken: {pos.token_mint}\nSold: {settings.TP1_SELL_PERCENT}%")

                elif sell_count >= 1 and current_price >= (pos.entry_price * (1 + settings.TAKE_PROFIT_PERCENT_2 / 100.0)):
                    result = await executor.sell(pos.token_mint, settings.TP2_SELL_PERCENT, pos.token_amount)
                    if result.success:
                        pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
                        db.add(
                            Trade(
                                position_id=pos.id,
                                side="sell",
                                token_mint=pos.token_mint,
                                price=current_price,
                                amount_inr=pos.amount_inr * (settings.TP2_SELL_PERCENT / 100.0),
                                tx_hash=result.tx_hash,
                                executor=executor.name,
                                status="tp2",
                            )
                        )
                        record_audit_event(
                            db,
                            event_type="sell_tp2",
                            side="sell",
                            token_mint=pos.token_mint,
                            message="TP2 target reached",
                            details={"current_price": current_price, "tx_hash": result.tx_hash, "pnl_pct": pnl_pct},
                        )
                        logger.info(f"TP2 hit token={pos.token_mint}; sold {settings.TP2_SELL_PERCENT}%")
                        await notifier.send(f"TP2 hit\nToken: {pos.token_mint}\nSold: {settings.TP2_SELL_PERCENT}%")

            db.commit()

        await asyncio.sleep(settings.POSITION_POLL_SECONDS)


async def main() -> None:
    setup_logger()
    validate_live_trade_startup()
    init_db()
    seed_wallets()
    record_startup_recovery_state()

    executor = get_executor()
    strategy = StrategyEngine()
    token_data_service = TokenDataService()
    notifier = TelegramNotifier()
    qualifier = WalletQualifier()

    logger.info(
        f"Bot started execution_mode={settings.EXECUTION_MODE} paper_trading={settings.PAPER_TRADING} "
        f"live_enabled={settings.LIVE_TRADING_ENABLED} executor={executor.name}"
    )

    await asyncio.gather(
        wallet_loop(executor, strategy, token_data_service, notifier, qualifier),
        position_loop(executor, strategy, notifier, token_data_service),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--mode", choices=["paper", "forward", "live"], default=None)
    args = parser.parse_args()
    if args.mode == "forward":
        profile = apply_forward_testing_profile(settings)
        logger.info(
            "Forward testing mode enabled: paper execution, live transactions disabled "
            f"profile={profile}"
        )
    elif args.mode == "live":
        settings.EXECUTION_MODE = "jupiter_live"
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as exc:
        logger.exception(f"Fatal error: {exc}")
