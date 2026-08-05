"""Protective action recommendations for crash protection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import normalize_timestamp


class ProtectiveActionType(StrEnum):
    """Protective actions Stage 037 may recommend."""

    BLOCK_NEW_ENTRIES = "block_new_entries"
    PAUSE_TRADING = "pause_trading"
    CANCEL_PENDING_ORDERS = "cancel_pending_orders"
    ENABLE_KILL_SWITCH = "enable_kill_switch"
    NOTIFY_OPERATOR = "notify_operator"
    WAIT_FOR_RECOVERY = "wait_for_recovery"


@dataclass(frozen=True, slots=True)
class ProtectiveAction:
    """One protective action recommendation.

    This is a request/contract only. It does not call exchanges or mutate live
    order state.
    """

    action_type: ProtectiveActionType
    reason: str
    requested_at: datetime
    priority: int
    requires_manual_review: bool = True
    can_execute_automatically: bool = False
    pending_order_count: int = 0

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("protective action reason is required")
        if self.priority < 0:
            raise ValueError("priority cannot be negative")
        if self.pending_order_count < 0:
            raise ValueError("pending_order_count cannot be negative")
        if self.can_execute_automatically and self.action_type in {
            ProtectiveActionType.CANCEL_PENDING_ORDERS,
            ProtectiveActionType.ENABLE_KILL_SWITCH,
        }:
            raise ValueError("destructive protective actions cannot auto-execute in Stage 037")
        object.__setattr__(self, "requested_at", normalize_timestamp(self.requested_at))

    def as_dict(self) -> dict[str, object]:
        return {
            "action_type": self.action_type.value,
            "reason": self.reason,
            "requested_at": self.requested_at.isoformat(),
            "priority": self.priority,
            "requires_manual_review": self.requires_manual_review,
            "can_execute_automatically": self.can_execute_automatically,
            "pending_order_count": self.pending_order_count,
        }


@dataclass(frozen=True, slots=True)
class ProtectiveActionPlan:
    """Ordered protective action plan."""

    actions: tuple[ProtectiveAction, ...]
    protection_active: bool
    block_new_trades: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("action plan reason is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "actions": [action.as_dict() for action in self.actions],
            "protection_active": self.protection_active,
            "block_new_trades": self.block_new_trades,
            "reason": self.reason,
        }


def plan_protective_actions(
    reasons: Sequence[str],
    *,
    checked_at: datetime,
    pending_order_count: int = 0,
    severe: bool = False,
) -> ProtectiveActionPlan:
    """Build an ordered action plan from detected crash-protection reasons."""

    if pending_order_count < 0:
        raise ValueError("pending_order_count cannot be negative")
    reason_text = "; ".join(dict.fromkeys(reason for reason in reasons if reason.strip()))
    if not reason_text:
        return ProtectiveActionPlan(
            actions=(),
            protection_active=False,
            block_new_trades=False,
            reason="market protection checks passed",
        )
    actions = [
        ProtectiveAction(
            action_type=ProtectiveActionType.BLOCK_NEW_ENTRIES,
            reason=reason_text,
            requested_at=checked_at,
            priority=0,
            requires_manual_review=False,
            can_execute_automatically=True,
        ),
        ProtectiveAction(
            action_type=ProtectiveActionType.PAUSE_TRADING,
            reason=reason_text,
            requested_at=checked_at,
            priority=1,
            requires_manual_review=False,
            can_execute_automatically=True,
        ),
        ProtectiveAction(
            action_type=ProtectiveActionType.NOTIFY_OPERATOR,
            reason=reason_text,
            requested_at=checked_at,
            priority=2,
            requires_manual_review=False,
            can_execute_automatically=True,
        ),
        ProtectiveAction(
            action_type=ProtectiveActionType.WAIT_FOR_RECOVERY,
            reason=reason_text,
            requested_at=checked_at,
            priority=5,
            requires_manual_review=False,
            can_execute_automatically=True,
        ),
    ]
    if pending_order_count:
        actions.insert(
            2,
            ProtectiveAction(
                action_type=ProtectiveActionType.CANCEL_PENDING_ORDERS,
                reason=reason_text,
                requested_at=checked_at,
                priority=2,
                requires_manual_review=True,
                can_execute_automatically=False,
                pending_order_count=pending_order_count,
            ),
        )
    if severe:
        actions.insert(
            3,
            ProtectiveAction(
                action_type=ProtectiveActionType.ENABLE_KILL_SWITCH,
                reason=reason_text,
                requested_at=checked_at,
                priority=3,
                requires_manual_review=True,
                can_execute_automatically=False,
            ),
        )
    return ProtectiveActionPlan(
        actions=tuple(sorted(actions, key=lambda action: action.priority)),
        protection_active=True,
        block_new_trades=True,
        reason=reason_text,
    )


def decimal_bps(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Return basis points with defensive zero handling."""

    if denominator <= Decimal("0"):
        return Decimal("999999")
    return numerator / denominator * Decimal("10000")
