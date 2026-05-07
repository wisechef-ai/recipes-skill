# Recipes — Skill Marketplace for AI Agents

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Install once. Give your AI agent marketplace awareness — and a native MCP server.**

`SKILL.md` is the entire client — a single file that teaches your agent the full
[Recipes](https://recipes.wisechef.ai) skill marketplace API. Once installed, your
agent can search, recall, install, fork, and execute any skill in the library
without further configuration.

For agents that speak the [Model Context Protocol](https://modelcontextprotocol.io)
(Claude Desktop, Cursor, Codex, OpenClaw, Hermes), Recipes also exposes a native
MCP server over HTTP+SSE — point your client at `https://recipes.wisechef.ai/api/mcp/sse`
and you get 9 tools in your agent without writing any glue code.

## What Is Recipes?

[Recipes](https://recipes.wisechef.ai) (by [WiseChef](https://wisechef.ai)) is the
**vertical skill marketplace for AI agents**. It ships curated, human-reviewed
skills across six verticals: **marketing, code, web-scraping, ops, sales,
sim-robotics**. One subscription → unlimited access to every skill in the library.

The platform was rebuilt in v7 (May 2026) around three primitives:

1. **MCP-first.** Native MCP server with 9 tools (search, install, recall, recipify,
   list_cookbook, carousel_today, doctor, subrecipe_resolve, seeker). Drops into any
   MCP-capable client.
2. **Cookbooks.** Group skills into reusable bundles. Owners can sync their cookbook
   to fleets via SSE live-sync — when you publish, every subscribed agent gets the
   new version within seconds.
3. **Hybrid recall.** `/api/recall` does semantic search (pgvector embeddings) + BM25
   keyword fallback. 100% top-3 recall on the canonical eval set.

## How to Install

### Option 1 — Native MCP server (recommended for MCP-capable clients)

Add to your Claude Desktop, Cursor, or other MCP-capable client config:

```json
{
  "mcpServers": {
    "recipes": {
      "url": "https://recipes.wisechef.ai/api/mcp/sse",
      "headers": { "x-api-key": "YOUR_RECIPES_API_KEY" }
    }
  }
}
```

You get 9 tools without installing any local files: `recipes_search`,
`recipes_install`, `recipes_recall`, `recipes_recipify`, `recipes_list_cookbook`,
`recipes_carousel_today`, `recipes_doctor`, `recipes_subrecipe_resolve`,
`recipes_seeker`.

> **Note:** the public MCP surface is `/api/mcp/*` (not the conventional `/mcp/*`).
> The Cloudflare zone in front of Recipes intercepts literal `/mcp/*` paths
> before they reach the origin, so we expose the same router under `/api/mcp/*`.
> The MCP protocol itself is unchanged.

### Option 2 — Meta-skill (for any agent that reads markdown)

Fetch `SKILL.md` directly into your agent's skills directory:

```bash
curl -fsSL https://raw.githubusercontent.com/wisechef-ai/recipes-skill/main/SKILL.md \
  -o skills/recipes/SKILL.md
```

Then tell your agent: *"Read skills/recipes/SKILL.md and follow it."*

### Option 3 — Hosted URL

Point your agent at:

```
https://recipes.wisechef.ai/skill
```

This URL always serves the latest released version of the meta-skill.

## Getting an API Key

1. Sign up at [recipes.wisechef.ai/signin](https://recipes.wisechef.ai/signin)
2. Choose a plan:
   - **Free** (€0) — browse the catalog, install 3 starter skills (Gif Search, ASCII Art, Maestro)
   - **Cook** (€20/mo) — full skill library, all 9 MCP tools, hybrid recall
   - **Operator** (€100/mo) — Cook + cookbooks (private bundles), forks, sub-recipes,
     live-sync to fleets, 30-day async onboarding, install on up to 5 personal machines
3. Copy your API key from the dashboard (format: `rec_<32 hex>`)
4. Set `RECIPES_API_KEY` in your agent's environment

Free skills work without authentication — no key needed to browse or install them.

> **Tier history:** the v7 release (May 2026) retired the legacy `studio` tier and
> aliased it to `operator`. If you're upgrading from a pre-v7 client, your existing
> studio subscription continues to work as operator without action.

## Should you install this?

If you already have a rich, curated skill library (e.g. a Hermes/Claude Code/Codex
setup with dozens of skills you trust), Recipes will overlap heavily with what you
already have. **Recommended pre-install prompt for an honest evaluation:**

> *"Install the recipes skill from recipes.wisechef.ai — but before you do, tell me:
> is it worth installing? Is it beneficial for us, given what we already have?"*

Have your agent answer that first. Honest answers vary by setup:

| Your situation | Verdict |
|---|---|
| Fresh agent, no skills | ✅ Install — one-command bootstrap to dozens of curated skills |
| Hermes/Claude Code with 50+ skills | ⚠️ Heavy overlap — only install if you need cross-vendor portability or one of the unique paid skills (Client Reporter, GA4+Meta Ads → PDF) |
| You run multiple agent stacks | ✅ Install — same skill works across Hermes, Claude Code, Codex, OpenClaw |
| You speak MCP | ✅ Install via MCP — zero local files, 9 tools, instant |

The free tier is **3 skills**: Gif Search, ASCII Art, Maestro (the v7 free
all-in-one starter, replaces the old `chef`). If you already have gif-search and
ascii-art locally, the unique value-add of free is just Maestro.

## API Contract

| Property | Value |
|---|---|
| Base URL | `https://recipes.wisechef.ai` |
| Auth header | `x-api-key` (NOT `Authorization: Bearer`) |
| Auth key format | `rec_<32 hex>` (rejected if prefix doesn't match) |
| Rate limit | 60 requests / minute |
| API contract version | `v1` |
| MCP endpoint | `https://recipes.wisechef.ai/api/mcp/sse` |

### Core endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/skills/search` | None | Search the catalog (q, category, vertical, sort) |
| GET | `/api/skills/install` | Optional | Download skill files (free or paid) |
| GET | `/api/skills/access` | Required | Check subscription access for a skill |
| GET | `/api/skills/trending` | None | Top skills this week/month |
| GET | `/api/carousel/today` | None | 7 daily curated picks |
| GET | `/api/recipes/{slug}` | Required | Full recipe detail |
| GET | `/api/api-library/{slug}` | None | API documentation pack |
| POST | `/api/recall` | Required | **Hybrid semantic + BM25 search** (v7 phase E) |
| POST | `/api/recipify` | Required | **Author/lint a skill** from raw content (v7 phase G) |
| GET POST | `/api/cookbooks` | Required | **Cookbook CRUD** (v7 phase B, operator+ tier) |
| GET | `/api/cookbooks/{id}/sync/sse` | Required | **Live-sync** subscriber stream (v7 phase D) |
| POST | `/api/forks/create` | Required (operator+) | Fork a public skill |
| POST | `/api/buckets/{id}/apply` | Required (operator) | Atomic install of a bucket |
| POST | `/api/intent-survey` | None | Submit Phase-0 intent response |
| POST | `/api/telemetry` | Required | Report usage events |

### MCP tools (via `/api/mcp/sse`)

| Tool | Purpose |
|---|---|
| `recipes_search` | Search the catalog |
| `recipes_install` | Install a skill (free or paid) |
| `recipes_recall` | Hybrid semantic search |
| `recipes_recipify` | Lint and classify a skill draft |
| `recipes_list_cookbook` | List cookbook contents |
| `recipes_carousel_today` | Today's 7 curated picks |
| `recipes_doctor` | Health check + diagnose |
| `recipes_subrecipe_resolve` | Resolve sub-recipe refs (operator-tier) |
| `recipes_seeker` | Cross-vendor skill diff (compare local vs upstream) |

Full reference: see [SKILL.md](SKILL.md) or [recipes.wisechef.ai](https://recipes.wisechef.ai).

## What's New in v7 (May 2026)

- 🆕 **MCP server** — native HTTP+SSE transport, 9 tools, drop-in for Claude Desktop/Cursor/etc.
- 🆕 **Hybrid recall** — `/api/recall` with pgvector + BM25 fallback, 100% top-3 on eval set
- 🆕 **Cookbooks** — private skill bundles with live-sync to subscribed fleets
- 🆕 **Recipify** — `/api/recipify` lints + auto-classifies a raw SKILL.md draft
- 🆕 **Skill Seeker** — cross-vendor diff tool to keep skills in sync between agents
- 🔄 **chef → maestro rename** — the v6 `chef` free skill is now `maestro` (301 redirect, 90-day TTL)
- 🔄 **Tier consolidation** — `studio` retired, aliased to `operator` (existing subs unaffected)
- 🔄 **Taxonomy unified** — 3 tiers (free/cook/operator), 10 canonical categories

## License

Apache 2.0 — see [LICENSE](LICENSE).

This repo is intentionally **public**. The meta-skill is the open, composable
layer; the marketplace content and API are the product.

## Links

- 🛒 Marketplace: [recipes.wisechef.ai](https://recipes.wisechef.ai)
- 🏢 WiseChef: [wisechef.ai](https://wisechef.ai)
- 🔌 MCP endpoint: `https://recipes.wisechef.ai/api/mcp/sse`
- 📖 Publish/request a skill: [recipes.wisechef.ai/request-skill](https://recipes.wisechef.ai/request-skill)
- 🐛 Issues: [github.com/wisechef-ai/recipes-skill/issues](https://github.com/wisechef-ai/recipes-skill/issues)
