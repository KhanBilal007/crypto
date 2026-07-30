# Trade Intelligence And Learning Engine

Stage 062 adds an advisory trade intelligence layer over completed trade
records. It extends the earlier self-learning module with holding-time review,
best observed regimes, best observed strategies, best observed indicator
relationships, AI-confidence accuracy, common mistake detection, and
improvement suggestions.

The engine uses deterministic completed-trade fixtures or stored paper/backtest
records. It does not call exchanges, call external providers, train models,
serve predictions, create signals, approve risk, create order intents, submit
orders, cancel orders, or execute trades.

## Inputs

Trade intelligence consumes `TradeLearningRecord` objects from the learning
package. Each record includes strategy, regime, opened/closed timestamps,
realized P/L, return percentage, fees, signal confidence, optional prediction
confidence, feature values, risk status, source references, and optional data
quality.

Rejected trade records are excluded. Degraded records degrade the report so
future strategy and risk modules cannot treat it as trusted evidence.

## Outputs

`build_trade_intelligence_report` emits a `TradeIntelligenceReport` containing:

- `LearningAnalysis` from the existing self-learning analyzer
- holding-time summary and longest losing trade reference
- best observed regimes and strategies, subject to minimum sample size
- strongest observed indicator relationships
- simple AI-confidence accuracy
- common mistakes such as high-confidence losses, fee drag, long holding losses,
  and weak regime fit
- improvement suggestions with evidence references
- quality status, source references, audit payload, and limitations

Suggestions are advisory and include hard safety flags:

- `requires_validation=true`
- `allowed_to_auto_apply=false`

## Operating Limits

- No profit is guaranteed.
- Trade intelligence must never bypass the Risk Management Engine.
- Suggestions cannot automatically change strategies, confidence thresholds,
  model selection, risk limits, allocations, or execution behavior.
- Poor-quality or under-sampled inputs degrade the report and suppress
  suggestions.
- AI accuracy is a simple audit metric over supplied `prediction_confidence`;
  it is not a live prediction service.
- Tests use deterministic fixtures and require no real exchange credentials,
  provider credentials, or network access.
