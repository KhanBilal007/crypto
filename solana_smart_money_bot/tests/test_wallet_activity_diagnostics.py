from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
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
from src.models import Wallet  # noqa: E402
from src.signal_coverage import classify_transaction, infer_zero_signals_cause, summarize_wallet_transactions  # noqa: E402
from src.tx_parser import TxParser  # noqa: E402
from src.wallet_monitor import WalletMonitor  # noqa: E402
from src.wallet_validation import is_valid_solana_address  # noqa: E402


VALID_WALLET = "FkaLnX17cXZGyeu3kZGdHCNdFMJJzBrPPYVvd18B3MZp"
BUY_MINT = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"


def _buy_like_tx(wallet: str) -> dict:
    return {
        "signature": "buy_sig",
        "type": "SWAP",
        "source": "RAYDIUM",
        "transactionError": None,
        "nativeTransfers": [],
        "tokenTransfers": [],
        "accountData": [
            {
                "account": wallet,
                "nativeBalanceChange": -8481991126,
                "tokenBalanceChanges": [
                    {
                        "userAccount": wallet,
                        "rawTokenAmount": {"tokenAmount": "-8481991126", "decimals": 9},
                        "mint": "So11111111111111111111111111111111111111112",
                    }
                ],
            },
            {
                "account": "token_account",
                "nativeBalanceChange": 0,
                "tokenBalanceChanges": [
                    {
                        "userAccount": wallet,
                        "rawTokenAmount": {"tokenAmount": "430713237", "decimals": 8},
                        "mint": BUY_MINT,
                    }
                ],
            },
        ],
    }


def _sell_tx(wallet: str) -> dict:
    return {
        "signature": "sell_sig",
        "type": "SWAP",
        "source": "RAYDIUM",
        "transactionError": None,
        "nativeTransfers": [],
        "tokenTransfers": [],
        "accountData": [
            {
                "account": wallet,
                "nativeBalanceChange": 5000,
                "tokenBalanceChanges": [],
            },
            {
                "account": "token_account",
                "nativeBalanceChange": 0,
                "tokenBalanceChanges": [
                    {
                        "userAccount": wallet,
                        "rawTokenAmount": {"tokenAmount": "-430713237", "decimals": 8},
                        "mint": BUY_MINT,
                    }
                ],
            },
        ],
    }


def _transfer_tx(wallet: str) -> dict:
    return {
        "signature": "transfer_sig",
        "type": "TRANSFER",
        "source": "SYSTEM",
        "transactionError": None,
        "nativeTransfers": [],
        "tokenTransfers": [],
        "accountData": [],
    }


class WalletActivityDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)
        self.addCleanup(self.engine.dispose)
        main.SessionLocal = self.Session

    def test_invalid_wallet_addresses_are_rejected(self) -> None:
        self.assertTrue(is_valid_solana_address(VALID_WALLET))
        self.assertFalse(is_valid_solana_address("not-a-solana-address"))

    def test_seed_wallets_skips_invalid_wallets(self) -> None:
        original_whales = main.settings.WHALE_WALLETS
        original_candidates = main.settings.CANDIDATE_WALLETS
        try:
            main.settings.WHALE_WALLETS = "not-a-solana-address"
            main.settings.CANDIDATE_WALLETS = ""
            main.seed_wallets()
            with self.Session() as db:
                self.assertEqual(db.query(Wallet).count(), 0)
        finally:
            main.settings.WHALE_WALLETS = original_whales
            main.settings.CANDIDATE_WALLETS = original_candidates

    def test_parser_detects_account_data_buy_like_swap(self) -> None:
        parser = TxParser()
        signal = parser.parse_buy_signal(VALID_WALLET, _buy_like_tx(VALID_WALLET))
        self.assertIsNotNone(signal)
        self.assertEqual(signal.token_mint, BUY_MINT)

        classification = classify_transaction(VALID_WALLET, _buy_like_tx(VALID_WALLET), parser)
        self.assertEqual(classification.category, "parsed_buy_signal")

    def test_summarize_wallet_transactions_counts_reasons(self) -> None:
        parser = TxParser()
        summary = summarize_wallet_transactions(
            VALID_WALLET,
            [_buy_like_tx(VALID_WALLET), _sell_tx(VALID_WALLET), _transfer_tx(VALID_WALLET)],
            parser,
        )
        self.assertEqual(summary["buy_signals"], 1)
        self.assertGreaterEqual(summary["reason_counts"].get("ignored_sell", 0), 1)
        self.assertGreaterEqual(summary["reason_counts"].get("ignored_transfer_only", 0), 1)

    def test_zero_signal_cause_inference(self) -> None:
        self.assertEqual(
            infer_zero_signals_cause(
                {
                    "total_active_wallets": 10,
                    "total_recent_transactions": 500,
                    "parser_succeeded": 28,
                    "buy_like_transactions": 30,
                    "api_errors": 0,
                    "filter_rejections": 0,
                    "forward_signals": 0,
                }
            ),
            "insufficient_runtime_window",
        )
        self.assertEqual(
            infer_zero_signals_cause(
                {
                    "total_active_wallets": 10,
                    "total_recent_transactions": 500,
                    "parser_succeeded": 0,
                    "buy_like_transactions": 2,
                    "api_errors": 0,
                    "filter_rejections": 0,
                    "forward_signals": 0,
                }
            ),
            "parser_not_detecting_buys",
        )

    def test_wallet_monitor_logs_empty_and_failure(self) -> None:
        async def run_empty() -> None:
            monitor = WalletMonitor()
            monitor.http.get = AsyncMock(return_value=[])
            with patch("src.wallet_monitor.logger.info") as info_log:
                txs = await monitor._poll_wallet_via_http(VALID_WALLET)
                self.assertEqual(txs, [])
                info_log.assert_any_call(f"Helius returned no transactions wallet={VALID_WALLET}")

        async def run_error() -> None:
            monitor = WalletMonitor()
            async def _raise(*args, **kwargs):
                raise RuntimeError("boom")
            monitor.http.get = _raise
            with patch("src.wallet_monitor.logger.error") as error_log:
                txs = await monitor._poll_wallet_via_http(VALID_WALLET)
                self.assertEqual(txs, [])
                error_log.assert_any_call(f"Helius fetch failed wallet={VALID_WALLET} error=boom")

        asyncio.run(run_empty())
        asyncio.run(run_error())


if __name__ == "__main__":
    unittest.main()
