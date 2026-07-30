"""Advisory macro and narrative intelligence from supplied normalized evidence."""

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


class NarrativeTheme(StrEnum):
    """Crypto narrative themes tracked by Stage 056."""

    AI = "ai"
    RWA = "rwa"
    STABLECOINS = "stablecoins"
    GAMING = "gaming"
    LAYER2 = "layer2"
    MEMECOIN = "memecoin"
    DEFI = "defi"


class MacroNarrativeMode(StrEnum):
    """Advisory macro/narrative environment."""

    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    NARRATIVE_LED = "narrative_led"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MacroNarrativePolicy:
    """Conservative thresholds for Stage 056 macro and narrative assessment."""

    macro_risk_block_threshold: Decimal = Decimal("0.65")
    risk_on_threshold: Decimal = Decimal("0.60")
    narrative_strength_threshold: Decimal = Decimal("0.62")
    min_confidence: Decimal = Decimal("0.40")
    min_required_narratives: int = 3
    policy_version: str = "stage-056.v1"

    def __post_init__(self) -> None:
        if self.min_required_narratives < 1:
            raise ValueError("min_required_narratives must be positive")
        for name, value in (
            ("macro_risk_block_threshold", self.macro_risk_block_threshold),
            ("risk_on_threshold", self.risk_on_threshold),
            ("narrative_strength_threshold", self.narrative_strength_threshold),
            ("min_confidence", self.min_confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class MacroInput:
    """Normalized macro evidence supplied by fixtures or future stored providers."""

    observed_at: datetime
    interest_rate_pressure_score: Decimal
    fed_hawkishness_score: Decimal
    ecb_hawkishness_score: Decimal
    inflation_pressure_score: Decimal
    cpi_surprise_score: Decimal
    ppi_surprise_score: Decimal
    dollar_strength_score: Decimal
    bond_yield_pressure_score: Decimal
    gold_safety_bid_score: Decimal
    oil_inflation_pressure_score: Decimal
    nasdaq_strength_score: Decimal
    sp500_strength_score: Decimal
    etf_flow_score: Decimal
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        for name, value in _macro_metric_items(self):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class NarrativeObservation:
    """Normalized narrative evidence for one crypto theme."""

    theme: NarrativeTheme
    strength_score: Decimal
    momentum_score: Decimal
    liquidity_score: Decimal
    attention_score: Decimal
    quality: DataQualityStatus
    observed_at: datetime
    source_ref: str
    stale: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "theme", NarrativeTheme(self.theme))
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        for name, value in (
            ("strength_score", self.strength_score),
            ("momentum_score", self.momentum_score),
            ("liquidity_score", self.liquidity_score),
            ("attention_score", self.attention_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))


@dataclass(frozen=True, slots=True)
class NarrativeStrength:
    """Computed strength for one narrative theme."""

    theme: NarrativeTheme
    strength_score: Decimal
    rank: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "theme", NarrativeTheme(self.theme))
        if self.rank < 1:
            raise ValueError("rank must be positive")
        if not DECIMAL_ZERO <= self.strength_score <= DECIMAL_ONE:
            raise ValueError("strength_score must be between 0 and 1")

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "theme": self.theme.value,
            "strength_score": str(self.strength_score),
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class MacroNarrativeEvidence:
    """One explainable macro or narrative contribution."""

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
class MacroNarrativeAssessment:
    """Advisory macro and narrative assessment with no trading authority."""

    generated_at: datetime
    mode: MacroNarrativeMode
    macro_risk_score: Decimal
    narrative_strength: Decimal
    risk_on_score: Decimal
    leading_narrative: NarrativeTheme | None
    narrative_rankings: tuple[NarrativeStrength, ...]
    confidence: Decimal
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[MacroNarrativeEvidence, ...]
    quality: DataQualityStatus
    policy_version: str
    limitations: tuple[str, ...] = (
        "Macro and narrative intelligence is advisory context only.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "No macro, news, ETF, exchange, or external provider calls are made in this stage.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by macro or narrative intelligence.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "mode", MacroNarrativeMode(self.mode))
        if self.leading_narrative is not None:
            object.__setattr__(self, "leading_narrative", NarrativeTheme(self.leading_narrative))
        for name, value in (
            ("macro_risk_score", self.macro_risk_score),
            ("narrative_strength", self.narrative_strength),
            ("risk_on_score", self.risk_on_score),
            ("confidence", self.confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.reasons:
            raise ValueError("macro narrative assessment requires reasons")
        if not self.evidence:
            raise ValueError("macro narrative assessment requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("macro narrative limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return (
            not self.rejection_reasons
            and self.quality.is_trusted
            and self.mode is not MacroNarrativeMode.RISK_OFF
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode.value,
            "macro_risk_score": str(self.macro_risk_score),
            "narrative_strength": str(self.narrative_strength),
            "risk_on_score": str(self.risk_on_score),
            "leading_narrative": self.leading_narrative.value if self.leading_narrative else None,
            "narrative_rankings": [item.as_dict() for item in self.narrative_rankings],
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
            "macro_risk_score": str(self.macro_risk_score),
            "narrative_strength": str(self.narrative_strength),
            "risk_on_score": str(self.risk_on_score),
            "leading_narrative": self.leading_narrative.value if self.leading_narrative else "",
            "confidence": str(self.confidence),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("macro narrative intelligence cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("macro narrative intelligence cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("macro narrative intelligence cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("macro narrative intelligence cannot submit orders")


def assess_macro_narrative(
    macro: MacroInput,
    narratives: Sequence[NarrativeObservation],
    *,
    generated_at: datetime,
    policy: MacroNarrativePolicy | None = None,
) -> MacroNarrativeAssessment:
    """Assess supplied macro and narrative evidence without provider calls."""

    active_policy = policy or MacroNarrativePolicy()
    unique_narratives = _unique_narratives(narratives)
    issues = list(macro.quality.issues)
    rejections: list[str] = []
    if macro.stale:
        reason = "macro inputs are stale"
        rejections.append(reason)
        issues.append(_issue("stale_macro", DataTrustLevel.REJECTED, reason))
    if macro.quality.is_rejected:
        reason = "macro input quality is rejected"
        rejections.append(reason)
        issues.append(_issue("rejected_macro_quality", DataTrustLevel.REJECTED, reason))
    elif macro.quality.is_degraded:
        issues.append(
            _issue("degraded_macro_quality", DataTrustLevel.DEGRADED, "macro quality is degraded")
        )
    if len(unique_narratives) < active_policy.min_required_narratives:
        reason = "not enough narrative themes supplied"
        rejections.append(reason)
        issues.append(_issue("insufficient_narratives", DataTrustLevel.REJECTED, reason))

    for observation in unique_narratives.values():
        issues.extend(observation.quality.issues)
        if observation.stale:
            reason = f"{observation.theme.value} narrative input is stale"
            rejections.append(reason)
            issues.append(_issue("stale_narrative", DataTrustLevel.REJECTED, reason))
        if observation.quality.is_rejected:
            reason = f"{observation.theme.value} narrative quality is rejected"
            rejections.append(reason)
            issues.append(_issue("rejected_narrative_quality", DataTrustLevel.REJECTED, reason))
        elif observation.quality.is_degraded:
            issues.append(
                _issue(
                    "degraded_narrative_quality",
                    DataTrustLevel.DEGRADED,
                    f"{observation.theme.value} narrative quality is degraded",
                )
            )

    macro_risk_score = _macro_risk_score(macro)
    rankings = _narrative_rankings(tuple(unique_narratives.values()))
    narrative_strength = rankings[0].strength_score if rankings else DECIMAL_ZERO
    risk_on_score = _risk_on_score(macro, macro_risk_score, narrative_strength)
    mode = _mode(macro_risk_score, narrative_strength, risk_on_score, active_policy)
    confidence = _confidence(macro, tuple(unique_narratives.values()), rankings, risk_on_score)
    if macro_risk_score >= active_policy.macro_risk_block_threshold:
        reason = "macro risk score is elevated"
        rejections.append(reason)
        issues.append(_issue("elevated_macro_risk", DataTrustLevel.REJECTED, reason))
    if confidence < active_policy.min_confidence:
        reason = "macro narrative confidence is below threshold"
        rejections.append(reason)
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reason))

    quality = _quality_status(tuple(issues), bool(rejections), generated_at)
    leading = rankings[0].theme if rankings else None
    return MacroNarrativeAssessment(
        generated_at=generated_at,
        mode=MacroNarrativeMode.UNKNOWN if rejections else mode,
        macro_risk_score=macro_risk_score,
        narrative_strength=narrative_strength,
        risk_on_score=risk_on_score,
        leading_narrative=leading,
        narrative_rankings=rankings,
        confidence=confidence,
        reasons=_reasons(mode, macro_risk_score, narrative_strength, risk_on_score, leading),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=_evidence(macro, tuple(unique_narratives.values()), rankings, risk_on_score),
        quality=quality,
        policy_version=active_policy.policy_version,
    )


def _macro_metric_items(inputs: MacroInput) -> tuple[tuple[str, Decimal], ...]:
    return (
        ("interest_rate_pressure_score", inputs.interest_rate_pressure_score),
        ("fed_hawkishness_score", inputs.fed_hawkishness_score),
        ("ecb_hawkishness_score", inputs.ecb_hawkishness_score),
        ("inflation_pressure_score", inputs.inflation_pressure_score),
        ("cpi_surprise_score", inputs.cpi_surprise_score),
        ("ppi_surprise_score", inputs.ppi_surprise_score),
        ("dollar_strength_score", inputs.dollar_strength_score),
        ("bond_yield_pressure_score", inputs.bond_yield_pressure_score),
        ("gold_safety_bid_score", inputs.gold_safety_bid_score),
        ("oil_inflation_pressure_score", inputs.oil_inflation_pressure_score),
        ("nasdaq_strength_score", inputs.nasdaq_strength_score),
        ("sp500_strength_score", inputs.sp500_strength_score),
        ("etf_flow_score", inputs.etf_flow_score),
    )


def _unique_narratives(
    observations: Sequence[NarrativeObservation],
) -> dict[NarrativeTheme, NarrativeObservation]:
    unique: dict[NarrativeTheme, NarrativeObservation] = {}
    for observation in observations:
        unique[observation.theme] = observation
    return unique


def _macro_risk_score(inputs: MacroInput) -> Decimal:
    risk = (
        inputs.interest_rate_pressure_score * Decimal("0.12")
        + inputs.fed_hawkishness_score * Decimal("0.10")
        + inputs.ecb_hawkishness_score * Decimal("0.07")
        + inputs.inflation_pressure_score * Decimal("0.12")
        + inputs.cpi_surprise_score * Decimal("0.08")
        + inputs.ppi_surprise_score * Decimal("0.06")
        + inputs.dollar_strength_score * Decimal("0.10")
        + inputs.bond_yield_pressure_score * Decimal("0.10")
        + inputs.gold_safety_bid_score * Decimal("0.06")
        + inputs.oil_inflation_pressure_score * Decimal("0.06")
        + (DECIMAL_ONE - inputs.nasdaq_strength_score) * Decimal("0.06")
        + (DECIMAL_ONE - inputs.sp500_strength_score) * Decimal("0.05")
        + (DECIMAL_ONE - inputs.etf_flow_score) * Decimal("0.02")
    )
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, risk)).quantize(SCORE_QUANT)


def _narrative_rankings(
    observations: tuple[NarrativeObservation, ...],
) -> tuple[NarrativeStrength, ...]:
    rows = [
        (
            observation.theme,
            (
                observation.strength_score * Decimal("0.40")
                + observation.momentum_score * Decimal("0.25")
                + observation.liquidity_score * Decimal("0.20")
                + observation.attention_score * Decimal("0.15")
            ).quantize(SCORE_QUANT),
        )
        for observation in observations
    ]
    ordered = sorted(rows, key=lambda row: (row[1], row[0].value), reverse=True)
    return tuple(
        NarrativeStrength(theme=theme, strength_score=strength, rank=index + 1)
        for index, (theme, strength) in enumerate(ordered)
    )


def _risk_on_score(
    macro: MacroInput, macro_risk_score: Decimal, narrative_strength: Decimal
) -> Decimal:
    equity_strength = (macro.nasdaq_strength_score + macro.sp500_strength_score) / Decimal("2")
    liquidity_impulse = (
        macro.etf_flow_score * Decimal("0.45")
        + equity_strength * Decimal("0.35")
        + narrative_strength * Decimal("0.20")
    )
    score = liquidity_impulse * Decimal("0.60") + (DECIMAL_ONE - macro_risk_score) * Decimal("0.40")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _mode(
    macro_risk_score: Decimal,
    narrative_strength: Decimal,
    risk_on_score: Decimal,
    policy: MacroNarrativePolicy,
) -> MacroNarrativeMode:
    if macro_risk_score >= policy.macro_risk_block_threshold:
        return MacroNarrativeMode.RISK_OFF
    if risk_on_score >= policy.risk_on_threshold:
        return MacroNarrativeMode.RISK_ON
    if narrative_strength >= policy.narrative_strength_threshold:
        return MacroNarrativeMode.NARRATIVE_LED
    return MacroNarrativeMode.NEUTRAL


def _confidence(
    macro: MacroInput,
    narratives: tuple[NarrativeObservation, ...],
    rankings: tuple[NarrativeStrength, ...],
    risk_on_score: Decimal,
) -> Decimal:
    if not narratives:
        return DECIMAL_ZERO
    coverage = min(DECIMAL_ONE, Decimal(len(narratives)) / Decimal("5"))
    leading_strength = rankings[0].strength_score if rankings else DECIMAL_ZERO
    confidence = Decimal("0.45") + coverage * Decimal("0.20")
    confidence += leading_strength * Decimal("0.15") + risk_on_score * Decimal("0.10")
    confidence += macro.etf_flow_score * Decimal("0.10")
    if macro.quality.is_degraded or any(item.quality.is_degraded for item in narratives):
        confidence -= Decimal("0.15")
    if macro.quality.is_rejected or macro.stale:
        confidence = min(confidence, Decimal("0.25"))
    if any(item.quality.is_rejected or item.stale for item in narratives):
        confidence = min(confidence, Decimal("0.25"))
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, confidence)).quantize(SCORE_QUANT)


