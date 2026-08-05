"""Feature engineering pipeline over normalized market and indicator inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from abtp.data import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    OrderBookMetrics,
    StreamHealth,
    normalize_timestamp,
)
from abtp.domain import AssetPair, Candle, PortfolioSnapshot
from abtp.features.schema import FeatureSchema, FeatureSnapshot, default_feature_schema
from abtp.indicators import IndicatorResult
from abtp.parameters import ParameterValue

ONE = Decimal("1")
BPS = Decimal("10000")


@dataclass(frozen=True, slots=True)
class FeaturePipelineInput:
    """Inputs for one historical or live feature generation cycle."""

    pair: AssetPair
    candles: tuple[Candle, ...]
    candle_quality: DataQualityStatus
    indicator_results: tuple[IndicatorResult, ...]
    generated_at: datetime
    order_book_metrics: OrderBookMetrics | None = None
    stream_health: StreamHealth | None = None
    parameter_values: tuple[ParameterValue, ...] = ()
    portfolio_snapshot: PortfolioSnapshot | None = None


class FeaturePipeline:
    """Build model-ready features without strategy, AI, risk, or execution logic."""

    def __init__(self, schema: FeatureSchema | None = None) -> None:
        self._schema = schema or default_feature_schema()

    @property
    def schema(self) -> FeatureSchema:
        return self._schema

    def build(self, inputs: FeaturePipelineInput) -> FeatureSnapshot:
        generated_at = normalize_timestamp(inputs.generated_at)
        leakage_issues = _leakage_issues(inputs, generated_at)
        if leakage_issues:
            return _snapshot(
                inputs,
                self._schema,
                values={},
                issues=leakage_issues,
                generated_at=generated_at,
                source_refs=_source_refs(inputs),
            )

        values: dict[str, Decimal] = {}
        values.update(_candle_features(inputs.candles))
        values.update(_indicator_features(inputs.indicator_results, inputs.candles))
        if inputs.order_book_metrics is not None:
            values.update(_order_book_features(inputs.order_book_metrics))
        if inputs.stream_health is not None:
            values.update(_stream_health_features(inputs.stream_health))
        values.update(_parameter_features(inputs.parameter_values))
        if inputs.portfolio_snapshot is not None:
            values.update(_portfolio_features(inputs.portfolio_snapshot, inputs.pair))

        source_issues = _source_quality_issues(inputs)
        values["data_quality.flag_count"] = Decimal(len(source_issues))
        schema_values = {key: value for key, value in values.items() if key in self._schema.names}
        schema_issues = self._schema.validate_values(schema_values)
        return _snapshot(
            inputs,
            self._schema,
            values=schema_values,
            issues=(*source_issues, *schema_issues),
            generated_at=generated_at,
            source_refs=_source_refs(inputs),
        )


def _snapshot(
    inputs: FeaturePipelineInput,
    schema: FeatureSchema,
    *,
    values: Mapping[str, Decimal],
    issues: tuple[DataQualityIssue, ...],
    generated_at: datetime,
    source_refs: Mapping[str, str],
) -> FeatureSnapshot:
    quality = _quality_status(
        issues, generated_at=generated_at, source_ref=f"features:{schema.version}"
    )
    lookback_start, lookback_end = _lookback(inputs, generated_at)
    return FeatureSnapshot(
        pair=inputs.pair,
        generated_at=generated_at,
        schema_version=schema.version,
        values=dict(values),
        quality=quality,
        lookback_start=lookback_start,
        lookback_end=lookback_end,
        source_refs=dict(source_refs),
    )


def _candle_features(candles: tuple[Candle, ...]) -> Mapping[str, Decimal]:
    if len(candles) < 4:
        return {}
    latest = candles[-1]
    previous = candles[-2]
    return_1 = _return(latest.close, previous.close)
    return_3 = _return(latest.close, candles[-4].close)
    prior_volumes = tuple(candle.volume for candle in candles[-4:-1])
    average_volume = sum(prior_volumes, Decimal("0")) / Decimal(len(prior_volumes))
    volume_ratio = (
        latest.volume / average_volume if average_volume != Decimal("0") else Decimal("0")
    )
    return {
        "market.close": latest.close,
        "market.return_1": return_1,
        "market.return_3": return_3,
        "market.volume_ratio": volume_ratio,
    }


def _indicator_features(
    indicators: tuple[IndicatorResult, ...],
    candles: tuple[Candle, ...],
) -> Mapping[str, Decimal]:
    values: dict[str, Decimal] = {}
    latest_close = candles[-1].close if candles else Decimal("0")
    for result in indicators:
        if result.is_rejected:
            continue
        for value_name, value in result.values.items():
            values[f"indicator.{result.metadata.name}.{value_name}"] = value
            if (
                result.metadata.name == "atr"
                and value_name == "atr"
                and latest_close != Decimal("0")
            ):
                values["indicator.atr.atr_pct"] = value / latest_close
    return values


def _order_book_features(metrics: OrderBookMetrics) -> Mapping[str, Decimal]:
    midpoint = (metrics.best_bid + metrics.best_ask) / Decimal("2")
    spread_bps = metrics.spread / midpoint * BPS if midpoint != Decimal("0") else Decimal("0")
    return {
        "liquidity.spread_bps": spread_bps,
        "liquidity.imbalance": metrics.imbalance,
        "liquidity.slippage_bps": spread_bps / Decimal("2"),
    }


def _stream_health_features(health: StreamHealth) -> Mapping[str, Decimal]:
    return {
        "stream.latency_ms": Decimal(health.latency_ms),
        "stream.disconnect_count": Decimal(health.disconnect_count),
    }


def _parameter_features(values: tuple[ParameterValue, ...]) -> Mapping[str, Decimal]:
    features: dict[str, Decimal] = {}
    for parameter in values:
        feature_name = f"parameter.{parameter.definition.key}"
        if parameter.value is None:
            continue
        try:
            features[feature_name] = Decimal(str(parameter.value))
        except Exception:
            continue
    return features


def _portfolio_features(
    portfolio: PortfolioSnapshot,
    pair: AssetPair,
) -> Mapping[str, Decimal]:
    exposure_base = Decimal("0")
    cash_quote = Decimal("0")
    for position in portfolio.positions:
        if position.asset.symbol == pair.base.symbol:
            exposure_base += position.quantity
        if position.asset.symbol == pair.quote.symbol:
            cash_quote += position.valuation
    return {
        "portfolio.exposure_base": exposure_base,
        "portfolio.cash_quote": cash_quote,
    }


def _source_quality_issues(inputs: FeaturePipelineInput) -> tuple[DataQualityIssue, ...]:
    issues = [*inputs.candle_quality.issues]
    for result in inputs.indicator_results:
        issues.extend(result.quality.issues)
        if result.is_rejected:
            issues.append(
                DataQualityIssue(
                    flag="rejected_indicator",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"indicator {result.metadata.name} is rejected",
                )
            )
    for parameter in inputs.parameter_values:
        issues.extend(parameter.quality.issues)
    if inputs.stream_health is not None:
        if inputs.stream_health.is_stale:
            issues.append(
                DataQualityIssue(
                    flag="stale_stream",
                    severity=DataTrustLevel.REJECTED,
                    reason="stream health is stale",
                )
            )
        elif inputs.stream_health.is_degraded or not inputs.stream_health.is_connected:
            issues.append(
                DataQualityIssue(
                    flag="degraded_stream",
                    severity=DataTrustLevel.DEGRADED,
                    reason="stream health is degraded",
                )
            )
    return tuple(issues)


def _leakage_issues(
    inputs: FeaturePipelineInput,
    generated_at: datetime,
) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    for candle in inputs.candles:
        if normalize_timestamp(candle.closed_at) > generated_at:
            issues.append(_future_issue("future_candle", "candle closes after generated_at"))
            break
    for result in inputs.indicator_results:
        if result.metadata.calculated_at > generated_at:
            issues.append(
                _future_issue("future_indicator", "indicator was calculated after generated_at")
            )
            break
    for parameter in inputs.parameter_values:
        if normalize_timestamp(parameter.observed_at) > generated_at:
            issues.append(
                _future_issue("future_parameter", "parameter observed after generated_at")
            )
            break
    if (
        inputs.portfolio_snapshot is not None
        and normalize_timestamp(inputs.portfolio_snapshot.captured_at) > generated_at
    ):
        issues.append(_future_issue("future_portfolio", "portfolio captured after generated_at"))
    return tuple(issues)


def _future_issue(flag: str, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=DataTrustLevel.REJECTED, reason=reason)


def _source_refs(inputs: FeaturePipelineInput) -> Mapping[str, str]:
    refs = {"candles": inputs.candle_quality.source_ref}
    for result in inputs.indicator_results:
        refs[f"indicator.{result.metadata.name}"] = result.quality.source_ref
    for parameter in inputs.parameter_values:
        refs[f"parameter.{parameter.definition.key}"] = parameter.quality.source_ref
    if inputs.portfolio_snapshot is not None:
        refs["portfolio"] = inputs.portfolio_snapshot.source_ref
    if inputs.stream_health is not None:
        refs["stream_health"] = f"stream:{inputs.stream_health.status}"
    return refs


def _lookback(inputs: FeaturePipelineInput, generated_at: datetime) -> tuple[datetime, datetime]:
    if not inputs.candles:
        return generated_at, generated_at
    starts = [normalize_timestamp(candle.opened_at) for candle in inputs.candles]
    ends = [normalize_timestamp(candle.closed_at) for candle in inputs.candles]
    return min(starts), max(end for end in ends if end <= generated_at)


def _quality_status(
    issues: tuple[DataQualityIssue, ...],
    *,
    generated_at: datetime,
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
        issues=issues,
        source_ref=source_ref,
        checked_at=generated_at,
    )


def _return(current: Decimal, previous: Decimal) -> Decimal:
    if previous == Decimal("0"):
        return Decimal("0")
    return current / previous - ONE
