from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

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

from src.database import Base  # noqa: E402
import src.historical_cache as historical_cache  # noqa: E402
from src.token_data import TokenDataService  # noqa: E402


class _FakeHTTP:
    async def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        if "birdeye.so/defi/v3/ohlcv" in url:
            return {
                "data": {
                    "items": [
                        {"unixTime": 1, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05, "v": 100},
                        {"unixTime": 2, "o": 1.05, "h": 1.2, "l": 1.0, "c": 1.15, "v": 120},
                    ]
                }
            }
        if "dexscreener" in url:
            return {
                "pairs": [
                    {
                        "liquidity": {"usd": 1200},
                        "priceUsd": "0.01",
                        "pairCreatedAt": 1710000000000,
                    }
                ]
            }
        if "geckoterminal" in url:
            return {
                "data": [
                    {
                        "attributes": {
                            "reserve_in_usd": "3500",
                            "base_token_price_usd": "0.0125",
                            "pool_created_at": "2026-07-01T00:00:00Z",
                        }
                    }
                ]
            }
        return {}


class TokenDataSourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        historical_cache.SessionLocal = self.Session
        self.addCleanup(engine.dispose)

    def test_multi_source_merge_prefers_best_liquidity(self) -> None:
        async def run() -> None:
            service = TokenDataService()
            service.http = _FakeHTTP()
            async def fake_chain_controls(token_mint: str):
                return {
                    "holder_count": 500,
                    "top_holder_percent": 8.0,
                    "top_10_holder_percent": 18.0,
                    "mint_revoked": True,
                    "freeze_revoked": True,
                }

            service._fetch_chain_controls = fake_chain_controls  # type: ignore[assignment]
            snapshot = await service.fetch_token_snapshot("Mint111111111111111111111111111111111111111")
            self.assertEqual(snapshot["liquidity_usd"], 3500.0)
            self.assertEqual(snapshot["price_usd"], 0.01)
            self.assertIn("dexscreener", snapshot["market_sources"])
            self.assertIn("geckoterminal", snapshot["market_sources"])

        asyncio.run(run())

    def test_ohlcv_candles_prefers_birdeye_and_normalizes_rows(self) -> None:
        async def run() -> None:
            service = TokenDataService()
            service.http = _FakeHTTP()
            candles = await service.fetch_ohlcv_candles("Mint111111111111111111111111111111111111111", 0, 10, interval="1m")
            self.assertEqual(len(candles), 2)
            self.assertEqual(candles[-1].close, 1.15)
            self.assertEqual(candles[-1].volume, 120.0)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
