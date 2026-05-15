---
phase: 206
artifact: PHASE-205-ROLLBACK-GATES
audience: operator
status: stable
enforced_by: scripts/phase206-predeploy-gate.sh
enforced_by_python: scripts/phase206-gate-check.py
thresholds_source: scripts/phase206-thresholds.json
---

# Phase 205/206 Rollback Gates — Operator Reference

## Purpose

Before Phase 209's Spectrum canary deploys `920Mbit besteffort wash`, the operator runs
`scripts/phase206-predeploy-gate.sh` against:
- the baseline `tests/fixtures/phase206_baseline_v143.json` (v1.43 reference; carries `gate_baseline` sub-object with the audit-grade numerics),
- a fresh A/B summary captured under the post-migration controller, and
- during the 24h soak, the post-deploy soak NDJSON.

Any one of three triggers tripping is **BLOCK** (exit 1) — do not proceed with the deploy or, if mid-soak, execute the documented two-snapshot rollback ritual.

## Thresholds — Single Source of Truth

All three threshold constants live in `scripts/phase206-thresholds.json`:

```json
{
  "thresholds_schema_version": 1,
  "RRUL_P99_REGRESSION_PCT": 5.0,
  "RESTART_RATE_INCREASE_PCT": 10.0,
  "TRANSITION_RATE_INCREASE_PCT": 10.0
}
```

`scripts/phase206-gate-check.py` loads these at module import. **This document inlines the values for operator readability** but the JSON is authoritative — Plan 04's closeout drift-check verifies the inlined values below match the JSON.

| Constant | Current value | Trigger semantics |
|----------|---------------|-------------------|
| `RRUL_P99_REGRESSION_PCT` | `5.0` | RRUL p99 increases by more than 5.0% → block (strict `>`). |
| `RESTART_RATE_INCREASE_PCT` | `10.0` | restart-rate exceeds baseline by more than 10.0% → block. Zero-baseline policy: any restart trips when baseline is 0.0/h. |
| `TRANSITION_RATE_INCREASE_PCT` | `10.0` | transition-rate (per hour, elapsed-window) exceeds baseline by more than 10.0% → block. Zero-baseline policy: any transition trips when baseline is 0.0/h. |

## Exit-Code Contract (mirrors scripts/phase201-predeploy-gate.sh)

| Code | Meaning |
|------|---------|
| 0 | PASS — all three triggers within thresholds |
| 1 | BLOCK — at least one trigger breached |
| 2 | ABORT — missing input, malformed env, SSH/parse failure, or `--mode post-soak` invoked without required inputs |

## Modes

| Mode | Behavior |
|------|----------|
| `--mode predeploy` (default) | Run RRUL check always. Skip restart/transition checks with INFO when inputs are absent and `gate_baseline` lacks the corresponding `*_baseline` field. ABORT on cross-mismatch. |
| `--mode post-soak` | Require all three triggers to be evaluated. Missing `--soak-ndjson`, missing `--restart-counter-*`, or missing `gate_baseline` fields → ABORT (rc=2). |

Use `--mode post-soak` for the 24h soak window's final gate check before declaring deploy success. Use `--mode predeploy` for the pre-deploy dry-run; RRUL-only is valid for predeploy when soak/restart inputs are not yet available.

## Rollback Trigger 1: RRUL p99 Latency Regression

### Definition

The 99th percentile of RRUL ping latency under the post-migration controller exceeds the v1.43 baseline by more than the threshold. Strict `>` per TOPO-05: `pct > 5.0` blocks.

Jitter (separate field in the A/B summary, informational) is defined as `p99 - p50` of the same RRUL ping series — the Bufferbloat/RPM convention. Apply it identically to pre and post sides (RESEARCH Pitfall 6).

### Threshold

`RRUL_P99_REGRESSION_PCT = 5.0` — source of truth: `scripts/phase206-thresholds.json`.

### Measurement Source

Two metric sources are supported (`summary["meta"]["metric_source"]` indicates which):

1. **`flent` path (preferred for production canary):** the A/B harness is run with `--flent-gz-pre PATH --flent-gz-post PATH` and parses real RRUL p99 / throughput / jitter from the flent `.gz` artifacts. The gate reads `summary["post"]["rrul_p99_latency_ms"]` directly.
2. **`controller_replay` path (default; CI-friendly):** no flent artifacts supplied. The harness emits controller-derived metrics (`controller_rate_p99_mbps` etc.) and `summary["post"]["rrul_p99_latency_ms"]` is absent. The gate falls back to `controller_rate_p99_mbps` as a proxy for “did the controller behave the same under load” — `check_rrul_p99` inverts the regression sense (a rate drop is a regression, not a rate increase).

### Formula

Flent path:

```text
pct = ((candidate.post.rrul_p99_latency_ms - baseline.post.rrul_p99_latency_ms) /
       baseline.post.rrul_p99_latency_ms) * 100.0
breach = pct > 5.0
```

Controller-replay path:

