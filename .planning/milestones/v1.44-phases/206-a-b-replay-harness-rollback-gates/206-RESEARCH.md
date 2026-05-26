# Phase 206: A/B replay harness + rollback gates — Research

**Researched:** 2026-05-14
**Domain:** Offline replay harness + machine-readable predeploy gate, wanctl scripts/tests only
**Confidence:** HIGH on prior-art reuse and SAFE-09 mechanics; MEDIUM on golden fixture provenance; LOW on whether the 2026-04-22 out-of-band flent artifact is actually recoverable verbatim
**No `src/wanctl/` edits expected.** Harness + script + fixture + tests + one rollback-criteria doc.

---

## Summary

Phase 206 is **scripts + tests + one operator-facing markdown**, no controller source diff. The Phase 193/194/195 replay pattern is alive, current, exercised by `tests/test_phase_205_*` style work, and is the right starting point — it's an **in-process Python harness** that drives `QueueController.adjust_4state` against a `CakeSignalSnapshot` trace and asserts byte-identical zone/rate output. Phase 206 extends that pattern from "single controller, classifier equivalence" to "two controller configs (pre/post `allow_wash` + besteffort) in one invocation, emit a structured A/B summary JSON, derive RRUL p99 latency / throughput / jitter from a committed deterministic fixture."

The predeploy gate has a clean precedent in `scripts/phase201-predeploy-gate.sh` (exit codes 0/1/2, `set -euo pipefail`, fail-closed, no auto-fix, local-override env var for tests). Reuse that skeleton verbatim.

**Two real research findings the planner must internalize:**

1. **The "2026-04-22 out-of-band flent finding" was not captured in `.planning/` at the time.** SEED-001 explicitly says "Out-of-band test details (date, flent profile, measured deltas) should be recovered from Kevin's test logs and added to the Phase 196 CONTEXT.md. If lost, Phase 196 must re-run the validation before landing." [VERIFIED: SEED-001-spectrum-topology-correct-cake-mode.md:77] The closest recoverable artifact is `/home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/` (a 920Mbit RRUL run, but 2026-04-29 not 2026-04-22). The phase must either (a) accept the 2026-04-29 920-besteffort artifact as the "spirit-of" baseline and document the substitution, or (b) re-run a fresh 920-besteffort flent capture before fixture-committing. Open Question 1.

2. **"Spectrum daemon restart-rate" and "pressure-state transition-rate per hour" are not first-class telemetry today.** [VERIFIED: grep `restart_rate|daemon_restart` across src/ scripts/ → 0 hits; grep `pressure_state` → 0 hits.] The closest existing signals are:
   - Restart-rate: derived from `journalctl -u wanctl@spectrum.service` (used by `scripts/soak-monitor.sh:144` via `journalctl ... -p err`). Restart events surface as `NStartLeaps`/start-stop pairs in journalctl, not as a counter in `/health`.
   - Pressure-state transitions: `_dl_zone_transitions` / `_ul_zone_transitions` deques exist in `wan_controller.py:728-729` but are internal flap-detector state, not exposed in `/health` or in soak NDJSON. The exposed proxy is `last_zone` + `zone_trace_tail` per-cycle in soak NDJSON, from which transitions are countable by adjacent-pair diff. [VERIFIED: soak-summary baseline `20260509T183037Z/soak-capture.ndjson` includes `last_zone` and `zone_trace_tail`.]

   The gate script must therefore derive both metrics from existing artifacts rather than invent telemetry: restart-rate from `journalctl --since` parsing, pressure-state transitions from adjacent-pair `last_zone` diffs in the post-deploy soak NDJSON. This is consistent with SAFE-09 (no controller source diff).

