#!/usr/bin/env bash
# install-fleet.sh — Recipes framework installer (stabilization_2605 Phase C).
#
# Served at recipes.wisechef.ai/fleet. Detects host, picks a runtime profile,
# and bootstraps an agent fleet on the operator's own machine.
#
# Usage:
#   curl -fsSL recipes.wisechef.ai/fleet | bash
#   ./install-fleet.sh --runtime=hermes [--with-agentpact] [--non-interactive]
#   ./install-fleet.sh --dry-run --non-interactive --runtime=byoa-codex
#
# Premortem-hardened (recipes-stabilization_2605):
#   - 4 explicit profiles: hermes (default), openclaw, byoa-codex,
#     byoa-claudecode. NO catch-all "generic" mode (F2).
#   - --with-agentpact is opt-in. Without the flag, zero AgentPact files
#     touch the install (F6).
#   - Dry-run mode prints a deterministic plan for CI to verify.

set -euo pipefail

# ─── defaults ───────────────────────────────────────────────────────────────

RUNTIME="hermes"
WITH_AGENTPACT="off"
DRY_RUN="${RECIPES_DRY_RUN:-0}"
NON_INTERACTIVE="0"

# ─── argument parsing ──────────────────────────────────────────────────────

usage() {
    cat <<'USAGE'
Usage: install-fleet.sh [options]
  --runtime=<name>      hermes | openclaw | byoa-codex | byoa-claudecode
  --with-agentpact      bundle AgentPact MCP servers (opt-in only)
  --non-interactive     do not prompt; rely on flags + defaults
  --dry-run             print the plan, do not execute it
  --help                show this message
USAGE
}

for arg in "$@"; do
    case "$arg" in
        --runtime=*)         RUNTIME="${arg#*=}" ;;
        --with-agentpact)    WITH_AGENTPACT="on" ;;
        --non-interactive)   NON_INTERACTIVE="1" ;;
        --dry-run)           DRY_RUN="1" ;;
        --help|-h)           usage; exit 0 ;;
        *)
            echo "install-fleet: unknown argument: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# ─── validate runtime ─────────────────────────────────────────────────────-─

case "$RUNTIME" in
    hermes|openclaw|byoa-codex|byoa-claudecode) ;;
    *)
        echo "install-fleet: unknown runtime '$RUNTIME'" >&2
        echo "                supported: hermes, openclaw, byoa-codex, byoa-claudecode" >&2
        exit 2
        ;;
esac

# ─── host detection ─────────────────────────────────────────────────────────

detect_os() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        *)       echo "unknown" ;;
    esac
}

detect_pkg_mgr() {
    if command -v brew >/dev/null 2>&1; then echo "brew"; return; fi
    if command -v apt-get >/dev/null 2>&1; then echo "apt"; return; fi
    if command -v dnf >/dev/null 2>&1; then echo "dnf"; return; fi
    if command -v pacman >/dev/null 2>&1; then echo "pacman"; return; fi
    echo "unknown"
}

probe_capability() {
    local tool="$1"
    if command -v "$tool" >/dev/null 2>&1; then
        echo "ok"
    else
        echo "missing"
    fi
}

OS="$(detect_os)"
PKG_MGR="$(detect_pkg_mgr)"

CAP_GIT="$(probe_capability git)"
CAP_PYTHON="$(probe_capability python3)"
CAP_NODE="$(probe_capability node)"
CAP_SQLITE="$(probe_capability sqlite3)"
CAP_JQ="$(probe_capability jq)"
CAP_SSH="$(probe_capability ssh)"
CAP_TMUX="$(probe_capability tmux)"
CAP_DOCKER="$(probe_capability docker)"
CAP_CURL="$(probe_capability curl)"

# ─── interactive runtime prompt ────────────────────────────────────────────-

if [ "$NON_INTERACTIVE" = "0" ] && [ -t 0 ] && [ "$DRY_RUN" = "0" ]; then
    echo
    echo "Recipes Fleet installer"
    echo "Pick a runtime:"
    echo "  1) hermes (default)"
    echo "  2) openclaw"
    echo "  3) byoa-codex"
    echo "  4) byoa-claudecode"
    printf "Choice [1]: "
    read -r choice || choice="1"
    case "${choice:-1}" in
        1|"") RUNTIME="hermes" ;;
        2)    RUNTIME="openclaw" ;;
        3)    RUNTIME="byoa-codex" ;;
        4)    RUNTIME="byoa-claudecode" ;;
        *)    echo "Invalid choice; defaulting to hermes." ; RUNTIME="hermes" ;;
    esac
fi

# ─── plan emission ─────────────────────────────────────────────────────────-

emit_plan() {
    cat <<PLAN
recipes-installer plan
runtime=$RUNTIME
agentpact=$WITH_AGENTPACT
os=$OS
pkg_mgr=$PKG_MGR
cap: git=$CAP_GIT
cap: python=$CAP_PYTHON
cap: node=$CAP_NODE
cap: sqlite=$CAP_SQLITE
cap: jq=$CAP_JQ
cap: ssh=$CAP_SSH
cap: tmux=$CAP_TMUX
cap: docker=$CAP_DOCKER
cap: curl=$CAP_CURL
PLAN
}

emit_plan

if [ "$DRY_RUN" = "1" ]; then
    echo "dry-run: not executing profile."
    exit 0
fi

# ─── dispatch to profile ───────────────────────────────────────────────────-

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE="$SCRIPT_DIR/profiles/$RUNTIME.sh"

if [ ! -f "$PROFILE" ]; then
    echo "install-fleet: profile not found: $PROFILE" >&2
    exit 3
fi

export RECIPES_RUNTIME="$RUNTIME"
export RECIPES_WITH_AGENTPACT="$WITH_AGENTPACT"
export RECIPES_NON_INTERACTIVE="$NON_INTERACTIVE"

bash "$PROFILE"
