# Supervised Live Trading Gateway

Stage 032 adds a tightly controlled live gateway contract. It is disabled by
default and exists to prove that no live order can be submitted unless all
minimum-risk gates pass.

## Required Gates

`SupervisedLiveTradingGateway.submit()` requires:

- a live-mode exchange adapter interface
- `enable_supervised_live=true` in gateway config
- `runtime_live_execution_supported=true` in gateway config
- a risk-approved `OrderIntent`
- a passing live preflight check
- a manual approval token bound to the same order intent
- an unexpired approval confirmation phrase

The repository runtime settings still do not implicitly enable live execution.
Environment variables alone are not enough to route a live order.

## Manual Approval

`LiveApprovalToken` binds an operator approval to one order intent, maximum
quantity, maximum notional, approval timestamp, expiration timestamp, and the
confirmation phrase:

```text
APPROVE_ABTP_TINY_LIVE_ORDER
```

Approval is invalid if it is expired, mismatched, oversized, or uses a wrong
confirmation phrase.

## Preflight

`run_live_preflight()` checks:

- risk approval is present and matches the order intent
- spot buy only
- order quantity does not exceed risk-approved max size
- estimated notional is within the tiny live risk limit
- quote balance is sufficient
- max one open live position by default
- spread and slippage are within limits
- exchange key permissions are read/trade only
- IP allowlist is present
- withdrawal, transfer, margin, futures, options, and admin scopes are rejected

The default max risk per trade is `0.25%`, and the default max order notional is
`25` quote currency units.

## Adapter Boundary

The gateway calls only the exchange adapter interface. Stage 032 tests use a
fake live adapter with no network behavior. No real exchange connector, real
credentials, HTTP call, websocket call, or live account integration is added.

## Operating Limits

The gateway is a supervised minimum-risk contract, not automation. It does not
claim profitability and does not bypass the Risk Management Engine. Margin,
leverage, futures, options, transfers, and withdrawals remain unsupported.
