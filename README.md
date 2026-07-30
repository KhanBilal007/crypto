# ABTP

ABTP is the AI Blockchain Trading Platform. This repository is currently at
Stage 073: Paper Trading Evaluation Gate.

The source documents describe a modular cryptocurrency trading platform with
backtesting, paper trading, live trading, strong risk management, auditability,
and maintainability. The current code creates the repository foundation, shared
vocabulary, typed configuration profiles, core domain models and interfaces,
local SQLite persistence, a deterministic sandbox exchange adapter, read-only
historical/live market data ingestion, data-quality checks, a dependency
parameter registry, a reusable technical indicator engine, and a versioned
feature engineering pipeline, plus optional external context ingestion
interfaces with deterministic stubs, and research/backtest AI dataset and
baseline prediction utilities, an advisory market regime classifier, and a
stable prediction service with deterministic explainability and audit hooks,
plus a pluggable strategy engine and a conservative BTC-only spot strategy that
emits non-executable signals only, and a mandatory fail-closed risk engine that
produces explicit allow/reject decisions before any future order creation, plus
a deterministic portfolio manager for balances, positions, exposure, P/L,
drawdown, cash reserve, and risk context, plus paper-safe execution routing for
risk-approved order intents, and deterministic historical backtesting with
fees, slippage, risk checks, and portfolio state, plus risk-adjusted
backtesting reports and paper-trading eligibility gates, and a live-like paper
trading engine with simulated fills, paper account state, risk halts, and audit
cycle records, plus dependency-free paper API and dashboard view contracts. It
also includes structured logging, deterministic local metrics, and append-only
audit-trail helpers for decision reconstruction, plus deterministic alert and
notification contracts for important safety states, plus secret redaction,
least-privilege exchange-key validation, role authorization, and dependency
audit-note contracts, plus a supervised live gateway contract with manual
approval and preflight gates, plus limited automation evidence gates and circuit
breaker contracts, plus final integration documentation, operator guidance,
deployment and incident-response checklists, and end-to-end readiness smoke
tests, plus deterministic self-learning analysis for completed trades,
confidence calibration, strategy/regime outcome summaries, advisory
recommendations, and monthly learning reports, plus a deterministic Multi-AI
Voting System that combines independent model-family votes into advisory
consensus context with explainable vote logs and rejection reasons, plus
fail-safe market crash protection that detects abnormal market conditions and
recommends pause, cancel-request, kill-switch, notification, and recovery
actions, plus an AI Strategy Optimiser that ranks strategies by performance,
regime suitability, stability, confidence, and risk limits, plus walk-forward
validation, strategy laboratory utilities, execution quality analysis, AI model
management, and deterministic model drift detection with downgrade/retraining
recommendations, plus deterministic-seeded Monte Carlo risk simulation for
drawdown, tail loss, cost, and capital-survival stress tests, plus deterministic
exchange/database reconciliation for balances, positions, orders, fills,
restart recovery, and API outage recovery recommendations, plus advisory
position-exit optimization for dynamic stops, ATR trailing stops, partial profit,
time exits, regime exits, volatility exits, and exit-quality evidence, plus
advisory portfolio allocation optimization with cash reserves, exposure limits,
correlation, drawdown, confidence, volatility, and Monte Carlo risk evidence,
plus deterministic exchange health scoring for latency, error rate, outage,
stream staleness, spread, liquidity, reconciliation, reliability, and permission
gate evidence, plus an advisory confidence scoring engine that aggregates
weighted trend, momentum, volatility, volume, order-book, AI prediction, market
regime, sentiment, on-chain, portfolio, risk, and data-quality context, plus
continuous performance analytics for daily, weekly, monthly, long-term,
strategy, regime, AI accuracy, risk, drawdown, execution, and operator dashboard
review, plus advisory multi-timeframe intelligence over monthly, weekly, daily,
four-hour, and one-hour market evidence, plus advisory market-cycle intelligence
for bull accumulation, bull expansion, euphoria, distribution, bear market,
capitulation, and recovery phases, plus advisory on-chain intelligence for
MVRV, SOPR, NUPL, exchange flows, whale activity, miner selling, dormancy, coin
days destroyed, realized price, hash rate, and network growth, plus advisory
fundamental asset ratings for market cap, liquidity, developer activity, GitHub
quality, TVL, staking, tokenomics, inflation, partnerships, institutional
adoption, security, roadmap, community, and governance, plus advisory capital
and sector rotation assessment for BTC, ETH, large caps, mid caps, small caps,
stablecoins, AI, RWA, Layer 2, gaming, DeFi, infrastructure, privacy, DePIN,
and meme sectors, plus advisory macro and narrative intelligence for rates,
central-bank pressure, inflation, dollar, yields, commodities, equities, ETF
flows, and crypto narrative themes, plus advisory opportunity discovery over a
supplied crypto universe using technical, AI, fundamental, on-chain, liquidity,
risk, relative-strength, momentum, market-cycle, and expected holding-period
evidence, plus advisory adaptive position management for dynamic stops, ATR
stops, trailing stops, partial profit, scaling review, time exits, volatility
exits, regime exits, confidence exits, position aging, and holding
recommendations, plus advisory portfolio intelligence and hedging review for
cash reserve, portfolio correlation, sector exposure, asset exposure, maximum
risk, diversification, stablecoin allocation, defensive allocation, and
rebalancing context, plus an advisory AI Investment Committee that combines
trend, momentum, macro, risk, on-chain, fundamental, liquidity, sentiment,
portfolio, and execution AI votes into confidence, disagreement,
recommendation, and reasoning, plus advisory capital preservation for crash,
exchange failure, liquidity crisis, extreme volatility, whale dump, macro
shock, ETF outflow, pause/reduce/cash/threshold/stop/kill-switch review,
protection mode, emergency level, and recovery status, plus advisory trade
intelligence over completed trades for winners, losers, holding time, best
regimes, best strategies, indicator observations, AI accuracy, common mistakes,
and improvement suggestions, plus explainable AI investment reports covering
why buy, why sell, why hold, market cycle, macro analysis, on-chain evidence,
fundamentals, AI votes, risk, expected return, expected holding, and portfolio
impact, plus a dynamic asset universe manager for research, paper, and live
candidate universes using supplied liquidity, market-cap, exchange
availability, security, governance, validation, and quality evidence, plus
institutional deterministic stress testing for crashes, stablecoin de-pegs,
exchange insolvency, flash crashes, liquidity evaporation, regulatory shocks,
network outages, survival score, worst drawdown, recovery estimate, and risk
recommendations, plus cross-asset correlation intelligence for BTC vs ETH,
crypto sectors, Nasdaq, gold, DXY, bond yields, correlation matrix,
diversification opportunities, and correlation risk alerts, plus advisory
institutional execution optimization for smart order slicing, liquidity-aware
execution, slippage prediction, spread optimization, timing recommendations,
execution plans, expected cost, and slippage estimates, plus governance and
compliance reporting for strategy approvals, model approvals, configuration
versioning, manual override logs, approval history, compliance status, and
policy violations, plus a paper-first command center that turns institutional
decision evidence, paper account state, data quality, exchange health,
confidence, risk, and protection context into simple BUY REVIEW, HOLD, AVOID,
or PROTECT CAPITAL labels, plus a deterministic paper trading runner that
processes paper-only simulated cycles and session summaries through command,
risk, stop-loss, audit, and metrics gates, plus a conservative paper evaluation
gate that reviews paper-session evidence and can only recommend remain paper,
more conservative settings, pause for review, or eligibility for a future
separate tiny-live proposal review. It does not implement real exchange API
calls, real external provider calls, external
notification providers, external AI services, automatic live strategy changes,
automatic strategy/risk rule modification, advanced ML infrastructure, real
order cancellation, automatic model switching, real retraining, or unsupervised
live trading.

