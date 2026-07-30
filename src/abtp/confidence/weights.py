"""Confidence component weights and policy contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class ConfidenceComponent(StrEnum):
    """Canonical Stage 049 confidence component names."""

    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    ORDER_BOOK = "order_book"
    AI_PREDICTION = "ai_prediction"
    MARKET_REGIME = "market_regime"
    SENTIMENT = "sentiment"
    ONCHAIN_CONTEXT = "onchain_context"
    PORTFOLIO_CONTEXT = "portfolio_context"
    RISK_CONTEXT = "risk_context"
    DATA_QUALITY = "data_quality"


DEFAULT_COMPONENT_WEIGHTS: Mapping[ConfidenceComponent, Decimal] = {
    ConfidenceComponent.TREND: Decimal("0.11"),
    ConfidenceComponent.MOMENTUM: Decimal("0.10"),
    ConfidenceComponent.VOLATILITY: Decimal("0.09"),
    ConfidenceComponent.VOLUME: Decimal("0.07"),
    ConfidenceComponent.ORDER_BOOK: Decimal("0.09"),
    ConfidenceComponent.AI_PREDICTION: Decimal("0.13"),
    ConfidenceComponent.MARKET_REGIME: Decimal("0.10"),
    ConfidenceComponent.SENTIMENT: Decimal("0.05"),
    ConfidenceComponent.ONCHAIN_CONTEXT: Decimal("0.05"),
    ConfidenceComponent.PORTFOLIO_CONTEXT: Decimal("0.08"),
    ConfidenceComponent.RISK_CONTEXT: Decimal("0.08"),
    ConfidenceComponent.DATA_QUALITY: Decimal("0.05"),
}

DEFAULT_REQUIRED_COMPONENTS: tuple[ConfidenceComponent, ...] = (
    ConfidenceComponent.TREND,
    ConfidenceComponent.MOMENTUM,
    ConfidenceComponent.VOLATILITY,
    ConfidenceComponent.VOLUME,
    ConfidenceComponent.ORDER_BOOK,
    ConfidenceComponent.AI_PREDICTION,
    ConfidenceComponent.MARKET_REGIME,
    ConfidenceComponent.PORTFOLIO_CONTEXT,
    ConfidenceComponent.RISK_CONTEXT,
    ConfidenceComponent.DATA_QUALITY,
)


@dataclass(frozen=True, slots=True)
class ConfidenceWeightPolicy:
    """Fail-closed weighting and actionability policy."""

    component_weights: Mapping[ConfidenceComponent, Decimal] = field(
        default_factory=lambda: dict(DEFAULT_COMPONENT_WEIGHTS)
    )
    required_components: tuple[ConfidenceComponent, ...] = DEFAULT_REQUIRED_COMPONENTS
    minimum_actionable_score: Decimal = Decimal("0.55")
    minimum_included_weight: Decimal = Decimal("0.70")
    low_component_threshold: Decimal = Decimal("0.20")
    disagreement_threshold: Decimal = Decimal("0.65")
    degraded_quality_multiplier: Decimal = Decimal("0.50")
    policy_version: str = "stage-049.v1"

    def __post_init__(self) -> None:
        if not self.component_weights:
            raise ValueError("component_weights are required")
        weights = {ConfidenceComponent(key): value for key, value in self.component_weights.items()}
        if any(weight < DECIMAL_ZERO for weight in weights.values()):
            raise ValueError("confidence weights cannot be negative")
        if sum(weights.values(), DECIMAL_ZERO) <= DECIMAL_ZERO:
            raise ValueError("total confidence weight must be positive")
        required = tuple(ConfidenceComponent(component) for component in self.required_components)
        missing_required_weights = tuple(
            component for component in required if component not in weights
        )
        if missing_required_weights:
            raise ValueError("required components must have configured weights")
        for name, value in (
            ("minimum_actionable_score", self.minimum_actionable_score),
            ("minimum_included_weight", self.minimum_included_weight),
            ("low_component_threshold", self.low_component_threshold),
            ("disagreement_threshold", self.disagreement_threshold),
            ("degraded_quality_multiplier", self.degraded_quality_multiplier),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "component_weights", weights)
        object.__setattr__(self, "required_components", required)

    @property
    def total_weight(self) -> Decimal:
        return sum(self.component_weights.values(), DECIMAL_ZERO)

    def weight_for(self, component: ConfidenceComponent) -> Decimal:
        return self.component_weights[component]

    def is_required(self, component: ConfidenceComponent) -> bool:
        return component in self.required_components
