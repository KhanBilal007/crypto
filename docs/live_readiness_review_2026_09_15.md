# Live Trading Readiness Review

Date: 2026-09-15, Asia/Calcutta. Verdict: **NO-GO for real-money trading**.

Rechecked 2026-09-30: **NO-GO unchanged**. See the dated follow-up below.

Updated 2026-10-05: reproduced local gateway/accounting defects corrected with
regression tests. **NO-GO remains** for real-money trading; see the October 5
implementation update. Findings and line references below describe the original
review snapshot, not the corrected source.

## Scope And Safety

Reviewed the current local worktree in `E:\krypto`, its live gateway, paper
promotion gate, Binance adapter, runtime configuration, HTTP routes, security
contracts, automation/reconciliation modules, tests, and deployment guidance.
Local HEAD is `60db1c1`; the September audit changes remain uncommitted.
Read the deployed public status at `https://3.233.15.209/api/status`.

No live mode was enabled. No real exchange order, cancellation, transfer, or
withdrawal was attempted. No credentials were requested, read, or transmitted.
The additional failure probes used the repository's fake adapter and local
unit-test inputs, not real accounts. The initial September 15 review changed
documentation only; the October 5 implementation update records subsequent fixes.

This is a readiness review, not a guarantee that every defect has been found.
No server shell access or authenticated Binance account access was available.

## Deployed Observations

Public status checked at approximately **01:54 IST on September 15**:

| Field | Observed value |
| --- | --- |
| Mode | PAPER MODE |
| SAFE_MODE | true |
| Live trading enabled | false |
| Source | binance spot |
| BTC/USDT price | 79,448.00 USDT |
| Market observation time | 2026-09-15 01:54:27.886 IST |
| Reported connection/freshness | connected / healthy |
| Main account equity / BTC | 1,000 USDT / 0 BTC |
| Main account transactions | 0 |
| Trader verdict: live_capital_ready | false |
| Trader verdict: readiness_level | blocked |
| Trader verdict: blocker | missing risk_decision evidence |
| General dashboard readiness | ready=true; this is NOT live approval |

The service still exposes the older response shape: latency is 10 ms, no new
strategy-data cursor/error fields, and no strategy versions in Compare Runs.
This is consistent with the local fixes not being deployed. The running server
commit and configuration cannot be verified without deployment access.

The shadow accounts reported Breakout +459.04, Support/Rebound +22.52,
Trend Pullback -48.12, and MinRisk 0.00 USDT. These are cumulative simulated
values from the existing deployment, not validated live profits or a clean
trial of the revised code. Each sample counter was 76, including startup
observations; it cannot demonstrate uninterrupted trading coverage.

Normal HTTPS validation failed with `SEC_E_UNTRUSTED_ROOT`. Only the public
GET diagnostic was repeated with certificate validation bypassed. This must
not become a production setting for authenticated requests.

## Blocking Findings

### 1. Real Binance Execution Does Not Exist In This Runtime

Severity: P1 / release blocker.

- `src/abtp/exchanges/binance.py:164`: order submission raises
  `UnsupportedOperationError`; lookup and cancellation are also disabled.
- `src/abtp/config/settings.py:74`: `live_execution_supported` returns false.
- `src/abtp/dashboard/paper_app.py:1406`: the dashboard rejects live enablement.
- `docs/live_trading.md` explicitly describes a fake-adapter contract, not an
  authenticated exchange integration.

Required: a separately reviewed connector with signed account/order access,
exchange filters, real balances, fees, order updates, and recovery. Simply
changing a flag or selecting Live Trading in the UI is not an implementation.

### 2. No Complete Live Exit And Protection Lifecycle

Severity: P1 / release blocker.

`src/abtp/live/preflight.py:131` rejects every side except BUY. There is no
integrated live SELL/close/reduce route or exchange-hosted protective-order
workflow. `src/abtp/paper/engine.py:466` provides candle-based simulated exits,
not protection for funds held on Binance if the process or network fails.

Required: tested exit authority, reduce-only spot quantity validation,
protective-order placement and confirmation, partial-fill handling, failure
recovery, and an explicit policy for what emergency stop does to open orders
and existing exposure.

