"""Deterministic self-learning analysis for completed trades."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
MAX_ADVISORY_ADJUSTMENT = Decimal("0.10")


class OutcomeLabel(StrEnum):
    """Completed trade outcome label."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


@dataclass(frozen=True, slots=True)
class TradeLearningRecord:
    """Normalized completed-trade record used by Stage 035 learning analysis."""

    trade_id: str
    strategy_name: str
    regime_label: str
    opened_at: datetime
    closed_at: datetime
    realized_pnl: Decimal
    return_pct: Decimal
    fees_paid: Decimal
    signal_confidence: Decimal
    risk_decision_status: str
    prediction_confidence: Decimal | None = None
    features: Mapping[str, Decimal] = field(default_factory=dict)
    source_refs: Mapping[str, str] = field(default_factory=dict)
    data_quality: DataQualityStatus | None = None
    validation_context: str = "paper"

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id is required")
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if not self.regime_label.strip():
            raise ValueError("regime_label is required")
        if self.closed_at < self.opened_at:
            raise ValueError("closed_at cannot be before opened_at")
        if self.fees_paid < DECIMAL_ZERO:
            raise ValueError("fees_paid cannot be negative")
        if not DECIMAL_ZERO <= self.signal_confidence <= DECIMAL_ONE:
            raise ValueError("signal_confidence must be between 0 and 1")
        if self.prediction_confidence is not None and not (
            DECIMAL_ZERO <= self.prediction_confidence <= DECIMAL_ONE
        ):
            raise ValueError("prediction_confidence must be between 0 and 1")
        if not self.risk_decision_status.strip():
            raise ValueError("risk_decision_status is required")
        if not self.validation_context.strip():
            raise ValueError("validation_context is required")
        object.__setattr__(self, "opened_at", normalize_timestamp(self.opened_at))
        object.__setattr__(self, "closed_at", normalize_timestamp(self.closed_at))
        object.__setattr__(self, "features", dict(self.features))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def outcome(self) -> OutcomeLabel:
        """Return the deterministic win/loss/breakeven outcome."""

        if self.realized_pnl > DECIMAL_ZERO:
            return OutcomeLabel.WIN
        if self.realized_pnl < DECIMAL_ZERO:
            return OutcomeLabel.LOSS
        return OutcomeLabel.BREAKEVEN

    @property
    def is_usable_for_learning(self) -> bool:
        """Rejected source data cannot produce trusted learning recommendations."""

        return self.data_quality is None or not self.data_quality.is_rejected

    def as_dict(self) -> dict[str, object]:
        """Return an audit-friendly record snapshot without secret values."""

        return {
            "trade_id": self.trade_id,
            "strategy_name": self.strategy_name,
            "regime_label": self.regime_label,
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat(),
            "realized_pnl": str(self.realized_pnl),
            "return_pct": str(self.return_pct),
            "fees_paid": str(self.fees_paid),
            "signal_confidence": str(self.signal_confidence),
            "prediction_confidence": (
                str(self.prediction_confidence) if self.prediction_confidence is not None else None
            ),
            "risk_decision_status": self.risk_decision_status,
            "outcome": self.outcome.value,
            "features": {key: str(value) for key, value in self.features.items()},
            "source_refs": dict(self.source_refs),
            "validation_context": self.validation_context,
        }


@dataclass(frozen=True, slots=True)
class TradeOutcomeAnalysis:
    """Aggregate completed-trade outcome analysis."""

    record_count: int
    wins: int
    losses: int
    breakeven: int
    win_rate: Decimal
    average_return: Decimal
    expectancy: Decimal
    total_pnl: Decimal
    total_fees: Decimal
    max_loss: Decimal

    def as_dict(self) -> dict[str, object]:
        return {
            "record_count": self.record_count,
            "wins": self.wins,
            "losses": self.losses,
            "breakeven": self.breakeven,
            "win_rate": str(self.win_rate),
            "average_return": str(self.average_return),
            "expectancy": str(self.expectancy),
            "total_pnl": str(self.total_pnl),
            "total_fees": str(self.total_fees),
            "max_loss": str(self.max_loss),
        }


