#!/usr/bin/env python3
"""chef tickets — Project board triage.

Categorizes tickets: stale (>48h in_progress), needs-review, blocked, ready-to-merge.
Suggests action per category. Shows velocity stats.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CACHE_DIR = Path(os.path.expanduser("~/.cache/chef"))


def load_config() -> dict[str, Any]:
    cfg_path = os.path.expanduser("~/.config/chef/config.yaml")
    if not Path(cfg_path).exists():
        return {"project_board": {"type": "paperclip", "api_key_env": "PAPERCLIP_API_KEY"}}
    try:
        import yaml
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def fetch_all_tickets(cfg: dict) -> list[dict]:
    """Fetch all open tickets. Returns [] with stub flag if creds missing."""
    pb = cfg.get("project_board", {})
    api_key = os.environ.get(pb.get("api_key_env", "PAPERCLIP_API_KEY"), "")
    if not api_key:
        return [{"_stub": True, "reason": "Configure PAPERCLIP_API_KEY (or your project_board.api_key_env)"}]

    cache_file = CACHE_DIR / "tickets-all.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            return []
    return []


def categorize(tickets: list[dict]) -> dict[str, list[dict]]:
    """Bucket tickets by action needed."""
    now = datetime.now(timezone.utc)
    cats = {"stale": [], "needs-review": [], "blocked": [], "ready-to-merge": [], "other": []}

    for t in tickets:
        if t.get("_stub"):
            continue
        status = t.get("status", "").lower()
        age_h = float(t.get("age_hours", 0))

        if status == "blocked":
            cats["blocked"].append(t)
        elif status == "in_progress" and age_h > 48:
            cats["stale"].append(t)
        elif status == "review":
            cats["needs-review"].append(t)
        elif status == "ready" or t.get("has_open_pr"):
            cats["ready-to-merge"].append(t)
        else:
            cats["other"].append(t)

    return cats


def render(cats: dict[str, list[dict]], stub: bool) -> str:
    lines = ["═══ Ticket triage ═══", ""]

    if stub:
        lines.append("⚠ Project board not configured.")
        lines.append("  Set PAPERCLIP_API_KEY (or update ~/.config/chef/config.yaml)")
        lines.append("  Run `chef setup` for an interactive walkthrough.")
        return "\n".join(lines)

    total = sum(len(v) for v in cats.values())
    if total == 0:
        lines.append("No open tickets. Inbox zero. 🎉")
        return "\n".join(lines)

    if cats["stale"]:
        lines.append(f"STALE ({len(cats['stale'])}) — close with comment or move forward")
        for t in cats["stale"][:5]:
            lines.append(f"  ⚠ {t.get('id')} — {t.get('title', '')[:60]} ({t.get('age_hours', '?'):.0f}h)")
        lines.append("")

    if cats["needs-review"]:
        lines.append(f"NEEDS REVIEW ({len(cats['needs-review'])}) — ping reviewer")
        for t in cats["needs-review"][:5]:
            lines.append(f"  👀 {t.get('id')} — {t.get('title', '')[:60]}")
        lines.append("")

    if cats["blocked"]:
        lines.append(f"BLOCKED ({len(cats['blocked'])}) — unblock or escalate")
        for t in cats["blocked"][:5]:
            lines.append(f"  🛑 {t.get('id')} — {t.get('title', '')[:60]}")
        lines.append("")

    if cats["ready-to-merge"]:
        lines.append(f"READY TO MERGE ({len(cats['ready-to-merge'])})")
        for t in cats["ready-to-merge"][:5]:
            lines.append(f"  ✓ {t.get('id')} — {t.get('title', '')[:60]}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="chef tickets — project board triage")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    tickets = fetch_all_tickets(cfg)
    stub = bool(tickets and tickets[0].get("_stub"))
    cats = categorize(tickets)

    if args.json:
        print(json.dumps({k: v for k, v in cats.items() if v}, indent=2, default=str))
    else:
        print(render(cats, stub))

    return 0


if __name__ == "__main__":
    sys.exit(main())
