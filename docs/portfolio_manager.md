# Portfolio and Position Manager

Stage 023 adds deterministic portfolio accounting and snapshot construction so
the risk engine can query consistent state before every decision.

## Inputs

`PortfolioManagerState` contains:

- balances
- spot position cost basis
- deterministic market prices
- equity history
- open-order cash reservations
- optional data-quality status

All inputs are local fixtures or repository-fed state. Stage 023 does not call
exchanges, fetch balances, place orders, or execute trades.

## Accounting

The accounting module provides:

- free/reserved balances
- position cost basis
- unrealized P/L
- realized P/L after fees
- max drawdown
- open-order cash reservations with fee buffers

## Exposure

The exposure module aggregates domain `PortfolioPosition` records by asset and
calculates gross exposure, net exposure, and exposure as a percentage of equity.
It also exposes cash-reserve, exposure-limit, and drawdown-limit helpers.

## Manager

`PortfolioManager` can produce:

- domain `PortfolioSnapshot`
- `RiskPortfolioContext` for Stage 022
- exposure summary
- portfolio constraint status

Minimum-risk controls include minimum cash reserve, maximum gross exposure, and
maximum drawdown. Constraint breaches block new positions at the portfolio layer
and provide explicit reasons for the risk engine or future strategy modules.

## Operating Limits

Stage 023 is not a live account sync service. It stores no credentials, makes no
exchange calls, creates no orders, and performs no execution. Live trading
remains disabled.
