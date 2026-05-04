---
phase: 201-docsis-aware-ul-congestion-control
plan: 11
type: execute
wave: 7
depends_on: [10]
files_modified:
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/loaded_capture.ndjson
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/loaded_iperf_summary.json
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/pre_idle_baseline.ndjson
  - .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/post_idle_baseline.ndjson
  - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
autonomous: false
requirements: [VALN-06]
tags: [phase-201, wave-7, canary, manual, valn-06-primary-gate, fail-closed]

must_haves:
  truths:
    - "Predeploy gate (scripts/phase201-predeploy-gate.sh) PASSED against /etc/wanctl/spectrum.yaml on the deploy target"
    - "v1.42.0 binary deployed to /opt/wanctl on cake-shaper; previous version archived to /opt/wanctl-prephase201-<TIMESTAMP>.tar.gz for rollback (D-10 mirror)"
    - "wanctl@spectrum.service restarted; /health.wans[].upload.docsis_mode_active reports true"
    - "Canary preflight passed: env-vs-YAML cross-check, /health DOCSIS-mode probe, remote-deps check all green"
    - "10-15 min iperf3 -P4 saturated UL canary at 18 Mbit ceiling completed"
    - "verdict.json reports ul_floor_hits_during_load = 0 (VALN-06 zero-floor-hit gate; D-13 NO RELAXATION)"
    - "Pre/post idle baseline RTTs bookend the run (proves fault-isolation on the test path itself)"
    - "REVIEWS HIGH-7 (2026-05-04): rollback restores BOTH /opt/wanctl (binary archive) AND /etc/wanctl/spectrum.yaml (from spectrum.yaml.prephase201 snapshot taken in Task 1 step 0); rollback verification asserts /etc/wanctl/spectrum.yaml no longer contains 'docsis_mode:' after rollback completes — leaving v1.42 YAML keys under v1.40 binary is undefined behavior"
    - "REVIEWS HIGH-5 (2026-05-04): canary verdict gates on `floor_hit_cycles_total` DELTA across the loaded window (computed as end-of-loaded-window minus start-of-loaded-window from /health.wans[0].upload.floor_hit_cycles_total). Delta == 0 is the VALN-06 PASS condition. 1 Hz /health snapshot rate-comparison is RETAINED as a secondary cross-check but is NOT the primary gate (1 Hz is 1000x coarser than the 50ms cycle interval — would miss sub-second floor touches)."
    - "On canary FAIL: D-10 rollback executed (v1.42 binary AND YAML replaced with prior snapshot); operator records the rolled-back state" 
    - "On canary PASS: operator approves Plan 201-12 (24h soak)"
  artifacts:
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
      provides: "Canary verdict per phase200-saturation-canary.sh schema"
      contains: "ul_floor_hits_during_load"
    - path: .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
      provides: "Operator-readable canary outcome + decisions"
      contains: "Canary verdict"
  key_links:
    - from: ".planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md"
      to: ".planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json"
      via: "operator copies verdict + interprets it"
      pattern: "verdict.json"
---

<objective>
Wave 6 live canary execution. The PRIMARY VALN-06 closure gate. Per D-13: zero floor hits, no relaxation. Same fail-closed rollback shape as Phase 200 D-10.

This is a manual-only checkpoint because the canary requires (a) live ISP link, (b) 10-15 min `iperf3 -P4` saturated upload against an internet endpoint, (c) operator SSH access to the deploy target, (d) operator approval of the deploy command. None of this is CI-runnable.

Phase 200 Attempt 3 produced 4 floor hits with the v1.41 stack. Phase 201's contract is ZERO. If the canary fails, RESEARCH §4 prescribed fallback: drop setpoint to 10 Mbit (parameter tune, NOT control-model rejection); a re-canary-attempt under setpoint=10 is allowed without re-architecting.

