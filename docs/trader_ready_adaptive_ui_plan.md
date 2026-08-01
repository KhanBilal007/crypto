# Trader-Ready Adaptive UI Plan

This plan upgrades ABTP from one paper dashboard into role-aware trading
workspaces. The goal is not to make trading more aggressive. The goal is to
show the right amount of information for the current user and strategy while
only activating backend modules that are safe and relevant for that view.

Live trading remains disabled unless a later explicit supervised-live stage is
reviewed and approved.

## Objective

Build one adaptive dashboard with three view families:

1. Beginner view: simple, safe, plain-language paper trading.
2. Advanced trader view: dense analytics, charts, backtests, and risk evidence.
3. Strategy views: layouts and modules tailored to the selected strategy.

Each view must declare which backend modules it uses. Backend modules should not
run just because they exist; they should run because the active view and strategy
need their evidence.

## View Selection

The dashboard should expose a top-level mode selector:

- Beginner
- Advanced Trader
- Strategy Lab

The selected view should be saved locally so the dashboard opens in the same
mode next time.

The UI mode is separate from trading mode. UI mode changes what is shown and
which advisory modules run. It must not enable live trading.

## Beginner View

Purpose: help a new user answer only three questions.

- Should I do anything now?
- Why is the bot saying BUY, HOLD, SELL, or WAIT?
- What happened to my paper money?

Expected sections:

- Simple status banner: Paper Mode, Safe Mode, Live Off.
- One command card: BUY, HOLD, SELL REVIEW, or DO NOTHING.
- Plain-language reason list.
- Paper portfolio summary: cash, equity, open BTC, P/L.
- Paper transactions table.
- Big safe controls: Approve Paper Trade, Pause, Emergency Stop.
- Beginner glossary for visible terms.

Backend modules to run:

- Paper dashboard controller.
- Paper trading engine.
- Risk engine.
- Binance read-only market data adapter when configured.
- Paper account persistence.
- Simple paper command center/checklist.
- Basic strategy explanation.

Backend modules not needed by default:

- Full backtesting.
- Multi-symbol universe scans.
- Institutional investment reports.
- Advanced performance analytics.
- Strategy laboratory.

Beginner rule:

If the result is HOLD or not executable, the UI should say "Do nothing now" and
keep approval disabled.

## Advanced Trader View

Purpose: give experienced traders enough evidence to judge the system.

Expected sections:

- Candlestick chart with indicators.
- Buy/sell/hold markers.
- Stop loss, target, and risk/reward lines.
- TradingView-quality chart interactions: zoom, pan, crosshair, OHLC tooltip,
  timeframe switching, indicator toggles, and responsive resizing.
- Drawing tools for trader annotation: trendlines, horizontal levels, boxes,
  notes, Fibonacci retracement, and local-only saved drawings.
- Watchlist and multi-symbol switching for supported spot pairs.
- Order book and market-depth panel with best bid/ask, spread, depth, and
  liquidity imbalance.
- Order-flow panel with recent trades, buy/sell pressure, and optional
  liquidity heatmap when data is available.
- Full strategy state: signal, confidence, regime, data quality, risk decision.
- Trade ledger with entry, exit, fees, P/L, reason, signal version, and audit ref.
- Backtest panel with win rate, expectancy, drawdown, Sharpe, Sortino, profit
  factor, fees, slippage, and sample size.
- Paper performance panel: daily, weekly, monthly, long-term.
- Exit review panel: hold, tighten stop, partial profit, exit review.
- Position panel with open size, average entry, unrealized P/L, stop, target,
  close-paper-position review, and reduce-paper-position review.
- Paper order ticket for market, limit, stop, and OCO-style simulated orders.
  The ticket must remain paper-only and require risk approval before any
  simulated fill. The ticket must also show and enforce Binance-style paper
  symbol filters for tick size, step size, minimum quantity, and minimum
  notional before staging a simulated paper order.
- Open paper orders panel for unfilled simulated limit, stop, and OCO orders.
- Alert panel for price, indicator, risk, drawdown, data-quality, and
  recommendation changes.
- Risk and safety panel: drawdown, halts, data quality, exchange health.
- Export buttons for CSV and report downloads.
- Trade journal analytics with tags, notes, setup type, mistake review,
  screenshots/chart context, P/L by strategy, P/L by regime, and lessons.
