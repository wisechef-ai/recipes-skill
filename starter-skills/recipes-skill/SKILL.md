# recipes-skill (entry meta-skill — free forever)

`recipes-skill` is the entry point. Install it once, and your agent gains
marketplace awareness — it can search, install, and run any other Recipes
skill on demand without further configuration.

## Tier
Free — install with no API key. This skill ships in every starter bundle.

## Triggers
The agent loads this skill whenever the operator asks to install, search,
or update a Recipes skill, or whenever a workflow references a skill slug
the agent does not yet have.

## Behaviour
1. Read the marketplace catalog.
2. Resolve a slug to a download URL and SHA-256.
3. Verify the signed receipt before installing.
4. Drop the skill into the agent's local skills directory.
5. Reload the agent so the new skill is available.

## Compatibility
Hermes default; OpenClaw fork; BYOA Codex; BYOA Claude Code.

## Notes
This is the smallest skill that ships in every starter pack. It is the
entry hook for the free-forever ladder — once installed, the operator can
opt into any other curated skill from the catalog.
