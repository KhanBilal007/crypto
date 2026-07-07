from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from config import settings
from src.models import Position, PositionWalletLink, Token, Wallet, WhaleSignal
from src.risk_engine import RiskEngine


class StrategyEngine:
    def __init__(self) -> None:
        self.risk_engine = RiskEngine()

    def calculate_wallet_score(self, wallet: Wallet) -> float:
        normalized_avg_roi = max(0.0, min(100.0, wallet.avg_roi + 50.0))
        successful_exit_rate = (wallet.successful_signals / wallet.total_signals * 100.0) if wallet.total_signals else 50.0
        low_rug_exposure_score = max(0.0, 100.0 - (wallet.bad_streak * 20.0))

        score = (
            wallet.win_rate * 0.35
            + normalized_avg_roi * 0.25
            + successful_exit_rate * 0.20
            + low_rug_exposure_score * 0.20
        )
        return max(0.0, min(100.0, score))

    def update_wallet_status(self, wallet: Wallet) -> None:
        if wallet.bad_streak >= 3:
            wallet.status = "disabled"
            wallet.disabled_until = datetime.utcnow() + timedelta(days=7)

    def recover_wallet_if_due(self, wallet: Wallet) -> None:
        if wallet.status == "disabled" and wallet.disabled_until and wallet.disabled_until <= datetime.utcnow():
            wallet.status = "active"
            wallet.disabled_until = None
            wallet.bad_streak = 0

    def get_whale_confirmations(self, db: Session, token_mint: str) -> tuple[int, float, list[str]]:
        window_start = datetime.utcnow() - timedelta(minutes=settings.CONFIRMATION_WINDOW_MINUTES)
        rows = (
            db.query(WhaleSignal.wallet_address)
            .filter(
                and_(
                    WhaleSignal.token_mint == token_mint,
                    WhaleSignal.action == "buy",
                    WhaleSignal.timestamp >= window_start,
                )
            )
            .distinct()
            .all()
        )
        wallets = [row[0] for row in rows]
        if not wallets:
            return 0, 0.0, []

        wallet_scores: list[float] = []
        for w in wallets:
            wallet_obj = db.query(Wallet).filter(Wallet.wallet_address == w).first()
            if wallet_obj:
                self.recover_wallet_if_due(wallet_obj)
                wallet_obj.score = self.calculate_wallet_score(wallet_obj)
                self.update_wallet_status(wallet_obj)
                wallet_scores.append(wallet_obj.score)

        avg_score = sum(wallet_scores) / len(wallet_scores) if wallet_scores else 0.0
        return len(wallets), avg_score, wallets

    def should_trade(self, db: Session, token: Token) -> tuple[bool, str, float, float, list[str]]:
        conf_count, combined_wallet_score, wallets = self.get_whale_confirmations(db, token.token_mint)

        if conf_count < settings.MIN_WHALE_CONFIRMATIONS:
            return False, "Not enough whale confirmations", 0.0, combined_wallet_score, wallets

        risk = self.risk_engine.score_token(token, conf_count)
        token.risk_score = risk.score

        if not risk.passed:
            return False, f"Risk fail: {', '.join(risk.reasons)}", risk.score, combined_wallet_score, wallets

        if combined_wallet_score < settings.MIN_COMBINED_WALLET_SCORE:
            return False, "Combined wallet score too low", risk.score, combined_wallet_score, wallets

        open_positions = db.query(func.count(Position.id)).filter(Position.status == "open").scalar() or 0
        if open_positions >= settings.MAX_OPEN_POSITIONS:
            return False, "Max open positions reached", risk.score, combined_wallet_score, wallets

        return True, "Approved", risk.score, combined_wallet_score, wallets

    def calculate_trade_size_inr(self, available_inr: float, combined_wallet_score: float) -> float:
        if combined_wallet_score < 80:
            target = settings.MIN_TRADE_INR
        elif combined_wallet_score < 90:
            target = max(settings.MAX_TRADE_INR, 500.0)
        else:
            target = settings.MAX_CONFIDENCE_TRADE_INR

        bounded = min(target, available_inr, settings.MAX_CONFIDENCE_TRADE_INR)
        if bounded < settings.MIN_TRADE_INR:
            return 0.0
        return bounded

    def daily_loss_hit(self, db: Session) -> bool:
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        closed_positions = db.query(Position).filter(Position.closed_at >= day_start, Position.status == "closed").all()
        total_pnl = sum(p.pnl_inr for p in closed_positions)
        return total_pnl <= -settings.DAILY_LOSS_LIMIT_INR

    def link_position_wallets(self, db: Session, position_id: int, wallet_addresses: list[str]) -> None:
        weight = 1.0 / len(wallet_addresses) if wallet_addresses else 0.0
        for wallet_address in wallet_addresses:
            db.add(PositionWalletLink(position_id=position_id, wallet_address=wallet_address, weight=weight))

    def apply_position_outcome_to_wallets(self, db: Session, position_id: int, pnl_percent: float) -> None:
        links = db.query(PositionWalletLink).filter(PositionWalletLink.position_id == position_id).all()

        winning = pnl_percent > 0
        for link in links:
            wallet = db.query(Wallet).filter(Wallet.wallet_address == link.wallet_address).first()
            if not wallet:
                continue

            wallet.total_signals += 1
            if winning:
                wallet.successful_signals += 1
                wallet.bad_streak = 0
            else:
                wallet.failed_signals += 1
                wallet.bad_streak += 1

            alpha = max(0.05, min(0.95, settings.OUTCOME_EMA_ALPHA))
            weighted_outcome = pnl_percent * max(0.1, link.weight)
            wallet.avg_roi = (alpha * weighted_outcome) + ((1 - alpha) * wallet.avg_roi)
            wallet.win_rate = (wallet.successful_signals / wallet.total_signals) * 100.0 if wallet.total_signals else 50.0
            wallet.score = self.calculate_wallet_score(wallet)
            self.update_wallet_status(wallet)

    def log_decision(self, token_mint: str, message: str, risk: float, wallet_score: float) -> None:
        logger.info(
            f"Decision token={token_mint} message='{message}' risk_score={risk:.2f} combined_wallet_score={wallet_score:.2f}"
        )
