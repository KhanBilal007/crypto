# Institutional Decision Intelligence Hub

Stage 070 combines platform intelligence into a single advisory investment
decision record. It consumes normalized evidence from earlier modules and
produces an audit-ready decision for operator review.

## Inputs

`DecisionEvidence` normalizes upstream reports from:

- multi-timeframe intelligence
- market-cycle assessment
- on-chain analysis
- fundamental rating
- macro and narrative intelligence
- AI investment committee
- portfolio status
- Risk Management Engine context
- opportunity scanner
- confidence engine

Each evidence item includes confidence, support score, risk score, quality
status, stale/blocking flags, source references, summary, and optional holding
period context.

## Outputs

`InstitutionalDecisionRecord` emits:

- final decision: favorable review, hold review, defensive review, or reject no
  action
- confidence score
- support score
- suggested allocation context
- holding period
- entry and exit plan
- risk assessment
- complete evidence list
- reasons and rejection reasons
- quality flags
- compact audit payload

Suggested allocation and entry/exit plans are advisory context only. They are
not signals, order intents, order instructions, or approval to move capital.

## Fail-Closed Behavior

The hub rejects favorable review when required evidence is missing, stale,
blocking, rejected, below confidence threshold, above risk threshold, or not
trusted. Risk-engine and confidence-engine evidence are required by default.

## Operating Limits

- The hub cannot create strategy signals.
- The hub cannot approve risk.
- The hub cannot create order intents.
- The hub cannot submit orders or execute trades.
- The hub cannot mutate model, strategy, portfolio, or configuration state.
- No exchange, provider, model-serving, or live trading calls are made.
- Future trading actions must still pass the Strategy Engine, supervised live
  controls where applicable, and the Risk Management Engine.
- No profit is guaranteed.
