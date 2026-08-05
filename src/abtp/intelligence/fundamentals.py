"""Advisory fundamental asset rating from supplied project-quality metrics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue
from abtp.intelligence.timeframes import DECIMAL_ONE, DECIMAL_ZERO, SCORE_QUANT


class FundamentalRating(StrEnum):
    """Advisory long-term project-quality rating."""

    STRONG = "strong"
    ADEQUATE = "adequate"
    WATCHLIST = "watchlist"
    WEAK = "weak"
    UNKNOWN = "unknown"


class FundamentalRiskGrade(StrEnum):
    """Conservative advisory risk grade for project fundamentals."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FundamentalPolicy:
    """Thresholds for Stage 054 fundamental asset ratings."""

    strong_threshold: Decimal = Decimal("0.78")
    adequate_threshold: Decimal = Decimal("0.62")
    watchlist_threshold: Decimal = Decimal("0.45")
    min_confidence: Decimal = Decimal("0.40")
    critical_security_floor: Decimal = Decimal("0.25")
    critical_liquidity_floor: Decimal = Decimal("0.25")
    policy_version: str = "stage-054.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("strong_threshold", self.strong_threshold),
            ("adequate_threshold", self.adequate_threshold),
            ("watchlist_threshold", self.watchlist_threshold),
            ("min_confidence", self.min_confidence),
            ("critical_security_floor", self.critical_security_floor),
            ("critical_liquidity_floor", self.critical_liquidity_floor),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not (self.watchlist_threshold < self.adequate_threshold < self.strong_threshold):
            raise ValueError("rating thresholds must increase from watchlist to strong")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class FundamentalInput:
    """Normalized project-quality metrics supplied by fixtures or stored providers."""

    observed_at: datetime
    market_cap_score: Decimal
    liquidity_score: Decimal
    developer_activity_score: Decimal
    github_score: Decimal
    tvl_score: Decimal
    staking_score: Decimal
    tokenomics_score: Decimal
    inflation_control_score: Decimal
    partnerships_score: Decimal
    institutional_adoption_score: Decimal
    security_score: Decimal
    roadmap_score: Decimal
    community_score: Decimal
    governance_score: Decimal
    quality: DataQualityStatus
    asset_symbol: str = "BTC"
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        if not self.asset_symbol.strip():
            raise ValueError("asset_symbol is required")
        for name, value in _metric_items(self):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "asset_symbol", self.asset_symbol.upper())
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class FundamentalEvidence:
    """One explainable fundamental metric contribution."""

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
class FundamentalAssessment:
    """Advisory project-quality assessment with no trading authority."""

    generated_at: datetime
    asset_symbol: str
    rating: FundamentalRating
    long_term_score: Decimal
    risk_grade: FundamentalRiskGrade
    confidence: Decimal
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[FundamentalEvidence, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Fundamental ratings are advisory context only.",
        "They cannot create strategy signals, risk decisions, order intents, or execution.",
        "No GitHub, blockchain, exchange, or external provider calls are made in this stage.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by fundamental ratings.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "asset_symbol", self.asset_symbol.upper())
        object.__setattr__(self, "rating", FundamentalRating(self.rating))
        object.__setattr__(self, "risk_grade", FundamentalRiskGrade(self.risk_grade))
        for name, value in (
            ("long_term_score", self.long_term_score),
            ("confidence", self.confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.asset_symbol.strip():
            raise ValueError("asset_symbol is required")
        if not self.reasons:
            raise ValueError("fundamental assessment requires reasons")
        if not self.evidence:
            raise ValueError("fundamental assessment requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("fundamental limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return (
            not self.rejection_reasons
            and self.quality.is_trusted
            and self.risk_grade is not FundamentalRiskGrade.SEVERE
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "asset_symbol": self.asset_symbol,
            "rating": self.rating.value,
            "long_term_score": str(self.long_term_score),
            "risk_grade": self.risk_grade.value,
            "confidence": str(self.confidence),
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "evidence": [item.as_dict() for item in self.evidence],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "asset_symbol": self.asset_symbol,
            "rating": self.rating.value,
            "long_term_score": str(self.long_term_score),
            "risk_grade": self.risk_grade.value,
            "confidence": str(self.confidence),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("fundamental ratings cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("fundamental ratings cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("fundamental ratings cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("fundamental ratings cannot submit orders")


def assess_fundamental_asset(
    inputs: FundamentalInput,
    *,
    generated_at: datetime,
    policy: FundamentalPolicy | None = None,
) -> FundamentalAssessment:
    """Assess supplied normalized project-quality metrics without provider calls."""

    active_policy = policy or FundamentalPolicy()
    rejections: list[str] = []
    issues = list(inputs.quality.issues)
    if inputs.stale:
        reason = "fundamental inputs are stale"
        rejections.append(reason)
        issues.append(_issue("stale_inputs", DataTrustLevel.REJECTED, reason))
    if inputs.quality.is_rejected:
        reason = "fundamental input quality is rejected"
        rejections.append(reason)
        issues.append(_issue("rejected_quality", DataTrustLevel.REJECTED, reason))
    elif inputs.quality.is_degraded:
        issues.append(
            _issue(
                "degraded_quality",
                DataTrustLevel.DEGRADED,
                "fundamental input quality is degraded",
            )
        )
    if inputs.security_score < active_policy.critical_security_floor:
        reason = "security score is below critical floor"
        rejections.append(reason)
        issues.append(_issue("critical_security", DataTrustLevel.REJECTED, reason))
    if inputs.liquidity_score < active_policy.critical_liquidity_floor:
        reason = "liquidity score is below critical floor"
        rejections.append(reason)
        issues.append(_issue("critical_liquidity", DataTrustLevel.REJECTED, reason))

    base_score = _base_score(inputs)
    long_term_score = _long_term_score(inputs, base_score)
    risk_grade = _risk_grade(inputs, long_term_score)
    rating = _rating(long_term_score, active_policy)
    confidence = _confidence(inputs, long_term_score, risk_grade)
    if confidence < active_policy.min_confidence:
        reason = "fundamental confidence is below threshold"
        rejections.append(reason)
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reason))
    quality = _quality_status(tuple(issues), bool(rejections), generated_at)
    return FundamentalAssessment(
        generated_at=generated_at,
        asset_symbol=inputs.asset_symbol,
        rating=FundamentalRating.UNKNOWN if rejections else rating,
        long_term_score=long_term_score,
        risk_grade=FundamentalRiskGrade.SEVERE if rejections else risk_grade,
        confidence=confidence,
        reasons=_reasons(long_term_score, risk_grade, rating, inputs),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=_evidence(inputs, base_score, long_term_score),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _metric_items(inputs: FundamentalInput) -> tuple[tuple[str, Decimal], ...]:
    return (
        ("market_cap_score", inputs.market_cap_score),
        ("liquidity_score", inputs.liquidity_score),
        ("developer_activity_score", inputs.developer_activity_score),
        ("github_score", inputs.github_score),
        ("tvl_score", inputs.tvl_score),
        ("staking_score", inputs.staking_score),
        ("tokenomics_score", inputs.tokenomics_score),
        ("inflation_control_score", inputs.inflation_control_score),
        ("partnerships_score", inputs.partnerships_score),
        ("institutional_adoption_score", inputs.institutional_adoption_score),
        ("security_score", inputs.security_score),
        ("roadmap_score", inputs.roadmap_score),
        ("community_score", inputs.community_score),
        ("governance_score", inputs.governance_score),
    )


def _base_score(inputs: FundamentalInput) -> Decimal:
    score = (
        inputs.market_cap_score * Decimal("0.08")
        + inputs.liquidity_score * Decimal("0.09")
        + inputs.developer_activity_score * Decimal("0.09")
        + inputs.github_score * Decimal("0.07")
        + inputs.tvl_score * Decimal("0.07")
        + inputs.staking_score * Decimal("0.05")
        + inputs.tokenomics_score * Decimal("0.10")
        + inputs.inflation_control_score * Decimal("0.08")
        + inputs.partnerships_score * Decimal("0.05")
        + inputs.institutional_adoption_score * Decimal("0.07")
        + inputs.security_score * Decimal("0.12")
        + inputs.roadmap_score * Decimal("0.06")
        + inputs.community_score * Decimal("0.04")
        + inputs.governance_score * Decimal("0.03")
    )
    return score.quantize(SCORE_QUANT)


def _long_term_score(inputs: FundamentalInput, base_score: Decimal) -> Decimal:
    score = (
        base_score * Decimal("0.55")
        + inputs.security_score * Decimal("0.12")
        + inputs.tokenomics_score * Decimal("0.10")
        + inputs.inflation_control_score * Decimal("0.07")
        + inputs.developer_activity_score * Decimal("0.06")
        + inputs.governance_score * Decimal("0.05")
        + inputs.roadmap_score * Decimal("0.05")
    )
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _risk_grade(inputs: FundamentalInput, long_term_score: Decimal) -> FundamentalRiskGrade:
    risk_score = (
        (DECIMAL_ONE - long_term_score) * Decimal("0.40")
        + (DECIMAL_ONE - inputs.security_score) * Decimal("0.25")
        + (DECIMAL_ONE - inputs.tokenomics_score) * Decimal("0.15")
        + (DECIMAL_ONE - inputs.inflation_control_score) * Decimal("0.10")
        + (DECIMAL_ONE - inputs.liquidity_score) * Decimal("0.10")
    )
    if risk_score >= Decimal("0.65"):
        return FundamentalRiskGrade.SEVERE
    if risk_score >= Decimal("0.45"):
        return FundamentalRiskGrade.HIGH
    if risk_score >= Decimal("0.25"):
        return FundamentalRiskGrade.MODERATE
    return FundamentalRiskGrade.LOW


def _rating(score: Decimal, policy: FundamentalPolicy) -> FundamentalRating:
    if score >= policy.strong_threshold:
        return FundamentalRating.STRONG
    if score >= policy.adequate_threshold:
        return FundamentalRating.ADEQUATE
    if score >= policy.watchlist_threshold:
        return FundamentalRating.WATCHLIST
    return FundamentalRating.WEAK


def _confidence(
    inputs: FundamentalInput,
    long_term_score: Decimal,
    risk_grade: FundamentalRiskGrade,
) -> Decimal:
    critical_weaknesses = sum(
        1
        for value in (
            inputs.security_score,
            inputs.tokenomics_score,
            inputs.inflation_control_score,
            inputs.liquidity_score,
            inputs.governance_score,
        )
        if value < Decimal("0.35")
    )
    separation = abs(long_term_score - Decimal("0.50"))
    confidence = Decimal("0.80") + separation * Decimal("0.25")
    confidence -= Decimal(critical_weaknesses) * Decimal("0.07")
    if risk_grade is FundamentalRiskGrade.SEVERE:
        confidence -= Decimal("0.20")
    if inputs.quality.is_degraded:
        confidence -= Decimal("0.20")
    if inputs.quality.is_rejected or inputs.stale:
        confidence = min(confidence, Decimal("0.25"))
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, confidence)).quantize(SCORE_QUANT)


def _reasons(
    long_term_score: Decimal,
    risk_grade: FundamentalRiskGrade,
    rating: FundamentalRating,
    inputs: FundamentalInput,
) -> tuple[str, ...]:
    reasons = [
        f"fundamental rating is {rating.value}",
        f"long-term score is {long_term_score}",
        f"fundamental risk grade is {risk_grade.value}",
    ]
    if inputs.security_score < Decimal("0.40"):
        reasons.append("security score is weak")
    if inputs.liquidity_score < Decimal("0.40"):
        reasons.append("liquidity score is weak")
    if inputs.tokenomics_score < Decimal("0.40"):
        reasons.append("tokenomics score is weak")
    if inputs.developer_activity_score >= Decimal("0.70"):
        reasons.append("developer activity supports project continuity")
    if inputs.institutional_adoption_score >= Decimal("0.70"):
        reasons.append("institutional adoption score supports durability")
    if inputs.quality.is_degraded:
        reasons.append("source quality is degraded")
    if inputs.quality.is_rejected:
        reasons.append("source quality is rejected")
    if inputs.stale:
        reasons.append("source inputs are stale")
    return tuple(reasons)


def _evidence(
    inputs: FundamentalInput,
    base_score: Decimal,
    long_term_score: Decimal,
) -> tuple[FundamentalEvidence, ...]:
    items = [
        FundamentalEvidence(
            key=name,
            value=str(value),
            reason=f"{name} supplied as normalized Stage 054 input",
            source_ref=inputs.source_refs.get(name, f"fundamentals:{inputs.asset_symbol}:{name}"),
        )
        for name, value in _metric_items(inputs)
    ]
    items.extend(
        (
            FundamentalEvidence(
                key="base_fundamental_score",
                value=str(base_score),
                reason="weighted project-quality score before long-term emphasis",
                source_ref=f"fundamentals:{inputs.asset_symbol}:base_score",
            ),
            FundamentalEvidence(
                key="long_term_score",
                value=str(long_term_score),
                reason=(
                    "weighted score emphasizing security, tokenomics, inflation, "
                    "governance, and roadmap"
                ),
                source_ref=f"fundamentals:{inputs.asset_symbol}:long_term_score",
            ),
        )
    )
    return tuple(items)


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
        source_ref="fundamentals:stage-054",
        checked_at=normalize_timestamp(checked_at),
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
