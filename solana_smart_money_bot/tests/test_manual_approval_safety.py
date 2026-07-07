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
from config import Settings  # noqa: E402
from src.database import Base  # noqa: E402
from src.execution.base import ExecutionResult  # noqa: E402
from src.models import PendingTrade, Position, Token, Trade, TradeAuditLog  # noqa: E402
from src.system_controls import approve_intent, clear_sell_all_request, load_state, request_sell_all, set_emergency_stop  # noqa: E402
from src.trade_safety import build_trade_intent, store_pending_trade  # noqa: E402


@dataclass
class FakeNotifier:
    messages: list[str]

    async def send(self, message: str) -> None:
        self.messages.append(message)


class FakeTokenDataService:
    def __init__(self, snapshot: dict | None = None, exc: Exception | None = None) -> None:
        self.snapshot = snapshot or {
            "liquidity_usd": 30000,
            "token_age_minutes": 90,
            "holder_count": 700,
            "top_holder_percent": 8,
            "top_10_holder_percent": 20,
            "mint_revoked": True,
            "freeze_revoked": True,
        }
        self.exc = exc

    async def fetch_token_snapshot(self, token_mint: str) -> dict:
        if self.exc:
            raise self.exc
        return dict(self.snapshot)


class FakeExecutor:
    name = "fake"

    def __init__(self, buy_result: ExecutionResult | None = None) -> None:
        self.buy_result = buy_result or ExecutionResult(
            success=True,
            tx_hash="tx-buy",
            price=1.0,
            token_amount=1.0,
            side="buy",
            executor="fake",
            confirmed=True,
            confirmation_status="confirmed",
        )
        self.buy_calls = 0

    async def buy(self, token_mint: str, amount_sol: float) -> ExecutionResult:
        self.buy_calls += 1
        return self.buy_result

    async def sell(self, token_mint: str, sell_percent: float, token_amount: float) -> ExecutionResult:
        raise NotImplementedError


