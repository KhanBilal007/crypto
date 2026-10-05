# Paper Bot Profitability And Runtime Audit

Date: 2026-09-10. Repository baseline: `60db1c1`.
Final local verification: 2026-09-14 (IST).

## Scope And Deployment Status

Inspected the public status and evidence exports at `https://3.233.15.209/`.
Implemented corrections in the local repository. These corrections have NOT
been installed on that server. Server deployment method/access is still needed.
No live orders, transfers, or account configuration changes were sent to it.

The requested operating policy is **real Binance market data for normal use**.
Paper trading refers to simulated money, not simulated prices. Normal dashboard
startup now defaults to `ABTP_MARKET_DATA_SOURCE=binance`. A Binance startup
failure raises an error; it cannot silently substitute demo candles. Failed
tickers become unavailable or retain their explicitly degraded last-known
price. Failed trade-tape requests return no trades, never generated trades.
Deterministic fixtures remain explicitly selected by automated unit tests.

## What The Deployed Server Actually Reported

Captured on 2026-09-10 at approximately 02:33 IST:

| Account | Starting balance (USDT) | Reported P/L (USDT) | Reported fills |
| --- | ---: | ---: | ---: |
| Main wallet / MinRisk | 1,000 | 0.00 | 0 |
| Shadow MinRisk | 10,000 | 0.00 | 0 |
| Shadow Breakout | 10,000 | +459.04 | 10 |
| Shadow Support/Rebound | 10,000 | +22.52 | 54 |
| Shadow Trend Pullback | 10,000 | -48.12 | 6 |

These are server-reported simulated results, not verified exchange profits.
The main wallet and shadow wallets are separate. Selecting a Strategy Lab row
does not switch the main wallet's strategy. The main engine still uses MinRisk.
The shadow sample counter was 97, while startup loads 60 hourly observations;
that counter cannot establish 30 days of uninterrupted operation. The event
export included a restart on September 2. Full server files and service logs
were not available, so this is not a reconstruction of every deployed trade.

## Findings And Corrections

1. **Processing depended on browser traffic.** The HTTP server only refreshed
   market data inside dashboard status requests. Added a server-loop refresh
   that works without browser requests. Requests and refreshes share a lock.
   A real HTTP-server test verifies refresh without sending any requests.

2. **Only one closed candle was fetched after an interruption.** Added bounded
   catch-up of up to 998 closed hourly candles. Older missed bars update
   indicators without fabricated historical fills. Execution is permitted only
   for bars closed within two minutes of the current check. Missed execution
   bars, last successful check, last processed candle, and errors are exposed.
   Downtime before the available history window is not reconstructed.

3. **Daily confirmation was frozen at process startup.** Refresh now updates
   every wrapped strategy using the last four daily candles available at the
   hourly signal time. No future daily close is applied to an earlier signal.

4. **Startup history could trade before wallet restoration.** Binance startup
   now warms indicators without trades. It requires 50 observations before new
   decisions can execute. The simulator rejects unfinished or unordered bars
   and does not execute the same candle twice.

5. **Suggested stops/targets were not enforced by the engine.** Added protective
   exits checked independently of entry filters. Stop first when a candle
   crosses both levels; adverse opening gaps fill at the worse price. Exits
   close the position, and drawdown halts allow exposure-reducing closure.
   Exit levels, halt state, and the candle cursor persist with the account.
   These remain candle-based simulations, not exchange-hosted stop orders.

6. **Entry filters suppressed exits.** The swing strategies previously returned
   HOLD on low volume or a downtrend before reaching their SELL logic. Exit
   evaluation now precedes those entry-only checks. Existing positions are
   managed without repeated swing entries. Breakout also exits below EMA 21;
   pullbacks require a higher close; rebounds require support to hold and enough
   room below resistance to cover the configured reward/risk and trading costs.

7. **ATR was a single candle's range.** Reused the repository's tested rolling
   true-range indicator, which accounts for gaps. Volume confirmation uses the
   previous 20 candles. Flat rolling RSI is neutral. Short fixture warmup values
   are never eligible for normal Binance execution before the 50-bar warmup.

