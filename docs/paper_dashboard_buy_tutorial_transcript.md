# ABTP Paper Dashboard Buy Tutorial

This tutorial explains how to approve a simulated paper BUY in the ABTP Paper Trading Dashboard.

## Safety First

Only use the dashboard when the header shows:

- PAPER MODE
- SAFE MODE
- LIVE OFF

This confirms the dashboard is for simulated paper trades only. It does not place real exchange orders.

## When To Buy

Approve a paper BUY only when all of these are true:

- Recommendation is BUY.
- Data quality is trusted.
- Risk decision is approved.
- The suggested trade includes stop-loss, target, risk amount, and reward-to-risk.

Do not approve when the UI shows HOLD, REJECTED, stale data, degraded data, excessive spread, paused bot, emergency stop, or any risk rejection.

## Why To Buy

Read the explanation before approving. The dashboard should show why ABTP produced the recommendation, such as:

- Indicator reasons.
- AI confidence if available.
- Market regime.
- Data-quality status.
- Risk Management Engine decision.

The BUY label alone is not enough. Risk approval and explanation are required.

## How To Buy

1. Open the dashboard at `http://127.0.0.1:8765`.
2. Confirm PAPER MODE, SAFE MODE, and LIVE OFF.
3. Review the Recommendation panel.
4. Review the Suggested Paper Trade panel.
5. Click Approve Paper Trade only if risk decision is approved.
6. Check Logs for `approve_paper_trade` and `paper_fill`.
7. Check Paper Portfolio for open BTC, cash, equity, and unrealized P/L.

## Important Limit

This is paper trading only and not financial advice. Leverage, margin, futures, options, withdrawals, transfers, and real live exchange execution remain disabled.