@dataclass(frozen=True, slots=True)
class PatternSummary:
    """Outcome pattern summary for a grouped slice such as regime or strategy."""

    group_name: str
    group_value: str
    sample_count: int
    win_rate: Decimal
    average_return: Decimal
    expectancy: Decimal
    reason: str

    def __post_init__(self) -> None:
        if not self.group_name.strip():
            raise ValueError("group_name is required")
        if not self.group_value.strip():
            raise ValueError("group_value is required")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "group_name": self.group_name,
            "group_value": self.group_value,
            "sample_count": self.sample_count,
            "win_rate": str(self.win_rate),
            "average_return": str(self.average_return),
            "expectancy": str(self.expectancy),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class FeatureImportanceObservation:
    """Simple deterministic feature/outcome observation."""

    feature_name: str
    sample_count: int
    positive_feature_average_return: Decimal
    non_positive_feature_average_return: Decimal
    directional_score: Decimal
    reason: str

    def __post_init__(self) -> None:
        if not self.feature_name.strip():
            raise ValueError("feature_name is required")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "feature_name": self.feature_name,
            "sample_count": self.sample_count,
            "positive_feature_average_return": str(self.positive_feature_average_return),
            "non_positive_feature_average_return": str(self.non_positive_feature_average_return),
            "directional_score": str(self.directional_score),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class StrategyLearningRank:
    """Advisory strategy ranking from completed-trade outcomes."""

    strategy_name: str
    sample_count: int
    win_rate: Decimal
    expectancy: Decimal
    score: Decimal
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        if not self.reasons:
            raise ValueError("strategy rank requires reasons")

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_name": self.strategy_name,
            "sample_count": self.sample_count,
            "win_rate": str(self.win_rate),
            "expectancy": str(self.expectancy),
            "score": str(self.score),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class LearningRecommendation:
    """Advisory recommendation that cannot self-apply trading changes."""

    recommendation_type: str
    target: str
    confidence_adjustment: Decimal
    rationale: str
    evidence_refs: tuple[str, ...]
    requires_validation: bool = True
    allowed_to_auto_apply: bool = False

    def __post_init__(self) -> None:
        if not self.recommendation_type.strip():
            raise ValueError("recommendation_type is required")
        if not self.target.strip():
            raise ValueError("recommendation target is required")
        if not -DECIMAL_ONE <= self.confidence_adjustment <= DECIMAL_ONE:
            raise ValueError("confidence_adjustment must be between -1 and 1")
        if not self.rationale.strip():
            raise ValueError("rationale is required")
        if not self.requires_validation:
            raise ValueError("learning recommendations require paper/backtest validation")
        if self.allowed_to_auto_apply:
            raise ValueError("learning recommendations cannot auto-apply trading changes")

    def as_dict(self) -> dict[str, object]:
        return {
            "recommendation_type": self.recommendation_type,
            "target": self.target,
            "confidence_adjustment": str(self.confidence_adjustment),
            "rationale": self.rationale,
            "evidence_refs": list(self.evidence_refs),
            "requires_validation": self.requires_validation,
            "allowed_to_auto_apply": self.allowed_to_auto_apply,
        }


@dataclass(frozen=True, slots=True)
class LearningAnalysis:
    """Full advisory self-learning output for completed trades."""

    generated_at: datetime
    quality: DataQualityStatus
    outcomes: TradeOutcomeAnalysis
    win_loss_patterns: tuple[PatternSummary, ...]
    regime_performance: tuple[PatternSummary, ...]
    feature_importance: tuple[FeatureImportanceObservation, ...]
    strategy_rankings: tuple[StrategyLearningRank, ...]
    recommendations: tuple[LearningRecommendation, ...]
    source_refs: Mapping[str, str]
    limitations: tuple[str, ...] = (
        "Learning output is advisory and cannot modify trading rules automatically.",
        "Recommendations require paper/backtest validation before adoption.",
        "Risk Management Engine rules remain authoritative.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "outcomes": self.outcomes.as_dict(),
            "win_loss_patterns": [item.as_dict() for item in self.win_loss_patterns],
            "regime_performance": [item.as_dict() for item in self.regime_performance],
            "feature_importance": [item.as_dict() for item in self.feature_importance],
            "strategy_rankings": [item.as_dict() for item in self.strategy_rankings],
            "recommendations": [item.as_dict() for item in self.recommendations],
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }


