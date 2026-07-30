# Simple Paper Trading Command Center

Stage 071 adds a simple, paper-first command center that turns the Stage 070
institutional decision record and existing safety evidence into one
operator-facing label.

## Labels

The command center emits only four labels:

- `BUY REVIEW`: eligible for paper-trade review only.
- `HOLD`: no new paper buy review; continue monitoring.
- `AVOID`: do not review a paper buy because checklist evidence is missing or
  unsafe.
- `PROTECT CAPITAL`: protection, kill switch, severe risk, stale data, exchange
  outage, or capital-preservation evidence overrides all other labels.

`BUY REVIEW` is not permission to trade real money. It is also not sufficient by
itself for future paper execution; Stage 072 must still require a strategy
signal, Risk Management Engine approval, conservative position sizing, and
stop-loss metadata.

## Checklist Inputs

`PaperTradeChecklistInput` consumes:

- Stage 070 `InstitutionalDecisionRecord`
- existing `PaperStatusResponse`
- data-quality status
- exchange-health score
- optional capital-preservation decision
- paper cash/equity/drawdown context
- max paper position size
- stop-loss requirement and stop-loss price
- daily and weekly loss state
- crash/capital-protection flags
- source references

The checklist requires trusted data, acceptable exchange health, acceptable
confidence, acceptable risk score, no active kill switch, no protection block,
available paper cash, positive max paper position size, and stop-loss metadata.

## Outputs

`PaperCommandRecommendation` includes:

- command label
- plain-language explanation
- paper readiness flag
- blocked reasons
- confidence, support, and risk scores
- risk level
- max paper position context
- stop-loss requirement
- account summary
- audit reference and compact audit payload

`PaperCommandCenterDashboardView` renders deterministic text for dashboards,
CLI snapshots, and tests. `PaperCommandCenterResponse` provides a
framework-neutral API response contract.

## Operating Limits

- The command center is paper-first and advisory only.
- It cannot create strategy signals.
- It cannot approve risk.
- It cannot create order intents.
- It cannot submit or cancel orders.
- It cannot call exchanges or providers.
- It cannot change configuration or enable live trading.
- Live trading remains impossible from this stage.
- No profit is guaranteed.
