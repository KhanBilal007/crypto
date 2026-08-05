"""Strategy selection contracts for optimiser recommendations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from abtp.config import TradingMode
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.optimizer.scorer import StrategyScore


@dataclass(frozen=True, slots=True)
class StrategySelectionPolicy:
    """Selection and live-change safety policy."""

    min_selected_score: Decimal = Decimal("0.50")
    underperforming_score: Decimal = Decimal("0.35")
    allow_research_paper_auto_disable: bool = True
    live_requires_manual_approval: bool = True
    policy_version: str = "stage-038.v1"

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.min_selected_score <= Decimal("1"):
            raise ValueError("min_selected_score must be between 0 and 1")
        if not Decimal("0") <= self.underperforming_score <= Decimal("1"):
            raise ValueError("underperforming_score must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class StrategyRecommendation:
    """Advisory selected-strategy recommendation."""

    selected_strategy: str | None
    confidence_score: Decimal
    ranked_strategies: tuple[StrategyScore, ...]
    rejected_reasons: tuple[str, ...]
    disable_recommendations: tuple[str, ...]
    explanation: str
    generated_at: datetime
    mode: TradingMode
    manual_approval_required: bool
    can_auto_apply_disable: bool
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.confidence_score <= Decimal("1"):
            raise ValueError("confidence_score must be between 0 and 1")
        if not self.explanation.strip():
            raise ValueError("recommendation explanation is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def recommended(self) -> bool:
        return self.selected_strategy is not None and not self.rejected_reasons

    def require_recommended(self) -> None:
        if not self.recommended:
            raise ValueError("; ".join(self.rejected_reasons))

    def as_dict(self) -> dict[str, object]:
        return {
            "selected_strategy": self.selected_strategy,
            "confidence_score": str(self.confidence_score),
            "ranked_strategies": [score.as_dict() for score in self.ranked_strategies],
            "rejected_reasons": list(self.rejected_reasons),
            "disable_recommendations": list(self.disable_recommendations),
            "explanation": self.explanation,
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode.value,
            "manual_approval_required": self.manual_approval_required,
            "can_auto_apply_disable": self.can_auto_apply_disable,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, str]:
        return {
            "selected_strategy": self.selected_strategy or "none",
            "confidence_score": str(self.confidence_score),
            "rejected_reasons": "|".join(self.rejected_reasons),
            "disable_recommendations": "|".join(self.disable_recommendations),
            "mode": self.mode.value,
            "manual_approval_required": str(self.manual_approval_required),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def select_strategy(
    scores: Sequence[StrategyScore],
    *,
    mode: TradingMode,
    generated_at: datetime,
    policy: StrategySelectionPolicy | None = None,
    manual_approval_for_live_change: bool = False,
    source_refs: Mapping[str, str] | None = None,
) -> StrategyRecommendation:
    """Select the highest eligible strategy with fail-closed live behavior."""

    active_policy = policy or StrategySelectionPolicy()
    ranked = tuple(sorted(scores, key=lambda item: (-item.total_score, item.strategy_name)))
    eligible = tuple(
        score
        for score in ranked
        if score.eligible and score.total_score >= active_policy.min_selected_score
    )
    reasons: list[str] = []
    selected = eligible[0] if eligible else None
    if not ranked:
        reasons.append("no strategy scores supplied")
    if selected is None:
        reasons.append("no eligible strategy met optimiser selection threshold")
    manual_required = mode is TradingMode.LIVE and active_policy.live_requires_manual_approval
    if manual_required and not manual_approval_for_live_change:
        reasons.append("manual approval required before live strategy change")
    disable_recommendations = tuple(
        score.strategy_name
        for score in ranked
        if score.total_score < active_policy.underperforming_score
    )
    can_auto_apply_disable = (
        active_policy.allow_research_paper_auto_disable
        and mode in {TradingMode.RESEARCH, TradingMode.PAPER}
        and bool(disable_recommendations)
    )
    confidence = selected.confidence_score if selected is not None else Decimal("0")
    quality = _selection_quality(ranked, tuple(reasons))
    return StrategyRecommendation(
        selected_strategy=selected.strategy_name if selected is not None and not reasons else None,
        confidence_score=confidence if not reasons else Decimal("0"),
        ranked_strategies=ranked,
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        disable_recommendations=disable_recommendations,
        explanation=_explanation(selected, reasons),
        generated_at=generated_at,
        mode=mode,
        manual_approval_required=manual_required,
        can_auto_apply_disable=can_auto_apply_disable,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _selection_quality(
    ranked: Sequence[StrategyScore],
    reasons: tuple[str, ...],
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    for score in ranked:
        issues.extend(score.quality.issues)
    issues.extend(
        DataQualityIssue(
            flag="optimizer_selection_rejection",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reasons
    )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="optimizer:selection",
        checked_at=ranked[0].quality.checked_at
        if ranked
        else normalize_timestamp(datetime.now(UTC)),
    )


def _explanation(selected: StrategyScore | None, reasons: Sequence[str]) -> str:
    if reasons:
        return "Optimiser rejected strategy selection: " + "; ".join(reasons)
    if selected is None:
        return "Optimiser did not receive a selectable strategy."
    return (
        f"Optimiser selected {selected.strategy_name} with total_score={selected.total_score} "
        f"and confidence_score={selected.confidence_score}; recommendation is advisory only."
    )