## Safety Notice

Cryptocurrency trading is risky. ABTP does not guarantee profit. Only risk
capital should ever be used, and live execution remains disabled in this stage.
The default configuration uses `SAFE_MODE=true`, `ABTP_TRADING_MODE=paper`, and
`ABTP_ENABLE_LIVE_TRADING=false`.

Stage 073 Paper Trading Evaluation Gate remains evidence-only and cannot enable
live trading.
Automation is
disabled unless evidence gates pass and stops immediately on circuit-breaker
conditions. Future stages must keep every order
path behind the Risk Management Engine and must not place exchange API calls
outside exchange adapter modules.

## Repository Layout

```text
migrations/            SQLite schema migrations
docs/                  Architecture, configuration, module, DB, exchange, data notes
src/abtp/              Domain, config, DB, repos, exchanges, data, parameters, indicators, features, context, ai
tests/                 Deterministic tests and testing guidance
.env.example           Safe local configuration template
pyproject.toml         Python packaging and tool configuration
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Verification

Run the local quality gate:

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
```

These checks validate that the package imports, contracts remain deterministic,
formatting is stable, lint rules pass, and type checking succeeds.

## Configuration

Typed profile configuration is documented in
[`docs/configuration.md`](docs/configuration.md). The default profile is
`paper`, and `ABTP_TRADING_MODE=live` does not implicitly select the live
profile. Live configuration requires `ABTP_PROFILE=live`, explicit live flags,
manual confirmation, and separate live credential variables.

## Module Contracts

