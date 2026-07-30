# Capital Preservation Framework

Stage 061 adds an advisory capital preservation framework for adverse market
conditions. It extends the existing crash-protection layer and evaluates
supplied evidence for crash, exchange failure, liquidity crisis, extreme
volatility, whale dump, macro shock, ETF outflow, cash reserve, confidence
thresholds, and source quality.

The framework does not execute protective actions. Pause trading, reduce
allocation, increase cash, raise confidence threshold, tighten stops, and
kill-switch review are recommendations only.

## Inputs

`CapitalPreservationInput` contains normalized `Decimal` scores between `0` and
`1` for:

- Crash
- Exchange failure
- Liquidity crisis
- Extreme volatility
- Whale dump
- Macro shock
- ETF outflow

It also accepts current cash percentage, current confidence threshold, source
quality, optional crash-protection decision, source references, and stale-input
status.

## Outputs

`evaluate_capital_preservation` returns `CapitalPreservationDecision` with:

- Protection mode: normal, watch, defensive, emergency, or kill-switch review
- Emergency level
- Recovery status
- Preservation score
- Target cash percentage
- Allocation reduction percentage
- Raised confidence threshold
- Stop-tightening multiplier
- Advisory actions
- Reasons, quality, and audit payload

## Safety Limits

Capital preservation fails closed when inputs are stale or rejected, crash
protection is active, or preservation scores reach emergency/kill-switch review
levels. All actions are advisory and manual-review oriented. Stage 061 cannot
create order intents, approve risk, submit orders, cancel orders, call
exchanges, or enable live trading.

No profit is guaranteed. Future trading actions must still pass supervised
controls and the Risk Management Engine.
