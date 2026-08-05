# Paper Trading Dashboard UI

The local paper dashboard is a standard-library HTTP UI for inspecting ABTP
paper mode. It uses deterministic sandbox data by default and wraps the
existing paper API, paper engine, minimum-risk strategy, Risk Management
Engine, portfolio accounting, and paper-safe execution contracts.

Start it locally:

```powershell
.\.venv\Scripts\python.exe -m abtp.dashboard.paper_server
```

Then open:

```text
http://127.0.0.1:8765
```

Stop it with `Ctrl+C` in the terminal that started the server.

Run the dashboard smoke check without opening a port:

```powershell
.\.venv\Scripts\python.exe -m abtp.dashboard.paper_server --smoke
```

## Exports

The dashboard exposes local read-only exports:

- `/paper-report` for current paper status and readiness verdict
- `/paper-transactions.csv` for paper transaction rows
- `/trader-feedback.csv` for trader review feedback rows
- `/trader-handoff.md` for a paper-mode trader review packet
- `/trader-evidence.json` for machine-readable readiness, safety, strategy,
  portfolio, transaction, and evidence sections

Use `docs/trader_review_handoff.md` before sharing the dashboard with a trader
reviewer.

## Visible State

The dashboard shows `PAPER MODE`, `SAFE MODE`, BTC/USDT price, spread, data
freshness, market regime, strategy recommendation, indicator reasons, AI
confidence when available, risk decision, data quality, suggested paper trade,
simulated portfolio state, paper logs, and a link to the paper-trading status
report.

Advanced Trader and Strategy Lab also include a local Trader Feedback panel for
reviewer corrections. Feedback entries are paper-only and can record reviewer
role, category, severity, summary, recommendation, open/closed status,
resolution, and resolved timestamp. Open blocker-severity feedback blocks
paper-demo readiness until closed, and closing a blocker requires a resolution
note.

The Advanced Trader paper order ticket shows Binance-style symbol filters for
the local BTC/USDT paper market: tick size, step size, minimum quantity, and
minimum notional. These filters validate simulated paper orders before they are
staged, but they do not submit orders to Binance.

When Binance market data is configured, the running dashboard refreshes
read-only ticker/watchlist and order-book observations through `/api/status` on
a throttled interval. The browser refreshes status every 15 seconds. If Binance
refresh fails, the dashboard marks the affected market rows degraded instead of
claiming stale prices are fresh.

## Controls

The controls are paper-only:

- Approve Paper Trade
- Reject Recommendation
- Pause Paper Bot
- Resume Paper Bot
- Emergency Stop

`Approve Paper Trade` records operator approval for an already risk-approved
simulated paper fill. It does not create an order, approve risk, submit an
order, call an exchange, or enable live trading. When the Risk Management
Engine rejects a recommendation, the dashboard disables approval and the API
rejects approval attempts.

## Safety Limits

- `SAFE_MODE=true`
- live trading disabled
- no real exchange credentials or secret values are displayed
- no live-order route exists
- leverage, margin, futures, options, withdrawals, and transfers are disabled
- every simulated fill still comes from the paper engine after Risk Management
  Engine approval

This UI is not financial advice and does not claim profitability.
