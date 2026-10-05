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
- Read-only Binance ticker/watchlist refresh while the dashboard is running,
  with degraded status when refresh fails.
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

8. Runtime telemetry modules:
   Add a compact dashboard status layer backed by real backend fields only. If a
   value cannot be measured from the active exchange adapter, paper engine, alert
   state, package metadata, or account ledger, the field must be marked
   `not_available` or degraded rather than filled with a fake value.

   1. 24h price change percentage:
      Read from the exchange adapter's public 24h ticker when configured. Demo
      mode and insufficient backend evidence must return `not_available`.

   2. Trend strength percentage:
      Compute from real paper-engine feature/candle evidence, such as the
      current lookback return, and expose the calculation source.

   3. True exchange connection status:
      Report adapter connectivity separately from market data source and
      freshness. The UI must distinguish `connected`, `degraded`,
      `disconnected`, and `not_configured`.

   4. Notification count and bell state:
      Count triggered local dashboard alerts and safety notifications from the
      alert/risk state. The bell state must reflect actual notification count.

   5. Latency in milliseconds:
      Surface the latest stream/adapter latency from backend health evidence.

   6. App version from backend:
      Read the installed ABTP package version from backend package metadata.

   7. Portfolio mini sparklines:
      Use the paper account's recorded equity history, not random or cosmetic
      points.

   8. Today's P/L:
      Expose today's mark-to-market P/L as a separate daily metric computed from
      current paper-cycle/account evidence.

   9. Exact next check-in countdown:
      Return backend `server_time`, `next_check_at`, refresh interval, and
      seconds remaining so the browser can show a real countdown.

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

### Stage G: Reference UI Parity Shell

Use the supplied ABTP dashboard reference image as the visual target while
keeping all displayed values backed by real backend evidence. If an editable
design file is later provided, use it for spacing, typography, icons, and exact
component proportions. Until then, treat the image as a high-level layout guide,
not a source of fake data.

1. Brand and top header:
   Add backend app/brand metadata for the ABTP name, product label, package
   version, trading mode, active symbol, exchange/source, last updated time,
   and status fields. The header must render `not_configured`,
   `not_available`, or degraded states when the backend cannot verify a value.

2. Market status strip:
   Keep current price, 24h price change, trend strength, mode, true exchange
   connection, latency, notification bell count, next check countdown, and last
   updated backed by the runtime telemetry fields from Stage C.8.

3. Sidebar navigation:
   Add backend navigation metadata for Dashboard, Advanced Trader, Strategy
   Lab, Backtesting, Reports, Alerts, Logs, and Settings. Items that are not
   full standalone workspaces yet must be marked `coming_soon`, `embedded`, or
   `external_report` rather than pretending to be implemented pages.

4. Sidebar collapse:
   Persist the collapsed/expanded sidebar state as a UI shell preference. This
   preference must not change trading mode, risk status, or paper/live
   permissions.

5. Notification bell:
   Add backend notification read/unread state so the bell badge can distinguish
   total notification count from unread count. Marking notifications as read
   must be a local dashboard preference/action only.

6. Recent activity view:
   Add a backend activity read model with severity/status labels and a
   `View All` route for full logs. The compact dashboard timeline can show the
   latest items while the backend preserves the complete local paper audit log.

7. Portfolio cards:
   Render portfolio value, cash, BTC holdings, and today's P/L as separate
   metric cards using the real paper ledger and equity history sparkline. Do
   not generate cosmetic sparkline points.

8. Recommendation and why panels:
   Redesign the beginner/dashboard recommendation card into a large command
   state with confidence and a separate checklist of evidence/reasons. Each
   checklist row must come from strategy, risk, indicator, or market evidence.

9. Control action tiles:
   Restyle approve, reject, pause, and emergency stop as large action tiles
   while preserving existing paper-only route guards and approval blockers.

10. AI explanation and verification:
    Show model/source, verification status, and explanation confidence only
    when these values are present in the backend payload. Otherwise use
    `not_available`.

11. Footer status rail:
    Match the reference footer with paper mode, data health, latency, exchange
    connection, risk status, and version. The footer must reuse the same
    backend telemetry fields as the header.

12. Icon and visual system:
    Replace temporary text placeholders with a real icon system during the UI
    implementation pass. Icons are presentation only and must not imply
    backend capabilities that are not exposed by the route inventory.

Status: implemented as a reference-style paper dashboard shell with top status
rail, sidebar navigation, recommendation hero card, evidence checklist,
portfolio cards, action tiles, AI explanation card, recent activity timeline,
footer status rail, navigation metadata, sidebar preference persistence,
notification read state, and activity view-all routing. The UI still renders
`not_available`, degraded, or `not_configured` when backend evidence is absent.

## Acceptance Criteria

### September 10 Runtime And Strategy Audit

- Implemented local corrections for unattended Binance polling, closed-candle
  catch-up, fresh daily confirmation, indicator warmup without historical fills,
  persisted protective exits, adverse SELL costs, and fee-inclusive trade metrics.
