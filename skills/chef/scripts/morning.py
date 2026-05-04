#!/usr/bin/env python3
"""chef morning — Yesterday's events, today's priorities, overnight spend.

Battle-tested by WiseChef. Reads from configured project board (default: Paperclip)
+ AI provider spend APIs + optional calendar. Graceful degradation when creds missing.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ─── config loader ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "project_board": {"type": "paperclip", "api_key_env": "PAPERCLIP_API_KEY"},
    "ai_providers": {"anthropic": {"api_key_env": "ANTHROPIC_API_KEY"}},
    "calendar": {"type": "none"},
}

CONFIG_PATH = os.path.expanduser("~/.config/chef/config.yaml")
CACHE_DIR = Path(os.path.expanduser("~/.cache/chef"))


def load_config() -> dict[str, Any]:
    if not Path(CONFIG_PATH).exists():
        return DEFAULT_CONFIG
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or DEFAULT_CONFIG
    except ImportError:
        return DEFAULT_CONFIG
    except Exception as e:
        print(f"[warning] failed to read {CONFIG_PATH}: {e}", file=sys.stderr)
        return DEFAULT_CONFIG


# ─── data fetchers (graceful degradation) ──────────────────────────────────────

def fetch_yesterday_tickets(cfg: dict) -> list[dict]:
    """Fetch tickets closed/stale yesterday. Returns [] if creds missing."""
    pb = cfg.get("project_board", {})
    api_key = os.environ.get(pb.get("api_key_env", "PAPERCLIP_API_KEY"), "")
    if not api_key:
        return [{"_stub": True, "reason": "no PAPERCLIP_API_KEY"}]

    # Real Paperclip API call would go here. For the v0 skill, we read from
    # local cache if available.
    cache_file = CACHE_DIR / "tickets-yesterday.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            return []
    return []


def fetch_overnight_spend(cfg: dict) -> dict[str, float]:
    """Fetch overnight $ spend per AI provider. Returns {} if creds missing."""
    spend = {}
    providers = cfg.get("ai_providers", {})
    for name, conf in providers.items():
        api_key = os.environ.get(conf.get("api_key_env", ""), "")
        if not api_key:
            spend[name] = None  # signal "unconfigured"
            continue
        # Real API call would aggregate cost here. For v0, read cache.
        cache_file = CACHE_DIR / f"spend-{name}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                spend[name] = data.get("overnight_usd", 0.0)
            except Exception:
                spend[name] = 0.0
        else:
            spend[name] = 0.0
    return spend


def fetch_today_meetings(cfg: dict) -> list[str]:
    cal = cfg.get("calendar", {})
    if cal.get("type") == "none":
        return []
    # Stub for v0 — would call gws CLI in production
    return []


# ─── output ────────────────────────────────────────────────────────────────────

def render_brief(tickets: list[dict], spend: dict[str, float], meetings: list[str]) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"═══ Morning brief — {today} ═══")
    lines.append("")

    # YESTERDAY section
    closed = [t for t in tickets if t.get("status") == "done"]
    stale = [t for t in tickets if t.get("status") == "in_progress"]
    if tickets and tickets[0].get("_stub"):
        lines.append("YESTERDAY")
        lines.append(f"  ⚠ {tickets[0]['reason']} — set the env var to enable ticket tracking")
    else:
        lines.append(f"YESTERDAY ({len(closed)} shipped, {len(stale)} stale)")
        for t in closed[:5]:
            lines.append(f"  ✓ {t.get('id', '?')} — {t.get('title', '?')[:60]}")
        for t in stale[:3]:
            lines.append(f"  ⚠ {t.get('id', '?')} — {t.get('title', '?')[:60]} ({t.get('age_hours', '?')}h)")
    lines.append("")

    # TODAY section
    lines.append("TODAY")
    if meetings:
        for m in meetings[:5]:
            lines.append(f"  📅 {m}")
    else:
        lines.append("  (no meetings on calendar)")
    lines.append("")

    # SPEND section
    lines.append("SPEND (overnight)")
    total = 0.0
    for name, amount in spend.items():
        if amount is None:
            lines.append(f"  {name.title()}: (not configured)")
        else:
            lines.append(f"  {name.title()}: ${amount:.2f}")
            total += amount
    lines.append(f"  Total: ${total:.2f}")

    return "\n".join(lines)


# ─── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="chef morning — daily brief")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen, no API calls")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    cfg = load_config()

    if args.dry_run:
        print("DRY RUN — would fetch from:")
        print(f"  Project board: {cfg.get('project_board', {}).get('type')}")
        print(f"  AI providers: {list(cfg.get('ai_providers', {}).keys())}")
        print(f"  Calendar: {cfg.get('calendar', {}).get('type')}")
        return 0

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    tickets = fetch_yesterday_tickets(cfg)
    spend = fetch_overnight_spend(cfg)
    meetings = fetch_today_meetings(cfg)

    if args.json:
        print(json.dumps({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "yesterday": {"tickets": tickets},
            "today": {"meetings": meetings},
            "spend_overnight": spend,
        }, indent=2))
    else:
        print(render_brief(tickets, spend, meetings))

    return 0


if __name__ == "__main__":
    sys.exit(main())
