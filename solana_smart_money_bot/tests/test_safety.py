from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

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

from config import Settings  # noqa: E402
from src.database import Base  # noqa: E402
from src.models import PendingTrade, Token  # noqa: E402
from src.system_controls import (  # noqa: E402
    clear_sell_all_request,
    consume_approval,
    load_state,
    approve_intent,
    reject_intent,
    request_sell_all,
    set_emergency_stop,
)
from src.trade_safety import (  # noqa: E402
    build_trade_intent,
    evaluate_buy_gate,
    requires_manual_approval,
    validate_live_trade_startup,
    store_pending_trade,
)


class SafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.addCleanup(self.engine.dispose)

        import src.system_controls as system_controls
        import src.trade_safety as trade_safety

        control_state = Path(self.tmpdir.name) / "controls.json"
        system_controls.settings.CONTROL_STATE_PATH = control_state
        trade_safety.settings.CONTROL_STATE_PATH = control_state

    def _safe_token(self, **overrides) -> Token:
        base = dict(
            token_mint="TOK",
            liquidity_usd=30000,
            token_age_minutes=90,
            holder_count=700,
            top_holder_percent=8,
            top_10_holder_percent=20,
            mint_revoked=True,
            freeze_revoked=True,
        )
        base.update(overrides)
        return Token(**base)

    def test_live_mode_requires_live_flag(self) -> None:
        with self.assertRaises(ValueError):
            Settings(EXECUTION_MODE="jupiter_live", LIVE_TRADING_ENABLED=False, PRIVATE_KEY="1111111111111111111111111111111111111111111111111111111111111111")

    def test_live_mode_requires_private_key_and_blocks_emergency(self) -> None:
        with self.assertRaises(ValueError):
            Settings(EXECUTION_MODE="jupiter_live", LIVE_TRADING_ENABLED=True, PRIVATE_KEY="")

        with self.assertRaises(ValueError):
            Settings(EXECUTION_MODE="jupiter_live", LIVE_TRADING_ENABLED=True, EMERGENCY_STOP=True, PRIVATE_KEY="1111111111111111111111111111111111111111111111111111111111111111")

    def test_paper_mode_stays_paper_even_when_live_flag_is_true(self) -> None:
        cfg = Settings(EXECUTION_MODE="paper", LIVE_TRADING_ENABLED=True, PRIVATE_KEY="")
        self.assertTrue(cfg.PAPER_TRADING)
        self.assertEqual(cfg.EXECUTOR, "paper")

    def test_buy_gate_blocks_emergency_and_allows_safe_token(self) -> None:
        with self.Session() as db:
            safe = self._safe_token(token_mint="SAFE", top_10_holder_percent=35)
            db.add(safe)
            db.commit()
            db.refresh(safe)

            set_emergency_stop(True)
            blocked = evaluate_buy_gate(db, safe, trade_amount_inr=300, combined_wallet_score=80)
            self.assertFalse(blocked.allowed)
            self.assertIn("Emergency stop", blocked.reason)

            set_emergency_stop(False)
            allowed = evaluate_buy_gate(db, safe, trade_amount_inr=300, combined_wallet_score=80)
            self.assertTrue(allowed.allowed)

    def test_buy_gate_fail_closed_on_token_risk_inputs(self) -> None:
        with self.Session() as db:
            cases = [
                (self._safe_token(token_mint="LOW_LIQ", liquidity_usd=9999), "Liquidity"),
                (self._safe_token(token_mint="TOO_NEW", token_age_minutes=5), "Token too new"),
                (self._safe_token(token_mint="MINT_ON", mint_revoked=False), "Mint authority"),
                (self._safe_token(token_mint="FREEZE_ON", freeze_revoked=False), "Freeze authority"),
                (self._safe_token(token_mint="WHALEY", top_holder_percent=30), "Top holder"),
                (self._safe_token(token_mint="CONCENTRATED", top_10_holder_percent=71), "Top 10 holder"),
            ]

            for token, reason in cases:
                db.add(token)
                db.commit()
                db.refresh(token)
                blocked = evaluate_buy_gate(db, token, trade_amount_inr=300, combined_wallet_score=80)
                self.assertFalse(blocked.allowed, token.token_mint)
                self.assertIn(reason, blocked.reason)

    def test_pending_trade_and_controls_roundtrip(self) -> None:
        with self.Session() as db:
            token = Token(
                token_mint="TOK",
                liquidity_usd=30000,
                token_age_minutes=90,
                holder_count=700,
                top_holder_percent=8,
                top_10_holder_percent=20,
                mint_revoked=True,
                freeze_revoked=True,
            )
            db.add(token)
            db.commit()
            db.refresh(token)

            intent = build_trade_intent(
                side="buy",
                token_mint=token.token_mint,
                amount_inr=300,
                amount_sol=0.025,
                reason="manual approval",
                wallet_score=88,
                risk_score=91,
                confirming_wallets=["W1", "W2"],
            )
            pending = store_pending_trade(db, intent)
            db.commit()

            saved = db.query(PendingTrade).filter(PendingTrade.intent_id == intent.intent_id).one()
            self.assertEqual(saved.status, "pending")
            self.assertTrue(saved.payload_json)

            approve_intent(intent.intent_id)
            self.assertTrue(consume_approval(intent.intent_id))
            self.assertFalse(consume_approval(intent.intent_id))

            reject_intent("reject-me")
            state = load_state()
            self.assertIn("reject-me", state.rejected_intents)

            request_sell_all()
            state = load_state()
            self.assertTrue(state.sell_all_requested)
            clear_sell_all_request()
            state = load_state()
            self.assertFalse(state.sell_all_requested)

    def test_validate_live_startup_and_manual_approval_switches(self) -> None:
        with patch.object(validate_live_trade_startup.__globals__["settings"], "EXECUTION_MODE", "paper"), patch.object(validate_live_trade_startup.__globals__["settings"], "LIVE_TRADING_ENABLED", False), patch.object(validate_live_trade_startup.__globals__["settings"], "EMERGENCY_STOP", False), patch.object(validate_live_trade_startup.__globals__["settings"], "PRIVATE_KEY", ""):
            validate_live_trade_startup()

        with patch.object(validate_live_trade_startup.__globals__["settings"], "EXECUTION_MODE", "jupiter_live"), patch.object(validate_live_trade_startup.__globals__["settings"], "LIVE_TRADING_ENABLED", True), patch.object(validate_live_trade_startup.__globals__["settings"], "EMERGENCY_STOP", False), patch.object(validate_live_trade_startup.__globals__["settings"], "PRIVATE_KEY", "1111111111111111111111111111111111111111111111111111111111111111"), patch.object(validate_live_trade_startup.__globals__["settings"], "MANUAL_APPROVAL_REQUIRED", True):
            self.assertTrue(requires_manual_approval())

        with patch.object(validate_live_trade_startup.__globals__["settings"], "EXECUTION_MODE", "paper"), patch.object(validate_live_trade_startup.__globals__["settings"], "MANUAL_APPROVAL_REQUIRED", True):
            self.assertFalse(requires_manual_approval())


if __name__ == "__main__":
    unittest.main()
