#!/usr/bin/env python3
"""chef weekly — 7-day retrospective.

Pulls: shipped tickets, MRR delta from Stripe, $-spent from AI providers.
Sunday-only by default (overrideable with --force).
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
        return {}
    try:
        import yaml
        with open(cfg_path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def fetch_shipped_7d() -> list[dict]:
    cache = CACHE_DIR / "tickets-shipped-7d.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass
    return []


def fetch_mrr_delta(cfg: dict) -> dict[str, Any]:
    rev = cfg.get("revenue", {})
    api_key = os.environ.get(rev.get("api_key_env", "STRIPE_API_KEY"), "")
    if not api_key:
        return {"_stub": True, "reason": "Configure STRIPE_API_KEY for MRR tracking"}

    cache = CACHE_DIR / "mrr-7d.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass
    return {"current": 0, "delta": 0, "new": 0, "churn": 0}


def fetch_spend_7d(cfg: dict) -> dict[str, float]:
    cache = CACHE_DIR / "spend-7d.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass
    return {}


def render(shipped: list, mrr: dict, spend: dict) -> str:
    week_of = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    lines = [f"═══ Weekly retro — week of {week_of} ═══", ""]

    # SHIPPED
    lines.append(f"SHIPPED ({len(shipped)} items)")
    for s in shipped[:10]:
        lines.append(f"  • {s.get('title', s.get('id', '?'))[:65]}")
    if not shipped:
        lines.append("  (no shipped items recorded — set up project_board to track)")
    lines.append("")

    # MRR
    if mrr.get("_stub"):
        lines.append("MRR DELTA")
        lines.append(f"  ⚠ {mrr['reason']}")
    else:
        cur = mrr.get("current", 0)
        delta = mrr.get("delta", 0)
        sign = "+" if delta >= 0 else ""
        lines.append(f"MRR: €{cur} ({sign}€{delta} vs last week)")
        if mrr.get("new"):
            lines.append(f"  • New subs: {mrr['new']}")
        if mrr.get("churn"):
            lines.append(f"  • Churn: {mrr['churn']}")
    lines.append("")

    # SPEND
    if spend:
        total = sum(spend.values())
        lines.append(f"SPEND (last 7d): ${total:.2f} (${total/7:.2f}/day avg)")
        for provider, amount in sorted(spend.items(), key=lambda x: -x[1]):
            pct = 100 * amount / total if total else 0
            lines.append(f"  • {provider.title()}: ${amount:.2f} ({pct:.0f}%)")
    else:
        lines.append("SPEND: (no AI provider spend tracked)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="chef weekly — 7-day retrospective")
    parser.add_argument("--force", action="store_true",
                        help="Run even if today is not Sunday")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.force and datetime.now().weekday() != 6:  # 6 = Sunday
        print("chef weekly is designed for Sunday evenings. Use --force to run any day.")
        return 0

    cfg = load_config()
    shipped = fetch_shipped_7d()
    mrr = fetch_mrr_delta(cfg)
    spend = fetch_spend_7d(cfg)

    if not shipped and not spend and mrr.get("_stub"):
        print("Not enough data yet. Chef needs ≥7 days of cached state to run weekly.")
        print("Try after running `chef morning` daily for a week.")
        return 0

    if args.json:
        print(json.dumps({"shipped": shipped, "mrr": mrr, "spend": spend}, indent=2))
    else:
        print(render(shipped, mrr, spend))

    return 0


if __name__ == "__main__":
    sys.exit(main())
