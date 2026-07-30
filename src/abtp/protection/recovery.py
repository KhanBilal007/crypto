"""Recovery checks for market crash protection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import normalize_timestamp
from abtp.protection.actions import ProtectiveActionPlan, plan_protective_actions
from abtp.protection.crash import (
    CrashProtectionConfig,
    CrashProtectionDecision,
    MarketProtectionSnapshot,
    evaluate_market_protection,
)


class RecoveryStatus(StrEnum):
    """Recovery workflow state."""

    BLOCKED = "blocked"
    MANUAL_APPROVAL_REQUIRED = "manual_approval_required"
    ELIGIBLE_FOR_GRADUAL_RESUME = "eligible_for_gradual_resume"


@dataclass(frozen=True, slots=True)
class RecoveryCheck:
    """One recovery health check."""

    name: str
    passed: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("recovery check name is required")
        if not self.reason.strip():
            raise ValueError("recovery check reason is required")

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """Deterministic crash-protection recovery decision."""

    checked_at: datetime
    status: RecoveryStatus
    can_resume: bool
    gradual_resume: bool
    manual_approval_required: bool
    checks: tuple[RecoveryCheck, ...]
    action_plan: ProtectiveActionPlan
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        if not self.checks:
            raise ValueError("recovery decision requires checks")

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(check.reason for check in self.checks if not check.passed)

    def require_resume_allowed(self) -> None:
        if not self.can_resume:
            raise RuntimeError("; ".join(self.reasons))

    def as_dict(self) -> dict[str, object]:
        return {
            "checked_at": self.checked_at.isoformat(),
            "status": self.status.value,
            "can_resume": self.can_resume,
            "gradual_resume": self.gradual_resume,
            "manual_approval_required": self.manual_approval_required,
            "checks": [check.as_dict() for check in self.checks],
            "action_plan": self.action_plan.as_dict(),
            "policy_version": self.policy_version,
        }


def evaluate_recovery(
    snapshots: Sequence[MarketProtectionSnapshot],
    *,
    previous_decision: CrashProtectionDecision,
    config: CrashProtectionConfig | None = None,
    manual_approval: bool = False,
) -> RecoveryDecision:
    """Evaluate whether protection mode can gradually resume."""

    active_config = config or CrashProtectionConfig()
    checked_at = snapshots[-1].observed_at if snapshots else previous_decision.checked_at
    checks = _checks(
        snapshots,
        previous_decision=previous_decision,
        config=active_config,
        manual_approval=manual_approval,
    )
    failed = tuple(check for check in checks if not check.passed)
    non_manual_failed = tuple(check for check in failed if check.name != "manual_recovery_approval")
    if non_manual_failed:
        status = RecoveryStatus.BLOCKED
        can_resume = False
        manual_required = active_config.require_manual_recovery_approval
    elif active_config.require_manual_recovery_approval and not manual_approval:
        status = RecoveryStatus.MANUAL_APPROVAL_REQUIRED
        can_resume = False
        manual_required = True
    else:
        status = RecoveryStatus.ELIGIBLE_FOR_GRADUAL_RESUME
        can_resume = True
        manual_required = False
    action_plan = (
        plan_protective_actions(
            tuple(check.reason for check in checks if not check.passed)
            or ("manual approval required before recovery",),
            checked_at=checked_at,
            severe=False,
        )
        if not can_resume
        else ProtectiveActionPlan(
            actions=(),
            protection_active=False,
            block_new_trades=False,
            reason="eligible for gradual resume",
        )
    )
    return RecoveryDecision(
        checked_at=checked_at,
        status=status,
        can_resume=can_resume,
        gradual_resume=can_resume,
        manual_approval_required=manual_required,
        checks=checks,
        action_plan=action_plan,
        policy_version=active_config.policy_version,
    )


def _checks(
    snapshots: Sequence[MarketProtectionSnapshot],
    *,
    previous_decision: CrashProtectionDecision,
    config: CrashProtectionConfig,
    manual_approval: bool,
) -> tuple[RecoveryCheck, ...]:
    checks: list[RecoveryCheck] = [
        RecoveryCheck(
            name="previous_protection_active",
            passed=previous_decision.protection_active,
            reason=(
                "previous protection decision is active"
                if previous_decision.protection_active
                else "no prior protection mode to recover from"
            ),
        ),
        RecoveryCheck(
            name="healthy_snapshot_count",
            passed=len(snapshots) >= config.severe_condition_count,
            reason=(
                "enough healthy snapshots supplied"
                if len(snapshots) >= config.severe_condition_count
                else "not enough healthy snapshots for recovery"
            ),
        ),
    ]
    current_decisions = tuple(
        evaluate_market_protection(snapshot, config=config) for snapshot in snapshots
    )
    no_active_conditions = all(not decision.protection_active for decision in current_decisions)
    checks.append(
        RecoveryCheck(
            name="no_active_crash_conditions",
            passed=no_active_conditions,
            reason=(
                "no active crash conditions detected"
                if no_active_conditions
                else "crash conditions are still active"
            ),
        )
    )
    stable_depth = all(
        snapshot.order_book_metrics is None or snapshot.total_depth >= config.min_total_depth
        for snapshot in snapshots
    )
    checks.append(
        RecoveryCheck(
            name="liquidity_recovered",
            passed=stable_depth,
            reason=(
                "liquidity is above recovery threshold"
                if stable_depth
                else "liquidity remains below recovery threshold"
            ),
        )
    )
    low_volatility = all(
        snapshot.realized_volatility_pct < config.abnormal_volatility_pct for snapshot in snapshots
    )
    checks.append(
        RecoveryCheck(
            name="volatility_normalized",
            passed=low_volatility,
            reason=(
                "volatility is below protection threshold"
                if low_volatility
                else "volatility remains abnormal"
            ),
        )
    )
    if config.require_manual_recovery_approval:
        checks.append(
            RecoveryCheck(
                name="manual_recovery_approval",
                passed=manual_approval,
                reason=(
                    "manual recovery approval supplied"
                    if manual_approval
                    else "manual recovery approval required"
                ),
            )
        )
    return tuple(checks)


def recovery_progress_score(decision: RecoveryDecision) -> Decimal:
    """Return the fraction of recovery checks that passed."""

    passed = sum(1 for check in decision.checks if check.passed)
    return Decimal(passed) / Decimal(len(decision.checks))