### 3. Repeated Approval Can Reach The Adapter Twice

Severity: P1 / release blocker for a future connected gateway.

`src/abtp/live/gateway.py:59` validates a token on every submit but does not
consume it or persist an order-intent deduplication record. Two calls with the
same intent and approval were both accepted by `FakeLiveAdapter`, which
recorded two submissions. This is a local test result, not two Binance trades.

Required: durable idempotency, single-use approval, concurrency protection,
stable exchange client-order identity, and query/reconciliation after an
ambiguous timeout instead of blindly retrying an order.

### 4. Freshness And Approval Validity Are Incomplete

Severity: P1 / release blocker.

- `src/abtp/live/preflight.py:99`: `checked_at` is copied into the preview but
  no age bound is enforced. A market snapshot one day old was accepted.
- `src/abtp/live/approval.py:110`: expiry is checked, but the approval's start
  time is not. An approval starting one hour in the future was accepted now.
- Permission, balance, spread, and exposure inputs are supplied values, not
  authenticated fresh exchange observations in the existing runtime.

Required: bounded market/account/risk-decision ages, clock-skew checks,
`approved_at <= now < expires_at`, bounded token lifetime, and fresh validation
immediately before submission. These checks must be enforced by the actual
connected order path, not only available as standalone helper functions.

### 5. The Promotion Gate Still Misstates Trade Profit

Severity: P1 / release blocker for promotion evidence.

`src/abtp/paper/evaluation.py:309` stores entry quantity/price without entry
fees, subtracts only the exit fee, and appends a result for each matched SELL.
This differs from the corrected completed-position statistics used by the
dashboard and new validation command.

Offline example: buy 1 at 100 with a 0.20 fee; sell 1 at 100.30 with a 0.20
fee. The promotion helper reports **+0.10**, while actual cash-flow P/L is
**-0.10**. Partial exits can also inflate its completed-trade count.

Required: one consistent fee-inclusive completed-position metric calculation
across promotion, reports, and dashboard; regression tests for entry fees,
partial exits, unmatched fills, and insufficient evidence. Default promotion
thresholds of 14 days and 3 completed trades are not proof of a durable edge.
The gate's eligibility result is only permission to prepare a future proposal,
not permission to trade.

### 6. Production Authentication And TLS Are Not Verified

Severity: P1 / release blocker before attaching real funds.

`src/abtp/dashboard/paper_server.py:58` passes POST requests to control routes
without authenticating the caller. Security role types exist elsewhere, but
this HTTP boundary does not authenticate a session or principal.

Public status was readable without credentials and TLS verification failed.
No remote control POST was attempted. A reverse proxy might separately protect
POST routes; its rules are unknown and must be inspected, not assumed absent
or assumed sufficient.

Required: trusted HTTPS, authenticated and authorized controls, request-origin
protection appropriate to the authentication design, restricted network access,
least-privilege keys, disabled withdrawal/transfer permissions, IP restrictions,
secret storage/rotation, and incident response tests.

### 7. Reconciliation And Emergency Controls Are Not End-To-End

Severity: P1 / release blocker.

`src/abtp/reconciliation/engine.py:126` compares supplied snapshots and produces
a recovery plan. It is not wired to a real Binance account/order feed.
`src/abtp/automation/controller.py:239` exposes a separate authorization guard;
the gateway does not itself consult that controller's pause/kill state.

Required: a single connected execution boundary that enforces halts and loss
limits, persists state, reconciles fills/balances/open orders on startup and
reconnect, and remains blocked when exchange order status is uncertain.
Standalone module tests do not establish this operational integration.

### 8. Deployment And Forward Performance Evidence Are Incomplete

Severity: P1 / release blocker for this proposed launch.

The corrected local paper implementation has not been rolled out to the
server. The September 10 historical comparison showed mixed performance and
small trade counts. It did not establish reliable profitability. No completed
forward trial of the corrected system or authenticated exchange lifecycle test
was available for this review.

