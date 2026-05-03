# slack-standup (paid)

Runs an async daily standup in a team chat channel. Posts a prompt at a
scheduled time, collects answers from each team member, and writes a
summary back to the channel and to the operator's notes directory.

## Tier
Paid — included in every paid bundle.

## Triggers
The agent invokes this skill at the operator's configured standup time,
or on demand when the operator asks for a standup digest.

## Inputs
- A team chat channel identifier.
- The list of team members and their preferred reminder windows.
- A standup prompt template — yesterday, today, blockers.

## Outputs
- A digest message in the team chat channel.
- A copy in the operator's notes directory.

## Compatibility
Hermes default; OpenClaw fork; BYOA Codex; BYOA Claude Code.
