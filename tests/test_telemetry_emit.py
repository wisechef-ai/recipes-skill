"""
tests/test_telemetry_emit.py — Tests for `recipes telemetry emit` subcommand.

Tests:
  1. test_telemetry_emit_happy_path      — full subprocess call with mock server, exit 0, prints event_id
  2. test_telemetry_emit_minimal         — only required flags (--skill + --event), correct JSON sent
  3. test_telemetry_emit_all_flags       — all optional flags forwarded correctly in payload
  4. test_telemetry_emit_no_api_key      — exits 1 with helpful stderr when RECIPES_API_KEY absent
  5. test_telemetry_emit_bad_event_type  — exits 1 for unrecognized event type
  6. test_telemetry_emit_bad_duration    — exits 1 when duration > 86400
  7. test_telemetry_emit_bad_agent_hash  — exits 1 for non-hex or too-short agent hash
  8. test_telemetry_emit_http_4xx        — exits 1 on 4xx response, prints stderr
  9. test_telemetry_emit_http_5xx        — exits 1 on 5xx response, prints stderr
 10. test_telemetry_emit_intervention_flag — --intervention sets user_intervention=true

Run with:
  pytest tests/test_telemetry_emit.py -v
"""

from __future__ import annotations

import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
from typing import Any

import pytest

# ─── Path to the CLI ──────────────────────────────────────────────────────────

CLI = pathlib.Path(__file__).parent.parent / "bin" / "recipes"
PYTHON = sys.executable


def run_cli(
    *args: str,
    env_extra: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run recipes CLI with given args; merges env_extra on top of os.environ."""
    cmd = [PYTHON, str(CLI)] + list(args)
    env = {**os.environ, **(env_extra or {})}
    # Strip any real API key from the environment so tests are hermetic
    env.pop("RECIPES_API_KEY", None)
    env.update(env_extra or {})
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)


# ─── Tiny HTTP server fixture ─────────────────────────────────────────────────


class TelemetryHandler(http.server.BaseHTTPRequestHandler):
    """Captures POST /telemetry; responds with a canned payload."""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.server._requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": json.loads(body) if body else {},
            }
        )
        status, resp_body = self.server._response
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp_body).encode())

    def log_message(self, *args: Any) -> None:  # silence server noise
        pass


class TelemetryServer(http.server.HTTPServer):
    def __init__(self, status: int, resp_body: dict):
        super().__init__(("127.0.0.1", 0), TelemetryHandler)
        self._requests: list[dict] = []
        self._response: tuple[int, dict] = (status, resp_body)


def start_telemetry_server(
    status: int = 201,
    resp_body: dict | None = None,
) -> tuple[TelemetryServer, str]:
    if resp_body is None:
        resp_body = {"status": "recorded", "event_id": "abc-123-def-456"}
    srv = TelemetryServer(status, resp_body)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    return srv, base


# ─── Test 1: happy path — full subprocess, mock server ───────────────────────


def test_telemetry_emit_happy_path():
    """Subprocess call with mock server: exit 0, prints event_id to stdout."""
    srv, base = start_telemetry_server(
        201, {"status": "recorded", "event_id": "event-uuid-1234"}
    )
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "agent-rescue",
            "--event", "task_completed",
            "--goal-class", "client-reporting",
            "--duration", "42",
            "--retries", "0",
            "--no-intervention",
            env_extra={
                "RECIPES_API_KEY": "rec_test_key",
                "RECIPES_API_BASE": base,
            },
        )
        assert result.returncode == 0, f"Expected exit 0; stderr={result.stderr!r}"
        assert "event-uuid-1234" in result.stdout
        assert len(srv._requests) == 1
        req = srv._requests[0]
        assert req["path"] == "/telemetry"
        # HTTP headers are case-insensitive; urllib capitalizes the first letter
        headers_lower = {k.lower(): v for k, v in req["headers"].items()}
        assert headers_lower.get("x-api-key") == "rec_test_key"
        payload = req["body"]
        assert payload["event_type"] == "task_completed"
        assert payload["skill_slug"] == "agent-rescue"
        assert payload["goal_class"] == "client-reporting"
        assert payload["duration_seconds"] == 42
        assert payload["retry_count"] == 0
        assert payload["user_intervention"] is False
    finally:
        srv.shutdown()


# ─── Test 2: minimal flags only ──────────────────────────────────────────────


def test_telemetry_emit_minimal():
    """Only --skill and --event are required; optional fields absent from payload."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "min-id"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "install",
            env_extra={
                "RECIPES_API_KEY": "rec_key",
                "RECIPES_API_BASE": base,
            },
        )
        assert result.returncode == 0, result.stderr
        assert "min-id" in result.stdout
        assert len(srv._requests) == 1
        payload = srv._requests[0]["body"]
        assert payload["event_type"] == "install"
        assert payload["skill_slug"] == "my-skill"
        # Optional fields absent
        assert "goal_class" not in payload
        assert "duration_seconds" not in payload
        assert "agent_class_hash" not in payload
        # Defaults present
        assert payload["retry_count"] == 0
        assert payload["user_intervention"] is False
    finally:
        srv.shutdown()


# ─── Test 3: all optional flags ───────────────────────────────────────────────