Core domain models and protocol interfaces are documented in
[`docs/module_contracts.md`](docs/module_contracts.md). These contracts let
future data, AI, strategy, risk, portfolio, and execution modules exchange typed
objects without direct database coupling or circular imports.

## Database

SQLite persistence and migrations are documented in
[`docs/database_design.md`](docs/database_design.md). The default database URL is
`sqlite:///./abtp.sqlite3`, and tests rebuild in-memory databases from
migrations.

## Exchange Adapters

Exchange adapter contracts and the deterministic sandbox connector are
documented in [`docs/exchange_adapter.md`](docs/exchange_adapter.md). The
sandbox adapter requires a risk-approved `OrderIntent` and rejects live mode,
live credentials, withdrawals, margin, leverage, futures, and options.

## Data Collection

Historical candle collection is documented in
[`docs/data_collection.md`](docs/data_collection.md). The collector is read-only,
uses exchange adapters only, stores candles through repositories, and supports
idempotent backfills with data-quality flags.

## Live Data

Live market data ingestion is documented in
[`docs/live_data.md`](docs/live_data.md). The stream emits health status,
staleness/degraded flags, order-book metrics, and normalized updates without
placing orders.

## Data Quality

Data quality and normalization are documented in
[`docs/data_quality.md`](docs/data_quality.md). The quality engine marks data as
trusted, degraded, or rejected and exposes flags future risk/strategy modules
can consume.

## Parameters

The Bitcoin and crypto dependency parameter catalog is documented in
[`docs/bitcoin_parameter_catalog.md`](docs/bitcoin_parameter_catalog.md). The
registry supports lookup by key, group, source, trust level, and live-decision
eligibility.

## Indicators

The technical indicator engine is documented in
[`docs/indicators.md`](docs/indicators.md). Indicators consume normalized
`Candle` objects and emit deterministic `IndicatorResult` values with metadata,
warmup handling, and source data-quality status. Indicators cannot create
signals, risk decisions, order intents, or exchange actions.

## Feature Engineering

The feature engineering pipeline is documented in
[`docs/feature_engineering.md`](docs/feature_engineering.md). It transforms
normalized candles, indicator results, order-book metrics, stream health,
parameter values, and optional portfolio context into versioned feature
snapshots with data-quality metadata and leakage checks.

## External Context

External context ingestion interfaces are documented in
[`docs/external_context.md`](docs/external_context.md). Stage 016 adds
provider-neutral contracts and deterministic stubs for derivatives, on-chain,
macro/calendar, and sentiment/news context. External context is optional,
lower-trust by default, and blocked from live eligibility unless a future stage
explicitly configures trusted sources.

## AI Research

AI dataset and baseline model design is documented in
[`docs/ai_design.md`](docs/ai_design.md). Stage 017 builds deterministic
research/backtest datasets from feature snapshots, generates future-window
labels, preserves time-ordered train/validation/test splits, calculates simple
metrics, and emits conservative probability/confidence predictions only.

## Market Regimes

Market regime classification is documented in
[`docs/market_regimes.md`](docs/market_regimes.md). Stage 018 classifies
feature snapshots as trend, range, high-volatility, shock, or unknown and emits
explainable advisory risk-adjustment context only. It cannot create signals,
risk decisions, order intents, exchange calls, or live execution.

## Prediction Service

Prediction service and explainability contracts are documented in
[`docs/prediction_service.md`](docs/prediction_service.md). Stage 019 exposes
model predictions through a stable service that records model version, feature
inputs, confidence, explanation, quality status, optional regime context,
optional prediction persistence, and optional audit events. Predictions remain
probability context only.

## Strategy Framework

The strategy framework is documented in
[`docs/strategy_framework.md`](docs/strategy_framework.md). Stage 020 registers,
enables/disables, and evaluates strategy plugins. Strategies emit domain
`Signal` objects and audit metadata only; they cannot create orders, risk
decisions, exchange calls, or live execution.

## Minimum-Risk Spot Strategy

The first concrete strategy is documented in
[`docs/strategies/min_risk_spot_v1.md`](docs/strategies/min_risk_spot_v1.md).
Stage 021 adds a BTC-only, long-only, no-averaging-down strategy that requires
trusted data, acceptable regime, trend/momentum/volume/spread confirmation,
ATR-based stop metadata, minimum reward-to-risk, and cooldown clearance after
losses. It emits `Signal` objects only.

## Risk Engine

The mandatory risk gate is documented in
[`docs/risk_engine.md`](docs/risk_engine.md). Stage 022 evaluates strategy
signals against stop-loss, confidence, data quality, drawdown, loss-limit,
spread, slippage, exposure, cash reserve, and kill-switch checks. It returns
domain `RiskDecision` objects only; order creation and execution remain absent.

## Portfolio Manager

