---
phase: 201-docsis-aware-ul-congestion-control
plan: 15
type: execute
wave: 11
depends_on: [13, 14]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/loaded_capture.ndjson
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/idle_capture.ndjson
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/build-identity.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
  - src/wanctl/__init__.py
  - pyproject.toml
  - docker/Dockerfile
  - CHANGELOG.md
autonomous: false
gap_closure: true
revision: 3  # Round-3 revision — closes codex 201-REVIEWS.md round-2 NEW-HIGH-1 (rollback YAML composition bug, fix via two-snapshot rollback strategy), MEDIUM-CODEX-3 (PARTIALLY-CLOSED, /health active-knob assertion via fields wired in 201-13 rev 3), and LOW/MEDIUM-NEW-3 (version bump on all surfaces, not just src/wanctl/__init__.py).
revision_driver: "201-REVIEWS.md round 2 — closes NEW-HIGH-1 (two-snapshot rollback strategy: snapshot A pre-reconcile clean for rollback target, snapshot B post-gate candidate for deploy evidence only), MEDIUM-CODEX-3 (canary preflight greps /health for red_decay_step_pct + red_decay_delta_max_pct as live-wiring proof — fields are wired by Plan 201-13 rev 3), and LOW/MEDIUM-NEW-3 (version 1.42.0 -> 1.42.1 in src/wanctl/__init__.py, pyproject.toml, docker/Dockerfile LABEL version, build-identity.json, AND validated via /health.version)."
requirements: [VALN-06]
tags: [phase-201, gap-closure, canary, valn-06-primary, recanary, operator-gated, fail-closed, codex-revised, codex-round-3, two-snapshot-rollback]

must_haves:
  truths:
    - "Re-canary runs at the ORIGINAL setpoint_mbps=12 (NOT A5 fallback setpoint=10) — the operator-confirmed closure path is the control-model amendment, not the setpoint workaround"
    - "**REV 3 (codex LOW/MEDIUM-NEW-3):** Version is bumped to 1.42.1 in ALL version surfaces BEFORE deploy: src/wanctl/__init__.py (`__version__`), pyproject.toml (`version =`), docker/Dockerfile (`LABEL version=`), build-identity.json (generated at canary-time), and validated via /health.version returning '1.42.1' in canary preflight. Split surfaces (e.g., pyproject says 1.42.1 but Dockerfile says 1.42.0) constitute split evidence and FAIL the preflight."
    - "build-identity.json captures git SHA + version + build_utc at canary-time so the canary evidence binds to the exact source tree, not just the version string"
    - "Re-canary uses the existing scripts/phase200-saturation-canary.sh extended in Plan 201-08; no new harness authored"
    - "**REV 3 (codex NEW-HIGH-1) — TWO-SNAPSHOT ROLLBACK STRATEGY.** The rollback YAML composition bug from rev 2 is fixed by capturing TWO snapshots in a strict ordering: **Snapshot A (rollback-clean)** is captured BEFORE any Phase 201 YAML is reconciled into /etc/wanctl/spectrum.yaml. Snapshot A is the rollback target. Verification: `grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' <snapshot_A>` returns 0 (no Phase 201 keys present). **Snapshot B (post-gate candidate)** is captured AFTER predeploy gate PASS (i.e., after configs/spectrum.yaml has been reconciled into /etc/wanctl/spectrum.yaml). Snapshot B holds the candidate Phase 201 YAML and is used as deploy evidence ONLY — it is NEVER used as a rollback target. The strict ordering: snapshot A -> predeploy gate -> reconcile Phase 201 YAML -> snapshot B -> deploy."
    - "Pre-deploy snapshot pair: /opt/wanctl binary archive AND /etc/wanctl/spectrum.yaml — captured at the snapshot-A moment for rollback-clean state, captured AGAIN at the snapshot-B moment for deploy evidence."
    - "PRIMARY GATE: floor_hit_cycles_total_delta_loaded_window == 0 (zero-tolerance, REVIEWS HIGH-5 cycle-fidelity counter)"
    - "SECONDARY GATE: ul_floor_hits_during_load == 0 (1Hz cross-check; disagreement with primary produces FAIL with diagnostic reason, not PASS)"
    - "Loaded-window NDJSON capture includes the diagnostic fields landed in Plan 201-13 rev 3 (max_delay_delta_us, red_streak, zone_trace, headroom_exhausted_streak, anti_windup_cycles, anti_windup_triggers, **red_decay_step_pct, red_decay_delta_max_pct**) — confirmed by jq inspection of any captured row"
    - "**REV 3 (codex MEDIUM-CODEX-3 closure) — ACTIVE CONTROL KNOB ASSERTION via /health.** Post-deploy /health probe explicitly asserts the rev-4 Plan 201-14 control parameters are LIVE in the running constructor (not stale defaults from a wiring bug). Per Plan 201-13 rev 3, /health.wans[0].upload now exposes `red_decay_step_pct` and `red_decay_delta_max_pct` as runtime-state echoes (live `self._red_decay_step_pct` / `self._red_decay_delta_max_pct` values). The preflight assertion: `red_decay_step_pct == 0.02` AND `red_decay_delta_max_pct == 0.10` AND `anti_windup_cycles == 60`, ALL via /health (not via SSH grep of YAML — YAML grep proves text presence, /health proves runtime wiring). Deployed-YAML SSH grep is retained as a SECONDARY check; both must agree."
    - "On FAIL: rollback executes per D-10; both binary AND YAML restored from **Snapshot A (rollback-clean)** (codex NEW-HIGH-1 — never from Snapshot B); verified by post-rollback /health.version=1.39.0 AND grep counts of all Phase 201 YAML keys == 0 in /etc/wanctl/spectrum.yaml"
    - "On PASS: Plan 201-16 (24h soak) is unblocked; 201-15-CANARY-VERDICT.md records verdict=pass, primary_gate=0, captures floor_hit_cycles_total_loaded_window_end as the T+0 baseline for the soak"
    - "Canary verdict.json schema-compatible with 201-11 verdict.json (same fields, same primary_gate identifier)"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
      provides: "Canonical re-canary verdict; primary_gate value, secondary_gate value, baseline RTT bookends, env capture, rollback decision"
      contains: "primary_gate"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/build-identity.json
      provides: "Git SHA + version 1.42.1 + build_utc — codex MEDIUM-CODEX-4/LOW-NEW-3 evidentiary binding"
      contains: "git_sha"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
      provides: "Operator-readable verdict; includes active-control-knob assertion table (via /health) AND two-snapshot rollback timeline"
      contains: "VALN-06"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json"
      to: ".planning/phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md"
      via: "verdict=pass unblocks soak; verdict=fail blocks soak and triggers next gap-closure cycle"
      pattern: "primary_gate"
    - from: "scripts/phase201-predeploy-gate.sh"
      to: "/etc/wanctl/spectrum.yaml on cake-shaper"
      via: "SSH probe + reconcile-or-block on residual rejected v1.41 keys; Snapshot A taken BEFORE reconcile, Snapshot B taken AFTER reconcile"
      pattern: "predeploy-gate"
    - from: "Snapshot A (rollback-clean YAML, no Phase 201 keys)"
      to: "rollback target on FAIL"
      via: "ssh cake-shaper sudo cp /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapA /etc/wanctl/spectrum.yaml"
      pattern: "snapA"
