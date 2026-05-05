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
autonomous: false
gap_closure: true
revision: 2  # Iteration 2 — incorporates Codex HIGH-CODEX-3, MEDIUM-CODEX-3, MEDIUM-CODEX-4 from 201-REVIEWS.md
requirements: [VALN-06]
tags: [phase-201, gap-closure, canary, valn-06-primary, recanary, operator-gated, fail-closed, codex-revised]

must_haves:
  truths:
    - "Re-canary runs at the ORIGINAL setpoint_mbps=12 (NOT A5 fallback setpoint=10) — the operator-confirmed closure path is the control-model amendment, not the setpoint workaround"
    - "Version is bumped to 1.42.1 in src/wanctl/__init__.py BEFORE deploy so /health.version distinguishes the failed 201-11 binary (1.42.0) from the gap-closure binary (1.42.1) — codex MEDIUM-CODEX-4 evidentiary distinguishability"
    - "build-identity.json captures git SHA + version + build_utc at canary-time so the canary evidence binds to the exact source tree, not just the version string"
    - "Re-canary uses the existing scripts/phase200-saturation-canary.sh extended in Plan 201-08; no new harness authored"
    - "ROLLBACK SNAPSHOT IS TAKEN AFTER PREDEPLOY GATE PASSES (codex HIGH-CODEX-3) — never before. If gate's first run BLOCKs on stale rejected v1.41 keys, the operator reconciles, gate is re-run, and ONLY after gate PASS are rollback artifacts captured. The snapshot represents a known-good predeploy state, never a stale pre-reconcile state."
    - "Pre-deploy snapshot: /opt/wanctl binary archive AND /etc/wanctl/spectrum.yaml — REVIEWS HIGH-7 dual-snapshot pattern, identical to 201-11 in shape but with corrected ordering"
    - "PRIMARY GATE: floor_hit_cycles_total_delta_loaded_window == 0 (zero-tolerance, REVIEWS HIGH-5 cycle-fidelity counter)"
    - "SECONDARY GATE: ul_floor_hits_during_load == 0 (1Hz cross-check; disagreement with primary produces FAIL with diagnostic reason, not PASS)"
    - "Loaded-window NDJSON capture includes the diagnostic fields landed in Plan 201-13 (max_delay_delta_us, red_streak, zone_trace, headroom_exhausted_streak, anti_windup_cycles, anti_windup_triggers) — confirmed by jq inspection of any captured row"
    - "ACTIVE CONTROL KNOB ASSERTION (codex MEDIUM-CODEX-3): post-deploy /health probe explicitly asserts the new control parameters are live in the running binary. Specifically: red_decay_step_pct == 0.02 OR effective step is bounded-absolute (verifiable by zone_trace pattern), anti_windup_cycles == 60 (echoed in /health), anti_windup_triggers field present (counter, may be 0). Without these assertions the canary could PASS with stale defaults, proving nothing about the rev-3 fix."
    - "On FAIL: rollback executes per D-10 / REVIEWS HIGH-7; both binary AND YAML restored from the post-gate-PASS snapshot; verified by post-rollback /health.version=1.39.0 AND grep counts of all new + existing Phase 201 YAML keys = 0 in /etc/wanctl/spectrum.yaml"
    - "On PASS: Plan 201-16 (24h soak) is unblocked; 201-15-CANARY-VERDICT.md records verdict=pass, primary_gate=0, captures floor_hit_cycles_total_loaded_window_end as the T+0 baseline for the soak"
    - "Canary verdict.json schema-compatible with 201-11 verdict.json (same fields, same primary_gate identifier)"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
      provides: "Canonical re-canary verdict; primary_gate value, secondary_gate value, baseline RTT bookends, env capture, rollback decision"
      contains: "primary_gate"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/build-identity.json
      provides: "Git SHA + version + build_utc — codex MEDIUM-CODEX-4 evidentiary binding"
      contains: "git_sha"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
      provides: "Operator-readable verdict; includes active-control-knob assertion table"
      contains: "VALN-06"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json"
      to: ".planning/phases/201-docsis-aware-ul-congestion-control/201-16-soak-and-closeout-PLAN.md"
      via: "verdict=pass unblocks soak; verdict=fail blocks soak and triggers next gap-closure cycle"
      pattern: "primary_gate"
    - from: "scripts/phase201-predeploy-gate.sh"
      to: "/etc/wanctl/spectrum.yaml on cake-shaper"
      via: "SSH probe + reconcile-or-block on residual rejected v1.41 keys; rollback snapshot taken AFTER PASS"
      pattern: "predeploy-gate"
