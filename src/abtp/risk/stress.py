"""Institutional scenario stress testing beyond Monte Carlo."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class StressScenarioType(StrEnum):
    """Institutional stress scenarios tracked by Stage 065."""

    MARKET_CRASH = "market_crash"
    STABLECOIN_DEPEG = "stablecoin_depeg"
    EXCHANGE_INSOLVENCY = "exchange_insolvency"
    FLASH_CRASH = "flash_crash"
    LIQUIDITY_EVAPORATION = "liquidity_evaporation"
    REGULATORY_SHOCK = "regulatory_shock"
    NETWORK_OUTAGE = "network_outage"


class StressRecommendationType(StrEnum):
    """Advisory stress-test recommendation labels."""

    ACCEPT_FOR_REVIEW = "accept_for_review"
    REDUCE_ALLOCATION = "reduce_allocation"
    INCREASE_CASH = "increase_cash"
    PAUSE_NEW_ENTRIES = "pause_new_entries"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class InstitutionalStressPolicy:
    """Conservative Stage 065 stress-test thresholds."""

    ruin_equity_pct: Decimal = Decimal("0.70")
    min_survival_score: Decimal = Decimal("0.80")
    max_worst_drawdown: Decimal = Decimal("0.35")
    max_recovery_days: int = 120
    severe_drawdown_threshold: Decimal = Decimal("0.50")
    policy_version: str = "stage-065.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("ruin_equity_pct", self.ruin_equity_pct),
            ("min_survival_score", self.min_survival_score),
            ("max_worst_drawdown", self.max_worst_drawdown),
            ("severe_drawdown_threshold", self.severe_drawdown_threshold),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_recovery_days < 1:
            raise ValueError("max_recovery_days must be positive")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class StressScenarioDefinition:
    """One deterministic stress scenario definition."""

    scenario_type: StressScenarioType
    severity_pct: Decimal
    risk_asset_loss_multiplier: Decimal
    stablecoin_loss_multiplier: Decimal = DECIMAL_ZERO
    exchange_loss_multiplier: Decimal = DECIMAL_ZERO
    liquidity_haircut_pct: Decimal = DECIMAL_ZERO
    recovery_days: int = 30
    blocks_trading: bool = False
    rationale: str = "institutional stress scenario"
    source_ref: str = "stress:scenario"

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_type", StressScenarioType(self.scenario_type))
        for name, value in (
            ("severity_pct", self.severity_pct),
            ("risk_asset_loss_multiplier", self.risk_asset_loss_multiplier),
            ("stablecoin_loss_multiplier", self.stablecoin_loss_multiplier),
            ("exchange_loss_multiplier", self.exchange_loss_multiplier),
            ("liquidity_haircut_pct", self.liquidity_haircut_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.recovery_days < 0:
            raise ValueError("recovery_days cannot be negative")
        if not self.rationale.strip():
            raise ValueError("scenario rationale is required")
        if not self.source_ref.strip():
            raise ValueError("scenario source_ref is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario_type": self.scenario_type.value,
            "severity_pct": str(self.severity_pct),
            "risk_asset_loss_multiplier": str(self.risk_asset_loss_multiplier),
            "stablecoin_loss_multiplier": str(self.stablecoin_loss_multiplier),
            "exchange_loss_multiplier": str(self.exchange_loss_multiplier),
            "liquidity_haircut_pct": str(self.liquidity_haircut_pct),
            "recovery_days": self.recovery_days,
            "blocks_trading": self.blocks_trading,
            "rationale": self.rationale,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class InstitutionalStressInput:
    """Portfolio exposure context supplied for deterministic scenario tests."""

    starting_equity: Decimal
    cash_pct: Decimal
    risk_asset_exposure_pct: Decimal
    stablecoin_exposure_pct: Decimal
    exchange_exposure_pct: Decimal
    quality: DataQualityStatus
    observed_at: datetime
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        if self.starting_equity <= DECIMAL_ZERO:
            raise ValueError("starting_equity must be positive")
        for name, value in (
            ("cash_pct", self.cash_pct),
            ("risk_asset_exposure_pct", self.risk_asset_exposure_pct),
            ("stablecoin_exposure_pct", self.stablecoin_exposure_pct),
            ("exchange_exposure_pct", self.exchange_exposure_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if (
            self.cash_pct + self.risk_asset_exposure_pct + self.stablecoin_exposure_pct
            > DECIMAL_ONE
        ):
            raise ValueError("cash, risk asset, and stablecoin exposure cannot exceed 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def ruin_equity(self) -> Decimal:
        return self.starting_equity * Decimal("0.70")


@dataclass(frozen=True, slots=True)
class StressScenarioResult:
    """One deterministic stress scenario result."""

    scenario: StressScenarioDefinition
    starting_equity: Decimal
    ending_equity: Decimal
    loss_pct: Decimal
    drawdown_pct: Decimal
    survived: bool
    recovery_days_estimate: int
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.starting_equity <= DECIMAL_ZERO:
            raise ValueError("starting_equity must be positive")
        if self.ending_equity < DECIMAL_ZERO:
            raise ValueError("ending_equity cannot be negative")
        for name, value in (("loss_pct", self.loss_pct), ("drawdown_pct", self.drawdown_pct)):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.recovery_days_estimate < 0:
            raise ValueError("recovery_days_estimate cannot be negative")
        if not self.reasons:
            raise ValueError("stress scenario result requires reasons")

    def as_dict(self) -> dict[str, object]:
        return {
            "scenario": self.scenario.as_dict(),
            "starting_equity": str(self.starting_equity),
            "ending_equity": str(self.ending_equity),
            "loss_pct": str(self.loss_pct),
            "drawdown_pct": str(self.drawdown_pct),
            "survived": self.survived,
            "recovery_days_estimate": self.recovery_days_estimate,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class StressRiskRecommendation:
    """Advisory risk recommendation from stress-test results."""

    recommendation_type: StressRecommendationType
    rationale: str
    severity: DataTrustLevel
    evidence_refs: tuple[str, ...]
    requires_manual_review: bool = True
    can_execute_automatically: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "recommendation_type", StressRecommendationType(self.recommendation_type)
        )
        object.__setattr__(self, "severity", DataTrustLevel(self.severity))
        if not self.rationale.strip():
            raise ValueError("stress recommendation rationale is required")
        if not self.evidence_refs:
            raise ValueError("stress recommendation evidence_refs are required")
        if self.can_execute_automatically:
            raise ValueError("stress recommendations cannot execute automatically")

    def as_dict(self) -> dict[str, object]:
        return {
            "recommendation_type": self.recommendation_type.value,
            "rationale": self.rationale,
            "severity": self.severity.value,
            "evidence_refs": list(self.evidence_refs),
            "requires_manual_review": self.requires_manual_review,
            "can_execute_automatically": self.can_execute_automatically,
        }


@dataclass(frozen=True, slots=True)
class InstitutionalStressReport:
    """Institutional scenario stress-test output with no trading authority."""

    generated_at: datetime
    portfolio_survival_score: Decimal
    worst_case_drawdown: Decimal
    recovery_time_estimate_days: int
    scenario_results: tuple[StressScenarioResult, ...]
    recommendations: tuple[StressRiskRecommendation, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Institutional stress testing is advisory risk evidence only.",
        "Stress reports cannot create signals, risk approvals, order intents, or execution.",
        "Stress scenarios use supplied exposure evidence and deterministic definitions only.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by stress testing.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not DECIMAL_ZERO <= self.portfolio_survival_score <= DECIMAL_ONE:
            raise ValueError("portfolio_survival_score must be between 0 and 1")
        if not DECIMAL_ZERO <= self.worst_case_drawdown <= DECIMAL_ONE:
            raise ValueError("worst_case_drawdown must be between 0 and 1")
        if self.recovery_time_estimate_days < 0:
            raise ValueError("recovery_time_estimate_days cannot be negative")
        if not self.scenario_results:
            raise ValueError("stress report requires scenario results")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("stress report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def acceptable_for_risk_review(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    @property
    def advisory_only(self) -> bool:
        return True

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional stress report cannot create signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional stress report cannot approve risk")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional stress report cannot create order intents")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("institutional stress report cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "portfolio_survival_score": str(self.portfolio_survival_score),
            "worst_case_drawdown": str(self.worst_case_drawdown),
            "recovery_time_estimate_days": self.recovery_time_estimate_days,
            "scenario_results": [result.as_dict() for result in self.scenario_results],
            "recommendations": [item.as_dict() for item in self.recommendations],
            "rejection_reasons": list(self.rejection_reasons),
            "acceptable_for_risk_review": self.acceptable_for_risk_review,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "portfolio_survival_score": str(self.portfolio_survival_score),
            "worst_case_drawdown": str(self.worst_case_drawdown),
            "recovery_time_estimate_days": str(self.recovery_time_estimate_days),
            "scenario_count": len(self.scenario_results),
            "recommendation_count": len(self.recommendations),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def run_institutional_stress_test(
    stress_input: InstitutionalStressInput,
    *,
    scenarios: Sequence[StressScenarioDefinition] | None = None,
    policy: InstitutionalStressPolicy | None = None,
    generated_at: datetime | None = None,
) -> InstitutionalStressReport:
    """Run deterministic institutional stress scenarios."""

    active_policy = policy or InstitutionalStressPolicy()
    active_scenarios = tuple(scenarios or default_stress_scenarios())
    if not active_scenarios:
        raise ValueError("stress scenarios are required")
    checked_at = normalize_timestamp(generated_at or datetime.now(UTC))
    results = tuple(
        _apply_scenario(stress_input, scenario, active_policy) for scenario in active_scenarios
    )
    survival_score = _survival_score(results)
    worst_drawdown = max((result.drawdown_pct for result in results), default=DECIMAL_ZERO)
    recovery_days = max((result.recovery_days_estimate for result in results), default=0)
    rejection_reasons = _rejection_reasons(
        stress_input,
        survival_score,
        worst_drawdown,
        recovery_days,
        active_policy,
    )
    recommendations = _recommendations(results, rejection_reasons, active_policy)
    quality = _quality(
        stress_input,
        rejection_reasons=rejection_reasons,
        checked_at=checked_at,
    )
    return InstitutionalStressReport(
        generated_at=checked_at,
        portfolio_survival_score=survival_score,
        worst_case_drawdown=worst_drawdown,
        recovery_time_estimate_days=recovery_days,
        scenario_results=results,
        recommendations=recommendations,
        rejection_reasons=rejection_reasons,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=stress_input.source_refs,
    )


def default_stress_scenarios() -> tuple[StressScenarioDefinition, ...]:
    """Return deterministic Stage 065 institutional stress definitions."""

    return (
        StressScenarioDefinition(
            scenario_type=StressScenarioType.MARKET_CRASH,
            severity_pct=Decimal("0.70"),
            risk_asset_loss_multiplier=Decimal("1"),
            liquidity_haircut_pct=Decimal("0.04"),
            recovery_days=180,
            rationale="70 percent market crash stress",
            source_ref="stress:market_crash_70",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.STABLECOIN_DEPEG,
            severity_pct=Decimal("0.30"),
            risk_asset_loss_multiplier=Decimal("0"),
            stablecoin_loss_multiplier=Decimal("1"),
            recovery_days=45,
            rationale="stablecoin de-peg stress",
            source_ref="stress:stablecoin_depeg",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.EXCHANGE_INSOLVENCY,
            severity_pct=Decimal("0.60"),
            risk_asset_loss_multiplier=Decimal("0"),
            exchange_loss_multiplier=Decimal("1"),
            recovery_days=240,
            blocks_trading=True,
            rationale="exchange insolvency stress",
            source_ref="stress:exchange_insolvency",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.FLASH_CRASH,
            severity_pct=Decimal("0.40"),
            risk_asset_loss_multiplier=Decimal("1"),
            liquidity_haircut_pct=Decimal("0.08"),
            recovery_days=21,
            rationale="flash crash and spread shock stress",
            source_ref="stress:flash_crash",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.LIQUIDITY_EVAPORATION,
            severity_pct=Decimal("0.25"),
            risk_asset_loss_multiplier=Decimal("1"),
            liquidity_haircut_pct=Decimal("0.12"),
            recovery_days=60,
            rationale="liquidity evaporation stress",
            source_ref="stress:liquidity_evaporation",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.REGULATORY_SHOCK,
            severity_pct=Decimal("0.35"),
            risk_asset_loss_multiplier=Decimal("1"),
            recovery_days=120,
            blocks_trading=True,
            rationale="regulatory shock stress",
            source_ref="stress:regulatory_shock",
        ),
        StressScenarioDefinition(
            scenario_type=StressScenarioType.NETWORK_OUTAGE,
            severity_pct=Decimal("0.12"),
            risk_asset_loss_multiplier=Decimal("0.50"),
            exchange_loss_multiplier=Decimal("0.50"),
            recovery_days=14,
            blocks_trading=True,
            rationale="network outage stress",
            source_ref="stress:network_outage",
        ),
    )


def _apply_scenario(
    stress_input: InstitutionalStressInput,
    scenario: StressScenarioDefinition,
    policy: InstitutionalStressPolicy,
) -> StressScenarioResult:
    scenario_loss_pct = (
        stress_input.risk_asset_exposure_pct
        * scenario.risk_asset_loss_multiplier
        * scenario.severity_pct
        + stress_input.stablecoin_exposure_pct
        * scenario.stablecoin_loss_multiplier
        * scenario.severity_pct
        + stress_input.exchange_exposure_pct
        * scenario.exchange_loss_multiplier
        * scenario.severity_pct
        + stress_input.risk_asset_exposure_pct * scenario.liquidity_haircut_pct
    )
    loss_pct = min(DECIMAL_ONE, scenario_loss_pct).quantize(SCORE_QUANT)
    ending_equity = (stress_input.starting_equity * (DECIMAL_ONE - loss_pct)).quantize(
        Decimal("0.0001")
    )
    ruin_equity = stress_input.starting_equity * policy.ruin_equity_pct
    survived = ending_equity >= ruin_equity
    recovery_days = _recovery_days(scenario, loss_pct)
    return StressScenarioResult(
        scenario=scenario,
        starting_equity=stress_input.starting_equity,
        ending_equity=ending_equity,
        loss_pct=loss_pct,
        drawdown_pct=loss_pct,
        survived=survived,
        recovery_days_estimate=recovery_days,
        reasons=_scenario_reasons(scenario, loss_pct, survived, recovery_days),
    )


def _scenario_reasons(
    scenario: StressScenarioDefinition,
    loss_pct: Decimal,
    survived: bool,
    recovery_days: int,
) -> tuple[str, ...]:
    reasons = [
        f"{scenario.scenario_type.value} loss_pct={loss_pct}",
        f"recovery_days_estimate={recovery_days}",
        "portfolio survived scenario" if survived else "portfolio breached ruin threshold",
    ]
    if scenario.blocks_trading:
        reasons.append("scenario blocks trading access")
    return tuple(reasons)


def _recovery_days(scenario: StressScenarioDefinition, loss_pct: Decimal) -> int:
    severity_multiplier = DECIMAL_ONE + loss_pct
    return int((Decimal(scenario.recovery_days) * severity_multiplier).to_integral_value())


def _survival_score(results: Sequence[StressScenarioResult]) -> Decimal:
    survived_count = sum(1 for result in results if result.survived)
    return (Decimal(survived_count) / Decimal(len(results))).quantize(SCORE_QUANT)


def _rejection_reasons(
    stress_input: InstitutionalStressInput,
    survival_score: Decimal,
    worst_drawdown: Decimal,
    recovery_days: int,
    policy: InstitutionalStressPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if stress_input.quality.is_rejected:
        reasons.append("stress input quality is rejected")
    if stress_input.stale:
        reasons.append("stress input is stale")
    if survival_score < policy.min_survival_score:
        reasons.append(
            f"survival score {survival_score} is below minimum {policy.min_survival_score}"
        )
    if worst_drawdown > policy.max_worst_drawdown:
        reasons.append(f"worst-case drawdown {worst_drawdown} exceeds {policy.max_worst_drawdown}")
    if recovery_days > policy.max_recovery_days:
        reasons.append(f"recovery estimate {recovery_days} days exceeds {policy.max_recovery_days}")
    return tuple(reasons)


def _recommendations(
    results: Sequence[StressScenarioResult],
    rejection_reasons: Sequence[str],
    policy: InstitutionalStressPolicy,
) -> tuple[StressRiskRecommendation, ...]:
    worst_drawdown = max((result.drawdown_pct for result in results), default=DECIMAL_ZERO)
    evidence_refs = tuple(result.scenario.source_ref for result in results)
    recommendations: list[StressRiskRecommendation] = []
    if rejection_reasons:
        recommendations.append(
            StressRiskRecommendation(
                recommendation_type=StressRecommendationType.PAUSE_NEW_ENTRIES,
                rationale="stress test failed safety thresholds",
                severity=DataTrustLevel.REJECTED,
                evidence_refs=evidence_refs,
            )
        )
        recommendations.append(
            StressRiskRecommendation(
                recommendation_type=StressRecommendationType.MANUAL_REVIEW,
                rationale="operator review required before accepting risk exposure",
                severity=DataTrustLevel.REJECTED,
                evidence_refs=evidence_refs,
            )
        )
    elif worst_drawdown > policy.max_worst_drawdown * Decimal("0.75"):
        recommendations.append(
            StressRiskRecommendation(
                recommendation_type=StressRecommendationType.REDUCE_ALLOCATION,
                rationale="stress drawdown is near the configured maximum",
                severity=DataTrustLevel.DEGRADED,
                evidence_refs=evidence_refs,
            )
        )
    else:
        recommendations.append(
            StressRiskRecommendation(
                recommendation_type=StressRecommendationType.ACCEPT_FOR_REVIEW,
                rationale="stress scenarios remained within configured thresholds",
                severity=DataTrustLevel.TRUSTED,
                evidence_refs=evidence_refs,
            )
        )
    if worst_drawdown > policy.severe_drawdown_threshold:
        recommendations.append(
            StressRiskRecommendation(
                recommendation_type=StressRecommendationType.INCREASE_CASH,
                rationale="severe drawdown scenario suggests higher cash reserve review",
                severity=DataTrustLevel.REJECTED,
                evidence_refs=evidence_refs,
            )
        )
    return tuple(recommendations)


def _quality(
    stress_input: InstitutionalStressInput,
    *,
    rejection_reasons: Sequence[str],
    checked_at: datetime,
) -> DataQualityStatus:
    issues = list(stress_input.quality.issues)
    for reason in rejection_reasons:
        issues.append(
            DataQualityIssue(
                flag="institutional_stress_rejection",
                severity=DataTrustLevel.REJECTED,
                reason=reason,
            )
        )
    if stress_input.quality.is_rejected or any(
        issue.severity is DataTrustLevel.REJECTED for issue in issues
    ):
        trust_level = DataTrustLevel.REJECTED
    elif stress_input.quality.is_degraded or issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="risk:institutional_stress",
        checked_at=normalize_timestamp(checked_at),
    )