---

<objective>
**Gap-closure Plan 3 of 4. OPERATOR-GATED CHECKPOINT. Revision 3 — closes codex round-2 NEW-HIGH-1 (rollback YAML composition bug), MEDIUM-CODEX-3 PARTIALLY-CLOSED (active-knob proof via /health), and LOW/MEDIUM-NEW-3 (version bump on all surfaces).**

Re-run the Phase 201 saturation canary at `setpoint_mbps=12` against the **v1.42.1** binary that contains the Plan 201-13 rev 3 diagnostic fields and the Plan 201-14 rev 4 control-model amendment.

This plan is the closure proof for the primary VERIFICATION.md gap. **Three round-3 changes from rev 2:**

1. **NEW-HIGH-1 — Two-snapshot rollback strategy.** Rev 2 captured the rollback snapshot AFTER predeploy-gate PASS, AFTER Phase 201 YAML had been reconciled into `/etc/wanctl/spectrum.yaml`. The snapshot therefore contained Phase 201 keys, contradicting Task 6 verification expecting zero Phase 201 keys post-rollback. Rev 3 fixes this by capturing TWO snapshots:

   - **Snapshot A (rollback-clean):** captured BEFORE any reconcile happens. Files: `/opt/wanctl-prephase201-recanary-<TS>-snapA.tar.gz` and `/etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapA`. Snapshot A contains the v1.39.0 binary AND the legacy YAML (no Phase 201 keys). Snapshot A is the rollback target on FAIL. Verification: `grep -cE '^[[:space:]]+(<phase-201-keys>):' <snapA-yaml>` returns 0.

   - **Snapshot B (post-gate candidate):** captured AFTER predeploy gate PASS (after Phase 201 YAML reconciled). Files: `<...>-snapB.tar.gz` and `<...>-snapB`. Snapshot B contains the v1.39.0 binary AND the candidate Phase 201 YAML (legitimate keys). Snapshot B is used for deploy evidence ONLY (proves what the deploy started from); it is NEVER a rollback target.

   Strict ordering enforced by Task 3:
   ```
   1. Snapshot A (rollback-clean: legacy binary + legacy YAML)
   2. Run predeploy gate (may BLOCK on residual v1.41 keys)
   3. If BLOCK: reconcile by overwriting /etc/wanctl/spectrum.yaml from configs/spectrum.yaml; re-run gate; loop until PASS
   4. Snapshot B (post-gate-PASS candidate: legacy binary + reconciled Phase 201 YAML)
   5. Deploy v1.42.1 binary
   ```

   Task 6 (FAIL path) restores from Snapshot A explicitly: `tar -xzf <...>-snapA.tar.gz` and `cp <...>-snapA /etc/wanctl/spectrum.yaml`. Acceptance criteria reference snapshot A by name.

2. **MEDIUM-CODEX-3 PARTIALLY-CLOSED — Active-knob proof via /health.** Rev 2's preflight asserted `anti_windup_cycles == 60` via /health (Plan 201-13 rev 2 wired that field) but the two `red_decay_*_pct` floats only via SSH grep of YAML. Codex correctly noted YAML grep proves text presence, not live wiring. Rev 3 closes this: Plan 201-13 rev 3 wires `red_decay_step_pct` and `red_decay_delta_max_pct` as runtime-state echoes in /health.wans[0].upload, AND this plan's Task 3 preflight asserts BOTH values via `/health` (with the YAML SSH grep retained as a SECONDARY agreement check; both must match the deployed values).

3. **LOW/MEDIUM-NEW-3 — Version bump on all surfaces.** Rev 2 only bumped `src/wanctl/__init__.py`. If `pyproject.toml` or `docker/Dockerfile` still says `1.42.0`, the evidence is split. Rev 3 bumps version 1.42.0 → 1.42.1 in ALL surfaces:
   - `src/wanctl/__init__.py` (`__version__ = "1.42.1"`)
   - `pyproject.toml` (`version = "1.42.1"`)
   - `docker/Dockerfile` (`LABEL version="1.42.1"`)
   - `build-identity.json` (generated at canary-time; carries the literal string from `__version__`)
   - **Validated via /health.version** returning `"1.42.1"` in canary preflight (Task 3 step 6).

   Task 1 greps each surface FIRST and only updates surfaces that exist; if a surface is absent (e.g., Dockerfile lacks LABEL version), Task 1 skips it but logs the skip in the commit message.

Per CONTEXT.md D-11: reuse `scripts/phase200-saturation-canary.sh`. Per Plan 201-08: extended for env-cross-check and counter-delta verdict-decision. Per Plan 201-07: predeploy gate is in place. Per D-10: rollback restores both binary AND YAML.

The re-canary uses the EXACT same env vars as 201-11 (preserve evidentiary continuity) — only the binary on cake-shaper changes (Plans 201-13 rev 3 + 201-14 rev 4 land new code; version becomes 1.42.1).

Output: a `canary/<TIMESTAMP>/` directory with verdict.json, loaded_capture.ndjson, idle_capture.ndjson, build-identity.json, and a 201-15-CANARY-VERDICT.md operator-readable summary that includes a two-snapshot rollback timeline section AND an active-control-knob assertion table grepping /health.

This plan is `autonomous: false` because it deploys to production and may rollback. The operator MUST approve at the predeploy checkpoint and the post-canary checkpoint.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-canary-execution-PLAN.md
@scripts/phase200-saturation-canary.sh
@scripts/phase201-predeploy-gate.sh
@scripts/deploy.sh
</context>

<interfaces>
<!-- The canary contract is FIXED by Plan 201-08. This plan invokes; it does not modify the script. -->

Required env (verbatim from 201-11):
```
PHASE200_OUT_DIR=.planning/phases/201-docsis-aware-ul-congestion-control
PHASE200_SPECTRUM_HEALTH_URL=http://10.10.110.223:9101/health
PHASE200_IPERF_TARGET=104.200.21.31
PHASE200_IPERF_LOCAL_BIND=10.10.110.226
PHASE200_UL_FLOOR_MBPS=8
PHASE200_UL_CEILING_MBPS=18
PHASE200_REMOTE_YAML_SSH=cake-shaper:/etc/wanctl/spectrum.yaml
PHASE201_DOCSIS_MODE=true
PHASE201_SETPOINT_MBPS=12
```

**Two-snapshot rollback ordering (codex NEW-HIGH-1):**

