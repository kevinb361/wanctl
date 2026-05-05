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
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
autonomous: false
gap_closure: true
requirements: [VALN-06]
tags: [phase-201, gap-closure, canary, valn-06-primary, recanary, operator-gated, fail-closed]

must_haves:
  truths:
    - "Re-canary runs at the ORIGINAL setpoint_mbps=12 (NOT A5 fallback setpoint=10) — the operator-confirmed closure path is the control-model amendment, not the setpoint workaround"
    - "Re-canary uses the existing scripts/phase200-saturation-canary.sh extended in Plan 201-08; no new harness authored"
    - "Re-canary uses the existing scripts/phase201-predeploy-gate.sh from Plan 201-07; first run BLOCKs on residual rejected v1.41 keys, manual reconcile, second run PASSes"
    - "Pre-deploy snapshot: /opt/wanctl binary archive AND /etc/wanctl/spectrum.yaml — REVIEWS HIGH-7 dual-snapshot pattern, identical to 201-11"
    - "PRIMARY GATE: floor_hit_cycles_total_delta_loaded_window == 0 (zero-tolerance, REVIEWS HIGH-5 cycle-fidelity counter)"
    - "SECONDARY GATE: ul_floor_hits_during_load == 0 (1Hz cross-check; disagreement with primary produces FAIL with diagnostic reason, not PASS)"
    - "Loaded-window NDJSON capture includes the three new diagnostic fields landed in Plan 201-13 (max_delay_delta_us, red_streak, zone_trace) — confirmed by jq inspection of any captured row"
    - "On FAIL: rollback executes per D-10 / REVIEWS HIGH-7; both binary AND YAML restored; verified by post-rollback /health.version=1.39.0 AND grep counts of all new + existing Phase 201 YAML keys = 0 in /etc/wanctl/spectrum.yaml"
    - "On PASS: Plan 201-16 (24h soak) is unblocked; 201-15-CANARY-VERDICT.md records verdict=pass, primary_gate=0, captures floor_hit_cycles_total_loaded_window_end as the T+0 baseline for the soak"
    - "Canary verdict.json schema-compatible with 201-11 verdict.json (same fields, same primary_gate identifier) so Plan 201-12-style soak harness can ingest it without modification"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
      provides: "Canonical re-canary verdict; primary_gate value, secondary_gate value, baseline RTT bookends, env capture, rollback decision"
      contains: "primary_gate"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
      provides: "Operator-readable verdict mirroring 201-11-CANARY-VERDICT.md format"
      contains: "VALN-06"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json"
      to: ".planning/phases/201-docsis-aware-ul-congestion-control/201-16-soak-PLAN.md (or re-staged 201-12)"
      via: "verdict=pass unblocks soak; verdict=fail blocks soak and triggers next gap-closure cycle"
      pattern: "primary_gate"
    - from: "scripts/phase201-predeploy-gate.sh"
      to: "/etc/wanctl/spectrum.yaml on cake-shaper"
      via: "SSH probe + reconcile-or-block on residual rejected v1.41 keys"
      pattern: "predeploy-gate"
---

<objective>
**Gap-closure Plan 3 of 4. OPERATOR-GATED CHECKPOINT.** Re-run the Phase 201 saturation canary at `setpoint_mbps=12` against the v1.42 binary that contains the Plan 201-13 diagnostic fields and the Plan 201-14 control-model amendment.

This plan is the closure proof for the primary VERIFICATION.md gap (truth-1: floor_hit_cycles_total delta = 0 over loaded window). Per the operator-confirmed closure direction (path b — control-model amendment), this re-canary tests the FIX, not the setpoint workaround. A5 fallback at setpoint=10 stays explicitly OFF the table for this attempt; if this re-canary fails, A5 is the next operator decision (recorded in CONTEXT.md `## Deferred Ideas`).

Per CONTEXT.md D-11: reuse `scripts/phase200-saturation-canary.sh`. Per Plan 201-08: that script has already been extended for Phase 201 env-cross-check, /health DOCSIS-mode probe, max_delay_delta_us capture, and counter-delta verdict-decision. Per Plan 201-07: predeploy gate is in place. Per REVIEWS HIGH-7 / D-10: rollback restores both binary AND YAML.

The re-canary uses the EXACT same env vars as 201-11 (preserve evidentiary continuity) — only the binary on cake-shaper changes (because Plans 201-13 and 201-14 land new code). YAML can stay as in configs/spectrum.yaml at deploy time (which Plan 201-14 will update with the two new keys `sustained_red_cycles: 8`, `anti_windup_cycles: 60`).

