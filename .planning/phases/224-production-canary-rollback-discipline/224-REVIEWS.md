---
phase: 224
reviewers: [codex]
reviewed_at: 2026-06-02T20:40:24-05:00
plans_reviewed:
  - 224-01-PLAN.md
  - 224-02-PLAN.md
  - 224-03-PLAN.md
  - 224-04-PLAN.md
  - 224-05-PLAN.md
cycle: 2
prior_cycles:
  - cycle: 1
    high_count: 6
    replan_commit: 3619cf4
---

# Cross-AI Plan Review — Phase 224 (Cycle 2)

## Cycle Context

Cycle 1 raised six HIGH defects plus five MEDIUMs. Replan commit `3619cf4` absorbed all of them — service name corrected to `steering.service`, spine probe now consumes raw `/health` via `curl 127.0.0.1:9102/health`, health fields rewritten against `src/wanctl/steering/health.py`, 4-cycle/200ms staleness replaced with `gate_rtt_source_fresh` (5s) using `rtt_source.last_measurement_age_sec`, Plan 01 new `--raw-dir` flag writes 0600 artifacts outside git, Plan 03 deploy flipped to `checkpoint:human-action`, Plan 05 SAFE-12 allowlist matches Phase 223 verbatim (`fusion_healer.py` single file, baseline `bee343b0c2f...`), Plan 04 `kept_aligned` now requires ≥15 samples AND ≥900s AND `window_end_reached`, Plan 04 rollback uses `--raw-dir` and restarts `steering.service`, invariant 3 renamed to `spectrum_state_not_written_by_daemon`.

This cycle re-verifies the six HIGH closures and looks for new HIGH defects introduced by the changes.

## Codex Review

**Summary**

Cycle 2 fixes most Cycle 1 interface defects, but I would still block execution. Two HIGH issues remain: the `--raw-dir` rollback path does not restore the actual steering state end-to-end, and Plan 02's `spectrum_state_not_written_by_daemon` production proxy expects `/var/lib/wanctl/spectrum_state.json` to be absent even though live config says that file is the autorate baseline input.

**Strengths**

- Service name is fixed in executable plans: Plan 01/03/04 use `steering.service`, matching `deploy/systemd/steering.service:14`, `scripts/install-systemd.sh:85`, and `scripts/deploy.sh:497`.
- Raw `/health` vs `canary-check --json` is now separated. Plan 02 requires raw health and rejects summary arrays; `canary-check` really emits `{target,service,result,detail}` arrays at `scripts/canary-check.sh:159` and `:483`.
- Health field names are corrected: Plan 02 uses `decision.last_transition_time`, `decision.time_in_state_seconds`, and top-level `rtt_source.*`; live health emits those at `src/wanctl/steering/health.py:196,280,365`.
- Plan 03 deploy/restart and Plan 04 conditional rollback are human-gated, not automated: `224-03-PLAN.md:176`, `224-04-PLAN.md:215`.
- SAFE-12 now uses the Phase 223 anchor/list, including `fusion_healer.py` (not `fusion/`): `224-05-PLAN.md:94`, `223 evidence/safe12-boundary-check.json:2`.

**Concerns By Severity**

**HIGH**

- **Plan 01 / rollback path: `--raw-dir` is not end-to-end restorable for state.** Plan 01 captures raw steering state to `<raw-dir>/deployed-steering-state.json` but the manifest restore step writes it to `/var/lib/wanctl/state.json` (`224-01-PLAN.md:98,104`). Actual steering state path is `/var/lib/wanctl/steering_state.json` per `configs/steering.yaml:93`, `src/wanctl/steering/daemon.py:689`, and `scripts/phase213-steering-snapshot.sh:77`. Plan 01 Task 2's rollback steps restore config only before restart/proof (`224-01-PLAN.md:147`). Net effect: rollback restores config but not steering state, leaving daemon to recreate state from stale config — CANARY-03 not actually achievable as designed.

- **Plan 02 / spine probe: `spectrum_state_not_written_by_daemon` is incorrectly modeled as "file absent."** Plan 02 says steady-state expected value is `absent` for `/var/lib/wanctl/spectrum_state.json` (`224-02-PLAN.md:95`). Live steering config reads baseline RTT from that file (`configs/steering.yaml:26`). Phase 223's invariant was no daemon-side write, detected by fingerprint around `run_cycle()`, not file absence (`223 evidence/spine-evidence.md:5`). This would likely false-fail predeploy or rollback in normal production where the file exists by design.

**MEDIUM**

- **Plan 02 / only-new selector**: expected selector source is mis-cited. Plan 02 says the selector is recorded in Phase 222/223 evidence (`224-02-PLAN.md:94`), but Phase 223 says actual RouterOS mangle-rule config was outside the harness (`223 evidence/spine-evidence.md:81`). The concrete repo rule shape is in `scripts/add_steering_rules.sh:53`.

- **Plan 05 / SAFE-12 schema**: path list and baseline are correct, but "Phase 223 schema verbatim" is not quite true. Phase 223 uses `audit_timestamp_utc`, `per_path_diff`, and `dirty_tree` (`223 evidence/safe12-boundary-check.json:5`), while Plan 05 templates `checked_at`, `controller_path_paths`, and `per_file_sha256_equal` (`224-05-PLAN.md:112`). Probably okay, but not exact reuse — call it "Phase 223-aligned" rather than "verbatim."

**LOW**

- **224-CONTEXT / 224-RESEARCH** still contain stale `wanctl-steering.service` and `canary-check --json` guidance, and the plans include those files as context (`224-CONTEXT.md:19`, `224-RESEARCH.md:61,80`). Executable plan text overrides this, but it is drift bait for future readers.

