from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.intelligence import (
    OpportunityBucket,
    OpportunityCandidate,
    OpportunityDiscoveryPolicy,
    discover_opportunities,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_discovery_report_ranks_top_watch_and_avoid_lists() -> None:
    report = discover_opportunities(_fixture_universe(), generated_at=NOW)

    assert report.universe_size == 5
    assert [item.symbol for item in report.top_opportunities] == ["BTC", "ETH"]
    assert [item.symbol for item in report.watch_list] == ["SOL"]
    assert [item.symbol for item in report.avoid_list] == ["XYZ", "DOGE"]
    assert report.top_opportunities[0].rank == 1
    assert report.top_opportunities[0].opportunity_score == Decimal("0.8888")
    assert report.top_opportunities[0].confidence == Decimal("0.9231")
    assert report.confidence == Decimal("0.6008")
    assert report.actionable_context
    assert report.quality.is_trusted
    assert report.audit_payload()["top_symbols"] == "BTC|ETH"


def test_top_n_policy_limits_top_opportunities() -> None:
    report = discover_opportunities(
        _fixture_universe(),
        generated_at=NOW,
        policy=OpportunityDiscoveryPolicy(top_n=1),
    )

    assert [item.symbol for item in report.top_opportunities] == ["BTC"]
    assert report.top_opportunities[0].rank == 1


def test_stale_or_rejected_candidates_go_to_avoid_list() -> None:
    stale = discover_opportunities(_fixture_universe(stale_symbol="ETH"), generated_at=NOW)
    rejected = discover_opportunities(
        _fixture_universe(quality_symbol="BTC", quality=_rejected_quality()),
        generated_at=NOW,
    )

    stale_eth = _find(stale.avoid_list, "ETH")
    rejected_btc = _find(rejected.avoid_list, "BTC")
    assert "ETH opportunity input is stale" in stale_eth.rejection_reasons
    assert "BTC opportunity quality is rejected" in rejected_btc.rejection_reasons
    assert stale.quality.is_rejected
    assert rejected.quality.is_rejected


def test_degraded_candidate_is_watch_or_avoid_not_top_actionable() -> None:
    report = discover_opportunities(
        _fixture_universe(quality_symbol="BTC", quality=_degraded_quality()),
        generated_at=NOW,
    )

    btc = _find((*report.watch_list, *report.avoid_list), "BTC")
    assert btc.bucket is OpportunityBucket.WATCH
    assert btc.quality.is_degraded
    assert not btc.actionable_context


def test_insufficient_universe_fails_closed() -> None:
    report = discover_opportunities(_fixture_universe()[:2], generated_at=NOW)

    assert not report.actionable_context
    assert report.quality.is_rejected
    assert "not enough opportunity candidates supplied" in report.rejection_reasons


def test_low_confidence_policy_fails_closed() -> None:
    report = discover_opportunities(
        _fixture_universe(),
        generated_at=NOW,
        policy=OpportunityDiscoveryPolicy(min_confidence=Decimal("0.95")),
    )

    assert not report.actionable_context
    assert report.quality.is_rejected
    assert "opportunity discovery confidence is below threshold" in report.rejection_reasons


def test_candidate_validates_score_bounds() -> None:
    with pytest.raises(ValueError, match="technical_score must be between 0 and 1"):
        _candidate("BTC", technical=Decimal("1.10"))


def test_discovery_report_has_no_trading_authority() -> None:
    report = discover_opportunities(_fixture_universe(), generated_at=NOW)

    with pytest.raises(ValueError, match="cannot create signals"):
        report.create_signal()
    with pytest.raises(ValueError, match="cannot create order intents"):
        report.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        report.approve_risk()
    with pytest.raises(ValueError, match="cannot submit orders"):
        report.submit_order()


def test_public_imports_are_available() -> None:
    from abtp.intelligence import (
        OpportunityDiscoveryReport,
        OpportunityEvidence,
        OpportunityRanking,
    )

    assert OpportunityDiscoveryReport is not None
    assert OpportunityEvidence is not None
    assert OpportunityRanking is not None


def _fixture_universe(
    *,
    stale_symbol: str | None = None,
    quality_symbol: str | None = None,
    quality: DataQualityStatus | None = None,
) -> tuple[OpportunityCandidate, ...]:
    return (
        _candidate(
            "BTC",
            Decimal("0.86"),
            Decimal("0.78"),
            Decimal("0.86"),
            Decimal("0.82"),
            Decimal("0.90"),
            Decimal("0.28"),
            Decimal("0.78"),
            Decimal("0.76"),
            Decimal("0.80"),
            stale_symbol,
            quality_symbol,
            quality,
        ),
        _candidate(
            "ETH",
            Decimal("0.82"),
            Decimal("0.76"),
            Decimal("0.78"),
            Decimal("0.72"),
            Decimal("0.84"),
            Decimal("0.34"),
            Decimal("0.80"),
            Decimal("0.78"),
            Decimal("0.74"),
            stale_symbol,
            quality_symbol,
            quality,
        ),
        _candidate(
            "SOL",
            Decimal("0.62"),
            Decimal("0.58"),
            Decimal("0.52"),
            Decimal("0.50"),
            Decimal("0.68"),
            Decimal("0.50"),
            Decimal("0.62"),
            Decimal("0.60"),
            Decimal("0.58"),
            stale_symbol,
            quality_symbol,
            quality,
        ),
        _candidate(
            "DOGE",
            Decimal("0.42"),
            Decimal("0.40"),
            Decimal("0.30"),
            Decimal("0.25"),
            Decimal("0.50"),
            Decimal("0.70"),
            Decimal("0.38"),
            Decimal("0.45"),
            Decimal("0.40"),
            stale_symbol,
            quality_symbol,
            quality,
        ),
        _candidate(
            "XYZ",
            Decimal("0.50"),
            Decimal("0.45"),
            Decimal("0.35"),
            Decimal("0.30"),
            Decimal("0.20"),
            Decimal("0.55"),
            Decimal("0.42"),
            Decimal("0.40"),
            Decimal("0.35"),
            stale_symbol,
            quality_symbol,
            quality,
        ),
    )


def _candidate(
    symbol: str,
    technical: Decimal = Decimal("0.70"),
    ai: Decimal = Decimal("0.70"),
    fundamental: Decimal = Decimal("0.70"),
    onchain: Decimal = Decimal("0.70"),
    liquidity: Decimal = Decimal("0.70"),
    risk: Decimal = Decimal("0.40"),
    relative_strength: Decimal = Decimal("0.70"),
    momentum: Decimal = Decimal("0.70"),
    market_cycle: Decimal = Decimal("0.70"),
    stale_symbol: str | None = None,
    quality_symbol: str | None = None,
    quality: DataQualityStatus | None = None,
) -> OpportunityCandidate:
    return OpportunityCandidate(
        symbol=symbol,
        technical_score=technical,
        ai_score=ai,
        fundamental_score=fundamental,
        onchain_score=onchain,
        liquidity_score=liquidity,
        risk_score=risk,
        relative_strength_score=relative_strength,
        momentum_score=momentum,
        market_cycle_score=market_cycle,
        expected_holding_period="swing",
        quality=quality if symbol == quality_symbol else _trusted_quality(),
        observed_at=NOW,
        stale=symbol == stale_symbol,
        source_refs={"technical_score": f"fixture:opportunity:{symbol}:technical"},
    )


def _find(items: tuple, symbol: str) -> object:
    for item in items:
        if item.symbol == symbol:
            return item
    raise AssertionError(f"{symbol} was not found")


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="fixture:opportunity",
        checked_at=NOW,
    )


def _degraded_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.DEGRADED,
        issues=(
            DataQualityIssue(
                flag="partial_opportunity_coverage",
                severity=DataTrustLevel.DEGRADED,
                reason="some optional opportunity sources are unavailable",
            ),
        ),
        source_ref="fixture:opportunity:degraded",
        checked_at=NOW,
    )


def _rejected_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="malformed_opportunity_payload",
                severity=DataTrustLevel.REJECTED,
                reason="opportunity payload cannot be trusted",
            ),
        ),
        source_ref="fixture:opportunity:rejected",
        checked_at=NOW,
    )
