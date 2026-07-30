# Dynamic Asset Universe Manager

Stage 064 adds an advisory dynamic asset universe manager. It selects separate
research, paper, and live candidate universes from supplied asset evidence
instead of relying only on a fixed coin list.

The manager does not scan exchanges, fetch market data, fetch fundamentals,
call providers, call blockchains, create signals, approve risk, create order
intents, submit orders, cancel orders, or execute trades.

## Inputs

`AssetUniverseCandidate` describes one asset candidate with:

- asset symbol
- market-cap score
- liquidity score
- exchange availability
- security score
- governance score
- validation status
- data-quality status
- source references

Scores are normalized from `0` to `1`. Candidates are supplied by deterministic
fixtures or future upstream modules. Duplicate symbols are deduplicated by the
latest `observed_at` timestamp.

## Outputs

`build_dynamic_asset_universe` emits an `AssetUniverseReport` with:

- approved research universe
- approved paper universe
- approved live universe
- watchlist
- excluded assets with reasons
- candidate decisions, scores, ranks, quality flags, and source references
- audit payload

Live universe inclusion requires trusted quality, sufficient score, and explicit
candidate validation by default. Degraded candidates may enter research review
only and are not approved for paper or live universes.

## Operating Limits

- No profit is guaranteed.
- Universe output is advisory configuration context only.
- Universe changes cannot bypass the Risk Management Engine.
- Approved assets do not imply permission to trade.
- Live trading remains disabled unless later supervised live gates explicitly
  approve execution.
- Rejected, stale, low-liquidity, weak-security, weak-governance, unavailable,
  or under-threshold assets are excluded with reasons.
- Tests use deterministic fixtures and require no real exchange credentials,
  provider credentials, or network access.