---

<objective>
**Gap-closure Plan 3 of 4. OPERATOR-GATED CHECKPOINT. Revision 2 — incorporates codex HIGH-CODEX-3 (snapshot ordering bug), MEDIUM-CODEX-3 (knob verification), MEDIUM-CODEX-4 (version distinguishability).**

Re-run the Phase 201 saturation canary at `setpoint_mbps=12` against the **v1.42.1** binary that contains the Plan 201-13 diagnostic fields and the Plan 201-14 rev-3 control-model amendment (bounded-absolute decay + anti-windup cap-and-clamp).

This plan is the closure proof for the primary VERIFICATION.md gap. Three structural changes from revision 1:

1. **Version bump 1.42.0 → 1.42.1** (codex MEDIUM-CODEX-4): A patch bump distinguishes the failed 201-11 binary from the gap-closure binary at `/health.version`. Without this, re-canary evidence cannot prove "different code ran." Captured in `src/wanctl/__init__.py` BEFORE deploy. Also: build-identity.json captures git SHA at canary-time so evidence binds to the exact tree, not merely the version string.

2. **Rollback snapshot moved AFTER predeploy gate PASS** (codex HIGH-CODEX-3): Revision 1 snapshotted rollback artifacts BEFORE the predeploy gate ran. If the gate's first run BLOCKed (as it did in 201-11) and the operator then reconciled the YAML, the snapshot would point at the stale pre-reconcile YAML — restoring on FAIL would put production back into the rejected state. Revision 2 inverts the order: gate runs first, operator reconciles if needed, gate re-runs to PASS, AND THEN the snapshot is taken. Snapshot always represents a known-good predeploy state.

3. **Active control knob assertion** (codex MEDIUM-CODEX-3): Post-deploy /health probe explicitly asserts the new Plan 201-14 rev-3 parameters are live, not stale defaults. The rev-3 knobs are `red_decay_step_pct=0.02`, `red_decay_delta_max_pct=0.10`, `anti_windup_cycles=60`. The `anti_windup_cycles` value and `anti_windup_triggers` counter are surfaced via /health (Plan 201-13 contract); the two `red_decay_*_pct` floats are NOT in /health (they are static YAML; we assert them via SSH grep of `/etc/wanctl/spectrum.yaml` AND inspect the live behavior pattern via the captured zone_trace post-canary). Without these assertions the canary could PASS with default factor_down=0.9 if the wiring failed silently.

Per CONTEXT.md D-11: reuse `scripts/phase200-saturation-canary.sh`. Per Plan 201-08: extended for env-cross-check and counter-delta verdict-decision. Per Plan 201-07: predeploy gate is in place. Per REVIEWS HIGH-7 / D-10: rollback restores both binary AND YAML.

The re-canary uses the EXACT same env vars as 201-11 (preserve evidentiary continuity) — only the binary on cake-shaper changes (Plans 201-13 + 201-14 rev 3 land new code; version becomes 1.42.1).

Output: a `canary/<TIMESTAMP>/` directory with verdict.json, loaded_capture.ndjson, idle_capture.ndjson, build-identity.json, and a 201-15-CANARY-VERDICT.md operator-readable summary.

This plan is `autonomous: false` because it deploys to production (cake-shaper, wanctl@spectrum.service running 24/7) and may rollback. The operator MUST approve at the predeploy checkpoint and the post-canary checkpoint.
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

Predeploy gate (Plan 201-07): first run may BLOCK on residual v1.41 keys → operator reconciles via SCP from `configs/spectrum.yaml` → second run PASSes. **Rollback snapshot is taken AFTER the second run PASSes (codex HIGH-CODEX-3).**

