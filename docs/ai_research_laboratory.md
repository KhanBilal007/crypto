# AI Research Laboratory

Stage 069 adds a controlled, audit-ready environment for comparing candidate
models, candidate strategies, bounded hyperparameter tests, and regime-specific
evaluations. It consumes evidence created by earlier modules instead of running
new exchange, provider, model-serving, or execution logic.

## Inputs

`ResearchExperimentSpec` records:

- experiment id, title, hypothesis, and evaluation window
- experiment type: model comparison, strategy comparison, hyperparameter test,
  or regime evaluation
- production baseline reference and candidate references
- optional regime label
- optional parameter candidate metadata
- source references for audit reconstruction

Model experiments consume existing `ModelComparisonResult` objects from the AI
model manager. Strategy experiments consume existing `StrategyBenchmarkResult`
objects from the strategy laboratory and walk-forward validation evidence.

## Outputs

`ResearchLabReport` emits:

- ranked experiment results
- candidate score, baseline delta, evidence, rejection reasons, and quality
- promotion advice
- policy version
- source references
- compact audit payload

Promotion advice is advisory. A candidate can only be recommended for review
when it improves over the production baseline, passes score thresholds, and has
trusted quality. Promotion still requires governance review, walk-forward
validation, and paper validation before any operational change.

## Operating Limits

- The research laboratory cannot serve predictions.
- The research laboratory cannot create strategy signals.
- The research laboratory cannot approve risk.
- The research laboratory cannot create order intents.
- The research laboratory cannot submit orders or call exchanges.
- The research laboratory cannot mutate production model or strategy state.
- Rejected or degraded input evidence keeps candidates research-only or rejected.
- No real external AI services, providers, exchange/API calls, or live trading
  behavior are used.
- No profit is guaranteed.
