"""Data-quality status objects and validation rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from abtp.data.anomaly import (
    DEFAULT_ANOMALY_THRESHOLDS,
    AnomalyThresholds,
    is_abnormal_spread,
    is_outlier_return,
    is_provider_disagreement,
)
from abtp.data.heartbeat import StreamHealth
from abtp.data.normalization import expected_close, normalize_candle, normalize_timestamp
from abtp.data.scheduler import interval_delta
from abtp.domain import Candle, OrderBookSnapshot


class DataTrustLevel(StrEnum):
    """Trust state consumed by future strategy and risk modules."""

    TRUSTED = "trusted"
    DEGRADED = "degraded"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """One data-quality flag with severity and explanation."""

    flag: str
    severity: DataTrustLevel
    reason: str


@dataclass(frozen=True, slots=True)
class DataQualityStatus:
    """Aggregate quality status for downstream consumers."""

    trust_level: DataTrustLevel
    issues: tuple[DataQualityIssue, ...]
    source_ref: str
    checked_at: datetime

    @property
    def is_trusted(self) -> bool:
        return self.trust_level is DataTrustLevel.TRUSTED

    @property
    def is_degraded(self) -> bool:
        return self.trust_level is DataTrustLevel.DEGRADED

    @property
    def is_rejected(self) -> bool:
        return self.trust_level is DataTrustLevel.REJECTED

    @property
    def flags(self) -> tuple[str, ...]:
        return tuple(issue.flag for issue in self.issues)

    def require_trusted(self) -> None:
        """Fail closed for future risk/strategy modules."""

        if not self.is_trusted:
            raise ValueError(f"data quality is {self.trust_level.value}: {', '.join(self.flags)}")


def evaluate_candles(
    candles: tuple[Candle, ...],
    *,
    interval: str,
    checked_at: datetime,
    stale_after: timedelta,
    provider_prices: tuple[Decimal, ...] = (),
    thresholds: AnomalyThresholds = DEFAULT_ANOMALY_THRESHOLDS,
) -> DataQualityStatus:
    """Evaluate candle sequence quality."""

    issues: list[DataQualityIssue] = []
    normalized = tuple(normalize_candle(candle) for candle in candles)
    if not normalized:
        issues.append(_issue("missing_candles", DataTrustLevel.REJECTED, "no candles supplied"))
        return _status(issues, source_ref="candles:empty", checked_at=checked_at)

    seen: set[datetime] = set()
    expected_delta = interval_delta(interval)
    previous: Candle | None = None
    for candle in normalized:
        if candle.opened_at in seen:
            issues.append(
                _issue(
                    "duplicate_timestamp",
                    DataTrustLevel.DEGRADED,
                    "duplicate candle opened_at timestamp",
                )
            )
        seen.add(candle.opened_at)
        if candle.open <= Decimal("0") or candle.high <= Decimal("0") or candle.low <= Decimal("0"):
            issues.append(
                _issue("non_positive_price", DataTrustLevel.REJECTED, "price must be positive")
            )
        if candle.close <= Decimal("0"):
            issues.append(
                _issue("non_positive_price", DataTrustLevel.REJECTED, "close must be positive")
            )
        if candle.volume <= Decimal("0"):
            issues.append(_issue("zero_volume", DataTrustLevel.DEGRADED, "volume must be positive"))
        if candle.closed_at != expected_close(candle.opened_at, interval):
            issues.append(
                _issue(
                    "timestamp_drift",
                    DataTrustLevel.DEGRADED,
                    "candle close timestamp does not match interval",
                )
            )
        if previous is not None:
            if candle.opened_at <= previous.opened_at:
                issues.append(
                    _issue(
                        "timestamp_order_error",
                        DataTrustLevel.REJECTED,
                        "candles are not strictly increasing",
                    )
                )
            if candle.opened_at - previous.opened_at != expected_delta:
                issues.append(
                    _issue("missing_candle_gap", DataTrustLevel.DEGRADED, "missing candle gap")
                )
            if is_outlier_return(previous, candle, thresholds):
                issues.append(
                    _issue("outlier_return", DataTrustLevel.DEGRADED, "return exceeds threshold")
                )
        previous = candle

    latest = normalized[-1]
    if normalize_timestamp(checked_at) - latest.closed_at > stale_after:
        issues.append(_issue("stale_data", DataTrustLevel.REJECTED, "latest candle is stale"))
    if provider_prices:
        reference = latest.close
        for provider_price in provider_prices:
            if is_provider_disagreement(reference, provider_price, thresholds):
                issues.append(
                    _issue(
                        "provider_disagreement",
                        DataTrustLevel.DEGRADED,
                        "provider price disagreement exceeds threshold",
                    )
                )
                break

    return _status(
        issues,
        source_ref=f"candles:{latest.pair.symbol}:{latest.interval}:{latest.closed_at.isoformat()}",
        checked_at=checked_at,
    )


def evaluate_order_book(
    snapshot: OrderBookSnapshot,
    *,
    checked_at: datetime,
    stale_after: timedelta,
    thresholds: AnomalyThresholds = DEFAULT_ANOMALY_THRESHOLDS,
) -> DataQualityStatus:
    """Evaluate order-book quality."""

    issues: list[DataQualityIssue] = []
    if normalize_timestamp(checked_at) - normalize_timestamp(snapshot.captured_at) > stale_after:
        issues.append(_issue("stale_data", DataTrustLevel.REJECTED, "order book is stale"))
    if is_abnormal_spread(snapshot, thresholds):
        issues.append(
            _issue("abnormal_spread", DataTrustLevel.DEGRADED, "spread exceeds threshold")
        )
    if any(level.quantity <= Decimal("0") for level in (*snapshot.bids, *snapshot.asks)):
        issues.append(
            _issue("empty_depth", DataTrustLevel.DEGRADED, "order-book depth must be positive")
        )
    return _status(issues, source_ref=snapshot.source_ref, checked_at=checked_at)


def evaluate_stream_health(health: StreamHealth, *, checked_at: datetime) -> DataQualityStatus:
    """Convert stream health into a data-quality status."""

    issues: list[DataQualityIssue] = []
    if health.is_stale:
        issues.append(_issue("stale_data", DataTrustLevel.REJECTED, "stream heartbeat is stale"))
    if health.is_degraded:
        issues.append(
            _issue("degraded_feed", DataTrustLevel.DEGRADED, "stream heartbeat is degraded")
        )
    return _status(issues, source_ref="stream:heartbeat", checked_at=checked_at)


def _status(
    issues: list[DataQualityIssue], *, source_ref: str, checked_at: datetime
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
        source_ref=source_ref,
        checked_at=normalize_timestamp(checked_at),
    )


def _issue(flag: str, severity: DataTrustLevel, reason: str) -> DataQualityIssue:
    return DataQualityIssue(flag=flag, severity=severity, reason=reason)


def now_utc() -> datetime:
    """Return current UTC time for callers that need a default check timestamp."""

    return datetime.now(UTC)
