"""Deterministic sentiment and verified-news context provider stubs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from abtp.context.base import (
    ContextCategory,
    ContextFixture,
    ContextProviderConfig,
    DeterministicContextProvider,
    default_optional_context_config,
)

DEFAULT_CONTEXT_OBSERVED_AT = datetime(2026, 1, 1, tzinfo=UTC)


class SentimentContextProvider(DeterministicContextProvider):
    """Fixture-backed sentiment context with no news or social provider calls."""

    def __init__(
        self,
        *,
        observed_at: datetime = DEFAULT_CONTEXT_OBSERVED_AT,
        fixtures: tuple[ContextFixture, ...] | None = None,
        config: ContextProviderConfig | None = None,
        failure_message: str | None = None,
    ) -> None:
        super().__init__(
            source_name="external_news_sentiment_stub",
            category=ContextCategory.SENTIMENT,
            fixtures=fixtures if fixtures is not None else default_sentiment_fixtures(observed_at),
            config=config or default_optional_context_config(timedelta(hours=1)),
            failure_message=failure_message,
        )


def default_sentiment_fixtures(observed_at: datetime) -> tuple[ContextFixture, ...]:
    """Return deterministic verified-news and sentiment fixtures."""

    return (
        ContextFixture(
            key="bitcoin_sentiment",
            value=Decimal("0.20"),
            observed_at=observed_at,
            parameter_key="news_sentiment.bitcoin_sentiment",
            confidence=Decimal("0.65"),
        ),
        ContextFixture(
            key="verified_news_count_1h",
            value=3,
            observed_at=observed_at,
            confidence=Decimal("0.65"),
        ),
    )