- Trader feedback log for paper-mode reviewer corrections, severity, category,
  follow-up status, resolution notes, and resolved timestamps.

Backend modules to run:

- Paper trading engine and API.
- Risk engine and portfolio manager.
- Binance read-only market data.
- Order-book and recent-trade market data adapters.
- Indicators and feature pipeline.
- Backtesting engine and reports.
- Performance analytics.
- Position exit optimizer.
- Exchange health and reconciliation reports.
- Confidence engine.
- Paper evaluation gate.
- Database repositories for paper ledger and audit evidence.
- Watchlist/universe manager.
- Notification and alert service.
- Trade-intelligence and learning reports.

Advanced rule:

The advanced view can show more evidence, but it still cannot bypass risk
approval or create live orders.

Advanced order-entry rule:

Market, limit, stop, and OCO controls in Advanced Trader view are simulated
paper-order controls only. They must never submit real orders. Any later live
order ticket must be introduced in a separate supervised-live stage with
explicit operator approval, preflight, exchange permissions, and risk approval.

## Strategy Lab View

Purpose: switch the UI and backend evidence based on strategy type.

Expected controls:

- Strategy selector.
- Symbol selector.
- Timeframe selector.
- Paper/backtest toggle.
- Parameter profile selector.
- Compare strategy runs.

Supported first strategy profile:

- MinRiskSpotStrategyV1

Future strategy profile examples:

- Trend-following spot strategy.
- Mean-reversion spot strategy.
- Breakout spot strategy.
- Defensive capital-preservation strategy.
- Multi-timeframe confirmation strategy.

Each strategy profile should define:

- Required market data.
- Required indicators.
- Required AI/context modules.
- Required risk checks.
- Required explanation fields.
- Required chart overlays.
- Required backtest metrics.
- Whether paper approval is allowed.

Strategy rule:

If a selected strategy cannot provide required evidence, the UI must mark the
recommendation as not actionable.

## Backend Module Routing

Create a module-routing layer for the dashboard.

Suggested contract:

- UI profile: beginner, advanced, strategy_lab.
- Strategy profile: selected strategy and timeframe.
- Evidence request: the set of modules required by the active view.
- Evidence response: normalized payload for the UI.

Example routing:

Beginner + MinRiskSpotStrategyV1:

- Run paper engine.
- Run risk engine.
- Run command checklist.
- Return simple recommendation, reasons, portfolio, transactions.

Advanced + MinRiskSpotStrategyV1:

- Run beginner modules.
- Add indicators, confidence engine, backtest summary, performance analytics,
  exit review, exchange health, and chart payload.

Strategy Lab + selected strategy:

- Load strategy profile.
- Run only modules declared by that strategy profile.
- Return strategy-specific dashboard sections.

## Persistence

Move paper dashboard state from JSON-only storage to SQLite-backed repositories.

Required records:

- Paper account snapshots.
- Paper transactions.
- Strategy evaluations.
- Risk decisions.
- Simulated fills.
- Operator approvals/rejections.
- View mode preference.
- Strategy profile selection.
- Open paper orders.
- Alert rules.
- Trade journal entries.
- Chart drawings.

JSON can remain as a fallback/export format, but it should not be the main
ledger for trader-facing use.

Status: implemented with SQLite-backed account snapshots, transactions,
strategy evaluations, risk decisions, simulated fills, operator actions,
preferences, open paper orders, alert rules, journal entries, and chart
drawings. The dashboard still keeps JSON snapshot restore/export compatibility
for local paper-mode recovery.

## Safety Rules

- UI mode must never enable live trading.
- Strategy selection must never bypass the Risk Management Engine.
- Every paper trade must be reconstructable from market data, features, signal,
  risk decision, simulated fill, account update, and operator action.
- Missing evidence must reduce confidence or block action.
- Beginner view must prefer "do nothing" wording when the bot is not actionable.
- Advanced view must show limitations and sample-size warnings.
- Strategy Lab must mark unvalidated strategies as research or paper-only.

## Implementation Stages

Status as of 2026-08-01: Stages A-F are implemented and covered by the full
repository verification gate. Live trading remains disabled.

### Stage A: Adaptive View Shell

- Add UI mode selector.
- Save selected UI mode locally.
- Split status payload into beginner, advanced, and strategy sections.
- Keep existing paper dashboard behavior intact.

### Stage B: Beginner View Completion

