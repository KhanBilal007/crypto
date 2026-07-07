from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("EXECUTION_MODE", "paper")
os.environ.setdefault("LIVE_TRADING_ENABLED", "false")
os.environ.setdefault("MANUAL_APPROVAL_REQUIRED", "true")
os.environ.setdefault("EMERGENCY_STOP", "false")
os.environ.setdefault("PRIVATE_KEY", "")

import main  # noqa: E402
from src.database import Base  # noqa: E402
from src.execution.base import ExecutionResult  # noqa: E402
from src.models import PendingTrade, Position, Token, Trade, TradeAuditLog  # noqa: E402
from src.system_controls import approve_intent, clear_sell_all_request, load_state, request_sell_all, set_emergency_stop  # noqa: E402
from src.trade_safety import build_trade_intent, evaluate_buy_gate, store_pending_trade  # noqa: E402


@dataclass
class FakeNotifier:
    messages: list[str]

    async def send(self, message: str) -> None:
        self.messages.append(message)


class FakePriceMonitor:
    def __init__(self, price: float = 1.0) -> None:
        self.price = price

    async def get_price(self, token_mint: str, fallback: float) -> float:
        return self.price


class FakeSellExecutor:
    name = "fake-sell"

    def __init__(self, results: list[ExecutionResult]) -> None:
        self.results = results
        self.calls = 0

    async def buy(self, token_mint: str, amount_sol: float) -> ExecutionResult:
        raise NotImplementedError

    async def sell(self, token_mint: str, sell_percent: float, token_amount: float) -> ExecutionResult:
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        return ExecutionResult(
            success=False,
            tx_hash="",
            price=0.0,
            token_amount=0.0,
            side="sell",
            executor=self.name,
            confirmed=False,
            confirmation_status="failed",
            message="no result configured",
        )


class RestartAndConfirmationSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.addCleanup(self.engine.dispose)

        main.SessionLocal = self.Session

        import src.system_controls as system_controls
        import src.trade_safety as trade_safety

        control_state = Path(self.tmpdir.name) / "controls.json"
        system_controls.settings.CONTROL_STATE_PATH = control_state
        trade_safety.settings.CONTROL_STATE_PATH = control_state
        set_emergency_stop(False)
        clear_sell_all_request()

    def _safe_token(self, token_mint: str = "TOK") -> Token:
        return Token(
            token_mint=token_mint,
            liquidity_usd=30000,
            token_age_minutes=90,
            holder_count=700,
            top_holder_percent=8,
            top_10_holder_percent=20,
            mint_revoked=True,
            freeze_revoked=True,
        )

    def test_restart_state_persists_emergency_and_sellall(self) -> None:
        set_emergency_stop(True)
        request_sell_all()
        state = load_state()
        self.assertTrue(state.emergency_stop)
        self.assertTrue(state.sell_all_requested)

    def test_restart_does_not_auto_execute_old_approval(self) -> None:
        with self.Session() as db:
            token = self._safe_token()
            db.add(token)
            db.commit()
            intent = build_trade_intent(
                side="buy",
                token_mint=token.token_mint,
                amount_inr=300,
                amount_sol=0.025,
                reason="restart",
                wallet_score=90,
                risk_score=90,
            )
            pending = store_pending_trade(db, intent)
            db.commit()
            pending.status = "approved"
            db.commit()
        approve_intent(intent.intent_id)

        self.assertIn(intent.intent_id, load_state().approved_intents or [])
        # Approval still requires process_pending_trades and revalidation; nothing executes automatically on reload.
        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent.intent_id).one()
            self.assertEqual(item.status, "approved")

    def test_unknown_and_expired_buy_confirmation_pause_new_buys_and_are_audited(self) -> None:
        for confirmation_status in ["unknown", "expired"]:
            with self.subTest(status=confirmation_status):
                with self.Session() as db:
                    token_mint = f"TOK_BUY_{confirmation_status}"
                    db.add(self._safe_token(token_mint=token_mint))
                    db.commit()
                    intent = build_trade_intent(
                        side="buy",
                        token_mint=token_mint,
                        amount_inr=300,
                        amount_sol=0.025,
                        wallet_score=90,
                        risk_score=90,
                        confirming_wallets=["W1", "W2"],
                    )
                    pending = store_pending_trade(db, intent)
                    db.commit()
                    pending.status = "approved"
                    db.commit()

                result = ExecutionResult(
                    success=False,
                    tx_hash="buytx",
                    price=1.0,
                    token_amount=1.0,
                    side="buy",
                    executor="fake",
                    confirmed=False,
                    confirmation_status=confirmation_status,
                    message=f"{confirmation_status} buy",
                )
                notifier = FakeNotifier([])
                executor = type(
                    "E",
                    (),
                    {"name": "fake", "buy": lambda self, token_mint, amount_sol: asyncio.sleep(0, result), "sell": None},
                )()

                async def run() -> None:
                    await main.process_pending_trades(
                        executor,
                        main.StrategyEngine(),
                        notifier,
                        type(
                            "S",
                            (),
                            {
                                "fetch_token_snapshot": lambda self, token_mint: asyncio.sleep(
                                    0,
                                    {
                                        "liquidity_usd": 30000,
                                        "token_age_minutes": 90,
                                        "holder_count": 700,
                                        "top_holder_percent": 8,
                                        "top_10_holder_percent": 20,
                                        "mint_revoked": True,
                                        "freeze_revoked": True,
                                    },
                                )
                            },
                        )(),
                        {},
                        {},
                    )

                asyncio.run(run())

                self.assertTrue(load_state().emergency_stop)
                with self.Session() as db:
                    self.assertTrue(
                        db.query(TradeAuditLog).filter(TradeAuditLog.event_type == "buy_unknown_confirmation").count()
                    )
                    item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent.intent_id).one()
                    self.assertEqual(item.status, "failed")
                set_emergency_stop(False)
                clear_sell_all_request()

    def test_unknown_and_expired_sell_confirmation_keeps_position_open(self) -> None:
        for confirmation_status in ["unknown", "expired"]:
            with self.subTest(status=confirmation_status):
                with self.Session() as db:
                    pos = Position(
                        token_mint=f"TOK_SELL_{confirmation_status}",
                        entry_price=1.0,
                        amount_inr=300.0,
                        amount_sol=0.025,
                        token_amount=10.0,
                        stop_loss_price=0.9,
                        take_profit_price=1.2,
                        status="open",
                        buy_tx_hash="buy",
                    )
                    db.add(pos)
                    db.commit()
                    db.refresh(pos)

                    executor = FakeSellExecutor(
                        [
                            ExecutionResult(
                                success=False,
                                tx_hash="selltx",
                                price=0.0,
                                token_amount=0.0,
                                side="sell",
                                executor="fake",
                                confirmed=False,
                                confirmation_status=confirmation_status,
                                message=f"{confirmation_status} sell",
                            )
                        ]
                    )
                    notifier = FakeNotifier([])

                    asyncio.run(
                        main._sell_open_position(
                            db,
                            pos=pos,
                            executor=executor,
                            strategy=main.StrategyEngine(),
                            notifier=notifier,
                            status="filled",
                            current_price=0.8,
                            amount_percent=100.0,
                        )
                    )
                    db.commit()
                    item = db.query(Position).filter(Position.id == pos.id).one()
                    self.assertEqual(item.status, "open")
                    self.assertTrue(load_state().emergency_stop)
                    self.assertTrue(
                        db.query(TradeAuditLog).filter(TradeAuditLog.event_type == "sell_unknown_confirmation").count()
                    )
                set_emergency_stop(False)

    def test_failed_sell_retry_is_audited_and_exhausted(self) -> None:
        with self.Session() as db:
            pos = Position(
                token_mint="TOK_RETRY",
                entry_price=1.0,
                amount_inr=300.0,
                amount_sol=0.025,
                token_amount=10.0,
                stop_loss_price=0.9,
                take_profit_price=1.2,
                status="open",
                buy_tx_hash="buy",
            )
            db.add(pos)
            db.commit()
            db.refresh(pos)

            executor = FakeSellExecutor(
                [
                    ExecutionResult(
                        success=False,
                        tx_hash="selltx",
                        price=0.0,
                        token_amount=0.0,
                        side="sell",
                        executor="fake",
                        confirmed=False,
                        confirmation_status="failed",
                        retries=2,
                        message="failed sell",
                    )
                ]
            )
            notifier = FakeNotifier([])

            asyncio.run(
                main._sell_open_position(
                    db,
                    pos=pos,
                    executor=executor,
                    strategy=main.StrategyEngine(),
                    notifier=notifier,
                    status="filled",
                    current_price=0.8,
                    amount_percent=100.0,
                )
            )
            db.commit()
            item = db.query(Position).filter(Position.id == pos.id).one()
            self.assertEqual(item.status, "open")
            self.assertTrue(
                db.query(TradeAuditLog).filter(TradeAuditLog.event_type == "sell_retry").count()
            )
            self.assertTrue(
                db.query(TradeAuditLog).filter(TradeAuditLog.event_type == "sell_failed").count()
            )

    def test_sell_all_success_clears_flag_and_partial_failure_keeps_flag(self) -> None:
        with self.Session() as db:
            for mint in ["A", "B"]:
                db.add(
                    Position(
                        token_mint=mint,
                        entry_price=1.0,
                        amount_inr=300.0,
                        amount_sol=0.025,
                        token_amount=10.0,
                        stop_loss_price=0.9,
                        take_profit_price=1.2,
                        status="open",
                        buy_tx_hash=f"buy-{mint}",
                    )
                )
            db.commit()

        request_sell_all()
        success_executor = FakeSellExecutor(
            [
                ExecutionResult(True, "tx1", 1.0, 10.0, side="sell", executor="fake", confirmed=True, confirmation_status="confirmed"),
                ExecutionResult(True, "tx2", 1.0, 10.0, side="sell", executor="fake", confirmed=True, confirmation_status="confirmed"),
            ]
        )
        notifier = FakeNotifier([])
        asyncio.run(main.process_sell_all_request(self.Session(), executor=success_executor, strategy=main.StrategyEngine(), notifier=notifier, price_monitor=FakePriceMonitor()))
        self.assertFalse(load_state().sell_all_requested)

        with self.Session() as db:
            db.query(Position).delete()
            db.add(
                Position(
                    token_mint="C",
                    entry_price=1.0,
                    amount_inr=300.0,
                    amount_sol=0.025,
                    token_amount=10.0,
                    stop_loss_price=0.9,
                    take_profit_price=1.2,
                    status="open",
                    buy_tx_hash="buy-C",
                )
            )
            db.commit()

        request_sell_all()
        fail_executor = FakeSellExecutor(
            [
                ExecutionResult(False, "txfail", 0.0, 0.0, side="sell", executor="fake", confirmed=False, confirmation_status="failed", message="boom")
            ]
        )
        notifier = FakeNotifier([])
        asyncio.run(main.process_sell_all_request(self.Session(), executor=fail_executor, strategy=main.StrategyEngine(), notifier=notifier, price_monitor=FakePriceMonitor()))
        state = load_state()
        self.assertTrue(state.emergency_stop)
        self.assertTrue(state.sell_all_requested)


if __name__ == "__main__":
    unittest.main()
