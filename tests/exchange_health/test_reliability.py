from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from abtp.data import DataTrustLevel
from abtp.exchanges.reliability import (
    ReliabilityInput,
    ReliabilityPolicy,
    score_reliability,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_reliability_scores_healthy_latency_and_error_rate() -> None:
    score = score_reliability(
        ReliabilityInput(
            exchange_name="sandbox",
            observed_at=NOW,
            request_count=100,
            error_count=1,
            latency_ms_samples=(80, 100, 110, 120, 150),
            source_refs={"adapter": "fixture:sandbox"},
        )
    )

    assert score.score == Decimal("0.9940")
    assert score.error_rate == Decimal("0.0100")
    assert score.p95_latency_ms == 150
    assert score.quality.trust_level is DataTrustLevel.TRUSTED
    assert score.audit_payload()["outage"] == "False"


def test_reliability_degrades_high_latency_and_error_rate() -> None:
    score = score_reliability(
        ReliabilityInput(
            exchange_name="sandbox",
            observed_at=NOW,
            request_count=100,
            error_count=10,
            latency_ms_samples=(100, 760, 900, 1200, 1300),
        ),
        policy=ReliabilityPolicy(degraded_latency_ms=750, rejected_latency_ms=2000),
    )

    assert score.quality.is_degraded
    assert "p95 latency exceeds degraded threshold" in score.reasons
    assert "error rate exceeds degraded threshold" in score.reasons
    assert score.score < Decimal("0.90")


def test_reliability_rejects_outage_and_unsafe_error_rate() -> None:
    score = score_reliability(
        ReliabilityInput(
            exchange_name="sandbox",
            observed_at=NOW,
            request_count=10,
            error_count=4,
            latency_ms_samples=(100, 200, 250),
            outage=True,
        )
    )

    assert score.quality.is_rejected
    assert score.score == Decimal("0.0100")
    assert "exchange outage reported" in score.reasons
    assert "error rate exceeds rejected threshold" in score.reasons


def test_reliability_missing_request_sample_degrades() -> None:
    score = score_reliability(
        ReliabilityInput(
            exchange_name="sandbox",
            observed_at=NOW,
            request_count=0,
            error_count=0,
            latency_ms_samples=(),
        )
    )

    assert score.error_rate == Decimal("1")
    assert score.quality.is_rejected
    assert "insufficient request sample for reliability" in score.reasons
