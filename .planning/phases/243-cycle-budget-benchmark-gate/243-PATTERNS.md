# Phase 243: Cycle-Budget Benchmark Gate - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 13 new files
**Analogs found:** 12 / 13 (1 novel artifact — pre-registration markdown — has no code analog)

This is a **measurement + gate** phase. It creates **zero** `src/wanctl/` edits (SAFE-17:
cleanest posture is an *empty* `src/wanctl/` diff vs the 242 close anchor). All new files are
throwaway benchmark scaffolding under `scripts/`, mirror unit tests under `tests/`, plus
pre-registration/evidence artifacts under the phase dir. Every new file copies an existing
in-repo analog — this phase is ~90% orchestration of existing instrumentation.

**Key anchor facts (verified):**
- **242 close anchor = `fcc2e15b`** (`git log`: "test(242-05): refresh SAFE-17 boundary
  evidence"; matches `head_commit` in `safe17-boundary-242.json`). The 243 SAFE-17 verifier
  diffs `src/wanctl/` from this commit and requires **empty**.
- **243 PHASE_CLOSE_ANCHOR** = the 243 close commit (TBD at phase close). The mirror test pins
  the worktree to this, **not HEAD** (memory: SAFE-17 boundary tests rot against HEAD).
- The cycle-budget capture path **already exists**: `"Cycle timing"` NDJSON →
  `scripts/profiling_collector_json.py` → per-label `avg_ms`/`p99_ms`. Reuse, don't rebuild.

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `scripts/phase243-safe17-boundary-check.sh` | boundary verifier (shell) | git-diff / transform | `scripts/phase242-safe17-boundary-check.sh` | exact (clone, simplify) |
| `tests/test_phase243_safe17_verifier.py` | test | request-response (subprocess) | `tests/test_phase241_safe17_verifier.py` | exact (clone, re-pin anchor) |
| `scripts/phase243-bench-run.sh` | bench launcher (shell) | event-driven / process-orchestration | `scripts/soak-capture.sh` (loop/env shape) + `src/wanctl/benchmark.py:424` (flent invoke) | role-match |
| `scripts/phase243-hygiene-sampler.sh` | soak sampler (shell) | streaming NDJSON | `scripts/soak-capture.sh` | exact (NDJSON-per-tick pattern) |
| `scripts/phase243-cycle-rollup.py` | rollup (python) | transform (NDJSON→stats) | `scripts/profiling_collector_json.py` (+ `soak_summary_aggregate.py` percentiles) | exact |
| `scripts/phase243-gate-eval.py` | gate evaluator (python) | transform (verdict) | `scripts/phase206-gate-check.py` + `scripts/phase224-gate-eval.py` | exact |
| `scripts/phase243-thresholds.json` | config (frozen thresholds) | config | `scripts/phase206-thresholds.json` | exact |
| `tests/test_phase243_cycle_rollup.py` | test | request-response | (pytest pattern from 241 mirror test) + collector contract | role-match |
| `tests/test_phase243_hygiene_sampler.py` | test | request-response | same | role-match |
| `tests/test_phase243_gate_eval.py` | test | request-response | same (fixtures: pass + each fail mode) | role-match |
| `tests/test_phase243_prereg.py` | test | request-response | same (presence/shape assertion) | role-match |
| `.planning/.../243-BENCHMARK-PREREGISTRATION.md` | doc (frozen gate) | doc | **none** (novel; mirror `phase206-thresholds.json` `_notes` single-source rule) | no analog |
| `.planning/.../evidence/safe17-boundary-243.json` | evidence (emitted) | data | `.planning/.../242-.../evidence/safe17-boundary-242.json` | exact (emitted by verifier) |

---

## Pattern Assignments

### `scripts/phase243-safe17-boundary-check.sh` (boundary verifier, git-diff)

**Analog:** `scripts/phase242-safe17-boundary-check.sh`

**CRITICAL simplification:** 242 carries 239/240/241 protected-body + `measure_rtt`
fping-scorer-guard machinery *because those phases edited controller source*. **243 edits
none.** The 243 verifier reduces to: dirty-tree fail-closed gate + **`src/wanctl/` diff vs the
242 close anchor must be EMPTY** + `--self-test` + evidence JSON. Drop the protected-body
helper call, the `check_measure_rtt_fping_scorer_guard`, and the per-frozen-file `git diff
--quiet` blocks — there is no allowed `src/wanctl/` diff to shape.

**`set -e` + anchor constants** (242 lines 17-25) — replace the multi-anchor block with a single
242-close anchor; the allowlist becomes the empty set:
```bash
set -euo pipefail
ANCHOR="fcc2e15b"   # Phase 242 close (matches safe17-boundary-242.json head_commit)
OUT=".planning/phases/243-cycle-budget-benchmark-gate/evidence/safe17-boundary-243.json"
ALLOWED_OUT_PREFIX=".planning/phases/243-cycle-budget-benchmark-gate/evidence/"
# 243 allowlist = ∅ : any changed src/wanctl path is disallowed.
```

**`--out` path confinement** (242 lines 419-434) — **copy verbatim** (V12 / path-traversal
control): reject `src/wanctl` targets, reject `..` components, `realpath -m` must stay inside
`ALLOWED_OUT_PREFIX`.

**Dirty-tree fail-closed gate** (242 lines 464-493) — **copy verbatim**: unstaged + staged +
untracked `src/wanctl/` all fail closed before any diff proof is accepted.

**Core boundary check** (242 lines 495-504) — keep but the disallowed set is *everything*:
```bash
CHANGED_PATHS="$(git diff --name-only "${ANCHOR_SHA}" HEAD -- src/wanctl/)"
# 243: ANY changed controller path is a violation (empty allowlist).
if [[ -n "${CHANGED_PATHS}" ]]; then
    echo "SAFE-17 VIOLATION: 243 is measurement-only; no src/wanctl edits permitted vs ${ANCHOR}" >&2
    printf '%s\n' "${CHANGED_PATHS}" >&2
    emit_evidence false -
    exit 1
fi
```

**`emit_evidence` python heredoc** (242 lines 58-209) — reuse the JSON-emit shape, **strip** the
`phase239/240/241` fields, `rtt_seam_*`, `reflector_scorer_unchanged`, `protected_body`,
`measure_rtt_fping_scorer_guard`. Keep: `anchor`, `anchor_sha`, `head_commit`, `changed_paths`,
`disallowed_paths`, `controller_path_diff_count`, `dirty_tree`, `dirty_tree_clean`, `passed`,
`checked_at`, `notes`. The evidence is written to `OUT` via `out.write_text(json.dumps(record,
indent=2, sort_keys=True) + "\n")`.

**`--self-test`** (242 lines 212-256) — **copy the mechanism verbatim**: `git worktree add
--detach` at HEAD, commit a disallowed `src/wanctl/queue_controller.py` edit, assert the
allowlist (now empty) trips, clean up, assert live tree not left dirty.

---

### `tests/test_phase243_safe17_verifier.py` (test, subprocess)

**Analog:** `tests/test_phase241_safe17_verifier.py`

**Anchor pin** (241 lines 22-25) — re-target to 243; **pin to the 243 close commit, NOT HEAD**:
```python
# Phase 243 close commit. Point-in-time gate; pin here so the test stays green
# as later phases (244+) legitimately change the controller.
PHASE_CLOSE_ANCHOR = "<243-CLOSE-SHA>"   # fill at phase close
```

**Detached-worktree fixture** (241 lines 50-61) — **copy verbatim** (`git worktree add --detach
... PHASE_CLOSE_ANCHOR`, teardown `git worktree remove --force`).

**`commit_worktree_change` helper** (241 lines 64-79) — **copy verbatim** (uses
`SKIP_DOC_CHECK=1` env so the pre-commit doc hook does not block the throwaway commit).

**Static contract test** (241 lines 82-111) — adapt assertions: assert
`"safe17-boundary-243.json" in text`, the 243 evidence prefix, `ANCHOR="fcc2e15b"` (242 close),
and that the script no longer references protected-body machinery (it's measurement-only). The
241 test asserts the allowlist regex contains each allowed basename; **243 asserts the empty-set
posture instead** — e.g. assert the violation message string for "no src/wanctl edits".

**Fail-mode tests** (241 lines 119-135) — keep `test_fails_on_out_of_allowlist_change` (edit ANY
`src/wanctl/*.py` → nonzero + violation message) and `test_fails_on_dirty_src_wanctl_change`
(uncommitted edit → "uncommitted, staged, or untracked src/wanctl/ edit"). **Drop**
`test_fails_on_protected_body_drift`, `test_fails_on_rtt_backend_drift_since_phase239`,
`test_reflector_scorer_edit_fails_closed` — those guard machinery 243 doesn't carry.

**`run()` subprocess helper** (241 lines 37-47) — **copy verbatim** (env-merge, `capture_output`,
`check=False`).

---

### `scripts/phase243-cycle-rollup.py` (rollup, NDJSON→stats)

**Analog:** `scripts/profiling_collector_json.py` (exact-match parser for the `"Cycle timing"`
schema) — **thin wrapper, not a rewrite.**

**NDJSON parse + label reconstruction** (collector lines 20-66) — reuse: filter
`record.get("message") == "Cycle timing"`, harvest every `*_ms` numeric key,
`canonical_label()` strips `_ms` → `autorate_*`. **`autorate_cycle_total` is the cycle-budget
metric and the n-floor source.**

**Percentile computation** (collector lines 26-42) — the collector's sorted-index
`calculate_statistics()` already yields `count`/`avg_ms`/`p50_ms`/`p95_ms`/`p99_ms`. For the
D-04c **n-floor**, read `count`. (If you prefer interpolated percentiles, import `percentile()`
from `soak_summary_aggregate.py:99` instead — stdlib, NumPy-free. Pick one and pin it.)

**Built-in validity guard** (collector lines 120-126) — **keep**: errors (exit 2) if no
`"Cycle timing"` records OR no `autorate_cycle_total` — a free proof the loop actually ran.

**NEW (243-only) addition — STALL gap detector** (Pattern 3 in RESEARCH): from consecutive
`"Cycle timing"` record `timestamp`s, compute `gap_ms = t[i] - t[i-1]`; emit
`stall_events = [g for g in gaps if g > 100.0]` into the per-arm profile JSON. This is the only
net-new logic; everything else is the collector.

**argparse shape** (collector lines 90-109) — copy: positional `input` (`-`/omitted = stdin),
`--output` (omitted = stdout), `main()` returns int exit code.

---

### `scripts/phase243-gate-eval.py` (gate evaluator, verdict)

**Analogs:** `scripts/phase206-gate-check.py` (delta-% + zero-baseline policy + fail-closed
exits) and `scripts/phase224-gate-eval.py` (per-gate dict + `outcome` + structured error class).

**Thresholds loaded from JSON, not literals** (206 lines 37-46) — **copy verbatim**; D-04
thresholds live ONLY in `phase243-thresholds.json`:
```python
def load_thresholds(path: Path | None = None) -> dict:
    target = path or (Path(__file__).resolve().parent / "phase243-thresholds.json")
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)
```

**Delta-% with zero-baseline guard** (206 lines 108, 122-143) — copy the pattern for each D-04
gate (`fping − icmplib` on the **same-run** arm; D-02 primary basis, NOT historical 2.85/6.9):
```python
pct = ((cur - pre) / pre) * 100.0 if pre > 0 else (0.0 if cur == 0 else float("inf"))
# avg_delta_pct <= 20 ; p99_delta_pct <= 20 ; fping.p99 < 10.0 (absolute ceiling)
# cpu_delta_pts < CPU_BOUND ; max(zombies)==0 ; fd no monotonic-upward ;
# max(tasks) <= baseline+TASKS_BOUND ; stall_events==0 ; count >= max(10000, cycles_30min)
```

**Per-gate verdict dict + outcome** (224 lines 73-81, 211-244) — copy `_gate(verdict, value,
**extra)` helper and the final scan: any `fail` → `rollback_trigger`; all pass → `pass`. Note:
**"keep icmplib" is a valid passing close** at the AB level (gate blocks only on *regression*).

**Structured fail-closed error + exit codes** (224 lines 25-31, 261-293; 206 lines 24-26) — copy
`GateEvalError` and `EXIT_PASS=0 / EXIT_BLOCK=1 / EXIT_ABORT=2`. **Fail closed on incomplete
arms** (missing `autorate_cycle_total`, n below D-04c floor) — must reject, not silently pass
(V5 control).

**JSON output** (224 lines 283-288) — write `243-BENCHMARK-VERDICT.json` via
`json.dumps(verdict, indent=2, sort_keys=True) + "\n"`; reference the frozen-thresholds commit
in the verdict so the gate can't be rationalized post-hoc.

---

### `scripts/phase243-thresholds.json` (config, frozen)

**Analog:** `scripts/phase206-thresholds.json`

**Shape** (206 thresholds, all 8 lines) — copy: `thresholds_schema_version`, numeric literals,
`_notes` single-source-of-truth rule. **Committed BEFORE any data** (BENCH-02). Suggested keys
(planner pre-commits exact figures, consistent with D-04):
```json
{
  "thresholds_schema_version": 1,
  "CYCLE_AVG_REGRESSION_PCT": 20.0,
  "CYCLE_P99_REGRESSION_PCT": 20.0,
  "CYCLE_P99_ABS_CEILING_MS": 10.0,
  "CPU_DELTA_PCT_POINTS": 2.0,
  "ZOMBIES_MAX": 0,
  "TASKS_BOUND": <n>,
  "STALL_GAP_MS": 100.0,
  "MIN_CYCLES": 10000,
  "MIN_MINUTES": 30,
  "ICMPLIB_REPRESENTATIVE_AVG_MS": 2.85,
  "ICMPLIB_REPRESENTATIVE_P99_MS": 6.9,
  "_notes": "BENCH-02 single source of truth. Committed BEFORE data collection. D-04/D-04a/D-04b/D-04c. Do not duplicate literals in markdown."
}
```

---

### `scripts/phase243-hygiene-sampler.sh` (soak sampler, NDJSON)

**Analog:** `scripts/soak-capture.sh`

**Env-driven + fail-closed validation** (soak-capture lines 23-44) — copy: `set -euo pipefail`,
required positional/env, numeric-range validation that aborts (exit 2) on bad input.

**1Hz NDJSON-per-tick loop with bounded failure tolerance** (soak-capture lines 61-161) — copy
the `while [ "$(date +%s)" -lt "$SOAK_END" ]; do ... sleep 1; done` skeleton plus the
`row_total`/`row_failed` + `SOAK_FAIL_RATE_THRESHOLD` bounded-failure gate. Replace the curl/jq
`/health` projection with `/proc` + `systemctl` sampling keyed on the unit MainPID (RESEARCH
Pattern 2):
```bash
PID=$(systemctl show -p MainPID --value "$BENCH_UNIT")
fd=$(ls /proc/$PID/fd | wc -l)
tasks=$(systemctl show -p TasksCurrent --value "$BENCH_UNIT")
# zombies: scan /proc/[0-9]*/stat for state Z whose PPID == $PID  (any Z = reaping bug = fail)
printf '{"t":%s,"fd":%s,"tasks":%s,"zombies":%s}\n' "$(date +%s)" "$fd" "$tasks" "$zombies" \
  >> "$CAPTURE_DIR/hygiene.ndjson"
```

**Trend test (consumed by gate-eval):** import `percentile` from `soak_summary_aggregate.py`;
"flat/bounded" = window-median fd not strictly increasing across windows; `max(zombies)==0`;
`max(tasks) <= baseline+bound` (RESEARCH Pattern 2).

---

### `scripts/phase243-bench-run.sh` (bench launcher, process orchestration)

**Analogs:** `scripts/soak-capture.sh` (env/loop/teardown discipline) + `src/wanctl/benchmark.py:424`
(flent invocation for the under-load arm). No exact single analog — role-match composite.

**Throwaway transient unit** (RESEARCH Pattern 1; D-01) — `systemd-run --unit=... --collect`,
`--setenv=WANCTL_LOG_FORMAT=json`, **NEVER `--pty`** (TTY defeats the STALL fingerprint):
```bash
sudo systemd-run --unit="wanctl-bench-${WAN}-${BACKEND}-${LOAD}" --collect \
  --setenv=WANCTL_LOG_FORMAT=json \
  /opt/wanctl/.venv/bin/python -m wanctl.autorate_continuous \
    --debug --config "/etc/wanctl/bench/${WAN}-bench-${BACKEND}.yaml"
# drain raw NDJSON → rollup:
journalctl -u "wanctl-bench-${WAN}-${BACKEND}-${LOAD}" -o cat --no-pager \
  | python3 scripts/phase243-cycle-rollup.py - --output evidence/${WAN}-${BACKEND}-${LOAD}.profile.json
```

**Under-load arm flent invocation** (benchmark.py lines 424-434) — reuse the established RRUL
path (D-03; no iperf): `flent rrul -H 104.200.21.31 -l <dur> -D <tmpdir>` source-bound to the WAN
IP. Spectrum + ATT both target the Dallas Linode (`104.200.21.31`).

**Collision avoidance (RESEARCH Pitfall 2):** bench config MUST use a unique unit name + health
port + `/run/wanctl` lock + state path so it never collides with live
`cake-autorate-{spectrum,att}-state-bridge` / steering. Preflight with `ss -ltnp`.

---

### `tests/test_phase243_{cycle_rollup,hygiene_sampler,gate_eval,prereg}.py` (tests)

**Analog:** pytest structure from `tests/test_phase241_safe17_verifier.py` (the `run()`
subprocess helper, fixture-driven, `capture_output`, `check=False`).

- **`test_phase243_cycle_rollup.py`** — feed a fixture `"Cycle timing"` NDJSON; assert
  `avg_ms`/`p99_ms` + the new stall-gap detector; assert the collector's no-`autorate_cycle_total`
  guard (exit 2) still fires.
- **`test_phase243_hygiene_sampler.py`** — assert well-formed `{t,fd,tasks,zombies}` NDJSON +
  the trend test (monotonic-upward fd rejected; nonzero zombie rejected).
- **`test_phase243_gate_eval.py`** — synthetic same-run arms: one **pass** fixture + one fixture
  per fail mode (avg/p99 delta, p99 ceiling, CPU, zombie, fd-trend, stall, n-floor). Mirrors the
  fail-mode coverage style of the 241 verifier test.
- **`test_phase243_prereg.py`** — presence/shape: `phase243-thresholds.json` + the prereg
  markdown exist and carry the D-04 keys (git-order discipline: committed before evidence).

---

## Shared Patterns

### SAFE-17 boundary discipline
**Source:** `scripts/phase242-safe17-boundary-check.sh` + `tests/test_phase241_safe17_verifier.py`
**Apply to:** the 243 verifier + its mirror test
- Fail-closed dirty-tree gate before any proof (242 lines 464-493).
- `--out` path confinement: no `src/wanctl`, no `..`, realpath inside evidence prefix (242
  lines 419-434).
- `--self-test` via detached worktree proving a committed disallowed edit trips the gate (242
  lines 212-256).
- **Mirror test pins worktree to PHASE_CLOSE_ANCHOR, never HEAD** (241 line 25; memory:
  boundary tests rot against HEAD).

### Pre-registered-threshold → verdict
**Source:** `scripts/phase206-gate-check.py` + `scripts/phase206-thresholds.json` +
`scripts/phase224-gate-eval.py`
**Apply to:** `phase243-gate-eval.py` + `phase243-thresholds.json`
- Thresholds in JSON only; `load_thresholds()` (206 lines 37-46). No literals in markdown.
- Zero-baseline delta-% policy (206 lines 108, 127-133).
- Structured fail-closed error + `EXIT_PASS/BLOCK/ABORT` (224 + 206); reject incomplete arms.
- Per-gate verdict dict + final outcome scan (224 lines 211-244).

### Stdlib NDJSON percentiles (no NumPy/pandas)
**Source:** `scripts/soak_summary_aggregate.py` (`percentile()` line 99, `histogram()` line 115)
and `scripts/profiling_collector_json.py` (`calculate_statistics()` line 26)
**Apply to:** `phase243-cycle-rollup.py`, the gate-eval fd-trend math, the hygiene trend test.

### NDJSON-per-tick soak loop with bounded failure tolerance
**Source:** `scripts/soak-capture.sh` (lines 23-161)
**Apply to:** `phase243-hygiene-sampler.sh` (and the bench-run drain/teardown discipline).

### Cycle-budget capture (read-only reuse — no controller edit)
**Source:** `src/wanctl/perf_profiler.py` (`record_cycle_profiling` → `"Cycle timing"` NDJSON,
avg/p95/p99) → `scripts/profiling_collector_json.py`
**Apply to:** every benchmark arm. `WANCTL_LOG_FORMAT=json` + `--debug` is the entire capture
mechanism. **Do NOT add a controller "observe mode"** — that is the SAFE-17 boundary expansion
this phase exists to avoid.

---

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `.planning/.../243-BENCHMARK-PREREGISTRATION.md` | doc (frozen gate) | No prior pre-registration markdown exists in `.planning/phases/` (verified: no `*PREREG*` match). It's a novel human-readable artifact. Mirror the single-source-of-truth discipline from `phase206-thresholds.json`'s `_notes`: the markdown narrates D-04 thresholds but the **numeric literals live only in `phase243-thresholds.json`** (no duplication). Must be committed before data collection (BENCH-02). |

---

## Metadata

**Analog search scope:** `scripts/` (gate/threshold/soak/profiling/benchmark), `tests/`
(SAFE-17 mirror tests), `src/wanctl/` (perf_profiler, benchmark, fping/rtt backends — read-only),
`.planning/phases/242-.../evidence/` (boundary evidence shape).
**Files read this session:** phase242 verifier, test_phase241 verifier,
profiling_collector_json.py, soak-capture.sh, soak_summary_aggregate.py, phase224-gate-eval.py,
phase206-gate-check.py, phase206-thresholds.json, benchmark.py (load-gen excerpt),
safe17-boundary-242.json (head).
**Pattern extraction date:** 2026-06-16
</content>
</invoke>
