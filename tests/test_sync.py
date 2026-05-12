"""
tests/test_sync.py — Test suite for `recipes sync` command.

Tests (≥6 required):
  1. test_sync_no_skills_installed         — sync exits cleanly when no skills found
  2. test_sync_dry_run_no_changes          — dry-run reports current, makes no changes
  3. test_sync_detects_update_available     — dry-run reports update available
  4. test_sync_writes_changelog             — sync writes entries to recipes-sync.log
  5. test_sync_persists_state               — sync writes recipes-sync-state.json
  6. test_sync_detects_local_edits          — sync skips skill with locally edited files
  7. test_sync_quiet_mode                   — quiet mode suppresses stdout
  8. test_sync_stable_channel_skips_prerelease — stable channel skips pre-release versions

Run with:
  pytest tests/test_sync.py -v
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import pathlib
import sys
import time

import pytest

CLI = pathlib.Path(__file__).parent.parent / "bin" / "recipes"
PYTHON = sys.executable


def load_cli_module(name: str = "recipes_sync_test"):
    """Load bin/recipes as a Python module."""
    loader = importlib.machinery.SourceFileLoader(name, str(CLI))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _make_installed_skill(
    skills_dir: pathlib.Path,
    slug: str = "test-skill",
    version: str = "1.0.0",
    category: str = "general",
    files: dict[str, str] | None = None,
) -> pathlib.Path:
    """Create a fake installed skill directory with .recipes-meta.json."""
    skill_dir = skills_dir / category / slug
    skill_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "slug": slug,
        "version": version,
        "installed_at": "2026-05-10T12:00:00+00:00",
        "sha256": "abc123",
        "source_url": "https://recipes.wisechef.ai/api/skills/test-skill/download",
    }
    (skill_dir / ".recipes-meta.json").write_text(json.dumps(meta, indent=2))

    if files:
        for fname, content in files.items():
            fpath = skill_dir / fname
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content)

    return skill_dir


class MockAPI:
    """Context manager that monkeypatches api_get to return controlled responses."""

    def __init__(self, responses: dict[str, dict]):
        """
        responses: {slug: {"version": "x.y.z", ...}}
        """
        self.responses = responses
        self._orig = None

    def __enter__(self):
        self._mod = load_cli_module()
        self._orig = self._mod.api_get

        def _mock_get(url: str, headers=None):
            # Extract slug from URL
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            slug = qs.get("slug", [""])[0]
            if slug in self.responses:
                return self.responses[slug]
            raise SystemExit(f"HTTP 404: skill {slug} not found")

        self._mod.api_get = _mock_get
        return self._mod

    def __exit__(self, *args):
        if self._orig:
            self._mod.api_get = self._orig


class TestSyncNoSkills:
    def test_sync_no_skills_installed(self, tmp_path, monkeypatch):
        """sync exits cleanly when no skills are installed."""
        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", tmp_path / "skills")
        monkeypatch.setattr(mod, "SYNC_LOG", tmp_path / "sync.log")
        monkeypatch.setattr(mod, "SYNC_STATE", tmp_path / "sync-state.json")

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=False, channel="stable")
        # Should not crash, just print "No skills installed"
        mod.cmd_sync(args)


class TestSyncDryRun:
    def test_sync_dry_run_no_changes(self, tmp_path, monkeypatch, capsys):
        """dry-run reports current when all skills are up-to-date."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", tmp_path / "sync.log")
        monkeypatch.setattr(mod, "SYNC_STATE", tmp_path / "sync-state.json")

        # Mock API to return same version
        def mock_get(url, headers=None):
            return {"version": "1.0.0", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=True, quiet=False, channel="stable")
        mod.cmd_sync(args)

        out = capsys.readouterr().out
        assert "Sync complete (dry-run)" in out
        assert "0 updated" in out

    def test_sync_dry_run_detects_update(self, tmp_path, monkeypatch, capsys):
        """dry-run reports update available."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", tmp_path / "sync.log")
        monkeypatch.setattr(mod, "SYNC_STATE", tmp_path / "sync-state.json")

        def mock_get(url, headers=None):
            return {"version": "2.0.0", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=True, quiet=False, channel="stable")
        mod.cmd_sync(args)

        out = capsys.readouterr().out
        assert "1.0.0" in out and "2.0.0" in out
        assert "1 updated" in out


class TestSyncLog:
    def test_sync_writes_changelog(self, tmp_path, monkeypatch):
        """sync writes entries to recipes-sync.log."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        sync_log = tmp_path / "sync.log"
        sync_state = tmp_path / "sync-state.json"

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", sync_log)
        monkeypatch.setattr(mod, "SYNC_STATE", sync_state)

        def mock_get(url, headers=None):
            return {"version": "1.0.0", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=True, channel="stable")
        mod.cmd_sync(args)

        assert sync_log.exists()
        log_content = sync_log.read_text()
        assert "OK" in log_content or "skipped_current" in log_content or "my-skill" in log_content

    def test_sync_persists_state(self, tmp_path, monkeypatch):
        """sync writes recipes-sync-state.json."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        sync_log = tmp_path / "sync.log"
        sync_state = tmp_path / "sync-state.json"

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", sync_log)
        monkeypatch.setattr(mod, "SYNC_STATE", sync_state)

        def mock_get(url, headers=None):
            return {"version": "1.0.0", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=True, channel="stable")
        mod.cmd_sync(args)

        assert sync_state.exists()
        state = json.loads(sync_state.read_text())
        assert state["channel"] == "stable"
        assert "my-skill" in state["skills"]
        assert state["skills"]["my-skill"]["version"] == "1.0.0"


class TestSyncLocalEdits:
    def test_sync_detects_local_edits(self, tmp_path, monkeypatch, capsys):
        """sync skips skill with locally edited files."""
        skills_dir = tmp_path / "skills"
        skill_path = _make_installed_skill(
            skills_dir,
            "my-skill",
            "1.0.0",
            files={"SKILL.md": "original content"},
        )

        # Set meta file mtime to the past so edit detection triggers
        meta_file = skill_path / ".recipes-meta.json"
        old_mtime = meta_file.stat().st_mtime - 10
        os.utime(meta_file, (old_mtime, old_mtime))

        # Now edit a file — its mtime will be newer than meta's
        edited_file = skill_path / "SKILL.md"
        edited_file.write_text("modified content")

        sync_log = tmp_path / "sync.log"
        sync_state = tmp_path / "sync-state.json"

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", sync_log)
        monkeypatch.setattr(mod, "SYNC_STATE", sync_state)

        def mock_get(url, headers=None):
            return {"version": "2.0.0", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=False, channel="stable")
        mod.cmd_sync(args)

        out = capsys.readouterr().out
        assert "local edits" in out.lower() or "skipped" in out.lower()
        # State should still show old version
        state = json.loads(sync_state.read_text())
        assert state["skills"]["my-skill"]["version"] == "1.0.0"


class TestSyncQuietMode:
    def test_sync_quiet_mode(self, tmp_path, monkeypatch, capsys):
        """quiet mode suppresses stdout."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", tmp_path / "sync.log")
        monkeypatch.setattr(mod, "SYNC_STATE", tmp_path / "sync-state.json")

        def mock_get(url, headers=None):
            return {"version": "1.0.0", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=True, channel="stable")
        mod.cmd_sync(args)

        out = capsys.readouterr().out
        assert out == ""


