"""Trade intelligence and learning engine for completed trades."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.learning.analyzer import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    FeatureImportanceObservation,
    LearningAnalysis,
    LearningRecommendation,
    OutcomeLabel,
    PatternSummary,
    TradeLearningRecord,
    build_learning_analysis,
)


class TradeMistakeType(StrEnum):
    """Explainable completed-trade mistake categories."""

    HIGH_CONFIDENCE_LOSS = "high_confidence_loss"
    LOW_CONFIDENCE_WIN = "low_confidence_win"
    FEE_DRAG = "fee_drag"
    LONG_HOLDING_LOSS = "long_holding_loss"
    WEAK_REGIME_FIT = "weak_regime_fit"


class TradeImprovementType(StrEnum):
    """Advisory improvement categories that require later validation."""

    CONFIDENCE_REVIEW = "confidence_review"
    STRATEGY_REVIEW = "strategy_review"
    REGIME_FILTER_REVIEW = "regime_filter_review"
    INDICATOR_REVIEW = "indicator_review"
    HOLDING_TIME_REVIEW = "holding_time_review"
    COST_REVIEW = "cost_review"


@dataclass(frozen=True, slots=True)
class HoldingTimeInsight:
    """Holding-time summary for completed trades."""

    sample_count: int
    average_seconds: Decimal
    winning_average_seconds: Decimal
    losing_average_seconds: Decimal
    longest_losing_trade_id: str | None
    reason: str

    def __post_init__(self) -> None:
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        if self.average_seconds < DECIMAL_ZERO:
            raise ValueError("average_seconds cannot be negative")
        if self.winning_average_seconds < DECIMAL_ZERO:
            raise ValueError("winning_average_seconds cannot be negative")
        if self.losing_average_seconds < DECIMAL_ZERO:
            raise ValueError("losing_average_seconds cannot be negative")
        if not self.reason.strip():
            raise ValueError("holding-time insight reason is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_count": self.sample_count,
            "average_seconds": str(self.average_seconds),
            "winning_average_seconds": str(self.winning_average_seconds),
            "losing_average_seconds": str(self.losing_average_seconds),
            "longest_losing_trade_id": self.longest_losing_trade_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class AIPredictionAccuracy:
    """Simple auditable AI-confidence accuracy summary."""

    evaluated_count: int
    correct_count: int
    accuracy: Decimal
    average_prediction_confidence: Decimal
    confidence_threshold: Decimal
    reason: str

    def __post_init__(self) -> None:
        if self.evaluated_count < 0:
            raise ValueError("evaluated_count cannot be negative")
        if self.correct_count < 0 or self.correct_count > self.evaluated_count:
            raise ValueError("correct_count must be within evaluated_count")
        if not DECIMAL_ZERO <= self.accuracy <= DECIMAL_ONE:
            raise ValueError("accuracy must be between 0 and 1")
        if not DECIMAL_ZERO <= self.average_prediction_confidence <= DECIMAL_ONE:
            raise ValueError("average_prediction_confidence must be between 0 and 1")
        if not DECIMAL_ZERO <= self.confidence_threshold <= DECIMAL_ONE:
            raise ValueError("confidence_threshold must be between 0 and 1")
        if not self.reason.strip():
            raise ValueError("AI accuracy reason is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluated_count": self.evaluated_count,
            "correct_count": self.correct_count,
            "accuracy": str(self.accuracy),
            "average_prediction_confidence": str(self.average_prediction_confidence),
            "confidence_threshold": str(self.confidence_threshold),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CommonTradeMistake:
    """One repeated behavior discovered in completed-trade records."""

    mistake_type: TradeMistakeType
    trade_ids: tuple[str, ...]
    severity: DataTrustLevel
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "mistake_type", TradeMistakeType(self.mistake_type))
        object.__setattr__(self, "severity", DataTrustLevel(self.severity))
        object.__setattr__(self, "trade_ids", tuple(sorted(self.trade_ids)))
        if not self.reason.strip():
            raise ValueError("mistake reason is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "mistake_type": self.mistake_type.value,
            "trade_ids": list(self.trade_ids),
            "severity": self.severity.value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TradeImprovementSuggestion:
    """Advisory improvement suggestion derived from completed trades."""

    suggestion_type: TradeImprovementType
    target: str
    rationale: str
    evidence_refs: tuple[str, ...]
    requires_validation: bool = True
    allowed_to_auto_apply: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "suggestion_type", TradeImprovementType(self.suggestion_type))
        if not self.target.strip():
            raise ValueError("suggestion target is required")
        if not self.rationale.strip():
            raise ValueError("suggestion rationale is required")
        if not self.evidence_refs:
            raise ValueError("suggestion evidence_refs are required")
        if not self.requires_validation:
            raise ValueError("trade intelligence suggestions require validation")
        if self.allowed_to_auto_apply:
            raise ValueError("trade intelligence suggestions cannot auto-apply")

    def as_dict(self) -> dict[str, object]:
        return {
            "suggestion_type": self.suggestion_type.value,
            "target": self.target,
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "requires_validation": self.requires_validation,
            "allowed_to_auto_apply": self.allowed_to_auto_apply,
        }


@dataclass(frozen=True, slots=True)
class TradeIntelligenceReport:
    """Stage 062 advisory trade intelligence output."""

    generated_at: datetime
    quality: DataQualityStatus
    learning_analysis: LearningAnalysis
    holding_time: HoldingTimeInsight
    best_regimes: tuple[PatternSummary, ...]
    best_strategies: tuple[PatternSummary, ...]
    best_indicators: tuple[FeatureImportanceObservation, ...]
    ai_accuracy: AIPredictionAccuracy
    common_mistakes: tuple[CommonTradeMistake, ...]
    improvement_suggestions: tuple[TradeImprovementSuggestion, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Trade intelligence is advisory research context only.",
        "Suggestions require deterministic paper/backtest validation before adoption.",
        "The engine cannot modify strategies, risk rules, allocations, or models.",
        "The engine cannot create signals, order intents, risk decisions, or execution.",
        "No profit is guaranteed by trade intelligence analysis.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))
        if not self.limitations:
            raise ValueError("trade intelligence limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    def create_order_intent(self) -> None:
        raise RuntimeError("trade intelligence cannot create order intents")

    def approve_risk(self) -> None:
        raise RuntimeError("trade intelligence cannot approve risk")

    def submit_order(self) -> None:
        raise RuntimeError("trade intelligence cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "learning_analysis": self.learning_analysis.as_dict(),
            "holding_time": self.holding_time.as_dict(),
            "best_regimes": [item.as_dict() for item in self.best_regimes],
            "best_strategies": [item.as_dict() for item in self.best_strategies],
            "best_indicators": [item.as_dict() for item in self.best_indicators],
            "ai_accuracy": self.ai_accuracy.as_dict(),
            "common_mistakes": [item.as_dict() for item in self.common_mistakes],
            "improvement_suggestions": [item.as_dict() for item in self.improvement_suggestions],
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "quality": self.quality.trust_level.value,
            "record_count": self.learning_analysis.outcomes.record_count,
            "win_rate": str(self.learning_analysis.outcomes.win_rate),
            "best_regime": self.best_regimes[0].group_value if self.best_regimes else None,
            "best_strategy": self.best_strategies[0].group_value if self.best_strategies else None,
            "ai_accuracy": str(self.ai_accuracy.accuracy),
            "common_mistake_count": len(self.common_mistakes),
            "suggestion_count": len(self.improvement_suggestions),
        }


def build_trade_intelligence_report(
    records: Sequence[TradeLearningRecord],
    *,
    generated_at: datetime | None = None,
    source_refs: Mapping[str, str] | None = None,
    min_sample_size: int = 2,
    confidence_threshold: Decimal = Decimal("0.60"),
    high_confidence_threshold: Decimal = Decimal("0.70"),
    low_confidence_threshold: Decimal = Decimal("0.40"),
) -> TradeIntelligenceReport:
    """Build a deterministic advisory intelligence report from completed trades."""

    if min_sample_size < 1:
        raise ValueError("min_sample_size must be positive")
    for name, value in (
        ("confidence_threshold", confidence_threshold),
        ("high_confidence_threshold", high_confidence_threshold),
        ("low_confidence_threshold", low_confidence_threshold),
    ):
        if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
            raise ValueError(f"{name} must be between 0 and 1")
    checked_at = generated_at or datetime.now(UTC)
    refs = dict(source_refs or {})
    refs.setdefault("trade_records", f"count:{len(records)}")
    learning = build_learning_analysis(records, generated_at=checked_at, source_refs=refs)
    usable = tuple(record for record in records if record.is_usable_for_learning)
    quality = _trade_intelligence_quality(
        learning.quality,
        usable_count=len(usable),
        min_sample_size=min_sample_size,
        checked_at=checked_at,
    )
    best_regimes = _best_patterns(
        learning.regime_performance,
        min_sample_size=min_sample_size,
    )
    best_strategies = _best_patterns(
        tuple(
            PatternSummary(
                group_name="strategy",
                group_value=item.strategy_name,
                sample_count=item.sample_count,
                win_rate=item.win_rate,
                average_return=DECIMAL_ZERO,
                expectancy=item.expectancy,
                reason="strategy ranking converted for Stage 062 intelligence",
            )
            for item in learning.strategy_rankings
        ),
        min_sample_size=min_sample_size,
    )
    mistakes = _common_mistakes(
        usable,
        best_regimes=best_regimes,
        high_confidence_threshold=high_confidence_threshold,
        low_confidence_threshold=low_confidence_threshold,
    )
    suggestions = (
        _improvement_suggestions(
            learning.recommendations,
            mistakes,
            learning.feature_importance,
            best_regimes,
            best_strategies,
        )
        if quality.is_trusted
        else ()
    )
    return TradeIntelligenceReport(
        generated_at=checked_at,
        quality=quality,
        learning_analysis=learning,
        holding_time=_holding_time(usable),
        best_regimes=best_regimes,
        best_strategies=best_strategies,
        best_indicators=learning.feature_importance[:3],
        ai_accuracy=_ai_accuracy(usable, confidence_threshold=confidence_threshold),
        common_mistakes=mistakes,
        improvement_suggestions=suggestions,
        source_refs=refs,
    )


def _trade_intelligence_quality(
    learning_quality: DataQualityStatus,
    *,
    usable_count: int,
    min_sample_size: int,
    checked_at: datetime,
) -> DataQualityStatus:
    issues = list(learning_quality.issues)
    if usable_count < min_sample_size:
        issues.append(
            DataQualityIssue(
                flag="insufficient_completed_trades",
                severity=DataTrustLevel.DEGRADED,
                reason=f"{usable_count} usable completed trades is below {min_sample_size}",
            )
        )
    if learning_quality.is_rejected:
        trust_level = DataTrustLevel.REJECTED
    elif any(issue.severity is DataTrustLevel.DEGRADED for issue in issues):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="learning:trade_intelligence",
        checked_at=normalize_timestamp(checked_at),
    )


def _holding_time(records: Sequence[TradeLearningRecord]) -> HoldingTimeInsight:
    durations = tuple(_duration_seconds(record) for record in records)
    winning = tuple(
        _duration_seconds(record) for record in records if record.outcome is OutcomeLabel.WIN
    )
    losing_records = tuple(record for record in records if record.outcome is OutcomeLabel.LOSS)
    losing = tuple(_duration_seconds(record) for record in losing_records)
    longest_losing = max(losing_records, key=_duration_seconds, default=None)
    return HoldingTimeInsight(
        sample_count=len(records),
        average_seconds=_average(durations),
        winning_average_seconds=_average(winning),
        losing_average_seconds=_average(losing),
        longest_losing_trade_id=longest_losing.trade_id if longest_losing else None,
        reason="holding time is computed from normalized opened_at and closed_at timestamps",
    )


def _ai_accuracy(
    records: Sequence[TradeLearningRecord],
    *,
    confidence_threshold: Decimal,
) -> AIPredictionAccuracy:
    with_prediction = tuple(
        record for record in records if record.prediction_confidence is not None
    )
    correct = 0
    for record in with_prediction:
        predicted_positive = bool(
            record.prediction_confidence and record.prediction_confidence >= confidence_threshold
        )
        actual_positive = record.outcome is OutcomeLabel.WIN
        if predicted_positive == actual_positive:
            correct += 1
    evaluated = len(with_prediction)
    return AIPredictionAccuracy(
        evaluated_count=evaluated,
        correct_count=correct,
        accuracy=Decimal(correct) / Decimal(evaluated) if evaluated else DECIMAL_ZERO,
        average_prediction_confidence=_average(
            tuple(record.prediction_confidence or DECIMAL_ZERO for record in with_prediction)
        ),
        confidence_threshold=confidence_threshold,
        reason=(
            "prediction_confidence above threshold is treated as positive outcome expectation"
            if evaluated
            else "no prediction_confidence values were available"
        ),
    )


def _best_patterns(
    patterns: Sequence[PatternSummary],
    *,
    min_sample_size: int,
) -> tuple[PatternSummary, ...]:
    eligible = tuple(
        item
        for item in patterns
        if item.sample_count >= min_sample_size and item.expectancy > DECIMAL_ZERO
    )
    return tuple(
        sorted(
            eligible,
            key=lambda item: (-item.expectancy, -item.win_rate, item.group_value),
        )
    )


def _common_mistakes(
    records: Sequence[TradeLearningRecord],
    *,
    best_regimes: Sequence[PatternSummary],
    high_confidence_threshold: Decimal,
    low_confidence_threshold: Decimal,
) -> tuple[CommonTradeMistake, ...]:
    mistakes: list[CommonTradeMistake] = []
    high_conf_losses = tuple(
        record.trade_id
        for record in records
        if record.signal_confidence >= high_confidence_threshold
        and record.outcome is OutcomeLabel.LOSS
    )
    if high_conf_losses:
        mistakes.append(
            CommonTradeMistake(
                mistake_type=TradeMistakeType.HIGH_CONFIDENCE_LOSS,
                trade_ids=high_conf_losses,
                severity=DataTrustLevel.DEGRADED,
                reason="high-confidence signals produced losing completed trades",
            )
        )
    low_conf_wins = tuple(
        record.trade_id
        for record in records
        if record.signal_confidence <= low_confidence_threshold
        and record.outcome is OutcomeLabel.WIN
    )
    if low_conf_wins:
        mistakes.append(
            CommonTradeMistake(
                mistake_type=TradeMistakeType.LOW_CONFIDENCE_WIN,
                trade_ids=low_conf_wins,
                severity=DataTrustLevel.DEGRADED,
                reason="low-confidence signals included winning completed trades",
            )
        )
    fee_drag = tuple(
        record.trade_id
        for record in records
        if record.realized_pnl > DECIMAL_ZERO and record.fees_paid >= record.realized_pnl.copy_abs()
    )
    if fee_drag:
        mistakes.append(
            CommonTradeMistake(
                mistake_type=TradeMistakeType.FEE_DRAG,
                trade_ids=fee_drag,
                severity=DataTrustLevel.DEGRADED,
                reason="fees consumed all or more than winning trade profit",
            )
        )
    holding = _holding_time(records)
    long_losses = tuple(
        record.trade_id
        for record in records
        if record.outcome is OutcomeLabel.LOSS
        and Decimal(_duration_seconds(record)) > holding.average_seconds
    )
    if long_losses:
        mistakes.append(
            CommonTradeMistake(
                mistake_type=TradeMistakeType.LONG_HOLDING_LOSS,
                trade_ids=long_losses,
                severity=DataTrustLevel.DEGRADED,
                reason="losing trades were held longer than the average completed trade",
            )
        )
    best_regime_names = {item.group_value for item in best_regimes[:2]}
    weak_regime_losses = tuple(
        record.trade_id
        for record in records
        if best_regime_names
        and record.regime_label not in best_regime_names
        and record.outcome is OutcomeLabel.LOSS
    )
    if weak_regime_losses:
        mistakes.append(
            CommonTradeMistake(
                mistake_type=TradeMistakeType.WEAK_REGIME_FIT,
                trade_ids=weak_regime_losses,
                severity=DataTrustLevel.DEGRADED,
                reason="losses occurred outside the best observed regimes",
            )
        )
    return tuple(sorted(mistakes, key=lambda item: item.mistake_type.value))


def _improvement_suggestions(
    recommendations: Sequence[LearningRecommendation],
    mistakes: Sequence[CommonTradeMistake],
    indicators: Sequence[FeatureImportanceObservation],
    best_regimes: Sequence[PatternSummary],
    best_strategies: Sequence[PatternSummary],
) -> tuple[TradeImprovementSuggestion, ...]:
    suggestions: list[TradeImprovementSuggestion] = []
    for recommendation in recommendations:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.CONFIDENCE_REVIEW,
                target=recommendation.target,
                rationale=recommendation.rationale,
                evidence_refs=recommendation.evidence_refs or ("learning:calibration",),
            )
        )
    mistake_types = {mistake.mistake_type for mistake in mistakes}
    if TradeMistakeType.HIGH_CONFIDENCE_LOSS in mistake_types:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.CONFIDENCE_REVIEW,
                target="high_confidence_loss",
                rationale="review confidence thresholds before trusting high-confidence entries",
                evidence_refs=_mistake_refs(mistakes, TradeMistakeType.HIGH_CONFIDENCE_LOSS),
            )
        )
    if TradeMistakeType.LONG_HOLDING_LOSS in mistake_types:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.HOLDING_TIME_REVIEW,
                target="losing_trade_holding_time",
                rationale="review time-based exits for losing completed trades",
                evidence_refs=_mistake_refs(mistakes, TradeMistakeType.LONG_HOLDING_LOSS),
            )
        )
    if TradeMistakeType.FEE_DRAG in mistake_types:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.COST_REVIEW,
                target="fee_drag",
                rationale="review fee and slippage assumptions for small winning trades",
                evidence_refs=_mistake_refs(mistakes, TradeMistakeType.FEE_DRAG),
            )
        )
    if best_regimes:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.REGIME_FILTER_REVIEW,
                target=best_regimes[0].group_value,
                rationale="best observed regime should be validated as a future strategy filter",
                evidence_refs=(f"regime:{best_regimes[0].group_value}",),
            )
        )
    if best_strategies:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.STRATEGY_REVIEW,
                target=best_strategies[0].group_value,
                rationale="best observed strategy should be benchmarked before promotion",
                evidence_refs=(f"strategy:{best_strategies[0].group_value}",),
            )
        )
    if indicators:
        suggestions.append(
            TradeImprovementSuggestion(
                suggestion_type=TradeImprovementType.INDICATOR_REVIEW,
                target=indicators[0].feature_name,
                rationale=(
                    "strongest observed indicator relationship should be validated out of sample"
                ),
                evidence_refs=(f"feature:{indicators[0].feature_name}",),
            )
        )
    return tuple(suggestions)


def _mistake_refs(
    mistakes: Sequence[CommonTradeMistake],
    mistake_type: TradeMistakeType,
) -> tuple[str, ...]:
    return tuple(
        f"trade:{trade_id}"
        for mistake in mistakes
        if mistake.mistake_type is mistake_type
        for trade_id in mistake.trade_ids
    )


def _duration_seconds(record: TradeLearningRecord) -> int:
    return int((record.closed_at - record.opened_at).total_seconds())


def _average(values: Sequence[Decimal | int]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return sum((Decimal(value) for value in values), DECIMAL_ZERO) / Decimal(len(values))