```
T0:  snapshot A (legacy state — rollback-clean)
        - /opt/wanctl  -> /opt/wanctl-prephase201-recanary-<TS>-snapA.tar.gz
        - /etc/wanctl/spectrum.yaml -> /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapA
        - VERIFY snapA YAML has 0 Phase 201 keys

T1:  predeploy gate run #1
        - if PASS: skip to T3 (no reconcile needed)
        - if BLOCK: continue to T2

T2:  reconcile YAML
        - scp configs/spectrum.yaml cake-shaper:/tmp/spectrum.yaml.new
        - ssh cake-shaper "sudo install -o root -g wanctl -m 0640 /tmp/spectrum.yaml.new /etc/wanctl/spectrum.yaml"
        - re-run predeploy gate -> must PASS

T3:  snapshot B (post-gate-PASS candidate state)
        - /opt/wanctl  -> /opt/wanctl-prephase201-recanary-<TS>-snapB.tar.gz
        - /etc/wanctl/spectrum.yaml -> /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapB
        - snapB YAML now contains Phase 201 keys (the candidate); deploy evidence only

T4:  deploy v1.42.1 binary
        - REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
        - ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"

ON FAIL:
  - tar -xzf <...>-snapA.tar.gz -C /         # restore legacy binary from snapshot A
  - cp <...>-snapA /etc/wanctl/spectrum.yaml  # restore legacy YAML from snapshot A
  - VERIFY post-rollback /health.version == 1.39.0 AND Phase 201 YAML key count == 0
```

Predeploy gate (Plan 201-07): runs at T1 (BEFORE snapshot B). On BLOCK at T1, operator reconciles at T2, gate re-runs.

Deploy invocation (201-11 verbatim, executed at T4):
```
REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
ssh cake-shaper sudo systemctl restart wanctl@spectrum.service
```

Verdict.json primary gate field (Plan 201-08): `primary_gate: "floor_hit_cycles_total_delta_loaded_window"`, `primary_gate_value: <int>`. PASS only if `primary_gate_value == 0` AND `ul_floor_hits_during_load == 0`. Disagreement = FAIL.

**Active control knob assertion (codex MEDIUM-CODEX-3, fully closed in rev 3 via Plan 201-13 rev 3 fields):** post-deploy /health must show:
- `version == "1.42.1"` (codex MEDIUM-CODEX-4 / LOW-NEW-3)
- `wans[0].upload.docsis_mode_active == true`
- `wans[0].upload.setpoint_mbps == 12.0`
- `wans[0].upload.anti_windup_cycles == 60` (Plan 201-13 echoes this YAML key)
- `wans[0].upload.anti_windup_triggers` is present and an int (may be 0)
- `wans[0].upload.headroom_exhausted_streak` is present and an int
- **`wans[0].upload.red_decay_step_pct == 0.02`** (REV 3 — Plan 201-13 rev 3 active-knob, codex MEDIUM-CODEX-3 closure)
- **`wans[0].upload.red_decay_delta_max_pct == 0.10`** (REV 3 — Plan 201-13 rev 3 active-knob, codex MEDIUM-CODEX-3 closure)

