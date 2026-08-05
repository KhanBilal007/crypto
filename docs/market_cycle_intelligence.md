# Market Cycle Intelligence

Stage 052 adds advisory cryptocurrency market-cycle intelligence. It classifies
the broad cycle using supplied BTC dominance, ETH dominance, altcoin-season,
market-breadth, fear/greed, and liquidity scores.

This stage does not call exchanges, call external data providers, create
strategy signals, approve risk, create order intents, execute orders, or enable
live trading.

## Inputs

`MarketCycleInput` contains normalized scores from `0` to `1`:

- BTC dominance
- ETH dominance
- altcoin season
- market breadth
- fear and greed
- liquidity
- data-quality status
- source references

All values are supplied by deterministic fixtures or future stored analytics.

## Outputs

`MarketCycleAssessment` includes:

- cycle phase
- cycle confidence
- risk level
- advisory allocation suggestion
- reasons and rejection reasons
- evidence records
- quality status
- policy version
- audit payload

Supported phases are bull accumulation, bull expansion, bull euphoria,
distribution, bear market, capitulation, recovery, and unknown.

## Safety Rules

Rejected, stale, or low-confidence cycle inputs fail closed. Allocation output
is advisory context only; it is not an executable rebalance, strategy change, or
order. Future trading actions must still pass the Strategy Engine, supervised
live gateway controls, preflight checks, and the Risk Management Engine. No
profit is guaranteed.
