# Architecture

## Stage Scope

Stage 005 established the ABTP repository structure, shared vocabulary, coding
standards, documentation skeleton, and safety defaults. Stage 006 added typed
configuration profiles for research, backtest, paper, and live environments.
Stage 007 added core domain models and module interfaces. Stage 008 added local
SQLite migrations and repositories. Stage 009 adds exchange adapter contracts
and a deterministic sandbox connector. Stage 010 adds read-only historical
OHLCV collection. Stage 011 adds read-only live data ingestion and stream
health. Stage 012 adds data quality, normalization, and anomaly utilities. Stage
013 adds a Bitcoin and crypto dependency parameter registry. Stage 014 adds a
pure technical indicator engine over normalized candle data. Stage 015 adds a
versioned feature engineering pipeline for model-ready feature vectors. Stage
016 adds optional external context ingestion interfaces with deterministic
stubs. Stage 017 adds research/backtest AI dataset construction and a
conservative baseline prediction model. No current stage implements production
trading behavior. Stage 018 adds an advisory market regime classifier for trend,
range, high-volatility, shock, and unknown market states. Stage 019 adds a
stable prediction service and deterministic explainability layer around
research/backtest model outputs. Stage 020 adds a pluggable strategy framework
that emits non-executable domain signals only. Stage 021 adds the first
conservative BTC-only spot strategy plugin on top of that framework. Stage 022
adds the mandatory Risk Management Engine that returns explicit allow/reject
decisions before any future order creation. Stage 023 adds portfolio accounting,
exposure, drawdown, cash-reserve checks, and risk-context construction. Stage
024 adds paper-safe order execution for risk-approved order intents. Stage 025
adds deterministic historical backtesting with costs, risk checks, strategy
signals, portfolio state, and paper-safe execution. Stage 026 adds
risk-adjusted backtesting metrics, reports, and paper-trading eligibility gates.
Stage 027 adds live-like paper trading cycles with simulated fills, account
state, risk halts, and audit-oriented cycle records. Stage 028 adds read-only
paper API and dashboard contracts for status, signal/risk inspection,
blocked-trade reasons, parameter health, portfolio state, drawdown, pause, and
kill-switch controls. Stage 029 adds structured logging, deterministic metrics,
and append-only audit-trail helpers for decision reconstruction. Stage 030 adds
alert and notification contracts for risk halts, kill switches, outages, stale
data, drawdown, slippage, repeated losses, manual approvals, and blocked trades.
Stage 031 adds secret-redaction, least-privilege exchange-key validation,
authorization, audit-access, and dependency audit-note contracts. Stage 032 adds
a disabled-by-default supervised live gateway with manual approval, tiny
position preflight, and risk-approved order requirements. Stage 033 adds
limited automation evidence gates, pause/resume/kill-switch controls, and
circuit breakers. Stage 034 adds final integration documentation, operator and
deployment guidance, incident response, a production release checklist, and
end-to-end readiness smoke tests. Stage 035 adds deterministic self-learning
analysis over completed trades for advisory confidence calibration, strategy
ranking, regime performance, feature observations, and monthly reports. Stage
036 adds deterministic Multi-AI voting over independent model-family votes with
configurable majority/weighted consensus, disagreement detection, and
explainable vote logs. Stage 037 adds fail-safe market crash protection,
protective action recommendations, and recovery checks. Stage 038 adds an
advisory AI Strategy Optimiser that ranks strategies by risk-adjusted
performance, regime fit, stability, confidence, and risk-limit evidence. Stage
039 adds walk-forward validation, Stage 040 adds strategy laboratory utilities,
Stage 041 adds execution quality analysis, Stage 042 adds AI model management,
and Stage 043 adds deterministic model drift detection with advisory downgrade
and retraining recommendations. Stage 044 adds deterministic-seeded Monte Carlo
risk simulation for drawdown, tail-risk, position-risk, cost, and capital
survival stress evidence. Stage 045 adds deterministic exchange/database
reconciliation for balances, positions, orders, fills, outage state, and
restart recovery recommendations. Stage 046 adds advisory position-exit
optimization for dynamic stops, ATR trailing stops, partial profit, time,
regime, volatility, and exit-quality evidence. Stage 047 adds advisory portfolio
allocation optimization with cash-reserve, exposure, correlation, drawdown,
confidence, volatility, and Monte Carlo risk evidence. Stage 048 adds exchange
health scoring over latency, error rate, outage, stream heartbeat, spread,
liquidity, reconciliation, reliability, and permission-gating evidence. Stage
049 adds advisory weighted confidence scoring over trend, momentum, volatility,
volume, order-book, AI prediction, regime, sentiment, on-chain, portfolio, risk,
and data-quality evidence. Stage 050 adds read-only continuous performance
analytics for daily, weekly, monthly, long-term, strategy, regime, AI accuracy,
risk, drawdown, execution, and operator dashboard reporting. Stage 051 adds
advisory multi-timeframe intelligence over monthly, weekly, daily, four-hour,
and one-hour market evidence. Stage 052 adds advisory market-cycle intelligence
over BTC dominance, ETH dominance, altcoin-season, market-breadth, fear/greed,
and liquidity evidence. Stage 053 adds advisory on-chain intelligence over
MVRV, SOPR, NUPL, exchange flows, whale wallet activity, miner selling,
dormancy, coin days destroyed, realized price, hash rate, and network growth
evidence. Stage 054 adds advisory fundamental asset ratings over market cap,
liquidity, developer activity, GitHub quality, TVL, staking, tokenomics,
inflation, partnerships, institutional adoption, security, roadmap, community,
and governance evidence. Stage 055 adds advisory capital and sector rotation
assessment over BTC, ETH, large caps, mid caps, small caps, stablecoins, AI,
RWA, Layer 2, gaming, DeFi, infrastructure, privacy, DePIN, and meme flow
evidence. Stage 056 adds advisory macro and narrative intelligence over rates,
Fed, ECB, inflation, CPI, PPI, dollar index, bond yields, gold, oil, Nasdaq,
S&P 500, ETF flows, and crypto narrative evidence. Stage 057 adds advisory
opportunity discovery over supplied top-coin and dynamic-universe evidence,
including technical, AI, fundamental, on-chain, liquidity, risk,
relative-strength, momentum, market-cycle, and expected holding-period inputs.
Stage 058 adds advisory adaptive position management over dynamic stops, ATR
stops, trailing stops, partial profit, scaling, time exits, volatility exits,
regime exits, confidence exits, position aging, and holding recommendations.
Stage 059 adds advisory portfolio intelligence and hedging review over
allocation optimization, cash reserve, portfolio correlation, sector exposure,
asset exposure, maximum risk, diversification, stablecoin allocation, defensive
allocation, and rebalancing context. Stage 060 adds advisory AI Investment
Committee voting over trend, momentum, macro, risk, on-chain, fundamental,
liquidity, sentiment, portfolio, and execution AI votes. Stage 061 adds
advisory capital preservation over crash, exchange failure, liquidity crisis,
extreme volatility, whale dump, macro shock, ETF outflow, pause trading, reduce
allocation, increase cash, raise confidence thresholds, tighten stops,
kill-switch review, protection mode, emergency level, and recovery status.
Stage 062 adds advisory trade intelligence over completed trades, including
winners, losers, holding time, best regimes, best strategies, indicator
observations, AI accuracy, common mistakes, and improvement suggestions.
Stage 063 adds explainable advisory AI investment reports covering why buy, why
sell, why hold, market cycle, macro analysis, on-chain evidence, fundamentals,
AI votes, risk, expected return, expected holding, and portfolio impact.
Stage 064 adds advisory dynamic asset universes for research, paper, and live
profiles using supplied liquidity, market-cap, exchange-availability, security,
governance, validation, and data-quality evidence.
Stage 065 adds deterministic institutional risk stress testing for market
crashes, stablecoin de-pegs, exchange insolvency, flash crashes, liquidity
evaporation, regulatory shocks, network outages, portfolio survival score,
worst-case drawdown, recovery-time estimate, and risk recommendations.
Stage 066 adds advisory cross-asset correlation intelligence for BTC versus
ETH, crypto sectors, Nasdaq, gold, DXY, bond yields, correlation matrix,
diversification opportunities, and correlation risk alerts.
Stage 067 adds advisory institutional execution optimization for smart order
slicing, liquidity-aware execution, slippage prediction, spread optimization,
execution timing recommendations, expected cost, and slippage estimates.
Stage 068 adds governance and compliance reporting for strategy approvals,
model approvals, configuration versioning, manual override logging, audit-ready
compliance status, approval history, and policy violations.
Stage 069 adds a controlled AI research laboratory for model comparisons,
strategy comparisons, hyperparameter tests, regime-specific evaluations,
research reports, promotion recommendations, and experiment results.
Stage 070 adds institutional decision intelligence that combines multi-timeframe,
market-cycle, on-chain, fundamental, macro/narrative, AI committee, portfolio,
risk, opportunity, and confidence evidence into one explainable advisory
decision record.
Stage 071 adds a simple paper trading command center that turns decision,
paper-account, data-quality, exchange-health, confidence, risk, and protection
evidence into BUY REVIEW, HOLD, AVOID, or PROTECT CAPITAL labels.
Stage 072 adds a deterministic paper trading runner and session loop that runs
paper-only simulated cycles through command-center, strategy, risk, stop-loss,
paper execution, audit, metrics, and summary contracts.
Stage 073 adds a conservative paper trading evaluation gate that reviews paper
sessions, completed paper trades, drawdown, fees, blocked cycles, loss events,
stop-loss compliance, confidence calibration, governance, capital-preservation,
and audit evidence without enabling live trading.

