# Subagent B Output — `recipes` CLI Sprint 2

**Branch:** `agent/tori/recipes-cli-sprint2`
**Worktree:** `/home/adam/.worktrees/recipes-skill/sprint2-cli`
**Deliverable:** `bin/recipes` — single-file Python 3.11 CLI
**Dependencies:** `cryptography>=42` (listed in `bin/requirements.txt`)

---

## Summary

Built the `recipes` Python CLI that lets Tori/Wise/Chef publish and install skills
against `https://recipes.wisechef.ai`. The CLI is a single executable file at
`bin/recipes` (shebang `#!/usr/bin/env python3`) using only Python 3.11 stdlib +
`cryptography` for ed25519 signing.

10/10 tests pass in `tests/test_recipes_cli.py`.

---

## Subcommands

### 1. `recipes init <skill-name>`

Creates `skill.toml` + `SKILL.md` scaffold in the current directory.
Refuses to overwrite existing files.

**skill.toml fields:** `name`, `version=0.1.0`, `description`, `license=MIT`,
`entrypoint=SKILL.md`, `tier=cook`, `is_public=false`.

**Example:**
```bash
mkdir my-new-skill && cd my-new-skill
recipes init "my new skill"
# Creates: skill.toml, SKILL.md
cat skill.toml
# [skill]
# name = "my-new-skill"
# version = "0.1.0"
# description = "A brief description of my new skill"
# license = "MIT"
# entrypoint = "SKILL.md"
# tier = "cook"
# is_public = false
```

---

### 2. `recipes pack [--out=<file>]`

Reads `skill.toml` in CWD, packs all files (excluding `.git`, `__pycache__`,
`venv`, `.venv`, `node_modules`) into a **deterministic** tar.gz.

**Determinism guarantees:**
- Files sorted lexicographically
- TarInfo `mtime=0`, `uid=0`, `gid=0`, `uname=""`, `gname=""`
- GzipFile `mtime=0` — eliminates host-timestamp variation
- Same content + same filenames = identical sha256, always

**Output:** prints sha256 of the tarball.

**Example:**
```bash
cd my-new-skill
recipes pack
# Packed: my-new-skill-0.1.0.tar.gz
# sha256: 80f61947ff2c51822b9f9e5c14d21b897be9e10987ca8469c8a3816d52fb08f7

recipes pack --out /tmp/my-skill-release.tar.gz
# Packed: /tmp/my-skill-release.tar.gz
# sha256: 80f61947ff2c51822b9f9e5c14d21b897be9e10987ca8469c8a3816d52fb08f7
```

---

### 3. `recipes publish [--api-key=<key>] [--private]`

Pack → ed25519-sign → multipart-POST to
`https://recipes.wisechef.ai/api/skills/_publish`.

**API key:** `--api-key=<key>` or env `RECIPES_API_KEY`.

**Keypair management:**
- First publish: generates ed25519 keypair, stores private key at
  `~/.recipes/keys/{slug}.priv` (mode `0600`)
- Subsequent publishes: reuses existing key
- Public key included in upload (base64-encoded raw bytes)
- Signature over tarball bytes, also base64-encoded

**Multipart POST fields sent:**
| Field        | Value                              |
|--------------|------------------------------------|
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

**Expected API response shape (being built in parallel by Subagent A):**
```json
{
  "slug": "my-new-skill",
  "version": "0.1.0",
  "url": "https://recipes.wisechef.ai/skills/my-new-skill"
}
```

**Example:**
```bash
export RECIPES_API_KEY=rec_your_key_here
cd my-new-skill
recipes publish
# Packing my-new-skill@0.1.0 ...
# sha256: 80f61...
# Generated new keypair → /home/adam/.recipes/keys/my-new-skill.priv
# Publishing my-new-skill@0.1.0 to https://recipes.wisechef.ai/api/skills/_publish ...
#
# ✓ Published: my-new-skill@0.1.0
#   URL: https://recipes.wisechef.ai/skills/my-new-skill
#   Slug: my-new-skill

# Force private even if skill.toml says is_public=true:
recipes publish --private
```

---

### 4. `recipes install <slug>[@<version>] [--client-mode] [--report-to=<url>] [--force]`

Calls `GET /api/skills/install?slug={slug}&version={ver}`, downloads tarball,
verifies sha256, extracts to `~/.hermes/skills/{category}/{slug}/`.

Writes `~/.hermes/skills/{category}/{slug}/.recipes-meta.json`:
```json
{
  "slug": "client-reporter",
  "version": "1.0.0",
  "installed_at": "2026-04-28T14:35:00+00:00",
  "sha256": "abc123...",
  "source_url": "https://recipes.wisechef.ai/tarballs/client-reporter-1.0.0.tar.gz"
}
```

Category comes from `manifest.category` in the install response.
Skips reinstall if already at requested version (override with `--force`).

