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
- `deploy_time_utc`: `2026-04-23T21:51:44Z` (fresh restart + rerun on the same deployed restored-config code; remote file hashes still match deploy commit `d49b91469b019e4f7f7398811b902aa816a0514a`)
- `deployed_config_verified`: `true`
- `fusion_mode_after_restart`: `enabled`
- `irtt_server_after_restart`: `104.200.21.31:2112`
- `reflector_reachability_passed`: `true`
- `outcome_class`: `valid_result`

The restored-config deployment returned ATT to the intended `v1.38` config posture by restoring `irtt.server` to `104.200.21.31` (replacing the drifted current value `zylone.org`) and re-enabling `fusion.enabled=true` under deploy commit `d49b91469b019e4f7f7398811b902aa816a0514a`.

The initial `nc -zv` pre-flight used during Phase 191.1 checked TCP on `104.200.21.31:2112`. That was the wrong probe for IRTT, which uses UDP. A manual `irtt client` probe from `cake-shaper` to `104.200.21.31:2112` succeeded, so the rerun proceeded and the final outcome below is based on actual flent captures, not the earlier false TCP negative.

### Artifacts

- ATT manifest: `/home/kevin/flent-results/phase191.1/p191_1_restored/p191_1_rerun_20260423c/att/20260423-165432/manifest.txt`
- Spectrum manifest: `/home/kevin/flent-results/phase191.1/p191_1_restored/p191_1_rerun_20260423c/spectrum/20260423-165800/manifest.txt`
- Structured rerun record: `.planning/phases/191.1-att-config-drift-resolution-and-phase-191-closure/191.1-rerun-results.json`

### ATT results

| Test | Metric | `v1.38` baseline | Restored-config rerun | Delta | Regression? |
| --- | --- | --- | --- | --- | --- |
| RRUL | ping p99 (ms) | `74.42` | `52.10` | `-22.32` | `no` |
| RRUL | download Mbps | `78.29` | `61.47` | `-16.82` | `yes` |
| RRUL | upload Mbps | `10.80` | `13.57` | `+2.77` | `no` |
| tcp_12down | ping p99 (ms) | `98.33` | `47.96` | `-50.37` | `no` |
| tcp_12down | download Mbps | `74.00` | `69.15` | `-4.85` | `yes` |
| VoIP | jitter p99 (ms) | `10.71` | `2.10` | `-8.61` | `no` |
| VoIP | one-way delay p99 (ms) | `29.79` | `25.35` | `-4.44` | `no` |
| VoIP | packet loss % | `0.0` | `0.0` | `0.0` | `no` |

### Spectrum discriminator

| Run | ping p99 (ms) | download Mbps |
| --- | --- | --- |
| restored-config discriminator | `1653.18` | `214.41` |

VALN-02 verdict: FAIL

Phase 191.1 recorded VALN-02 verdict: FAIL against the restored ATT config (deploy commit `d49b91469b019e4f7f7398811b902aa816a0514a`). Per Phase 191.1 D-USER-02, Phase 191 STAYS BLOCKED and cannot close until the regression is resolved. Phase 192 cannot begin. This outcome is recorded honestly per D-11 and is NOT to be overridden by re-running until a favorable sample appears.

**Operator note (2026-04-20):** The ATT rerun appears to have happened during severe rain on the live path. Treat this as weather-confounded evidence: keep the measured FAIL on record, but do not treat it as clean attribution against the restored ATT config until the same rerun is repeated in normal conditions.

**Operator note (2026-04-21):** A second rerun was captured under label `p191_1_rerun_20260421`. ATT improved materially to `74.03 Mbps`, but still missed the `78.29 Mbps ±5%` closure bar by `0.44` percentage points (`-5.44%`). Spectrum simultaneously showed a bad discriminator sample (`283.40 Mbps`, `733.67 ms` ping p99), so this run is also treated as environment-confounded rather than a clean closure sample.

**Operator note (2026-04-21b):** A third rerun was captured under label `p191_1_rerun_20260421b`. ATT fell back to `67.83 Mbps` with `83.91 ms` ping p99, while Spectrum remained degraded at `309.04 Mbps` and `375.64 ms` ping p99. This reinforces that the rerun environment was still unstable; the sample remains useful as context but not as clean closure evidence.

**Operator note (2026-04-23):** A fourth rerun was captured under label `p191_1_rerun_20260423_attclean` after restoring the dev-host source-IP policy so `10.10.110.233` again exited as ATT (`99.126.115.47`) while `10.10.110.226` exited as Spectrum (`70.123.224.169`). This produced the first clean post-policy ATT sample: ATT RRUL `64.40 Mbps` down / `14.45 Mbps` up / `70.57 ms` ping p99, ATT `tcp_12down` `73.30 Mbps` / `97.16 ms` ping p99, and ATT VoIP `27.84 ms` one-way delay p99 with `6.12 ms` jitter p99. However, the matching Spectrum discriminator was still bad at `286.42 Mbps` down with `812.33 ms` ping p99, so this run remains environment-confounded overall even though the ATT source path was verified clean.

