#!/usr/bin/env bash
# byoa-claudecode.sh — Bring Your Own Agent: Claude Code.
#
# Same shape as byoa-codex.sh — emits a paste-ready prompt the operator
# drops into Claude Code. Claude Code installs MCP servers + skills.

set -euo pipefail

WITH_AP="${RECIPES_WITH_AGENTPACT:-off}"

step() { printf "[byoa-claudecode] %s\n" "$*"; }

step "preparing paste-ready prompt for Claude Code"

OUT_DIR="${HOME}/.recipes/byoa-claudecode"
mkdir -p "$OUT_DIR"
PROMPT_FILE="${OUT_DIR}/claudecode-install-prompt.txt"

{
    echo "Paste the following into your Claude Code session:"
    echo
    echo "---"
    echo "Install the Recipes starter-fleet-operator bundle into this"
    echo "project. Specifically:"
    echo
    echo "1. Add the Recipes MCP server to your Claude Code MCP config."
    echo "2. Pull the bundled skill index from the marketplace."
    echo "3. Install the 10 starter skills under the project's skills"
    echo "   directory."
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
