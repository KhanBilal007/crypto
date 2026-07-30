"""Extensible parameter registry for future ABTP modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue


class ParameterGroup(StrEnum):
    """Bitcoin and crypto dependency parameter groups."""

    PRICE_ACTION = "price_action"
    LIQUIDITY = "liquidity"
    VOLATILITY = "volatility"
    TREND = "trend"
    VOLUME = "volume"
    DERIVATIVES = "derivatives"
    ON_CHAIN = "on_chain"
    CROSS_ASSET = "cross_asset"
    MACRO = "macro"
    NEWS_SENTIMENT = "news_sentiment"
    EXCHANGE_HEALTH = "exchange_health"
    PORTFOLIO = "portfolio"
    DATA_QUALITY = "data_quality"


class FailureBehavior(StrEnum):
    """How missing or failed parameters should affect downstream decisions."""

    REJECT = "reject"
    DEGRADE = "degrade"
    OPTIONAL = "optional"


class StaleBehavior(StrEnum):
    """How stale parameters should be treated."""

    REJECT = "reject"
    DEGRADE = "degrade"
    IGNORE = "ignore"


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    """Static metadata for one dependency parameter."""

    key: str
    group: ParameterGroup
    source_key: str
    description: str
    refresh_interval: timedelta
    trust_level: DataTrustLevel
    stale_behavior: StaleBehavior
    failure_behavior: FailureBehavior
    live_allowed: bool
    optional: bool = False

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("parameter key is required")
        if not self.source_key.strip():
            raise ValueError("parameter source_key is required")
        if self.refresh_interval <= timedelta(0):
            raise ValueError("parameter refresh_interval must be positive")
        if self.live_allowed and self.trust_level is not DataTrustLevel.TRUSTED:
            raise ValueError("live-allowed parameters must be trusted")
        if self.failure_behavior is FailureBehavior.OPTIONAL and not self.optional:
            raise ValueError("optional failure behavior requires optional=True")


@dataclass(frozen=True, slots=True)
class ParameterValue:
    """A deterministic parameter value with quality status."""

    definition: ParameterDefinition
    value: JsonValue
    observed_at: datetime
    quality: DataQualityStatus

    @property
    def is_live_eligible(self) -> bool:
        return self.definition.live_allowed and self.quality.is_trusted


class ParameterRegistry:
    """Lookup registry for parameter definitions."""

    def __init__(self, definitions: tuple[ParameterDefinition, ...]) -> None:
        by_key: dict[str, ParameterDefinition] = {}
        for definition in definitions:
            if definition.key in by_key:
                raise ValueError(f"duplicate parameter key: {definition.key}")
            by_key[definition.key] = definition
        self._by_key = by_key

    def all(self) -> tuple[ParameterDefinition, ...]:
        return tuple(self._by_key.values())

    def get(self, key: str) -> ParameterDefinition:
        try:
            return self._by_key[key]
        except KeyError as exc:
            raise KeyError(f"unknown parameter key: {key}") from exc

    def by_group(self, group: ParameterGroup) -> tuple[ParameterDefinition, ...]:
        return tuple(
            definition for definition in self._by_key.values() if definition.group is group
        )

    def by_source(self, source_key: str) -> tuple[ParameterDefinition, ...]:
        return tuple(
            definition
            for definition in self._by_key.values()
            if definition.source_key == source_key
        )

    def by_live_allowed(self, live_allowed: bool) -> tuple[ParameterDefinition, ...]:
        return tuple(
            definition
            for definition in self._by_key.values()
            if definition.live_allowed is live_allowed
        )

    def by_trust_level(self, trust_level: DataTrustLevel) -> tuple[ParameterDefinition, ...]:
        return tuple(
            definition
            for definition in self._by_key.values()
            if definition.trust_level is trust_level
        )

    def quality_for_missing(
        self, definition: ParameterDefinition, *, checked_at: datetime
    ) -> DataQualityStatus:
        severity = _severity_for_failure(definition)
        return DataQualityStatus(
            trust_level=severity,
            issues=(
                DataQualityIssue(
                    flag="missing_parameter",
                    severity=severity,
                    reason=f"parameter {definition.key} is missing",
                ),
            ),
            source_ref=f"parameter:{definition.key}",
            checked_at=checked_at,
        )

    def evaluate_value(
        self,
        key: str,
        *,
        value: JsonValue | None,
        observed_at: datetime,
        checked_at: datetime,
    ) -> ParameterValue:
        definition = self.get(key)
        if value is None:
            return ParameterValue(
                definition=definition,
                value=None,
                observed_at=observed_at,
                quality=self.quality_for_missing(definition, checked_at=checked_at),
            )
        quality = _quality_for_value(definition, observed_at=observed_at, checked_at=checked_at)
        return ParameterValue(
            definition=definition,
            value=value,
            observed_at=observed_at,
            quality=quality,
        )


def _quality_for_value(
    definition: ParameterDefinition, *, observed_at: datetime, checked_at: datetime
) -> DataQualityStatus:
    age = checked_at - observed_at
    if age > definition.refresh_interval:
        severity = (
            DataTrustLevel.REJECTED
            if definition.stale_behavior is StaleBehavior.REJECT
            else DataTrustLevel.DEGRADED
        )
        return DataQualityStatus(
            trust_level=severity,
            issues=(
                DataQualityIssue(
                    flag="stale_parameter",
                    severity=severity,
                    reason=f"parameter {definition.key} is stale",
                ),
            ),
            source_ref=f"parameter:{definition.key}",
            checked_at=checked_at,
        )
    return DataQualityStatus(
        trust_level=definition.trust_level,
        issues=(),
        source_ref=f"parameter:{definition.key}",
        checked_at=checked_at,
    )


def _severity_for_failure(definition: ParameterDefinition) -> DataTrustLevel:
    if definition.failure_behavior is FailureBehavior.REJECT:
        return DataTrustLevel.REJECTED
    return DataTrustLevel.DEGRADED


def decimal_value(value: Decimal) -> JsonValue:
    """Represent decimal parameter values in JSON-compatible form."""

    return str(value)
