# AI Investment Report Generator

Stage 063 adds a structured, explainable investment report generator. Reports
combine supplied advisory evidence into an institutional-style summary with
sections for why buy, why sell, why hold, market cycle, macro analysis,
on-chain evidence, fundamentals, AI votes, risk, expected return, expected
holding period, and portfolio impact.

The generator does not fetch data, call exchanges, call external providers,
serve AI models, create strategy signals, approve risk, create order intents,
submit orders, cancel orders, or execute trades.

## Inputs

`InvestmentReportInput` accepts an asset symbol, generated timestamp, expected
return, expected holding period, source references, and a deterministic sequence
of `InvestmentReportSection` objects. Each section includes:

- section type
- title and summary
- stance: supportive, opposing, neutral, or unknown
- confidence and weight
- data-quality status
- evidence points and source references

All report evidence is supplied by earlier advisory modules or deterministic
fixtures. Missing, stale, rejected, or degraded evidence fails closed.

## Outputs

`generate_investment_report` emits an `AIInvestmentReport` containing:

- advisory recommendation: buy review, sell review, hold review, or no decision
- directional scorecard
- why-buy, why-sell, and why-hold evidence
- expected return and holding-period context
- portfolio impact summary
- rejection reasons and quality flags
- audit payload
- deterministic Markdown rendering

The recommendation labels are review labels only. They are not strategy
signals, order intents, risk approvals, or live-trading permissions.

## Operating Limits

- No profit is guaranteed.
- Reports must never bypass the Risk Management Engine.
- Reports cannot automatically change strategy, allocation, risk, model, or
  execution behavior.
- If required sections are missing, stale, rejected, or below confidence
  thresholds, the report returns `no_decision`.
- Tests use deterministic fixtures and require no real credentials, provider
  access, exchange access, or network calls.