**Operator note (2026-04-23c):** A fifth rerun was captured under label `p191_1_rerun_20260423c` after a fresh `wanctl@att` restart on the same restored-config deploy commit `d49b91469b019e4f7f7398811b902aa816a0514a`. The dev-host source-IP policy remained correct (`10.10.110.233` => `99.126.115.47`, `10.10.110.226` => `70.123.224.169`), and UDP `irtt client 104.200.21.31:2112` succeeded immediately before flent. Even in that cleaner setup, ATT RRUL still came back at only `61.47 Mbps` down / `13.57 Mbps` up / `52.10 ms` ping p99, and the matching Spectrum discriminator was catastrophically degraded at `214.41 Mbps` down with `1653.18 ms` ping p99. This strengthens the conclusion that the window was still globally confounded rather than being a clean ATT-only signal.

**Operator note (2026-04-24):** A sixth rerun was captured under label `p191_1_rerun_20260424`. ATT RRUL improved to `70.95 Mbps` down / `14.40 Mbps` up / `48.62 ms` ping p99 but still missed the old `78.29 Mbps ±5%` closure lower bound of `74.38 Mbps`. ATT `tcp_12down` was within tolerance at `72.95 Mbps` versus `74.00 Mbps`, and ATT VoIP one-way p99 improved to `28.02 ms` versus `29.79 ms`. The Spectrum discriminator showed strong throughput (`343.83 Mbps`) but poor latency (`653.68 ms` ping p99). This is still not a clean Phase 191 closure sample, but it narrows the observed problem to the old ATT RRUL download comparator rather than a broad ATT service regression.

## Phase 192 Operator Waiver

Phase 191 remains open and `VALN-02 verdict: FAIL` remains the recorded Phase 191 closure verdict. The operator explicitly authorizes Phase 192 to proceed under the waiver recorded in `.planning/phases/192-reflector-scorer-blackout-awareness-and-log-hygiene/192-PRECONDITION-WAIVER.md`.

This waiver is narrow: it allows Phase 192 additive observability/log-hygiene work and its guarded canary/soak path to continue despite the unresolved Phase 191 closure artifact. It does not close Phase 191, does not change the Phase 191 comparator, and does not permit threshold/timing/state-machine changes.

## Remaining Work

1. Treat ATT as the blocking evidence set for Phase 191 closure under the current deployed ATT config.
2. Decide whether `SAFE-03` closure for Phase 191 should use the strict milestone-wide `v1.38..HEAD` comparator or the phase-local comparator, because the strict proof remains dirty from pre-existing milestone work outside this phase.
3. If closure is still desired, open follow-up work for ATT config drift:
   - decide whether `irtt.server=zylone.org` and/or `fusion.enabled=false` should remain
   - rerun ATT validation after choosing the intended ATT production config
   - keep Phase 191 evidence scoped: the root-cause probe above suggests the red ATT result is not primarily caused by Phase 191 code
4. Repeat Plan `191.1-02` under a visibly clean network window before treating any of the `2026-04-20`, `2026-04-21`, `2026-04-21b`, `2026-04-23`, or `2026-04-23c` samples as stable config/runtime evidence.
5. Post-merge only: run the 24-hour soak and compare against the pre-soak snapshot above for `TIME-03` / `TIME-04`.

## Manual Checkpoint Outcome

The manual checkpoint is no longer blocked on missing artifacts. It is now blocked on the actual evidence:

- `VALN-02` does not support a PASS verdict on ATT minimum coverage, and the fresh rerun reinforced that
- `SAFE-03` strict milestone-wide proof is still not clean

Phase 191 should not be marked complete from this verification artifact as it stands.

### Phase 191.1 update

Phase 191.1 deployed the restored ATT config under commit `d49b91469b019e4f7f7398811b902aa816a0514a` and recorded `VALN-02 verdict: FAIL`. Phase 191 therefore stays blocked. Six post-restore reruns now exist: `2026-04-20` (`63.83 Mbps`), `2026-04-21` (`74.03 Mbps`), `2026-04-21b` (`67.83 Mbps`), `2026-04-23` (`64.40 Mbps`), `2026-04-23c` (`61.47 Mbps`), and `2026-04-24` (`70.95 Mbps`). The latest `2026-04-24` sample improved ATT RRUL, kept ATT tcp_12down and VoIP effectively healthy, and showed strong Spectrum throughput with poor Spectrum latency. Phase 191 still does not close, but Phase 192 may proceed under the explicit operator waiver in `192-PRECONDITION-WAIVER.md`.
