# Deployment

Stage 034 deployment means a controlled local or internal release candidate. It
does not mean unsupervised live trading approval.

## Environment

Required safe defaults:

```text
SAFE_MODE=true
ABTP_PROFILE=paper
ABTP_TRADING_MODE=paper
ABTP_ENABLE_LIVE_TRADING=false
ABTP_ENABLE_PAPER_TRADING=true
ABTP_MARKET_DATA_SOURCE=binance
```

Live mode, if reviewed in a later stage, requires separate environment
variables for live credentials, manual confirmation, least-privilege API scopes,
IP allowlisting, supervised preflight, and approval evidence. Do not store
plaintext secrets in files, logs, metrics, audit rows, or database records.

## Release Steps

1. Install dependencies in a clean virtual environment.
2. Run the full verification gate.
3. Apply SQLite migrations to the target local database.
4. Confirm `.env.example` and local environment preserve safe defaults.
5. Review `docs/production_release_checklist.md`.
6. Review `docs/incident_response.md`.
7. Perform the restore drill from a database backup or SQLite dump.
8. Confirm notification channels are configured for the intended environment.
9. Record operator acknowledgement that profit is not guaranteed and only risk
   capital may be used.

## Dashboard Access Boundary

The dashboard server now refuses non-loopback binding. Keep it on
`127.0.0.1` behind a separately configured HTTPS reverse proxy for remote use;
an existing deployment using `--host 0.0.0.0` must be adjusted before rollout.
Do not expose its HTTP port directly. Configure all of:

- `ABTP_DASHBOARD_USERNAME`
- `ABTP_DASHBOARD_PASSWORD` (at least 20 characters; inject securely, never commit)
- `ABTP_DASHBOARD_PUBLIC_ORIGIN` (exact HTTPS origin, with no trailing slash/path)

The browser receives an HTTP Basic authentication challenge. The proxy must
preserve the public Host and Authorization headers, terminate trusted HTTPS,
and restrict direct access to the upstream. The application verifies Host,
authentication, JSON content type, request size, and cross-origin controls.
Local loopback-only use remains available without credentials. These checks
do not replace TLS, firewall rules, login rate limiting, or server hardening.
No production proxy or certificate configuration has been changed or verified;
the deployed IP's certificate still failed trusted validation on October 5.

## Database

The repository supports local SQLite migrations through `abtp.db`. A release
candidate must be able to recreate the schema from migrations and reconstruct
decision trails from append-only audit records. Backups may use SQLite file
copies or dumps while the process is stopped.

## Smoke Checks

Normal dashboard operation uses real Binance spot market data. Demo input is
only for explicitly selected offline tests. A Binance startup failure must not
silently substitute sample candles. The server loop polls every 15 seconds even
with no browser open; strategies evaluate closed hourly candles. Run one server
process per paper ledger and supervise it for restart after failures.

Before updating a running trial, follow the backup and validation steps in
[the September 10 audit](profitability_audit_2026_09_10.md). Existing balances are
preserved; cumulative wallet metrics may include earlier strategy versions.

Deployment smoke is satisfied when:

- default settings cannot execute live orders
- unsafe live settings fail validation or preflight
- paper dashboard/API status can be produced from deterministic inputs
- audit rows remain append-only
- a backup/restore drill preserves audit reconstruction

## Rollback

Rollback to a previous release by stopping all running jobs, keeping
`SAFE_MODE=true`, preserving the current database backup, restoring the previous
application version, re-running migrations and verification, and validating that
paper/API/audit smoke tests pass before resuming any controlled operation.
