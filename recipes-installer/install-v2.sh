#!/usr/bin/env bash
# recipes — universal installer v2 (WIS-901)
#
# Top-class probe + dep-aware installer for the Recipes meta-skill.
# Detects which agent skills directories exist, picks the right one,
# installs skills, scans frontmatter for binary deps, and verifies.
#
# Usage:
#   curl -fsSL https://recipes.wisechef.ai/install.sh | bash
#   ./install.sh --target-dir /path/to/skills
#   ./install.sh --dry-run
#
# Tested on bash + zsh + fish on Linux/macOS.
# WSL/Nix/PowerShell users: open an issue or use --target-dir.
#
# Source: https://github.com/wisechef-ai/recipes-skill
# License: Apache-2.0

set -uo pipefail

VERSION="2.0.0"
API_BASE="${RECIPES_API_BASE:-https://recipes.wisechef.ai}"
API_KEY="${RECIPES_API_KEY:-}"
DRY_RUN=0
TARGET_DIR=""
NON_INTERACTIVE=0
VERBOSE=0

# ─── Counters ────────────────────────────────────────────────────────────────
COUNT_INSTALLED=0
COUNT_DEPS=0
COUNT_SKIPPED=0
COUNT_ERRORS=0
NEEDS_HUMAN=0

# ─── Colors ──────────────────────────────────────────────────────────────────
if [ -t 2 ]; then
  BOLD='\033[1m'; DIM='\033[2m'; GREEN='\033[0;32m'
  YELLOW='\033[0;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; RESET='\033[0m'
else
  BOLD=''; DIM=''; GREEN=''; YELLOW=''; RED=''; CYAN=''; RESET=''
fi

info()  { printf "${BOLD}${CYAN}▸${RESET} %s\n" "$*" >&2; }
ok()    { printf "${GREEN}✓${RESET} %s\n" "$*" >&2; }
warn()  { printf "${YELLOW}!${RESET} %s\n" "$*" >&2; }
err()   { printf "${RED}✗${RESET} %s\n" "$*" >&2; }
die()   { err "$@"; exit 1; }

# ─── Argument parsing ────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: install.sh [options]

Options:
  --target-dir <path>   Override skill directory detection
  --api-key <key>       Recipes API key (or set RECIPES_API_KEY)
  --dry-run             Print the plan, do not execute
  --non-interactive     Never prompt; use first match or --target-dir
  --verbose             Print probe details
  --help                Show this message

Environment:
  RECIPES_API_KEY       API key for recipes.wisechef.ai
  RECIPES_API_BASE      Override API base URL
  AGENT_HOME            Override agent home directory

Tested on bash + zsh + fish on Linux/macOS.
WSL/Nix/PowerShell users: open an issue or use --target-dir.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target-dir=*)   TARGET_DIR="${1#*=}"; shift ;;
    --target-dir)     TARGET_DIR="${2:?--target-dir needs a value}"; shift 2 ;;
    --api-key=*)      API_KEY="${1#*=}"; shift ;;
    --api-key)        API_KEY="${2:?--api-key needs a value}"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --non-interactive) NON_INTERACTIVE=1; shift ;;
    --verbose)        VERBOSE=1; shift ;;
    --help|-h)        usage; exit 0 ;;
    *)                die "Unknown argument: $1. Try --help." ;;
  esac
done

# ─── Preflight ───────────────────────────────────────────────────────────────
have() { command -v "$1" >/dev/null 2>&1; }

if ! have curl && ! have wget; then
  die "Need curl or wget. Install one and retry."
fi

fetch() {
  if have curl; then
    curl -fsSL ${API_KEY:+-H "x-api-key: $API_KEY"} "$1" 2>/dev/null
  else
    wget -qO- --header="${API_KEY:+x-api-key: $API_KEY}" "$1" 2>/dev/null
  fi
}

info "Recipes installer v${VERSION}"

# ─── Step 1: Probe agent skill directories ───────────────────────────────────
# Probe in priority order, collect existing dirs with their names.

