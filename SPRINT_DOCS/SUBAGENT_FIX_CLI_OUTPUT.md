# Subagent Fix — CLI Copilot Review Output

**Branch:** `agent/tori/recipes-cli-sprint2`
**Worktree:** `/home/adam/.worktrees/recipes-skill/sprint2-cli`
**Date:** 2026-04-28
**Source contract:** `/home/adam/.worktrees/recipes-api/sprint2-publisher/SPRINT_DOCS/COPILOT_FIX_CONTRACT.md`
**Sections addressed:** F-CLI-01, F-CLI-02, F-CLI-03

---

## Test Count Before / After

| State  | Tests Passing |
|--------|--------------|
| Before | 9/10 (1 failure: `test_publish_dryrun_fields`) |
| After  | 12/12 ✅ |

---

## F-CLI-01 — Test rewrite: `test_publish_dryrun_fields`

**File:** `tests/test_recipes_cli.py`
**Commit:** `fix(cli): rewrite test_publish_dryrun_fields to assert actual wire format (PR #1 review)`

**Issue:** Test at line ~483 asserted that the multipart POST contained form fields
`name`, `version`, `sha256`, `public_key` — but the CLI (since commit `cdf5c80`)
sends `skill_toml`, `tarball`, `signature`, `signing_pubkey` as file parts +
`is_public` as the sole form field. Test was asserting the *old* wire format and
failing every run.

**Before (broken assertions):**
```python
assert "name" in body_str
assert "test-pub-skill" in body_str
assert "sha256" in body_str
assert "public_key" in body_str
assert "signature" in body_str
assert "version" in body_str
```

**After (correct assertions):**
```python
# Assert actual multipart file fields (current wire format per commit cdf5c80)
assert "skill_toml" in body_str, "missing 'skill_toml' file part"
assert "tarball" in body_str, "missing 'tarball' file part"
assert "signature" in body_str, "missing 'signature' file part"
assert "signing_pubkey" in body_str, "missing 'signing_pubkey' file part"
assert "is_public" in body_str, "missing 'is_public' form field"
assert "test-pub-skill" in body_str, "skill name not present in body"
# Old fields (name/version/sha256/public_key as separate form fields) are gone
assert "sha256" not in body_str.split("test-pub-skill")[0], (
    "'sha256' should not appear as a standalone form field"
)
```

**Test result:** PASSED ✅

---

## F-CLI-02 — Doc fix: `SPRINT_DOCS/SUBAGENT_B_OUTPUT.md` wire format table

**File:** `SPRINT_DOCS/SUBAGENT_B_OUTPUT.md`
**Commit:** `fix(cli): update SUBAGENT_B_OUTPUT.md wire format table to current multipart fields (PR #1 review)`

**Issue:** Lines 90–103 of SUBAGENT_B_OUTPUT.md described the *old* wire format
(form fields `name`, `version`, `description`, `license`, `tier`, `is_public`,
`sha256`, `public_key`, `signature`, `tarball`) instead of the actual current
format (file uploads `skill_toml`, `tarball`, `signature`, `signing_pubkey` +
form field `is_public`).

**Before (verbatim old table):**
```
| Field        | Value                              |
|--------------|------------------------------------|-
| `name`       | skill name from toml               |
| `version`    | skill version                      |
| `description`| from toml                          |
| `license`    | from toml                          |
| `tier`       | from toml                          |
| `is_public`  | `true`/`false`                     |
| `sha256`     | hex digest of tarball              |
| `public_key` | base64(raw ed25519 pubkey, 32 bytes)|
| `signature`  | base64(ed25519 signature, 64 bytes) |
| `tarball`    | file upload (`application/gzip`)   |
```

**After (verbatim replacement per Copilot suggestion):**
```
| Part           | Kind        | Content-Type              | Description                                 |
|----------------|-------------|---------------------------|---------------------------------------------|
| `skill_toml`   | file upload | `text/plain`              | Raw bytes of `skill.toml`                   |
| `tarball`      | file upload | `application/gzip`        | Packed `.tar.gz` of the skill directory     |
| `signature`    | file upload | `application/octet-stream`| ed25519 signature over `sha256(tarball).digest()` (64 raw bytes) |
| `signing_pubkey` | file upload | `application/octet-stream` | ed25519 public key (32 raw bytes)         |
| `is_public`    | form field  | —                         | `"true"` or `"false"`                       |
```

Also updated the keypair management bullet points to reflect raw binary uploads
(not base64-encoded).

**Test:** N/A (doc-only change) ✅

---

## F-CLI-03 — CLI category-aware install + new tests

**Files:** `bin/recipes`, `tests/test_recipes_cli.py`
**Commit:** `fix(cli): category-aware install reads skill.toml fallback when manifest.category absent (PR #1 review)`

**Issue:** `cmd_install` defaulted to `category = "general"` when `manifest.category`
was absent from the install response. Since the server currently doesn't populate
`manifest.category` (F-API-14 is the server-side fix, separate concern), all skills
were installing to `~/.hermes/skills/general/<slug>/` regardless of their actual
category, forcing manual moves.

