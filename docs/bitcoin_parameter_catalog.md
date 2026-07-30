# Bitcoin Parameter Catalog

Stage 013 adds a deterministic registry of Bitcoin and crypto dependency
parameters for future indicators, AI models, strategies, and risk checks. It
does not fetch real external data or implement indicators, models, strategies,
risk decisions, order execution, or live trading.

## Registry

`ParameterRegistry` supports lookup by:

- key
- group
- source
- live-decision eligibility
- trust level

New parameters can be added as `ParameterDefinition` records without changing
strategy or risk internals.

## Required Groups

The default catalog includes:

- price action
- liquidity
- volatility
- trend
- volume
- derivatives
- on-chain
- cross-asset
- macro
- news/sentiment
- exchange health
- portfolio
- data quality

## Minimum Metadata

Every parameter defines:

- trust level
- source key
- refresh interval
- stale behavior
- failure behavior
- whether it is allowed in live decisions
- whether it is optional

Missing or stale required parameters reject future decisions. Missing optional
parameters degrade future decisions. Nothing silently produces trusted values.

## Source Policy

Internal market data, portfolio, and data-quality sources may be trusted when
their source data is trusted. External derivatives, on-chain, macro, and
news/sentiment sources are deterministic stubs in Stage 013 and mapped by the
Stage 016 external context interfaces where appropriate. They are optional,
lower-trust, and blocked from live-decision eligibility until later stages add
deterministic source-quality validation.

## Live Eligibility

Live-allowed parameters must be trusted. A `ParameterValue` is live-eligible
only when:

- its definition allows live decisions
- its current quality status is trusted

This keeps future strategy and risk modules from consuming missing, stale, or
lower-trust external parameters as if they were safe.
