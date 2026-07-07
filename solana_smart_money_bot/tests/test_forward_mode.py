from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]

from src.forward_profile import apply_forward_testing_profile, FORWARD_TESTING_PROFILE  # noqa: E402
from config import Settings  # noqa: E402
from backtest_7d import Backtester  # noqa: E402


class ForwardModeTests(unittest.TestCase):
    def test_forward_profile_uses_softer_discovery_thresholds(self) -> None:
        cfg = SimpleNamespace(
            FORWARD_TESTING_MODE=False,
            EXECUTION_MODE="trojan",
            PAPER_TRADING=False,
            EXECUTOR="trojan",
        )

        profile = apply_forward_testing_profile(cfg)
        self.assertTrue(cfg.FORWARD_TESTING_MODE)
        self.assertEqual(cfg.EXECUTION_MODE, "paper")
        self.assertTrue(cfg.PAPER_TRADING)
        self.assertEqual(cfg.EXECUTOR, "paper")
        self.assertEqual(profile, FORWARD_TESTING_PROFILE)
        self.assertEqual(profile["MIN_WHALE_CONFIRMATIONS"], 1)
        self.assertEqual(profile["MIN_LIQUIDITY_USD"], 2000.0)
        self.assertEqual(profile["MIN_TOKEN_AGE_MINUTES"], 5.0)
        self.assertEqual(profile["MIN_TOKEN_RISK_SCORE"], 50.0)
        self.assertEqual(profile["MIN_COMBINED_WALLET_SCORE"], 55.0)

    def test_forward_mode_boots_in_paper_execution(self) -> None:
        env = os.environ.copy()
        env.setdefault("EXECUTION_MODE", "paper")
        env.setdefault("LIVE_TRADING_ENABLED", "false")
        env.setdefault("MANUAL_APPROVAL_REQUIRED", "true")
        env.setdefault("EMERGENCY_STOP", "false")
        env.setdefault("PRIVATE_KEY", "")

        with tempfile.NamedTemporaryFile(mode="w+") as out:
            proc = subprocess.Popen(
                [sys.executable, "main.py", "--mode", "forward"],
                cwd=ROOT,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                proc.wait(timeout=6)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)

            out.seek(0)
            data = out.read()
            self.assertIn("Forward testing mode enabled", data)
            self.assertIn("execution_mode=paper", data)
            self.assertIn("profile=", data)

    def test_readiness_script_outputs_required_flags(self) -> None:
        proc = subprocess.run(
            [sys.executable, "validate_live_readiness.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("PAPER_MODE_READY=", proc.stdout)
        self.assertIn("FORWARD_TESTING_READY=", proc.stdout)
        self.assertIn("LIVE_TRADING_READY=false", proc.stdout)
        self.assertIn("TINY_STAGING_TEST_READY=false", proc.stdout)

    def test_paper_default_capital_is_updated(self) -> None:
        cfg = Settings(EXECUTION_MODE="paper", LIVE_TRADING_ENABLED=False, PRIVATE_KEY="")
        self.assertEqual(cfg.STARTING_CAPITAL_INR, 100000.0)

    def test_backtest_profile_selector_supports_balanced_mode(self) -> None:
        old = os.environ.get("BT_SIMULATION_PROFILE")
        try:
            os.environ["BT_SIMULATION_PROFILE"] = "balanced"
            bt = Backtester()
            self.assertTrue(bt._balanced_mode())
            self.assertFalse(bt._aggressive_mode())
        finally:
            if old is None:
                os.environ.pop("BT_SIMULATION_PROFILE", None)
            else:
                os.environ["BT_SIMULATION_PROFILE"] = old

    def test_proxy_exit_flag_defaults_on_and_can_be_disabled(self) -> None:
        old = os.environ.get("BT_ALLOW_PROXY_EXIT")
        try:
            os.environ.pop("BT_ALLOW_PROXY_EXIT", None)
            self.assertTrue(Backtester._allow_proxy_exit())
            os.environ["BT_ALLOW_PROXY_EXIT"] = "false"
            self.assertFalse(Backtester._allow_proxy_exit())
        finally:
            if old is None:
                os.environ.pop("BT_ALLOW_PROXY_EXIT", None)
            else:
                os.environ["BT_ALLOW_PROXY_EXIT"] = old

    def test_trade_picker_defaults_to_first_and_supports_best_quality(self) -> None:
        old = os.environ.get("BT_TRADE_PICKER")
        try:
            os.environ.pop("BT_TRADE_PICKER", None)
            self.assertEqual(Backtester._trade_picker(), "first")
            os.environ["BT_TRADE_PICKER"] = "best_quality"
            self.assertEqual(Backtester._trade_picker(), "best_quality")
        finally:
            if old is None:
                os.environ.pop("BT_TRADE_PICKER", None)
            else:
                os.environ["BT_TRADE_PICKER"] = old

    def test_quality_floor_and_real_exit_flags_default_safely(self) -> None:
        old_floor = os.environ.get("BT_SIGNAL_QUALITY_FLOOR")
        old_real = os.environ.get("BT_REQUIRE_REAL_EXIT")
        try:
            os.environ.pop("BT_SIGNAL_QUALITY_FLOOR", None)
            os.environ.pop("BT_REQUIRE_REAL_EXIT", None)
            self.assertEqual(Backtester._signal_quality_floor(), 0.0)
            self.assertFalse(Backtester._require_real_exit())
            os.environ["BT_SIGNAL_QUALITY_FLOOR"] = "35"
            os.environ["BT_REQUIRE_REAL_EXIT"] = "true"
            self.assertEqual(Backtester._signal_quality_floor(), 35.0)
            self.assertTrue(Backtester._require_real_exit())
        finally:
            if old_floor is None:
                os.environ.pop("BT_SIGNAL_QUALITY_FLOOR", None)
            else:
                os.environ["BT_SIGNAL_QUALITY_FLOOR"] = old_floor
            if old_real is None:
                os.environ.pop("BT_REQUIRE_REAL_EXIT", None)
            else:
                os.environ["BT_REQUIRE_REAL_EXIT"] = old_real


if __name__ == "__main__":
    unittest.main()
