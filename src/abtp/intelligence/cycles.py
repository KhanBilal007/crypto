"""Advisory cryptocurrency market-cycle intelligence."""

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


class MarketCyclePhase(StrEnum):
    """Supported cryptocurrency market-cycle phases."""

    BULL_ACCUMULATION = "bull_accumulation"
    BULL_EXPANSION = "bull_expansion"
    BULL_EUPHORIA = "bull_euphoria"
    DISTRIBUTION = "distribution"
    BEAR_MARKET = "bear_market"
    CAPITULATION = "capitulation"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"


class CycleRiskLevel(StrEnum):
    """Advisory cycle-risk labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass(frozen=True, slots=True)
class MarketCyclePolicy:
    """Conservative thresholds for cycle classification."""

    bull_threshold: Decimal = Decimal("0.65")
    bear_threshold: Decimal = Decimal("0.35")
    euphoria_fear_greed_threshold: Decimal = Decimal("0.85")
    capitulation_fear_greed_threshold: Decimal = Decimal("0.15")
    distribution_breadth_threshold: Decimal = Decimal("0.45")
    recovery_liquidity_threshold: Decimal = Decimal("0.50")
    min_confidence: Decimal = Decimal("0.45")
    policy_version: str = "stage-052.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("bull_threshold", self.bull_threshold),
            ("bear_threshold", self.bear_threshold),
            ("euphoria_fear_greed_threshold", self.euphoria_fear_greed_threshold),
            ("capitulation_fear_greed_threshold", self.capitulation_fear_greed_threshold),
            ("distribution_breadth_threshold", self.distribution_breadth_threshold),
            ("recovery_liquidity_threshold", self.recovery_liquidity_threshold),
            ("min_confidence", self.min_confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.bear_threshold >= self.bull_threshold:
            raise ValueError("bear_threshold must be below bull_threshold")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class MarketCycleInput:
    """Provider-neutral cycle metrics supplied by fixtures or stored analytics."""

    observed_at: datetime
    btc_dominance_score: Decimal
    eth_dominance_score: Decimal
    altcoin_season_score: Decimal
    market_breadth_score: Decimal
    fear_greed_score: Decimal
    liquidity_score: Decimal
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("btc_dominance_score", self.btc_dominance_score),
            ("eth_dominance_score", self.eth_dominance_score),
            ("altcoin_season_score", self.altcoin_season_score),
            ("market_breadth_score", self.market_breadth_score),
            ("fear_greed_score", self.fear_greed_score),
            ("liquidity_score", self.liquidity_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class CycleAllocationSuggestion:
    """Advisory allocation context; not an executable portfolio change."""

    max_risk_asset_allocation: Decimal
    min_cash_reserve: Decimal
    allow_new_entries: bool
    rationale: str

    def __post_init__(self) -> None:
        for name, value in (
            ("max_risk_asset_allocation", self.max_risk_asset_allocation),
            ("min_cash_reserve", self.min_cash_reserve),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.rationale.strip():
            raise ValueError("allocation rationale is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "max_risk_asset_allocation": str(self.max_risk_asset_allocation),
            "min_cash_reserve": str(self.min_cash_reserve),
            "allow_new_entries": self.allow_new_entries,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class CycleEvidence:
    """One explainable cycle input."""

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
class MarketCycleAssessment:
    """Advisory market-cycle assessment with no trading authority."""

    generated_at: datetime
    phase: MarketCyclePhase
    confidence: Decimal
    risk_level: CycleRiskLevel
    suggested_allocation: CycleAllocationSuggestion
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[CycleEvidence, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Market-cycle intelligence is advisory context only.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "Suggested allocation is not an executable portfolio change.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by market-cycle classification.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "phase", MarketCyclePhase(self.phase))
        object.__setattr__(self, "risk_level", CycleRiskLevel(self.risk_level))
        if not DECIMAL_ZERO <= self.confidence <= DECIMAL_ONE:
            raise ValueError("cycle confidence must be between 0 and 1")
        if not self.reasons:
            raise ValueError("cycle assessment requires reasons")
        if not self.evidence:
            raise ValueError("cycle assessment requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("cycle limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "phase": self.phase.value,
            "confidence": str(self.confidence),
            "risk_level": self.risk_level.value,
            "suggested_allocation": self.suggested_allocation.as_dict(),
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
            "phase": self.phase.value,
            "confidence": str(self.confidence),
            "risk_level": self.risk_level.value,
            "allow_new_entries": str(self.suggested_allocation.allow_new_entries),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("market-cycle intelligence cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("market-cycle intelligence cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("market-cycle intelligence cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("market-cycle intelligence cannot submit orders")


def assess_market_cycle(
    inputs: MarketCycleInput,
    *,
    generated_at: datetime,
    policy: MarketCyclePolicy | None = None,
) -> MarketCycleAssessment:
    """Classify the current cryptocurrency market cycle from supplied metrics."""

    active_policy = policy or MarketCyclePolicy()
    reasons: list[str] = []
    rejections: list[str] = []
    issues = list(inputs.quality.issues)

    if inputs.stale:
        reason = "market-cycle inputs are stale"
        rejections.append(reason)
        issues.append(_issue("stale_cycle_inputs", DataTrustLevel.REJECTED, reason))
    if inputs.quality.is_rejected:
        reason = "market-cycle input quality is rejected"
        rejections.append(reason)
        issues.append(_issue("rejected_cycle_quality", DataTrustLevel.REJECTED, reason))
    elif inputs.quality.is_degraded:
        issues.append(
            _issue(
                "degraded_cycle_quality",
                DataTrustLevel.DEGRADED,
                "market-cycle input quality is degraded",
            )
        )

    cycle_score = _cycle_score(inputs)
    risk_pressure = _risk_pressure(inputs)
    phase = _phase(inputs, cycle_score, active_policy)
    confidence = _confidence(inputs, cycle_score, phase, active_policy)
    risk_level = _risk_level(phase, risk_pressure)
    if confidence < active_policy.min_confidence:
        reason = "cycle confidence is below threshold"
        rejections.append(reason)
        issues.append(_issue("low_cycle_confidence", DataTrustLevel.REJECTED, reason))
    reasons.extend(_reasons(inputs, phase, cycle_score, risk_pressure))
    quality = _quality_status(tuple(issues), bool(rejections), generated_at)
    return MarketCycleAssessment(
        generated_at=generated_at,
        phase=MarketCyclePhase.UNKNOWN
        if rejections and phase is not MarketCyclePhase.CAPITULATION
        else phase,
        confidence=confidence,
        risk_level=risk_level,
        suggested_allocation=_allocation_for(phase, risk_level),
        reasons=tuple(dict.fromkeys(reasons)),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=_evidence(inputs, cycle_score, risk_pressure),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _cycle_score(inputs: MarketCycleInput) -> Decimal:
    score = (
        inputs.btc_dominance_score * Decimal("0.20")
        + inputs.eth_dominance_score * Decimal("0.15")
        + inputs.altcoin_season_score * Decimal("0.15")
        + inputs.market_breadth_score * Decimal("0.25")
        + inputs.liquidity_score * Decimal("0.25")
    )
    return score.quantize(SCORE_QUANT)


def _risk_pressure(inputs: MarketCycleInput) -> Decimal:
    greed_pressure = abs(inputs.fear_greed_score - Decimal("0.50")) * Decimal("2")
    breadth_stress = DECIMAL_ONE - inputs.market_breadth_score
    liquidity_stress = DECIMAL_ONE - inputs.liquidity_score
    return (
        greed_pressure * Decimal("0.40")
        + breadth_stress * Decimal("0.30")
        + liquidity_stress * Decimal("0.30")
    ).quantize(SCORE_QUANT)


def _phase(
    inputs: MarketCycleInput,
    cycle_score: Decimal,
    policy: MarketCyclePolicy,
) -> MarketCyclePhase:
    if (
        cycle_score <= policy.bear_threshold
        and inputs.fear_greed_score <= policy.capitulation_fear_greed_threshold
    ):
        return MarketCyclePhase.CAPITULATION
    if cycle_score <= policy.bear_threshold:
        return MarketCyclePhase.BEAR_MARKET
    if (
        cycle_score >= policy.bull_threshold
        and inputs.fear_greed_score >= policy.euphoria_fear_greed_threshold
    ):
        return MarketCyclePhase.BULL_EUPHORIA
    if (
        inputs.market_breadth_score < policy.distribution_breadth_threshold
        and inputs.fear_greed_score >= Decimal("0.60")
        and inputs.liquidity_score >= policy.recovery_liquidity_threshold
    ):
        return MarketCyclePhase.DISTRIBUTION
    if cycle_score >= policy.bull_threshold:
        return MarketCyclePhase.BULL_EXPANSION
    if (
        inputs.liquidity_score >= policy.recovery_liquidity_threshold
        and inputs.market_breadth_score >= policy.distribution_breadth_threshold
    ):
        return MarketCyclePhase.RECOVERY
    return MarketCyclePhase.BULL_ACCUMULATION


def _confidence(
    inputs: MarketCycleInput,
    cycle_score: Decimal,
    phase: MarketCyclePhase,
    policy: MarketCyclePolicy,
) -> Decimal:
    distance = min(
        abs(cycle_score - policy.bull_threshold), abs(cycle_score - policy.bear_threshold)
    )
    base = min(DECIMAL_ONE, Decimal("0.45") + distance)
    if phase in {MarketCyclePhase.BULL_EUPHORIA, MarketCyclePhase.CAPITULATION}:
        base += Decimal("0.10")
    if inputs.quality.is_degraded:
        base *= Decimal("0.60")
    if inputs.quality.is_rejected or inputs.stale:
        base *= Decimal("0.25")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, base)).quantize(SCORE_QUANT)


def _risk_level(phase: MarketCyclePhase, risk_pressure: Decimal) -> CycleRiskLevel:
    if phase in {
        MarketCyclePhase.CAPITULATION,
        MarketCyclePhase.BULL_EUPHORIA,
    } or risk_pressure >= Decimal("0.80"):
        return CycleRiskLevel.EXTREME
    if phase in {
        MarketCyclePhase.BEAR_MARKET,
        MarketCyclePhase.DISTRIBUTION,
    } or risk_pressure >= Decimal("0.60"):
        return CycleRiskLevel.HIGH
    if phase in {
        MarketCyclePhase.RECOVERY,
        MarketCyclePhase.BULL_ACCUMULATION,
    } or risk_pressure >= Decimal("0.35"):
        return CycleRiskLevel.MEDIUM
    return CycleRiskLevel.LOW


def _allocation_for(
    phase: MarketCyclePhase,
    risk_level: CycleRiskLevel,
) -> CycleAllocationSuggestion:
    if risk_level is CycleRiskLevel.EXTREME:
        return CycleAllocationSuggestion(
            max_risk_asset_allocation=Decimal("0.10"),
            min_cash_reserve=Decimal("0.80"),
            allow_new_entries=False,
            rationale=f"{phase.value} carries extreme cycle risk",
        )
    if risk_level is CycleRiskLevel.HIGH:
        return CycleAllocationSuggestion(
            max_risk_asset_allocation=Decimal("0.25"),
            min_cash_reserve=Decimal("0.60"),
            allow_new_entries=False,
            rationale=f"{phase.value} requires defensive allocation",
        )
    if risk_level is CycleRiskLevel.MEDIUM:
        return CycleAllocationSuggestion(
            max_risk_asset_allocation=Decimal("0.50"),
            min_cash_reserve=Decimal("0.35"),
            allow_new_entries=True,
            rationale=f"{phase.value} supports cautious review only",
        )
    return CycleAllocationSuggestion(
        max_risk_asset_allocation=Decimal("0.70"),
        min_cash_reserve=Decimal("0.25"),
        allow_new_entries=True,
        rationale=f"{phase.value} supports normal review within risk limits",
    )


def _reasons(
    inputs: MarketCycleInput,
    phase: MarketCyclePhase,
    cycle_score: Decimal,
    risk_pressure: Decimal,
) -> tuple[str, ...]:
    return (
        f"cycle phase {phase.value} from cycle_score={cycle_score}",
        f"risk pressure={risk_pressure}",
        f"fear and greed score={inputs.fear_greed_score}",
        f"market breadth score={inputs.market_breadth_score}",
        f"liquidity score={inputs.liquidity_score}",
    )


def _evidence(
    inputs: MarketCycleInput,
    cycle_score: Decimal,
    risk_pressure: Decimal,
) -> tuple[CycleEvidence, ...]:
    refs = dict(inputs.source_refs)
    return (
        CycleEvidence(
            "btc_dominance",
            str(inputs.btc_dominance_score),
            "BTC dominance input",
            refs.get("btc_dominance", "cycle:btc_dominance"),
        ),
        CycleEvidence(
            "eth_dominance",
            str(inputs.eth_dominance_score),
            "ETH dominance input",
            refs.get("eth_dominance", "cycle:eth_dominance"),
        ),
        CycleEvidence(
            "altcoin_season",
            str(inputs.altcoin_season_score),
            "Altcoin season input",
            refs.get("altcoin_season", "cycle:altcoin_season"),
        ),
        CycleEvidence(
            "market_breadth",
            str(inputs.market_breadth_score),
            "Market breadth input",
            refs.get("market_breadth", "cycle:market_breadth"),
        ),
        CycleEvidence(
            "fear_greed",
            str(inputs.fear_greed_score),
            "Fear and greed input",
            refs.get("fear_greed", "cycle:fear_greed"),
        ),
        CycleEvidence(
            "liquidity",
            str(inputs.liquidity_score),
            "Liquidity input",
            refs.get("liquidity", "cycle:liquidity"),
        ),
        CycleEvidence("cycle_score", str(cycle_score), "Weighted cycle score", "cycle:score"),
        CycleEvidence(
            "risk_pressure", str(risk_pressure), "Cycle risk pressure", "cycle:risk_pressure"
        ),
    )


def _quality_status(
    issues: tuple[DataQualityIssue, ...],
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
        source_ref="intelligence:market_cycle",
        checked_at=generated_at,
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=f"market_cycle_{flag}", severity=severity, reason=reason)
