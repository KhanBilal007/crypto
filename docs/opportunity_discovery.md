# Opportunity Discovery

Stage 057 adds an advisory opportunity discovery engine. It ranks a supplied
crypto universe using normalized technical, AI, fundamental, on-chain,
liquidity, risk, relative-strength, momentum, market-cycle, and expected holding
period evidence.

The engine does not scan exchanges, call market-data providers, call ranking
vendors, call blockchains, or call external services. A future collector may
populate the input universe, but this stage only ranks supplied deterministic
candidate objects.

## Inputs

`OpportunityCandidate` contains:

- Asset symbol
- Technical score
- AI score
- Fundamental score
- On-chain score
- Liquidity score
- Risk score
- Relative-strength score
- Momentum score
- Market-cycle score
- Expected holding period
- `DataQualityStatus`
- Source references and stale flag

Scores are normalized `Decimal` values between `0` and `1`.

## Outputs

`discover_opportunities` returns `OpportunityDiscoveryReport` with:

- `top_opportunities`: ranked advisory top list, capped by policy
- `watch_list`: candidates that may deserve monitoring but do not clear top
  filters
- `avoid_list`: candidates rejected by low score, high risk, low liquidity, bad
  quality, stale inputs, or low confidence
- Report confidence
- Rejection reasons
- Quality status
- Audit payload

Each `OpportunityRanking` includes reasons, evidence, confidence, risk,
liquidity, expected holding period, and source-quality context.

## Safety Limits

Opportunity discovery is advisory ranking context only. It cannot create
strategy signals, approve risk, create order intents, submit orders, execute
trades, call exchanges, call external providers, or enable live trading.

Insufficient universe coverage, stale or rejected inputs, high risk, weak
liquidity, low confidence, and no qualifying top opportunities fail closed or
move candidates to watch/avoid lists. Avoid-list entries do not imply bad data
when the reason is market risk or weak liquidity; they are still explicit
non-actionable rankings.

No profit is guaranteed. Future strategy or execution behavior must still pass
the Risk Management Engine.
