"""Historical data collection utilities."""

from abtp.data.anomaly import (
    DEFAULT_ANOMALY_THRESHOLDS,
    AnomalyThresholds,
    candle_return,
    is_abnormal_spread,
    is_outlier_return,
    is_provider_disagreement,
    provider_disagreement_bps,
    spread_bps,
)
from abtp.data.heartbeat import HeartbeatMonitor, StreamHealth
from abtp.data.historical_collector import BackfillResult, HistoricalMarketDataCollector
from abtp.data.live_stream import LiveMarketDataStream, LiveMarketDataUpdate
from abtp.data.normalization import (
    expected_close,
    normalize_asset_pair,
    normalize_asset_symbol,
    normalize_candle,
    normalize_interval,
    normalize_provider_payload,
    normalize_timestamp,
    quantize_decimal,
)
from abtp.data.order_book import (
    OrderBookDelta,
    OrderBookMetrics,
    calculate_order_book_metrics,
    diff_order_books,
)
from abtp.data.quality import (
    DataQualityIssue,
    DataQualityStatus,
    DataTrustLevel,
    evaluate_candles,
    evaluate_order_book,
    evaluate_stream_health,
)
from abtp.data.scheduler import BackfillWindow, plan_backfill_windows
from abtp.data.symbols import SUPPORTED_CANDLE_INTERVALS, validate_interval, validate_symbol

__all__ = [
    "BackfillResult",
    "BackfillWindow",
    "DataQualityIssue",
    "DataQualityStatus",
    "DataTrustLevel",
    "DEFAULT_ANOMALY_THRESHOLDS",
    "HeartbeatMonitor",
    "HistoricalMarketDataCollector",
    "LiveMarketDataStream",
    "LiveMarketDataUpdate",
    "OrderBookDelta",
    "OrderBookMetrics",
    "StreamHealth",
    "SUPPORTED_CANDLE_INTERVALS",
    "AnomalyThresholds",
    "calculate_order_book_metrics",
    "candle_return",
    "diff_order_books",
    "evaluate_candles",
    "evaluate_order_book",
    "evaluate_stream_health",
    "expected_close",
    "is_abnormal_spread",
    "is_outlier_return",
    "is_provider_disagreement",
    "normalize_asset_pair",
    "normalize_asset_symbol",
    "normalize_candle",
    "normalize_interval",
    "normalize_provider_payload",
    "normalize_timestamp",
    "plan_backfill_windows",
    "provider_disagreement_bps",
    "quantize_decimal",
    "spread_bps",
    "validate_interval",
    "validate_symbol",
]
