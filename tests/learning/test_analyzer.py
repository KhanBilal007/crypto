from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.learning import (
    OutcomeLabel,
    TradeLearningRecord,
    analyze_trade_outcomes,
    build_learning_analysis,
    feature_importance_observations,
    regime_performance,
    strategy_rankings,
    win_loss_patterns,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_trade_outcome_analysis_and_patterns_are_deterministic() -> None:
    records = _records()

    outcomes = analyze_trade_outcomes(records)
    patterns = win_loss_patterns(records)
    regimes = regime_performance(records)
    ranks = strategy_rankings(records)

    assert records[0].outcome is OutcomeLabel.WIN
    assert outcomes.record_count == 4
    assert outcomes.wins == 2
    assert outcomes.losses == 1
    assert outcomes.breakeven == 1
    assert outcomes.win_rate == Decimal("0.5")
    assert outcomes.total_pnl == Decimal("33")
    assert outcomes.max_loss == Decimal("-5")
    assert [pattern.group_value for pattern in patterns] == [
        "mean-reversion",
        "min-risk-spot-v1",
        "range_bound",
        "trend_up",
    ]
    assert regimes[0].group_value == "range_bound"
    assert ranks[0].strategy_name == "mean-reversion"


def test_feature_importance_uses_trade_outcomes_without_model_training() -> None:
    observations = feature_importance_observations(_records())

    by_name = {item.feature_name: item for item in observations}

    assert by_name["indicator.rsi"].sample_count == 4
    assert by_name["market.return_1"].directional_score > Decimal("0")
    assert "positive feature values" in by_name["market.return_1"].reason


def test_learning_analysis_excludes_rejected_records_and_blocks_recommendations() -> None:
    rejected = _record(
        "bad-data",
        pnl=Decimal("100"),
        return_pct=Decimal("0.50"),
        confidence=Decimal("0.90"),
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(
                DataQualityIssue(
                    flag="stale_trade_record",
                    severity=DataTrustLevel.REJECTED,
                    reason="fixture rejected record",
                ),
            ),
            source_ref="fixture:rejected",
            checked_at=NOW,
        ),
    )

    analysis = build_learning_analysis((*_records(), rejected), generated_at=NOW)

    assert analysis.quality.is_degraded
    assert analysis.outcomes.record_count == 4
    assert analysis.recommendations == ()
    assert "rejected_trade_records_excluded" in analysis.quality.flags


def _records() -> tuple[TradeLearningRecord, ...]:
    return (
        _record(
            "t1",
            strategy="min-risk-spot-v1",
            regime="trend_up",
            pnl=Decimal("20"),
            return_pct=Decimal("0.04"),
            confidence=Decimal("0.70"),
            features={"market.return_1": Decimal("0.02"), "indicator.rsi": Decimal("58")},
        ),
        _record(
            "t2",
            strategy="min-risk-spot-v1",
            regime="trend_up",
            pnl=Decimal("-5"),
            return_pct=Decimal("-0.01"),
            confidence=Decimal("0.80"),
            features={"market.return_1": Decimal("-0.01"), "indicator.rsi": Decimal("48")},
        ),
        _record(
            "t3",
            strategy="mean-reversion",
            regime="range_bound",
            pnl=Decimal("0"),
            return_pct=Decimal("0"),
            confidence=Decimal("0.40"),
            features={"market.return_1": Decimal("-0.02"), "indicator.rsi": Decimal("35")},
        ),
        _record(
            "t4",
            strategy="mean-reversion",
            regime="range_bound",
            pnl=Decimal("18"),
            return_pct=Decimal("0.03"),
            confidence=Decimal("0.45"),
            features={"market.return_1": Decimal("0.01"), "indicator.rsi": Decimal("42")},
        ),
    )


def _record(
    trade_id: str,
    *,
    pnl: Decimal,
    return_pct: Decimal,
    confidence: Decimal,
    strategy: str = "min-risk-spot-v1",
    regime: str = "trend_up",
    features: dict[str, Decimal] | None = None,
    quality: DataQualityStatus | None = None,
) -> TradeLearningRecord:
    index = int("".join(ch for ch in trade_id if ch.isdigit()) or "9")
    opened_at = NOW + timedelta(hours=index)
    return TradeLearningRecord(
        trade_id=trade_id,
        strategy_name=strategy,
        regime_label=regime,
        opened_at=opened_at,
        closed_at=opened_at + timedelta(minutes=30),
        realized_pnl=pnl,
        return_pct=return_pct,
        fees_paid=Decimal("0.10"),
        signal_confidence=confidence,
        risk_decision_status="approved",
        prediction_confidence=confidence,
        features=features or {},
        source_refs={"trade": f"fixture:{trade_id}"},
        data_quality=quality,
    )
