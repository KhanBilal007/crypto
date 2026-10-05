# Paper Trading Evaluation Gate

Stage 073 reviews completed paper-trading evidence and produces one
conservative recommendation:

- `remain_paper`
- `make_more_conservative`
- `pause_for_review`
- `eligible_for_future_tiny_live_proposal`

The last recommendation is not live trading approval. It only means the
supplied paper evidence passed this deterministic gate strongly enough that a
future, separate, supervised tiny-live proposal could be prepared in a later
explicit stage.

## Evidence Reviewed

The gate consumes `PaperTradingSessionSummary` records, completed `PaperTrade`
fills, evaluation window dates, daily and weekly loss events, stop-loss
violations, confidence calibration error, capital-preservation events,
governance violations, audit references, source references, and optional data
quality status.

Metrics include evaluation days, completed trade count, net return, win rate,
average win, average loss, expectancy, profit factor, maximum drawdown, blocked
cycle rate, risk rejection count, fee impact, stop-loss compliance, confidence
calibration, governance status, and audit completeness.

## Completed-Position Accounting

As of October 5, 2026, the gate uses `closed_trade_pnls`, the same fee-inclusive
completed-position calculation used by the dashboard and strategy validation.
Supply the complete entry/exit ledger for one account and pair, including the
entries backing any exit; do not combine separate strategy wallets. Fills are
ordered by their observation times, preserving input order when times match.

Each flat-to-flat position is one completed trade. All entry and exit fees are
included. Partial entries/exits do not inflate the sample count, and an open or
partly closed position is not yet counted as a completed win. For example, buy
one unit at 100 with a 0.20 fee and sell at 100.30 with a 0.20 fee produces
**-0.10**, not +0.10.

A sell without sufficient matching entry quantity, non-finite or nonpositive
quantity/price, or negative/non-finite fee raises `ValueError`. No promotion
result is produced for invalid evidence. Callers must keep live trading locked
and repair the evidence, not discard unmatched fills to obtain eligibility.
Session-based equity/drawdown and the existing policy thresholds are unchanged;
passing the gate still does not establish a durable trading edge.

## Fail-Closed Rules

The default posture is `remain_paper`. Insufficient evaluation days,
insufficient completed trades, or missing audit evidence prevents future live
consideration. Drawdown breaches, unstable expectancy, poor profit factor, high
fees, high blocked-cycle rate, or poor confidence calibration produce
`make_more_conservative`. Stop-loss violations, capital-preservation events,
governance violations, loss-limit breaches, or rejected evidence quality produce
`pause_for_review`.

## Operating Limits

The evaluation gate cannot enable live trading, create live orders, approve
risk, submit orders, apply strategy changes, modify risk rules, call exchanges,
call providers, or mutate production configuration. Every later trading path
must still pass supervised live controls, preflight checks, and the Risk
Management Engine.

ABTP does not guarantee profit. Paper trading evidence is simulated evidence
only, and only risk capital may ever be considered in a later explicit live
stage.
