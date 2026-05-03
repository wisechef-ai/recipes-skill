"""Tests for the framework installer entry script.

We don't actually run a profile in unit tests (that needs real network +
docker). Instead we verify the installer's flag parsing, host detection,
profile dispatch table, and --with-agentpact gating.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "recipes-installer" / "install-fleet.sh"
PROFILES = REPO_ROOT / "recipes-installer" / "profiles"


# ─── installer file is present and well-formed ──────────────────────────────


def test_installer_script_exists() -> None:
    assert INSTALLER.exists(), f"missing installer at {INSTALLER}"


def test_installer_is_executable() -> None:
    assert os.access(INSTALLER, os.X_OK), "install-fleet.sh must be executable"


def test_installer_has_shebang() -> None:
    first = INSTALLER.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!/"), f"missing shebang, got {first!r}"


def test_installer_passes_shellcheck_or_bash_n() -> None:
    """Either shellcheck (preferred) or `bash -n` must accept the script."""
    if shutil.which("shellcheck"):
        proc = subprocess.run(
            ["shellcheck", "-S", "error", str(INSTALLER)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
    else:
        proc = subprocess.run(
            ["bash", "-n", str(INSTALLER)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr


# ─── all 4 runtime profiles present ─────────────────────────────────────────


def test_all_four_runtime_profiles_present() -> None:
    expected = ["hermes.sh", "openclaw.sh", "byoa-codex.sh", "byoa-claudecode.sh"]
    actual = sorted(p.name for p in PROFILES.glob("*.sh"))
    for name in expected:
        assert name in actual, f"missing profile {name}; have {actual}"


def test_no_catch_all_generic_profile() -> None:
    """Premortem F2: no `generic` runtime — 4 explicit profiles only."""
    assert not (PROFILES / "generic.sh").exists()


# ─── flag parsing: dry-run mode reports what it would do ───────────────────


def _dry_run(*flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--non-interactive", *flags],
        capture_output=True,
        text=True,
        env={**os.environ, "RECIPES_DRY_RUN": "1"},
    )


def test_dry_run_default_runtime_is_hermes() -> None:
    proc = _dry_run()
    assert proc.returncode == 0, proc.stderr
    assert "runtime=hermes" in proc.stdout


def test_dry_run_explicit_runtime_openclaw() -> None:
    proc = _dry_run("--runtime=openclaw")
    assert proc.returncode == 0
    assert "runtime=openclaw" in proc.stdout


def test_dry_run_byoa_codex() -> None:
    proc = _dry_run("--runtime=byoa-codex")
    assert proc.returncode == 0
    assert "runtime=byoa-codex" in proc.stdout


def test_dry_run_byoa_claudecode() -> None:
    proc = _dry_run("--runtime=byoa-claudecode")
    assert proc.returncode == 0
    assert "runtime=byoa-claudecode" in proc.stdout


def test_dry_run_unknown_runtime_fails() -> None:
    proc = _dry_run("--runtime=does-not-exist")
    assert proc.returncode != 0


# ─── --with-agentpact opt-in ────────────────────────────────────────────────


def test_dry_run_without_agentpact_omits_it() -> None:
    proc = _dry_run("--runtime=hermes")
    assert proc.returncode == 0
    assert "agentpact=off" in proc.stdout
    # AgentPact must not appear elsewhere in dry-run output without the flag
    assert "agentpact=on" not in proc.stdout


def test_dry_run_with_agentpact_flag_enables_it() -> None:
    proc = _dry_run("--runtime=hermes", "--with-agentpact")
    assert proc.returncode == 0
    assert "agentpact=on" in proc.stdout


# ─── host detection probe ──────────────────────────────────────────────────


def test_dry_run_reports_host_capabilities() -> None:
    proc = _dry_run("--runtime=hermes")
    assert proc.returncode == 0
    # capabilities probe lines look like "cap: git=ok|missing"
    assert "cap:" in proc.stdout
    # at minimum we always probe these
    for tool in ("git", "python", "ssh", "tmux"):
        assert f"cap: {tool}=" in proc.stdout, proc.stdout
