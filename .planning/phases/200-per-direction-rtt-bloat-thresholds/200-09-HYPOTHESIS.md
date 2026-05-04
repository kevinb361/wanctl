# Phase 200 Plan 09 — Canary Failure Root-Cause Hypothesis

**Author:** the agent (gsd-planner gap-closure, reviews-mode revision)  
**Date:** 2026-05-04 UTC  
**Status:** awaiting operator approval at Plan 09 checkpoint

**Inputs:**
- `canary/20260503T215734Z/loaded_capture.ndjson` (886 1Hz `/health` samples, primary evidence)
- `canary/20260503T215734Z/verdict.json` (summary only)
- `200-DEPLOY-LOG.md` Failure Analysis
- `200-CONTEXT.md` D-02/D-05/D-06 locks
- `.planning/spectrum-inline-native-18-upload-test-2026-04-29.md`
- `src/wanctl/queue_controller.py:33-34` (`factor_down_yellow` default `1.0`), `:223-231` (UL 3-state decay)
- `configs/spectrum.yaml:68-76` (`ceiling_mbps: 18`, `factor_down_yellow: 0.98`, `target_bloat_ms: 42`, `warn_bloat_ms: 105`)
- `200-REVIEWS.md` (round-1 + round-2 findings: 1Hz sample/cycle framing, jq pipeline, R5 evidence-to-ship, R3 reset semantics, R2 typo)

## Sampling Reality (correct framing)

- Canary `/health` polling is 1Hz; the 886 NDJSON lines are *samples*, not 50ms controller *cycles*.
- The wanctl controller cycle is 50ms (20 Hz). One floor sample at second N could correspond to a single ~1s sojourn at floor, or many short floor incidents that the 1Hz sampler aliases into one observation per second.
- Therefore any sample-count-only statement about floor-collapse frequency is unsupported. We must use run lengths, transitions, state/rate coincidence, and RTT-delta buckets from `loaded_capture.ndjson`.

## NDJSON Analysis Commands and Outputs

Source file:

```bash
NDJSON=.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/loaded_capture.ndjson
set -o pipefail
```

### A) Floor-sample run lengths

```bash
jq -c '{ts: .sampled_at_utc, rate: .wans[0].upload.current_rate_mbps, state: .wans[0].upload.state, base: .wans[0].baseline_rtt_ms, load: .wans[0].load_rtt_ms}' "$NDJSON" | python3 -c '...'
```

Output:

```text
floor_run_lengths: [3, 1, 2, 6, 2, 1, 1, 2, 2, 1, 1, 3, 1, 2, 4, 1, 1, 1, 1, 4, 1, 2, 2, 2, 1, 1, 3, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 2, 2, 6, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 4, 1, 7, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2]
count: 73 max: 7 total_floor_samples: 122
```

### B) State-transition adjacency matrix

```bash
jq -r '.wans[0].upload.state' "$NDJSON" | python3 -c '...'
```

Output:

```text
transitions: {('GREEN', 'GREEN'): 117, ('GREEN', 'YELLOW'): 188, ('YELLOW', 'GREEN'): 157, ('YELLOW', 'YELLOW'): 321, ('YELLOW', 'RED'): 43, ('RED', 'YELLOW'): 13, ('RED', 'GREEN'): 31, ('RED', 'RED'): 14, ('GREEN', 'RED'): 1}
counts: {'GREEN': 306, 'YELLOW': 522, 'RED': 58}
```

### C) RTT-delta percentiles bucketed by zone

```bash
jq -c '{ts: .sampled_at_utc, baseline: .wans[0].baseline_rtt_ms, load: .wans[0].load_rtt_ms, state: .wans[0].upload.state}' "$NDJSON" | python3 -c '...'
```

Output:

```text
GREEN: n=306 p50=20.1 p90=35.6 p95=38.4 max=41.9
YELLOW: n=522 p50=45.0 p90=80.2 p95=88.9 max=104.5
RED: n=58 p50=126.8 p90=169.5 p95=178.5 max=264.6
```

### D) Distribution of YELLOW samples vs floor samples

