"""Default Bitcoin and crypto dependency parameter catalog."""

from __future__ import annotations

from datetime import timedelta

from abtp.data import DataTrustLevel
from abtp.parameters.registry import (
    FailureBehavior,
    ParameterDefinition,
    ParameterGroup,
    ParameterRegistry,
    StaleBehavior,
)


def default_parameter_registry() -> ParameterRegistry:
    """Build the default Stage 013 parameter registry."""

    return ParameterRegistry(default_parameter_definitions())


def default_parameter_definitions() -> tuple[ParameterDefinition, ...]:
    """Return default Bitcoin/crypto dependency parameter definitions."""

    return (
        _trusted(
            key="price.close",
            group=ParameterGroup.PRICE_ACTION,
            description="Latest trusted close price.",
            refresh=timedelta(minutes=1),
        ),
        _trusted(
            key="price.return_1m",
            group=ParameterGroup.PRICE_ACTION,
            description="One-minute close-to-close return.",
            refresh=timedelta(minutes=1),
        ),
        _trusted(
            key="liquidity.spread_bps",
            group=ParameterGroup.LIQUIDITY,
            description="Order-book spread in basis points.",
            refresh=timedelta(seconds=30),
        ),
        _trusted(
            key="liquidity.depth_top",
            group=ParameterGroup.LIQUIDITY,
            description="Top-of-book available bid and ask depth.",
            refresh=timedelta(seconds=30),
        ),
        _trusted(
            key="liquidity.imbalance",
            group=ParameterGroup.LIQUIDITY,
            description="Bid/ask depth imbalance.",
            refresh=timedelta(seconds=30),
        ),
        _trusted(
            key="volatility.realized_1h",
            group=ParameterGroup.VOLATILITY,
            description="Realized volatility over the last hour.",
            refresh=timedelta(minutes=5),
        ),
        _trusted(
            key="trend.moving_average_state",
            group=ParameterGroup.TREND,
            description="Trend state derived from trusted moving averages.",
            refresh=timedelta(minutes=5),
        ),
        _trusted(
            key="volume.base_volume_1h",
            group=ParameterGroup.VOLUME,
            description="Base asset traded volume over the last hour.",
            refresh=timedelta(minutes=5),
        ),
        _optional_external(
            key="derivatives.funding_rate",
            group=ParameterGroup.DERIVATIVES,
            source_key="external_derivatives_stub",
            description="Optional perpetual funding rate stub.",
            refresh=timedelta(hours=1),
        ),
        _optional_external(
            key="derivatives.open_interest",
            group=ParameterGroup.DERIVATIVES,
            source_key="external_derivatives_stub",
            description="Optional open interest stub.",
            refresh=timedelta(hours=1),
        ),
        _optional_external(
            key="on_chain.hash_rate",
            group=ParameterGroup.ON_CHAIN,
            source_key="external_on_chain_stub",
            description="Optional Bitcoin hash-rate stub.",
            refresh=timedelta(hours=6),
        ),
        _optional_external(
            key="on_chain.exchange_netflow",
            group=ParameterGroup.ON_CHAIN,
            source_key="external_on_chain_stub",
            description="Optional exchange netflow stub.",
            refresh=timedelta(hours=1),
        ),
        _trusted(
            key="cross_asset.eth_btc_return",
            group=ParameterGroup.CROSS_ASSET,
            description="Trusted cross-asset return comparison from stored candles.",
            refresh=timedelta(minutes=5),
        ),
        _optional_external(
            key="macro.usd_liquidity_proxy",
            group=ParameterGroup.MACRO,
            source_key="external_macro_stub",
            description="Optional macro liquidity proxy stub.",
            refresh=timedelta(days=1),
        ),
        _optional_external(
            key="macro.rates_proxy",
            group=ParameterGroup.MACRO,
            source_key="external_macro_stub",
            description="Optional rates proxy stub.",
            refresh=timedelta(days=1),
        ),
        _optional_external(
            key="news_sentiment.bitcoin_sentiment",
            group=ParameterGroup.NEWS_SENTIMENT,
            source_key="external_news_sentiment_stub",
            description="Optional Bitcoin news/sentiment stub.",
            refresh=timedelta(hours=1),
        ),
        _trusted(
            key="exchange_health.stream_status",
            group=ParameterGroup.EXCHANGE_HEALTH,
            source_key="data_quality_engine",
            description="Live stream health status from heartbeat checks.",
            refresh=timedelta(seconds=30),
        ),
        _trusted(
            key="exchange_health.latency_ms",
            group=ParameterGroup.EXCHANGE_HEALTH,
            source_key="data_quality_engine",
            description="Latest stream latency in milliseconds.",
            refresh=timedelta(seconds=30),
        ),
        _trusted(
            key="portfolio.exposure_btc",
            group=ParameterGroup.PORTFOLIO,
            source_key="portfolio_repository",
            description="Current Bitcoin portfolio exposure.",
            refresh=timedelta(minutes=1),
        ),
        _trusted(
            key="portfolio.cash_available",
            group=ParameterGroup.PORTFOLIO,
            source_key="portfolio_repository",
            description="Available quote balance for spot trading decisions.",
            refresh=timedelta(minutes=1),
        ),
        _trusted(
            key="data_quality.market_trust_level",
            group=ParameterGroup.DATA_QUALITY,
            source_key="data_quality_engine",
            description="Aggregate market data trust level.",
            refresh=timedelta(seconds=30),
        ),
        _trusted(
            key="data_quality.flag_count",
            group=ParameterGroup.DATA_QUALITY,
            source_key="data_quality_engine",
            description="Count of active market data quality flags.",
            refresh=timedelta(seconds=30),
        ),
    )


def _trusted(
    *,
    key: str,
    group: ParameterGroup,
    description: str,
    refresh: timedelta,
    source_key: str = "market_data_repository",
) -> ParameterDefinition:
    return ParameterDefinition(
        key=key,
        group=group,
        source_key=source_key,
        description=description,
        refresh_interval=refresh,
        trust_level=DataTrustLevel.TRUSTED,
        stale_behavior=StaleBehavior.REJECT,
        failure_behavior=FailureBehavior.REJECT,
        live_allowed=True,
    )


def _optional_external(
    *,
    key: str,
    group: ParameterGroup,
    source_key: str,
    description: str,
    refresh: timedelta,
) -> ParameterDefinition:
    return ParameterDefinition(
        key=key,
        group=group,
        source_key=source_key,
        description=description,
        refresh_interval=refresh,
        trust_level=DataTrustLevel.DEGRADED,
        stale_behavior=StaleBehavior.DEGRADE,
        failure_behavior=FailureBehavior.OPTIONAL,
        live_allowed=False,
        optional=True,
    )