```text
pct = -((candidate.post.controller_rate_p99_mbps - baseline.post.controller_rate_p99_mbps) /
        baseline.post.controller_rate_p99_mbps) * 100.0   # NOTE: inverted sign
breach = pct > 5.0
```

### Example: Breach

```text
baseline.post.rrul_p99_latency_ms = 20.0 ms
candidate.post.rrul_p99_latency_ms = 22.0 ms
pct = +10.0% > 5.0% -> BLOCK
[phase206-gate-check BLOCK] RRUL p99 regression: baseline=20.00 current=22.00 delta=+10.0% > 5.0% (source: rrul_p99_latency_ms)
```

### Example: Pass

```text
baseline.post.rrul_p99_latency_ms = 20.0 ms
candidate.post.rrul_p99_latency_ms = 21.0 ms
pct = +5.0% (NOT > 5.0) -> PASS at the boundary (strict inequality)
[phase206-gate-check INFO] RRUL p99: +5.0% (within +/-5.0%) (source: rrul_p99_latency_ms)
```

## Rollback Trigger 2: Daemon Restart-Rate Increase

### Definition

The Spectrum daemon's `wanctl@spectrum.service` `NRestarts` counter increased over the post-deploy window faster than the v1.43 baseline rate, by more than the threshold. Includes the operator-side deploy-grace adjustment (RESEARCH Pitfall 4): the rate-window start is `deploy_complete_timestamp + 5min`, not the deploy timestamp itself — the intentional once-only deploy restart is not counted.

### Threshold

`RESTART_RATE_INCREASE_PCT = 10.0` — source of truth: `scripts/phase206-thresholds.json`. Rationale: strict-binary “any increase trips” would fire on rounding noise around the baseline zero; 10% is the smallest practical threshold that distinguishes signal from noise given typical baseline rates.

**Zero-baseline policy:** when `restart_rate_per_hour_baseline == 0.0` (the v1.43 reference soak case), the percent math does not apply. The gate treats any `current_rate_per_hour > 0.0` as breach. The committed `gate_baseline.restart_rate_per_hour_baseline` is `0.0` because the v1.43 reference soak had zero `wanctl@spectrum.service` restarts.

### Measurement Source (Locked Decision D3)

`systemctl show -p NRestarts wanctl@spectrum.service` — cumulative integer counter, sampled twice (window start and window end), differenced and divided by window hours.

**The bash wrapper owns the SSH** (M7); the Python core operates on explicit counter literals the wrapper passes in.

Wrapper SSH pattern (mirrors `scripts/soak-monitor.sh:130-146`):

```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes cake-shaper \
    "systemctl show -p NRestarts wanctl@spectrum.service"
# Output: NRestarts=N
```

Operator usage:

1. After `deploy_complete + 5min` grace, run on the operator-side host: `ssh cake-shaper "systemctl show -p NRestarts wanctl@spectrum.service"` → capture `<RC_START>`.
2. After the 24h soak, invoke the gate with `--ssh-target cake-shaper --restart-counter-start <RC_START> --window-start-iso8601 <T0+5min> --window-end-iso8601 <T0+24h>` — the wrapper samples `<RC_END>` itself and computes `--window-hours`.
3. Alternatively, capture `<RC_END>` manually and pass `--restart-counter-start <RC_START> --restart-counter-end <RC_END> --window-hours <H>` to skip SSH entirely.

### Baseline Derivation

`gate_baseline.restart_rate_per_hour_baseline = 0.0` — the committed v1.43 baseline. Source is documented in `tests/fixtures/phase206_baseline_v143.json` under `gate_baseline._provenance.restart_rate_per_hour_baseline_source`. If the operator wishes to refresh this value, capture `NRestarts` twice (soak-start and soak-end) on a fresh v1.43-equivalent host and recompute.

### Formula

```text
current_rate_per_hour = (counter_end - counter_start) / window_hours
pct = ((current_rate_per_hour - baseline_rate_per_hour) / baseline_rate_per_hour) * 100.0
breach = pct > 10.0
```

Zero-baseline branch:

```text
if baseline_rate_per_hour == 0.0:
    breach = current_rate_per_hour > 0.0
```

### Example: Breach

```text
counter_start = 0, counter_end = 5, window_hours = 1.0
current_rate_per_hour = 5.0/h
baseline_rate_per_hour = 0.0/h
-> zero-baseline policy: 5.0 > 0.0 -> BLOCK
```

### Example: Pass

```text
counter_start = 10, counter_end = 10, window_hours = 24.0
current_rate_per_hour = 0.0/h
baseline_rate_per_hour = 0.0/h
-> zero-baseline policy: 0.0 is not > 0.0 -> PASS
```

## Rollback Trigger 3: Pressure-State Transition-Rate Increase (per hour)

### Definition (Locked Decision D2)

Count of distinct adjacent zone changes in the post-deploy soak NDJSON's `last_zone` field, normalized per **elapsed** hour. Includes both escalations (GREEN → YELLOW, YELLOW → SOFT_RED, SOFT_RED → RED) and de-escalations (RED → SOFT_RED, etc.). RESEARCH Pitfall 3 weighed strict-escalation vs any-adjacency and chose any-adjacency — a controller that flaps in either direction is unhealthy.

