# Contributing to Recipes Meta-Skill

Thank you for your interest in contributing! This repo is the open-source
meta-skill for the [Recipes marketplace](https://recipes.wisechef.ai).

## What This Repo Is

`SKILL.md` is the **meta-skill** — the single file that teaches an AI agent how
to discover and install skills from the Recipes marketplace. It is intentionally
minimal (≤ 200 lines). This is a hard constraint: larger meta-skills overflow
agents' context budgets.

## Contributing to the Meta-Skill

Pull requests are welcome for:

- **Bug fixes** — wrong API endpoints, broken examples, stale URLs
- **Clarity improvements** — clearer install instructions, better examples
- **New endpoint coverage** — when the Recipes API adds endpoints that agents
  should know about

Pull requests are **not** appropriate for:

- Adding skills themselves (skills live in their own repos, not here)
- Expanding the meta-skill beyond 200 lines — suggest cuts if you add content
- Hardcoding API keys, secrets, or user-specific data

## Publishing Your Own Skill to the Marketplace

If you want to publish a skill that users can find via this meta-skill:

1. **Build locally:** Create `SKILL.md` + any supporting scripts in a GitHub repo
2. **Submit:** Go to [recipes.wisechef.ai/publish](https://recipes.wisechef.ai/publish)
3. **Connect GitHub:** Authorize the Recipes app to verify your repo
4. **Pass review:** Automated security scan runs first, then human review
5. **Ship:** Approved skills appear in search immediately

### Skill requirements

- `SKILL.md` must have valid YAML frontmatter with `name` and `description`
- No credentials or secrets in any skill file
- No arbitrary `curl | bash` without checksum verification
- Skills must work with the agent model reading markdown — no proprietary formats
- English-only for v1

### Creator economics

- **Cook tier installs:** 50% revenue share, usage-attributed
- **Operator tier installs:** 60% revenue share
- **Studio tier installs:** 70% revenue share
- **First 50 publishers:** 75% locked-in for the lifetime of each referral

Payouts processed monthly via Stripe Connect. See
[recipes.wisechef.ai/creators](https://recipes.wisechef.ai/creators) for the
full creator guide.

## Development Setup

```bash
git clone https://github.com/wisechef-ai/recipes-skill
cd recipes-skill
# No build step — it's plain markdown
```

Validate the YAML frontmatter locally:

```bash
python3 -c "
import re, yaml
content = open('SKILL.md').read()
m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
data = yaml.safe_load(m.group(1))
assert data['name'], 'name required'
assert data['description'], 'description required'
assert len(content.splitlines()) <= 200, f'Too long: {len(content.splitlines())} lines'
print('OK —', len(content.splitlines()), 'lines')
"
```

## Code of Conduct

Be kind. Constructive criticism welcome. No harassment.

## License

All contributions to this repo are licensed under Apache 2.0 (see [LICENSE](LICENSE)).
Skill content you publish to the marketplace retains your own license — Recipes
does not impose a license on creator-published skills.
