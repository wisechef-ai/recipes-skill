#!/usr/bin/env python3
"""chef marketing — Content pipeline status, posts to schedule.

Reads scheduled queue from configured tool (Postiz default). Suggests 1-2 posts based on
recent shipped work. Graceful degradation: shows draft + "needs auth" message if creds missing.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path
from typing import Any

CACHE_DIR = Path(os.path.expanduser("~/.cache/chef"))


def load_config() -> dict[str, Any]:
    cfg_path = os.path.expanduser("~/.config/chef/config.yaml")
    if not Path(cfg_path).exists():
        return {"content_pipeline": {"type": "postiz", "api_key_env": "POSTIZ_API_KEY"}}
    try:
        import yaml
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def fetch_pipeline_status(cfg: dict) -> dict[str, Any]:
    cp = cfg.get("content_pipeline", {})
    api_key = os.environ.get(cp.get("api_key_env", "POSTIZ_API_KEY"), "")
    if not api_key:
        return {"_stub": True, "reason": f"Configure {cp.get('api_key_env', 'POSTIZ_API_KEY')}"}

    cache_file = CACHE_DIR / "pipeline.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except Exception:
            pass
    return {"scheduled": [], "drafts": [], "needs_creative": []}


def fetch_recent_shipped() -> list[str]:
    """Pull last 7 days of shipped tickets to inform post drafts."""
    cache = CACHE_DIR / "tickets-shipped-7d.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            return []
    return []


def draft_post_from_shipped(items: list[str]) -> str:
    if not items:
        return "(no recent shipped work to summarize)"
    if len(items) == 1:
        return f"Just shipped: {items[0]}"
    return f"Last 7 days, shipped {len(items)} things. Highlights: {', '.join(items[:3])}"


def render(status: dict, draft: str) -> str:
    lines = ["═══ Marketing pipeline ═══", ""]

    if status.get("_stub"):
        lines.append("⚠ Content pipeline not configured.")
        lines.append(f"  {status['reason']} — then run `chef marketing` again.")
        lines.append("")
        lines.append("DRAFT (to schedule once configured)")
        lines.append(f"  {draft}")
        return "\n".join(lines)

    scheduled = status.get("scheduled", [])
    drafts = status.get("drafts", [])
    creative = status.get("needs_creative", [])

    lines.append(f"SCHEDULED ({len(scheduled)})")
    for p in scheduled[:5]:
        lines.append(f"  📅 {p.get('scheduled_at', '?')} — {p.get('platform', '?')} — {p.get('preview', '')[:60]}")
    lines.append("")

    lines.append(f"DRAFTS ({len(drafts)})")
    for p in drafts[:5]:
        lines.append(f"  📝 {p.get('platform', '?')} — {p.get('preview', '')[:60]}")
    lines.append("")

    if creative:
        lines.append(f"NEEDS CREATIVE INPUT ({len(creative)})")
        for p in creative[:5]:
            lines.append(f"  🎨 {p.get('platform', '?')} — {p.get('hint', '')[:60]}")
        lines.append("")

    lines.append("SUGGESTED NEXT POST")
    lines.append(f"  {draft}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="chef marketing — content pipeline")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    status = fetch_pipeline_status(cfg)
    shipped = fetch_recent_shipped()
    draft = draft_post_from_shipped(shipped)

    if args.json:
        out = {"status": status, "suggested_post": draft}
        print(json.dumps(out, indent=2))
    else:
        print(render(status, draft))

    return 0


if __name__ == "__main__":
    sys.exit(main())
