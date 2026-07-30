# Exchange Adapter

Stage 009 defines a unified exchange adapter contract and a deterministic
sandbox connector. It does not implement real exchange HTTP calls, websocket
streams, live trading, withdrawals, margin, leverage, futures, options, AI
training, strategy logic, or risk decision-making.

## Adapter Contract

The base contract lives in `src/abtp/exchanges/base.py` and covers:

- market metadata and supported symbols
- tick sizes and lot sizes
- fee assumptions
- balances
- ticker snapshots
- candle access
- order-book snapshots
- order submission, lookup, and cancellation lifecycle methods
- rate-limit state
- latency and websocket state in sandbox fixtures

Only exchange adapter modules may contain exchange-specific API behavior. Other
data or execution modules should depend on `ExchangeAdapter` rather than a
venue-specific client.

## Sandbox Connector

`SandboxExchangeAdapter` is fixture-driven and deterministic. Defaults include:

- symbol: `BTC/USDT`
- price: `100000`
- tick size: `0.01`
- lot size: `0.0001`
- maker fee: `10` bps
- taker fee: `20` bps
- balances: `1 BTC` and `1000000 USDT`

The sandbox tracks submitted orders in memory and fills valid market/limit
orders immediately at the fixture price or supplied limit price.

## Minimum-Risk Controls

Sandbox order submission requires a Stage 007 `OrderIntent` with a matching,
approved `RiskDecision`. Missing, rejected, mismatched, stale, kill-switch, or
invalid-size orders are rejected before any lifecycle result is created.

The sandbox cannot be constructed with `mode=live`, and it rejects any signal
that live credentials are present. This stage does not enable live execution,
even for validated Stage 006 live configuration.

## Disabled Operations

The following remain blocked:

- real credentials
- real exchange API calls
- withdrawals
- margin
- leverage
- futures
- options

Later real adapters must keep live API calls inside exchange adapter modules and
must preserve the risk-approved order requirement.

