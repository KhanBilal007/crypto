from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    MultiTimeframePolicy,
    Timeframe,
    TimeframeObservation,
    TrendBias,
    evaluate_multi_timeframe_intelligence,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_aligned_bullish_timeframes_emit_high_confidence_context() -> None:
    result = evaluate_multi_timeframe_intelligence(_observations(), generated_at=NOW)

    assert result.higher_timeframe_bias is TrendBias.BULL
    assert result.high_confidence_context
    assert result.trend_alignment_score == Decimal("0.8100")
    assert result.trend_strength == Decimal("0.8100")
    assert result.timeframe_agreement_pct == Decimal("1.0000")
    assert result.entry_timing_score == Decimal("0.8000")
    assert result.exit_timing_score == Decimal("0.7500")
    assert result.market_structure == "aligned_bull"
    assert result.quality.is_trusted
    assert result.audit_payload()["higher_timeframe_bias"] == "bull"


def test_monthly_weekly_bear_daily_bull_rejects_no_alignment() -> None:
    observations = (
        _observation(Timeframe.MONTHLY, TrendBias.BEAR),
        _observation(Timeframe.WEEKLY, TrendBias.BEAR),
        _observation(Timeframe.DAILY, TrendBias.BULL),
        _observation(Timeframe.FOUR_HOUR, TrendBias.BULL),
        _observation(Timeframe.ONE_HOUR, TrendBias.BULL),
    )

    result = evaluate_multi_timeframe_intelligence(observations, generated_at=NOW)

    assert result.higher_timeframe_bias is TrendBias.BEAR
    assert not result.high_confidence_context
    assert result.quality.is_rejected
    assert "monthly and weekly are bear while daily is bull" in result.rejection_reasons
    assert any(rule.startswith("block_entry") for rule in result.risk_rules)


def test_missing_required_timeframe_fails_closed() -> None:
    observations = tuple(
        item for item in _observations() if item.timeframe is not Timeframe.ONE_HOUR
    )

    result = evaluate_multi_timeframe_intelligence(observations, generated_at=NOW)

    assert not result.high_confidence_context
    assert result.quality.is_rejected
    assert "required timeframe 1h is missing" in result.rejection_reasons
    assert "multi_timeframe_missing_timeframe" in result.quality.flags


def test_stale_or_rejected_timeframe_quality_fails_closed() -> None:
    observations = (
        _observation(Timeframe.MONTHLY, TrendBias.BULL),
        _observation(Timeframe.WEEKLY, TrendBias.BULL, quality=_rejected_quality()),
        _observation(Timeframe.DAILY, TrendBias.BULL, stale=True),
        _observation(Timeframe.FOUR_HOUR, TrendBias.BULL),
        _observation(Timeframe.ONE_HOUR, TrendBias.BULL),
    )

    result = evaluate_multi_timeframe_intelligence(observations, generated_at=NOW)

    assert not result.high_confidence_context
    assert result.quality.is_rejected
    assert "timeframe weekly quality is rejected" in result.rejection_reasons
    assert "timeframe daily is stale" in result.rejection_reasons


def test_degraded_timeframe_quality_reduces_alignment_and_quality() -> None:
    observations = (
        _observation(Timeframe.MONTHLY, TrendBias.BULL),
        _observation(Timeframe.WEEKLY, TrendBias.BULL, quality=_degraded_quality()),
        _observation(Timeframe.DAILY, TrendBias.BULL),
        _observation(Timeframe.FOUR_HOUR, TrendBias.BULL),
        _observation(Timeframe.ONE_HOUR, TrendBias.BULL),
    )

    result = evaluate_multi_timeframe_intelligence(observations, generated_at=NOW)

    assert result.trend_alignment_score == Decimal("0.8100")
    assert result.quality.is_degraded
    assert not result.high_confidence_context
    assert "multi_timeframe_degraded_timeframe_quality" in result.quality.flags


def test_alignment_policy_can_raise_thresholds() -> None:
    result = evaluate_multi_timeframe_intelligence(
        _observations(trend_strength=Decimal("0.66")),
        generated_at=NOW,
        policy=MultiTimeframePolicy(min_alignment_score=Decimal("0.80")),
    )

    assert not result.high_confidence_context
    assert "trend alignment score is below threshold" in result.rejection_reasons


def test_duplicate_timeframe_observation_is_rejected() -> None:
    monthly = _observation(Timeframe.MONTHLY, TrendBias.BULL)

    with pytest.raises(ValueError, match="duplicate timeframe observation"):
        evaluate_multi_timeframe_intelligence((monthly, monthly), generated_at=NOW)


def test_multi_timeframe_result_has_no_signal_order_or_risk_authority() -> None:
    result = evaluate_multi_timeframe_intelligence(_observations(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        result.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        result.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        result.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        result.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import MultiTimeframeIntelligence, TimeframeEvidence

    assert MultiTimeframeIntelligence is not None
    assert TimeframeEvidence is not None


def _observations(
    *,
    trend_strength: Decimal = Decimal("0.81"),
) -> tuple[TimeframeObservation, ...]:
    return tuple(
        _observation(timeframe, TrendBias.BULL, trend_strength=trend_strength)
        for timeframe in Timeframe
    )


def _observation(
    timeframe: Timeframe,
    trend_bias: TrendBias,
    *,
    trend_strength: Decimal = Decimal("0.81"),
    quality: DataQualityStatus | None = None,
    stale: bool = False,
) -> TimeframeObservation:
    return TimeframeObservation(
        timeframe=timeframe,
        observed_at=NOW,
        trend_bias=trend_bias,
        trend_strength=trend_strength,
        momentum_score=Decimal("0.80"),
        volatility_score=Decimal("0.30"),
        volume_score=Decimal("0.80"),
        market_structure_score=Decimal("0.80"),
        support_resistance_score=Decimal("0.80"),
        liquidity_score=Decimal("0.80"),
        quality=quality or _trusted_quality(),
        source_ref=f"fixture:{timeframe.value}",
        stale=stale,
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="fixture_degraded",
                severity=DataTrustLevel.DEGRADED,
                reason="fixture degraded",
            ),
        ),
        source_ref="fixture:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="fixture_rejected",
                severity=DataTrustLevel.REJECTED,
                reason="fixture rejected",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
