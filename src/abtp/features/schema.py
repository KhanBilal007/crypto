"""Versioned feature schema contracts for model-ready snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import AssetPair, FeatureVector
from abtp.domain.models import JsonValue

FEATURE_SCHEMA_VERSION = "stage-015.v1"


class FeatureDataType(StrEnum):
    """Supported model-ready feature value types."""

    DECIMAL = "decimal"


class FeatureSourceKind(StrEnum):
    """Source families used to build feature values."""

    CANDLES = "candles"
    INDICATOR = "indicator"
    ORDER_BOOK = "order_book"
    STREAM_HEALTH = "stream_health"
    PARAMETER = "parameter"
    PORTFOLIO = "portfolio"
    DATA_QUALITY = "data_quality"


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    """Stable definition for one feature."""

    name: str
    data_type: FeatureDataType
    source_kind: FeatureSourceKind
    source_name: str
    required: bool
    description: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.name, "feature name"),
            (self.source_name, "feature source_name"),
            (self.description, "feature description"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")


@dataclass(frozen=True, slots=True)
class FeatureSchema:
    """Versioned set of stable feature definitions."""

    version: str
    definitions: tuple[FeatureDefinition, ...]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("feature schema version is required")
        by_name: set[str] = set()
        for definition in self.definitions:
            if definition.name in by_name:
                raise ValueError(f"duplicate feature name: {definition.name}")
            by_name.add(definition.name)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(definition.name for definition in self.definitions)

    @property
    def required_names(self) -> tuple[str, ...]:
        return tuple(definition.name for definition in self.definitions if definition.required)

    def get(self, name: str) -> FeatureDefinition:
        for definition in self.definitions:
            if definition.name == name:
                return definition
        raise KeyError(f"unknown feature: {name}")

    def validate_values(self, values: Mapping[str, Decimal]) -> tuple[DataQualityIssue, ...]:
        issues: list[DataQualityIssue] = []
        known = set(self.names)
        for name in values:
            if name not in known:
                issues.append(
                    DataQualityIssue(
                        flag="unknown_feature",
                        severity=DataTrustLevel.REJECTED,
                        reason=f"feature {name} is not in schema {self.version}",
                    )
                )
        for name in self.required_names:
            if name not in values:
                issues.append(
                    DataQualityIssue(
                        flag="missing_required_feature",
                        severity=DataTrustLevel.REJECTED,
                        reason=f"required feature {name} is missing",
                    )
                )
        for name, value in values.items():
            if not value.is_finite():
                issues.append(
                    DataQualityIssue(
                        flag="invalid_feature_value",
                        severity=DataTrustLevel.REJECTED,
                        reason=f"feature {name} is not finite",
                    )
                )
        return tuple(issues)


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    """Model-ready feature vector plus quality and trace metadata."""

    pair: AssetPair
    generated_at: datetime
    schema_version: str
    values: Mapping[str, Decimal]
    quality: DataQualityStatus
    lookback_start: datetime
    lookback_end: datetime
    source_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "lookback_start", normalize_timestamp(self.lookback_start))
        object.__setattr__(self, "lookback_end", normalize_timestamp(self.lookback_end))
        if self.lookback_end > self.generated_at:
            raise ValueError("feature lookback_end cannot be after generated_at")
        if self.lookback_start > self.lookback_end:
            raise ValueError("feature lookback_start cannot be after lookback_end")
        if not self.schema_version.strip():
            raise ValueError("feature schema_version is required")

    @property
    def is_trusted(self) -> bool:
        return self.quality.is_trusted

    @property
    def is_degraded(self) -> bool:
        return self.quality.is_degraded

    @property
    def is_rejected(self) -> bool:
        return self.quality.is_rejected

    @property
    def flags(self) -> tuple[str, ...]:
        return self.quality.flags

    @property
    def is_live_eligible(self) -> bool:
        return self.is_trusted

    def require_live_eligible(self) -> None:
        if not self.is_live_eligible:
            raise ValueError(f"feature vector is not live-eligible: {', '.join(self.flags)}")

    def to_domain_feature_vector(self) -> FeatureVector:
        if not self.values:
            raise ValueError("cannot persist an empty feature vector")
        return FeatureVector(
            pair=self.pair,
            generated_at=self.generated_at,
            values=dict(self.values),
            inputs_ref=self.inputs_ref,
            feature_version=self.schema_version,
        )

    @property
    def inputs_ref(self) -> str:
        refs = ",".join(f"{key}={value}" for key, value in sorted(self.source_refs.items()))
        return f"features:{self.schema_version}:{refs}"

    def metadata_json(self) -> Mapping[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at.isoformat(),
            "lookback_start": self.lookback_start.isoformat(),
            "lookback_end": self.lookback_end.isoformat(),
            "quality": self.quality.trust_level.value,
            "flags": list(self.flags),
            "source_refs": dict(self.source_refs),
        }


def default_feature_schema() -> FeatureSchema:
    """Return the default Stage 015 feature schema."""

    return FeatureSchema(
        version=FEATURE_SCHEMA_VERSION,
        definitions=(
            _feature(
                "market.close",
                FeatureSourceKind.CANDLES,
                "close",
                True,
                "Latest close available at generation time.",
            ),
            _feature(
                "market.return_1",
                FeatureSourceKind.CANDLES,
                "return_1",
                True,
                "Close-to-close return over one candle.",
            ),
            _feature(
                "market.return_3",
                FeatureSourceKind.CANDLES,
                "return_3",
                True,
                "Close-to-close return over three candles.",
            ),
            _feature(
                "market.volume_ratio",
                FeatureSourceKind.CANDLES,
                "volume_ratio",
                True,
                "Latest volume divided by prior-window average volume.",
            ),
            _feature(
                "indicator.sma.sma",
                FeatureSourceKind.INDICATOR,
                "sma.sma",
                True,
                "SMA indicator value.",
            ),
            _feature(
                "indicator.rsi.rsi",
                FeatureSourceKind.INDICATOR,
                "rsi.rsi",
                True,
                "RSI indicator value.",
            ),
            _feature(
                "indicator.atr.atr_pct",
                FeatureSourceKind.INDICATOR,
                "atr.atr_pct",
                True,
                "ATR divided by latest close.",
            ),
            _feature(
                "data_quality.flag_count",
                FeatureSourceKind.DATA_QUALITY,
                "flag_count",
                True,
                "Count of active source quality flags.",
            ),
            _feature(
                "liquidity.spread_bps",
                FeatureSourceKind.ORDER_BOOK,
                "spread_bps",
                False,
                "Top-of-book spread in basis points.",
            ),
            _feature(
                "liquidity.imbalance",
                FeatureSourceKind.ORDER_BOOK,
                "imbalance",
                False,
                "Bid/ask depth imbalance.",
            ),
            _feature(
                "liquidity.slippage_bps",
                FeatureSourceKind.ORDER_BOOK,
                "slippage_bps",
                False,
                "Conservative half-spread slippage estimate.",
            ),
            _feature(
                "stream.latency_ms",
                FeatureSourceKind.STREAM_HEALTH,
                "latency_ms",
                False,
                "Latest stream latency in milliseconds.",
            ),
            _feature(
                "stream.disconnect_count",
                FeatureSourceKind.STREAM_HEALTH,
                "disconnect_count",
                False,
                "Observed stream disconnect count.",
            ),
            _feature(
                "portfolio.exposure_base",
                FeatureSourceKind.PORTFOLIO,
                "exposure_base",
                False,
                "Base-asset quantity from optional portfolio context.",
            ),
            _feature(
                "portfolio.cash_quote",
                FeatureSourceKind.PORTFOLIO,
                "cash_quote",
                False,
                "Quote-asset valuation from optional portfolio context.",
            ),
            _feature(
                "parameter.price.close",
                FeatureSourceKind.PARAMETER,
                "price.close",
                False,
                "Optional parameter registry close value.",
            ),
            _feature(
                "parameter.liquidity.spread_bps",
                FeatureSourceKind.PARAMETER,
                "liquidity.spread_bps",
                False,
                "Optional parameter registry spread value.",
            ),
            _feature(
                "parameter.data_quality.flag_count",
                FeatureSourceKind.PARAMETER,
                "data_quality.flag_count",
                False,
                "Optional parameter registry quality flag count.",
            ),
        ),
    )


def _feature(
    name: str,
    source_kind: FeatureSourceKind,
    source_name: str,
    required: bool,
    description: str,
) -> FeatureDefinition:
    return FeatureDefinition(
        name=name,
        data_type=FeatureDataType.DECIMAL,
        source_kind=source_kind,
        source_name=source_name,
        required=required,
        description=description,
    )