**Example:**
```bash
# Install latest version:
recipes install client-reporter

# Install specific version:
recipes install client-reporter@1.0.0

# Install with client-mode flag + reporting URL:
recipes install client-reporter --client-mode --report-to=https://my-hub.example.com/report

# Force reinstall:
recipes install client-reporter --force

# Installed client-reporter@1.0.0 at /home/adam/.hermes/skills/devops/client-reporter
```

**API endpoint called:**
```
GET https://recipes.wisechef.ai/api/skills/install?slug=client-reporter
# Headers: x-api-key: rec_...  (if RECIPES_API_KEY set)
#
# Response:
# {
#   "slug": "client-reporter",
#   "version": "1.0.0",
#   "tarball_url": "https://...",
#   "sha256": "abc123...",
#   "manifest": { "category": "devops" }
# }
```

---

### 5. `recipes update [<slug>]`

For each installed skill (or just one if slug given): checks latest version from
`/api/skills/install`, re-installs if newer. Inherits `client_mode` and `report_to`
from existing `.recipes-meta.json`.

**Example:**
```bash
# Update all installed skills:
recipes update

# Update only one:
recipes update client-reporter

# Checking client-reporter (current: 0.9.0) ...
#   ↑ client-reporter: 0.9.0 → 1.0.0
#   [install output...]
# Done. 1 skill(s) updated.
```

---

### 6. `recipes list`

Lists all installed skills with version, install date, and source URL by reading
`.recipes-meta.json` files under `~/.hermes/skills/`.

**Example:**
```bash
recipes list

# Slug                           Version      Installed At                 Source URL
# ──────────────────────────────────────────────────────────────────────────────────
# client-reporter                1.0.0        2026-04-28T14:35:00+00:00   https://recipes.wisechef.ai/tarballs/...
# agent-rescue                   2.1.0        2026-04-27T09:12:00+00:00   https://recipes.wisechef.ai/tarballs/...
```

---

## Tests (`tests/test_recipes_cli.py`)

10 tests using `pytest` + in-process `http.server` mocking. All pass.

| # | Test | Covers |
|---|------|--------|
| 1 | `test_init_creates_files` | `init` creates `skill.toml` + `SKILL.md` |
| 2 | `test_init_valid_toml` | `skill.toml` is parseable, has correct keys/values |
| 3 | `test_init_refuses_overwrite` | `init` exits non-zero if files already exist |
| 4 | `test_pack_determinism` | Same content → same sha256 after 1-second delay |
| 5 | `test_pack_excludes_git` | `.git` dir absent from tarball members |
| 6 | `test_install_bad_sha256_fails` | Mismatched sha256 → `SystemExit` with "mismatch" |
| 7 | `test_install_writes_meta` | `.recipes-meta.json` written with correct fields |
| 8 | `test_list_reads_meta` | `list` prints slug, version, date from meta file |
| 9 | `test_publish_dryrun_fields` | Multipart POST contains all required fields |
| 10 | `test_update_skips_when_current` | `update` skips when version is already latest |

**Run:**
```bash
cd /home/adam/.worktrees/recipes-skill/sprint2-cli
python3 -m pytest tests/test_recipes_cli.py -v
```

---

## File Layout

```
bin/
  recipes           # Main CLI (executable, shebang #!/usr/bin/env python3)
  requirements.txt  # cryptography>=42
tests/
  test_recipes_cli.py  # 10 tests
SPRINT_DOCS/
  SUBAGENT_B_OUTPUT.md  # This file
.gitignore
```

---

## Git History

```
9a2c710  feat(cli): tests — 10 tests covering all subcommands with mocked http.server
6cb6a1b  feat(cli): recipes list — show all installed skills from .recipes-meta.json
b1f23f8  feat(cli): recipes update — re-install if newer version available
9087ce7  feat(cli): recipes install — sha256-verified extraction to ~/.hermes/skills/
a38daaf  feat(cli): recipes publish — ed25519-sign + multipart-POST
1817143  feat(cli): recipes pack — deterministic tar.gz with sha256
4149357  feat(cli): recipes init — scaffold skill.toml + SKILL.md
```

---

## Install Instructions

```bash
# Install cryptography (only external dep):
pip install cryptography>=42

# Make the CLI available globally:
sudo ln -sf /home/adam/.worktrees/recipes-skill/sprint2-cli/bin/recipes /usr/local/bin/recipes

# Verify:
recipes --help
```

---

## Known Gaps / Future Work

- **Semver comparison in `update`**: currently uses string equality; a proper semver
  comparison library (or stdlib `packaging`) would be needed for `>=`, `~=`, etc.
  The API returns latest-stable so string equality is safe for current usage.
- **`/api/skills/_publish` endpoint**: being built in parallel by Subagent A.
  The publish subcommand is complete on the CLI side; tests use a local mock server.
- **Tarball path traversal check**: uses a simple `".." in name.split("/")` check.
  Production hardening should use `pathlib.Path.resolve()`.
- **Rate limiting / retry**: no exponential backoff on network errors.

---

*Generated by Subagent B — April 28, 2026*