```bash
jq -c '{rate: .wans[0].upload.current_rate_mbps, state: .wans[0].upload.state}' "$NDJSON" | python3 -c '...'
```

Output:

```text
{('GREEN', 'above_floor'): 289, ('YELLOW', 'above_floor'): 468, ('RED', 'FLOOR'): 51, ('YELLOW', 'FLOOR'): 54, ('GREEN', 'FLOOR'): 17, ('RED', 'above_floor'): 7}
```

### E) Time-to-first-floor from start of loaded window

```bash
jq -c '{ts: .sampled_at_utc, rate: .wans[0].upload.current_rate_mbps}' "$NDJSON" | python3 -c '...'
```

Output:

```text
first_load_sample: 2026-05-03T21:58:36Z first_floor_sample: 2026-05-03T21:58:45Z
```

### F) Floor-precedence cross-reference

```bash
jq -c '{rate: .wans[0].upload.current_rate_mbps, state: .wans[0].upload.state}' "$NDJSON" | python3 -c '...'
```

Output:

```text
floor_total=122 preceded_by_yellow_3=40 preceded_by_red=36
```

### G) True-YELLOW vs below-target vs above-warn breakdown

```bash
jq -c 'select(.wans[0].upload.state == "YELLOW") | {delta: (.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms), state_reason: .wans[0].upload.state_reason}' "$NDJSON" \
  | awk -F'"delta":' '{ split($2, a, ","); d = a[1]+0; if (d < 42) below_target++; else if (d <= 105) deadband++; else above_warn++ } END { printf "true-yellow-deadband (target<delta<=warn): %d, below-target: %d, above-warn: %d\n", deadband, below_target, above_warn }'
```

Output:

```text
true-yellow-deadband (target<delta<=warn): 293, below-target: 229, above-warn: 0
```

### H) Supplemental baseline and schema sanity

Output:

```text
total_samples: 886
first_baseline: 22.57 last_baseline: 22.74 delta: 0.17
wan0_keys: ['asymmetry_gate', 'background_workers', 'baseline_rtt_ms', 'cake_signal', 'cycle_budget', 'download', 'fusion', 'irtt', 'load_rtt_ms', 'measurement', 'name', 'reflector_quality', 'router_connectivity', 'runtime', 'signal_arbitration', 'signal_quality', 'storage', 'tuning', 'upload']
upload_keys: ['current_rate_mbps', 'hysteresis', 'state', 'state_reason']
```

## What We Observed (from NDJSON, not summary)

- Total samples: 886 loaded-window 1Hz `/health` samples.
- Sample distribution by state/rate bucket: 289 GREEN above floor, 468 YELLOW above floor, 7 RED above floor, 17 GREEN floor, 54 YELLOW floor, 51 RED floor.
- State distribution: GREEN 306, YELLOW 522, RED 58.
- Transition adjacency: YELLOW→YELLOW dominates at 321 transitions; GREEN↔YELLOW churn is also high (188 GREEN→YELLOW, 157 YELLOW→GREEN); RED transitions exist but RED is not the dominant state.
- Floor run-lengths: 73 floor sojourns totaling 122 1Hz samples, max run 7 seconds. The failure is many short floor sojourns rather than one long 122-second floor residency.
- RTT-delta percentiles by state: GREEN p95 38.4ms below the 42ms target; YELLOW p50 45.0ms and p95 88.9ms inside the 42–105ms band; RED p50 126.8ms above warn.
- Time-to-first-floor: first floor sample appeared 9 seconds after the loaded window began (`21:58:45Z` vs `21:58:36Z`).
- Floor-precedence: 40/122 floor samples were preceded by three consecutive 1Hz YELLOW samples; 36/122 had a RED in the previous three samples.
- True-YELLOW vs below-target: among YELLOW samples, 293 were true target-to-warn YELLOW, 229 were below-target cling/deadband, and 0 were above-warn anomalies.

### Key derived signals