Portfolio accounting and risk context are documented in
[`docs/portfolio_manager.md`](docs/portfolio_manager.md). Stage 023 builds
consistent `PortfolioSnapshot` and `RiskPortfolioContext` objects from local
balances, positions, deterministic prices, equity history, and open-order
reservations.

## Order Execution

Paper-safe order execution is documented in
[`docs/order_execution.md`](docs/order_execution.md). Stage 024 accepts only
risk-approved `OrderIntent` objects, supports idempotent paper/sandbox routing,
records lifecycle and audit events, and blocks live routes entirely.

## Backtesting

Historical simulation is documented in
[`docs/backtesting.md`](docs/backtesting.md). Stage 025 replays historical
candles through feature generation, regime classification, strategy evaluation,
risk checks, paper-safe execution, and broker accounting with explicit fees and
slippage.

## Performance Metrics

Backtesting reports are documented in
[`docs/performance_metrics.md`](docs/performance_metrics.md). Stage 026
calculates risk-adjusted metrics and applies acceptance gates so positive net
return alone cannot qualify a strategy for paper trading when drawdown,
tail-loss, costs, or sample-size checks fail.

## Paper Trading

Paper trading is documented in
[`docs/paper_trading.md`](docs/paper_trading.md). Stage 027 runs strategies
against live-like market snapshots with simulated fills, account state, risk
checks, data-health blocks, and paper performance records. It rejects direct
order submission and cannot route real orders.

## API and Dashboard

API and dashboard contracts are documented in
[`docs/api_design.md`](docs/api_design.md) and
[`docs/dashboard.md`](docs/dashboard.md). Stage 028 exposes paper status,
signals, risk decisions, blocked-trade reasons, parameter health, portfolio
state, drawdown, and safe controls through dependency-free contracts. The API
rejects order submission.

## Monitoring and Audit

Logging, metrics, and audit-trail helpers are documented in
[`docs/monitoring.md`](docs/monitoring.md). Stage 029 emits structured logs,
local metric points, and append-only audit events that preserve blocked-trade
and risk-rejection reasons without storing plaintext secrets.

## Notifications

Alerts and notification contracts are documented in
[`docs/notifications.md`](docs/notifications.md). Stage 030 adds deterministic
alert generation, in-memory channel delivery, throttling, and fail-closed
critical alert dispatch for future live-mode risk events. No external
notification providers are added.

## Security

Security hardening is documented in [`docs/security.md`](docs/security.md) and
[`docs/operations_security.md`](docs/operations_security.md). Stage 031 adds
secret redaction, encrypted-secret references, exchange scope validation,
role-based authorization, audit-access checks, and local dependency audit notes.
Withdrawal permissions are unsupported and rejected.

## Live Gateway

The supervised live gateway is documented in
[`docs/live_trading.md`](docs/live_trading.md). Stage 032 adds manual approval,
tiny-position preflight checks, and a disabled-by-default live gateway contract.
Tests use a fake live adapter only; no real exchange connector is added.

## Automation

Limited automation policy is documented in
[`docs/automation_policy.md`](docs/automation_policy.md). Stage 033 adds
evidence gates, pause/resume/kill-switch controls, and circuit breakers that
stop automation on loss, drawdown, stale data, outage, abnormal spread,
volatility shock, model error, risk error, or missing operator presence.

## Final Integration

Stage 034 readiness is documented in
[`docs/final_integration.md`](docs/final_integration.md),
[`docs/user_guide.md`](docs/user_guide.md), [`docs/deployment.md`](docs/deployment.md),
[`docs/incident_response.md`](docs/incident_response.md), and
[`docs/production_release_checklist.md`](docs/production_release_checklist.md).
It adds operator guidance, deployment and incident-response procedures, a
release checklist, and e2e smoke tests for paper, API/dashboard, audit,
security, deployment, and restore flows.

## Self-Learning

Self-learning is documented in [`docs/self_learning.md`](docs/self_learning.md).
Stage 035 analyzes completed trades, win/loss patterns, regime performance,
feature observations, strategy rankings, and confidence calibration. It emits
advisory recommendations only; it cannot modify trading rules, create signals,
create risk decisions, create order intents, or execute orders.

## Multi-AI Voting

Multi-AI voting is documented in
[`docs/multi_ai_voting.md`](docs/multi_ai_voting.md). Stage 036 combines Trend,
Momentum, Volatility, Order Book, On-chain, and Sentiment model-family votes
using configurable majority or weighted voting. The result is advisory strategy
context only and is non-actionable when agreement, confidence, or data-quality
requirements fail.

## Market Crash Protection

Market crash protection is documented in
[`docs/market_crash_protection.md`](docs/market_crash_protection.md). Stage 037
detects flash crashes, abnormal volatility, exchange outage, stale data, high
spread, liquidity collapse, API failure, and rejected data quality. Any active
condition blocks new trades and returns auditable protective action
recommendations without calling exchanges or canceling real orders.

