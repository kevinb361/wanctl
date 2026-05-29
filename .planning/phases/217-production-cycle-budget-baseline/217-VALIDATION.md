---
phase: 217
slug: production-cycle-budget-baseline
status: approved
nyquist_compliant: n/a-measurement-phase
wave_0_complete: n/a
created: 2026-05-29
revised: 2026-05-29
approved: 2026-05-29
revision_note: "Updated post-reviews (Codex) + research refresh. Old text/grep-based verifies (HIGH finding 1, 2) replaced with jq-based JSON-format verifies. Task IDs restructured to match the new 3-plan layout (scaffold/parser/runbook → pilot+capture → analysis/summary/todo). Per-task <automated> blocks in each PLAN.md are the canonical source; this file is a navigation map."
---

# Phase 217 — Validation Strategy (revised)

> Per-phase validation contract. **This phase ships no `src/` code** — it is a measurement
> + decision phase (offline JSON parser + runbook + capture + summary + todo lifecycle).
> The Nyquist sampling contract (test framework, watched suite, Wave-0 stubs) does not apply.
> Validation is **artifact-shape**, not test-runtime.
>
> **Revision context:** the original 3-plan structure relied on a text-DEBUG capture path
> with regex-based `grep -c "autorate_cycle_total:" >= 60000` verifies. Codex review and
> the research refresh established that `autorate_cycle_total` is NOT emitted in
> text-formatter DEBUG output (it lives only in the `extra=` dict of `"Cycle timing"`).
> The data path switched to `WANCTL_LOG_FORMAT=json` NDJSON + a new offline parser, so all
> verifies that targeted the text-grep contract were rewritten to `jq`-based JSON checks.

---

## Why `nyquist_compliant: n/a-measurement-phase`

The standard Nyquist contract assumes a code phase with a test framework (`pytest`, etc.)
producing fast-feedback signal on every task commit. Phase 217 ships:

- One **operator runbook** (`docs/PROFILING.md`).
- One **offline NDJSON parser** (`scripts/profiling_collector_json.py`) — fixture-verifiable inline (Plan 01 Task 2).
- A **gitignored capture directory** (`.planning/perf/capture/`) for raw production NDJSON.
- One **committed capture-window metadata** (`.planning/perf/217-capture-window.json`).
- One **committed aggregate artifact** (`.planning/perf/v1.45-baseline-spectrum-<date>.profile.json`).
- One **committed storage-attribution artifact** (`.planning/perf/v1.45-baseline-spectrum-<date>.ingestion.json` OR an unmeasured stub).
- One **1-page summary** (`.planning/perf/217-cycle-budget-summary.md`).
- One **todo lifecycle move** (`pending/` → `done/`).

There is no production-path code to regression-test. The phase's correctness is established by:

1. The offline parser passes its inline fixture (Plan 01 Task 2 — golden + label-reconstruction + skip-stray + skip-malformed + missing-extras + error-path).
2. The pilot empirically confirms `cycle_total_ms` appears as a top-level JSON key under production conditions AND that the production disk sustains DEBUG I/O without watchdog impact (Plan 02 Task 1 — research Open Questions 1 + 2 resolved at runtime).
3. The full window NDJSON spans ≥1h with ≥60000 `"Cycle timing"` records and the drop-in is reverted with the canonical `systemctl cat` + `ps -ef` checks (Plan 02 Tasks 2 + 3).
4. The aggregate `.profile.json` parses, contains `autorate_cycle_total`, and the jq verdict pipeline yields a structured boolean pair (Plan 03 Task 1).
5. The summary states the falsifiable D-03 verdict pair with real measured numbers (Plan 03 Task 2).
6. The todo file ends in `done/` with a verdict dated from `217-capture-window.json.window.end_utc` (Plan 03 Task 3).

Each task carries an inline `<verify><automated>...</automated></verify>` block — that is
the sampling rate for this phase.

---

## Per-Task Verification Map (revised)

The per-task `<automated>` blocks in each PLAN.md are canonical. This table is a
navigation map showing which task closes which acceptance condition. Status columns update
during execute-phase.

