"""Simple paper trading command center for Stage 071."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityStatus, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.intelligence import FinalInvestmentDecision
from abtp.paper.trade_checklist import (
    PaperTradeChecklistInput,
    PaperTradeChecklistPolicy,
    PaperTradeChecklistResult,
    evaluate_paper_trade_checklist,
)

DECIMAL_ZERO = Decimal("0")


class PaperCommandLabel(StrEnum):
    """Plain-language labels shown to operators."""

    BUY_REVIEW = "BUY REVIEW"
    HOLD = "HOLD"
    AVOID = "AVOID"
    PROTECT_CAPITAL = "PROTECT CAPITAL"


@dataclass(frozen=True, slots=True)
class PaperCommandCenterInput:
    """Inputs for one simple paper command-center recommendation."""

    checklist_input: PaperTradeChecklistInput
    audit_ref: str
    generated_at: datetime
    policy: PaperTradeChecklistPolicy | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.audit_ref.strip():
            raise ValueError("audit_ref is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class PaperCommandRecommendation:
    """Simple deterministic command-center payload."""

    label: PaperCommandLabel
    paper_trade_ready: bool
    explanation: str
    checklist: PaperTradeChecklistResult
    confidence_score: Decimal
    support_score: Decimal
    risk_score: Decimal
    risk_level: str
    holding_period: str
    stop_loss_required: bool
    max_paper_position_size: Decimal
    take_profit_review: str
    blocked_reasons: tuple[str, ...]
    audit_ref: str
    generated_at: datetime
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Command-center labels are paper-mode operator guidance only.",
        "BUY REVIEW is not permission to place real orders.",
        "Future paper trades still require strategy signal, risk approval, and stop-loss metadata.",
        "The command center cannot create signals, approve risk, create order intents, "
        "or submit orders.",
        "No profit is guaranteed by command-center labels.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", PaperCommandLabel(self.label))
        if self.max_paper_position_size < DECIMAL_ZERO:
            raise ValueError("max_paper_position_size cannot be negative")
        if not self.explanation.strip():
            raise ValueError("command explanation is required")
        if not self.risk_level.strip():
            raise ValueError("risk_level is required")
        if not self.audit_ref.strip():
            raise ValueError("audit_ref is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "paper_trade_ready": self.paper_trade_ready,
            "explanation": self.explanation,
            "checklist": self.checklist.as_dict(),
            "confidence_score": str(self.confidence_score),
            "support_score": str(self.support_score),
            "risk_score": str(self.risk_score),
            "risk_level": self.risk_level,
            "holding_period": self.holding_period,
            "stop_loss_required": self.stop_loss_required,
            "max_paper_position_size": str(self.max_paper_position_size),
            "take_profit_review": self.take_profit_review,
            "blocked_reasons": list(self.blocked_reasons),
            "audit_ref": self.audit_ref,
            "generated_at": self.generated_at.isoformat(),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "label": self.label.value,
            "paper_trade_ready": str(self.paper_trade_ready),
            "confidence_score": str(self.confidence_score),
            "support_score": str(self.support_score),
            "risk_score": str(self.risk_score),
            "risk_level": self.risk_level,
            "holding_period": self.holding_period,
            "max_paper_position_size": str(self.max_paper_position_size),
            "blocked_reasons": "|".join(self.blocked_reasons),
            "audit_ref": self.audit_ref,
            "quality": self.quality.trust_level.value,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command center cannot create strategy signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command center cannot approve risk")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command center cannot create order intents")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command center cannot submit orders")

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper command center cannot enable live trading")


def build_paper_command_recommendation(
    inputs: PaperCommandCenterInput,
) -> PaperCommandRecommendation:
    """Build one paper-first command recommendation."""

    checklist = evaluate_paper_trade_checklist(
        inputs.checklist_input,
        policy=inputs.policy,
    )
    label = _label(inputs.checklist_input, checklist)
    blocked_reasons = _blocked_reasons(inputs.checklist_input, checklist, label)
    decision = inputs.checklist_input.decision
    ready = label is PaperCommandLabel.BUY_REVIEW and checklist.paper_trade_ready
    return PaperCommandRecommendation(
        label=label,
        paper_trade_ready=ready,
        explanation=_explanation(label, ready, blocked_reasons),
        checklist=checklist,
        confidence_score=decision.confidence_score,
        support_score=decision.support_score,
        risk_score=decision.risk_assessment.risk_score,
        risk_level=decision.risk_assessment.risk_level,
        holding_period=decision.holding_period,
        stop_loss_required=checklist.stop_loss_required,
        max_paper_position_size=checklist.max_paper_position_size,
        take_profit_review=_take_profit_review(label),
        blocked_reasons=blocked_reasons,
        audit_ref=inputs.audit_ref,
        generated_at=inputs.generated_at,
        quality=checklist.data_quality,
        source_refs=inputs.source_refs,
    )


def _label(
    inputs: PaperTradeChecklistInput,
    checklist: PaperTradeChecklistResult,
) -> PaperCommandLabel:
    if _protect_capital_active(inputs):
        return PaperCommandLabel.PROTECT_CAPITAL
    decision = inputs.decision.final_decision
    if decision is FinalInvestmentDecision.FAVORABLE_REVIEW:
        return (
            PaperCommandLabel.BUY_REVIEW if checklist.paper_trade_ready else PaperCommandLabel.AVOID
        )
    if decision is FinalInvestmentDecision.HOLD_REVIEW:
        return PaperCommandLabel.HOLD
    if decision is FinalInvestmentDecision.DEFENSIVE_REVIEW:
        return PaperCommandLabel.AVOID
    return PaperCommandLabel.AVOID


def _protect_capital_active(inputs: PaperTradeChecklistInput) -> bool:
    return (
        inputs.paper_status.kill_switch_active
        or inputs.capital_protection_block
        or inputs.crash_protection_active
        or (
            inputs.decision.risk_assessment.block_new_entries
            and inputs.decision.risk_assessment.risk_score > Decimal("0.55")
        )
        or (
            inputs.capital_preservation is not None and inputs.capital_preservation.block_new_trades
        )
        or (
            inputs.exchange_health is not None
            and inputs.exchange_health.permission_gate.pause_trading
        )
    )


def _blocked_reasons(
    inputs: PaperTradeChecklistInput,
    checklist: PaperTradeChecklistResult,
    label: PaperCommandLabel,
) -> tuple[str, ...]:
    reasons = list(checklist.blocked_reasons)
    if label is PaperCommandLabel.PROTECT_CAPITAL and not reasons:
        reasons.append("capital protection override is active")
    if label is PaperCommandLabel.HOLD:
        reasons.append("operator should hold because Stage 070 decision is hold_review")
    if label is PaperCommandLabel.AVOID and not reasons:
        reasons.append(f"Stage 070 decision is {inputs.decision.final_decision.value}")
    return tuple(dict.fromkeys(reason for reason in reasons if reason.strip()))


def _explanation(
    label: PaperCommandLabel,
    ready: bool,
    blocked_reasons: tuple[str, ...],
) -> str:
    if label is PaperCommandLabel.BUY_REVIEW and ready:
        return "Eligible for paper-trade review only; real trading remains locked."
    if label is PaperCommandLabel.HOLD:
        return "Hold paper action and continue monitoring supplied evidence."
    if label is PaperCommandLabel.PROTECT_CAPITAL:
        return "Protect capital conditions override all paper buy-review labels."
    reason = blocked_reasons[0] if blocked_reasons else "paper checklist did not pass"
    return f"Avoid paper buy review: {reason}."


def _take_profit_review(label: PaperCommandLabel) -> str:
    if label is PaperCommandLabel.BUY_REVIEW:
        return "operator_review_required"
    if label is PaperCommandLabel.PROTECT_CAPITAL:
        return "defer_take_profit_review_until_protection_clears"
    return "not_applicable"