## AI Strategy Optimiser

The AI Strategy Optimiser is documented in
[`docs/ai_strategy_optimizer.md`](docs/ai_strategy_optimizer.md). Stage 038
scores strategies using historical/recent performance, win rate, expectancy,
drawdown, Sharpe ratio, profit factor, regime suitability, stability, and
confidence. Recommendations are advisory only and cannot create signals, risk
decisions, order intents, execution, or live strategy changes without manual
approval.

## Walk-Forward Validation

Walk-forward validation is documented in
[`docs/walk_forward_validation.md`](docs/walk_forward_validation.md). Stage 039
creates deterministic rolling and expanding time-series validation windows,
aggregates out-of-sample performance, scores robustness, detects overfit
patterns, and rejects fragile strategies from promotion. Reports are advisory
evidence only and cannot create signals, risk decisions, order intents,
exchange calls, or execution behavior.

## Strategy Laboratory

The strategy laboratory is documented in
[`docs/strategy_laboratory.md`](docs/strategy_laboratory.md). Stage 040 adds a
catalogue for many strategy versions, deterministic parameter candidate
generation, benchmark comparison against baselines, and regime-specific
evaluation using existing performance and walk-forward validation evidence. It
is advisory only and cannot apply live strategy changes, create signals, create
risk decisions, create order intents, or execute orders.

## Execution Quality

Execution quality analysis is documented in
[`docs/execution_quality.md`](docs/execution_quality.md). Stage 041 measures
slippage, partial fills, fee impact, latency, execution efficiency, and
conservative market impact from stored execution records and order-book context.
Reports are read-only risk context and cannot submit, cancel, route, or modify
orders.

## AI Model Manager

AI model management is documented in
[`docs/model_manager.md`](docs/model_manager.md). Stage 042 tracks model
registry entries, training history, evaluation snapshots, metric comparisons,
retirement state, and advisory active-model recommendations. It is metadata-only
management and cannot train models, serve predictions, create signals, approve
risk, create order intents, execute orders, or apply live model swaps
automatically.

## Model Drift

Model drift detection is documented in
[`docs/model_drift.md`](docs/model_drift.md). Stage 043 compares baseline and
current feature distributions, prediction outcomes, confidence trends,
calibration error, label distributions, and data-quality status. It emits
explainable downgrade and retraining recommendations only and cannot train
models, swap active models, create signals, approve risk, create order intents,
execute orders, or change live behavior.

## Monte Carlo Risk

Monte Carlo risk simulation is documented in
[`docs/monte_carlo_risk.md`](docs/monte_carlo_risk.md). Stage 044 runs
deterministic-seeded capital-path stress tests from supplied return samples,
fee/slippage ranges, position-size assumptions, and risk limits. It emits
drawdown, tail-risk, survival-probability, risk-of-ruin, rejection, and
allocation-reduction evidence only. It cannot create signals, approve risk,
create order intents, execute orders, or change live behavior.

## Exchange Reconciliation

Exchange reconciliation is documented in
[`docs/exchange_reconciliation.md`](docs/exchange_reconciliation.md). Stage 045
compares supplied database and adapter snapshots for balances, positions,
orders, fills, outage state, stale adapter state, and restart markers. It emits
explainable mismatches and recovery recommendations only. It cannot call real
exchange APIs, store credentials, submit or cancel orders, approve risk, or
change live behavior.

## Position Exit Optimizer

Position exit optimization is documented in
[`docs/position_exit_optimizer.md`](docs/position_exit_optimizer.md). Stage 046
produces advisory stop, trailing-stop, partial-profit, time-exit, regime-exit,
volatility-exit, and exit-quality recommendations for open spot positions. It
cannot submit or cancel orders, approve risk, create order intents, call
exchanges, or change live behavior.

## Portfolio Allocation Optimizer

Portfolio allocation optimization is documented in
[`docs/portfolio_allocation_optimizer.md`](docs/portfolio_allocation_optimizer.md).
Stage 047 produces advisory allocation and rebalance recommendations that
preserve cash reserves, respect exposure limits, reduce correlated or volatile
expansion, and block unsafe allocation changes. It cannot create orders, approve
risk, submit orders, call exchanges, or change live behavior.

## Exchange Health

Exchange health scoring is documented in
[`docs/exchange_health_scoring.md`](docs/exchange_health_scoring.md). Stage 048
scores supplied latency, error-rate, outage, stream heartbeat, spread,
liquidity, imbalance, and reconciliation evidence. It emits permission-gating
recommendations only and cannot submit orders, approve risk, call exchanges, or
bypass the Risk Management Engine.