**Suggestions**

- Fix Plan 01/04 rollback to parse `state.file` from deployed `steering.yaml`, capture that exact raw file, restore to that exact path, verify SHA, and include the state restore in `phase224-rollback.sh`.
- Replace Plan 02's `spectrum_state.json` absence check. Use "configured autorate state file exists and RTT source is fresh" for live canary, and keep "daemon does not write spectrum_state" as Phase 223 code/replay evidence unless you add an explicit production attribution mechanism (e.g., mtime delta probe with daemon UID attribution).
- Anchor the only-new selector to `scripts/add_steering_rules.sh` or an exported live RouterOS rule artifact, not Phase 223 spine evidence.
- Clean stale service/health-parser text in `224-CONTEXT.md` and `224-RESEARCH.md` before execution.

**Risk Assessment**

HIGH overall until the rollback state restore and `spectrum_state.json` proxy are fixed. After those, residual risk drops to MEDIUM because this is still a production steering canary.

**CYCLE 2 Verdict**

1. **Six HIGH defects resolved**: PARTIAL. Five are materially fixed; raw rollback is only partially fixed because state restore path is wrong/omitted.
2. **No new HIGH defects**: NEW_DEFECT. The `spectrum_state.json` absence proxy is a new blocker introduced by the invariant-3 rename.
3. **`--raw-dir` strategy executable end-to-end**: PARTIAL. Raw config restore works in plan; raw state restore does not (wrong filename and missing from rollback script).
4. **Health field names correct**: RESOLVED. Plan 02 matches live `health.py` fields.
5. **`steering.service` unit references match**: RESOLVED. Executable plans align with deployed unit.
6. **SAFE-12 allowlist and baseline match Phase 223**: RESOLVED. Uses `bee343b0...`, `v1.47`, and `fusion_healer.py`.
7. **`gate_rtt_source_fresh` implementable**: RESOLVED. `rtt_source.last_measurement_age_sec` exists in live payload; it is a freshness proxy, not 50ms cycle staleness — but the plan now correctly scopes it as freshness.

---

## Consensus Summary (Cycle 2)

Single reviewer this cycle (Codex). Anchor for Cycle 3 if needed.

### Resolved from Cycle 1 (5 of 6 HIGHs)

1. **Systemd unit name** → `steering.service` consistent across Plans 01/03/04. RESOLVED.
2. **JSON schema for gate-eval** → raw `/health` via curl + `canary-check --json` summary cleanly separated. RESOLVED.
3. **Health field names** → match `src/wanctl/steering/health.py` (`decision.last_transition_time`, `decision.time_in_state_seconds`, top-level `rtt_source.*`). RESOLVED.
4. **Plan 03 deploy `auto` → `checkpoint:human-action`** → flipped, operator-gated. RESOLVED.
5. **SAFE-12 path list** → matches Phase 223 anchor (`fusion_healer.py`, `bee343b0...`, v1.47). RESOLVED.

### Cycle 1 HIGH still open

6. **Plan 01 rollback restores redacted artifacts** → `--raw-dir` mitigation introduced but rollback's state restore writes to wrong path (`/var/lib/wanctl/state.json` vs actual `/var/lib/wanctl/steering_state.json`) and is omitted from the rollback script. **PARTIAL — still HIGH.**

### New HIGH introduced in Cycle 2

7. **Plan 02 `spectrum_state_not_written_by_daemon` proxy** → models invariant 3 as "file absent" but live config reads autorate baseline RTT from that file. Plan would false-fail predeploy or rollback gates in normal production. Phase 223 used a code-fingerprint around `run_cycle()`, not file absence. **NEW HIGH.**

### Agreed Concerns (HIGH — must address before Plan 03 runs)

1. Plan 01 rollback state-restore path is wrong (`state.json` vs `steering_state.json`) and absent from `phase224-rollback.sh`.
2. Plan 02 spine probe `spectrum_state_not_written_by_daemon` cannot use file-absence as its production proxy.

### Cycle 2 Action Items (for re-planning, if Cycle 3 attempted)

- Plan 01: read `state.file` from deployed `steering.yaml`, capture/restore the exact path; add state restore step to `phase224-rollback.sh`; SHA-verify on restore.
- Plan 02: replace invariant-3 production proxy. Options: (a) mtime delta + daemon UID attribution probe, (b) "configured state file exists and `rtt_source` is fresh" as live canary, leave code-fingerprint evidence to Phase 223.
- Plan 02 only-new selector: cite `scripts/add_steering_rules.sh:53` (or exported live RouterOS rule) as expected selector source, not Phase 223 spine evidence.
- Plan 05: rename "Phase 223 schema verbatim" to "Phase 223-aligned" or align fields exactly (`audit_timestamp_utc`, `per_path_diff`, `dirty_tree`).
- 224-CONTEXT.md / 224-RESEARCH.md: scrub stale `wanctl-steering.service` and `canary-check --json` text so future readers don't inherit Cycle 1 drift.

### Divergent Views

N/A — single reviewer this cycle.

### Net Convergence Status

- Cycle 1 HIGH count: 6
- Cycle 1 HIGHs closed: 5
- Cycle 1 HIGHs partially closed: 1 (rollback state restore)
- New HIGHs introduced: 1 (`spectrum_state.json` absence proxy)
- **Current HIGH count: 2**

Convergence not yet reached. Recommend `/gsd:plan-phase 224 --reviews` cycle 3 to absorb the two remaining HIGHs, or operator override with explicit acknowledgement.