8. **SELL slippage increased the sale price.** Corrected the shared paper router
   so costs worsen both BUY and SELL prices. Risk sizing uses the same fee
   assumption as the fill simulator. Prior reported results may be optimistic.

9. **Win rate and expectancy used candle returns instead of closed trades.**
   Added complete-position statistics, including entry and exit fees and partial
   fills. The table separates fills from closed trades and labels quote-currency
   expectancy. No closed trades produces N/A, not a claimed zero-percent result.
   An incomplete legacy ledger produces unavailable trade statistics.
   The Advanced performance summary now uses the same closed-position basis;
   an unrealized price increase is not counted as a winning trade.

10. **Pause and emergency-stop state did not protect the background path.**
    All five engines now respect dashboard pause/stop controls. These controls
    persist across restart. JSON state uses an atomic replacement when saved.

11. **Live-data presentation included misleading placeholders.** Removed the
    unsupported static `GPT-4o / Verified` label; the current strategy path is
    rule-based, with no configured AI model. Header, footer, and runtime telemetry
    now share measured full-refresh duration (not a fabricated 10 ms, and not
    websocket latency). The public trade tape requests Binance's latest 20
    aggregate trades rather than the first 20 in an older time window. Only the
    selected strategy gets a selection marker in Compare Runs.

## Historical Evaluation Using Real Binance Data

Input: public Binance BTC/USDT hourly and daily candles, downloaded on the audit
date. This is historical exchange data, not a synthetic sample. The machine-readable
report is [strategy_validation_2026_09_10.json](strategy_validation_2026_09_10.json).
It includes timestamps, a dataset SHA-256, signal counts, blocked-entry reasons,
trade counts, fees, P/L, drawdown, and all comparison rows.

Method: 90 days split chronologically into 60 days and 30 days, independently
funded accounts per window, 10,000 USDT initial equity, maximum 0.01 BTC per
entry, 0.25% maximum risk per trade, 20 bps fee on each side, 10 bps spread,
and 5/10 bps slippage scenarios. Entries and strategy-directed exits use the
next candle open. Stops and targets use conservative bar-range simulation.
No parameter grid search or tuning to the reported result was performed.

Legacy rows use the old strategy rules on the SAME corrected indicator,
daily-confirmation, risk, and execution pipeline. They are not a reproduction
of the faulty deployed runtime. The main MinRisk rules remain the control.

Results at 5 bps slippage, net USDT per independent 10,000-USDT account:

| Strategy | Old rules, first 60d | Revised rules, first 60d | Old rules, final 30d | Revised rules, final 30d | Revised closed trades, final 30d |
| --- | ---: | ---: | ---: | ---: | ---: |
| Trend Pullback | -35.53 | -14.49 | -39.47 | -22.04 | 4 |
| Breakout | -37.58 | -24.29 | +16.99 | +27.31 | 7 |
| Support/Rebound | -246.20 | 0.00 | -99.72 | 0.00 | 0 |
| MinRisk control | unchanged rules | +3.56 | unchanged rules | +19.01 | 1 |

At 10 bps slippage, revised Breakout made +22.17 USDT in the final 30 days.
It still lost in the first 60 days. Trend Pullback remains negative. The revised
rebound rules avoided the old rules' losing trades by staying out; no trades
does NOT demonstrate a profitable strategy. One winning MinRisk trade also
does not establish an edge.

**Conclusion: engineering improvements and reduced losses are supported by
these checks. Large or dependable profits are NOT established.** Position size
and risk ceilings were not raised to inflate the result. The 0.01-BTC entry cap
also limits account-level returns: a strategy's price move is not the same as
the percentage return on the entire wallet.

Limitations: no historical order book, queue position, tick sequence, or actual
exchange fee tier; estimated fills can differ from real fills. The chronological
last-30-day check is not a pristine unseen holdout after this audit. Price-only
buy-and-hold comparison is gross and fully invested, with different exposure.
The old standalone backtesting engine is not used by this comparison; the
validation command deliberately uses the same paper pipeline as the dashboard.