- **Single long sojourn or many short ones?** Many short ones: 73 floor runs, max 7 seconds, total 122 samples.
- **Did floor samples coincide with YELLOW or RED?** Both: 54 YELLOW-floor and 51 RED-floor, plus 17 GREEN-floor recovery/alias samples. This weakens an R5-only interpretation and strengthens a mixed C2/C3/C7 view.
- **Are floor samples predominantly preceded by ≥3 consecutive YELLOW samples?** Not predominantly at the 1Hz sample level: 40/122 (33%) were preceded by three YELLOW samples; 36/122 (30%) had RED nearby. Because control cycles are 20Hz, this does not rule out intra-second YELLOW cascades, but the NDJSON evidence does not satisfy the strict R5-alone checklist item.
- **For YELLOW samples, is RTT delta typically in `(target=42, warn=105]` or below-target cling?** Mixed but true-YELLOW dominates: 293 true-YELLOW samples vs 229 below-target YELLOW samples. YELLOW p50 is 45.0ms, just over target; p90/p95 stay well below warn.
- **Baseline invariant?** Baseline was effectively frozen during load: 22.57ms → 22.74ms (+0.17ms), so D-02 baseline drift is not implicated by this capture.

## Candidate Causes (≥ 8, ranked by NDJSON-evidence weight)

### C1: Ceiling itself too high for Spectrum upstream (steady-state)

Hypothesis: 18 Mbit shaped rate is still close enough to real DOCSIS upstream capacity that saturated traffic can routinely push RTT delta into the YELLOW band. Evidence: GREEN p90/p95 (35.6/38.4ms) are below the 42ms target, so C1 is not independently proven by GREEN samples. However, the first floor appears within 9 seconds and RED p50 is 126.8ms, so actual saturated dynamics can still overrun the shaping margin. C1 is plausible but not dominant alone.

### C2: `factor_down_yellow=0.98` cascades to floor on YELLOW dwell (ROOT-SUSPECT)

Hypothesis: `QueueController` default `factor_down_yellow: 1.0` means no YELLOW decay, but Spectrum YAML overrides it to `0.98`. With a 50ms cycle, 18 → 8 Mbps takes about 40 consecutive YELLOW decay calls (~2 seconds). Evidence: YELLOW is 522/886 samples and YELLOW→YELLOW has 321 transitions; 54 floor samples are in YELLOW and true-YELLOW samples dominate YELLOW buckets (293). This strongly supports C2 as a major mechanism, but floor-precedence F does not satisfy the strict R5-alone evidence threshold at 1Hz.

### C3: Missing bound on consecutive YELLOW decay

Hypothesis: there is no max-streak clamp on YELLOW multiplicative decay, so a valid YELLOW dwell can continue multiplying until the floor. Evidence: 73 short floor runs and high YELLOW→YELLOW count indicate repeated cascades rather than stable shaping. This is adjacent to C2 but would be fixed by an explicit consecutive-YELLOW clamp (R3) while preserving RED immediate decay.

### C4: Baseline RTT updating during load (D-02 invariant violation)

Hypothesis: baseline rises under load and masks true RTT delta. Evidence rejects this for this capture: baseline moved only +0.17ms over the loaded window (22.57 → 22.74ms). C4 is low-likelihood.

### C5: CAKE shaping not actually applying as expected

Hypothesis: router/Linux CAKE enforcement does not apply the requested ceiling consistently, so modem/CMTS queues still absorb saturated upload. NDJSON does not include live `tc -s qdisc` enforcement proof. The rate state shows wanctl *requested* 18→floor oscillations, not whether the kernel shaped bytes as intended. C5 remains an offline investigation candidate, not selected from current evidence.

### C6: RTT signal asymmetry or measurement-source artifact under saturated UL

Hypothesis: RTT/load measurement is biased high under saturated upload because ICMP/IRTT reflectors or return paths interact with upstream saturation. NDJSON exposes `measurement`, `reflector_quality`, `irtt`, and `signal_quality` keys, but Plan 09 did not find a per-sample alternate RTT decomposition sufficient to separate control-path queueing from measurement bias. C6 remains possible but less supported than C2/C3.

### C7: Verdict-script / 1Hz aliasing artifact

