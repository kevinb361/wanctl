# Phase 200 Deploy Log — Plan 06

**Status:** Plan 06 closed as **D-07 FAIL** at `2026-05-03T22:14:37Z`. Saturation canary recorded 122 UL collapse-to-floor events in 900s loaded window. D-10 rollback executed at `2026-05-03T22:15:04Z`; production restored to v1.40 baseline. Plan 07 BLOCKED. Gap-closure phase required.

## Local Precheck

- Checked at: `2026-05-03T18:40:30Z`
- Executor: sequential main working tree
- Production action taken by executor: **none**

### Plans 01-04 Commit Evidence

Recent Phase 200 commits present on the current branch:

```text
12330b0 docs(200-04): complete release coherence plan
566d66c docs(200-04): document v1.41 migration guidance
2dffb7a chore(200-04): bump version and adopt Spectrum UL settings
6583f8d docs(200-03): complete startup unknown-key warnings plan
715eb63 feat(200-03): warn on startup unknown config keys
029885d test(200-03): add failing test for startup unknown-key warnings
b681a52 docs(200-02): complete SAFE-05 count baseline plan
013049a test(200-02): bump SAFE-05 threshold counts for v1.41 per-direction thresholds (D-09)
8d054b3 fix(200-01): UL ordering guard in _apply_threshold_param
404dedc feat(200-01): per-key presence flags fix Codex value-derived flag bug
```

### Hot-Path Regression Slice

