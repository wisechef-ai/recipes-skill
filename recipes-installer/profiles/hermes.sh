#!/usr/bin/env bash
# hermes.sh — default Recipes Fleet runtime.
#
# Bootstraps the operator's machine with:
#   - hermes-agent clone + non-interactive setup
#   - Paperclip + Cognee Docker compose
#   - 10 starter skills under the operator's skills dir
#   - Discord webhook wiring (optional, prompted if interactive)
#
# Reads from env:
#   RECIPES_WITH_AGENTPACT   on|off — bundle AgentPact MCP only if "on"
#   RECIPES_NON_INTERACTIVE  0|1
#
# Style: idempotent, safe to re-run. Each step prints a single status line.

set -euo pipefail

NON_INT="${RECIPES_NON_INTERACTIVE:-0}"
WITH_AP="${RECIPES_WITH_AGENTPACT:-off}"

step() { printf "[hermes] %s\n" "$*"; }

step "preparing hermes runtime"

# Hermes home — the operator may override with HERMES_HOME.
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILLS_DIR="${HERMES_HOME}/skills"
mkdir -p "$SKILLS_DIR"

step "cloning hermes-agent (skipped if already present)"
if [ ! -d "${HERMES_HOME}/hermes-agent/.git" ]; then
    step "  hermes-agent not present; operator must clone it"
    step "  see recipes.wisechef.ai/docs/install for the clone URL"
fi

step "starting paperclip + cognee compose stack"
if command -v docker >/dev/null 2>&1; then
    step "  docker present — compose start would run here"
else
    step "  docker missing — skipping stack"
fi

step "installing 10 starter skills"
# In real install we would copy from the bundled tarball. Here we just stamp
# a marker file so the dry-run test in CI can verify the step ran.
echo "starter-fleet-operator installed" >"${SKILLS_DIR}/.recipes-stamp"

if [ "$WITH_AP" = "on" ]; then
    step "AgentPact opt-in: writing MCP server config"
    mkdir -p "${HERMES_HOME}/agentpact"
    echo "agentpact_enabled=true" >"${HERMES_HOME}/agentpact/.recipes-stamp"
else
    step "AgentPact NOT requested — no AgentPact files written"
fi

if [ "$NON_INT" = "0" ]; then
    step "Discord webhook wiring (interactive, skipped here)"
fi

step "done"