## Confidence Scoring

Confidence scoring is documented in
[`docs/confidence_scoring.md`](docs/confidence_scoring.md). Stage 049 aggregates
weighted confidence from trend, momentum, volatility, volume, order book, AI
prediction, market regime, sentiment, on-chain context, portfolio context, risk
context, and data quality. It emits advisory confidence context only and cannot
create signals, approve risk, create order intents, submit orders, or bypass the
Risk Management Engine.

## Continuous Performance Analytics

Continuous performance analytics is documented in
[`docs/continuous_performance_analytics.md`](docs/continuous_performance_analytics.md).
Stage 050 builds read-only daily, weekly, monthly, long-term, strategy, regime,
AI accuracy, risk, drawdown, execution, and operator dashboard analytics from
supplied evidence. It cannot change strategies, approve risk, create order
intents, submit orders, call exchanges, or enable live trading.

## Multi-Timeframe Intelligence

Multi-timeframe intelligence is documented in
[`docs/multi_timeframe_intelligence.md`](docs/multi_timeframe_intelligence.md).
Stage 051 evaluates monthly, weekly, daily, four-hour, and one-hour trend,
momentum, volatility, volume, market-structure, support/resistance, and
liquidity evidence. It emits advisory alignment and timing context only and
cannot create signals, approve risk, create order intents, submit orders, call
exchanges, or enable live trading.

## Market Cycle Intelligence

Market cycle intelligence is documented in
[`docs/market_cycle_intelligence.md`](docs/market_cycle_intelligence.md). Stage 052
classifies supplied BTC dominance, ETH dominance, altcoin-season, market-breadth,
fear/greed, and liquidity scores into advisory cycle phase, confidence, risk
level, and suggested allocation context. It cannot create signals, approve risk,
create order intents, submit orders, call exchanges, or enable live trading.

## On-Chain Intelligence

On-chain intelligence is documented in
[`docs/onchain_intelligence.md`](docs/onchain_intelligence.md). Stage 053
evaluates supplied MVRV, SOPR, NUPL, exchange inflow/outflow, whale wallet
activity, miner selling, dormancy, coin-days-destroyed, realized price, hash
rate, and network-growth scores. It emits advisory on-chain state, score,
accumulation, distribution, confidence, quality, and evidence context only and
cannot create signals, approve risk, create order intents, submit orders, call
blockchains, call external providers, call exchanges, or enable live trading.

## Fundamental Asset Rating

Fundamental asset rating is documented in
[`docs/fundamental_asset_rating.md`](docs/fundamental_asset_rating.md). Stage 054
evaluates supplied market cap, liquidity, developer activity, GitHub quality,
TVL, staking, tokenomics, inflation control, partnerships, institutional
adoption, security, roadmap, community, and governance scores. It emits advisory
rating, long-term score, risk grade, confidence, quality, and evidence context
only and cannot create signals, approve risk, create order intents, submit
orders, call GitHub, call blockchains, call external providers, call exchanges,
or enable live trading.

## Capital And Sector Rotation

Capital and sector rotation is documented in
[`docs/capital_sector_rotation.md`](docs/capital_sector_rotation.md). Stage 055
evaluates supplied flow, liquidity, momentum, and relative-strength evidence for
BTC, ETH, large caps, mid caps, small caps, stablecoins, AI, RWA, Layer 2,
gaming, DeFi, infrastructure, privacy, DePIN, and meme sectors. It emits an
advisory capital flow map, rotation probability, sector-strength rankings,
risk-off score, confidence, quality, and evidence context only and cannot create
signals, approve risk, create order intents, submit orders, call exchanges, call
external providers, or enable live trading.

## Macro And Narrative Intelligence

Macro and narrative intelligence is documented in
[`docs/macro_narrative_intelligence.md`](docs/macro_narrative_intelligence.md).
Stage 056 evaluates supplied interest-rate, Fed, ECB, inflation, CPI, PPI,
dollar-index, bond-yield, gold, oil, Nasdaq, S&P 500, ETF-flow, and crypto
narrative evidence. It emits advisory macro risk score, narrative strength,
risk-on score, leading narrative, confidence, quality, and evidence context
only and cannot create signals, approve risk, create order intents, submit
orders, call news services, call macro providers, call exchanges, or enable live
trading.

## Opportunity Discovery

Opportunity discovery is documented in
[`docs/opportunity_discovery.md`](docs/opportunity_discovery.md). Stage 057
ranks a supplied crypto universe using technical, AI, fundamental, on-chain,
liquidity, risk, relative-strength, momentum, market-cycle, and expected
holding-period evidence. It emits advisory top opportunities, watch list, avoid
list, confidence, quality, rejection reasons, and audit context only and cannot
create signals, approve risk, create order intents, submit orders, scan
exchanges, call external providers, or enable live trading.