PLUS via SSH grep of `/etc/wanctl/spectrum.yaml` (SECONDARY agreement check): same five rev-4/rev-3 keys present at YAML-key positions. The two surfaces (live /health + deployed YAML) must AGREE on `red_decay_step_pct=0.02`, `red_decay_delta_max_pct=0.10`, `anti_windup_cycles=60`. Disagreement signals a wiring failure → ABORT.
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Bump version to 1.42.1 in ALL surfaces (src/wanctl/__init__.py, pyproject.toml, docker/Dockerfile LABEL); commit (codex LOW/MEDIUM-NEW-3)</name>
  <read_first>
    - src/wanctl/__init__.py (current __version__ value)
    - pyproject.toml (look for `version =` line)
    - docker/Dockerfile (look for `LABEL version=` or `ARG VERSION=` or absence)
    - CHANGELOG.md (latest version section)
  </read_first>
  <files>src/wanctl/__init__.py, pyproject.toml, docker/Dockerfile, CHANGELOG.md</files>
  <action>
    Codex LOW/MEDIUM-NEW-3 fix: avoid split version evidence (one surface 1.42.1, another 1.42.0).

    1. **Pre-grep all surfaces** to inventory which exist:
       ```
       grep -nE '__version__' src/wanctl/__init__.py
       grep -nE '^version' pyproject.toml
       grep -nE 'LABEL version|ARG VERSION' docker/Dockerfile || echo "NO_VERSION_SURFACE_IN_DOCKERFILE"
       ```
       Record each surface's current value before edit. If Dockerfile lacks any version surface, skip step 4 and note the skip in the commit message.

    2. **src/wanctl/__init__.py**: Bump `__version__ = "1.42.0"` → `__version__ = "1.42.1"`.

    3. **pyproject.toml**: Bump the `version = "1.42.0"` line under `[project]` (or wherever it currently lives) to `version = "1.42.1"`. Use `grep -n "^version" pyproject.toml` to locate first.

    4. **docker/Dockerfile**: If the pre-grep found `LABEL version="1.42.0"` (current state — confirmed at planning time), bump to `LABEL version="1.42.1"`. If `ARG VERSION=` exists, bump that too. If NO version surface exists in Dockerfile, skip and document.

    5. **CHANGELOG.md**: Add a `## 1.42.1` section above `## 1.42.0`:
       ```markdown
       ## 1.42.1 — 2026-05-XX

       ### Fixed
       - Phase 201 gap-closure (rev 4): bounded-absolute RED decay + anti-windup cap-and-clamp + config validators. See Plan 201-14 / canary <RECANARY_TS>.
       - Phase 201 rev-3 evidentiary distinguishability (codex LOW/MEDIUM-NEW-3): version bumped on all surfaces (src/wanctl/__init__.py, pyproject.toml, docker/Dockerfile LABEL).
       ```

    6. **Commit:** `chore(201-15): bump version to 1.42.1 across all surfaces (codex LOW/MEDIUM-NEW-3 + MEDIUM-CODEX-4 evidentiary distinguishability)`.

    7. Run hot-path slice to confirm no test relies on the literal `"1.42.0"` string:
       ```
       .venv/bin/pytest -o addopts='' tests/test_health_check.py -q
       ```
  </action>
  <verify>
    <automated>grep -q '__version__ = "1.42.1"' src/wanctl/__init__.py</automated>
    <automated>grep -qE '^version[[:space:]]*=[[:space:]]*"1\.42\.1"' pyproject.toml</automated>
    <automated>(grep -qE 'LABEL version="1\.42\.1"' docker/Dockerfile) || (! grep -qE 'LABEL version|ARG VERSION' docker/Dockerfile && echo "Dockerfile has no version surface; skipped per Task 1 step 1 fallback")</automated>
    <automated>grep -q "## 1.42.1" CHANGELOG.md</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `src/wanctl/__init__.py` shows `__version__ = "1.42.1"`
    - `pyproject.toml` shows `version = "1.42.1"`
    - `docker/Dockerfile` shows `LABEL version="1.42.1"` (current Dockerfile has `LABEL version="1.42.0"` per planning-time grep)
    - CHANGELOG.md has a `## 1.42.1` section that mentions both Plan 201-14 rev 4 and the codex LOW/MEDIUM-NEW-3 evidentiary fix
    - test_health_check.py passes (no test brittle on the literal old version)
    - Commit recorded with surface inventory in commit message
    - **Negative criterion:** `grep -rE '"1\.42\.0"' src/wanctl/__init__.py pyproject.toml docker/Dockerfile | grep -v '^#' | wc -l` returns 0 (no surface still says 1.42.0)
  </acceptance_criteria>
  <done>
    Version bumped on all three surfaces; CHANGELOG updated; binary built from this tree will report 1.42.1 in /health, AND `cat pyproject.toml` will show 1.42.1, AND `docker image inspect` will show LABEL 1.42.1.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Predeploy approval — verify Plans 201-13 rev 3 + 201-14 rev 4 landed, version=1.42.1 on all surfaces, tests green; operator confirms re-canary go</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
    - configs/spectrum.yaml (verify red_decay_step_pct + red_decay_delta_max_pct + anti_windup_cycles present; sustained_red_cycles ABSENT)
    - src/wanctl/__init__.py, pyproject.toml, docker/Dockerfile (verify all show 1.42.1)
  </read_first>
  <what-built>
    Plans 201-13 rev 3, 201-14 rev 4, and Task 1 of this plan must be complete:
    - 201-13 rev 3: /health.wans[0].upload exposes max_delay_delta_us, red_streak, zone_trace, headroom_exhausted_streak, anti_windup_cycles, anti_windup_triggers, **red_decay_step_pct, red_decay_delta_max_pct** (codex MEDIUM-CODEX-3 active-knob proof). No sustained_red_cycles.
    - 201-14 rev 4: queue_controller has bounded-absolute RED decay (Option B) with rev-4 invariant wording, integral anti-windup cap-and-clamp with synchronous headroom_state recompute, rate-limited logging, codex MEDIUM-NEW-2 validators rejecting unsafe red-decay knobs at config-load. SAFE-05 byte-identity preserved. Cycle-1-18 table test green.
    - configs/spectrum.yaml has explicit `red_decay_step_pct: 0.02`, `red_decay_delta_max_pct: 0.10`, `anti_windup_cycles: 60` under continuous_monitoring.upload. `sustained_red_cycles` ABSENT.
    - Version is 1.42.1 in src/wanctl/__init__.py AND pyproject.toml AND docker/Dockerfile (codex LOW/MEDIUM-NEW-3 — all surfaces).
  </what-built>
  <how-to-verify>
    1. Confirm summaries exist:
       ```
       ls .planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
       ls .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
       ```

    2. Confirm version bump on ALL surfaces (codex LOW/MEDIUM-NEW-3):
       ```
       grep '__version__' src/wanctl/__init__.py
       grep '^version' pyproject.toml
       grep -E 'LABEL version|ARG VERSION' docker/Dockerfile
       ```
       Each must show `1.42.1`.

    3. Confirm hot-path slice green:
       ```
       .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_check_config.py -q
       ```

    4. Confirm new YAML keys present, deleted key absent:
       ```
       grep -E "red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles" configs/spectrum.yaml
       grep -E "sustained_red_cycles" configs/spectrum.yaml | grep -v '^#'
       ```
       First grep must show 3 matches; second must be empty.

    5. Confirm cycle-1-18 table test green specifically:
       ```
       .venv/bin/pytest -o addopts='' tests/test_queue_controller.py::TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table -v
       ```

    6. Confirm codex MEDIUM-NEW-2 validators present:
       ```
       .venv/bin/pytest -o addopts='' tests/test_autorate_config.py::TestRedDecayValidators tests/test_check_config.py::TestCheckConfigRedDecayValidators -v
       ```

    7. Operator decides: proceed with re-canary at setpoint_mbps=12, or hold for additional review.
  </how-to-verify>
  <resume-signal>Type "approved" to proceed to Task 3 (snapshot A → predeploy gate → snapshot B → deploy), or describe blockers.</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved"
    - Both prerequisite SUMMARY files exist
    - All three version surfaces show `1.42.1`
    - Hot-path slice exits 0
    - Cycle-1-18 table test passes
    - codex MEDIUM-NEW-2 validator boundary tests pass on both autorate_config + check_config surfaces
    - configs/spectrum.yaml has new keys; `sustained_red_cycles` absent
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 3: Snapshot A (rollback-clean) FIRST → predeploy gate → reconcile if blocked → Snapshot B (post-gate candidate) → deploy v1.42.1; verify /health version + all rev-4 active control knobs via /health</name>
  <read_first>
    - scripts/phase201-predeploy-gate.sh
    - scripts/deploy.sh
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md (Pre-deploy Reconciliation section, lines 13-19)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (NEW-HIGH-1 — two-snapshot rollback strategy; MEDIUM-CODEX-3 — knob verification via /health; MEDIUM-CODEX-4 / LOW-NEW-3 — version distinguishability)
  </read_first>
  <files>
    /opt/wanctl-prephase201-recanary-&lt;TS&gt;-snapA.tar.gz (on cake-shaper, PRE-reconcile rollback-clean snapshot),
    /etc/wanctl/spectrum.yaml.prephase201-recanary-&lt;TS&gt;-snapA (on cake-shaper, PRE-reconcile rollback-clean snapshot),
    /opt/wanctl-prephase201-recanary-&lt;TS&gt;-snapB.tar.gz (on cake-shaper, post-gate-PASS deploy-evidence snapshot),
    /etc/wanctl/spectrum.yaml.prephase201-recanary-&lt;TS&gt;-snapB (on cake-shaper, post-gate-PASS deploy-evidence snapshot),
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/&lt;RECANARY_TS&gt;/build-identity.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
  </files>
  <action>
    1. **Set TS variable**:
       ```
       export RECANARY_TS=$(date -u +%Y%m%dT%H%M%SZ)
       echo "Re-canary timestamp: $RECANARY_TS"
       ```

    2. **Capture build identity NOW** (codex MEDIUM-CODEX-4 / LOW-NEW-3 — git SHA captured at canary-time, version pulled from __init__.py):
       ```
       mkdir -p .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}
       BUILD_DIR=.planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}
       cat > $BUILD_DIR/build-identity.json <<EOF
       {
         "git_sha": "$(git rev-parse HEAD)",
         "git_status_clean": $(if [ -z "$(git status --porcelain)" ]; then echo true; else echo false; fi),
         "version_init_py": "$(grep '__version__' src/wanctl/__init__.py | sed -E 's/.*= "(.*)"/\1/')",
         "version_pyproject": "$(grep -E '^version' pyproject.toml | sed -E 's/.*= "(.*)"/\1/')",
         "version_dockerfile": "$(grep -E 'LABEL version' docker/Dockerfile | sed -E 's/.*version="([^"]*)".*/\1/' || echo 'NO_LABEL')",
         "build_utc": "$(date -u -Iseconds)",
         "recanary_ts": "${RECANARY_TS}"
       }
       EOF
       cat $BUILD_DIR/build-identity.json
       jq -e '.version_init_py == "1.42.1" and .version_pyproject == "1.42.1"' $BUILD_DIR/build-identity.json
       ```

    3. **SNAPSHOT A — rollback-clean state, BEFORE any reconcile** (codex NEW-HIGH-1 step 1):
       ```
       echo "=== T0: Snapshot A (rollback-clean: legacy binary + legacy YAML, NO Phase 201 keys) ==="
       ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapA.tar.gz -C / opt/wanctl"
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapA"
       ssh cake-shaper "ls -lh /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapA.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapA"

       # CRITICAL VERIFICATION: snapshot A YAML must have 0 Phase 201 keys.
       SNAPA_YAML="/etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapA"
       SNAPA_KEY_COUNT=$(ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' $SNAPA_YAML" || echo "0")
       SNAPA_KEY_COUNT=$(echo "$SNAPA_KEY_COUNT" | tr -d '[:space:]')
       echo "Snapshot A Phase 201 key count: $SNAPA_KEY_COUNT (must be 0)"
       if [ "$SNAPA_KEY_COUNT" != "0" ]; then
         echo "FATAL: Snapshot A contains Phase 201 keys. Production was already partially reconciled before this canary started — abort and investigate."
         exit 2
       fi
       ```

    4. **Run predeploy gate** (codex NEW-HIGH-1 step 2):
       ```
       echo "=== T1: Predeploy gate run #1 ==="
       ./scripts/phase201-predeploy-gate.sh
       GATE_RC=$?
       ```
       If first run BLOCKs (`GATE_RC != 0`) on residual v1.41 keys, **reconcile at T2**:
       ```
       echo "=== T2: Reconcile YAML (gate BLOCKed on residual v1.41 keys) ==="
       scp configs/spectrum.yaml cake-shaper:/tmp/spectrum.yaml.new
       ssh cake-shaper "sudo install -o root -g wanctl -m 0640 /tmp/spectrum.yaml.new /etc/wanctl/spectrum.yaml"
       echo "=== T2b: Predeploy gate run #2 (must PASS) ==="
       ./scripts/phase201-predeploy-gate.sh
       ```

       Capture both gate runs (BLOCK reason if any, then PASS) into a temporary log for inclusion in 201-15-CANARY-VERDICT.md.

    5. **SNAPSHOT B — post-gate-PASS candidate state** (codex NEW-HIGH-1 step 3 — AFTER reconcile, AFTER PASS, BEFORE deploy):
       ```
       echo "=== T3: Snapshot B (post-gate-PASS candidate: legacy binary + reconciled Phase 201 YAML) ==="
       ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapB.tar.gz -C / opt/wanctl"
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapB"
       ssh cake-shaper "ls -lh /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapB.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapB"

       # Snapshot B is for deploy evidence ONLY. Sanity check: it should NOW contain Phase 201 keys
       # (the candidate config that the gate just approved).
       SNAPB_YAML="/etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapB"
       SNAPB_KEY_COUNT=$(ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' $SNAPB_YAML" || echo "0")
       SNAPB_KEY_COUNT=$(echo "$SNAPB_KEY_COUNT" | tr -d '[:space:]')
       echo "Snapshot B Phase 201 key count: $SNAPB_KEY_COUNT (expected >= 5 — proves reconcile happened)"
       ```

    6. **Deploy v1.42.1 binary** (codex NEW-HIGH-1 step 4):
       ```
       echo "=== T4: Deploy v1.42.1 binary ==="
       REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
       ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
       sleep 5
       ```

    7. **Verify post-deploy /health — including ACTIVE CONTROL KNOB assertion via /health** (codex MEDIUM-CODEX-3 closure, now via Plan 201-13 rev 3 fields):
       ```
       curl -s http://10.10.110.223:9101/health | jq '{
         version: .version,
         docsis_mode_active: .wans[0].upload.docsis_mode_active,
         setpoint_mbps: .wans[0].upload.setpoint_mbps,
         anti_windup_cycles: .wans[0].upload.anti_windup_cycles,
         anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
         headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
         floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
         max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
         red_streak: .wans[0].upload.red_streak,
         zone_trace_len: (.wans[0].upload.zone_trace | length),
         red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
         red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct
       }'
       ```
       Required values:
       - `version` == `"1.42.1"` (codex MEDIUM-CODEX-4 / LOW-NEW-3 — distinguishes from failed 201-11 binary)
       - `docsis_mode_active` == true
       - `setpoint_mbps` == 12.0
       - `anti_windup_cycles` == 60 (codex MEDIUM-CODEX-3 — proves Plan 201-14 rev-4 knob is active, not stale default)
       - **`red_decay_step_pct` == 0.02** (REV 3 — codex MEDIUM-CODEX-3 closure via Plan 201-13 rev 3 active-knob field)
       - **`red_decay_delta_max_pct` == 0.10** (REV 3 — codex MEDIUM-CODEX-3 closure via Plan 201-13 rev 3 active-knob field)
       - `anti_windup_triggers`, `headroom_exhausted_streak`, `floor_hit_cycles_total`, `max_delay_delta_us`, `red_streak` are ints
       - `zone_trace_len` >= 1

       PLUS — SECONDARY agreement check via SSH grep of `/etc/wanctl/spectrum.yaml`:
       ```
       ssh cake-shaper "sudo grep -E '^[[:space:]]+(red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml"
       ```
       Must show `red_decay_step_pct: 0.02`, `red_decay_delta_max_pct: 0.10`, `anti_windup_cycles: 60`. If /health shows `red_decay_step_pct=0.02` but YAML shows `red_decay_step_pct=0.05`, that's a DISAGREEMENT — ABORT, do NOT proceed to Task 4.

       If ANY of the above fails (including version mismatch on any surface OR /health-vs-YAML disagreement), ABORT — record the failure mode in 201-15-CANARY-VERDICT.md.

    8. **Record predeploy state** in `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md` (create file with the same section structure as 201-11-CANARY-VERDICT.md). Capture:
       - RECANARY_TS value
       - build-identity.json contents (git SHA + all three version surfaces + clean status)
       - **Two-snapshot rollback timeline** with explicit T0/T1/T2/T3/T4 ordering and snapshot A vs snapshot B distinction (codex NEW-HIGH-1)
       - Snapshot A verification: Phase 201 key count == 0 (rollback-clean confirmed)
       - Snapshot B verification: Phase 201 key count >= 5 (reconcile confirmed)
       - Predeploy gate run results (BLOCK reason if any, then PASS)
       - Post-deploy /health snapshot from step 7
       - Active control knob assertion table (codex MEDIUM-CODEX-3 closure):

         | Knob | Source | Expected | Actual | Pass? |
         |------|--------|----------|--------|-------|
         | version | /health | 1.42.1 | <actual> | yes/no |
         | version | pyproject.toml | 1.42.1 | <actual> | yes/no |
         | version | docker/Dockerfile LABEL | 1.42.1 | <actual> | yes/no |
         | anti_windup_cycles | /health | 60 | <actual> | yes/no |
         | red_decay_step_pct | /health | 0.02 | <actual> | yes/no |
         | red_decay_delta_max_pct | /health | 0.10 | <actual> | yes/no |
         | red_decay_step_pct | YAML SSH grep | 0.02 | <actual> | yes/no |
         | red_decay_delta_max_pct | YAML SSH grep | 0.10 | <actual> | yes/no |
         | anti_windup_cycles | YAML SSH grep | 60 | <actual> | yes/no |
  </action>
  <verify>
    <automated>test -f .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}/build-identity.json</automated>
    <automated>jq -e '.git_sha and .version_init_py == "1.42.1" and .version_pyproject == "1.42.1"' .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}/build-identity.json</automated>
    <automated>ssh cake-shaper "ls /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapA.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapA /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapB.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapB" 2>&1 | grep -c "wanctl-prephase201" | tr -d '[:space:]' | grep -qE '^[24]$'</automated>
    <automated>ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapA" | tr -d '[:space:]' | grep -qE '^0$'</automated>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1" and .wans[0].upload.docsis_mode_active == true and .wans[0].upload.setpoint_mbps == 12.0 and .wans[0].upload.anti_windup_cycles == 60 and .wans[0].upload.red_decay_step_pct == 0.02 and .wans[0].upload.red_decay_delta_max_pct == 0.10 and (.wans[0].upload.anti_windup_triggers | type == "number") and (.wans[0].upload.headroom_exhausted_streak | type == "number") and (.wans[0].upload.max_delay_delta_us | type == "number") and (.wans[0].upload.red_streak | type == "number") and (.wans[0].upload.zone_trace | type == "array")'</automated>
    <automated>ssh cake-shaper "sudo grep -cE '^[[:space:]]+(red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml" | tr -d '[:space:]' | grep -qE '^3$'</automated>
  </verify>
  <acceptance_criteria>
    - build-identity.json captures git SHA AND all three version surfaces showing 1.42.1
    - **Snapshot A exists with rollback-clean state (codex NEW-HIGH-1)**: snapA tarball + snapA YAML on cake-shaper; snapA YAML grep returns 0 Phase 201 keys (proves it captures legacy state, not reconciled state)
    - **Snapshot B exists with post-gate-PASS state (codex NEW-HIGH-1)**: snapB tarball + snapB YAML on cake-shaper; snapB YAML grep returns >= 5 Phase 201 keys (proves reconcile happened before snapshot)
    - Both A and B snapshot files exist with non-zero size
    - Predeploy gate ran BETWEEN snapshot A and snapshot B (verifiable from 201-15-CANARY-VERDICT.md timeline)
    - /health.version == "1.42.1"
    - /health.wans[0].upload.docsis_mode_active == true
    - /health.wans[0].upload.setpoint_mbps == 12.0
    - /health.wans[0].upload.anti_windup_cycles == 60 (active knob proven via /health)
    - **/health.wans[0].upload.red_decay_step_pct == 0.02** (codex MEDIUM-CODEX-3 closure via /health)
    - **/health.wans[0].upload.red_decay_delta_max_pct == 0.10** (codex MEDIUM-CODEX-3 closure via /health)
    - /health.wans[0].upload.{anti_windup_triggers, headroom_exhausted_streak, max_delay_delta_us, red_streak, zone_trace} all present and correctly typed
    - SSH grep of `/etc/wanctl/spectrum.yaml` shows red_decay_step_pct, red_decay_delta_max_pct, anti_windup_cycles all present (secondary check)
    - 201-15-CANARY-VERDICT.md exists with two-snapshot rollback timeline + active-control-knob assertion table populated
  </acceptance_criteria>
  <done>
    v1.42.1 binary deployed; rollback-clean Snapshot A captured BEFORE reconcile; deploy-evidence Snapshot B captured AFTER gate PASS; /health confirms DOCSIS-mode active and all rev-4 control knobs (including the two REV-3 active-knob floats) verified live via /health. Ready for canary execution.
  </done>