**Fix in `bin/recipes` — `cmd_install` function:**

Priority order implemented:
1. `manifest.category` from install response (server-side preference, future-proof)
2. `[skill].category` from the downloaded skill.toml inside the tarball (fallback)
3. `"general"` (hard default)

Key change — after download + sha256 verification, if `category` is still empty:
```python
if not category:
    try:
        with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
            toml_member = next(
                (m for m in tar.getmembers() if m.name.lstrip("./") == "skill.toml" or m.name == "skill.toml"),
                None,
            )
            if toml_member:
                raw_toml = tar.extractfile(toml_member)
                if raw_toml:
                    parsed = tomllib.loads(raw_toml.read().decode("utf-8", errors="replace"))
                    category = parsed.get("skill", parsed).get("category", "")
    except Exception:
        pass  # best-effort; fall through to default

if not category:
    category = "general"

# Recalculate install_dir now that category is resolved
install_dir = SKILLS_DIR / category / remote_slug
meta_path = install_dir / ".recipes-meta.json"
```

**New tests added:**

| # | Test | Result |
|---|------|--------|
| 11 | `test_install_uses_skill_toml_category` | PASSED ✅ |
| 12 | `test_install_manifest_category_takes_priority` | PASSED ✅ |

- **test 11:** Mock install response with empty manifest, tarball contains `skill.toml` with `category = "devops"`. Asserts skill installed at `~/.hermes/skills/devops/devops-tool/`, NOT `general/`.
- **test 12:** Mock install response with `manifest.category = "infra"`, tarball's `skill.toml` says `category = "devops"`. Asserts `infra/` wins — server preference takes priority.

---

## Git Log (4 commits on this branch)

```
543e12a  fix(cli): add test_install_manifest_category_takes_priority — priority order coverage (PR #1 review)
0e04da5  fix(cli): category-aware install reads skill.toml fallback when manifest.category absent (PR #1 review)
fc9ba52  fix(cli): update SUBAGENT_B_OUTPUT.md wire format table to current multipart fields (PR #1 review)
6445ffe  fix(cli): rewrite test_publish_dryrun_fields to assert actual wire format (PR #1 review)
```

---

## Final Test Run Output

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/adam/.worktrees/recipes-skill/sprint2-cli
plugins: anyio-4.12.1, mock-3.15.1, typeguard-4.1.5, cov-4.1.0, colcon-core-0.20.1
collecting ... collected 12 items

tests/test_recipes_cli.py::test_init_creates_files PASSED                [  8%]
tests/test_recipes_cli.py::test_init_valid_toml PASSED                   [ 16%]
tests/test_recipes_cli.py::test_init_refuses_overwrite PASSED            [ 25%]
tests/test_recipes_cli.py::test_pack_determinism PASSED                  [ 33%]
tests/test_recipes_cli.py::test_pack_excludes_git PASSED                 [ 41%]
tests/test_recipes_cli.py::test_install_bad_sha256_fails PASSED          [ 50%]
tests/test_recipes_cli.py::test_install_writes_meta PASSED               [ 58%]
tests/test_recipes_cli.py::test_list_reads_meta PASSED                   [ 66%]
tests/test_recipes_cli.py::test_publish_dryrun_fields PASSED             [ 75%]
tests/test_recipes_cli.py::test_update_skips_when_current PASSED         [ 83%]
tests/test_recipes_cli.py::test_install_uses_skill_toml_category PASSED  [ 91%]
tests/test_recipes_cli.py::test_install_manifest_category_takes_priority PASSED [100%]

=============================== warnings summary ===============================
tests/test_recipes_cli.py::test_install_writes_meta
tests/test_recipes_cli.py::test_install_writes_meta
tests/test_recipes_cli.py::test_install_uses_skill_toml_category
tests/test_recipes_cli.py::test_install_uses_skill_toml_category
tests/test_recipes_cli.py::test_install_manifest_category_takes_priority
tests/test_recipes_cli.py::test_install_manifest_category_takes_priority
  /usr/lib/python3.12/tarfile.py:2274: DeprecationWarning: Python 3.14 will, by default, filter extracted tar archives and reject files or modify their metadata. Use the filter argument to control this behavior.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 12 passed, 6 warnings in 6.15s ========================
```

---

## Acceptance Gate Status

| Gate | Status |
|------|--------|
| All recipes-skill tests pass | ✅ 12/12 |
| Target 10 → 12+ tests | ✅ 12 tests |
| F-CLI-01 test rewrite | ✅ |
| F-CLI-02 doc fix (verbatim per Copilot) | ✅ |
| F-CLI-03 CLI category-aware install | ✅ |
| One commit per fix | ✅ (4 commits, clean history) |
| No new branches created | ✅ |
| Pushed to origin | ✅ |

---

*Generated by Subagent Fix-CLI — April 28, 2026*
