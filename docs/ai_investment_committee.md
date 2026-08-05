# AI Investment Committee

Stage 060 adds an advisory AI Investment Committee. It combines supplied votes
from independent committee members into a transparent recommendation with
confidence, disagreement, reasoning, quality, and audit context.

The committee does not serve models, train models, call external AI providers,
call exchanges, create strategy signals, approve risk, create order intents, or
execute trades.

## Committee Members

The committee supports the Stage 060 seats:

- Trend AI
- Momentum AI
- Macro AI
- Risk AI
- On-chain AI
- Fundamental AI
- Liquidity AI
- Sentiment AI
- Portfolio AI
- Execution AI

Each `InvestmentCommitteeVote` includes member, direction, confidence, weight,
rationale, input reference, source quality, timestamp, and source references.

## Outputs

`evaluate_investment_committee` returns `InvestmentCommitteeReport` with:

- Recommendation: favorable review, defensive review, hold review, or no
  decision
- Winning direction
- Confidence
- Disagreement
- Weighted tally
- Votes
- Reasons
- Rejection reasons
- Quality status
- Audit payload

## Safety Limits

Missing required risk or portfolio votes, insufficient vote count, rejected
vote quality, abstentions, low confidence, weak agreement, or excessive
disagreement fail closed to no decision.

Committee recommendations are advisory context only. Any future action must
still pass strategy logic, supervised controls, order-intent creation, and the
Risk Management Engine.

No profit is guaranteed.
