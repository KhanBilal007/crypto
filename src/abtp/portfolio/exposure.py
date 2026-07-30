"""Exposure aggregation and portfolio constraint helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from abtp.domain import Asset, PortfolioPosition


@dataclass(frozen=True, slots=True)
class AssetExposure:
    """Quote-denominated exposure for one asset."""

    asset: Asset
    quantity: Decimal
    notional: Decimal
    pct_of_equity: Decimal


@dataclass(frozen=True, slots=True)
class ExposureSummary:
    """Aggregated exposure state for risk and portfolio constraints."""

    total_equity: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    exposures: tuple[AssetExposure, ...]

    @property
    def gross_exposure_pct(self) -> Decimal:
        if self.total_equity <= Decimal("0"):
            return Decimal("0")
        return self.gross_exposure / self.total_equity


def aggregate_exposure(
    positions: Sequence[PortfolioPosition],
    *,
    total_equity: Decimal,
) -> ExposureSummary:
    """Aggregate spot exposures from domain portfolio positions."""

    if total_equity <= Decimal("0"):
        raise ValueError("total_equity must be positive")
    by_asset: dict[str, tuple[Asset, Decimal, Decimal]] = {}
    for position in positions:
        asset = position.asset
        _, quantity, notional = by_asset.get(asset.symbol, (asset, Decimal("0"), Decimal("0")))
        by_asset[asset.symbol] = (
            asset,
            quantity + position.quantity,
            notional + position.valuation,
        )
    exposures = tuple(
        AssetExposure(
            asset=asset,
            quantity=quantity,
            notional=notional,
            pct_of_equity=notional / total_equity,
        )
        for asset, quantity, notional in sorted(by_asset.values(), key=lambda item: item[0].symbol)
    )
    gross = sum((abs(item.notional) for item in exposures), Decimal("0"))
    net = sum((item.notional for item in exposures), Decimal("0"))
    return ExposureSummary(
        total_equity=total_equity,
        gross_exposure=gross,
        net_exposure=net,
        exposures=exposures,
    )


def cash_reserve_ratio(*, available_cash: Decimal, total_equity: Decimal) -> Decimal:
    """Return available cash as a share of equity."""

    if total_equity <= Decimal("0"):
        raise ValueError("total_equity must be positive")
    if available_cash < Decimal("0"):
        raise ValueError("available_cash cannot be negative")
    return available_cash / total_equity


def has_min_cash_reserve(
    *,
    available_cash: Decimal,
    total_equity: Decimal,
    min_cash_reserve_pct: Decimal,
) -> bool:
    """Check minimum cash reserve constraint."""

    return cash_reserve_ratio(available_cash=available_cash, total_equity=total_equity) >= (
        min_cash_reserve_pct
    )


def exposure_limit_breached(
    summary: ExposureSummary,
    *,
    max_gross_exposure_pct: Decimal,
) -> bool:
    """Return true when gross exposure exceeds policy."""

    return summary.gross_exposure_pct > max_gross_exposure_pct


def drawdown_limit_breached(
    *,
    current_drawdown_pct: Decimal,
    max_drawdown_pct: Decimal,
) -> bool:
    """Return true when drawdown exceeds policy."""

    return current_drawdown_pct > max_drawdown_pct
