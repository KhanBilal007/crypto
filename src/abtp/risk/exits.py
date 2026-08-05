"""Advisory position exit optimizer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain import Asset
from abtp.domain.models import JsonValue
from abtp.risk.exit_quality import (
    ExitQualityPolicy,
    ExitQualityReport,
    analyze_exit_quality,
)
from abtp.risk.trailing_stops import (
    TrailingStopPolicy,
    TrailingStopState,
    initial_stop_price,
    update_atr_trailing_stop,
)

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class ExitAction(StrEnum):
    """Advisory exit action labels."""

    HOLD = "hold"
    TIGHTEN_STOP = "tighten_stop"
    PARTIAL_PROFIT = "partial_profit"
    EXIT_POSITION = "exit_position"
    MANUAL_REVIEW = "manual_review"


class PositionExitPosition(Protocol):
    """Minimal spot position shape consumed by exit optimization."""

    asset: Asset
    quantity: Decimal
    average_entry_price: Decimal


@dataclass(frozen=True, slots=True)
class PositionExitPolicy:
    """Conservative exit recommendation thresholds."""

    trailing_stop_policy: TrailingStopPolicy = field(default_factory=TrailingStopPolicy)
    quality_policy: ExitQualityPolicy = field(default_factory=ExitQualityPolicy)
    partial_profit_pct: Decimal = Decimal("0.05")
    partial_exit_fraction: Decimal = Decimal("0.50")
    max_holding_period: timedelta = timedelta(days=14)
    high_volatility_atr_pct: Decimal = Decimal("0.05")
    shock_atr_pct: Decimal = Decimal("0.10")
    tighten_stop_multiplier: Decimal = Decimal("0.75")
    policy_version: str = "stage-046.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("partial_profit_pct", self.partial_profit_pct),
            ("partial_exit_fraction", self.partial_exit_fraction),
            ("high_volatility_atr_pct", self.high_volatility_atr_pct),
            ("shock_atr_pct", self.shock_atr_pct),
            ("tighten_stop_multiplier", self.tighten_stop_multiplier),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.partial_profit_pct == DECIMAL_ZERO:
            raise ValueError("partial_profit_pct must be positive")
        if self.partial_exit_fraction == DECIMAL_ZERO:
            raise ValueError("partial_exit_fraction must be positive")
        if self.max_holding_period < timedelta(0):
            raise ValueError("max_holding_period cannot be negative")
        if self.shock_atr_pct < self.high_volatility_atr_pct:
            raise ValueError("shock_atr_pct cannot be below high_volatility_atr_pct")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class PositionExitInput:
    """Inputs for one advisory position exit review."""

    position: PositionExitPosition
    current_price: Decimal
    evaluated_at: datetime
    source_quality: DataQualityStatus
    atr: Decimal | None = None
    current_stop_price: Decimal | None = None
    opened_at: datetime | None = None
    highest_price: Decimal | None = None
    regime_label: str = "unknown"
    volatility_regime: str = "unknown"
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.current_price <= DECIMAL_ZERO:
            raise ValueError("current_price must be positive")
        if self.atr is not None and self.atr <= DECIMAL_ZERO:
            raise ValueError("atr must be positive when supplied")
        if self.current_stop_price is not None and self.current_stop_price <= DECIMAL_ZERO:
            raise ValueError("current_stop_price must be positive when supplied")
        if self.highest_price is not None and self.highest_price <= DECIMAL_ZERO:
            raise ValueError("highest_price must be positive when supplied")
        if not self.regime_label.strip():
            raise ValueError("regime_label is required")
        if not self.volatility_regime.strip():
            raise ValueError("volatility_regime is required")
        object.__setattr__(self, "evaluated_at", normalize_timestamp(self.evaluated_at))
        if self.opened_at is not None:
            object.__setattr__(self, "opened_at", normalize_timestamp(self.opened_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def holding_period(self) -> timedelta | None:
        if self.opened_at is None:
            return None
        return self.evaluated_at - self.opened_at


@dataclass(frozen=True, slots=True)
class ExitRecommendation:
    """Explainable advisory exit recommendation with no execution authority."""

    action: ExitAction
    asset_symbol: str
    generated_at: datetime
    recommended_exit_fraction: Decimal
    stop_price: Decimal
    trailing_stop: TrailingStopState
    quality_report: ExitQualityReport
    block_holding: bool
    tighten_stops: bool
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.asset_symbol.strip():
            raise ValueError("asset_symbol is required")
        if not DECIMAL_ZERO <= self.recommended_exit_fraction <= DECIMAL_ONE:
            raise ValueError("recommended_exit_fraction must be between 0 and 1")
        if self.stop_price <= DECIMAL_ZERO:
            raise ValueError("stop_price must be positive")
        if not self.reasons:
            raise ValueError("exit recommendation requires reasons")
        if not self.evidence:
            raise ValueError("exit recommendation requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "asset_symbol": self.asset_symbol,
            "generated_at": self.generated_at.isoformat(),
            "recommended_exit_fraction": str(self.recommended_exit_fraction),
            "stop_price": str(self.stop_price),
            "trailing_stop": self.trailing_stop.as_dict(),
            "quality_report": self.quality_report.as_dict(),
            "block_holding": self.block_holding,
            "tighten_stops": self.tighten_stops,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "action": self.action.value,
            "asset_symbol": self.asset_symbol,
            "recommended_exit_fraction": str(self.recommended_exit_fraction),
            "stop_price": str(self.stop_price),
            "block_holding": str(self.block_holding),
            "tighten_stops": str(self.tighten_stops),
            "reasons": "|".join(self.reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
            "policy_version": self.policy_version,
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("exit recommendation cannot submit orders")

    def cancel_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject cancellation authority."""

        raise ValueError("exit recommendation cannot cancel orders")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("exit recommendation cannot approve risk")


