from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.learning import (
    TradeImprovementSuggestion,
    TradeImprovementType,
    TradeIntelligenceReport,
    TradeLearningRecord,
    TradeMistakeType,
    build_trade_intelligence_report,
)

NOW = datetime(2026, 1, 20, tzinfo=UTC)


def test_trade_intelligence_report_summarizes_best_evidence_and_mistakes() -> None:
    report = build_trade_intelligence_report(
        _records(),
        generated_at=NOW,
        source_refs={"paper_trades": "fixture:stage062"},
    )

    assert report.advisory_only is True
    assert report.quality.is_trusted
    assert report.learning_analysis.outcomes.record_count == 5
    assert report.holding_time.longest_losing_trade_id == "slow-loss"
    assert report.best_regimes[0].group_value == "trend_up"
    assert report.best_strategies[0].group_value == "breakout"
    assert report.best_indicators[0].feature_name == "indicator.macd"
    assert report.ai_accuracy.evaluated_count == 5
    assert report.ai_accuracy.correct_count == 4
    assert report.ai_accuracy.accuracy == Decimal("0.8")
    assert {item.mistake_type for item in report.common_mistakes} == {
        TradeMistakeType.FEE_DRAG,
        TradeMistakeType.HIGH_CONFIDENCE_LOSS,
        TradeMistakeType.LONG_HOLDING_LOSS,
        TradeMistakeType.LOW_CONFIDENCE_WIN,
        TradeMistakeType.WEAK_REGIME_FIT,
    }
    assert any(
        item.suggestion_type is TradeImprovementType.REGIME_FILTER_REVIEW
        for item in report.improvement_suggestions
    )
    assert report.audit_payload()["best_strategy"] == "breakout"


def test_trade_intelligence_suggestions_cannot_auto_apply() -> None:
    try:
        TradeImprovementSuggestion(
            suggestion_type=TradeImprovementType.STRATEGY_REVIEW,
            target="breakout",
            rationale="fixture unsafe suggestion",
            evidence_refs=("strategy:breakout",),
            allowed_to_auto_apply=True,
        )
    except ValueError as exc:
        assert "cannot auto-apply" in str(exc)
    else:
        raise AssertionError("auto-apply suggestion should be rejected")


def test_trade_intelligence_blocks_order_and_risk_authority() -> None:
    report = build_trade_intelligence_report(_records(), generated_at=NOW)

    for method_name in ("create_order_intent", "approve_risk", "submit_order"):
        try:
            getattr(report, method_name)()
        except RuntimeError as exc:
            assert "trade intelligence cannot" in str(exc)
        else:
            raise AssertionError(f"{method_name} should be blocked")


def test_trade_intelligence_degrades_when_sample_is_too_small() -> None:
    report = build_trade_intelligence_report(
        (_record("only", pnl=Decimal("1"), return_pct=Decimal("0.01")),),
        generated_at=NOW,
        min_sample_size=3,
    )

    assert report.quality.is_degraded
    assert "insufficient_completed_trades" in report.quality.flags
    assert report.improvement_suggestions == ()


def test_trade_intelligence_excludes_rejected_records() -> None:
    rejected = _record(
        "rejected-win",
        pnl=Decimal("100"),
        return_pct=Decimal("1"),
        quality=DataQualityStatus(
            trust_level=DataTrustLevel.REJECTED,
            issues=(
                DataQualityIssue(
                    flag="bad_trade_fixture",
                    severity=DataTrustLevel.REJECTED,
                    reason="fixture rejected record",
                ),
            ),
            source_ref="fixture:rejected",
            checked_at=NOW,
        ),
    )

    report = build_trade_intelligence_report((*_records(), rejected), generated_at=NOW)

    assert report.quality.is_degraded
    assert report.learning_analysis.outcomes.record_count == 5
    assert "rejected_trade_records_excluded" in report.quality.flags
    assert report.improvement_suggestions == ()


def test_trade_intelligence_public_imports() -> None:
    assert TradeIntelligenceReport.__name__ == "TradeIntelligenceReport"
    assert TradeMistakeType.HIGH_CONFIDENCE_LOSS.value == "high_confidence_loss"


def _records() -> tuple[TradeLearningRecord, ...]:
    return (
        _record(
            "trend-win-1",
            strategy="breakout",
            regime="trend_up",
            pnl=Decimal("12"),
            return_pct=Decimal("0.06"),
            confidence=Decimal("0.78"),
            prediction_confidence=Decimal("0.75"),
            features={"indicator.macd": Decimal("2"), "indicator.rsi": Decimal("62")},
            hours=1,
        ),
        _record(
            "trend-win-2",
            strategy="breakout",
            regime="trend_up",
            pnl=Decimal("10"),
            return_pct=Decimal("0.05"),
            confidence=Decimal("0.66"),
            prediction_confidence=Decimal("0.64"),
            features={"indicator.macd": Decimal("1.5"), "indicator.rsi": Decimal("58")},
            hours=2,
        ),
        _record(
            "range-win",
            strategy="mean-reversion",
            regime="range_bound",
            pnl=Decimal("4"),
            return_pct=Decimal("0.02"),
            confidence=Decimal("0.35"),
            prediction_confidence=Decimal("0.55"),
            features={"indicator.macd": Decimal("-0.5"), "indicator.rsi": Decimal("35")},
            fees=Decimal("4"),
            hours=1,
        ),
        _record(
            "slow-loss",
            strategy="mean-reversion",
            regime="range_bound",
            pnl=Decimal("-9"),
            return_pct=Decimal("-0.045"),
            confidence=Decimal("0.76"),
            prediction_confidence=Decimal("0.50"),
            features={"indicator.macd": Decimal("-1"), "indicator.rsi": Decimal("42")},
            hours=8,
        ),
        _record(
            "trend-breakeven",
            strategy="breakout",
            regime="trend_up",
            pnl=Decimal("0"),
            return_pct=Decimal("0"),
            confidence=Decimal("0.50"),
            prediction_confidence=Decimal("0.45"),
            features={"indicator.macd": Decimal("0.2"), "indicator.rsi": Decimal("51")},
            hours=1,
        ),
    )


def _record(
    trade_id: str,
    *,
    pnl: Decimal,
    return_pct: Decimal,
    confidence: Decimal = Decimal("0.60"),
    prediction_confidence: Decimal | None = Decimal("0.60"),
    strategy: str = "fixture-strategy",
    regime: str = "trend_up",
    features: dict[str, Decimal] | None = None,
    fees: Decimal = Decimal("0.10"),
    hours: int = 1,
    quality: DataQualityStatus | None = None,
) -> TradeLearningRecord:
    index = sum(ord(ch) for ch in trade_id) % 24
    opened_at = NOW + timedelta(hours=index)
    return TradeLearningRecord(
        trade_id=trade_id,
        strategy_name=strategy,
        regime_label=regime,
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=hours),
        realized_pnl=pnl,
        return_pct=return_pct,
        fees_paid=fees,
        signal_confidence=confidence,
        risk_decision_status="approved",
        prediction_confidence=prediction_confidence,
        features=features or {},
        source_refs={"trade": f"fixture:{trade_id}"},
        data_quality=quality,
    )