Output: timestamped canary directory with the standard Phase 200 capture shape; 201-11-CANARY-VERDICT.md operator-readable summary; rollback artifact (whether canary passes or fails — pre-archive captured BEFORE deploy).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-10-CODEX-STOP-TIME-REVIEW.md
@scripts/phase200-saturation-canary.sh
@scripts/phase201-predeploy-gate.sh
@scripts/deploy.sh
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Pre-deploy archive + predeploy gate + deploy v1.42.0 to cake-shaper</name>
  <what-built>
    Stop-time review (Plan 201-10) is GO. v1.42.0 binary exists locally and tests are green. Production is on v1.40 binary post-rollback (per Phase 200 closure). /etc/wanctl/spectrum.yaml on the deploy target carries v1.41-only inactive keys that MUST be reconciled before the v1.42 binary moves.
  </what-built>
  <how-to-verify>
    Operator MUST execute:

    1. **Capture pre-deploy archive AND YAML snapshot** (rollback artifacts for D-10 + REVIEWS HIGH-7):
       ```
       TS=$(date -u +%Y%m%dT%H%M%SZ)
       # (a) /opt/wanctl binary archive
       ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase201-${TS}.tar.gz -C /opt/wanctl ."
       ssh cake-shaper "ls -la /opt/wanctl-prephase201-*.tar.gz | tail -1"
       # (b) REVIEWS HIGH-7: /etc/wanctl/spectrum.yaml snapshot.
       # Without this, rollback would leave v1.42 YAML keys (docsis_mode,
       # setpoint_mbps, integral_window_seconds, etc.) on disk under the
       # restored v1.40 binary — undefined behavior (validator may fail
       # closed, silent-drop unknown keys, or fall through to legacy paths
       # that never knew about them).
       ssh cake-shaper "sudo cp -p /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201-${TS}"
       ssh cake-shaper "ls -la /etc/wanctl/spectrum.yaml.prephase201-*"
       ```
       Record BOTH artifact paths in `.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md` `## Rollback Artifacts` section. The TS variable is the SAME for both so they pair cleanly during rollback.

    2. **Reconcile /etc/wanctl/spectrum.yaml on the deploy target.**
       Run the predeploy gate manually first to see what's flagged:
       ```
       REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml \
           bash scripts/phase201-predeploy-gate.sh
       ```
       The gate is expected to BLOCK with messages citing `target_bloat_ms` and `warn_bloat_ms` (still on /etc/wanctl/spectrum.yaml from Phase 200 closure). Reconcile per RESEARCH §5:
       - REMOVE `continuous_monitoring.upload.target_bloat_ms`
       - REMOVE `continuous_monitoring.upload.warn_bloat_ms`
       - ADD `continuous_monitoring.upload.docsis_mode: true`
       - ADD `continuous_monitoring.upload.setpoint_mbps: 12`
       - ADD `continuous_monitoring.upload.integral_window_seconds: 2.0`
       - ADD `continuous_monitoring.upload.integral_threshold_ms_s: 30.0`
       - ADD `continuous_monitoring.upload.cake_backlog_low_threshold_bytes: 5000`
       - ADD `continuous_monitoring.upload.cake_delay_delta_low_threshold_us: 5000`
       - KEEP `continuous_monitoring.upload.factor_down_yellow: 1.0`
       - KEEP `continuous_monitoring.upload.consecutive_yellow_decay_clamp: 40`
       - KEEP `continuous_monitoring.upload.floor_mbps: 8`
       - KEEP `continuous_monitoring.upload.ceiling_mbps: 18`

       Edit via:
       ```
       ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase201"
       ssh cake-shaper "sudo nano /etc/wanctl/spectrum.yaml"   # or vi/sed/etc.
       ```

       Re-run the gate; expect PASS:
       ```
       REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml \
           bash scripts/phase201-predeploy-gate.sh
       echo "exit=$?"   # expect 0
       ```

    3. **Deploy v1.42.0 binary** via `scripts/deploy.sh` (which now invokes the gate inline as a redundancy check). Operator confirms the deploy. Then restart:
       ```
       ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
       ssh cake-shaper "sleep 5 && sudo systemctl status wanctl@spectrum.service --no-pager | head -20"
       ```

    4. **Confirm /health reports v1.42 + DOCSIS-mode active**:
       ```
       ssh cake-shaper "curl -sS http://127.0.0.1:9101/health" \
           | jq '.version, .wans[0].upload.docsis_mode_active, .wans[0].upload.setpoint_mbps, .wans[0].upload.headroom_state'
       ```
       Expected: `"1.42.0"`, `true`, `12`, `"EXHAUSTED"` (or AVAILABLE if idle long enough).

    Record each step's output in 201-11-CANARY-VERDICT.md `## Deploy Steps` section.
  </how-to-verify>
  <resume-signal>
    After v1.42.0 is deployed, daemon restarted, and `/health` confirms `docsis_mode_active=true`, type "deployed" to proceed to Task 2 (canary run).

    If anything in Task 1 fails (predeploy gate keeps blocking, daemon won't start, /health doesn't show DOCSIS-active), STOP and type "deploy-failed" + the specific failure mode. The orchestrator routes to gap-closure planning; rollback may be needed even before the canary runs.
  </resume-signal>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 2: Run 10-15 min iperf3 -P4 saturated UL canary; collect verdict</name>
  <what-built>
    v1.42.0 is live on cake-shaper:wanctl@spectrum.service. /health reports docsis_mode_active=true, setpoint_mbps=12, ceiling=18. Canary script + env template have Phase 201 extensions.
  </what-built>
  <how-to-verify>
    Operator MUST execute:

    1. **Set up canary env file** (operator's local copy of `scripts/phase200-saturation-canary.env.example`):
       ```
       PHASE200_OUT_DIR=".planning/phases/201-docsis-aware-ul-congestion-control"
       PHASE200_SPECTRUM_HEALTH_URL="http://10.10.110.223:9101/health"
       PHASE200_IPERF_TARGET="<operator-supplied iperf3 server>"
       PHASE200_IPERF_LOCAL_BIND="<operator-supplied local Spectrum-bound IP>"
       PHASE200_UL_FLOOR_MBPS=8
       PHASE200_UL_CEILING_MBPS=18
       PHASE200_REMOTE_YAML_SSH="<operator-ssh-user>@10.10.110.223:/etc/wanctl/spectrum.yaml"
       # Phase 201 D-12 additions:
       PHASE201_DOCSIS_MODE=true
       PHASE201_SETPOINT_MBPS=12
       ```

    2. **Run the canary**:
       ```
       set -a; source <env-file>; set +a
       bash scripts/phase200-saturation-canary.sh
       ```
       Expected duration: 15-20 minutes (60s pre-baseline + 900s loaded + 60s post-baseline + summarization).

    3. **Locate the canary output directory**: `.planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/`. Verify these files:
       - `verdict.json`
       - `loaded_capture.ndjson` (>= 800 lines for a 900s loaded window at 1 Hz)
       - `loaded_iperf_summary.json`
       - `pre_idle_baseline.ndjson` + `pre_idle_baseline.json`
       - `post_idle_baseline.ndjson` + `post_idle_baseline.json`

    4. **Read the verdict (REVIEWS HIGH-5: counter delta is PRIMARY GATE)**:
       ```
       # Primary gate: cycle-fidelity floor_hit_cycles_total delta across loaded window.
       # Plan 08 canary script captures /health snapshots at start-of-loaded-window
       # and end-of-loaded-window; verdict.json publishes the delta as a top-level field.
       jq '.verdict,
           .floor_hit_cycles_total_delta_loaded_window,
           .ul_floor_hits_during_load,
           .baseline_rtt_pre_p50, .baseline_rtt_post_p50' \
           .planning/phases/201-docsis-aware-ul-congestion-control/canary/<TIMESTAMP>/verdict.json
       ```
       VALN-06 PASS condition (REVIEWS HIGH-5):
       - `verdict == "pass"` AND
       - `floor_hit_cycles_total_delta_loaded_window == 0` (PRIMARY — cycle-fidelity 50ms counter delta) AND
       - `ul_floor_hits_during_load == 0` (SECONDARY cross-check — 1 Hz snapshot rate compare) AND
       - `baseline_rtt_pre_p50` close to `baseline_rtt_post_p50` (within ~3 ms — proves the test path itself is fault-isolated).

       The 1 Hz snapshot rate compare REMAINS as a defense-in-depth cross-check. If the two metrics disagree (e.g., counter delta == 0 but ul_floor_hits_during_load > 0, or vice versa), STOP and investigate — this is a sign of either a counter-increment bug in Plan 04 OR a /health serialization gap in Plan 05.

    5. **Capture the operator-readable verdict** in 201-11-CANARY-VERDICT.md:

       ```
       # Phase 201 — Canary Verdict (VALN-06 Primary Gate)

       **Captured:** YYYY-MM-DD HH:MM UTC
       **Capture path:** canary/<TIMESTAMP>/

       ## Pre-deploy Reconciliation
       - Predeploy gate first run: <BLOCK message excerpt>
       - YAML edits applied: <list of REMOVED/ADDED keys>
       - Predeploy gate second run: PASS

       ## Deploy
       - Pre-deploy archive: /opt/wanctl-prephase201-<TS>.tar.gz
       - Binary version after restart: 1.42.0 (per /health.version)
       - /health.wans[0].upload.docsis_mode_active: true
       - /health.wans[0].upload.setpoint_mbps: 12

       ## Canary
       - Pre-idle baseline RTT p50: <value> ms
       - Loaded window duration: <s>
       - **floor_hit_cycles_total at loaded-window start: <value>** (REVIEWS HIGH-5 — primary cycle-fidelity gate)
       - **floor_hit_cycles_total at loaded-window end: <value>**
       - **floor_hit_cycles_total delta (PRIMARY VERDICT): <value>** — MUST be 0 for VALN-06 PASS
       - ul_floor_hits_during_load (1 Hz secondary cross-check): <value>
       - Post-idle baseline RTT p50: <value> ms
       - Verdict: PASS | FAIL
       - verdict.json reason: <verbatim>

       ## Decision
       - [ ] PASS -> proceed to Plan 201-12 (24h soak)
       - [ ] FAIL -> execute rollback below; consider re-canary attempt at setpoint_mbps=10 per RESEARCH §4 fallback
       - [ ] ABORT -> verdict.json shows ABORT verdict; environment issue; remediate per verdict reason and re-run

       ## Rollback (executed if FAIL — REVIEWS HIGH-7: BOTH binary AND YAML)
       - `ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase201-<TS>.tar.gz -C /opt/wanctl"`  # binary restore
       - `ssh cake-shaper "sudo cp -p /etc/wanctl/spectrum.yaml.prephase201-<TS> /etc/wanctl/spectrum.yaml"`  # YAML restore (REVIEWS HIGH-7)
       - `ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"`
       - Confirm /health.version == previous baseline (1.41.0 or 1.40.0 — operator records)
       - **REVIEWS HIGH-7 verification:** assert v1.42 YAML keys are gone after restore:
         ```
         ssh cake-shaper "sudo cat /etc/wanctl/spectrum.yaml" | grep -c 'docsis_mode:'      # MUST return 0
         ssh cake-shaper "sudo cat /etc/wanctl/spectrum.yaml" | grep -c 'setpoint_mbps:'    # MUST return 0
         ssh cake-shaper "sudo cat /etc/wanctl/spectrum.yaml" | grep -c 'integral_window_seconds:'  # MUST return 0
         ```
         Record the grep counts in 201-11-CANARY-VERDICT.md `## Rollback Verification` section. If ANY grep returns non-zero, the YAML restore failed — STOP and investigate before declaring rollback complete.
       ```

    6. **On FAIL, execute rollback**. The full rollback command is in `verdict.json` as `rollback_protocol` (Phase 200 D-10 mirror). After rollback, type "fail-rollback-complete". Re-canary at setpoint=10 is a separate operator decision; if pursued, edit /etc/wanctl/spectrum.yaml `setpoint_mbps: 10` and re-run from Task 1.

    7. **On PASS**, commit the canary directory + 201-11-CANARY-VERDICT.md with `docs(201): canary VALN-06 PASS at setpoint=12`. Operator records the final test-suite pass count and continues to Plan 201-12.
  </how-to-verify>
  <resume-signal>
    After capturing verdict and committing 201-11-CANARY-VERDICT.md:

    PASS -> type "canary-pass" to proceed to Plan 201-12 (24h soak).
    FAIL -> type "canary-fail-setpoint-12-rolled-back" + operator's re-attempt decision (re-canary at setpoint=10? Or escalate to gap-closure planning?).
    ABORT -> type "canary-abort" + the verdict.json reason; the environment must be remediated before any retry.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator workstation -> production cake-shaper VM | SSH+sudo deploy + restart. Existing Phase 200 trust shape. |
| canary runner -> ISP -> internet iperf3 server | Real ISP path; no mitigation possible (the canary IS the test). |
| /health endpoint -> canary script | Read-only HTTP; same as Phase 200. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-47 | Tampering | Operator skips predeploy gate ("I know the YAML is fine") | mitigate | deploy.sh now invokes the gate inline (Plan 201-07 Task 2); manual run in Task 1 above is a redundancy. |
| T-201-48 | Tampering | Pre-deploy archive missing -> rollback impossible | mitigate | Task 1 step 1 captures the archive BEFORE any /opt/wanctl write; archive path recorded in verdict.md. |
| T-201-49 | DoS to production | Canary takes Spectrum offline for non-canary work | accept | 15-min window scheduled by operator; same risk profile as Phase 200 canaries. |
| T-201-50 | Tampering | False-PASS due to env-var drift | mitigate | Phase 201 canary preflight extension (Plan 201-08) cross-checks PHASE201_DOCSIS_MODE + PHASE201_SETPOINT_MBPS; mismatch ABORTs. |
| T-201-51 | Repudiation | Canary verdict not recorded | mitigate | 201-11-CANARY-VERDICT.md is required artifact; verdict.json is canonical. |
| T-201-52 | Tampering | Operator forgets to reconcile YAML (R0 keys still present) | mitigate | Predeploy gate BLOCKS; canary preflight `/health` probe also asserts docsis_mode_active=true. Two layers. |
| T-201-52a | Tampering | **REVIEWS HIGH-7:** Rollback restores v1.40 binary but leaves v1.42 YAML keys in place — undefined behavior under old binary | mitigate | Task 1 step 1 captures `/etc/wanctl/spectrum.yaml.prephase201-<TS>` snapshot BEFORE deploy. Rollback restores BOTH /opt/wanctl (binary) AND /etc/wanctl/spectrum.yaml (config). Acceptance grep asserts `docsis_mode:` is absent from spectrum.yaml after rollback. |
| T-201-52b | Tampering | **REVIEWS HIGH-5:** 1 Hz /health snapshot misses 50ms floor touches (1000x coarser than control loop), canary falsely PASS | mitigate | New `floor_hit_cycles_total` runtime counter (Plan 04-T2 + Plan 05-T2) provides cycle-fidelity (50ms) evidence. Plan 11-T2 verdict gate is counter-delta-PRIMARY, snapshot-rate-SECONDARY. |
</threat_model>

<verification>
- canary/<TIMESTAMP>/verdict.json exists with `verdict == "pass"` AND `ul_floor_hits_during_load == 0`.
- 201-11-CANARY-VERDICT.md committed with operator decision.
- Pre-deploy archive path recorded.
- Predeploy gate ran twice (first BLOCK to surface keys, second PASS after reconcile).
- /health confirms 1.42.0 + docsis_mode_active=true post-deploy.
- On FAIL: rollback executed; operator decision on re-canary documented.
</verification>

<success_criteria>
- Primary VALN-06 gate passed live: zero loaded-window floor hits.
- D-13 zero-floor-hit gate honored without relaxation.
- D-10 rollback protocol available and exercised on fail.
- Predeploy gate proven against production state.
</success_criteria>

<output>
The artifact IS the SUMMARY: `.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md`. Plan 201-12 (24h soak) gates on this file's PASS verdict.
</output>