## Source Document Assumptions

The available ABTP source documents define the platform goals as capital
preservation, modular architecture, AI-assisted decisions, multi-exchange
support, strong risk management, complete audit logs, and comprehensive testing
and documentation.

The high-level module map is:

- User Interface / Dashboard
- API Gateway
- Market Data Collector
- Database Layer
- Indicator Engine
- Feature Engineering Engine
- AI Prediction Engine
- Strategy Engine
- Risk Management Engine
- Portfolio Manager
- Order Execution Engine
- Backtesting Engine
- Paper Trading Engine
- Live Trading Engine
- Logging and Monitoring
- Notification Service

## Architectural Rules

- Keep modules loosely coupled and highly cohesive.
- Use environment-driven configuration.
- Keep exchange API calls inside exchange adapter modules only.
- Route every order intent through the Risk Management Engine before execution.
- Prefer spot trading first.
- Keep leverage, margin, futures, and options disabled until a later explicit
  stage enables them.
- Store enough inputs, signals, risk checks, and audit events to explain every
  decision.
- Use deterministic tests with fixtures and no real exchange credentials.

## Decision Flow

The intended decision path is:

```text
market data -> indicators/features -> signals -> strategy decision
  -> risk checks -> approved order intent -> execution adapter
  -> portfolio update -> audit events
```

No later implementation may add an order path that bypasses risk checks.

## Shared Vocabulary

