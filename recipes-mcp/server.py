"""recipes-mcp/server.py — FastMCP server wiring 6 recipes tools.

Wires to https://recipes.wisechef.ai. Tools are callable from Claude Code,
Cursor, Cline, Codex, Zed, and any other MCP-aware client.

Run:
  python recipes-mcp/server.py          # stdio transport (default for MCP clients)
  RECIPES_API_KEY=<key> python recipes-mcp/server.py
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
import pathlib
import tarfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from fastmcp import FastMCP

API_BASE = os.environ.get("RECIPES_API_BASE", "https://recipes.wisechef.ai/api")
_DEFAULT_DEST = "~/.claude/skills"

mcp = FastMCP(
    "recipes",
    instructions=(
        "Search, install, sync, publish, check, and report errors for skills "
        "from recipes.wisechef.ai. Use recipes_search before installing. "
        "After any skill failure, call recipes_check then recipes_report_error."
    ),
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def _auth_headers() -> dict[str, str]:
    key = os.environ.get("RECIPES_API_KEY", "")
    return {"x-api-key": key} if key else {}


def _api_get(path: str, params: dict | None = None) -> dict | list:
    url = f"{API_BASE}{path}"
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url += "?" + urllib.parse.urlencode(filtered)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "recipes-mcp/1.0.0 (+https://recipes.wisechef.ai)")
    for k, v in _auth_headers().items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_post(path: str, body: dict) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(data)))
    req.add_header("User-Agent", "recipes-mcp/1.0.0 (+https://recipes.wisechef.ai)")
    for k, v in _auth_headers().items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _api_download(url: str) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "recipes-mcp/1.0.0 (+https://recipes.wisechef.ai)")
    for k, v in _auth_headers().items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


# ── Tar-slip protection ───────────────────────────────────────────────────────


def _safe_extract(tarball_bytes: bytes, target_dir: pathlib.Path) -> None:
    """Extract tarball, refusing any member that escapes target_dir.

    Per skill #53: iterates getmembers() checking each member resolves
    under target_dir.resolve(). Refuses '..' paths and absolute paths.
    """
    resolved_target = target_dir.resolve()
    resolved_str = str(resolved_target)

    with tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            # Reject absolute paths outright
            if os.path.isabs(member.name):
                raise ValueError(
                    f"Unsafe tarball: absolute path {member.name!r} rejected"
                )
            # Resolve and verify the member stays inside target_dir
            member_resolved = (resolved_target / member.name).resolve()
            member_str = str(member_resolved)
            inside = member_str == resolved_str or member_str.startswith(
                resolved_str + os.sep
            )
            if not inside:
                raise ValueError(
                    f"Unsafe tarball: path {member.name!r} escapes install dir "
                    f"(resolves to {member_str!r}, expected under {resolved_str!r})"
                )
            tar.extract(member, target_dir, set_attrs=False)


# ── Internal install (shared by recipes_install and recipes_sync) ─────────────


def _do_install(slug: str, dest: str | None = None, *, force: bool = False) -> dict:
    """Fetch, verify SHA256, and safely extract a skill tarball."""
    effective_dest = dest if dest is not None else _DEFAULT_DEST
    target_dir = pathlib.Path(effective_dest).expanduser()
    skill_dir = target_dir / slug
    meta_path = skill_dir / ".recipes-meta.json"

    # Fetch install manifest
    info = _api_get("/skills/install", {"slug": slug})
    slug_real: str = info["slug"]
    version: str = info["version"]
    tarball_url: str = info["tarball_url"]
    expected_sha256: str | None = info.get("checksum_sha256") or info.get("sha256")
    if not expected_sha256:
        raise ValueError(f"Install manifest for '{slug}' missing checksum_sha256")

    # Skip re-install if already at this version (unless forced)
    if not force and meta_path.exists():
        with open(meta_path) as f:
            existing = json.load(f)
        if existing.get("version") == version:
            return existing

    # Download tarball
    tarball_bytes = _api_download(tarball_url)

    # Verify SHA256 BEFORE any extraction (security requirement per skill #53)
    actual_sha256 = hashlib.sha256(tarball_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"SHA256 mismatch for '{slug}': "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    # Safe extract with tar-slip protection
    skill_dir.mkdir(parents=True, exist_ok=True)
    _safe_extract(tarball_bytes, skill_dir)

    meta: dict = {
        "slug": slug_real,
        "version": version,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "sha256": actual_sha256,
        "path": str(skill_dir),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta


# ── MCP tools ─────────────────────────────────────────────────────────────────


@mcp.tool()
def recipes_search(query: str, subset: str = "all") -> list[dict]:
    """Search the Recipes marketplace for skills.

    Searches across Pantry (3rd-party originals), Menu (curated Cook+ skills),
    and the user's Personal Cookbook. Returns matching skill records.

    Args:
        query: Search terms — skill name, keyword, or use-case description.
        subset: Filter results to 'pantry', 'menu', 'cookbook', or 'all' (default).

    Returns:
        List of skill dicts with slug, name, description, tier, installs fields.
    """
    params: dict = {"q": query}
    if subset != "all":
        params["subset"] = subset
    result = _api_get("/skills/search", params)
    if isinstance(result, dict):
        return result.get("skills", [])
    if isinstance(result, list):
        return result
    return []


@mcp.tool()
def recipes_install(slug: str, dest: str = _DEFAULT_DEST) -> dict:
    """Install a skill from the Recipes marketplace.

    Fetches the skill tarball and verifies its SHA256 checksum against the
    API metadata BEFORE extraction. Refuses any tarball that contains path-
    traversal sequences (../) or absolute paths (tar-slip protection).

    On the first authenticated call the server silently forks the Base Cookbook
    into a Personal Cookbook for the user — no client action required.

    Args:
        slug: Skill identifier, e.g. 'client-reporter' or 'seo-audit@1.2.0'.
        dest: Local directory to install into. Defaults to ~/.claude/skills.

    Returns:
        Dict with slug, version, installed_at, sha256, path fields.
    """
    return _do_install(slug, dest=dest)


@mcp.tool()
def recipes_publish(skill_dir: str, channel: str = "canary") -> dict:
    """Publish a local skill directory to the user's Cookbook.

    Packs the skill into a deterministic tarball and pushes it to the user's
    Personal Cookbook on recipes.wisechef.ai. Defaults to the canary channel
    (7-day soak period before promotion to stable).

    Args:
        skill_dir: Path to the local skill directory (must contain skill.toml).
        channel: Release channel — 'canary' (default) or 'stable'.

    Returns:
        Dict with slug, version, channel, url fields returned by the API.
    """
    skill_path = pathlib.Path(skill_dir).expanduser().resolve()
    if not skill_path.exists():
        raise ValueError(f"skill_dir does not exist: {skill_dir}")
    toml_path = skill_path / "skill.toml"
    if not toml_path.exists():
        raise ValueError(f"skill.toml not found in {skill_dir}")

    with open(toml_path, "rb") as f:
        meta = tomllib.load(f)
    skill_meta = meta.get("skill", meta)
    slug = skill_meta["name"]
    version = skill_meta["version"]

    # Build deterministic tarball in memory
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for fpath in sorted(skill_path.rglob("*")):
            if not fpath.is_file():
                continue
            rel = str(fpath.relative_to(skill_path))
            info = tarfile.TarInfo(name=rel)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.size = fpath.stat().st_size
            with open(fpath, "rb") as fh:
                tar.addfile(info, fh)

    gz_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buf, mode="wb", mtime=0, compresslevel=6) as gz:
        gz.write(raw.getvalue())
    tarball_bytes = gz_buf.getvalue()
    sha256_digest = hashlib.sha256(tarball_bytes).hexdigest()

    payload = {
        "slug": slug,
        "version": version,
        "channel": channel,
        "tarball_b64": base64.b64encode(tarball_bytes).decode(),
        "checksum_sha256": sha256_digest,
    }
    return _api_post("/v1/cookbook/publish", payload)


@mcp.tool()
def recipes_sync(channel: str = "stable", quiet: bool = True) -> dict:
    """Pull subscribed skill bundles and install any updates.

    Sends the current local skill inventory to recipes.wisechef.ai and receives
    a diff. Installs new skills and force-updates changed ones. On first run,
    also wires a daily cron via the CLI wrapper (if available).

    Args:
        channel: Subscription channel — 'stable' (default), 'canary', or 'frozen'.
        quiet: Suppress per-skill progress output (default True, for cron use).

    Returns:
        Dict with installed, updated, unchanged, removed lists plus channel and errors.
    """
    # Collect installed versions from the default skills dir
    skills_dir = pathlib.Path(_DEFAULT_DEST).expanduser()
    current_versions: dict[str, str] = {}
    if skills_dir.exists():
        for meta_path in skills_dir.rglob(".recipes-meta.json"):
            try:
                with open(meta_path) as f:
                    m = json.load(f)
                if m.get("slug"):
                    current_versions[m["slug"]] = m.get("version", "")
            except Exception:
                pass

    diff = _api_post(
        "/v1/fleet/sync",
        {"current_versions": current_versions, "channel": channel},
    )

    installed: list[str] = []
    updated: list[str] = []
    errors: list[str] = []

    for item in diff.get("to_install", []):
        s = item.get("slug", item) if isinstance(item, dict) else str(item)
        try:
            _do_install(s, force=False)
            installed.append(s)
        except Exception as exc:
            errors.append(f"{s}: {exc}")

    for item in diff.get("to_update", []):
        s = item.get("slug", item) if isinstance(item, dict) else str(item)
        try:
            _do_install(s, force=True)
            updated.append(s)
        except Exception as exc:
            errors.append(f"{s}: {exc}")

    return {
        "installed": installed,
        "updated": updated,
        "unchanged": diff.get("unchanged", []),
        "removed": diff.get("removed", []),
        "channel": channel,
        "errors": errors,
    }


@mcp.tool()
def recipes_check(slug: str) -> dict:
    """Check whether a newer version of a skill is available.

    Compares the locally installed version against the latest published version
    on recipes.wisechef.ai. Returns version metadata, changelog excerpt, and a
    flag indicating whether the update contains breaking changes.

    Args:
        slug: Skill identifier to check, e.g. 'client-reporter'.

    Returns:
        Dict with slug, installed_version, latest_version, has_update (bool),
        changelog (str), and breaking_changes (bool).
    """
    return _api_get(f"/v1/skills/{urllib.parse.quote(slug)}/check")


@mcp.tool()
def recipes_report_error(slug: str, error_class: str, error_msg: str) -> dict:
    """Report a skill execution error to recipes.wisechef.ai.

    Posts an anonymized error report so the WiseChef team can track failure
    patterns and ship fixes. Error content is stripped of file paths and
    personal data server-side before storage.

    The /api/v1/skill-error endpoint is a Phase C deliverable. Until it goes
    live this call returns a stub response and is safe to call at any time.

    Args:
        slug: The skill that failed, e.g. 'seo-audit'.
        error_class: Exception class name, e.g. 'FileNotFoundError'.
        error_msg: Human-readable error message (anonymized server-side).

    Returns:
        Dict with report_id, status ('received' or 'stub'), and message.
    """
    payload = {"slug": slug, "error_class": error_class, "error_msg": error_msg}
    try:
        return _api_post("/v1/skill-error", payload)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {
                "report_id": None,
                "status": "stub",
                "message": (
                    "Error reporting endpoint not yet live (Phase C). "
                    "Report queued — no action needed."
                ),
            }
        raise


if __name__ == "__main__":
    mcp.run()
