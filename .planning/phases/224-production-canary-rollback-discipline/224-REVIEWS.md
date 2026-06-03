---
phase: 224
reviewers: [codex]
reviewed_at: 2026-06-02T21:05:01-05:00
plans_reviewed:
  - 224-01-PLAN.md
  - 224-02-PLAN.md
  - 224-03-PLAN.md
  - 224-04-PLAN.md
  - 224-05-PLAN.md
cycle: 3
prior_cycles:
  - cycle: 1
    high_count: 6
    replan_commit: 3619cf4
  - cycle: 2
    high_count: 2
    replan_commit: fb2824d
---

# Cross-AI Plan Review — Phase 224 (Cycle 3 — Final Allowed Cycle)

## Cycle Context

Cycle 2 left 2 HIGH defects. Replan commit `fb2824d` absorbed both:

1. **Plan 01 state-restore path** — snapshot now reads `state.file` from captured `deployed-steering.yaml`, writes a literal `<raw-dir>/deployed-steering-state.source-path.txt` artifact, and rollback gains an explicit Step 4 (state restore) before `systemctl restart`, with regex validation against `^/var/lib/wanctl/[A-Za-z0-9_.-]+\.json$` and SHA-256 verification. Rollback script must NOT contain the string `/var/lib/wanctl/state.json` anywhere.
2. **Plan 02 invariant-3** — chose option (a) code-fingerprint. Probe replaces `file_present`/`mtime_iso`/`mtime_age_seconds` with `method: "code-fingerprint"`, `daemon_source_path`, `deployed_sha256`, `baseline_sha256`. Probe accepts `--baseline-fingerprint <sha256>` (required) + `--daemon-source-path` (default `/opt/wanctl/src/wanctl/steering/daemon.py`). Gate-eval EXEMPTS `gate_spectrum_state_not_written_by_daemon` from restart-window symptom classification. New pytest cases cover match, mismatch-in-restart-window, and legacy-shape fail-fast.

Cross-plan ripple: Plan 03 Task 2 computes baseline via `git show v1.47:src/wanctl/steering/daemon.py | sha256sum`, persists to `evidence/snapshot-a/<TS>/baseline-daemon-source.sha256.txt`, validates 64-char lowercase hex; plumbs `--baseline-fingerprint` through Leg A pre-deploy and Leg B post-deploy. Plan 04 reads `BASELINE_FP` from the snapshot directory and plumbs it through the per-sample loop and post-revert spine probe. Plan 05 evidence index includes the baseline file and CANARY-02 closeout cites `method: "code-fingerprint"` and the sha pair.

This is **Cycle 3 — the final allowed cycle before max-cycles escalation**.

## Codex Review

**Summary**

Cycle 3 is improved but not converged. The rollback state restore defect is materially fixed in the plans, and the `spectrum_state.json` file-absence proxy was correctly replaced with a code-fingerprint concept. However, the new fingerprint probe points at the wrong deployed path: the plans default to `/opt/wanctl/src/wanctl/steering/daemon.py`, while the repo's deploy path syncs `src/wanctl/` directly into `/opt/wanctl/`, making the expected deployed daemon path `/opt/wanctl/steering/daemon.py`. I would block execution and escalate the final-cycle result with HIGH defects still open.

**Strengths**

- Plan 01 now reads `state.file` from captured deployed `steering.yaml`, writes `deployed-steering-state.source-path.txt`, restores state before restart, validates the `/var/lib/wanctl/*.json` path, and bans `/var/lib/wanctl/state.json`.
- `state.file` is correctly anchored: `configs/steering.yaml:95` sets `/var/lib/wanctl/steering_state.json`, and `src/wanctl/steering/daemon.py:691` loads `self.data["state"]["file"]`.
- The file-absence proxy is gone from executable plan semantics. Plan 02 now requires `method: "code-fingerprint"` and rejects legacy `file_present` shape with a structured fail-fast.
- `v1.47` exists and peels to `bee343b0c2f16207101aec82007a5e55fa9b6407`; `git show v1.47:src/wanctl/steering/daemon.py | sha256sum` resolves locally and returns `c7280976f03916aacb2f27c4c91a2288cab14e7b9a8c229f3146deef2826d00d`.
- Prior Cycle 1 fixes remain mostly intact: `steering.service`, raw `/health`, real health field names, human deploy checkpoint, and SAFE-12 anchor/list.

**Concerns by Severity**

**HIGH**

