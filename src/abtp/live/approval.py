"""Manual approval contracts for supervised live orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from abtp.data import normalize_timestamp
from abtp.domain import OrderIntent

LIVE_APPROVAL_CONFIRMATION = "APPROVE_ABTP_TINY_LIVE_ORDER"


@dataclass(frozen=True, slots=True)
class LiveApprovalPolicy:
    """Manual approval requirements for one supervised live order."""

    confirmation_phrase: str = LIVE_APPROVAL_CONFIRMATION
    ttl: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if not self.confirmation_phrase.strip():
            raise ValueError("confirmation_phrase is required")
        if self.ttl <= timedelta(0):
            raise ValueError("approval ttl must be positive")


@dataclass(frozen=True, slots=True)
class LiveApprovalToken:
    """Operator approval bound to one order preview."""

    order_intent_id: UUID
    approved_by: str
    approved_at: datetime
    expires_at: datetime
    confirmation_phrase: str
    max_quantity: Decimal
    max_notional: Decimal
    approval_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        object.__setattr__(self, "approved_at", normalize_timestamp(self.approved_at))
        object.__setattr__(self, "expires_at", normalize_timestamp(self.expires_at))
        if not self.approved_by.strip():
            raise ValueError("approved_by is required")
        if self.expires_at <= self.approved_at:
            raise ValueError("approval expires_at must be after approved_at")
        if self.max_quantity <= Decimal("0"):
            raise ValueError("approval max_quantity must be positive")
        if self.max_notional <= Decimal("0"):
            raise ValueError("approval max_notional must be positive")

    @classmethod
    def create(
        cls,
        *,
        order_intent_id: UUID,
        approved_by: str,
        approved_at: datetime,
        max_quantity: Decimal,
        max_notional: Decimal,
        confirmation_phrase: str = LIVE_APPROVAL_CONFIRMATION,
        policy: LiveApprovalPolicy | None = None,
    ) -> LiveApprovalToken:
        active_policy = policy or LiveApprovalPolicy()
        return cls(
            order_intent_id=order_intent_id,
            approved_by=approved_by,
            approved_at=approved_at,
            expires_at=normalize_timestamp(approved_at) + active_policy.ttl,
            confirmation_phrase=confirmation_phrase,
            max_quantity=max_quantity,
            max_notional=max_notional,
        )


@dataclass(frozen=True, slots=True)
class LiveApprovalCheck:
    """Approval validation result."""

    allowed: bool
    reasons: tuple[str, ...]

    def require_allowed(self) -> None:
        if not self.allowed:
            raise PermissionError("; ".join(self.reasons))


def validate_live_approval(
    intent: OrderIntent,
    token: LiveApprovalToken | None,
    *,
    now: datetime,
    estimated_notional: Decimal,
    policy: LiveApprovalPolicy | None = None,
) -> LiveApprovalCheck:
    """Validate manual approval for one order intent and preview."""

    active_policy = policy or LiveApprovalPolicy()
    if token is None:
        return LiveApprovalCheck(False, ("manual approval token is required",))
    normalized_now = normalize_timestamp(now)
    reasons: list[str] = []
    if token.order_intent_id != intent.id:
        reasons.append("approval token does not match order intent")
    if token.confirmation_phrase != active_policy.confirmation_phrase:
        reasons.append("approval confirmation phrase is invalid")
    if normalized_now < token.approved_at:
        reasons.append("approval token is not yet valid")
    if normalized_now >= token.expires_at:
        reasons.append("approval token is expired")
    if token.expires_at - token.approved_at > active_policy.ttl:
        reasons.append("approval lifetime exceeds policy limit")
    if intent.quantity > token.max_quantity:
        reasons.append("order quantity exceeds approved maximum")
    if estimated_notional > token.max_notional:
        reasons.append("order notional exceeds approved maximum")
    return LiveApprovalCheck(allowed=not reasons, reasons=tuple(reasons))
