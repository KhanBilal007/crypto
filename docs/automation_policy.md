# Limited Automation and Circuit Breakers

Stage 033 adds limited automation controls. Automation is disabled by default
and can only be enabled when evidence gates pass.

## Evidence Gates

Automation requires:

- paper-trading eligibility passed
- small-live results manually reviewed
- live P/L evidence accepted by policy
- drawdown below automation limit
- consecutive losses below automation limit
- no volatility shock
- exchange health is acceptable
- operator presence confirmed

Failure of any gate keeps automation disabled.

## Circuit Breakers

Automation stops immediately on:

- daily loss limit breach
- weekly loss limit breach
- max drawdown breach
- stale data
- exchange outage
- abnormal spread
- consecutive loss limit breach
- volatility shock
- model error
- risk error
- missing operator presence

When a breaker trips, `AutomationController` switches to kill-switch state and
`require_can_automate()` fails closed.

## Controls

Operators with the required permission can pause automation or activate the kill
switch. Resume uses the same evidence gates as enable. A kill switch cannot be
cleared by this stage.

## Operating Limits

Stage 033 does not submit orders, call exchanges, train models, approve risk, or
enable unsupervised live trading. Future automated submissions must still pass
through the supervised live gateway, manual/risk/preflight controls, and every
later circuit breaker.
