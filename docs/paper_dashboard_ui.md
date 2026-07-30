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

## Visible State

The dashboard shows `PAPER MODE`, `SAFE MODE`, BTC/USDT price, spread, data
freshness, market regime, strategy recommendation, indicator reasons, AI
confidence when available, risk decision, data quality, suggested paper trade,
simulated portfolio state, paper logs, and a link to the paper-trading status
report.

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
