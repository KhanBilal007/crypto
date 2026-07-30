# Fundamental Asset Rating

Stage 054 adds an advisory fundamental asset rating engine. It evaluates
supplied, normalized project-quality metrics and emits a long-term rating,
long-term score, risk grade, confidence, evidence, and quality status.

The engine does not call GitHub, blockchains, exchanges, market-data providers,
fundamental-data vendors, or any other external service. GitHub and developer
activity inputs are normalized scores supplied by deterministic fixtures or
future stored provider outputs.

## Inputs

`FundamentalInput` contains normalized `Decimal` scores between `0` and `1` for:

- Market cap
- Liquidity
- Developer activity
- GitHub quality
- TVL
- Staking
- Tokenomics
- Inflation control
- Partnerships
- Institutional adoption
- Security
- Roadmap
- Community
- Governance

Each input also carries `asset_symbol`, `observed_at`, `DataQualityStatus`,
source references, and a stale-input flag.

## Outputs

`assess_fundamental_asset` returns `FundamentalAssessment` with:

- `rating`: `strong`, `adequate`, `watchlist`, `weak`, or `unknown`
- `long_term_score`: weighted project-quality score
- `risk_grade`: `low`, `moderate`, `high`, `severe`, or `unknown`
- `confidence`: deterministic confidence in the rating context
- `reasons`: human-readable classification reasons
- `rejection_reasons`: fail-closed causes
- `evidence`: metric-level source references and contributions
- `quality`: trusted, degraded, or rejected quality status
- `audit_payload`: compact reconstruction fields for audit events

## Safety Limits

Fundamental ratings are advisory context only. They cannot create signals,
approve risk, create order intents, submit orders, execute trades, call
exchanges, call GitHub, call external providers, or enable live trading.

Rejected, stale, critically weak security, critically weak liquidity, or
low-confidence inputs fail closed by returning an `unknown` rating and `severe`
risk grade. Degraded inputs remain visible but are not actionable context.

No profit is guaranteed. Future strategy or execution behavior must still pass
the Risk Management Engine.
