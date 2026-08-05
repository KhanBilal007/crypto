"""Dynamic asset universe selection from supplied candidate evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.config import ProfileName
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


class AssetUniverseStatus(StrEnum):
    """Dynamic-universe candidate status."""

    APPROVED = "approved"
    WATCHLIST = "watchlist"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class AssetUniversePolicy:
    """Conservative thresholds for Stage 064 dynamic universes."""

    target_min_assets: int = 20
    target_max_assets: int = 30
    min_research_score: Decimal = Decimal("0.45")
    min_paper_score: Decimal = Decimal("0.58")
    min_live_score: Decimal = Decimal("0.72")
    min_liquidity_score: Decimal = Decimal("0.45")
    min_market_cap_score: Decimal = Decimal("0.45")
    min_security_score: Decimal = Decimal("0.50")
    min_governance_score: Decimal = Decimal("0.40")
    min_exchange_count: int = 1
    require_live_validation: bool = True
    policy_version: str = "stage-064.v1"

    def __post_init__(self) -> None:
        if self.target_min_assets < 1:
            raise ValueError("target_min_assets must be positive")
        if self.target_max_assets < self.target_min_assets:
            raise ValueError("target_max_assets cannot be below target_min_assets")
        if self.min_exchange_count < 1:
            raise ValueError("min_exchange_count must be positive")
        for name, value in (
            ("min_research_score", self.min_research_score),
            ("min_paper_score", self.min_paper_score),
            ("min_live_score", self.min_live_score),
            ("min_liquidity_score", self.min_liquidity_score),
            ("min_market_cap_score", self.min_market_cap_score),
            ("min_security_score", self.min_security_score),
            ("min_governance_score", self.min_governance_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.min_research_score <= self.min_paper_score <= self.min_live_score:
            raise ValueError("profile score thresholds must increase from research to live")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class AssetUniverseCandidate:
    """Supplied asset evidence for dynamic-universe selection."""

    symbol: str
    observed_at: datetime
    market_cap_score: Decimal
    liquidity_score: Decimal
    exchange_availability: tuple[str, ...]
    security_score: Decimal
    governance_score: Decimal
    quality: DataQualityStatus
    validation_passed: bool = False
    source_refs: Mapping[str, str] = field(default_factory=dict)
    stale: bool = False

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("asset universe candidate symbol is required")
        for name, value in _candidate_metric_items(self):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        exchanges = tuple(
            sorted(
                {
                    exchange.strip().lower()
                    for exchange in self.exchange_availability
                    if exchange.strip()
                }
            )
        )
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "exchange_availability", exchanges)
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def composite_score(self) -> Decimal:
        """Weighted score used for deterministic ranking."""

        return (
            self.liquidity_score * Decimal("0.35")
            + self.market_cap_score * Decimal("0.25")
            + self.exchange_availability_score * Decimal("0.20")
            + self.security_score * Decimal("0.10")
            + self.governance_score * Decimal("0.10")
        ).quantize(SCORE_QUANT)

    @property
    def exchange_availability_score(self) -> Decimal:
        exchange_count = min(len(self.exchange_availability), 5)
        return (Decimal(exchange_count) / Decimal("5")).quantize(SCORE_QUANT)

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "observed_at": self.observed_at.isoformat(),
            "market_cap_score": str(self.market_cap_score),
            "liquidity_score": str(self.liquidity_score),
            "exchange_availability": list(self.exchange_availability),
            "exchange_availability_score": str(self.exchange_availability_score),
            "security_score": str(self.security_score),
            "governance_score": str(self.governance_score),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "validation_passed": self.validation_passed,
            "composite_score": str(self.composite_score),
            "source_refs": dict(self.source_refs),
            "stale": self.stale,
        }


@dataclass(frozen=True, slots=True)
class AssetUniverseDecision:
    """One candidate's approved/watch/excluded decision."""

    symbol: str
    status: AssetUniverseStatus
    score: Decimal
    approved_profiles: tuple[ProfileName, ...]
    reasons: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]
    quality: DataQualityStatus
    rank: int | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("asset universe decision symbol is required")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "status", AssetUniverseStatus(self.status))
        object.__setattr__(
            self,
            "approved_profiles",
            tuple(ProfileName(profile) for profile in self.approved_profiles),
        )
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("asset universe decision score must be between 0 and 1")
        if self.rank is not None and self.rank < 1:
            raise ValueError("rank must be positive when supplied")
        if not self.reasons:
            raise ValueError("asset universe decision requires reasons")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def approved(self) -> bool:
        return self.status is AssetUniverseStatus.APPROVED

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "status": self.status.value,
            "score": str(self.score),
            "rank": self.rank,
            "approved_profiles": [profile.value for profile in self.approved_profiles],
            "reasons": list(self.reasons),
            "exclusion_reasons": list(self.exclusion_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True, slots=True)
