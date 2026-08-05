"""Advisory multi-timeframe intelligence engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class Timeframe(StrEnum):
    """Supported multi-timeframe hierarchy."""

    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"
    FOUR_HOUR = "4h"
    ONE_HOUR = "1h"


class TrendBias(StrEnum):
    """Directional bias labels used for alignment scoring."""

    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


TIMEFRAME_WEIGHTS: Mapping[Timeframe, Decimal] = {
    Timeframe.MONTHLY: Decimal("0.30"),
    Timeframe.WEEKLY: Decimal("0.25"),
    Timeframe.DAILY: Decimal("0.20"),
    Timeframe.FOUR_HOUR: Decimal("0.15"),
    Timeframe.ONE_HOUR: Decimal("0.10"),
}

LOWER_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe.DAILY,
    Timeframe.FOUR_HOUR,
    Timeframe.ONE_HOUR,
)
HIGHER_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe.MONTHLY,
    Timeframe.WEEKLY,
)
DEFAULT_REQUIRED_TIMEFRAMES: tuple[Timeframe, ...] = tuple(Timeframe)


@dataclass(frozen=True, slots=True)
class MultiTimeframePolicy:
    """Conservative alignment thresholds for Stage 051."""

    required_timeframes: tuple[Timeframe, ...] = DEFAULT_REQUIRED_TIMEFRAMES
    min_alignment_score: Decimal = Decimal("0.65")
    min_agreement_pct: Decimal = Decimal("0.70")
    min_entry_timing_score: Decimal = Decimal("0.55")
    min_exit_timing_score: Decimal = Decimal("0.45")
    degraded_quality_multiplier: Decimal = Decimal("0.50")
    policy_version: str = "stage-051.v1"

    def __post_init__(self) -> None:
        required = tuple(Timeframe(timeframe) for timeframe in self.required_timeframes)
        for name, value in (
            ("min_alignment_score", self.min_alignment_score),
            ("min_agreement_pct", self.min_agreement_pct),
            ("min_entry_timing_score", self.min_entry_timing_score),
            ("min_exit_timing_score", self.min_exit_timing_score),
            ("degraded_quality_multiplier", self.degraded_quality_multiplier),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "required_timeframes", required)


@dataclass(frozen=True, slots=True)
class TimeframeObservation:
    """Normalized technical evidence for one timeframe."""

    timeframe: Timeframe
    observed_at: datetime
    trend_bias: TrendBias
    trend_strength: Decimal
    momentum_score: Decimal
    volatility_score: Decimal
    volume_score: Decimal
    market_structure_score: Decimal
    support_resistance_score: Decimal
    liquidity_score: Decimal
    quality: DataQualityStatus
    source_ref: str
    stale: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeframe", Timeframe(self.timeframe))
        object.__setattr__(self, "trend_bias", TrendBias(self.trend_bias))
        for name, value in (
            ("trend_strength", self.trend_strength),
            ("momentum_score", self.momentum_score),
            ("volatility_score", self.volatility_score),
            ("volume_score", self.volume_score),
            ("market_structure_score", self.market_structure_score),
            ("support_resistance_score", self.support_resistance_score),
            ("liquidity_score", self.liquidity_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))

    def as_dict(self) -> dict[str, object]:
        return {
            "timeframe": self.timeframe.value,
            "observed_at": self.observed_at.isoformat(),
            "trend_bias": self.trend_bias.value,
            "trend_strength": str(self.trend_strength),
            "momentum_score": str(self.momentum_score),
            "volatility_score": str(self.volatility_score),
            "volume_score": str(self.volume_score),
            "market_structure_score": str(self.market_structure_score),
            "support_resistance_score": str(self.support_resistance_score),
            "liquidity_score": str(self.liquidity_score),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_ref": self.source_ref,
            "stale": self.stale,
        }


@dataclass(frozen=True, slots=True)
class TimeframeEvidence:
    """One explainable input used by the multi-timeframe engine."""

    timeframe: Timeframe
    key: str
    value: JsonValue
    reason: str
    source_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "timeframe", Timeframe(self.timeframe))
        for value, field_name in (
            (self.key, "evidence key"),
            (self.reason, "evidence reason"),
            (self.source_ref, "evidence source_ref"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "timeframe": self.timeframe.value,
            "key": self.key,
            "value": self.value,
            "reason": self.reason,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class MultiTimeframeIntelligence:
    """Advisory multi-timeframe market context with no trading authority."""

    generated_at: datetime
    higher_timeframe_bias: TrendBias
    trend_alignment_score: Decimal
    trend_strength: Decimal
    timeframe_agreement_pct: Decimal
    entry_timing_score: Decimal
    exit_timing_score: Decimal
    market_structure: str
    high_confidence_context: bool
    rejection_reasons: tuple[str, ...]
    risk_rules: tuple[str, ...]
    evidence: tuple[TimeframeEvidence, ...]
    observations: tuple[TimeframeObservation, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Multi-timeframe intelligence is advisory context only.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "Future strategy actions must still pass the Strategy Engine.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by multi-timeframe alignment.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "higher_timeframe_bias", TrendBias(self.higher_timeframe_bias))
        for name, value in (
            ("trend_alignment_score", self.trend_alignment_score),
            ("trend_strength", self.trend_strength),
            ("timeframe_agreement_pct", self.timeframe_agreement_pct),
            ("entry_timing_score", self.entry_timing_score),
            ("exit_timing_score", self.exit_timing_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.market_structure.strip():
            raise ValueError("market_structure is required")
        if not self.evidence:
            raise ValueError("multi-timeframe intelligence requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("multi-timeframe limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "higher_timeframe_bias": self.higher_timeframe_bias.value,
            "trend_alignment_score": str(self.trend_alignment_score),
            "trend_strength": str(self.trend_strength),
            "timeframe_agreement_pct": str(self.timeframe_agreement_pct),
            "entry_timing_score": str(self.entry_timing_score),
            "exit_timing_score": str(self.exit_timing_score),
            "market_structure": self.market_structure,
            "high_confidence_context": self.high_confidence_context,
            "rejection_reasons": list(self.rejection_reasons),
            "risk_rules": list(self.risk_rules),
            "evidence": [item.as_dict() for item in self.evidence],
            "observations": [item.as_dict() for item in self.observations],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "higher_timeframe_bias": self.higher_timeframe_bias.value,
            "trend_alignment_score": str(self.trend_alignment_score),
            "trend_strength": str(self.trend_strength),
            "timeframe_agreement_pct": str(self.timeframe_agreement_pct),
            "entry_timing_score": str(self.entry_timing_score),
            "exit_timing_score": str(self.exit_timing_score),
            "market_structure": self.market_structure,
            "high_confidence_context": str(self.high_confidence_context),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "risk_rules": "|".join(self.risk_rules),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject strategy-signal authority."""

        raise ValueError("multi-timeframe intelligence cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order-intent authority."""

        raise ValueError("multi-timeframe intelligence cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("multi-timeframe intelligence cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("multi-timeframe intelligence cannot submit orders")


def evaluate_multi_timeframe_intelligence(
    observations: Sequence[TimeframeObservation],
    *,
    generated_at: datetime,
    policy: MultiTimeframePolicy | None = None,
) -> MultiTimeframeIntelligence:
    """Evaluate deterministic multi-timeframe alignment from supplied observations."""

    active_policy = policy or MultiTimeframePolicy()
    normalized = _normalized_observations(observations)
    by_timeframe = {item.timeframe: item for item in normalized}
    reasons: list[str] = []
    risk_rules: list[str] = []
    issues: list[DataQualityIssue] = []

    for timeframe in active_policy.required_timeframes:
        if timeframe not in by_timeframe:
            reason = f"required timeframe {timeframe.value} is missing"
            reasons.append(reason)
            risk_rules.append(f"block_entry: {reason}")
            issues.append(_issue("missing_timeframe", DataTrustLevel.REJECTED, reason))

    included = tuple(item for item in normalized if _include_observation(item, reasons, issues))
    higher_bias = _higher_timeframe_bias(included)
    if higher_bias is TrendBias.UNKNOWN:
        reason = "higher-timeframe bias is unknown"
        reasons.append(reason)
        risk_rules.append(f"block_entry: {reason}")
        issues.append(_issue("unknown_higher_timeframe_bias", DataTrustLevel.REJECTED, reason))

    contradiction = _alignment_contradiction(by_timeframe, higher_bias)
    if contradiction:
        reasons.append(contradiction)
        risk_rules.append(f"block_entry: {contradiction}")
        issues.append(
            _issue("timeframe_alignment_contradiction", DataTrustLevel.REJECTED, contradiction)
        )

    alignment = _alignment_score(included, higher_bias)
    trend_strength = _weighted_metric(included, lambda item: item.trend_strength)
    agreement = _agreement_pct(included, higher_bias)
    entry_timing = _entry_timing_score(included, higher_bias)
    exit_timing = _exit_timing_score(included)
    if alignment < active_policy.min_alignment_score:
        reason = "trend alignment score is below threshold"
        reasons.append(reason)
        risk_rules.append(f"block_entry: {reason}")
    if agreement < active_policy.min_agreement_pct:
        reason = "timeframe agreement percentage is below threshold"
        reasons.append(reason)
        risk_rules.append(f"block_entry: {reason}")
    if entry_timing < active_policy.min_entry_timing_score:
        reason = "entry timing score is below threshold"
        reasons.append(reason)
        risk_rules.append(f"block_entry: {reason}")

    inherited_issues = tuple(issue for item in normalized for issue in item.quality.issues)
    quality = _quality_status(
        (*inherited_issues, *issues),
        rejected=bool(reasons),
        generated_at=generated_at,
    )
    high_confidence_context = (
        not reasons
        and quality.is_trusted
        and alignment >= active_policy.min_alignment_score
        and agreement >= active_policy.min_agreement_pct
        and entry_timing >= active_policy.min_entry_timing_score
        and exit_timing >= active_policy.min_exit_timing_score
    )
    return MultiTimeframeIntelligence(
        generated_at=generated_at,
        higher_timeframe_bias=higher_bias,
        trend_alignment_score=alignment,
        trend_strength=trend_strength,
        timeframe_agreement_pct=agreement,
        entry_timing_score=entry_timing,
        exit_timing_score=exit_timing,
        market_structure=_market_structure_label(included, higher_bias),
        high_confidence_context=high_confidence_context,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        risk_rules=tuple(dict.fromkeys(risk_rules)) or ("review_alignment_before_entry",),
        evidence=_evidence(normalized, higher_bias),
        observations=normalized,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=_source_refs(normalized),
    )


def _normalized_observations(
    observations: Sequence[TimeframeObservation],
) -> tuple[TimeframeObservation, ...]:
    normalized = tuple(observations)
    seen: set[Timeframe] = set()
    for item in normalized:
        if item.timeframe in seen:
            raise ValueError(f"duplicate timeframe observation: {item.timeframe.value}")
        seen.add(item.timeframe)
    return tuple(sorted(normalized, key=lambda item: _timeframe_rank(item.timeframe)))


def _include_observation(
    observation: TimeframeObservation,
    reasons: list[str],
    issues: list[DataQualityIssue],
) -> bool:
    include = True
    if observation.quality.is_rejected:
        reason = f"timeframe {observation.timeframe.value} quality is rejected"
        reasons.append(reason)
        issues.append(_issue("rejected_timeframe_quality", DataTrustLevel.REJECTED, reason))
        include = False
    elif observation.quality.is_degraded:
        issues.append(
            _issue(
                "degraded_timeframe_quality",
                DataTrustLevel.DEGRADED,
                f"timeframe {observation.timeframe.value} quality is degraded",
            )
        )
    if observation.stale:
        reason = f"timeframe {observation.timeframe.value} is stale"
        reasons.append(reason)
        issues.append(_issue("stale_timeframe", DataTrustLevel.REJECTED, reason))
        include = False
    return include


def _higher_timeframe_bias(observations: tuple[TimeframeObservation, ...]) -> TrendBias:
    higher = tuple(item for item in observations if item.timeframe in HIGHER_TIMEFRAMES)
    if not higher:
        return TrendBias.UNKNOWN
    bull = _bias_weight(higher, TrendBias.BULL)
    bear = _bias_weight(higher, TrendBias.BEAR)
    if bull == bear:
        return TrendBias.NEUTRAL if bull > DECIMAL_ZERO else TrendBias.UNKNOWN
    return TrendBias.BULL if bull > bear else TrendBias.BEAR


def _alignment_contradiction(
    by_timeframe: Mapping[Timeframe, TimeframeObservation],
    higher_bias: TrendBias,
) -> str | None:
    monthly = by_timeframe.get(Timeframe.MONTHLY)
    weekly = by_timeframe.get(Timeframe.WEEKLY)
    daily = by_timeframe.get(Timeframe.DAILY)
    if monthly is None or weekly is None or daily is None:
        return None
    if (
        monthly.trend_bias is TrendBias.BEAR
        and weekly.trend_bias is TrendBias.BEAR
        and daily.trend_bias is TrendBias.BULL
    ):
        return "monthly and weekly are bear while daily is bull"
    if higher_bias in {TrendBias.BULL, TrendBias.BEAR} and daily.trend_bias not in {
        higher_bias,
        TrendBias.NEUTRAL,
    }:
        return "daily trend opposes higher-timeframe bias"
    return None


def _alignment_score(
    observations: tuple[TimeframeObservation, ...],
    higher_bias: TrendBias,
) -> Decimal:
    if higher_bias not in {TrendBias.BULL, TrendBias.BEAR}:
        return DECIMAL_ZERO
    aligned = tuple(item for item in observations if item.trend_bias is higher_bias)
    total_weight = _total_weight(observations)
    if total_weight == DECIMAL_ZERO:
        return DECIMAL_ZERO
    weighted = sum(
        (_weight_for(item) * item.trend_strength for item in aligned),
        DECIMAL_ZERO,
    )
    return (weighted / total_weight).quantize(SCORE_QUANT)


def _agreement_pct(
    observations: tuple[TimeframeObservation, ...],
    higher_bias: TrendBias,
) -> Decimal:
    total_weight = _total_weight(observations)
    if total_weight == DECIMAL_ZERO or higher_bias not in {TrendBias.BULL, TrendBias.BEAR}:
        return DECIMAL_ZERO
    aligned_weight = sum(
        (_weight_for(item) for item in observations if item.trend_bias is higher_bias),
        DECIMAL_ZERO,
    )
    return (aligned_weight / total_weight).quantize(SCORE_QUANT)


def _entry_timing_score(
    observations: tuple[TimeframeObservation, ...],
    higher_bias: TrendBias,
) -> Decimal:
    lower = tuple(item for item in observations if item.timeframe in LOWER_TIMEFRAMES)
    if not lower or higher_bias not in {TrendBias.BULL, TrendBias.BEAR}:
        return DECIMAL_ZERO
    aligned = tuple(item for item in lower if item.trend_bias is higher_bias)
    if not aligned:
        return DECIMAL_ZERO
    scores = tuple(
        (
            item.momentum_score
            + item.volume_score
            + item.market_structure_score
            + item.support_resistance_score
            + item.liquidity_score
        )
        / Decimal("5")
        for item in aligned
    )
    return (sum(scores, DECIMAL_ZERO) / Decimal(len(scores))).quantize(SCORE_QUANT)


def _exit_timing_score(observations: tuple[TimeframeObservation, ...]) -> Decimal:
    lower = tuple(item for item in observations if item.timeframe in LOWER_TIMEFRAMES)
    if not lower:
        return DECIMAL_ZERO
    scores = tuple(
        ((DECIMAL_ONE - item.volatility_score) + item.support_resistance_score) / Decimal("2")
        for item in lower
    )
    return (sum(scores, DECIMAL_ZERO) / Decimal(len(scores))).quantize(SCORE_QUANT)


def _weighted_metric(
    observations: tuple[TimeframeObservation, ...],
    metric: Callable[[TimeframeObservation], Decimal],
) -> Decimal:
    total_weight = _total_weight(observations)
    if total_weight == DECIMAL_ZERO:
        return DECIMAL_ZERO
    weighted = sum((_weight_for(item) * metric(item) for item in observations), DECIMAL_ZERO)
    return (weighted / total_weight).quantize(SCORE_QUANT)


def _bias_weight(observations: tuple[TimeframeObservation, ...], bias: TrendBias) -> Decimal:
    return sum(
        (_weight_for(item) for item in observations if item.trend_bias is bias),
        DECIMAL_ZERO,
    )


def _total_weight(observations: tuple[TimeframeObservation, ...]) -> Decimal:
    return sum((_weight_for(item) for item in observations), DECIMAL_ZERO)


def _weight_for(observation: TimeframeObservation) -> Decimal:
    base_weight = TIMEFRAME_WEIGHTS[observation.timeframe]
    if observation.quality.is_degraded:
        return (base_weight * Decimal("0.50")).quantize(SCORE_QUANT)
    return base_weight


def _timeframe_rank(timeframe: Timeframe) -> int:
    return {
        Timeframe.MONTHLY: 0,
        Timeframe.WEEKLY: 1,
        Timeframe.DAILY: 2,
        Timeframe.FOUR_HOUR: 3,
        Timeframe.ONE_HOUR: 4,
    }[timeframe]


def _market_structure_label(
    observations: tuple[TimeframeObservation, ...],
    higher_bias: TrendBias,
) -> str:
    structure = _weighted_metric(observations, lambda item: item.market_structure_score)
    if higher_bias is TrendBias.UNKNOWN:
        return "unavailable"
    if structure >= Decimal("0.70"):
        return f"aligned_{higher_bias.value}"
    if structure >= Decimal("0.45"):
        return f"mixed_{higher_bias.value}"
    return "weak_structure"


def _evidence(
    observations: tuple[TimeframeObservation, ...],
    higher_bias: TrendBias,
) -> tuple[TimeframeEvidence, ...]:
    evidence: list[TimeframeEvidence] = []
    for item in observations:
        evidence.append(
            TimeframeEvidence(
                timeframe=item.timeframe,
                key="trend_bias",
                value=item.trend_bias.value,
                reason=f"{item.timeframe.value} trend contributes to {higher_bias.value} bias",
                source_ref=item.source_ref,
            )
        )
        evidence.append(
            TimeframeEvidence(
                timeframe=item.timeframe,
                key="timing_scores",
                value={
                    "momentum": str(item.momentum_score),
                    "volume": str(item.volume_score),
                    "market_structure": str(item.market_structure_score),
                    "support_resistance": str(item.support_resistance_score),
                    "liquidity": str(item.liquidity_score),
                    "volatility": str(item.volatility_score),
                },
                reason=f"{item.timeframe.value} timing and structure evidence",
                source_ref=item.source_ref,
            )
        )
    return tuple(evidence)


def _quality_status(
    issues: tuple[DataQualityIssue, ...],
    *,
    rejected: bool,
    generated_at: datetime,
) -> DataQualityStatus:
    if rejected or any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=issues,
        source_ref="intelligence:multi_timeframe",
        checked_at=generated_at,
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=f"multi_timeframe_{flag}", severity=severity, reason=reason)


def _source_refs(observations: tuple[TimeframeObservation, ...]) -> Mapping[str, str]:
    return {item.timeframe.value: item.source_ref for item in observations}
