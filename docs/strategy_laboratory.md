# Strategy Laboratory

Stage 040 adds an advisory laboratory for maintaining, comparing, and preparing
many strategy versions. It does not replace the Strategy Engine and it does not
create executable trading actions.

## Catalogue

`StrategyCatalogueEntry` records:

- strategy key, name, version, and family
- catalogue status: benchmark, candidate, active, disabled, or retired
- regime suitability labels
- optional parameter-space and validation references
- source references for auditability

`StrategyLaboratoryRegistry` provides deterministic registration and lookup by
key, family, status, version, and regime suitability. Disabled and retired
strategies can remain in the catalogue for audit and comparison, but they are
not eligible for laboratory promotion.

## Parameter Candidates

`ParameterSearchSpace` and `ParameterSpec` generate bounded deterministic
parameter candidates for offline evaluation. Candidate generation is
conservative:

- parameter ranges must have explicit minimum, maximum, step, and default
- candidate counts are capped
- the default candidate can be preserved even when the search is truncated
- generated candidates are not applied to live strategy code

These utilities prepare experiments only. Any candidate must still pass
backtesting, walk-forward validation, risk gates, and manual promotion reviews.

## Benchmarks

`compare_strategies` consumes catalogue entries, existing `PerformanceMetrics`,
and optional Stage 039 `RobustnessScore` values. It compares candidates against
a baseline using:

- win rate
- expectancy
- drawdown
- profit factor
- regime fit
- walk-forward robustness
- data-quality status
- catalogue status

Candidates are rejected when they are disabled or retired, fail risk limits,
lack walk-forward evidence, do not improve enough over the baseline, lack regime
suitability, or use untrusted input quality.

## Auditability

`StrategyLaboratoryReport` serializes ranked benchmark results, rejected
reasons, recommended strategy key, policy version, and source references. Its
audit payload is compact enough to store alongside future operator review
records.

## Operating Limits

- Laboratory recommendations are advisory only.
- The laboratory cannot create strategy signals.
- The laboratory cannot create risk decisions.
- The laboratory cannot create order intents or submit orders.
- Parameter optimization cannot self-apply changes to live strategies.
- Live strategy changes remain blocked unless supervised live controls and
  manual approvals explicitly allow them.
- No real exchange/API calls or external providers are used.
- No profit is guaranteed.
