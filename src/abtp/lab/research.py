"""Controlled AI and strategy research laboratory contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.ai.model_selection import ModelComparisonResult
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.lab.benchmarks import StrategyBenchmarkResult
from abtp.lab.parameters import ParameterCandidate

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class ResearchExperimentType(StrEnum):
    """Supported controlled experiment families."""

    MODEL_COMPARISON = "model_comparison"
    STRATEGY_COMPARISON = "strategy_comparison"
    HYPERPARAMETER_TEST = "hyperparameter_test"
    REGIME_EVALUATION = "regime_evaluation"


class PromotionRecommendation(StrEnum):
    """Advisory promotion recommendation from the research lab."""

    PROMOTE_TO_REVIEW = "promote_to_review"
    KEEP_RESEARCH_ONLY = "keep_research_only"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ResearchExperimentSpec:
    """Metadata for one controlled research experiment."""

    experiment_id: str
    experiment_type: ResearchExperimentType
    title: str
    baseline_ref: str
    candidate_refs: tuple[str, ...]
    hypothesis: str
    evaluation_window: str
    regime_label: str | None = None
    parameter_candidates: tuple[ParameterCandidate, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id is required")
        if not self.title.strip():
            raise ValueError("experiment title is required")
        if not self.baseline_ref.strip():
            raise ValueError("baseline_ref is required")
        if not self.candidate_refs:
            raise ValueError("candidate_refs are required")
        if any(not candidate.strip() for candidate in self.candidate_refs):
            raise ValueError("candidate_refs cannot contain blank values")
        if self.baseline_ref in self.candidate_refs:
            raise ValueError("baseline_ref cannot also be a candidate")
        if not self.hypothesis.strip():
            raise ValueError("experiment hypothesis is required")
        if not self.evaluation_window.strip():
            raise ValueError("evaluation_window is required")
        object.__setattr__(self, "created_at", normalize_timestamp(self.created_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "experiment_type": self.experiment_type.value,
            "title": self.title,
            "baseline_ref": self.baseline_ref,
            "candidate_refs": list(self.candidate_refs),
            "hypothesis": self.hypothesis,
            "evaluation_window": self.evaluation_window,
            "regime_label": self.regime_label,
            "parameter_candidates": [
                candidate.as_dict() for candidate in self.parameter_candidates
            ],
            "created_at": self.created_at.isoformat(),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class ResearchLabPolicy:
    """Promotion thresholds for controlled research experiments."""

    min_model_score: Decimal = Decimal("0.60")
    min_strategy_score: Decimal = Decimal("0.60")
    min_score_delta_vs_baseline: Decimal = Decimal("0.05")
    require_trusted_quality: bool = True
    require_all_candidates_ranked: bool = True
    policy_version: str = "stage-069.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_model_score", self.min_model_score),
            ("min_strategy_score", self.min_strategy_score),
            ("min_score_delta_vs_baseline", self.min_score_delta_vs_baseline),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ResearchExperimentResult:
    """Ranked result for one model or strategy candidate."""

    candidate_ref: str
    score: Decimal
    rank: int
    eligible: bool
    baseline_delta: Decimal
    result_type: ResearchExperimentType
    evidence: tuple[str, ...]
    rejected_reasons: tuple[str, ...]
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.candidate_ref.strip():
            raise ValueError("candidate_ref is required")
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("experiment score must be between 0 and 1")
        if self.rank <= 0:
            raise ValueError("rank must be positive")
        if not self.evidence:
            raise ValueError("experiment result requires evidence")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_ref": self.candidate_ref,
            "score": str(self.score),
            "rank": self.rank,
            "eligible": self.eligible,
            "baseline_delta": str(self.baseline_delta),
            "result_type": self.result_type.value,
            "evidence": list(self.evidence),
            "rejected_reasons": list(self.rejected_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class ResearchPromotionAdvice:
    """Advisory promotion decision for a controlled experiment."""

    recommendation: PromotionRecommendation
    candidate_ref: str | None
    rationale: tuple[str, ...]
    requires_governance_review: bool
    requires_walk_forward_validation: bool
    requires_paper_validation: bool

    def __post_init__(self) -> None:
        if self.recommendation is PromotionRecommendation.PROMOTE_TO_REVIEW and (
            self.candidate_ref is None or not self.candidate_ref.strip()
        ):
            raise ValueError("promoted research advice requires a candidate_ref")
        if not self.rationale:
            raise ValueError("promotion advice requires rationale")

    def as_dict(self) -> dict[str, object]:
        return {
            "recommendation": self.recommendation.value,
            "candidate_ref": self.candidate_ref,
            "rationale": list(self.rationale),
            "requires_governance_review": self.requires_governance_review,
            "requires_walk_forward_validation": self.requires_walk_forward_validation,
            "requires_paper_validation": self.requires_paper_validation,
        }


@dataclass(frozen=True, slots=True)
class ResearchLabReport:
    """Audit-ready report for controlled AI and strategy experiments."""

    experiment: ResearchExperimentSpec
    generated_at: datetime
    results: tuple[ResearchExperimentResult, ...]
    promotion_advice: ResearchPromotionAdvice
    rejected_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Research laboratory results are advisory only.",
        "Promotion recommendations require governance, validation, and paper evidence.",
        "The research laboratory cannot serve predictions, create signals, approve risk, "
        "or submit orders.",
        "No profit is guaranteed by research experiments.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def recommended_candidate_ref(self) -> str | None:
        return self.promotion_advice.candidate_ref

    @property
    def advisory_only(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "experiment": self.experiment.as_dict(),
            "generated_at": self.generated_at.isoformat(),
            "results": [result.as_dict() for result in self.results],
            "promotion_advice": self.promotion_advice.as_dict(),
            "rejected_reasons": list(self.rejected_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "experiment_id": self.experiment.experiment_id,
            "experiment_type": self.experiment.experiment_type.value,
            "baseline_ref": self.experiment.baseline_ref,
            "ranked_candidates": "|".join(result.candidate_ref for result in self.results),
            "recommended_candidate_ref": self.recommended_candidate_ref or "none",
            "recommendation": self.promotion_advice.recommendation.value,
            "rejected_reasons": "|".join(self.rejected_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def predict(self, *_args: object, **_kwargs: object) -> None:
        """Reject prediction serving; research reports are offline evidence."""

        raise ValueError("research laboratory cannot serve predictions")

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject signal creation; research reports have no strategy authority."""

        raise ValueError("research laboratory cannot create strategy signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk approval; all order paths must use the Risk Management Engine."""

        raise ValueError("research laboratory cannot approve risk")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order intent creation; research reports are non-executable."""

        raise ValueError("research laboratory cannot create order intents")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject order submission; research reports have no execution authority."""

        raise ValueError("research laboratory cannot submit orders")


def build_research_report(
    experiment: ResearchExperimentSpec,
    *,
    model_results: Sequence[ModelComparisonResult] = (),
    strategy_results: Sequence[StrategyBenchmarkResult] = (),
    generated_at: datetime | None = None,
    policy: ResearchLabPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> ResearchLabReport:
    """Build an advisory research report from existing model/strategy evidence."""

    active_policy = policy or ResearchLabPolicy()
    now = generated_at or datetime.now(UTC)
    results = _rank_results(
        (
            *_model_experiment_results(experiment, model_results, active_policy, now),
            *_strategy_experiment_results(experiment, strategy_results, active_policy, now),
        )
    )
    rejected_reasons = _report_rejections(experiment, results, active_policy)
    quality = _report_quality(results, rejected_reasons, now)
    advice = _promotion_advice(results, rejected_reasons, quality)
    return ResearchLabReport(
        experiment=experiment,
        generated_at=now,
        results=results,
        promotion_advice=advice,
        rejected_reasons=rejected_reasons,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _model_experiment_results(
    experiment: ResearchExperimentSpec,
    model_results: Sequence[ModelComparisonResult],
    policy: ResearchLabPolicy,
    generated_at: datetime,
) -> tuple[ResearchExperimentResult, ...]:
    if experiment.experiment_type is not ResearchExperimentType.MODEL_COMPARISON:
        return ()
    baseline = _find_model_result(model_results, experiment.baseline_ref)
    return tuple(
        _research_result_from_model(
            result,
            baseline_score=baseline.score,
            policy=policy,
            generated_at=generated_at,
        )
        for result in model_results
        if result.model_ref in experiment.candidate_refs
    )


def _strategy_experiment_results(
    experiment: ResearchExperimentSpec,
    strategy_results: Sequence[StrategyBenchmarkResult],
    policy: ResearchLabPolicy,
    generated_at: datetime,
) -> tuple[ResearchExperimentResult, ...]:
    if experiment.experiment_type not in {
        ResearchExperimentType.STRATEGY_COMPARISON,
        ResearchExperimentType.HYPERPARAMETER_TEST,
        ResearchExperimentType.REGIME_EVALUATION,
    }:
        return ()
    baseline = _find_strategy_result(strategy_results, experiment.baseline_ref)
    return tuple(
        _research_result_from_strategy(
            result,
            result_type=experiment.experiment_type,
            baseline_score=baseline.score,
            policy=policy,
            generated_at=generated_at,
        )
        for result in strategy_results
        if result.strategy_key in experiment.candidate_refs
    )


def _research_result_from_model(
    result: ModelComparisonResult,
    *,
    baseline_score: Decimal,
    policy: ResearchLabPolicy,
    generated_at: datetime,
) -> ResearchExperimentResult:
    reasons = [
        *result.rejected_reasons,
        *_candidate_rejections(
            result.score,
            baseline_delta=result.score - baseline_score,
            threshold=policy.min_model_score,
            policy=policy,
            quality=result.quality,
        ),
    ]
    quality = _candidate_quality(result.quality, reasons, generated_at, result.model_ref)
    return ResearchExperimentResult(
        candidate_ref=result.model_ref,
        score=result.score,
        rank=result.rank,
        eligible=result.eligible and not reasons and quality.is_trusted,
        baseline_delta=result.score - baseline_score,
        result_type=ResearchExperimentType.MODEL_COMPARISON,
        evidence=(
            *result.evidence,
            f"baseline_delta={result.score - baseline_score}",
            f"approval_status={result.approval_status.value}",
            f"lifecycle_status={result.lifecycle_status.value}",
        ),
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        quality=quality,
        source_refs=result.source_refs,
    )


def _research_result_from_strategy(
    result: StrategyBenchmarkResult,
    *,
    result_type: ResearchExperimentType,
    baseline_score: Decimal,
    policy: ResearchLabPolicy,
    generated_at: datetime,
) -> ResearchExperimentResult:
    reasons = [
        *result.rejected_reasons,
        *_candidate_rejections(
            result.score,
            baseline_delta=result.score - baseline_score,
            threshold=policy.min_strategy_score,
            policy=policy,
            quality=result.quality,
        ),
    ]
    quality = _candidate_quality(result.quality, reasons, generated_at, result.strategy_key)
    return ResearchExperimentResult(
        candidate_ref=result.strategy_key,
        score=result.score,
        rank=result.rank,
        eligible=result.eligible and not reasons and quality.is_trusted,
        baseline_delta=result.score - baseline_score,
        result_type=result_type,
        evidence=(
            *result.evidence,
            f"baseline_delta={result.score - baseline_score}",
            f"regime_score={result.regime_score}",
        ),
        rejected_reasons=tuple(dict.fromkeys(reasons)),
        quality=quality,
        source_refs=result.source_refs,
    )


def _candidate_rejections(
    score: Decimal,
    *,
    baseline_delta: Decimal,
    threshold: Decimal,
    policy: ResearchLabPolicy,
    quality: DataQualityStatus,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if score < threshold:
        reasons.append("candidate score is below research threshold")
    if baseline_delta < policy.min_score_delta_vs_baseline:
        reasons.append("candidate does not improve enough over production baseline")
    if policy.require_trusted_quality and not quality.is_trusted:
        reasons.append("candidate quality is not trusted")
    return tuple(reasons)


def _rank_results(
    results: Sequence[ResearchExperimentResult],
) -> tuple[ResearchExperimentResult, ...]:
    return tuple(
        _with_rank(result, index + 1)
        for index, result in enumerate(
            sorted(results, key=lambda item: (-item.score, item.candidate_ref))
        )
    )


def _with_rank(result: ResearchExperimentResult, rank: int) -> ResearchExperimentResult:
    return ResearchExperimentResult(
        candidate_ref=result.candidate_ref,
        score=result.score,
        rank=rank,
        eligible=result.eligible,
        baseline_delta=result.baseline_delta,
        result_type=result.result_type,
        evidence=result.evidence,
        rejected_reasons=result.rejected_reasons,
        quality=result.quality,
        source_refs=result.source_refs,
    )


def _report_rejections(
    experiment: ResearchExperimentSpec,
    results: tuple[ResearchExperimentResult, ...],
    policy: ResearchLabPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not results:
        reasons.append("no experiment results matched candidate_refs")
    if policy.require_all_candidates_ranked:
        ranked_refs = {result.candidate_ref for result in results}
        missing_refs = tuple(ref for ref in experiment.candidate_refs if ref not in ranked_refs)
        if missing_refs:
            reasons.append(f"missing results for candidates: {', '.join(missing_refs)}")
    if not any(result.eligible for result in results):
        reasons.append("no candidate passed research promotion policy")
    return tuple(dict.fromkeys(reasons))


def _promotion_advice(
    results: tuple[ResearchExperimentResult, ...],
    rejected_reasons: tuple[str, ...],
    quality: DataQualityStatus,
) -> ResearchPromotionAdvice:
    best = next((result for result in results if result.eligible), None)
    if best is None or rejected_reasons or not quality.is_trusted:
        recommendation = (
            PromotionRecommendation.REJECT
            if quality.is_rejected
            else PromotionRecommendation.KEEP_RESEARCH_ONLY
        )
        rationale = rejected_reasons or ("no eligible research candidate",)
        return ResearchPromotionAdvice(
            recommendation=recommendation,
            candidate_ref=None,
            rationale=rationale,
            requires_governance_review=False,
            requires_walk_forward_validation=True,
            requires_paper_validation=True,
        )
    return ResearchPromotionAdvice(
        recommendation=PromotionRecommendation.PROMOTE_TO_REVIEW,
        candidate_ref=best.candidate_ref,
        rationale=(
            f"{best.candidate_ref} passed research policy",
            f"score={best.score}",
            f"baseline_delta={best.baseline_delta}",
        ),
        requires_governance_review=True,
        requires_walk_forward_validation=True,
        requires_paper_validation=True,
    )


def _report_quality(
    results: tuple[ResearchExperimentResult, ...],
    rejected_reasons: tuple[str, ...],
    generated_at: datetime,
) -> DataQualityStatus:
    issues = [
        DataQualityIssue(
            flag="research_report_rejection",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in rejected_reasons
    ]
    for result in results:
        issues.extend(result.quality.issues)
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="lab:research_report",
        checked_at=normalize_timestamp(generated_at),
    )


def _candidate_quality(
    source_quality: DataQualityStatus,
    reasons: Sequence[str],
    generated_at: datetime,
    candidate_ref: str,
) -> DataQualityStatus:
    issues = [*source_quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="research_candidate_rejection",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reasons
        if reason not in source_quality.flags
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
        source_ref=f"lab:research:{candidate_ref}",
        checked_at=normalize_timestamp(generated_at),
    )


def _find_model_result(
    results: Sequence[ModelComparisonResult],
    model_ref: str,
) -> ModelComparisonResult:
    for result in results:
        if result.model_ref == model_ref:
            return result
    raise KeyError(f"baseline model result not found: {model_ref}")


def _find_strategy_result(
    results: Sequence[StrategyBenchmarkResult],
    strategy_key: str,
) -> StrategyBenchmarkResult:
    for result in results:
        if result.strategy_key == strategy_key:
            return result
    raise KeyError(f"baseline strategy result not found: {strategy_key}")
