from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import Base  # noqa: E402
import src.historical_cache as historical_cache  # noqa: E402


class HistoricalCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        historical_cache.SessionLocal = self.Session
        self.addCleanup(engine.dispose)

    def test_wallet_transaction_cache_roundtrip(self) -> None:
        txs = [
            {"signature": "sig1", "timestamp": "2026-07-01T00:00:00+00:00", "type": "SWAP"},
            {"signature": "sig2", "timestamp": "2026-07-02T00:00:00+00:00", "type": "SWAP"},
        ]
        saved = historical_cache.cache_wallet_transactions("wallet1", txs)
        self.assertEqual(saved, 2)

        loaded = historical_cache.load_wallet_transactions(["wallet1"], historical_cache._coerce_dt("2026-07-01T00:00:00+00:00"))
        self.assertEqual(len(loaded), 2)
        self.assertEqual({row["signature"] for row in loaded}, {"sig1", "sig2"})

    def test_price_point_cache_roundtrip(self) -> None:
        historical_cache.cache_price_point("mint1", "birdeye", 12345, 0.42, {"price": 0.42})
        self.assertEqual(historical_cache.load_price_point("mint1", 12345, source="birdeye"), 0.42)


if __name__ == "__main__":
    unittest.main()
