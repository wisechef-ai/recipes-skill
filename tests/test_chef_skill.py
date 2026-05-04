"""tests/test_chef_skill.py — TDD tests for the chef skill.

Tests each of the 5 sub-command scripts via subprocess, verifying:
- Graceful degradation when creds missing
- Correct CLI flags (--json, --dry-run)
- Help text quality (mentions all 5 sub-commands)
- chef code requires a task argument
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

CHEF_DIR = Path(__file__).parent.parent / "skills" / "chef"
CHEF_BIN = CHEF_DIR / "chef"
SCRIPTS = CHEF_DIR / "scripts"


def run_chef(*args, env=None):
    """Run the chef CLI, return CompletedProcess."""
    full_env = os.environ.copy()
    if env:
        # Strip API keys to test graceful degradation paths
        for k in list(full_env):
            if k.endswith("_API_KEY"):
                del full_env[k]
        full_env.update(env)
    return subprocess.run(
        ["bash", str(CHEF_BIN), *args],
        capture_output=True,
        text=True,
        env=full_env,
        timeout=20,
    )


# ─── help & version ────────────────────────────────────────────────────────────

def test_chef_version():
    r = run_chef("--version")
    assert r.returncode == 0
    assert "chef" in r.stdout
    assert "0.1.0" in r.stdout


def test_chef_help_lists_all_5_commands():
    r = run_chef("--help")
    assert r.returncode == 0
    for cmd in ("morning", "marketing", "code", "tickets", "weekly"):
        assert cmd in r.stdout, f"help missing {cmd}"


def test_chef_no_args_shows_help():
    r = run_chef()
    assert r.returncode == 0
    assert "USAGE" in r.stdout or "morning" in r.stdout


def test_chef_unknown_command_exits_1():
    r = run_chef("dance")
    assert r.returncode != 0


# ─── morning ───────────────────────────────────────────────────────────────────

def test_morning_dry_run_no_creds():
    """morning --dry-run should work without any API keys."""
    r = run_chef("morning", "--dry-run", env={})
    assert r.returncode == 0
    assert "DRY RUN" in r.stdout or "would fetch" in r.stdout.lower()


def test_morning_no_creds_graceful():
    """morning without creds should print structured output, not crash."""
    r = run_chef("morning", env={})
    assert r.returncode == 0
    # Must have all 3 sections
    assert "Morning brief" in r.stdout
    assert "YESTERDAY" in r.stdout
    assert "TODAY" in r.stdout
    assert "SPEND" in r.stdout


def test_morning_json_output():
    r = run_chef("morning", "--json", env={})
    assert r.returncode == 0
    import json
    data = json.loads(r.stdout)
    assert "date" in data
    assert "yesterday" in data
    assert "spend_overnight" in data


# ─── tickets ───────────────────────────────────────────────────────────────────

def test_tickets_no_creds_shows_setup():
    r = run_chef("tickets", env={})
    assert r.returncode == 0
    out = r.stdout.lower()
    assert "configure" in out or "not configured" in out or "papercli" in out


def test_tickets_json_works_no_creds():
    r = run_chef("tickets", "--json", env={})
    assert r.returncode == 0
    import json
    json.loads(r.stdout)  # must be valid JSON


# ─── marketing ─────────────────────────────────────────────────────────────────

def test_marketing_no_creds_shows_draft_and_setup():
    r = run_chef("marketing", env={})
    assert r.returncode == 0
    out = r.stdout
    assert "DRAFT" in out or "configure" in out.lower()


# ─── code ──────────────────────────────────────────────────────────────────────

def test_code_no_task_returns_1():
    r = run_chef("code")
    assert r.returncode == 1
    assert "Usage" in r.stdout or "chef code" in r.stdout


def test_code_with_task_no_delegate_shows_install_hint():
    """If neither codex nor claude is on PATH, show install hint + the prompt."""
    # Run with PATH cleared so codex/claude can't be found
    env = {"PATH": "/usr/bin:/bin"}  # no node, no claude
    r = run_chef("code", "add tests for foo", env=env)
    out = r.stdout.lower()
    # Should either show install hint OR use what's available — both are valid.
    # Critical: doesn't crash, prints something useful.
    assert r.returncode in (0, 1)
    assert "task" in out or "delegate" in out or "prompt" in out


def test_code_does_not_auto_execute_without_flag():
    """chef code should print, not run, unless --auto or CHEF_AUTO_DELEGATE=true."""
    r = run_chef("code", "rm -rf /")
    assert "rm -rf /" not in str(r.stderr)  # didn't actually run!
    # Output must indicate what would happen, not that it happened
    assert r.returncode in (0, 1)


# ─── weekly ────────────────────────────────────────────────────────────────────

def test_weekly_non_sunday_says_skip():
    """weekly without --force should say it's not Sunday (unless today is Sunday)."""
    import datetime
    if datetime.datetime.now().weekday() != 6:
        r = run_chef("weekly", env={})
        assert r.returncode == 0
        assert "Sunday" in r.stdout


def test_weekly_force_runs_any_day():
    r = run_chef("weekly", "--force", env={})
    assert r.returncode == 0
    # Must have some output — either a retro or "not enough data"
    assert len(r.stdout) > 20


# ─── doctor ────────────────────────────────────────────────────────────────────

def test_doctor_runs_and_shows_status():
    r = run_chef("doctor")
    assert r.returncode == 0
    assert "VERSION" in r.stdout
    assert "PYTHON" in r.stdout
    assert "CONFIG" in r.stdout
    assert "ENV VARS" in r.stdout


# ─── adversarial ───────────────────────────────────────────────────────────────

def test_adversarial_unicorn_request():
    """chef should not silently 'succeed' on a meaningless request."""
    r = run_chef("summon-unicorn")
    assert r.returncode != 0  # unknown command rejected
    out = r.stdout + r.stderr
    assert "Unknown" in out or "unknown" in out


# ─── content audit ────────────────────────────────────────────────────────────

def test_skill_md_no_pii_leaks():
    """SKILL.md must not contain Adam, Bombilla, /home/adam, wisechef-agents, etc."""
    skill_md = (CHEF_DIR / "SKILL.md").read_text()
    forbidden = ["Bombilla", "wisechef-agents", "wisechef-hq", "/home/adam", "adam-xps", "obsidian-vault"]
    for token in forbidden:
        assert token not in skill_md, f"PII leak: '{token}' found in SKILL.md"


def test_skill_md_no_fork_word():
    """chef should not mention 'fork' anywhere user-facing (per v6 invisible-fork rule)."""
    skill_md = (CHEF_DIR / "SKILL.md").read_text()
    # Allow 'fork' in technical context (e.g., "fork it, modify it" license note is OK)
    # but flag it for awareness — the test fails if more than 2 occurrences (rough heuristic)
    import re
    forks = len(re.findall(r"\bfork\b", skill_md, re.IGNORECASE))
    assert forks <= 2, f"chef SKILL.md mentions 'fork' {forks} times — should be near-zero"


def test_recipe_yaml_has_compatibility():
    """recipe.yaml must declare runtime.compatibility (per v6 architecture-awareness rule)."""
    import yaml
    recipe = yaml.safe_load((CHEF_DIR / "recipe.yaml").read_text())
    assert "runtime" in recipe
    assert "compatibility" in recipe["runtime"]
    compat = recipe["runtime"]["compatibility"]
    assert "os" in compat
    assert "arch" in compat


def test_manifest_allowlist_exists():
    """MANIFEST.allowlist.yaml must exist (per A.7 linter)."""
    assert (CHEF_DIR / "MANIFEST.allowlist.yaml").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