</task>

<task type="auto">
  <name>Task 4: Execute saturation canary; capture verdict.json + loaded_capture.ndjson; consume primary gate</name>
  <read_first>
    - scripts/phase200-saturation-canary.sh
    - scripts/phase200-saturation-canary.env.example
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json (schema reference)
  </read_first>
  <files>
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/&lt;RECANARY_TS&gt;/verdict.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/&lt;RECANARY_TS&gt;/loaded_capture.ndjson,
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/&lt;RECANARY_TS&gt;/idle_capture.ndjson
  </files>
  <action>
    1. **Set canary env** (verbatim from 201-11):
       ```
       export PHASE200_OUT_DIR=.planning/phases/201-docsis-aware-ul-congestion-control
       export PHASE200_SPECTRUM_HEALTH_URL=http://10.10.110.223:9101/health
       export PHASE200_IPERF_TARGET=104.200.21.31
       export PHASE200_IPERF_LOCAL_BIND=10.10.110.226
       export PHASE200_UL_FLOOR_MBPS=8
       export PHASE200_UL_CEILING_MBPS=18
       export PHASE200_REMOTE_YAML_SSH=cake-shaper:/etc/wanctl/spectrum.yaml
       export PHASE201_DOCSIS_MODE=true
       export PHASE201_SETPOINT_MBPS=12
       unset PHASE201_LOCAL_YAML_OVERRIDE
       unset PHASE201_LEGACY_MODE
       ```

    2. **Run the canary** (single invocation, blocking until verdict written):
       ```
       ./scripts/phase200-saturation-canary.sh
       ```

    3. **Locate the canary directory and read the verdict**:
       ```
       CANARY_DIR=$(ls -dt .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/ | head -1)
       echo "Canary dir: $CANARY_DIR"
       jq '{
         verdict, reason, primary_gate, primary_gate_value,
         floor_hit_cycles_total_loaded_window_start,
         floor_hit_cycles_total_loaded_window_end,
         floor_hit_cycles_total_delta_loaded_window,
         ul_floor_hits_during_load,
         duration_sec, pre_baseline_rtt_ms, post_baseline_rtt_ms
       }' "$CANARY_DIR/verdict.json"
       ```

       If the canary chose a DIFFERENT TS directory than RECANARY_TS, manually copy the build-identity.json into the canary's chosen directory:
       ```
       if [ "$CANARY_DIR" != ".planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}/" ]; then
         cp .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}/build-identity.json "$CANARY_DIR/build-identity.json"
       fi
       ```

    4. **Confirm Plan 201-13 rev 3 diagnostic fields landed in capture** (now includes the two REV-3 active-knob floats):
       ```
       head -1 "$CANARY_DIR/loaded_capture.ndjson" | jq '{
         max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
         red_streak: .wans[0].upload.red_streak,
         zone_trace_len: (.wans[0].upload.zone_trace | length),
         anti_windup_cycles: .wans[0].upload.anti_windup_cycles,
         anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
         headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
         red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
         red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct
       }'
       ```
       All EIGHT fields must be present in at least one captured row.

    5. **Append canary results section to 201-15-CANARY-VERDICT.md**: capture the full verdict.json contents, key field values, and a brief inline analysis (e.g. "primary_gate_value=0; FAIL margin closed from 1453 to 0").
  </action>
  <verify>
    <automated>ls .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | sort -r | head -1</automated>
    <automated>jq -e '.primary_gate == "floor_hit_cycles_total_delta_loaded_window"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)</automated>
    <automated>head -1 $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/loaded_capture.ndjson | head -1) | jq -e '.wans[0].upload.zone_trace | type == "array"'</automated>
    <automated>head -1 $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/loaded_capture.ndjson | head -1) | jq -e '.wans[0].upload.anti_windup_cycles == 60 and .wans[0].upload.red_decay_step_pct == 0.02 and .wans[0].upload.red_decay_delta_max_pct == 0.10'</automated>
  </verify>
  <acceptance_criteria>
    - verdict.json exists with `primary_gate == "floor_hit_cycles_total_delta_loaded_window"`
    - loaded_capture.ndjson contains all eight Plan 201-13 rev 3 fields per captured row (3 original + 3 absorbed + 2 REV-3 active-knob)
    - First captured row shows `anti_windup_cycles == 60`, `red_decay_step_pct == 0.02`, `red_decay_delta_max_pct == 0.10` (proves rev-4 knobs propagated through capture)
    - 201-15-CANARY-VERDICT.md updated with canary results section
    - The canary completed without operator-side abort
  </acceptance_criteria>
  <done>
    Canary executed; verdict.json captured; diagnostic fields and rev-4 knobs confirmed live in NDJSON. Ready for verdict-based decision.
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 5: Operator verdict decision — PASS proceeds to soak; FAIL triggers rollback from Snapshot A; ABORT preserves v1.42.1</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/&lt;RECANARY_TS&gt;/verdict.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (predeploy + canary results sections; the active control knob assertion table; the two-snapshot rollback timeline)
  </read_first>
  <decision>
    The canary verdict.json has been written. Operator must decide the next action based on the verdict value.
  </decision>
  <context>
    Reading verdict.json:
    - PRIMARY GATE: `primary_gate_value` (== `floor_hit_cycles_total_delta_loaded_window`). MUST be 0 for PASS.
    - SECONDARY GATE: `ul_floor_hits_during_load`. MUST be 0 for PASS.
    - DISAGREEMENT (one is 0 and the other is not) is automatic FAIL with a diagnostic reason.

    Read the verdict:
    ```
    jq '{verdict, reason, primary_gate_value, ul_floor_hits_during_load}' \
      $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
    ```
  </context>
  <options>
    <option id="pass">
      <name>PASS — primary_gate_value == 0 AND ul_floor_hits_during_load == 0</name>
      <pros>VALN-06 primary gate met; control-model amendment (Option B) proven on production hardware; Plan 201-16 (24h soak) is unblocked</pros>
      <cons>None — this is the goal state</cons>
    </option>
    <option id="fail">
      <name>FAIL — primary_gate_value > 0 OR ul_floor_hits_during_load > 0 OR disagreement</name>
      <pros>Honest negative result; rollback restores production from SNAPSHOT A (rollback-clean); the next gap-closure planning cycle has fresh evidence including build-identity</pros>
      <cons>Phase 201 stays at gaps_found; may require A5 fallback or further control-model work in v1.43+</cons>
    </option>
    <option id="abort">
      <name>ABORT — environment failure (network unreachable, iperf3 target down, etc.)</name>
      <pros>Distinguishes environmental noise from actual control-model failure; preserves the v1.42.1 binary for a re-attempt</pros>
      <cons>Re-canary must be re-staged once environment is healthy</cons>
    </option>
  </options>
  <resume-signal>Type one of: "pass", "fail", or "abort". On "fail", Task 6 (rollback from Snapshot A) executes automatically. On "pass", proceed to Task 7. On "abort", proceed to Task 8.</resume-signal>
  <acceptance_criteria>
    - Operator entered "pass", "fail", or "abort"
    - Decision recorded in 201-15-CANARY-VERDICT.md "Decision" section
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 6: On FAIL — execute rollback from SNAPSHOT A (rollback-clean, codex NEW-HIGH-1); verify /health.version=1.39.0 AND zero Phase 201 YAML keys</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md (Rollback + Rollback Verification sections, lines 64-86)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (NEW-HIGH-1 — restore from snapshot A, never snapshot B)
  </read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 5 returned "fail". Skip on "pass" or "abort".

    **CRITICAL (codex NEW-HIGH-1):** restore from SNAPSHOT A (rollback-clean), NEVER from SNAPSHOT B. Snapshot B contains Phase 201 keys; restoring from it would leave production with old binary AND new YAML — exactly the scenario rev 2 introduced and codex flagged. Snapshot A captured the legacy state BEFORE any reconcile, so restoring from A returns production to a clean pre-Phase-201 state.

    1. **Restore binary from SNAPSHOT A**:
       ```
       ssh cake-shaper "sudo systemctl stop wanctl@spectrum.service"
       ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase201-recanary-${RECANARY_TS}-snapA.tar.gz -C /"
       ```

    2. **Restore YAML from SNAPSHOT A**:
       ```
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}-snapA /etc/wanctl/spectrum.yaml"
       ssh cake-shaper "sudo chown root:wanctl /etc/wanctl/spectrum.yaml && sudo chmod 0640 /etc/wanctl/spectrum.yaml"
       ```

    3. **Restart service**:
       ```
       ssh cake-shaper "sudo systemctl start wanctl@spectrum.service"
       sleep 5
       ```

    4. **Verify rollback** (codex NEW-HIGH-1 — snapshot A YAML must produce 0 Phase 201 keys post-restore):
       ```
       curl -s http://10.10.110.223:9101/health | jq '{version, status}'
       # Expected: version="1.39.0", status="healthy"

       # Phase 201 + rev-4 key list (9 keys total). Anchored per-key grep prevents
       # comment false positives. Snapshot A was the rollback-clean snapshot, so
       # this MUST return 0.
       ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml"
       # Expected: 0 (all 9 keys absent at YAML-key positions)
       ```

    5. **Append rollback section to 201-15-CANARY-VERDICT.md**. Note explicitly:
       - "Rollback restored from SNAPSHOT A (rollback-clean, captured BEFORE predeploy gate / reconcile)."
       - "Snapshot B was NOT used for rollback; Snapshot B is deploy-evidence only (codex NEW-HIGH-1)."
       - Post-rollback Phase 201 YAML key count: 0 (verified)
  </action>
  <verify>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.39.0" and .status == "healthy"'</automated>
    <automated>ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml" | tr -d '[:space:]' | grep -qE '^0$'</automated>
  </verify>
  <acceptance_criteria>
    - /health.version == "1.39.0"
    - /health.status == "healthy"
    - All 9 Phase 201 + rev-4 YAML keys grep count to 0 in /etc/wanctl/spectrum.yaml (the snapshot A invariant codex NEW-HIGH-1 demanded)
    - 201-15-CANARY-VERDICT.md Rollback section explicitly references SNAPSHOT A (rollback-clean) as the restore source AND states that Snapshot B was deploy-evidence only and was NOT used
  </acceptance_criteria>
  <done>
    Production restored to pre-Phase-201 state from SNAPSHOT A (rollback-clean, codex NEW-HIGH-1). Snapshot B preserved for evidence but never restored. Phase 201 stays at gaps_found.
  </done>