- **Code-fingerprint remote path is wrong for this deployment layout.** Plan 02 defaults `--daemon-source-path` to `/opt/wanctl/src/wanctl/steering/daemon.py` at `224-02-PLAN.md:91` and fingerprints that path at `224-02-PLAN.md:96`. But `deploy.sh` sets `TARGET_CODE_DIR=/opt/wanctl` (`scripts/deploy.sh:28`) and rsyncs `src/wanctl/` into that directory (`scripts/deploy.sh:190`). The steering unit runs with `PYTHONPATH=/opt` and `python3 -m wanctl.steering.daemon` from `WorkingDirectory=/opt/wanctl` (`deploy/systemd/steering.service:13-14,18`). The actual deployed daemon path is `/opt/wanctl/steering/daemon.py` — independently verified on the live target `cake-shaper`: `/opt/wanctl/steering/daemon.py` exists (and its sha256 already matches the v1.47 baseline `c7280976...`); `/opt/wanctl/src/wanctl/steering/daemon.py` does NOT exist. Every spine probe in Plans 02/03/04 would fail at first invocation with a missing-file error, breaking Leg A predeploy gate, Leg B postdeploy gate, and every per-sample observation gate.

- **Baseline-fingerprint plumbing uses unset/inconsistent paths after deploy.** Plan 03 Task 2 sets `SNAPSHOT_DIR=.planning/phases/224-production-canary-rollback-discipline/evidence/snapshot-a/${TS}` (`224-03-PLAN.md:126`) but Task 3 only sets `SNAP_TS` (`224-03-PLAN.md:190`) without re-defining `SNAPSHOT_DIR`, then references `${SNAPSHOT_DIR}/baseline-daemon-source.sha256.txt` for the postdeploy spine probe at `224-03-PLAN.md:203`. Task 3 also calls rollback with `--snapshot evidence/snapshot-a/${SNAP_TS}` (relative path, `224-03-PLAN.md:199`), inconsistent with Task 2's full repo-relative path. Plan 04 repeats the same relative `evidence/snapshot-a/${SNAP_TS}` pattern at `224-04-PLAN.md:97`, `:106`, `:227`, `:233`, `:238`. If Task 3 runs in a fresh shell or Task 2's variables aren't re-sourced, `${SNAPSHOT_DIR}` is empty and the postdeploy spine probe reads `--baseline-fingerprint "$(cat /baseline-daemon-source.sha256.txt)"` — a no-such-file error. Even if it works under "run all tasks in one shell" semantics, the inconsistency between full and relative paths is fragile and would silently misdirect a rollback or observation run executed from a different cwd.

**MEDIUM**

- **Predeploy spine gate still permits read-error/null matches.** Plan 03 Task 2 acceptance check at `224-03-PLAN.md:171` allows `match == true OR null (read-error)`, but the prose action at `224-03-PLAN.md:132` says "verify all three spine matches == true." For a production canary predeploy gate, `null` (probe read-error) should block, not pass-through under "not false."

- **Only-new selector source remains weakly cited.** Plan 02 says the expected selector is recorded in Phase 222/223 evidence at `224-02-PLAN.md:95`, but Phase 223 spine evidence explicitly notes RouterOS mangle-rule configuration was outside the harness. The concrete repo rule (`connection-state=new`) lives in `scripts/add_steering_rules.sh:59`. This was raised as MEDIUM in cycle 2 and is unchanged in cycle 3.

**LOW**

- Plan 05 still calls its SAFE-12 output "Phase 223 schema verbatim," but the templated JSON shape (`checked_at`, `controller_path_paths`, `per_file_sha256_equal`) is only Phase-223-aligned, not identical to `audit_timestamp_utc`, `per_path_diff`, `dirty_tree`. Cycle 2 carry-forward, unchanged.

- 224-CONTEXT.md and 224-RESEARCH.md still contain stale `wanctl-steering.service` and `canary-check --json` text (`224-RESEARCH.md:15,62,102,137,143,188`, `224-CONTEXT.md:19`). Executable plans correctly use `steering.service`, but the drift bait remains. Cycle 2 carry-forward, unchanged.

**Suggestions**

