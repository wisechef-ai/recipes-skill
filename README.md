# Recipes Skill

Install agent skills from recipes.wisechef.ai into Claude Code, Cursor, Windsurf, OpenClaw, Hermes, or any Anthropic Skills-compatible host.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Install

Replace `<slug>` with the skill slug from [recipes.wisechef.ai/skills](https://recipes.wisechef.ai/skills).

| Agent host | Install command |
|------------|----------------|
| **Claude Code** | `npx @wisechef/recipes-skill install <slug>` |
| **Cursor** | `pip install recipes-cli` then `recipes install <slug>` |
| **Windsurf** | `pip install recipes-cli` then `recipes install <slug>` |
| **Cline** | `pip install recipes-cli` then `recipes install <slug>` |
| **OpenClaw** | `claw skill install recipes:<slug>` |
| **Hermes** | `hermes skill install recipes:<slug>` |

The install command fetches the skill manifest from the Recipes API, validates the allowlist against your agent host's policy, verifies the ed25519 signature, resolves dependencies, and writes the skill to your agent's workspace. No manual steps.

**Quick start with the free gateway skill:**

```bash
npx @wisechef/recipes-skill install super-memory
```

No account required. See [recipes.wisechef.ai/skills/super-memory](https://recipes.wisechef.ai/skills/super-memory).

---

## Pricing

| Tier | Price | Seats | What you get |
|------|-------|-------|-------------|
| **Free** | $0/mo | 1 | Free skills only (currently 2, including super-memory) |
| **Pro** | $20/mo | 1 | All 38 Pro-tier skills + full catalog access |
| **Pro+** | $100/mo | 20 endpoints | All 14 Pro+ skills + fleet sync across 20 agent endpoints |

Free skills are always free — no subscription required, no credit card, no expiry.

Pro and Pro+ are billed in USD. Full pricing details and a tier comparison at [recipes.wisechef.ai/pricing](https://recipes.wisechef.ai/pricing).

Note for API consumers: the REST API returns `tier: "cook"` for Pro and `tier: "operator"` for Pro+. These are stable DB identifiers. The display labels (Pro / Pro+) are portal-only. See the Common Issues section below.

---

## Earn 50% Recurring

Sign up as a creator at [recipes.wisechef.ai/creators](https://recipes.wisechef.ai/creators). You get a referral link. Every user who clicks your link and subscribes within 30 days generates 50% of their monthly subscription fee — paid to you, every month, for as long as they stay subscribed.

- Pro referral: $10/month per subscriber, recurring
- Pro+ referral: $50/month per subscriber, recurring
- No cap. No expiry. No cliff.

The first 100 creators who publish an approved skill get permanent featured placement in the catalog — a `featured` badge and priority in search results. This is not a time-limited promotion; the first 100 slots are permanent.

To publish a skill: open a PR against this repo. The 5-step quality pipeline (security scan, discipline check, quality score, allowlist validation, manifest integrity) runs automatically. Pass all five and a human reviewer approves. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full submission process.

---

## Common Issues

### Skill won't install on macOS Apple Silicon

Symptom: install fails with a dependency resolution error mentioning `cognee` or `pgvector`.

Fix: cognee 1.0.9 (in super-memory PR #67) resolves the Apple Silicon wheel incompatibility. If you installed super-memory before PR #67 was merged, reinstall:

```bash
npx @wisechef/recipes-skill install super-memory
```

The installer is idempotent — reinstalling over an existing skill updates it in place.

---

### "Architecture-aware install said no"

Symptom: install prints `refused: incompatible host` and exits non-zero.

This is intentional. The Recipes installer probes your agent host before writing any files. If the host does not implement the Anthropic Skills handshake (allowlist validation, signature verification), the installer refuses rather than silently installing an unverified skill. This protects you from skills that could exfiltrate data or exceed their stated network permissions.

Check that your agent host version supports the Anthropic Skills standard. See [recipes.wisechef.ai/docs/install](https://recipes.wisechef.ai/docs/install) for per-host compatibility notes.

---

### "I see Pro/Pro+ in the UI but the API still returns cook/operator"

This is by design. The rev7.3 release renamed the display labels from Cook→Pro and Operator→Pro+. The underlying DB slugs (`cook`, `operator`) were not changed — they are stable API contract identifiers.

If you are building against the API, use `cook` and `operator` as the tier identifiers. They will not change. The portal displays "Pro" and "Pro+" for user-facing clarity; the API returns the stable slugs.

---

### "My install_count looks wrong"

install_count values are reconciled hourly by `install_count_drift_probe.py` (cron job on the Recipes backend). If a batch of install events arrived out-of-order (common when multiple agent hosts flush install queues simultaneously), counts can appear stale for up to 1 hour.

Events within 5 minutes of real-time are considered in-flight and excluded from the reconciliation window. If your count looks wrong for more than 1 hour after an install, open an issue.

---

## License

This repository is MIT licensed. See [LICENSE](LICENSE).

Each skill in the catalog has its own license declared in its `SKILL.md` frontmatter. The default for skills published without an explicit license is MIT. Check the skill's SKILL.md before depending on it in a commercial project.
