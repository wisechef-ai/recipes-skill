"""Tests for `recipes capabilities` and `recipes onboard` subcommands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECIPES = REPO_ROOT / "bin" / "recipes"


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RECIPES), *args],
        capture_output=True,
        text=True,
        input=stdin,
    )


# ─── capabilities ──────────────────────────────────────────────────────────-


def test_capabilities_text_output_lists_known_tools() -> None:
    proc = _run("capabilities")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    for tool in ("git", "python", "ssh", "tmux"):
        assert tool in out, f"capabilities text output missing {tool}: {out}"


def test_capabilities_json_is_valid_and_machine_readable() -> None:
    proc = _run("capabilities", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "os" in payload
    assert "capabilities" in payload
    caps = payload["capabilities"]
    for tool in ("git", "python", "ssh", "tmux", "docker", "node"):
        assert tool in caps
        assert caps[tool] in ("ok", "missing")


# ─── onboard ───────────────────────────────────────────────────────────────-


def test_onboard_non_interactive_suggests_starter_pack() -> None:
    """In non-interactive mode, onboard prints a recommendation and exits 0."""
    proc = _run("onboard", "--non-interactive")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    # the recommendation must mention one of the bundle names
    assert ("starter-solo-operator" in out) or ("starter-fleet-operator" in out)


def test_onboard_with_goal_solo_returns_solo_bundle() -> None:
    proc = _run("onboard", "--non-interactive", "--goal=solo")
    assert proc.returncode == 0, proc.stderr
    assert "starter-solo-operator" in proc.stdout


def test_onboard_with_goal_fleet_returns_fleet_bundle() -> None:
    proc = _run("onboard", "--non-interactive", "--goal=fleet")
    assert proc.returncode == 0, proc.stderr
    assert "starter-fleet-operator" in proc.stdout


def test_onboard_unknown_goal_fails() -> None:
    proc = _run("onboard", "--non-interactive", "--goal=does-not-exist")
    assert proc.returncode != 0


def test_onboard_json_output() -> None:
    proc = _run("onboard", "--non-interactive", "--goal=solo", "--json")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["bundle"] == "starter-solo-operator"
    assert "skills" in payload
    assert isinstance(payload["skills"], list)
    assert len(payload["skills"]) >= 1
