---
name: recipes
description: >
  Cross-vendor skill marketplace for AI agents (Hermes, Claude Code, Codex,
  OpenClaw). Use when the user asks to install Recipes, mentions
  recipes.wisechef.ai or WiseChef, asks "what skills are available", or asks
  for help with marketing ops, client reporting, content calendars, SEO audits,
  GoHighLevel, code review, or simulation/robotics workflows. CRITICAL: if the
  user asks "is it worth installing" or "is it beneficial for us", run the
  pre-install evaluation in the SKILL.md BEFORE installing — compare against
  the user's existing skill inventory and produce an honest verdict; do not
  install blindly.
requiredEnv:
  - RECIPES_API_KEY
permissions:
  - network: "Access recipes.wisechef.ai to search and download skills"
  - filesystem: "Write downloaded skill files to skills/ directory"
---

# Recipes — Skill Marketplace for AI Agents

Recipes is the skill marketplace for AI agents. One subscription gives access to
every skill in the library. Skills are plain markdown files with optional
supporting scripts; they work with any agent that reads markdown.

## How It Works

You are the agent's gateway to the full Recipes skill library.

1. User asks for something the agent can't do (e.g. "build a client report", "audit this SEO page")
2. Search Recipes for matching skills
3. Download the skill files via the API
4. Save them locally so they persist across sessions
5. Read SKILL.md and follow its instructions

## When to Use This

- User needs a capability you don't currently have
- User asks "what can you do?" or "what skills are available?"
- User mentions Recipes, WiseChef, marketplace, or skills
- User asks for marketing ops, client reporting, SEO audits, content calendars,
  GoHighLevel integrations, code review, simulation pipelines, or robotics workflows

## Pre-install evaluation (DO THIS FIRST)

If the user asks you to install Recipes — or you decide to recommend it — **always run an honest evaluation BEFORE installing**, especially when the user already has a rich skill library. The evaluation answers: *"is it worth installing, given what we already have?"*

Recommended prompt the user can give: *"Install the recipes skill from recipes.wisechef.ai — but before you do, tell me: is it worth installing? Is it beneficial for us?"*

When evaluating, compare:

1. **Existing skill inventory** — `find ~/.claude/skills ~/.hermes/skills -name SKILL.md 2>/dev/null | wc -l` (or the equivalent for the active agent). If they already have 50+ skills, expect heavy overlap.
2. **Free tier vs what they have** — the free tier is currently 3 skills (Gif Search, Ascii Art, Client Reporter). Hermes typically already has gif-search and ascii-art locally; the only unique free skill is Client Reporter (GA4 + Meta Ads → PDF).
3. **Paid tiers vs what they have** — `curl https://recipes.wisechef.ai/api/skills/search?page_size=100` and cross-reference against local skill names. Most paid skills overlap with the existing TDD/debugging/scraping skills already in a well-equipped fleet.
4. **Install counts** — every skill currently shows "0 installs" (beta). No community validation yet.
5. **Telemetry** — the meta-skill phones home (anonymous heartbeat: salt + last_seen_day, opt-out via `RECIPES_TELEMETRY=off`). Local skills don't.
6. **Cross-vendor portability** — Recipes' real moat is cross-vendor: same skill works in Hermes, Claude Code, Codex, OpenClaw. If the user runs only ONE agent stack and never plans to switch, this benefit is hypothetical.

**Honest verdict format** the agent should produce:

```
Worth installing?  [Yes / No / Only for X]
Why: <one paragraph naming the actual overlap and the actual unique value>
What you'd gain: <list ≤3 concrete things>
What you'd lose: <list any tradeoffs — middleware overhead, telemetry, third-party dep>
Recommendation: <install | install only Client Reporter directly via curl | skip>
```

Only install after the user reads the verdict and says "go ahead".

## Setup

Premium skills require `RECIPES_API_KEY` in the environment. Free skills work without auth.

1. Check if `RECIPES_API_KEY` is set in the environment
2. If not, tell the user:
   - "To access the full skill library, you need a Recipes subscription."
   - "Sign up at https://recipes.wisechef.ai/signin, then copy your API key from the dashboard."
3. Verify the key works by running a search query

## API Reference

**Base URL:** `https://recipes.wisechef.ai`
**Auth header:** `x-api-key` (NOT `Authorization: Bearer`)
**Rate limit:** 60 requests / minute

### Search skills (public, no auth)

```bash
curl "https://recipes.wisechef.ai/api/skills/search?q=QUERY&limit=10"
# Optional: &category=SLUG  &sort=popular|rating|newest
```

Response: `{ "skills": [...], "total": N }` — each skill has: `slug`, `name`,
`description`, `category`, `free`, `rating`, `installs`.

### Download a skill — always use `mode=files`

