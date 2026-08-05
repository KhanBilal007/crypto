# Portfolio Intelligence And Hedging

Stage 059 adds advisory portfolio intelligence and hedging recommendations. It
builds on the existing allocation optimizer and reviews supplied portfolio
evidence for cash reserve, asset exposure, sector exposure, correlation,
maximum asset risk, diversification, defensive signals, and allocation quality.

The engine does not create hedge orders. Hedging means advisory cash reserve,
stablecoin allocation, diversification, or exposure-reduction review only.
Futures, margin, options, leverage, derivatives, and executable hedge paths
remain disabled.

## Inputs

`PortfolioIntelligenceInput` contains:

- `AllocationInput` for current portfolio, cash, equity, target weights,
  drawdown, confidence, volatility, liquidity, correlation, and data quality
- Sector exposure map
- Asset risk score map
- Diversification score
- Defensive signal score
- Confidence score
- Optional source quality override

All scores and exposure percentages are normalized `Decimal` values between `0`
and `1`.

## Outputs

`evaluate_portfolio_intelligence` returns `PortfolioIntelligenceReport` with:

- Portfolio health: healthy, watch, defensive, rebalance review, or unknown
- Health score
- Hedge recommendation: none, raise cash, increase stablecoins, reduce
  exposure, diversify, or manual review
- Hedge percentage
- Recommended cash reserve percentage
- Recommended stablecoin percentage
- Diversification score
- Maximum asset exposure
- Maximum sector exposure
- Maximum correlation
- Nested allocation plan
- Reasons, rejection reasons, evidence, quality, and audit payload

## Safety Limits

Rejected quality, cash reserve breach, excessive asset exposure, excessive
sector exposure, excessive correlation, high asset risk, low diversification,
low confidence, or allocation rejection fail closed to defensive review.

Portfolio intelligence cannot create order intents, approve risk, submit
orders, call exchanges, call providers, trade derivatives, or enable live
trading. Any future portfolio change must still pass supervised controls,
order-intent creation, and the Risk Management Engine.

No profit is guaranteed.
