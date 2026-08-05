"""Deterministic market regime classification rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from abtp.ai.regime import (
    MarketRegimeLabel,
    RegimeClassification,
    RegimeEvidence,
    RiskAdjustmentSuggestion,
    unknown_regime,
)
from abtp.context import ContextBatch, ContextItem
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot


@dataclass(frozen=True, slots=True)
class RegimeRuleThresholds:
    """Conservative default thresholds for Stage 018 rules."""

    trend_return_threshold: Decimal = Decimal("0.015")
    range_return_threshold: Decimal = Decimal("0.006")
    high_volatility_atr_pct: Decimal = Decimal("0.035")
    shock_atr_pct: Decimal = Decimal("0.075")
    shock_return_abs: Decimal = Decimal("0.08")
    high_volume_ratio: Decimal = Decimal("2")
    shock_volume_ratio: Decimal = Decimal("3")
    high_spread_bps: Decimal = Decimal("75")
    shock_spread_bps: Decimal = Decimal("150")
    severe_drawdown: Decimal = Decimal("-0.08")
    negative_sentiment: Decimal = Decimal("-0.50")
    liquidation_shock: Decimal = Decimal("10000000")


def classify_market_regime(
    snapshot: FeatureSnapshot,
    *,
    context_batches: Sequence[ContextBatch] = (),
    thresholds: RegimeRuleThresholds | None = None,
) -> RegimeClassification:
    """Classify the current market regime from features and optional context."""

    rule_thresholds = thresholds or RegimeRuleThresholds()
    source_refs = _source_refs(snapshot, context_batches)
    base_evidence = _base_evidence(snapshot)
    quality_issues = [*snapshot.quality.issues, *_context_quality_issues(context_batches)]

    if snapshot.quality.is_rejected:
        quality = _quality(
            quality_issues,
            checked_at=snapshot.generated_at,
            source_ref="regime:rejected_features",
        )
        return unknown_regime(
            snapshot=snapshot,
            confidence=Decimal("0"),
            reasons=("feature snapshot is rejected; regime cannot be trusted",),
            evidence=base_evidence,
            quality=quality,
            source_refs=source_refs,
        )

    missing = _missing_required_features(snapshot)
    if missing:
        quality_issues.extend(
            DataQualityIssue(
                flag="missing_regime_feature",
                severity=DataTrustLevel.DEGRADED,
                reason=f"missing regime feature: {name}",
            )
            for name in missing
        )
        quality = _quality(
            quality_issues,
            checked_at=snapshot.generated_at,
            source_ref="regime:missing_features",
        )
        return unknown_regime(
            snapshot=snapshot,
            confidence=Decimal("0.10"),
            reasons=("required regime inputs are missing",),
            evidence=base_evidence,
            quality=quality,
            source_refs=source_refs,
        )

    context_evidence, context_shock = _context_evidence(context_batches, rule_thresholds)
    evidence = (*base_evidence, *context_evidence)
    if context_shock:
        quality_issues.append(
            DataQualityIssue(
                flag="low_trust_context_used",
                severity=DataTrustLevel.DEGRADED,
                reason="optional external context contributed to shock classification",
            )
        )

    values = snapshot.values
    return_1 = values.get("market.return_1", Decimal("0"))
    return_3 = values["market.return_3"]
    atr_pct = values["indicator.atr.atr_pct"]
    volume_ratio = values["market.volume_ratio"]
    spread_bps = values.get("liquidity.spread_bps", Decimal("0"))
    rsi = values.get("indicator.rsi.rsi")
    close = values.get("market.close")
    sma = values.get("indicator.sma.sma")
    drawdown = values.get("portfolio.drawdown", Decimal("0"))

    shock_reasons = _shock_reasons(
        return_1=return_1,
        atr_pct=atr_pct,
        volume_ratio=volume_ratio,
        spread_bps=spread_bps,
        drawdown=drawdown,
        context_shock=context_shock,
        thresholds=rule_thresholds,
    )
    if shock_reasons:
        return _classification(
            snapshot=snapshot,
            label=MarketRegimeLabel.SHOCK,
            confidence=Decimal("0.90"),
            risk_adjustment=_risk_adjustment(MarketRegimeLabel.SHOCK),
            reasons=shock_reasons,
            evidence=evidence,
            quality_issues=tuple(quality_issues),
            source_refs=source_refs,
        )

    high_vol_reasons = _high_volatility_reasons(
        atr_pct=atr_pct,
        volume_ratio=volume_ratio,
        spread_bps=spread_bps,
        thresholds=rule_thresholds,
    )
    if high_vol_reasons:
        return _classification(
            snapshot=snapshot,
            label=MarketRegimeLabel.HIGH_VOLATILITY,
            confidence=Decimal("0.78"),
            risk_adjustment=_risk_adjustment(MarketRegimeLabel.HIGH_VOLATILITY),
            reasons=high_vol_reasons,
            evidence=evidence,
            quality_issues=tuple(quality_issues),
            source_refs=source_refs,
        )

    trend_label = _trend_label(
        return_3=return_3,
        close=close,
        sma=sma,
        rsi=rsi,
        thresholds=rule_thresholds,
    )
    if trend_label is not None:
        return _classification(
            snapshot=snapshot,
            label=trend_label,
            confidence=Decimal("0.68"),
            risk_adjustment=_risk_adjustment(trend_label),
            reasons=(f"{trend_label.value} conditions met by return, SMA, and RSI alignment",),
            evidence=evidence,
            quality_issues=tuple(quality_issues),
            source_refs=source_refs,
        )

    if abs(return_3) <= rule_thresholds.range_return_threshold and (
        rsi is None or Decimal("40") <= rsi <= Decimal("60")
    ):
        return _classification(
            snapshot=snapshot,
            label=MarketRegimeLabel.RANGE_BOUND,
            confidence=Decimal("0.62"),
            risk_adjustment=_risk_adjustment(MarketRegimeLabel.RANGE_BOUND),
            reasons=("returns are muted and momentum is neutral",),
            evidence=evidence,
            quality_issues=tuple(quality_issues),
            source_refs=source_refs,
        )

    return _classification(
        snapshot=snapshot,
        label=MarketRegimeLabel.UNKNOWN,
        confidence=Decimal("0.30"),
        risk_adjustment=_risk_adjustment(MarketRegimeLabel.UNKNOWN),
        reasons=("features do not meet trend, range, high-volatility, or shock rules",),
        evidence=evidence,
        quality_issues=tuple(quality_issues),
        source_refs=source_refs,
    )


def _base_evidence(snapshot: FeatureSnapshot) -> tuple[RegimeEvidence, ...]:
    keys = (
        "market.return_1",
        "market.return_3",
        "indicator.atr.atr_pct",
        "market.volume_ratio",
        "liquidity.spread_bps",
        "liquidity.imbalance",
        "indicator.rsi.rsi",
        "indicator.sma.sma",
        "market.close",
        "portfolio.drawdown",
    )
    return tuple(
        RegimeEvidence(
            key=key,
            value=_json_value(snapshot.values[key]),
            reason="feature input used by regime rules",
            source_ref=snapshot.inputs_ref,
        )
        for key in keys
        if key in snapshot.values
    )


def _context_evidence(
    context_batches: Sequence[ContextBatch],
    thresholds: RegimeRuleThresholds,
) -> tuple[tuple[RegimeEvidence, ...], bool]:
    evidence: list[RegimeEvidence] = []
    shock = False
    for batch in context_batches:
        for item in batch.items:
            evidence.append(
                RegimeEvidence(
                    key=f"context.{item.key}",
                    value=item.value,
                    reason="optional external context considered by regime rules",
                    source_ref=item.quality.source_ref,
                )
            )
            if _context_item_is_shock(item, thresholds):
                shock = True
    return tuple(evidence), shock


def _context_item_is_shock(item: ContextItem, thresholds: RegimeRuleThresholds) -> bool:
    value = _decimal_or_none(item.value)
    if item.key == "bitcoin_sentiment" and value is not None:
        return value <= thresholds.negative_sentiment
    if item.key == "liquidations_1h" and value is not None:
        return value >= thresholds.liquidation_shock
    if item.key == "major_calendar_event" and isinstance(item.value, dict):
        return str(item.value.get("impact", "")).lower() == "high"
    return False


def _missing_required_features(snapshot: FeatureSnapshot) -> tuple[str, ...]:
    required = ("market.return_3", "indicator.atr.atr_pct", "market.volume_ratio")
    return tuple(name for name in required if name not in snapshot.values)


def _shock_reasons(
    *,
    return_1: Decimal,
    atr_pct: Decimal,
    volume_ratio: Decimal,
    spread_bps: Decimal,
    drawdown: Decimal,
    context_shock: bool,
    thresholds: RegimeRuleThresholds,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if abs(return_1) >= thresholds.shock_return_abs:
        reasons.append("single-period return exceeds shock threshold")
    if atr_pct >= thresholds.shock_atr_pct:
        reasons.append("ATR percentage exceeds shock threshold")
    if volume_ratio >= thresholds.shock_volume_ratio:
        reasons.append("volume anomaly exceeds shock threshold")
    if spread_bps >= thresholds.shock_spread_bps:
        reasons.append("spread exceeds shock threshold")
    if drawdown <= thresholds.severe_drawdown:
        reasons.append("drawdown exceeds severe threshold")
    if context_shock:
        reasons.append("optional external context indicates sudden shock risk")
    return tuple(reasons)


def _high_volatility_reasons(
    *,
    atr_pct: Decimal,
    volume_ratio: Decimal,
    spread_bps: Decimal,
    thresholds: RegimeRuleThresholds,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if atr_pct >= thresholds.high_volatility_atr_pct:
        reasons.append("ATR percentage exceeds high-volatility threshold")
    if volume_ratio >= thresholds.high_volume_ratio:
        reasons.append("volume anomaly exceeds high-volatility threshold")
    if spread_bps >= thresholds.high_spread_bps:
        reasons.append("spread/liquidity exceeds high-volatility threshold")
    return tuple(reasons)


def _trend_label(
    *,
    return_3: Decimal,
    close: Decimal | None,
    sma: Decimal | None,
    rsi: Decimal | None,
    thresholds: RegimeRuleThresholds,
) -> MarketRegimeLabel | None:
    if (
        return_3 >= thresholds.trend_return_threshold
        and (close is None or sma is None or close >= sma)
        and (rsi is None or rsi >= Decimal("55"))
    ):
        return MarketRegimeLabel.TREND_UP
    if (
        return_3 <= -thresholds.trend_return_threshold
        and (close is None or sma is None or close <= sma)
        and (rsi is None or rsi <= Decimal("45"))
    ):
        return MarketRegimeLabel.TREND_DOWN
    return None


def _classification(
    *,
    snapshot: FeatureSnapshot,
    label: MarketRegimeLabel,
    confidence: Decimal,
    risk_adjustment: RiskAdjustmentSuggestion,
    reasons: tuple[str, ...],
    evidence: tuple[RegimeEvidence, ...],
    quality_issues: tuple[DataQualityIssue, ...],
    source_refs: Mapping[str, str],
) -> RegimeClassification:
    quality = _quality(
        quality_issues,
        checked_at=snapshot.generated_at,
        source_ref=f"regime:{label.value}:{snapshot.generated_at.isoformat()}",
    )
    if quality.is_degraded and label in {MarketRegimeLabel.TREND_UP, MarketRegimeLabel.TREND_DOWN}:
        label = MarketRegimeLabel.UNKNOWN
        confidence = Decimal("0.20")
        risk_adjustment = _risk_adjustment(MarketRegimeLabel.UNKNOWN)
        reasons = ("degraded inputs prevent trusted directional regime classification",)
    return RegimeClassification(
        label=label,
        confidence=confidence,
        risk_adjustment=risk_adjustment,
        reasons=reasons,
        evidence=evidence,
        source_refs=source_refs,
        feature_schema_version=snapshot.schema_version,
        generated_at=snapshot.generated_at,
        quality=quality,
    )


def _risk_adjustment(label: MarketRegimeLabel) -> RiskAdjustmentSuggestion:
    if label is MarketRegimeLabel.SHOCK:
        return RiskAdjustmentSuggestion(
            max_position_multiplier=Decimal("0"),
            block_new_entries=True,
            tighten_stops=True,
            reduce_trade_frequency=True,
            rationale="shock regime blocks new entries until conditions normalize",
        )
    if label is MarketRegimeLabel.HIGH_VOLATILITY:
        return RiskAdjustmentSuggestion(
            max_position_multiplier=Decimal("0.25"),
            block_new_entries=True,
            tighten_stops=True,
            reduce_trade_frequency=True,
            rationale="high volatility requires reduced size and blocked new entries",
        )
    if label is MarketRegimeLabel.RANGE_BOUND:
        return RiskAdjustmentSuggestion(
            max_position_multiplier=Decimal("0.50"),
            block_new_entries=False,
            tighten_stops=True,
            reduce_trade_frequency=True,
            rationale="range-bound regime suggests smaller, more selective risk",
        )
    if label in {MarketRegimeLabel.TREND_UP, MarketRegimeLabel.TREND_DOWN}:
        return RiskAdjustmentSuggestion(
            max_position_multiplier=Decimal("1"),
            block_new_entries=False,
            tighten_stops=False,
            reduce_trade_frequency=False,
            rationale="trend regime permits normal risk context subject to later risk checks",
        )
    return RiskAdjustmentSuggestion(
        max_position_multiplier=Decimal("0"),
        block_new_entries=True,
        tighten_stops=True,
        reduce_trade_frequency=True,
        rationale="unknown regime blocks new entries until classification is clearer",
    )


def _quality(
    issues: Sequence[DataQualityIssue],
    *,
    checked_at: datetime,
    source_ref: str,
) -> DataQualityStatus:
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref=source_ref,
        checked_at=normalize_timestamp(checked_at),
    )


def _context_quality_issues(
    context_batches: Sequence[ContextBatch],
) -> tuple[DataQualityIssue, ...]:
    return tuple(issue for batch in context_batches for issue in batch.quality.issues)


def _source_refs(
    snapshot: FeatureSnapshot,
    context_batches: Sequence[ContextBatch],
) -> Mapping[str, str]:
    refs = dict(snapshot.source_refs)
    refs["features"] = snapshot.inputs_ref
    for batch in context_batches:
        refs[f"context.{batch.category.value}.{batch.source_name}"] = batch.quality.source_ref
    return refs


def _json_value(value: Decimal) -> JsonValue:
    return str(value)


def _decimal_or_none(value: JsonValue) -> Decimal | None:
    try:
        return Decimal(str(value))
    except Exception:
        return None
