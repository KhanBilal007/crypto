from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.learning import TradeLearningRecord, calibrate_confidence

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_confidence_calibration_buckets_and_suggestions_are_advisory() -> None:
    report = calibrate_confidence(
        (
            _record("low-win", pnl=Decimal("4"), confidence=Decimal("0.20")),
            _record("high-loss", pnl=Decimal("-3"), confidence=Decimal("0.80")),
            _record("high-loss-2", pnl=Decimal("-1"), confidence=Decimal("0.75")),
        ),
        bucket_size=Decimal("0.25"),
        generated_at=NOW,
    )

    assert [bucket.label for bucket in report.buckets] == ["0-0.25", "0.75-1.00"]
    assert report.buckets[0].win_rate == Decimal("1")
    assert report.buckets[1].win_rate == Decimal("0")
    assert report.suggestions[0].allowed_to_auto_apply is False
    assert report.suggestions[0].requires_validation is True
    assert report.suggestions[0].adjustment == Decimal("0.10")
    assert report.suggestions[1].adjustment == Decimal("-0.10")


def test_confidence_calibration_validates_parameters() -> None:
    with pytest.raises(ValueError, match="bucket_size"):
        calibrate_confidence((), bucket_size=Decimal("0"))


def _record(trade_id: str, *, pnl: Decimal, confidence: Decimal) -> TradeLearningRecord:
    opened_at = NOW + timedelta(minutes=len(trade_id))
    return TradeLearningRecord(
        trade_id=trade_id,
        strategy_name="fixture-strategy",
        regime_label="trend_up",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=10),
        realized_pnl=pnl,
        return_pct=pnl / Decimal("100"),
        fees_paid=Decimal("0.01"),
        signal_confidence=confidence,
        risk_decision_status="approved",
    )
