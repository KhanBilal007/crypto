# Trader Review Handoff

This document explains how to share ABTP with traders for paper-mode review.
It is not approval for live trading and it is not a profitability claim.

## Review Scope

ABTP can be shown for controlled paper-mode review when the dashboard readiness
gate reports `paper_demo_ready=true`. The correct scope is:

- paper-mode user experience review
- strategy evidence review
- risk and safety review
- paper order-ticket workflow review
- report and ledger audit review

The correct scope is not:

- live-capital trading
- performance marketing
- exchange execution approval
- unmanaged automation
- profitability claims

## Before Sharing

Start the dashboard with paper settings only:

```powershell
.\.venv\Scripts\python.exe -m abtp.dashboard.paper_server
```

Open the local dashboard:

```text
http://127.0.0.1:8765
```

Confirm the top badges show:

- `PAPER MODE`
- `SAFE MODE`
- `LIVE OFF`

Open the Readiness Gate and confirm:

- paper demo ready is true
- live capital ready is false
- profitability claim is none
- blockers are empty

If SQLite persistence is expected, run the dashboard with `ABTP_PAPER_DB_PATH`
configured so trader actions are preserved in the local paper ledger.

## Export Packet

Use these local dashboard exports during review:

- `/paper-report`
- `/paper-transactions.csv`
- `/trader-feedback.csv`
- `/trader-handoff.md`
- `/trader-evidence.json`

The trader handoff export summarizes the current readiness verdict, proof
points, blockers, warnings, current paper state, and suggested reviewer
questions. The evidence JSON export contains machine-readable readiness,
portfolio, Strategy Lab, Advanced Trader, transaction, and safety sections for
review tools or audit scripts. The feedback CSV export is a simple punch-list
format for sorting reviewer corrections by category, severity, and status.

## What Traders Should Check

Ask reviewers to inspect:

- whether Beginner view explains BUY, HOLD, SELL, and blocked actions clearly
- whether Advanced Trader view has enough market, chart, order-flow, position,
  journal, and risk evidence
- whether Strategy Lab shows required evidence and module routing clearly
- whether paper order ticket controls can be mistaken for live trading
- whether stop loss, target, sizing, and risk/reward are visible before paper
  approval
- whether reports contain enough information to reconstruct a paper decision

Record reviewer corrections in the dashboard's Trader Feedback panel. Feedback
items are local, paper-only records with reviewer role, category, severity,
summary, recommendation, status, resolution, and resolved timestamp.

## Required Warnings

Keep these warnings visible in any demo:

- ABTP remains paper-only.
- Live trading is disabled.
- This is not financial advice.
- This does not claim profitability.
- Longer paper testing and trader review are required before any separate
  supervised-live proposal.

## Feedback To Capture

Capture feedback in these categories:

- confusing terms or labels
- missing trader controls
- missing risk evidence
- missing market data
- missing strategy evidence
- unclear actionability or approval state
- report/audit gaps
- UI layout issues on the review machine

The dashboard supports these structured categories directly: UI, risk,
strategy, market data, order ticket, reporting, and missing feature. Severity
can be low, medium, high, or blocker. Open blocker-severity feedback blocks the
paper-demo readiness verdict until the item is closed or resolved. Closing a
blocker requires a resolution note so the handoff packet and feedback CSV show
why readiness was restored.

Do not convert feedback into live-trading changes without a separate
supervised-live design and approval stage.
