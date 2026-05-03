#!/usr/bin/env python3
"""Positive-allowlist PII linter for Recipes skills.

Each skill ships ``MANIFEST.allowlist.yaml`` declaring every external string
(URLs, hostnames, emails, env vars, paths, ports) the skill is allowed to
reference. The linter scans every file in the skill and rejects any
URL/email/env-var/path/port that is not in the allowlist.

Hard-abort: any unlisted match → exit code 1, no warn-merge.

Usage::

    allowlist_lint.py <skill-dir> [--json]
    allowlist_lint.py <skill-dir-1> <skill-dir-2> ... [--json]

Stdlib only. Designed for CI on every PR touching ``starter-skills/**``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

MANIFEST_NAME = "MANIFEST.allowlist.yaml"

# Files that are always skipped (binary or generated)
_SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".otf",
    ".mp3", ".mp4", ".mov", ".webm",
}
_SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", ".venv", "venv"}

# ─── regex catalog ──────────────────────────────────────────────────────────

# Order matters: URL is matched first, then port-bearing host, then bare host.
_RE_URL = re.compile(r"https?://[^\s<>\"'`)\]]+", re.IGNORECASE)
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RE_PATH_ABS = re.compile(r"(?<![A-Za-z0-9_./-])(?:~/[\w./-]+|/(?:home|var|etc|opt|usr|tmp|root|srv|mnt)(?:/[\w.-]+)+)")
_RE_PATH_WIN = re.compile(r"\b[A-Za-z]:\\[\w\\.-]+")
# Env vars: ALL_CAPS_WITH_UNDERSCORES, ≥4 chars, must contain underscore OR digit OR be ≥6 chars
# Tighten further: starts with letter, no leading word-char before
_RE_ENV = re.compile(r"(?<![A-Za-z0-9_\$])[A-Z][A-Z0-9_]{3,}(?![A-Za-z0-9_])")
# Port like ":8200" not preceded by word-char
_RE_PORT_STANDALONE = re.compile(r"(?<![\w:]):(\d{2,5})\b")

# Words that look like env vars but are not (common false positives)
_ENV_FALSE_POSITIVES = {
    # English uppercase nouns commonly seen
    "TODO", "FIXME", "XXX", "NOTE", "WARN", "ERROR", "INFO", "DEBUG",
    "TRUE", "FALSE", "NULL", "NONE", "READ", "WRITE", "OPEN", "CLOSE",
    "HTTP", "HTTPS", "HTML", "JSON", "YAML", "XML", "CSV", "PDF", "API",
    "OAUTH", "REST", "GRAPHQL", "SDK", "CLI", "GUI", "OS", "URL", "URI",
    "UUID", "UTC", "PST", "EST", "ASCII", "UNIX", "POSIX", "SHA", "MD5",
    "AES", "RSA", "TLS", "SSL", "DNS", "TCP", "UDP", "IPV4", "IPV6",
    "AGPL", "MIT", "BSD", "GPLV3", "APACHE", "LGPL",
    # Markdown / shell artifacts
    "BEGIN", "END", "EOF",
    # Skill metadata that's not actually env
    "SKILL", "RECIPES", "MANIFEST", "ALLOWLIST", "README", "LICENSE",
    "INSTALL", "USAGE", "DOC", "DOCS",
    # Common HTTP verbs
    "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS",
}

# Hostnames: bare domain like "example.com" — only flag inside text not already in URL
# Implementation note: easier to check after stripping URLs/emails from a line.
_RE_HOST = re.compile(r"\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,63}(?:\.[a-z]{2,63})?)\b")
_HOST_FALSE_POSITIVES = {
    # File extensions misidentified as hosts
    "skill.md", "readme.md", "license.md", "config.yaml", "config.yml",
    "package.json", "tsconfig.json", "manifest.yaml", "manifest.yml",
    "recipe.yaml", "recipe.yml", "settings.json",
}


# ─── manifest parsing (tiny YAML subset, stdlib only) ───────────────────────


def _load_manifest(manifest_path: Path) -> dict[str, set[str]]:
    """Parse a YAML allowlist manifest using a minimal hand-rolled parser.

    Schema::

        name: <skill-name>
        allowlist:
          urls: [...]
          hostnames: [...]
          emails: [...]
          env_vars: [...]
          paths: [...]
          ports: [...]
          names: [...]   # person/org names, free text

    We accept block-style lists ("- value") and inline empty maps ("{}").
    Anything else is undefined behaviour and the linter will emit findings.
    """
    text = manifest_path.read_text(encoding="utf-8")
    buckets: dict[str, set[str]] = {
        "urls": set(),
        "hostnames": set(),
        "emails": set(),
        "env_vars": set(),
        "paths": set(),
        "ports": set(),
        "names": set(),
    }

    in_allowlist = False
    current_key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        # top-level
        if not raw.startswith(" ") and not raw.startswith("\t"):
            in_allowlist = line.startswith("allowlist:")
            current_key = None
            continue
        if not in_allowlist:
            continue
        # 2-space indent: key under allowlist
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 2 and stripped.endswith(":"):
            current_key = stripped[:-1].strip()
            continue
        if indent == 2 and ":" in stripped and not stripped.startswith("-"):
            # allow inline "key: []" or "key: {}"
            k, _, rest = stripped.partition(":")
            current_key = k.strip()
            rest = rest.strip()
            if rest in ("[]", "{}", ""):
                continue
            # inline scalar — treat as single-element list
            if current_key in buckets:
                buckets[current_key].add(rest.strip().strip("\"'"))
            continue
        if indent >= 4 and stripped.startswith("-"):
            value = stripped[1:].strip().strip("\"'")
            if current_key in buckets and value:
                buckets[current_key].add(value)
            continue
    return buckets


def _is_in_allowlist(kind: str, value: str, allow: dict[str, set[str]]) -> bool:
    if kind == "url":
        return value in allow["urls"]
    if kind == "hostname":
        return value in allow["hostnames"] or any(value in u for u in allow["urls"])
    if kind == "email":
        return value in allow["emails"]
    if kind == "env_var":
        return value in allow["env_vars"]
    if kind == "path":
        return value in allow["paths"]
    if kind == "port":
        if value in allow["ports"]:
            return True
        # ports inside an allowed URL are fine
        return any(f":{value}" in u for u in allow["urls"])
    if kind == "name":
        return value in allow["names"]
    return False


# ─── scanning ───────────────────────────────────────────────────────────────


def _iter_skill_files(skill_dir: Path) -> Iterable[Path]:
    for p in skill_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.name == MANIFEST_NAME:
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in _SKIP_SUFFIXES:
            continue
        yield p


def _scan_line(line: str, allow: dict[str, set[str]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    masked = line  # progressively blank-out matches so later regexes don't double-flag

    # 1. URLs
    for m in _RE_URL.finditer(line):
        val = m.group(0).rstrip(".,;:)")
        if not _is_in_allowlist("url", val, allow):
            findings.append({
                "kind": "url",
                "value": val,
                "span": [m.start(), m.start() + len(val)],
                "suggestion": f"add `{val}` to allowlist.urls or remove the URL",
            })
        masked = masked[:m.start()] + (" " * (m.end() - m.start())) + masked[m.end():]

    # 2. emails
    for m in _RE_EMAIL.finditer(masked):
        val = m.group(0)
        if not _is_in_allowlist("email", val, allow):
            findings.append({
                "kind": "email",
                "value": val,
                "span": [m.start(), m.end()],
                "suggestion": f"add `{val}` to allowlist.emails or remove the email",
            })
        masked = masked[:m.start()] + (" " * (m.end() - m.start())) + masked[m.end():]

    # 3. absolute paths
    for rx in (_RE_PATH_ABS, _RE_PATH_WIN):
        for m in rx.finditer(masked):
            val = m.group(0).rstrip(".,;:)")
            if not _is_in_allowlist("path", val, allow):
                findings.append({
                    "kind": "path",
                    "value": val,
                    "span": [m.start(), m.start() + len(val)],
                    "suggestion": f"add `{val}` to allowlist.paths or use a placeholder",
                })
            masked = masked[:m.start()] + (" " * (m.end() - m.start())) + masked[m.end():]

    # 4. env vars
    for m in _RE_ENV.finditer(masked):
        val = m.group(0)
        if val in _ENV_FALSE_POSITIVES:
            continue
        # require either an underscore (typical env style) OR length ≥6 to cut prose noise
        if "_" not in val and len(val) < 6:
            continue
        if not _is_in_allowlist("env_var", val, allow):
            findings.append({
                "kind": "env_var",
                "value": val,
                "span": [m.start(), m.end()],
                "suggestion": f"add `{val}` to allowlist.env_vars or rename",
            })

    # 5. ports — only if not already inside an allowed URL (URLs are masked above)
    for m in _RE_PORT_STANDALONE.finditer(masked):
        val = m.group(1)
        if not _is_in_allowlist("port", val, allow):
            findings.append({
                "kind": "port",
                "value": val,
                "span": [m.start(1), m.end(1)],
                "suggestion": f"add `{val}` to allowlist.ports or remove the port",
            })

    return findings


def _lint_skill(skill_dir: Path) -> dict[str, Any]:
    manifest_path = skill_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return {
            "skill": skill_dir.name,
            "error": f"missing {MANIFEST_NAME} in {skill_dir}",
            "findings": [],
        }
    allow = _load_manifest(manifest_path)
    findings: list[dict[str, Any]] = []
    for f in _iter_skill_files(skill_dir):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = str(f.relative_to(skill_dir))
        for lineno, line in enumerate(text.splitlines(), start=1):
            for finding in _scan_line(line, allow):
                finding["file"] = rel
                finding["line"] = lineno
                findings.append(finding)
    return {"skill": skill_dir.name, "findings": findings}


# ─── CLI ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Positive-allowlist PII linter for Recipes skills")
    p.add_argument("skills", nargs="+", help="One or more skill directories to lint")
    p.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    args = p.parse_args(argv)

    rc = 0
    if len(args.skills) == 1:
        result = _lint_skill(Path(args.skills[0]))
        if "error" in result or result["findings"]:
            rc = 1
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_human(result)
        return rc

    # multi-skill mode
    results = [_lint_skill(Path(s)) for s in args.skills]
    if any("error" in r or r["findings"] for r in results):
        rc = 1
    if args.json:
        print(json.dumps({"skills": results}, indent=2))
    else:
        for r in results:
            _print_human(r)
    return rc


def _print_human(result: dict[str, Any]) -> None:
    if result.get("error"):
        sys.stderr.write(f"[allowlist] {result['skill']}: ERROR {result['error']}\n")
        return
    if not result["findings"]:
        sys.stderr.write(f"[allowlist] {result['skill']}: clean ✓\n")
        return
    sys.stderr.write(f"[allowlist] {result['skill']}: {len(result['findings'])} finding(s)\n")
    for f in result["findings"]:
        sys.stderr.write(
            f"  {f['file']}:{f['line']}  {f['kind']}={f['value']!r}  → {f['suggestion']}\n"
        )


if __name__ == "__main__":
    sys.exit(main())