- Asset: A tradeable symbol such as BTC or USDT.
- Exchange: A venue identifier such as coinbase or kraken.
- Candle: OHLCV market data over a fixed interval.
- Signal: A generated directional recommendation with inputs and rationale.
- Risk check: A single policy evaluation.
- Risk decision: The combined risk result for an order intent.
- Order intent: A proposed order before execution.
- Portfolio snapshot: Positions and cash balances at a point in time.
- Audit event: An immutable record of inputs, outputs, and decisions.

The core Python domain contracts live in `src/abtp/domain/`, protocol
interfaces live in `src/abtp/interfaces/`, runtime safety settings and profile
validation live in `src/abtp/config/`, repositories live in
`src/abtp/repositories/`, exchange adapter contracts live in
`src/abtp/exchanges/`, data collection utilities live in `src/abtp/data/`,
parameter definitions live in `src/abtp/parameters/`, and `src/abtp/contracts.py` preserves
backward-compatible Stage 005 imports.
Technical indicators live in `src/abtp/indicators/` and depend on domain/data
contracts only.
Feature engineering lives in `src/abtp/features/` and depends on domain,
data-quality, parameter, indicator, and repository contracts only.
External context ingestion lives in `src/abtp/context/` and depends on
data-quality and parameter contracts only.
AI research utilities live in `src/abtp/ai/` and depend on feature snapshots,
data-quality, domain prediction contracts, and optional context metadata only.
Stage 018 regime classification also lives in `src/abtp/ai/` and emits
explainable advisory risk context without creating signals, risk decisions,
order intents, exchange calls, or execution behavior.
Stage 019 prediction services live in `src/abtp/ai/` with a framework-neutral
facade in `src/abtp/api/`. They expose predictions and explanations without
strategy logic, risk approval, or execution authority.
Strategy plugins and the strategy engine live in `src/abtp/strategies/`. They
depend on feature, prediction, regime, and domain signal contracts only. They do
not create order intents, risk decisions, exchange calls, or execution behavior.
`min_risk_spot_v1` is long-only and emits HOLD unless conservative BTC setup
checks pass.
Risk checks live in `src/abtp/risk/` and consume strategy evaluations plus
portfolio/risk context. They produce domain `RiskDecision` objects and never
create order intents or exchange calls.
Portfolio state lives in `src/abtp/portfolio/` and converts local balances,
positions, prices, equity history, and open-order reservations into consistent
`PortfolioSnapshot` and `RiskPortfolioContext` values.
Paper-safe execution lives in `src/abtp/execution/` and depends on domain order
intents, risk approvals, repositories, and exchange adapter contracts. Live
routes are rejected until a later explicit live gateway stage.
Backtesting lives in `src/abtp/backtesting/` and reuses strategy, risk,
portfolio, and execution contracts without exchange or external-provider calls.
Backtesting reports in the same package consume `BacktestResult` values and
produce paper-trading eligibility checks without creating signals, risk
decisions, order intents, or execution behavior.
Paper trading lives in `src/abtp/paper/` and reuses strategy, risk, portfolio,
and paper-safe execution contracts. It consumes live-like data snapshots but
does not call exchanges, infer live mode, or submit real orders.
Paper status APIs live in `src/abtp/api/`; dashboard view models live in
`src/abtp/dashboard/`. They inspect paper state and expose safe controls without
placing orders or coupling to exchange-specific APIs.
Observability lives in `src/abtp/observability/`, and audit helpers live in
`src/abtp/audit/`. They record logs, metric points, and audit events without
creating order intents, bypassing risk checks, or calling exchange APIs.
Notifications live in `src/abtp/notifications/`. They send deterministic alerts
through local channel contracts only and fail closed for critical live-mode risk
events when delivery fails.
Security contracts live in `src/abtp/security/`. They validate declared
exchange-key permissions, reject withdrawal-capable keys, represent encrypted
secret references, enforce local roles, and record dependency audit notes
without storing plaintext credentials or calling external scanners.
Supervised live gateway contracts live in `src/abtp/live/`. They call only the
exchange adapter interface and require explicit gateway flags, manual approval,
passing preflight, and an approved risk decision before adapter submission.
Automation contracts live in `src/abtp/automation/`. They decide whether
automation may be enabled and when it must stop; they do not submit orders or
call exchanges.
Final integration readiness lives in `docs/final_integration.md`,
`docs/user_guide.md`, `docs/deployment.md`, `docs/incident_response.md`, and
`docs/production_release_checklist.md`. End-to-end smoke tests live in
`tests/e2e/` and validate paper, API/dashboard, audit, security, deployment,
and restore behavior across module boundaries.
Self-learning lives in `src/abtp/learning/`. It consumes completed trade
records and emits advisory analysis and reports. It does not create signals,
risk decisions, order intents, exchange calls, or execution behavior, and it
cannot auto-apply strategy or risk-rule changes.
Multi-AI voting lives in `src/abtp/ai/vote_models.py`,
`src/abtp/ai/consensus.py`, and `src/abtp/ai/voting.py`. It consumes
deterministic model votes and emits advisory consensus context only. It does
not call external AI services, create strategy signals, create risk decisions,
create order intents, or execute orders.
Market crash protection lives in `src/abtp/protection/`. It consumes market
health, data quality, stream heartbeat, order-book metrics, API failure flags,
and pending-order counts. It emits detection decisions, protective action
recommendations, and recovery decisions. It does not call exchanges, cancel real
orders, create order intents, or execute trades.
Strategy optimisation lives in `src/abtp/optimizer/`. It consumes strategy
performance snapshots and market-regime context, then emits advisory scores,
rankings, recommendations, and audit payloads. It does not create signals, risk
decisions, order intents, exchange calls, or execution behavior.
Stage 039 adds walk-forward validation, Stage 040 adds strategy laboratory
utilities, Stage 041 adds execution quality analysis, Stage 042 adds AI model
management, and Stage 043 adds deterministic model drift detection with
advisory downgrade and retraining recommendations. Stage 044 adds Monte Carlo
risk simulation over supplied return, cost, and position-size assumptions. Stage
045 adds exchange reconciliation over supplied database and adapter snapshots.
Stage 046 adds position-exit recommendation utilities over stored position,
price, stop, indicator, regime, quality, and holding-time inputs. Stage 047
adds allocation and rebalance recommendation utilities over stored portfolio,
cash, exposure, target-weight, correlation, confidence, volatility, drawdown,
regime, and Monte Carlo evidence. Stage 048 adds exchange health scoring over
supplied reliability, heartbeat, order-book, and reconciliation evidence with
permission-gating recommendations. Stage 049 adds confidence aggregation over
component scores, weights, quality, rejection reasons, risk context, exchange
health, and audit evidence. Stage 050 adds continuous performance analytics
over stored performance observations, costs, risk breaches, predictions,
regimes, execution quality, dashboard metrics, and audit references. Stage 051
adds multi-timeframe alignment and timing context over supplied timeframe
observations. Stage 052 adds market-cycle phase, confidence, risk-level, and
allocation-context assessment over supplied cycle metrics. Stage 053 adds
on-chain state, on-chain score, accumulation, distribution, confidence, and
quality assessment over supplied blockchain-activity metrics. Stage 054 adds
fundamental rating, long-term score, risk grade, confidence, and quality
assessment over supplied project-quality metrics. Stage 055 adds capital flow
map, rotation probability, sector strength, risk-off score, confidence, and
quality assessment over supplied flow metrics. Stage 056 adds macro risk score,
narrative strength, risk-on score, leading narrative, confidence, and quality
assessment over supplied macro and narrative metrics. Stage 057 adds ranked top
opportunities, watch list, avoid list, opportunity confidence, rejection
reasons, and quality assessment over supplied candidate metrics. Stage 058 adds
current risk, hold percentage, sell percentage, increase-review percentage,
exit-review percentage, stop price, reasons, evidence, and quality assessment
over supplied open-position metrics. Stage 059 adds portfolio health, hedge
recommendation, allocation plan, cash reserve target, stablecoin target,
exposure, correlation, diversification, reasons, evidence, and quality
assessment over supplied portfolio metrics. Stage 060 adds committee votes,
confidence, disagreement, recommendation, reasoning, rejection reasons, and
quality assessment over supplied AI committee votes. Stage 061 adds protection
mode, emergency level, recovery status, preservation score, target cash,
allocation reduction, confidence threshold, stop tightening, actions, reasons,
evidence, and quality assessment over supplied adverse-condition metrics.
Stage 062 adds holding-time insight, best regimes, best strategies, best
indicators, AI prediction-confidence accuracy, common mistakes, improvement
suggestions, evidence, and quality assessment over completed trade records.
Stage 063 adds report sections, directional scorecard, why-buy, why-sell,
why-hold evidence, expected return, expected holding, portfolio-impact summary,
reasons, rejection reasons, rendered report text, and quality assessment over
supplied advisory investment evidence.
Stage 064 adds approved research, paper, and live universes, watchlists,
excluded assets with reasons, profile-specific approvals, scores, ranks,
quality flags, source references, and audit payloads over supplied asset
candidate evidence.
Stage 065 adds stress scenario definitions, per-scenario results, portfolio
survival score, worst-case drawdown, recovery-time estimate, advisory risk
recommendations, rejection reasons, quality flags, and audit payloads over
supplied portfolio exposure evidence.
Stage 066 adds return-series inputs, cross-asset classes, correlation matrix
entries, diversification opportunities, risk alerts, quality flags, source
references, and audit payloads over supplied cross-asset return evidence.
Stage 067 adds execution optimization inputs, policies, plan slices, timing
actions, expected cost, slippage estimate, spread estimate, market-impact
estimate, reasons, rejection reasons, quality flags, and audit payloads over
supplied order-book evidence.
Stage 068 adds approval records, configuration version records, manual override
logs, governance review inputs, compliance reports, policy violations, quality
flags, source references, and audit payloads over supplied governance evidence.
Walk-forward validation lives in `src/abtp/validation/`. It consumes ordered
timestamps, backtesting `PerformanceMetrics`, strategy parameters, regime
coverage, and data-quality status to produce advisory validation reports. It
does not create signals, risk decisions, order intents, exchange calls, or
execution behavior.
Strategy laboratory utilities live in `src/abtp/lab/`. They catalogue strategy
versions, generate bounded parameter candidates, and compare candidates against
benchmarks using existing performance and walk-forward evidence. They do not
create signals, risk decisions, order intents, exchange calls, execution
behavior, or live strategy changes.
Execution quality analysis lives in `src/abtp/execution/quality.py`,
`src/abtp/execution/latency.py`, and `src/abtp/execution/reports.py`. It
consumes stored execution results, fills, expected prices, timing records, fees,
and optional order-book metrics to produce read-only reports. It does not route,
submit, modify, or cancel orders.
AI model management lives in `src/abtp/ai/model_registry.py`,
`src/abtp/ai/model_selection.py`, and `src/abtp/ai/model_manager.py`. It tracks
model metadata, training history, evaluation snapshots, comparison results,
retirement state, and advisory active-model recommendations. It does not train
models, serve predictions, create signals, approve risk, create order intents,
call exchanges, or execute orders.
Model drift detection lives in `src/abtp/ai/drift.py`,
`src/abtp/ai/drift_rules.py`, and `src/abtp/ai/drift_reports.py`. It compares
stored baseline/current feature, prediction-outcome, confidence, label, and
quality windows. It emits advisory downgrade and retraining evidence only and
does not change model registry state, train models, create signals, approve
risk, create order intents, call exchanges, or execute orders.
Monte Carlo risk simulation lives in `src/abtp/risk/simulation.py`,
`src/abtp/risk/tail_risk.py`, and `src/abtp/risk/monte_carlo.py`. It consumes
deterministic return samples, fee/slippage bounds, position-size assumptions,
and risk limits to produce scenario paths, tail-risk summaries, survival
probability, risk-of-ruin, rejection reasons, and allocation-reduction evidence.
It does not create signals, approve risk, create order intents, call exchanges,
or execute orders.
Exchange reconciliation lives in `src/abtp/reconciliation/`. It consumes
non-secret database and adapter snapshots for balances, positions, orders,
fills, outage markers, stale adapter state, and restart markers. It emits
mismatch records and advisory recovery plans only. It does not call real
exchange APIs, store credentials, submit orders, cancel orders, approve risk, or
execute trades.
Position exit optimization lives in `src/abtp/risk/exits.py`,
`src/abtp/risk/trailing_stops.py`, and `src/abtp/risk/exit_quality.py`. It
consumes position cost basis, current price, stop inputs, ATR, regime labels,
quality status, and holding time to produce advisory hold, tighten-stop,
partial-profit, exit-review, and manual-review recommendations. It does not
create order intents, submit orders, cancel orders, approve risk, call
exchanges, or execute trades.
Portfolio allocation optimization lives in `src/abtp/portfolio/allocation.py`,
`src/abtp/portfolio/correlation.py`, and `src/abtp/portfolio/rebalancing.py`.
It consumes stored portfolio snapshots, target weights, cash reserves,
exposure, drawdown, correlation, confidence, volatility, regime, liquidity, and
Monte Carlo-style reduction evidence to produce advisory allocation and
rebalance recommendations. It does not create order intents, approve risk,
submit orders, call exchanges, or execute trades.
Exchange health scoring lives in `src/abtp/exchanges/health.py`,
`src/abtp/exchanges/reliability.py`, and
`src/abtp/exchanges/permission_gates.py`. It consumes supplied latency,
error-rate, outage, stream heartbeat, order-book spread/depth/imbalance, and
reconciliation evidence to produce health scores and permission-gating
recommendations. It does not call exchanges, create order intents, approve
risk, submit orders, cancel orders, or execute trades.
Confidence scoring lives in `src/abtp/confidence/`. It consumes normalized
component confidence from indicators, order book, predictions, regimes,
sentiment, on-chain context, portfolio, risk, exchange health, and data-quality
evidence. It produces weighted advisory confidence results with contribution
records, rejection reasons, quality status, source references, and audit
payloads. It does not create strategy signals, risk decisions, order intents,
exchange calls, or execution behavior.
Continuous performance analytics lives in `src/abtp/analytics/`. It consumes
supplied or stored performance observations, equity snapshots, trade counts,
fees, slippage, prediction outcomes, risk breaches, regimes, and execution
quality scores to produce window reports, comparison rows, trend reports, and
operator dashboard metric snapshots. It does not change strategies, approve
risk, create order intents, call exchanges, or execute trades.
Multi-timeframe intelligence lives in `src/abtp/intelligence/`. It consumes
supplied monthly, weekly, daily, four-hour, and one-hour observations covering
trend, momentum, volatility, volume, market structure, support/resistance,
liquidity, and data quality. It emits advisory alignment, timing, higher-bias,
risk-rule, and evidence records. It does not create strategy signals, approve
risk, create order intents, call exchanges, or execute trades.
Market-cycle intelligence also lives in `src/abtp/intelligence/`. It consumes
supplied BTC dominance, ETH dominance, altcoin-season, market-breadth,
fear/greed, liquidity, and quality evidence to classify cycle phase, confidence,
risk level, suggested allocation context, reasons, and audit evidence. It does
not create strategy signals, approve risk, create order intents, call exchanges,
or execute trades.
On-chain intelligence also lives in `src/abtp/intelligence/`. It consumes
supplied normalized MVRV, SOPR, NUPL, exchange-flow, whale-activity,
miner-selling, dormancy, coin-days-destroyed, realized-price, hash-rate, and
network-growth evidence. It emits advisory on-chain state, on-chain score,
accumulation score, distribution score, confidence, reasons, quality, and audit
evidence. It does not call blockchains, external providers, exchanges, create
strategy signals, approve risk, create order intents, or execute trades.
Fundamental asset rating also lives in `src/abtp/intelligence/`. It consumes
supplied normalized market-cap, liquidity, developer-activity, GitHub-quality,
TVL, staking, tokenomics, inflation-control, partnership,
institutional-adoption, security, roadmap, community, and governance evidence.
It emits advisory rating, long-term score, risk grade, confidence, reasons,
quality, and audit evidence. It does not call GitHub, blockchains, external
providers, exchanges, create strategy signals, approve risk, create order
intents, or execute trades.
Capital and sector rotation also lives in `src/abtp/intelligence/`. It consumes
supplied normalized inflow, outflow, momentum, liquidity, and relative-strength
evidence for BTC, ETH, large caps, mid caps, small caps, stablecoins, AI, RWA,
Layer 2, gaming, DeFi, infrastructure, privacy, DePIN, and meme sectors. It
emits advisory capital flow map, rotation probability, ranked sector strength,
risk-off score, confidence, reasons, quality, and audit evidence. It does not
call exchanges, external flow providers, create strategy signals, approve risk,
create order intents, or execute trades.
Macro and narrative intelligence also lives in `src/abtp/intelligence/`. It
consumes supplied normalized interest-rate, central-bank, inflation, CPI, PPI,
dollar-index, bond-yield, gold, oil, equity-index, ETF-flow, and crypto
narrative evidence. It emits advisory macro risk score, narrative strength,
risk-on score, leading narrative, confidence, reasons, quality, and audit
evidence. It does not call macro providers, news services, ETF providers,
exchanges, create strategy signals, approve risk, create order intents, or
execute trades.
Opportunity discovery also lives in `src/abtp/intelligence/`. It consumes a
supplied candidate universe with normalized technical, AI, fundamental,
on-chain, liquidity, risk, relative-strength, momentum, market-cycle, and
expected holding-period evidence. It emits advisory top opportunities, watch
list, avoid list, confidence, rejection reasons, quality, and audit evidence. It
does not scan exchanges, call external ranking providers, create strategy
signals, approve risk, create order intents, or execute trades.
Adaptive position management lives in `src/abtp/risk/adaptive_position.py`. It
builds on the existing advisory exit optimizer and consumes supplied confidence,
volatility, regime-risk, scaling, stop, ATR, trailing-stop, holding-age, and
source-quality evidence. It emits advisory current risk, hold percentage, sell
percentage, increase-review percentage, exit-review percentage, stop price,
reasons, quality, and audit evidence. It does not submit orders, cancel orders,
create order intents, approve risk, call exchanges, or execute trades.
Portfolio intelligence and hedging lives in `src/abtp/portfolio/intelligence.py`.
It builds on the existing advisory allocation optimizer and consumes supplied
cash reserve, asset exposure, sector exposure, correlation, asset risk,
diversification, defensive signal, confidence, and source-quality evidence. It
emits advisory portfolio health, hedge recommendation, allocation plan, cash
reserve target, stablecoin target, reasons, quality, and audit evidence. Hedge
recommendations mean cash, stablecoin, diversification, or exposure-review
context only. It does not create order intents, approve risk, call exchanges,
trade derivatives, or execute trades.
AI Investment Committee voting lives in `src/abtp/ai/investment_committee.py`.
It consumes supplied votes from trend, momentum, macro, risk, on-chain,
fundamental, liquidity, sentiment, portfolio, and execution AI committee seats.
It emits advisory recommendation, direction, confidence, disagreement, weighted
tally, reasoning, rejection reasons, quality, and audit evidence. It does not
serve models, call external AI providers, create strategy signals, approve
risk, create order intents, call exchanges, or execute trades.
Capital preservation lives in `src/abtp/protection/capital.py`. It consumes
supplied crash, exchange-failure, liquidity-crisis, extreme-volatility,
whale-dump, macro-shock, ETF-outflow, cash-reserve, confidence-threshold,
source-quality, and optional crash-protection evidence. It emits advisory
protection mode, emergency level, recovery status, target cash, allocation
reduction, raised confidence threshold, stop-tightening multiplier, actions,
reasons, quality, and audit evidence. It does not create order intents, approve
risk, submit orders, cancel orders, call exchanges, or execute trades.
Trade intelligence lives in `src/abtp/learning/trade_intelligence.py`. It
consumes completed `TradeLearningRecord` inputs and builds on the existing
self-learning analyzer. It emits advisory holding-time insight, best observed
regimes, best observed strategies, best indicator relationships, AI-confidence
accuracy, common mistakes, improvement suggestions, quality, source references,
and audit evidence. It does not train models, modify strategies, modify risk
rules, create signals, approve risk, create order intents, call exchanges, or
execute trades.
AI investment report generation lives in `src/abtp/ai/investment_report.py`.
It consumes supplied section evidence for buy, sell, hold, market cycle, macro,
on-chain, fundamentals, AI votes, risk, expected return, expected holding, and
portfolio impact. It emits an advisory institutional-style report, scorecard,
reasons, rejection reasons, quality, audit payload, and deterministic Markdown
rendering. It does not fetch data, serve models, create signals, approve risk,
create order intents, call providers, call exchanges, or execute trades.
Dynamic asset universe management lives in `src/abtp/universe/manager.py`. It
consumes supplied asset candidates with liquidity, market-cap,
exchange-availability, security, governance, validation, stale, source-reference,
and quality evidence. It emits advisory research, paper, and live candidate
universes, watchlists, excluded assets with reasons, candidate decisions,
quality, and audit evidence. It does not scan exchanges, fetch data, update live
permissions, create signals, approve risk, create order intents, call
providers, call exchanges, or execute trades.
Institutional risk stress testing lives in `src/abtp/risk/stress.py`. It
consumes supplied starting equity, cash, risk-asset exposure, stablecoin
exposure, exchange exposure, stale state, source references, and quality
evidence. It emits deterministic scenario results for market crashes,
stablecoin de-pegs, exchange insolvency, flash crashes, liquidity evaporation,
regulatory shocks, and network outages, plus portfolio survival score,
worst-case drawdown, recovery estimate, recommendations, rejection reasons,
quality, and audit evidence. It does not fetch data, create signals, approve
risk, create order intents, call providers, call exchanges, or execute trades.
Cross-asset correlation intelligence lives in
`src/abtp/intelligence/correlation.py`. It consumes supplied aligned return
series for BTC, ETH, crypto sectors, Nasdaq, gold, DXY, bond yields, and
optional additional assets. It emits an advisory correlation matrix,
diversification opportunities, high-correlation alerts, macro-risk linkage
alerts, quality, source references, and audit evidence. It does not fetch data,
create signals, approve risk, create order intents, call providers, call
exchanges, or execute trades.
Institutional execution optimization lives in `src/abtp/execution/optimizer.py`.
It consumes supplied symbol, side, quantity, reference price, order-book metrics,
volatility, urgency, stale state, source references, and quality evidence. It
emits advisory execution slices, timing action, expected cost, slippage estimate,
spread estimate, market-impact estimate, reasons, rejection reasons, quality,
and audit evidence. It does not create order intents, approve risk, route
orders, submit orders, call providers, call exchanges, or execute trades.
Governance and compliance reporting lives in `src/abtp/governance/compliance.py`.
It consumes supplied strategy approvals, model approvals, configuration version
records, manual override logs, active strategy/model/config identifiers, stale
or quality evidence, and source references. It emits advisory compliance status,
approval history, policy violations, quality, and audit evidence. It does not
create signals, approve risk, create order intents, modify configuration, call
providers, call exchanges, or execute trades.
AI research laboratory contracts live in `src/abtp/lab/research.py`. They
consume existing model comparison results, strategy benchmark results,
hyperparameter candidate metadata, regime labels, quality flags, and source
references. They emit advisory research reports, experiment results, promotion
recommendations, rejection reasons, quality, and audit evidence. They do not
train models, serve predictions, create signals, approve risk, create order
intents, mutate production state, call providers, call exchanges, or execute
trades.
Institutional decision intelligence lives in
`src/abtp/intelligence/decision_hub.py`. It consumes normalized evidence from
multi-timeframe intelligence, market cycle, on-chain analysis, fundamentals,
macro/narrative, AI committee, portfolio status, Risk Management Engine context,
opportunity scanner, and confidence engine. It emits an advisory final decision,
confidence score, suggested allocation context, holding period, entry/exit plan,
risk assessment, rejection reasons, quality flags, source references, and audit
payload. It does not create signals, approve risk, create order intents, mutate
state, call providers, call exchanges, or execute trades.
The simple paper command center lives in `src/abtp/paper/command_center.py` and
`src/abtp/paper/trade_checklist.py`, with render/API wrappers in
`src/abtp/dashboard/command_center.py` and `src/abtp/api/command_center.py`. It
consumes the Stage 070 decision record, paper status, data quality, exchange
health, optional capital-preservation evidence, loss state, stop-loss metadata,
and source references. It emits paper-only command labels, checklist results,
account summary, blocked reasons, quality flags, and audit payloads. It does
not create signals, approve risk, create order intents, submit orders, call
providers, call exchanges, change configuration, or enable live trading.
The paper trading runner lives in `src/abtp/paper/runner.py`,
`src/abtp/paper/cycle.py`, `src/abtp/paper/session.py`, and
`src/abtp/paper/summary.py`. It consumes paper market snapshots, Stage 071
command recommendations, stop-loss metadata, safety flags, existing paper
engine results, and optional metrics. It emits deterministic cycle results,
blocked reasons, audit payloads, local metrics, and session summaries. It does
not create live orders, approve risk, bypass risk, call exchanges, mutate live
accounts, or enable live trading.
The paper evaluation gate lives in `src/abtp/paper/evaluation.py`,
`src/abtp/paper/promotion_gate.py`, and `src/abtp/paper/review_report.py`. It
consumes paper session summaries, completed paper fills, loss-event evidence,
confidence calibration, governance status, capital-preservation events, audit
references, and source quality. It emits deterministic metrics, rejection
reasons, a conservative promotion-gate recommendation, audit payloads, and a
beginner-readable review report. It cannot enable live trading, create live
orders, approve risk, apply strategy changes, call exchanges, or mutate
production configuration.