Output: a `canary/<TIMESTAMP>/` directory with verdict.json, loaded_capture.ndjson, idle_capture.ndjson, and a 201-15-CANARY-VERDICT.md operator-readable summary. On PASS, Plan 201-16 (soak) proceeds. On FAIL, rollback executes and the next gap-closure planning cycle begins.

This plan is `autonomous: false` because it deploys to production (cake-shaper, wanctl@spectrum.service running 24/7) and may rollback. The operator MUST approve at the predeploy checkpoint and the post-canary checkpoint.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-VERIFICATION.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json
@.planning/phases/201-docsis-aware-ul-congestion-control/201-11-canary-execution-PLAN.md
@scripts/phase200-saturation-canary.sh
@scripts/phase201-predeploy-gate.sh
@scripts/deploy.sh
</context>

<interfaces>
<!-- The canary contract is FIXED by Plan 201-08. This plan invokes; it does not modify the script. -->

Required env (from canary 20260504T231334Z evidence + Plan 201-08):
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
# PHASE201_LOCAL_YAML_OVERRIDE unset (per 201-11 pattern)
```

Predeploy gate invocation (Plan 201-07 pattern):
```
./scripts/phase201-predeploy-gate.sh
# First run: BLOCK on residual v1.41 keys -> operator reconciles by SCP /etc/wanctl/spectrum.yaml or copies repo configs/spectrum.yaml
# Second run: PASS
```

Deploy invocation (201-11 verbatim):
```
REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
ssh cake-shaper sudo systemctl restart wanctl@spectrum.service
```

Verdict.json primary gate field (Plan 201-08): `primary_gate: "floor_hit_cycles_total_delta_loaded_window"`, `primary_gate_value: <int>`. PASS only if `primary_gate_value == 0` AND `ul_floor_hits_during_load == 0`. Disagreement = FAIL with diagnostic reason.

Rollback artifacts (REVIEWS HIGH-7 / D-10): pre-deploy `tar -czf /opt/wanctl-prephase201-recanary-<TS>.tar.gz /opt/wanctl` AND `cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>` BEFORE deploy. On FAIL, restore both, restart service, verify /health.version reverts to 1.39.0.
</interfaces>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Predeploy approval — verify Plans 201-13 + 201-14 landed and tests green; operator confirms re-canary go</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
    - configs/spectrum.yaml (verify sustained_red_cycles + anti_windup_cycles present)
  </read_first>
  <what-built>
    Plans 201-13 and 201-14 must be complete:
    - 201-13: /health.wans[0].upload now exposes max_delay_delta_us, red_streak, zone_trace (additive).
    - 201-14: queue_controller has floor-anchored RED decay below setpoint, push-down setpoint clamp, and integral anti-windup. All docsis_mode-gated. SAFE-05 byte-identity preserved.
    - configs/spectrum.yaml has explicit `sustained_red_cycles: 8` and `anti_windup_cycles: 60` under continuous_monitoring.upload.
  </what-built>
  <how-to-verify>
    1. Confirm summaries exist:
       ```
       ls .planning/phases/201-docsis-aware-ul-congestion-control/201-13-SUMMARY.md
       ls .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
       ```
       Both must exist.

    2. Confirm hot-path slice green:
       ```
       .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
       ```
       Exit code 0.

    3. Confirm new YAML keys live in repo:
       ```
       grep -E "sustained_red_cycles|anti_windup_cycles" configs/spectrum.yaml
       ```
       Must show both values (8 and 60).

    4. Confirm new diagnostic fields wired:
       ```
       grep -E '"zone_trace"|"red_streak"|"max_delay_delta_us"' src/wanctl/queue_controller.py src/wanctl/health_check.py
       ```
       Must show >= 6 hits across both files.

    5. Operator decides: proceed with re-canary at setpoint_mbps=12, or hold for additional review.
  </how-to-verify>
  <resume-signal>Type "approved" to proceed to Task 2 (predeploy gate + canary execution), or describe blockers.</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved"
    - Both prerequisite SUMMARY files exist
    - Hot-path slice exits 0
    - configs/spectrum.yaml has both new keys
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 2: Run predeploy gate, snapshot rollback artifacts, deploy v1.42, verify /health DOCSIS-mode active</name>
  <read_first>
    - scripts/phase201-predeploy-gate.sh
    - scripts/deploy.sh
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md (Pre-deploy Reconciliation section, lines 13-19)
  </read_first>
  <files>
    /opt/wanctl-prephase201-recanary-<TS>.tar.gz (on cake-shaper, pre-deploy snapshot),
    /etc/wanctl/spectrum.yaml.prephase201-recanary-<TS> (on cake-shaper, pre-deploy snapshot)
  </files>
  <action>
    1. **Set TS variable** for this re-canary attempt:
       ```
       export RECANARY_TS=$(date -u +%Y%m%dT%H%M%SZ)
       echo "Re-canary timestamp: $RECANARY_TS"
       ```

    2. **Snapshot rollback artifacts on cake-shaper** (REVIEWS HIGH-7 / D-10 dual-snapshot pattern; mirror 201-11):
       ```
       ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz -C / opt/wanctl"
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}"
       ssh cake-shaper "ls -lh /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}"
       ```
       Both files must exist with non-zero size.

    3. **Run predeploy gate** (Plan 201-07):
       ```
       ./scripts/phase201-predeploy-gate.sh
       ```
       If first run BLOCKs on rejected v1.41 keys, reconcile by overwriting `/etc/wanctl/spectrum.yaml` from local `configs/spectrum.yaml`:
       ```
       scp configs/spectrum.yaml cake-shaper:/tmp/spectrum.yaml.new
       ssh cake-shaper "sudo install -o root -g wanctl -m 0640 /tmp/spectrum.yaml.new /etc/wanctl/spectrum.yaml"
       ./scripts/phase201-predeploy-gate.sh   # second run must PASS
       ```

    4. **Deploy v1.42 binary** (201-11 invocation verbatim):
       ```
       REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
       ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
       sleep 5
       ```

    5. **Verify post-deploy /health**:
       ```
       curl -s http://10.10.110.223:9101/health | jq '{
         version: .version,
         docsis_mode_active: .wans[0].upload.docsis_mode_active,
         setpoint_mbps: .wans[0].upload.setpoint_mbps,
         floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
         max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
         red_streak: .wans[0].upload.red_streak,
         zone_trace_len: (.wans[0].upload.zone_trace | length)
       }'
       ```
       Required values:
       - `version` == "1.42.0" (or whatever the post-201-14 binary reports)
       - `docsis_mode_active` == true
       - `setpoint_mbps` == 12.0
       - `floor_hit_cycles_total` == 0
       - `max_delay_delta_us` is an int (NOT null) — proves Plan 201-13 wired it
       - `red_streak` is an int >= 0 — proves Plan 201-13 wired it
       - `zone_trace_len` >= 1 — proves the ring buffer is being filled

       If ANY field is missing or wrong-typed, ABORT — do NOT proceed to Task 3. Record the failure mode in 201-15-CANARY-VERDICT.md and route back to Plan 201-13 or 201-14 for a fix.

    6. **Record predeploy state** in `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md` (create file with the same section structure as 201-11-CANARY-VERDICT.md). Capture:
       - RECANARY_TS value
       - Rollback artifact paths and sizes
       - Predeploy gate run results (first run BLOCK reason, second run PASS)
       - Post-deploy /health snapshot from step 5
  </action>
  <verify>
    <automated>ssh cake-shaper "ls /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS}" 2>&1 | grep -c "wanctl-prephase201" | grep -qE '^[12]$'</automated>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.wans[0].upload.docsis_mode_active == true and .wans[0].upload.setpoint_mbps == 12.0 and (.wans[0].upload.max_delay_delta_us | type == "number") and (.wans[0].upload.red_streak | type == "number") and (.wans[0].upload.zone_trace | type == "array")'</automated>
  </verify>
  <acceptance_criteria>
    - Both rollback snapshots exist on cake-shaper with non-zero size
    - Predeploy gate exits 0 on second run
    - /health.version reflects v1.42 binary
    - /health.wans[0].upload.docsis_mode_active == true
    - /health.wans[0].upload.setpoint_mbps == 12.0
    - /health.wans[0].upload.{max_delay_delta_us, red_streak, zone_trace} all present and correctly typed
    - 201-15-CANARY-VERDICT.md exists with predeploy section populated
  </acceptance_criteria>
  <done>
    v1.42 binary deployed with snapshots in place, /health confirms DOCSIS-mode active and all six new diagnostic fields live. Ready for canary execution.
  </done>
</task>

<task type="auto">
  <name>Task 3: Execute saturation canary; capture verdict.json + loaded_capture.ndjson; consume primary gate</name>
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
       The script writes to `$PHASE200_OUT_DIR/canary/<TS>/`. Capture the actual TS the script chose (it generates its own UTC timestamp; the script's TS may differ from RECANARY_TS by a few seconds).

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

    4. **Confirm Plan 201-13 diagnostic fields landed in capture**:
       ```
       head -1 "$CANARY_DIR/loaded_capture.ndjson" | jq '{
         max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
         red_streak: .wans[0].upload.red_streak,
         zone_trace_len: (.wans[0].upload.zone_trace | length)
       }'
       ```
       All three fields must be present in at least one captured row. If absent, the canary script (Plan 201-08) didn't pick them up — that's a downstream gap, not a control-model failure.

    5. **Append canary results section to 201-15-CANARY-VERDICT.md**: capture the full verdict.json contents, key field values, and a brief inline analysis (e.g. "primary_gate_value=0; FAIL margin closed from 1453 to 0").
  </action>
  <verify>
    <automated>ls .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | sort -r | head -1</automated>
    <automated>jq -e '.primary_gate == "floor_hit_cycles_total_delta_loaded_window"' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)</automated>
    <automated>head -1 $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/loaded_capture.ndjson | head -1) | jq -e '.wans[0].upload.zone_trace | type == "array"'</automated>
  </verify>
  <acceptance_criteria>
    - verdict.json exists with `primary_gate == "floor_hit_cycles_total_delta_loaded_window"`
    - loaded_capture.ndjson contains the three Plan 201-13 fields per captured row
    - 201-15-CANARY-VERDICT.md updated with canary results section
    - The canary completed without operator-side abort (verdict is "pass" or "fail", NOT "abort")
  </acceptance_criteria>
  <done>
    Canary executed; verdict.json captured; diagnostic fields confirmed live in NDJSON. Ready for verdict-based decision.
  </done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 4: Operator verdict decision — PASS proceeds to soak; FAIL triggers rollback + re-plan</name>
  <decision>
    The canary verdict.json has been written. Operator must decide the next action based on the verdict value.
  </decision>
  <context>
    Reading verdict.json:
    - PRIMARY GATE: `primary_gate_value` (== `floor_hit_cycles_total_delta_loaded_window`). MUST be 0 for PASS.
    - SECONDARY GATE: `ul_floor_hits_during_load`. MUST be 0 for PASS.
    - DISAGREEMENT (one is 0 and the other is not) is automatic FAIL with a diagnostic reason — operator should still confirm the disagreement direction.

    Read the verdict:
    ```
    jq '{verdict, reason, primary_gate_value, ul_floor_hits_during_load}' \
      $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
    ```
  </context>
  <options>
    <option id="pass">
      <name>PASS — primary_gate_value == 0 AND ul_floor_hits_during_load == 0</name>
      <pros>VALN-06 primary gate met; control-model amendment is proven on production hardware; Plan 201-16 (24h soak) is unblocked</pros>
      <cons>None — this is the goal state</cons>
    </option>
    <option id="fail">
      <name>FAIL — primary_gate_value > 0 OR ul_floor_hits_during_load > 0 OR disagreement</name>
      <pros>Honest negative result; rollback restores production to v1.39.0 binary + pre-Phase-201 YAML; the next gap-closure planning cycle has fresh evidence</pros>
      <cons>Phase 201 stays at gaps_found; may require A5 fallback (setpoint=10) re-canary or deeper control-model work in v1.43+</cons>
    </option>
    <option id="abort">
      <name>ABORT — environment failure (network unreachable, iperf3 target down, /health unreachable, etc.)</name>
      <pros>Distinguishes environmental noise from actual control-model failure; preserves the v1.42 binary for a re-attempt</pros>
      <cons>Re-canary must be re-staged once environment is healthy</cons>
    </option>
  </options>
  <resume-signal>Type one of: "pass", "fail", or "abort". On "fail", Task 5 (rollback) executes automatically. On "pass", proceed to Task 6 (close out the verdict file). On "abort", proceed to Task 7 (environment-failure cleanup, no rollback).</resume-signal>
  <acceptance_criteria>
    - Operator entered "pass", "fail", or "abort"
    - Decision recorded in 201-15-CANARY-VERDICT.md "Decision" section (mirror 201-11-CANARY-VERDICT.md format)
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 5: On FAIL — execute rollback (binary + YAML); verify /health.version=1.39.0; record rollback verification</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md (Rollback + Rollback Verification sections, lines 64-86)
  </read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 4 returned "fail". Skip on "pass" or "abort".

    1. **Restore binary**:
       ```
       ssh cake-shaper "sudo systemctl stop wanctl@spectrum.service"
       ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase201-recanary-${RECANARY_TS}.tar.gz -C /"
       ```

    2. **Restore YAML**:
       ```
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml.prephase201-recanary-${RECANARY_TS} /etc/wanctl/spectrum.yaml"
       ssh cake-shaper "sudo chown root:wanctl /etc/wanctl/spectrum.yaml && sudo chmod 0640 /etc/wanctl/spectrum.yaml"
       ```

    3. **Restart service**:
       ```
       ssh cake-shaper "sudo systemctl start wanctl@spectrum.service"
       sleep 5
       ```

    4. **Verify rollback** (REVIEWS HIGH-7 dual verification — both binary and YAML):
       ```
       curl -s http://10.10.110.223:9101/health | jq '{version, status}'
       # Expected: version="1.39.0", status="healthy"

       # WARNING 5 fix: anchored per-key grep prevents false positives from YAML comments
       # that mention these key names (e.g. comment-block prose in spectrum.yaml).
       # Each key must be matched as a top-level YAML key (indented, followed by colon),
       # not as a substring inside a # comment line.
       ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|sustained_red_cycles|anti_windup_cycles):' /etc/wanctl/spectrum.yaml"
       # Expected: 0 (all 8 keys absent at YAML-key positions; comment text containing these names ignored)
       ```
       NOTE: this restored YAML is from the predeploy snapshot (Task 2), which itself may have been the post-201-11-rollback YAML (no Phase 201 keys). Both readings must show 0 for ALL eight Phase 201 + Phase 201-gap-closure keys.

    5. **Append rollback section to 201-15-CANARY-VERDICT.md** (mirror 201-11-CANARY-VERDICT.md Rollback + Rollback Verification sections). Include the post-rollback /health.version, /health.status, and the YAML grep counts table for all 8 keys.
  </action>
  <verify>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version == "1.39.0" and .status == "healthy"'</automated>
    <automated>ssh cake-shaper "sudo grep -cE '^[[:space:]]+(docsis_mode|setpoint_mbps|integral_window_seconds|integral_threshold_ms_s|cake_backlog_low_threshold_bytes|cake_delay_delta_low_threshold_us|sustained_red_cycles|anti_windup_cycles):' /etc/wanctl/spectrum.yaml" | tr -d '[:space:]' | grep -qE '^0$'</automated>
  </verify>
  <acceptance_criteria>
    - /health.version == "1.39.0"
    - /health.status == "healthy"
    - All 8 Phase 201 + gap-closure YAML keys grep count to 0 in /etc/wanctl/spectrum.yaml
    - 201-15-CANARY-VERDICT.md Rollback section populated with verification table
  </acceptance_criteria>
  <done>
    Production restored to pre-Phase-201 state. Phase 201 stays at gaps_found. Operator may now author the next gap-closure cycle (e.g. A5 fallback re-canary at setpoint=10) or close Phase 201 to v1.43+.
  </done>
</task>

<task type="auto">
  <name>Task 6: On PASS — finalize 201-15-CANARY-VERDICT.md; capture T+0 baseline for soak; unblock Plan 201-16</name>
  <read_first>
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-12-soak-and-closeout-PLAN.md (Step 1.5 T+0 baseline pattern, lines 22-24 of frontmatter)
  </read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 4 returned "pass". Skip on "fail" or "abort".

    1. **Capture T+0 soak baseline** from the canary verdict (REVIEWS round-5 / Plan 201-12 step 1.5 pattern):
       ```
       VERDICT_FILE=$(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)
       T0_BASELINE=$(jq -r '.floor_hit_cycles_total_loaded_window_end' "$VERDICT_FILE")
       echo "Soak T+0 baseline: $T0_BASELINE"
       ```
       This is the floor_hit_cycles_total counter value at the end of the canary's loaded window. The 24h soak (Plan 201-16) will subtract this from the counter at soak end to compute its primary gate.

    2. **Append PASS verdict section to 201-15-CANARY-VERDICT.md**:
       - Verdict: PASS
       - Primary gate value: 0
       - Secondary gate value: 0
       - Soak T+0 baseline: $T0_BASELINE
       - Live /health snapshot post-canary (curl + jq filter same as Task 2 step 5)
       - Decision: proceed to Plan 201-16 (24h soak)

    3. **Verify v1.42 stays deployed**:
       ```
       curl -s http://10.10.110.223:9101/health | jq -e '.version != "1.39.0"'
       ```
       v1.42 binary stays in place; YAML stays as deployed. No rollback. Plan 201-16 deploys ON TOP of this binary state.
  </action>
  <verify>
    <automated>jq -e '.verdict == "pass" and .primary_gate_value == 0 and .ul_floor_hits_during_load == 0' $(ls -t .planning/phases/201-docsis-aware-ul-congestion-control/canary/*/verdict.json | head -1)</automated>
    <automated>grep -q "Soak T+0 baseline" .planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</automated>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.version != "1.39.0"'</automated>
  </verify>
  <acceptance_criteria>
    - verdict.json shows verdict=pass, primary_gate_value=0, ul_floor_hits_during_load=0
    - 201-15-CANARY-VERDICT.md records Soak T+0 baseline value
    - v1.42 binary remains deployed (not rolled back)
    - Plan 201-16 (24h soak) is unblocked
  </acceptance_criteria>
  <done>
    Re-canary PASS recorded; Soak T+0 baseline captured; control-model amendment proven on production. Plan 201-16 may proceed.
  </done>
</task>

<task type="auto">
  <name>Task 7: On ABORT — record environment-failure context; do NOT rollback; preserve v1.42 for re-attempt</name>
  <read_first>None additional</read_first>
  <files>.planning/phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md</files>
  <action>
    Execute ONLY if Task 4 returned "abort". Skip on "pass" or "fail".

    1. **Record abort reason** in 201-15-CANARY-VERDICT.md "Decision" section:
       - Verdict from verdict.json (likely "abort" or partial — script may have fail-closed before producing a verdict)
       - Specific environment failure observed (e.g. iperf3 target unreachable, /health 502, network down)
       - State of cake-shaper deployment: v1.42 binary stays in place, YAML stays as deployed (NO rollback for environment failures)

    2. **Do NOT rollback.** Operator re-runs the canary (Tasks 3-4) once environment is healthy.

    3. **Confirm wanctl service is still healthy**:
       ```
       curl -s http://10.10.110.223:9101/health | jq '{version, status}'
       ssh cake-shaper "sudo systemctl is-active wanctl@spectrum.service"
       ```
       Both must show healthy / active. If they don't, escalate to manual operator intervention — environment failure that took the daemon down is NOT in this plan's scope.
  </action>
  <verify>
    <automated>curl -s http://10.10.110.223:9101/health | jq -e '.status == "healthy"'</automated>
    <automated>ssh cake-shaper "sudo systemctl is-active wanctl@spectrum.service" | tr -d '[:space:]' | grep -qE '^active$'</automated>
  </verify>
  <acceptance_criteria>
    - 201-15-CANARY-VERDICT.md records abort reason
    - wanctl@spectrum.service still active
    - /health responding healthy on v1.42 binary
    - No rollback executed
  </acceptance_criteria>
  <done>
    Environment failure documented; v1.42 binary preserved; Tasks 3-4 may be re-run after environment recovery.
  </done>
</task>

</tasks>

<verification>
End-of-plan state varies by Task 4 verdict:

- **PASS**: Plan 201-16 unblocked; v1.42 binary deployed; 201-15-CANARY-VERDICT.md records pass + T+0 baseline
- **FAIL**: Production rolled back to v1.39.0; YAML clean of all Phase 201 keys; 201-15-CANARY-VERDICT.md records fail + rollback verification table
- **ABORT**: v1.42 binary preserved; no rollback; 201-15-CANARY-VERDICT.md records abort reason
</verification>

<success_criteria>
- 201-15-CANARY-VERDICT.md exists with predeploy + canary + decision sections populated
- canary/<TS>/verdict.json exists, schema-compatible with 201-11 verdict.json
- canary/<TS>/loaded_capture.ndjson contains the three Plan 201-13 diagnostic fields
- Operator decision (pass/fail/abort) recorded
- One of three downstream paths executed correctly (PASS unblocks soak; FAIL rolls back; ABORT preserves)
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-15-SUMMARY.md` per the standard template. Include: re-canary timestamp, verdict, primary_gate_value, ul_floor_hits_during_load, decision taken, downstream effect (soak unblocked / rollback complete / re-attempt staged).
</output>
