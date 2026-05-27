---
phase: 213-experience-baseline-harness
verified: 2026-05-27T22:52:29Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
---

# Phase 213: Experience Baseline Harness Verification Report

**Phase Goal:** Capture enough controlled evidence to explain what “internet quality is not good enough” means operationally.
**Verified:** 2026-05-27T22:52:29Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Baseline runbook covers normal browsing, upload, download, RRUL, and `tcp_12down` checks with commands and artifact paths. | ✓ VERIFIED | `docs/RUNBOOKS/baseline.md` documents one-command invocation, `--bind-map`, modes, D-10 posture, serialized order, and `evidence/RUN-<ts>/` tree with `browse`, `tcp_upload`, `tcp_download`, `rrul`, `tcp_12down`. |
| 2 | Each run captures matching `/health`, CAKE state, SQLite alert counts, current rates, measurement quality, and steering state. | ✓ VERIFIED | `RUN-20260527T222043Z` contains 10 `<wan>/<test>` dirs; each has `health-spectrum.ndjson`, `health-att.ndjson`, alert JSONs, steering pre/post health and redacted state, and browse/flent artifact. NDJSON schema test and manifest evidence passed. |
| 3 | Summary maps observed symptoms to likely cause bucket(s). | ✓ VERIFIED | `signal-sheet.json` has all six bucket keys; `213-REPORT.md` gives per-bucket verdicts with evidence citations. Flagged buckets: `upload_ceiling_setpoint` and `refractory_semantics`. |
| 4 | Baseline recommends whether to proceed to measurement investigation, upload reclaim, or another narrower phase first. | ✓ VERIFIED | `signal-sheet.json` and `213-REPORT.md` select primary Phase 215 with runners-up Phase 216 and Phase 214. |
| 5 | Repeatable harness surfaces and offline/live evidence capture exist and are tested (BASE-01). | ✓ VERIFIED | Six Phase 213 scripts exist, are syntactically valid, executable where applicable, and `tests/test_phase213_*.py` passed: 23 passed. Offline `--check-manifest` spot-check produced schema-valid manifest under `/tmp/opencode/p213-verify-check`. |
| 6 | No-mutation/read-only safety boundaries hold (BASE-02). | ✓ VERIFIED | Mutation-boundary tests passed; script grep found no D-10 forbidden mutation tokens in `scripts/phase213-*`; alert-window uses `mode=ro`, no `immutable=1`; no controller source changes required for the phase goal. |
| 7 | Live serialized Spectrum→ATT evidence and operator report exist with recommended next phase (BASE-03). | ✓ VERIFIED | `RUN-20260527T222043Z/manifest.json` records ordered tests: all five Spectrum tests, then all five ATT tests; `bind_map` and egress values are present; `213-REPORT.md` contains recommended next phase. |
| 8 | Per-WAN bind-map and egress provenance are recorded. | ✓ VERIFIED | Live manifest has `bind_map: {spectrum: 10.10.110.226, att: 10.10.110.233}` and observed egress `spectrum: 70.123.224.169`, `att: 99.126.115.47`. |
| 9 | Signal sheet is emitted inside the live RUN dir. | ✓ VERIFIED | `evidence/RUN-20260527T222043Z/signal-sheet.json` and `.md` exist inside the run directory. |
| 10 | Redaction posture holds for committed evidence. | ✓ VERIFIED | Verification scan found zero `*.raw.json` under the live run and zero unredacted D-08 secret-key hits in JSON/MD/CSV/NDJSON/TSV evidence. |
| 11 | Background health pollers did not leave live residue. | ✓ VERIFIED | Evidence row counts are balanced per test (77–94 rows per WAN endpoint) with zero `poll-failures.tsv` failure rows; process check found no persistent `phase213-health-poller` beyond the verifier’s own search command. |
| 12 | ROADMAP success criteria are covered. | ✓ VERIFIED | Success Criteria 1–4 map directly to truths 1–4 above and are supported by runbook, evidence tree, signal sheet, and operator report. |
| 13 | BASE-01 is satisfied. | ✓ VERIFIED | Repeatable runbook plus orchestrator scripts and live artifacts cover browsing/upload/download/RRUL/`tcp_12down` with timestamps, commands, and artifact paths. |
| 14 | BASE-02 is satisfied. | ✓ VERIFIED | Matching `/health` NDJSON, CAKE/current-rate/measurement-quality fields, alert windows, and steering snapshots exist for each live test window. |
| 15 | BASE-03 is satisfied. | ✓ VERIFIED | Results classify primary and runner-up buckets and recommend Phase 215 first. |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase213-baseline-capture.sh` | One-command orchestrator with bind-map, offline/live modes, serialized run, poller cleanup, classifier invocation. | ✓ VERIFIED | 347 lines; `bash -n` passed; invokes all leaf scripts, writes manifest/signal sheet, records bind map. Advisory WR-01 noted below, not blocking for captured run. |
| `scripts/phase213-health-poller.sh` | 1Hz extended `/health` NDJSON poller with TSV failure sidecar. | ✓ VERIFIED | 259 lines; `bash -n` passed; emits required projection fields; schema test passed. |
| `scripts/phase213-browse-loop.sh` | Source-bound curl browse CSV loop. | ✓ VERIFIED | 122 lines; `bash -n` passed; uses `curl --interface`, seven default sites, exact CSV header. |
| `scripts/phase213-alert-window.sh` | Read-only SQLite alert extraction; offline local DB mode. | ✓ VERIFIED | 245 lines; `bash -n` passed; `mode=ro` present, no `immutable=1`; alert-window tests passed. |
| `scripts/phase213-steering-snapshot.sh` | Pre/post steering `/health` and redacted state capture; raw temp outside evidence. | ✓ VERIFIED | 108 lines; `bash -n` passed; `mktemp -t phase213-steering-raw` and immediate EXIT trap present; no raw evidence artifacts found. |
| `scripts/phase213-classify.py` | Offline six-bucket signal-sheet emitter. | ✓ VERIFIED | 388 lines; Python compile passed; no `wanctl` import; no `setpoint_mbps + 6`; classifier tests passed. Advisory WR-02 noted below, not blocking for captured run. |
| `docs/RUNBOOKS/baseline.md` | Operator runbook. | ✓ VERIFIED | Documents one command, modes, mutation posture, serialized order, bind-map, artifact tree, and signal sheet reading. |
| `evidence/RUN-CHECK-MANIFEST/manifest.json` | Offline manifest-check artifact. | ✓ VERIFIED | Contains every key from `manifest-expected-keys.json`, including `bind_map`. |
| `evidence/RUN-20260527T222043Z/` | Full live evidence tree. | ✓ VERIFIED | 10 test dirs; each has health, alert, steering, and browse/flent artifacts; manifest has 10 ordered tests. |
| `213-REPORT.md` | Operator-authored final report. | ✓ VERIFIED | Contains per-bucket verdicts, evidence citations, next-phase recommendation, run metadata, and safety/redaction closeout. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `phase213-baseline-capture.sh` | Leaf scripts | `bash scripts/phase213-{health-poller,browse-loop,alert-window,steering-snapshot}.sh` | ✓ WIRED | Direct invocations present in `run_bracketed_test()` and `start_pollers()`. |
| `phase213-baseline-capture.sh` | `phase191-flent-capture.sh` | per-test non-browse call with per-WAN `--local-bind` | ✓ WIRED | Flent call passes `--tests`, `--wan`, `--local-bind`, `--host`, `--duration`, `--output-dir`. |
| `phase213-baseline-capture.sh` | Per-WAN bind map | `--bind-map` parsed into `BIND[wan]` | ✓ WIRED | Live manifest records expected Spectrum/ATT bind values and observed egress. |
| `phase213-baseline-capture.sh` | Poller cleanup | `POLLER_PIDS=()` and `trap 'cleanup_pollers; cleanup_temp' EXIT INT TERM` | ✓ WIRED | Present and live evidence shows no orphaned pollers / zero poll failure rows. |
| `phase213-alert-window.sh` | SQLite live DBs | `sqlite3 -readonly -json "file:${db}?mode=ro"` over SSH | ✓ WIRED | Live evidence includes alert JSONs for each test; `immutable=1` absent. |
| `phase213-alert-window.sh` | Offline fixture DB | `--local-db` branch without SSH | ✓ WIRED | Alert-window tests passed; offline mode exercised against fixture. |
| `phase213-steering-snapshot.sh` | Raw temp cleanup/redaction | `mktemp -t ...`; `trap 'rm -f "$RAW_TMP"' EXIT INT TERM`; Python redactor | ✓ WIRED | Live evidence contains redacted state only; zero raw JSON under evidence. |
| `phase213-classify.py` | Live run evidence | `--run-dir` reads NDJSON/alerts/flent/browse/steering files | ✓ WIRED | Signal sheet generated from `RUN-20260527T222043Z`; six buckets present. |
| `213-REPORT.md` | Signal-sheet evidence | `evidence/RUN-20260527T222043Z/...` citations | ✓ WIRED | Report cites signal sheet and per-test evidence paths for bucket verdicts. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `phase213-health-poller.sh` | NDJSON row fields | Live `/health` endpoints via `curl`, projected by `jq` | Yes — live run has 77–94 rows per test endpoint and zero poll failures. | ✓ FLOWING |
| `phase213-alert-window.sh` | `rows`, `summary` | Live SQLite DBs with `mode=ro` over SSH, fixture DB for tests | Yes — alert JSON files exist for all live test dirs; fixture tests passed. | ✓ FLOWING |
| `phase213-steering-snapshot.sh` | redacted state JSON | SSH `sudo -n cat /var/lib/wanctl/steering_state.json` to temp, then redactor | Yes — pre/post redacted files exist in every test dir. | ✓ FLOWING |
| `phase213-browse-loop.sh` | `browse.curl.csv` rows | `curl --interface` site rotation | Yes — live browse CSV artifacts exist for Spectrum and ATT. | ✓ FLOWING |
| `phase213-baseline-capture.sh` | `manifest.json`, `signal-sheet.*` | Orchestrated leaf artifacts + classifier | Yes — live manifest lists 10 ordered tests and signal sheet exists in run dir. | ✓ FLOWING |
| `phase213-classify.py` | bucket evidence rows | `RUN-20260527T222043Z` NDJSON/CSV/JSON evidence and config ceiling values | Yes — signal sheet has six buckets and non-empty evidence rows. | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 213 tests pass | `.venv/bin/pytest tests/test_phase213_*.py -q` | `23 passed in 1.42s` | ✓ PASS |
| Script syntax valid | `bash -n` for shell scripts + `py_compile` for classifier | all exited 0 | ✓ PASS |
| Offline manifest mode runs without production access | `bash scripts/phase213-baseline-capture.sh --check-manifest --bind-map spectrum=fixture,att=fixture --evidence-root /tmp/opencode/p213-verify-check` | emitted schema-valid `RUN-CHECK-MANIFEST/manifest.json` | ✓ PASS |
| Live evidence tree is complete | Python inspection of run dir | 10 test dirs; all have health, alert, steering, and browse/flent artifacts | ✓ PASS |
| Manifest schema coverage | Python compare against `manifest-expected-keys.json` | no missing keys in check-manifest or live manifest | ✓ PASS |
| Redaction/no-raw audit | Python scan under live run | zero `*.raw.json`; zero unredacted D-08 key hits | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| BASE-01 | Plans 01, 02, 04, 05 | Operator has repeatable production baseline runbook for browsing/upload/download/RRUL/`tcp_12down` with timestamps, commands, artifact paths. | ✓ SATISFIED | `docs/RUNBOOKS/baseline.md`, orchestrator help/modes, live `manifest.json` with 10 ordered tests, report requirement table. |
| BASE-02 | Plans 01, 02, 03, 04, 05 | Each baseline run captures matching `/health`, CAKE state, SQLite alert counts, current rates, measurement quality, and steering state for the same time window. | ✓ SATISFIED | Live per-test evidence dirs include health NDJSON, alert JSONs, steering pre/post redacted state; NDJSON expected-key and alert-window tests passed. |
| BASE-03 | Plans 01, 04, 05 | Baseline results classify perceived-quality issue into cause bucket(s). | ✓ SATISFIED | `signal-sheet.json` has six buckets, flags upload ceiling/setpoint and refractory semantics, and recommends Phase 215; `213-REPORT.md` gives operator verdicts. |

No additional Phase 213 requirement IDs were found orphaned in `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase213-baseline-capture.sh` | 113-119 | Code review WR-01: `cleanup_pollers` suppresses `wait` status for already-exited pollers. | ⚠️ Warning | Non-blocking for Phase 213 goal: live run evidence has balanced health row counts and zero poll failures. Track if reusing harness for future repeated captures. |
| `scripts/phase213-classify.py` | 146-159 | Code review WR-02: unrecovered RED/SOFT_RED would be represented as `0` recovery lag. | ⚠️ Warning | Non-blocking for captured evidence: verification found all RRUL/`tcp_12down` download states were `GREEN` with zero RED/SOFT_RED rows, so this path did not affect the Phase 213 verdict. Track before relying on future runs with unrecovered RED. |
| `scripts/phase213-classify.py` | 90, 191 | Empty returns for missing optional files (`return []`, `return {}`). | ℹ️ Info | Defensive defaults, not stubs; live run populated required evidence and tests cover expected fixture behavior. |

### Human Verification Required

None. The human-only production run checkpoint has already produced committed evidence and an operator-authored report; automated verification checked those artifacts rather than re-running production traffic.

### Gaps Summary

No blocking gaps found. The phase goal is achieved: the repeatable harness exists, safety boundaries held, offline/live evidence exists, the live serialized Spectrum→ATT run produced classified evidence, and the report recommends Phase 215 with runners-up.

---

_Verified: 2026-05-27T22:52:29Z_
_Verifier: the agent (gsd-verifier)_
