from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    CorrelationRiskAlertType,
    CrossAssetClass,
    CrossAssetCorrelationPolicy,
    CrossAssetCorrelationReport,
    CrossAssetReturnSeries,
    evaluate_cross_asset_correlation,
)

NOW = datetime(2026, 2, 5, tzinfo=UTC)


def test_cross_asset_correlation_builds_matrix_opportunities_and_alerts() -> None:
    report = evaluate_cross_asset_correlation(
        _series(),
        generated_at=NOW,
        source_refs={"window": "fixture:stage066"},
    )

    assert report.advisory_only is True
    assert report.quality.is_degraded
    assert len(report.matrix) == 21
    assert any(
        entry.asset_a == "BTC" and entry.asset_b == "ETH" and entry.correlation > Decimal("0.99")
        for entry in report.matrix
    )
    assert any(
        {item.asset_a, item.asset_b} == {"GOLD", "SECTOR_AI"}
        for item in report.diversification_opportunities
    )
    alert_types = {alert.alert_type for alert in report.risk_alerts}
    assert CorrelationRiskAlertType.HIGH_CONCENTRATION in alert_types
    assert CorrelationRiskAlertType.MACRO_RISK_LINKAGE in alert_types
    assert report.audit_payload()["matrix_count"] == 21


def test_missing_required_cross_assets_fail_closed() -> None:
    report = evaluate_cross_asset_correlation(
        _series(symbols=("BTC", "ETH", "NASDAQ")),
        generated_at=NOW,
    )

    assert report.quality.is_rejected
    assert "missing_tracked_cross_assets" in report.quality.flags
    assert not report.actionable_context


def test_stale_or_rejected_cross_asset_inputs_fail_closed() -> None:
    report = evaluate_cross_asset_correlation(
        (
            *_series(),
            _return_series(
                "DOGE",
                (Decimal("0.01"), Decimal("0.01"), Decimal("-0.02")),
                CrossAssetClass.CRYPTO,
                quality=_rejected_quality(),
                stale=True,
            ),
        ),
        generated_at=NOW,
        policy=CrossAssetCorrelationPolicy(require_tracked_symbols=False),
    )

    assert report.quality.is_rejected
    assert CorrelationRiskAlertType.STALE_OR_REJECTED_INPUT in {
        alert.alert_type for alert in report.risk_alerts
    }
    assert "correlation_stale_or_rejected_input" in report.quality.flags


def test_insufficient_sample_alert_rejects_report() -> None:
    report = evaluate_cross_asset_correlation(
        _series(),
        generated_at=NOW,
        policy=CrossAssetCorrelationPolicy(min_sample_count=6),
    )

    assert report.quality.is_rejected
    assert CorrelationRiskAlertType.INSUFFICIENT_SAMPLE in {
        alert.alert_type for alert in report.risk_alerts
    }


def test_cross_asset_report_has_no_signal_risk_or_order_authority() -> None:
    report = evaluate_cross_asset_correlation(_series(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_cross_asset_public_imports_and_dedupes_latest_series() -> None:
    report = evaluate_cross_asset_correlation(
        (
            *_series(),
            _return_series(
                "BTC",
                (Decimal("-0.01"), Decimal("-0.02"), Decimal("0.01")),
                CrossAssetClass.CRYPTO,
                observed_at=datetime(2026, 2, 6, tzinfo=UTC),
            ),
        ),
        generated_at=NOW,
    )

    assert CrossAssetCorrelationReport.__name__ == "CrossAssetCorrelationReport"
    btc_eth = next(
        entry for entry in report.matrix if {entry.asset_a, entry.asset_b} == {"BTC", "ETH"}
    )
    assert btc_eth.sample_count == 3


def _series(symbols: tuple[str, ...] | None = None) -> tuple[CrossAssetReturnSeries, ...]:
    all_series = {
        "BTC": _return_series(
            "BTC",
            (Decimal("0.01"), Decimal("0.02"), Decimal("-0.01"), Decimal("0.03"), Decimal("-0.02")),
            CrossAssetClass.CRYPTO,
        ),
        "ETH": _return_series(
            "ETH",
            (
                Decimal("0.011"),
                Decimal("0.018"),
                Decimal("-0.009"),
                Decimal("0.028"),
                Decimal("-0.018"),
            ),
            CrossAssetClass.CRYPTO,
        ),
        "SECTOR_AI": _return_series(
            "SECTOR_AI",
            (Decimal("0.03"), Decimal("-0.01"), Decimal("0.02"), Decimal("-0.02"), Decimal("0.01")),
            CrossAssetClass.CRYPTO_SECTOR,
        ),
        "NASDAQ": _return_series(
            "NASDAQ",
            (
                Decimal("0.005"),
                Decimal("0.01"),
                Decimal("-0.004"),
                Decimal("0.011"),
                Decimal("-0.006"),
            ),
            CrossAssetClass.EQUITY,
        ),
        "GOLD": _return_series(
            "GOLD",
            (
                Decimal("-0.002"),
                Decimal("0.001"),
                Decimal("0"),
                Decimal("-0.001"),
                Decimal("0.002"),
            ),
            CrossAssetClass.COMMODITY,
        ),
        "DXY": _return_series(
            "DXY",
            (
                Decimal("0.004"),
                Decimal("0.008"),
                Decimal("-0.003"),
                Decimal("0.010"),
                Decimal("-0.004"),
            ),
            CrossAssetClass.CURRENCY,
        ),
        "BOND_YIELDS": _return_series(
            "BOND_YIELDS",
            (
                Decimal("0.003"),
                Decimal("0.006"),
                Decimal("-0.002"),
                Decimal("0.008"),
                Decimal("-0.003"),
            ),
            CrossAssetClass.RATES,
        ),
    }
    selected = symbols or tuple(all_series)
    return tuple(all_series[symbol] for symbol in selected)


def _return_series(
    symbol: str,
    returns: tuple[Decimal, ...],
    asset_class: CrossAssetClass,
    *,
    quality: DataQualityStatus | None = None,
    stale: bool = False,
    observed_at: datetime = NOW,
) -> CrossAssetReturnSeries:
    return CrossAssetReturnSeries(
        symbol=symbol,
        returns=returns,
        asset_class=asset_class,
        quality=quality or _trusted_quality(symbol),
        observed_at=observed_at,
        source_ref=f"fixture:{symbol.lower()}",
        stale=stale,
    )


def _trusted_quality(symbol: str) -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=f"fixture:{symbol.lower()}:quality",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_return_series",
                severity=DataTrustLevel.REJECTED,
                reason="fixture return series rejected",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
