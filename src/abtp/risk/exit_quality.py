"""Exit recommendation quality analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class ExecutionQualityContext(Protocol):
    """Minimal execution-quality shape consumed by exit quality analysis."""

    quality_score: Decimal


@dataclass(frozen=True, slots=True)
class ExitQualityPolicy:
    """Conservative quality thresholds for advisory exit recommendations."""

    max_stop_distance_pct: Decimal = Decimal("0.08")
    min_unrealized_pnl_for_profit_exit: Decimal = Decimal("0.02")
    min_execution_quality_score: Decimal = Decimal("0.70")
    policy_version: str = "stage-046.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("max_stop_distance_pct", self.max_stop_distance_pct),
            ("min_unrealized_pnl_for_profit_exit", self.min_unrealized_pnl_for_profit_exit),
            ("min_execution_quality_score", self.min_execution_quality_score),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ExitQualityReport:
    """Read-only quality context for one advisory exit recommendation."""

    generated_at: datetime
    quality_score: Decimal
    unrealized_pnl_pct: Decimal
    stop_distance_pct: Decimal
    warning_reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not DECIMAL_ZERO <= self.quality_score <= DECIMAL_ONE:
            raise ValueError("quality_score must be between 0 and 1")
        if self.stop_distance_pct < DECIMAL_ZERO:
            raise ValueError("stop_distance_pct cannot be negative")
        if not self.evidence:
            raise ValueError("exit quality report requires evidence")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def acceptable(self) -> bool:
        return not self.rejection_reasons and self.quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "quality_score": str(self.quality_score),
            "unrealized_pnl_pct": str(self.unrealized_pnl_pct),
            "stop_distance_pct": str(self.stop_distance_pct),
            "warning_reasons": list(self.warning_reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "evidence": list(self.evidence),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "quality_score": str(self.quality_score),
            "unrealized_pnl_pct": str(self.unrealized_pnl_pct),
            "stop_distance_pct": str(self.stop_distance_pct),
            "acceptable": str(self.acceptable),
            "warning_reasons": "|".join(self.warning_reasons),
            "rejection_reasons": "|".join(self.rejection_reasons),
            "policy_version": self.policy_version,
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("exit quality report cannot submit orders")

    def cancel_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject cancellation authority."""

        raise ValueError("exit quality report cannot cancel orders")


def analyze_exit_quality(
    *,
    entry_price: Decimal,
    current_price: Decimal,
    stop_price: Decimal,
    generated_at: datetime,
    source_quality: DataQualityStatus,
    execution_quality: ExecutionQualityContext | None = None,
    policy: ExitQualityPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> ExitQualityReport:
    """Build deterministic exit-quality evidence without execution authority."""

    active_policy = policy or ExitQualityPolicy()
    for value, field_name in (
        (entry_price, "entry_price"),
        (current_price, "current_price"),
        (stop_price, "stop_price"),
    ):
        if value <= DECIMAL_ZERO:
            raise ValueError(f"{field_name} must be positive")
    pnl_pct = current_price / entry_price - DECIMAL_ONE
    stop_distance_pct = abs(current_price - stop_price) / current_price
    warnings: list[str] = []
    rejections: list[str] = []
    if stop_distance_pct > active_policy.max_stop_distance_pct:
        warnings.append("stop distance is wide relative to current price")
    if source_quality.is_degraded:
        warnings.append("source quality is degraded")
    if source_quality.is_rejected:
        rejections.append("source quality is rejected")
    if (
        execution_quality is not None
        and execution_quality.quality_score < active_policy.min_execution_quality_score
    ):
        warnings.append("recent execution quality is below preferred threshold")
    score = _score(
        stop_distance_pct=stop_distance_pct,
        source_quality=source_quality,
        execution_quality=execution_quality,
        policy=active_policy,
    )
    quality = _quality_status(warnings, rejections, source_quality, generated_at)
    return ExitQualityReport(
        generated_at=generated_at,
        quality_score=score,
        unrealized_pnl_pct=pnl_pct,
        stop_distance_pct=stop_distance_pct,
        warning_reasons=tuple(dict.fromkeys(warnings)),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        evidence=(
            f"entry_price={entry_price}",
            f"current_price={current_price}",
            f"stop_price={stop_price}",
            f"stop_distance_pct={stop_distance_pct}",
            f"unrealized_pnl_pct={pnl_pct}",
        ),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=source_refs or {},
    )


def _score(
    *,
    stop_distance_pct: Decimal,
    source_quality: DataQualityStatus,
    execution_quality: ExecutionQualityContext | None,
    policy: ExitQualityPolicy,
) -> Decimal:
    score = DECIMAL_ONE
    if policy.max_stop_distance_pct > DECIMAL_ZERO:
        excess_distance = max(DECIMAL_ZERO, stop_distance_pct - policy.max_stop_distance_pct)
        score -= min(Decimal("0.30"), excess_distance / policy.max_stop_distance_pct)
    if source_quality.is_degraded:
        score -= Decimal("0.20")
    if source_quality.is_rejected:
        score -= Decimal("0.60")
    if execution_quality is not None:
        score = min(score, execution_quality.quality_score)
    return min(DECIMAL_ONE, max(DECIMAL_ZERO, score))


def _quality_status(
    warnings: list[str],
    rejections: list[str],
    source_quality: DataQualityStatus,
    generated_at: datetime,
) -> DataQualityStatus:
    issues = [*source_quality.issues]
    issues.extend(
        DataQualityIssue(
            flag="exit_quality_warning",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in warnings
    )
    issues.extend(
        DataQualityIssue(
            flag="exit_quality_rejection",
            severity=DataTrustLevel.REJECTED,
            reason=reason,
        )
        for reason in rejections
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
        source_ref="risk:exit_quality",
        checked_at=generated_at,
    )
