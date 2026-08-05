"""Base contracts for non-executable strategy plugins."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from abtp.ai.prediction_service import PredictionServiceResult
from abtp.ai.regime import RegimeClassification
from abtp.data import normalize_timestamp
from abtp.domain import Signal, SignalDirection
from abtp.domain.models import JsonValue
from abtp.features import FeatureSnapshot


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Common strategy plugin metadata and enablement state."""

    name: str
    version: str
    enabled: bool = True
    supported_timeframes: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d")
    description: str = "non-executable strategy plugin"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("strategy name is required")
        if not self.version.strip():
            raise ValueError("strategy version is required")
        if not self.supported_timeframes:
            raise ValueError("strategy must support at least one timeframe")


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Inputs available to a strategy evaluation cycle."""

    features: FeatureSnapshot
    generated_at: datetime
    timeframe: str
    prediction: PredictionServiceResult | None = None
    regime: RegimeClassification | None = None

    def __post_init__(self) -> None:
        if not self.timeframe.strip():
            raise ValueError("strategy timeframe is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    @property
    def feature_snapshot_ref(self) -> str:
        return self.features.inputs_ref


@dataclass(frozen=True, slots=True)
class StrategySignalPlan:
    """Non-executable signal metadata for audit and future risk modules."""

    entry_reason: str
    timeframe: str
    feature_snapshot_ref: str
    stop_suggestion: Decimal | None = None
    target_suggestion: Decimal | None = None
    regime_label: str | None = None
    prediction_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.entry_reason.strip():
            raise ValueError("entry_reason is required")
        if not self.timeframe.strip():
            raise ValueError("timeframe is required")
        if not self.feature_snapshot_ref.strip():
            raise ValueError("feature_snapshot_ref is required")
        if self.stop_suggestion is not None and self.stop_suggestion <= Decimal("0"):
            raise ValueError("stop_suggestion must be positive when supplied")
        if self.target_suggestion is not None and self.target_suggestion <= Decimal("0"):
            raise ValueError("target_suggestion must be positive when supplied")

    def to_json_dict(self) -> Mapping[str, JsonValue]:
        """Return JSON-compatible audit metadata."""

        return {
            "entry_reason": self.entry_reason,
            "timeframe": self.timeframe,
            "feature_snapshot_ref": self.feature_snapshot_ref,
            "stop_suggestion": str(self.stop_suggestion) if self.stop_suggestion else None,
            "target_suggestion": str(self.target_suggestion) if self.target_suggestion else None,
            "regime_label": self.regime_label,
            "prediction_ref": self.prediction_ref,
        }


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    """Result of one strategy plugin evaluation."""

    strategy_name: str
    strategy_version: str
    enabled: bool
    signal: Signal
    plan: StrategySignalPlan
    reasons: tuple[str, ...]
    generated_at: datetime
    signal_ref: str | None = None
    audit_event_id: str | None = None

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if not self.strategy_version.strip():
            raise ValueError("strategy_version is required")
        if not self.reasons:
            raise ValueError("strategy evaluation requires reasons")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))

    @property
    def is_trade_signal(self) -> bool:
        """Whether the strategy emitted directional context for later risk review."""

        return self.enabled and self.signal.direction is not SignalDirection.HOLD

    def with_persistence(
        self,
        *,
        signal_ref: str | None,
        audit_event_id: str | None,
    ) -> StrategyEvaluation:
        """Return the same evaluation with repository identifiers attached."""

        return StrategyEvaluation(
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            enabled=self.enabled,
            signal=self.signal,
            plan=self.plan,
            reasons=self.reasons,
            generated_at=self.generated_at,
            signal_ref=signal_ref,
            audit_event_id=audit_event_id,
        )

    def audit_payload(self) -> Mapping[str, str]:
        """Return append-only audit payload values."""

        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "enabled": str(self.enabled),
            "direction": self.signal.direction.value,
            "confidence": str(self.signal.confidence),
            "inputs_ref": self.signal.inputs_ref,
            "prediction_ref": self.signal.prediction_ref or "not_supplied",
            "entry_reason": self.plan.entry_reason,
            "timeframe": self.plan.timeframe,
            "feature_snapshot_ref": self.plan.feature_snapshot_ref,
            "regime_label": self.plan.regime_label or "not_supplied",
            "stop_suggestion": str(self.plan.stop_suggestion or ""),
            "target_suggestion": str(self.plan.target_suggestion or ""),
            "reasons": ",".join(self.reasons),
        }


class StrategyPlugin(Protocol):
    """Protocol every strategy plugin must satisfy."""

    @property
    def config(self) -> StrategyConfig:
        """Strategy metadata and enablement state."""

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        """Evaluate inputs and return a non-executable signal evaluation."""
