# Macro And Narrative Intelligence

Stage 056 adds an advisory macro and narrative intelligence engine. It evaluates
supplied, normalized macro pressure, equity/liquidity, ETF flow, and crypto
narrative evidence, then emits macro risk, narrative strength, risk-on score,
confidence, reasons, quality, and audit context.

The engine does not call central-bank, inflation, ETF, news, market-data,
exchange, or external-provider services. All inputs are supplied by
deterministic fixtures or future stored provider outputs.

## Inputs

`MacroInput` contains normalized `Decimal` scores between `0` and `1` for:

- Interest-rate pressure
- Fed hawkishness
- ECB hawkishness
- Inflation pressure
- CPI surprise
- PPI surprise
- Dollar index strength
- Bond-yield pressure
- Gold safety bid
- Oil inflation pressure
- Nasdaq strength
- S&P 500 strength
- ETF flows

`NarrativeObservation` contains normalized strength, momentum, liquidity, and
attention scores for AI, RWA, stablecoins, gaming, Layer 2, memecoin, and DeFi
narratives.

Every input carries `DataQualityStatus`, timestamps, source references, and a
stale flag.

## Outputs

`assess_macro_narrative` returns `MacroNarrativeAssessment` with:

- `macro_risk_score`
- `narrative_strength`
- `risk_on_score`
- `mode`: risk-on, risk-off, narrative-led, neutral, or unknown
- `leading_narrative`
- ranked narrative strengths
- confidence, reasons, rejection reasons, quality, and audit payload

## Safety Limits

Macro and narrative output is advisory context only. It cannot create strategy
signals, approve risk, create order intents, submit orders, execute trades, call
exchanges, call external providers, call news services, or enable live trading.

Elevated macro risk, stale or rejected inputs, insufficient narrative coverage,
and low confidence fail closed. Degraded inputs remain visible but are not
actionable context.

No profit is guaranteed. Future strategy or execution behavior must still pass
the Risk Management Engine.
