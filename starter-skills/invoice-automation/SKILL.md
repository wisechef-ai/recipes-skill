# invoice-automation (paid)

Generates and sends recurring client invoices on the operator's billing
cadence. Pulls billable line items from the operator's tracker, applies
rate cards, and queues invoices through the operator's billing provider.

## Tier
Paid — included in every paid bundle.

## Triggers
The agent invokes this skill on the operator's monthly billing day, or
on demand when the operator asks for a fresh invoice.

## Inputs
- A client identifier.
- A billing period.
- A rate card profile — fixed retainer, hourly, or hybrid.

## Outputs
- A draft invoice queued in the operator's billing provider.
- A copy in the operator's records directory.

## Compatibility
Hermes default; OpenClaw fork; BYOA Codex; BYOA Claude Code.
