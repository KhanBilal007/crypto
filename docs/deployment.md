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

## Database

The repository supports local SQLite migrations through `abtp.db`. A release
candidate must be able to recreate the schema from migrations and reconstruct
decision trails from append-only audit records. Backups may use SQLite file
copies or dumps while the process is stopped.

## Smoke Checks

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