Required: preserve old evidence, deploy a reviewed release in paper mode,
identify the exact strategy/version for each run, and collect dated, complete
forward evidence with realistic costs and explicit drawdown/coverage limits.
Keep exchange integration qualification separate from profitability evaluation.

## Verification Executed

- Full existing suite: **631 passed in 14.36 seconds**.
- Ruff lint: passed.
- Ruff formatting: 424 files already formatted.
- mypy: no issues in 217 source files.
- Additional offline probes: repeated intent/approval reached the fake adapter
  twice; day-old market data was accepted; a future-dated approval was accepted;
  the promotion helper reported +0.10 instead of -0.10 after all fees.

The new probes reveal missing coverage; passing the existing test suite is
not evidence that these defects are fixed. No production order was sent.

## Not Verified

- Server OS, firewall, reverse proxy rules, process supervisor, deployed commit,
  environment, time synchronization, service logs, or actual backup restore.
- Binance account eligibility, API-key restrictions, authenticated balances,
  private account stream, fee tier, or current symbol filters for real orders.
- End-to-end exchange rejection, partial fill, disconnect, timeout, restart,
  duplicate message, protective-order failure, and emergency-stop scenarios.
- External notification delivery, dependency vulnerability scanning, and a
  comprehensive penetration test or mobile/UI certification.

No conclusion of safety should be inferred for these unverified areas.

## Required Sequence Before Reconsideration

1. Keep live execution locked and fix the gateway/promotion defects above.
2. Secure the deployment and publish a traceable paper-only release after
   backing up existing state and preserving prior run history.
3. Build the authenticated exchange connector and full order/exit lifecycle
   behind disabled-by-default controls; validate with virtual exchange funds.
4. Test duplicate submissions, ambiguous timeouts, partial fills, stale input,
   restart reconciliation, limits, and protective-order failures end to end.
5. Continue real Binance market-data forward paper tests, with accounts and
   versions separated. Evaluate net results and risk, not raw profit alone.
6. Reassess readiness with the operator. Only after the blockers are resolved
   can a separately specified, tightly capped supervised live proposal be
   considered. This document authorizes no real-money order.

Binance Spot Testnet uses virtual funds. It is useful for connector tests, not
proof of main-market fills or profits; keep the real-data forward paper trial
separate. Binance also documents that a timed-out request can have an unknown
execution status and requires checking the account stream/order status.

## References