| Task ID  | Plan | Wave | Requirement | Verify Type    | Verifies (summary; canonical command in PLAN.md `<automated>`)                                                                                                                                                                          | Status     |
|----------|------|------|-------------|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|
| 217-01-1 | 01   | 1    | PERF-01     | scaffold       | `.planning/perf/.gitkeep` exists AND `.planning/perf/capture/.gitignore` ignores all but itself (gitignored capture dir per research Pitfall 7).                                                                                          | ⬜ pending |
| 217-01-2 | 01   | 1    | PERF-02     | unit-fixture   | `scripts/profiling_collector_json.py` golden + label-reconstruction + skip-stray + skip-malformed + missing-extras + error-path checks pass on a 5-line inline fixture; exit 0 on golden, exit 2 on empty input (NOT exit 1).             | ⬜ pending |
| 217-01-3 | 01   | 1    | PERF-01     | doc-shape      | `docs/PROFILING.md` exists AND contains `WANCTL_LOG_FORMAT=json`, `--profile --debug`, `systemctl revert wanctl@spectrum`, `profiling_collector_json.py`, `spectrum_debug.log`, `40`, `ingestion-rate`, `router_communication`, `Pilot`; NO `10.10.x.x` literal. | ⬜ pending |
| 217-02-1 | 02   | 1    | PERF-01     | pilot-gate     | (operator) 5-min pilot drop-in installed; `jq keys` on `spectrum_debug.log` lists `cycle_total_ms`; zero unit restarts; pilot reverted (canonical `systemctl cat` + `ps -ef`); `.planning/perf/capture/pilot-spectrum_debug.ndjson` ≥5000 records. | ⬜ pending |
| 217-02-2 | 02   | 1    | PERF-01     | full-capture   | (operator) Full drop-in installed; window ≥1h; driven segment landed inside window; **revert verified** (`systemctl cat` no override, `ps -ef` no `--profile`/`--debug`/`WANCTL_LOG_FORMAT=json`, `/health.version == 1.45.0`); `.planning/perf/217-capture-window.json` committed with `revert_verified: true`. | ⬜ pending |
| 217-02-3 | 02   | 1    | PERF-01     | artifact-shape | `jq -c 'select(.message=="Cycle timing") \| .cycle_total_ms' spectrum_debug.ndjson \| wc -l` ≥ 60000 AND `cycle_total_ms` types include `"number"` (not `"null"`) AND `217-capture-window.json.validation.router_write_coverage` is `present` or `absent_gap`. | ⬜ pending |
| 217-03-1 | 03   | 2    | PERF-02     | analysis-shape | `.profile.json` exists, contains `autorate_cycle_total` with `count >= 60000`, populated `avg_ms`/`p99_ms`; `.ingestion.json` exists (real windowed call OR `unmeasured` stub); `/tmp/217-verdict.json` has `passes_headroom`, `passes_dominance`, `verdict` booleans + numbers; ingestion used explicit `--from/--to` from `217-capture-window.json`. | ⬜ pending |
| 217-03-2 | 03   | 2    | PERF-02, PERF-03 | summary-shape | `.planning/perf/217-cycle-budget-summary.md` contains: `cycle_total`, `passes_headroom`, `passes_dominance`, `40`, `observer`, `storage`, `deprioritiz`/`promote`, `router_communication`, `v1.45`; NO `TBD`/`<...>` placeholders; NO `10.10.x.x` literal; driven-segment coupling enforced (if `router_write_coverage==absent_gap` and verdict `no_action`, body contains `conditional on steady-state` or `promote`). | ⬜ pending |
| 217-03-3 | 03   | 2    | PERF-01     | todo-lifecycle | `.planning/todos/done/2026-04-15-...md` exists AND NOT in `pending/`; contains `## (Closed|Promoted)`, `Phase 217`, `217-cycle-budget-summary.md` reference; close-date matches `217-capture-window.json.window.end_utc[:10]` (no hard-coded date — REVIEWS LOW finding fix). | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## What Changed vs the Original VALIDATION.md

| Original verify                                                                                | Revised verify                                                                                                            | Why                                                                                            |
|------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `grep -c "autorate_cycle_total:" .planning/perf/spectrum-capture-raw.log >= 60000`             | `jq -c 'select(.message=="Cycle timing") \| .cycle_total_ms' .planning/perf/capture/spectrum_debug.ndjson \| wc -l >= 60000` | Text formatter drops `extra=` keys; `autorate_cycle_total` is never emitted as a parseable text DEBUG line. JSON formatter preserves it. (REVIEWS HIGH 1.) |
| `head -1 /var/log/wanctl/spectrum.log` returns non-JSON                                        | (removed — capture uses `WANCTL_LOG_FORMAT=json` deliberately) AND `jq keys` on `spectrum_debug.log` lists `cycle_total_ms` | `spectrum.log` is INFO-only; DEBUG sink is `spectrum_debug.log`. (REVIEWS HIGH 2.)              |
| `scripts/profiling_categorize.py <fixture> --budget 50` (separate categorize helper)            | (categorize math is now inline jq pipeline, encoded in PLAN 03 Task 1 and docs/PROFILING.md). The fixture-verified helper is the NEW `scripts/profiling_collector_json.py`. | Reduced surface — one new script does NDJSON → `.profile.json`; verdict math is a jq one-liner the runbook also documents. |
| Mid-window `/health` snapshot vs DEBUG cycle_total delta                                       | Adjacent ON/OFF `/health` windows (option a) OR documented caveat (option b)                                              | Same-window delta is ~0 by construction (same in-process profiler). (REVIEWS HIGH 3.)         |
| `wanctl-history --ingestion-rate --wan spectrum` (no time bounds)                              | `wanctl-history --ingestion-rate --wan spectrum --from <window.start_utc> --to <window.end_utc>` derived from `217-capture-window.json` | Default is last hour at `src/wanctl/history.py:616-624`; misaligns if Plan 03 runs hours later. (REVIEWS MEDIUM finding.) |
| Subjective "comfortable headroom" verdict                                                      | Falsifiable: `passes_headroom = avg_ms < 40.0 AND p99_ms < 50.0`; `passes_dominance = max_category_pct < 40.0`           | Pre-data numeric bar required for D-03 to be falsifiable. (REVIEWS MEDIUM finding.)            |
| Hard-coded `2026-05-30` in todo lifecycle text                                                  | Close date derived from `217-capture-window.json.window.end_utc[:10]`                                                     | (REVIEWS LOW finding.)                                                                          |
| `.planning/perf/spectrum-capture-raw.log` committed to repo                                    | Raw NDJSON stays in gitignored `.planning/perf/capture/`; only aggregate `.profile.json` + `.ingestion.json` + summary + window-metadata committed. | (REVIEWS MEDIUM finding + research Pitfall 7.)                                                  |

