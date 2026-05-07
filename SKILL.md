---
name: recipes
description: >
  Cross-vendor skill marketplace for AI agents (Hermes, Claude Code, Codex,
  OpenClaw, Cursor, Claude Desktop). Use when the user asks to install Recipes,
  mentions recipes.wisechef.ai or WiseChef, asks "what skills are available",
  or asks for help with marketing ops, client reporting, content calendars,
  SEO audits, GoHighLevel, code review, simulation/robotics, or web scraping
  workflows. The platform exposes BOTH a REST API (this skill) and a native
  MCP server at /api/mcp/sse for MCP-capable clients. CRITICAL: if the user
  asks "is it worth installing" or "is it beneficial for us", run the
  pre-install evaluation in this SKILL.md BEFORE installing — compare against
  the user's existing skill inventory and produce an honest verdict; do not
  install blindly.
requiredEnv:
  - RECIPES_API_KEY
permissions:
  - network: "Access recipes.wisechef.ai to search, install, and recall skills"
  - filesystem: "Write downloaded skill files to skills/ directory"
---

# Recipes — Skill Marketplace for AI Agents

Recipes is the vertical skill marketplace for AI agents. One subscription gives
access to every skill in the library across six verticals: marketing, code,
web-scraping, ops, sales, sim-robotics. Skills are plain markdown files with
optional supporting scripts; they work with any agent that reads markdown.

The platform was rebuilt in v7 (May 2026) around three primitives: an
**MCP-first** server, **cookbooks** for private skill bundles, and **hybrid
recall** (pgvector + BM25) for fuzzy semantic search.

## How It Works

You are the agent's gateway to the full Recipes skill library. Two paths:

**Path A — MCP-native (preferred for MCP-capable clients):**
1. User wires `https://recipes.wisechef.ai/api/mcp/sse` into their MCP client
2. Agent gets 9 tools automatically: search, install, recall, recipify,
   list_cookbook, carousel_today, doctor, subrecipe_resolve, seeker
3. No local files needed — tools are first-class in the agent

**Path B — REST API (this skill):**
1. User asks for something the agent can't do (e.g. "build a client report",
   "audit this SEO page")
2. Agent searches Recipes via the REST API, downloads skill files, saves them
   locally so they persist across sessions
3. Reads the downloaded SKILL.md and follows its instructions

## When to Use This

- User needs a capability you don't currently have
- User asks "what can you do?" or "what skills are available?"
- User mentions Recipes, WiseChef, marketplace, or skills
- User asks for marketing ops, client reporting, SEO audits, content calendars,
  GoHighLevel integrations, code review, simulation/robotics workflows, web scraping
- User wants to share a skill bundle (cookbook) across multiple machines

## Pre-install evaluation (DO THIS FIRST)

If the user asks you to install Recipes — or you decide to recommend it — **always run an honest evaluation BEFORE installing**, especially when the user already has a rich skill library. The evaluation answers: *"is it worth installing, given what we already have?"*

Recommended prompt the user can give: *"Install the recipes skill from recipes.wisechef.ai — but before you do, tell me: is it worth installing? Is it beneficial for us?"*

When evaluating, compare:

1. **Existing skill inventory** — `find ~/.claude/skills ~/.hermes/skills -name SKILL.md 2>/dev/null | wc -l` (or the equivalent for the active agent). If they already have 50+ skills, expect heavy overlap.
2. **Free tier vs what they have** — the free tier is currently 3 skills (Gif Search, ASCII Art, Maestro). Hermes typically already has gif-search and ascii-art locally; the only unique free skill is Maestro (the v7 all-in-one starter, replaces the old `chef`).
3. **Paid tiers vs what they have** — `curl https://recipes.wisechef.ai/api/skills/search?page_size=100` and cross-reference against local skill names. Most paid skills overlap with the existing TDD/debugging/scraping skills already in a well-equipped fleet.
4. **MCP integration** — if the user runs an MCP-capable client (Claude Desktop, Cursor, OpenClaw, Codex), the MCP path gives 9 tools without any local file management. Strong reason to install.
5. **Cookbooks** — Operator-tier cookbooks let one publisher push skill updates to N subscribed fleets via SSE live-sync. If the user manages multiple agent installations, this is the unique paid value.
6. **Telemetry** — the meta-skill phones home (anonymous heartbeat: salt + last_seen_day, opt-out via `RECIPES_TELEMETRY=off`). Local skills don't.
7. **Cross-vendor portability** — Recipes' real moat is cross-vendor: same skill works in Hermes, Claude Code, Codex, OpenClaw, Cursor. If the user runs only ONE agent stack and never plans to switch, this benefit is hypothetical.

