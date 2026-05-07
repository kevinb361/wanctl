---
id: 204-01
phase: 204
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/__init__.py
  - pyproject.toml
  - docker/Dockerfile
  - .planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md
autonomous: false
production_canary: true
created: 2026-05-06
requirements:
  - CALIB-01
  - SAFE-07
notes:
  - "Open Q3 (Deploy 1 version bump): adopting `1.43.0` per researcher recommendation. decision_basis: \"researcher recommendation, no operator confirmation\" (204-RESEARCH.md §`Claude's Discretion` line 52; pattern-mapper verified version literals are not in any SAFE-05 pin dict — 204-PATTERNS.md lines 39-45)."
  - "Open Q5 (Deploy 2 ritual symmetry): NOT applicable here (Plan 204-04 owns Deploy 2). This plan owns the FULL Plan 201-15 T0/T1/T2/T3/T4 sequence; Snapshot A and B are byte-identical because v1.43 ships zero new YAML keys (REQUIREMENTS.md \"Out of Scope\" §3) — captured separately for evidence symmetry per 204-RESEARCH.md §Q7 lines 379-388. decision_basis: \"researcher recommendation, no operator confirmation\"."
must_haves:
  truths:
    - "Version surfaces report 1.43.0: src/wanctl/__init__.py:3, pyproject.toml:3, docker/Dockerfile:13."
    - "scripts/check-safe07-source-diff.sh exit 0 against ref b72b463 BEFORE Snapshot A capture."
    - "Snapshot A captured: /opt/wanctl-prephase204-deploy1-<TS>-snapA.tar.gz AND /etc/wanctl/spectrum.yaml.prephase204-deploy1-<TS>-snapA exist on cake-shaper."
    - "Snapshot B captured: /opt/wanctl-prephase204-deploy1-<TS>-snapB.tar.gz AND /etc/wanctl/spectrum.yaml.prephase204-deploy1-<TS>-snapB exist on cake-shaper (byte-identical to A — v1.43 ships no YAML keys)."
    - "v1.43 binary deployed to /opt/wanctl on cake-shaper; wanctl@spectrum.service restarted; /health.version reports 1.43.0."
    - "Post-deploy /health smoke passes: METRIC-01 fields (suppressions_completed_window_count, suppressions_completed_window_by_cause, suppressions_lifetime_by_cause) AND OBSV-05 source fields (load_rtt_ms, baseline_rtt_ms) all present at /health.wans[].upload.hysteresis.* and /health.wans[].* respectively."
    - "204-01-DEPLOY-VERIFICATION.md exists with verdict: pass and references the snapshot file paths and post-deploy /health excerpt."
    - "git diff b72b463..HEAD -- src/wanctl/ produces 0 lines (SAFE-07: version bump touches src/wanctl/__init__.py:3 — verified NOT in any SAFE-05 pin dict per 204-PATTERNS.md lines 39-45)."
  artifacts:
    - path: src/wanctl/__init__.py
      provides: "Version constant bumped from 1.42.1 to 1.43.0 for Deploy 1."
      contains: "__version__ = \"1.43.0\""
    - path: pyproject.toml
      provides: "Project version bumped to 1.43.0."
      contains: "version = \"1.43.0\""
    - path: docker/Dockerfile
      provides: "Container LABEL version bumped to 1.43.0."
      contains: "LABEL version=\"1.43.0\""
    - path: .planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md
      provides: "Operator-readable verdict capturing two-snapshot evidence, predeploy gate exit code, post-deploy /health smoke, and rollback commands."
      contains: "verdict: pass"
  key_links:
    - from: "scripts/check-safe07-source-diff.sh"
      to: "src/wanctl/ vs b72b463"
      via: "exit 0 confirms zero control-path diff before Snapshot A"
      pattern: "check-safe07-source-diff.sh"
    - from: "scripts/deploy.sh"
      to: "/opt/wanctl on cake-shaper"
      via: "rsync deploy after Snapshot B captured"
      pattern: "deploy.sh spectrum cake-shaper"
    - from: "/health.version"
      to: "1.43.0"
      via: "post-restart curl verifies binary running with bumped version"
      pattern: "version.*1\\.43\\.0"
---

<objective>
Bump version surfaces to 1.43.0 and execute Deploy 1 of Phase 204: install the v1.43 binary on cake-shaper so METRIC-01 (Phase 202) and OBSV-05 (Phase 203) `/health` fields are live in production. Use the verbatim Plan 201-15 two-snapshot rollback pattern (T0/T1/T2/T3/T4) — Snapshot A is the rollback target, Snapshot B is deploy evidence only. Snapshots A and B are byte-identical here because v1.43 ships no new YAML keys (REQUIREMENTS.md "Out of Scope" §3); they are captured separately for evidence symmetry.

