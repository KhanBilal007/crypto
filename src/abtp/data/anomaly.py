"""Conservative anomaly detection utilities for market data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abtp.data.order_book import calculate_order_book_metrics
from abtp.domain import Candle, OrderBookSnapshot


@dataclass(frozen=True, slots=True)
class AnomalyThresholds:
    """Default thresholds for conservative data-quality checks."""

    max_abs_return: Decimal = Decimal("0.25")
    max_spread_bps: Decimal = Decimal("100")
    max_provider_price_disagreement_bps: Decimal = Decimal("50")


DEFAULT_ANOMALY_THRESHOLDS = AnomalyThresholds()


def candle_return(previous: Candle, current: Candle) -> Decimal:
    """Return close-to-close candle return."""

    if previous.close <= Decimal("0"):
        raise ValueError("previous close must be positive")
    return (current.close - previous.close) / previous.close


def is_outlier_return(
    previous: Candle,
    current: Candle,
    thresholds: AnomalyThresholds = DEFAULT_ANOMALY_THRESHOLDS,
) -> bool:
    """Detect an abnormal close-to-close return."""

    return abs(candle_return(previous, current)) > thresholds.max_abs_return


def spread_bps(snapshot: OrderBookSnapshot) -> Decimal:
    """Calculate order-book spread in basis points."""

    metrics = calculate_order_book_metrics(snapshot)
    midpoint = (metrics.best_bid + metrics.best_ask) / Decimal("2")
    if midpoint <= Decimal("0"):
        raise ValueError("order-book midpoint must be positive")
    return metrics.spread / midpoint * Decimal("10000")


def is_abnormal_spread(
    snapshot: OrderBookSnapshot,
    thresholds: AnomalyThresholds = DEFAULT_ANOMALY_THRESHOLDS,
) -> bool:
    """Detect an abnormal bid/ask spread."""

    return spread_bps(snapshot) > thresholds.max_spread_bps


def provider_disagreement_bps(reference_price: Decimal, provider_price: Decimal) -> Decimal:
    """Return absolute provider disagreement in basis points."""

    if reference_price <= Decimal("0"):
        raise ValueError("reference_price must be positive")
    return abs(provider_price - reference_price) / reference_price * Decimal("10000")


def is_provider_disagreement(
    reference_price: Decimal,
    provider_price: Decimal,
    thresholds: AnomalyThresholds = DEFAULT_ANOMALY_THRESHOLDS,
) -> bool:
    """Detect conflicting provider prices."""

    return (
        provider_disagreement_bps(reference_price, provider_price)
        > thresholds.max_provider_price_disagreement_bps
    )
