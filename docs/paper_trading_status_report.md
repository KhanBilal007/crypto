# Paper Trading Status Report

Generated from a deterministic local paper-mode smoke run on 2026-07-30.

## Configuration Used

- Profile: `paper`
- SAFE_MODE: `true`
- Live trading enabled: `false`
- Runtime can execute live: `false`
- Market data: deterministic sandbox fixture
- Asset focus: `BTC/USDT`
- Strategy: `MinRiskSpotStrategyV1`
- Initial simulated balance: `10000 USDT`
- Max risk per trade: `0.25%`
- Daily loss halt: `1%`
- Weekly loss halt: `3%`
- Max drawdown halt: `5%`
- Leverage, margin, futures, options, withdrawals, and transfers: disabled
- Stop-loss required: `true`
- Minimum reward-to-risk target: `2.0` in saved run config
- Stale/degraded data: rejected
- Spread/slippage ceilings: `25 bps` spread, `10 bps` slippage
- Audit/reporting: enabled through cycle audit payloads and this report

The saved non-secret run configuration is
[`docs/paper_trading_run_config.json`](paper_trading_run_config.json).

## Verification Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
```

Result before the smoke run: all checks passed, including `562 passed`.

## Smoke Run Result

- Paper session: `paper-smoke-001`
- Session status: `completed`
- Cycles processed: `4`
- Simulated executed trades: `2`
- Blocked cycles in main session: `0`
- Risk-rejected cycles in main session: `0`
- Starting equity: `10000`
- Ending equity: `10000.016393455`
- Cash after simulated fills: `9997.936393455`
- Open BTC quantity: `0.02`
- Realized P/L: `0`
- Total simulated fees: `0.002061545`
- Current drawdown: `0`
- Paper halt active: `false`

Simulated fills:

| Side | Quantity | Price | Fee | Time |
| --- | ---: | ---: | ---: | --- |
| buy | `0.01` | `102.07650` | `0.001020765` | `2026-01-01T03:00:01+00:00` |
| buy | `0.01` | `104.07800` | `0.00104078` | `2026-01-01T04:00:01+00:00` |

All simulated executed cycles had `risk_decision_status=approved` before the
paper-safe execution route accepted the fill.

## Rejection And Safety Checks

- Risk rejection smoke: passed.
- Risk rejection reason: `Risk Management Engine rejected simulated paper order`.
- Risk rejection audit status: `risk_rejected`.
- Stale data smoke: passed.
- Stale data reason: `market snapshot is stale`.
- Live mode request smoke: passed.
- Live mode request status: `skipped`.
- Live mode request reasons:
  - `live mode is not allowed for paper runner`
  - `live credentials are not allowed for paper runner`
- Direct live enable call: rejected by `PaperTradingRunner.enable_live_trading()`.
- Direct paper engine order submission: rejected by `PaperTradingEngine.submit_order()`.
- Runtime live capability: `can_execute_live=false`.

## Secret Check

- `mask_secret("dummy-secret-for-smoke")` returned `[REDACTED]`.
- Secret-like storage key `api_secret` was rejected by
  `assert_no_plaintext_secret_keys`.
- No real exchange credentials were used or stored.

## Status

ABTP is ready for deterministic paper-mode operation using sandbox/fixture
market data and simulated balances. Live trading remains blocked. This report
does not claim profitability; it only records verified paper-mode behavior.