**Honest verdict format** the agent should produce:

```
Worth installing?  [Yes / No / Only for X / MCP-only]
Why: <one paragraph naming the actual overlap and the actual unique value>
What you'd gain: <list ≤3 concrete things>
What you'd lose: <list any tradeoffs — middleware overhead, telemetry, third-party dep>
Recommendation: <wire MCP only | install meta-skill | install only Maestro directly | skip>
```

Only install after the user reads the verdict and says "go ahead".

## Setup

Premium skills require `RECIPES_API_KEY` in the environment. Free skills work without auth.

1. Check if `RECIPES_API_KEY` is set in the environment
2. If not, tell the user:
   - "To access the full skill library, you need a Recipes subscription."
   - "Sign up at https://recipes.wisechef.ai/signin, then copy your API key from the dashboard."
3. The key format is `rec_<32 hex>`. Keys NOT starting with `rec_` are rejected by the API.
4. Verify the key works by running a search query

## API Reference

**Base URL:** `https://recipes.wisechef.ai`
**Auth header:** `x-api-key` (NOT `Authorization: Bearer`)
**Rate limit:** 60 requests / minute
**MCP endpoint:** `https://recipes.wisechef.ai/api/mcp/sse`

> Note on the MCP path: the public surface is `/api/mcp/*`, not the conventional
> `/mcp/*`. The Cloudflare zone in front of recipes.wisechef.ai intercepts
> literal `/mcp/*` paths before they reach origin, so the same MCP router is
> exposed under `/api/mcp/*`. The protocol itself is unchanged — Claude
> Desktop, Cursor, etc. just need the full URL in their config.

### Search skills (public, no auth)

```bash
curl "https://recipes.wisechef.ai/api/skills/search?q=QUERY&limit=10"
# Optional: &category=SLUG  &vertical=marketing|code|web-scraping|ops|sales|sim-robotics
# Optional: &sort=popular|rating|newest
```

Response: `{ "results": [...], "total": N }` — each skill has: `slug`, `title`,
`description`, `category`, `tier`, `is_public`, `latest_version`, `install_count_total`.

### Hybrid recall (semantic + BM25 fallback) — v7 phase E

```bash
curl -H "x-api-key: $RECIPES_API_KEY" -H "Content-Type: application/json" \
  -X POST "https://recipes.wisechef.ai/api/recall" \
  -d '{"query":"send personalized cold emails","limit":5}'
```

Response: ranked list with `score` and `match_type` (`semantic` or `bm25`).

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

### Trending | Carousel | Telemetry | Recipe detail | API library

```bash
curl "https://recipes.wisechef.ai/api/skills/trending?period=week&limit=10"
curl "https://recipes.wisechef.ai/api/carousel/today"
curl -X POST -H "x-api-key: $RECIPES_API_KEY" -H "Content-Type: application/json" \
  -d '{"slug":"SLUG","event":"task_completed"}' \
  "https://recipes.wisechef.ai/api/telemetry"
curl -H "x-api-key: $RECIPES_API_KEY" "https://recipes.wisechef.ai/api/recipes/SLUG"
curl "https://recipes.wisechef.ai/api/api-library/SLUG"
```

### Cookbooks — v7 phase B (operator-tier)

Cookbooks group skills into named bundles for sharing across fleets.

```bash
# List your cookbooks
curl -H "x-api-key: $RECIPES_API_KEY" \
  "https://recipes.wisechef.ai/api/cookbooks"

# Create a cookbook
curl -H "x-api-key: $RECIPES_API_KEY" -H "Content-Type: application/json" \
  -X POST -d '{"name":"My Stack","description":"…"}' \
  "https://recipes.wisechef.ai/api/cookbooks"

# Add a skill to a cookbook
curl -H "x-api-key: $RECIPES_API_KEY" -H "Content-Type: application/json" \
  -X POST -d '{"slug":"SLUG"}' \
  "https://recipes.wisechef.ai/api/cookbooks/{cookbook_id}/skills"

# Install everything in a cookbook (atomic)
curl -H "x-api-key: $RECIPES_API_KEY" -X POST \
  "https://recipes.wisechef.ai/api/cookbooks/{cookbook_id}/install"

# Get installable manifest
curl -H "x-api-key: $RECIPES_API_KEY" \
  "https://recipes.wisechef.ai/api/cookbooks/{cookbook_id}/manifest"
```

