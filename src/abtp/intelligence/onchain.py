"""Advisory on-chain intelligence from supplied blockchain activity metrics."""

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


class OnChainState(StrEnum):
    """High-level advisory on-chain state."""

    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    NETWORK_STRENGTH = "network_strength"
    NETWORK_STRESS = "network_stress"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OnChainPolicy:
    """Conservative thresholds for Stage 053 on-chain intelligence."""

    accumulation_threshold: Decimal = Decimal("0.60")
    distribution_threshold: Decimal = Decimal("0.60")
    network_strength_threshold: Decimal = Decimal("0.70")
    network_stress_threshold: Decimal = Decimal("0.35")
    min_confidence: Decimal = Decimal("0.45")
    policy_version: str = "stage-053.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("accumulation_threshold", self.accumulation_threshold),
            ("distribution_threshold", self.distribution_threshold),
            ("network_strength_threshold", self.network_strength_threshold),
            ("network_stress_threshold", self.network_stress_threshold),
            ("min_confidence", self.min_confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.network_stress_threshold >= self.network_strength_threshold:
            raise ValueError("network_stress_threshold must be below network_strength_threshold")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class OnChainInput:
    """Normalized on-chain metrics supplied by fixtures or future stored providers."""

    observed_at: datetime
    mvrv_score: Decimal
    sopr_score: Decimal
    nupl_score: Decimal
    exchange_inflow_score: Decimal
    exchange_outflow_score: Decimal
    whale_accumulation_score: Decimal
    miner_selling_score: Decimal
    dormancy_score: Decimal
    coin_days_destroyed_score: Decimal
    realized_price_position_score: Decimal
    hash_rate_score: Decimal
    network_growth_score: Decimal
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("mvrv_score", self.mvrv_score),
            ("sopr_score", self.sopr_score),
            ("nupl_score", self.nupl_score),
            ("exchange_inflow_score", self.exchange_inflow_score),
            ("exchange_outflow_score", self.exchange_outflow_score),
            ("whale_accumulation_score", self.whale_accumulation_score),
            ("miner_selling_score", self.miner_selling_score),
            ("dormancy_score", self.dormancy_score),
            ("coin_days_destroyed_score", self.coin_days_destroyed_score),
            ("realized_price_position_score", self.realized_price_position_score),
            ("hash_rate_score", self.hash_rate_score),
            ("network_growth_score", self.network_growth_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class OnChainEvidence:
    """One explainable on-chain metric contribution."""

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
class OnChainAssessment:
    """Advisory on-chain assessment with no trading authority."""

    generated_at: datetime
    state: OnChainState
    on_chain_score: Decimal
    accumulation_score: Decimal
    distribution_score: Decimal
    confidence: Decimal
    reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[OnChainEvidence, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "On-chain intelligence is advisory context only.",
        "It cannot create strategy signals, risk decisions, order intents, or execution.",
        "No blockchain, exchange, or external provider calls are made in this stage.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by on-chain intelligence.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "state", OnChainState(self.state))
        for name, value in (
            ("on_chain_score", self.on_chain_score),
            ("accumulation_score", self.accumulation_score),
            ("distribution_score", self.distribution_score),
            ("confidence", self.confidence),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.reasons:
            raise ValueError("on-chain assessment requires reasons")
        if not self.evidence:
            raise ValueError("on-chain assessment requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("on-chain limitations are required")
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
            "state": self.state.value,
            "on_chain_score": str(self.on_chain_score),
            "accumulation_score": str(self.accumulation_score),
            "distribution_score": str(self.distribution_score),
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
            "state": self.state.value,
            "on_chain_score": str(self.on_chain_score),
            "accumulation_score": str(self.accumulation_score),
            "distribution_score": str(self.distribution_score),
            "confidence": str(self.confidence),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("on-chain intelligence cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("on-chain intelligence cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("on-chain intelligence cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("on-chain intelligence cannot submit orders")


def assess_onchain_intelligence(
    inputs: OnChainInput,
    *,
    generated_at: datetime,
    policy: OnChainPolicy | None = None,
) -> OnChainAssessment:
    """Assess supplied normalized on-chain metrics without provider calls."""

    active_policy = policy or OnChainPolicy()
    rejections: list[str] = []
    issues = list(inputs.quality.issues)
    if inputs.stale:
        reason = "on-chain inputs are stale"
        rejections.append(reason)
        issues.append(_issue("stale_inputs", DataTrustLevel.REJECTED, reason))
    if inputs.quality.is_rejected:
        reason = "on-chain input quality is rejected"
        rejections.append(reason)
        issues.append(_issue("rejected_quality", DataTrustLevel.REJECTED, reason))
    elif inputs.quality.is_degraded:
        issues.append(
            _issue(
                "degraded_quality", DataTrustLevel.DEGRADED, "on-chain input quality is degraded"
            )
        )

    accumulation_score = _accumulation_score(inputs)
    distribution_score = _distribution_score(inputs)
    network_score = _network_score(inputs)
    on_chain_score = _on_chain_score(accumulation_score, distribution_score, network_score)
    state = _state(
        accumulation_score=accumulation_score,
        distribution_score=distribution_score,
        network_score=network_score,
        policy=active_policy,
    )
    confidence = _confidence(
        inputs,
        accumulation_score=accumulation_score,
        distribution_score=distribution_score,
        network_score=network_score,
        state=state,
    )
    if confidence < active_policy.min_confidence:
        reason = "on-chain confidence is below threshold"
        rejections.append(reason)
        issues.append(_issue("low_confidence", DataTrustLevel.REJECTED, reason))
    quality = _quality_status(tuple(issues), bool(rejections), generated_at)
    return OnChainAssessment(
        generated_at=generated_at,
        state=OnChainState.UNKNOWN if rejections else state,
        on_chain_score=on_chain_score,
        accumulation_score=accumulation_score,
        distribution_score=distribution_score,
        confidence=confidence,
        reasons=_reasons(accumulation_score, distribution_score, network_score, state),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=_evidence(inputs, accumulation_score, distribution_score, network_score),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _accumulation_score(inputs: OnChainInput) -> Decimal:
    score = (
        (DECIMAL_ONE - inputs.mvrv_score) * Decimal("0.16")
        + (DECIMAL_ONE - inputs.sopr_score) * Decimal("0.10")
        + (DECIMAL_ONE - inputs.nupl_score) * Decimal("0.08")
        + inputs.exchange_outflow_score * Decimal("0.16")
        + inputs.whale_accumulation_score * Decimal("0.16")
        + (DECIMAL_ONE - inputs.miner_selling_score) * Decimal("0.10")
        + (DECIMAL_ONE - inputs.dormancy_score) * Decimal("0.08")
        + (DECIMAL_ONE - inputs.coin_days_destroyed_score) * Decimal("0.08")
        + inputs.network_growth_score * Decimal("0.08")
    )
    return score.quantize(SCORE_QUANT)


def _distribution_score(inputs: OnChainInput) -> Decimal:
    score = (
        inputs.mvrv_score * Decimal("0.14")
        + inputs.sopr_score * Decimal("0.12")
        + inputs.nupl_score * Decimal("0.12")
        + inputs.exchange_inflow_score * Decimal("0.16")
        + (DECIMAL_ONE - inputs.exchange_outflow_score) * Decimal("0.08")
        + (DECIMAL_ONE - inputs.whale_accumulation_score) * Decimal("0.08")
        + inputs.miner_selling_score * Decimal("0.12")
        + inputs.dormancy_score * Decimal("0.10")
        + inputs.coin_days_destroyed_score * Decimal("0.08")
    )
    return score.quantize(SCORE_QUANT)


def _network_score(inputs: OnChainInput) -> Decimal:
    score = (
        inputs.hash_rate_score * Decimal("0.35")
        + inputs.network_growth_score * Decimal("0.35")
        + inputs.realized_price_position_score * Decimal("0.15")
        + (DECIMAL_ONE - inputs.miner_selling_score) * Decimal("0.15")
    )
    return score.quantize(SCORE_QUANT)


def _on_chain_score(
    accumulation_score: Decimal,
    distribution_score: Decimal,
    network_score: Decimal,
) -> Decimal:
    score = (
        accumulation_score * Decimal("0.35")
        + (DECIMAL_ONE - distribution_score) * Decimal("0.30")
        + network_score * Decimal("0.35")
    )
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)


def _state(
    *,
    accumulation_score: Decimal,
    distribution_score: Decimal,
    network_score: Decimal,
    policy: OnChainPolicy,
) -> OnChainState:
    if distribution_score >= policy.distribution_threshold:
        return OnChainState.DISTRIBUTION
    if accumulation_score >= policy.accumulation_threshold:
        return OnChainState.ACCUMULATION
    if network_score >= policy.network_strength_threshold:
        return OnChainState.NETWORK_STRENGTH
    if network_score <= policy.network_stress_threshold:
        return OnChainState.NETWORK_STRESS
    return OnChainState.NEUTRAL


def _confidence(
    inputs: OnChainInput,
    *,
    accumulation_score: Decimal,
    distribution_score: Decimal,
    network_score: Decimal,
    state: OnChainState,
) -> Decimal:
    separation = abs(accumulation_score - distribution_score)
    network_distance = abs(network_score - Decimal("0.50"))
    base = min(DECIMAL_ONE, Decimal("0.40") + separation + (network_distance * Decimal("0.50")))
    if state in {OnChainState.ACCUMULATION, OnChainState.DISTRIBUTION}:
        base += Decimal("0.05")
    if inputs.quality.is_degraded:
        base *= Decimal("0.60")
    if inputs.quality.is_rejected or inputs.stale:
        base *= Decimal("0.25")
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, base)).quantize(SCORE_QUANT)


def _reasons(
    accumulation_score: Decimal,
    distribution_score: Decimal,
    network_score: Decimal,
    state: OnChainState,
) -> tuple[str, ...]:
    return (
        f"on-chain state {state.value}",
        f"accumulation_score={accumulation_score}",
        f"distribution_score={distribution_score}",
        f"network_score={network_score}",
    )


def _evidence(
    inputs: OnChainInput,
    accumulation_score: Decimal,
    distribution_score: Decimal,
    network_score: Decimal,
) -> tuple[OnChainEvidence, ...]:
    refs = dict(inputs.source_refs)
    entries = (
        ("mvrv", inputs.mvrv_score, "MVRV normalized valuation pressure"),
        ("sopr", inputs.sopr_score, "SOPR normalized spent-output profitability"),
        ("nupl", inputs.nupl_score, "NUPL normalized unrealized profit/loss"),
        ("exchange_inflow", inputs.exchange_inflow_score, "Exchange inflow pressure"),
        ("exchange_outflow", inputs.exchange_outflow_score, "Exchange outflow support"),
        ("whale_wallet_activity", inputs.whale_accumulation_score, "Whale accumulation activity"),
        ("miner_selling", inputs.miner_selling_score, "Miner selling pressure"),
        ("dormancy", inputs.dormancy_score, "Dormancy pressure"),
        ("coin_days_destroyed", inputs.coin_days_destroyed_score, "Coin days destroyed"),
        ("realized_price", inputs.realized_price_position_score, "Realized price position"),
        ("hash_rate", inputs.hash_rate_score, "Hash-rate strength"),
        ("network_growth", inputs.network_growth_score, "Network growth strength"),
    )
    evidence = [
        OnChainEvidence(
            key=key,
            value=str(value),
            reason=reason,
            source_ref=refs.get(key, f"onchain:{key}"),
        )
        for key, value, reason in entries
    ]
    evidence.extend(
        (
            OnChainEvidence(
                "accumulation_score",
                str(accumulation_score),
                "Weighted accumulation score",
                "onchain:accumulation_score",
            ),
            OnChainEvidence(
                "distribution_score",
                str(distribution_score),
                "Weighted distribution score",
                "onchain:distribution_score",
            ),
            OnChainEvidence(
                "network_score",
                str(network_score),
                "Weighted network health score",
                "onchain:network_score",
            ),
        )
    )
    return tuple(evidence)


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
        source_ref="intelligence:onchain",
        checked_at=generated_at,
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=f"onchain_{flag}", severity=severity, reason=reason)
