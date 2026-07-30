"""Conservative paper-trading promotion gate for Stage 073."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from abtp.data import DataQualityStatus, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.paper.evaluation import (
    DECIMAL_ZERO,
    PaperEvaluationInput,
    PaperEvaluationMetrics,
    PaperEvaluationPolicy,
    build_paper_evaluation_metrics,
    paper_evaluation_quality,
)


class PaperGateRecommendation(StrEnum):
    """Stage 073 paper-evaluation recommendations."""

    REMAIN_PAPER = "remain_paper"
    MAKE_MORE_CONSERVATIVE = "make_more_conservative"
    PAUSE_FOR_REVIEW = "pause_for_review"
    ELIGIBLE_FOR_FUTURE_TINY_LIVE_PROPOSAL = "eligible_for_future_tiny_live_proposal"


@dataclass(frozen=True, slots=True)
class PromotionGateResult:
    """Deterministic gate result for a paper-trading evaluation period."""

    generated_at: datetime
    recommendation: PaperGateRecommendation
    metrics: PaperEvaluationMetrics
    policy: PaperEvaluationPolicy
    rejection_reasons: tuple[str, ...]
    rationale: tuple[str, ...]
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Paper evaluation is evidence for operator review only.",
        "Future tiny-live proposal eligibility is not live trading approval.",
        "This gate cannot approve risk, create order intents, submit orders, "
        "or enable live trading.",
        "Paper performance does not guarantee profit.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "recommendation", PaperGateRecommendation(self.recommendation))
        if not self.rationale:
            raise ValueError("promotion gate rationale is required")
        if not self.limitations:
            raise ValueError("promotion gate limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def live_trading_locked(self) -> bool:
        return True

    @property
    def eligible_for_future_tiny_live_proposal(self) -> bool:
        return self.recommendation is PaperGateRecommendation.ELIGIBLE_FOR_FUTURE_TINY_LIVE_PROPOSAL

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "recommendation": self.recommendation.value,
            "eligible_for_future_tiny_live_proposal": self.eligible_for_future_tiny_live_proposal,
            "live_trading_locked": self.live_trading_locked,
            "metrics": self.metrics.as_dict(),
            "policy": self.policy.as_dict(),
            "rejection_reasons": list(self.rejection_reasons),
            "rationale": list(self.rationale),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        payload = self.metrics.audit_payload()
        payload.update(
            {
                "generated_at": self.generated_at.isoformat(),
                "recommendation": self.recommendation.value,
                "eligible_for_future_tiny_live_proposal": str(
                    self.eligible_for_future_tiny_live_proposal
                ),
                "live_trading_locked": str(self.live_trading_locked),
                "rejection_reasons": "|".join(self.rejection_reasons),
                "quality": self.quality.trust_level.value,
                "policy_version": self.policy.policy_version,
            }
        )
        return payload

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation gate cannot enable live trading")

    def create_live_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation gate cannot create live orders")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation gate cannot approve risk")

    def apply_strategy_change(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper evaluation gate cannot apply strategy changes")


def evaluate_paper_promotion_gate(
    evaluation_input: PaperEvaluationInput,
    *,
    policy: PaperEvaluationPolicy | None = None,
) -> PromotionGateResult:
    """Evaluate paper performance without enabling live trading."""

    active_policy = policy or PaperEvaluationPolicy()
    metrics = build_paper_evaluation_metrics(evaluation_input)
    rejection_reasons = _rejection_reasons(metrics, active_policy, evaluation_input)
    quality = paper_evaluation_quality(evaluation_input, metrics, active_policy, rejection_reasons)
    recommendation = _recommendation(metrics, rejection_reasons, quality, active_policy)
    return PromotionGateResult(
        generated_at=evaluation_input.generated_at,
        recommendation=recommendation,
        metrics=metrics,
        policy=active_policy,
        rejection_reasons=rejection_reasons,
        rationale=_rationale(recommendation, metrics, rejection_reasons),
        quality=quality,
        source_refs=evaluation_input.source_refs,
    )


def _rejection_reasons(
    metrics: PaperEvaluationMetrics,
    policy: PaperEvaluationPolicy,
    evaluation_input: PaperEvaluationInput,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if evaluation_input.review_quality.is_rejected:
        reasons.append("paper evaluation input quality is rejected")
    if metrics.evaluation_days < policy.min_paper_trading_days:
        reasons.append(
            f"minimum paper-trading days not met: {metrics.evaluation_days} < "
            f"{policy.min_paper_trading_days}"
        )
    if metrics.completed_trade_count < policy.min_completed_trades:
        reasons.append(
            f"minimum completed paper trades not met: {metrics.completed_trade_count} < "
            f"{policy.min_completed_trades}"
        )
    if metrics.max_drawdown > policy.max_drawdown:
        reasons.append(f"drawdown breach: {metrics.max_drawdown} > {policy.max_drawdown}")
    if metrics.daily_loss_events > policy.max_daily_loss_events:
        reasons.append(
            f"daily loss events exceed policy: {metrics.daily_loss_events} > "
            f"{policy.max_daily_loss_events}"
        )
    if metrics.weekly_loss_events > policy.max_weekly_loss_events:
        reasons.append(
            f"weekly loss events exceed policy: {metrics.weekly_loss_events} > "
            f"{policy.max_weekly_loss_events}"
        )
    if metrics.expectancy < policy.min_expectancy:
        reasons.append(f"unstable expectancy: {metrics.expectancy} < {policy.min_expectancy}")
    if metrics.profit_factor < policy.min_profit_factor:
        reasons.append(
            f"profit factor below policy: {metrics.profit_factor} < {policy.min_profit_factor}"
        )
    if metrics.fee_impact_pct > policy.max_fee_impact_pct:
        reasons.append(
            f"excessive fee impact: {metrics.fee_impact_pct} > {policy.max_fee_impact_pct}"
        )
    if metrics.blocked_cycle_rate > policy.max_blocked_cycle_rate:
        reasons.append(
            f"blocked-cycle rate too high: {metrics.blocked_cycle_rate} > "
            f"{policy.max_blocked_cycle_rate}"
        )
    if (
        metrics.confidence_calibration_error is not None
        and metrics.confidence_calibration_error > policy.max_confidence_calibration_error
    ):
        reasons.append(
            "confidence calibration error too high: "
            f"{metrics.confidence_calibration_error} > "
            f"{policy.max_confidence_calibration_error}"
        )
    if policy.require_stop_loss_compliance and metrics.stop_loss_violations:
        reasons.append(f"stop-loss violation count is {metrics.stop_loss_violations}")
    if metrics.capital_preservation_events:
        reasons.append(f"capital-preservation event count is {metrics.capital_preservation_events}")
    if metrics.governance_violations:
        reasons.append(f"governance violation count is {metrics.governance_violations}")
    if policy.require_complete_audit and not metrics.audit_complete:
        reasons.append("missing audit evidence for paper evaluation")
    return tuple(dict.fromkeys(reasons))


def _recommendation(
    metrics: PaperEvaluationMetrics,
    rejection_reasons: tuple[str, ...],
    quality: DataQualityStatus,
    policy: PaperEvaluationPolicy,
) -> PaperGateRecommendation:
    if _pause_required(rejection_reasons, quality):
        return PaperGateRecommendation.PAUSE_FOR_REVIEW
    if _insufficient_only(rejection_reasons):
        return PaperGateRecommendation.REMAIN_PAPER
    if rejection_reasons:
        return PaperGateRecommendation.MAKE_MORE_CONSERVATIVE
    if (
        quality.is_trusted
        and metrics.evaluation_days >= policy.min_paper_trading_days
        and metrics.completed_trade_count >= policy.min_completed_trades
        and metrics.expectancy >= DECIMAL_ZERO
        and metrics.net_return >= DECIMAL_ZERO
    ):
        return PaperGateRecommendation.ELIGIBLE_FOR_FUTURE_TINY_LIVE_PROPOSAL
    return PaperGateRecommendation.REMAIN_PAPER


def _pause_required(reasons: tuple[str, ...], quality: DataQualityStatus) -> bool:
    if quality.is_rejected:
        return True
    return any(
        term in reason
        for reason in reasons
        for term in (
            "stop-loss violation",
            "capital-preservation event",
            "governance violation",
            "daily loss events",
            "weekly loss events",
            "input quality is rejected",
        )
    )


def _insufficient_only(reasons: tuple[str, ...]) -> bool:
    return bool(reasons) and all(
        reason.startswith("minimum paper-trading days")
        or reason.startswith("minimum completed paper trades")
        or reason.startswith("missing audit evidence")
        for reason in reasons
    )


def _rationale(
    recommendation: PaperGateRecommendation,
    metrics: PaperEvaluationMetrics,
    rejection_reasons: tuple[str, ...],
) -> tuple[str, ...]:
    if rejection_reasons:
        return tuple(rejection_reasons)
    if recommendation is PaperGateRecommendation.ELIGIBLE_FOR_FUTURE_TINY_LIVE_PROPOSAL:
        return (
            "paper evaluation gates passed with complete audit evidence",
            f"net_return={metrics.net_return}",
            f"max_drawdown={metrics.max_drawdown}",
            "live trading remains locked pending a later explicit supervised stage",
        )
    return ("default recommendation is remain_paper until stronger evidence exists",)
