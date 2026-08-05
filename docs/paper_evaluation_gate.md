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