- Change Plan 02 default `--daemon-source-path` to `/opt/wanctl/steering/daemon.py`. Optionally add a Plan 03 preflight that runs `ssh <host> 'test -f /opt/wanctl/steering/daemon.py && sha256sum /opt/wanctl/steering/daemon.py'` and fails before deploy if the file does not exist. Update all docstrings/plan prose accordingly.
- Define `SNAPSHOT_DIR=.planning/phases/224-production-canary-rollback-discipline/evidence/snapshot-a/${SNAP_TS}` anywhere `SNAP_TS` is set (Plan 03 Task 3, Plan 04 Tasks), and use that absolute repo-relative path consistently for both `--snapshot` and `--baseline-fingerprint "$(cat ${SNAPSHOT_DIR}/baseline-daemon-source.sha256.txt)"` invocations. Alternatively, persist `SNAP_TS` and `SNAPSHOT_DIR` to a runtime env file at the end of Task 2 and source it at the start of Tasks 3, Plan 04, Plan 05.
- Treat any spine `match: null` or `read_error` as a hard predeploy STOP in Plan 03 Task 2 verify block — align the acceptance check with the prose action.
- Anchor only-new selector comparison to `scripts/add_steering_rules.sh:53,59` or a captured/exported live RouterOS rule artifact.
- Clean stale `wanctl-steering.service` / `canary-check --json` text in 224-CONTEXT.md and 224-RESEARCH.md before execution.

**Cycle 3 Verdict** (per-item answers for the 7 verification questions)