**Primary recommendation:** Build the harness as a single Python entry point (`scripts/phase206-ab-replay.py`) that loads one deterministic golden fixture (NDJSON of CAKE snapshots + RTT trace), runs `_replay()` twice (pre-config = diffserv4 nowash, post-config = besteffort wash via `allow_wash=True`), and writes `ab-summary.json` with a stable schema. Build the gate as a bash wrapper (`scripts/phase206-predeploy-gate.sh`) following the `phase201-predeploy-gate.sh` exit-code contract, calling a Python helper for the three threshold checks. Reuse Phase 201 fixture style (`tests/fixtures/phase206_replay_corpus.py` exporting deterministic `ReplaySample` records). Mechanical SAFE-09 check: `git diff 6508d68 --name-only -- src/wanctl/` returns exactly the Phase 205 5-file set — no new entries.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pre/post controller replay (zone, rate, p99 latency emission) | `tests/` + `scripts/` (offline Python harness) | — | Phase 193/194/195 pattern is `tests/test_phase_*_replay.py` driving `QueueController` directly. Phase 206 extends it into a script-callable harness so the same code path runs both as a pytest invariant and as an operator's CI step. No controller-tier work. |
| Golden fixture (CAKE snapshot trace + RTT trace) | `tests/fixtures/` | `.planning/phases/206-*/` (provenance markdown) | Reuse `tests/fixtures/phase201_replay_corpus.py` shape — module-level NDJSON loader returning frozen `ReplaySample` dataclasses. The flent `.flent.gz` raw stays outside `tests/` (it's ~MB binary); the **derived deterministic NDJSON** is the committed fixture. Provenance + parse pipeline live in `.planning/phases/206-*/`. |
| RRUL p99 latency / throughput / jitter extraction | `scripts/` Python helper | — | Reuse `phase198-rerun-flent-3run.sh`'s `extract_median()` shape (gzip+json+statistics, no external dep). Extend to p99 via `statistics.quantiles(method="exclusive", n=100)[-1]`. |
| A/B summary emission | `scripts/phase206-ab-replay.py` | — | One Python script writes one JSON file. Keep `schema_version: 1` top-level so Phase 209's canary consumer is a one-line `if schema_version == 1` gate. |
| Predeploy gate (3 rollback triggers) | `scripts/phase206-predeploy-gate.sh` (bash skeleton) + Python check helper | — | Bash skeleton mirrors `phase201-predeploy-gate.sh` for operator familiarity (same exit codes 0/1/2, same env-var local override). Python helper does the threshold math against baseline JSON. |
| Rollback criteria doc | `.planning/phases/206-*/PHASE-205-ROLLBACK-GATES.md` (per ROADMAP wording) | — | Operator-facing markdown, lives alongside the gate script. Single source of truth for the 3 thresholds. |
| SAFE-09 phase-boundary verification | `git diff 6508d68 --name-only -- src/wanctl/` | mechanical pytest hot-path slice | One git command run from the closeout plan. Already-precedented in Plan 205-04-PLAN Task 1 Step 2 — copy verbatim with new expected-set assertion (still 5 files; same Phase 205 set). |

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOPO-04 | A/B replay harness captures pre/post RRUL p99 latency, throughput, jitter against the 2026-04-22 out-of-band flent finding. Reuses the Phase 193/194/195 replay pattern; deterministic golden fixture committed. | §"Replay pattern reuse" + §"Deterministic golden fixture" sections below. Pattern from `tests/test_phase_193_replay.py` (in-process `QueueController.adjust_4state` loop) + flent `.flent.gz` parsing precedent from `scripts/phase198-rerun-flent-3run.sh:240-267` (`extract_median`). |
| TOPO-05 | Rollback criteria documented in machine-readable form (`PHASE-205-ROLLBACK-GATES.md` or equivalent): regression >5% on RRUL p99 latency OR Spectrum daemon restart-rate increase OR pressure-state transition-rate increase per hour. Predeploy gate script enforces. | §"Rollback gate inputs" + §"Gate script structure". Precedent: `scripts/phase201-predeploy-gate.sh` exit-code contract + `tests/test_phase201_predeploy_gate.py` shell-test scaffolding. |

---

## Standard Stack

### Core (already in repo — no installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest` | 9.0.2 [VERIFIED: `.venv/bin/pytest --version`] | Replay test runner | Every existing replay test (`test_phase_193_replay.py` etc.) uses pytest with class-based grouping. Same harness modules will export pytest classes AND a CLI entry point. |
| `wanctl.queue_controller.QueueController` | repo-local | Pre/post controller under test | This is the controller. The "pre" config is the same class with `allow_wash`-equivalent params off; "post" is the same class with the Phase 205 `allow_wash` gate effectively on. No controller-tier diff. |
| `wanctl.cake_signal.{CakeSignalSnapshot, TinSnapshot, CakeSignalProcessor}` | repo-local | Snapshot data classes consumed by the controller | Phase 193 replay constructs these directly with literal field values [VERIFIED: `tests/test_phase_193_replay.py:160-185`]. Reuse `_snap()` helper or import it. |
| Python stdlib `gzip` + `json` + `statistics` | 3.11+ | Parse `.flent.gz`, derive p99/median/jitter | Already used in `scripts/phase198-rerun-flent-3run.sh:240-267`. No `numpy` dep — Kevin keeps the wanctl runtime stdlib-only on purpose. |
| `bash` + `jq` + `python3` | system | Gate script skeleton | `phase201-predeploy-gate.sh` proves the pattern works without bash-isms beyond `set -euo pipefail`. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `journalctl` | systemd | Restart-event source for gate input | Gate script invokes `journalctl -u wanctl@spectrum.service --since "<baseline-start>" --output=json` and counts `_TRANSPORT=stdout` start events. Same SSH pattern as `scripts/soak-monitor.sh:144`. |
| `flent` 2.x | system | NOT a runtime dep — only the consumer of fixture provenance | The harness reads `.flent.gz` files but does not invoke flent itself. Live flent runs are operator-side (Phase 209 canary); Phase 206 harness is fully offline. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-process `QueueController` replay | Full subprocess `wanctl` invocation against a tap | Subprocess gives end-to-end coverage but introduces nondeterminism (clock, jitter, threading) — defeats "deterministic golden fixture". In-process replay is what Phases 193/194/195 chose and what made those phases mechanically verifiable. **Stay with in-process.** |
| Single combined script | Separate harness + gate | Separating them lets Phase 209's canary call the gate script standalone against `/etc/wanctl/soak-baseline.json` and a fresh post-deploy NDJSON, without re-running the offline replay. Stable contract for Phase 209. |
| `numpy` for p99 | Python `statistics.quantiles` | `statistics.quantiles(data, method="exclusive", n=100)[-1]` returns p99 with stdlib only. Avoid pulling numpy into the harness path. [CITED: https://docs.python.org/3/library/statistics.html#statistics.quantiles] |
| Pandas for NDJSON | Stdlib `json.loads` per line | Same: stdlib is sufficient and matches existing aggregator (`scripts/soak_summary_aggregate.py` uses plain json). |

**Installation:** none required. All deps are already in `.venv` or system. [VERIFIED: `/usr/bin/flent` `/usr/bin/jq` present; pytest 9.0.2 in venv.]

---

## Architecture Patterns

### System Architecture Diagram

```
                  ┌─────────────────────────────────────┐
                  │   Phase 193/194/195 prior art       │
                  │   tests/test_phase_*_replay.py      │
                  │   • literal CakeSignalSnapshot()    │
                  │   • driven by _replay()             │
                  │   • assert byte-identical zones     │
                  └────────────────┬────────────────────┘
                                   │ reuse pattern
                                   ▼
┌─────────────────────────────────────────────────────────────┐
│   COMMITTED GOLDEN FIXTURE                                  │
│   tests/fixtures/phase206_replay_corpus.py                  │
│   • ReplaySample(ts, cake_snap_dict, rtt_pair, ...)         │
│   • Loads phase206_golden_capture.ndjson (provenance noted) │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│   HARNESS: scripts/phase206-ab-replay.py                             │
│                                                                      │
│   ┌───────────────────────┐     ┌───────────────────────┐            │
│   │  PRE-config replay    │     │  POST-config replay   │            │
│   │  diffserv4 / nowash   │     │  besteffort / wash    │            │
│   │  QueueController(A)   │     │  QueueController(B)   │            │
│   │  + CakeSignalProcessor│     │  + CakeSignalProcessor│            │
│   └──────────┬────────────┘     └──────────┬────────────┘            │
│              │                              │                        │
│              ▼                              ▼                        │
│   ┌──────────────────────────────────────────────┐                   │
│   │   FLENT METRIC EXTRACTOR                     │                   │
│   │   • RRUL p99 latency_ms (Ping.* series)      │                   │
│   │   • throughput_mbps (TCP download SUM)       │                   │
│   │   • jitter_ms (latency p99 - p50)            │                   │
│   └────────────────┬─────────────────────────────┘                   │
│                    ▼                                                 │
│   ┌──────────────────────────────────────────────┐                   │
│   │   AB SUMMARY EMITTER                         │                   │
│   │   schema_version: 1                          │                   │
│   │   { pre: {…}, post: {…}, delta: {…},         │                   │
│   │     gates: {rrul_p99_pct, …}, meta: {…} }    │                   │
│   └────────────────┬─────────────────────────────┘                   │
└────────────────────┼─────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────────────┐
        │   ab-summary.json                  │
        │   (committed for v1.43 baseline)   │
        └─────────────┬──────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────────────────┐
   │   GATE: scripts/phase206-predeploy-gate.sh              │
   │   exit 0  PASS  — all three thresholds clear            │
   │   exit 1  BLOCK — at least one threshold breached       │
   │   exit 2  ABORT — missing input, malformed env, etc.    │
   │                                                         │
   │   Inputs:                                               │
   │     --baseline <ab-summary.json>                        │
   │     --candidate <ab-summary.json or NDJSON>             │
   │     --journal-since <ISO8601>  (for restart-rate)       │
   │     --ssh-target <host>        (for journalctl)         │
   │                                                         │
   │   Checks (calls Python helper):                         │
   │     1. RRUL p99 latency regression > 5% → BLOCK         │
   │     2. Restart-rate (per hour) increased → BLOCK        │
   │     3. Pressure-state transitions/hour increased → BLOCK│
   └─────────────────────────────────────────────────────────┘
                      │
                      ▼
   ┌──────────────────────────────────────────┐
   │   Operator dry-run on v1.43 baseline:    │
   │   gate --baseline X --candidate X        │
   │   exits 0 by construction (X vs X = 0%)  │
   └──────────────────────────────────────────┘
```

### Recommended Project Structure

```
.planning/phases/206-a-b-replay-harness-rollback-gates/
├── 206-RESEARCH.md                       # (this file)
├── 206-PLAN.md (or 206-NN-PLAN.md split) # planner writes
├── 206-*-SUMMARY.md                      # post-execution
├── 206-VALIDATION.md                     # Per-Task Verification Map
├── 206-VERIFICATION.md                   # closeout
├── PHASE-205-ROLLBACK-GATES.md           # the TOPO-05 operator-facing doc
└── golden-fixture-provenance.md          # what the fixture came from + how to re-derive

tests/
├── test_phase_206_replay.py              # the A/B replay pytest entry
├── test_phase206_predeploy_gate.py       # shell + python gate tests
└── fixtures/
    ├── phase206_replay_corpus.py         # NDJSON loader + ReplaySample
    └── phase206_golden_capture.ndjson    # COMMITTED deterministic trace

scripts/
├── phase206-ab-replay.py                 # harness entry point (CLI + importable)
├── phase206-predeploy-gate.sh            # bash skeleton (exit 0/1/2)
└── phase206-gate-check.py                # python helper called by the bash gate
```

### Pattern 1: In-process replay (lifted verbatim from Phase 193)

**What:** Drive `QueueController.adjust_4state(...)` in a Python loop against literal `CakeSignalSnapshot` snapshots and a list of `(baseline_rtt, load_rtt)` tuples. Assert zone/rate sequences match committed `EXPECTED_*` lists.

**When to use:** Every Phase 206 replay test. Same loop, two configs.

**Example:**
```python
# Source: tests/test_phase_193_replay.py:188-204 (already in repo)
def _replay(controller, trace, snapshot):
    zones, rates = [], []
    for baseline_rtt, load_rtt in trace:
        zone, rate, _ = controller.adjust_4state(
            baseline_rtt=baseline_rtt,
            load_rtt=load_rtt,
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
            cake_snapshot=snapshot,
        )
        zones.append(zone)
        rates.append(rate)
    return zones, rates
```

Phase 206 calls `_replay()` twice — once with a controller built from the pre-config (diffserv4, nowash, 940 ceiling) and once from the post-config (besteffort, wash, 920 ceiling). The CakeSignalSnapshot trace differs between runs only in `tins` count (4 vs 1) since the same kernel-level queue inputs feed both.

### Pattern 2: Predeploy gate exit-code contract (from Phase 201)

**What:** Bash script with three exit codes and operator-actionable messages.

**When to use:** TOPO-05 predeploy gate must follow this contract exactly so operators don't have to learn a new failure semantics.

**Example:**
```bash
# Source: scripts/phase201-predeploy-gate.sh:25-33 (verbatim — REUSE)
set -euo pipefail
EXIT_PASS=0     # all thresholds clear
EXIT_BLOCK=1    # one or more thresholds breached, operator must reconcile
EXIT_ABORT=2    # missing deps, SSH fail, parse error, malformed env
log_info()  { printf '[predeploy-gate INFO]  %s\n' "$*" >&2; }
log_block() { printf '[predeploy-gate BLOCK] %s\n' "$*" >&2; printf '%s\n' "$*"; }
log_abort() { printf '[predeploy-gate ABORT] %s\n' "$*" >&2; }
```

Plus the test-side env-var override [VERIFIED: `scripts/phase201-predeploy-gate.sh:22-23, 43-49`]:
```bash
if [[ -n "${PHASE206_LOCAL_BASELINE_OVERRIDE:-}" ]]; then ...
```
…which makes `tests/test_phase206_predeploy_gate.py` runnable without SSH.

### Pattern 3: Stable A/B summary JSON schema

**What:** Top-level `schema_version`, parallel `pre`/`post` blocks, computed `delta`, computed `gates`, separate `meta`. Designed so the Phase 209 canary comparator is a one-line consumer change (just read a different file path).

**When to use:** The harness's only JSON output. Both the v1.43 baseline A/B summary AND post-canary candidate A/B summary use this exact schema.

**Example:**
```json
{
  "schema_version": 1,
  "phase": 206,
  "fixture_provenance": "tests/fixtures/phase206_golden_capture.ndjson",
  "fixture_sha256": "<sha>",
  "meta": {
    "generated_at_utc": "2026-05-15T14:32:11Z",
    "head_sha": "cb1ff9f",
    "phase_205_close_sha": "<TBD>",
    "tool_version": "phase206-ab-replay/1.0"
  },
  "pre": {
    "config": {"ceiling_mbps": 940, "diffserv": "diffserv4", "allow_wash": false},
    "rrul_p99_latency_ms": 42.7,
    "throughput_mbps": 591.3,
    "jitter_ms": 8.4,
    "zone_distribution": {"GREEN": 1840, "YELLOW": 120, "SOFT_RED": 30, "RED": 10},
    "rate_apply_count": 47
  },
  "post": {
    "config": {"ceiling_mbps": 920, "diffserv": "besteffort", "allow_wash": true},
    "rrul_p99_latency_ms": 18.9,
    "throughput_mbps": 905.1,
    "jitter_ms": 3.1,
    "zone_distribution": {"GREEN": 1960, "YELLOW": 35, "SOFT_RED": 5, "RED": 0},
    "rate_apply_count": 22
  },
  "delta": {
    "rrul_p99_latency_ms": -23.8,
    "rrul_p99_latency_pct": -55.7,
    "throughput_mbps": 313.8,
    "throughput_pct": 53.1,
    "jitter_ms": -5.3
  },
  "gates": {
    "rrul_p99_latency_regression_pct_threshold": 5.0,
    "rrul_p99_latency_regression_pct_actual": -55.7,
    "rrul_p99_latency_breach": false
  }
}
```

**Schema-stability rationale:** Phase 209's canary diff compares two of these JSONs (the baseline committed during 206 vs a fresh capture). Adding fields is backward-compatible. Renaming or moving keys is not — so all field names and nesting must be locked here. `schema_version: 1` is the explicit forward signal; Phase 209 reads it and refuses unknown versions.

### Anti-Patterns to Avoid

- **Don't invent new `/health` fields for restart-rate or pressure-state-transitions.** That would be a `src/wanctl/` source diff = SAFE-09 (behavioral) violation. Derive both metrics in the gate script from existing artifacts (journalctl, soak NDJSON `last_zone` adjacency).
- **Don't run flent live from the harness.** Flent is operator-side, Phase 209. Phase 206 harness reads pre-captured `.flent.gz` provenance OR a pure NDJSON-derived synthetic trace. If you call flent from the script, the result is no longer deterministic and "golden fixture" loses meaning.
- **Don't pull in numpy / pandas / scipy.** wanctl is stdlib-only by Kevin's preference. `statistics.quantiles(data, n=100, method="exclusive")[-1]` gives p99.
- **Don't shell out to `git diff` inside the harness.** The SAFE-09 check belongs in the closeout plan (mechanical, one bash line), not inside the runtime harness.
- **Don't commit the raw `.flent.gz` file in `tests/fixtures/`.** It's ~MB, opaque, and version-control unfriendly. Commit a derived deterministic NDJSON (RTT trace + CAKE snapshot trace), with provenance pointing to the `.flent.gz` in `/home/kevin/flent-results/`. Phase 201 did exactly this [VERIFIED: `tests/fixtures/phase201_replay_corpus.py:17-21`].

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Replay loop | New `Trace` / `Replayer` class | `_replay()` and `_snap()` from `tests/test_phase_193_replay.py` | Already tested in production by 193/194/195 + 197 + 201 + 202 + 203 + 204 replay tests. Re-implementation = behavior drift risk. |
| Flent .gz parsing | Custom container reader | `extract_median()` pattern in `scripts/phase198-rerun-flent-3run.sh:240-267` (gzip + json.load) | Stdlib only. Extend to p99 by walking `results["Ping (ms) ICMP"]` (or "TCP totals") through `statistics.quantiles`. |
| Bash gate skeleton | New exit-code convention | `phase201-predeploy-gate.sh` template (exit 0/1/2, env override, log_info/log_block/log_abort) | Operators already know this contract. |
| NDJSON fixture loader | Generic NDJSON util | `tests/fixtures/phase201_replay_corpus.py` ReplaySample dataclass + per-line parser | Frozen dataclasses avoid mutation surprises across two replay runs. |
| Soak NDJSON `last_zone` extraction | Bespoke parser | `jq -r '.last_zone'` per line + Python adjacency diff | The v1.43 baseline soak already has `last_zone` and `zone_trace_tail` per row [VERIFIED: `20260509T183037Z/soak-capture.ndjson`]. |
| journalctl restart-event counting | journalctl wrapper class | The `--output=json` form + Python loop counting `MESSAGE` matches OR the `_PID` start-of-unit boundary (NStarts via `systemctl show -p NRestarts`) | `scripts/soak-monitor.sh:132-146` shows the established ssh+journalctl pattern. `systemctl show -p NRestarts wanctl@spectrum.service` returns a cumulative integer — diff it across two timestamps for rate. |

**Key insight:** Phase 206 is mostly *plumbing already-tested components together in a new script*. The biggest implementation risk is reinventing infrastructure that's already proven. Lean on the prior-art tightly.

---

## Common Pitfalls

### Pitfall 1: Treating the 2026-04-22 flent finding as committed-and-immutable

**What goes wrong:** Plan assumes a `.flent.gz` from 2026-04-22 exists in `.planning/` and just needs to be referenced. It does not.
**Why it happens:** The phase wording says "2026-04-22 out-of-band flent finding" as if it were a captured artifact. It isn't — it surfaced retroactively on 2026-04-24 and was never committed [VERIFIED: SEED-001:17 "The result wasn't captured in `.planning/` at the time — it surfaced on 2026-04-24 during Phase 195 planning when Kevin recalled the finding."]
**How to avoid:** Treat fixture provenance as an explicit Plan 0 task. Either (a) accept the 2026-04-29 `cake-shaper-920-rrul-20260429-231547` artifact as the closest recoverable shape and document the substitution, or (b) operator runs a fresh 920-besteffort flent before Phase 206 source code lands. Open Question 1.
**Warning signs:** Plan references "the 2026-04-22 fixture" without a `find / -path "*2026-04-22*flent*"` result attached.

### Pitfall 2: Phase 209 canary comparator needs >1-line change because schema drifts

**What goes wrong:** Phase 206 lands `pre`/`post` keys at top level. Phase 209 reads the baseline summary, then realizes it wants `pre_canary` / `post_canary` for clarity, renames, breaks compatibility with the committed v1.43 baseline.
**Why it happens:** Schema designed without the Phase 209 consumer in mind.
**How to avoid:** The schema in §"Pattern 3" is designed for Phase 209 to consume directly. The Phase 209 canary writes a *second* file with the same schema; comparison is `delta(baseline.json, canary.json)`. Both files have identical shape. If Phase 209 needs anything more, add it as a new optional key — never rename.
**Warning signs:** Plan proposes "we'll refactor the schema in Phase 209."

### Pitfall 3: Gate script counts wrong direction of zone transition

**What goes wrong:** Gate counts every zone change (GREEN→YELLOW and YELLOW→GREEN both count), making a stable controller look noisy.
**Why it happens:** Ambiguity in "pressure-state transition" — is it any edge, or only pressure-increasing edges (GREEN→YELLOW, YELLOW→SOFT_RED, SOFT_RED→RED)?
**How to avoid:** Define explicitly in `PHASE-205-ROLLBACK-GATES.md`. Recommend: count **distinct adjacent zone changes** (any edge), then normalize per hour. Healthy idle has ~0 transitions/hour; loaded has tens. The "increase" check is *relative to v1.43 baseline soak's transition-rate-per-hour*, not an absolute threshold. Document the formula and the baseline value (computable from `20260509T183037Z/soak-capture.ndjson`).
**Warning signs:** Plan says "transitions" without specifying which edges count.

### Pitfall 4: Restart-rate baseline poisoned by the deploy itself

**What goes wrong:** Operator deploys, wanctl restarts once (intentionally), then the post-deploy 24h window counts 1 restart vs baseline 0 — gate trips.
**Why it happens:** Naive restart-rate = `(count_after - count_before) / hours_elapsed`.
**How to avoid:** Restart-rate window must START at `deploy_complete_timestamp + grace_period` (e.g., 5 min), not at deploy time. Document this in the gate doc. Implementation: `--journal-since <ISO8601>` with the operator passing the post-deploy stabilization marker.
**Warning signs:** Gate fails on first-canary dry-run against a deployment that didn't actually misbehave.

### Pitfall 5: Phase 205's "5-file allowlist" silently grows to 6

**What goes wrong:** Phase 206 author adds a helpful function to `src/wanctl/operator_summary.py` (to expose `pressure_state_transitions_per_hour`), thinking it's "non-controller". SAFE-09 closeout fails Phase 209.
**Why it happens:** SAFE-09 (behavioral) is bounded by file allowlist; even non-controller files count as src/wanctl/ diffs.
**How to avoid:** Hard rule for Phase 206 closeout: `git diff 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l` returns **5** (the unchanged Phase 205 set: `cake_signal.py`, `cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py`). Any 6th entry = SAFE-09 boundary breach.
**Warning signs:** Plan proposes "let's expose this as a metric." Push back: derive it in the script.

### Pitfall 6: jitter definition disagreement between pre and post

**What goes wrong:** Pre-config jitter computed as latency-stdev; post-config jitter computed as p99-p50. Numbers aren't comparable.
**Why it happens:** Two different intuitive definitions of "jitter".
**How to avoid:** Lock the formula in PHASE-205-ROLLBACK-GATES.md. Recommend: `jitter_ms = p99_latency_ms - p50_latency_ms` (Bufferbloat / RPM project convention). Apply identically to both pre and post.
**Warning signs:** Two different `compute_jitter()` helpers in the harness.

---

## Code Examples

### Loading a deterministic NDJSON fixture (Phase 201 pattern, adapted)

```python
# Source: tests/fixtures/phase201_replay_corpus.py (adapted)
from dataclasses import dataclass
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_NDJSON = Path(__file__).resolve().parent / "phase206_golden_capture.ndjson"

@dataclass(frozen=True)
class GoldenSample:
    ts: str
    baseline_rtt_ms: float
    load_rtt_ms: float
    cake_avg_delay_us: int
    cake_base_delay_us: int
    # ... only fields the replay needs

def load_golden() -> list[GoldenSample]:
    out = []
    for raw in GOLDEN_NDJSON.read_text(encoding="utf-8").splitlines():
        if not raw.strip(): continue
        obj = json.loads(raw)
        out.append(GoldenSample(
            ts=obj["ts"],
            baseline_rtt_ms=obj["baseline_rtt_ms"],
            load_rtt_ms=obj["load_rtt_ms"],
            cake_avg_delay_us=obj["cake_avg_delay_us"],
            cake_base_delay_us=obj["cake_base_delay_us"],
        ))
    return out
```

### A/B harness skeleton (drives QueueController twice)

```python
# scripts/phase206-ab-replay.py (sketch)
import json, statistics, sys
from pathlib import Path
from wanctl.cake_signal import CakeSignalSnapshot, TinSnapshot
from wanctl.queue_controller import QueueController
from tests.fixtures.phase206_replay_corpus import load_golden

SCHEMA_VERSION = 1

def _controller(ceiling_bps: int) -> QueueController:
    # Reuse the Phase 193 spectrum factory shape verbatim, only ceiling varies
    return QueueController(
        name="download",
        floor_green=800_000_000, floor_yellow=600_000_000,
        floor_soft_red=500_000_000, floor_red=400_000_000,
        ceiling=ceiling_bps,
        step_up=10_000_000, factor_down=0.85, factor_down_yellow=0.96,
        green_required=5, dwell_cycles=2, deadband_ms=0.0,
    )

def _snap_for(sample, tin_layout: str) -> CakeSignalSnapshot:
    # diffserv4 → 4 tins (Bulk/BestEffort/Video/Voice); besteffort → 1 tin
    tin_count = 4 if tin_layout == "diffserv4" else 1
    tins = tuple(TinSnapshot(name="BestEffort" if tin_layout=="besteffort" else f"T{i}",
                              dropped_packets=0, drop_delta=0, backlog_bytes=0,
                              peak_delay_us=0, ecn_marked_packets=0,
                              avg_delay_us=sample.cake_avg_delay_us,
                              base_delay_us=sample.cake_base_delay_us,
                              delay_delta_us=max(0, sample.cake_avg_delay_us - sample.cake_base_delay_us))
                  for i in range(tin_count))
    return CakeSignalSnapshot(
        drop_rate=0.0, total_drop_rate=0.0, backlog_bytes=0, peak_delay_us=0,
        tins=tins, cold_start=False,
        avg_delay_us=sample.cake_avg_delay_us, base_delay_us=sample.cake_base_delay_us,
        max_delay_delta_us=max(0, sample.cake_avg_delay_us - sample.cake_base_delay_us),
    )

def _replay(ctrl: QueueController, samples, tin_layout: str) -> tuple[list[str], list[int]]:
    zones, rates = [], []
    for s in samples:
        snap = _snap_for(s, tin_layout)
        zone, rate, _ = ctrl.adjust_4state(
            baseline_rtt=s.baseline_rtt_ms, load_rtt=s.load_rtt_ms,
            green_threshold=15.0, soft_red_threshold=45.0, hard_red_threshold=80.0,
            cake_snapshot=snap,
        )
        zones.append(zone); rates.append(rate)
    return zones, rates

def _latency_p99_p50(rrul_flent_gz: Path) -> tuple[float, float]:
    import gzip
    with gzip.open(rrul_flent_gz, "rt") as fh:
        data = json.load(fh)
    pings = [v for v in (data["results"].get("Ping (ms) ICMP") or []) if isinstance(v, (int, float))]
    qs = statistics.quantiles(pings, n=100, method="exclusive")
    return qs[98], qs[49]  # p99, p50

def main():
    samples = load_golden()
    pre_zones, pre_rates = _replay(_controller(940_000_000), samples, tin_layout="diffserv4")
    post_zones, post_rates = _replay(_controller(920_000_000), samples, tin_layout="besteffort")
    # ... compute zone_distribution, throughput from rates, jitter from latency provenance ...
    summary = {
        "schema_version": SCHEMA_VERSION, "phase": 206,
        "pre": {...}, "post": {...}, "delta": {...}, "gates": {...}, "meta": {...},
    }
    print(json.dumps(summary, indent=2))
```

### Gate script — Python helper (called from bash skeleton)

```python
# scripts/phase206-gate-check.py (sketch)
import argparse, json, subprocess, sys, statistics

EXIT_PASS, EXIT_BLOCK, EXIT_ABORT = 0, 1, 2

def check_rrul_p99(baseline: dict, candidate: dict, threshold_pct: float) -> tuple[bool, str]:
    pre = baseline["post"]["rrul_p99_latency_ms"]   # the v1.43 baseline IS the "post" of the captured A/B
    cur = candidate["post"]["rrul_p99_latency_ms"]
    pct = ((cur - pre) / pre) * 100.0 if pre > 0 else 0.0
    if pct > threshold_pct:
        return False, f"RRUL p99 latency regression: baseline={pre:.2f}ms current={cur:.2f}ms delta=+{pct:.1f}% > {threshold_pct}%"
    return True, f"RRUL p99 latency: {pct:+.1f}% (within ±{threshold_pct}%)"

def check_restart_rate(ssh_target: str, since: str, baseline_rate_per_hour: float) -> tuple[bool, str]:
    # systemctl show -p NRestarts wanctl@spectrum.service over the window
    # OR journalctl --output=json --since="$since" and count start-of-unit events
    ...

def check_zone_transitions(soak_ndjson: str, baseline_rate_per_hour: float) -> tuple[bool, str]:
    rates_per_hour = 0
    prev = None; hours_observed = 0.0
    with open(soak_ndjson) as fh:
        for line in fh:
            obj = json.loads(line)
            cur = obj.get("last_zone")
            if prev is not None and cur != prev:
                rates_per_hour += 1
            prev = cur
            hours_observed = (obj["t_monotonic"]) / 3600.0
    actual = rates_per_hour / max(hours_observed, 1e-9)
    if actual > baseline_rate_per_hour:
        return False, f"Zone-transition rate: baseline={baseline_rate_per_hour:.2f}/h current={actual:.2f}/h"
    return True, f"Zone-transition rate: {actual:.2f}/h (baseline {baseline_rate_per_hour:.2f}/h)"
```

---

## Runtime State Inventory

> Phase 206 is greenfield script/test work. No runtime state is renamed, no service configuration changes, no stored data is migrated. This section intentionally short.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 206 reads existing soak NDJSON, never writes runtime state | None |
| Live service config | None — gate script is operator-invoked, not a daemon | None |
| OS-registered state | None — no systemd unit changes; `wanctl@spectrum.service` remains as-is | None |
| Secrets / env vars | New env var `PHASE206_LOCAL_BASELINE_OVERRIDE` for tests (test-only, no production secret) | Document in script header |
| Build artifacts | None — pure Python + bash; no compiled output | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Harness + gate helper | ✓ | 3.11+ (venv) | — |
| pytest | Replay test execution | ✓ | 9.0.2 [VERIFIED] | — |
| `jq` | Gate script JSON parsing | ✓ | system | — |
| `bash` (POSIX) | Gate script | ✓ | system | — |
| `flent` | Live capture (Phase 209 only — not 206) | ✓ | system | Phase 206 doesn't invoke flent |
| `ssh` to cake-shaper | Gate script restart-rate check | ✓ in operator env; ✗ in test env | — | Test mode via `PHASE206_LOCAL_BASELINE_OVERRIDE` env override (Phase 201 pattern) |
| `journalctl` on cake-shaper | Restart-rate measurement | ✓ on remote | systemd | Test mode mocks this |
| `systemctl show -p NRestarts` on cake-shaper | Alternative restart counter | ✓ | systemd | Same as above |
| Existing v1.43 baseline soak NDJSON | Pressure-state baseline-rate-per-hour computation | ✓ at `.planning/milestones/v1.43-phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson` [VERIFIED] | — | — |
| The 2026-04-22 flent finding artifact | Golden fixture provenance | ✗ NOT FOUND in `.planning/` | — | Use 2026-04-29 `cake-shaper-920-rrul-20260429-231547` as closest substitute, OR have operator re-run a fresh 920-besteffort flent before fixture commit |

**Missing dependencies with no fallback:** None — every required tool is present.

**Missing dependencies with fallback:** The "2026-04-22 finding" must be substituted or re-derived. Open Question 1.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 [VERIFIED] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (lines 151-153) |
| Quick run command | `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_predeploy_gate.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |
| Hot-path slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` (per CLAUDE.md) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOPO-04 | Harness emits A/B summary with pre/post p99 latency, throughput, jitter | unit + integration | `.venv/bin/pytest tests/test_phase_206_replay.py::TestAbSummaryEmission -v` | ❌ Wave 0 |
| TOPO-04 | Harness reuses Phase 193/194/195 `_replay` shape (no parallel reimplementation) | unit (import-only) | `.venv/bin/pytest tests/test_phase_206_replay.py::TestPattern193Reuse -v` | ❌ Wave 0 |
| TOPO-04 | Golden fixture is deterministic (loads same `ReplaySample` list across runs) | unit | `.venv/bin/pytest tests/test_phase_206_replay.py::TestGoldenFixtureDeterminism -v` | ❌ Wave 0 |
| TOPO-04 | Schema version 1 is stable (key set matches frozen snapshot) | unit | `.venv/bin/pytest tests/test_phase_206_replay.py::TestSchemaV1Stability -v` | ❌ Wave 0 |
| TOPO-05 | Gate exits 0 when candidate == baseline (operator dry-run on v1.43 baseline) | shell-integration | `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestGateDryRun -v` | ❌ Wave 0 |
| TOPO-05 | Gate exits 1 when RRUL p99 regression > 5% | shell-integration | `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestRrulP99Block -v` | ❌ Wave 0 |
| TOPO-05 | Gate exits 1 when restart-rate increased | shell-integration | `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestRestartRateBlock -v` | ❌ Wave 0 |
| TOPO-05 | Gate exits 1 when pressure-state transition-rate increased | shell-integration | `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestTransitionRateBlock -v` | ❌ Wave 0 |
| TOPO-05 | Gate exits 2 on missing input / malformed env | shell-integration | `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestGateAbort -v` | ❌ Wave 0 |
| SAFE-09 boundary | `git diff 6508d68 --name-only -- src/wanctl/` returns exactly the Phase 205 5-file set | mechanical | `[[ $(git diff 6508d68 --name-only -- src/wanctl/ \| sort -u \| wc -l) -eq 5 ]]` | ✓ (in Plan-04 closeout pattern) |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_predeploy_gate.py -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -q` (full suite — must include Phase 193/194/195 replay byte-identity, must still pass)
- **Phase gate:** Full suite green + hot-path slice green + SAFE-09 boundary diff = exactly 5 files + harness end-to-end run against committed fixture produces a stable `ab-summary.json` whose sha matches a committed expected hash.

### Wave 0 Gaps

- [ ] `tests/test_phase_206_replay.py` — pytest entry for TOPO-04 behaviors
- [ ] `tests/test_phase206_predeploy_gate.py` — shell-integration entry for TOPO-05 (model on `tests/test_phase201_predeploy_gate.py`)
- [ ] `tests/fixtures/phase206_replay_corpus.py` — loader for the deterministic golden fixture
- [ ] `tests/fixtures/phase206_golden_capture.ndjson` — the fixture itself; provenance traced to `cake-shaper-920-rrul-20260429-231547` OR a fresh re-run (resolved by Open Question 1)
- [ ] `scripts/phase206-ab-replay.py` — the harness
- [ ] `scripts/phase206-predeploy-gate.sh` — the bash gate skeleton
- [ ] `scripts/phase206-gate-check.py` — Python helper called from the bash gate
- [ ] `.planning/phases/206-a-b-replay-harness-rollback-gates/PHASE-205-ROLLBACK-GATES.md` — operator-facing 3-trigger doc
- [ ] `.planning/phases/206-a-b-replay-harness-rollback-gates/golden-fixture-provenance.md` — fixture origin + re-derivation steps

No framework install needed.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Gate runs locally or via existing SSH key auth to cake-shaper; no new auth path |
| V3 Session Management | no | No session state |
| V4 Access Control | yes (minimal) | Gate script's `--ssh-target` parameter must validate against same safe-path regex as `phase201-predeploy-gate.sh:36-39` to prevent command injection via env vars |
| V5 Input Validation | yes | Gate script must validate `--baseline` and `--candidate` paths exist and parse as JSON before threshold checks. Reject paths with shell metacharacters. |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns for bash+Python gate script

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection via `--ssh-target` env var | Tampering | Regex-validate the hostname (alphanumeric + dot + hyphen). Same pattern as `phase201-predeploy-gate.sh:36`. |
| Path traversal via `--baseline` or `--candidate` | Tampering | `Path.resolve()` and require the file to exist and be a regular file before reading. |
| YAML/JSON deserialization | Tampering | Use `json.load` (not `pickle` or `yaml.unsafe_load`). Phase 201 uses `yaml.safe_load`; we use `json.load` exclusively since A/B summaries are JSON not YAML. |
| `journalctl` output spoofing | Information Disclosure | Run journalctl over SSH with `BatchMode=yes`, `--output=json`, and parse line-by-line; never `eval` output. |

This is a low-security-surface phase — no new auth, no new network listener, no new persistence. The threat model is narrower than Phase 201's was.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-phase ad-hoc replay tests with different shapes | Shared `_replay()` + `_snap()` helpers, imported across replays | Phase 193 → onward [VERIFIED: `tests/test_phase_195_replay.py:34-42` imports from `test_phase_193_replay`] | Phase 206 imports the same helpers — no parallel implementation. |
| Live-router rerun for every soak comparison | Mix of live-rerun (Phase 198) + in-process replay (Phase 193/194/195) + corpus-fixture replay (Phase 201) | Phase 201 → onward | Phase 206 uses the corpus-fixture pattern (newest, most deterministic). |
| `secondary_gate_legacy` dual emission | `secondary_gate_completed_window` single source of truth | Phase 202/203/204 (v1.43) [VERIFIED: ROADMAP Phase 207 HRDN-03 retires the legacy block] | Don't introduce a new dual-emission. Single schema, single gate. |

**Deprecated / outdated:**
- Don't take patterns from Phase 191/192 ad-hoc harnesses — those predate the consolidated Phase 193 `_replay` shape.
- Don't take the Phase 198 live-rerun shape (`phase198-rerun-flent-3run.sh`) as a model — it's a separate kind of harness (live, off-peak-gated, three flent runs). Phase 206 is offline replay.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The "2026-04-22 out-of-band flent finding" artifact is not recoverable verbatim and must be substituted with the 2026-04-29 `cake-shaper-920-rrul-20260429-231547` capture OR a fresh re-run before Phase 206 source code lands. | Summary §2; Pitfall 1; Open Question 1 | HIGH — the fixture provenance is the entire "deterministic golden fixture committed" requirement of TOPO-04. Wrong substitute = wrong baseline = wrong gates. **Operator confirmation required before planning.** |
| A2 | "Pressure-state transitions" means "any adjacent zone change" (GREEN↔YELLOW, etc.), counted from `last_zone` per-cycle NDJSON values, normalized per hour. | Pitfall 3 | MEDIUM — gate threshold semantics. If Kevin means "RED-ward only" or "stalls in RED" instead, the gate counts the wrong thing. **Clarify before locking PHASE-205-ROLLBACK-GATES.md.** |
| A3 | "Spectrum daemon restart-rate" means `systemctl show -p NRestarts wanctl@spectrum.service` diff over the post-deploy window, or equivalently start-event count from `journalctl`. | Pitfall 4 | MEDIUM — if Kevin means "the wanctl-internal soft-restart counter" (a thing that doesn't exist today), the gate measures the wrong thing. **Recommended interpretation:** systemd NRestarts. |
| A4 | Phase 209's canary comparator will run the SAME `phase206-ab-replay.py` against a fresh soak NDJSON + a fresh flent rerun and produce the same-schema `ab-summary.json`, then diff baseline vs canary. | Pattern 3; Summary | LOW — if Phase 209 wants a different shape, A/B summary becomes Phase-206-only and the "one-line consumer change" criterion fails. Mitigation: schema_version field is forward-compatible. |
| A5 | Jitter is defined as p99-p50 of RRUL latency (bufferbloat convention), not standard-deviation. | Pitfall 6 | LOW — internal definition; matters only for consistency. |
| A6 | The gate script's `EXIT_BLOCK` (1) blocks Phase 209 deploy hard. There is no "force-deploy" override flag. | Pattern 2 | LOW — matches Phase 201 precedent ("Auto-strip is intentionally NOT implemented — operator must decide."). |
| A7 | Phase 205's source-diff allowlist is exactly 5 files: `cake_signal.py`, `cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py`. | SAFE-09 boundary section | LOW — verified twice: ROADMAP success criterion #4 and `git diff 6508d68 --name-only -- src/wanctl/` [VERIFIED]. |

---

## Locked Operator Decisions (resolved 2026-05-14, pre-plan)

These decisions resolve Assumptions Log entries A1–A3 and Open Question 1. Planner must treat them as locked.

| # | Decision | Resolves | Effect on plan |
|---|----------|----------|----------------|
| D1 | **Golden fixture = 2026-04-29 920-besteffort flent capture** at `/home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/`. Date substitution from the roadmap's "2026-04-22" reference is documented in `golden-fixture-provenance.md`. No fresh flent re-run scheduled. | A1, Open Q1 | Phase 206 commits a deterministic subset of the 2026-04-29 capture as `tests/fixtures/phase206_golden_capture.ndjson` (or matching path). `golden-fixture-provenance.md` is a required plan artifact. |
| D2 | **Pressure-state transition definition = any adjacent zone change.** Counted from `last_zone` per-cycle in the soak NDJSON, normalized per hour. Includes both escalations (GREEN→YELLOW, etc.) and de-escalations. | A2 | `phase206-gate-check.py` computes adjacency-rate (`sum(last_zone[i] != last_zone[i-1]) / hours_in_window`). PHASE-205-ROLLBACK-GATES.md documents this definition explicitly. |
| D3 | **Daemon restart-rate source = `systemctl show -p NRestarts wanctl@spectrum.service` diff over window.** Gate script SSHes to host, samples NRestarts at window-start and window-end, computes rate. SSH pattern matches `scripts/soak-monitor.sh` (lines 130-146). **No `src/wanctl/` edits** — preserves SAFE-09 zero-control-path-diff invariant for Phase 206. | A3 | `phase206-gate-check.py` accepts a `--restart-counter <int>` arg (or reads via SSH when given `--host`). Test fixtures inject synthetic counter pairs. |

**Deferred to planner (researcher defaults stand unless Kevin overrides during plan-checker):**
- Open Question 2 (threshold semantics): RRUL p99 = strict `>5%`, restart-rate / transition-rate = `>10%` increase (more practical than strict-binary which trips on rounding). Planner bakes these as named constants in `phase206-gate-check.py` and documents them in PHASE-205-ROLLBACK-GATES.md.
- Open Question 3 (baseline file): plan commits BOTH `ab-summary.json` (design-time pre/post from golden fixture) AND `baseline-v143.json` (derived from `20260509T183037Z` soak for restart/transition baselines). Gate script accepts either as `--baseline`.

---

## Open Questions

1. **What artifact stands in for the 2026-04-22 flent finding?**
   - What we know: the finding exists conceptually (920 besteffort wash > 940 diffserv4 nowash). The 2026-04-29 `/home/kevin/flent-results/cake-shaper-920-rrul-20260429-231547/` capture is a 920Mbit RRUL run on the post-config, so it's the right *shape* even if the wrong date. SEED-001:77 explicitly says re-run if lost.
   - What's unclear: does Kevin accept the 2026-04-29 substitute, or must Phase 206 schedule a fresh re-run? If a re-run is required, this is a pre-plan gate (operator runs flent, hands the .flent.gz to the planner).
   - Recommendation: **operator decision in `/gsd-discuss-phase 206`.** Default proposal: use the 2026-04-29 artifact, document the date substitution in `golden-fixture-provenance.md`, derive the NDJSON fixture from it. Phase 206 does not require fresh capture in this path.

2. **Should the gate script be authoritative for "increase" semantics, or merely report?**
   - What we know: TOPO-05 says "regression >5% on RRUL p99 latency OR ... restart-rate increase OR ... transition-rate increase."  "Increase" is binary — any positive delta. "Regression >5%" is thresholded.
   - What's unclear: should restart-rate and transition-rate be thresholded too (e.g., >5% increase, or >2 events/hour increase), or strict binary (any positive increase trips)?
   - Recommendation: **operator decision.** Default proposal: keep RRUL at >5% (per requirement text), make restart-rate and transition-rate >10% increase (a more practical operator threshold — strict binary fires on rounding noise). Document the chosen thresholds in `PHASE-205-ROLLBACK-GATES.md` and bake them into `phase206-gate-check.py` constants.

3. **Where does the v1.43 baseline `ab-summary.json` come from on the first run?**
   - What we know: Phase 206 must produce A/B summaries against two configs (pre = diffserv4 nowash, post = besteffort wash). The "v1.43 baseline" for restart-rate and transition-rate measurement is the `20260509T183037Z` soak [VERIFIED].
   - What's unclear: is the committed-fixture A/B summary itself enough to serve as the baseline that Phase 209's gate dry-run compares against? Or must Plan 206 also run the harness against `20260509T183037Z` data to derive an authoritative `baseline-v143.json`?
   - Recommendation: commit BOTH — `ab-summary.json` (derived from the deterministic golden fixture, shows the design-time pre/post comparison) AND `baseline-v143.json` (derived by running the gate-check helper over the `20260509T183037Z` soak NDJSON and a `--no-flent` stub, populating only the restart-rate + transition-rate baseline fields). The gate script accepts either as `--baseline`.

---

## Sources

### Primary (HIGH confidence)
- `/home/kevin/projects/wanctl/.planning/ROADMAP.md` Phase 205 + 206 + 209 sections — phase scope, SAFE-09 boundary, dependency chain [VERIFIED: read in full]
- `/home/kevin/projects/wanctl/.planning/REQUIREMENTS.md` TOPO-04, TOPO-05, SAFE-09 [VERIFIED: read in full]
- `/home/kevin/projects/wanctl/.planning/seeds/SEED-001-spectrum-topology-correct-cake-mode.md` — origin of the "2026-04-22 out-of-band" finding; the lost-capture acknowledgement [VERIFIED: read in full]
- `/home/kevin/projects/wanctl/tests/test_phase_193_replay.py` — canonical replay pattern: `_replay()`, `_snap()`, `_fresh_controller()`, EXPECTED_ZONES/RATES literal lists [VERIFIED: read]
- `/home/kevin/projects/wanctl/tests/test_phase_195_replay.py` — pattern extension: imports `_replay`/`_snap` from 193, adds new trace shapes [VERIFIED: read]
- `/home/kevin/projects/wanctl/scripts/phase201-predeploy-gate.sh` — gate script skeleton: exit-code contract, env-override, log helpers [VERIFIED: read in full]
- `/home/kevin/projects/wanctl/tests/test_phase201_predeploy_gate.py` — gate-test scaffolding pattern: subprocess invocation, env-var fixture, tmp-path YAML [VERIFIED: read]
- `/home/kevin/projects/wanctl/tests/fixtures/phase201_replay_corpus.py` — fixture loader pattern: `ReplaySample` dataclass, REPO_ROOT/NDJSON paths [VERIFIED: read]
- `/home/kevin/projects/wanctl/scripts/phase198-rerun-flent-3run.sh:240-267` — flent `.flent.gz` parsing precedent: `extract_median()` using gzip+json+statistics [VERIFIED: read]
- `/home/kevin/projects/wanctl/scripts/soak-monitor.sh:130-146` — journalctl-over-SSH pattern for restart/error counting [VERIFIED: read]
- `/home/kevin/projects/wanctl/.planning/phases/205-tin-agnostic-cake-signal-allow-wash-gate/205-04-PLAN.md` — SAFE-09 boundary verification mechanics, value-invariance grep pattern [VERIFIED: read in full]
- `/home/kevin/projects/wanctl/.planning/milestones/v1.43-phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson` — v1.43 baseline NDJSON shape: confirms `last_zone`, `zone_trace_tail` available per cycle [VERIFIED: read sample]
- `/home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/rrul-*.flent.gz` — closest available 920-besteffort RRUL artifact [VERIFIED: file exists, schema inspected — `metadata`, `results`, `x_values`, `raw_values` keys; 38 result series including "Ping (ms) ICMP"]

### Secondary (MEDIUM confidence)
- `/home/kevin/projects/wanctl/.planning/v1.44-THESIS-DRAFT.md` — milestone spine + rollback gate wording [VERIFIED: read]
- `/home/kevin/projects/wanctl/.planning/PROJECT.md` — current milestone context [VERIFIED: read]
- `/home/kevin/projects/wanctl/scripts/soak_summary_aggregate.py` — aggregator schema (the existing `aggregate_soak()` output shape) — relevant if Phase 206 augments the schema, which it shouldn't [VERIFIED: read keys]
- Python stdlib `statistics.quantiles` for p99 [CITED: https://docs.python.org/3/library/statistics.html#statistics.quantiles]

### Tertiary (LOW confidence)
- "Bufferbloat / RPM convention: jitter = p99-p50 latency" — convention is widely used; not formally cited here. [ASSUMED — A5]

---

## Project Constraints (from CLAUDE.md)

These constraints are extracted verbatim from `/home/kevin/projects/wanctl/CLAUDE.md` and apply to Phase 206:

- **Change policy:** "Explain risky changes before changing behavior. Never refactor core logic, algorithms, thresholds, or timing without approval. Prefer targeted fixes over broad cleanup in the control path. Priority: stability > safety > clarity > elegance." → Phase 206 is harness-only; this constraint is auto-satisfied as long as `src/wanctl/` diff stays at 5 files.
- **Portable controller architecture:** "The controller is link-agnostic. The same code must run across cable, DSL, fiber, and other deployments. Deployment-specific behavior belongs in YAML config, not Python branching." → The harness must drive `QueueController` with config dictionaries that represent both pre and post via different parameter values, not branching code paths. ✓ matches the §"Pattern 1" sketch.
- **Architectural Spine (Read-Only Unless Explicitly Requested):**
  - State logic: DL = 4-state GREEN/YELLOW/SOFT_RED/RED; UL = 3-state. Phase 206 must report on both; the A/B summary's `zone_distribution` block should be per-direction.
  - Flash wear: "Queue limits should only be sent to the router when values change." → the offline harness doesn't apply limits, so this is informational; document that `rate_apply_count` in the summary counts the number of times `adjust_4state` returned a rate different from the previous cycle.
  - Health/observability: "do not break payload shape casually." → Phase 206 emits a new file (`ab-summary.json`), not a modification of `/health` payload. Safe.
- **Service Model:** "Active deployment is service-based, not timer-based... Current units: `wanctl@.service`, `steering.service`." → Restart-rate measurement targets `wanctl@spectrum.service` specifically, not `wanctl.timer`.
- **Performance Characteristics:** "Cycle Interval: 50ms (production standard)." → Harness fixture must use 50ms cycle granularity (`x_values` step 0.2s is 200ms per flent point; the in-process replay uses one snapshot per "cycle" — clarify that one fixture sample = one 50ms controller cycle, OR document the downsampling factor).
- **Documentation primary references:** updates to `docs/CONFIGURATION.md` etc. are explicitly Phase 209 work (TOPO-07), not Phase 206. Don't touch them.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every tool is repo-local or in the existing venv; precedents in Phase 193/198/201 are concrete and read directly.
- Architecture: HIGH — pattern is "Phase 193 in-process replay + Phase 201 gate skeleton," both proven.
- Pitfalls: HIGH on pitfalls 2/5/6 (mechanical), MEDIUM on pitfalls 1/3/4 (depend on operator intent — see Assumptions Log A1/A2/A3).
- Fixture provenance: LOW — the 2026-04-22 artifact is missing; requires operator decision (Open Question 1).
- Telemetry sources for gate inputs: HIGH for transition-rate (NDJSON `last_zone` is real); MEDIUM for restart-rate (multiple viable derivation paths, no first-class metric).

**Research date:** 2026-05-14
**Valid until:** 2026-06-13 (30 days — Phase 206 is on stable footing; only risk is Kevin disagreeing with A1/A2/A3)

---

## RESEARCH COMPLETE

**Phase:** 206 — A/B replay harness + rollback gates
**Confidence:** HIGH (with three explicit assumptions requiring `/gsd-discuss-phase 206` confirmation)

### Key Findings

1. **Prior art is strong and current.** Phase 193 established the in-process replay pattern (`_replay()` + `_snap()` + `EXPECTED_ZONES`/`EXPECTED_RATES` literal lists); Phase 195 and Phase 201 extend it; the test files import directly from each other. Phase 206 plugs into this lineage — no new harness shape required.
2. **Predeploy gate has a tested skeleton.** `scripts/phase201-predeploy-gate.sh` is the exact template (exit 0/1/2, env-var local override, `set -euo pipefail`, no-auto-fix, operator-actionable messages). Copy verbatim, change the three checks.
3. **The 2026-04-22 flent artifact is missing.** SEED-001:77 acknowledged this risk at seed-plant time. The closest substitute is `cake-shaper-920-rrul-20260429-231547`. **This is the single most important operator question for `/gsd-discuss-phase 206`.**
4. **Restart-rate and pressure-state-transition-rate are NOT first-class telemetry.** Both must be *derived* in the gate script: restart-rate from `systemctl show -p NRestarts` or `journalctl --output=json`; transition-rate from adjacency diff over `last_zone` in soak NDJSON. Inventing a new `/health` field would breach SAFE-09.
5. **SAFE-09 boundary mechanics are already proven.** Plan 205-04-PLAN Task 1 Step 2 documents the exact `git diff 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l` check. Phase 206 closeout copies this verbatim; expected count remains 5 (no new src/wanctl/ files).

### File Created
`/home/kevin/projects/wanctl/.planning/phases/206-a-b-replay-harness-rollback-gates/206-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard stack | HIGH | All deps already in venv; prior-art directly readable |
| Architecture | HIGH | Pattern = Phase 193 replay + Phase 201 gate; both currently passing |
| Pitfalls | HIGH on mechanics; MEDIUM on intent | A1/A2/A3 in Assumptions Log require operator confirmation |
| Fixture provenance | LOW | 2026-04-22 artifact missing; substitute documented but operator must approve |
| Telemetry derivation | HIGH for transitions; MEDIUM for restart-rate (multiple viable paths) |

### Open Questions (operator-facing for `/gsd-discuss-phase 206`)

1. Accept 2026-04-29 `cake-shaper-920-rrul-20260429-231547` as the golden-fixture provenance, or schedule a fresh 920-besteffort flent re-run first?
2. Thresholds for restart-rate and pressure-state-transition-rate: strict binary (any positive delta blocks) or +10% margin (current RESEARCH default)?
3. Commit both `ab-summary.json` (design-time) AND `baseline-v143.json` (derived from `20260509T183037Z` soak), or just one?

### Ready for Planning

Research complete. The planner can now produce 206-NN-PLAN.md files for:
- Wave 0: failing tests for harness + gate (TOPO-04, TOPO-05 acceptance shapes)
- Wave 1: golden-fixture-provenance.md + committed NDJSON fixture (gated by Open Question 1 resolution in CONTEXT.md)
- Wave 2: `scripts/phase206-ab-replay.py` + `scripts/phase206-gate-check.py`
- Wave 3: `scripts/phase206-predeploy-gate.sh` + `PHASE-205-ROLLBACK-GATES.md`
- Wave 4: SAFE-09 boundary verification + closeout SUMMARY (Plan 205-04 pattern; expected diff scope still 5 files)