</task>

<task type="auto">
  <name>Task 7: On PASS — finalize 201-15-CANARY-VERDICT.md; capture T+0 baseline for soak; unblock Plan 201-16</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Step 1.5 T+0 baseline pattern)
  </read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 5 returned "pass". Skip on "fail" or "abort".

    1. **Capture T+0 soak baseline** from the canary verdict:
       ```
       VERDICT_FILE=$(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
       T0_BASELINE=$(jq -r '.floor_hit_cycles_total_loaded_window_end' "$VERDICT_FILE")
       echo "Soak T+0 baseline: $T0_BASELINE"
       ```

    2. **Append PASS verdict section to 201-15-CANARY-VERDICT.md**:
       - Verdict: PASS
       - Build identity: contents of build-identity.json (git SHA + version 1.42.1 on all three surfaces)
       - Two-snapshot rollback timeline (codex NEW-HIGH-1) — recorded but unused since canary PASSED
       - Active control knob assertion table (filled in from Task 3) — including the two REV-3 active-knob floats verified via /health
       - Primary gate value: 0
       - Secondary gate value: 0
       - Soak T+0 baseline: $T0_BASELINE
       - Live /health snapshot post-canary
       - Decision: proceed to Plan 201-16 (24h soak)
       - Note: Snapshot A and Snapshot B both retained on cake-shaper for evidence; soak runs against the deployed v1.42.1 binary state.

    3. **Verify v1.42.1 stays deployed**:
       ```
       curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1"'
       ```
  </action>
  <verify>
    <automated>jq -e '.verdict == "pass" and .primary_gate_value == 0 and .ul_floor_hits_during_load == 0' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)</automated>
    <automated>grep -q "Soak T+0 baseline" .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</automated>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1"'</automated>
  </verify>
  <acceptance_criteria>
    - verdict.json shows verdict=pass, primary_gate_value=0, ul_floor_hits_during_load=0
    - 201-15-CANARY-VERDICT.md records Soak T+0 baseline value AND the active-control-knob assertion table (incl. red_decay_step_pct/red_decay_delta_max_pct via /health) AND the two-snapshot rollback timeline (per codex NEW-HIGH-1)
    - v1.42.1 binary remains deployed
    - Plan 201-16 (24h soak) is unblocked
  </acceptance_criteria>
  <done>
    Re-canary PASS recorded; build identity bound on all three version surfaces; Soak T+0 baseline captured; control-model amendment proven on production with active-knob proof via /health. Plan 201-16 may proceed.
  </done>
