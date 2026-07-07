# Forward Test Report

## 1. Date/Time of Run

- UTC: `2026-07-04T10:55:16Z`
- Local: `2026-07-04 14:55:16 +04:00`

## 2. Runtime Command Used

```bash
/OPT/ANACONDA3/bin/python3 main.py --mode forward
```

## 3. Safety Config

- `EXECUTION_MODE=paper`
- `LIVE_TRADING_ENABLED=false`
- `PRIVATE_KEY` not required
- `MANUAL_APPROVAL_REQUIRED=true`
- `FORWARD_TESTING_MODE=true`
- Jupiter live sending disabled
- Audit logging enabled
- Dashboard and status expose forward mode

## 4. Signals Detected

- Signals detected during this forward window: `0`
- Historical whale signals already present in the database were not part of this window.

## 5. Trades Approved

- Simulated trades approved during this window: `0`

## 6. Trades Rejected

- Simulated trades rejected during this window: `0`

## 7. Rejection Reason Breakdown

- No forward-window signals were processed, so there were no rejection reasons to classify.

## 8. Simulated Open Positions

- `0`

## 9. Closed Simulated Trades

- `0`

## 10. Win Rate

- `n/a`

## 11. Gross PnL

- `0.00`

## 12. Net PnL After Fees and Slippage

- `0.00`

## 13. Max Drawdown

- `0.00`

## 14. Biggest Win

- `n/a`

## 15. Biggest Loss

- `n/a`

## 16. Average Holding Time

- `n/a`

## 17. Top Performing Wallets

- `n/a` for this run because no simulated trades were opened.

## 18. Worst Performing Wallets

- `n/a` for this run because no simulated trades were opened.

## 19. Best Token Conditions

- `n/a` for this run because no simulated trades were opened.

## 20. Worst Token Conditions

- `n/a` for this run because no simulated trades were opened.

## 21. Any Safety Issues

- None observed in the forward run.
- The bot stayed in paper/simulated execution only.
- No live transaction path was exercised.

## 22. Any Audit-Log Gaps

- No forward-window audit events were generated because no qualifying signals were processed.
- This is not a live-execution gap, but it means forward performance coverage is still insufficient.

## 23. Any Runtime Errors

- None observed.
- The process booted successfully in forward mode and remained healthy until it was terminated after the timed observation window.

## 24. Final Recommendation

- Do not advance to tiny funded staging yet.
- Forward mode is safe, but this run did not produce enough signal/trade volume to judge performance.

## Tiny Staging Eligibility

Requirements:
- at least 7 days of forward testing, or enough meaningful signal coverage
- at least 20 simulated trades
- positive net PnL after modeled costs
- no unresolved ambiguous states
- no audit-log gaps
- no live-execution leakage
- emergency stop tested
- sell-all tested
- approval flow tested
- acceptable max drawdown
- not dependent on one lucky outlier trade

Current status:
- `TINY_STAGING_TEST_READY=false`

## Final Status

- `PAPER_MODE_READY=true`
- `FORWARD_TESTING_READY=true`
- `TINY_STAGING_TEST_READY=false`
- `LIVE_TRADING_READY=false`

## Forward Run Notes

- The forward session used paper execution only.
- The session completed without sending any live transaction.
- No whale signals arrived during the timed observation window, so performance metrics remain uninitialized.