## Operating Limits

Live trading remains disabled by default in Stage 073. Automation cannot be
enabled until evidence gates pass and can be stopped instantly. Learning
recommendations require paper/backtest validation before adoption and cannot
self-modify trading rules. Voting consensus is advisory and fail-closed when
model agreement, confidence, or quality checks fail. Market crash protection
blocks new trades while protection mode is active and requires healthy recovery
checks before gradual resume. Optimiser recommendations are advisory, reject
poor-quality or under-sampled inputs, and require manual approval for live
strategy changes. Walk-forward validation rejects overfitted or fragile
strategies from promotion when out-of-sample, robustness, data-quality,
sample-size, or regime-coverage checks fail. Strategy laboratory
recommendations are advisory and cannot self-apply parameter or live strategy
changes. Execution quality reports are read-only and cannot submit, cancel, or
route orders. Model manager recommendations are metadata-only; stale, weak,
unapproved, retired, or poor-quality models fail closed, and live active-model
changes require explicit approval gates. Model drift detection fails safe:
severe drift, stale windows, rejected quality, or confidence degradation can
recommend downgrade/non-actionable status and retraining review, but it cannot
apply model changes. Monte Carlo risk simulation fails safe when survival,
drawdown, tail loss, or ruin limits are unsafe and can only recommend rejection
or reduced allocation. Exchange reconciliation fails safe when mismatches,
outages, stale adapter state, restart markers, or unresolved fills are present
and can only recommend pause, hold, manual review, refresh, or replay. Position
exit optimization remains advisory; unsafe quality, stop breaches, shock, high
volatility, or holding-time limits can only recommend exit review, stop
tightening, partial profit, manual review, or blocked holding. Portfolio
allocation optimization remains advisory; unsafe data, cash-reserve breaches,
drawdown, exposure, correlation, volatility, or low confidence can only block
expansion, reduce allocation, or recommend review. Exchange health scoring
fails safe when latency, error rate, outage, stale heartbeat, abnormal spread,
thin liquidity, or reconciliation state is unsafe and can only recommend
read-only, paper-only, block-new-entries, pause, or manual-review states.
Confidence scoring remains advisory; missing, stale, rejected, contradictory,
poor-quality, high-risk, poor exchange-health, or low-confidence evidence can
only reduce confidence or mark the score non-actionable. Continuous performance
analytics remains read-only; reports must include costs, fees, slippage,
drawdown, and risk breaches and cannot trigger strategy changes, risk approvals,
orders, or execution automatically. Multi-timeframe intelligence fails closed
when required timeframes are missing, stale, rejected, or contradictory and can
only mark alignment context non-actionable. Market-cycle intelligence fails
closed when cycle inputs are stale, rejected, or low-confidence, and suggested
allocation remains advisory context only. On-chain intelligence fails closed
when inputs are stale, rejected, or low-confidence; it can only mark optional
context non-actionable and cannot fetch data or trigger trading behavior. Stage
054 fundamental rating fails closed when inputs are stale, rejected,
low-confidence, critically weak in security, or critically weak in liquidity;
ratings remain advisory context only and cannot fetch provider data or trigger
trading behavior. Capital and sector rotation fails closed when required
buckets are missing, inputs are stale or rejected, confidence is low, or
risk-off capital flow is elevated; it remains advisory context only and cannot
fetch flow data or trigger trading behavior. Macro and narrative intelligence
fails closed when macro risk is elevated, narrative coverage is insufficient,
inputs are stale or rejected, or confidence is low; it remains advisory context
only and cannot fetch macro/news/ETF data or trigger trading behavior.
Opportunity discovery fails closed when universe coverage is insufficient,
inputs are stale or rejected, confidence is low, or no candidate clears
conservative top filters; rankings remain advisory context only and cannot scan
markets or trigger trading behavior. Adaptive position management fails closed
when source quality is rejected, stops are breached, current risk is high, or
exit review is required; percentages remain advisory context only and cannot
submit, cancel, or modify orders. Portfolio intelligence and hedging fails
closed when quality is rejected, cash reserve is breached, exposure or
correlation is excessive, asset risk is high, diversification is low, confidence
is low, or allocation review rejects expansion; hedge recommendations remain
advisory cash/stablecoin/diversification/exposure-review context only and
cannot create derivative or spot orders. AI Investment Committee voting fails
closed to no decision when required votes are missing, vote quality is rejected,
confidence is low, agreement is weak, or disagreement is excessive; committee
output remains advisory context only and cannot create signals, risk approvals,
order intents, or execution. Capital preservation fails closed when inputs are
stale or rejected, crash protection is active, preservation score is
emergency/critical, or kill-switch review is required; actions remain
advisory/manual-review context only and cannot create order intents, approve
risk, submit orders, cancel orders, or execute trades. Trade intelligence fails
closed when completed-trade evidence is missing, rejected, degraded, or below
minimum sample size; suggestions remain advisory validation requests only and
cannot auto-apply model, strategy, risk, allocation, or execution changes.
AI investment report generation fails closed to no decision when required
sections are missing, stale, rejected, degraded, below confidence thresholds, or
lacking expected return or expected holding context; report recommendations are
review labels only and cannot create signals, risk approvals, order intents, or
execution. Dynamic asset universe management fails closed when candidates are
missing, stale, rejected, below liquidity, below market-cap, below security,
below governance, unavailable on exchanges, unvalidated for live, or below
profile thresholds; approved universe output is advisory configuration context
only and cannot create signals, risk approvals, order intents, or execution.
Institutional stress testing fails closed when survival score, worst drawdown,
recovery time, stale inputs, or rejected quality violates policy thresholds;
recommendations remain advisory/manual-review context only and cannot create
signals, approve risk, create order intents, submit orders, or execute trades.
Cross-asset correlation intelligence fails closed when required tracked assets
are missing, inputs are stale or rejected, samples are insufficient, or quality
is rejected; diversification opportunities and correlation alerts remain
advisory context only and cannot create signals, risk approvals, order intents,
or execution. Institutional execution optimization fails closed when input
quality is rejected, inputs are stale, order-book depth is unavailable, spread
is unsafe, or expected cost exceeds policy; smart slices and timing actions
remain advisory context only and cannot create order intents, approve risk,
route orders, submit orders, or execute trades. Governance and compliance
reporting fails closed when strategy approvals, model approvals, configuration
versions, approved config changes, manual override logs, or trusted evidence are
missing; compliance status remains audit context only and cannot create signals,
approve risk, create order intents, modify configuration, or execute trades.
AI research laboratory experiments fail closed when candidate evidence is
missing, degraded, rejected, below threshold, or does not improve over the
production baseline; promotion recommendations remain advisory review context
only and cannot serve predictions, create signals, approve risk, create order
intents, modify model or strategy state, or execute trades. Institutional
decision intelligence fails closed when required evidence is missing, stale,
blocking, rejected, below confidence thresholds, above risk thresholds, or not
trusted; final decisions, allocations, and entry/exit plans remain advisory
review context only and cannot create signals, approve risk, create order
intents, submit orders, or execute trades. The paper command center fails closed
when decision support, data quality, exchange health, confidence, risk,
stop-loss metadata, paper cash, kill switch, loss halts, or capital-protection
evidence is missing or unsafe; BUY REVIEW remains paper-review context only and
cannot create signals, approve risk, create order intents, submit orders, call
exchanges, or enable live trading. The paper trading runner fails closed when
live mode, live credentials, unsafe mode, missing BUY REVIEW, missing stop-loss
metadata, stale data, kill switches, exchange-health blocks,
capital-protection blocks, or portfolio loss halts are present; it records
blocked paper cycles rather than creating executable actions. The paper
evaluation gate defaults to remain paper, rejects weak or incomplete evidence,
can recommend more conservative paper settings or pause for review, and treats
future tiny-live proposal eligibility only as later review evidence. Stage 073
is not approval for unsupervised live trading. Future automated submissions
must still pass supervised live gateway controls, preflight, and the Risk
Management Engine.