def recommend_position_exit(
    inputs: PositionExitInput,
    *,
    policy: PositionExitPolicy | None = None,
) -> ExitRecommendation:
    """Return an advisory exit recommendation for one open spot position."""

    active_policy = policy or PositionExitPolicy()
    base_stop = inputs.current_stop_price or initial_stop_price(
        entry_price=inputs.position.average_entry_price,
        atr=inputs.atr,
        policy=active_policy.trailing_stop_policy,
    )
    trailing_state = update_atr_trailing_stop(
        TrailingStopState(
            asset=inputs.position.asset,
            entry_price=inputs.position.average_entry_price,
            highest_price=inputs.highest_price
            or max(inputs.position.average_entry_price, inputs.current_price),
            stop_price=base_stop,
            atr=inputs.atr,
            updated_at=inputs.evaluated_at,
            source_refs=inputs.source_refs,
        ),
        current_price=inputs.current_price,
        atr=inputs.atr,
        updated_at=inputs.evaluated_at,
        policy=active_policy.trailing_stop_policy,
        source_refs=inputs.source_refs,
    )
    stop_price = _tightened_stop(inputs, trailing_state.stop_price, active_policy)
    quality_report = analyze_exit_quality(
        entry_price=inputs.position.average_entry_price,
        current_price=inputs.current_price,
        stop_price=stop_price,
        generated_at=inputs.evaluated_at,
        source_quality=inputs.source_quality,
        policy=active_policy.quality_policy,
        source_refs=inputs.source_refs,
    )
    action, fraction, block_holding, tighten_stops, reasons = _decision(
        inputs,
        stop_price=stop_price,
        policy=active_policy,
    )
    quality = _recommendation_quality(inputs, quality_report, block_holding, reasons)
    return ExitRecommendation(
        action=action,
        asset_symbol=inputs.position.asset.symbol,
        generated_at=inputs.evaluated_at,
        recommended_exit_fraction=fraction,
        stop_price=stop_price,
        trailing_stop=trailing_state,
        quality_report=quality_report,
        block_holding=block_holding,
        tighten_stops=tighten_stops,
        reasons=reasons,
        evidence=_evidence(inputs, stop_price, active_policy),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _decision(
    inputs: PositionExitInput,
    *,
    stop_price: Decimal,
    policy: PositionExitPolicy,
) -> tuple[ExitAction, Decimal, bool, bool, tuple[str, ...]]:
    reasons: list[str] = []
    if inputs.source_quality.is_rejected:
        reasons.append("source quality is rejected; holding is non-actionable")
        return ExitAction.MANUAL_REVIEW, DECIMAL_ONE, True, True, tuple(reasons)
    if inputs.current_price <= stop_price:
        reasons.append("current price is at or below stop price")
        return ExitAction.EXIT_POSITION, DECIMAL_ONE, True, True, tuple(reasons)
    atr_pct = _atr_pct(inputs)
    if inputs.regime_label == "shock" or atr_pct >= policy.shock_atr_pct:
        reasons.append("shock regime or shock-level volatility recommends exit")
        return ExitAction.EXIT_POSITION, DECIMAL_ONE, True, True, tuple(reasons)
    if inputs.regime_label == "high_volatility" or atr_pct >= policy.high_volatility_atr_pct:
        reasons.append("high-volatility regime recommends tighter stops")
        return ExitAction.TIGHTEN_STOP, Decimal("0"), False, True, tuple(reasons)
    if inputs.holding_period is not None and inputs.holding_period >= policy.max_holding_period:
        reasons.append("maximum holding period reached")
        return ExitAction.EXIT_POSITION, DECIMAL_ONE, True, True, tuple(reasons)
    if _unrealized_pnl_pct(inputs) >= policy.partial_profit_pct:
        reasons.append("partial profit threshold reached")
        return (
            ExitAction.PARTIAL_PROFIT,
            policy.partial_exit_fraction,
            False,
            True,
            tuple(reasons),
        )
    if inputs.source_quality.is_degraded:
        reasons.append("source quality is degraded; tighten stops")
        return ExitAction.TIGHTEN_STOP, Decimal("0"), False, True, tuple(reasons)
    reasons.append("position may be held with current advisory stop")
    return ExitAction.HOLD, Decimal("0"), False, False, tuple(reasons)


def _tightened_stop(
    inputs: PositionExitInput,
    stop_price: Decimal,
    policy: PositionExitPolicy,
) -> Decimal:
    if (
        inputs.regime_label == "high_volatility"
        or _atr_pct(inputs) >= policy.high_volatility_atr_pct
    ):
        distance = inputs.current_price - stop_price
        if distance > DECIMAL_ZERO:
            return inputs.current_price - distance * policy.tighten_stop_multiplier
    if inputs.source_quality.is_degraded:
        distance = inputs.current_price - stop_price
        if distance > DECIMAL_ZERO:
            return inputs.current_price - distance * policy.tighten_stop_multiplier
    return stop_price


def _recommendation_quality(
    inputs: PositionExitInput,
    quality_report: ExitQualityReport,
    block_holding: bool,
    reasons: tuple[str, ...],
) -> DataQualityStatus:
    issues = [*quality_report.quality.issues]
    if block_holding:
        issues.append(
            DataQualityIssue(
                flag="exit_blocks_holding",
                severity=DataTrustLevel.REJECTED,
                reason="; ".join(reasons),
            )
        )
    elif inputs.source_quality.is_degraded or quality_report.quality.is_degraded:
        issues.append(
            DataQualityIssue(
                flag="exit_quality_degraded",
                severity=DataTrustLevel.DEGRADED,
                reason="exit recommendation is advisory with degraded inputs",
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="risk:position_exit",
        checked_at=inputs.evaluated_at,
    )


def _atr_pct(inputs: PositionExitInput) -> Decimal:
    if inputs.atr is None:
        return DECIMAL_ZERO
    return inputs.atr / inputs.current_price


def _evidence(
    inputs: PositionExitInput,
    stop_price: Decimal,
    policy: PositionExitPolicy,
) -> tuple[str, ...]:
    holding = inputs.holding_period
    return (
        f"entry_price={inputs.position.average_entry_price}",
        f"current_price={inputs.current_price}",
        f"quantity={inputs.position.quantity}",
        f"unrealized_pnl_pct={_unrealized_pnl_pct(inputs)}",
        f"stop_price={stop_price}",
        f"atr_pct={_atr_pct(inputs)}",
        f"regime_label={inputs.regime_label}",
        f"volatility_regime={inputs.volatility_regime}",
        f"holding_period={holding}" if holding is not None else "holding_period=unknown",
        f"partial_profit_pct={policy.partial_profit_pct}",
        f"max_holding_period={policy.max_holding_period}",
    )


def _unrealized_pnl_pct(inputs: PositionExitInput) -> Decimal:
    return inputs.current_price / inputs.position.average_entry_price - DECIMAL_ONE
