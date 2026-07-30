# Multi-AI Voting System

Stage 036 combines independent AI model opinions into advisory strategy context.
It does not create strategy signals, risk decisions, order intents, exchange
calls, or execution behavior.

## Model Families

The voting layer defines provider-neutral model families:

- Trend AI
- Momentum AI
- Volatility AI
- Order Book AI
- On-chain AI
- Sentiment AI

On-chain and sentiment votes are optional and lower-trust unless a deterministic
source-quality path is available. Tests use deterministic stubs only.

## Voting Contracts

Each `ModelVote` includes:

- model name and family
- direction: bullish, bearish, neutral, or abstain
- confidence
- weight
- input reference
- rationale
- data-quality status
- source references

`ConsensusResult` includes:

- advisory consensus direction
- consensus score
- confidence
- actionable flag
- rejected reasons
- quality status
- vote logs
- voting policy version
- source references

## Consensus Rules

`VotingPolicy` supports majority and weighted voting. A consensus is
non-actionable when:

- there are too few usable votes
- model confidence is below threshold
- model vote quality is rejected
- trusted votes are required and a vote is degraded
- agreement is below threshold
- disagreement is above threshold
- consensus confidence is below threshold

Non-actionable consensus is explicit and fail-closed. Consumers must inspect
`rejected_reasons` and `quality` before using the result.

## Safety Limits

- Voting output is advisory strategy context only.
- Voting cannot submit orders.
- Voting cannot create order intents or risk decisions.
- All future signals must still pass the Strategy Engine.
- All future order paths must still pass the Risk Management Engine.
- No real external AI service, exchange API, external provider, or live trading
  behavior is added in this stage.
- No profit is guaranteed.
