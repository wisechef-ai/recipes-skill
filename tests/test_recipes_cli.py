"""
tests/test_recipes_cli.py — Test suite for bin/recipes CLI.

Tests (≥6 required):
  1.  test_init_creates_files            — init creates skill.toml + SKILL.md
  2.  test_init_valid_toml               — init produces valid, parseable skill.toml
  3.  test_init_refuses_overwrite        — init exits non-zero if files exist
  4.  test_pack_determinism              — two packs of same content → same sha256
  5.  test_pack_excludes_git             — .git dir not in tarball
  6.  test_install_bad_sha256_fails      — install rejects tarball with wrong sha256
  7.  test_install_writes_meta           — install writes .recipes-meta.json
  8.  test_list_reads_meta               — list reads meta and prints slug/version
  9.  test_publish_dryrun_fields         — publish (mocked server) sends expected fields
  10. test_update_skips_when_current     — update skips if version already matches

Run with:
  pytest tests/test_recipes_cli.py -v
"""

from __future__ import annotations

import gzip
import hashlib
import http.server
import io
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import tomllib
import urllib.parse
from datetime import datetime, timezone

import importlib.machinery
import importlib.util

import pytest

# ─── Path to the CLI ─────────────────────────────────────────────────────────

CLI = pathlib.Path(__file__).parent.parent / "bin" / "recipes"
PYTHON = sys.executable


