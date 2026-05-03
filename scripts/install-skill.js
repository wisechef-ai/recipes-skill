#!/usr/bin/env node
// postinstall: drop SKILL.md into the user's preferred skills directory.
// Detection order: ~/.claude/skills (Claude Code) → ~/.codex/skills (Codex) → ./skills (fallback).

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const dryRun = process.argv.includes('--dry-run');

function pickTarget() {
  const home = os.homedir();
  const claude = path.join(home, '.claude', 'skills');
  const codex = path.join(home, '.codex', 'skills');
  if (fs.existsSync(path.dirname(claude))) return path.join(claude, 'recipes');
  if (fs.existsSync(path.dirname(codex))) return path.join(codex, 'recipes');
  return path.join(process.cwd(), 'skills', 'recipes');
}

const pkgRoot = path.resolve(__dirname, '..');
const sourceMd = path.join(pkgRoot, 'SKILL.md');

if (!fs.existsSync(sourceMd)) {
  // Not installed via npm pack — silently skip (e.g. running test in CI).
  process.exit(0);
}

const target = pickTarget();
const targetMd = path.join(target, 'SKILL.md');

if (dryRun) {
  console.log(`recipes postinstall (dry-run): would write ${targetMd}`);
  process.exit(0);
}

try {
  fs.mkdirSync(target, { recursive: true });
  fs.copyFileSync(sourceMd, targetMd);
  console.log(`✓ Installed Recipes meta-skill → ${targetMd}`);
  console.log("  Tell your agent: 'Read this SKILL.md and follow it.'");
} catch (err) {
  // Don't block npm install on a non-critical filesystem error.
  console.warn(`recipes postinstall: could not write ${targetMd}: ${err.message}`);
  console.warn('  You can copy SKILL.md manually from this package later.');
  process.exit(0);
}