PROBE_DIRS=()   # paths
PROBE_NAMES=()  # agent names

probe_dir() {
  local dir="$1" name="$2"
  if [ -d "$dir" ]; then
    PROBE_DIRS+=("$dir")
    PROBE_NAMES+=("$name")
    [ "$VERBOSE" = "1" ] && info "Probe: found $name at $dir"
  else
    [ "$VERBOSE" = "1" ] && info "Probe: no $name ($dir)"
  fi
}

probe_dir "${HOME}/.claude/skills" "claude-code"
probe_dir "${HOME}/.codex/skills"  "codex"
probe_dir "${HOME}/.hermes/skills" "hermes"

AGENT_HOME="${AGENT_HOME:-}"
if [ -n "$AGENT_HOME" ]; then
  [ -d "${AGENT_HOME}/skills" ] && probe_dir "${AGENT_HOME}/skills" "AGENT_HOME/skills"
  [ -d "${AGENT_HOME}" ]        && probe_dir "${AGENT_HOME}"        "AGENT_HOME"
fi

# ─── Target selection ────────────────────────────────────────────────────────
# Final list of dirs to install into
INSTALL_DIRS=()

if [ -n "$TARGET_DIR" ]; then
  INSTALL_DIRS+=("$TARGET_DIR")
  info "Using manual target: $TARGET_DIR"