Deploy invocation (201-11 verbatim):
```
REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
ssh cake-shaper sudo systemctl restart wanctl@spectrum.service
```

Verdict.json primary gate field (Plan 201-08): `primary_gate: "floor_hit_cycles_total_delta_loaded_window"`, `primary_gate_value: <int>`. PASS only if `primary_gate_value == 0` AND `ul_floor_hits_during_load == 0`. Disagreement = FAIL.

Rollback artifacts (REVIEWS HIGH-7 / D-10): pre-deploy `tar -czf /opt/wanctl-prephase201-recanary-<TS>.tar.gz /opt/wanctl` AND `cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>` AFTER predeploy gate PASS, BEFORE deploy. On FAIL, restore both, restart service, verify /health.version reverts to 1.39.0.

**Active control knob assertion (codex MEDIUM-CODEX-3):** post-deploy /health must show:
- `version == "1.42.1"` (codex MEDIUM-CODEX-4)
- `wans[0].upload.docsis_mode_active == true`
- `wans[0].upload.setpoint_mbps == 12.0`
- `wans[0].upload.anti_windup_cycles == 60` (Plan 201-13 echoes this YAML key)
- `wans[0].upload.anti_windup_triggers` is present and an int (may be 0; the field's existence proves Plan 201-13 wired it AND Plan 201-14 incremented the counter — even if it never fired during the canary)
- `wans[0].upload.headroom_exhausted_streak` is present and an int

PLUS via SSH grep of `/etc/wanctl/spectrum.yaml`: `red_decay_step_pct: 0.02` AND `red_decay_delta_max_pct: 0.10` (these are static YAML, not in /health).
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Bump version to 1.42.1 in src/wanctl/__init__.py + commit</name>
  <read_first>
    - src/wanctl/__init__.py (current __version__ value)
    - CHANGELOG.md (latest version section)
  </read_first>
  <files>src/wanctl/__init__.py, CHANGELOG.md</files>
  <action>
    Codex MEDIUM-CODEX-4 fix: distinguish the failed 201-11 binary (1.42.0) from the gap-closure binary at /health.version.

    1. Locate `__version__` in `src/wanctl/__init__.py`. Bump from `"1.42.0"` to `"1.42.1"`.

    2. Update CHANGELOG.md: add a `## 1.42.1` section above `## 1.42.0` with a one-line entry referencing this plan and the Plan 201-14 rev-3 control-model amendment:
       ```markdown
       ## 1.42.1 — 2026-05-XX

       ### Fixed
       - Phase 201 gap-closure (rev 3): bounded-absolute RED decay + anti-windup cap-and-clamp. See Plan 201-14 / canary <RECANARY_TS>.
       ```

    3. Commit: `chore(201-15): bump version to 1.42.1 for codex evidentiary distinguishability (MEDIUM-CODEX-4)`.

    Run hot-path slice to confirm no test relies on the literal `"1.42.0"` string:
    ```
    .venv/bin/pytest -o addopts='' tests/test_health_check.py -q
    ```
  </action>
  <verify>
    <automated>grep -q '__version__ = "1.42.1"' src/wanctl/__init__.py</automated>
    <automated>grep -q "## 1.42.1" CHANGELOG.md</automated>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `src/wanctl/__init__.py` shows `__version__ = "1.42.1"`
    - CHANGELOG.md has a `## 1.42.1` section
    - test_health_check.py passes (no test brittle on the literal old version)
    - Commit recorded
  </acceptance_criteria>
  <done>
    Version bumped; CHANGELOG updated; binary built from this tree will report 1.42.1 in /health.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Predeploy approval — verify Plans 201-13 + 201-14 landed, version=1.42.1, tests green; operator confirms re-canary go</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
    - configs/spectrum.yaml (verify red_decay_step_pct + red_decay_delta_max_pct + anti_windup_cycles present; sustained_red_cycles ABSENT)
    - src/wanctl/__init__.py (verify __version__ == "1.42.1")
  </read_first>
  <what-built>
    Plans 201-13, 201-14 (rev 3), and Task 1 of this plan must be complete:
    - 201-13: /health.wans[0].upload exposes max_delay_delta_us, red_streak, zone_trace, headroom_exhausted_streak, anti_windup_cycles, anti_windup_triggers (no sustained_red_cycles per rev-2 coordination).
    - 201-14 rev 3: queue_controller has bounded-absolute RED decay (Option B), integral anti-windup cap-and-clamp with synchronous headroom_state recompute, rate-limited logging. SAFE-05 byte-identity preserved. Cycle-1-18 table test green.
    - configs/spectrum.yaml has explicit `red_decay_step_pct: 0.02`, `red_decay_delta_max_pct: 0.10`, `anti_windup_cycles: 60` under continuous_monitoring.upload. `sustained_red_cycles` ABSENT.
    - Version is 1.42.1 in src/wanctl/__init__.py.
  </what-built>
  <how-to-verify>
    1. Confirm summaries exist:
       ```
       ls .planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
       ls .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
       ```

    2. Confirm version bump:
       ```
       grep '__version__' src/wanctl/__init__.py
       ```
       Must show `__version__ = "1.42.1"`.

    3. Confirm hot-path slice green:
       ```
       .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
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
       Exit code 0 — this is the BLOCKER fix proof.

    6. Operator decides: proceed with re-canary at setpoint_mbps=12, or hold for additional review.
  </how-to-verify>
  <resume-signal>Type "approved" to proceed to Task 3 (predeploy gate + rollback snapshot + deploy), or describe blockers.</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved"
    - Both prerequisite SUMMARY files exist
    - `__version__ == "1.42.1"`
    - Hot-path slice exits 0
    - Cycle-1-18 table test passes
    - configs/spectrum.yaml has new keys; `sustained_red_cycles` absent
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 3: Run predeploy gate FIRST; reconcile if blocked; ONLY THEN snapshot rollback artifacts; deploy v1.42.1; verify /health version + active control knobs</name>
  <read_first>
    - scripts/phase201-predeploy-gate.sh
    - scripts/deploy.sh
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md (Pre-deploy Reconciliation section, lines 13-19)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-REVIEWS.md (HIGH-CODEX-3 — snapshot AFTER PASS, MEDIUM-CODEX-3 — knob verification, MEDIUM-CODEX-4 — version distinguishability)
  </read_first>
  <files>
    /opt/wanctl-prephase201-recanary-<TS>.tar.gz (on cake-shaper, post-gate-PASS snapshot),
    /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS> (on cake-shaper, post-gate-PASS snapshot),
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/<RECANARY_TS>/build-identity.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
  </files>
  <action>
    1. **Set TS variable**:
       ```
       export RECANARY_TS=$(date -u +%Y%m%dT%H%M%SZ)
       echo "Re-canary timestamp: $RECANARY_TS"
       ```

    2. **Capture build identity NOW** (codex MEDIUM-CODEX-4 — git SHA captured at canary-time, before any artifact is built):
       ```
       mkdir -p .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}
       BUILD_DIR=.planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}
       cat > $BUILD_DIR/build-identity.json <<EOF
       {
         "git_sha": "$(git rev-parse HEAD)",
         "git_status_clean": $(if [ -z "$(git status --porcelain)" ]; then echo true; else echo false; fi),
         "version": "$(grep '__version__' src/wanctl/__init__.py | sed -E 's/.*= "(.*)"/\1/')",
         "build_utc": "$(date -u -Iseconds)",
         "recanary_ts": "${RECANARY_TS}"
       }
       EOF
       cat $BUILD_DIR/build-identity.json
       ```
       The `git_status_clean: false` value is a soft warning, not a blocker (canary still proceeds), but it's recorded for evidentiary integrity.

    3. **Run predeploy gate FIRST** (codex HIGH-CODEX-3 — gate must run BEFORE rollback snapshot):
       ```
       ./scripts/phase201-predeploy-gate.sh
       ```
       If first run BLOCKs on residual v1.41 keys, reconcile by overwriting `/etc/wanctl/spectrum.yaml`:
       ```
       scp configs/spectrum.yaml cake-shaper:/tmp/spectrum.yaml.new
       ssh cake-shaper "sudo install -o root -g wanctl -m 0640 /tmp/spectrum.yaml.new /etc/wanctl/spectrum.yaml"
       ./scripts/phase201-predeploy-gate.sh   # second run must PASS
       ```

       Capture both gate runs (BLOCK reason if any, then PASS) into a temporary log for inclusion in 201-15-CANARY-VERDICT.md.

    4. **NOW snapshot rollback artifacts** (codex HIGH-CODEX-3 — AFTER PASS, never before):
       ```
       ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz -C / opt/wanctl"
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}"
       ssh cake-shaper "ls -lh /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}"
       ```
       Both files must exist with non-zero size. The snapshotted YAML now reflects the post-reconcile state — restoring on FAIL will return production to a known-good predeploy state, NOT a stale rejected state.

    5. **Deploy v1.42.1 binary**:
       ```
       REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
       ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
       sleep 5
       ```

    6. **Verify post-deploy /health — including ACTIVE CONTROL KNOB assertion** (codex MEDIUM-CODEX-3):
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
         zone_trace_len: (.wans[0].upload.zone_trace | length)
       }'
       ```
       Required values:
       - `version` == `"1.42.1"` (codex MEDIUM-CODEX-4 — distinguishes from failed 201-11 binary)
       - `docsis_mode_active` == true
       - `setpoint_mbps` == 12.0
       - `anti_windup_cycles` == 60 (codex MEDIUM-CODEX-3 — proves Plan 201-14 rev-3 knob is active, not stale default)
       - `anti_windup_triggers` is an int (NOT null) — proves Plan 201-13 wired the counter AND Plan 201-14 initialized it
       - `headroom_exhausted_streak` is an int — proves the streak counter is wired
       - `floor_hit_cycles_total` is an int (== 0 fresh after restart)
       - `max_delay_delta_us` is an int — proves Plan 201-13 wired it
       - `red_streak` is an int >= 0
       - `zone_trace_len` >= 1 — proves the ring buffer is being filled

       PLUS — assert the static YAML knobs that don't appear in /health (codex MEDIUM-CODEX-3 supplemental):
       ```
       ssh cake-shaper "sudo grep -E '^[[:space:]]+(red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml"
       ```
       Must show all three lines with the rev-3 values: `red_decay_step_pct: 0.02`, `red_decay_delta_max_pct: 0.10`, `anti_windup_cycles: 60`.

       If ANY of the above fails, ABORT — do NOT proceed to Task 4. Record the failure mode in 201-15-CANARY-VERDICT.md; the canary cannot proceed because the active-control-knob assertion has not been satisfied (codex MEDIUM-CODEX-3).

    7. **Record predeploy state** in `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md` (create file with the same section structure as 201-11-CANARY-VERDICT.md). Capture:
       - RECANARY_TS value
       - build-identity.json contents (git SHA + version + clean status)
       - Predeploy gate run results (first run BLOCK reason if any, second run PASS) — note the ORDER: gate first, then snapshot
       - Rollback artifact paths and sizes (with explicit note: "snapshot taken AFTER predeploy gate PASS per codex HIGH-CODEX-3")
       - Post-deploy /health snapshot from step 6
       - Active control knob assertion table:

         | Knob | Source | Expected | Actual | Pass? |
         |------|--------|----------|--------|-------|
         | version | /health | 1.42.1 | <actual> | yes/no |
         | anti_windup_cycles | /health | 60 | <actual> | yes/no |
         | anti_windup_triggers | /health | int (any) | <actual> | yes/no |
         | red_decay_step_pct | /etc/wanctl/spectrum.yaml | 0.02 | <actual> | yes/no |
         | red_decay_delta_max_pct | /etc/wanctl/spectrum.yaml | 0.10 | <actual> | yes/no |
  </action>
  <verify>
    <automated>test -f .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}/build-identity.json</automated>
    <automated>jq -e '.git_sha and .version == "1.42.1"' .planning/phases/201-docsis-aware-ul-congestion-control/canary/${RECANARY_TS}/build-identity.json</automated>
    <automated>ssh cake-shaper "ls /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}" 2>&1 | grep -c "wanctl-prephase201" | grep -qE '^[12]$'</automated>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1" and .wans[0].upload.docsis_mode_active == true and .wans[0].upload.setpoint_mbps == 12.0 and .wans[0].upload.anti_windup_cycles == 60 and (.wans[0].upload.anti_windup_triggers | type == "number") and (.wans[0].upload.headroom_exhausted_streak | type == "number") and (.wans[0].upload.max_delay_delta_us | type == "number") and (.wans[0].upload.red_streak | type == "number") and (.wans[0].upload.zone_trace | type == "array")'</automated>
    <automated>ssh cake-shaper "sudo grep -cE '^[[:space:]]+(red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml" | tr -d '[:space:]' | grep -qE '^3$'</automated>
  </verify>
  <acceptance_criteria>
    - build-identity.json captures git SHA and version 1.42.1
    - Predeploy gate ran BEFORE rollback snapshot (verifiable from 201-15-CANARY-VERDICT.md timeline)
    - Both rollback snapshots exist on cake-shaper with non-zero size
    - /health.version == "1.42.1"
    - /health.wans[0].upload.docsis_mode_active == true
    - /health.wans[0].upload.setpoint_mbps == 12.0
    - /health.wans[0].upload.anti_windup_cycles == 60 (active knob proven)
    - /health.wans[0].upload.{anti_windup_triggers, headroom_exhausted_streak, max_delay_delta_us, red_streak, zone_trace} all present and correctly typed
    - SSH grep of `/etc/wanctl/spectrum.yaml` shows red_decay_step_pct, red_decay_delta_max_pct, anti_windup_cycles all present
    - 201-15-CANARY-VERDICT.md exists with predeploy section + active-control-knob assertion table populated
  </acceptance_criteria>
  <done>
    v1.42.1 binary deployed with snapshots in place (taken AFTER gate PASS), /health confirms DOCSIS-mode active and all rev-3 control knobs verified active. Ready for canary execution.
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
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/<RECANARY_TS>/verdict.json,
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/<RECANARY_TS>/loaded_capture.ndjson,
    .planning/phases/201-docsis-aware-ul-congestion-control/canary/<RECANARY_TS>/idle_capture.ndjson
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
       The script writes to `$PHASE200_OUT_DIR/canary/<TS>/`. The script's TS may differ from RECANARY_TS by a few seconds; if it picks the same RECANARY_TS directory we already created in Task 3, the build-identity.json will be co-located with verdict.json.

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

    4. **Confirm Plan 201-13 diagnostic fields landed in capture**:
       ```
       head -1 "$CANARY_DIR/loaded_capture.ndjson" | jq '{
         max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
         red_streak: .wans[0].upload.red_streak,
         zone_trace_len: (.wans[0].upload.zone_trace | length),
         anti_windup_cycles: .wans[0].upload.anti_windup_cycles,
         anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
         headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak
       }'
       ```
       All six fields must be present in at least one captured row.

    5. **Append canary results section to 201-15-CANARY-VERDICT.md**: capture the full verdict.json contents, key field values, and a brief inline analysis (e.g. "primary_gate_value=0; FAIL margin closed from 1453 to 0"). Note any anti_windup_triggers > 0 — that's informational (the safety net engaged at some point during the canary, which is fine on PASS).
  </action>
  <verify>
    <automated>ls .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | sort -r | head -1</automated>
    <automated>jq -e '.primary_gate == "floor_hit_cycles_total_delta_loaded_window"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)</automated>
    <automated>head -1 $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/loaded_capture.ndjson | head -1) | jq -e '.wans[0].upload.zone_trace | type == "array"'</automated>
    <automated>head -1 $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/loaded_capture.ndjson | head -1) | jq -e '.wans[0].upload.anti_windup_cycles == 60'</automated>
  </verify>
  <acceptance_criteria>
    - verdict.json exists with `primary_gate == "floor_hit_cycles_total_delta_loaded_window"`
    - loaded_capture.ndjson contains all six Plan 201-13 fields per captured row (3 original + 3 absorbed: anti_windup_cycles, anti_windup_triggers, headroom_exhausted_streak)
    - First captured row shows anti_windup_cycles == 60 (proves rev-3 knob propagated through capture)
    - 201-15-CANARY-VERDICT.md updated with canary results section
    - The canary completed without operator-side abort (verdict is "pass" or "fail", NOT "abort")
  </acceptance_criteria>
  <done>
    Canary executed; verdict.json captured; diagnostic fields and rev-3 knobs confirmed live in NDJSON. Ready for verdict-based decision.
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 5: Operator verdict decision — PASS proceeds to soak; FAIL triggers rollback + re-plan</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/&lt;RECANARY_TS&gt;/verdict.json (the verdict file written by Task 4)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (predeploy + canary results sections; the active control knob assertion table)
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
      <pros>Honest negative result; rollback restores production from the post-gate-PASS snapshot; the next gap-closure planning cycle has fresh evidence including build-identity</pros>
      <cons>Phase 201 stays at gaps_found; may require A5 fallback or further control-model work in v1.43+</cons>
    </option>
    <option id="abort">
      <name>ABORT — environment failure (network unreachable, iperf3 target down, etc.)</name>
      <pros>Distinguishes environmental noise from actual control-model failure; preserves the v1.42.1 binary for a re-attempt</pros>
      <cons>Re-canary must be re-staged once environment is healthy</cons>
    </option>
  </options>
  <resume-signal>Type one of: "pass", "fail", or "abort". On "fail", Task 6 (rollback) executes automatically. On "pass", proceed to Task 7. On "abort", proceed to Task 8.</resume-signal>
  <acceptance_criteria>
    - Operator entered "pass", "fail", or "abort"
    - Decision recorded in 201-15-CANARY-VERDICT.md "Decision" section
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 6: On FAIL — execute rollback (binary + YAML from POST-GATE-PASS snapshot); verify /health.version=1.39.0</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md (Rollback + Rollback Verification sections, lines 64-86)
  </read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 5 returned "fail". Skip on "pass" or "abort".

    1. **Restore binary from POST-GATE-PASS snapshot** (codex HIGH-CODEX-3 — never restore stale pre-reconcile state):
       ```
       ssh cake-shaper "sudo systemctl stop wanctl@spectrum.service"
       ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz -C /"
       ```

    2. **Restore YAML from POST-GATE-PASS snapshot**:
       ```
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS} /etc/wanctl/spectrum.yaml"
       ssh cake-shaper "sudo chown root:wanctl /etc/wanctl/spectrum.yaml && sudo chmod 0640 /etc/wanctl/spectrum.yaml"
       ```

    3. **Restart service**:
       ```
       ssh cake-shaper "sudo systemctl start wanctl@spectrum.service"
       sleep 5
       ```

    4. **Verify rollback** (REVIEWS HIGH-7 dual verification):
       ```
       curl -s http://10.10.110.223:9101/health | jq '{version, status}'
       # Expected: version="1.39.0", status="healthy"

       # WARNING 5 fix preserved: anchored per-key grep prevents false positives from comments.
       # Updated key list reflects rev-3 (red_decay_step_pct, red_decay_delta_max_pct;
       # sustained_red_cycles removed since it was deleted in rev 3).
       ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml"
       # Expected: 0 (all 9 keys absent at YAML-key positions)
       ```

    5. **Append rollback section to 201-15-CANARY-VERDICT.md**. Note explicitly: "Rollback restored from snapshot taken AFTER predeploy gate PASS (codex HIGH-CODEX-3). Snapshot did NOT contain stale rejected v1.41 keys."
  </action>
  <verify>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.39.0" and .status == "healthy"'</automated>
    <automated>ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|red_decay_step_pct|red_decay_delta_max_pct|anti_windup_cycles):' /etc/wanctl/spectrum.yaml" | tr -d '[:space:]' | grep -qE '^0$'</automated>
  </verify>
  <acceptance_criteria>
    - /health.version == "1.39.0"
    - /health.status == "healthy"
    - All 9 Phase 201 + rev-3 YAML keys grep count to 0 in /etc/wanctl/spectrum.yaml
    - 201-15-CANARY-VERDICT.md Rollback section populated, explicitly noting post-gate-PASS snapshot lineage
  </acceptance_criteria>
  <done>
    Production restored to pre-Phase-201 state from a known-good (post-gate-PASS) snapshot. Phase 201 stays at gaps_found.
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
       - Build identity: contents of build-identity.json (git SHA + version 1.42.1)
       - Active control knob assertion table (filled in from Task 3)
       - Primary gate value: 0
       - Secondary gate value: 0
       - Soak T+0 baseline: $T0_BASELINE
       - Live /health snapshot post-canary
       - Decision: proceed to Plan 201-16 (24h soak)

    3. **Verify v1.42.1 stays deployed**:
       ```
       curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1"'
       ```
       v1.42.1 binary stays in place; YAML stays as deployed. No rollback. Plan 201-16 deploys ON TOP of this binary state.
  </action>
  <verify>
    <automated>jq -e '.verdict == "pass" and .primary_gate_value == 0 and .ul_floor_hits_during_load == 0' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)</automated>
    <automated>grep -q "Soak T+0 baseline" .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</automated>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.42.1"'</automated>
  </verify>
  <acceptance_criteria>
    - verdict.json shows verdict=pass, primary_gate_value=0, ul_floor_hits_during_load=0
    - 201-15-CANARY-VERDICT.md records Soak T+0 baseline value AND the active-control-knob assertion table
    - v1.42.1 binary remains deployed
    - Plan 201-16 (24h soak) is unblocked
  </acceptance_criteria>
  <done>
    Re-canary PASS recorded; build identity bound; Soak T+0 baseline captured; control-model amendment proven on production. Plan 201-16 may proceed.
  </done>