Hypothesis: 50ms floor visits are short bursts and the 1Hz `/health` sampler aliases them. Evidence partially supports and partially rejects this. It is not one long false aggregate: max run is 7s and many runs are singletons. But total 122 floor samples across 73 runs means floor state was observed repeatedly and sometimes consecutively; this is more than a pure one-sample counter artifact. C7 affects interpretation, not the fail verdict.

### C8: Per-direction threshold not actually wired through to live decision

Hypothesis: the runtime canary did not actually use UL-specific 42/105 thresholds. Evidence weighs against C8: Plan 06 D-06 journal line confirmed `upload_target_bloat_ms=42 upload_warn_bloat_ms=105 (target_explicit=True warn_explicit=True)` on the deployed v1.41 binary, and NDJSON state thresholds align with GREEN max delta 41.9 and YELLOW max 104.5. C8 is low-likelihood.

### C9: YELLOW deadband/backlog recovery interaction keeps below-target samples in decay state

Hypothesis: below-target YELLOW/deadband or backlog-suppressed recovery keeps the upload path in YELLOW while RTT delta is already under target, allowing unnecessary YELLOW decay. Evidence: analysis G shows 229 YELLOW samples below 42ms. This makes below-target guards or hold policies relevant, though true-YELLOW samples still dominate.

## Remediation Options (5 total; combinable)

### R1 — YAML-only ceiling lower (`continuous_monitoring.upload.ceiling_mbps: 18 → 14` or `12`)

- **Pros:** Pure config diff; reversible.
- **Cons:** May worsen C2 because lower ceiling means fewer YELLOW decay cycles to hit the 8 Mbps floor. It sacrifices throughput and does not directly address the repeated-decay mechanism.
- **Files touched:** `configs/spectrum.yaml`, `CHANGELOG.md`, `docs/CONFIGURATION.md`. No source change.
- **Required evidence to ship R1:** GREEN p90 RTT delta ≥ target (42ms), floor samples not correlated with YELLOW dwell, and C1 dominates. Current evidence does **not** meet this: GREEN p90 is 35.6ms and YELLOW dwell is prominent.

### R2 — Delta-below-target floor guard

- **Definition:** Optional `QueueController` mode that refuses to decay below `floor + epsilon` only when measured RTT delta is `< target_delta`. It does not fire during true YELLOW (`target < delta ≤ warn`).
- **Pros:** Targets below-target cling (229 YELLOW samples below 42ms).
- **Cons:** Does not address 293 true-YELLOW samples or RED-adjacent floor samples; unlikely sufficient standalone.
- **Files touched:** `src/wanctl/queue_controller.py`, `src/wanctl/autorate_config.py`, `src/wanctl/check_config_validators.py`, tests, docs, changelog.
- **Required evidence to ship R2:** Below-target YELLOW samples are large and floor samples concentrate in below-target YELLOW. Current evidence supports R2 only as adjunct; below-target YELLOW is material but not dominant.

### R3 — Consecutive-YELLOW decay clamp

- **Definition:** Add `consecutive_yellow_decay_clamp: int = 0` to `QueueController`; default 0 is byte-identical. When `>0`, increment a `_yellow_decay_streak` only on YELLOW decay; after the streak exceeds the clamp, hold the current rate. Reset on any non-YELLOW zone, including a single GREEN sample and any RED sample. RED immediate decay remains untouched.
- **Pros:** Directly bounds C2/C3 cascade while preserving link-agnostic controller architecture via config.
- **Cons:** Touches the hot path and introduces an operator-tunable count.
- **Files touched:** `src/wanctl/queue_controller.py`, config schema/validators, tests, docs, changelog.
- **Required evidence to ship R3:** YELLOW→YELLOW count >100 and floor samples frequently adjacent to YELLOW. Current evidence meets this: YELLOW→YELLOW=321; floor is 54 YELLOW plus 40 preceded by three 1Hz YELLOW samples.

### R4 — Operator-tunable deadband hysteresis on YELLOW→GREEN

