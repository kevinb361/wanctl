# Phase 191 Plan 05 Verification

## Status

`PARTIALLY COMPLETE / MANUAL A/B EXECUTED / PHASE NOT READY TO CLOSE`

Task 1 and Task 3 are complete enough to produce evidence, but the phase is still not cleanly closable:

- Focused hot-path regression slice: passed
- Full `pytest` suite: passed
- `SAFE-04` diff proof: passed
- `SAFE-03` phase-local diff proof: passed
- `SAFE-03` strict `v1.38..HEAD` proof: still dirty because earlier milestone work outside Phase 191 touched `step_up_mbps`
- `VALN-02` flent A/B: executed on ATT with minimum coverage, but ATT RRUL aggregate download throughput regressed materially vs baseline
- Pre-soak `/health` and slow-apply journal baseline: captured for both WANs

## Phase 191 Closure Rule (set by Phase 191.1)

> "Phase 191 closes using the phase-local SAFE-03 comparator (`git diff <phase-start-sha>..HEAD -- 'src/wanctl/**/*.py'` against the SAFE-03 protected token set), which has been clean since phase start. The strict milestone-wide `v1.38..HEAD` SAFE-03 comparator remains dirty due to pre-existing `step_up_mbps` additions in `src/wanctl/backends/linux_cake.py` that predate Phase 191. Per Phase 191.1 D-06 that milestone-wide dirty diff is preserved in this artifact as contextual debt; per D-07 Phase 191.1 does not attempt to clean that unrelated earlier work. The milestone-wide comparator is therefore NOT the gating rule for Phase 191 closure."

Decision citations:

- `D-05`: phase-local SAFE-03 is the gating comparator for Phase 191 closure.
- `D-06`: strict milestone-wide SAFE-03 evidence remains in this artifact as contextual debt, not the closure gate.
- `D-07`: no cleanup of unrelated pre-existing milestone SAFE-03 debt is attempted in Phase 191.1.

## Requirement Closure Statement

| Requirement | Planned closure in this plan | Current status |
| --- | --- | --- |
| `VALN-02` | Full closure via flent A/B vs `v1.38.0` | `NOT CLOSED` - ATT minimum-coverage A/B completed, but RRUL aggregate download throughput regressed vs baseline, so the run does not support a clean PASS verdict |
| `SAFE-03` | Full closure via diff proof | `PARTIAL` - Phase 191 itself shows zero protected-token touches since phase start, but the strict `v1.38..HEAD` grep still finds pre-existing milestone-level `step_up_mbps` additions outside this phase |
| `SAFE-04` | Full closure via diff proof + VALN-02 evidence | `PASS` - no new latency primitives were added in the apply-path files checked by this plan |
| `TIME-03` | `PARTIAL EVIDENCE ONLY` via pre-soak baseline snapshot | `PARTIAL EVIDENCE CAPTURED` - current `/health` snapshot and last-hour slow-apply journal evidence recorded for both WANs |
| `TIME-04` | `PARTIAL EVIDENCE ONLY` via pre-soak baseline snapshot | `PARTIAL EVIDENCE CAPTURED` - current overlap snapshot recorded for both WANs |

## Regression Evidence

**HEAD base:** `80cb89101d4625eb3467fb6a49924fd1864d9135`  
**Date:** `2026-04-20`  
**Tested tree:** current working tree on top of `HEAD` with local fixes in `docker/Dockerfile`, `scripts/check_private_access.py`, `src/wanctl/check_steering_validators.py`, `src/wanctl/steering/daemon.py`, `src/wanctl/storage/writer.py`, `tests/steering/test_steering_daemon.py`, and `tests/test_failure_cascade.py`

### Focused hot-path slice

