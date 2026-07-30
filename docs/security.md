# Security Hardening

Stage 031 adds security contracts for secret redaction, least-privilege exchange
keys, role authorization, and dependency audit notes.

## Secrets

`src/abtp/security/secrets.py` provides:

- display-safe secret masks
- non-secret `SecretFingerprint` values
- `EncryptedSecretRef` metadata for externally encrypted secrets
- rejection of payloads with secret-like keys

ABTP still stores only secret references or fingerprints, never plaintext
exchange credentials.

## Exchange API Permissions

`src/abtp/security/permissions.py` validates declared exchange key scopes.
Trading keys must be least-privilege:

- read scope required
- trade scope required
- IP allowlist required by default
- withdrawal, transfer, margin, futures, options, and admin scopes rejected

Withdrawal capability is unsupported in Stage 031 and fails validation.

## Authorization

`src/abtp/security/auth.py` defines roles and permissions for future adapters.
Audit access requires explicit audit permission. Viewer roles cannot control
paper trading or read audit trails; admin has all local permissions.

## Dependency Notes

`src/abtp/security/dependencies.py` records local dependency audit notes without
network calls. Reports can mark dependencies as ok, review, or blocked.

Stage 031 does not run an online vulnerability scan. It provides deterministic
contracts so future CI or operations stages can attach scanner results.

## Operating Limits

This stage does not add live trading, real exchange calls, credential storage,
external identity providers, or network dependency scanning. Live execution
remains disabled.