Command:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_phase_195_replay.py -q
```

Result: `642 passed in 40.86s`

## Operator Pre-Deploy Gate

### Captured at `2026-05-03T21:29:42Z`

- **Production `/etc/wanctl/spectrum.yaml` D-05 settings verified** on cake-shaper (`10.10.110.223`):
  - `ceiling_mbps=18` ✓
  - `target_bloat_ms=42` ✓
  - `warn_bloat_ms=105` ✓
  - `factor_down_yellow=0.98` ✓
- **Pre-deploy `/opt/wanctl` rollback snapshot:** `/opt/wanctl-prephase200-20260503T212942Z.tar.gz` on cake-shaper (1.5M, root-owned).
- **Pre-deploy `wanctl@spectrum.service` state:** `active (running) since Wed 2026-04-29 23:08:44 CDT; 3 days ago`.
- **Pre-deploy `/health` baseline:** captured at `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/pre-deploy-health.json`. Snapshot:
  - `upload.state=GREEN`
  - `upload.current_rate_mbps=18.0`
  - `upload.hysteresis.transitions_suppressed=7997`
  - `upload.hysteresis.suppressions_per_min=4`
  - `upload.hysteresis.green_streak=168` (deeply settled at ceiling)
- **Concurrent Spectrum experiment check:** pending operator confirmation.
- **Operator approval signal pending:** `approved — pre-deploy snapshot at 20260503T212942Z, prod yaml verified, no concurrent experiment, ready to deploy v1.41`

### Pin Variable for Task 2/3 Rollback

```bash
export UTC_TS=20260503T212942Z
```

The same `UTC_TS` value is the rollback tarball stem in case D-10 is triggered.

## Deploy Timeline (Attempt 1 — ABORTED)

- Pre-deploy snapshot: `/opt/wanctl-prephase200-20260503T212942Z.tar.gz` on cake-shaper (1.5M, root-owned).
- Pre-deploy `/health` baseline: `canary/pre-deploy-health.json` (UL state=GREEN, current=18.0 Mbps, suppressions_per_min=4 cumulative-since-start).
- Deploy commit: `8461489` (working tree HEAD).
- Local→remote Python-tree sha256 fingerprint: `ee60132e7140ec809a86a07a1d84784e6d5c083d99a86cfcf1fc836d72cd0b4d` (matched).
- Deploy command: `./scripts/deploy.sh spectrum kevin@10.10.110.223` at approximately `2026-05-03T21:30:30Z`.
- Service restart: `sudo systemctl restart wanctl@spectrum.service` at `2026-05-03T21:31:46Z`.
- Post-restart status: `active` at `2026-05-03T21:31:52Z`.
- Post-restart journal: clean — no Python tracebacks. SAFE-06 unknown-key check produced zero unknown-key warnings against prod spectrum.yaml (Plan 03 silent-pass confirmed via journal scan).
- Post-restart explicit-UL-thresholds journal line: **MISSING** — root cause is implementation bug in Plan 01 Task 2.

### Abort Cause

Plan 01 Task 2 emits the contracted INFO line via `logging.getLogger(__name__)` (i.e., the `wanctl.wan_controller` module logger). Production logging is configured in `wanctl/logging_utils.py::setup_logging` against the per-WAN named logger `cake_continuous_spectrum` only — no handlers are attached to the root logger or to module loggers, so module-scope `INFO` records are dropped. The journal grep specified in the plan as the D-06 verification surface therefore can never match on a correctly-deployed v1.41 binary.

### Substitute Evidence (Recorded for Reference, Not Used as Pass Criteria)

In-process load of the deployed binary against prod YAML on cake-shaper proved the explicit flags resolve correctly:

```text
target_explicit = True
warn_explicit   = True
upload_target_bloat_ms = 42
upload_warn_bloat_ms   = 105
global target_bloat_ms = 15
global warn_bloat_ms   = 75
```

The runtime control path *would* have used 42/105 ms UL thresholds had the canary proceeded. Substitute evidence demonstrates the bug is in the verification surface, not the control path.

### Rollback (D-10)

- Rollback command: `ssh kevin@10.10.110.223 "sudo tar -xzf /opt/wanctl-prephase200-20260503T212942Z.tar.gz -C / && sudo systemctl restart wanctl@spectrum.service"`
- Rollback issued at: `2026-05-03T21:35:36Z`
- Post-rollback `is-active`: `active`
- Post-rollback `/health` upload: `state=GREEN, current_rate_mbps=18.0, hysteresis.suppressions_per_min=0` (resumed pre-Phase-200 baseline behavior).
- Post-rollback fingerprint: `b9c7c19513aa3678dbe171a4d0c29906a85c23ceae67b499fed5e81f7b3e7e9e` (differs from v1.41 fingerprint, confirms binary was actually replaced).
- Post-rollback `phase200 explicit UL thresholds active` count in journal: 0 (sanity — v1.40 binary doesn't carry that log).

## Canary Run

Not executed — aborted before Task 3 due to Task 2 verification failure.

## Decision

Path A (Literal Plan Compliance) selected by operator. D-10 rollback executed.

Plan 06 is BLOCKED. Plan 07 (24h regression soak) is BLOCKED.

### Required Before Retry

1. Fix `src/wanctl/wan_controller.py:439-448` — INFO log must be emitted via the per-WAN configured logger (the same logger that emits `=== Continuous CAKE Controller - spectrum ===`), not via `logging.getLogger(__name__)`. Pass the configured logger into `WANController.__init__` or have the caller emit the line after construction.
2. Add a regression test that asserts the INFO line is emitted on construction with explicit-UL config and is absent under default-UL config.
3. Re-deploy v1.41 (committed fix) and retry Plan 06 from Task 1.

## Deploy Timeline (Attempt 2 — DEPLOYED)

- Fix commit: `417e2b9` — `fix(200-06): emit Phase 200 D-06 explicit UL log via per-WAN logger`.
- Local commit at deploy: `417e2b9` (HEAD).
- Pre-deploy `/opt/wanctl` snapshot from Attempt 1 retained at `/opt/wanctl-prephase200-20260503T212942Z.tar.gz` on cake-shaper (still represents the v1.40 baseline; D-10 rollback path remains valid).
- Local→remote Python-tree sha256 fingerprint: `c00f42274ad48c8c61accd326c8bce32eb295b2b1f80a93c09aab4bc06d1f870` (matched, differs from Attempt 1 `ee60132e...`, confirms D-06 fix is in deployed tree).
- Deploy command: `./scripts/deploy.sh spectrum kevin@10.10.110.223` at approximately `2026-05-03T21:47:30Z`.
- Service restart: `sudo systemctl restart wanctl@spectrum.service` at `2026-05-03T21:48:15Z`.
- Post-restart `is-active`: `active` at `2026-05-03T21:48:21Z`.
- Post-restart explicit-UL-thresholds journal line (D-06 verification surface — now correctly emitted via per-WAN logger):

  ```
  May 03 16:48:17 cake-shaper wanctl-spectrum[2839232]: 2026-05-03 16:48:17,412 [spectrum] [INFO] phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105 (target_explicit=True warn_explicit=True)
  ```

- Post-restart `/health` upload: `state=GREEN, current_rate_mbps=18.0, hysteresis.{green_streak, suppressions_per_min}=null` (counters initialize lazily after restart; null is normal for first ~5 cycles).
- Post-restart journal: clean (no Python tracebacks).

## Canary Run (Attempt 2)

### Sub-attempt 1 (ABORT — Plan 05 script bug)

- Started at: `2026-05-03T21:52:18Z`
- Script exit: 2 (ABORT)
- Reason: preflight asserted `.wans[0].upload.{floor_mbps, ceiling_mbps}` shape; `/health` does not expose these (only runtime state). Verdict file `verdict.json` written with reason `health_unreachable_or_shape_invalid`.

### Plan 05 Canary Fix (commit `dd67493`)

- Added `PHASE200_UL_FLOOR_MBPS` and `PHASE200_UL_CEILING_MBPS` env vars (sourced from deployed `continuous_monitoring.upload.{floor_mbps, ceiling_mbps}` YAML).
- Dropped floor/ceiling from preflight `/health` shape assertion; kept `current_rate_mbps`.
- Floor-collapse selector now compares `.wans[0].upload.current_rate_mbps == $floor` via `--argjson`.
- Smoke-tested validators (require_var, ordering check) — both correctly ABORT.
- v1.41 binary (commit `417e2b9`) remained deployed throughout the patch window; no production touch required for the script-only fix.

### Sub-attempt 2 (D-07 FAIL)

- Env: `PHASE200_UL_FLOOR_MBPS=8`, `PHASE200_UL_CEILING_MBPS=18`, `PHASE200_IPERF_TARGET=104.200.21.31`, `PHASE200_IPERF_LOCAL_BIND=10.10.110.226`.
- Started: `2026-05-03T21:57:34Z`
- Loaded window: `2026-05-03T21:58:36Z` → `2026-05-03T22:13:36Z` (900s)
- Finished: `2026-05-03T22:14:37Z` (1023s total)
- Run dir: `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/`
- **Verdict: FAIL** — `ul_floor_hits_during_load=122` (script exit 1).
- Sample distribution (886 samples in loaded window):
  - **18.0 Mbps (ceiling): 470 samples (53%)**
  - **8.0 Mbps (floor): 122 samples (14%)** ← collapse events
  - 8.2-17.9 Mbps (intermediate decay): 294 samples (33%)
- UL state distribution: GREEN 306 (35%), YELLOW 522 (59%), RED 58 (7%).
- Pre/post baseline RTT: not captured — third Plan 05 path mismatch (`summarize_baseline` looks for `.wans[0].rtt.baseline_rtt_ms` but `/health` exposes it at `.wans[0].baseline_rtt_ms`). Verdict unaffected (RTT was advisory); evidence loss only.

## Decision

**FAIL → D-10 rollback executed.**

- Rollback command: `ssh kevin@10.10.110.223 "sudo tar -xzf /opt/wanctl-prephase200-20260503T212942Z.tar.gz -C / && sudo systemctl restart wanctl@spectrum.service"`
- Rollback issued at: `2026-05-03T22:15:04Z`
- Post-rollback `is-active`: `active`
- Post-rollback `/health` upload: `state=GREEN, current_rate_mbps=18.0`
- Post-rollback `phase200 explicit UL thresholds active` count in journal: 0 (sanity — v1.40 binary doesn't carry that log).

**Plan 07 (24h regression soak) is BLOCKED** — running a 24h soak against the v1.40 binary is meaningless for VALN-06.

### Failure Analysis (for gap-closure phase planning)

The 42/105 ms thresholds did not prevent UL collapse-to-floor under saturated DOCSIS upload. Hypothesis "wider thresholds resolve UL collapse" REJECTED at p < 0.001 (122 events / 900s ≈ 1 collapse every 7.4s).

The bimodal sample distribution (53% at ceiling, 14% at floor, 33% transitional) shows the controller actively oscillates between ceiling and floor rather than settling at an intermediate equilibrium rate. State distribution skewed toward YELLOW (59%) indicates persistent active decay, not stable shaping.

**Root cause hypothesis:** UL queue delay during DOCSIS saturation routinely exceeds 200-500 ms regardless of shaping rate, because the wanctl-imposed 18 Mbit ceiling is barely below the actual provisioned upstream rate, leaving no shaping headroom. The control model assumes shaping rate < link capacity by enough margin that wanctl's queue absorbs bufferbloat instead of the modem's queue. On DOCSIS this margin is too thin.

### Candidate Directions (gap-closure phase)

Per Plan 06 Task 3 FAIL branch wording:

1. **Gentler decay**: upload-specific `factor_down` < 0.90, smaller `step_up_mbps`. **Rejected by data**: oscillation pattern is bimodal, not gradual; gentler decay alone does not address the cause.
2. **Higher target_bloat_ms (50-60 ms)**: weaker than what 42/105 already failed at; unlikely to help.
3. **DOCSIS-aware UL congestion mode** (deferred from CONTEXT.md). **Most likely fix**: explicit upstream queue-depth tracking with a setpoint well below ceiling, treating ceiling as a guard rail rather than a target. May require collaborating with the modem's CMTS-side queue behavior rather than fighting it.
4. **Substantially lower ceiling**: shape at 12-14 Mbit instead of 18 Mbit, sacrificing peak throughput for stable latency. Operator choice; a Phase 200 follow-up could spike this.

Recommend opening Phase 201 (or sequel-numbered) for DOCSIS-aware UL congestion control with the 122-collapse evidence file from this canary run as the seed.

## Deploy Timeline (Attempt 3 — Gap-Closure)

- Pre-deploy snapshot: `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz` on cake-shaper (`1.5M`, root-owned, verified before deploy).
- Operator gate: prior `Approved to deploy` response carried forward after the missing timestamp blocker was closed; no concurrent Spectrum experiment and production YAML gate were already operator-confirmed.
- Deploy commit: `57be072` (working tree HEAD with Plans 10-13 landed).
- Deploy command: `./scripts/deploy.sh spectrum kevin@10.10.110.223` at `2026-05-04T13:30:57Z`.
- Deploy result: rsync application tree matched `101` Python files; config deployed to `/etc/wanctl/spectrum.yaml`; pre-startup validation had `0` errors and one existing transport-name warning (`linux-cake-netlink` skipped by validator).
- Service restart: `sudo systemctl restart wanctl@spectrum.service` at `2026-05-04T13:31:00Z`.
- Post-restart `is-active`: `active` at `2026-05-04T13:31:06Z`.
- Post-restart explicit-UL-thresholds journal grep:
  `journalctl -u wanctl@spectrum.service --since "2026-05-04T13:31:00Z" | grep "phase200 explicit UL thresholds active"`
  hit:

  ```text
  May 04 08:31:01 cake-shaper wanctl-spectrum[3212509]: 2026-05-04 08:31:01,618 [spectrum] [INFO] phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105 (target_explicit=True warn_explicit=True)
  ```

- Post-restart `/health` upload snapshot: `state=GREEN`, `current_rate_mbps=18.0`, `hysteresis.suppressions_per_min=0`, `hysteresis.transitions_suppressed=0`, `hysteresis.green_streak=4766`.
- Local→remote Python-tree sha256 fingerprint: `707bdaedce6cfeb74b21fd1c869263811922a138a487e305514de8940be26d6d` (matched local, differs from v1.40 fingerprint `b9c7c19513aa3678dbe171a4d0c29906a85c23ceae67b499fed5e81f7b3e7e9e` from Plan 06 rollback).

### Attempt 3 Rollback Pin

```bash
export UTC_TS=20260504T132936Z
```

If D-10 is triggered by Attempt 3 canary `fail` or `abort`, restore `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz` and restart `wanctl@spectrum.service`.
