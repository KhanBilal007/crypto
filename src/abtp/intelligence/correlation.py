"""Cross-asset correlation intelligence from supplied return series."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.portfolio.correlation import CorrelationEstimate, estimate_correlation

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")
SCORE_QUANT = Decimal("0.0001")

REQUIRED_TRACKED_SYMBOLS = frozenset({"BTC", "ETH", "NASDAQ", "GOLD", "DXY", "BOND_YIELDS"})


class CrossAssetClass(StrEnum):
    """Asset classes tracked by cross-asset correlation intelligence."""

    CRYPTO = "crypto"
    CRYPTO_SECTOR = "crypto_sector"
    EQUITY = "equity"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    RATES = "rates"
    UNKNOWN = "unknown"


class CorrelationRiskAlertType(StrEnum):
    """Correlation risk alert labels."""

    HIGH_CONCENTRATION = "high_concentration"
    MACRO_RISK_LINKAGE = "macro_risk_linkage"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    STALE_OR_REJECTED_INPUT = "stale_or_rejected_input"


@dataclass(frozen=True, slots=True)
class CrossAssetCorrelationPolicy:
    """Conservative thresholds for Stage 066 correlation intelligence."""

    high_correlation_threshold: Decimal = Decimal("0.75")
    diversification_threshold: Decimal = Decimal("0.35")
    macro_linkage_threshold: Decimal = Decimal("0.50")
    min_sample_count: int = 3
    require_tracked_symbols: bool = True
    policy_version: str = "stage-066.v1"

    def __post_init__(self) -> None:
        if self.min_sample_count < 2:
            raise ValueError("min_sample_count must be at least 2")
        for name, value in (
            ("high_correlation_threshold", self.high_correlation_threshold),
            ("diversification_threshold", self.diversification_threshold),
            ("macro_linkage_threshold", self.macro_linkage_threshold),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.diversification_threshold >= self.high_correlation_threshold:
            raise ValueError("diversification_threshold must be below high_correlation_threshold")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class CrossAssetReturnSeries:
    """Aligned return series supplied by fixtures or upstream storage."""

    symbol: str
    returns: tuple[Decimal, ...]
    asset_class: CrossAssetClass
    quality: DataQualityStatus
    observed_at: datetime
    source_ref: str
    stale: bool = False

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("return series symbol is required")
        if len(self.returns) < 2:
            raise ValueError("return series requires at least two observations")
        if any(not value.is_finite() for value in self.returns):
            raise ValueError("return series values must be finite")
        if not self.source_ref.strip():
            raise ValueError("return series source_ref is required")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "asset_class", CrossAssetClass(self.asset_class))
        object.__setattr__(self, "observed_at", normalize_timestamp(self.observed_at))

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "returns": [str(value) for value in self.returns],
            "asset_class": self.asset_class.value,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "observed_at": self.observed_at.isoformat(),
            "source_ref": self.source_ref,
            "stale": self.stale,
        }


@dataclass(frozen=True, slots=True)
class CorrelationMatrixEntry:
    """One pairwise matrix entry with cross-asset metadata."""

    estimate: CorrelationEstimate
    asset_a_class: CrossAssetClass
    asset_b_class: CrossAssetClass

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_a_class", CrossAssetClass(self.asset_a_class))
        object.__setattr__(self, "asset_b_class", CrossAssetClass(self.asset_b_class))

    @property
    def asset_a(self) -> str:
        return self.estimate.asset_a

    @property
    def asset_b(self) -> str:
        return self.estimate.asset_b

    @property
    def correlation(self) -> Decimal:
        return self.estimate.correlation.quantize(SCORE_QUANT)

    @property
    def sample_count(self) -> int:
        return self.estimate.sample_count

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "asset_a_class": self.asset_a_class.value,
            "asset_b_class": self.asset_b_class.value,
            "correlation": str(self.correlation),
            "sample_count": self.sample_count,
            "source_ref": self.estimate.source_ref,
        }


@dataclass(frozen=True, slots=True)
class DiversificationOpportunity:
    """Potential diversification pair based on low absolute correlation."""

    asset_a: str
    asset_b: str
    correlation: Decimal
    rationale: str
    source_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_a", self.asset_a.upper())
        object.__setattr__(self, "asset_b", self.asset_b.upper())
        if not Decimal("-1") <= self.correlation <= DECIMAL_ONE:
            raise ValueError("diversification correlation must be between -1 and 1")
        if not self.rationale.strip():
            raise ValueError("diversification rationale is required")
        if not self.source_ref.strip():
            raise ValueError("diversification source_ref is required")

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "correlation": str(self.correlation),
            "rationale": self.rationale,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class CorrelationRiskAlert:
    """One cross-asset correlation risk alert."""

    alert_type: CorrelationRiskAlertType
    severity: DataTrustLevel
    message: str
    asset_pair: tuple[str, str] | None
    source_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "alert_type", CorrelationRiskAlertType(self.alert_type))
        object.__setattr__(self, "severity", DataTrustLevel(self.severity))
        if self.asset_pair is not None:
            object.__setattr__(
                self, "asset_pair", tuple(symbol.upper() for symbol in self.asset_pair)
            )
        if not self.message.strip():
            raise ValueError("correlation alert message is required")
        if not self.source_ref.strip():
            raise ValueError("correlation alert source_ref is required")

    def as_dict(self) -> dict[str, object]:
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "asset_pair": list(self.asset_pair) if self.asset_pair else None,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class CrossAssetCorrelationReport:
    """Advisory cross-asset correlation intelligence report."""

    generated_at: datetime
    matrix: tuple[CorrelationMatrixEntry, ...]
    diversification_opportunities: tuple[DiversificationOpportunity, ...]
    risk_alerts: tuple[CorrelationRiskAlert, ...]
    quality: DataQualityStatus
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Cross-asset correlation intelligence is advisory context only.",
        "Correlation output cannot create signals, risk approvals, order intents, or execution.",
        "Correlations are computed from supplied return series only.",
        "Future trading actions must still pass the Risk Management Engine.",
        "No profit is guaranteed by correlation intelligence.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.matrix:
            raise ValueError("cross-asset report requires a correlation matrix")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        if not self.limitations:
            raise ValueError("cross-asset report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def advisory_only(self) -> bool:
        return True

    @property
    def actionable_context(self) -> bool:
        return self.quality.is_trusted and not any(
            alert.severity is DataTrustLevel.REJECTED for alert in self.risk_alerts
        )

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("cross-asset correlation report cannot create signals")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("cross-asset correlation report cannot approve risk")

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("cross-asset correlation report cannot create order intents")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("cross-asset correlation report cannot submit orders")

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "matrix": [entry.as_dict() for entry in self.matrix],
            "diversification_opportunities": [
                opportunity.as_dict() for opportunity in self.diversification_opportunities
            ],
            "risk_alerts": [alert.as_dict() for alert in self.risk_alerts],
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "matrix_count": len(self.matrix),
            "diversification_opportunity_count": len(self.diversification_opportunities),
            "risk_alert_count": len(self.risk_alerts),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
            "policy_version": self.policy_version,
        }


def evaluate_cross_asset_correlation(
    series: Sequence[CrossAssetReturnSeries],
    *,
    generated_at: datetime | None = None,
    policy: CrossAssetCorrelationPolicy | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> CrossAssetCorrelationReport:
    """Build cross-asset correlation matrix, opportunities, and alerts."""

    active_policy = policy or CrossAssetCorrelationPolicy()
    checked_at = normalize_timestamp(generated_at or datetime.now(UTC))
    unique_series = _dedupe_series(series)
    matrix = _matrix(unique_series)
    alerts = _alerts(unique_series, matrix, active_policy)
    opportunities = _opportunities(matrix, active_policy)
    quality = _quality(unique_series, alerts, active_policy, checked_at=checked_at)
    refs = {item.symbol: item.source_ref for item in unique_series}
    refs.update(source_refs or {})
    return CrossAssetCorrelationReport(
        generated_at=checked_at,
        matrix=matrix,
        diversification_opportunities=opportunities,
        risk_alerts=alerts,
        quality=quality,
        policy_version=active_policy.policy_version,
        source_refs=refs,
    )


def _matrix(series: Sequence[CrossAssetReturnSeries]) -> tuple[CorrelationMatrixEntry, ...]:
    entries: list[CorrelationMatrixEntry] = []
    for left_index, left in enumerate(series):
        for right in series[left_index + 1 :]:
            sample_count = min(len(left.returns), len(right.returns))
            estimate = estimate_correlation(
                asset_a=left.symbol,
                asset_b=right.symbol,
                returns_a=left.returns[-sample_count:],
                returns_b=right.returns[-sample_count:],
                source_ref=f"{left.source_ref}|{right.source_ref}",
            )
            entries.append(
                CorrelationMatrixEntry(
                    estimate=estimate,
                    asset_a_class=left.asset_class,
                    asset_b_class=right.asset_class,
                )
            )
    return tuple(sorted(entries, key=lambda item: (item.asset_a, item.asset_b)))


def _opportunities(
    matrix: Sequence[CorrelationMatrixEntry],
    policy: CrossAssetCorrelationPolicy,
) -> tuple[DiversificationOpportunity, ...]:
    opportunities = [
        DiversificationOpportunity(
            asset_a=entry.asset_a,
            asset_b=entry.asset_b,
            correlation=entry.correlation,
            rationale="absolute correlation is below diversification threshold",
            source_ref=entry.estimate.source_ref,
        )
        for entry in matrix
        if abs(entry.correlation) <= policy.diversification_threshold
    ]
    return tuple(
        sorted(opportunities, key=lambda item: (abs(item.correlation), item.asset_a, item.asset_b))
    )


def _alerts(
    series: Sequence[CrossAssetReturnSeries],
    matrix: Sequence[CorrelationMatrixEntry],
    policy: CrossAssetCorrelationPolicy,
) -> tuple[CorrelationRiskAlert, ...]:
    alerts: list[CorrelationRiskAlert] = []
    for item in series:
        if item.quality.is_rejected or item.stale:
            alerts.append(
                CorrelationRiskAlert(
                    alert_type=CorrelationRiskAlertType.STALE_OR_REJECTED_INPUT,
                    severity=DataTrustLevel.REJECTED,
                    message=f"{item.symbol} input is stale or rejected",
                    asset_pair=None,
                    source_ref=item.source_ref,
                )
            )
    for entry in matrix:
        if entry.sample_count < policy.min_sample_count:
            alerts.append(
                CorrelationRiskAlert(
                    alert_type=CorrelationRiskAlertType.INSUFFICIENT_SAMPLE,
                    severity=DataTrustLevel.REJECTED,
                    message=f"{entry.asset_a}/{entry.asset_b} sample count is below threshold",
                    asset_pair=(entry.asset_a, entry.asset_b),
                    source_ref=entry.estimate.source_ref,
                )
            )
        if abs(entry.correlation) >= policy.high_correlation_threshold:
            alerts.append(
                CorrelationRiskAlert(
                    alert_type=CorrelationRiskAlertType.HIGH_CONCENTRATION,
                    severity=DataTrustLevel.DEGRADED,
                    message=f"{entry.asset_a}/{entry.asset_b} correlation is high",
                    asset_pair=(entry.asset_a, entry.asset_b),
                    source_ref=entry.estimate.source_ref,
                )
            )
        if _is_macro_risk_linkage(entry, policy):
            alerts.append(
                CorrelationRiskAlert(
                    alert_type=CorrelationRiskAlertType.MACRO_RISK_LINKAGE,
                    severity=DataTrustLevel.DEGRADED,
                    message=f"BTC has elevated positive linkage to {entry.asset_b}",
                    asset_pair=(entry.asset_a, entry.asset_b),
                    source_ref=entry.estimate.source_ref,
                )
            )
    return tuple(alerts)


def _is_macro_risk_linkage(
    entry: CorrelationMatrixEntry,
    policy: CrossAssetCorrelationPolicy,
) -> bool:
    pair = {entry.asset_a, entry.asset_b}
    macro_symbols = {"DXY", "BOND_YIELDS"}
    return (
        "BTC" in pair
        and bool(pair & macro_symbols)
        and entry.correlation >= policy.macro_linkage_threshold
    )


def _quality(
    series: Sequence[CrossAssetReturnSeries],
    alerts: Sequence[CorrelationRiskAlert],
    policy: CrossAssetCorrelationPolicy,
    *,
    checked_at: datetime,
) -> DataQualityStatus:
    issues = [issue for item in series for issue in item.quality.issues]
    if not series:
        issues.append(
            DataQualityIssue(
                flag="missing_cross_asset_series",
                severity=DataTrustLevel.REJECTED,
                reason="cross-asset correlation requires supplied return series",
            )
        )
    if policy.require_tracked_symbols:
        present = {item.symbol for item in series}
        missing = sorted(REQUIRED_TRACKED_SYMBOLS - present)
        if missing:
            issues.append(
                DataQualityIssue(
                    flag="missing_tracked_cross_assets",
                    severity=DataTrustLevel.REJECTED,
                    reason=f"missing tracked assets: {', '.join(missing)}",
                )
            )
    for alert in alerts:
        issues.append(
            DataQualityIssue(
                flag=f"correlation_{alert.alert_type.value}",
                severity=alert.severity,
                reason=alert.message,
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif any(issue.severity is DataTrustLevel.DEGRADED for issue in issues):
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="intelligence:cross_asset_correlation",
        checked_at=normalize_timestamp(checked_at),
    )


def _dedupe_series(
    series: Sequence[CrossAssetReturnSeries],
) -> tuple[CrossAssetReturnSeries, ...]:
    latest: dict[str, CrossAssetReturnSeries] = {}
    for item in series:
        current = latest.get(item.symbol)
        if current is None or item.observed_at >= current.observed_at:
            latest[item.symbol] = item
    return tuple(sorted(latest.values(), key=lambda item: item.symbol))