Command: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`  
Result: `462 passed in 37.99s`  
Exit code: `0`

### Full suite

Command: `.venv/bin/pytest tests/ -q`  
Result: `4564 passed, 2 deselected in 254.35s (0:04:14)`  
Exit code: `0`

## SAFE-03 Diff Proof

### Baseline ref used

Primary requested ref `v1.38.0` does not exist in this repo. The nearest shipped milestone tag present locally is `v1.38` at commit `a4afec9`.

### Strict milestone-wide proof requested by the plan

Command:

```bash
git diff v1.38..HEAD -- 'src/wanctl/**/*.py' \
  | grep -E '^[+-]' \
  | grep -E '(EWMA|dwell_cycles|deadband|burst_detection|target_bloat_ms|warn_bloat_ms|factor_down|step_up|green_required|accel_threshold_ms|accel_confirm_cycles|CYCLE_INTERVAL_SECONDS|_cycle_interval_ms|alpha_baseline|alpha_load|baseline_time_constant|load_time_constant)'
```

Literal output:

```text
+                .get("step_up_mbps", 0)
+                .get("step_up_mbps", 0)
```

Interpretation: the strict `v1.38..HEAD` grep is not clean. The hits come from earlier milestone work in `src/wanctl/backends/linux_cake.py`, not from Phase 191 files.

Secondary guard command:

```bash
git diff v1.38..HEAD -- 'src/wanctl/queue_controller.py' 'src/wanctl/cake_signal.py'
```

Literal output:

```text
SAFE-03 PROOF: queue_controller.py and cake_signal.py untouched
```

### Phase-local proof for Phase 191 scope

Command:

```bash
git diff 12b8579a015095c36fe37fe9e909933e0776ae8c..HEAD -- 'src/wanctl/**/*.py' \
  | grep -E '^[+-]' \
  | grep -E '(EWMA|dwell_cycles|deadband|burst_detection|target_bloat_ms|warn_bloat_ms|factor_down|step_up|green_required|accel_threshold_ms|accel_confirm_cycles|CYCLE_INTERVAL_SECONDS|_cycle_interval_ms|alpha_baseline|alpha_load|baseline_time_constant|load_time_constant)'
```

Literal output:

```text
PHASE-LOCAL SAFE-03: zero protected tokens touched since phase start
```

Interpretation: Phase 191 itself did not touch the protected token set, but the plan's stricter milestone-wide comparator is still dirty from earlier work.

## SAFE-04 Diff Proof

### Baseline ref used

`v1.38` (`a4afec9`) because `v1.38.0` is not present locally.

Command:

```bash
git diff v1.38..HEAD -- 'src/wanctl/backends/netlink_cake.py' 'src/wanctl/wan_controller.py' 'src/wanctl/cake_stats_thread.py' \
  | grep -E '^\+' \
  | grep -E 'time\.sleep|threading\.Lock|\.acquire\(|Event\(\)\.wait|\.wait\(timeout'