def analyze_trade_outcomes(records: Sequence[TradeLearningRecord]) -> TradeOutcomeAnalysis:
    """Analyze completed trade outcomes."""

    usable = _usable_records(records)
    if not usable:
        return TradeOutcomeAnalysis(
            0,
            0,
            0,
            0,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
            DECIMAL_ZERO,
        )
    wins = sum(1 for record in usable if record.outcome is OutcomeLabel.WIN)
    losses = sum(1 for record in usable if record.outcome is OutcomeLabel.LOSS)
    breakeven = sum(1 for record in usable if record.outcome is OutcomeLabel.BREAKEVEN)
    returns = tuple(record.return_pct for record in usable)
    pnl_values = tuple(record.realized_pnl for record in usable)
    return TradeOutcomeAnalysis(
        record_count=len(usable),
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        win_rate=Decimal(wins) / Decimal(len(usable)),
        average_return=_average(returns),
        expectancy=_average(pnl_values),
        total_pnl=sum(pnl_values, DECIMAL_ZERO),
        total_fees=sum((record.fees_paid for record in usable), DECIMAL_ZERO),
        max_loss=min((*pnl_values, DECIMAL_ZERO)),
    )


def win_loss_patterns(records: Sequence[TradeLearningRecord]) -> tuple[PatternSummary, ...]:
    """Summarize deterministic win/loss patterns by strategy and regime."""

    return (
        *_group_patterns(
            _usable_records(records), group_name="strategy", key=lambda item: item.strategy_name
        ),
        *_group_patterns(
            _usable_records(records), group_name="regime", key=lambda item: item.regime_label
        ),
    )


def regime_performance(records: Sequence[TradeLearningRecord]) -> tuple[PatternSummary, ...]:
    """Summarize completed-trade performance by market regime."""

    return _group_patterns(
        _usable_records(records), group_name="regime", key=lambda item: item.regime_label
    )


def feature_importance_observations(
    records: Sequence[TradeLearningRecord],
) -> tuple[FeatureImportanceObservation, ...]:
    """Return simple feature/outcome observations for available numeric features."""

    usable = _usable_records(records)
    feature_names = sorted({name for record in usable for name in record.features})
    observations: list[FeatureImportanceObservation] = []
    for feature_name in feature_names:
        with_feature = tuple(record for record in usable if feature_name in record.features)
        positive_returns = tuple(
            record.return_pct
            for record in with_feature
            if record.features[feature_name] > DECIMAL_ZERO
        )
        non_positive_returns = tuple(
            record.return_pct
            for record in with_feature
            if record.features[feature_name] <= DECIMAL_ZERO
        )
        positive_average = _average(positive_returns)
        non_positive_average = _average(non_positive_returns)
        score = positive_average - non_positive_average
        observations.append(
            FeatureImportanceObservation(
                feature_name=feature_name,
                sample_count=len(with_feature),
                positive_feature_average_return=positive_average,
                non_positive_feature_average_return=non_positive_average,
                directional_score=score,
                reason=(
                    "positive feature values had stronger outcomes"
                    if score > DECIMAL_ZERO
                    else "positive feature values did not improve outcomes"
                ),
            )
        )
    return tuple(
        sorted(observations, key=lambda item: (-abs(item.directional_score), item.feature_name))
    )


