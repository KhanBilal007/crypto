from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.context import (
    ContextCategory,
    DerivativesContextProvider,
    MacroContextProvider,
    OnChainContextProvider,
    SentimentContextProvider,
    context_items_to_parameter_values,
)
from abtp.data import DataTrustLevel
from abtp.parameters import default_parameter_registry

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_default_providers_emit_low_trust_optional_context() -> None:
    providers = (
        DerivativesContextProvider(observed_at=NOW),
        OnChainContextProvider(observed_at=NOW),
        MacroContextProvider(observed_at=NOW),
        SentimentContextProvider(observed_at=NOW),
    )

    batches = tuple(
        provider.fetch(received_at=NOW + timedelta(minutes=1)) for provider in providers
    )

    assert tuple(batch.category for batch in batches) == (
        ContextCategory.DERIVATIVES,
        ContextCategory.ON_CHAIN,
        ContextCategory.MACRO,
        ContextCategory.SENTIMENT,
    )
    assert all(batch.is_degraded for batch in batches)
    assert all(
        item.trust_level is DataTrustLevel.DEGRADED for batch in batches for item in batch.items
    )
    assert all(not item.live_allowed for batch in batches for item in batch.items)
    assert all(not item.is_live_eligible for batch in batches for item in batch.items)


def test_context_items_map_to_known_parameter_keys() -> None:
    batch = DerivativesContextProvider(observed_at=NOW).fetch(received_at=NOW)
    registry = default_parameter_registry()

    values = context_items_to_parameter_values(batch.items, registry)

    assert tuple(value.definition.key for value in values) == (
        "derivatives.funding_rate",
        "derivatives.open_interest",
    )
    assert values[0].value == "0.0001"
    assert values[0].quality.is_degraded
    assert not values[0].is_live_eligible


def test_macro_and_sentiment_include_required_fixture_concepts() -> None:
    macro = MacroContextProvider(observed_at=NOW).fetch(received_at=NOW)
    sentiment = SentimentContextProvider(observed_at=NOW).fetch(received_at=NOW)

    assert {item.key for item in macro.items} >= {"major_calendar_event", "rates_proxy"}
    assert {item.key for item in sentiment.items} >= {
        "bitcoin_sentiment",
        "verified_news_count_1h",
    }
    assert sentiment.items[0].confidence == Decimal("0.65")
