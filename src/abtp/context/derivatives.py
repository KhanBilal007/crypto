"""Deterministic derivatives context provider stubs."""

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


class DerivativesContextProvider(DeterministicContextProvider):
    """Fixture-backed derivatives context with no real provider calls."""

    def __init__(
        self,
        *,
        observed_at: datetime = DEFAULT_CONTEXT_OBSERVED_AT,
        fixtures: tuple[ContextFixture, ...] | None = None,
        config: ContextProviderConfig | None = None,
        failure_message: str | None = None,
    ) -> None:
        super().__init__(
            source_name="external_derivatives_stub",
            category=ContextCategory.DERIVATIVES,
            fixtures=fixtures
            if fixtures is not None
            else default_derivatives_fixtures(observed_at),
            config=config or default_optional_context_config(timedelta(hours=1)),
            failure_message=failure_message,
        )


def default_derivatives_fixtures(observed_at: datetime) -> tuple[ContextFixture, ...]:
    """Return deterministic funding, open-interest, and liquidation fixtures."""

    return (
        ContextFixture(
            key="funding_rate",
            value=Decimal("0.0001"),
            observed_at=observed_at,
            parameter_key="derivatives.funding_rate",
            confidence=Decimal("0.60"),
        ),
        ContextFixture(
            key="open_interest",
            value=Decimal("1250000000"),
            observed_at=observed_at,
            parameter_key="derivatives.open_interest",
            confidence=Decimal("0.60"),
        ),
        ContextFixture(
            key="liquidations_1h",
            value=Decimal("2500000"),
            observed_at=observed_at,
            confidence=Decimal("0.55"),
        ),
    )
