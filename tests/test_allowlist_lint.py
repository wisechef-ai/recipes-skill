"""Tests for allowlist_lint — positive-allowlist PII linter.

Phase C of stabilization_2605. Premortem F1 fix: use a positive list of
permitted external strings (URLs, hostnames, emails, env vars, paths) per
skill, instead of a deny-regex.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LINTER = REPO_ROOT / "scripts" / "allowlist_lint.py"


def _run(skill_dir: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(LINTER), str(skill_dir), "--json"],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
    return proc.returncode, payload


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ─── allowlist match passes ─────────────────────────────────────────────────


def test_clean_skill_with_complete_allowlist_passes(tmp_path: Path) -> None:
    skill = tmp_path / "ok-skill"
    _write(skill / "SKILL.md", "Visit https://example.com for docs.\n")
    _write(
        skill / "MANIFEST.allowlist.yaml",
        "name: ok-skill\nallowlist:\n  urls:\n    - https://example.com\n",
    )
    code, out = _run(skill)
    assert code == 0, out
    assert out["findings"] == []


# ─── URL leak detected ──────────────────────────────────────────────────────


def test_url_not_in_allowlist_fails(tmp_path: Path) -> None:
    skill = tmp_path / "leaky"
    _write(skill / "SKILL.md", "See https://leak.example.org/docs\n")
    _write(skill / "MANIFEST.allowlist.yaml", "name: leaky\nallowlist: {}\n")
    code, out = _run(skill)
    assert code == 1, out
    kinds = {f["kind"] for f in out["findings"]}
    values = {f["value"] for f in out["findings"]}
    assert "url" in kinds
    assert "https://leak.example.org/docs" in values


# ─── env var detected ───────────────────────────────────────────────────────


def test_env_var_not_in_allowlist_fails(tmp_path: Path) -> None:
    skill = tmp_path / "env-leak"
    _write(skill / "SKILL.md", "export MY_SECRET_TOKEN=value\n")
    _write(skill / "MANIFEST.allowlist.yaml", "name: env-leak\nallowlist: {}\n")
    code, out = _run(skill)
    assert code == 1
    kinds = {f["kind"] for f in out["findings"]}
    assert "env_var" in kinds
    assert any(f["value"] == "MY_SECRET_TOKEN" for f in out["findings"])


def test_env_var_in_allowlist_passes(tmp_path: Path) -> None:
    skill = tmp_path / "env-ok"
    _write(skill / "SKILL.md", "Set OPENAI_API_KEY in your env.\n")
    _write(
        skill / "MANIFEST.allowlist.yaml",
        "name: env-ok\nallowlist:\n  env_vars:\n    - OPENAI_API_KEY\n",
    )
    code, out = _run(skill)
    assert code == 0, out


# ─── email detected ─────────────────────────────────────────────────────────


def test_email_not_in_allowlist_fails(tmp_path: Path) -> None:
    skill = tmp_path / "email-leak"
    _write(skill / "SKILL.md", "Contact alice@example.org for help.\n")
    _write(skill / "MANIFEST.allowlist.yaml", "name: email-leak\nallowlist: {}\n")
    code, out = _run(skill)
    assert code == 1
    kinds = {f["kind"] for f in out["findings"]}
    assert "email" in kinds


# ─── absolute path detected ─────────────────────────────────────────────────


def test_absolute_path_not_in_allowlist_fails(tmp_path: Path) -> None:
    skill = tmp_path / "path-leak"
    _write(skill / "SKILL.md", "Logs go to /var/log/myapp/output.log\n")
    _write(skill / "MANIFEST.allowlist.yaml", "name: path-leak\nallowlist: {}\n")
    code, out = _run(skill)
    assert code == 1
    kinds = {f["kind"] for f in out["findings"]}
    assert "path" in kinds


# ─── port detected ──────────────────────────────────────────────────────────


def test_port_in_url_in_allowlist_passes(tmp_path: Path) -> None:
    skill = tmp_path / "port-ok"
    _write(skill / "SKILL.md", "API at https://api.example.com:8200/v1\n")
    _write(
        skill / "MANIFEST.allowlist.yaml",
        "name: port-ok\nallowlist:\n  urls:\n    - https://api.example.com:8200/v1\n  ports:\n    - 8200\n",
    )
    code, out = _run(skill)
    assert code == 0, out


# ─── suggestion present in finding ──────────────────────────────────────────


def test_finding_includes_suggestion(tmp_path: Path) -> None:
    skill = tmp_path / "suggest"
    _write(skill / "SKILL.md", "https://surprise.example/path\n")
    _write(skill / "MANIFEST.allowlist.yaml", "name: suggest\nallowlist: {}\n")
    code, out = _run(skill)
    assert code == 1
    f = out["findings"][0]
    assert "suggestion" in f
    assert f["suggestion"]  # non-empty


# ─── line and span are reported ─────────────────────────────────────────────


def test_finding_includes_line_and_span(tmp_path: Path) -> None:
    skill = tmp_path / "loc"
    _write(skill / "SKILL.md", "First\nLink: https://nope.example\nThird\n")
    _write(skill / "MANIFEST.allowlist.yaml", "name: loc\nallowlist: {}\n")
    code, out = _run(skill)
    assert code == 1
    f = next(f for f in out["findings"] if f["kind"] == "url")
    assert f["line"] == 2
    assert f["span"][0] >= 0 and f["span"][1] > f["span"][0]


# ─── manifest missing ──────────────────────────────────────────────────────


def test_missing_manifest_fails(tmp_path: Path) -> None:
    skill = tmp_path / "no-manifest"
    _write(skill / "SKILL.md", "hi\n")
    code, out = _run(skill)
    assert code == 1
    # presence of error is enough
    assert "error" in out or "findings" in out


# ─── manifest itself is excluded from scan ─────────────────────────────────


def test_manifest_file_is_not_scanned(tmp_path: Path) -> None:
    """The manifest itself necessarily contains the allowed strings; it must
    not produce findings against itself."""
    skill = tmp_path / "self-scan"
    _write(skill / "SKILL.md", "see https://kept.example\n")
    _write(
        skill / "MANIFEST.allowlist.yaml",
        "name: self-scan\nallowlist:\n  urls:\n    - https://kept.example\n",
    )
    code, out = _run(skill)
    assert code == 0, out
