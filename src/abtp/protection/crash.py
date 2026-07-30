"""Market crash detection and fail-safe protection decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    OrderBookMetrics,
    StreamHealth,
    normalize_timestamp,
)
from abtp.domain.models import JsonValue
from abtp.protection.actions import ProtectiveActionPlan, decimal_bps, plan_protective_actions


class CrashCondition(StrEnum):
    """Abnormal conditions detected by Stage 037."""

    FLASH_CRASH = "flash_crash"
    ABNORMAL_VOLATILITY = "abnormal_volatility"
    EXCHANGE_OUTAGE = "exchange_outage"
    STALE_DATA = "stale_data"
    HIGH_SPREAD = "high_spread"
    LIQUIDITY_COLLAPSE = "liquidity_collapse"
    API_FAILURE = "api_failure"
    REJECTED_DATA_QUALITY = "rejected_data_quality"


@dataclass(frozen=True, slots=True)
class CrashProtectionConfig:
    """Conservative fail-safe thresholds for market crash protection."""

    flash_crash_return_pct: Decimal = Decimal("-0.08")
    abnormal_volatility_pct: Decimal = Decimal("0.05")
    max_spread_bps: Decimal = Decimal("100")
    min_total_depth: Decimal = Decimal("1")
    severe_condition_count: int = 2
    require_manual_recovery_approval: bool = True
    policy_version: str = "stage-037.v1"

    def __post_init__(self) -> None:
        if self.flash_crash_return_pct >= Decimal("0"):
            raise ValueError("flash_crash_return_pct must be negative")
        if self.abnormal_volatility_pct < Decimal("0"):
            raise ValueError("abnormal_volatility_pct cannot be negative")
        if self.max_spread_bps < Decimal("0"):
            raise ValueError("max_spread_bps cannot be negative")
        if self.min_total_depth < Decimal("0"):
            raise ValueError("min_total_depth cannot be negative")
        if self.severe_condition_count <= 0:
            raise ValueError("severe_condition_count must be positive")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class MarketProtectionSnapshot:
    """Inputs used to detect crash-protection conditions."""

    observed_at: datetime
    exchange_name: str
    price_return_pct: Decimal = Decimal("0")
    realized_volatility_pct: Decimal = Decimal("0")
    order_book_metrics: OrderBookMetrics | None = None
    stream_health: StreamHealth | None = None
    data_quality: DataQualityStatus | None = None
    api_failure: bool = False
    pending_order_count: int = 0
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.exchange_name.strip():
            raise ValueError("exchange_name is required")
        if self.realized_volatility_pct < Decimal("0"):
            raise ValueError("realized_volatility_pct cannot be negative")
        if self.pending_order_count < 0:
            raise ValueError("pending_order_count cannot be negative")
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def spread_bps(self) -> Decimal:
        if self.order_book_metrics is None:
            return Decimal("0")
        mid = (self.order_book_metrics.best_bid + self.order_book_metrics.best_ask) / Decimal("2")
        return decimal_bps(self.order_book_metrics.spread, mid)

    @property
    def total_depth(self) -> Decimal:
        if self.order_book_metrics is None:
            return Decimal("0")
        return self.order_book_metrics.bid_depth + self.order_book_metrics.ask_depth


@dataclass(frozen=True, slots=True)
class CrashDetection:
    """One detected crash-protection condition."""

    condition: CrashCondition
    reason: str
    observed: Decimal | str
    limit: Decimal | str
    severe: bool = True

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("crash detection reason is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "condition": self.condition.value,
            "reason": self.reason,
            "observed": str(self.observed),
            "limit": str(self.limit),
            "severe": self.severe,
        }


@dataclass(frozen=True, slots=True)
class CrashProtectionDecision:
    """Fail-safe market protection decision."""

    checked_at: datetime
    protection_active: bool
    block_new_trades: bool
    detections: tuple[CrashDetection, ...]
    action_plan: ProtectiveActionPlan
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "checked_at", normalize_timestamp(self.checked_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(detection.reason for detection in self.detections)

    def require_trading_allowed(self) -> None:
        """Fail closed for future consumers before new trades."""

        if self.block_new_trades:
            raise RuntimeError("; ".join(self.reasons))

    def as_dict(self) -> dict[str, object]:
        return {
            "checked_at": self.checked_at.isoformat(),
            "protection_active": self.protection_active,
            "block_new_trades": self.block_new_trades,
            "detections": [detection.as_dict() for detection in self.detections],
            "action_plan": self.action_plan.as_dict(),
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        """Return a compact append-only audit payload."""

        return {
            "protection_active": str(self.protection_active),
            "block_new_trades": str(self.block_new_trades),
            "conditions": "|".join(detection.condition.value for detection in self.detections),
            "reasons": "|".join(self.reasons),
            "action_types": "|".join(
                action.action_type.value for action in self.action_plan.actions
            ),
            "quality": self.quality.trust_level.value,
            "policy_version": self.policy_version,
        }


def evaluate_market_protection(
    snapshot: MarketProtectionSnapshot,
    *,
    config: CrashProtectionConfig | None = None,
) -> CrashProtectionDecision:
    """Detect abnormal market conditions and return fail-safe protection actions."""

    active_config = config or CrashProtectionConfig()
    detections = _detect(snapshot, active_config)
    severe = (
        sum(1 for detection in detections if detection.severe)
        >= active_config.severe_condition_count
    )
    action_plan = plan_protective_actions(
        tuple(detection.reason for detection in detections),
        checked_at=snapshot.observed_at,
        pending_order_count=snapshot.pending_order_count,
        severe=severe,
    )
    quality = _decision_quality(snapshot, detections)
    return CrashProtectionDecision(
        checked_at=snapshot.observed_at,
        protection_active=bool(detections),
        block_new_trades=bool(detections),
        detections=tuple(detections),
        action_plan=action_plan,
        quality=quality,
        policy_version=active_config.policy_version,
        source_refs=snapshot.source_refs,
    )


def _detect(
    snapshot: MarketProtectionSnapshot,
    config: CrashProtectionConfig,
) -> tuple[CrashDetection, ...]:
    detections: list[CrashDetection] = []
    if snapshot.price_return_pct <= config.flash_crash_return_pct:
        detections.append(
            CrashDetection(
                condition=CrashCondition.FLASH_CRASH,
                reason="flash crash return threshold breached",
                observed=snapshot.price_return_pct,
                limit=f"<= {config.flash_crash_return_pct}",
            )
        )
    if snapshot.realized_volatility_pct >= config.abnormal_volatility_pct:
        detections.append(
            CrashDetection(
                condition=CrashCondition.ABNORMAL_VOLATILITY,
                reason="abnormal volatility threshold breached",
                observed=snapshot.realized_volatility_pct,
                limit=f">= {config.abnormal_volatility_pct}",
            )
        )
    if snapshot.stream_health is not None:
        if not snapshot.stream_health.is_connected:
            detections.append(
                CrashDetection(
                    condition=CrashCondition.EXCHANGE_OUTAGE,
                    reason="exchange data feed is disconnected",
                    observed=snapshot.stream_health.status,
                    limit="connected",
                )
            )
        if snapshot.stream_health.is_stale:
            detections.append(
                CrashDetection(
                    condition=CrashCondition.STALE_DATA,
                    reason="market data is stale",
                    observed=snapshot.stream_health.status,
                    limit="fresh",
                )
            )
    if snapshot.order_book_metrics is not None:
        if snapshot.spread_bps > config.max_spread_bps:
            detections.append(
                CrashDetection(
                    condition=CrashCondition.HIGH_SPREAD,
                    reason="order-book spread exceeds protection threshold",
                    observed=snapshot.spread_bps,
                    limit=f"<= {config.max_spread_bps}",
                )
            )
        if snapshot.total_depth < config.min_total_depth:
            detections.append(
                CrashDetection(
                    condition=CrashCondition.LIQUIDITY_COLLAPSE,
                    reason="order-book depth is below protection threshold",
                    observed=snapshot.total_depth,
                    limit=f">= {config.min_total_depth}",
                )
            )
    if snapshot.api_failure:
        detections.append(
            CrashDetection(
                condition=CrashCondition.API_FAILURE,
                reason="exchange API failure reported",
                observed="failure",
                limit="healthy",
            )
        )
    if snapshot.data_quality is not None and snapshot.data_quality.is_rejected:
        detections.append(
            CrashDetection(
                condition=CrashCondition.REJECTED_DATA_QUALITY,
                reason="market data quality is rejected",
                observed=snapshot.data_quality.trust_level.value,
                limit=DataTrustLevel.TRUSTED.value,
            )
        )
    return tuple(detections)


def _decision_quality(
    snapshot: MarketProtectionSnapshot,
    detections: tuple[CrashDetection, ...],
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = []
    if snapshot.data_quality is not None:
        issues.extend(snapshot.data_quality.issues)
    issues.extend(
        DataQualityIssue(
            flag=f"protection_{detection.condition.value}",
            severity=DataTrustLevel.REJECTED if detection.severe else DataTrustLevel.DEGRADED,
            reason=detection.reason,
        )
        for detection in detections
    )
    if any(
        detection.condition
        in {
            CrashCondition.FLASH_CRASH,
            CrashCondition.EXCHANGE_OUTAGE,
            CrashCondition.STALE_DATA,
            CrashCondition.API_FAILURE,
            CrashCondition.REJECTED_DATA_QUALITY,
        }
        for detection in detections
    ):
        trust_level = DataTrustLevel.REJECTED
    elif detections or (snapshot.data_quality is not None and snapshot.data_quality.is_degraded):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="protection:market_crash",
        checked_at=normalize_timestamp(snapshot.observed_at),
    )
