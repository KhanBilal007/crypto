"""Deterministic on-chain context provider stubs."""

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


class OnChainContextProvider(DeterministicContextProvider):
    """Fixture-backed on-chain context with no blockchain or API calls."""

    def __init__(
        self,
        *,
        observed_at: datetime = DEFAULT_CONTEXT_OBSERVED_AT,
        fixtures: tuple[ContextFixture, ...] | None = None,
        config: ContextProviderConfig | None = None,
        failure_message: str | None = None,
    ) -> None:
        super().__init__(
            source_name="external_on_chain_stub",
            category=ContextCategory.ON_CHAIN,
            fixtures=fixtures if fixtures is not None else default_onchain_fixtures(observed_at),
            config=config or default_optional_context_config(timedelta(hours=6)),
            failure_message=failure_message,
        )


def default_onchain_fixtures(observed_at: datetime) -> tuple[ContextFixture, ...]:
    """Return deterministic active-address, hash-rate, and flow fixtures."""

    return (
        ContextFixture(
            key="active_addresses",
            value=Decimal("925000"),
            observed_at=observed_at,
            confidence=Decimal("0.55"),
        ),
        ContextFixture(
            key="hash_rate",
            value=Decimal("650000000"),
            observed_at=observed_at,
            parameter_key="on_chain.hash_rate",
            confidence=Decimal("0.55"),
        ),
        ContextFixture(
            key="exchange_netflow",
            value=Decimal("-1200"),
            observed_at=observed_at,
            parameter_key="on_chain.exchange_netflow",
            confidence=Decimal("0.55"),
        ),
    )