class TestSyncChannel:
    def test_sync_stable_skips_prerelease(self, tmp_path, monkeypatch, capsys):
        """stable channel skips pre-release versions (versions with '-')."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        sync_log = tmp_path / "sync.log"
        sync_state = tmp_path / "sync-state.json"

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", sync_log)
        monkeypatch.setattr(mod, "SYNC_STATE", sync_state)

        def mock_get(url, headers=None):
            return {"version": "2.0.0-beta.1", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=False, channel="stable")
        mod.cmd_sync(args)

        out = capsys.readouterr().out
        assert "pre-release" in out
        # State should show old version since we skipped the pre-release
        state = json.loads(sync_state.read_text())
        assert state["skills"]["my-skill"]["version"] == "1.0.0"

    def test_sync_latest_includes_prerelease(self, tmp_path, monkeypatch, capsys):
        """latest channel does NOT skip pre-release versions."""
        skills_dir = tmp_path / "skills"
        _make_installed_skill(skills_dir, "my-skill", "1.0.0")

        sync_log = tmp_path / "sync.log"
        sync_state = tmp_path / "sync-state.json"

        mod = load_cli_module()
        monkeypatch.setattr(mod, "SKILLS_DIR", skills_dir)
        monkeypatch.setattr(mod, "SYNC_LOG", sync_log)
        monkeypatch.setattr(mod, "SYNC_STATE", sync_state)

        def mock_get(url, headers=None):
            return {"version": "2.0.0-beta.1", "slug": "my-skill", "tarball_url": "https://example.com/t.tar.gz"}

        monkeypatch.setattr(mod, "api_get", mock_get)

        # Mock cmd_install to avoid actually downloading
        install_calls = []
        def mock_install(args):
            install_calls.append(args.slug)

        monkeypatch.setattr(mod, "cmd_install", mock_install)

        import argparse
        args = argparse.Namespace(dry_run=False, quiet=False, channel="latest")
        mod.cmd_sync(args)

        out = capsys.readouterr().out
        assert "1.0.0" in out and "2.0.0-beta.1" in out
        assert "1 updated" in out
        assert install_calls == ["my-skill@2.0.0-beta.1"]
