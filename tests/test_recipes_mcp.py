"""tests/test_recipes_mcp.py — TDD tests for recipes-mcp/server.py.

Covers:
  - All 6 MCP tools with mocked API responses
  - SHA256 mismatch → install aborted before extraction
  - Tar-slip (../ path) → install refused
  - Absolute path in tarball → install refused
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import pathlib
import sys
import tarfile
from unittest.mock import patch

import pytest

# ── Load server module ────────────────────────────────────────────────────────

SERVER_PATH = pathlib.Path(__file__).parent.parent / "recipes-mcp" / "server.py"
sys.path.insert(0, str(SERVER_PATH.parent))

import importlib.util

spec = importlib.util.spec_from_file_location("recipes_mcp_server", str(SERVER_PATH))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_tarball(files: dict[str, bytes]) -> bytes:
    """Build a minimal tar.gz from {filename: content}."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    raw_bytes = raw.getvalue()
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0) as f:
        f.write(raw_bytes)
    return gz.getvalue()


def make_malicious_tarball(member_name: str) -> bytes:
    """Build a tar.gz with a single malicious member path."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        data = b"rm -rf ~\n"
        info = tarfile.TarInfo(name=member_name)
        info.size = len(data)
        info.mtime = 0
        tar.addfile(info, io.BytesIO(data))
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0) as f:
        f.write(raw.getvalue())
    return gz.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(slug: str = "test-skill", version: str = "1.0.0",
             tarball: bytes | None = None) -> dict:
    """Build a fake install manifest (SHA matches tarball if provided)."""
    digest = sha256(tarball) if tarball is not None else "a" * 64
    return {
        "slug": slug,
        "version": version,
        "tarball_url": f"https://fake/{slug}-{version}.tar.gz",
        "checksum_sha256": digest,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 1: recipes_search
# ═══════════════════════════════════════════════════════════════════════════════


def test_search_returns_skill_list():
    fake_resp = {"skills": [{"slug": "seo-audit", "name": "SEO Audit", "tier": "cook"}]}
    with patch.object(server, "_api_get", return_value=fake_resp):
        result = server.recipes_search("seo")
    assert isinstance(result, list)
    assert result[0]["slug"] == "seo-audit"


def test_search_handles_direct_list_response():
    fake_resp = [{"slug": "client-reporter"}, {"slug": "seo-audit"}]
    with patch.object(server, "_api_get", return_value=fake_resp):
        result = server.recipes_search("reporter")
    assert len(result) == 2


def test_search_passes_subset_param():
    captured: dict = {}

    def fake_get(path, params=None):
        captured["params"] = params or {}
        return {"skills": []}

    with patch.object(server, "_api_get", side_effect=fake_get):
        server.recipes_search("audit", subset="pantry")

    assert captured["params"].get("subset") == "pantry"


def test_search_subset_all_not_forwarded():
    captured: dict = {}

    def fake_get(path, params=None):
        captured["params"] = params or {}
        return []

    with patch.object(server, "_api_get", side_effect=fake_get):
        server.recipes_search("test", subset="all")

    assert "subset" not in captured["params"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: recipes_install — happy path
# ═══════════════════════════════════════════════════════════════════════════════


def test_install_happy_path(tmp_path):
    tarball = make_tarball({"SKILL.md": b"# Hello\n", "script.sh": b"#!/bin/bash\n"})
    m = manifest("test-skill", "1.0.0", tarball)

    with patch.object(server, "_api_get", return_value=m), \
         patch.object(server, "_api_download", return_value=tarball):
        result = server.recipes_install("test-skill", dest=str(tmp_path))

    assert result["slug"] == "test-skill"
    assert result["version"] == "1.0.0"
    assert result["sha256"] == sha256(tarball)
    assert (tmp_path / "test-skill" / "SKILL.md").exists()
    assert (tmp_path / "test-skill" / "script.sh").exists()
    assert (tmp_path / "test-skill" / ".recipes-meta.json").exists()


def test_install_writes_correct_meta(tmp_path):
    tarball = make_tarball({"SKILL.md": b"# skill\n"})
    m = manifest("meta-skill", "2.3.4", tarball)

    with patch.object(server, "_api_get", return_value=m), \
         patch.object(server, "_api_download", return_value=tarball):
        server.recipes_install("meta-skill", dest=str(tmp_path))

    meta_path = tmp_path / "meta-skill" / ".recipes-meta.json"
    with open(meta_path) as f:
        meta = json.load(f)

    assert meta["slug"] == "meta-skill"
    assert meta["version"] == "2.3.4"
    assert "installed_at" in meta
    assert "sha256" in meta
    assert "path" in meta


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: recipes_install — SHA256 security
# ═══════════════════════════════════════════════════════════════════════════════


def test_install_sha256_mismatch_aborts_before_extraction(tmp_path):
    """SHA256 must be verified BEFORE any file is written to disk."""
    tarball = make_tarball({"SKILL.md": b"# real\n"})
    m = manifest("bad-skill", "1.0.0")  # digest is "a" * 64 — wrong
    m["checksum_sha256"] = "0" * 64

    with patch.object(server, "_api_get", return_value=m), \
         patch.object(server, "_api_download", return_value=tarball), \
         pytest.raises(ValueError, match="SHA256 mismatch"):
        server.recipes_install("bad-skill", dest=str(tmp_path))

    # Nothing must be extracted
    assert not (tmp_path / "bad-skill" / "SKILL.md").exists()


def test_install_missing_checksum_raises(tmp_path):
    """Install raises if manifest has no checksum field at all."""
    m = {"slug": "no-sha", "version": "1.0.0", "tarball_url": "https://fake/x.tar.gz"}
    with patch.object(server, "_api_get", return_value=m), \
         pytest.raises(ValueError, match="checksum_sha256"):
        server.recipes_install("no-sha", dest=str(tmp_path))


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 2: recipes_install — tar-slip protection
# ═══════════════════════════════════════════════════════════════════════════════


def test_install_tar_slip_dotdot_refused(tmp_path):
    """Tarball with ../ path escape must be rejected (tar-slip protection)."""
    malicious = make_malicious_tarball("../evil.sh")
    digest = sha256(malicious)
    m = {
        "slug": "slip-skill",
        "version": "1.0.0",
        "tarball_url": "https://fake/slip.tar.gz",
        "checksum_sha256": digest,
    }

    with patch.object(server, "_api_get", return_value=m), \
         patch.object(server, "_api_download", return_value=malicious), \
         pytest.raises(ValueError):
        server.recipes_install("slip-skill", dest=str(tmp_path))

    # Parent dir must not have evil.sh
    assert not (tmp_path.parent / "evil.sh").exists()
    assert not (tmp_path / "evil.sh").exists()


def test_install_nested_dotdot_refused(tmp_path):
    """good/../../evil.sh must also be rejected (traverse via intermediate dir)."""
    malicious = make_malicious_tarball("good/../../evil.sh")
    digest = sha256(malicious)
    m = {
        "slug": "nested-slip",
        "version": "1.0.0",
        "tarball_url": "https://fake/nested.tar.gz",
        "checksum_sha256": digest,
    }

    with patch.object(server, "_api_get", return_value=m), \
         patch.object(server, "_api_download", return_value=malicious), \
         pytest.raises(ValueError):
        server.recipes_install("nested-slip", dest=str(tmp_path))


def test_install_absolute_path_refused(tmp_path):
    """Tarball with an absolute path member must be rejected."""
    malicious = make_malicious_tarball("/etc/cron.d/evil")
    digest = sha256(malicious)
    m = {
        "slug": "abs-skill",
        "version": "1.0.0",
        "tarball_url": "https://fake/abs.tar.gz",
        "checksum_sha256": digest,
    }

    with patch.object(server, "_api_get", return_value=m), \
         patch.object(server, "_api_download", return_value=malicious), \
         pytest.raises(ValueError, match=r"[Aa]bsolute|[Uu]nsafe"):
        server.recipes_install("abs-skill", dest=str(tmp_path))


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 3: recipes_publish
# ═══════════════════════════════════════════════════════════════════════════════


def test_publish_posts_tarball_to_api(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.toml").write_text(
        '[skill]\nname = "my-skill"\nversion = "0.1.0"\n'
    )
    (skill_dir / "SKILL.md").write_text("# my-skill\n")

    captured: dict = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"slug": "my-skill", "version": "0.1.0", "channel": "canary", "url": "https://fake/..."}

    with patch.object(server, "_api_post", side_effect=fake_post):
        result = server.recipes_publish(str(skill_dir), channel="canary")

    assert result["slug"] == "my-skill"
    assert captured["body"]["slug"] == "my-skill"
    assert captured["body"]["version"] == "0.1.0"
    assert captured["body"]["channel"] == "canary"
    assert "tarball_b64" in captured["body"]
    assert "checksum_sha256" in captured["body"]


def test_publish_missing_dir_raises():
    with pytest.raises(ValueError, match="does not exist"):
        server.recipes_publish("/nonexistent/skill/dir")


def test_publish_missing_skill_toml_raises(tmp_path):
    empty = tmp_path / "empty-skill"
    empty.mkdir()
    with pytest.raises(ValueError, match="skill.toml"):
        server.recipes_publish(str(empty))


def test_publish_default_channel_is_canary(tmp_path):
    skill_dir = tmp_path / "s"
    skill_dir.mkdir()
    (skill_dir / "skill.toml").write_text('[skill]\nname = "s"\nversion = "0.1.0"\n')
    (skill_dir / "SKILL.md").write_text("# s\n")

    captured: dict = {}

    def fake_post(path, body):
        captured["body"] = body
        return {"slug": "s", "version": "0.1.0", "channel": "canary", "url": "https://fake/..."}

    with patch.object(server, "_api_post", side_effect=fake_post):
        server.recipes_publish(str(skill_dir))

    assert captured["body"]["channel"] == "canary"


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 4: recipes_sync
# ═══════════════════════════════════════════════════════════════════════════════


def test_sync_installs_to_install_list():
    diff = {
        "to_install": [{"slug": "new-skill"}],
        "to_update": [],
        "unchanged": [],
        "removed": [],
    }
    installed: list = []

    def fake_do_install(slug, dest=None, *, force=False):
        installed.append(slug)
        return {"slug": slug, "version": "1.0.0", "installed_at": "now", "sha256": "x", "path": "/tmp"}

    with patch.object(server, "_api_post", return_value=diff), \
         patch.object(server, "_do_install", side_effect=fake_do_install):
        result = server.recipes_sync(channel="stable")

    assert "new-skill" in result["installed"]
    assert "new-skill" in installed


def test_sync_updates_to_update_list():
    diff = {
        "to_install": [],
        "to_update": [{"slug": "old-skill"}],
        "unchanged": ["kept-skill"],
        "removed": [],
    }
    updated: list = []

    def fake_do_install(slug, dest=None, *, force=False):
        if force:
            updated.append(slug)
        return {"slug": slug, "version": "2.0.0", "installed_at": "now", "sha256": "x", "path": "/tmp"}

    with patch.object(server, "_api_post", return_value=diff), \
         patch.object(server, "_do_install", side_effect=fake_do_install):
        result = server.recipes_sync(channel="stable")

    assert "old-skill" in result["updated"]
    assert "old-skill" in updated
    assert result["unchanged"] == ["kept-skill"]


def test_sync_returns_channel_in_result():
    diff = {"to_install": [], "to_update": [], "unchanged": [], "removed": []}

    with patch.object(server, "_api_post", return_value=diff), \
         patch.object(server, "_do_install", side_effect=lambda *a, **kw: {}):
        result = server.recipes_sync(channel="canary")

    assert result["channel"] == "canary"


def test_sync_posts_current_versions_to_fleet_endpoint():
    captured: dict = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"to_install": [], "to_update": [], "unchanged": [], "removed": []}

    with patch.object(server, "_api_post", side_effect=fake_post), \
         patch.object(server, "_do_install", side_effect=lambda *a, **kw: {}):
        server.recipes_sync(channel="frozen")

    assert "fleet/sync" in captured["path"] or "sync" in captured["path"]
    assert captured["body"]["channel"] == "frozen"
    assert "current_versions" in captured["body"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 5: recipes_check
# ═══════════════════════════════════════════════════════════════════════════════


def test_check_returns_version_info():
    api_resp = {
        "slug": "seo-audit",
        "installed_version": "1.0.0",
        "latest_version": "1.1.0",
        "has_update": True,
        "changelog": "Fixed parser bug.",
        "breaking_changes": False,
    }
    with patch.object(server, "_api_get", return_value=api_resp):
        result = server.recipes_check("seo-audit")

    assert result["slug"] == "seo-audit"
    assert result["has_update"] is True
    assert result["latest_version"] == "1.1.0"
    assert result["breaking_changes"] is False


def test_check_calls_correct_endpoint():
    captured: dict = {}

    def fake_get(path, params=None):
        captured["path"] = path
        return {"slug": "test-skill", "has_update": False}

    with patch.object(server, "_api_get", side_effect=fake_get):
        server.recipes_check("test-skill")

    assert "test-skill" in captured["path"]
    assert "check" in captured["path"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tool 6: recipes_report_error
# ═══════════════════════════════════════════════════════════════════════════════


def test_report_error_posts_correct_payload():
    captured: dict = {}

    def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        return {"report_id": "rpt_abc123", "status": "received", "message": "ok"}

    with patch.object(server, "_api_post", side_effect=fake_post):
        result = server.recipes_report_error("seo-audit", "FileNotFoundError", "script not found")

    assert captured["body"]["slug"] == "seo-audit"
    assert captured["body"]["error_class"] == "FileNotFoundError"
    assert captured["body"]["error_msg"] == "script not found"
    assert "skill-error" in captured["path"]
    assert result["status"] == "received"


def test_report_error_stub_on_404():
    """When /v1/skill-error returns 404 (Phase C stub), return graceful stub dict."""
    import urllib.error

    def fake_post(path, body):
        raise urllib.error.HTTPError(
            url="https://fake/skill-error",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )

    with patch.object(server, "_api_post", side_effect=fake_post):
        result = server.recipes_report_error("test-skill", "RuntimeError", "oops")

    assert result["status"] == "stub"
    assert result["report_id"] is None


def test_report_error_reraises_non_404():
    """Non-404 HTTP errors must propagate (not swallowed)."""
    import urllib.error

    def fake_post(path, body):
        raise urllib.error.HTTPError(
            url="https://fake/skill-error",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
        )

    with patch.object(server, "_api_post", side_effect=fake_post), \
         pytest.raises(urllib.error.HTTPError):
        server.recipes_report_error("test-skill", "RuntimeError", "server error")
