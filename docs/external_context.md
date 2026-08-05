# External Context

Stage 016 adds optional ingestion interfaces for external Bitcoin and crypto
context. The implementation is provider-neutral and deterministic; it does not
call real on-chain, macro, derivatives, sentiment, news, exchange, or vendor
APIs.

## Provider Families

The context package defines contracts and stubs for:

- derivatives: funding rate, open interest, liquidation context
- on-chain: active addresses, hash rate, exchange flows
- macro/calendar: liquidity/rates proxies and major calendar events
- sentiment/news: verified news counts and sentiment scores

Each provider emits a `ContextBatch` containing zero or more `ContextItem`
objects.

## Context Items

Every `ContextItem` includes:

- category and key
- source name
- observed timestamp
- received timestamp
- trust level
- stale behavior
- failure behavior
- quality status
- live-eligibility flag
- optional confidence
- optional mapping to a Stage 013 parameter key

External context is optional and lower-trust by default. The deterministic
stubs set `live_allowed=false`, so context items are not live-eligible in this
stage.

## Failure Behavior

Provider failures, empty fixture sets, stale observations, malformed payloads,
and invalid confidence values produce degraded or rejected quality statuses.
They do not crash the platform. This lets future strategies remain functional
without external context while preserving quality flags for explainability.

## Parameter Mapping

Context items can map to existing Stage 013 parameter definitions:

- `derivatives.funding_rate`
- `derivatives.open_interest`
- `on_chain.hash_rate`
- `on_chain.exchange_netflow`
- `macro.usd_liquidity_proxy`
- `macro.rates_proxy`
- `news_sentiment.bitcoin_sentiment`

Items without a parameter key remain context-only until a future stage defines
additional schema mappings.

## Operating Limits

Stage 016 does not implement AI training, predictions, strategy signals, risk
decisions, order intents, order execution, real provider calls, real exchange
connectors, or live trading. External context may inform future features or
strategies, but it cannot authorize trading and remains non-actionable when
stale, missing, malformed, rejected, or lower-trust.