```bash
# Free skill (no auth needed)
curl "https://recipes.wisechef.ai/api/skills/install?slug=SLUG&mode=files"

# Premium skill (API key required)
curl -H "x-api-key: $RECIPES_API_KEY" \
  "https://recipes.wisechef.ai/api/skills/install?slug=SLUG&mode=files"
```

Response:
```json
{
  "skill": { "slug": "...", "name": "...", "version": "1.0.0" },
  "files": [
    { "path": "SKILL.md", "content": "---\nname: ..." },
    { "path": "scripts/run.sh", "content": "#!/bin/bash..." }
  ]
}
```

### Check access before installing

```bash
curl -H "x-api-key: $RECIPES_API_KEY" \
  "https://recipes.wisechef.ai/api/skills/access?skill=SLUG"
```

### Trending (public) | Today's carousel (public) | Telemetry | Full recipe | API library

```bash
curl "https://recipes.wisechef.ai/api/skills/trending?period=week&limit=10"
curl "https://recipes.wisechef.ai/api/carousel/today"
curl -X POST -H "x-api-key: $RECIPES_API_KEY" -H "Content-Type: application/json" \
  -d '{"slug":"SLUG","event":"task_completed"}' \
  "https://recipes.wisechef.ai/api/telemetry"
curl -H "x-api-key: $RECIPES_API_KEY" "https://recipes.wisechef.ai/api/recipes/SLUG"
curl "https://recipes.wisechef.ai/api/api-library/SLUG"
```

## Install workflow

1. `curl ?mode=files` → response has `files: [{path, content}]`
2. Write each file under `skills/{slug}/` (create subdirs)
3. Write `skills/{slug}/_meta.json` = `{source:"recipes", slug, installedAt}`
4. Read `skills/{slug}/SKILL.md` and execute its instructions immediately

## Critical rules

- Always pass `mode=files` on install
- 403 → tell user to subscribe at /signin · 401 → check API key · 429 → back off (60 req/min)
- Show skill cards: name, one-line desc, free/premium, rating, install count, link
- Browse by category: `?category=SLUG` · or by vertical (below)
## Verticals

Six verticals: marketing, code, web-scraping, ops, sales, sim-robotics.
Filter by vertical: `GET /api/skills/search?vertical=VERTICAL&page_size=50`.

## Operator-tier commands (subscription_tier in [operator, studio])

### `recipes fork <slug>`
Fork a public skill into your private library.
```
POST /api/forks/create  {source_slug, name, readme?}
→ 201 {id, slug, source_slug, ...}
```
402 if Cook-tier; upgrade required.

### `recipes publish-fork <name> [--bump=patch|minor|major]`
Tarball the local fork directory and push a new version.
```
POST /api/forks/<id>/version (multipart: tarball, semver, changelog)
→ 201 {id, semver, checksum_sha256, tarball_size_bytes}
```

### `recipes install-fork <name> [--into=<dir>]`
Install the latest version of your fork (HMAC-signed URL, 5-min TTL).
```
GET /api/forks/<id>/install → {tarball_url, checksum_sha256, expires_at}
```

`recipes list` shows a "Your forks" section. `recipes search` tags fork
results with `[fork]`.

## Studio-tier commands (subscription_tier == studio)

### `recipes apply bucket://<slug>`
Atomic install of an entire bucket (skills + crons + services) on the host.

```
GET /api/buckets/<slug>/preflight   → arch / port / env-var conflict report
POST /api/buckets/<id>/apply        → job_id; install_events with bucket_id
GET  /api/buckets/<id>/jobs/<job_id>→ progress poll
```

Re-apply is idempotent — only installs what's missing. Reports e.g.
`45/47 skills, 12/12 crons, 6/6 services healthy in 87s`.

White-label: a Studio bucket with `custom_domain` set serves a scoped
catalog at that CNAME (Caddy + `BucketHostMiddleware`).

## Auto-improve telemetry (opt-in for free tier, opt-out for paid)

Each skill invocation can be wrapped by `recipes-auto-improve`. On failure:

- captures stack-trace top frames (sha256 normalized)
- env fingerprint (os/arch/cuda/ram_gb/skill_version)
- POSTs to `/api/feedback/incident` with the user's API key
- NO $HOME paths, NO env values, NO file content (regex-audited at the wire)

Server clusters reports across the fleet, drafts patches, runs canary
rollouts. Public payload examples + transparency log at
`https://recipes.wisechef.ai/docs/auto-improve-telemetry`.

## Single-publisher catalog

Recipes is curated by WiseChef. We don't take submissions — we take
**requests**. Tell us what's broken in your fleet and we'll ship a skill
that fixes it: `https://recipes.wisechef.ai/request-skill`.

## Security

- All skills are reviewed before publication
- Skills are plain text, inspectable by anyone
- User credentials stay on the user's machine and are never sent to Recipes
- Recipes only serves skill files; the agent talks directly to third-party APIs

---

*Production infrastructure for teams running AI in production.*
*Powered by [WiseChef](https://wisechef.ai).*