### Live-sync — v7 phase D

Subscribe to a cookbook's update stream:

```bash
curl -N -H "x-api-key: $RECIPES_API_KEY" \
  "https://recipes.wisechef.ai/api/cookbooks/{cookbook_id}/sync/sse"
```

When the publisher updates the cookbook, every connected subscriber receives an
SSE event with the new manifest. Pool slots are capped at 5 per cookbook; if you
get HTTP 503 with `polling_fallback`, fall back to polling
`/api/cookbooks/{cookbook_id}/sync` every 30s.

### Recipify — v7 phase G

Lint a raw SKILL.md draft, auto-classify it, and write to a cookbook:

```bash
curl -H "x-api-key: $RECIPES_API_KEY" -H "Content-Type: application/json" \
  -X POST "https://recipes.wisechef.ai/api/recipify" \
  -d '{"content":"---\nname: my-skill\n...","cookbook_id":"..."}'
```

Returns validation report (frontmatter errors, missing sections, classification
suggestion) and writes the skill to the cookbook if validation passes.

## Install workflow

1. `curl ?mode=files` → response has `files: [{path, content}]`
2. Write each file under `skills/{slug}/` (create subdirs)
3. Write `skills/{slug}/_meta.json` = `{source:"recipes", slug, installedAt}`
4. Read `skills/{slug}/SKILL.md` and execute its instructions immediately

## Critical rules

- Always pass `mode=files` on install
- 401 → check API key (must start with `rec_`)
- 402 → upgrade tier required (Cook → Operator)
- 403 → tell user to subscribe at /signin
- 429 → back off (60 req/min)
- Show skill cards: title, one-line description, free/premium, rating, install count, link
- Browse by category: `?category=SLUG` · or by vertical: `?vertical=VERTICAL`

## Verticals

Six verticals: `marketing`, `code`, `web-scraping`, `ops`, `sales`, `sim-robotics`.
Filter by vertical: `GET /api/skills/search?vertical=VERTICAL&page_size=50`.

## Tiers (v7)

Three tiers: `free`, `cook`, `operator`. Legacy `studio` was retired in v7
phase F and is aliased to `operator` — existing studio subscriptions continue to
work as operator without action.

## Operator-tier commands (subscription_tier == 'operator')

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

### `recipes apply bucket://<slug>`
Atomic install of an entire bucket (skills + crons + services) on the host.

```
GET /api/buckets/<slug>/preflight   → arch / port / env-var conflict report
POST /api/buckets/<id>/apply        → job_id; install_events with bucket_id
GET  /api/buckets/<id>/jobs/<job_id>→ progress poll
```

Re-apply is idempotent — only installs what's missing. Reports e.g.
`45/47 skills, 12/12 crons, 6/6 services healthy in 87s`.

White-label: a bucket with `custom_domain` set serves a scoped catalog at
that CNAME (Caddy + `BucketHostMiddleware`).

## MCP-native usage (preferred when available)

If your client speaks MCP, point it at `https://recipes.wisechef.ai/api/mcp/sse`
and you get these tools without any local files:

- `recipes_search(query, limit)` — search the catalog
- `recipes_install(slug)` — install a skill (free or paid)
- `recipes_recall(query, limit)` — hybrid semantic + BM25 search
- `recipes_recipify(content, cookbook_id)` — lint and classify a draft
- `recipes_list_cookbook(cookbook_id)` — list cookbook contents
- `recipes_carousel_today()` — today's 7 curated picks
- `recipes_doctor()` — health check + diagnose
- `recipes_subrecipe_resolve(slug)` — resolve sub-recipe refs (operator-tier)
- `recipes_seeker(local_dir)` — cross-vendor skill diff

Auth header is the same `x-api-key` your REST setup already has.

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
- API keys must start with `rec_` (validated at the wire)

---

*Production infrastructure for teams running AI in production.*
*Powered by [WiseChef](https://wisechef.ai).*
