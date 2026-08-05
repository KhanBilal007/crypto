"""Advisory capital and sector rotation assessment from supplied flow metrics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue
from abtp.intelligence.timeframes import DECIMAL_ONE, DECIMAL_ZERO, SCORE_QUANT


class CapitalBucket(StrEnum):
    """Capital-flow bucket or crypto sector tracked by Stage 055."""

    BTC = "btc"
    ETH = "eth"
    LARGE_CAPS = "large_caps"
    MID_CAPS = "mid_caps"
    SMALL_CAPS = "small_caps"
    STABLECOINS = "stablecoins"
    AI = "ai"
    RWA = "rwa"
    LAYER2 = "layer2"
    GAMING = "gaming"
    DEFI = "defi"
    INFRASTRUCTURE = "infrastructure"
    PRIVACY = "privacy"
    DEPIN = "depin"
    MEME = "meme"


class RotationMode(StrEnum):
    """Advisory capital-rotation mode."""

    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    SECTOR_ROTATION = "sector_rotation"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CapitalRotationPolicy:
    """Conservative thresholds for Stage 055 rotation assessment."""

    min_required_buckets: int = 4
    rotation_threshold: Decimal = Decimal("0.35")
    risk_off_threshold: Decimal = Decimal("0.62")
    min_confidence: Decimal = Decimal("0.40")
    weak_liquidity_floor: Decimal = Decimal("0.25")
    policy_version: str = "stage-055.v1"

    def __post_init__(self) -> None:
        if self.min_required_buckets < 3:
            raise ValueError("min_required_buckets must be at least 3")
        for name, value in (
            ("rotation_threshold", self.rotation_threshold),
            ("risk_off_threshold", self.risk_off_threshold),
            ("min_confidence", self.min_confidence),
            ("weak_liquidity_floor", self.weak_liquidity_floor),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class CapitalFlowObservation:
    """Normalized flow evidence for one asset bucket or crypto sector."""

    bucket: CapitalBucket
    inflow_score: Decimal
    outflow_score: Decimal
    momentum_score: Decimal
    liquidity_score: Decimal
    relative_strength_score: Decimal
    quality: DataQualityStatus
    observed_at: datetime
    source_ref: str
    stale: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "bucket", CapitalBucket(self.bucket))
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        for name, value in (
            ("inflow_score", self.inflow_score),
            ("outflow_score", self.outflow_score),
            ("momentum_score", self.momentum_score),
            ("liquidity_score", self.liquidity_score),
            ("relative_strength_score", self.relative_strength_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))


@dataclass(frozen=True, slots=True)
class SectorStrength:
    """Computed capital-flow strength for one bucket."""

    bucket: CapitalBucket
    strength_score: Decimal
    net_flow_score: Decimal
    liquidity_score: Decimal
    rank: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "bucket", CapitalBucket(self.bucket))
        if self.rank < 1:
            raise ValueError("rank must be positive")
        for name, value in (
            ("strength_score", self.strength_score),
            ("net_flow_score", self.net_flow_score),
            ("liquidity_score", self.liquidity_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "bucket": self.bucket.value,
            "strength_score": str(self.strength_score),
            "net_flow_score": str(self.net_flow_score),
            "liquidity_score": str(self.liquidity_score),
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class CapitalRotationEvidence:
    """One explainable capital-rotation contribution."""

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
class CapitalRotationAssessment:
    """Advisory capital and sector rotation result with no trading authority."""

    generated_at: datetime
    mode: RotationMode
    capital_flow_map: Mapping[str, str]
    rotation_probability: Decimal
    sector_strength: tuple[SectorStrength, ...]
    leading_bucket: CapitalBucket | None
    lagging_bucket: CapitalBucket | None
    risk_off_score: Decimal
    confidence: Decimal
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[CapitalRotationEvidence, ...]
    quality: DataQualityStatus
    policy_version: str
    limitations: tuple[str, ...] = (
        "Capital rotation assessment is advisory context only.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "No exchange, fund-flow, ETF, or external provider calls are made in this stage.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by capital rotation assessment.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "mode", RotationMode(self.mode))
        if self.leading_bucket is not None:
            object.__setattr__(self, "leading_bucket", CapitalBucket(self.leading_bucket))
        if self.lagging_bucket is not None:
            object.__setattr__(self, "lagging_bucket", CapitalBucket(self.lagging_bucket))
        for name, value in (
            ("rotation_probability", self.rotation_probability),
            ("risk_off_score", self.risk_off_score),
            ("confidence", self.confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.sector_strength:
            raise ValueError("capital rotation assessment requires sector strength")
        if not self.reasons:
            raise ValueError("capital rotation assessment requires reasons")
        if not self.evidence:
            raise ValueError("capital rotation assessment requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("capital rotation limitations are required")
        object.__setattr__(self, "capital_flow_map", dict(self.capital_flow_map))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return (
            not self.rejection_reasons
            and self.quality.is_trusted
            and self.mode is not RotationMode.RISK_OFF
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode.value,
            "capital_flow_map": dict(self.capital_flow_map),
            "rotation_probability": str(self.rotation_probability),
            "sector_strength": [item.as_dict() for item in self.sector_strength],
            "leading_bucket": self.leading_bucket.value if self.leading_bucket else None,
            "lagging_bucket": self.lagging_bucket.value if self.lagging_bucket else None,
            "risk_off_score": str(self.risk_off_score),
            "confidence": str(self.confidence),
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "evidence": [item.as_dict() for item in self.evidence],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "mode": self.mode.value,
            "rotation_probability": str(self.rotation_probability),
            "leading_bucket": self.leading_bucket.value if self.leading_bucket else "",
            "lagging_bucket": self.lagging_bucket.value if self.lagging_bucket else "",
            "risk_off_score": str(self.risk_off_score),
            "confidence": str(self.confidence),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital rotation assessment cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital rotation assessment cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital rotation assessment cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("capital rotation assessment cannot submit orders")


def assess_capital_rotation(
    observations: Sequence[CapitalFlowObservation],
    *,
    generated_at: datetime,
    policy: CapitalRotationPolicy | None = None,
) -> CapitalRotationAssessment:
    """Assess supplied capital-flow evidence without provider or exchange calls."""

    active_policy = policy or CapitalRotationPolicy()
    unique = _unique_observations(observations)
    issues: list[DataQualityIssue] = []
    rejections: list[str] = []
    if len(unique) < active_policy.min_required_buckets:
        reason = "not enough capital-flow buckets supplied"
        rejections.append(reason)
        issues.append(_issue("insufficient_buckets", DataTrustLevel.REJECTED, reason))
    for required in (CapitalBucket.BTC, CapitalBucket.ETH, CapitalBucket.STABLECOINS):
        if required not in unique:
            reason = f"required bucket {required.value} is missing"
            rejections.append(reason)
            issues.append(_issue(f"missing_{required.value}", DataTrustLevel.REJECTED, reason))

    for observation in unique.values():
        issues.extend(observation.quality.issues)
        if observation.stale:
            reason = f"{observation.bucket.value} capital-flow input is stale"
            rejections.append(reason)
            issues.append(_issue("stale_inputs", DataTrustLevel.REJECTED, reason))
        if observation.quality.is_rejected:
            reason = f"{observation.bucket.value} capital-flow quality is rejected"
            rejections.append(reason)
            issues.append(_issue("rejected_quality", DataTrustLevel.REJECTED, reason))
        elif observation.quality.is_degraded:
            issues.append(
                _issue(
                    "degraded_quality",
                    DataTrustLevel.DEGRADED,
                    f"{observation.bucket.value} capital-flow quality is degraded",
                )
            )
        if observation.liquidity_score < active_policy.weak_liquidity_floor:
            issues.append(
                _issue(
                    "weak_liquidity",
                    DataTrustLevel.DEGRADED,
                    f"{observation.bucket.value} liquidity score is weak",
                )
            )

    strengths = _sector_strength(tuple(unique.values()))
    capital_flow_map = _capital_flow_map(strengths)
    rotation_probability = _rotation_probability(strengths, tuple(unique.values()))
    risk_off_score = _risk_off_score(strengths, unique)
    mode = _mode(rotation_probability, risk_off_score, strengths, active_policy)
    confidence = _confidence(
        strengths, tuple(unique.values()), rotation_probability, risk_off_score
    )
    if risk_off_score >= active_policy.risk_off_threshold:
        reason = "risk-off capital flow is elevated"
        rejections.append(reason)
        issues.append(_issue("risk_off_rotation", DataTrustLevel.REJECTED, reason))
    if confidence < active_policy.min_confidence:
        reason = "capital rotation confidence is below threshold"
        rejections.append(reason)
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reason))

    quality = _quality_status(tuple(issues), bool(rejections), generated_at)
    leading = strengths[0].bucket if strengths else None
    lagging = strengths[-1].bucket if strengths else None
    return CapitalRotationAssessment(
        generated_at=generated_at,
        mode=RotationMode.UNKNOWN if rejections else mode,
        capital_flow_map=capital_flow_map,
        rotation_probability=rotation_probability,
        sector_strength=strengths,
        leading_bucket=leading,
        lagging_bucket=lagging,
        risk_off_score=risk_off_score,
        confidence=confidence,
        reasons=_reasons(mode, rotation_probability, risk_off_score, leading, lagging),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=_evidence(strengths, tuple(unique.values()), rotation_probability, risk_off_score),
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def _unique_observations(
    observations: Sequence[CapitalFlowObservation],
) -> dict[CapitalBucket, CapitalFlowObservation]:
    unique: dict[CapitalBucket, CapitalFlowObservation] = {}
    for observation in observations:
        unique[observation.bucket] = observation
    return unique


def _sector_strength(
    observations: tuple[CapitalFlowObservation, ...],
) -> tuple[SectorStrength, ...]:
    rows: list[tuple[CapitalBucket, Decimal, Decimal, Decimal]] = []
    for observation in observations:
        net_flow = (
            (observation.inflow_score - observation.outflow_score + DECIMAL_ONE) / Decimal("2")
        ).quantize(SCORE_QUANT)
        strength = (
            net_flow * Decimal("0.40")
            + observation.momentum_score * Decimal("0.25")
            + observation.relative_strength_score * Decimal("0.25")
            + observation.liquidity_score * Decimal("0.10")
        ).quantize(SCORE_QUANT)
        rows.append((observation.bucket, strength, net_flow, observation.liquidity_score))
    ordered = sorted(rows, key=lambda row: (row[1], row[2], row[0].value), reverse=True)
    return tuple(
        SectorStrength(
            bucket=bucket,
            strength_score=strength,
            net_flow_score=net_flow,
            liquidity_score=liquidity,
            rank=index + 1,
        )
        for index, (bucket, strength, net_flow, liquidity) in enumerate(ordered)
    )


def _capital_flow_map(strengths: tuple[SectorStrength, ...]) -> dict[str, str]:
    flow_map: dict[str, str] = {}
    for item in strengths:
        if item.strength_score >= Decimal("0.70"):
            state = "strong_inflow"
        elif item.strength_score >= Decimal("0.55"):
            state = "moderate_inflow"
        elif item.strength_score >= Decimal("0.45"):
            state = "balanced"
        elif item.strength_score >= Decimal("0.30"):
            state = "moderate_outflow"
        else:
            state = "strong_outflow"
        flow_map[item.bucket.value] = state
    return flow_map


def _rotation_probability(
    strengths: tuple[SectorStrength, ...],
    observations: tuple[CapitalFlowObservation, ...],
) -> Decimal:
    if not strengths:
        return DECIMAL_ZERO
    dispersion = strengths[0].strength_score - strengths[-1].strength_score
    average_net_delta = sum(
        abs(observation.inflow_score - observation.outflow_score) for observation in observations
    ) / Decimal(len(observations))
    probability = dispersion * Decimal("0.65") + average_net_delta * Decimal("0.35")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, probability)).quantize(SCORE_QUANT)


def _risk_off_score(
    strengths: tuple[SectorStrength, ...],
    observations: Mapping[CapitalBucket, CapitalFlowObservation],
) -> Decimal:
    stable = observations.get(CapitalBucket.STABLECOINS)
    if stable is None or not strengths:
        return DECIMAL_ONE
    stable_pressure = (
        stable.inflow_score * Decimal("0.50")
        + stable.momentum_score * Decimal("0.25")
        + stable.relative_strength_score * Decimal("0.25")
    )
    risk_strengths = [
        item.strength_score for item in strengths if item.bucket is not CapitalBucket.STABLECOINS
    ]
    risk_weakness = (
        sum(DECIMAL_ONE - value for value in risk_strengths) / Decimal(len(risk_strengths))
        if risk_strengths
        else DECIMAL_ONE
    )
    score = stable_pressure * Decimal("0.55") + risk_weakness * Decimal("0.45")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _mode(
    rotation_probability: Decimal,
    risk_off_score: Decimal,
    strengths: tuple[SectorStrength, ...],
    policy: CapitalRotationPolicy,
) -> RotationMode:
    if risk_off_score >= policy.risk_off_threshold:
        return RotationMode.RISK_OFF
    if not strengths:
        return RotationMode.UNKNOWN
    leader = strengths[0].bucket
    if rotation_probability >= policy.rotation_threshold:
        if leader in (CapitalBucket.BTC, CapitalBucket.ETH, CapitalBucket.LARGE_CAPS):
            return RotationMode.RISK_ON
        return RotationMode.SECTOR_ROTATION
    return RotationMode.NEUTRAL


def _confidence(
    strengths: tuple[SectorStrength, ...],
    observations: tuple[CapitalFlowObservation, ...],
    rotation_probability: Decimal,
    risk_off_score: Decimal,
) -> Decimal:
    if not observations:
        return DECIMAL_ZERO
    coverage = min(DECIMAL_ONE, Decimal(len(observations)) / Decimal("8"))
    average_liquidity = sum(item.liquidity_score for item in strengths) / Decimal(len(strengths))
    confidence = Decimal("0.45") + coverage * Decimal("0.20")
    confidence += rotation_probability * Decimal("0.20")
    confidence += average_liquidity * Decimal("0.15")
    if any(observation.quality.is_degraded for observation in observations):
        confidence -= Decimal("0.15")
    if any(observation.quality.is_rejected or observation.stale for observation in observations):
        confidence = min(confidence, Decimal("0.25"))
    if risk_off_score >= Decimal("0.62"):
        confidence -= Decimal("0.10")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, confidence)).quantize(SCORE_QUANT)


def _reasons(
    mode: RotationMode,
    rotation_probability: Decimal,
    risk_off_score: Decimal,
    leading: CapitalBucket | None,
    lagging: CapitalBucket | None,
) -> tuple[str, ...]:
    reasons = [
        f"rotation mode is {mode.value}",
        f"rotation probability is {rotation_probability}",
        f"risk-off score is {risk_off_score}",
    ]
    if leading:
        reasons.append(f"leading bucket is {leading.value}")
    if lagging:
        reasons.append(f"lagging bucket is {lagging.value}")
    return tuple(reasons)


def _evidence(
    strengths: tuple[SectorStrength, ...],
    observations: tuple[CapitalFlowObservation, ...],
    rotation_probability: Decimal,
    risk_off_score: Decimal,
) -> tuple[CapitalRotationEvidence, ...]:
    source_refs = {observation.bucket: observation.source_ref for observation in observations}
    evidence = [
        CapitalRotationEvidence(
            key=f"{item.bucket.value}_sector_strength",
            value=str(item.strength_score),
            reason=(
                "strength uses normalized inflow, outflow, momentum, "
                "relative strength, and liquidity"
            ),
            source_ref=source_refs[item.bucket],
        )
        for item in strengths
    ]
    evidence.extend(
        (
            CapitalRotationEvidence(
                key="rotation_probability",
                value=str(rotation_probability),
                reason="probability uses strength dispersion and net-flow imbalance",
                source_ref="capital_rotation:stage-055:rotation_probability",
            ),
            CapitalRotationEvidence(
                key="risk_off_score",
                value=str(risk_off_score),
                reason="risk-off score uses stablecoin pressure and risk-asset weakness",
                source_ref="capital_rotation:stage-055:risk_off_score",
            ),
        )
    )
    return tuple(evidence)


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
        source_ref="capital_rotation:stage-055",
        checked_at=normalize_timestamp(checked_at),
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
