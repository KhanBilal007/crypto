# Paper Trading Engine

Stage 027 adds live-like paper trading cycles with simulated fills, realistic
fee/spread/slippage assumptions, portfolio accounting, risk checks, and
auditable cycle records.

## Cycle Flow

For each accepted market update, the paper engine:

1. Builds a `PaperMarketSnapshot` from live-stream output or deterministic test
   fixtures.
2. Converts candle, order-book metrics, stream health, and paper account state
   into a Stage 015 `FeatureSnapshot`.
3. Classifies market regime.
4. Evaluates the configured strategy.
5. Sends directional strategy output through the Stage 022 Risk Management
   Engine.
6. Creates an `OrderIntent` only after risk approval.
7. Routes that intent through the Stage 024 paper-safe execution engine.
8. Applies simulated fills to the local paper account.
9. Records a `PaperTradingCycleResult` with feature, regime, strategy, risk,
   execution, equity, and skip reasons.

## Simulated Account

`PaperTradingAccount` tracks quote cash, BTC base quantity, average entry price,
realized P/L, fees, equity history, and simulated trade fills. It can build the
same `RiskPortfolioContext` used by the Risk Management Engine.

No live credentials, exchange balances, withdrawals, margin, futures, leverage,
or external provider calls are used or stored.

## Fill Assumptions

`PaperFillSimulationConfig` defines:

- fee basis points
- spread basis points
- slippage basis points
- fill ratio
- simulated latency

The engine uses `PaperSafeExecutionEngine` and `PaperOrderRouter` in paper mode
only. Direct order submission is rejected; orders can only emerge from a
strategy cycle that receives an approved `RiskDecision`.

## Safety Controls

Paper trading is blocked when:

- live data is stale
- live data is degraded and `block_degraded_data=true`
- generated features are not trusted
- paper drawdown exceeds the configured halt threshold
- the strategy emits HOLD
- the Risk Management Engine rejects the proposed order

Stage 027 still does not support live execution. It produces live-like paper
performance records for validation only and does not claim any strategy is
profitable.
