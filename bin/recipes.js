#!/usr/bin/env node
// Thin Node shim — proxies to the Python CLI bundled with the package.
// The Python CLI is the canonical implementation; this exists so npm users
// can invoke `recipes ...` without installing the pip package.

const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const cliPath = path.join(__dirname, 'recipes');
if (!fs.existsSync(cliPath)) {
  console.error(`recipes: bundled CLI not found at ${cliPath}`);
  process.exit(127);
}

function findPython() {
  const candidates = process.platform === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python'];
  for (const p of candidates) {
    try {
      const r = require('node:child_process').spawnSync(p, ['-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)']);
      if (r.status === 0) return p;
    } catch {}
  }
  return null;
}

const py = findPython();
if (!py) {
  console.error('recipes: requires Python 3.11+ on PATH (apt install python3 / brew install python).');
  process.exit(127);
}

const child = spawn(py, [cliPath, ...process.argv.slice(2)], { stdio: 'inherit' });
child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
