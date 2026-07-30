# ABTP Sequential Codex Execution Plan

Extracted from `abtp_execution_plan_artifacts/ABTP_Sequential_Codex_Execution_Plan.docx` so stage guidance is available inside the repository without relying on chat history.

ABTP Sequential Codex Execution Plan

AI Blockchain Trading Platform staged prompt book for minimum-risk automated crypto trading development

Version 1.0 | Prepared from ABTP source documents | 28 July 2026

Purpose

This document converts the ABTP vision, SRS, engineering package plan, system architecture, master index, and project summary into a sequential execution plan. Each stage is written as a complete Codex-executable prompt that can be copied into Codex and completed before the next stage begins.

The practical goal is to build an AI-assisted crypto trading platform that studies many Bitcoin and cryptocurrency dependency parameters, but the governing principle is minimum risk: the system must protect capital, reject unsafe trades, and prove behavior in backtesting and paper trading before any live automation.

Source Alignment

Master Index: project vision, capital preservation, modular architecture, AI-assisted decisions, multi-exchange support, testing and documentation.

SRS: backtesting, paper trading, live trading, configurable risk management, audit logs, dashboard/reporting, security, observability, and maintainability.

Engineering Package Plan: 30 detailed implementation prompts, module specifications, database/API/AI/risk/deployment/testing guides.

System Architecture: Dashboard, API Gateway, Data Collector, Database, Indicator Engine, Feature Engineering, AI Prediction, Strategy, Risk, Portfolio, Execution, Backtesting, Paper Trading, Live Trading, Monitoring, Notification.

Project Summary: phased delivery through Foundation, Data, AI/Intelligence, Trading, Risk, Backtesting, Paper Trading, Live Trading, and Deployment.

Financial and Safety Boundary

ABTP must be engineered as a decision-support and controlled automation system, not as a guaranteed-income machine. Automated systems and AI models cannot predict future market shocks with certainty. Crypto assets can be volatile, speculative, manipulated, technically disrupted, or affected by platform failures.

External risk references for operator awareness: CFTC AI trading bot advisory; CFTC virtual currency trading risks; SEC crypto asset investor alert.

Architecture Rules for Every Stage

Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.

Do not place exchange API calls outside exchange adapter modules.

Do not allow any order path to bypass the Risk Management Engine.

Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.

Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.

Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.

Bitcoin and Crypto Dependency Parameter Catalogue

No bot can study literally every factor in the world, so ABTP should instead implement an extensible parameter registry. The registry lets the platform add new data sources without rewriting strategies or risk controls.

Parameter Group

Examples to Support

Price action

OHLCV candles, returns, gaps, candle body/wick ratios, support/resistance, breakouts, reversals, market structure highs/lows.

Liquidity and microstructure

Bid-ask spread, order-book depth, imbalance, recent trade flow, estimated slippage, exchange fees, minimum order rules.

Trend and momentum

Moving averages, EMA/SMA crossovers, MACD, RSI, stochastic, ADX, rate of change, multi-timeframe confirmation.

Volatility

ATR, realized volatility, Bollinger Bands, volatility regime, abnormal candle range, volatility expansion/contraction.

Volume

Volume spikes, volume moving averages, VWAP, OBV, accumulation/distribution, buy/sell taker pressure where available.

Derivatives context

Funding rates, open interest, basis, long/short ratios, liquidation clusters; collect as optional signals, not required for spot-only MVP.

On-chain context

Transaction volume, active addresses, exchange inflow/outflow, miner behavior, fees, hash-rate/protocol health where reliable providers exist.

Cross-asset and market context

BTC dominance, ETH/BTC trend, total crypto market cap, stablecoin supply/flows, correlations among selected assets.

Macro and calendar context

Interest-rate events, inflation releases, liquidity proxies, major market holidays, high-impact scheduled announcements.

News and sentiment

Verified news events, social sentiment, fear/greed proxies, scam/manipulation warnings; treat as low-trust unless source confidence is high.

Exchange and infrastructure health

API latency, outage status, websocket disconnects, stale data, rejected orders, wallet/deposit/withdrawal warnings.

Portfolio state

Current exposure, unrealized P/L, drawdown, correlated positions, cash reserve, concentration, open orders, recent losses.

Data quality

Missing candles, duplicate records, timestamp drift, outliers, stale feeds, provider disagreement, schema version.

Minimum-Risk Control Policy

Default mode is research/backtest/paper; live trading remains locked until final stages and manual approval.

Default instrument scope is spot crypto only. No leverage by default.

Every trade requires a stop-loss, position-size calculation, reward-to-risk check, slippage estimate, fee estimate, and audit record.

Suggested initial defaults: max risk per trade 0.25 percent of trading capital, daily loss halt 1 percent, weekly loss halt 3 percent, max account drawdown halt 5 percent.

Reject trades during stale data, exchange outage, abnormal spread, excessive slippage, parameter disagreement, news shock, or risk-engine failure.

Require paper-trading evidence before live trading: at least 30 calendar days or 100 simulated trades, positive expectancy after fees, acceptable drawdown, and stable behavior across market regimes.

Sequential Stage Map

Stage

Phase

Codex Prompt

005

Foundation

Repository Foundation and Engineering Standards

006

Foundation

Configuration, Secrets, and Environment Profiles

007

Foundation

Core Domain Models and Module Interfaces

008

Foundation

Database Schema, Migrations, and Repositories

009

Data

Exchange Adapter Contracts and Sandbox Connector

010

Data

Historical Market Data Collector

011

Data

Live Market Data Stream

012

Data

Data Quality and Normalization Engine

013

Data

Bitcoin Dependency Parameter Registry

014

Intelligence

Technical Indicator Engine

015

Intelligence

Feature Engineering Pipeline

016

Intelligence

External Context Ingestion Interfaces

017

Intelligence

AI Dataset Builder and Baseline Model

018

Intelligence

Market Regime Classifier

019

Intelligence

Prediction Service and Explainability Layer

020

Trading

Strategy Engine Framework

021

Trading

Minimum-Risk Spot Strategy V1

022

Risk

Risk Management Engine

023

Risk

Portfolio and Position Manager

024

Trading

Order Execution Engine in Paper-Safe Mode

025

Validation

Backtesting Engine

026

Validation

Backtesting Reports and Performance Metrics

027

Validation

Paper Trading Engine

028

Validation

Paper Trading Dashboard and API

029

Production

Logging, Monitoring, and Audit Trail

030

Production

Alerts and Notification Service

031

Production

Security Hardening and Credential Protection

032

Production

Supervised Live Trading Gateway

033

Production

Limited Automation and Circuit Breakers

034

Production

Final Integration, Release Checklist, and User Guide

035

Intelligence

Self-Learning Module

036

Intelligence

Multi-AI Voting System

037

Production

Market Crash Protection

038

Intelligence

AI Strategy Optimiser

039

Validation

Walk-Forward Validation Engine

040

Trading

Strategy Laboratory

041

Validation

Execution Quality Analyzer

042

Intelligence

AI Model Manager

043

Intelligence

Model Drift Detection

044

Risk

Monte Carlo Risk Simulator

045

Production

Exchange Reconciliation Engine

046

Risk

Position Exit Optimizer

047

Risk

Portfolio Allocation Optimizer

048

Production

Exchange Health Scoring

049

Intelligence

Confidence Scoring Engine

050

Production

Continuous Performance Analytics

051

Intelligence

Multi-Timeframe Intelligence Engine

052

Intelligence

Market Cycle Intelligence Engine

053

Intelligence

On-Chain Intelligence Engine

054

Intelligence

Fundamental Asset Rating Engine

055

Intelligence

Capital & Sector Rotation Engine

056

Intelligence

Macro & Narrative Intelligence Engine

057

Intelligence

Opportunity Discovery Engine

058

Risk

Adaptive Position Management Engine

059

Risk

Portfolio Intelligence & Hedging Engine

060

Intelligence

AI Investment Committee

061

Risk

Capital Preservation Framework

062

Intelligence

Trade Intelligence & Learning Engine

063

Intelligence

AI Investment Report Generator

064

Production

Dynamic Asset Universe Manager

065

Risk

Institutional Risk Stress Testing

066

Intelligence

Cross-Asset Correlation Intelligence

067

Production

Institutional Execution Optimizer

068

Production

Governance & Compliance Engine

069

Intelligence

AI Research Laboratory

070

Intelligence

Institutional Decision Intelligence Hub

071

Paper Trading Usability

Simple Paper Trading Command Center

072

Paper Trading Execution

Paper Trading Runner and Simulation Loop

073

Paper Trading Evaluation

Paper Trading Evaluation Gate

How to Execute These Prompts

Run one stage at a time in Codex.

Do not start the next stage until the previous stage's tests and acceptance criteria pass.

If Codex discovers an existing codebase, it should adapt to the existing structure while preserving the architecture rules.

For every stage, require a completion summary that lists files changed, tests run, assumptions, and remaining risks.

Never enable live trading until the supervised live gateway and limited automation stages are completed and reviewed.

Codex-Executable Stage Prompts

Copy one full prompt at a time. Each prompt already includes objectives, prerequisites, files, architecture constraints, parameter focus, minimum-risk controls, tests, and acceptance criteria.


## Stage 005 - Repository Foundation and Engineering Standards

Phase: Foundation

You are Codex working in the ABTP repository. Implement Stage 005: Repository Foundation and Engineering Standards.Objective:Create the base ABTP repository structure, coding standards, development workflow, and project documentation skeleton.Prerequisites:ABTP source documents available; no existing production code required.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:README.md; pyproject.toml/package config; .env.example; docs/architecture.md; docs/codex_workflow.md; src/abtp/__init__.py; tests/README.md.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:No trading parameters yet. Define shared vocabulary for assets, exchanges, candles, signals, risks, orders, portfolios, and audit events.Minimum-risk controls:Live trading disabled by default; create SAFE_MODE=true configuration; document that no profit is guaranteed and only risk capital may be used.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Project import test, lint/type-check command, formatting check, CI smoke test.Acceptance criteria:A fresh clone can install dependencies, run tests, read documentation, and confirm live execution is impossible.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 006 - Configuration, Secrets, and Environment Profiles

Phase: Foundation

You are Codex working in the ABTP repository. Implement Stage 006: Configuration, Secrets, and Environment Profiles.Objective:Implement typed configuration for research, backtest, paper, and live profiles without exposing credentials.Prerequisites:Stage 005 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/config/settings.py; src/abtp/config/profiles.py; src/abtp/config/validation.py; .env.example; docs/configuration.md; tests/config/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Risk limits, exchange names, asset universe, candle intervals, data providers, fee assumptions, slippage ceilings, paper/live flags.Minimum-risk controls:Default profile must be paper or research. Live profile requires explicit environment variable, manual confirmation flag, and separate credentials.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Validation tests for missing secrets, unsafe live flags, invalid risk values, and profile precedence.Acceptance criteria:Unsafe configs fail fast with clear messages and no module can infer live mode implicitly.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 007 - Core Domain Models and Module Interfaces

Phase: Foundation

