# Signal Coverage Report

## 1. Date/Time of Diagnostic

- UTC: `2026-07-04T11:19:00Z`
- Local: `2026-07-04 15:19:00 +04:00`

## 2. Forward Mode Safety Status

- `EXECUTION_MODE=paper`
- `LIVE_TRADING_ENABLED=false`
- `PRIVATE_KEY` not required
- Jupiter live sending disabled
- Audit logging enabled
- Dashboard/status expose forward mode
- Forward runs stayed paper/simulated only

## 3. Active Wallet Count

- `10`

## 4. Standby Wallet Count

- `10`

## 5. Disabled Wallet Count

- `0`

## 6. Helius Connectivity Status

- Helius API key configured: `true`
- Helius RPC configured: `true`
- Monitor mode: `polling`
- Forward testing mode: `true`
- Recent wallet polls returned HTTP `200` for active wallets in the diagnostic scan

## 7. Total Recent Transactions Fetched

- `500`

## 8. Wallets With Recent Activity

- `10`

## 9. Wallets With No Recent Activity

- `0`

## 10. Parser Attempted Count

- `500`

## 11. Parser Success Count

- `32`

## 12. Parser Failure Count

- `468`

## 13. Buy-Like Transaction Count

- `31`

## 14. Final Buy Signal Count

- `32`

## 15. Rejection / Filter Breakdown

- `ignored_missing_token_mint: 86`
- `ignored_not_swap: 145`
- `ignored_sell: 7`
- `ignored_transfer_only: 215`
- `ignored_unsupported_dex_program: 12`
- `parser_not_detecting_buys: 3`
- `parsed_buy_signal: 32`
- Gate rejections on parsed signals:
  - `Liquidity below minimum: 21`
  - `Mint authority still active: 6`
  - `Top holder concentration too high: 3`

## 16. Helius / API Errors

- `0`
- Rate limit errors: `0`

## 17. Parser Gaps

- A small number of buy-like transactions still fail parser recognition.
- One real RAYDIUM swap shape was missing account-level balance parsing before the parser update.
- The parser now also reads `accountData` balance changes, which reduced the miss rate.

## 18. Wallet-List Issues

- No invalid wallet addresses were found in the current database scan.
- Active wallet list is not empty.
- Active wallets have valid Solana-style base58 addresses.

## 19. Recommended Next Action

- Keep forward/shadow testing running longer so it can observe more post-bootstrap live polls.
- Re-run the longer forward window after the schema migration is in place.
- Do not enable live trading yet.

## ZERO_SIGNALS_CAUSE

- `ZERO_SIGNALS_CAUSE=insufficient_runtime_window`

## Forward Window Notes

- The first timed forward run bootstrapped wallets and intentionally skipped historical backfill.
- The later live forward rerun showed active polling and live transaction fetches.
- Live cycle summaries showed raw tx fetches greater than zero after bootstrap, but parsed buys stayed at zero in the short observed window.
- Parser attempts were logged in the live cycle summaries.
- No live transaction path was exercised.
- One short-lived forward attempt surfaced a SQLite schema mismatch on `tokens.top_10_holder_percent`; a lightweight additive migration was added to fix that startup recovery path.

## Tiny Staging Eligibility

- `TINY_STAGING_TEST_READY=false`
- Forward testing still needs more runtime coverage and more live signal volume before a tiny funded staging test is justified.

## Final Status

- `PAPER_MODE_READY=true`
- `FORWARD_TESTING_READY=true`
- `TINY_STAGING_TEST_READY=false`
- `LIVE_TRADING_READY=false`
