"""Advisory portfolio rebalance recommendation contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityStatus, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class RebalanceAction(StrEnum):
    """Advisory rebalance action labels."""

    HOLD = "hold"
    INCREASE = "increase"
    REDUCE = "reduce"
    BLOCK_EXPANSION = "block_expansion"


@dataclass(frozen=True, slots=True)
class RebalanceLine:
    """One asset-level advisory allocation line."""

    asset_symbol: str
    current_weight: Decimal
    target_weight: Decimal
    recommended_weight: Decimal
    current_notional: Decimal
    recommended_notional: Decimal
    notional_delta: Decimal
    action: RebalanceAction
    reasons: tuple[str, ...]
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_symbol", self.asset_symbol.strip().upper())
        if not self.asset_symbol:
            raise ValueError("asset_symbol is required")
        for name, value in (
            ("current_weight", self.current_weight),
            ("target_weight", self.target_weight),
            ("recommended_weight", self.recommended_weight),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.current_notional < DECIMAL_ZERO or self.recommended_notional < DECIMAL_ZERO:
            raise ValueError("notional values cannot be negative")
        if not self.reasons:
            raise ValueError("rebalance line requires reasons")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "asset_symbol": self.asset_symbol,
            "current_weight": str(self.current_weight),
            "target_weight": str(self.target_weight),
            "recommended_weight": str(self.recommended_weight),
            "current_notional": str(self.current_notional),
            "recommended_notional": str(self.recommended_notional),
            "notional_delta": str(self.notional_delta),
            "action": self.action.value,
            "reasons": list(self.reasons),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class PortfolioAllocationRecommendation:
    """Read-only allocation recommendation for dashboard/risk review."""

    generated_at: datetime
    total_equity: Decimal
    available_cash: Decimal
    cash_reserve_pct: Decimal
    recommended_cash_reserve_pct: Decimal
    lines: tuple[RebalanceLine, ...]
    block_expansion: bool
    manual_review_required: bool
    rejection_reasons: tuple[str, ...]
    reduction_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Portfolio allocation recommendations are advisory only.",
        "Recommendations cannot create orders, approve risk, or execute trades.",
        "All future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by allocation optimization.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if self.total_equity <= DECIMAL_ZERO:
            raise ValueError("total_equity must be positive")
        if self.available_cash < DECIMAL_ZERO:
            raise ValueError("available_cash cannot be negative")
        for name, value in (
            ("cash_reserve_pct", self.cash_reserve_pct),
            ("recommended_cash_reserve_pct", self.recommended_cash_reserve_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.evidence:
            raise ValueError("allocation recommendation requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("allocation recommendation limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def acceptable_for_review(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_equity": str(self.total_equity),
            "available_cash": str(self.available_cash),
            "cash_reserve_pct": str(self.cash_reserve_pct),
            "recommended_cash_reserve_pct": str(self.recommended_cash_reserve_pct),
            "lines": [line.as_dict() for line in self.lines],
            "block_expansion": self.block_expansion,
            "manual_review_required": self.manual_review_required,
            "rejection_reasons": list(self.rejection_reasons),
            "reduction_reasons": list(self.reduction_reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "line_count": str(len(self.lines)),
            "block_expansion": str(self.block_expansion),
            "manual_review_required": str(self.manual_review_required),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "reduction_reasons": "|".join(self.reduction_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
            "policy_version": self.policy_version,
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order creation authority."""

        raise ValueError("allocation recommendation cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk approval authority."""

        raise ValueError("allocation recommendation cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("allocation recommendation cannot submit orders")
