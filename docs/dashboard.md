# Paper Trading Dashboard

Stage 028 adds read-only dashboard view models for paper trading. The dashboard
is dependency-free and renders deterministic text for tests and future CLI/UI
wrappers.

## Visible State

The paper dashboard shows:

- current BTC price
- active regime
- latest signal
- latest risk decision
- blocked-trade reason
- data health
- pause and kill-switch state
- simulated cash, BTC quantity, equity, fees, and drawdown
- trade count
- parameter health for close price, spread, stream latency, and data-quality
  flags

This gives an operator enough information to inspect why paper mode did or did
not trade during the latest cycle.

## Controls

The dashboard data model surfaces only safe controls supplied by the API layer:
pause, resume, and activate kill switch. It does not expose order placement,
exchange calls, withdrawals, live routes, leverage, margin, futures, or options.

## Operating Limits

The Stage 028 dashboard is a validation surface, not a production operations
console. It does not claim profitability and does not authorize live trading.

## Local Paper Dashboard UI

The browser UI is documented in
[`docs/paper_dashboard_ui.md`](paper_dashboard_ui.md). It is a standard-library
local server over the existing paper API and paper engine contracts:

```powershell
.\.venv\Scripts\python.exe -m abtp.dashboard.paper_server
```

If the package is installed, the same server can be started through the
console script:

```powershell
abtp-paper-dashboard
```

You can also launch the package module directly:

```powershell
python -m abtp.dashboard
```

Open `http://127.0.0.1:8765` while the command is running. Stop it with
`Ctrl+C`. The UI is paper-only and cannot submit live orders.