</task>

<task type="auto">
  <name>Task 8: On ABORT — record environment-failure context; do NOT rollback; preserve v1.42.1 for re-attempt</name>
  <read_first>None additional</read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 5 returned "abort". Skip on "pass" or "fail".

    1. **Record abort reason** in 201-15-CANARY-VERDICT.md "Decision" section. Note that both Snapshot A and Snapshot B are preserved on cake-shaper for re-attempt.
    2. **Do NOT rollback.** Operator re-runs the canary (Tasks 4-5) once environment is healthy.
    3. **Confirm wanctl service is still healthy**:
       ```
       curl -s http://10.10.110.223:9101/health | jq '{version, status}'
       ssh cake-shaper "sudo systemctl is-active wanctl@spectrum.service"
       ```
       Both must show healthy / active. version should still be 1.42.1.
  </action>
  <verify>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.status == "healthy"'</automated>
    <automated>ssh cake-shaper "sudo systemctl is-active wanctl@spectrum.service" | tr -d '[:space:]' | grep -qE '^active$'</automated>
  </verify>
  <acceptance_criteria>
    - 201-15-CANARY-VERDICT.md records abort reason
    - wanctl@spectrum.service still active
    - /health responding healthy on v1.42.1 binary
    - No rollback executed; Snapshot A + Snapshot B both preserved on cake-shaper for re-attempt
  </acceptance_criteria>
  <done>
    Environment failure documented; v1.42.1 binary preserved; both snapshots preserved; Tasks 4-5 may be re-run after environment recovery.
  </done>
