"""Advisory opportunity discovery over a supplied crypto universe."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue
from abtp.intelligence.timeframes import DECIMAL_ONE, DECIMAL_ZERO, SCORE_QUANT


class OpportunityBucket(StrEnum):
    """Advisory discovery bucket."""

    TOP = "top_opportunity"
    WATCH = "watch_list"
    AVOID = "avoid_list"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OpportunityDiscoveryPolicy:
    """Conservative thresholds for Stage 057 opportunity discovery."""

    top_n: int = 10
    watch_score_threshold: Decimal = Decimal("0.55")
    top_score_threshold: Decimal = Decimal("0.68")
    avoid_score_threshold: Decimal = Decimal("0.35")
    max_risk_score: Decimal = Decimal("0.62")
    min_liquidity_score: Decimal = Decimal("0.35")
    min_confidence: Decimal = Decimal("0.40")
    min_universe_size: int = 3
    policy_version: str = "stage-057.v1"

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n must be positive")
        if self.min_universe_size < 1:
            raise ValueError("min_universe_size must be positive")
        for name, value in (
            ("watch_score_threshold", self.watch_score_threshold),
            ("top_score_threshold", self.top_score_threshold),
            ("avoid_score_threshold", self.avoid_score_threshold),
            ("max_risk_score", self.max_risk_score),
            ("min_liquidity_score", self.min_liquidity_score),
            ("min_confidence", self.min_confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.avoid_score_threshold < self.watch_score_threshold < self.top_score_threshold:
            raise ValueError("score thresholds must increase from avoid to top")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class OpportunityCandidate:
    """Normalized opportunity evidence for one asset in a supplied universe."""

    symbol: str
    technical_score: Decimal
    ai_score: Decimal
    fundamental_score: Decimal
    onchain_score: Decimal
    liquidity_score: Decimal
    risk_score: Decimal
    relative_strength_score: Decimal
    momentum_score: Decimal
    market_cycle_score: Decimal
    expected_holding_period: str
    quality: DataQualityStatus
    observed_at: datetime
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if not self.expected_holding_period.strip():
            raise ValueError("expected_holding_period is required")
        for name, value in _candidate_metric_items(self):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class OpportunityEvidence:
    """One explainable discovery contribution."""

    key: str
    value: JsonValue
    reason: str
    source_ref: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.key, "evidence key"),
            (self.reason, "evidence reason"),
            (self.source_ref, "evidence source_ref"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "key": self.key,
            "value": self.value,
            "reason": self.reason,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class OpportunityRanking:
    """Ranked advisory opportunity item."""

    symbol: str
    bucket: OpportunityBucket
    opportunity_score: Decimal
    confidence: Decimal
    risk_score: Decimal
    liquidity_score: Decimal
    expected_holding_period: str
    rank: int | None
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[OpportunityEvidence, ...]
    quality: DataQualityStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "bucket", OpportunityBucket(self.bucket))
        if self.rank is not None and self.rank < 1:
            raise ValueError("rank must be positive when supplied")
        for name, value in (
            ("opportunity_score", self.opportunity_score),
            ("confidence", self.confidence),
            ("risk_score", self.risk_score),
            ("liquidity_score", self.liquidity_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.reasons:
            raise ValueError("opportunity ranking requires reasons")
        if not self.evidence:
            raise ValueError("opportunity ranking requires evidence")
        if not self.expected_holding_period.strip():
            raise ValueError("expected_holding_period is required")

    @property
    def actionable_context(self) -> bool:
        return (
            self.bucket is OpportunityBucket.TOP
            and not self.rejection_reasons
            and self.quality.is_trusted
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "bucket": self.bucket.value,
            "opportunity_score": str(self.opportunity_score),
            "confidence": str(self.confidence),
            "risk_score": str(self.risk_score),
            "liquidity_score": str(self.liquidity_score),
            "expected_holding_period": self.expected_holding_period,
            "rank": self.rank,
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "evidence": [item.as_dict() for item in self.evidence],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
        }


@dataclass(frozen=True, slots=True)
class OpportunityDiscoveryReport:
    """Advisory opportunity discovery report with no trading authority."""

    generated_at: datetime
    universe_size: int
    top_opportunities: tuple[OpportunityRanking, ...]
    watch_list: tuple[OpportunityRanking, ...]
    avoid_list: tuple[OpportunityRanking, ...]
    confidence: Decimal
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    limitations: tuple[str, ...] = (
        "Opportunity discovery is advisory ranking context only.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "No exchange, market scanner, ranking-provider, or external provider calls are made.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by opportunity discovery.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if self.universe_size < 0:
            raise ValueError("universe_size cannot be negative")
        if not DECIMAL_ZERO <= self.confidence <= DECIMAL_ONE:
            raise ValueError("confidence must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("opportunity discovery limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "universe_size": self.universe_size,
            "top_opportunities": [item.as_dict() for item in self.top_opportunities],
            "watch_list": [item.as_dict() for item in self.watch_list],
            "avoid_list": [item.as_dict() for item in self.avoid_list],
            "confidence": str(self.confidence),
            "rejection_reasons": list(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "universe_size": self.universe_size,
            "top_symbols": "|".join(item.symbol for item in self.top_opportunities),
            "watch_symbols": "|".join(item.symbol for item in self.watch_list),
            "avoid_symbols": "|".join(item.symbol for item in self.avoid_list),
            "confidence": str(self.confidence),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("opportunity discovery cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("opportunity discovery cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("opportunity discovery cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("opportunity discovery cannot submit orders")


def discover_opportunities(
    candidates: Sequence[OpportunityCandidate],
    *,
    generated_at: datetime,
    policy: OpportunityDiscoveryPolicy | None = None,
) -> OpportunityDiscoveryReport:
    """Rank a supplied crypto universe without scanning providers or exchanges."""

    active_policy = policy or OpportunityDiscoveryPolicy()
    unique = _unique_candidates(candidates)
    issues: list[DataQualityIssue] = []
    report_rejections: list[str] = []
    if len(unique) < active_policy.min_universe_size:
        reason = "not enough opportunity candidates supplied"
        report_rejections.append(reason)
        issues.append(_issue("insufficient_universe", DataTrustLevel.REJECTED, reason))

    rankings = tuple(
        _rank_candidate(candidate, policy=active_policy, generated_at=generated_at)
        for candidate in unique.values()
    )
    for ranking in rankings:
        issues.extend(
            issue
            for issue in ranking.quality.issues
            if issue.flag
            in {
                "stale_candidate",
                "rejected_candidate_quality",
                "degraded_candidate_quality",
            }
        )
    sorted_rankings = sorted(
        rankings,
        key=lambda item: (item.opportunity_score, item.confidence, item.symbol),
        reverse=True,
    )
    top_candidates = [item for item in sorted_rankings if item.bucket is OpportunityBucket.TOP]
    top_opportunities = tuple(
        OpportunityRanking(
            symbol=item.symbol,
            bucket=item.bucket,
            opportunity_score=item.opportunity_score,
            confidence=item.confidence,
            risk_score=item.risk_score,
            liquidity_score=item.liquidity_score,
            expected_holding_period=item.expected_holding_period,
            rank=index + 1,
            reasons=item.reasons,
            rejection_reasons=item.rejection_reasons,
            evidence=item.evidence,
            quality=item.quality,
        )
        for index, item in enumerate(top_candidates[: active_policy.top_n])
    )
    watch_list = tuple(item for item in sorted_rankings if item.bucket is OpportunityBucket.WATCH)
    avoid_list = tuple(item for item in sorted_rankings if item.bucket is OpportunityBucket.AVOID)
    if not top_opportunities:
        reason = "no top opportunities passed conservative filters"
        report_rejections.append(reason)
        issues.append(_issue("no_top_opportunities", DataTrustLevel.DEGRADED, reason))
    confidence = _report_confidence(rankings, top_opportunities)
    if confidence < active_policy.min_confidence:
        reason = "opportunity discovery confidence is below threshold"
        report_rejections.append(reason)
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reason))
    quality = _quality_status(tuple(issues), bool(report_rejections), generated_at)
    return OpportunityDiscoveryReport(
        generated_at=generated_at,
        universe_size=len(unique),
        top_opportunities=top_opportunities,
        watch_list=watch_list,
        avoid_list=avoid_list,
        confidence=confidence,
        rejection_reasons=tuple(dict.fromkeys(report_rejections)),
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def _unique_candidates(
    candidates: Sequence[OpportunityCandidate],
) -> dict[str, OpportunityCandidate]:
    unique: dict[str, OpportunityCandidate] = {}
    for candidate in candidates:
        unique[candidate.symbol] = candidate
    return unique


def _rank_candidate(
    candidate: OpportunityCandidate,
    *,
    policy: OpportunityDiscoveryPolicy,
    generated_at: datetime,
) -> OpportunityRanking:
    issues = list(candidate.quality.issues)
    rejections: list[str] = []
    if candidate.stale:
        reason = f"{candidate.symbol} opportunity input is stale"
        rejections.append(reason)
        issues.append(_issue("stale_candidate", DataTrustLevel.REJECTED, reason))
    if candidate.quality.is_rejected:
        reason = f"{candidate.symbol} opportunity quality is rejected"
        rejections.append(reason)
        issues.append(_issue("rejected_candidate_quality", DataTrustLevel.REJECTED, reason))
    elif candidate.quality.is_degraded:
        issues.append(
            _issue(
                "degraded_candidate_quality",
                DataTrustLevel.DEGRADED,
                f"{candidate.symbol} opportunity quality is degraded",
            )
        )
    score = _opportunity_score(candidate)
    confidence = _candidate_confidence(candidate, score)
    if candidate.risk_score > policy.max_risk_score:
        reason = f"{candidate.symbol} risk score is above limit"
        rejections.append(reason)
        issues.append(_issue("excessive_risk", DataTrustLevel.REJECTED, reason))
    if candidate.liquidity_score < policy.min_liquidity_score:
        reason = f"{candidate.symbol} liquidity score is below floor"
        rejections.append(reason)
        issues.append(_issue("weak_liquidity", DataTrustLevel.REJECTED, reason))
    if confidence < policy.min_confidence:
        reason = f"{candidate.symbol} opportunity confidence is below threshold"
        rejections.append(reason)
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reason))
    bucket = _candidate_bucket(score, rejections, candidate, policy)
    quality = _quality_status(tuple(issues), bool(rejections), generated_at)
    return OpportunityRanking(
        symbol=candidate.symbol,
        bucket=bucket,
        opportunity_score=score,
        confidence=confidence,
        risk_score=candidate.risk_score,
        liquidity_score=candidate.liquidity_score,
        expected_holding_period=candidate.expected_holding_period,
        rank=None,
        reasons=_candidate_reasons(candidate, score, confidence, bucket),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=_candidate_evidence(candidate, score, confidence),
        quality=quality,
    )


def _candidate_bucket(
    score: Decimal,
    rejections: list[str],
    candidate: OpportunityCandidate,
    policy: OpportunityDiscoveryPolicy,
) -> OpportunityBucket:
    if rejections or score <= policy.avoid_score_threshold:
        return OpportunityBucket.AVOID
    if score >= policy.top_score_threshold and candidate.quality.is_trusted:
        return OpportunityBucket.TOP
    if score >= policy.watch_score_threshold:
        return OpportunityBucket.WATCH
    return OpportunityBucket.AVOID


def _candidate_metric_items(candidate: OpportunityCandidate) -> tuple[tuple[str, Decimal], ...]:
    return (
        ("technical_score", candidate.technical_score),
        ("ai_score", candidate.ai_score),
        ("fundamental_score", candidate.fundamental_score),
        ("onchain_score", candidate.onchain_score),
        ("liquidity_score", candidate.liquidity_score),
        ("risk_score", candidate.risk_score),
        ("relative_strength_score", candidate.relative_strength_score),
        ("momentum_score", candidate.momentum_score),
        ("market_cycle_score", candidate.market_cycle_score),
    )


def _opportunity_score(candidate: OpportunityCandidate) -> Decimal:
    score = (
        candidate.technical_score * Decimal("0.16")
        + candidate.ai_score * Decimal("0.14")
        + candidate.fundamental_score * Decimal("0.12")
        + candidate.onchain_score * Decimal("0.10")
        + candidate.liquidity_score * Decimal("0.12")
        + (DECIMAL_ONE - candidate.risk_score) * Decimal("0.16")
        + candidate.relative_strength_score * Decimal("0.12")
        + candidate.momentum_score * Decimal("0.10")
        + candidate.market_cycle_score * Decimal("0.08")
    )
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _candidate_confidence(candidate: OpportunityCandidate, score: Decimal) -> Decimal:
    confidence = Decimal("0.45") + score * Decimal("0.35")
    confidence += candidate.liquidity_score * Decimal("0.10")
    confidence += (DECIMAL_ONE - candidate.risk_score) * Decimal("0.10")
    if candidate.quality.is_degraded:
        confidence -= Decimal("0.15")
    if candidate.quality.is_rejected or candidate.stale:
        confidence = min(confidence, Decimal("0.25"))
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, confidence)).quantize(SCORE_QUANT)


def _candidate_reasons(
    candidate: OpportunityCandidate,
    score: Decimal,
    confidence: Decimal,
    bucket: OpportunityBucket,
) -> tuple[str, ...]:
    reasons = [
        f"{candidate.symbol} discovery bucket is {bucket.value}",
        f"opportunity score is {score}",
        f"confidence is {confidence}",
        f"expected holding period is {candidate.expected_holding_period}",
    ]
    if candidate.technical_score >= Decimal("0.70"):
        reasons.append("technical score supports ranking")
    if candidate.ai_score >= Decimal("0.70"):
        reasons.append("AI score supports ranking")
    if candidate.risk_score >= Decimal("0.62"):
        reasons.append("risk score is elevated")
    if candidate.liquidity_score < Decimal("0.35"):
        reasons.append("liquidity score is weak")
    if candidate.quality.is_degraded:
        reasons.append("source quality is degraded")
    if candidate.quality.is_rejected:
        reasons.append("source quality is rejected")
    if candidate.stale:
        reasons.append("source inputs are stale")
    return tuple(reasons)


def _candidate_evidence(
    candidate: OpportunityCandidate, score: Decimal, confidence: Decimal
) -> tuple[OpportunityEvidence, ...]:
    evidence = [
        OpportunityEvidence(
            key=f"{candidate.symbol.lower()}_{name}",
            value=str(value),
            reason=f"{name} supplied as normalized Stage 057 input",
            source_ref=candidate.source_refs.get(name, f"opportunity:{candidate.symbol}:{name}"),
        )
        for name, value in _candidate_metric_items(candidate)
    ]
    evidence.extend(
        (
            OpportunityEvidence(
                key=f"{candidate.symbol.lower()}_opportunity_score",
                value=str(score),
                reason=(
                    "weighted discovery score across technical, AI, fundamental, "
                    "on-chain, liquidity, risk, relative strength, momentum, and "
                    "cycle inputs"
                ),
                source_ref=f"opportunity:{candidate.symbol}:score",
            ),
            OpportunityEvidence(
                key=f"{candidate.symbol.lower()}_confidence",
                value=str(confidence),
                reason="confidence uses opportunity score, liquidity, risk, and quality",
                source_ref=f"opportunity:{candidate.symbol}:confidence",
            ),
        )
    )
    return tuple(evidence)


def _report_confidence(
    rankings: tuple[OpportunityRanking, ...], top_opportunities: tuple[OpportunityRanking, ...]
) -> Decimal:
    if not rankings:
        return DECIMAL_ZERO
    average = sum(item.confidence for item in rankings) / Decimal(len(rankings))
    top_bonus = min(Decimal("0.10"), Decimal(len(top_opportunities)) * Decimal("0.02"))
    confidence = average * Decimal("0.90") + top_bonus
    if any(item.quality.is_rejected for item in rankings):
        confidence -= Decimal("0.15")
    elif any(item.quality.is_degraded for item in rankings):
        confidence -= Decimal("0.08")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, confidence)).quantize(SCORE_QUANT)


def _quality_status(
    issues: tuple[DataQualityIssue, ...], has_rejections: bool, checked_at: datetime
) -> DataQualityStatus:
    if has_rejections or any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=issues,
        source_ref="opportunity_discovery:stage-057",
        checked_at=normalize_timestamp(checked_at),
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
