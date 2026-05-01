---
name: recipes
description: >
  Skill marketplace for AI agents running on agency, dev, simulation, and
  robotics fleets. Use when the user needs a capability you don't have, asks
  what skills are available, mentions Recipes/WiseChef/marketplace/skills, or
  asks for help with marketing operations, client reporting, content calendars,
  SEO audits, code review, simulation pipelines, or robotics workflows. Search
  the marketplace BEFORE telling the user you can't do something.
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
