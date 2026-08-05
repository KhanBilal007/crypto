"""Deterministic macro and calendar context provider stubs."""

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


class MacroContextProvider(DeterministicContextProvider):
    """Fixture-backed macro context with no calendar or data-provider calls."""

    def __init__(
        self,
        *,
        observed_at: datetime = DEFAULT_CONTEXT_OBSERVED_AT,
        fixtures: tuple[ContextFixture, ...] | None = None,
        config: ContextProviderConfig | None = None,
        failure_message: str | None = None,
    ) -> None:
        super().__init__(
            source_name="external_macro_stub",
            category=ContextCategory.MACRO,
            fixtures=fixtures if fixtures is not None else default_macro_fixtures(observed_at),
            config=config or default_optional_context_config(timedelta(days=1)),
            failure_message=failure_message,
        )


def default_macro_fixtures(observed_at: datetime) -> tuple[ContextFixture, ...]:
    """Return deterministic macro proxy and calendar fixtures."""

    return (
        ContextFixture(
            key="usd_liquidity_proxy",
            value=Decimal("0.15"),
            observed_at=observed_at,
            parameter_key="macro.usd_liquidity_proxy",
            confidence=Decimal("0.50"),
        ),
        ContextFixture(
            key="rates_proxy",
            value=Decimal("0.0425"),
            observed_at=observed_at,
            parameter_key="macro.rates_proxy",
            confidence=Decimal("0.50"),
        ),
        ContextFixture(
            key="major_calendar_event",
            value={"event": "fixture_cpi_release", "impact": "medium"},
            observed_at=observed_at,
            confidence=Decimal("0.50"),
        ),
    )