1. **Two Cycle 2 HIGHs resolved end-to-end:** PARTIAL. State restore is fully resolved at the plan level (path, regex, SHA-verify, ban-string). Code-fingerprint replaces file absence conceptually, but the wrong deployed path in the executable plan default prevents end-to-end proof.
2. **No new HIGH defects introduced:** NO — two new HIGHs introduced by the Cycle 3 changes (wrong deployed daemon path, snapshot-dir variable scope/path inconsistency).
3. **State.file value matches config/source:** YES — `/var/lib/wanctl/steering_state.json` confirmed at `configs/steering.yaml:95` and loaded by `src/wanctl/steering/daemon.py:691`.
4. **Baseline computation and deployed path:** SPLIT. Baseline command is correct: `v1.47` tag exists, `git show v1.47:src/wanctl/steering/daemon.py | sha256sum` returns `c7280976f03916aacb2f27c4c91a2288cab14e7b9a8c229f3146deef2826d00d`. Deployed path is wrong: `/opt/wanctl/src/wanctl/steering/daemon.py` does not exist on `cake-shaper`; the actual path is `/opt/wanctl/steering/daemon.py`.
5. **SAFE-12 boundary holds:** YES — controller-path `git diff v1.47 HEAD` is empty across `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `alert_engine.py`, `fusion_healer.py`, `backends/`.
6. **Prior resolved Cycle 1 HIGHs regressed:** NO material regression — `steering.service` unit name, raw `/health` schema, health field names, deploy checkpoint type, and SAFE-12 anchor/list (`bee343b0...`, v1.47, `fusion_healer.py`) all match the Cycle 2 resolutions.
7. **Restart-window exemption consistency:** YES — only `gate_binary_on_off` is restart-window eligible (per `224-02-PLAN.md:178`). `gate_spectrum_state_not_written_by_daemon` is explicitly EXEMPTED (`224-02-PLAN.md:175,178,230`); `gate_version_alignment`, `gate_only_new_connections`, `gate_rtt_source_fresh` are not marked exempt nor mis-classified. Pytest cases enforce the distinction (`test_spectrum_state_fingerprint_mismatch_triggers_rollback_even_in_restart_window`, `test_steady_state_binary_violation_triggers_rollback`, `test_rtt_source_stale_triggers_rollback`).

**Risk Assessment**

HIGH until the fingerprint deployed path and snapshot-baseline plumbing are fixed. This final review cycle should escalate as not converged, with the above HIGHs carried into the max-cycles decision.

---

## Consensus Summary (Cycle 3 — Single Reviewer)

Single reviewer this cycle (Codex). This is the anchor for the max-cycles escalation decision.

### Resolved from Cycle 2 (1 of 2 HIGHs)

1. **Plan 01 rollback state-restore path** — fully resolved at the plan level. `state.file` is read from captured deployed YAML, restored to the literal canonical path `/var/lib/wanctl/steering_state.json`, regex-validated, SHA-verified, and the banned-string check covers `/var/lib/wanctl/state.json`. RESOLVED.

### Cycle 2 HIGH partially resolved

2. **Plan 02 `spectrum_state_not_written_by_daemon` proxy** — the file-absence model was correctly replaced with a code-fingerprint concept and the gate-eval distinction is sound, but the deployed path is wrong (see new HIGH #1 below). The semantic fix landed; the executable parameter does not match the deployment layout. PARTIAL.

### New HIGHs introduced in Cycle 3

1. **Wrong deployed daemon path (`224-02-PLAN.md:91,96`).** Plan 02 default `--daemon-source-path /opt/wanctl/src/wanctl/steering/daemon.py` does not exist on the target. Live verification on `cake-shaper`: `/opt/wanctl/steering/daemon.py` exists; `/opt/wanctl/src/wanctl/steering/daemon.py` does not. Every spine probe in Plans 02/03/04 would fail at first invocation. Root cause: `scripts/deploy.sh:28,190` rsyncs `src/wanctl/` into `/opt/wanctl/` directly, so the deployed module tree is rooted at `/opt/wanctl/`, not `/opt/wanctl/src/wanctl/`.

2. **`SNAPSHOT_DIR` variable scope / path inconsistency (`224-03-PLAN.md:126,190,199,203`; `224-04-PLAN.md:97,106,227,233,238`).** Plan 03 Task 2 sets `SNAPSHOT_DIR=...evidence/snapshot-a/${TS}` (full repo-relative path) but Task 3 references `${SNAPSHOT_DIR}` without re-defining it and uses `evidence/snapshot-a/${SNAP_TS}` relative paths elsewhere. Plan 04 uses the same relative-path pattern. If executed across separate shells or from a non-repo-root cwd, `${SNAPSHOT_DIR}` resolves to empty and the postdeploy spine probe / rollback / per-sample gate-eval all break.

### Agreed Concerns (HIGH — must address before Plan 03 runs OR operator overrides)

1. Plan 02 `--daemon-source-path` default must point at the actual deployed path `/opt/wanctl/steering/daemon.py`; cascade through Plan 03 verify, Plan 04 per-sample loop, and any plan prose that names the path.
2. Plan 03 Task 3 and Plan 04 must consistently define `SNAPSHOT_DIR` (full repo-relative) whenever `SNAP_TS` is set, OR persist both to a `.env`-style file at the end of Plan 03 Task 2 and source it at the start of Task 3 / Plan 04.

### Cycle 3 Action Items (for re-planning if operator chooses Cycle 4 OR for max-cycles override decision)

- Plan 02: change default `--daemon-source-path` to `/opt/wanctl/steering/daemon.py`. Update docstrings, action prose, acceptance checks, and risk-table anti-patterns. Add an optional Plan 03 preflight `ssh host test -f <path> && sha256sum <path>` that fails before deploy on missing file.
- Plan 03 Task 3: re-set `SNAPSHOT_DIR=.planning/phases/224-production-canary-rollback-discipline/evidence/snapshot-a/${SNAP_TS}` after computing `SNAP_TS`. Convert `evidence/snapshot-a/${SNAP_TS}` to `${SNAPSHOT_DIR}` throughout. Plan 04: same treatment for Tasks 2–4.
- Plan 03 Task 2 verify block: tighten acceptance to require `match == true` (not `true OR null`). `null` is a probe read-error and MUST stop the canary before deploy.
- Plan 02 only-new selector: cite `scripts/add_steering_rules.sh:53,59` (or exported live RouterOS rule) as the expected selector source. Carry-forward from cycle 2 MEDIUM.
- Plan 05: align the SAFE-12 JSON field names exactly with Phase 223 (`audit_timestamp_utc`, `per_path_diff`, `dirty_tree`) OR change wording from "verbatim" to "aligned." Carry-forward from cycle 2 LOW.
- 224-CONTEXT.md / 224-RESEARCH.md: scrub stale `wanctl-steering.service` and `canary-check --json` text. Carry-forward from cycle 2 LOW.

### Divergent Views

N/A — single reviewer this cycle.

### Net Convergence Status

- Cycle 1 HIGH count: 6
- Cycle 2 HIGH count: 2 (after replan 3619cf4)
- Cycle 3 HIGH count: **2** (after replan fb2824d — 1 of 2 Cycle 2 HIGHs fully resolved, 1 partially resolved, 2 new HIGHs introduced)
- **Current HIGH count: 2**

Convergence NOT reached after the final allowed cycle. Recommend either:
1. Operator override with explicit acknowledgement of the two carried HIGHs (wrong deployed path + snapshot-dir plumbing), accepting that Plan 02 default must be patched at execution time and the snapshot env vars must be set in a single shell session, OR
2. Max-cycles escalation per `/gsd:plan-review-convergence` contract.

CYCLE_SUMMARY: current_high=2