- **Definition:** Widen or tune upload-only deadband/recovery requirements so near-target oscillation does not repeatedly enter YELLOW decay.
- **Pros:** Addresses the fact that YELLOW p50 is just 45.0ms and 229 YELLOW samples are below target.
- **Cons:** Indirect. It does not bound multiplicative YELLOW decay during true target-to-warn samples.
- **Files touched:** `src/wanctl/queue_controller.py`, config schema/validators, tests, docs, changelog, possibly wiring.
- **Required evidence to ship R4:** YELLOW samples cluster near target/deadband. Current evidence partially supports this (YELLOW p50 45.0ms), but p90/p95 show a wider true-YELLOW band.

### R5 — YAML-only YELLOW hold (RECOMMENDED conservative default)

- **Definition:** Set Spectrum `continuous_monitoring.upload.factor_down_yellow: 1.0` (or near-hold, e.g. `0.995`). This restores the existing `QueueController` default for Spectrum only. RED decay remains immediate via `factor_down`.
- **Pros:** Zero source code change; most conservative under `AGENTS.md` stability rule; directly targets C2; non-Spectrum deployments unchanged.
- **Cons:** If RED/C1/C5 contributes significantly, R5 alone may reduce floor cascades but not pass the canary.
- **Files touched:** `configs/spectrum.yaml`, `CHANGELOG.md`, `docs/CONFIGURATION.md`. No source change.
- **R5 ship-decision evidence:**
  - [ ] Floor sample sojourns predominantly preceded by ≥3 consecutive YELLOW samples: **not met at 1Hz** (40/122).
  - [x] Mean/typical RTT delta during YELLOW falls in 42–105ms band: **mostly met** (293 true-YELLOW vs 229 below-target, p50 45.0ms, p95 88.9ms).
  - [ ] No floor sample occurs without adjacent YELLOW/RED within 3 seconds: **partially met** for YELLOW; RED adjacency is also material (36/122 had RED nearby).
  - **Conclusion:** R5 is still the safest first lever, but current evidence suggests R5-alone is a conservative experiment, not a guaranteed complete fix. Pairing with R3 is better supported if source changes are acceptable.

### Combinations

- **R5+R3 (recommended hedged branch):** YAML hold for immediate Spectrum safety plus a byte-identical-default clamp to protect future deployments that choose `factor_down_yellow != 1.0`.
- **R5 alone:** Smallest safe production diff; acceptable if operator wants minimal change and a learning canary, but evidence does not fully satisfy the R5-alone checklist.
- **R2+R3+R5:** Covers below-target cling and true-YELLOW cascade, but largest scope.
- **R1+R5:** Consider only if an R5/R3 retry still shows high RTT at stable ceiling without repeated floor cascades.

## What This Plan Does NOT Decide

- Final ceiling number, `factor_down_yellow` value, or clamp count.
- Whether to build a DOCSIS-aware UL congestion mode.
- Any production deploy or source/config change.

## Constraints That Plan 200-10 Must Honor (D-06 locks)

- No DL behavior changes: `adjust_4state` and DL `factor_down_yellow` use sites untouched.
- No `/health` schema changes.
- No arbitration logic changes.
- No `initialize_cake` refactor.
- Architectural spine: RTT-delta decisions, frozen baseline under load, immediate RED decrease, sustained-cycle recovery.
- Byte-identical behavior when new keys are absent.
- Hot-path slice must stay green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py`.
- SAFE-06: any new config key must be added to schema, `KNOWN_AUTORATE_PATHS`, tests, and docs.

## Open Questions for Operator

1. Pick one or more remediation branches: R1 / R2 / R3 / R4 / R5, or a combination. Evidence-weighted recommendation: **R5+R3** if source changes are acceptable; **R5 alone** if you want the smallest conservative canary.
2. If R1 or R3 is selected, confirm the value (R1 ceiling target; R3 clamp count).
3. Approve the rollback protocol unchanged from D-10 for the next canary.

## Operator Approval

[Filled at Plan 09 checkpoint:]
- Approved branch(es): __________
- If R1: ceiling target = __________
- If R3: clamp count = __________
- If R5: factor_down_yellow target = __________
- Rationale: __________
- Date / signal: __________
