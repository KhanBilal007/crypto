# Live Data

Stage 011 adds read-only live market data ingestion abstractions for ticker,
candle, trade-adjacent, and order-book updates through exchange adapters. It
uses the deterministic sandbox connector for tests and does not implement real
exchange websocket/API calls.

## Scope

The live data layer includes:

- `LiveMarketDataStream` for polling normalized snapshots through an
  `ExchangeAdapter`
- `HeartbeatMonitor` for latency, stale data, disconnect counts, and last
  message time
- order-book metrics for bid/ask, spread, depth, and imbalance
- order-book delta utilities for snapshot consistency checks

Accepted live candles and order-book snapshots are stored through Stage 008
repositories where appropriate.

## Health State

Live stream health exposes:

- `is_connected`
- `is_stale`
- `is_degraded`
- `disconnect_count`
- `last_message_at`
- `latency_ms`
- `status`

Data is marked stale after a configurable threshold. Degraded or stale updates
are emitted with health status, but they are not accepted for repository storage
by the live stream. Future strategy modules must reject stale or degraded data.

## Order Book Metrics

Order-book utilities calculate:

- best bid
- best ask
- spread
- bid depth
- ask depth
- imbalance

Snapshot deltas identify changed levels and removed prices. These utilities are
pure functions over Stage 007 domain models and do not depend on exchange APIs
or database state.

## Read-Only Controls

Live data ingestion cannot submit or modify orders. Any attempt to submit an
order through the stream raises `UnsupportedOperationError`. Trading behavior
must remain behind the Risk Management Engine and exchange adapter execution
controls from earlier stages.

## Not Implemented

Stage 011 does not add:

- real websocket connections
- real exchange HTTP calls
- live trading
- indicators
- AI features
- strategy logic
- risk decision-making
- order execution

