#!/usr/bin/env python3
"""chef code — Delegate a coding task to local agent (Codex/Claude Code).

Reads CLAUDE.md/AGENTS.md for project conventions, generates delegation prompt,
either runs OR prints command. Safe by default: prints, doesn't auto-execute.
"""
from __future__ import annotations
import argparse, json, os, shutil, sys
from pathlib import Path
from typing import Any


def find_project_conventions() -> str:
    """Look for CLAUDE.md / AGENTS.md / .cursorrules in cwd + parents."""
    cwd = Path.cwd()
    for d in [cwd] + list(cwd.parents):
        for fname in ["CLAUDE.md", "AGENTS.md", ".cursorrules"]:
            p = d / fname
            if p.exists():
                try:
                    return p.read_text()[:3000]  # cap context size
                except Exception:
                    pass
    return ""


def detect_delegate() -> str:
    """Return 'codex' / 'claude' / 'none' based on what's installed."""
    if shutil.which("codex"):
        return "codex"
    if shutil.which("claude"):
        return "claude"
    return "none"


def build_prompt(task: str, conventions: str) -> str:
    parts = []
    if conventions:
        parts.append("PROJECT CONVENTIONS (from CLAUDE.md/AGENTS.md):")
        parts.append(conventions)
        parts.append("")
    parts.append(f"TASK: {task}")
    parts.append("")
    parts.append("Constraints:")
    parts.append(f"- Working dir: {Path.cwd()}")
    parts.append("- Follow TDD if tests exist for the affected code")
    parts.append("- Open a PR when complete")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="chef code — delegate to local agent")
    parser.add_argument("task", nargs="?", help="What to do (e.g., 'add error logging to main.py')")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-execute (default: print command). Also: CHEF_AUTO_DELEGATE=true env.")
    parser.add_argument("--delegate", choices=["codex", "claude", "auto"], default="auto",
                        help="Which agent to delegate to (default: auto-detect)")
    args = parser.parse_args()

    if not args.task:
        print("Usage: chef code \"<task description>\"")
        print("Example: chef code \"add error logging to main.py\"")
        return 1

    conventions = find_project_conventions()
    delegate = args.delegate if args.delegate != "auto" else detect_delegate()
    prompt = build_prompt(args.task, conventions)

    auto = args.auto or os.environ.get("CHEF_AUTO_DELEGATE", "").lower() == "true"

    if delegate == "none":
        print("⚠ No local delegate found (codex / claude not on PATH).")
        print("Install one:")
        print("  npm i -g @openai/codex")
        print("  curl -fsSL https://claude.ai/install.sh | bash")
        print("\n--- Generated prompt (paste into your tool of choice) ---")
        print(prompt)
        return 1

    cmd = {
        "codex": ["codex", "exec", "--full-auto" if auto else "--ask"],
        "claude": ["claude", "--print", "--max-turns", "20"] + (["--permission-mode", "bypassPermissions"] if auto else []),
    }[delegate]

    print(f"═══ Delegating to {delegate} ═══")
    print(f"\nPrompt:\n{prompt}\n")
    print(f"Command: {' '.join(cmd)} \"<prompt-above>\"")

    if auto:
        import subprocess
        result = subprocess.run(cmd + [prompt], capture_output=False)
        return result.returncode
    else:
        print("\n(--auto not set — prompt printed, not executed.)")
        print("To run automatically, re-run with --auto OR export CHEF_AUTO_DELEGATE=true")
        return 0


if __name__ == "__main__":
    sys.exit(main())
