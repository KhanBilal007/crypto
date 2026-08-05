# Institutional Risk Stress Testing

Stage 065 adds deterministic scenario stress testing beyond Monte Carlo. It
applies explicit institutional shock scenarios to supplied portfolio exposure
evidence and reports survival, worst drawdown, recovery time, and advisory risk
recommendations.

The stress engine does not fetch market data, call exchanges, call providers,
create strategy signals, approve risk, create order intents, submit orders,
cancel orders, or execute trades.

## Inputs

`InstitutionalStressInput` contains:

- starting equity
- cash percentage
- risk-asset exposure percentage
- stablecoin exposure percentage
- exchange exposure percentage
- data-quality status
- observed timestamp and source references

`StressScenarioDefinition` describes deterministic shocks such as:

- 30-70% market crashes
- stablecoin de-pegs
- exchange insolvency
- flash crashes
- liquidity evaporation
- regulatory shocks
- network outages

## Outputs

`run_institutional_stress_test` emits an `InstitutionalStressReport` with:

- portfolio survival score
- worst-case drawdown
- recovery-time estimate
- per-scenario results
- rejection reasons
- advisory risk recommendations
- quality flags
- audit payload

Recommendations are manual-review context only. They cannot automatically
pause trading, increase cash, reduce allocation, approve risk, or place orders.

## Operating Limits

- No profit is guaranteed.
- Stress-test output must never bypass the Risk Management Engine.
- Unsafe survival score, drawdown, recovery time, stale inputs, or rejected
  inputs fail closed.
- Scenario assumptions are deterministic and should be reviewed before use in
  any later production workflow.
- Tests use deterministic fixtures and require no real credentials, provider
  access, exchange access, or network calls.
