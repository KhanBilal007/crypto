"""Deterministic exchange reliability scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from abtp.data.normalization import normalize_timestamp
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class ReliabilityPolicy:
    """Conservative thresholds for adapter reliability evidence."""

    degraded_latency_ms: int = 750
    rejected_latency_ms: int = 2000
    degraded_error_rate: Decimal = Decimal("0.05")
    rejected_error_rate: Decimal = Decimal("0.20")
    min_request_count: int = 1
    policy_version: str = "stage-048.reliability.v1"

    def __post_init__(self) -> None:
        if self.degraded_latency_ms < 0:
            raise ValueError("degraded_latency_ms cannot be negative")
        if self.rejected_latency_ms < self.degraded_latency_ms:
            raise ValueError("rejected_latency_ms must be at least degraded_latency_ms")
        if not DECIMAL_ZERO <= self.degraded_error_rate <= DECIMAL_ONE:
            raise ValueError("degraded_error_rate must be between 0 and 1")
        if not DECIMAL_ZERO <= self.rejected_error_rate <= DECIMAL_ONE:
            raise ValueError("rejected_error_rate must be between 0 and 1")
        if self.rejected_error_rate < self.degraded_error_rate:
            raise ValueError("rejected_error_rate must be at least degraded_error_rate")
        if self.min_request_count <= 0:
            raise ValueError("min_request_count must be positive")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ReliabilityInput:
    """Non-secret observations used to score one exchange reliability window."""

    exchange_name: str
    observed_at: datetime
    request_count: int
    error_count: int
    latency_ms_samples: Sequence[int] = ()
    outage: bool = False
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.exchange_name.strip():
            raise ValueError("exchange_name is required")
        if self.request_count < 0:
            raise ValueError("request_count cannot be negative")
        if self.error_count < 0:
            raise ValueError("error_count cannot be negative")
        if self.error_count > self.request_count:
            raise ValueError("error_count cannot exceed request_count")
        if any(sample < 0 for sample in self.latency_ms_samples):
            raise ValueError("latency samples cannot be negative")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "latency_ms_samples", tuple(self.latency_ms_samples))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def error_rate(self) -> Decimal:
        if self.request_count == 0:
            return DECIMAL_ONE
        return (Decimal(self.error_count) / Decimal(self.request_count)).quantize(SCORE_QUANT)


@dataclass(frozen=True, slots=True)
class ReliabilityScore:
    """Scored adapter reliability evidence for exchange health consumers."""

    exchange_name: str
    observed_at: datetime
    score: Decimal
    error_rate: Decimal
    average_latency_ms: int
    p95_latency_ms: int
    outage: bool
    reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("score must be between 0 and 1")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "exchange_name": self.exchange_name,
            "observed_at": self.observed_at.isoformat(),
            "score": str(self.score),
            "error_rate": str(self.error_rate),
            "average_latency_ms": self.average_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "outage": self.outage,
            "reasons": list(self.reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "exchange_name": self.exchange_name,
            "score": str(self.score),
            "error_rate": str(self.error_rate),
            "average_latency_ms": str(self.average_latency_ms),
            "p95_latency_ms": str(self.p95_latency_ms),
            "outage": str(self.outage),
            "reasons": "|".join(self.reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def score_reliability(
    inputs: ReliabilityInput,
    *,
    policy: ReliabilityPolicy | None = None,
) -> ReliabilityScore:
    """Score reliability from deterministic latency, error, and outage evidence."""

    active_policy = policy or ReliabilityPolicy()
    average_latency = _average_latency(inputs.latency_ms_samples)
    p95_latency = _percentile_95(inputs.latency_ms_samples)
    error_rate = inputs.error_rate
    issues: list[DataQualityIssue] = []
    reasons: list[str] = []

    if inputs.request_count < active_policy.min_request_count:
        reasons.append("insufficient request sample for reliability")
        issues.append(
            DataQualityIssue(
                flag="exchange_reliability_insufficient_sample",
                severity=DataTrustLevel.DEGRADED,
                reason="insufficient request sample for reliability",
            )
        )
    if inputs.outage:
        reasons.append("exchange outage reported")
        issues.append(
            DataQualityIssue(
                flag="exchange_reliability_outage",
                severity=DataTrustLevel.REJECTED,
                reason="exchange outage reported",
            )
        )
    if p95_latency >= active_policy.rejected_latency_ms:
        reasons.append("p95 latency exceeds rejected threshold")
        issues.append(
            DataQualityIssue(
                flag="exchange_reliability_latency_rejected",
                severity=DataTrustLevel.REJECTED,
                reason="p95 latency exceeds rejected threshold",
            )
        )
    elif p95_latency >= active_policy.degraded_latency_ms:
        reasons.append("p95 latency exceeds degraded threshold")
        issues.append(
            DataQualityIssue(
                flag="exchange_reliability_latency_degraded",
                severity=DataTrustLevel.DEGRADED,
                reason="p95 latency exceeds degraded threshold",
            )
        )
    if error_rate >= active_policy.rejected_error_rate:
        reasons.append("error rate exceeds rejected threshold")
        issues.append(
            DataQualityIssue(
                flag="exchange_reliability_error_rate_rejected",
                severity=DataTrustLevel.REJECTED,
                reason="error rate exceeds rejected threshold",
            )
        )
    elif error_rate >= active_policy.degraded_error_rate:
        reasons.append("error rate exceeds degraded threshold")
        issues.append(
            DataQualityIssue(
                flag="exchange_reliability_error_rate_degraded",
                severity=DataTrustLevel.DEGRADED,
                reason="error rate exceeds degraded threshold",
            )
        )

    score = _bounded_score(
        DECIMAL_ONE
        - (error_rate * Decimal("0.60"))
        - _latency_penalty(p95_latency, active_policy)
        - (Decimal("0.75") if inputs.outage else DECIMAL_ZERO)
    )
    quality = _quality_status(issues, inputs.observed_at)
    return ReliabilityScore(
        exchange_name=inputs.exchange_name,
        observed_at=inputs.observed_at,
        score=score,
        error_rate=error_rate,
        average_latency_ms=average_latency,
        p95_latency_ms=p95_latency,
        outage=inputs.outage,
        reasons=tuple(reasons) or ("reliability evidence within policy thresholds",),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _average_latency(samples: Sequence[int]) -> int:
    if not samples:
        return 0
    return int((Decimal(sum(samples)) / Decimal(len(samples))).to_integral_value(ROUND_HALF_UP))


def _percentile_95(samples: Sequence[int]) -> int:
    if not samples:
        return 0
    ordered = sorted(samples)
    index = max(0, int((Decimal("0.95") * Decimal(len(ordered))).to_integral_value()) - 1)
    return ordered[min(index, len(ordered) - 1)]


def _latency_penalty(latency_ms: int, policy: ReliabilityPolicy) -> Decimal:
    if latency_ms <= policy.degraded_latency_ms:
        return DECIMAL_ZERO
    if latency_ms >= policy.rejected_latency_ms:
        return Decimal("0.50")
    span = Decimal(policy.rejected_latency_ms - policy.degraded_latency_ms)
    excess = Decimal(latency_ms - policy.degraded_latency_ms)
    return (excess / span * Decimal("0.50")).quantize(SCORE_QUANT)


def _bounded_score(value: Decimal) -> Decimal:
    return max(DECIMAL_ZERO, min(DECIMAL_ONE, value)).quantize(SCORE_QUANT)


def _quality_status(
    issues: list[DataQualityIssue],
    checked_at: datetime,
) -> DataQualityStatus:
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="exchange:reliability",
        checked_at=checked_at,
    )
