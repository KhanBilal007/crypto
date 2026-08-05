# Order Execution Engine in Paper-Safe Mode

Stage 024 adds paper-safe order execution. The engine accepts only
risk-approved `OrderIntent` objects and routes them to deterministic paper fills
or sandbox adapters.

## Inputs

`PaperSafeExecutionEngine.submit()` requires:

- an `OrderIntent`
- a matching approved `RiskDecision`
- idempotency key
- submission timestamp
- execution price for paper market orders

If the order intent lacks a matching approved risk decision, it is rejected
before routing.

## Router

`PaperOrderRouter` supports:

- `paper` route: deterministic simulated fills
- `sandbox` route: adapter-routed sandbox submission

`live` route is rejected during configuration. Live adapters are also rejected.
Stage 024 does not implement real exchange HTTP/websocket calls or live
execution.

## Lifecycle and Audit

Accepted submissions append:

- order intent row
- submitted lifecycle event
- final lifecycle event (`filled`, `submitted` for partial paper fills, or
  `failed`)
- optional audit event

Repeated submissions with the same idempotency key return the original result
without adding duplicate lifecycle events.

## Safety Controls

Only risk-approved order intents are accepted. Paper is the default route.
Partial fills, adapter failures, fees, route mode, exchange order id, and
idempotency key are recorded for auditability.

Stage 024 does not generate signals, approve risk, create live routes, manage
real balances, or claim profitability.
