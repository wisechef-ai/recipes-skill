#!/usr/bin/env bash
# byoa-codex.sh — Bring Your Own Agent: Codex CLI.
#
# This profile does NOT install an agent. The operator already has Codex
# installed. This profile prints a paste-ready prompt the operator drops
# into their Codex session; Codex itself then installs the MCP servers
# and skill bundle into its own config.

set -euo pipefail

WITH_AP="${RECIPES_WITH_AGENTPACT:-off}"

step() { printf "[byoa-codex] %s\n" "$*"; }

step "preparing paste-ready prompt for Codex"

OUT_DIR="${HOME}/.recipes/byoa-codex"
mkdir -p "$OUT_DIR"
PROMPT_FILE="${OUT_DIR}/codex-install-prompt.txt"

{
    echo "Paste the following into your Codex CLI session:"
    echo
    echo "---"
    echo "Install the Recipes starter-fleet-operator bundle into your"
    echo "current workspace. Specifically:"
    echo
    echo "1. Add the Recipes MCP server to your Codex configuration."
    echo "2. Pull the bundled skill index from the marketplace."
    echo "3. Install the 10 starter skills under the workspace skills"
    echo "   directory the operator has chosen."
    echo "4. Wire the optional Discord webhook only if the operator has"
    echo "   provided one."
    if [ "$WITH_AP" = "on" ]; then
        echo "5. AGENTPACT REQUESTED — also install the AgentPact MCP"
        echo "   server config alongside the Recipes server."
    else
        echo "5. AgentPact is NOT requested — do not install any AgentPact"
        echo "   files."
    fi
    echo "---"
} >"$PROMPT_FILE"

step "wrote $PROMPT_FILE"
step "done"

cat "$PROMPT_FILE"