- Normal operation defaults to Binance. No automatic demo fallback is allowed;
  synthetic observations are restricted to explicitly selected automated tests.
- Added a reproducible 90-day historical Binance evaluation and a separate
  current-data paper check. Strategy revisions reduced losses in that evaluation
  but have not established large or dependable profits.
- Server installation, authentication/certificate review, and a sustained forward
  trial remain pending. Existing run history must be preserved.
- Evidence and remaining rollout work:
  [September 10 audit](profitability_audit_2026_09_10.md).
- September 14 verification: 631 tests, lint, formatting, and type checks pass.
  Browser checks confirmed current Binance data, all four comparison accounts,
  measured latency, and corrected model/performance labels. Changes remain
  local; the deployed server still needs the rollout above.

### September 15 Live Readiness Review

Decision: **NO-GO for real-money trading**. Full review and evidence:
[live readiness review](live_readiness_review_2026_09_15.md).

- [ ] Build and qualify an authenticated Binance order/account connector;
  the current Binance adapter remains read-only.
- [ ] Implement the complete live SELL/close/protective-order lifecycle.
- [x] Enforce durable order deduplication and single-use approval tokens in the
  local gateway contract (October 5); exchange-side identity/recovery is pending.
- [x] Enforce market/account/risk freshness and approval start/expiry bounds in
  the local gateway contract (October 5); authenticated input collection is pending.
- [x] Correct promotion-gate entry fees and partial-exit trade counting (October 5).
- [ ] Integrate reconciliation, loss limits, and emergency controls with every
  connected submission path; test ambiguous timeouts and restart recovery.
- [ ] Verify server authentication, trusted TLS, least-privilege key restrictions,
  backup restoration, process supervision, and notifications.
- [ ] Deploy the corrected paper release and complete dated forward evidence;
  qualify exchange behavior with virtual funds before any live proposal.

Verification: 631 existing tests, lint, formatting, and typing pass. Additional
offline probes nevertheless reproduce four safety/metrics gaps documented in
the review. No real trading was enabled; this update adds review findings only.

September 30 recheck: NO-GO unchanged. The deployed service still reports
`live_capital_ready=false`; trusted TLS remains unresolved. All 631 existing
tests pass again, but fresh offline probes reproduce the same four defects.
At that recheck the checklist was still pending; evidence is appended to the
[live readiness review](live_readiness_review_2026_09_15.md).

### October 5 Local Safety Fixes

- Implemented a durable SQLite submission ledger, concurrency/restart duplicate
  protection, and a fail-closed block after ambiguous exchange outcomes.
- Added independent account timestamps, bounded data/risk/intent ages, an
  internal gateway clock, and a second validation immediately before submission.
- Enforced approval start time, exclusive expiry, and maximum policy lifetime.
- Reused fee-inclusive completed-position accounting in the promotion gate;
  invalid or unmatched fills cannot yield promotion eligibility.
- Verification: **689 tests passed**, including 58 added regression cases;
  lint, formatting, and type checks passed. Tests used isolated fake adapters
  and temporary ledgers, not exchange accounts or the user's paper history.
- These are local, uncommitted changes. No push, deployment, credentials,
  testnet order, or real-money action occurred. Runtime live support stays false.
- Decision remains **NO-GO**: authenticated connector/testnet qualification,
  live exits/protection, integrated reconciliation/halts, secure deployment,
  reviewed rollout, and corrected forward evidence remain pending.

### October 5 Testnet And HTTP Follow-Up

- Added a fixed-host, signed Binance Spot Testnet client and no-matched-order
  qualification command. Production execution stays disabled and disconnected.
- Authenticated account, order-query, and `order/test` checks passed against
  Binance Spot Testnet at 12:57 UTC. Zero matched trades were created. See
  [the qualification report](testnet_qualification_2026_10_05.md).
- Added offline tests for virtual order request construction, protective OCO
  requests, partial statuses, commission assets, clock correction, and read-only
  reconciliation. These are not completed exchange lifecycle qualification.
- Added persistent gateway halt checks and HTTP authentication/origin/size/Host
  checks, with loopback-only binding. Remote deployment requires a trusted HTTPS
  proxy and credentials; see [deployment guidance](deployment.md).
- Full test suite before final publication: 732 passed. Real-money readiness
  remains NO-GO. Matched testnet lifecycle tests, integrated production controls,
  secured deployment, and corrected forward performance evidence remain open.
- Credential files and the user's local portfolio state are excluded from the
  publication. No deployment or real-money action is part of the Git push.

### Original Acceptance Criteria

- A beginner can use the dashboard without understanding trading jargon.
- An advanced trader can audit why the bot made a decision.
- A strategy researcher can switch strategies and see relevant evidence only.
- The UI mode changes backend evidence collection, but never changes safety
  permissions.
- All paper transactions are persisted and visible after restart.
- The dashboard still clearly says paper-only and not proven profitable.
