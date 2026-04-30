# Vendoring note — `.github/skill_quality_gate.py`

This file is a **vendored copy** of:

```
wisechef-ai/recipes-api:scripts/skill_quality_gate.py
```

Why vendored: `recipes-api` is a private repo, so the CI runner can't fetch the
script via raw GitHub URL without an auth token. Vendoring sidesteps the auth
plumbing and makes this PUBLIC repo's CI fully self-contained.

## How to update

When the canonical script changes upstream, sync it here:

```bash
cp ../recipes-api/scripts/skill_quality_gate.py .github/skill_quality_gate.py
git add .github/skill_quality_gate.py
git commit -m "chore(ci): sync skill_quality_gate.py from recipes-api"
```

Or, when in doubt, copy from your latest local checkout of `recipes-api`.

## Source of truth

The CANONICAL implementation lives in `recipes-api/scripts/skill_quality_gate.py`
with full test coverage (`recipes-api/tests/test_skill_quality_gate.py`,
44 tests as of this writing). All bug fixes and rule changes happen there
first, then are vendored down to this and other consumer repos.

Never edit this file directly — propose changes upstream, sync down.