def load_cli_module(name: str):
    """Load bin/recipes as a Python module (no .py extension — needs manual loader)."""
    loader = importlib.machinery.SourceFileLoader(name, str(CLI))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run_cli(*args: str, cwd: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run recipes CLI with given args, return CompletedProcess."""
    cmd = [PYTHON, str(CLI)] + list(args)
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=merged_env,
        capture_output=True,
        text=True,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_deterministic_tarball(files: dict[str, bytes]) -> bytes:
    """Build a deterministic tar.gz from a dict of {name: content}."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name=name)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))

    raw_bytes = raw.getvalue()
    gz_buf = io.BytesIO()
    import gzip as gzip_mod
    with gzip_mod.GzipFile(fileobj=gz_buf, mode="wb", mtime=0, compresslevel=6) as gz:
        gz.write(raw_bytes)
    return gz_buf.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_skill_dir(tmp_path: pathlib.Path, name: str = "test-skill", version: str = "0.1.0") -> pathlib.Path:
    """Create a minimal skill dir and return its path."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    toml = (
        f"[skill]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        f'description = "A test skill"\n'
        f'license = "MIT"\n'
        f'entrypoint = "SKILL.md"\n'
        f'tier = "cook"\n'
        f'is_public = false\n'
    )
    (skill_dir / "skill.toml").write_text(toml)
    (skill_dir / "SKILL.md").write_text(f"# {name}\n\nA test skill.\n")
    return skill_dir


# ─── Tiny HTTP Server Fixture ─────────────────────────────────────────────────

class RecordingHandler(http.server.BaseHTTPRequestHandler):
    """Records requests and serves canned responses."""

    _registry: dict  # filled by fixture

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        resp = self.server._routes.get(("GET", parsed.path), (404, {}, b"not found"))
        status, headers, body = resp
        if callable(body):
            body = body(parsed)
        self.server._requests.append(("GET", self.path, None))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.server._requests.append(("POST", self.path, body))
        resp = self.server._routes.get(("POST", self.path), (200, {}, {"ok": True}))
        status, headers, rbody = resp
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(rbody if isinstance(rbody, bytes) else json.dumps(rbody).encode())

    def log_message(self, *args) -> None:  # silence output
        pass


class RecordingServer(http.server.HTTPServer):
    def __init__(self, routes: dict):
        super().__init__(("127.0.0.1", 0), RecordingHandler)
        self._routes = routes  # {("GET", "/path"): (status, headers, body)}
        self._requests: list = []


def start_server(routes: dict) -> tuple[RecordingServer, str, threading.Thread]:
    srv = RecordingServer(routes)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{port}", t


# ─── Test 1: init creates both files ─────────────────────────────────────────

def test_init_creates_files(tmp_path):
    """init should create skill.toml and SKILL.md in the target dir."""
    result = run_cli("init", "my-cool-skill", cwd=str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "skill.toml").exists(), "skill.toml was not created"
    assert (tmp_path / "SKILL.md").exists(), "SKILL.md was not created"


# ─── Test 2: init produces valid skill.toml ───────────────────────────────────

def test_init_valid_toml(tmp_path):
    """init should produce a parseable skill.toml with correct keys."""
    run_cli("init", "my-cool-skill", cwd=str(tmp_path))
    with open(tmp_path / "skill.toml", "rb") as f:
        data = tomllib.load(f)

    skill = data.get("skill", data)  # support both flat and [skill]-table forms
    assert skill["name"] == "my-cool-skill"
    assert skill["version"] == "0.1.0"
    assert skill["license"] == "MIT"
    assert skill["entrypoint"] == "SKILL.md"
    assert skill["tier"] == "cook"
    assert skill["is_public"] is False


# ─── Test 3: init refuses overwrite ───────────────────────────────────────────

def test_init_refuses_overwrite(tmp_path):
    """init should exit non-zero if skill.toml or SKILL.md already exist."""
    run_cli("init", "skill-one", cwd=str(tmp_path))
    result = run_cli("init", "skill-one", cwd=str(tmp_path))
    assert result.returncode != 0
    assert "overwrite" in result.stderr.lower() or "exists" in result.stderr.lower()


# ─── Test 4: pack is deterministic ────────────────────────────────────────────

def test_pack_determinism(tmp_path):
    """Two pack invocations of same content should produce identical sha256."""
    skill_dir = make_skill_dir(tmp_path)
    out1 = tmp_path / "pack1.tar.gz"
    out2 = tmp_path / "pack2.tar.gz"
    r1 = run_cli("pack", f"--out={out1}", cwd=str(skill_dir))
    time.sleep(1)  # wait a second — gzip should still be identical
    r2 = run_cli("pack", f"--out={out2}", cwd=str(skill_dir))
    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr
    assert out1.read_bytes() == out2.read_bytes(), "Tarball content should be identical"
    # Also verify sha256 lines match
    sha1 = [line for line in r1.stdout.splitlines() if "sha256:" in line][0]
    sha2 = [line for line in r2.stdout.splitlines() if "sha256:" in line][0]
    assert sha1 == sha2


# ─── Test 5: pack excludes .git ───────────────────────────────────────────────

def test_pack_excludes_git(tmp_path):
    """Tarball must not contain any .git entries."""
    skill_dir = make_skill_dir(tmp_path)
    git_dir = skill_dir / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

    out = tmp_path / "test.tar.gz"
    r = run_cli("pack", f"--out={out}", cwd=str(skill_dir))
    assert r.returncode == 0, r.stderr

    with tarfile.open(str(out), "r:gz") as tar:
        names = tar.getnames()

    assert not any(".git" in n for n in names), f".git appeared in tarball: {names}"


# ─── Test 6: install rejects bad sha256 ──────────────────────────────────────

def test_install_bad_sha256_fails(tmp_path, monkeypatch):
    """install must fail if the downloaded tarball sha256 does not match."""
    tarball_content = make_deterministic_tarball({"SKILL.md": b"# test\n"})
    good_sha = sha256(tarball_content)
    bad_sha = "0" * 64  # deliberately wrong

    install_meta = {
        "slug": "bad-sha-skill",
        "version": "0.1.0",
        "tarball_url": "__TARBALL_URL__",
        "sha256": bad_sha,
        "manifest": {"category": "test"},
    }

    routes = {
        ("GET", "/skills/install"): (200, {}, install_meta),
        ("GET", "/tarball/bad-sha-skill-0.1.0.tar.gz"): (200, {}, tarball_content),
    }

    srv, base, _ = start_server(routes)
    # Patch tarball_url to point at local server
    install_meta["tarball_url"] = f"{base}/tarball/bad-sha-skill-0.1.0.tar.gz"

    # Patch the CLI's API_BASE to point at local server
    env_extra = {
        "RECIPES_API_BASE": base,
        "HERMES_SKILLS_DIR": str(tmp_path / "hermes_skills"),
    }

    # We need to monkeypatch the API_BASE in the CLI. Since it's a single file
    # script, we can pass the base via env and patch via a wrapper, OR we can
    # import the module directly.
    mod = load_cli_module("recipes_cli_test6")

    # Patch API_BASE and SKILLS_DIR in the module
    original_api = mod.API_BASE
    original_skills = mod.SKILLS_DIR
    mod.API_BASE = base
    mod.SKILLS_DIR = tmp_path / "hermes_skills"

    try:
        class FakeArgs:
            slug = "bad-sha-skill"
            force = False
            client_mode = False
            report_to = None

        with pytest.raises(SystemExit) as exc:
            mod.cmd_install(FakeArgs())
        # SystemExit with a string message means sha256 mismatch was detected
        exit_val = str(exc.value)
        assert "mismatch" in exit_val.lower() or "sha256" in exit_val.lower(), (
            f"Expected sha256 mismatch error, got: {exit_val}"
        )
    finally:
        mod.API_BASE = original_api
        mod.SKILLS_DIR = original_skills
        srv.shutdown()


# ─── Test 7: install writes .recipes-meta.json ────────────────────────────────

def test_install_writes_meta(tmp_path):
    """install should write .recipes-meta.json with correct fields."""
    tarball_content = make_deterministic_tarball({
        "SKILL.md": b"# test-skill\n\nA skill.\n",
        "skill.toml": b"[skill]\nname = \"test-skill\"\nversion = \"1.2.3\"\n",
    })
    good_sha = sha256(tarball_content)

    install_meta = {
        "slug": "test-skill",
        "version": "1.2.3",
        "tarball_url": "__TARBALL_URL__",
        "sha256": good_sha,
        "manifest": {"category": "general"},
    }

    routes: dict = {}
    srv = RecordingServer(routes)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    install_meta["tarball_url"] = f"{base}/tarball/test-skill-1.2.3.tar.gz"

    routes[("GET", "/skills/install")] = (200, {}, install_meta)
    routes[("GET", "/tarball/test-skill-1.2.3.tar.gz")] = (200, {}, tarball_content)

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    mod = load_cli_module("recipes_cli_test7")

    skills_dir = tmp_path / "hermes_skills"
    original_api = mod.API_BASE
    original_skills = mod.SKILLS_DIR
    mod.API_BASE = base
    mod.SKILLS_DIR = skills_dir

    try:
        class FakeArgs:
            slug = "test-skill"
            force = False
            client_mode = False
            report_to = None

        mod.cmd_install(FakeArgs())

        meta_path = skills_dir / "general" / "test-skill" / ".recipes-meta.json"
        assert meta_path.exists(), f".recipes-meta.json not found at {meta_path}"

        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["slug"] == "test-skill"
        assert meta["version"] == "1.2.3"
        assert meta["sha256"] == good_sha
        assert "installed_at" in meta
        assert "source_url" in meta
    finally:
        mod.API_BASE = original_api
        mod.SKILLS_DIR = original_skills
        srv.shutdown()


# ─── Test 8: list reads .recipes-meta.json ────────────────────────────────────

def test_list_reads_meta(tmp_path, monkeypatch):
    """list should read .recipes-meta.json files and print slug + version."""
    skills_dir = tmp_path / "hermes_skills"
    meta = {
        "slug": "my-listed-skill",
        "version": "2.5.1",
        "installed_at": "2026-01-01T00:00:00+00:00",
        "sha256": "abc123",
        "source_url": "https://recipes.wisechef.ai/tarballs/my-listed-skill-2.5.1.tar.gz",
    }
    skill_dir = skills_dir / "devops" / "my-listed-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / ".recipes-meta.json").write_text(json.dumps(meta))

    mod = load_cli_module("recipes_cli_test8")

    original_skills = mod.SKILLS_DIR
    mod.SKILLS_DIR = skills_dir

    import io as _io
    captured = _io.StringIO()

    try:
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured

        class FakeArgs:
            pass

        mod.cmd_list(FakeArgs())
    finally:
        sys.stdout = old_stdout
        mod.SKILLS_DIR = original_skills

    output = captured.getvalue()
    assert "my-listed-skill" in output
    assert "2.5.1" in output
    assert "2026-01-01" in output


# ─── Test 9: publish (mocked) sends expected multipart fields ─────────────────

def test_publish_dryrun_fields(tmp_path):
    """publish should POST multipart with skill_toml, tarball, signature, signing_pubkey files + is_public field."""
    received: list[tuple] = []

    class CaptureHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            received.append(("POST", self.path, self.headers.get("Content-Type", ""), body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = json.dumps({
                "slug": "test-pub-skill",
                "version": "0.1.0",
                "url": "https://recipes.wisechef.ai/skills/test-pub-skill",
            })
            self.wfile.write(resp.encode())

        def log_message(self, *args):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), CaptureHandler)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    skill_dir = make_skill_dir(tmp_path, name="test-pub-skill")

    mod = load_cli_module("recipes_cli_test9")

    original_api = mod.API_BASE
    original_keys = mod.KEYS_DIR
    mod.API_BASE = base
    mod.KEYS_DIR = tmp_path / "keys"

    try:
        class FakeArgs:
            api_key = "rec_test_key_12345"
            private = False

        old_cwd = os.getcwd()
        os.chdir(skill_dir)

        import io as _io
        captured = _io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            mod.cmd_publish(FakeArgs())
        finally:
            sys.stdout = old_stdout
            os.chdir(old_cwd)

        output = captured.getvalue()

        assert len(received) == 1, f"Expected 1 POST, got {len(received)}"
        method, path, content_type, body = received[0]
        assert "multipart/form-data" in content_type

        body_str = body.decode("latin-1")
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

        # CLI should have printed version and URL
        assert "0.1.0" in output
        assert "test-pub-skill" in output or "Published" in output

    finally:
        mod.API_BASE = original_api
        mod.KEYS_DIR = original_keys
        srv.shutdown()


# ─── Test 10: update skips when version is current ────────────────────────────

def test_update_skips_when_current(tmp_path):
    """update should skip a skill if installed version == latest from API."""
    skills_dir = tmp_path / "hermes_skills"
    skill_meta = {
        "slug": "up-to-date-skill",
        "version": "3.0.0",
        "installed_at": "2026-01-01T00:00:00+00:00",
        "sha256": "abc123",
        "source_url": "https://recipes.wisechef.ai/tarballs/up-to-date-skill-3.0.0.tar.gz",
    }
    skill_dir = skills_dir / "general" / "up-to-date-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / ".recipes-meta.json").write_text(json.dumps(skill_meta))

    # Mock API returning same version
    api_response = {
        "slug": "up-to-date-skill",
        "version": "3.0.0",
        "tarball_url": "https://recipes.wisechef.ai/tarballs/up-to-date-skill-3.0.0.tar.gz",
        "sha256": "abc123",
        "manifest": {"category": "general"},
    }

    routes = {
        ("GET", "/skills/install"): (200, {}, api_response),
    }
    srv, base, _ = start_server(routes)

    mod = load_cli_module("recipes_cli_test10")

    original_api = mod.API_BASE
    original_skills = mod.SKILLS_DIR
    mod.API_BASE = base
    mod.SKILLS_DIR = skills_dir

    import io as _io
    captured = _io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    try:
        class FakeArgs:
            slug = None

        mod.cmd_update(FakeArgs())
    finally:
        sys.stdout = old_stdout
        mod.API_BASE = original_api
        mod.SKILLS_DIR = original_skills
        srv.shutdown()

    output = captured.getvalue()
    # Should report already at latest, no update triggered
    assert "latest" in output.lower() or "already" in output.lower()
    # Should NOT say "updated" or "Installed"
    assert "Installed" not in output


# ─── Test 11: install uses skill.toml category when manifest.category absent ──

def test_install_uses_skill_toml_category(tmp_path):
    """install should fall back to [skill].category from tarball's skill.toml
    when manifest.category is absent from the install response."""
    # Build a tarball that includes a skill.toml declaring category = "devops"
    skill_toml_content = (
        b"[skill]\n"
        b'name = "devops-tool"\n'
        b'version = "0.2.0"\n'
        b'category = "devops"\n'
        b'description = "A devops skill"\n'
        b'license = "MIT"\n'
        b'entrypoint = "SKILL.md"\n'
        b'tier = "cook"\n'
        b'is_public = false\n'
    )
    tarball_content = make_deterministic_tarball({
        "SKILL.md": b"# devops-tool\n\nA devops skill.\n",
        "skill.toml": skill_toml_content,
    })
    good_sha = sha256(tarball_content)

    # Install response with NO manifest.category (empty manifest)
    install_meta = {
        "slug": "devops-tool",
        "version": "0.2.0",
        "tarball_url": "__TARBALL_URL__",
        "checksum_sha256": good_sha,
        "manifest": {},  # no category — forces fallback to skill.toml
    }

    routes: dict = {}
    srv = RecordingServer(routes)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    install_meta["tarball_url"] = f"{base}/tarball/devops-tool-0.2.0.tar.gz"

    routes[("GET", "/skills/install")] = (200, {}, install_meta)
    routes[("GET", "/tarball/devops-tool-0.2.0.tar.gz")] = (200, {}, tarball_content)

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    mod = load_cli_module("recipes_cli_test11")
    skills_dir = tmp_path / "hermes_skills"
    original_api = mod.API_BASE
    original_skills = mod.SKILLS_DIR
    mod.API_BASE = base
    mod.SKILLS_DIR = skills_dir

    try:
        class FakeArgs:
            slug = "devops-tool"
            force = False
            client_mode = False
            report_to = None

        mod.cmd_install(FakeArgs())

        # Must be installed under devops/ (read from skill.toml), not general/
        expected_path = skills_dir / "devops" / "devops-tool" / ".recipes-meta.json"
        wrong_path = skills_dir / "general" / "devops-tool" / ".recipes-meta.json"

        assert expected_path.exists(), (
            f".recipes-meta.json not found at expected devops path {expected_path}"
        )
        assert not wrong_path.exists(), (
            f"Skill was incorrectly installed under general/ instead of devops/"
        )

        with open(expected_path) as f:
            meta = json.load(f)
        assert meta["slug"] == "devops-tool"
        assert meta["version"] == "0.2.0"

    finally:
        mod.API_BASE = original_api
        mod.SKILLS_DIR = original_skills
        srv.shutdown()


# ─── Test 12: manifest.category takes priority over skill.toml category ────────

def test_install_manifest_category_takes_priority(tmp_path):
    """manifest.category from the install response must take priority over
    [skill].category in the tarball's skill.toml (priority order per F-CLI-03)."""
    # skill.toml says devops, but manifest says infra — manifest wins
    skill_toml_content = (
        b"[skill]\n"
        b'name = "infra-tool"\n'
        b'version = "1.0.0"\n'
        b'category = "devops"\n'  # would put it in devops/ if manifest absent
        b'description = "A skill"\n'
        b'license = "MIT"\n'
        b'entrypoint = "SKILL.md"\n'
        b'tier = "cook"\n'
        b'is_public = false\n'
    )
    tarball_content = make_deterministic_tarball({
        "SKILL.md": b"# infra-tool\n",
        "skill.toml": skill_toml_content,
    })
    good_sha = sha256(tarball_content)

    install_meta = {
        "slug": "infra-tool",
        "version": "1.0.0",
        "tarball_url": "__TARBALL_URL__",
        "checksum_sha256": good_sha,
        "manifest": {"category": "infra"},  # server says infra
    }

    routes: dict = {}
    srv = RecordingServer(routes)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    install_meta["tarball_url"] = f"{base}/tarball/infra-tool-1.0.0.tar.gz"

    routes[("GET", "/skills/install")] = (200, {}, install_meta)
    routes[("GET", "/tarball/infra-tool-1.0.0.tar.gz")] = (200, {}, tarball_content)

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    mod = load_cli_module("recipes_cli_test12")
    skills_dir = tmp_path / "hermes_skills"
    original_api = mod.API_BASE
    original_skills = mod.SKILLS_DIR
    mod.API_BASE = base
    mod.SKILLS_DIR = skills_dir

    try:
        class FakeArgs:
            slug = "infra-tool"
            force = False
            client_mode = False
            report_to = None

        mod.cmd_install(FakeArgs())

        # manifest.category="infra" wins over skill.toml category="devops"
        infra_path = skills_dir / "infra" / "infra-tool" / ".recipes-meta.json"
        devops_path = skills_dir / "devops" / "infra-tool" / ".recipes-meta.json"

        assert infra_path.exists(), (
            f"Expected install under infra/ but not found at {infra_path}"
        )
        assert not devops_path.exists(), (
            "Skill landed under devops/ — manifest.category was not respected"
        )

    finally:
        mod.API_BASE = original_api
        mod.SKILLS_DIR = original_skills
        srv.shutdown()
