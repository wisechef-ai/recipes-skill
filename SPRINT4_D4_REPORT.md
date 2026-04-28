# Sprint 4 D4 Report — `recipes telemetry emit` CLI Subcommand

**Date:** 2026-04-28  
**Branch:** `agent/tori/recipes-cli-sprint4-telemetry`  
**Deliverable:** D4 — CLI `telemetry emit` subcommand

---

## Deliverables Checklist

- [x] `recipes telemetry emit` subcommand implemented in `bin/recipes`
- [x] All required flags: `--skill`, `--event`
- [x] All optional flags: `--goal-class`, `--duration`, `--retries`, `--intervention` / `--no-intervention`, `--agent-hash`
- [x] `RECIPES_API_KEY` env var required; exits 1 with message if absent
- [x] `RECIPES_API_BASE` env var used for base URL (default: `https://recipes.wisechef.ai/api`)
- [x] POSTs JSON to `${BASE}/telemetry` with `x-api-key` header
- [x] Exit 0 on 201, prints `event_id` to stdout
- [x] Exit 1 with stderr message on 4xx, 5xx, or network error
- [x] Client-side validation:
  - `event_type` ∈ `{install, first_use, task_completed, task_failed, replaced}`
  - `duration_seconds` 0..86400
  - `agent_class_hash` regex `^[a-f0-9]{8,64}$`
- [x] `tests/test_telemetry_emit.py` with 14 tests
- [x] All tests pass (`pytest -x -k telemetry`)
- [x] All pre-existing tests pass (26 total)
- [x] Files committed per sprint invariant

---

## Files Touched

| File | Change |
|---|---|
| `bin/recipes` | Added `cmd_telemetry_emit`, `cmd_telemetry` functions; updated `build_parser()` with `telemetry emit` subparser; updated `main()` dispatch table |
| `tests/test_telemetry_emit.py` | New file — 14 tests |

---

## Wire Format Sent

POST `${RECIPES_API_BASE}/telemetry`

Headers:
- `Content-Type: application/json`
- `x-api-key: <RECIPES_API_KEY>`
- `User-Agent: recipes-cli/0.1.0 (+https://recipes.wisechef.ai)`

Body (typed mode):
```json
{
  "event_type": "task_completed",
  "skill_slug": "agent-rescue",
  "goal_class": "client-reporting",
  "duration_seconds": 42,
  "retry_count": 0,
  "user_intervention": false,
  "agent_class_hash": "deadbeef1234abcd"
}
```

Optional fields (`goal_class`, `duration_seconds`, `agent_class_hash`) are omitted from the payload when not provided (no `null` pollution).

---

## Tests Added

File: `tests/test_telemetry_emit.py`

| # | Test | Coverage |
|---|---|---|
| 1 | `test_telemetry_emit_happy_path` | Full subprocess + mock server; exit 0; event_id printed; headers and payload checked |
| 2 | `test_telemetry_emit_minimal` | Only required flags; optional fields absent from payload; defaults correct |
| 3 | `test_telemetry_emit_all_flags` | All optional flags forwarded in payload |
| 4 | `test_telemetry_emit_no_api_key` | Exit 1 + RECIPES_API_KEY in stderr when env var absent |
| 5 | `test_telemetry_emit_bad_event_type` | Exit 1 for unrecognized event type |
| 6 | `test_telemetry_emit_bad_duration` | Exit 1 for duration > 86400 |
| 7 | `test_telemetry_emit_duration_zero_ok` | duration=0 accepted (boundary) |
| 8 | `test_telemetry_emit_duration_max_ok` | duration=86400 accepted (boundary) |
| 9 | `test_telemetry_emit_bad_agent_hash` | Exit 1 for short or uppercase hash |
| 10 | `test_telemetry_emit_agent_hash_valid` | Minimum 8-char lowercase hex hash accepted |
| 11 | `test_telemetry_emit_http_4xx` | Exit 1 on 422 response, non-empty stderr |
| 12 | `test_telemetry_emit_http_5xx` | Exit 1 on 500 response, "500" or "error" in stderr |
| 13 | `test_telemetry_emit_intervention_flag` | `--intervention` → `user_intervention: true` |
| 14 | `test_telemetry_emit_no_intervention_default` | `--no-intervention` → `user_intervention: false` |

---

## Test Pass Output

```
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-9.0.2, pluggy-1.6.0
collected 14 items

tests/test_telemetry_emit.py::test_telemetry_emit_happy_path PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_minimal PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_all_flags PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_no_api_key PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_bad_event_type PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_bad_duration PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_duration_zero_ok PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_duration_max_ok PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_bad_agent_hash PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_agent_hash_valid PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_http_4xx PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_http_5xx PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_intervention_flag PASSED
tests/test_telemetry_emit.py::test_telemetry_emit_no_intervention_default PASSED

============================= 14 passed in 8.03s ==============================

Total suite: 26 passed (including 12 pre-existing tests)
```

---

## Known Issues / TODOs

None. All contract requirements met.

- The server-side `skill_slug` validation (must exist in `skills` table) is enforced by the API (D3); the CLI sends the slug as-is per contract.
- `goal_class` is an open enum per contract — no client-side enum validation applied (server validates).
- `retry_count` has no range constraint in the contract — no client-side bound applied.