Purpose: CALIB-01 (Plan 204-02) cannot run until the v1.43 binary is producing `suppressions_completed_window_count` + `load_rtt_delta_us` rows in production `/health`. Deploy 1 is the gate.

Output: v1.43.0 binary running on cake-shaper, two snapshot files for rollback safety, `204-01-DEPLOY-VERIFICATION.md` verdict file. Zero `src/wanctl/` source diff vs Phase 202 close (`b72b463`) — verified via `scripts/check-safe07-source-diff.sh`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@CLAUDE.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-RESEARCH.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-PATTERNS.md
@.planning/phases/204-d-14-successor-recalibration-calib/204-VALIDATION.md
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md
@scripts/check-safe07-source-diff.sh
@scripts/deploy.sh
@scripts/soak-capture.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bump version surfaces to 1.43.0</name>
  <read_first>
    - src/wanctl/__init__.py:1-5 (current `__version__ = "1.42.1"` at line 3)
    - pyproject.toml:1-10 (current `version = "1.42.1"` at line 3)
    - docker/Dockerfile:10-20 (current `LABEL version="1.42.1"` at line 13)
    - 204-PATTERNS.md lines 39-45 (verified: none of these literals appear in SAFE-05 pin dicts at tests/test_phase_195_replay.py:642-714)
  </read_first>
  <files>src/wanctl/__init__.py, pyproject.toml, docker/Dockerfile</files>
  <action>
    Edit three files using the Edit tool — exact string substitutions, no other changes:
      1. src/wanctl/__init__.py:3 — replace `__version__ = "1.42.1"` with `__version__ = "1.43.0"`.
      2. pyproject.toml:3 — replace `version = "1.42.1"` with `version = "1.43.0"`.
      3. docker/Dockerfile:13 — replace `LABEL version="1.42.1"` with `LABEL version="1.43.0"`.
    Per 204-RESEARCH.md §`Claude's Discretion` line 52, the recommended Deploy 1 version is `1.43.0` (not `1.42.2` or `1.43-dev`) — mirrors the Plan 201-15 "version distinguishability" lesson. decision_basis: researcher recommendation, no operator confirmation.

    DO NOT touch any other file in src/wanctl/. Per 204-PATTERNS.md lines 39-45, the version literal is not in any SAFE-05 pin dict (verified — `__version__` is not pinned).
  </action>
  <verify>
    <automated>grep -q '^__version__ = "1.43.0"$' src/wanctl/__init__.py &amp;&amp; grep -q '^version = "1.43.0"$' pyproject.toml &amp;&amp; grep -q '^LABEL version="1.43.0"$' docker/Dockerfile &amp;&amp; bash scripts/check-safe07-source-diff.sh</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q '^__version__ = "1.43.0"$' src/wanctl/__init__.py` exits 0
    - `grep -q '^version = "1.43.0"$' pyproject.toml` exits 0
    - `grep -q '^LABEL version="1.43.0"$' docker/Dockerfile` exits 0
    - `bash scripts/check-safe07-source-diff.sh` exits 0 ("SAFE-07 OK: no src/wanctl/ diff vs b72b463")
    - `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` exits 0 (1 passed)
    - Hot-path slice `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` exits 0
  </acceptance_criteria>
  <done>Version surfaces report 1.43.0; SAFE-07 source-diff check still clean; SAFE-05 pin block still byte-identical; hot-path tests green.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Operator pre-deploy approval gate</name>
  <read_first>
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md (Plan 201-15 approval-task pattern)
    - 204-PATTERNS.md "Operator-blocking checkpoint task pattern" lines 765-789
  </read_first>
  <files>(operator interaction; no file writes from Claude)</files>
  <what-built>
    Version surfaces bumped to 1.43.0; SAFE-07 source-diff clean against `b72b463`; SAFE-05 pin block byte-identical; hot-path tests green. Ready to begin two-snapshot rollback ritual on cake-shaper.
  </what-built>
  <how-to-verify>
    1. Confirm `git status` is clean except for the three version-bump files plus this PLAN; commit and push if not already.
    2. Confirm cake-shaper is reachable: `ssh cake-shaper 'systemctl is-active wanctl@spectrum.service'` returns `active`.
    3. Confirm pre-deploy `/health.version` is `1.42.1`: `ssh cake-shaper 'curl -s http://127.0.0.1:9101/health' | jq -r '.version'` returns `1.42.1`.
    4. Confirm baseline floor-hit counter and a snapshot of `/health.wans[0].upload.hysteresis.*` for post-deploy comparison.
    5. Operator decides: approve (proceed to T0/Snapshot A) or reject (record reason; abort plan).
  </how-to-verify>
  <resume-signal>Type "approved: deploy v1.43.0 to cake-shaper" or "rejected: &lt;reason&gt;".</resume-signal>
  <acceptance_criteria>
    - Operator typed "approved"
    - Pre-deploy /health.version recorded as 1.42.1 in operator's notes (will be cited in 204-01-DEPLOY-VERIFICATION.md)
  </acceptance_criteria>
  <done>Operator approves; T0 may proceed.</done>
</task>

<task type="auto">
  <name>Task 3: Execute T0/T1/T2/T3/T4 two-snapshot deploy</name>
  <read_first>
    - 204-PATTERNS.md lines 522-550 (verbatim T0..T4 sequence + ON FAIL block lifted from Plan 201-15)
    - 204-RESEARCH.md §Q7 lines 376-388 (Phase 204 application: byte-identical A and B because v1.43 ships no new YAML keys)
    - scripts/deploy.sh (existing deploy mechanic)
    - scripts/check-safe07-source-diff.sh (predeploy gate)
  </read_first>
  <files>(remote /opt/wanctl on cake-shaper; remote /etc/wanctl/spectrum.yaml on cake-shaper; no local files written by this task)</files>
  <action>
    Execute the strict T0..T4 sequence on cake-shaper (commands below are verbatim per 204-PATTERNS.md lines 522-550 with Phase 204 substitutions). Capture `TS=$(date -u +%Y%m%dT%H%M%SZ)` once at the start; reuse for all snapshot file names.

    ```bash
    TS=$(date -u +%Y%m%dT%H%M%SZ)
    echo "Phase 204 Deploy 1 timestamp: $TS"

    # T0: Snapshot A (legacy v1.42.1 state — rollback-clean)
    ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase204-deploy1-${TS}-snapA.tar.gz -C / opt/wanctl"
    ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapA"
    ssh cake-shaper "ls -la /opt/wanctl-prephase204-deploy1-${TS}-snapA.tar.gz /etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapA"

    # T1: Predeploy gate (run locally; the candidate v1.43 source tree is HEAD)
    bash scripts/check-safe07-source-diff.sh    # MUST exit 0
    echo "SAFE-07 predeploy gate exit=$?"

    # T2: No reconcile needed — v1.43 ships zero new YAML keys (REQUIREMENTS.md "Out of Scope" §3)
    echo "T2 SKIPPED: no v1.43 YAML keys to reconcile"

    # T3: Snapshot B (post-gate-PASS candidate; byte-identical to A in this case, captured for evidence symmetry per 204-RESEARCH.md §Q7)
    ssh cake-shaper "sudo tar -czf /opt/wanctl-prephase204-deploy1-${TS}-snapB.tar.gz -C / opt/wanctl"
    ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapB"

    # T4: Deploy v1.43.0 binary
    REMOTE_SSH_TARGET=cake-shaper REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml ./scripts/deploy.sh spectrum cake-shaper
    ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
    sleep 5
    ssh cake-shaper "systemctl is-active wanctl@spectrum.service"   # MUST report 'active'
    ```

    Save the literal `TS` value into operator notes for use in Task 4 (it goes into 204-01-DEPLOY-VERIFICATION.md).

    ON ANY FAIL between T0 and T4 (predeploy gate exit non-zero, deploy.sh non-zero, or systemctl not active): rollback per 204-PATTERNS.md lines 546-550:
    ```bash
    ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase204-deploy1-${TS}-snapA.tar.gz -C /"
    ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapA /etc/wanctl/spectrum.yaml"
    ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
    ssh cake-shaper "curl -s http://127.0.0.1:9101/health | jq -r '.version'"   # MUST report 1.42.1
    ```
    Then escalate: write 204-01-DEPLOY-VERIFICATION.md with `verdict: fail` and the rollback evidence; abort plan.
  </action>
  <verify>
    <automated>ssh cake-shaper 'ls /opt/wanctl-prephase204-deploy1-*-snapA.tar.gz /opt/wanctl-prephase204-deploy1-*-snapB.tar.gz /etc/wanctl/spectrum.yaml.prephase204-deploy1-*-snapA /etc/wanctl/spectrum.yaml.prephase204-deploy1-*-snapB' &amp;&amp; ssh cake-shaper "systemctl is-active wanctl@spectrum.service" &amp;&amp; ssh cake-shaper "curl -s http://127.0.0.1:9101/health | jq -re '.version == \"1.43.0\"'"</automated>
  </verify>
  <acceptance_criteria>
    - Snapshot A files exist on cake-shaper at `/opt/wanctl-prephase204-deploy1-${TS}-snapA.tar.gz` and `/etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapA`
    - Snapshot B files exist at the corresponding `-snapB` paths
    - `bash scripts/check-safe07-source-diff.sh` exited 0 between T0 and T3
    - `systemctl is-active wanctl@spectrum.service` on cake-shaper returns `active`
    - `curl -s http://127.0.0.1:9101/health | jq -r '.version'` on cake-shaper returns `1.43.0`
  </acceptance_criteria>
  <done>v1.43.0 running on cake-shaper; two snapshot pairs captured; rollback-clean state preserved.</done>
