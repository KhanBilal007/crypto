"""Capital preservation framework for adverse market conditions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.protection.crash import CrashProtectionDecision
from abtp.protection.recovery import RecoveryStatus

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class PreservationMode(StrEnum):
    """Advisory capital-preservation mode."""

    NORMAL = "normal"
    WATCH = "watch"
    DEFENSIVE = "defensive"
    EMERGENCY = "emergency"
    KILL_SWITCH_REVIEW = "kill_switch_review"


class EmergencyLevel(StrEnum):
    """Severity level for capital-preservation review."""

    NONE = "none"
    LOW = "low"
    ELEVATED = "elevated"
    SEVERE = "severe"
    CRITICAL = "critical"


class PreservationActionType(StrEnum):
    """Advisory preservation actions."""

    PAUSE_TRADING = "pause_trading"
    REDUCE_ALLOCATION = "reduce_allocation"
    INCREASE_CASH = "increase_cash"
    RAISE_CONFIDENCE_THRESHOLD = "raise_confidence_threshold"
    TIGHTEN_STOPS = "tighten_stops"
    KILL_SWITCH_REVIEW = "kill_switch_review"
    WAIT_FOR_RECOVERY = "wait_for_recovery"
    NOTIFY_OPERATOR = "notify_operator"


@dataclass(frozen=True, slots=True)
class CapitalPreservationPolicy:
    """Conservative Stage 061 capital-preservation thresholds."""

    watch_threshold: Decimal = Decimal("0.25")
    defensive_threshold: Decimal = Decimal("0.45")
    emergency_threshold: Decimal = Decimal("0.65")
    kill_switch_threshold: Decimal = Decimal("0.80")
    min_confidence_threshold: Decimal = Decimal("0.35")
    defensive_cash_target_pct: Decimal = Decimal("0.40")
    severe_cash_target_pct: Decimal = Decimal("0.60")
    allocation_reduction_pct: Decimal = Decimal("0.35")
    severe_allocation_reduction_pct: Decimal = Decimal("0.75")
    stop_tightening_multiplier: Decimal = Decimal("0.50")
    confidence_threshold_increase: Decimal = Decimal("0.15")
    policy_version: str = "stage-061.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("watch_threshold", self.watch_threshold),
            ("defensive_threshold", self.defensive_threshold),
            ("emergency_threshold", self.emergency_threshold),
            ("kill_switch_threshold", self.kill_switch_threshold),
            ("min_confidence_threshold", self.min_confidence_threshold),
            ("defensive_cash_target_pct", self.defensive_cash_target_pct),
            ("severe_cash_target_pct", self.severe_cash_target_pct),
            ("allocation_reduction_pct", self.allocation_reduction_pct),
            ("severe_allocation_reduction_pct", self.severe_allocation_reduction_pct),
            ("stop_tightening_multiplier", self.stop_tightening_multiplier),
            ("confidence_threshold_increase", self.confidence_threshold_increase),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.watch_threshold < self.defensive_threshold < self.emergency_threshold:
            raise ValueError("preservation thresholds must increase from watch to emergency")
        if self.kill_switch_threshold < self.emergency_threshold:
            raise ValueError("kill_switch_threshold cannot be below emergency_threshold")
        if self.severe_cash_target_pct < self.defensive_cash_target_pct:
            raise ValueError("severe_cash_target_pct cannot be below defensive_cash_target_pct")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class CapitalPreservationInput:
    """Supplied adverse-condition evidence for one preservation review."""

    observed_at: datetime
    crash_score: Decimal = DECIMAL_ZERO
    exchange_failure_score: Decimal = DECIMAL_ZERO
    liquidity_crisis_score: Decimal = DECIMAL_ZERO
    extreme_volatility_score: Decimal = DECIMAL_ZERO
    whale_dump_score: Decimal = DECIMAL_ZERO
    macro_shock_score: Decimal = DECIMAL_ZERO
    etf_outflow_score: Decimal = DECIMAL_ZERO
    current_cash_pct: Decimal = Decimal("0.20")
    current_confidence_threshold: Decimal = Decimal("0.50")
    source_quality: DataQualityStatus | None = None
    crash_decision: CrashProtectionDecision | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        for name, value in _score_items(self):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not DECIMAL_ZERO <= self.current_cash_pct <= DECIMAL_ONE:
            raise ValueError("current_cash_pct must be between 0 and 1")
        if not DECIMAL_ZERO <= self.current_confidence_threshold <= DECIMAL_ONE:
            raise ValueError("current_confidence_threshold must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def quality(self) -> DataQualityStatus:
        return self.source_quality or DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="capital_preservation:input",
            checked_at=self.observed_at,
        )


@dataclass(frozen=True, slots=True)
class PreservationAction:
    """One advisory capital-preservation action."""

    action_type: PreservationActionType
    reason: str
    priority: int
    value: Decimal | None = None
    requires_manual_review: bool = True
    can_execute_automatically: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_type", PreservationActionType(self.action_type))
        if not self.reason.strip():
            raise ValueError("preservation action reason is required")
        if self.priority < 0:
            raise ValueError("priority cannot be negative")
        if self.value is not None and not DECIMAL_ZERO <= self.value <= DECIMAL_ONE:
            raise ValueError("preservation action value must be between 0 and 1")
        if self.can_execute_automatically:
            raise ValueError("capital-preservation actions cannot auto-execute in Stage 061")

    def as_dict(self) -> dict[str, object]:
        return {
            "action_type": self.action_type.value,
            "reason": self.reason,
            "priority": self.priority,
            "value": str(self.value) if self.value is not None else None,
            "requires_manual_review": self.requires_manual_review,
            "can_execute_automatically": self.can_execute_automatically,
        }


@dataclass(frozen=True, slots=True)
class CapitalPreservationDecision:
    """Advisory protection mode, emergency level, and recovery status."""

    checked_at: datetime
    protection_mode: PreservationMode
    emergency_level: EmergencyLevel
    recovery_status: RecoveryStatus
    preservation_score: Decimal
    target_cash_pct: Decimal
    allocation_reduction_pct: Decimal
    confidence_threshold: Decimal
    stop_tightening_multiplier: Decimal
    actions: tuple[PreservationAction, ...]
    reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Capital preservation output is advisory safety context only.",
        "Recommendations cannot create orders, order intents, risk decisions, or execution.",
        "Kill-switch review requires manual operator action.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by capital preservation.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        object.__setattr__(self, "protection_mode", PreservationMode(self.protection_mode))
        object.__setattr__(self, "emergency_level", EmergencyLevel(self.emergency_level))
        object.__setattr__(self, "recovery_status", RecoveryStatus(self.recovery_status))
        for name, value in (
            ("preservation_score", self.preservation_score),
            ("target_cash_pct", self.target_cash_pct),
            ("allocation_reduction_pct", self.allocation_reduction_pct),
            ("confidence_threshold", self.confidence_threshold),
            ("stop_tightening_multiplier", self.stop_tightening_multiplier),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.reasons:
            raise ValueError("capital preservation decision requires reasons")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("capital preservation limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def block_new_trades(self) -> bool:
        return self.protection_mode in {
            PreservationMode.DEFENSIVE,
            PreservationMode.EMERGENCY,
            PreservationMode.KILL_SWITCH_REVIEW,
        }

    def require_trading_allowed(self) -> None:
        if self.block_new_trades:
            raise RuntimeError("; ".join(self.reasons))

    def as_dict(self) -> dict[str, object]:
        return {
            "checked_at": self.checked_at.isoformat(),
            "protection_mode": self.protection_mode.value,
            "emergency_level": self.emergency_level.value,
            "recovery_status": self.recovery_status.value,
            "preservation_score": str(self.preservation_score),
            "target_cash_pct": str(self.target_cash_pct),
            "allocation_reduction_pct": str(self.allocation_reduction_pct),
            "confidence_threshold": str(self.confidence_threshold),
            "stop_tightening_multiplier": str(self.stop_tightening_multiplier),
            "actions": [action.as_dict() for action in self.actions],
            "reasons": list(self.reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "protection_mode": self.protection_mode.value,
            "emergency_level": self.emergency_level.value,
            "recovery_status": self.recovery_status.value,
            "preservation_score": str(self.preservation_score),
            "target_cash_pct": str(self.target_cash_pct),
            "allocation_reduction_pct": str(self.allocation_reduction_pct),
            "action_types": "|".join(action.action_type.value for action in self.actions),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital preservation cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital preservation cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital preservation cannot submit orders")


def evaluate_capital_preservation(
    inputs: CapitalPreservationInput,
    *,
    policy: CapitalPreservationPolicy | None = None,
) -> CapitalPreservationDecision:
    """Evaluate fail-closed capital-preservation context without execution."""

    active_policy = policy or CapitalPreservationPolicy()
    score = _preservation_score(inputs)
    issues = list(inputs.quality.issues)
    reasons = _reasons(inputs, score, active_policy)
    if inputs.stale:
        reason = "capital preservation inputs are stale"
        reasons.append(reason)
        issues.append(_issue("stale_capital_preservation", DataTrustLevel.REJECTED, reason))
    if inputs.quality.is_rejected:
        reason = "capital preservation source quality is rejected"
        reasons.append(reason)
        issues.append(_issue("rejected_capital_preservation", DataTrustLevel.REJECTED, reason))
    if inputs.crash_decision is not None and inputs.crash_decision.block_new_trades:
        reason = "market crash protection blocks new trades"
        reasons.append(reason)
        issues.append(_issue("crash_protection_active", DataTrustLevel.REJECTED, reason))
        score = max(score, active_policy.emergency_threshold).quantize(SCORE_QUANT)
    mode = _mode(score, inputs, active_policy)
    emergency = _emergency_level(score, mode, active_policy)
    recovery = _recovery_status(mode, inputs, score, active_policy)
    target_cash = _target_cash(inputs, mode, active_policy)
    allocation_reduction = _allocation_reduction(mode, active_policy)
    confidence_threshold = min(
        DECIMAL_ONE,
        inputs.current_confidence_threshold + _confidence_increase(mode, active_policy),
    ).quantize(SCORE_QUANT)
    stop_multiplier = _stop_multiplier(mode, active_policy)
    actions = _actions(
        mode, reasons, target_cash, allocation_reduction, confidence_threshold, stop_multiplier
    )
    quality = _quality(issues, mode, inputs.observed_at)
    return CapitalPreservationDecision(
        checked_at=inputs.observed_at,
        protection_mode=mode,
        emergency_level=emergency,
        recovery_status=recovery,
        preservation_score=score,
        target_cash_pct=target_cash,
        allocation_reduction_pct=allocation_reduction,
        confidence_threshold=confidence_threshold,
        stop_tightening_multiplier=stop_multiplier,
        actions=actions,
        reasons=tuple(dict.fromkeys(reasons)) or ("capital preservation checks passed",),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _score_items(inputs: CapitalPreservationInput) -> tuple[tuple[str, Decimal], ...]:
    return (
        ("crash_score", inputs.crash_score),
        ("exchange_failure_score", inputs.exchange_failure_score),
        ("liquidity_crisis_score", inputs.liquidity_crisis_score),
        ("extreme_volatility_score", inputs.extreme_volatility_score),
        ("whale_dump_score", inputs.whale_dump_score),
        ("macro_shock_score", inputs.macro_shock_score),
        ("etf_outflow_score", inputs.etf_outflow_score),
    )


def _preservation_score(inputs: CapitalPreservationInput) -> Decimal:
    score = (
        inputs.crash_score * Decimal("0.20")
        + inputs.exchange_failure_score * Decimal("0.16")
        + inputs.liquidity_crisis_score * Decimal("0.16")
        + inputs.extreme_volatility_score * Decimal("0.16")
        + inputs.whale_dump_score * Decimal("0.10")
        + inputs.macro_shock_score * Decimal("0.12")
        + inputs.etf_outflow_score * Decimal("0.10")
    )
    if inputs.quality.is_degraded:
        score += Decimal("0.08")
    if inputs.quality.is_rejected or inputs.stale:
        score = max(score, Decimal("0.75"))
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _mode(
    score: Decimal,
    inputs: CapitalPreservationInput,
    policy: CapitalPreservationPolicy,
) -> PreservationMode:
    if inputs.quality.is_rejected or inputs.stale or score >= policy.kill_switch_threshold:
        return PreservationMode.KILL_SWITCH_REVIEW
    if score >= policy.emergency_threshold:
        return PreservationMode.EMERGENCY
    if score >= policy.defensive_threshold:
        return PreservationMode.DEFENSIVE
    if score >= policy.watch_threshold:
        return PreservationMode.WATCH
    return PreservationMode.NORMAL


def _emergency_level(
    score: Decimal, mode: PreservationMode, policy: CapitalPreservationPolicy
) -> EmergencyLevel:
    if mode is PreservationMode.KILL_SWITCH_REVIEW:
        return EmergencyLevel.CRITICAL
    if score >= policy.emergency_threshold:
        return EmergencyLevel.SEVERE
    if score >= policy.defensive_threshold:
        return EmergencyLevel.ELEVATED
    if score >= policy.watch_threshold:
        return EmergencyLevel.LOW
    return EmergencyLevel.NONE


def _recovery_status(
    mode: PreservationMode,
    inputs: CapitalPreservationInput,
    score: Decimal,
    policy: CapitalPreservationPolicy,
) -> RecoveryStatus:
    if mode in {PreservationMode.EMERGENCY, PreservationMode.KILL_SWITCH_REVIEW}:
        return RecoveryStatus.BLOCKED
    if mode is PreservationMode.DEFENSIVE or score >= policy.watch_threshold:
        return RecoveryStatus.MANUAL_APPROVAL_REQUIRED
    if inputs.quality.is_trusted:
        return RecoveryStatus.ELIGIBLE_FOR_GRADUAL_RESUME
    return RecoveryStatus.MANUAL_APPROVAL_REQUIRED


def _target_cash(
    inputs: CapitalPreservationInput,
    mode: PreservationMode,
    policy: CapitalPreservationPolicy,
) -> Decimal:
    if mode in {PreservationMode.EMERGENCY, PreservationMode.KILL_SWITCH_REVIEW}:
        return max(inputs.current_cash_pct, policy.severe_cash_target_pct).quantize(SCORE_QUANT)
    if mode is PreservationMode.DEFENSIVE:
        return max(inputs.current_cash_pct, policy.defensive_cash_target_pct).quantize(SCORE_QUANT)
    return inputs.current_cash_pct.quantize(SCORE_QUANT)


def _allocation_reduction(mode: PreservationMode, policy: CapitalPreservationPolicy) -> Decimal:
    if mode in {PreservationMode.EMERGENCY, PreservationMode.KILL_SWITCH_REVIEW}:
        return policy.severe_allocation_reduction_pct
    if mode is PreservationMode.DEFENSIVE:
        return policy.allocation_reduction_pct
    return DECIMAL_ZERO


def _confidence_increase(mode: PreservationMode, policy: CapitalPreservationPolicy) -> Decimal:
    if mode in {
        PreservationMode.DEFENSIVE,
        PreservationMode.EMERGENCY,
        PreservationMode.KILL_SWITCH_REVIEW,
    }:
        return policy.confidence_threshold_increase
    if mode is PreservationMode.WATCH:
        return policy.confidence_threshold_increase / Decimal("2")
    return DECIMAL_ZERO


def _stop_multiplier(mode: PreservationMode, policy: CapitalPreservationPolicy) -> Decimal:
    if mode in {
        PreservationMode.DEFENSIVE,
        PreservationMode.EMERGENCY,
        PreservationMode.KILL_SWITCH_REVIEW,
    }:
        return policy.stop_tightening_multiplier
    return DECIMAL_ONE


def _actions(
    mode: PreservationMode,
    reasons: list[str],
    target_cash: Decimal,
    allocation_reduction: Decimal,
    confidence_threshold: Decimal,
    stop_multiplier: Decimal,
) -> tuple[PreservationAction, ...]:
    if mode is PreservationMode.NORMAL:
        return ()
    reason = "; ".join(dict.fromkeys(reasons)) or f"capital preservation mode is {mode.value}"
    actions = [
        PreservationAction(PreservationActionType.NOTIFY_OPERATOR, reason, 0),
        PreservationAction(PreservationActionType.WAIT_FOR_RECOVERY, reason, 6),
    ]
    if mode in {
        PreservationMode.DEFENSIVE,
        PreservationMode.EMERGENCY,
        PreservationMode.KILL_SWITCH_REVIEW,
    }:
        actions.extend(
            (
                PreservationAction(PreservationActionType.PAUSE_TRADING, reason, 1),
                PreservationAction(
                    PreservationActionType.REDUCE_ALLOCATION,
                    reason,
                    2,
                    value=allocation_reduction,
                ),
                PreservationAction(
                    PreservationActionType.INCREASE_CASH,
                    reason,
                    3,
                    value=target_cash,
                ),
                PreservationAction(
                    PreservationActionType.RAISE_CONFIDENCE_THRESHOLD,
                    reason,
                    4,
                    value=confidence_threshold,
                ),
                PreservationAction(
                    PreservationActionType.TIGHTEN_STOPS,
                    reason,
                    5,
                    value=stop_multiplier,
                ),
            )
        )
    if mode is PreservationMode.KILL_SWITCH_REVIEW:
        actions.append(PreservationAction(PreservationActionType.KILL_SWITCH_REVIEW, reason, 7))
    return tuple(sorted(actions, key=lambda action: action.priority))


def _reasons(
    inputs: CapitalPreservationInput,
    score: Decimal,
    policy: CapitalPreservationPolicy,
) -> list[str]:
    reasons: list[str] = []
    for name, value in _score_items(inputs):
        if value >= policy.defensive_threshold:
            reasons.append(f"{name} is elevated")
    if score >= policy.watch_threshold:
        reasons.append(f"capital preservation score is {score}")
    if inputs.quality.is_degraded:
        reasons.append("capital preservation source quality is degraded")
    return reasons


def _quality(
    issues: list[DataQualityIssue],
    mode: PreservationMode,
    checked_at: datetime,
) -> DataQualityStatus:
    if mode in {PreservationMode.EMERGENCY, PreservationMode.KILL_SWITCH_REVIEW} or any(
        issue.severity is DataTrustLevel.REJECTED for issue in issues
    ):
        trust = DataTrustLevel.REJECTED
    elif mode in {PreservationMode.WATCH, PreservationMode.DEFENSIVE} or issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="capital_preservation:stage-061",
        checked_at=normalize_timestamp(checked_at),
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
