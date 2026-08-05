"""Named ABTP environment profiles and safe defaults."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from enum import StrEnum

from abtp.config.settings import (
    AppSettings,
    FeeAssumptions,
    RiskLimits,
    RuntimeSettings,
    TradingMode,
)


class ProfileName(StrEnum):
    """Supported configuration profiles."""

    RESEARCH = "research"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


_BASE_RISK_LIMITS = RiskLimits(
    max_order_notional=Decimal("1000"),
    max_position_percent=Decimal("0.10"),
    max_daily_loss_percent=Decimal("0.02"),
    max_open_orders=5,
)

_BASE_FEES = FeeAssumptions(
    maker_fee_bps=Decimal("10"),
    taker_fee_bps=Decimal("20"),
    slippage_ceiling_bps=Decimal("50"),
)


def default_profile(profile: ProfileName) -> AppSettings:
    """Return immutable defaults for a named profile."""

    base = AppSettings(
        profile=profile,
        runtime=RuntimeSettings(
            environment=profile.value,
            safe_mode=True,
            trading_mode=TradingMode.PAPER,
            enable_live_trading_requested=False,
        ),
        exchange_names=("coinbase", "kraken"),
        asset_universe=("BTC", "USDT"),
        candle_intervals=("1m", "5m", "15m", "1h", "4h", "1d"),
        data_providers=("fixture",),
        database_url="sqlite:///./abtp.sqlite3",
        risk_limits=_BASE_RISK_LIMITS,
        fee_assumptions=_BASE_FEES,
        paper_trading_enabled=False,
        live_trading_enabled=False,
    )

    if profile is ProfileName.RESEARCH:
        return replace(
            base,
            data_providers=("fixture", "local-research"),
            runtime=replace(base.runtime, trading_mode=TradingMode.RESEARCH),
        )
    if profile is ProfileName.BACKTEST:
        return replace(
            base,
            data_providers=("fixture", "historical"),
            runtime=replace(base.runtime, trading_mode=TradingMode.BACKTEST),
        )
    if profile is ProfileName.PAPER:
        return replace(
            base,
            paper_trading_enabled=True,
            data_providers=("fixture", "paper"),
            runtime=replace(base.runtime, trading_mode=TradingMode.PAPER),
        )
    if profile is ProfileName.LIVE:
        return replace(
            base,
            data_providers=("live-market-data",),
            runtime=replace(
                base.runtime,
                safe_mode=True,
                trading_mode=TradingMode.LIVE,
                enable_live_trading_requested=False,
            ),
        )

    raise ValueError(f"unsupported profile: {profile}")
