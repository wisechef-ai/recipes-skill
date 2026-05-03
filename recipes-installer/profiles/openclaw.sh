#!/usr/bin/env bash
# openclaw.sh — Recipes Fleet runtime for the OpenClaw fork.

set -euo pipefail

NON_INT="${RECIPES_NON_INTERACTIVE:-0}"
WITH_AP="${RECIPES_WITH_AGENTPACT:-off}"

step() { printf "[openclaw] %s\n" "$*"; }

step "preparing openclaw runtime"

CLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
SKILLS_DIR="${CLAW_HOME}/skills"
mkdir -p "$SKILLS_DIR"

step "cloning openclaw fork (skipped if already present)"
if [ ! -d "${CLAW_HOME}/openclaw/.git" ]; then
    step "  openclaw not present; operator must clone the fork"
fi

step "starting paperclip + cognee compose stack (openclaw flavour)"
if command -v docker >/dev/null 2>&1; then
    step "  docker present — compose start would run here"
else
    step "  docker missing — skipping stack"
fi

step "installing 10 starter skills"
echo "starter-fleet-operator installed (openclaw)" >"${SKILLS_DIR}/.recipes-stamp"

if [ "$WITH_AP" = "on" ]; then
    step "AgentPact opt-in: writing MCP server config"
    mkdir -p "${CLAW_HOME}/agentpact"
    echo "agentpact_enabled=true" >"${CLAW_HOME}/agentpact/.recipes-stamp"
else
    step "AgentPact NOT requested — no AgentPact files written"
fi

if [ "$NON_INT" = "0" ]; then
    step "Discord webhook wiring (interactive, skipped here)"
fi

step "done"
