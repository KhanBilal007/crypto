from __future__ import annotations

import os
import tempfile
import unittest
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

from src.audit import record_audit_event  # noqa: E402
from src.database import Base  # noqa: E402
from src.models import TradeAuditLog  # noqa: E402


class AuditLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.addCleanup(self.engine.dispose)

    def test_sensitive_fields_are_redacted(self) -> None:
        with self.Session() as db:
            record_audit_event(
                db,
                event_type="secret_test",
                message="checking redaction",
                details={
                    "private_key": "abc",
                    "telegram_bot_token": "bot",
                    "nested": {"helius_api_key": "helius", "ok": 1},
                    "items": [{"seed_phrase": "one two three", "keep": "yes"}],
                },
            )
            db.commit()

            row = db.query(TradeAuditLog).one()
            self.assertIn("[REDACTED]", row.details_json)
            self.assertNotIn("abc", row.details_json)
            self.assertNotIn("one two three", row.details_json)


if __name__ == "__main__":
    unittest.main()
