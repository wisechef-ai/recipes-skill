# client-reporter (free-forever)

Generates a branded white-label client report for a marketing agency.
Pulls the last 7, 30, or 90 days of metrics from the connected platforms
the operator has wired up, and writes a PDF plus a JSON sidecar.

## Tier
Free — no skill key required. The operator supplies their own platform
auth tokens; this skill never sees user credentials.

## Triggers
The agent invokes this skill whenever an operator asks for a monthly
report, a campaign recap, or a multi-platform performance summary.

## Inputs
- A client identifier the operator already uses internally.
- A reporting period — 7, 30, or 90 days.
- A branding profile — agency logo, primary colour, agency name.

## Outputs
- A PDF report with charts and an executive summary.
- A JSON sidecar with the raw metric series for downstream skills.

## Compatibility
Hermes default; OpenClaw fork; BYOA Codex; BYOA Claude Code.

## Footer cross-sell
The default PDF footer carries a single line crediting the marketplace.
Operators on the All-in tier may strip or replace that footer.