Reproduce with the retained local dataset:

```powershell
.\.venv\Scripts\python.exe -m abtp.paper.strategy_validation --data .codex_tmp/btc_validation_2026_09_10.json --output docs/strategy_validation_2026_09_10.json --days 90 --baseline-ref 60db1c1
```

Add `--download` to fetch a new rolling period. Raw data stays in the ignored
`.codex_tmp` folder; the JSON report and this audit are reviewable repository
files. A new download will have different data/timestamps and results.

## Current Binance Check

An isolated local server on `http://127.0.0.1:8871/` uses real Binance prices and
separate test wallets. Its state/database are under `.codex_tmp/realtime_audit*`.
It does not replace the user's saved wallet or alter the remote deployment.

Two observations verified current BTC/USDT price/timestamp movement:

| Time (IST, September 10) | BTC price (USDT) | Source |
| --- | ---: | --- |
| 02:55:35 | 78,260.01 | Binance spot |
| 02:56:05 | 78,268.52 | Binance spot |

The 15-second server poll operates without a browser. Strategy decisions use
closed 1-hour candles and daily confirmation. This short check establishes a
working live-data connection, not a new 30-day performance record.

### September 14 Verification

- Full suite: `631 passed`; Ruff lint and format checks passed; mypy passed for
  217 source files. `git diff --check` found no whitespace errors.
- Browser checks covered Beginner, Advanced, and Strategy Mode navigation,
  live Binance source/price/timestamps, the four comparison rows, corrected
  model labeling, and unavailable win rate before any position closes.
  No browser console errors were reported during this check.
- At 01:56:10 IST, BTC/USDT was 77,317.30 USDT; the latest displayed aggregate
  trade was timestamped 01:56:11.243 IST. At 01:59:17 IST the displayed price
  was 77,326.01 USDT. Both the market and runtime panels reported 2,219 ms for
  that later refresh. Data and strategy freshness were current, live execution
  remained false, and four independent shadow accounts were present.
- Visual inspection was on desktop. This was not a complete mobile/layout
  certification. Compare Runs now keeps strategy names and monetary values
  intact, formats balances to two decimals and rates as percentages, and uses
  horizontal scrolling for its wide set of columns. All 48 dashboard tests
  passed again after this final presentation adjustment.
- These changes and reports are saved locally, not committed or pushed as part
  of this audit. The original `docs/paper_dashboard_state.json` was already
  modified before the audit and was not edited or reset by this work.

## Remaining Before A Server Rollout

- Obtain the server deployment path/service name and authorized update method.
- Back up both the JSON state and SQLite database, including any WAL sidecars,
  while the service is stopped. Preserve all prior trial evidence.
- Install the reviewed changes with `ABTP_MARKET_DATA_SOURCE=binance` and paper
  execution settings. Do not enable live order placement.
- Keep old and revised performance periods separate for analysis. Existing
  wallet history is preserved and explicitly labeled as cumulative; it is not
  automatically reset or represented as a fresh v2 experiment.
- Inspect existing legacy positions: old saved files have no durable protective
  levels. Do not invent historical stop orders or pretend they were executed.
- Confirm a new candle is processed with every browser closed, then verify the
  cursor and safety controls survive a restart. Use a supervisor with restart
  policy because unavailable Binance data now causes a visible startup failure.
- Review reverse-proxy authentication. Public wallet/evidence GET routes were
  accessible without credentials; application code does not authenticate its
  control routes. No unauthorized-control request was attempted. The HTTPS
  certificate was not trusted by the local client and also needs replacement.
- Continue a dated forward paper trial. Do not promote a strategy on seven
  trades, select a winner by raw profit alone, or erase its losing periods.

## References

- [Binance spot market-data API](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints): closed-candle time fields and historical pagination.
- [Fidelity ATR guide](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr): true range and gaps in volatility measurement.