- Add plain-language command card.
- Add glossary panel.
- Clean transaction and portfolio display.
- Show "Do nothing now" for HOLD.

### Stage C: Advanced Trader View

Stage C should be split into smaller Advanced Trader milestones:

1. Chart upgrade:
   Add a real candlestick chart with zoom, pan, crosshair, OHLC tooltip,
   timeframe switching, indicator toggles, buy/sell/hold markers, stop-loss
   line, target line, and risk/reward line.

   Status: implemented with local-only drawing tools for horizontal levels,
   trendlines, boxes, notes, Fibonacci retracement, persistence, canvas
   rendering, and paper-safe dashboard routes.

2. Market microstructure:
   Add order book, market depth, spread, depth imbalance, recent trades, and
   optional order-flow/heatmap panel when supported by data.

   Status: implemented with order book/depth, recent public market trades,
   buy/sell pressure, liquidity heatmap rows, Binance read-only aggregate
   trades, deterministic demo fallback, and paper-safe UI rendering.

3. Trader controls:
   Add paper-only market, limit, stop, and OCO-style order ticket. Add open
   paper orders, simulated order cancel, and simulated order status. Keep real
   execution impossible.

   Status: implemented with paper-only ticket staging, open paper orders,
   cancel support, and Binance-style paper symbol-filter validation for tick
   size, step size, minimum quantity, and minimum notional.

4. Position management:
   Add open position panel, close-paper-position review, reduce-paper-position
   review, stop-loss status, target status, trailing-stop review, and exit
   optimizer output.

5. Watchlist and symbols:
   Add watchlist, symbol selector, multi-symbol paper state, and per-symbol
   market data health.

6. Alerts:
   Add local alerts for price, indicator, risk, drawdown, stale data,
   recommendation change, and paper-order events.

   Status: implemented for local dashboard alerts with price, indicator
   confidence, risk halt, drawdown, stale/degraded data, recommendation, and
   paper-order event triggers. Alerts remain local and paper-only.

6a. Risk and safety panel:
   Add a dedicated Advanced Trader panel for drawdown, halts, data quality,
   exchange/data health, unsupported markets, and paper ledger reconciliation.

   Status: implemented with risk checks, exchange/data health rows,
   reconciliation rows, unsupported-market safety status, and paper-only
   dashboard rendering.

7. Analytics and journal:
   Add backtest summary panel, performance panel, trade journal analytics,
   notes/tags, setup type, mistake review, P/L by strategy, P/L by regime, and
   CSV/report export buttons.

   Status: implemented for paper mode with local journal notes, tags, setup
   type, mistake review, lessons, chart context, P/L by strategy/regime
   summaries, persistence, and paper-safe dashboard routes.

### Stage D: Strategy Lab

- Add strategy profile registry.
- Add strategy selector.
- Add strategy-specific module routing.
- Add compare strategy run summaries.

Status: implemented for MinRiskSpotStrategyV1 with a strategy profile registry,
saved Strategy Lab selectors, paper-only module routing, required-evidence
matrix, parameter profile configuration, and compare-run metric rows. Missing
required evidence blocks actionability and live execution remains disabled.

### Stage E: Persistence Upgrade

- Move paper ledger and preferences into SQLite repositories.
- Add migration for paper dashboard state if needed.
- Keep import/export from JSON for compatibility.

Status: implemented with structured SQLite rows for paper open orders, alert
rules, journal entries, and chart drawings, in addition to the existing paper
ledger and full JSON snapshot compatibility.

### Stage F: Trader Readiness Gate

- Add dashboard readiness checklist.
- Verify every view has tests.
- Verify every backend route is paper-safe.
- Verify full reconstructability of paper trades.

Status: implemented with a dashboard readiness checklist, paper-safe backend
route inventory, paper-trade reconstructability checks, and a trader-facing
verdict that separates paper-demo readiness from live-capital readiness. The
paper report now exports proof points, blockers, warnings, and next steps.
Trader-review handoff, evidence JSON, and local structured feedback capture are
implemented for paper-mode reviewer workflows.

## Acceptance Criteria

- A beginner can use the dashboard without understanding trading jargon.
- An advanced trader can audit why the bot made a decision.
- A strategy researcher can switch strategies and see relevant evidence only.
- The UI mode changes backend evidence collection, but never changes safety
  permissions.
- All paper transactions are persisted and visible after restart.
- The dashboard still clearly says paper-only and not proven profitable.
