from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.context import ContextFixture, OnChainContextProvider, SentimentContextProvider
from abtp.context.base import ContextProviderConfig, DeterministicContextProvider
from abtp.data import DataTrustLevel
from abtp.parameters import FailureBehavior, StaleBehavior

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_missing_provider_data_degrades_without_crashing() -> None:
    batch = OnChainContextProvider(observed_at=NOW, fixtures=()).fetch(received_at=NOW)

    assert batch.is_degraded
    assert batch.items == ()
    assert batch.flags == ("missing_context",)


def test_provider_failure_degrades_without_crashing() -> None:
    batch = SentimentContextProvider(
        observed_at=NOW,
        failure_message="fixture provider unavailable",
    ).fetch(received_at=NOW)

    assert batch.is_degraded
    assert batch.items == ()
    assert batch.flags == ("provider_failure",)


def test_stale_context_uses_configured_failure_policy() -> None:
    degraded = OnChainContextProvider(observed_at=NOW).fetch(received_at=NOW + timedelta(days=1))
    rejected = OnChainContextProvider(
        observed_at=NOW,
        config=ContextProviderConfig(
            stale_after=timedelta(minutes=1),
            stale_behavior=StaleBehavior.REJECT,
            failure_behavior=FailureBehavior.OPTIONAL,
        ),
    ).fetch(received_at=NOW + timedelta(minutes=2))

    assert degraded.is_degraded
    assert "stale_context" in degraded.flags
    assert rejected.is_rejected
    assert "stale_context" in rejected.flags


def test_invalid_confidence_and_malformed_payload_reject_items_not_batches() -> None:
    fixture = ContextFixture(
        key="bitcoin_sentiment",
        value=object(),
        observed_at=NOW,
        parameter_key="news_sentiment.bitcoin_sentiment",
        confidence=Decimal("1.5"),
    )
    provider = DeterministicContextProvider(
        source_name="external_news_sentiment_stub",
        category=SentimentContextProvider(observed_at=NOW).category,
        fixtures=(fixture,),
        config=ContextProviderConfig(stale_after=timedelta(hours=1)),
    )

    batch = provider.fetch(received_at=NOW)

    assert batch.is_rejected
    assert batch.items[0].quality.is_rejected
    assert batch.items[0].value is None
    assert batch.items[0].confidence is None
    assert batch.items[0].flags == ("malformed_context", "invalid_confidence")
    assert batch.quality.trust_level is DataTrustLevel.REJECTED