class ManualApprovalSafetyTests(unittest.TestCase):
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

    def _seed_pending(self, *, token_mint: str = "TOK", status: str = "approved", expires_at=None) -> str:
        with self.Session() as db:
            intent = build_trade_intent(
                side="buy",
                token_mint=token_mint,
                amount_inr=300,
                amount_sol=0.025,
                reason="manual approval",
                wallet_score=90,
                risk_score=90,
                confirming_wallets=["W1", "W2"],
            )
            pending = store_pending_trade(db, intent)
            db.commit()
            pending.status = status
            if expires_at is not None:
                pending.expires_at = expires_at
            db.commit()
            return intent.intent_id

    def _seed_safe_token(self, token_mint: str = "TOK") -> None:
        with self.Session() as db:
            db.add(
                Token(
                    token_mint=token_mint,
                    liquidity_usd=30000,
                    token_age_minutes=90,
                    holder_count=700,
                    top_holder_percent=8,
                    top_10_holder_percent=20,
                    mint_revoked=True,
                    freeze_revoked=True,
                )
            )
            db.commit()

    def _run_pending(self, executor: FakeExecutor, token_service: FakeTokenDataService, notifier: FakeNotifier) -> None:
        asyncio.run(
            main.process_pending_trades(
                executor,
                main.StrategyEngine(),
                notifier,
                token_service,
                {},
                {},
            )
        )

    def test_expired_approval_cannot_execute(self) -> None:
        self._seed_safe_token()
        intent_id = self._seed_pending(status="approved", expires_at=datetime.utcnow() - timedelta(minutes=1))
        executor = FakeExecutor()
        notifier = FakeNotifier([])

        self._run_pending(executor, FakeTokenDataService(), notifier)

        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
            self.assertEqual(item.status, "expired")
        self.assertEqual(executor.buy_calls, 0)

    def test_rejected_trade_cannot_execute(self) -> None:
        self._seed_safe_token()
        intent_id = self._seed_pending(status="rejected")
        executor = FakeExecutor()
        notifier = FakeNotifier([])

        self._run_pending(executor, FakeTokenDataService(), notifier)

        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
            self.assertEqual(item.status, "rejected")
        self.assertEqual(executor.buy_calls, 0)

    def test_duplicate_approval_executes_once(self) -> None:
        self._seed_safe_token()
        intent_id = self._seed_pending(status="approved")
        approve_intent(intent_id)
        executor = FakeExecutor()
        notifier = FakeNotifier([])

        self._run_pending(executor, FakeTokenDataService(), notifier)
        self._run_pending(executor, FakeTokenDataService(), notifier)

        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
            self.assertEqual(item.status, "executed")
        self.assertFalse(load_state().approved_intents)
        self.assertEqual(executor.buy_calls, 1)

    def test_approval_rechecks_live_gates_before_execution(self) -> None:
        cases = [
            ("emergency", lambda: set_emergency_stop(True), "rejected"),
            ("sellall", lambda: request_sell_all(), "rejected"),
        ]

        for label, state_fn, expected_status in cases:
            with self.subTest(label=label):
                token_mint = f"TOK_{label}"
                self._seed_safe_token(token_mint=token_mint)
                intent_id = self._seed_pending(token_mint=token_mint, status="approved")
                state_fn()
                executor = FakeExecutor()
                notifier = FakeNotifier([])

                self._run_pending(executor, FakeTokenDataService(), notifier)

                with self.Session() as db:
                    item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
                    self.assertEqual(item.status, expected_status)
                self.assertEqual(executor.buy_calls, 0)
                set_emergency_stop(False)
                if label == "sellall":
                    self.assertTrue(load_state().sell_all_requested)
                    clear_sell_all_request()
                else:
                    self.assertFalse(load_state().sell_all_requested)

    def test_approval_rechecks_open_positions_daily_loss_and_exposure(self) -> None:
        with self.Session() as db:
            db.add(
                Position(
                    token_mint="LOCKED",
                    entry_price=1.0,
                    amount_inr=4900.0,
                    amount_sol=0.1,
                    token_amount=1000.0,
                    stop_loss_price=0.9,
                    take_profit_price=1.2,
                    status="open",
                    buy_tx_hash="buy",
                )
            )
            db.add(
                Trade(
                    position_id=None,
                    side="sell",
                    token_mint="LOSS",
                    price=1.0,
                    amount_inr=0.0,
                    tx_hash="t",
                    executor="paper",
                    status="filled",
                )
            )
            db.commit()

        scenarios = [
            ("max_open", lambda db: None),
            ("loss_limit", lambda db: db.add(Position(
                token_mint="LOSSPOS",
                entry_price=1.0,
                amount_inr=100.0,
                amount_sol=0.1,
                token_amount=1.0,
                stop_loss_price=0.9,
                take_profit_price=1.2,
                status="closed",
                buy_tx_hash="b",
                closed_at=datetime.utcnow(),
                pnl_inr=-600.0,
                pnl_percent=-10.0,
            ))),
        ]

        for label, mutate in scenarios:
            with self.subTest(label=label):
                token_mint = f"TOK_{label}"
                self._seed_safe_token(token_mint=token_mint)
                intent_id = self._seed_pending(token_mint=token_mint, status="approved")
                with self.Session() as db:
                    mutate(db)
                    db.commit()
                executor = FakeExecutor()
                notifier = FakeNotifier([])
                self._run_pending(executor, FakeTokenDataService(), notifier)

                with self.Session() as db:
                    item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
                    self.assertIn(item.status, {"rejected", "failed"})
                self.assertEqual(executor.buy_calls, 0)

    def test_token_data_missing_fails_closed_and_is_audited(self) -> None:
        self._seed_safe_token()
        intent_id = self._seed_pending(status="approved")
        executor = FakeExecutor()
        notifier = FakeNotifier([])

        self._run_pending(executor, FakeTokenDataService(exc=RuntimeError("missing data")), notifier)

        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
            self.assertEqual(item.status, "failed")
            self.assertTrue(db.query(TradeAuditLog).filter(TradeAuditLog.intent_id == intent_id, TradeAuditLog.event_type == "approval_failed").count())
        self.assertTrue(load_state().emergency_stop)
        self.assertIn("APPROVAL FAILED", "\n".join(notifier.messages))


if __name__ == "__main__":
    unittest.main()