def test_telemetry_emit_all_flags():
    """All optional flags are forwarded in the payload."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "all-id"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "seo-audit",
            "--event", "task_failed",
            "--goal-class", "seo-audit",
            "--duration", "120",
            "--retries", "3",
            "--intervention",
            "--agent-hash", "deadbeef1234abcd",
            env_extra={
                "RECIPES_API_KEY": "rec_key",
                "RECIPES_API_BASE": base,
            },
        )
        assert result.returncode == 0, result.stderr
        payload = srv._requests[0]["body"]
        assert payload["goal_class"] == "seo-audit"
        assert payload["duration_seconds"] == 120
        assert payload["retry_count"] == 3
        assert payload["user_intervention"] is True
        assert payload["agent_class_hash"] == "deadbeef1234abcd"
    finally:
        srv.shutdown()


# ─── Test 4: missing RECIPES_API_KEY ─────────────────────────────────────────


def test_telemetry_emit_no_api_key():
    """Must exit 1 with helpful message when RECIPES_API_KEY is not set."""
    result = run_cli(
        "telemetry", "emit",
        "--skill", "my-skill",
        "--event", "install",
        # No RECIPES_API_KEY in env_extra; run_cli strips the real one too
        env_extra={},
    )
    assert result.returncode == 1
    assert "RECIPES_API_KEY" in result.stderr


# ─── Test 5: invalid event type ──────────────────────────────────────────────


def test_telemetry_emit_bad_event_type():
    """Unrecognized event type should exit 1 before hitting the network."""
    result = run_cli(
        "telemetry", "emit",
        "--skill", "my-skill",
        "--event", "not_a_real_event",
        env_extra={"RECIPES_API_KEY": "rec_key"},
    )
    assert result.returncode == 1
    assert "event" in result.stderr.lower() or "invalid" in result.stderr.lower()


# ─── Test 6: duration out of range ────────────────────────────────────────────


def test_telemetry_emit_bad_duration():
    """duration > 86400 should exit 1 with error message."""
    result = run_cli(
        "telemetry", "emit",
        "--skill", "my-skill",
        "--event", "task_completed",
        "--duration", "86401",
        env_extra={"RECIPES_API_KEY": "rec_key"},
    )
    assert result.returncode == 1
    assert "duration" in result.stderr.lower() or "86400" in result.stderr


def test_telemetry_emit_duration_zero_ok():
    """duration=0 should be accepted (boundary)."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "dur-ok"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "install",
            "--duration", "0",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 0, result.stderr
        assert srv._requests[0]["body"]["duration_seconds"] == 0
    finally:
        srv.shutdown()


def test_telemetry_emit_duration_max_ok():
    """duration=86400 should be accepted (boundary)."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "dur-max"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "install",
            "--duration", "86400",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 0, result.stderr
        assert srv._requests[0]["body"]["duration_seconds"] == 86400
    finally:
        srv.shutdown()


# ─── Test 7: bad agent hash ───────────────────────────────────────────────────


def test_telemetry_emit_bad_agent_hash():
    """agent-hash that doesn't match ^[a-f0-9]{8,64}$ should exit 1."""
    # Too short (7 chars)
    result = run_cli(
        "telemetry", "emit",
        "--skill", "my-skill",
        "--event", "install",
        "--agent-hash", "abc1234",
        env_extra={"RECIPES_API_KEY": "rec_key"},
    )
    assert result.returncode == 1
    assert "agent-hash" in result.stderr.lower() or "hash" in result.stderr.lower()

    # Contains uppercase
    result2 = run_cli(
        "telemetry", "emit",
        "--skill", "my-skill",
        "--event", "install",
        "--agent-hash", "DEADBEEF1234ABCD",
        env_extra={"RECIPES_API_KEY": "rec_key"},
    )
    assert result2.returncode == 1


def test_telemetry_emit_agent_hash_valid():
    """Minimum-length (8-char) valid hash should be accepted."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "hash-ok"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "install",
            "--agent-hash", "deadbeef",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 0, result.stderr
        assert srv._requests[0]["body"]["agent_class_hash"] == "deadbeef"
    finally:
        srv.shutdown()


# ─── Test 8: HTTP 4xx from server ────────────────────────────────────────────


def test_telemetry_emit_http_4xx():
    """4xx response should exit 1 with error on stderr."""
    srv, base = start_telemetry_server(
        422, {"detail": "skill not found"}
    )
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "nonexistent-skill",
            "--event", "install",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 1
        assert result.stderr.strip() != ""
    finally:
        srv.shutdown()


# ─── Test 9: HTTP 5xx from server ────────────────────────────────────────────


def test_telemetry_emit_http_5xx():
    """5xx response should exit 1 with error on stderr."""
    srv, base = start_telemetry_server(
        500, {"detail": "internal server error"}
    )
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "task_completed",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 1
        assert "500" in result.stderr or "error" in result.stderr.lower()
    finally:
        srv.shutdown()


# ─── Test 10: --intervention flag ────────────────────────────────────────────


def test_telemetry_emit_intervention_flag():
    """--intervention sets user_intervention=true in payload."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "intv-id"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "task_completed",
            "--intervention",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 0, result.stderr
        assert srv._requests[0]["body"]["user_intervention"] is True
    finally:
        srv.shutdown()


def test_telemetry_emit_no_intervention_default():
    """--no-intervention (default) sets user_intervention=false."""
    srv, base = start_telemetry_server(201, {"status": "recorded", "event_id": "no-intv-id"})
    try:
        result = run_cli(
            "telemetry", "emit",
            "--skill", "my-skill",
            "--event", "first_use",
            "--no-intervention",
            env_extra={"RECIPES_API_KEY": "rec_key", "RECIPES_API_BASE": base},
        )
        assert result.returncode == 0, result.stderr
        assert srv._requests[0]["body"]["user_intervention"] is False
    finally:
        srv.shutdown()