</task>

<task type="auto">
  <name>Task 4: Post-deploy /health smoke + write 204-01-DEPLOY-VERIFICATION.md</name>
  <read_first>
    - 204-PATTERNS.md lines 562-575 (active-knob assertion jq pattern with the five Phase 204 field paths)
    - 204-PATTERNS.md "204-01-DEPLOY-VERIFICATION.md (deploy verdict, Plan 204-01)" section lines 516-575
    - scripts/soak-capture.sh:35-57 (confirms which fields are captured per row; same fields the smoke must find in /health)
    - .planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-CANARY-VERDICT.md (verdict file structural analog)
  </read_first>
  <files>.planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md</files>
  <action>
    Run the post-deploy `/health` smoke check. The five field paths are verbatim from 204-PATTERNS.md lines 562-575:

    ```bash
    ssh cake-shaper 'curl -s http://127.0.0.1:9101/health' | jq -e '
      .version == "1.43.0"
      and (.wans[0].upload.hysteresis.suppressions_completed_window_count != null)
      and (.wans[0].upload.hysteresis.suppressions_completed_window_by_cause != null)
      and (.wans[0].upload.hysteresis.suppressions_lifetime_by_cause != null)
      and (.wans[0].load_rtt_ms != null)
      and (.wans[0].baseline_rtt_ms != null)
    '
    ```
    Save the full `/health` JSON output for inclusion in the verdict file:
    ```bash
    ssh cake-shaper 'curl -s http://127.0.0.1:9101/health' > /tmp/204-01-postdeploy-health.json
    ```

    Then write `.planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md` using this template (substitute `${TS}` with the literal value from Task 3, paste full /health excerpt where indicated):

    ```markdown
    # Phase 204 — Plan 204-01 Deploy Verification (METRIC-01 + OBSV-05 binary on cake-shaper)

    timestamp: <UTC ISO from `date -u -Iseconds`>
    deploy_ts: ${TS}
    verdict: pass
    operator_approval: "Task 2 approved"

    ---

    ## Deploy Summary

    Deployed v1.43.0 binary to cake-shaper:/opt/wanctl. METRIC-01 (Phase 202) and OBSV-05 (Phase 203) `/health` fields now live in production. Two-snapshot rollback per Plan 201-15 pattern (Snapshot A == Snapshot B byte-identical because v1.43 ships zero new YAML keys, captured separately for evidence symmetry per 204-RESEARCH.md §Q7).

    ## Two-Snapshot Evidence

    - Snapshot A (rollback-clean, pre-deploy v1.42.1):
      - `/opt/wanctl-prephase204-deploy1-${TS}-snapA.tar.gz`
      - `/etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapA`
    - Snapshot B (post-gate candidate, byte-identical to A):
      - `/opt/wanctl-prephase204-deploy1-${TS}-snapB.tar.gz`
      - `/etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapB`

    ## Predeploy Gate

    `bash scripts/check-safe07-source-diff.sh` exit code: 0
    Default ref: `b72b463` (Phase 202 close)

    ## Post-Deploy /health Smoke

    The five Phase 204 field paths verified present:
    - `.version == "1.43.0"` ✓
    - `.wans[0].upload.hysteresis.suppressions_completed_window_count` (METRIC-01) ✓
    - `.wans[0].upload.hysteresis.suppressions_completed_window_by_cause` (METRIC-02) ✓
    - `.wans[0].upload.hysteresis.suppressions_lifetime_by_cause` (METRIC-02 lifetime) ✓
    - `.wans[0].load_rtt_ms` (OBSV-05 source) ✓
    - `.wans[0].baseline_rtt_ms` (OBSV-05 source) ✓

    Full /health JSON: see `204-01-postdeploy-health.json` (committed alongside this verdict file).

    ## Rollback Commands (kept for operator reference)

    ```bash
    ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase204-deploy1-${TS}-snapA.tar.gz -C /"
    ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml.prephase204-deploy1-${TS}-snapA /etc/wanctl/spectrum.yaml"
    ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
    ssh cake-shaper "curl -s http://127.0.0.1:9101/health | jq -r '.version'"   # MUST report 1.42.1
    ```

    ## References

    - Plan 201-15 two-snapshot precedent: `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md`
    - Phase 204 RESEARCH §Q7: `.planning/phases/204-d-14-successor-recalibration-calib/204-RESEARCH.md`
    - Phase 204 PATTERNS deploy-verdict template: `.planning/phases/204-d-14-successor-recalibration-calib/204-PATTERNS.md` (lines 516-575)
    ```

    Also copy `/tmp/204-01-postdeploy-health.json` to `.planning/phases/204-d-14-successor-recalibration-calib/204-01-postdeploy-health.json` so the verdict has the supporting evidence committed alongside.
  </action>
  <verify>
    <automated>test -f .planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md &amp;&amp; grep -q "^verdict: pass$" .planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md &amp;&amp; grep -q "1.43.0" .planning/phases/204-d-14-successor-recalibration-calib/204-01-DEPLOY-VERIFICATION.md &amp;&amp; test -f .planning/phases/204-d-14-successor-recalibration-calib/204-01-postdeploy-health.json &amp;&amp; jq -e '.version == "1.43.0" and .wans[0].upload.hysteresis.suppressions_completed_window_count != null and .wans[0].load_rtt_ms != null' .planning/phases/204-d-14-successor-recalibration-calib/204-01-postdeploy-health.json</automated>
  </verify>
  <acceptance_criteria>
    - 204-01-DEPLOY-VERIFICATION.md exists, contains `verdict: pass`, references both Snapshot A and B file paths
    - 204-01-postdeploy-health.json exists in the phase directory and parses as JSON with `.version == "1.43.0"`
    - All five field-presence checks documented as `✓` in the verdict file
    - Hot-path slice still green: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` exits 0
  </acceptance_criteria>
  <done>Deploy 1 verified; production cake-shaper running 1.43.0 with METRIC-01 + OBSV-05 fields live; verdict committed.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local dev → cake-shaper SSH | Operator-initiated rsync deploy + systemctl restart; SSH is the only network egress involved. |
| cake-shaper → MikroTik router | Existing wanctl→router path; not modified by this plan. |
| `/health` HTTP endpoint | Bound to 127.0.0.1:9101 on cake-shaper; SSH-tunnel only access from operator workstation. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-204-01-01 | Tampering | `scripts/deploy.sh` rsync target | mitigate | Snapshot A captured BEFORE rsync; rollback restores byte-identical legacy binary on failure. SAFE-07 source-diff gate (exit 0) confirms no unauthorized control-path change in the deploy candidate. |
| T-204-01-02 | Denial of Service | `wanctl@spectrum.service` restart | accept | Standard production-restart risk; mitigated by Snapshot A rollback path; soak-monitor will detect post-restart anomalies. Mirror of Plan 201-15 risk acceptance. |
| T-204-01-03 | Information Disclosure | Snapshot files contain /etc/wanctl/spectrum.yaml | accept | Snapshots stored on cake-shaper (same trust zone as production state); access requires sudo. No new exposure vs current operational practice. |
| T-204-01-04 | Repudiation | Operator-approval Task 2 | mitigate | Operator approval recorded in `204-01-DEPLOY-VERIFICATION.md` with timestamp; not silently written into a verdict file (Codex 201-REVIEWS LOW-CODEX-5 lesson). |
</threat_model>

<verification>
- `bash scripts/check-safe07-source-diff.sh` exit 0 (SAFE-07)
- `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` 1 passed
- Hot-path slice green
- `/health.version == "1.43.0"` on cake-shaper
- All five Phase 204 field paths present in /health
- 204-01-DEPLOY-VERIFICATION.md committed with verdict: pass
</verification>

<success_criteria>
v1.43.0 binary running in production on cake-shaper. METRIC-01 + OBSV-05 fields live. Two snapshots captured for rollback. Zero `src/wanctl/` source diff vs Phase 201 close (`b72b463`). SAFE-05 pin block byte-identical. Verdict file committed. CALIB-01 (Plan 204-02) is unblocked.
</success_criteria>

<output>
After completion, create `.planning/phases/204-d-14-successor-recalibration-calib/204-01-SUMMARY.md` recording:
- Deploy timestamp `${TS}`
- Both snapshot file paths (A and B)
- Predeploy gate exit code (must be 0)
- Post-deploy `/health.version` (must be `1.43.0`)
- Hand-off pointer to Plan 204-02 (CALIB-01 baseline soak)
</output>