- [Binance Spot Testnet](https://github.com/binance/binance-spot-api-docs/blob/master/testnet/general-info.md)
- [Binance Spot REST API and timeout handling](https://developers.binance.com/en/docs/products/spot/rest-api)
- [Previous profitability/runtime audit](profitability_audit_2026_09_10.md)
- [Supervised live gateway contract](live_trading.md)
- [Paper evaluation contract](paper_evaluation_gate.md)

## September 30 Follow-Up

Resumed the readiness review without enabling live trading or modifying
execution code. Local HEAD remains `60db1c1`; the prior runtime/strategy fixes
and audit reports remain uncommitted. The newly identified live gateway and
promotion defects have not been fixed by this review.

### Current Server Observation

Public status checked at **18:15:41 IST on September 30, 2026**:

- PAPER MODE, SAFE_MODE true, live trading false.
- Binance spot reported connected/healthy, BTC/USDT 84,934.90 USDT, market
  observation timestamp 18:15:35.786 IST.
- Main account equity remained 1,000 USDT with zero transactions.
- `live_capital_ready=false`, `readiness_level=blocked`, missing risk-decision
  evidence. A general dashboard readiness pass is not a live-capital pass.
- All four shadow accounts retained the same reported P/L and fill counts as
  September 15. The sample counter was 73 rather than 76. This is not a
  cumulative coverage measure and cannot prove a continuous trial; server
  logs and persisted history are required to establish what ran between checks.
- The response still lacks revised strategy-version/cursor fields and reports
  10 ms latency. It remains consistent with the old deployment, but an exact
  server commit was not available for verification.
- HTTPS certificate verification still failed with `SEC_E_UNTRUSTED_ROOT`.
  Only a public GET was repeated with the certificate check bypassed; no
  credentials or control commands were sent.

### Current Verification Results

- Full existing suite: **631 passed in 15.19 seconds**.
- Ruff lint and format checks passed; mypy passed for 217 source files.
- Fresh offline probes reproduced all four gaps: same intent/token submitted
  twice to a fake adapter; one-day-old market data accepted; future-dated
  approval accepted; promotion helper returned +0.10 for a trade with -0.10
  fee-inclusive cash-flow P/L. These probes made zero network calls.
- The live Binance execution connector, complete live exit/protection path,
  authenticated operational integration, and forward evidence remain blockers.
- Server administration and authenticated account checks remain outside the
  verified scope. No deployment, commit, push, or real exchange action occurred.

Next implementation work should address the reproduced safety and promotion
defects with regression tests while preserving the live-execution lock. This
review is not authorization to skip connector qualification or deploy live.

## October 5 Implementation Update

Implemented and verified locally in `E:\krypto`. The live execution lock remains
unchanged, and the remote deployment was not changed or rechecked in this pass.

### Corrected Locally

1. **Single-use submissions and approvals:** a dedicated persistent SQLite
   ledger atomically reserves intent/approval IDs before the adapter call.
   Concurrency, repeat requests, new approvals for an old intent, and restarts
   cannot reuse them. Missing storage prevents submission. Ambiguous adapter
   failures, mismatched responses, or lost outcome writes leave a durable block
   on further submissions pending reconciliation. This corrects the reproduced
   duplicate-call bug; a stable Binance client-order ID and authenticated
   reconciliation/recovery still require a real connector.
2. **Freshness:** the gateway uses an internal clock, rejects stale/future
   submission times, checks independent market/account timestamps (30 seconds
   by default), and checks intent/risk age (five minutes). Input clock skew is
   capped at two seconds. All checks run again after durable reservation and
   before calling the adapter. The actual authenticated collection of balances,
   exposure, permissions, and order updates remains unimplemented.
3. **Approval validity:** future approvals, exact-expiry approvals, and tokens
   whose lifetime exceeds the active policy are rejected. Validation enforces
   `approved_at <= now < expires_at`, with a default five-minute TTL.
4. **Promotion accounting:** the gate now shares the completed-position P/L
   calculation with the dashboard/validator. Both entry and exit fees count;
   partial exits do not inflate completed-trade samples. Unmatched/invalid fills
   raise an evidence error rather than returning promotion eligibility. The
   reproduced +0.10 error is now correctly reported as **-0.10** after fees.

### Verification

- Full suite: **689 passed in 13.81 seconds**, up from 631 tests.
- Focused gateway/accounting/end-to-end safety selection: **84 passed**.
- Ruff lint: passed; format check: 426 files already formatted.
- mypy: no issues in 218 source files.
- New regression coverage includes concurrent submissions, durable restart
  deduplication, approval-ID rebinding, crash/timeout uncertainty, storage
  failure, exchange-response mismatch, timestamp boundaries, post-reservation
  expiry, entry/exit fees, partial exits, unsorted and invalid evidence.

Tests use isolated temporary databases and fake exchange responses. No credentials
were read or transmitted, and no authenticated testnet or real-money order was
attempted. The existing paper portfolio/history file was left untouched. Normal
market-data operation remains Binance-only; deterministic test fixtures do not
change the operational data source.

### Remaining Launch Blockers

- Authenticated Binance connector, exchange filters, stable client-order IDs,
  verified account permissions, and virtual-fund lifecycle qualification.
- Live sell/close, partial-fill accounting, exchange-hosted protection, and
  reconciled emergency/loss controls enforced on every connected order path.
- Trusted TLS, authenticated dashboard controls, server configuration, key
  restrictions, restore/recovery, supervision, and notification evidence.
- Reviewed paper deployment and dated forward evidence for the corrected
  strategies. These safety fixes neither change the strategy thresholds nor
  demonstrate profitability.

Local HEAD remains `60db1c1`; these changes and earlier September work remain
uncommitted and undeployed. Passing offline checks is not exchange certification
or authorization to enable real-money trading.

