"""Exchange health scoring from supplied adapter and market-health evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data.heartbeat import StreamHealth
from abtp.data.normalization import normalize_timestamp
from abtp.data.order_book import OrderBookMetrics
from abtp.data.quality import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain.models import JsonValue
from abtp.exchanges.permission_gates import (
    PermissionGateInput,
    PermissionGatePolicy,
    PermissionGateRecommendation,
    recommend_permission_gate,
)
from abtp.exchanges.reliability import (
    DECIMAL_ONE,
    DECIMAL_ZERO,
    SCORE_QUANT,
    ReliabilityScore,
)


class ExchangeHealthStatus(StrEnum):
    """Deterministic health status for an exchange venue."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class ExchangeHealthPolicy:
    """Conservative thresholds for scoring venue health."""

    max_spread_bps: Decimal = Decimal("75")
    min_liquidity_depth: Decimal = Decimal("1")
    max_abs_imbalance: Decimal = Decimal("0.75")
    min_health_score: Decimal = Decimal("0.80")
    min_degraded_score: Decimal = Decimal("0.50")
    policy_version: str = "stage-048.health.v1"

    def __post_init__(self) -> None:
        if self.max_spread_bps < DECIMAL_ZERO:
            raise ValueError("max_spread_bps cannot be negative")
        if self.min_liquidity_depth < DECIMAL_ZERO:
            raise ValueError("min_liquidity_depth cannot be negative")
        if not DECIMAL_ZERO <= self.max_abs_imbalance <= DECIMAL_ONE:
            raise ValueError("max_abs_imbalance must be between 0 and 1")
        if not DECIMAL_ZERO <= self.min_degraded_score <= self.min_health_score <= DECIMAL_ONE:
            raise ValueError("health score thresholds must be ordered between 0 and 1")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class ExchangeHealthInput:
    """Supplied evidence for one exchange-health scoring pass."""

    exchange_name: str
    checked_at: datetime
    reliability: ReliabilityScore
    stream_health: StreamHealth | None = None
    order_book_metrics: OrderBookMetrics | None = None
    reconciliation_blocked: bool = False
    reconciliation_quality: DataQualityStatus | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.exchange_name.strip():
            raise ValueError("exchange_name is required")
        if self.exchange_name != self.reliability.exchange_name:
            raise ValueError("exchange_name must match reliability exchange_name")
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class ExchangeHealthScore:
    """Auditable exchange health result and advisory permission gate."""

    exchange_name: str
    checked_at: datetime
    status: ExchangeHealthStatus
    score: Decimal
    reliability: ReliabilityScore
    permission_gate: PermissionGateRecommendation
    spread_bps: Decimal | None
    liquidity_depth: Decimal | None
    imbalance_abs: Decimal | None
    health_reasons: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not DECIMAL_ZERO <= self.score <= DECIMAL_ONE:
            raise ValueError("score must be between 0 and 1")
        if not self.health_reasons:
            raise ValueError("health reasons are required")
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "exchange_name": self.exchange_name,
            "checked_at": self.checked_at.isoformat(),
            "status": self.status.value,
            "score": str(self.score),
            "reliability": self.reliability.as_dict(),
            "permission_gate": self.permission_gate.as_dict(),
            "spread_bps": None if self.spread_bps is None else str(self.spread_bps),
            "liquidity_depth": None if self.liquidity_depth is None else str(self.liquidity_depth),
            "imbalance_abs": None if self.imbalance_abs is None else str(self.imbalance_abs),
            "health_reasons": list(self.health_reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "exchange_name": self.exchange_name,
            "status": self.status.value,
            "score": str(self.score),
            "permission": self.permission_gate.permission.value,
            "block_new_entries": str(self.permission_gate.block_new_entries),
            "pause_trading": str(self.permission_gate.pause_trading),
            "manual_review_required": str(self.permission_gate.manual_review_required),
            "spread_bps": "" if self.spread_bps is None else str(self.spread_bps),
            "liquidity_depth": "" if self.liquidity_depth is None else str(self.liquidity_depth),
            "imbalance_abs": "" if self.imbalance_abs is None else str(self.imbalance_abs),
            "reasons": "|".join(self.health_reasons),
            "rejections": "|".join(self.rejection_reasons),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("exchange health score cannot submit orders")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        """Reject order-intent authority."""

        raise ValueError("exchange health score cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("exchange health score cannot approve risk")


def score_exchange_health(
    inputs: ExchangeHealthInput,
    *,
    policy: ExchangeHealthPolicy | None = None,
    gate_policy: PermissionGatePolicy | None = None,
) -> ExchangeHealthScore:
    """Score exchange health from supplied reliability, stream, and market data."""

    active_policy = policy or ExchangeHealthPolicy()
    issues: list[DataQualityIssue] = [*inputs.reliability.quality.issues]
    reasons: list[str] = [*inputs.reliability.reasons]
    rejections: list[str] = []
    score = inputs.reliability.score

    spread_bps = _spread_bps(inputs.order_book_metrics)
    liquidity_depth = _liquidity_depth(inputs.order_book_metrics)
    imbalance_abs = (
        None if inputs.order_book_metrics is None else abs(inputs.order_book_metrics.imbalance)
    )
    if inputs.order_book_metrics is None:
        reasons.append("order-book metrics are missing")
        issues.append(
            _issue(
                "exchange_health_missing_order_book",
                DataTrustLevel.DEGRADED,
                "order-book metrics are missing",
            )
        )
        score -= Decimal("0.10")
    else:
        if spread_bps is not None and spread_bps > active_policy.max_spread_bps:
            reason = "order-book spread exceeds exchange health threshold"
            reasons.append(reason)
            rejections.append(reason)
            issues.append(_issue("exchange_health_spread", DataTrustLevel.REJECTED, reason))
            score -= Decimal("0.30")
        if liquidity_depth is not None and liquidity_depth < active_policy.min_liquidity_depth:
            reason = "liquidity depth is below exchange health threshold"
            reasons.append(reason)
            rejections.append(reason)
            issues.append(_issue("exchange_health_liquidity", DataTrustLevel.REJECTED, reason))
            score -= Decimal("0.30")
        if imbalance_abs is not None and imbalance_abs > active_policy.max_abs_imbalance:
            reason = "order-book imbalance exceeds exchange health threshold"
            reasons.append(reason)
            issues.append(_issue("exchange_health_imbalance", DataTrustLevel.DEGRADED, reason))
            score -= Decimal("0.10")

    if inputs.stream_health is None:
        reasons.append("stream heartbeat evidence is missing")
        issues.append(
            _issue(
                "exchange_health_missing_stream",
                DataTrustLevel.DEGRADED,
                "stream heartbeat evidence is missing",
            )
        )
        score -= Decimal("0.10")
    else:
        if not inputs.stream_health.is_connected:
            reason = "stream heartbeat is disconnected"
            reasons.append(reason)
            rejections.append(reason)
            issues.append(
                _issue("exchange_health_stream_disconnected", DataTrustLevel.REJECTED, reason)
            )
            score -= Decimal("0.30")
        if inputs.stream_health.is_stale:
            reason = "stream heartbeat is stale"
            reasons.append(reason)
            rejections.append(reason)
            issues.append(_issue("exchange_health_stream_stale", DataTrustLevel.REJECTED, reason))
            score -= Decimal("0.30")
        elif inputs.stream_health.is_degraded:
            reason = "stream heartbeat is degraded"
            reasons.append(reason)
            issues.append(
                _issue("exchange_health_stream_degraded", DataTrustLevel.DEGRADED, reason)
            )
            score -= Decimal("0.10")

    if inputs.reconciliation_quality is not None:
        issues.extend(inputs.reconciliation_quality.issues)
        if inputs.reconciliation_quality.is_rejected:
            reason = "exchange reconciliation quality is rejected"
            reasons.append(reason)
            rejections.append(reason)
            score -= Decimal("0.30")
        elif inputs.reconciliation_quality.is_degraded:
            reasons.append("exchange reconciliation quality is degraded")
            score -= Decimal("0.10")
    if inputs.reconciliation_blocked:
        reason = "exchange reconciliation blocks continuation"
        reasons.append(reason)
        rejections.append(reason)
        issues.append(
            _issue("exchange_health_reconciliation_blocked", DataTrustLevel.REJECTED, reason)
        )
        score -= Decimal("0.30")

    bounded_score = max(DECIMAL_ZERO, min(DECIMAL_ONE, score)).quantize(SCORE_QUANT)
    quality = _quality_status(issues, inputs.checked_at)
    status = _status_for(bounded_score, quality, active_policy)
    refs = _source_refs(inputs)
    gate = recommend_permission_gate(
        PermissionGateInput(
            exchange_name=inputs.exchange_name,
            checked_at=inputs.checked_at,
            health_score=bounded_score,
            health_status=status.value,
            quality=quality,
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            health_reasons=tuple(dict.fromkeys(reasons)),
            source_refs=refs,
        ),
        policy=gate_policy,
    )
    return ExchangeHealthScore(
        exchange_name=inputs.exchange_name,
        checked_at=inputs.checked_at,
        status=status,
        score=bounded_score,
        reliability=inputs.reliability,
        permission_gate=gate,
        spread_bps=spread_bps,
        liquidity_depth=liquidity_depth,
        imbalance_abs=imbalance_abs,
        health_reasons=tuple(dict.fromkeys(reasons)),
        rejection_reasons=tuple(dict.fromkeys(rejections)),
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=refs,
    )


def _spread_bps(metrics: OrderBookMetrics | None) -> Decimal | None:
    if metrics is None:
        return None
    midpoint = (metrics.best_bid + metrics.best_ask) / Decimal("2")
    if midpoint <= DECIMAL_ZERO:
        return None
    return ((metrics.spread / midpoint) * Decimal("10000")).quantize(SCORE_QUANT)


def _liquidity_depth(metrics: OrderBookMetrics | None) -> Decimal | None:
    if metrics is None:
        return None
    return min(metrics.bid_depth, metrics.ask_depth)


def _status_for(
    score: Decimal,
    quality: DataQualityStatus,
    policy: ExchangeHealthPolicy,
) -> ExchangeHealthStatus:
    if quality.is_rejected:
        return ExchangeHealthStatus.UNAVAILABLE
    if score < policy.min_degraded_score:
        return ExchangeHealthStatus.MANUAL_REVIEW
    if quality.is_degraded or score < policy.min_health_score:
        return ExchangeHealthStatus.DEGRADED
    return ExchangeHealthStatus.HEALTHY


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
        source_ref="exchange:health",
        checked_at=checked_at,
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)


def _source_refs(inputs: ExchangeHealthInput) -> Mapping[str, str]:
    refs = dict(inputs.reliability.source_refs)
    refs.update(inputs.source_refs)
    if inputs.reconciliation_quality is not None:
        refs.setdefault("reconciliation_quality", inputs.reconciliation_quality.source_ref)
    return refs
