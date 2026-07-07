from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
import sys

from fastapi.testclient import TestClient
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

import dashboard  # noqa: E402
from src.database import Base  # noqa: E402
from src.models import PendingTrade  # noqa: E402
from src.wallet_activity_state import save_wallet_activity_snapshot  # noqa: E402
from src.system_controls import load_state  # noqa: E402
from src.trade_safety import build_trade_intent, store_pending_trade  # noqa: E402


class AdminRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        db_path = Path(self.tmpdir.name) / "admin.db"
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        state_path = Path(self.tmpdir.name) / "controls.json"
        dashboard.SessionLocal = self.Session
        import src.system_controls as system_controls
        import src.trade_safety as trade_safety

        system_controls.settings.CONTROL_STATE_PATH = state_path
        trade_safety.settings.CONTROL_STATE_PATH = state_path

        self.client = TestClient(dashboard.app)
        save_wallet_activity_snapshot(
            {
                "generated_at_utc": "2026-07-04T11:19:00Z",
                "source": "test",
                "total_active_wallets": 10,
                "total_recent_transactions": 500,
                "wallets_with_recent_transactions": 10,
                "wallets_with_zero_recent_transactions": 0,
                "parser_attempted": 500,
                "parser_succeeded": 32,
                "parser_failed": 468,
                "buy_like_transactions": 31,
                "buy_signals": 32,
                "api_errors": 0,
                "rate_limit_errors": 0,
                "forward_signals": 0,
                "zero_signals_cause": "insufficient_runtime_window",
                "wallets": [{"wallet": "abc", "short_wallet": "abc", "score": 63.75, "status": "active", "last_seen": "n/a", "recent_txs": 50, "parser_hits": 1, "buy_like": 0}],
            }
        )

    def _seed_pending(self) -> str:
        with self.Session() as db:
            intent = build_trade_intent(
                side="buy",
                token_mint="ADMINTOK",
                amount_inr=300,
                amount_sol=0.025,
                reason="route test",
                wallet_score=90,
                risk_score=95,
                confirming_wallets=["W1"],
            )
            store_pending_trade(db, intent)
            db.commit()
            return intent.intent_id

    def test_admin_page_renders(self) -> None:
        resp = self.client.get("/admin")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Admin Control Center", resp.text)
        self.assertIn("Wallet Activity / Zero-Signal Diagnosis", resp.text)
        self.assertIn("Paper Capital", resp.text)
        self.assertIn("₹100000", resp.text)

    def test_wallet_activity_api_renders(self) -> None:
        resp = self.client.get("/api/wallet-activity")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["zero_signals_cause"], "insufficient_runtime_window")

    def test_approve_reject_and_controls(self) -> None:
        intent_id = self._seed_pending()

        resp = self.client.get(f"/admin/approve/{intent_id}", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
            self.assertEqual(item.status, "approved")

        state = load_state()
        self.assertIn(intent_id, state.approved_intents)

        resp = self.client.get(f"/admin/reject/{intent_id}", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        with self.Session() as db:
            item = db.query(PendingTrade).filter(PendingTrade.intent_id == intent_id).one()
            self.assertEqual(item.status, "rejected")

        resp = self.client.get("/admin/emergency/on", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(load_state().emergency_stop)

        resp = self.client.get("/admin/emergency/off", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertFalse(load_state().emergency_stop)

        resp = self.client.get("/admin/sellall", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(load_state().sell_all_requested)

        resp = self.client.get("/admin/sellall/clear", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertFalse(load_state().sell_all_requested)


if __name__ == "__main__":
    unittest.main()
