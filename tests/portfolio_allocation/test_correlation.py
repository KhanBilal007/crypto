from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.portfolio import CorrelationSnapshot, estimate_correlation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_estimate_correlation_is_deterministic_for_aligned_returns() -> None:
    estimate = estimate_correlation(
        asset_a="btc",
        asset_b="eth",
        returns_a=(Decimal("0.01"), Decimal("0.02"), Decimal("-0.01")),
        returns_b=(Decimal("0.02"), Decimal("0.04"), Decimal("-0.02")),
    )

    assert estimate.asset_a == "BTC"
    assert estimate.asset_b == "ETH"
    assert estimate.correlation == Decimal("1")


def test_correlation_snapshot_lookup_and_max_abs() -> None:
    snapshot = CorrelationSnapshot(
        generated_at=NOW,
        estimates=(
            estimate_correlation(
                asset_a="BTC",
                asset_b="ETH",
                returns_a=(Decimal("0.01"), Decimal("0.02"), Decimal("-0.01")),
                returns_b=(Decimal("0.02"), Decimal("0.04"), Decimal("-0.02")),
            ),
            estimate_correlation(
                asset_a="BTC",
                asset_b="SOL",
                returns_a=(Decimal("0.01"), Decimal("0.00"), Decimal("-0.01")),
                returns_b=(Decimal("-0.01"), Decimal("0.00"), Decimal("0.01")),
            ),
        ),
    )

    assert snapshot.estimate_for("ETH", "BTC") is not None
    assert snapshot.max_abs_correlation_for("BTC") == Decimal("1")