</task>

<task type="auto">
  <name>Task 8: On ABORT — record environment-failure context; do NOT rollback; preserve v1.42.1 for re-attempt</name>
  <read_first>None additional</read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 5 returned "abort". Skip on "pass" or "fail".

    1. **Record abort reason** in 201-15-CANARY-VERDICT.md "Decision" section.
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
    - No rollback executed
  </acceptance_criteria>
  <done>
    Environment failure documented; v1.42.1 binary preserved; Tasks 4-5 may be re-run after environment recovery.
  </done>
</task>

</tasks>

<verification>
End-of-plan state varies by Task 5 verdict:

- **PASS**: Plan 201-16 unblocked; v1.42.1 binary deployed; 201-15-CANARY-VERDICT.md records pass + T+0 baseline + active-control-knob assertion table + build identity
- **FAIL**: Production rolled back to v1.39.0 from POST-GATE-PASS snapshot (HIGH-CODEX-3); YAML clean of all rev-3 + Phase 201 keys; 201-15-CANARY-VERDICT.md records fail + rollback verification table
- **ABORT**: v1.42.1 binary preserved; no rollback; 201-15-CANARY-VERDICT.md records abort reason
</verification>

<success_criteria>
- 201-15-CANARY-VERDICT.md exists with predeploy + canary + decision sections populated
- canary/<TS>/verdict.json exists, schema-compatible with 201-11 verdict.json
- canary/<TS>/build-identity.json exists with git SHA + version 1.42.1 (codex MEDIUM-CODEX-4)
- canary/<TS>/loaded_capture.ndjson contains all six Plan 201-13 diagnostic fields
- Predeploy gate ran BEFORE rollback snapshot (codex HIGH-CODEX-3)
- Active control knob assertion table populated, all five knobs verified live (codex MEDIUM-CODEX-3)
- Operator decision (pass/fail/abort) recorded
- One of three downstream paths executed correctly
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-SUMMARY.md` per the standard template. Include: re-canary timestamp, build identity (git SHA + version 1.42.1), verdict, primary_gate_value, ul_floor_hits_during_load, active control knob assertion outcome, snapshot ordering confirmation (post-gate-PASS), decision taken, downstream effect (soak unblocked / rollback complete / re-attempt staged), codex review findings closed (HIGH-CODEX-3, MEDIUM-CODEX-3, MEDIUM-CODEX-4).
</output>