## Adaptive Position Management

Adaptive position management is documented in
[`docs/adaptive_position_management.md`](docs/adaptive_position_management.md).
Stage 058 combines existing exit optimization with supplied confidence,
volatility, regime-risk, scaling, stop, ATR, trailing-stop, holding-age, and
source-quality evidence. It emits advisory current risk, hold percentage, sell
percentage, increase-review percentage, exit-review percentage, stop price,
quality, reasons, and audit context only and cannot create signals, approve
risk, create order intents, submit orders, cancel orders, call exchanges, or
enable live trading.

## Portfolio Intelligence And Hedging

Portfolio intelligence and hedging is documented in
[`docs/portfolio_intelligence_hedging.md`](docs/portfolio_intelligence_hedging.md).
Stage 059 builds on allocation optimization and reviews supplied cash reserve,
asset exposure, sector exposure, correlation, asset risk, diversification,
defensive signal, confidence, and quality evidence. It emits advisory portfolio
health, hedge recommendation, allocation plan, cash reserve, stablecoin target,
quality, reasons, and audit context only and cannot create order intents,
approve risk, submit orders, trade derivatives, call exchanges, or enable live
trading.

## AI Investment Committee

AI Investment Committee voting is documented in
[`docs/ai_investment_committee.md`](docs/ai_investment_committee.md). Stage 060
combines supplied trend, momentum, macro, risk, on-chain, fundamental,
liquidity, sentiment, portfolio, and execution AI votes into advisory
recommendation, direction, confidence, disagreement, reasoning, quality, and
audit context only. It cannot create signals, approve risk, create order
intents, submit orders, serve models, call external AI providers, call
exchanges, or enable live trading.

## Capital Preservation Framework

Capital preservation is documented in
[`docs/capital_preservation.md`](docs/capital_preservation.md). Stage 061
evaluates supplied crash, exchange-failure, liquidity-crisis,
extreme-volatility, whale-dump, macro-shock, ETF-outflow, cash-reserve,
confidence-threshold, and source-quality evidence. It emits advisory protection
mode, emergency level, recovery status, target cash, allocation reduction,
confidence threshold, stop tightening, actions, quality, reasons, and audit
context only and cannot create order intents, approve risk, submit orders,
cancel orders, call exchanges, or enable live trading.

## Trade Intelligence & Learning Engine

Trade intelligence is documented in
[`docs/trade_intelligence.md`](docs/trade_intelligence.md). Stage 062 extends
self-learning over completed trade records with holding-time review, best
observed regimes, best observed strategies, indicator observations, AI
confidence accuracy, common mistakes, and improvement suggestions. It emits
advisory reports and audit payloads only and cannot change strategies, modify
risk rules, create signals, approve risk, create order intents, submit orders,
call exchanges, or enable live trading.

## AI Investment Report Generator

AI investment reports are documented in
[`docs/ai_investment_reports.md`](docs/ai_investment_reports.md). Stage 063
generates structured, explainable institutional-style reports from supplied
advisory evidence for why buy, why sell, why hold, market cycle, macro,
on-chain, fundamentals, AI votes, risk, expected return, expected holding, and
portfolio impact. Reports are advisory review context only and cannot create
signals, approve risk, create order intents, submit orders, call providers, call
exchanges, or enable live trading.

## Dynamic Asset Universe Manager

Dynamic asset universes are documented in
[`docs/dynamic_asset_universe.md`](docs/dynamic_asset_universe.md). Stage 064
selects approved research, paper, and live candidate universes from supplied
asset evidence for liquidity, market cap, exchange availability, security,
governance, validation, and data quality. It emits approved universes,
watchlists, excluded assets with reasons, quality flags, and audit payloads
only and cannot scan markets, change live trading permissions, create signals,
approve risk, create order intents, submit orders, call providers, call
exchanges, or enable live trading.

## Institutional Risk Stress Testing

Institutional stress testing is documented in
[`docs/institutional_stress_testing.md`](docs/institutional_stress_testing.md).
Stage 065 applies deterministic crash, stablecoin de-peg, exchange insolvency,
flash-crash, liquidity-evaporation, regulatory-shock, and network-outage
scenarios to supplied portfolio exposure evidence. It emits portfolio survival
score, worst-case drawdown, recovery-time estimate, scenario results, rejection
reasons, risk recommendations, quality flags, and audit payloads only and cannot
create signals, approve risk, create order intents, submit orders, call
providers, call exchanges, or enable live trading.

## Cross-Asset Correlation Intelligence

