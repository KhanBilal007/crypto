# Institutional Execution Optimizer

Stage 067 adds an advisory execution optimizer for large or illiquid positions.
It estimates execution cost and slippage from supplied order-book evidence and
produces smart slicing and timing recommendations.

The optimizer does not call exchanges, call routers, create order intents,
approve risk, submit orders, cancel orders, or execute trades.

## Inputs

`ExecutionOptimizationInput` contains:

- symbol and side
- total quantity
- reference price
- order-book metrics
- volatility score
- urgency score
- data-quality status
- observed timestamp and source references

All inputs are supplied by deterministic fixtures or upstream modules. The
optimizer never fetches market data.

## Outputs

`optimize_institutional_execution` emits an
`InstitutionalExecutionPlan` containing:

- advisory execution slices
- timing action
- expected cost in basis points
- slippage estimate in basis points
- spread and market-impact estimates
- reasons and rejection reasons
- quality flags
- audit payload

Timing actions are review labels only: execute review, split over time, wait
for spread, manual review, or blocked.

## Operating Limits

- No profit or fill quality is guaranteed.
- Plans are advisory and cannot bypass the Risk Management Engine.
- Smart slices are not order intents.
- Poor-quality, stale, no-depth, overly wide spread, or excessive expected-cost
  inputs fail closed.
- Future execution must still use the approved order-intent, risk, gateway,
  router, and exchange-adapter controls.
- Tests use deterministic fixtures and require no real exchange credentials,
  provider access, exchange access, or network calls.