---

## Wave 0 Artifacts (no test stubs needed)

- `.planning/perf/.gitkeep` — created by Plan 01 Task 1.
- `.planning/perf/capture/.gitignore` — created by Plan 01 Task 1 (gitignores all raw NDJSON retrieval).
- `scripts/profiling_collector_json.py` — created by Plan 01 Task 2 with inline fixture verification.
- `docs/PROFILING.md` — created by Plan 01 Task 3 with the JSON-data-path runbook.
- No test framework install, no `conftest.py`, no Wave-0 test stubs — this phase ships no `src/` code.

---

## Manual-Only Verifications

| Behavior                                                                                         | Requirement | Why Manual                                                                  | Test Instructions                                                                                  |
|--------------------------------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| 5-min pilot drop-in + JSON-key gate + watchdog observation on the Spectrum production host       | PERF-01     | Touches a 24/7 production daemon; requires operator judgment + SSH         | Plan 02 Task 1 `<how-to-verify>` step-by-step                                                   |
| Full ≥1h drop-in + revert + retrieval on the Spectrum production host                            | PERF-01     | Touches a 24/7 production daemon; requires operator judgment + SSH         | Plan 02 Task 2 `<how-to-verify>` step-by-step                                                   |
| Driven RRUL/upload segment inside the capture window (D-02)                                      | PERF-01     | Run from dev VM against external test target                               | `scripts/phase213-baseline-capture.sh --host dallas --flent-duration 60 --tests tcp_upload,rrul --wans spectrum` |
| (Optional) Adjacent ON/OFF `/health` poll windows for observer-effect number (research §Q5 (a))   | PERF-03     | Polls a production endpoint over ~10 min; requires operator scheduling      | Plan 02 Task 2 steps 1 + 3                                                                       |
| Pre-commit secret/IP scrub of `.planning/perf/*.profile.json` + `.ingestion.json` + summary       | PERF-01     | Adversarial inspection of operator artifacts                                | Operator reviews diff before `git commit`; no `secrets`/`credentials` content; non-secret timing/operating-point data acceptable |

---

## Validation Sign-Off

- [x] Every task has an inline `<automated>` verify OR a documented manual operator step
- [x] No 3 consecutive tasks without automated verify (all 9 tasks carry inline verifies)
- [x] No watch-mode flags (none applicable — no test suite)
- [x] Artifact-shape acceptance criteria are falsifiable (file existence, jq counts, JSON-parse, exit codes, boolean type checks)
- [x] `nyquist_compliant: n/a-measurement-phase` justified above
- [x] D-03 verdict is falsifiable (numeric headroom bar + numeric dominance bar) BEFORE the data is seen
- [x] Storage attribution uses explicit `--from/--to` window bounds (research Pitfall 4)
- [x] Raw NDJSON stays out of git (research Pitfall 7)
- [x] Observer-effect is a number OR a documented caveat — never a same-window `/health` delta (research Pitfall 3)
- [x] Driven-segment coupling enforced: unconditional no-action requires `router_write_coverage == "present"`

**Approval:** revised + re-approved 2026-05-29 (orchestrator, post `--reviews` replan)
**Supersedes:** the original VALIDATION.md task map of 2026-05-29 (text-DEBUG/regex contract) — task IDs and verify commands restructured to match the JSON capture data path. Raw `.planning/perf/spectrum-capture-raw.log` artifact removed (no longer committed; replaced by gitignored `.planning/perf/capture/spectrum_debug.ndjson`).
</content>
</invoke>
