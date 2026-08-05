from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.config import ProfileName
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.universe import (
    AssetUniverseCandidate,
    AssetUniversePolicy,
    AssetUniverseReport,
    AssetUniverseStatus,
    build_dynamic_asset_universe,
)

NOW = datetime(2026, 1, 30, tzinfo=UTC)
TEST_POLICY = AssetUniversePolicy(
    target_min_assets=1,
    target_max_assets=3,
    min_research_score=Decimal("0.40"),
    min_paper_score=Decimal("0.55"),
    min_live_score=Decimal("0.70"),
    min_liquidity_score=Decimal("0.40"),
    min_market_cap_score=Decimal("0.40"),
    min_security_score=Decimal("0.45"),
    min_governance_score=Decimal("0.35"),
)


def test_dynamic_universe_builds_separate_profile_universes() -> None:
    report = build_dynamic_asset_universe(
        _candidates(),
        generated_at=NOW,
        policy=TEST_POLICY,
        source_refs={"candidate_batch": "fixture:stage064"},
    )

    assert report.advisory_only is True
    assert report.quality.is_trusted
    assert report.approved_universes[ProfileName.RESEARCH] == ("BTC", "ETH", "SOL")
    assert report.approved_universes[ProfileName.PAPER] == ("BTC", "ETH", "SOL")
    assert report.approved_universes[ProfileName.LIVE] == ("BTC", "ETH")
    assert report.watchlist == ()
    assert [decision.symbol for decision in report.excluded] == ["MEME"]
    assert report.audit_payload()["live_count"] == 2


def test_newly_validated_asset_is_added_to_live_universe() -> None:
    candidates = (
        *_candidates(),
        _candidate(
            "LINK",
            market=Decimal("0.72"),
            liquidity=Decimal("0.74"),
            security=Decimal("0.76"),
            governance=Decimal("0.70"),
            exchanges=("coinbase", "kraken", "binance"),
            validation_passed=True,
        ),
    )

    report = build_dynamic_asset_universe(candidates, generated_at=NOW, policy=TEST_POLICY)

    assert "LINK" in report.approved_universes[ProfileName.LIVE]
    assert report.decisions[0].symbol == "BTC"
    assert next(item for item in report.decisions if item.symbol == "LINK").approved


def test_asset_removed_when_liquidity_security_or_governance_fails() -> None:
    report = build_dynamic_asset_universe(
        (
            _candidate(
                "WEAK",
                market=Decimal("0.80"),
                liquidity=Decimal("0.20"),
                security=Decimal("0.30"),
                governance=Decimal("0.20"),
                exchanges=("coinbase", "kraken"),
                validation_passed=True,
            ),
        ),
        generated_at=NOW,
        policy=TEST_POLICY,
    )

    decision = report.excluded[0]

    assert decision.status is AssetUniverseStatus.EXCLUDED
    assert "liquidity is below threshold" in decision.exclusion_reasons
    assert "security is below threshold" in decision.exclusion_reasons
    assert "governance is below threshold" in decision.exclusion_reasons
    assert report.quality.is_degraded


def test_degraded_candidate_can_enter_research_only() -> None:
    report = build_dynamic_asset_universe(
        (
            _candidate(
                "ARB",
                market=Decimal("0.68"),
                liquidity=Decimal("0.70"),
                security=Decimal("0.70"),
                governance=Decimal("0.65"),
                exchanges=("coinbase", "kraken"),
                quality=_degraded_quality(),
                validation_passed=True,
            ),
        ),
        generated_at=NOW,
        policy=TEST_POLICY,
    )

    assert report.approved_universes[ProfileName.RESEARCH] == ("ARB",)
    assert report.approved_universes[ProfileName.PAPER] == ()
    assert report.approved_universes[ProfileName.LIVE] == ()


