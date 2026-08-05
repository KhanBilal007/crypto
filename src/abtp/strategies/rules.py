"""Deterministic rule helpers for strategy plugins."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abtp.data import DataQualityIssue, DataTrustLevel
from abtp.domain import Signal, SignalDirection
from abtp.strategies.base import (
    StrategyConfig,
    StrategyContext,
    StrategyEvaluation,
    StrategySignalPlan,
)


@dataclass(frozen=True, slots=True)
class ThresholdRuleStrategyConfig(StrategyConfig):
    """Generic threshold strategy used for framework tests and examples."""

    buy_probability_threshold: Decimal = Decimal("0.60")
    sell_probability_threshold: Decimal = Decimal("0.60")
    minimum_confidence: Decimal = Decimal("0.30")

    def __post_init__(self) -> None:
        StrategyConfig.__post_init__(self)
        for value, field_name in (
            (self.buy_probability_threshold, "buy_probability_threshold"),
            (self.sell_probability_threshold, "sell_probability_threshold"),
            (self.minimum_confidence, "minimum_confidence"),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be between 0 and 1")


class ThresholdRuleStrategy:
    """Simple pluggable strategy that turns prediction context into a Signal."""

    def __init__(self, config: ThresholdRuleStrategyConfig) -> None:
        self._config = config

    @property
    def config(self) -> ThresholdRuleStrategyConfig:
        return self._config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        return rule_based_signal(config=self.config, context=context)


def rule_based_signal(
    *,
    config: ThresholdRuleStrategyConfig,
    context: StrategyContext,
) -> StrategyEvaluation:
    """Evaluate deterministic rules and return a non-executable domain signal."""

    reasons = list(_safety_reasons(config, context))
    if reasons:
        return _evaluation(
            config=config,
            context=context,
            direction=SignalDirection.HOLD,
            confidence=Decimal("0"),
            entry_reason=reasons[0],
            reasons=tuple(reasons),
        )

    prediction = context.prediction
    if prediction is None:
        return _evaluation(
            config=config,
            context=context,
            direction=SignalDirection.HOLD,
            confidence=Decimal("0"),
            entry_reason="prediction context is required",
            reasons=("prediction context is required",),
        )

    if (
        prediction.probability_up >= config.buy_probability_threshold
        and prediction.confidence >= config.minimum_confidence
    ):
        return _evaluation(
            config=config,
            context=context,
            direction=SignalDirection.BUY,
            confidence=prediction.confidence,
            entry_reason="probability_up and confidence passed strategy thresholds",
            reasons=("buy probability threshold passed",),
        )
    if (
        prediction.probability_down >= config.sell_probability_threshold
        and prediction.confidence >= config.minimum_confidence
    ):
        return _evaluation(
            config=config,
            context=context,
            direction=SignalDirection.SELL,
            confidence=prediction.confidence,
            entry_reason="probability_down and confidence passed strategy thresholds",
            reasons=("sell probability threshold passed",),
        )
    return _evaluation(
        config=config,
        context=context,
        direction=SignalDirection.HOLD,
        confidence=prediction.confidence,
        entry_reason="prediction did not pass directional strategy thresholds",
        reasons=("directional thresholds were not met",),
    )


def _safety_reasons(
    config: ThresholdRuleStrategyConfig,
    context: StrategyContext,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("strategy is disabled")
    if context.timeframe not in config.supported_timeframes:
        reasons.append("timeframe is not supported by strategy")
    if not context.features.quality.is_trusted:
        reasons.append("feature snapshot quality is not trusted")
    if context.regime is not None and context.regime.risk_adjustment.block_new_entries:
        reasons.append("regime risk context blocks new entries")
    if context.prediction is not None and not context.prediction.actionable:
        reasons.append("prediction is not actionable")
    return tuple(reasons)


def _evaluation(
    *,
    config: ThresholdRuleStrategyConfig,
    context: StrategyContext,
    direction: SignalDirection,
    confidence: Decimal,
    entry_reason: str,
    reasons: tuple[str, ...],
) -> StrategyEvaluation:
    plan = StrategySignalPlan(
        entry_reason=entry_reason,
        timeframe=context.timeframe,
        feature_snapshot_ref=context.feature_snapshot_ref,
        stop_suggestion=_stop_suggestion(context, direction),
        target_suggestion=_target_suggestion(context, direction),
        regime_label=context.regime.label.value if context.regime is not None else None,
        prediction_ref=_prediction_ref(context),
    )
    return StrategyEvaluation(
        strategy_name=config.name,
        strategy_version=config.version,
        enabled=config.enabled,
        signal=Signal(
            source=f"{config.name}:{config.version}",
            pair=context.features.pair,
            generated_at=context.generated_at,
            direction=direction,
            confidence=confidence,
            inputs_ref=context.feature_snapshot_ref,
            rationale=entry_reason,
            prediction_ref=_prediction_ref(context),
        ),
        plan=plan,
        reasons=_with_quality_reasons(reasons, context),
        generated_at=context.generated_at,
    )


def _with_quality_reasons(
    reasons: tuple[str, ...],
    context: StrategyContext,
) -> tuple[str, ...]:
    quality_reasons = tuple(
        issue.reason
        for issue in _quality_issues(context)
        if issue.severity is DataTrustLevel.REJECTED
    )
    return tuple(dict.fromkeys((*reasons, *quality_reasons)))


def _quality_issues(context: StrategyContext) -> tuple[DataQualityIssue, ...]:
    issues = [*context.features.quality.issues]
    if context.prediction is not None:
        issues.extend(context.prediction.quality.issues)
    if context.regime is not None:
        issues.extend(context.regime.quality.issues)
    return tuple(issues)


def _prediction_ref(context: StrategyContext) -> str | None:
    if context.prediction is None:
        return None
    return context.prediction.prediction_ref or context.prediction.prediction.features_ref


def _stop_suggestion(
    context: StrategyContext,
    direction: SignalDirection,
) -> Decimal | None:
    if direction is SignalDirection.HOLD:
        return None
    close = context.features.values.get("market.close")
    atr_pct = context.features.values.get("indicator.atr.atr_pct")
    if close is None or atr_pct is None or atr_pct <= Decimal("0"):
        return None
    offset = close * atr_pct * Decimal("2")
    if direction is SignalDirection.BUY:
        return max(Decimal("0.01"), close - offset)
    return close + offset


def _target_suggestion(
    context: StrategyContext,
    direction: SignalDirection,
) -> Decimal | None:
    if direction is SignalDirection.HOLD:
        return None
    close = context.features.values.get("market.close")
    atr_pct = context.features.values.get("indicator.atr.atr_pct")
    if close is None or atr_pct is None or atr_pct <= Decimal("0"):
        return None
    offset = close * atr_pct * Decimal("3")
    if direction is SignalDirection.BUY:
        return close + offset
    return max(Decimal("0.01"), close - offset)
