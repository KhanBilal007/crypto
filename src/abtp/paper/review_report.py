"""Beginner-readable paper evaluation reports for Stage 073."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from abtp.data import normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.paper.evaluation import PaperEvaluationInput, PaperEvaluationPolicy
from abtp.paper.promotion_gate import (
    PaperGateRecommendation,
    PromotionGateResult,
    evaluate_paper_promotion_gate,
)


@dataclass(frozen=True, slots=True)
class PaperEvaluationReport:
    """Operator-facing paper evaluation report."""

    report_id: str
    generated_at: datetime
    gate_result: PromotionGateResult
    beginner_summary: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "This report cannot enable live trading.",
        "Eligibility is only for a future tiny supervised live-trading proposal review.",
        "Paper trading does not guarantee profit.",
        "Any future order path must still pass supervised live controls and "
        "the Risk Management Engine.",
    )

    def __post_init__(self) -> None:
        if not self.report_id.strip():
            raise ValueError("report_id is required")
        if not self.beginner_summary.strip():
            raise ValueError("beginner_summary is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def live_trading_locked(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "gate_result": self.gate_result.as_dict(),
            "beginner_summary": self.beginner_summary,
            "live_trading_locked": self.live_trading_locked,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        payload = self.gate_result.audit_payload()
        payload.update(
            {
                "report_id": self.report_id,
                "beginner_summary": self.beginner_summary,
                "live_trading_locked": str(self.live_trading_locked),
            }
        )
        return payload

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation report cannot enable live trading")

    def create_live_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation report cannot create live orders")

    def apply_strategy_change(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation report cannot apply strategy changes")


def build_paper_evaluation_report(
    evaluation_input: PaperEvaluationInput,
    *,
    policy: PaperEvaluationPolicy | None = None,
    report_id: str = "paper-evaluation-stage-073",
) -> PaperEvaluationReport:
    """Build a deterministic paper-evaluation report."""

    gate = evaluate_paper_promotion_gate(evaluation_input, policy=policy)
    return PaperEvaluationReport(
        report_id=report_id,
        generated_at=evaluation_input.generated_at,
        gate_result=gate,
        beginner_summary=_beginner_summary(gate),
        source_refs=evaluation_input.source_refs,
    )


def _beginner_summary(gate: PromotionGateResult) -> str:
    metrics = gate.metrics
    helped = (
        "Paper trading helped in this evaluation window."
        if metrics.net_return >= 0 and metrics.expectancy >= 0 and not gate.rejection_reasons
        else "Paper trading has not produced enough safe evidence yet."
    )
    if gate.rejection_reasons:
        went_wrong = "; ".join(gate.rejection_reasons)
    else:
        went_wrong = "No policy rejection was found in the supplied paper evidence."
    if gate.recommendation is PaperGateRecommendation.ELIGIBLE_FOR_FUTURE_TINY_LIVE_PROPOSAL:
        change = "Prepare evidence for a later supervised tiny-live proposal review only."
    elif gate.recommendation is PaperGateRecommendation.PAUSE_FOR_REVIEW:
        change = "Pause paper review and investigate the blocking safety evidence."
    elif gate.recommendation is PaperGateRecommendation.MAKE_MORE_CONSERVATIVE:
        change = "Make the paper setup more conservative before more evaluation."
    else:
        change = "Keep running paper mode until sample size and audit evidence improve."
    return "\n".join(
        (
            f"Did paper trading help? {helped}",
            f"What went wrong? {went_wrong}",
            f"What should be changed? {change}",
            "Is real trading still locked? Yes. Stage 073 cannot enable live trading.",
        )
    )