def _reasons(
    mode: MacroNarrativeMode,
    macro_risk_score: Decimal,
    narrative_strength: Decimal,
    risk_on_score: Decimal,
    leading: NarrativeTheme | None,
) -> tuple[str, ...]:
    reasons = [
        f"macro narrative mode is {mode.value}",
        f"macro risk score is {macro_risk_score}",
        f"narrative strength is {narrative_strength}",
        f"risk-on score is {risk_on_score}",
    ]
    if leading:
        reasons.append(f"leading narrative is {leading.value}")
    return tuple(reasons)


def _evidence(
    macro: MacroInput,
    narratives: tuple[NarrativeObservation, ...],
    rankings: tuple[NarrativeStrength, ...],
    risk_on_score: Decimal,
) -> tuple[MacroNarrativeEvidence, ...]:
    evidence = [
        MacroNarrativeEvidence(
            key=name,
            value=str(value),
            reason=f"{name} supplied as normalized Stage 056 macro input",
            source_ref=macro.source_refs.get(name, f"macro:stage-056:{name}"),
        )
        for name, value in _macro_metric_items(macro)
    ]
    narrative_refs = {item.theme: item.source_ref for item in narratives}
    evidence.extend(
        MacroNarrativeEvidence(
            key=f"{item.theme.value}_narrative_strength",
            value=str(item.strength_score),
            reason=(
                "narrative strength uses normalized strength, momentum, liquidity, and attention"
            ),
            source_ref=narrative_refs[item.theme],
        )
        for item in rankings
    )
    evidence.append(
        MacroNarrativeEvidence(
            key="risk_on_score",
            value=str(risk_on_score),
            reason="risk-on score uses equity strength, ETF flows, narratives, and macro risk",
            source_ref="macro_narrative:stage-056:risk_on_score",
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
        source_ref="macro_narrative:stage-056",
        checked_at=normalize_timestamp(checked_at),
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)