### Threshold

`TRANSITION_RATE_INCREASE_PCT = 10.0` — source of truth: `scripts/phase206-thresholds.json`. Same rationale as trigger 2.

### Measurement Source

Post-deploy soak NDJSON `last_zone` field — already present in the v1.43 baseline soak `20260509T183037Z/soak-capture.ndjson` per RESEARCH Sources line 700. No `/health` field changes required (SAFE-09 preserved).

### Formula (elapsed-window correction per codex)

```python
transitions = sum(1 for i in range(1, len(last_zones))
                  if last_zones[i] != last_zones[i - 1])
elapsed_s = max(t_monotonic_values) - min(t_monotonic_values)
hours = max(elapsed_s / 3600.0, 1e-9)
current_rate_per_hour = transitions / hours
pct = ((current_rate_per_hour - baseline_rate_per_hour) /
       baseline_rate_per_hour) * 100.0
breach = pct > 10.0
```

### Baseline Derivation

`gate_baseline.transition_rate_per_hour_baseline = 77.17` — derived at Plan 02 planning time from `.planning/milestones/v1.43-phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson`: 1852 adjacent zone changes over an elapsed window of 86399.6 seconds = 23.9999 hours, yielding 77.17 transitions per hour. Computation script lives in `phase206_baseline_v143.json._provenance.transition_rate_per_hour_baseline_source`. To refresh, re-run the script against a current v1.43 soak NDJSON.

### Example: Breach

```text
baseline_rate_per_hour = 77.17/h
current_rate_per_hour = 90.00/h
pct = +16.6% > 10.0% -> BLOCK
```

### Example: Pass

```text
baseline_rate_per_hour = 77.17/h
current_rate_per_hour = 84.88/h
pct = +9.99% (NOT > 10.0) -> PASS at the boundary
```

## Operator Workflow

1. (Predeploy) Generate a fresh A/B summary against the current main:
   ```bash
   .venv/bin/python scripts/phase206-ab-replay.py --out /tmp/ab-canary.json
   ```
   Optionally with real RRUL parsing: add `--flent-gz-pre <pre.gz> --flent-gz-post <post.gz>`.
2. (Predeploy) Run the gate against the v1.43 baseline in `--mode predeploy`:
   ```bash
   scripts/phase206-predeploy-gate.sh \
       --mode predeploy \
       --baseline tests/fixtures/phase206_baseline_v143.json \
       --candidate /tmp/ab-canary.json
   ```
   Expected: exit 0.
3. (Deploy) Apply the Spectrum config migration. Record `deploy_complete_timestamp`.
4. (Post-deploy stabilization) Wait 5 minutes. Capture `restart_counter_start`:
   ```bash
   ssh cake-shaper "systemctl show -p NRestarts wanctl@spectrum.service"
   ```
5. (Soak — 24h) Run `scripts/soak-capture.sh` to produce the post-deploy soak NDJSON.
6. (Post-soak) Run the gate in `--mode post-soak` (all three triggers required):
   ```bash
   scripts/phase206-predeploy-gate.sh \
       --mode post-soak \
       --baseline tests/fixtures/phase206_baseline_v143.json \
       --candidate /tmp/ab-canary.json \
       --soak-ndjson /var/log/wanctl/<run-id>/soak-capture.ndjson \
       --ssh-target cake-shaper \
       --restart-counter-start <RC_START> \
       --window-start-iso8601 "<deploy_complete + 5min>" \
       --window-end-iso8601 "<end_of_soak>" \
       --journal-since "<deploy_complete + 5min>"
   ```
   Expected: exit 0. Non-zero exit = execute the v1.42/v1.43 two-snapshot rollback ritual.

## What This Doc Does NOT Authorize

- Adding new fields to `/health` for restart-rate or pressure-state-transitions. That would be a `src/wanctl/` source diff and a SAFE-09 behavioral violation. Both metrics are derived in `scripts/phase206-gate-check.py` from existing artifacts.
- Changing controller thresholds/algorithms (EWMA, dwell, deadband, burst). SAFE-09 invariant; the controller behavior must remain identical to v1.43 close (`6508d68`) for non-allowlisted files.
- Force-deploying through a BLOCK. There is no `--force` flag (matches Phase 201's “operator must decide” precedent).
- Hardcoding threshold numerics in operator-facing scripts. Modify `scripts/phase206-thresholds.json` instead, then re-run the full pytest suite to confirm no test asserts the old value.

## Traceability

- TOPO-05: This document is the TOPO-05 operator-readable deliverable.
- Threshold source of truth: `scripts/phase206-thresholds.json` (Plan 02).
- Enforced by: `scripts/phase206-predeploy-gate.sh` (Plan 02 bash wrapper; owns SSH).
- Implemented by: `scripts/phase206-gate-check.py` (Plan 02 Python core; SSH-free, JSON-only).
- Tested by: `tests/test_phase206_predeploy_gate.py` (Plan 02 tests).