def test_rejected_and_stale_candidates_are_excluded_and_degrade_report() -> None:
    report = build_dynamic_asset_universe(
        (
            _candidate("BAD", quality=_rejected_quality(), validation_passed=True),
            _candidate("OLD", stale=True, validation_passed=True),
        ),
        generated_at=NOW,
        policy=TEST_POLICY,
    )

    assert report.quality.is_degraded
    assert {decision.symbol for decision in report.excluded} == {"BAD", "OLD"}
    assert "rejected_universe_candidates" in report.quality.flags
    assert "stale_universe_candidates" in report.quality.flags


def test_dynamic_universe_report_has_no_trading_authority() -> None:
    report = build_dynamic_asset_universe(_candidates(), generated_at=NOW, policy=TEST_POLICY)

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_dynamic_universe_public_imports_and_dedupes_latest_candidate() -> None:
    report = build_dynamic_asset_universe(
        (
            _candidate("DOT", market=Decimal("0.45"), observed_at=NOW - timedelta(days=1)),
            _candidate(
                "DOT",
                market=Decimal("0.80"),
                liquidity=Decimal("0.82"),
                security=Decimal("0.78"),
                governance=Decimal("0.74"),
                exchanges=("coinbase", "kraken", "binance"),
                observed_at=NOW,
                validation_passed=True,
            ),
        ),
        generated_at=NOW,
        policy=TEST_POLICY,
    )

    assert AssetUniverseReport.__name__ == "AssetUniverseReport"
    assert report.approved_universes[ProfileName.LIVE] == ("DOT",)
    assert len(report.decisions) == 1


def _candidates() -> tuple[AssetUniverseCandidate, ...]:
    return (
        _candidate(
            "BTC",
            market=Decimal("0.95"),
            liquidity=Decimal("0.95"),
            security=Decimal("0.90"),
            governance=Decimal("0.85"),
            exchanges=("coinbase", "kraken", "binance"),
            validation_passed=True,
        ),
        _candidate(
            "ETH",
            market=Decimal("0.88"),
            liquidity=Decimal("0.86"),
            security=Decimal("0.82"),
            governance=Decimal("0.76"),
            exchanges=("coinbase", "kraken", "binance"),
            validation_passed=True,
        ),
        _candidate(
            "SOL",
            market=Decimal("0.72"),
            liquidity=Decimal("0.70"),
            security=Decimal("0.65"),
            governance=Decimal("0.58"),
            exchanges=("coinbase", "kraken"),
            validation_passed=False,
        ),
        _candidate(
            "MEME",
            market=Decimal("0.30"),
            liquidity=Decimal("0.35"),
            security=Decimal("0.28"),
            governance=Decimal("0.25"),
            exchanges=("tiny-exchange",),
        ),
    )


def _candidate(
    symbol: str,
    *,
    market: Decimal = Decimal("0.75"),
    liquidity: Decimal = Decimal("0.75"),
    security: Decimal = Decimal("0.75"),
    governance: Decimal = Decimal("0.75"),
    exchanges: tuple[str, ...] = ("coinbase", "kraken"),
    quality: DataQualityStatus | None = None,
    observed_at: datetime = NOW,
    validation_passed: bool = False,
    stale: bool = False,
) -> AssetUniverseCandidate:
    return AssetUniverseCandidate(
        symbol=symbol,
        observed_at=observed_at,
        market_cap_score=market,
        liquidity_score=liquidity,
        exchange_availability=exchanges,
        security_score=security,
        governance_score=governance,
        quality=quality or _trusted_quality(),
        validation_passed=validation_passed,
        source_refs={"asset": f"fixture:{symbol.lower()}"},
        stale=stale,
    )


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:trusted",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="thin_history",
                severity=DataTrustLevel.DEGRADED,
                reason="fixture history is thin",
            ),
        ),
        source_ref="fixture:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="failed_asset_validation",
                severity=DataTrustLevel.REJECTED,
                reason="fixture asset validation failed",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
