# gohighlevel-toolkit (paid)

A toolkit of common operations against the operator's marketing
automation suite. Wraps contact sync, pipeline updates, calendar
bookings, and campaign triggers behind a single skill so that other
skills can call into the suite without each re-learning the API surface.

## Tier
Paid — included in every paid bundle.

## Triggers
The agent invokes this skill whenever another skill needs to read or
write to the operator's marketing automation suite.

## Inputs
- A subaccount identifier.
- An operation name — sync contacts, move pipeline stage, book slot.
- An operation payload — schema depends on the operation.

## Outputs
- The result of the operation — created records, updated stages, or a
  structured error the calling skill can surface to the operator.

## Compatibility
Hermes default; OpenClaw fork; BYOA Codex; BYOA Claude Code.
