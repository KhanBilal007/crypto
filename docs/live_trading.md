# Supervised Live Trading Gateway

Stage 032 adds a tightly controlled live gateway contract. It is disabled by
default and exists to prove that no live order can be submitted unless all
minimum-risk gates pass.

## Required Gates

`SupervisedLiveTradingGateway.submit()` requires:

- a live-mode exchange adapter interface
- a persistent `LiveSubmissionLedger` shared by all gateway instances for the account
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

Approval is invalid if it is future-dated, expired (including the exact expiry
instant), mismatched, oversized, or uses a wrong confirmation phrase. Its
validity interval must satisfy `approved_at <= now < expires_at`, and its
lifetime cannot exceed the active policy's TTL, which defaults to five minutes.
The gateway uses its own UTC clock, not a client-provided submission timestamp,
to validate freshness and approval. Clock injection is for deterministic tests.

## Durable Submission Guard

`LiveSubmissionLedger(Path(...))` creates a dedicated SQLite safety ledger.
Supplying this ledger is now required before an enabled gateway will submit;
an in-memory ledger is not supported. Keep the same file across restarts and
share it across workers for the same account. Restrict access, preserve it in
backups, and do not delete/rotate it or switch paths to retry an order. It is
separate from the paper dashboard's saved state and does not migrate that state.

Intent and approval identifiers are consumed atomically in a committed
reservation before an exchange call. Duplicate requests, reissued approvals for
the same intent, and rebinding an already consumed approval ID are rejected.
The database transaction serializes concurrent reservations across instances.
Successful acknowledgements are saved without releasing either identifier.

A crash after reservation, adapter exception/timeout, response for a different
intent, or failure to persist the outcome leaves a pending reconciliation record.
That record blocks both retries and new intents, including after restart.
`accepted=false` with an unknown outcome does NOT prove that no exchange order
exists. No automatic retry or reconciliation release is implemented. A future
authenticated connector must query the exchange using a stable client-order
identity, reconcile the account, and support an audited recovery procedure.
Do not remove ledger rows to bypass this block.

An unavailable ledger prevents submission. Validation is repeated after the
reservation to catch expiry or stale data during a storage wait. A request
that becomes invalid at that point is recorded as `not_submitted`; its
identifiers remain consumed and it must be reviewed as a new proposal.

## Preflight

`run_live_preflight()` checks:

- risk approval is present and matches the order intent
- market and account snapshots are each at most 30 seconds old by default
- order intent and risk decision are each at most five minutes old by default
- future-dated input timestamps beyond two seconds of clock skew are rejected
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

`LiveMarketPreflight` now requires an independent `account_checked_at` alongside
the market's `checked_at`. Account time must represent the actual balance and
exposure observation, not the time cached values were repackaged. Standalone
preflight uses the current UTC time by default; tests can supply `now` explicitly.
These timestamp checks do not authenticate the supplied account or permission
data. Obtaining and verifying that evidence remains the connector's responsibility.

## Adapter Boundary

The gateway calls only the exchange adapter interface. Its unit tests use a
fake live adapter with no network behavior. The production Binance adapter
remains read-only, and runtime live execution remains disabled.

A separate `BinanceSpotTestnetClient` now implements signed testnet account,
order-validation, lookup/cancel, bounded LIMIT FOK, and protective OCO request
methods. It is not wired into the production gateway or dashboard. Its host is
fixed to `https://testnet.binance.vision`; matched virtual orders are disabled
unless explicitly enabled in the client constructor. The qualification command
never enables them. Testnet credentials must use separate environment variables:
`ABTP_BINANCE_TESTNET_API_KEY` and `ABTP_BINANCE_TESTNET_API_SECRET`.

Run `python -m abtp.live.testnet_qualification --authenticated` in an environment
where those credentials have been securely configured. This checks account access
and `order/test`, which does not send an order to the matching engine. It does not
automatically load any credential file. Do not put keys in command arguments,
reports, logs, or Git. The optional local credential file is plaintext even when
Git-ignored, so restrict access and remove it when no longer required.

Authenticated checks passed on October 5; see the
[qualification report](testnet_qualification_2026_10_05.md). Matched virtual-fund
entry/exit/protection and recovery qualification remain pending. Read-only
reconciliation reconstructs commissions by asset and checks actual OCO legs,
but never clears ledger halts or retries orders automatically. This is not a
complete supervised execution lifecycle and is not production certification.

## Operating Limits

The gateway is a supervised minimum-risk contract, not automation. It does not
claim profitability and does not bypass the Risk Management Engine. Margin,
leverage, futures, options, transfers, and withdrawals remain unsupported.