def strategy_rankings(records: Sequence[TradeLearningRecord]) -> tuple[StrategyLearningRank, ...]:
    """Rank strategies from completed trade outcomes."""

    ranks: list[StrategyLearningRank] = []
    for group in _group_patterns(
        _usable_records(records), group_name="strategy", key=lambda item: item.strategy_name
    ):
        score = group.win_rate + group.average_return + group.expectancy / Decimal("100")
        ranks.append(
            StrategyLearningRank(
                strategy_name=group.group_value,
                sample_count=group.sample_count,
                win_rate=group.win_rate,
                expectancy=group.expectancy,
                score=score,
                reasons=(
                    f"win_rate={group.win_rate}",
                    f"average_return={group.average_return}",
                    f"expectancy={group.expectancy}",
                ),
            )
        )
    return tuple(sorted(ranks, key=lambda item: (-item.score, item.strategy_name)))


def build_learning_analysis(
    records: Sequence[TradeLearningRecord],
    *,
    generated_at: datetime | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> LearningAnalysis:
    """Build a complete advisory learning analysis."""

    from abtp.learning.calibration import calibrate_confidence

    checked_at = generated_at or datetime.now(UTC)
    quality = _aggregate_quality(records, checked_at=checked_at)
    usable = _usable_records(records)
    calibration = calibrate_confidence(usable, generated_at=checked_at)
    recommendations = tuple(
        LearningRecommendation(
            recommendation_type="confidence_calibration",
            target=suggestion.target,
            confidence_adjustment=suggestion.adjustment,
            rationale=suggestion.rationale,
            evidence_refs=suggestion.evidence_refs,
        )
        for suggestion in calibration.suggestions
    )
    return LearningAnalysis(
        generated_at=checked_at,
        quality=quality,
        outcomes=analyze_trade_outcomes(usable),
        win_loss_patterns=win_loss_patterns(usable),
        regime_performance=regime_performance(usable),
        feature_importance=feature_importance_observations(usable),
        strategy_rankings=strategy_rankings(usable),
        recommendations=recommendations if quality.is_trusted else (),
        source_refs=source_refs or {},
    )


def _group_patterns(
    records: Sequence[TradeLearningRecord],
    *,
    group_name: str,
    key: Callable[[TradeLearningRecord], str],
) -> tuple[PatternSummary, ...]:
    grouped: dict[str, list[TradeLearningRecord]] = {}
    for record in records:
        group_value = key(record)
        grouped.setdefault(group_value, []).append(record)
    summaries: list[PatternSummary] = []
    for group_value, group_records in sorted(grouped.items()):
        outcomes = analyze_trade_outcomes(group_records)
        summaries.append(
            PatternSummary(
                group_name=group_name,
                group_value=group_value,
                sample_count=outcomes.record_count,
                win_rate=outcomes.win_rate,
                average_return=outcomes.average_return,
                expectancy=outcomes.expectancy,
                reason=(
                    f"{group_name} {group_value} has {outcomes.wins} wins "
                    f"and {outcomes.losses} losses"
                ),
            )
        )
    return tuple(summaries)


def _aggregate_quality(
    records: Sequence[TradeLearningRecord],
    *,
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    if not records:
        issues.append(
            DataQualityIssue(
                flag="missing_trade_records",
                severity=DataTrustLevel.REJECTED,
                reason="self-learning requires completed trade records",
            )
        )
    rejected_count = sum(
        1 for record in records if record.data_quality and record.data_quality.is_rejected
    )
    degraded_count = sum(
        1 for record in records if record.data_quality and record.data_quality.is_degraded
    )
    if rejected_count:
        issues.append(
            DataQualityIssue(
                flag="rejected_trade_records_excluded",
                severity=DataTrustLevel.DEGRADED,
                reason=f"{rejected_count} rejected records were excluded from learning",
            )
        )
    if degraded_count:
        issues.append(
            DataQualityIssue(
                flag="degraded_trade_records",
                severity=DataTrustLevel.DEGRADED,
                reason=f"{degraded_count} degraded records were included with degraded quality",
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="learning:trade_records",
        checked_at=normalize_timestamp(checked_at),
    )


def _usable_records(records: Sequence[TradeLearningRecord]) -> tuple[TradeLearningRecord, ...]:
    return tuple(record for record in records if record.is_usable_for_learning)


def _average(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return DECIMAL_ZERO
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))