Cross-asset correlation intelligence is documented in
[`docs/cross_asset_correlation.md`](docs/cross_asset_correlation.md). Stage 066
computes a correlation matrix from supplied return series for BTC, ETH, crypto
sectors, Nasdaq, gold, DXY, bond yields, and optional additional assets. It
emits diversification opportunities, correlation risk alerts, quality flags,
source references, and audit payloads only and cannot create signals, approve
risk, create order intents, submit orders, call providers, call exchanges, or
enable live trading.

## Institutional Execution Optimizer

Institutional execution optimization is documented in
[`docs/institutional_execution_optimizer.md`](docs/institutional_execution_optimizer.md).
Stage 067 plans smart slices, liquidity-aware timing, expected cost, slippage,
spread, and market-impact estimates from supplied order-book evidence. It emits
advisory execution plans, timing recommendations, rejection reasons, quality
flags, and audit payloads only and cannot create order intents, approve risk,
submit orders, call routers, call providers, call exchanges, or enable live
trading.

## Governance & Compliance Engine

Governance and compliance are documented in
[`docs/governance_compliance.md`](docs/governance_compliance.md). Stage 068
builds audit-ready compliance reports from supplied strategy approvals, model
approvals, configuration versions, and manual override logs. It emits compliance
status, approval history, policy violations, quality flags, and audit payloads
only and cannot create signals, approve risk, create order intents, submit
orders, change configuration, call providers, call exchanges, or enable live
trading.

## AI Research Laboratory

AI research laboratory contracts are documented in
[`docs/ai_research_laboratory.md`](docs/ai_research_laboratory.md). Stage 069
compares candidate models, strategies, hyperparameter tests, and regime-specific
evaluations against production baselines using existing deterministic evidence.
It emits research reports, promotion recommendations, experiment results,
quality flags, and audit payloads only and cannot serve predictions, create
signals, approve risk, create order intents, submit orders, mutate production
state, call providers, call exchanges, or enable live trading.

## Institutional Decision Intelligence Hub

Institutional decision intelligence is documented in
[`docs/institutional_decision_hub.md`](docs/institutional_decision_hub.md).
Stage 070 combines normalized evidence from multi-timeframe intelligence,
market cycle, on-chain analysis, fundamentals, macro/narrative, AI committee,
portfolio status, risk context, opportunity scanner, and confidence engine into
one explainable final decision record. It emits advisory decision, confidence,
allocation context, holding period, entry/exit plan, risk assessment, quality
flags, and audit payloads only and cannot create signals, approve risk, create
order intents, submit orders, execute trades, call providers, call exchanges, or
enable live trading.

## Simple Paper Trading Command Center

The paper command center is documented in
[`docs/simple_paper_command_center.md`](docs/simple_paper_command_center.md).
Stage 071 converts Stage 070 decision records and existing paper/risk/health
evidence into one operator-facing command payload. `BUY REVIEW` means eligible
for paper-trade review only; it is not live permission and is not sufficient for
future paper execution without strategy, risk, sizing, and stop-loss checks.
The command center cannot create signals, approve risk, create order intents,
submit orders, call providers, call exchanges, change configuration, or enable
live trading.

## Paper Trading Runner

The paper trading runner is documented in
[`docs/paper_trading_runner.md`](docs/paper_trading_runner.md). Stage 072 runs
deterministic paper-only cycles and sessions using the existing strategy, Risk
Management Engine, paper account, paper-safe execution, command-center, audit,
metrics, and summary contracts. It records executed, skipped, no-signal, and
risk-rejected cycles. It fails closed on live mode, live credentials, unsafe
mode, missing BUY REVIEW, missing stop loss, stale data, kill switches,
exchange-health blocks, capital-protection blocks, and portfolio loss halts.
It cannot create live orders, approve risk, bypass risk, call exchanges, change
configuration, or enable live trading.

## Paper Trading Evaluation Gate

The paper evaluation gate is documented in
[`docs/paper_evaluation_gate.md`](docs/paper_evaluation_gate.md). Stage 073
reviews paper sessions, completed paper trades, loss events, drawdown, fees,
blocked cycles, risk rejections, stop-loss compliance, confidence calibration,
capital-preservation events, governance status, and audit evidence. It emits
one conservative recommendation: `remain_paper`, `make_more_conservative`,
`pause_for_review`, or `eligible_for_future_tiny_live_proposal`. Future tiny
live eligibility is not live approval; it only permits a later explicit
supervised proposal review. The gate cannot create live orders, approve risk,
change strategies, change risk rules, call exchanges, mutate production
configuration, or enable live trading.

## Operating Limits

- Spot trading is the preferred first market type.
- Margin, leverage, futures, and options remain disabled unless a later explicit
  stage enables them.
- Unit tests must not require real exchange credentials or network access.
- Trading decisions must be explainable through stored inputs, generated
  signals, risk checks, order intents, and audit events.
- Unsupervised live execution is not approved by this stage.