elif [ ${#PROBE_DIRS[@]} -eq 0 ]; then
  err "No agent skill directory found."
  err ""
  err "Create one of:"
  err "  mkdir -p ~/.claude/skills    # Claude Code"
  err "  mkdir -p ~/.codex/skills     # Codex"
  err "  mkdir -p ~/.hermes/skills    # Hermes"
  err ""
  err "Or use: --target-dir /path/to/skills"
  exit 2
elif [ ${#PROBE_DIRS[@]} -eq 1 ]; then
  INSTALL_DIRS+=("${PROBE_DIRS[0]}")
  info "Detected: ${PROBE_NAMES[0]} (${PROBE_DIRS[0]})"
elif [ "$NON_INTERACTIVE" = "1" ] || [ ! -t 0 ]; then
  INSTALL_DIRS+=("${PROBE_DIRS[0]}")
  warn "Multiple agent dirs found. Non-interactive: using ${PROBE_NAMES[0]} (${PROBE_DIRS[0]})."
  warn "Use --target-dir to override."
else
  # Interactive: prompt user
  echo ""
  info "Multiple agent skill directories detected:"
  _i=0
  for _i in "${!PROBE_DIRS[@]}"; do
    printf "  %d) %s  (%s)\n" "$((_i + 1))" "${PROBE_NAMES[_i]}" "${PROBE_DIRS[_i]}" >&2
  done
  _all=$(( ${#PROBE_DIRS[@]} + 1 ))
  printf "  %d) All of the above\n" "$_all" >&2
  printf "Choice [1]: " >&2
  read -r choice || choice="1"
  choice="${choice:-1}"

  if [ "$choice" = "$_all" ]; then
    for d in "${PROBE_DIRS[@]}"; do
      INSTALL_DIRS+=("$d")
    done
  elif [ "$choice" -ge 1 ] 2>/dev/null && [ "$choice" -le "${#PROBE_DIRS[@]}" ] 2>/dev/null; then
    idx=$((choice - 1))
    INSTALL_DIRS+=("${PROBE_DIRS[$idx]}")
    info "Selected: ${PROBE_NAMES[$idx]} (${PROBE_DIRS[$idx]})"
  else
    warn "Invalid choice '$choice', using first: ${PROBE_NAMES[0]}"
    INSTALL_DIRS+=("${PROBE_DIRS[0]}")
  fi
fi

[ ${#INSTALL_DIRS[@]} -eq 0 ] && die "No target directories resolved."

# ─── Step 2: Determine skills to install ─────────────────────────────────────
info "Fetching skill catalog..."

SKILLS_JSON=""
SKILLS_JSON="$(fetch "${API_BASE}/api/skills" 2>/dev/null)" || true

if [ -z "$SKILLS_JSON" ] || echo "$SKILLS_JSON" | grep -q '"detail"'; then
  warn "Could not fetch skill catalog (may need API key). Installing meta-skill only."
  SKILLS_JSON="[]"
fi

# Extract slugs from JSON
parse_slugs() {
  if have python3; then
    python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
if isinstance(data, list):
    items = data
elif isinstance(data, dict) and 'skills' in data:
    items = data['skills']
else:
    items = []
for s in items:
    if isinstance(s, dict):
        slug = s.get('slug','')
        if slug: print(slug)
    elif isinstance(s, str):
        print(s)
" 2>/dev/null
  else
    grep -oP '"slug"\s*:\s*"\K[^"]+' 2>/dev/null || true
  fi
}

SLUGS=""
if [ "$SKILLS_JSON" != "[]" ]; then
  SLUGS="$(echo "$SKILLS_JSON" | parse_slugs)"
fi

if [ -z "$SLUGS" ]; then
  SLUGS="recipes"
fi

SLUG_COUNT="$(echo "$SLUGS" | wc -l | tr -d ' ')"
info "Skills to install: $SLUG_COUNT"

# ─── Step 3: Install each skill ──────────────────────────────────────────────

is_installed() {
  local dir="$1" slug="$2"
  [ -f "${dir}/${slug}/SKILL.md" ]
}

extract_requires() {
  local skill_file="$1"
  if have python3; then
    python3 -c "
import sys, re
try:
    content = open('$skill_file').read()
except:
    sys.exit(0)
m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
if not m:
    sys.exit(0)
fm = m.group(1)
if 'requires:' not in fm:
    sys.exit(0)
in_requires = False
for line in fm.split('\n'):
    stripped = line.strip()
    if stripped.startswith('requires:'):
        in_requires = True
        continue
    if in_requires:
        if stripped.startswith('- '):
            dep = stripped[2:].strip()
            if dep: print(dep)
        elif not line.startswith(' ') and not line.startswith('\t'):
            break
" 2>/dev/null
  fi
}

install_dep() {
  local dep="$1"
  local dep_type="${dep%%:*}"
  local dep_name="${dep#*:}"

  if [ "$dep_type" = "$dep" ]; then
    # No colon — treat as bare package name, guess from context
    warn "Dep without type prefix: $dep (expected pip:name or npm:name)"
    return 0
  fi

  case "$dep_type" in
    pip)
      if have python3 && python3 -c "import ${dep_name//-/_}" 2>/dev/null; then
        [ "$VERBOSE" = "1" ] && ok "pip:$dep_name already installed"
        return 0
      fi
      ;;
    npm)
      if have npm && npm list -g "$dep_name" >/dev/null 2>&1; then
        [ "$VERBOSE" = "1" ] && ok "npm:$dep_name already installed"
        return 0
      fi
      ;;
    *)
      warn "Unknown dep type: $dep"
      return 0
      ;;
  esac

  if [ "$DRY_RUN" = "1" ]; then
    info "[dry-run] Would install: $dep"
    return 0
  fi

  info "Installing dep: $dep"
  case "$dep_type" in
    pip)
      if have pip3; then
        if pip3 install --user "$dep_name" 2>/dev/null; then
          COUNT_DEPS=$((COUNT_DEPS + 1)); return 0
        fi
      elif have pip; then
        if pip install --user "$dep_name" 2>/dev/null; then
          COUNT_DEPS=$((COUNT_DEPS + 1)); return 0
        fi
      fi
      warn "Cannot install pip:$dep_name — no pip found"
      NEEDS_HUMAN=1
      ;;
    npm)
      if have npm; then
        if npm install -g "$dep_name" 2>/dev/null; then
          COUNT_DEPS=$((COUNT_DEPS + 1)); return 0
        fi
      fi
      warn "Cannot install npm:$dep_name — no npm found"
      NEEDS_HUMAN=1
      ;;
  esac
}

install_skill() {
  local slug="$1" dir="$2"

  if is_installed "$dir" "$slug"; then
    [ "$VERBOSE" = "1" ] && ok "$slug already in $dir"
    COUNT_SKIPPED=$((COUNT_SKIPPED + 1))
    return 0
  fi

  if [ "$DRY_RUN" = "1" ]; then
    info "[dry-run] $slug → $dir/$slug/"
    return 0
  fi

  local skill_dir="${dir}/${slug}"
  mkdir -p "$skill_dir"

  # Try fetching SKILL.md from the API
  local skill_content
  skill_content="$(fetch "${API_BASE}/api/skills/${slug}/skill.md" 2>/dev/null)" || true

  if [ -n "$skill_content" ] && ! echo "$skill_content" | grep -q '"detail"\|404\|not found'; then
    echo "$skill_content" > "${skill_dir}/SKILL.md"
    ok "Installed $slug → ${skill_dir}/SKILL.md"
    COUNT_INSTALLED=$((COUNT_INSTALLED + 1))

    # Scan for requires: in frontmatter
    local requires
    requires="$(extract_requires "${skill_dir}/SKILL.md")"
    if [ -n "$requires" ]; then
      while IFS= read -r dep; do
        [ -n "$dep" ] && install_dep "$dep"
      done <<< "$requires"
    fi
    return 0
  fi

  # Fallback: try /skill endpoint for meta-skill
  if [ "$slug" = "recipes" ]; then
    local meta_content
    meta_content="$(fetch "${API_BASE}/skill" 2>/dev/null)" || true
    if [ -n "$meta_content" ]; then
      mkdir -p "${dir}/recipes"
      echo "$meta_content" > "${dir}/recipes/SKILL.md"
      ok "Installed recipes meta-skill → ${dir}/recipes/SKILL.md"
      COUNT_INSTALLED=$((COUNT_INSTALLED + 1))
      return 0
    fi
  fi

  warn "Could not fetch skill: $slug"
  rmdir "$skill_dir" 2>/dev/null || true
  COUNT_ERRORS=$((COUNT_ERRORS + 1))
  return 1
}

for slug in $SLUGS; do
  for tdir in "${INSTALL_DIRS[@]}"; do
    install_skill "$slug" "$tdir"
  done
done

# ─── Step 4: Final report ────────────────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────────────────────"
if [ "$DRY_RUN" = "1" ]; then
  info "[DRY RUN] Plan complete."
  echo "  Would install: $SLUG_COUNT skills"
  echo "  Target dirs:   ${INSTALL_DIRS[*]}"
else
  printf "  ${GREEN}Installed${RESET}: %d skills, %d binary deps\n" "$COUNT_INSTALLED" "$COUNT_DEPS"
  printf "  ${YELLOW}Skipped${RESET}:  %d (already present)\n" "$COUNT_SKIPPED"
  [ "$COUNT_ERRORS" -gt 0 ] && printf "  ${RED}Errors${RESET}:    %d\n" "$COUNT_ERRORS"
fi
echo ""
echo "  Support matrix: Tested on bash + zsh + fish on Linux/macOS."
echo "  WSL/Nix/PowerShell users: open an issue or use --target-dir."
echo ""
echo "  Try it:     recipes --help"
echo "  Verify:     recipes verify"
echo "  Browse:     https://recipes.wisechef.ai"
echo "  Tell your agent: \"Read the recipes skill and follow it.\""
echo "──────────────────────────────────────────────────────────"

# ─── Exit codes ───────────────────────────────────────────────────────────────
[ "$DRY_RUN" = "1" ] && exit 0
[ "$COUNT_ERRORS" -gt 0 ] && exit 1
[ "$NEEDS_HUMAN" -gt 0 ] && exit 2
exit 0