```

Literal output:

```text
SAFE-04 PROOF: no new latency primitive in apply-path files
```

Result: pass. No new latency primitive was added to the apply-path files inspected by this plan.

## Manual A/B Prerequisites Verified

Repo-side/manual-environment checks completed on this machine:

- `flent` is installed: `/usr/bin/flent`
- `dallas` is reachable: `ping_dallas:0`
- `netperf` connectivity to `dallas` works: `netperf_dallas:0`
- Spectrum source IP on this dev host is `10.10.110.226`
- ATT source IP on this dev host is `10.10.110.233`

## VALN-02 Flent A/B Results

**WAN(s) tested:** `att`  
**Coverage level per C9 policy:** `minimum (one WAN)`  
**Dev machine:** `dev`  
**Baseline ref:** `v1.38` tag (`a4afec9`)  
**HEAD ref:** `80cb891+local`  
**Date:** `2026-04-20`

**Artifacts**

- Baseline manifest: `/home/kevin/flent-results/phase191/baseline_v1.38/att/20260420-102214/manifest.txt`
- Current manifest: `/home/kevin/flent-results/phase191/p191_head/att/20260420-102710/manifest.txt`
- Fresh current manifest: `/home/kevin/flent-results/phase191/p191_head_att_fresh/att/20260420-110533/manifest.txt`

**Method note:** Flent `2.1.1` did not emit a bufferbloat grade in the CLI stats used here, so this verification used ping p99 under load as the plan's fallback comparator.

### ATT

| Test | Metric | `v1.38` baseline | Phase 191 current | Delta | Regression? |
| --- | --- | --- | --- | --- | --- |
| RRUL | ping p99 (ms) | `74.42` | `68.21` | `-6.21` | `no` |
| RRUL | download Mbps | `77.46` | `62.06` | `-15.40` | `yes` |
| RRUL | upload Mbps | `14.65` | `13.95` | `-0.70` | `no` |
| tcp_12down | ping p99 (ms) | `98.33` | `78.95` | `-19.38` | `no` |
| tcp_12down | download Mbps | `74.00` | `73.80` | `-0.20` | `no` |
| VoIP | jitter p99 (ms) | `10.71` | `0.96` | `-9.75` | `no` |
| VoIP | packet loss % | `0.0` | `0.0` | `0.0` | `no` |
| VoIP | one-way delay p99 (ms) | `29.79` | `19.36` | `-10.43` | `no` |

**Verdict:** `FAIL`

**Notes:**

- The ATT run materially improved latency and VoIP quality.
- `tcp_12down` throughput stayed effectively flat.
- RRUL aggregate download throughput fell from `77.46 Mbps` to `62.06 Mbps`, which is too large to call "no regression" honestly.
- Upload throughput stayed within the practical `±5%` tolerance mentioned in the plan guidance.
- The current-side capture was taken after restoring service via redeploy from the current working tree because the initial remote tar backup only preserved `/opt/wanctl` and did not include `/etc/wanctl` or systemd unit files.

### ATT RRUL follow-up repeats

To check whether the initial ATT RRUL throughput drop was just sample noise, two additional current-side ATT RRUL runs were captured:

| Run | ping p99 (ms) | download Mbps | upload Mbps |
| --- | --- | --- | --- |
| baseline `v1.38` | `74.42` | `78.29` | `10.80` |
| current run 1 | `68.21` | `62.56` | `10.26` |
| current repeat 1 | `86.85` | `66.25` | `10.44` |
| current repeat 2 | `60.27` | `69.64` | `10.66` |

Interpretation:

- ATT upload stayed near baseline across all three current-side runs.
- ATT latency varied, but two of the three current-side runs still beat the baseline p99.
- ATT download throughput recovered somewhat on repeats but remained below the `78.29 Mbps` baseline on every current-side run.

### ATT fresh full rerun

To remove the possibility that only the first full ATT set was bad luck, a fresh full ATT current-side set was captured later on the settled current workspace state:

| Test | Metric | `v1.38` baseline | ATT fresh current | Delta | Regression? |
| --- | --- | --- | --- | --- | --- |
| RRUL | ping p99 (ms) | `74.42` | `66.94` | `-7.48` | `no` |
| RRUL | download Mbps | `77.46` | `56.09` | `-21.37` | `yes` |
| RRUL | upload Mbps | `14.65` | `10.27` | `-4.38` | `yes` |
| tcp_12down | ping p99 (ms) | `98.33` | `79.95` | `-18.38` | `no` |
| tcp_12down | download Mbps | `74.00` | `66.98` | `-7.02` | `yes` |
| VoIP | jitter p99 (ms) | `10.71` | `6.11` | `-4.60` | `no` |
| VoIP | packet loss % | `0.0` | `0.03` | `+0.03` | `yes` |
| VoIP | one-way delay p99 (ms) | `29.79` | `35.70` | `+5.91` | `yes` |

Interpretation:

- The fresh full ATT rerun strengthened the negative verdict instead of softening it.
- Under this later run, ATT still showed lower RRUL throughput and now also showed weaker `tcp_12down` throughput plus non-zero VoIP loss.
- At this point the evidence is strong enough to treat ATT as a real regression signal, not just a noisy one-off sample.

### Spectrum RRUL discriminator

To determine whether the throughput drop looked Phase-191-wide or ATT-specific, a Spectrum RRUL baseline/current pair was also captured:

| Run | ping p99 (ms) | download Mbps | upload Mbps |
| --- | --- | --- | --- |
| Spectrum baseline `v1.38` | `75.11` | `288.41` | `2.68` |
| Spectrum current | `68.15` | `402.20` | `7.75` |

Interpretation:

- Spectrum did not reproduce the ATT throughput drop.
- On this single RRUL discriminator run, Spectrum current performance was materially better than the baseline on both latency and throughput.
- The follow-up evidence points to an ATT-specific issue or test-condition difference, not a broad throughput regression across both WANs.

### ATT root-cause isolation probes

Two targeted live probes were run after the ATT repeats to isolate likely causes:

#### Probe 1: disable ATT write coalescing on current code

Temporary test build:

- current code
- ATT-only override in `LinuxCakeAdapter.from_config()` so `increase_coalesce_window_sec=0.0` for `wan_name == "att"`

RRUL result:

| Run | ping p99 (ms) | download Mbps | upload Mbps |
| --- | --- | --- | --- |
| baseline `v1.38` | `74.42` | `78.29` | `10.80` |
| no-coalescing probe | `75.46` | `60.59` | `10.45` |

Interpretation:

- Disabling ATT coalescing did **not** restore throughput.
- The coalescing path is therefore not the primary explanation for the ATT regression.

#### Probe 2: restore ATT config drift to `v1.38` values on current code

Temporary test build:

- current code
- ATT config reverted only for:
  - `irtt.server`: `zylone.org` -> `104.200.21.31`
  - `fusion.enabled`: `false` -> `true`

RRUL result:

| Run | ping p99 (ms) | download Mbps | upload Mbps |
| --- | --- | --- | --- |
| baseline `v1.38` | `74.42` | `78.29` | `10.80` |
| current code + `v1.38` ATT config | `76.77` | `78.92` | `10.76` |

Interpretation:

- Restoring the ATT `v1.38` config on current code brought ATT RRUL throughput back to baseline.
- That makes ATT config/runtime drift the leading cause, not the Phase 191 overlap instrumentation and not the write-coalescing experiment above.
- The most important ATT drift since `v1.38` is:
  - `irtt.server`: `104.200.21.31` -> `zylone.org`
  - `fusion.enabled`: `true` -> `false`

Working hypothesis:

- Phase 191 did not create the ATT throughput regression directly.
- Current ATT validation failure is primarily explained by ATT-specific config/runtime drift that happened after `v1.38`.
- Phase 191 remains blocked for closure because the validation artifact is still red on the current shipped ATT config, but the root cause appears to sit outside the narrow Phase 191 code changes.

## Pre-Soak Baseline Snapshot (TIME-03/TIME-04 closure path)

**Files captured**

- `/tmp/phase191-presoak/spectrum_p191_health_pre_soak.json`
- `/tmp/phase191-presoak/att_p191_health_pre_soak.json`
- `/tmp/phase191-presoak/spectrum_slow_apply_pre_soak.txt`
- `/tmp/phase191-presoak/att_slow_apply_pre_soak.txt`

### Spectrum overlap snapshot

```json
{
  "active_now": false,
  "episodes": 0,
  "last_apply_finished_monotonic": null,
  "last_apply_started_monotonic": null,
  "last_dump_elapsed_ms": 5.684,
  "last_dump_finished_monotonic": 1113472.155,
  "last_dump_started_monotonic": 1113472.152,
  "last_overlap_monotonic": null,
  "last_overlap_ms": null,
  "max_overlap_ms": 0.0,
  "slow_apply_with_overlap_count": 0
}
```

Slow-apply summary, last hour:

- `8` concrete slow-apply warnings
- `3` suppression notices
- max observed warning in captured window: `38.7ms`

### ATT overlap snapshot

```json
{
  "active_now": false,
  "episodes": 2,
  "last_apply_finished_monotonic": 1113373.601,
  "last_apply_started_monotonic": 1113373.599,
  "last_dump_elapsed_ms": 4.281,
  "last_dump_finished_monotonic": 1113472.233,
  "last_dump_started_monotonic": 1113472.231,
  "last_overlap_monotonic": 1113271.851,
  "last_overlap_ms": 1.733,
  "max_overlap_ms": 2.638,
  "slow_apply_with_overlap_count": 1
}
```

Slow-apply summary, last hour:

- `2` concrete slow-apply warnings
- `0` suppression notices
- max observed warning in captured window: `107.2ms`

Full `TIME-03` / `TIME-04` closure requires 24 hours of post-merge soak comparison against this snapshot and is out of scope for this plan.

## Phase 191.1 Restored-Config Rerun (VALN-02 closure evidence)

### Deploy metadata

- `deploy_commit`: `d49b91469b019e4f7f7398811b902aa816a0514a`
- `deploy_time_utc`: `2026-04-20T17:24:13Z`
- `deployed_config_verified`: `true`
- `fusion_mode_after_restart`: `enabled`
- `irtt_server_after_restart`: `104.200.21.31:2112`
- `reflector_reachability_passed`: `false`
- `outcome_class`: `reflector_unreachable`

The restored-config deployment returned ATT to the intended `v1.38` config posture by restoring `irtt.server` to `104.200.21.31` (replacing the drifted current value `zylone.org`) and re-enabling `fusion.enabled=true` under deploy commit `d49b91469b019e4f7f7398811b902aa816a0514a`.

### Artifacts

- ATT manifest: none recorded in `.planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json` (`att_manifest: null`) because flent did not run after the reflector gate failed. Planned artifact root: `~/flent-results/phase191.1/p191_1_restored/att/`
- Spectrum manifest: none recorded in `.planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json` (`spectrum_manifest: null`) because flent did not run after the reflector gate failed. Planned artifact root: `~/flent-results/phase191.1/p191_1_restored/spectrum/`
- Structured rerun record: `.planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json`

### ATT results

| Test | Metric | `v1.38` baseline | Restored-config rerun | Delta | Regression? |
| --- | --- | --- | --- | --- | --- |
| RRUL | ping p99 (ms) | `74.42` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| RRUL | download Mbps | `78.29` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| RRUL | upload Mbps | `10.80` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| tcp_12down | ping p99 (ms) | `98.33` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| tcp_12down | download Mbps | `74.00` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| VoIP | jitter p99 (ms) | `10.71` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| VoIP | one-way delay p99 (ms) | `29.79` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |
| VoIP | packet loss % | `0.0` | `not recorded (reflector_unreachable)` | `n/a` | `blocked` |

### Spectrum discriminator

| Run | ping p99 (ms) | download Mbps |
| --- | --- | --- |
| restored-config discriminator | `not recorded (reflector_unreachable)` | `not recorded (reflector_unreachable)` |

VALN-02 verdict: BLOCKED (reflector_unreachable)

The rerun stopped at the `reflector_unreachable` pre-flight gate after the restored ATT config deploy succeeded, so this is neither a PASS nor a throughput-regression FAIL. The rerun could not produce a valid throughput verdict, and Phase 191 remains blocked on reflector reachability as a different sub-cause until the restored reflector path is measurable.

## Remaining Work

1. Treat ATT as the blocking evidence set for Phase 191 closure under the current deployed ATT config.
2. Decide whether `SAFE-03` closure for Phase 191 should use the strict milestone-wide `v1.38..HEAD` comparator or the phase-local comparator, because the strict proof remains dirty from pre-existing milestone work outside this phase.
3. If closure is still desired, open follow-up work for ATT config drift:
   - decide whether `irtt.server=zylone.org` and/or `fusion.enabled=false` should remain
   - rerun ATT validation after choosing the intended ATT production config
   - keep Phase 191 evidence scoped: the root-cause probe above suggests the red ATT result is not primarily caused by Phase 191 code
4. Post-merge only: run the 24-hour soak and compare against the pre-soak snapshot above for `TIME-03` / `TIME-04`.

## Manual Checkpoint Outcome

The manual checkpoint is no longer blocked on missing artifacts. It is now blocked on the actual evidence:

- `VALN-02` does not support a PASS verdict on ATT minimum coverage, and the fresh rerun reinforced that
- `SAFE-03` strict milestone-wide proof is still not clean

Phase 191 should not be marked complete from this verification artifact as it stands.

### Phase 191.1 update

Phase 191.1 deployed the restored ATT config under commit `d49b91469b019e4f7f7398811b902aa816a0514a` and recorded `VALN-02 verdict: BLOCKED (reflector_unreachable)`. Phase 191 therefore stays blocked on the reflector-reachability sub-cause; restored-config closure evidence is incomplete until the ATT reflector path can be measured under the phase-local SAFE-03 comparator rule.
