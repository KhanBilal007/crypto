from __future__ import annotations

import unittest

from src.exit_rules import OhlcvCandle, evaluate_exit_rule, normalize_ohlcv_candles


class ExitRulesTests(unittest.TestCase):
    def _candles(self) -> list[OhlcvCandle]:
        rows = [
            {"unixTime": 1, "o": 1.0, "h": 1.05, "l": 0.98, "c": 1.00, "v": 100},
            {"unixTime": 2, "o": 1.0, "h": 1.10, "l": 0.99, "c": 1.08, "v": 120},
            {"unixTime": 3, "o": 1.08, "h": 1.15, "l": 1.05, "c": 1.12, "v": 110},
            {"unixTime": 4, "o": 1.12, "h": 1.13, "l": 1.00, "c": 1.01, "v": 30},
        ]
        return normalize_ohlcv_candles(rows)

    def test_take_profit_hits_first(self) -> None:
        candles = self._candles()
        decision = evaluate_exit_rule(
            candles,
            entry_price=1.0,
            stop_loss_price=0.9,
            take_profit_price=1.02,
            peak_price=1.15,
            trailing_stop_percent=10.0,
        )
        self.assertTrue(decision.should_exit)
        self.assertEqual(decision.reason, "take_profit")

    def test_stop_loss_hits_first(self) -> None:
        candles = [
            OhlcvCandle(1, 1.0, 1.05, 0.88, 0.90, 100),
            OhlcvCandle(2, 0.9, 0.92, 0.86, 0.87, 120),
        ]
        decision = evaluate_exit_rule(
            candles,
            entry_price=1.0,
            stop_loss_price=0.89,
            take_profit_price=1.2,
            peak_price=1.05,
            trailing_stop_percent=10.0,
        )
        self.assertTrue(decision.should_exit)
        self.assertEqual(decision.reason, "stop_loss")

    def test_trailing_stop_hits(self) -> None:
        candles = [
            OhlcvCandle(1, 1.0, 1.30, 0.99, 1.28, 100),
            OhlcvCandle(2, 1.28, 1.35, 1.10, 1.12, 40),
        ]
        decision = evaluate_exit_rule(
            candles,
            entry_price=1.0,
            stop_loss_price=0.9,
            take_profit_price=1.5,
            peak_price=1.35,
            trailing_stop_percent=10.0,
        )
        self.assertTrue(decision.should_exit)
        self.assertEqual(decision.reason, "trailing_stop")

    def test_volume_dying_and_trend_break_hits(self) -> None:
        candles = [
            OhlcvCandle(1, 1.0, 1.05, 0.99, 1.04, 150),
            OhlcvCandle(2, 1.04, 1.08, 1.01, 1.05, 140),
            OhlcvCandle(3, 1.05, 1.07, 1.00, 1.03, 130),
            OhlcvCandle(4, 1.03, 1.04, 0.99, 1.00, 120),
            OhlcvCandle(5, 1.00, 1.01, 0.96, 0.98, 35),
            OhlcvCandle(6, 0.98, 0.99, 0.94, 0.95, 20),
        ]
        decision = evaluate_exit_rule(
            candles,
            entry_price=1.0,
            stop_loss_price=0.85,
            take_profit_price=1.3,
            peak_price=1.08,
            trailing_stop_percent=10.0,
        )
        self.assertTrue(decision.should_exit)
        self.assertIn(decision.reason, {"trailing_stop", "volume_dying", "ema_vwap_break", "momentum_fade"})


if __name__ == "__main__":
    unittest.main()