</task>

</tasks>

<verification>
End-of-plan state varies by Task 5 verdict:

- **PASS**: Plan 201-16 unblocked; v1.42.1 binary deployed; 201-15-CANARY-VERDICT.md records pass + T+0 baseline + active-control-knob assertion table (with red_decay_step_pct + red_decay_delta_max_pct verified via /health per codex MEDIUM-CODEX-3) + two-snapshot rollback timeline (codex NEW-HIGH-1) + build identity on three version surfaces (codex LOW/MEDIUM-NEW-3)
- **FAIL**: Production rolled back to v1.39.0 from SNAPSHOT A (codex NEW-HIGH-1); YAML clean of all rev-4 + Phase 201 keys; Snapshot B preserved for evidence but unused; 201-15-CANARY-VERDICT.md records fail + rollback verification table
- **ABORT**: v1.42.1 binary preserved; both snapshots preserved; no rollback; 201-15-CANARY-VERDICT.md records abort reason
</verification>

<success_criteria>
- 201-15-CANARY-VERDICT.md exists with predeploy + canary + decision sections populated
- canary/<TS>/verdict.json exists, schema-compatible with 201-11 verdict.json
- canary/<TS>/build-identity.json exists with git SHA + all three version surfaces showing 1.42.1 (codex LOW/MEDIUM-NEW-3)
- canary/<TS>/loaded_capture.ndjson contains all eight Plan 201-13 rev 3 diagnostic fields (3 original + 3 absorbed + 2 REV-3 active-knob)
- **TWO snapshots taken in correct order** (codex NEW-HIGH-1): Snapshot A (rollback-clean, BEFORE reconcile) + Snapshot B (post-gate-PASS, AFTER reconcile); strict timeline T0/T1/T2/T3/T4 enforced
- Snapshot A YAML grep returns 0 Phase 201 keys at capture time
- Snapshot B YAML grep returns >= 5 Phase 201 keys at capture time
- Active control knob assertion table populated, all knobs verified via /health AND YAML SSH grep agreement (codex MEDIUM-CODEX-3 — closure via /health-surfaced fields)
- Operator decision (pass/fail/abort) recorded
- One of three downstream paths executed correctly; FAIL path restores from Snapshot A explicitly (NEVER Snapshot B)
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-SUMMARY.md` per the standard template. Include: re-canary timestamp, build identity (git SHA + version 1.42.1 on all three surfaces), verdict, primary_gate_value, ul_floor_hits_during_load, active control knob assertion outcome (including the two REV-3 active-knob floats verified via /health), two-snapshot rollback timeline confirmation (Snapshot A pre-reconcile, Snapshot B post-gate, FAIL restores from A only), decision taken, downstream effect (soak unblocked / rollback complete / re-attempt staged), codex review findings closed (NEW-HIGH-1 two-snapshot rollback, MEDIUM-CODEX-3 fully closed by /health surfacing, MEDIUM-CODEX-4/LOW-NEW-3 version on all surfaces).
</output>
</content>
</invoke>