You are Codex working in the ABTP repository. Implement Stage 007: Core Domain Models and Module Interfaces.Objective:Define typed domain models and interfaces used across data, AI, strategy, risk, portfolio, and execution modules.Prerequisites:Stages 005-006 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/domain/models.py; src/abtp/domain/enums.py; src/abtp/interfaces/*.py; docs/module_contracts.md; tests/domain/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:AssetPair, Candle, OrderBookSnapshot, Trade, FeatureVector, Prediction, Signal, RiskDecision, OrderIntent, PortfolioSnapshot.Minimum-risk controls:RiskDecision must include allow/reject, reasons, max position size, stop-loss requirement, and kill-switch status.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Serialization, validation, enum, interface contract, and backward-compatible schema tests.Acceptance criteria:All future modules can exchange typed objects without circular imports or direct database coupling.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 008 - Database Schema, Migrations, and Repositories

Phase: Foundation

You are Codex working in the ABTP repository. Implement Stage 008: Database Schema, Migrations, and Repositories.Objective:Create persistent storage for market data, features, predictions, signals, risk decisions, orders, positions, and audit logs.Prerequisites:Stage 007 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:migrations/; src/abtp/db/session.py; src/abtp/db/models.py; src/abtp/repositories/*.py; docs/database_design.md; tests/db/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Candles, order books, indicator values, feature snapshots, data quality flags, model versions, trade lifecycle, P/L, risk limits.Minimum-risk controls:Audit tables must be append-only for trade decisions; live credentials must never be stored in database rows.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Migration up/down tests, repository CRUD tests, constraint tests, timestamp/order uniqueness tests.Acceptance criteria:Database can be recreated from migrations and every trading decision can be reconstructed from stored records.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 009 - Exchange Adapter Contracts and Sandbox Connector

Phase: Data

You are Codex working in the ABTP repository. Implement Stage 009: Exchange Adapter Contracts and Sandbox Connector.Objective:Create a unified exchange adapter layer and a sandbox/fake connector for tests before any real exchange integration.Prerequisites:Stages 006-008 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/exchanges/base.py; src/abtp/exchanges/sandbox.py; src/abtp/exchanges/errors.py; docs/exchange_adapter.md; tests/exchanges/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Symbols, tick sizes, lot sizes, fees, balances, order status, rate limits, latency, websocket state.Minimum-risk controls:Adapters cannot execute live orders unless mode=live and risk-approved OrderIntent is supplied.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Contract tests, fake order lifecycle tests, rate-limit behavior, rejected-order handling.Acceptance criteria:Data and execution modules can depend on adapter interfaces without knowing exchange-specific APIs.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 010 - Historical Market Data Collector

Phase: Data

You are Codex working in the ABTP repository. Implement Stage 010: Historical Market Data Collector.Objective:Collect and store historical OHLCV candles for Bitcoin and configured crypto assets.Prerequisites:Stage 009 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/data/historical_collector.py; src/abtp/data/scheduler.py; src/abtp/data/symbols.py; docs/data_collection.md; tests/data/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:OHLCV candles across 1m, 5m, 15m, 1h, 4h, 1d intervals; volume; missing candle status; provider timestamp.Minimum-risk controls:Collector is read-only; reject trading actions from data jobs; preserve raw provider payloads for audit where practical.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Backfill pagination, duplicate prevention, gap detection, timezone normalization, retry behavior.Acceptance criteria:BTC historical candles can be backfilled idempotently with data-quality flags.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 011 - Live Market Data Stream

Phase: Data

You are Codex working in the ABTP repository. Implement Stage 011: Live Market Data Stream.Objective:Implement live ticker, candle, trade, and order-book ingestion through exchange adapters.Prerequisites:Stage 010 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/data/live_stream.py; src/abtp/data/order_book.py; src/abtp/data/heartbeat.py; docs/live_data.md; tests/data_live/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Bid/ask, spread, depth, imbalance, recent trades, candle updates, stream latency, disconnect counts.Minimum-risk controls:Mark data stale after configurable threshold; downstream strategies must reject stale or degraded data.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Websocket reconnect simulation, stale heartbeat test, order-book snapshot/delta consistency.Acceptance criteria:Live feed updates normalized data objects and emits health status without placing orders.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 012 - Data Quality and Normalization Engine

Phase: Data

You are Codex working in the ABTP repository. Implement Stage 012: Data Quality and Normalization Engine.Objective:Build validation rules that detect missing, stale, duplicate, abnormal, or conflicting market data.Prerequisites:Stages 010-011 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/data/quality.py; src/abtp/data/normalization.py; src/abtp/data/anomaly.py; docs/data_quality.md; tests/data_quality/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Missing candles, duplicate timestamps, outlier returns, zero volume, timestamp drift, provider disagreement, abnormal spread.Minimum-risk controls:Risk engine must receive data-quality status and reject trades when quality is below threshold.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Fixture-based anomaly tests, malformed payload tests, degraded feed tests.Acceptance criteria:Every feature and signal can trace whether its source data was trusted, degraded, or rejected.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 013 - Bitcoin Dependency Parameter Registry

Phase: Data

You are Codex working in the ABTP repository. Implement Stage 013: Bitcoin Dependency Parameter Registry.Objective:Create an extensible registry of Bitcoin and crypto dependency parameters that future indicators, AI models, and strategies can consume.Prerequisites:Stage 012 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/parameters/registry.py; src/abtp/parameters/catalog.py; src/abtp/parameters/sources.py; docs/bitcoin_parameter_catalog.md; tests/parameters/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Register price action, liquidity, volatility, trend, volume, derivatives, on-chain, cross-asset, macro, news/sentiment, exchange health, portfolio, and data-quality parameters.Minimum-risk controls:Each parameter must define trust level, source, refresh interval, failure behavior, and whether it is allowed in live decisions.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Registry lookup, schema validation, missing-source handling, allowed/blocked live parameter tests.Acceptance criteria:New parameters can be added without changing strategy or risk engine internals.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 014 - Technical Indicator Engine

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 014: Technical Indicator Engine.Objective:Implement reusable technical indicators over normalized market data.Prerequisites:Stage 013 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/indicators/engine.py; src/abtp/indicators/trend.py; src/abtp/indicators/momentum.py; src/abtp/indicators/volatility.py; docs/indicators.md; tests/indicators/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:SMA, EMA, RSI, MACD, ATR, Bollinger Bands, VWAP, ADX, stochastic, OBV, support/resistance helpers.Minimum-risk controls:Indicators emit values only; no indicator can directly create an executable order.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Known-value indicator tests, warmup-window tests, NaN/missing-data tests.Acceptance criteria:Indicators are deterministic, versioned, and available for backtesting and live pipelines.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 015 - Feature Engineering Pipeline

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 015: Feature Engineering Pipeline.Objective:Transform raw data and indicators into model-ready feature vectors with versioned schemas.Prerequisites:Stage 014 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/features/pipeline.py; src/abtp/features/schema.py; src/abtp/features/store.py; docs/feature_engineering.md; tests/features/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Multi-timeframe returns, trend state, volatility regime, liquidity state, spread/slippage estimate, volume anomaly, portfolio context.Minimum-risk controls:Feature vectors must carry data-quality status and cannot be used for live signals if stale or untrusted.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Feature schema tests, leakage prevention tests, reproducibility tests, backfill/live parity tests.Acceptance criteria:The same feature definition works in historical backtests and live decision cycles.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 016 - External Context Ingestion Interfaces

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 016: External Context Ingestion Interfaces.Objective:Add optional ingestion interfaces for on-chain, macro, derivatives, and sentiment providers without hard-coding vendors.Prerequisites:Stage 015 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/context/base.py; src/abtp/context/onchain.py; src/abtp/context/macro.py; src/abtp/context/sentiment.py; docs/external_context.md; tests/context/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Funding rate, open interest, liquidations, active addresses, exchange flows, major calendar events, verified news/sentiment scores.Minimum-risk controls:External context is optional and low-trust by default; provider failure must degrade signals, not crash the platform.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Provider contract tests, missing-provider tests, stale-context tests, confidence scoring tests.Acceptance criteria:Strategies can use external context when available while remaining functional without it.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 017 - AI Dataset Builder and Baseline Model

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 017: AI Dataset Builder and Baseline Model.Objective:Build datasets and a conservative baseline prediction model for research and backtesting.Prerequisites:Stage 016 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/ai/datasets.py; src/abtp/ai/baseline.py; src/abtp/ai/metrics.py; docs/ai_design.md; tests/ai/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Feature vectors, labels for future return/volatility, market regime, fees/slippage assumptions, train/validation/test splits.Minimum-risk controls:Prevent look-ahead bias and data leakage; AI output is probability/confidence only, never a direct order.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Split integrity tests, label leakage tests, deterministic training smoke test, metric calculation tests.Acceptance criteria:A baseline model can train on historical data and produce auditable predictions with documented limitations.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 018 - Market Regime Classifier

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 018: Market Regime Classifier.Objective:Classify market conditions so strategies and risk controls can behave differently in trend, range, high-volatility, and shock regimes.Prerequisites:Stage 017 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/ai/regime.py; src/abtp/ai/regime_rules.py; docs/market_regimes.md; tests/ai_regime/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Trend strength, volatility percentile, volume anomaly, drawdown, correlation, spread, liquidity, sudden news/context flags.Minimum-risk controls:High-volatility or shock regime should automatically tighten size or block new entries.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Rule/classifier fixtures, boundary tests, regime transition tests.Acceptance criteria:Each decision cycle includes a regime label, confidence, and risk adjustment suggestion.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 019 - Prediction Service and Explainability Layer

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 019: Prediction Service and Explainability Layer.Objective:Expose AI predictions through a stable service that records model version, inputs, confidence, and explanation.Prerequisites:Stage 018 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/ai/prediction_service.py; src/abtp/ai/explainability.py; src/abtp/api/predictions.py; docs/prediction_service.md; tests/prediction_service/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Probability of upward/downward move, expected volatility, confidence, feature importance, regime, data-quality score.Minimum-risk controls:Predictions below confidence threshold or with degraded inputs must be marked non-actionable.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Service contract tests, versioning tests, low-confidence rejection tests, audit persistence tests.Acceptance criteria:Strategy modules can request predictions without knowing model internals.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 020 - Strategy Engine Framework

Phase: Trading

You are Codex working in the ABTP repository. Implement Stage 020: Strategy Engine Framework.Objective:Create a plug-in strategy framework that turns indicators and predictions into non-executable trade signals.Prerequisites:Stage 019 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/strategies/base.py; src/abtp/strategies/engine.py; src/abtp/strategies/rules.py; docs/strategy_framework.md; tests/strategies/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Signal direction, entry reason, stop suggestion, target suggestion, timeframe, confidence, regime, feature snapshot reference.Minimum-risk controls:Strategy output is Signal only. It cannot call exchange adapters or create orders directly.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Strategy contract tests, deterministic fixture tests, disabled-strategy tests, signal audit tests.Acceptance criteria:Multiple strategies can be registered, enabled/disabled, and evaluated consistently.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 021 - Minimum-Risk Spot Strategy V1

Phase: Trading

You are Codex working in the ABTP repository. Implement Stage 021: Minimum-Risk Spot Strategy V1.Objective:Implement the first conservative BTC spot strategy focused on capital preservation and clear exits.Prerequisites:Stage 020 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/strategies/min_risk_spot_v1.py; docs/strategies/min_risk_spot_v1.md; tests/strategies/test_min_risk_spot_v1.py.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Trend confirmation, RSI/momentum filter, ATR stop distance, volume confirmation, spread ceiling, regime filter, AI confidence as optional confirmation.Minimum-risk controls:Long-only spot, no leverage, no averaging down, required stop-loss, minimum reward-to-risk threshold, trade cooldown after losses.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:No-trade in bad regimes, signal in valid setup, stop/target generation, cooldown behavior.Acceptance criteria:Strategy produces explainable signals and rejects unclear conditions more often than it trades.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 022 - Risk Management Engine

Phase: Risk

You are Codex working in the ABTP repository. Implement Stage 022: Risk Management Engine.Objective:Implement the mandatory risk gate that approves, modifies, or rejects every signal before order creation.Prerequisites:Stage 021 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/risk/engine.py; src/abtp/risk/rules.py; src/abtp/risk/position_sizing.py; docs/risk_engine.md; tests/risk/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Capital, max risk per trade, stop distance, spread, slippage, fees, drawdown, daily/weekly P/L, open exposure, correlated positions, data quality.Minimum-risk controls:Default reject on missing stop, stale data, drawdown breach, daily loss breach, excessive spread/slippage, low confidence, or kill switch.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Reject/approve fixtures, position-size formula tests, circuit-breaker tests, audit-reason tests.Acceptance criteria:No signal can become an OrderIntent without a RiskDecision containing explicit allow/reject reasons.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 023 - Portfolio and Position Manager

Phase: Risk

You are Codex working in the ABTP repository. Implement Stage 023: Portfolio and Position Manager.Objective:Track balances, positions, exposure, P/L, drawdown, cash reserve, and portfolio constraints.Prerequisites:Stage 022 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/portfolio/manager.py; src/abtp/portfolio/accounting.py; src/abtp/portfolio/exposure.py; docs/portfolio_manager.md; tests/portfolio/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Balances, realized/unrealized P/L, exposure by asset, cash allocation, open orders, correlated exposure, drawdown.Minimum-risk controls:Maintain minimum cash reserve; block new positions when exposure or drawdown limits are breached.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:P/L calculations, drawdown tests, exposure aggregation, open-order reservation tests.Acceptance criteria:Risk engine can query a consistent PortfolioSnapshot before every decision.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 024 - Order Execution Engine in Paper-Safe Mode

Phase: Trading

You are Codex working in the ABTP repository. Implement Stage 024: Order Execution Engine in Paper-Safe Mode.Objective:Create an execution engine that converts risk-approved OrderIntent objects into simulated or adapter-routed orders.Prerequisites:Stage 023 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/execution/engine.py; src/abtp/execution/order_router.py; src/abtp/execution/fills.py; docs/order_execution.md; tests/execution/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Order type, limit/market choice, estimated slippage, fees, partial fills, retries, idempotency key, exchange status.Minimum-risk controls:Default route is sandbox/paper. Live route must be impossible until the live gateway stage.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Idempotent order submission, rejected order handling, partial fills, adapter failure, audit trail.Acceptance criteria:Only risk-approved orders are accepted and every order lifecycle event is recorded.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 025 - Backtesting Engine

Phase: Validation

You are Codex working in the ABTP repository. Implement Stage 025: Backtesting Engine.Objective:Build historical simulation for strategies using realistic fees, slippage, position sizing, and risk checks.Prerequisites:Stage 024 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/backtesting/engine.py; src/abtp/backtesting/broker.py; src/abtp/backtesting/slippage.py; docs/backtesting.md; tests/backtesting/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Historical candles, fees, spread/slippage model, risk rules, strategy signals, portfolio state, market regimes.Minimum-risk controls:Backtests must include costs and cannot report gross-only performance as success.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Known scenario tests, no-lookahead tests, fee/slippage tests, drawdown halt tests.Acceptance criteria:A strategy can be replayed across historical BTC data with auditable trades and risk decisions.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 026 - Backtesting Reports and Performance Metrics

Phase: Validation

You are Codex working in the ABTP repository. Implement Stage 026: Backtesting Reports and Performance Metrics.Objective:Generate reports that judge strategies by risk-adjusted quality, not only profit.Prerequisites:Stage 025 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/backtesting/reports.py; src/abtp/backtesting/metrics.py; docs/performance_metrics.md; tests/backtesting_reports/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Net return, max drawdown, profit factor, Sharpe/Sortino, win rate, expectancy, average win/loss, exposure time, regime performance.Minimum-risk controls:A strategy fails acceptance if drawdown or tail-loss rules fail, even if net return is positive.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Metric formula tests, report snapshot tests, acceptance gate tests.Acceptance criteria:Reports clearly show whether a strategy is eligible for paper trading and why.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 027 - Paper Trading Engine

Phase: Validation

You are Codex working in the ABTP repository. Implement Stage 027: Paper Trading Engine.Objective:Run strategies against live market data with simulated execution, realistic fees, and full auditability.Prerequisites:Stage 026 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/paper/engine.py; src/abtp/paper/account.py; src/abtp/paper/simulator.py; docs/paper_trading.md; tests/paper/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Live candles/order book, simulated balances, estimated fills, slippage, fees, latency, risk limits, trade outcomes.Minimum-risk controls:Paper engine must use the same strategy, risk, portfolio, and execution interfaces intended for live trading.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Simulated fill tests, live-data degradation tests, risk-halt tests, parity tests with execution contracts.Acceptance criteria:Paper trading can run unattended without real orders and produces live-like performance records.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 028 - Paper Trading Dashboard and API

Phase: Validation

You are Codex working in the ABTP repository. Implement Stage 028: Paper Trading Dashboard and API.Objective:Expose paper-trading state, signals, risk decisions, trades, P/L, and parameter health through API and dashboard.Prerequisites:Stage 027 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/api/*.py; src/abtp/dashboard/; docs/api_design.md; docs/dashboard.md; tests/api/; tests/dashboard/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Current BTC price, active regime, latest signals, blocked-trade reasons, data health, portfolio snapshot, drawdown.Minimum-risk controls:Dashboard is read-only for paper state except safe controls such as pause/resume and kill switch.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:API contract tests, dashboard render tests, kill-switch endpoint tests, authorization tests.Acceptance criteria:User can inspect why the bot did or did not trade during paper mode.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 029 - Logging, Monitoring, and Audit Trail

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 029: Logging, Monitoring, and Audit Trail.Objective:Create structured logs, metrics, traces, and immutable audit records for all platform decisions.Prerequisites:Stage 028 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/observability/logging.py; src/abtp/observability/metrics.py; src/abtp/audit/events.py; docs/monitoring.md; tests/observability/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Data latency, signal count, risk rejects, order status, error rate, P/L, drawdown, exchange health, model version.Minimum-risk controls:Audit must capture risk rejection reasons and never hide failed or blocked trade attempts.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Structured log tests, metric emission tests, audit persistence tests, sensitive-data redaction tests.Acceptance criteria:An operator can reconstruct every decision cycle from logs and audit tables.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 030 - Alerts and Notification Service

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 030: Alerts and Notification Service.Objective:Notify the user about important states, blocked trades, losses, outages, and manual approval requests.Prerequisites:Stage 029 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/notifications/service.py; src/abtp/notifications/channels.py; docs/notifications.md; tests/notifications/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Risk halt, kill switch, exchange outage, stale data, drawdown, large slippage, repeated losses, manual approval request.Minimum-risk controls:Critical alerts must be sent for live-mode risk events; alert failures must not permit trading.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Channel adapter tests, alert throttling tests, critical-failure tests.Acceptance criteria:The system clearly notifies the user when risk controls pause or block the bot.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 031 - Security Hardening and Credential Protection

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 031: Security Hardening and Credential Protection.Objective:Harden secrets, API permissions, authentication, authorization, dependency handling, and operational security.Prerequisites:Stage 030 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/security/*.py; docs/security.md; docs/operations_security.md; tests/security/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Exchange API scopes, IP restrictions, encrypted secrets, user roles, audit access, dependency vulnerabilities.Minimum-risk controls:Use least-privilege exchange keys; withdrawal permissions must be unsupported and rejected by validation.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Secret redaction tests, permission tests, unsafe-key detection, authz tests, dependency audit notes.Acceptance criteria:The system can run with trading-only keys and no withdrawal capability.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 032 - Supervised Live Trading Gateway

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 032: Supervised Live Trading Gateway.Objective:Add a tightly controlled live gateway that requires manual approval and tiny position limits.Prerequisites:Stages 027-031 complete plus documented paper-trading success.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/live/gateway.py; src/abtp/live/approval.py; src/abtp/live/preflight.py; docs/live_trading.md; tests/live/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Exchange balance, live fees, live spread, live slippage, approval token, order preview, current risk limits.Minimum-risk controls:Manual approval required; max risk per trade defaults to 0.25 percent; max one open live position until explicitly changed.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Approval required tests, preflight rejection tests, live-mode lock tests with fake adapter.Acceptance criteria:No live order can be sent without explicit approval, passing preflight, and passing risk engine.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 033 - Limited Automation and Circuit Breakers

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 033: Limited Automation and Circuit Breakers.Objective:Enable restricted automation only after evidence gates are met, with circuit breakers and immediate shutdown controls.Prerequisites:Stage 032 complete and manually reviewed small-live results.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:src/abtp/automation/controller.py; src/abtp/automation/circuit_breakers.py; docs/automation_policy.md; tests/automation/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Paper-trading eligibility, live P/L, drawdown, consecutive losses, volatility shock, exchange health, operator presence.Minimum-risk controls:Automation must stop on daily loss, weekly loss, max drawdown, stale data, exchange outage, abnormal spread, or model/risk error.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:Circuit-breaker tests, eligibility-gate tests, pause/resume tests, kill-switch tests.Acceptance criteria:Automation cannot be enabled until evidence gates pass and can be stopped instantly.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 034 - Final Integration, Release Checklist, and User Guide

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 034: Final Integration, Release Checklist, and User Guide.Objective:Perform end-to-end integration, documentation, deployment checklist, operator guide, and production readiness review.Prerequisites:Stages 005-033 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Preserve existing user work and follow existing project patterns where they exist.3. If files already exist, modify them carefully instead of replacing unrelated work.Files to create or modify:docs/final_integration.md; docs/user_guide.md; docs/deployment.md; docs/incident_response.md; docs/production_release_checklist.md; tests/e2e/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Complete lifecycle: data, features, prediction, strategy, risk, portfolio, execution, monitoring, alerts, dashboard.Minimum-risk controls:Production release requires all minimum-risk gates, kill switch, backup plan, incident response, and user acknowledgement.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts.3. Add documentation explaining assumptions, configuration, and operating limits.4. Ensure future stages can extend the module without tight coupling.Tests to add or run:End-to-end paper flow, risk rejection flow, dashboard/API flow, security smoke, deployment smoke, restore drill.Acceptance criteria:ABTP is documented, tested, auditable, and ready only for controlled, minimum-risk operation.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.

## Stage 035 - Self-Learning Module

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 035: Self-Learning Module.Objective:Analyse every completed trade to improve future confidence scoring without changing core risk rules.Prerequisites:Stages 005-034 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 035 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing trade, indicator, prediction, market-regime, risk-decision, paper/backtest, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/learning/analyzer.py; src/abtp/learning/calibration.py; src/abtp/learning/reports.py; docs/self_learning.md; tests/learning/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, generated signals, risk checks, audit events, trade outcomes, and learning recommendations.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:completed trades, trade outcomes, win/loss patterns, indicators, feature vectors, AI predictions, market regimes, risk decisions, strategy identity, confidence scores, regime-based performance, strategy ranking, monthly reports.Minimum-risk controls:Learning recommendations must never bypass the Risk Management Engine, must never self-modify strategy/risk/trading rules automatically, and must require paper/backtest validation before adoption.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for trade outcome analysis, pattern summaries, feature-importance observations, confidence calibration suggestions, strategy rankings, and learning reports.3. Add documentation explaining assumptions, configuration, operating limits, and how recommendations remain advisory.4. Ensure future stages can extend the module without tight coupling.5. Emit explainable confidence adjustments and recommendations only; do not create signals, risk decisions, order intents, exchange calls, or execution behavior.6. Preserve full auditability from stored trade inputs through generated recommendations.7. Do not implement automatic live-rule updates, online model retraining, real external provider calls, real exchange connectors, or live trading in this stage.Tests to add or run:Trade outcome analysis tests, win/loss pattern tests, confidence calibration tests, regime performance tests, strategy ranking tests, report/audit tests.Acceptance criteria:Self-learning analysis is deterministic, fully auditable, and produces explainable recommendations without modifying trading rules automatically.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 036 - Multi-AI Voting System

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 036: Multi-AI Voting System.Objective:Combine independent AI model opinions before generating actionable strategy context.Prerequisites:Stages 005-035 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 036 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing AI prediction, feature, external context, regime, strategy, risk, observability, and audit contracts.6. Use deterministic model stubs/fixtures; do not add real external AI services, exchange/API calls, or external provider calls.Files to create or modify:src/abtp/ai/voting.py; src/abtp/ai/vote_models.py; src/abtp/ai/consensus.py; docs/multi_ai_voting.md; tests/ai_voting/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every decision must be explainable through stored inputs, model votes, consensus rules, generated signals, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:Trend AI, Momentum AI, Volatility AI, Order Book AI, On-chain AI, Sentiment AI, model confidence, vote weights, minimum confidence threshold, disagreement detection, rejected reasons.Minimum-risk controls:No trade context may be considered actionable on insufficient agreement, low confidence, stale/rejected model inputs, or model disagreement above configured limits. Voting output is advisory/strategy context only and must not create orders, order intents, risk decisions, exchange calls, or execution behavior.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for model votes, voting policies, consensus results, disagreement summaries, and vote logs.3. Add documentation explaining assumptions, configuration, operating limits, and failure behavior.4. Ensure future stages can extend the module without tight coupling.5. Implement configurable majority and weighted voting with deterministic confidence aggregation and explicit rejection reasons.6. Include explainable vote logs linking each model input to the consensus result.7. Mark optional/low-trust model families as degraded unless deterministic source quality is available.8. Do not implement advanced model serving, real external AI calls, strategy order creation, risk decisions, order execution, real exchange connectors, or live trading in this stage.Tests to add or run:Consensus voting tests, weighted voting tests, minimum-confidence tests, disagreement rejection tests, explainable vote-log tests, public import tests.Acceptance criteria:Voting produces deterministic consensus scores, confidence, and rejected reasons with explainable vote logs.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 037 - Market Crash Protection

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 037: Market Crash Protection.Objective:Detect abnormal market conditions and immediately protect capital.Prerequisites:Stages 005-036 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 037 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing data quality, live stream heartbeat, exchange adapter contracts, risk engine, execution, automation, notification, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/protection/crash.py; src/abtp/protection/actions.py; src/abtp/protection/recovery.py; docs/market_crash_protection.md; tests/protection/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every protection decision must be explainable through stored inputs, health checks, detection reasons, protection actions, alerts, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:flash crashes, abnormal volatility, exchange outage, stale data, high spreads, liquidity collapse, API failures, pause state, pending-order cancellation requests, kill-switch state, notifications, recovery health checks.Minimum-risk controls:Default fail-safe behavior; no new trades during protection mode. Crash protection may request pause, cancellation, kill-switch, notification, and recovery workflows but must not create a new trade entry path or bypass risk controls.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for crash detection, protection decisions, protective actions, recovery checks, and audit evidence.3. Add documentation explaining assumptions, configuration, operating limits, manual approval options, and recovery flow.4. Ensure future stages can extend the module without tight coupling.5. Detect abnormal conditions including flash crash, abnormal volatility, exchange outage, stale data, high spread, liquidity collapse, and API failure from existing health/quality/market inputs.6. Implement protective action recommendations for pause trading, cancel pending orders, enable kill switch, notify operator, and wait for recovery.7. Implement recovery checks and gradual resume recommendations with optional manual approval.8. Do not implement real exchange cancellation calls, real order execution, real exchange connectors, strategy logic, AI training, or live trading in this stage.Tests to add or run:Simulated crash tests, stale/outage/high-spread/liquidity-collapse tests, protection action tests, audit-log tests, recovery workflow tests.Acceptance criteria:Crash protection fails safe, blocks new trades during protection mode, emits audit logs, and supports a deterministic recovery workflow.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 038 - AI Strategy Optimiser

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 038: AI Strategy Optimiser.Objective:Build an AI Strategy Optimiser that evaluates multiple trading strategies and recommends the most suitable strategy for the current market regime without bypassing the Risk Management Engine.Prerequisites:Stages 005-037 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 038 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing strategy, regime, feature, prediction, backtesting, paper trading, portfolio, risk, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls, real external provider calls, or heavyweight ML infrastructure.Files to create or modify:src/abtp/optimizer/engine.py; src/abtp/optimizer/scorer.py; src/abtp/optimizer/selector.py; docs/ai_strategy_optimizer.md; tests/optimizer/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every optimiser recommendation must be explainable through stored inputs, strategy metrics, regime evidence, risk limits, scoring components, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:market regime, feature vectors, AI predictions, backtest metrics, paper-trading metrics, live metrics if enabled, risk limits, win rate, expectancy, drawdown, Sharpe ratio, profit factor, regime suitability, stability, confidence.Minimum-risk controls:The optimiser never places orders directly. All signals continue through the Strategy Engine and Risk Management Engine. Underperforming strategies may be disabled automatically only in research/paper mode. Live strategy changes require manual approval. Optimisation must be rejected when data quality is poor or sample size is insufficient.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for strategy scores, scoring policies, ranked strategy lists, selected strategy recommendations, confidence scores, and optimisation reports.3. Add documentation explaining assumptions, configuration, operating limits, manual approval requirements, and failure behavior.4. Ensure future stages can extend the module without tight coupling.5. Score strategies using historical and recent performance, win rate, expectancy, drawdown, Sharpe ratio, profit factor, regime suitability, stability, and confidence.6. Produce ranked strategy lists and explainable selected-strategy recommendations.7. Include audit evidence for every recommendation and rejection.8. Do not implement order execution, direct strategy signal creation, risk decisions, real exchange connectors, real external provider calls, or unsupervised live strategy changes in this stage.Tests to add or run:Deterministic ranking tests, regime-switch tests, insufficient-data tests, audit-log tests, explainability tests, public import tests.Acceptance criteria:The optimiser consistently ranks strategies, produces explainable recommendations, and cannot bypass existing safety controls.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.

## Stage 039 - Walk-Forward Validation Engine

Phase: Validation

You are Codex working in the ABTP repository. Implement Stage 039: Walk-Forward Validation Engine.Objective:Build rolling-window validation, out-of-sample testing, time-series cross validation, strategy robustness scoring, and automatic rejection of overfitted strategies.Prerequisites:Stages 005-038 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 039 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing strategy, optimiser, backtesting, performance-metric, regime, risk, portfolio, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls, real external provider calls, or heavyweight ML infrastructure.Files to create or modify:src/abtp/validation/walk_forward.py; src/abtp/validation/splits.py; src/abtp/validation/robustness.py; docs/walk_forward_validation.md; tests/validation/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every validation result must be explainable through stored inputs, split definitions, strategy metrics, risk checks, rejection reasons, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:rolling train/test windows, out-of-sample returns, drawdown, Sharpe/Sortino, profit factor, expectancy, regime coverage, sample size, parameter stability, fee and slippage assumptions.Minimum-risk controls:Strategies that fail out-of-sample, robustness, drawdown, sample-size, leakage, or overfit checks must be rejected from promotion. Validation output is advisory/evidence only and must not create signals, risk decisions, order intents, exchange calls, or execution behavior.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for validation windows, split policies, walk-forward runs, robustness scores, rejection reasons, and validation reports.3. Add documentation explaining assumptions, configuration, operating limits, and overfit rejection behavior.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic rolling-window and expanding-window split utilities for time-series data.6. Implement out-of-sample evaluation aggregation and regime-aware robustness scoring.7. Detect suspiciously unstable parameters, inconsistent results, insufficient samples, and degraded data quality.8. Preserve full auditability from source backtest inputs through validation reports.9. Do not implement strategy signal generation, risk decisions, order intents, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Rolling-window split tests, out-of-sample aggregation tests, overfit rejection tests, regime robustness tests, leakage prevention tests, public import tests.Acceptance criteria:Strategies can be validated across deterministic walk-forward windows, and overfitted or fragile strategies are automatically rejected from promotion.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 040 - Strategy Laboratory

Phase: Trading

You are Codex working in the ABTP repository. Implement Stage 040: Strategy Laboratory.Objective:Create a framework for maintaining many strategies with strategy registration, benchmark comparison, parameter optimization, regime-specific strategy evaluation, and an extensible strategy catalogue.Prerequisites:Stages 005-039 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 040 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing strategy framework, optimiser, walk-forward validation, backtesting, regime, risk, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/lab/registry.py; src/abtp/lab/benchmarks.py; src/abtp/lab/parameters.py; docs/strategy_laboratory.md; tests/lab/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every laboratory recommendation must be explainable through stored strategy definitions, benchmark inputs, parameter ranges, validation results, risk constraints, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:strategy identity, version, parameter ranges, benchmark metrics, regime labels, validation scores, drawdown limits, expected fees, slippage assumptions, eligibility status, retirement status.Minimum-risk controls:The laboratory never creates executable orders. Parameter optimization must not bypass walk-forward validation, risk limits, or manual approval requirements. Live strategy changes remain blocked unless explicitly approved by live-stage controls.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for strategy catalogue entries, parameter spaces, benchmark reports, regime evaluations, and laboratory recommendations.3. Add documentation explaining assumptions, configuration, operating limits, and promotion requirements.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic strategy registration and lookup by key, family, regime suitability, status, and version.6. Implement benchmark comparison against baseline, disabled, and candidate strategies.7. Implement conservative parameter optimization utilities that generate candidate configurations without self-applying them to live strategies.8. Preserve full auditability for catalogue changes and recommendation reasons.9. Do not implement direct strategy signal generation, risk decisions, order intents, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Strategy registration tests, benchmark comparison tests, parameter search tests, regime evaluation tests, disabled-strategy tests, audit tests.Acceptance criteria:Many strategies can be catalogued, compared, and optimized deterministically without changing live behavior or bypassing safety gates.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 041 - Execution Quality Analyzer

Phase: Validation

You are Codex working in the ABTP repository. Implement Stage 041: Execution Quality Analyzer.Objective:Analyze slippage, partial fills, order latency, execution efficiency, fee impact, market impact estimation, and execution quality reporting.Prerequisites:Stages 005-040 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 041 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing order execution, exchange adapter, repository, portfolio, risk, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/execution/quality.py; src/abtp/execution/latency.py; src/abtp/execution/reports.py; docs/execution_quality.md; tests/execution_quality/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every execution-quality result must be explainable through stored order intents, risk decisions, fills, market snapshots, fees, latency observations, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:expected price, fill price, slippage, partial-fill ratio, order submit time, acknowledgement time, fill time, spread, depth, fees, estimated market impact, rejected/cancelled status.Minimum-risk controls:Execution analysis is reporting and risk-context only. Poor execution quality should degrade future eligibility or recommend tighter limits, but it must not place, modify, cancel, or route orders directly.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for execution observations, slippage records, latency records, fee impact, market impact estimates, quality scores, and reports.3. Add documentation explaining assumptions, configuration, operating limits, and how reports feed risk context.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic slippage, partial-fill, latency, fee-impact, and execution-efficiency calculations.6. Estimate market impact conservatively from stored order-book and fill context where available.7. Produce explainable execution-quality reports with warning and rejection reasons.8. Do not implement exchange calls, order routing, cancellation, strategy logic, risk decisions, real exchange connectors, or live trading in this stage.Tests to add or run:Slippage tests, partial-fill tests, latency tests, fee-impact tests, market-impact estimate tests, report/audit tests.Acceptance criteria:Execution quality can be measured from stored records and converted into explainable reports without creating any execution path.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 042 - AI Model Manager

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 042: AI Model Manager.Objective:Manage multiple models with registry entries, model versioning, training history, evaluation metrics, model comparison, model retirement, and active model selection.Prerequisites:Stages 005-041 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 042 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing AI dataset, baseline model, prediction, voting, validation, observability, and audit contracts.6. Use deterministic model metadata fixtures; do not add real external AI services, real provider calls, exchange/API calls, or heavyweight ML infrastructure.Files to create or modify:src/abtp/ai/model_registry.py; src/abtp/ai/model_manager.py; src/abtp/ai/model_selection.py; docs/model_manager.md; tests/ai_model_manager/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every model-management decision must be explainable through stored model metadata, training history, evaluation metrics, selection rules, retirement reasons, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:model name, model version, feature schema version, training window, label horizon, training metrics, validation metrics, calibration, active/retired status, limitations, approval status.Minimum-risk controls:Model selection is advisory to prediction/voting services and must not create signals, risk decisions, order intents, execution behavior, or live model swaps without explicit approval gates. Poor or stale models must be downgraded or retired fail-closed.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for model registry entries, training history, evaluation snapshots, comparison reports, retirement records, and active model recommendations.3. Add documentation explaining assumptions, configuration, operating limits, and approval requirements.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic model registration, lookup, version comparison, training-history recording, metric comparison, retirement marking, and active model selection.6. Preserve full auditability for every active model change recommendation.7. Never print, log, or store secrets in model metadata.8. Do not implement real model serving, advanced ML training, strategy signals, risk decisions, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Model registry tests, versioning tests, metric comparison tests, retirement tests, active-selection tests, public import tests.Acceptance criteria:Multiple model versions can be tracked, compared, retired, and selected deterministically without bypassing safety controls.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 043 - Model Drift Detection

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 043: Model Drift Detection.Objective:Detect concept drift, feature drift, data distribution drift, prediction quality degradation, confidence degradation, automatic model downgrade conditions, and retraining recommendations.Prerequisites:Stages 005-042 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 043 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing data-quality, feature, prediction, AI metrics, model-manager, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls, real external provider calls, or heavyweight ML infrastructure.Files to create or modify:src/abtp/ai/drift.py; src/abtp/ai/drift_rules.py; src/abtp/ai/drift_reports.py; docs/model_drift.md; tests/ai_drift/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every drift decision must be explainable through stored feature distributions, prediction outcomes, confidence trends, quality status, downgrade reasons, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:feature distribution windows, model prediction outcomes, confidence trend, calibration buckets, label drift, concept drift, data-quality status, market regime, retraining recommendation, downgrade eligibility.Minimum-risk controls:Drift detection must fail safe. Severe drift or confidence degradation must recommend model downgrade or non-actionable status, never increase trading permissions or bypass the Risk Management Engine.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for drift windows, drift measurements, degradation reasons, downgrade recommendations, and retraining reports.3. Add documentation explaining assumptions, configuration, operating limits, and downgrade behavior.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic feature-drift, distribution-drift, concept-drift proxy, prediction-quality degradation, and confidence-degradation checks.6. Produce retraining recommendations and active-model downgrade recommendations for the model manager.7. Preserve explainability by listing the inputs and thresholds that caused each drift status.8. Do not implement real retraining, strategy signals, risk decisions, order intents, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Feature-drift tests, concept-drift proxy tests, confidence degradation tests, downgrade recommendation tests, stale/poor-quality data tests, report tests.Acceptance criteria:Model drift can be detected deterministically and severe degradation produces explainable downgrade or retraining recommendations without changing live behavior directly.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 044 - Monte Carlo Risk Simulator

Phase: Risk

You are Codex working in the ABTP repository. Implement Stage 044: Monte Carlo Risk Simulator.Objective:Run thousands of deterministic-seeded randomized simulations for drawdown estimation, tail-risk analysis, position-risk simulation, fee/slippage randomization, and capital survival probability.Prerequisites:Stages 005-043 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 044 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing backtesting metrics, portfolio, risk, execution-quality, strategy-laboratory, observability, and audit contracts.6. Use deterministic seeds and fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/risk/monte_carlo.py; src/abtp/risk/simulation.py; src/abtp/risk/tail_risk.py; docs/monte_carlo_risk.md; tests/risk_monte_carlo/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every simulation result must be explainable through input distributions, deterministic seeds, fee/slippage assumptions, risk limits, scenario outcomes, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:return samples, volatility regime, position size, win/loss distribution, drawdown, tail loss, fee distribution, slippage distribution, capital path, survival probability, risk-of-ruin estimate.Minimum-risk controls:Monte Carlo output is risk evidence only. Unsafe survival probability, drawdown, or tail-risk results must recommend rejection or reduced allocation, but must not create orders, signals, risk approvals, or execution behavior.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for simulation assumptions, scenario paths, tail-risk summaries, capital survival reports, and rejection reasons.3. Add documentation explaining assumptions, configuration, operating limits, deterministic seeding, and limitations.4. Ensure future stages can extend the module without tight coupling.5. Implement seeded simulations with configurable trial counts, fee/slippage randomization, position-risk assumptions, drawdown estimates, and tail-risk summaries.6. Produce explainable risk reports with conservative defaults and clear rejection thresholds.7. Preserve full auditability from input samples through simulation outputs.8. Do not implement strategy signals, risk decisions, order intents, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Seed reproducibility tests, drawdown estimation tests, tail-risk tests, survival probability tests, fee/slippage randomization tests, rejection threshold tests.Acceptance criteria:Risk can be stress-tested with deterministic Monte Carlo simulations and unsafe scenarios produce explainable rejection or reduction recommendations.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 045 - Exchange Reconciliation Engine

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 045: Exchange Reconciliation Engine.Objective:Reconcile exchange state against database state for balances, positions, orders, fills, restart recovery, and recovery after API outage.Prerequisites:Stages 005-044 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 045 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing exchange adapter contracts, repositories, execution, portfolio, protection, observability, and audit contracts.6. Use deterministic sandbox fixtures; do not add real exchange/API calls, real credentials, or real external provider calls.Files to create or modify:src/abtp/reconciliation/engine.py; src/abtp/reconciliation/checks.py; src/abtp/reconciliation/recovery.py; docs/exchange_reconciliation.md; tests/reconciliation/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every reconciliation result must be explainable through stored database state, adapter-provided state, mismatch records, recovery recommendations, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:exchange balances, database balances, positions, open orders, fills, order status, provider timestamp, outage status, restart marker, reconciliation difference, recovery action recommendation.Minimum-risk controls:Mismatch, stale adapter state, outage, or unresolved fill differences must fail safe by recommending pause, manual review, or reconciliation hold. The engine must not place new orders or bypass the Risk Management Engine.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for reconciliation snapshots, mismatch records, balance checks, position checks, order checks, fill checks, recovery plans, and audit evidence.3. Add documentation explaining assumptions, configuration, operating limits, restart recovery, and outage recovery.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic reconciliation between repository records and adapter snapshots supplied by sandbox fixtures.6. Produce recovery recommendations for restart, API outage, missing fills, stale orders, and balance mismatches.7. Never store credentials in reconciliation records.8. Do not implement real exchange HTTP/websocket calls, real cancellation, real order execution, strategy logic, risk approvals, or live trading in this stage.Tests to add or run:Balance mismatch tests, position mismatch tests, order mismatch tests, fill reconciliation tests, restart recovery tests, outage recovery tests.Acceptance criteria:Exchange and database state can be reconciled deterministically, and unresolved mismatches block unsafe continuation until reviewed or recovered.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 046 - Position Exit Optimizer

Phase: Risk

You are Codex working in the ABTP repository. Implement Stage 046: Position Exit Optimizer.Objective:Generate advisory exit recommendations using dynamic stop-loss, ATR trailing stop, partial profit taking, time-based exits, regime-based exits, volatility exits, and exit-quality analysis.Prerequisites:Stages 005-045 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 046 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing portfolio, position, indicator, market-regime, risk, strategy, execution-quality, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/risk/exits.py; src/abtp/risk/trailing_stops.py; src/abtp/risk/exit_quality.py; docs/position_exit_optimizer.md; tests/position_exits/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every exit recommendation must be explainable through stored position inputs, stops, targets, indicators, regime evidence, volatility, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:entry price, current price, stop loss, ATR, trailing stop distance, unrealized P/L, holding time, volatility regime, market regime, partial-profit thresholds, exit quality metrics.Minimum-risk controls:Exit optimization is advisory/risk-context only and must not submit, cancel, or modify orders directly. Exit recommendations must flow through existing strategy, risk, and execution controls before any action.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for exit policies, trailing-stop states, partial-profit recommendations, time exits, regime exits, volatility exits, and exit-quality reports.3. Add documentation explaining assumptions, configuration, operating limits, and how exit recommendations remain advisory.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic dynamic stop, ATR trailing stop, partial profit, time-based, regime-based, and volatility-based exit recommendation utilities.6. Include conservative defaults that tighten or block holding when source data quality is poor, volatility is abnormal, or regime is shock/high-volatility.7. Preserve explainability for every exit recommendation and rejection.8. Do not implement order execution, order cancellation, risk approvals, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Dynamic stop tests, ATR trailing stop tests, partial-profit tests, time-exit tests, regime/volatility exit tests, exit-quality tests.Acceptance criteria:Open positions can receive explainable exit recommendations without creating any direct order path or bypassing the Risk Management Engine.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 047 - Portfolio Allocation Optimizer

Phase: Risk

You are Codex working in the ABTP repository. Implement Stage 047: Portfolio Allocation Optimizer.Objective:Produce advisory portfolio allocation, capital distribution, correlation-aware allocation, exposure balancing, dynamic allocation recommendations, and cash reserve management.Prerequisites:Stages 005-046 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 047 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing portfolio, risk, market-regime, confidence, strategy-laboratory, Monte Carlo, observability, and audit contracts where available.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/portfolio/allocation.py; src/abtp/portfolio/correlation.py; src/abtp/portfolio/rebalancing.py; docs/portfolio_allocation_optimizer.md; tests/portfolio_allocation/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every allocation recommendation must be explainable through stored portfolio state, correlation estimates, exposure limits, cash reserves, risk limits, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:cash balance, asset exposure, target allocation, correlation matrix, volatility, drawdown, cash reserve, risk budget, confidence score, regime, liquidity, rebalance threshold.Minimum-risk controls:Allocation optimization is advisory only. Recommendations must preserve cash reserves, respect exposure limits, and cannot create orders, risk approvals, or execution behavior. Unsafe data or excessive correlation must reduce allocation or block expansion.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for allocation policies, correlation snapshots, exposure summaries, rebalance recommendations, cash reserve checks, and rejection reasons.3. Add documentation explaining assumptions, configuration, operating limits, and advisory-only behavior.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic allocation recommendation utilities with correlation-aware exposure balancing and cash reserve enforcement.6. Produce clear reduced-allocation or blocked-allocation reasons when risk, data quality, volatility, correlation, or cash reserve limits fail.7. Preserve full auditability for allocation inputs and recommendations.8. Do not implement order creation, risk decisions, execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Allocation calculation tests, correlation exposure tests, cash reserve tests, rebalance recommendation tests, risk-limit rejection tests, audit tests.Acceptance criteria:Portfolio allocation recommendations are deterministic, explainable, cash-reserve aware, and unable to bypass trading safety controls.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 048 - Exchange Health Scoring

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 048: Exchange Health Scoring.Objective:Score exchange health from API latency, error rate, exchange outages, spread quality, liquidity quality, reliability, and trading permission gating based on health.Prerequisites:Stages 005-047 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 048 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing exchange adapter, live stream heartbeat, order-book, data-quality, crash-protection, reconciliation, risk, observability, and audit contracts.6. Use deterministic sandbox fixtures; do not add real exchange/API calls, real credentials, or real external provider calls.Files to create or modify:src/abtp/exchanges/health.py; src/abtp/exchanges/reliability.py; src/abtp/exchanges/permission_gates.py; docs/exchange_health_scoring.md; tests/exchange_health/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every exchange-health score must be explainable through stored latency, errors, outage state, spread, liquidity, reliability, gating rules, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:API latency, error count, error rate, outage status, stale heartbeat, spread quality, liquidity depth, order-book imbalance, reconciliation health, reliability score, trading permission status.Minimum-risk controls:Poor exchange health must block or degrade trading permissions and should recommend pause/manual review. Health scoring must not place orders, approve risk, or bypass the Risk Management Engine.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for exchange health inputs, reliability scores, health statuses, permission gates, blocked reasons, and audit evidence.3. Add documentation explaining assumptions, configuration, operating limits, and gating behavior.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic health scoring from adapter/heartbeat/order-book/reconciliation fixtures.6. Implement permission-gating recommendations for read-only, paper-only, block-new-entries, pause, and manual-review states.7. Preserve explainability for each health score and gate.8. Do not implement real exchange calls, real order execution, strategy logic, risk approvals, real external provider calls, or live trading in this stage.Tests to add or run:Latency scoring tests, error-rate tests, outage tests, spread/liquidity quality tests, permission gate tests, public import tests.Acceptance criteria:Exchange health can be scored deterministically and unsafe exchange conditions block trading permissions without creating any execution path.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 049 - Confidence Scoring Engine

Phase: Intelligence

You are Codex working in the ABTP repository. Implement Stage 049: Confidence Scoring Engine.Objective:Aggregate confidence from trend, momentum, volatility, volume, order book, AI prediction, market regime, sentiment, on-chain context, portfolio context, risk context, and data quality into one explainable advisory confidence score with weighted contributions and rejection reasons.Prerequisites:Stages 005-048 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 049 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing indicators, order-book, AI prediction, market-regime, external context, portfolio, risk, data-quality, voting, optimiser, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/confidence/engine.py; src/abtp/confidence/weights.py; src/abtp/confidence/reasons.py; docs/confidence_scoring.md; tests/confidence/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every confidence score must be explainable through stored inputs, component weights, contribution values, data-quality status, rejection reasons, risk checks, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:trend confidence, momentum confidence, volatility confidence, volume confidence, order-book confidence, AI prediction confidence, regime confidence, sentiment confidence, on-chain confidence, portfolio confidence, risk confidence, data-quality confidence, weights, rejection reasons.Minimum-risk controls:Trading confidence is advisory only and must never bypass the Risk Management Engine. Missing, stale, rejected, contradictory, or low-quality inputs must reduce confidence or mark the score non-actionable, never silently increase it.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for confidence inputs, component contributions, weighting policies, confidence results, rejection reasons, and audit evidence.3. Add documentation explaining assumptions, configuration, operating limits, advisory-only behavior, and failure handling.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic weighted aggregation with explicit contribution records for trend, momentum, volatility, volume, order book, AI prediction, market regime, sentiment, on-chain context, portfolio context, risk context, and data quality.6. Implement conservative rejection and non-actionable rules for insufficient evidence, model disagreement, poor data quality, high risk, poor exchange health, and low confidence.7. Preserve explainability by listing all included and excluded components, weights, and reasons.8. Do not implement strategy signal generation, risk decisions, order intents, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Weighted aggregation tests, missing-component tests, rejection-reason tests, quality degradation tests, advisory-only tests, public import tests.Acceptance criteria:Decision cycles can consume one deterministic confidence object with weighted contributions and rejection reasons, while all trading actions still require the Risk Management Engine.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.


## Stage 050 - Continuous Performance Analytics

Phase: Production

You are Codex working in the ABTP repository. Implement Stage 050: Continuous Performance Analytics.Objective:Build daily, weekly, monthly, long-term, strategy, regime, AI accuracy, risk, drawdown, execution, and operator dashboard performance analytics.Prerequisites:Stages 005-049 complete.First actions:1. Inspect the repository structure, existing documentation, tests, and configuration.2. Read docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md and confirm Stage 050 source requirements.3. Preserve existing user work and follow existing project patterns where they exist.4. If files already exist, modify them carefully instead of replacing unrelated work.5. Reuse existing backtesting reports, paper trading, live gateway, execution quality, learning, optimiser, risk, portfolio, dashboard, observability, and audit contracts.6. Use deterministic fixtures; do not add real exchange/API calls or real external provider calls.Files to create or modify:src/abtp/analytics/performance.py; src/abtp/analytics/trends.py; src/abtp/analytics/dashboard_metrics.py; docs/continuous_performance_analytics.md; tests/performance_analytics/.Architecture constraints:- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.- Do not place exchange API calls outside exchange adapter modules.- Do not allow any order path to bypass the Risk Management Engine.- Prefer spot trading first; leverage, margin, futures, and options stay disabled unless a later explicit stage enables them.- Every analytics report must be explainable through stored trades, portfolio snapshots, risk decisions, predictions, regimes, execution records, dashboard metrics, and audit events.- Use deterministic tests with fixtures; do not require real exchange credentials for unit tests.Data and Bitcoin-dependency parameters:daily performance, weekly performance, monthly performance, strategy comparison, regime comparison, AI accuracy trend, risk trend, drawdown trend, execution trend, long-term reporting, operator dashboard metrics.Minimum-risk controls:Performance analytics is read-only and advisory. Reports must include costs, fees, slippage, drawdown, and risk breaches, and must not trigger live strategy changes, order creation, risk approvals, or execution behavior automatically.Implementation requirements:1. Keep the module narrowly scoped to this stage.2. Define clear interfaces and data contracts for performance windows, trend reports, strategy comparisons, regime comparisons, AI accuracy trends, risk trends, drawdown trends, execution trends, and dashboard metric snapshots.3. Add documentation explaining assumptions, configuration, operating limits, and reporting limitations.4. Ensure future stages can extend the module without tight coupling.5. Implement deterministic daily, weekly, monthly, and long-term analytics from stored fixture records.6. Include strategy, regime, AI accuracy, risk, drawdown, and execution comparisons with explicit source references.7. Expose operator dashboard metric objects without adding unsafe control endpoints.8. Preserve full auditability from stored inputs through report outputs.9. Do not implement strategy changes, risk decisions, order intents, order execution, real exchange connectors, real external provider calls, or live trading in this stage.Tests to add or run:Daily/weekly/monthly report tests, strategy comparison tests, regime comparison tests, AI accuracy trend tests, risk/drawdown/execution trend tests, dashboard metric tests.Acceptance criteria:Operators can inspect continuous deterministic performance analytics across strategy, regime, AI, risk, drawdown, and execution dimensions without any automatic trading action.Completion response:Summarize created/modified files, tests run, remaining risks, and any assumptions. Do not claim the bot is profitable; report only verified behavior.

Final Readiness Gate

ABTP should be considered ready for controlled operation only when all Stage 005-073 acceptance criteria pass and the operator can inspect data health, signal reasoning, risk decisions, open exposure, account drawdown, alerts, learning recommendations, optimiser recommendations, walk-forward validation, strategy laboratory evidence, execution quality, model management, model drift, Monte Carlo risk, reconciliation status, exit recommendations, allocation recommendations, exchange health, confidence scoring, continuous performance analytics, multi-timeframe intelligence, market-cycle intelligence, on-chain intelligence, fundamental ratings, macro and narrative intelligence, opportunity discovery, portfolio intelligence, AI committee evidence, governance and compliance evidence, AI research evidence, institutional decision intelligence, paper command-center evidence, paper runner/session evidence, paper evaluation-gate evidence, protection mode, and the kill switch from the dashboard.

Backtests include costs, slippage, drawdown, and market-regime analysis.

Paper trading demonstrates stable behavior for the agreed evaluation window.

Live trading starts supervised, tiny, spot-only, and manually approved.

Limited automation remains bounded by hard circuit breakers.

The project documentation remains the single source of truth for future Codex work.

Stage 051 – Multi-Timeframe Intelligence Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Create a hierarchical market analysis engine that evaluates multiple timeframes and only produces high-confidence investment signals when the higher and lower timeframes are aligned.
Responsibilities
Timeframes
Monthly
Weekly
Daily
4 Hour
1 Hour
Analysis
Trend
Momentum
Volatility
Volume
Market Structure
Support/Resistance
Liquidity
Outputs
Trend Alignment Score
Trend Strength
Timeframe Agreement %
Entry Timing Score
Exit Timing Score
Market Structure
Higher-Timeframe Bias
Risk Rules
Reject trade if
Monthly = Bear
Weekly = Bear
Daily = Bull
No alignment
Stage 052 – Market Cycle Intelligence Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Determine the current cryptocurrency market cycle.
Detect
Bull Accumulation
Bull Expansion
Bull Euphoria
Distribution
Bear Market
Capitulation
Recovery
Analyze
BTC Dominance
ETH Dominance
Altcoin Season
Market Breadth
Fear & Greed
Liquidity
Output
Cycle Phase
Cycle Confidence
Risk Level
Suggested Allocation
Stage 053 – On-Chain Intelligence Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Evaluate blockchain activity.
Parameters
MVRV
SOPR
NUPL
Exchange Inflow
Exchange Outflow
Whale Wallet Activity
Miner Selling
Dormancy
Coin Days Destroyed
Realized Price
Hash Rate
Network Growth
Output
On-chain Score
Accumulation Score
Distribution Score
Confidence
Stage 054 – Fundamental Asset Rating Engine
Priority: ⭐⭐⭐⭐
Objective
Evaluate project quality.
Parameters
Market Cap
Liquidity
Developer Activity
GitHub
TVL
Staking
Tokenomics
Inflation
Partnerships
Institutional Adoption
Security
Roadmap
Community
Governance
Output
Fundamental Rating
Long-Term Score
Risk Grade
Stage 055 – Capital & Sector Rotation Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Identify where institutional money is flowing.
Track
BTC
ETH
Large Caps
Mid Caps
Small Caps
Stablecoins
Sector Rotation
AI
RWA
Layer2
Gaming
DeFi
Infrastructure
Privacy
DePIN
Meme
Output
Capital Flow Map
Rotation Probability
Sector Strength
Stage 056 – Macro & Narrative Intelligence Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Monitor global macro events.
Track
Interest Rates
Fed
ECB
Inflation
CPI
PPI
Dollar Index
Bond Yield
Gold
Oil
Nasdaq
S&P500
ETF Flows
Crypto Narratives
AI
RWA
Stablecoins
Gaming
Layer2
Memecoin
DeFi
Output
Macro Risk Score
Narrative Strength
Risk-On Score
Stage 057 – Opportunity Discovery Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Scan the complete crypto market every day.
Universe
Top 20–30 Coins
Dynamic Universe
Ranking
Technical Score
AI Score
Fundamental Score
On-chain Score
Liquidity
Risk
Relative Strength
Momentum
Market Cycle
Expected Holding Period
Output
Top 10 Opportunities
Avoid List
Watch List
Stage 058 – Adaptive Position Management Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Manage open positions intelligently.
Features
Dynamic Stop Loss
ATR Stop
Trailing Stop
Partial Profit
Scaling
Time Exit
Volatility Exit
Regime Exit
Confidence Exit
Position Aging
Holding Recommendation
Output
Current Risk
Hold %
Sell %
Increase %
Exit %
Stage 059 – Portfolio Intelligence & Hedging Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Manage the portfolio like an investment fund.
Features
Allocation Optimization
Cash Reserve
Portfolio Correlation
Sector Exposure
Asset Exposure
Maximum Risk
Diversification
Stablecoin Allocation
Defensive Allocation
Rebalancing
Output
Portfolio Health
Hedge Recommendation
Allocation Plan
Stage 060 – AI Investment Committee
Priority: ⭐⭐⭐⭐⭐
Objective
Replace single-model decisions with committee voting.
Members
Trend AI
Momentum AI
Macro AI
Risk AI
On-chain AI
Fundamental AI
Liquidity AI
Sentiment AI
Portfolio AI
Execution AI
Output
Votes
Confidence
Disagreement
Recommendation
Reasoning
Stage 061 – Capital Preservation Framework
Priority: ⭐⭐⭐⭐⭐
Objective
Protect capital under adverse conditions.
Detect
Crash
Exchange Failure
Liquidity Crisis
Extreme Volatility
Whale Dump
Macro Shock
ETF Outflow
Actions
Pause Trading
Reduce Allocation
Increase Cash
Raise Confidence Threshold
Tighten Stops
Kill Switch
Output
Protection Mode
Emergency Level
Recovery Status
Stage 062 – Trade Intelligence & Learning Engine
Priority: ⭐⭐⭐⭐⭐
Objective
Learn from every completed trade.
Analyze
Winning Trades
Losing Trades
Holding Time
Best Regime
Best Strategy
Best Indicators
AI Accuracy
Common Mistakes
Output
Learning Report
Strategy Ranking
Improvement Suggestions
Stage 063 – AI Investment Report Generator
Priority: ⭐⭐⭐⭐⭐
Objective
Generate explainable investment reports.
Include
Why Buy
Why Sell
Why Hold
Market Cycle
Macro Analysis
On-chain
Fundamentals
AI Votes
Risk
Expected Return
Expected Holding
Portfolio Impact
Output
Institutional Investment Report
Stage 064 – Dynamic Asset Universe Manager
Priority: ⭐⭐⭐⭐⭐
Objective
Maintain a dynamic investment universe instead of a fixed coin list.
Features
Select top 20–30 assets based on liquidity, market cap, exchange availability, and minimum quality thresholds.
Automatically add newly qualified assets after validation.
Remove assets that fall below liquidity, security, or governance requirements.
Maintain separate universes for research, paper trading, and live trading.
Output
Approved Asset Universe
Watchlist
Excluded Assets with Reasons
Stage 065 – Institutional Risk Stress Testing
Priority: ⭐⭐⭐⭐⭐
Objective
Run advanced scenario analysis beyond Monte Carlo.
Simulate
30–70% market crashes
Stablecoin de-pegs
Exchange insolvency
Flash crashes
Liquidity evaporation
Regulatory shocks
Network outages
Output
Portfolio Survival Score
Worst-Case Drawdown
Recovery Time Estimate
Risk Recommendations
Stage 066 – Cross-Asset Correlation Intelligence
Priority: ⭐⭐⭐⭐
Objective
Monitor relationships between crypto and traditional markets.
Track
BTC vs ETH
Crypto sectors
BTC vs Nasdaq
BTC vs Gold
BTC vs DXY
BTC vs Bond Yields
Output
Correlation Matrix
Diversification Opportunities
Correlation Risk Alerts
Stage 067 – Institutional Execution Optimizer
Priority: ⭐⭐⭐⭐
Objective
Improve execution quality for large or illiquid positions.
Features
Smart order slicing
Liquidity-aware execution
Slippage prediction
Spread optimization
Execution timing recommendations
Output
Execution Plan
Expected Cost
Slippage Estimate
Stage 068 – Governance & Compliance Engine
Priority: ⭐⭐⭐⭐
Objective
Provide operational governance and policy enforcement.
Features
Strategy approval workflow
Model approval workflow
Configuration versioning
Manual override logging
Audit-ready compliance reports
Output
Compliance Status
Approval History
Policy Violations
Stage 069 – AI Research Laboratory
Priority: ⭐⭐⭐⭐
Objective
Provide a controlled environment for experimentation.
Features
Compare candidate models
Compare strategies
Hyperparameter testing
Regime-specific evaluations
Benchmarking against production models
Output
Research Reports
Promotion Recommendations
Experiment Results
Stage 070 – Institutional Decision Intelligence Hub
Priority: ⭐⭐⭐⭐⭐
Objective
Combine all platform intelligence into a single investment decision.
Inputs
Multi-Timeframe Intelligence
Market Cycle
On-Chain Analysis
Fundamental Rating
Macro & Narrative
AI Committee
Portfolio Status
Risk Engine
Opportunity Scanner
Confidence Engine
Outputs
Final Investment Decision
Confidence Score
Suggested Allocation
Holding Period
Entry & Exit Plan
Risk Assessment
Complete Explainable Decision Record


## Stage 071 - Simple Paper Trading Command Center

Phase: Paper Trading Usability

You are Codex working in the ABTP repository. Implement Stage 071: Simple Paper Trading Command Center.

Objective:
Turn the Stage 070 institutional decision record and existing paper-trading, portfolio, risk, confidence, crash-protection, exchange-health, and analytics outputs into one simple operator-facing paper-trading command view. The goal is to make the bot easy to understand and safe to operate in paper mode before any real-money trading is considered.

Prerequisites:
Stages 005-070 complete and passing. Stage 070 must produce an advisory InstitutionalDecisionRecord. Stage 027 paper trading, Stage 028 API/dashboard contracts, Stage 029 monitoring/audit, Stage 030 notifications, Stage 033 automation controls, Stage 048 exchange health, Stage 049 confidence scoring, Stage 050 performance analytics, Stage 061 capital preservation, and Stage 070 decision hub should be reused where available.

First actions:
1. Inspect the repository structure, existing documentation, tests, and configuration.
2. Read README.md, docs/institutional_decision_hub.md, docs/paper_trading.md, docs/dashboard.md, docs/api_design.md, docs/risk_engine.md, docs/capital_preservation.md, docs/exchange_health_scoring.md, docs/confidence_scoring.md, and docs/continuous_performance_analytics.md.
3. Preserve existing user work and follow existing project patterns where they exist.
4. If files already exist, modify them carefully instead of replacing unrelated work.
5. Reuse existing domain, risk, paper, portfolio, analytics, protection, exchange-health, dashboard, observability, and audit contracts.
6. Use deterministic fixtures; do not add real exchange/API calls, real external provider calls, real AI service calls, or real live-trading behavior.

Files to create or modify:
src/abtp/paper/command_center.py; src/abtp/paper/trade_checklist.py; src/abtp/dashboard/command_center.py; src/abtp/api/command_center.py; docs/simple_paper_command_center.md; README.md; tests/paper_command_center/.

Architecture constraints:
- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.
- Do not place exchange API calls outside exchange adapter modules.
- Do not allow any order path to bypass the Risk Management Engine.
- Prefer spot trading first; leverage, margin, futures, options, transfers, withdrawals, and admin exchange permissions remain disabled.
- Every command-center recommendation must be explainable through stored decision evidence, risk checks, confidence score, paper account state, data quality, exchange health, capital-protection state, and audit events.
- Use deterministic tests with fixtures; do not require real exchange credentials, network access, paid data providers, or external AI services for unit tests.
- The command center must not create strategy signals, approve risk, create live order intents, submit orders, cancel real orders, call exchanges, change configuration, or enable live trading.

Data and Bitcoin-dependency parameters:
Decision label, confidence score, support score, risk score, risk level, paper account balance, current paper equity, open paper positions, unrealized P/L, realized P/L, max paper position size, stop-loss requirement, take-profit review, exchange-health status, data-quality status, capital-protection mode, drawdown, daily loss, weekly loss, blocked-trade reasons, audit reference, and operator-facing action label.

Minimum-risk controls:
The command center is paper-first and must default to no trading action when evidence is missing, stale, contradictory, degraded, rejected, or unsafe. It must display simple labels only: BUY REVIEW, HOLD, AVOID, or PROTECT CAPITAL. BUY REVIEW means "eligible for paper-trade review", not permission to place real orders. PROTECT CAPITAL must override all other labels when kill switch, capital preservation, severe drawdown, crash protection, exchange outage, stale data, or risk rejection is active.

Implementation requirements:
1. Keep the module narrowly scoped to this stage.
2. Define clear data contracts for command-center input, checklist result, simple recommendation, paper trade readiness, blocked reasons, account summary, and display payload.
3. Implement a deterministic trade checklist that requires trusted data, acceptable exchange health, acceptable confidence, acceptable risk score, no active kill switch, no capital-protection block, no daily/weekly loss halt, available paper balance, stop-loss metadata, and advisory-only Stage 070 decision support.
4. Convert Stage 070 decisions into plain-language command labels:
   - favorable_review can become BUY REVIEW only if the checklist passes.
   - hold_review becomes HOLD.
   - defensive_review becomes PROTECT CAPITAL when protection evidence is active, otherwise AVOID or HOLD with reasons.
   - reject_no_action becomes AVOID or PROTECT CAPITAL depending on risk/protection evidence.
5. Produce a compact dashboard view object that can be rendered as deterministic text for tests and future UI work.
6. Produce a dependency-free API response contract for the command center; no HTTP framework is required.
7. Include a plain-language explanation and a compact audit payload for every recommendation.
8. Ensure unsafe, missing, or inconsistent inputs fail closed to AVOID or PROTECT CAPITAL.
9. Add documentation explaining how the command center uses prior stages, why it remains paper-only, and how an operator should interpret each label.
10. Do not implement live exchange calls, real order submission, real order cancellation, credential handling beyond existing config, automatic live strategy changes, or unsupervised live trading.

Tests to add or run:
Command label mapping tests, checklist pass/fail tests, missing evidence tests, stale data tests, risk rejection tests, capital-protection override tests, exchange-health block tests, confidence threshold tests, stop-loss-required tests, dashboard text rendering tests, API response contract tests, advisory-only safety tests, public import tests.

Acceptance criteria:
An operator can inspect one simple deterministic command-center payload and understand whether a paper trade is allowed, why it is allowed or blocked, the maximum paper position context, the stop-loss requirement, the risk state, and the current paper account status in under 60 seconds. Unsafe conditions must block paper trading with clear reasons. Live trading remains impossible.

Completion response:
Summarize created/modified files, tests run, assumptions, remaining risks, and any operator-facing behavior added. Do not claim the bot is profitable; report only verified behavior.


## Stage 072 - Paper Trading Runner and Simulation Loop

Phase: Paper Trading Execution

You are Codex working in the ABTP repository. Implement Stage 072: Paper Trading Runner and Simulation Loop.

Objective:
Create a deterministic paper-trading runner that uses the existing strategy, risk, portfolio, paper execution, command-center, audit, monitoring, and analytics modules to run complete simulated trading cycles. The runner should make ABTP behave like a real bot in paper mode while guaranteeing that no real money, live exchange order, or unsafe direct execution path is used.

Prerequisites:
Stages 005-071 complete and passing. Stage 071 must expose a simple paper command-center/checklist contract. Stage 027 paper trading, Stage 024 paper-safe execution routing, Stage 022 risk engine, Stage 023 portfolio manager, Stage 020 strategy framework, Stage 021 minimum-risk spot strategy, Stage 029 monitoring/audit, Stage 030 notifications, Stage 033 automation policy, Stage 048 exchange health, and Stage 070 decision hub should be reused where available.

First actions:
1. Inspect the repository structure, existing documentation, tests, and configuration.
2. Read docs/paper_trading.md, docs/order_execution.md, docs/risk_engine.md, docs/portfolio_manager.md, docs/strategy_framework.md, docs/simple_paper_command_center.md, docs/automation_policy.md, docs/monitoring.md, and docs/final_integration.md.
3. Preserve existing user work and follow existing project patterns where they exist.
4. If files already exist, modify them carefully instead of replacing unrelated work.
5. Reuse existing paper account, paper simulator, strategy engine, risk engine, portfolio manager, audit, metrics, alert, and command-center contracts.
6. Use deterministic fixtures and simulated market snapshots; do not add real exchange/API calls, real external provider calls, real AI service calls, or live-trading behavior.

Files to create or modify:
src/abtp/paper/runner.py; src/abtp/paper/cycle.py; src/abtp/paper/session.py; src/abtp/paper/summary.py; docs/paper_trading_runner.md; README.md; tests/paper_runner/.

Architecture constraints:
- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.
- Do not place exchange API calls outside exchange adapter modules.
- Do not allow any order path to bypass the Risk Management Engine.
- Prefer spot trading first; leverage, margin, futures, options, transfers, withdrawals, and admin exchange permissions remain disabled.
- Every simulated paper trade must be reconstructable from market snapshot, features, signal, risk decision, paper order intent, simulated fill, portfolio update, command-center decision, and audit event.
- Use deterministic tests with fixtures; do not require real exchange credentials, network access, paid data providers, or external AI services for unit tests.
- The runner must not create live orders, call live exchange trading endpoints, mutate live account state, or enable live trading.

Data and Bitcoin-dependency parameters:
Configured paper symbol, paper starting balance, market snapshot, feature snapshot reference, strategy signal, risk decision, max paper risk per trade, stop-loss price, take-profit context, fee estimate, slippage estimate, simulated order, simulated fill, paper position, paper cash balance, paper equity, drawdown, command-center label, blocked reasons, cycle status, audit reference, metrics summary, and session status.

Minimum-risk controls:
The runner must run only in paper mode by default. If configuration indicates live trading, live credentials, unsafe mode, missing risk engine, missing stop loss, missing command-center approval, active kill switch, stale data, exchange-health block, capital-protection block, or portfolio loss halt, it must skip the simulated trade and record a blocked cycle. BUY REVIEW from Stage 071 is necessary but not sufficient; the runner must still require strategy signal, risk approval, position sizing, and stop-loss metadata.

Implementation requirements:
1. Keep the module narrowly scoped to this stage.
2. Define data contracts for PaperTradingCycleInput, PaperTradingCycleResult, PaperTradingSessionConfig, PaperTradingSessionSummary, blocked cycle reasons, and audit payloads.
3. Implement a single-cycle runner that consumes a market snapshot and produces either a blocked cycle or a simulated paper trade.
4. Implement a session runner that can process a deterministic sequence of market snapshots and aggregate session-level results.
5. Require the Stage 071 command checklist before any simulated paper order is routed.
6. Require the Risk Management Engine decision before any simulated paper order is routed.
7. Require stop-loss metadata and conservative position sizing before any simulated fill is created.
8. Update paper account state and portfolio context only through existing paper/portfolio contracts.
9. Emit deterministic audit events and local metrics for every cycle, including skipped cycles.
10. Produce plain-language summaries for cycle result and session result.
11. Add documentation explaining how to run a paper session, how to interpret skipped cycles, and why the runner is not live trading.
12. Do not implement real exchange adapters, live order submission, live order cancellation, withdrawals, transfers, margin, leverage, futures, options, automatic strategy changes, or unsupervised live trading.

Tests to add or run:
Single-cycle allowed paper trade test, risk rejection blocked-cycle test, command-center rejection test, missing stop-loss test, stale data test, exchange-health block test, kill-switch block test, paper account update test, deterministic session summary test, audit payload test, no-live-mode test, public import test.

Acceptance criteria:
ABTP can run complete deterministic paper-trading cycles that simulate bot behavior end to end while preserving every safety boundary. Paper trades occur only when command-center readiness, strategy signal, risk decision, position sizing, stop-loss metadata, data quality, exchange health, and portfolio controls all pass. Blocked cycles are recorded with plain-language reasons. Live trading remains impossible.

Completion response:
Summarize created/modified files, tests run, assumptions, remaining risks, and how to run the paper runner. Do not claim the bot is profitable; report only verified behavior.


## Stage 073 - Paper Trading Evaluation Gate

Phase: Paper Trading Evaluation

You are Codex working in the ABTP repository. Implement Stage 073: Paper Trading Evaluation Gate.

Objective:
Create a conservative evaluation gate that reviews paper-trading performance over a configured period and decides whether the bot should remain in paper mode, be made more conservative, be paused for review, or be eligible for a future tiny supervised live-trading proposal. This stage must not enable live trading; it only produces evidence and recommendations.

Prerequisites:
Stages 005-072 complete and passing. Stage 072 must produce deterministic paper-trading session summaries. Stage 026 performance metrics, Stage 027 paper trading, Stage 029 monitoring/audit, Stage 033 automation policy, Stage 035 self-learning, Stage 039 walk-forward validation, Stage 044 Monte Carlo risk, Stage 050 continuous performance analytics, Stage 061 capital preservation, and Stage 068 governance/compliance should be reused where available.

First actions:
1. Inspect the repository structure, existing documentation, tests, and configuration.
2. Read docs/paper_trading_runner.md, docs/performance_metrics.md, docs/continuous_performance_analytics.md, docs/self_learning.md, docs/walk_forward_validation.md, docs/monte_carlo_risk.md, docs/capital_preservation.md, docs/governance_compliance.md, and docs/production_release_checklist.md.
3. Preserve existing user work and follow existing project patterns where they exist.
4. If files already exist, modify them carefully instead of replacing unrelated work.
5. Reuse existing paper session summaries, performance metrics, analytics, self-learning, risk, drawdown, audit, governance, and capital-preservation contracts.
6. Use deterministic fixtures; do not add real exchange/API calls, real external provider calls, real AI service calls, or live-trading behavior.

Files to create or modify:
src/abtp/paper/evaluation.py; src/abtp/paper/promotion_gate.py; src/abtp/paper/review_report.py; docs/paper_evaluation_gate.md; docs/production_release_checklist.md; README.md; tests/paper_evaluation/.

Architecture constraints:
- Preserve modular architecture, loose coupling, high cohesion, testability, observability, and environment-driven configuration.
- Do not place exchange API calls outside exchange adapter modules.
- Do not allow any order path to bypass the Risk Management Engine.
- Prefer spot trading first; leverage, margin, futures, options, transfers, withdrawals, and admin exchange permissions remain disabled.
- Every evaluation recommendation must be explainable through paper trades, skipped cycles, blocked reasons, fees, slippage, drawdown, risk decisions, command-center labels, confidence scores, exchange-health history, capital-protection events, and audit references.
- Use deterministic tests with fixtures; do not require real exchange credentials, network access, paid data providers, or external AI services for unit tests.
- The evaluation gate must not enable live trading, create live orders, approve risk, change strategy parameters automatically, change risk rules automatically, or mutate production configuration.

Data and Bitcoin-dependency parameters:
Evaluation window, minimum paper-trading days, minimum completed paper trades, net return, win rate, average win, average loss, expectancy, profit factor, maximum drawdown, daily loss events, weekly loss events, blocked cycle count, skip reason distribution, fee/slippage impact, risk rejection count, stop-loss compliance, command-center accuracy review, confidence calibration, strategy/regime performance, capital-preservation events, governance status, and final gate recommendation.

Minimum-risk controls:
The default recommendation must be remain_paper unless evidence strongly supports future review. Any drawdown breach, insufficient sample size, stop-loss violation, missing audit evidence, unstable expectancy, excessive fees/slippage, poor confidence calibration, high blocked-cycle rate, capital-protection event, or governance violation must prevent future live consideration. Future live eligibility means only "prepare a supervised tiny-live-trade proposal in a later explicit stage"; it is not live trading approval.

Implementation requirements:
1. Keep the module narrowly scoped to this stage.
2. Define data contracts for PaperEvaluationPolicy, PaperEvaluationInput, PaperEvaluationReport, PromotionGateResult, evaluation metrics, rejection reasons, recommendations, and audit payloads.
3. Implement deterministic evaluation over paper-trading sessions and completed paper trades.
4. Require minimum sample size, minimum evaluation window, stop-loss compliance, acceptable drawdown, acceptable loss limits, positive or stable expectancy, acceptable fee/slippage impact, and complete audit evidence.
5. Produce one of these recommendations: remain_paper, make_more_conservative, pause_for_review, or eligible_for_future_tiny_live_proposal.
6. Include plain-language reasons, numeric evidence, and source references for every recommendation.
7. Include a beginner-readable summary that answers: Did paper trading help? What went wrong? What should be changed? Is real trading still locked?
8. Update the production release checklist to reference Stage 073 as a paper-evidence gate, not live approval.
9. Add documentation explaining that this stage cannot enable live trading and does not guarantee profit.
10. Do not implement real exchange adapters, live order submission, live order cancellation, withdrawals, transfers, margin, leverage, futures, options, automatic strategy/risk modification, or unsupervised live trading.

Tests to add or run:
Insufficient sample rejection test, drawdown rejection test, loss-limit rejection test, stop-loss violation rejection test, positive paper result eligibility test, high fee/slippage rejection test, blocked-cycle analysis test, confidence calibration test, audit completeness test, beginner summary test, no-live-approval test, public import test.

Acceptance criteria:
ABTP can evaluate a paper-trading period and produce a deterministic, explainable gate recommendation. The gate must keep live trading locked, clearly explain whether paper trading is improving results, and identify what must be fixed before any future tiny supervised live-trading stage can be proposed.

Completion response:
Summarize created/modified files, tests run, assumptions, remaining risks, and the final paper-evaluation behavior. Do not claim the bot is profitable; report only verified behavior.
