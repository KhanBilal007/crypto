# Operations Security

Stage 031 operational security defaults are conservative and fail closed.

## Credential Handling

- Use separate live credential environment variables.
- Do not commit `.env` files containing real credentials.
- Use trading-only exchange keys.
- Disable withdrawal, transfer, margin, futures, options, and admin scopes.
- Configure IP allowlists where the exchange supports them.
- Store encrypted secrets outside ABTP runtime objects and pass only references.

## Access Control

Map users or services into Stage 031 roles:

- `viewer`: inspect paper state only
- `operator`: control paper mode
- `risk_manager`: manage future risk operations
- `auditor`: read audit trails
- `admin`: local administrative permissions

Production adapters must authenticate users before constructing
`AuthenticatedPrincipal` objects.

## Dependency Handling

Dependency audit notes are local records in this stage. Future CI should feed
scanner output into `DependencyAuditReport` and block deployments on blocked
findings.

## Incident Response

When unsafe scopes, missing IP allowlists, secret-like payloads, or blocked
dependency notes are detected, ABTP should fail closed and keep trading disabled
until an operator fixes the configuration.