class AssetUniverseReport:
    """Approved, watchlisted, and excluded dynamic-universe outputs."""

    generated_at: datetime
    approved_universes: Mapping[ProfileName, tuple[str, ...]]
    watchlist: tuple[AssetUniverseDecision, ...]
    excluded: tuple[AssetUniverseDecision, ...]
    decisions: tuple[AssetUniverseDecision, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Dynamic asset universe output is advisory configuration context only.",
        "Universe changes cannot create signals, risk decisions, order intents, or execution.",
        "Live universe candidates require explicit validation and separate live approval.",
        "No exchange, market-data, provider, or blockchain calls are made in this stage.",
        "No profit is guaranteed by universe selection.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        normalized_universes = {
            ProfileName(profile): tuple(symbols)
            for profile, symbols in self.approved_universes.items()
        }
        object.__setattr__(self, "approved_universes", normalized_universes)
        object.__setattr__(self, "source_refs", dict(self.source_refs))
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("asset universe report limitations are required")

    @property
    def advisory_only(self) -> bool:
        return True

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("asset universe manager cannot create signals")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("asset universe manager cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("asset universe manager cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("asset universe manager cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "approved_universes": {
                profile.value: list(symbols) for profile, symbols in self.approved_universes.items()
            },
            "watchlist": [decision.as_dict() for decision in self.watchlist],
            "excluded": [decision.as_dict() for decision in self.excluded],
            "decisions": [decision.as_dict() for decision in self.decisions],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "research_count": len(self.approved_universes.get(ProfileName.RESEARCH, ())),
            "paper_count": len(self.approved_universes.get(ProfileName.PAPER, ())),
            "live_count": len(self.approved_universes.get(ProfileName.LIVE, ())),
            "watchlist_count": len(self.watchlist),
            "excluded_count": len(self.excluded),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def build_dynamic_asset_universe(
    candidates: Sequence[AssetUniverseCandidate],
    *,
    generated_at: datetime | None = None,
    policy: AssetUniversePolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> AssetUniverseReport:
    """Select profile-specific universes from supplied deterministic candidates."""

    active_policy = policy or AssetUniversePolicy()
    checked_at = generated_at or datetime.now(UTC)
    unique_candidates = _dedupe_candidates(candidates)
    ranked = tuple(
        sorted(
            unique_candidates, key=lambda candidate: (-candidate.composite_score, candidate.symbol)
        )
    )
    decisions = tuple(
        _decision(candidate, active_policy, rank=index + 1)
        for index, candidate in enumerate(ranked)
    )
    approved_universes = _approved_universes(decisions, active_policy)
    issues = _quality_issues(unique_candidates, approved_universes, active_policy)
    quality = _quality(issues, checked_at=checked_at)
    return AssetUniverseReport(
        generated_at=checked_at,
        approved_universes=approved_universes,
        watchlist=tuple(
            decision for decision in decisions if decision.status is AssetUniverseStatus.WATCHLIST
        ),
        excluded=tuple(
            decision for decision in decisions if decision.status is AssetUniverseStatus.EXCLUDED
        ),
        decisions=decisions,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _decision(
    candidate: AssetUniverseCandidate,
    policy: AssetUniversePolicy,
    *,
    rank: int,
) -> AssetUniverseDecision:
    exclusions = _candidate_exclusion_reasons(candidate, policy)
    profiles = _approved_profiles(candidate, policy, exclusions)
    if profiles:
        status = AssetUniverseStatus.APPROVED
    elif candidate.quality.is_rejected or candidate.stale or exclusions:
        status = AssetUniverseStatus.EXCLUDED
    else:
        status = AssetUniverseStatus.WATCHLIST
    reasons = (
        f"score={candidate.composite_score}",
        f"exchange_count={len(candidate.exchange_availability)}",
        f"status={status.value}",
    )
    return AssetUniverseDecision(
        symbol=candidate.symbol,
        status=status,
        score=candidate.composite_score,
        approved_profiles=profiles,
        rank=rank if status is AssetUniverseStatus.APPROVED else None,
        reasons=reasons,
        exclusion_reasons=tuple(exclusions),
        quality=candidate.quality,
        source_refs=candidate.source_refs,
    )


def _approved_profiles(
    candidate: AssetUniverseCandidate,
    policy: AssetUniversePolicy,
    exclusions: Sequence[str],
) -> tuple[ProfileName, ...]:
    if candidate.quality.is_rejected or candidate.stale or exclusions:
        return ()
    profiles: list[ProfileName] = []
    if candidate.composite_score >= policy.min_research_score:
        profiles.append(ProfileName.RESEARCH)
    if candidate.quality.is_trusted and candidate.composite_score >= policy.min_paper_score:
        profiles.append(ProfileName.PAPER)
    if (
        candidate.quality.is_trusted
        and candidate.composite_score >= policy.min_live_score
        and (candidate.validation_passed or not policy.require_live_validation)
    ):
        profiles.append(ProfileName.LIVE)
    return tuple(profiles)


def _candidate_exclusion_reasons(
    candidate: AssetUniverseCandidate,
    policy: AssetUniversePolicy,
) -> list[str]:
    reasons: list[str] = []
    if candidate.quality.is_rejected:
        reasons.append("candidate quality is rejected")
    if candidate.stale:
        reasons.append("candidate evidence is stale")
    if len(candidate.exchange_availability) < policy.min_exchange_count:
        reasons.append("exchange availability is below threshold")
    if candidate.liquidity_score < policy.min_liquidity_score:
        reasons.append("liquidity is below threshold")
    if candidate.market_cap_score < policy.min_market_cap_score:
        reasons.append("market cap is below threshold")
    if candidate.security_score < policy.min_security_score:
        reasons.append("security is below threshold")
    if candidate.governance_score < policy.min_governance_score:
        reasons.append("governance is below threshold")
    return reasons


def _approved_universes(
    decisions: Sequence[AssetUniverseDecision],
    policy: AssetUniversePolicy,
) -> dict[ProfileName, tuple[str, ...]]:
    universes: dict[ProfileName, tuple[str, ...]] = {}
    for profile in (ProfileName.RESEARCH, ProfileName.PAPER, ProfileName.LIVE):
        symbols = tuple(
            decision.symbol for decision in decisions if profile in decision.approved_profiles
        )[: policy.target_max_assets]
        universes[profile] = symbols
    return universes


def _quality_issues(
    candidates: Sequence[AssetUniverseCandidate],
    approved_universes: Mapping[ProfileName, tuple[str, ...]],
    policy: AssetUniversePolicy,
) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    if not candidates:
        issues.append(
            DataQualityIssue(
                flag="missing_universe_candidates",
                severity=DataTrustLevel.REJECTED,
                reason="dynamic universe requires supplied asset candidates",
            )
        )
    rejected_count = sum(1 for candidate in candidates if candidate.quality.is_rejected)
    stale_count = sum(1 for candidate in candidates if candidate.stale)
    if rejected_count:
        issues.append(
            DataQualityIssue(
                flag="rejected_universe_candidates",
                severity=DataTrustLevel.DEGRADED,
                reason=f"{rejected_count} rejected candidates were excluded",
            )
        )
    if stale_count:
        issues.append(
            DataQualityIssue(
                flag="stale_universe_candidates",
                severity=DataTrustLevel.DEGRADED,
                reason=f"{stale_count} stale candidates were excluded",
            )
        )
    for profile, symbols in approved_universes.items():
        if len(symbols) < policy.target_min_assets:
            issues.append(
                DataQualityIssue(
                    flag=f"{profile.value}_universe_below_target_min",
                    severity=DataTrustLevel.DEGRADED,
                    reason=f"{profile.value} universe has {len(symbols)} approved assets",
                )
            )
    return issues


def _quality(
    issues: Sequence[DataQualityIssue],
    *,
    checked_at: datetime,
) -> DataQualityStatus:
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif any(issue.severity is DataTrustLevel.DEGRADED for issue in issues):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="dynamic_asset_universe",
        checked_at=normalize_timestamp(checked_at),
    )


def _dedupe_candidates(
    candidates: Sequence[AssetUniverseCandidate],
) -> tuple[AssetUniverseCandidate, ...]:
    best: dict[str, AssetUniverseCandidate] = {}
    for candidate in candidates:
        current = best.get(candidate.symbol)
        if current is None or candidate.observed_at >= current.observed_at:
            best[candidate.symbol] = candidate
    return tuple(best.values())


def _candidate_metric_items(
    candidate: AssetUniverseCandidate,
) -> tuple[tuple[str, Decimal], ...]:
    return (
        ("market_cap_score", candidate.market_cap_score),
        ("liquidity_score", candidate.liquidity_score),
        ("security_score", candidate.security_score),
        ("governance_score", candidate.governance_score),
    )
