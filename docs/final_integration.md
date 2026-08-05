# Final Integration

Stage 073 ties the completed ABTP foundations into one controlled operating
picture. It does not add new trading logic, real exchange connectors, external
provider calls, or unsupervised live execution. The purpose is to verify that
the existing modules can be installed, tested, audited, operated, and stopped
under minimum-risk controls.

## Integrated Lifecycle

The intended lifecycle is:

```text
market data -> quality/normalization -> indicators -> features
  -> prediction/regime/context intelligence -> strategy signal
  -> risk decision -> portfolio context -> paper-safe execution
  -> analytics/governance/research/decision intelligence/command center
  -> paper runner simulation loop
  -> paper evaluation gate
  -> audit events -> metrics/logs -> alerts -> dashboard/API
```

Every executable order path must pass through the Risk Management Engine before
execution. Current production readiness is limited to deterministic research,
backtesting, paper trading, and supervised-live contract validation with fake or
adapter-provided inputs. Live trading remains disabled by default.

## Integration Boundaries

- Data modules are read-only and call exchanges only through adapter contracts.
- Indicator, feature, AI, regime, and strategy modules emit values, context, or
  non-executable signals.
- Risk modules produce explicit allow/reject decisions.
- Execution modules accept only risk-approved `OrderIntent` objects.
- Paper trading simulates fills locally and never submits real orders.
- The paper runner processes only deterministic paper cycles and records
  blocked cycles when command, risk, stop-loss, stale-data, kill-switch,
  exchange-health, capital-protection, or portfolio-loss gates fail.
- The paper evaluation gate reviews paper evidence only and cannot enable live
  trading, approve risk, create orders, or change strategy/risk rules.
- Supervised live gateway contracts require explicit live flags, preflight, a
  manual approval token, and an approved risk decision.
- Automation contracts can pause or stop future automated use; they do not
  place orders.
- Notifications, logs, metrics, and audit helpers must not expose secrets.

## Readiness Evidence

A controlled release candidate must show:

- A fresh install can run the full verification gate.
- Paper flow produces auditable cycles and dashboard/API status.
- Risk rejection and stale/degraded data paths fail closed.
- Security smoke checks reject unsafe exchange permissions and plaintext secret
  storage.
- Database migrations can recreate the local schema.
- Append-only audit records can be backed up and restored for reconstruction.
- Intelligence, research, governance, confidence, and decision-hub reports are
  explainable and remain advisory only.
- The simple paper command center maps evidence into BUY REVIEW, HOLD, AVOID,
  or PROTECT CAPITAL without creating executable actions.
- Paper runner sessions produce deterministic summaries for executed, skipped,
  no-signal, and risk-rejected cycles without enabling live trading.
- Paper evaluation reports show whether to remain paper, make paper settings
  more conservative, pause for review, or prepare only a future supervised
  tiny-live proposal review.
- Incident response and kill-switch procedures are documented and understood.

## Operating Limits

ABTP does not guarantee profit. Cryptocurrency markets are volatile, and only
risk capital should ever be used. This stage does not certify unsupervised live
trading. Any later production live release must keep `SAFE_MODE=true` until an
operator explicitly changes configuration, confirms live risk, supplies separate
least-privilege credentials, and passes all release checklist gates.
