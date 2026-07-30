# Governance & Compliance Engine

Stage 068 adds operational governance and policy enforcement. It produces
audit-ready compliance reports from supplied approval records, configuration
version records, and manual override logs.

The engine does not call exchanges, call providers, create signals, approve
risk, create order intents, submit orders, cancel orders, or execute trades.

## Inputs

`GovernanceReviewInput` contains:

- strategy approval records
- model approval records
- configuration version records
- manual override logs
- required active strategy IDs
- required active model IDs
- active configuration keys
- pending manual override IDs
- data-quality status and source references

Configuration records contain non-secret identifiers, versions, and checksums.
They must never contain plaintext credentials or secret values.

## Outputs

`build_governance_review_report` emits a `GovernanceReviewReport` with:

- compliance status
- approval history
- configuration versions
- manual override logs
- policy violations
- quality flags
- source references
- audit payload

Compliance status can be `compliant`, `review_required`, or `blocked`.

## Operating Limits

- No profit is guaranteed.
- Governance approval does not bypass the Risk Management Engine.
- Missing strategy approval, missing model approval, missing configuration
  versioning, unapproved configuration versions, unlogged manual overrides,
  revoked approvals, or rejected evidence fail closed.
- Reports are advisory compliance context only and cannot perform live changes.
- Tests use deterministic fixtures and require no real credentials, provider
  access, exchange access, or network calls.
