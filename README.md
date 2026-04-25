# Recipes Meta-Skill

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Install once. Give your AI agent marketplace awareness.**

`SKILL.md` is the entire client — a single file that teaches your agent the full
[Recipes](https://recipes.wisechef.ai) skill marketplace API. Once installed, your
agent can search, download, and execute any skill in the library without further
configuration.

## What Is Recipes?

[Recipes](https://recipes.wisechef.ai) (by [WiseChef](https://wisechef.ai)) is a
vertical skill marketplace for AI agents. It ships curated, human-reviewed skills
for marketing agencies — client reporting, SEO audits, content calendars, ad
campaign management — with horizontal categories (dev tools, code review,
simulation, robotics) following in subsequent releases.

One subscription → unlimited access to every skill in the library.

## How to Install

### Option 1 — Fetch directly into your agent's skills directory

```bash
curl -fsSL https://raw.githubusercontent.com/wisechef-ai/recipes-skill/main/SKILL.md \
  -o skills/recipes/SKILL.md
```

Then tell your agent: "Read skills/recipes/SKILL.md and follow it."

### Option 2 — Reference the hosted URL

Point your agent at:

```
https://recipes.wisechef.ai/skill
```

This URL always serves the latest released version of the meta-skill.

### Option 3 — Manual install via SKILL.md URL

If your agent supports direct skill URLs:

```
https://raw.githubusercontent.com/wisechef-ai/recipes-skill/main/SKILL.md
```

## Getting an API Key

1. Sign up at [recipes.wisechef.ai/signin](https://recipes.wisechef.ai/signin)
2. Choose a plan: **Cook** ($24.99/mo), **Operator** ($79/mo), or **Studio** ($249/mo)
3. Copy your API key from the dashboard
4. Set `RECIPES_API_KEY` in your agent's environment

Free skills work without authentication — no key needed to browse or install them.

## API Contract

| Property | Value |
|---|---|
| Base URL | `https://api.recipes.wisechef.ai` |
| Auth header | `x-api-key` (NOT `Authorization: Bearer`) |
| Rate limit | 60 requests / minute |
| API contract version | `v1` |

### Core endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/skills/search` | None | Search the catalog |
| GET | `/api/skills/install` | Optional | Download skill files |
| GET | `/api/skills/access` | Required | Check subscription access |
| GET | `/api/skills/trending` | None | Top skills this week/month |
| GET | `/api/carousel/today` | None | 7 daily curated picks |
| POST | `/api/telemetry` | Required | Report usage events |
| GET | `/api/recipes/{slug}` | Required | Full recipe detail |
| GET | `/api/api-library/{slug}` | None | API documentation pack |

Full reference: see [SKILL.md](SKILL.md) or [recipes.wisechef.ai](https://recipes.wisechef.ai).

## License

Apache 2.0 — see [LICENSE](LICENSE).

This repo is intentionally **public**. The meta-skill is the open, composable
layer; the marketplace content and API are the product.

## Links

- 🛒 Marketplace: [recipes.wisechef.ai](https://recipes.wisechef.ai)
- 🏢 WiseChef: [wisechef.ai](https://wisechef.ai)
- 📖 Publish a skill: [recipes.wisechef.ai/publish](https://recipes.wisechef.ai/publish)
- 🐛 Issues: [github.com/wisechef-ai/recipes-skill/issues](https://github.com/wisechef-ai/recipes-skill/issues)
