from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.data import DataTrustLevel
from abtp.parameters import (
    FailureBehavior,
    ParameterDefinition,
    ParameterGroup,
    ParameterRegistry,
    StaleBehavior,
    default_parameter_definitions,
    default_parameter_registry,
    default_sources,
)
from abtp.parameters.registry import decimal_value

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_default_registry_covers_required_groups() -> None:
    registry = default_parameter_registry()
    groups = {definition.group for definition in registry.all()}

    assert groups == set(ParameterGroup)
    assert registry.get("price.close").group is ParameterGroup.PRICE_ACTION
    assert registry.get("data_quality.market_trust_level").source_key == "data_quality_engine"


def test_registry_lookup_by_group_source_live_and_trust() -> None:
    registry = default_parameter_registry()

    assert registry.by_group(ParameterGroup.LIQUIDITY)
    assert registry.by_source("external_on_chain_stub")
    assert all(definition.live_allowed for definition in registry.by_live_allowed(True))
    assert all(
        not definition.live_allowed for definition in registry.by_source("external_macro_stub")
    )
    assert all(
        definition.trust_level is DataTrustLevel.DEGRADED
        for definition in registry.by_trust_level(DataTrustLevel.DEGRADED)
    )


def test_schema_validation_rejects_unsafe_live_and_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="live-allowed parameters must be trusted"):
        ParameterDefinition(
            key="bad.live",
            group=ParameterGroup.MACRO,
            source_key="external_macro_stub",
            description="bad",
            refresh_interval=timedelta(minutes=1),
            trust_level=DataTrustLevel.DEGRADED,
            stale_behavior=StaleBehavior.DEGRADE,
            failure_behavior=FailureBehavior.OPTIONAL,
            live_allowed=True,
            optional=True,
        )

    definition = default_parameter_definitions()[0]
    with pytest.raises(ValueError, match="duplicate parameter key"):
        ParameterRegistry((definition, definition))


def test_missing_required_parameter_rejects_and_optional_parameter_degrades() -> None:
    registry = default_parameter_registry()

    required = registry.evaluate_value(
        "price.close",
        value=None,
        observed_at=NOW,
        checked_at=NOW,
    )
    optional = registry.evaluate_value(
        "news_sentiment.bitcoin_sentiment",
        value=None,
        observed_at=NOW,
        checked_at=NOW,
    )

    assert required.quality.is_rejected
    assert required.quality.flags == ("missing_parameter",)
    assert optional.quality.is_degraded
    assert optional.definition.failure_behavior is FailureBehavior.OPTIONAL
    assert optional.is_live_eligible is False


def test_stale_parameter_degrades_or_rejects_by_definition() -> None:
    registry = default_parameter_registry()

    trusted_stale = registry.evaluate_value(
        "price.close",
        value=decimal_value(Decimal("100")),
        observed_at=NOW,
        checked_at=NOW + timedelta(hours=1),
    )
    optional_stale = registry.evaluate_value(
        "on_chain.hash_rate",
        value="stub",
        observed_at=NOW,
        checked_at=NOW + timedelta(days=1),
    )

    assert trusted_stale.quality.is_rejected
    assert optional_stale.quality.is_degraded
    assert "stale_parameter" in trusted_stale.quality.flags


def test_live_parameter_eligibility_requires_trusted_quality() -> None:
    registry = default_parameter_registry()

    fresh = registry.evaluate_value(
        "price.close",
        value=decimal_value(Decimal("100")),
        observed_at=NOW,
        checked_at=NOW + timedelta(seconds=10),
    )
    optional = registry.evaluate_value(
        "derivatives.funding_rate",
        value="0.01",
        observed_at=NOW,
        checked_at=NOW + timedelta(seconds=10),
    )

    assert fresh.is_live_eligible is True
    assert optional.is_live_eligible is False
    assert optional.quality.trust_level is DataTrustLevel.DEGRADED


def test_source_metadata_blocks_untrusted_live_sources() -> None:
    sources = default_sources()
    source_by_key = {source.key: source for source in sources}

    assert source_by_key["market_data_repository"].live_allowed is True
    assert source_by_key["external_news_sentiment_stub"].live_allowed is False
    assert source_by_key["external_news_sentiment_stub"].trust_level is DataTrustLevel.DEGRADED
