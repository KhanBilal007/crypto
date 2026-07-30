"""Provider-neutral external context contracts and deterministic stubs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.parameters import (
    FailureBehavior,
    ParameterRegistry,
    ParameterValue,
    StaleBehavior,
)


class ContextCategory(StrEnum):
    """External context families supported by Stage 016."""

    DERIVATIVES = "derivatives"
    ON_CHAIN = "on_chain"
    MACRO = "macro"
    SENTIMENT = "sentiment"


@dataclass(frozen=True, slots=True)
class ContextProviderConfig:
    """Safety and freshness defaults for one context provider."""

    stale_after: timedelta
    trust_level: DataTrustLevel = DataTrustLevel.DEGRADED
    stale_behavior: StaleBehavior = StaleBehavior.DEGRADE
    failure_behavior: FailureBehavior = FailureBehavior.OPTIONAL
    live_allowed: bool = False

    def __post_init__(self) -> None:
        if self.stale_after <= timedelta(0):
            raise ValueError("context stale_after must be positive")
        if self.live_allowed and self.trust_level is not DataTrustLevel.TRUSTED:
            raise ValueError("live-allowed context must be trusted")


@dataclass(frozen=True, slots=True)
class ContextFixture:
    """Static input row for deterministic context providers."""

    key: str
    value: object
    observed_at: datetime
    parameter_key: str | None = None
    confidence: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("context fixture key is required")


@dataclass(frozen=True, slots=True)
class ContextItem:
    """Normalized optional external context item."""

    category: ContextCategory
    key: str
    value: JsonValue
    source_name: str
    observed_at: datetime
    received_at: datetime
    trust_level: DataTrustLevel
    stale_behavior: StaleBehavior
    failure_behavior: FailureBehavior
    quality: DataQualityStatus
    live_allowed: bool
    parameter_key: str | None = None
    confidence: Decimal | None = None

    def __post_init__(self) -> None:
        for value, field_name in ((self.key, "context key"), (self.source_name, "source name")):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        if self.confidence is not None and not _confidence_in_range(self.confidence):
            raise ValueError("context confidence must be between 0 and 1")
        if self.live_allowed and self.trust_level is not DataTrustLevel.TRUSTED:
            raise ValueError("live-allowed context must be trusted")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "received_at", normalize_timestamp(self.received_at))

    @property
    def is_live_eligible(self) -> bool:
        return (
            self.live_allowed
            and self.trust_level is DataTrustLevel.TRUSTED
            and self.quality.is_trusted
        )

    @property
    def flags(self) -> tuple[str, ...]:
        return self.quality.flags

    def to_parameter_value(self, registry: ParameterRegistry) -> ParameterValue | None:
        """Map the item to a Stage 013 parameter value when a key is defined."""

        if self.parameter_key is None:
            return None
        return ParameterValue(
            definition=registry.get(self.parameter_key),
            value=self.value,
            observed_at=self.observed_at,
            quality=self.quality,
        )


@dataclass(frozen=True, slots=True)
class ContextBatch:
    """Provider fetch result with optional items and aggregate quality."""

    source_name: str
    category: ContextCategory
    received_at: datetime
    items: tuple[ContextItem, ...]
    quality: DataQualityStatus

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

    def to_parameter_values(self, registry: ParameterRegistry) -> tuple[ParameterValue, ...]:
        return tuple(
            value
            for value in (item.to_parameter_value(registry) for item in self.items)
            if value is not None
        )


class ContextProvider(Protocol):
    """Provider-neutral external context interface."""

    @property
    def source_name(self) -> str:
        """Provider/source name without credentials or vendor-specific client state."""

    @property
    def category(self) -> ContextCategory:
        """Context category emitted by the provider."""

    def fetch(self, *, received_at: datetime) -> ContextBatch:
        """Fetch or synthesize context items for a deterministic timestamp."""


class DeterministicContextProvider:
    """Static fixture-backed provider with no network or vendor API calls."""

    def __init__(
        self,
        *,
        source_name: str,
        category: ContextCategory,
        fixtures: Sequence[ContextFixture],
        config: ContextProviderConfig,
        failure_message: str | None = None,
    ) -> None:
        if not source_name.strip():
            raise ValueError("context source_name is required")
        self._source_name = source_name
        self._category = category
        self._fixtures = tuple(fixtures)
        self._config = config
        self._failure_message = failure_message

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def category(self) -> ContextCategory:
        return self._category

    def fetch(self, *, received_at: datetime) -> ContextBatch:
        normalized_received = normalize_timestamp(received_at)
        if self._failure_message:
            issue = _issue(
                "provider_failure",
                _failure_severity(self._config.failure_behavior),
                self._failure_message,
            )
            return self._batch((), (issue,), normalized_received)
        if not self._fixtures:
            issue = _issue(
                "missing_context",
                DataTrustLevel.DEGRADED,
                f"{self.source_name} returned no context fixtures",
            )
            return self._batch((), (issue,), normalized_received)

        items = tuple(
            self._item_from_fixture(fixture, normalized_received) for fixture in self._fixtures
        )
        return self._batch(
            items,
            tuple(issue for item in items for issue in item.quality.issues),
            normalized_received,
        )

    def _item_from_fixture(self, fixture: ContextFixture, received_at: datetime) -> ContextItem:
        issues: list[DataQualityIssue] = []
        observed_at = normalize_timestamp(fixture.observed_at)
        try:
            value = _json_value(fixture.value)
        except ValueError as exc:
            value = None
            issues.append(_issue("malformed_context", DataTrustLevel.REJECTED, str(exc)))
        if fixture.confidence is not None and not _confidence_in_range(fixture.confidence):
            issues.append(
                _issue(
                    "invalid_confidence",
                    DataTrustLevel.REJECTED,
                    "context confidence must be between 0 and 1",
                )
            )
        if received_at - observed_at > self._config.stale_after:
            issues.append(
                _issue(
                    "stale_context",
                    _stale_severity(self._config.stale_behavior),
                    f"context {fixture.key} is stale",
                )
            )
        quality = _quality_status(
            tuple(issues),
            default_trust=self._config.trust_level,
            source_ref=f"context:{self.source_name}:{fixture.key}",
            checked_at=received_at,
        )
        return ContextItem(
            category=self.category,
            key=fixture.key,
            value=value,
            source_name=self.source_name,
            observed_at=observed_at,
            received_at=received_at,
            trust_level=self._config.trust_level,
            stale_behavior=self._config.stale_behavior,
            failure_behavior=self._config.failure_behavior,
            quality=quality,
            live_allowed=self._config.live_allowed,
            parameter_key=fixture.parameter_key,
            confidence=_valid_confidence(fixture.confidence),
        )

    def _batch(
        self,
        items: tuple[ContextItem, ...],
        issues: tuple[DataQualityIssue, ...],
        received_at: datetime,
    ) -> ContextBatch:
        quality = _quality_status(
            issues,
            default_trust=self._config.trust_level,
            source_ref=f"context:{self.source_name}",
            checked_at=received_at,
        )
        return ContextBatch(
            source_name=self.source_name,
            category=self.category,
            received_at=received_at,
            items=items,
            quality=quality,
        )


def default_optional_context_config(stale_after: timedelta) -> ContextProviderConfig:
    """Low-trust optional default for external providers."""

    return ContextProviderConfig(
        stale_after=stale_after,
        trust_level=DataTrustLevel.DEGRADED,
        stale_behavior=StaleBehavior.DEGRADE,
        failure_behavior=FailureBehavior.OPTIONAL,
        live_allowed=False,
    )


def _json_value(value: object) -> JsonValue:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    raise ValueError(f"unsupported context value type: {type(value).__name__}")


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)


def _quality_status(
    issues: tuple[DataQualityIssue, ...],
    *,
    default_trust: DataTrustLevel,
    source_ref: str,
    checked_at: datetime,
) -> DataQualityStatus:
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = default_trust
    return DataQualityStatus(
        trust_level=trust_level,
        issues=issues,
        source_ref=source_ref,
        checked_at=checked_at,
    )


def _failure_severity(behavior: FailureBehavior) -> DataTrustLevel:
    if behavior is FailureBehavior.REJECT:
        return DataTrustLevel.REJECTED
    return DataTrustLevel.DEGRADED


def _stale_severity(behavior: StaleBehavior) -> DataTrustLevel:
    if behavior is StaleBehavior.REJECT:
        return DataTrustLevel.REJECTED
    return DataTrustLevel.DEGRADED


def _valid_confidence(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if _confidence_in_range(value):
        return value
    return None


def _confidence_in_range(value: Decimal) -> bool:
    return value.is_finite() and Decimal("0") <= value <= Decimal("1")


def context_items_to_parameter_values(
    items: Sequence[ContextItem],
    registry: ParameterRegistry,
) -> tuple[ParameterValue, ...]:
    """Convert mappable context items to Stage 013 parameter values."""

    values: list[ParameterValue] = []
    for item in items:
        value = item.to_parameter_value(registry)
        if value is not None:
            values.append(value)
    return tuple(values)
