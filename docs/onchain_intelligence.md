# On-Chain Intelligence

Stage 053 adds advisory on-chain intelligence from normalized blockchain
activity metrics supplied by fixtures or future stored provider outputs.

This stage does not call blockchains, exchanges, external APIs, or data
providers. It does not create strategy signals, approve risk, create order
intents, execute orders, or enable live trading.

## Inputs

`OnChainInput` includes normalized scores for:

- MVRV
- SOPR
- NUPL
- exchange inflow
- exchange outflow
- whale wallet activity
- miner selling
- dormancy
- coin days destroyed
- realized price position
- hash rate
- network growth
- data-quality status
- source references

## Outputs

`OnChainAssessment` includes:

- on-chain state
- on-chain score
- accumulation score
- distribution score
- confidence
- reasons and rejection reasons
- evidence records
- data-quality status
- policy version
- audit payload

Supported states are accumulation, distribution, network strength, network
stress, neutral, and unknown.

## Safety Rules

Rejected, stale, or low-confidence on-chain inputs fail closed. On-chain output
is optional intelligence context only. Future trading actions must still pass
the Strategy Engine, supervised live gateway controls, preflight checks, and the
Risk Management Engine. No profit is guaranteed.
