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
- Full strategy state: signal, confidence, regime, data quality, risk decision.
- Trade ledger with entry, exit, fees, P/L, reason, signal version, and audit ref.
- Backtest panel with win rate, expectancy, drawdown, Sharpe, Sortino, profit
  factor, fees, slippage, and sample size.
- Paper performance panel: daily, weekly, monthly, long-term.
- Exit review panel: hold, tighten stop, partial profit, exit review.
- Risk and safety panel: drawdown, halts, data quality, exchange health.
- Export buttons for CSV and report downloads.

Backend modules to run:

- Paper trading engine and API.
- Risk engine and portfolio manager.
- Binance read-only market data.
- Indicators and feature pipeline.
- Backtesting engine and reports.
- Performance analytics.
- Position exit optimizer.
- Exchange health and reconciliation reports.
- Confidence engine.
- Paper evaluation gate.
- Database repositories for paper ledger and audit evidence.

Advanced rule:

The advanced view can show more evidence, but it still cannot bypass risk
approval or create live orders.

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

JSON can remain as a fallback/export format, but it should not be the main
ledger for trader-facing use.

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

- Add chart payload and browser chart.
- Add backtest summary panel.
- Add performance panel.
- Add exit review panel.
- Add CSV/report export buttons.

### Stage D: Strategy Lab

- Add strategy profile registry.
- Add strategy selector.
- Add strategy-specific module routing.
- Add compare strategy run summaries.

### Stage E: Persistence Upgrade

- Move paper ledger and preferences into SQLite repositories.
- Add migration for paper dashboard state if needed.
- Keep import/export from JSON for compatibility.

### Stage F: Trader Readiness Gate

- Add dashboard readiness checklist.
- Verify every view has tests.
- Verify every backend route is paper-safe.
- Verify full reconstructability of paper trades.

## Acceptance Criteria

- A beginner can use the dashboard without understanding trading jargon.
- An advanced trader can audit why the bot made a decision.
- A strategy researcher can switch strategies and see relevant evidence only.
- The UI mode changes backend evidence collection, but never changes safety
  permissions.
- All paper transactions are persisted and visible after restart.
- The dashboard still clearly says paper-only and not proven profitable.
