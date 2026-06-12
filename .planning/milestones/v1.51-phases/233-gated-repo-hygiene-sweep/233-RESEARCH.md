# Phase 233: Gated Repo Hygiene Sweep - Research

**Researched:** 2026-06-11
**Domain:** Repo hygiene / deletion-and-doc-sweep under a machine-checkable boundary guard (no feature work, no controller-path changes)
**Confidence:** HIGH (all claims verified against live repo state via git plumbing, grep, and script execution)

## Summary

Phase 233 is a **deletion / doc-hygiene phase**, not a feature phase. The risk model is "delete something still referenced" and "touch a denylisted surface." The good news: the Phase 232 BOUND-01 guard (`scripts/check-cleanup-boundary.sh`) already exists, passes clean on the current tree, and fails closed on any protected-surface touch. SAFE-15 controller-path zero-diff also currently holds (verified: `git diff --quiet v1.50..HEAD -- <controller paths>` exits 0). The phase is small and surgical.

The single most important finding the planner must internalize: **the entire `.planning/cake-autorate-trials/` directory is git-ignored** (`.gitignore:12` matches `.planning/` and the trial subtree was never force-added). All 22 top-level `run_*` one-off trial scripts plus ~68M of timestamped result dirs are **untracked, worktree-only files**. No tracked file references any of them. This reshapes SWEEP-01: removing them is a pure filesystem operation invisible to `git`, and — crucially — invisible to the boundary guard too (the guard inspects git-tracked/anchor blobs, except for `must-exist` rows it checks via `Path.exists()`). The canonical denylist-source doc `WANCTL_CAKE_AUTORATE_FUTURE.md` is itself untracked and protected only by a filesystem-existence `must-exist` row.

SWEEP-02 (residual stale native-ownership docs) and SWEEP-03 (Spectrum-only hardcoding where a generic `$wan` pattern already exists) both have concrete, enumerable targets. SWEEP-03 in particular has a clean, no-new-abstraction fix already latent in the codebase: the two state-bridge scripts are **byte-identical** and already fully env-driven (`WANCTL_EXTERNAL_*`); the only Spectrum-only hardcoding is that the Spectrum systemd unit relies on the script's Spectrum-flavored fallback defaults while the ATT unit sets every env var explicitly.

**Primary recommendation:** Run the BOUND-01 guard and the SAFE-15 boundary check before AND after every commit. Scope SWEEP-01 to deleting the untracked trial subtree (deletion safety already proven — zero tracked references). Scope SWEEP-02 to adding a one-line mode-disambiguation note to the ~5 operational docs that show `wanctl@<wan>` commands without noting external cake-autorate mode (do NOT delete the operational examples — the native unit is still a real, documented procedure). Scope SWEEP-03 to making the Spectrum bridge unit explicit (mirror the ATT unit) and/or neutralizing the Spectrum-specific script defaults — no new abstraction, the env pattern already exists.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trial-script removal (SWEEP-01) | Repo / planning artifacts (untracked) | — | Lives entirely in git-ignored `.planning/cake-autorate-trials/`; filesystem op only |
| Doc mode-disambiguation (SWEEP-02) | Docs (`docs/*.md`, README) | — | Pure documentation surface; no code/config behavior |
| Spectrum hardcoding removal (SWEEP-03) | Deploy artifacts (`deploy/systemd/`, `deploy/scripts/`) | — | systemd unit env + bridge script defaults; deploy-layer only, NOT controller path |
| Boundary enforcement (gate) | Tooling (`scripts/check-cleanup-boundary.sh`) | — | Read-only git/worktree guard; runs as a gate, owns no product behavior |
| Controller invariant (SAFE-15) | `src/wanctl/` controller path | — | MUST remain zero-diff vs `v1.50`; this phase must not touch it at all |

## Standard Stack

No external packages are installed or required by this phase. It uses only repo-local tooling already delivered by Phase 232 and the existing test/lint stack.

### Core (existing, no install)
| Tool | Purpose | Why Standard |
|------|---------|--------------|
| `scripts/check-cleanup-boundary.sh` | BOUND-01 denylist guard, JSON evidence, exit 0/1/2 | Delivered + verified by Phase 232; the gate for every SWEEP change `[VERIFIED: ran clean on current tree]` |
| `scripts/phase225-safe13-boundary-check.sh` | SAFE-15 controller-path zero-diff proof vs anchor | Established SAFE-07..14 checker; reused for SAFE-15 `[VERIFIED: ran clean --anchor v1.50]` |
| `git` plumbing (`ls-files`, `hash-object`, `rev-parse`, `diff --quiet`) | Tracking/diff inspection, deletion-safety, zero-diff proof | Repo-native; no install |
| `.venv/bin/pytest` | Default-suite gate incl. `tests/test_cleanup_boundary_guard.py` | Existing test infra `[VERIFIED: 9 passed]` |
| `.venv/bin/ruff` / `shellcheck` | Lint gates for any touched script | Existing project CI gates |

**Installation:** None. `## Package Legitimacy Audit` is intentionally omitted — this phase installs zero external packages.

## Project Constraints (from CLAUDE.md)

- **Production network control system — change conservatively.** Priority: **stability > safety > clarity > elegance**.
- **Controller is link-agnostic.** Deployment-specific behavior belongs in YAML/env, **not** Python branching. SWEEP-03 must NOT introduce a new `$wan` abstraction — only remove hardcoding where a generic pattern already exists.
- **Never refactor core logic / algorithms / thresholds / timing without approval.** This phase touches none of that — controller path is zero-diff (SAFE-15).
- **`always_confirm_destructive: true`** (config.json) — deletions (SWEEP-01) are destructive; planner should gate the actual `rm`/archive on operator confirmation and/or a reversible move.
- **project-finalizer is MANDATORY before every commit** (CLAUDE.md Git Workflow). Phase 232 used `SKIP_DOC_CHECK=1` for task commits per repo research guidance; expect the doc pre-commit hook to fire on doc/script edits.
- Both WANs run **cake-autorate external mode** since 2026-06-08; `wanctl@` units disabled in production; state bridges feed steering/health. The two-mode reality is the doc target for SWEEP-02.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SWEEP-01 | Remove/archive superseded one-off trial scripts per the "safe to remove soon" policy; boundary guard passes | Cleanup policy located (`WANCTL_CAKE_AUTORATE_FUTURE.md:73-87`); trial subtree is untracked + zero tracked references (deletion-safe); guard passes clean now |
| SWEEP-02 | No active doc describes Spectrum/ATT as native-wanctl-owned rate control without noting external mode (residual beyond v1.50 Phase 231 DOCS-04) | Concrete file/line inventory below; DOCS-04's "no `wanctl@` hits" claim is stale — many operational-command hits remain |
| SWEEP-03 | Strip Spectrum-only hardcoding only where a generic `$wan` bridge/service pattern already exists; no new abstraction; native path untouched | Bridge scripts byte-identical + fully env-driven; Spectrum unit relies on script defaults, ATT unit is explicit — the generic pattern already exists |
| SAFE-15 | Controller-path zero-diff at phase boundary | Verified holding now; exact diff command + checker documented below |
</phase_requirements>

## Architecture Patterns

### System Architecture Diagram (the gate loop)

```
  [SWEEP change]  (delete trial files | edit doc | edit deploy unit/script)
        |
        v
  scripts/check-cleanup-boundary.sh --out <evidence.json>     <-- BOUND-01 gate
        |  exit 0  -> proceed                exit 1 -> STOP (denylist violation, revert)
        v
  scripts/phase225-safe13-boundary-check.sh --anchor v1.50    <-- SAFE-15 gate
        |  passed -> proceed                 failed -> STOP (controller path drifted)
        v
  .venv/bin/pytest (cleanup-boundary + hot-path slice)        <-- regression gate
        |
        v
  project-finalizer -> commit (SKIP_DOC_CHECK=1 if doc hook blocks task commit)
```

A reader traces every SWEEP edit through three gates before it lands. The guard is read-only; it never mutates the worktree.

### Pattern 1: Guard-before-and-after every commit (BOUND-01)
**What:** Run `bash scripts/check-cleanup-boundary.sh --out <path>` immediately before and after each SWEEP commit.
**When to use:** Every task that deletes a file, edits a deploy artifact, or edits a doc near a protected surface.
**Example:**
```bash
# Source: scripts/check-cleanup-boundary.sh header + Phase 232 verification
bash scripts/check-cleanup-boundary.sh --out /tmp/bound01-pre.json   # expect exit 0
# ... make the change ...
bash scripts/check-cleanup-boundary.sh --out /tmp/bound01-post.json  # expect exit 0
# exit 1 = BOUND-01 VIOLATION (revert immediately); exit 2 = usage/anchor error
```
The guard's protected manifest (26 rows) lives inline in the script (`scripts/check-cleanup-boundary.sh:108-140`). Policies: `must-match-anchor` (file must equal `v1.50` blob — controller, native deploy path, native tests, native config validation, `phase227-rollback.sh`) and `must-exist` (deletion forbidden, content drift allowed — `phase231-rollback.sh`, its test, `docs/UPGRADING.md`, `docs/DEPLOYMENT.md`, and the FUTURE doc).

### Pattern 2: Deletion-safety proof before removing untracked files (SWEEP-01)
**What:** Prove no tracked file references a trial script before deleting it.
**Example:**
```bash
# Source: verified during research
git grep -l "run_one_trial" | grep -v cake-autorate-trials   # expect: no output
```
All 22 `run_*` one-offs returned zero tracked references.

### Pattern 3: Mirror-the-generic-unit, don't abstract (SWEEP-03)
**What:** Make the Spectrum systemd bridge unit explicit (set `WANCTL_EXTERNAL_*` env like the ATT unit already does) instead of relying on the script's Spectrum-flavored fallback defaults. The generic env pattern ALREADY exists in the script — no new abstraction is introduced.

### Anti-Patterns to Avoid
- **Deleting operational `wanctl@<wan>` command examples for SWEEP-02.** Native mode is still a real, documented rollback/profiling procedure. SWEEP-02 wants a *mode-disambiguation note*, not removal of the native procedure. Deleting it would lose operator value and risk drifting `must-match-anchor` native deploy docs.
- **Introducing a new shared/parameterized bridge file or a `$wan`-template unit for SWEEP-03.** Out of scope per REQUIREMENTS.md ("no new `$wan` abstractions"). The fix is to remove hardcoding using the env pattern that exists, not to build a template.
- **Touching anything under `src/wanctl/` controller path.** SAFE-15 forbids it. The whole milestone surface is "scripts/docs/planning/tests only — zero src/wanctl controller-path mutation" (STATE.md:97).
- **Trusting the boundary guard to catch trial-file deletion.** It will NOT — those files are untracked and not in the manifest. The guard protects the *retention* set, not the *removal* set. Deletion safety for SWEEP-01 comes from the grep proof, not the guard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Denylist enforcement | A new check script or ad-hoc grep | `scripts/check-cleanup-boundary.sh` | Phase 232 delivered + verified it; 26-row manifest, JSON evidence, fail-closed |
| Controller zero-diff proof | Manual file-by-file diff | `scripts/phase225-safe13-boundary-check.sh --anchor v1.50` | Established SAFE-07..14 checker with object-ID + numstat proof |
| Deletion-safety reference check | Reading files by hand | `git grep -l <name>` | Deterministic, fast, already proven zero refs |

**Key insight:** All the hard tooling for this phase already exists. The phase is about *applying* the gates surgically, not building anything.

## Runtime State Inventory

> This is a rename/refactor/deletion phase — inventory required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None affected. Trial result dirs hold historical CSV/flent data only; no live datastore keys reference trial-script names. SWEEP-03 does NOT change WAN names, DB paths, or state-file paths (`metrics-<wan>.db`, `<wan>_state.json` stay identical). | None — verified `metrics-spectrum.db`/`spectrum_state.json` references unchanged by the proposed SWEEP-03 fix |
| Live service config | `cake-autorate-spectrum-state-bridge.service` and `cake-autorate-att-state-bridge.service` are installed on the live host (`/etc/systemd/system`, `/usr/local/sbin`). SWEEP-03 edits to the **repo** unit/script do NOT auto-apply — a redeploy + `systemctl daemon-reload` is required to take effect live. | Repo edit only this phase; flag that live apply needs operator-gated redeploy (out of scope for the sweep, but must be noted so repo≠prod is explicit) |
| OS-registered state | systemd unit *names* are unchanged by the recommended SWEEP-03 fix (mirror ATT env in the Spectrum unit). If the planner instead consolidates `ExecStart` to a single shared script path, that changes an installed path and requires reinstall — higher risk, recommend against. | None if name/path preserved; reinstall if path consolidated (recommend preserving) |
| Secrets/env vars | The Spectrum bridge unit sets only `CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.223`. Making it explicit ADDS `WANCTL_EXTERNAL_WAN_NAME=spectrum` etc. matching current script defaults — no secret involved, no behavior change (defaults already equal the explicit values). | Add explicit env vars equal to current defaults; verify the `WANCTL_EXTERNAL_BASELINE_RTT` Spectrum default (`22.535852814520855`) is the intended live value before pinning it in the unit |
| Build artifacts | Trial dir contains `__pycache__` and timestamped result dirs (~68M total, untracked). No egg-info / installed-package staleness from this phase (no `pyproject.toml`/package rename). | Delete trial `__pycache__` with the trial subtree; no package reinstall needed |

**Canonical question — after every repo file is updated, what runtime state still carries the old shape?** The live systemd units on the host still carry the pre-edit env until a redeploy. That redeploy is explicitly *out of scope* for the sweep (repo hygiene only); the planner must state "repo edit ≠ live apply" so no one assumes the Spectrum unit changed in production.

## Common Pitfalls

### Pitfall 1: Assuming the boundary guard gates SWEEP-01 deletions
**What goes wrong:** Planner writes "delete trial scripts, guard confirms safety." The guard does not see untracked files; it confirms the *retention* set is intact, not that the *deleted* set was safe.
**Why it happens:** The guard's purpose ("fails closed if denylisted surface is touched") is easy to over-read as "validates all deletions."
**How to avoid:** Use `git grep -l` for deletion safety; use the guard only to confirm no protected surface was collaterally touched.
**Warning signs:** A task whose only deletion-safety evidence is "guard passed."

### Pitfall 2: Over-deleting for SWEEP-02
**What goes wrong:** Treating every `wanctl@spectrum`/`wanctl@att` doc hit as a stale native-ownership claim and removing the command. Many are legitimate native-mode operational procedures (profiling, journalctl, silicom-bypass which references the native unit *by design*).
**Why it happens:** Phase 231 DOCS-04's verification recorded "grep found no `wanctl@spectrum`/`wanctl@att` active-doc hits" — but that is stale: the current tree has many hits across 6 docs. Reconciling that gap by deleting is the wrong move.
**How to avoid:** SWEEP-02's bar is "describes Spectrum/ATT as native-wanctl-owned rate control *without noting external mode*." The fix is a mode-disambiguation note (the README already models this at lines 80-82, 265-267), not deletion.
**Warning signs:** A task that removes a `systemctl`/`journalctl` example or edits a `must-match-anchor` native deploy doc.

### Pitfall 3: Stale DOCS-04 claim creates a false "already done" read
**What goes wrong:** Reading 231-VERIFICATION.md, the planner concludes SWEEP-02 is mostly empty.
**Why it happens:** DOCS-04 cleaned README/DEPLOYMENT/CONFIGURATION/ARCHITECTURE (which DO now note external mode) but did not sweep PERFORMANCE/PROFILING/RUNBOOK/CABLE_TUNING/STEERING/SILICOM-BYPASS (which do NOT mention external mode at all — verified 0 hits each).
**How to avoid:** Use the concrete residual inventory below, not the DOCS-04 summary.

### Pitfall 4: SWEEP-03 scope creep into a new abstraction
**What goes wrong:** "The two bridge files are identical, let's merge them into one shared file with a `$wan` arg." That is a NEW abstraction — explicitly out of scope.
**How to avoid:** The minimal in-scope fix is to make the Spectrum *unit* explicit (env vars) so the script's Spectrum-flavored defaults are no longer the load-bearing source of Spectrum identity. Optionally neutralize the script defaults. Do not consolidate files.

## SWEEP-01 Inventory: trial scripts (untracked, in `.planning/cake-autorate-trials/`)

**Tracking status:** entire dir git-ignored via `.gitignore:12` (`.planning/`); never force-added. `git ls-files .planning/cake-autorate-trials/` returns 0 files. Size ~68M.

**"Safe to remove soon" policy text** (`WANCTL_CAKE_AUTORATE_FUTURE.md:75-79`):
> - temporary one-off trial scripts that are superseded by repo-owned deploy artifacts
> - stale docs that describe Spectrum as native-wanctl-owned without noting current external mode
> - Spectrum-only hardcoding after a generic `$wan` bridge/service pattern exists

**"Not safe to remove yet"** (`:81-87`): native controller (`autorate_continuous.py`), native `wanctl@$wan.service` deploy path, native controller tests, native config validation, rollback commands/docs. **All of these are also the BOUND-01 manifest — the guard is the machine-checkable encoding of this list.**

**Concrete one-off trial scripts (22 top-level `run_*`), all untracked, all zero tracked references:**
`run_one_trial.sh`, `run_netperf_ping_trial.sh`, `run_att_netperf_trial.py`, `run_att_dev_bound_trial.py`, `run_att_dev_bound_full_trial.py`, `run_att_http_multidown.py`, `run_att_manual_tcp12down.py`, `run_spectrum_dev_bound_full_trial.py`, `run_spectrum_cap_sweep.py`, `run_spectrum_4mode_ladder.py`, `run_spectrum_cake_flags_sweep.py`, `run_spectrum_cake_placement.py`, `run_spectrum_dallas_same_window_ab.py`, `run_spectrum_dual_iperf_lower_cap_ladder.py`, `run_spectrum_first_hop_localization.py`, `run_spectrum_htb_fq_codel_alternating.py`, `run_spectrum_htb_fq_codel_ceiling_sweep.py`, `run_spectrum_path_localization.py`, `run_spectrum_qdisc_followup.py`, `run_spectrum_qdisc_offload_mechanics.py`, `run_spectrum_raw_vs_inline_ab.py`, `run_spectrum_same_window_path_variance.py`, plus `parse_flent_summary.py` and dozens of timestamped result subdirs.

**DO NOT touch within the trials dir:** `WANCTL_CAKE_AUTORATE_FUTURE.md` (BOUND-01 `must-exist` denylist source — deletion fails the guard). `SPECTRUM_CAKE_FINDINGS.md` and the `*-review-*.md` markdown summaries are *findings* docs, not one-off scripts — planner should treat these as "keep or archive, operator call," NOT auto-remove (they are knowledge, not superseded tooling).

**Planner decision needed:** delete vs archive. Since the subtree is untracked, "archive" within the same ignored dir achieves nothing in git terms. Recommend: operator-confirmed `rm` of the `run_*` one-off scripts + their result dirs, preserving the FUTURE doc and findings `.md` files. Because deletion is destructive and `always_confirm_destructive: true`, gate the actual removal behind a `checkpoint:human-verify` task.

## SWEEP-02 Inventory: residual native-ownership doc surfaces

**Bar:** active doc presents Spectrum/ATT as *currently native-wanctl-owned rate control* without noting external cake-autorate mode.

**Already compliant (DOCS-04, Phase 231) — note external mode, leave alone:** `README.md` (lines 80-82, 265-267 explicitly scope native vs external), `docs/ARCHITECTURE.md` (lines 24, 41-48 describe external mode; the line-71 `wanctl@spectrum` is a link-agnostic portability illustration, not a current-ownership claim), `docs/DEPLOYMENT.md`, `docs/CONFIGURATION.md`.

**Residual candidates — `wanctl@<wan>` hits with ZERO external-mode mention (verified `grep -ciE 'cake-autorate|external mode' = 0`):**

| Doc | Nature of hits | SWEEP-02 disposition | Confidence |
|-----|----------------|----------------------|-----------|
| `docs/PROFILING.md` | `systemctl edit/restart wanctl@spectrum`, `journalctl -u wanctl@spectrum` (lines 30,46,59,92,102,104,110,117,130,146) | Operational native-mode procedure. Add one mode-disambiguation note at top ("examples assume native `wanctl@` mode; in external cake-autorate mode the controller is `cake-autorate-<wan>.service`"). Do NOT delete commands. | MEDIUM |
| `docs/PERFORMANCE.md` | `systemctl edit/revert/restart wanctl@spectrum`, `journalctl` (lines 53,61,62,68,69) | Same — add disambiguation note. | MEDIUM |
| `docs/RUNBOOK.md` | `journalctl -u wanctl@spectrum.service -u wanctl@att.service` (line 398); DB-name notes (342,348) | Operator runbook. Add disambiguation note where native units are invoked. | MEDIUM |
| `docs/CABLE_TUNING.md` | "Managed `wanctl@spectrum` still underperformed…" (107,146,190-192) + `systemctl restart wanctl@spectrum` (666) | Mostly **historical tuning log** (past-tense experiment narrative) — likely legitimate as-is. The line-666 live command may warrant a note. Operator call on whether historical narrative needs annotation. | LOW |
| `docs/STEERING.md` | `wanctl@<wan>` hit(s); 0 external-mode mentions | Inspect in planning — likely operational steering examples; add note if it asserts current native ownership. | LOW |
| `docs/SILICOM-BYPASS.md` | `Before=wanctl@att.service wanctl@spectrum.service`, "Stopping wanctl@att.service put only ATT into bypass" (35,149,150,177-181,309) | **By design** — the silicom bypass watchdog references the native unit as the thing being stopped/started. These are correct references, not stale ownership claims. Likely NO change, OR a single note that production now runs external mode + the bypass watchdog targets the cake-autorate unit. Operator call. | LOW |

**Recommendation:** SWEEP-02 is a *small annotation* task, not a deletion task. The concrete, defensible work is adding a mode-disambiguation note to `PROFILING.md`, `PERFORMANCE.md`, `RUNBOOK.md` (HIGH-value, clearly missing). `CABLE_TUNING.md`, `STEERING.md`, `SILICOM-BYPASS.md` are judgment calls — surface them to the operator in discuss/plan rather than auto-editing. None of these are `must-match-anchor` protected; all are freely editable (`docs/DEPLOYMENT.md` and `docs/UPGRADING.md` ARE `must-exist`-protected against deletion but content-editable).

## SWEEP-03 Inventory: Spectrum-only hardcoding where generic `$wan` pattern already exists

**The generic pattern already exists** — verified by comparing the two state bridges:

- `deploy/scripts/cake-autorate-spectrum-state-bridge` and `deploy/scripts/cake-autorate-att-state-bridge` are **byte-identical** (`diff` exit 0).
- The shared script body is **fully env-driven**: `WAN_NAME = os.environ.get("WANCTL_EXTERNAL_WAN_NAME", "spectrum")`, `DL_IF=...get(...,"spec-router")`, `UL_IF=...get(...,"spec-modem")`, log/state/DB/baseline-RTT all `WANCTL_EXTERNAL_*` env with **Spectrum-flavored fallback defaults**.

**The Spectrum-only hardcoding (in-scope, no new abstraction needed):**

| Location | Hardcoding | Fix (uses existing env pattern) |
|----------|-----------|-------------------------------|
| `deploy/systemd/cake-autorate-spectrum-state-bridge.service` | Sets ONLY `CAKE_AUTORATE_BRIDGE_HEALTH_HOST`. Relies on the script's Spectrum defaults for WAN_NAME/DL_IF/UL_IF/LOG/STATE/DB/BASELINE_RTT. ATT unit sets ALL of these explicitly. | Add explicit `WANCTL_EXTERNAL_*` env to the Spectrum unit, mirroring the ATT unit. Values equal current defaults → zero behavior change. Makes Spectrum identity explicit rather than implicit-via-defaults. |
| `deploy/scripts/cake-autorate-*-state-bridge` defaults | The `os.environ.get(..., "spectrum"/"spec-router"/"spec-modem"/...)` fallbacks bake Spectrum into the shared script. | OPTIONAL once the Spectrum unit is explicit: neutralize defaults (e.g., require env, or make defaults generic). Lower priority; do only if the unit is made explicit first so nothing breaks. |

**Out-of-scope / would require NEW abstraction (flag, do NOT do):**
- Merging the two identical bridge files into one shared `/usr/local/sbin/cake-autorate-state-bridge` with a `$wan` arg/path → changes installed paths, requires reinstall, and is a new abstraction. Out of scope.
- `deploy/scripts/cake-autorate-spectrum-qdisc-init`, `deploy/nftables/bridge-qos.nft` (`spectrum_dl` chain, `spec-modem`/`spec-router` rules), `scripts/check-tuning-gate.sh` (`SPECTRUM_CONFIG=/etc/wanctl/spectrum.yaml`), `scripts/add_steering_rules.sh` — these have Spectrum literals but **no pre-existing generic `$wan` pattern** to lean on. Removing their hardcoding would require *building* an abstraction → out of scope by SWEEP-03's own precondition.

**Recommendation:** SWEEP-03's only clean, in-scope target is making `cake-autorate-spectrum-state-bridge.service` explicit (mirror ATT). This is behavior-preserving (defaults already equal the values), removes the implicit Spectrum hardcoding, and introduces no abstraction. Verify the `WANCTL_EXTERNAL_BASELINE_RTT` default `22.535852814520855` is the intended live Spectrum value before pinning it.

## SAFE-15: controller-path zero-diff invariant

**Controller path (the protected set):** `src/wanctl/wan_controller.py`, `wan_controller_state.py`, `queue_controller.py`, `cake_signal.py`, `alert_engine.py`, `fusion_healer.py`, and `src/wanctl/backends/` (all files). `[VERIFIED: scripts/phase225-safe13-boundary-check.sh:68-74]`

**Exact zero-diff command (currently exits 0):**
```bash
git diff --quiet v1.50..HEAD -- \
  src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py \
  src/wanctl/queue_controller.py src/wanctl/cake_signal.py \
  src/wanctl/alert_engine.py src/wanctl/fusion_healer.py src/wanctl/backends/
# exit 0 = zero-diff (verified 2026-06-11)
```

**Canonical proof checker (writes JSON evidence, the format prior phases used):**
```bash
bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/safe15-boundary-233.json
# "SAFE-13 boundary check passed" + JSON {passed:true, controller_path_diff_count:0} (verified)
```
The checker also covers committed + staged + dirty-tree diff and per-file object-ID equality vs the anchor, so it is strictly stronger than `--quiet`. Phase 232 stored its proof at `evidence/safe15-boundary-232.json`; mirror that for 233.

## Code Examples

### Run all three gates after a SWEEP change
```bash
# Source: Phase 232 verification + script headers (all verified clean on current tree)
bash scripts/check-cleanup-boundary.sh \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/cleanup-boundary-233.json   # exit 0
bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/safe15-boundary-233.json    # passed
.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q                     # 9 passed
```

### Hot-path regression slice (per CLAUDE.md, run on any deploy/script touch)
```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py \
  tests/test_wan_controller.py tests/test_health_check.py -q
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `wanctl@<wan>.service` owns rate control (native autorate) | `cake-autorate-<wan>.service` owns rates; `cake-autorate-<wan>-state-bridge.service` publishes wanctl-compatible state/health | 2026-06-08 (both WANs migrated; `wanctl@` disabled) | Docs must note both modes; native path retained as rollback (denylisted, not removable) |
| Phase 231 DOCS-04 "no `wanctl@` doc hits" | Stale — 6 docs still carry native-unit references with no external-mode note | This research (2026-06-11) | SWEEP-02 residual is real and enumerated above |

**Deprecated/outdated:**
- The 231-VERIFICATION.md DOCS-04 line "grep found no `wanctl@spectrum`/`wanctl@att` active-doc hits" is not accurate against the current tree. Use this research's inventory, not that claim.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `CABLE_TUNING.md`, `STEERING.md`, `SILICOM-BYPASS.md` native-unit references are legitimate (historical/by-design) and may need no SWEEP-02 edit | SWEEP-02 inventory | If operator wants them annotated, scope is slightly larger; LOW risk — additive notes only |
| A2 | Making the Spectrum bridge unit explicit is behavior-preserving because unit env defaults already equal the script defaults | SWEEP-03 inventory | If the live `BASELINE_RTT` differs from the `22.535852814520855` default, pinning it could change bridge baseline behavior — verify against live before committing |
| A3 | SWEEP-01 = delete (not archive), since the trials subtree is git-ignored and "archiving" within it is a no-op | SWEEP-01 inventory | If operator wants the trial scripts preserved in a tracked archive, that's a different (additive) task; LOW risk — surface in discuss/plan |
| A4 | The findings `.md` files in the trials dir (`SPECTRUM_CAKE_FINDINGS.md`, `*-review-*.md`) are knowledge to keep, not one-off scripts to remove | SWEEP-01 inventory | If treated as removable, knowledge loss — recommend keep/operator-confirm |

## Open Questions (RESOLVED — gated to operator checkpoints in Plans 01-03)

1. **Delete vs archive for SWEEP-01 trial scripts.**
   - What we know: subtree is git-ignored, untracked, zero tracked references, ~68M, 22 `run_*` one-offs + result dirs.
   - What's unclear: whether operator wants outright `rm` or a tracked archive (e.g., move to `docs/.archive/` — the existing archive convention — which would *git-add* them, the opposite of hygiene).
   - Recommendation: operator-confirmed `rm` of `run_*` scripts + result dirs; preserve FUTURE doc + findings `.md`. Gate behind `checkpoint:human-verify` (destructive).

2. **SWEEP-02 breadth: annotate all 6 docs or only the 3 clear ones?**
   - What we know: PROFILING/PERFORMANCE/RUNBOOK clearly lack any external-mode note; CABLE_TUNING/STEERING/SILICOM-BYPASS are judgment calls.
   - Recommendation: do the clear 3 with a standard one-line note (mirror README's phrasing); surface the other 3 for operator decision in discuss-phase.

3. **SWEEP-03: edit the Spectrum unit only, or also neutralize script defaults?**
   - What we know: making the unit explicit fully removes the load-bearing Spectrum hardcoding with zero behavior change.
   - Recommendation: unit-explicit first (clearly in scope, behavior-preserving). Treat default-neutralization as optional follow-up; do not consolidate the two identical files (new abstraction).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `git` | All gates / inventory | ✓ | repo-native | — |
| `python3` | Boundary guard, SAFE-15 checker | ✓ | 3.11/3.12 (mypy cache shows both) | — |
| `.venv/bin/pytest` | Regression gate | ✓ | per project | — |
| `shellcheck` | Lint touched scripts | ✓ (used in Phase 232) | — | `bash -n` syntax-only |
| `git tag v1.50` | SAFE-15 + boundary anchor | ✓ | resolves | — |

No external/network dependencies. No live host access required — this is repo-local hygiene. (Live systemd redeploy of the SWEEP-03 unit edit is explicitly out of scope.)

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`). Section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project `.venv`) |
| Config file | `pyproject.toml` (addopts present; override with `-o addopts=''` for focused runs, per CLAUDE.md) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements → Test/Gate Map
| Req ID | Behavior | Type | Automated Command | Exists? |
|--------|----------|------|-------------------|---------|
| SWEEP-01 | Superseded trial files removed; no protected surface touched | gate | `bash scripts/check-cleanup-boundary.sh --out <ev>` (exit 0) + `git grep -l <name>` (no tracked refs) | ✅ |
| SWEEP-01 | Guard still green after removal | gate + test | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` | ✅ (9 passed) |
| SWEEP-02 | No active doc claims native ownership w/o external-mode note | grep sweep | `for f in docs/PROFILING.md docs/PERFORMANCE.md docs/RUNBOOK.md; do grep -ciE 'cake-autorate\|external mode' $f; done` (each ≥1 after edit) | ✅ (grep) |
| SWEEP-02 | Native deploy docs not collaterally damaged | gate | boundary guard (DEPLOYMENT.md/UPGRADING.md `must-exist`) | ✅ |
| SWEEP-03 | Spectrum hardcoding removed; native path untouched | gate + lint | boundary guard exit 0 + `diff` confirming bridge scripts still valid + `shellcheck`/`bash -n` on touched units | ✅ |
| SAFE-15 | Controller-path zero-diff at boundary | gate | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out <ev>` + `git diff --quiet v1.50..HEAD -- <controller paths>` | ✅ (passed now) |

### Sampling Rate
- **Per task commit:** BOUND-01 guard (exit 0) + `tests/test_cleanup_boundary_guard.py` + (if deploy/script touched) hot-path slice + `shellcheck`/`ruff`.
- **Per wave merge:** full `.venv/bin/pytest tests/` + SAFE-15 boundary check.
- **Phase gate:** BOUND-01 guard green, SAFE-15 zero-diff proven (JSON evidence committed), full suite green, before `/gsd:verify-work`.

### Wave 0 Gaps
- None for tooling — `scripts/check-cleanup-boundary.sh`, `scripts/phase225-safe13-boundary-check.sh`, and `tests/test_cleanup_boundary_guard.py` all exist and pass.
- Evidence dir to create: `.planning/phases/233-gated-repo-hygiene-sweep/evidence/` for `cleanup-boundary-233.json` and `safe15-boundary-233.json` (mirrors Phase 232 layout).

## Security Domain

security_enforcement is not disabled in config, but this phase has **no auth/session/access-control/crypto/input-validation surface**: it deletes untracked trial files, annotates docs, and edits a systemd unit's env. No threat-bearing code path is added or modified. The controller path is zero-diff by invariant.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | no | No new input surface; guard/checker are read-only |
| V6 Cryptography | no | None touched |
| V2/V3/V4 Auth/Session/Access | no | None touched |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental deletion of a still-referenced file | Denial of Service (loss of retention surface) | BOUND-01 guard (fail-closed on protected touch) + `git grep` deletion-safety proof |
| Silent controller-path drift via collateral edit | Tampering | SAFE-15 zero-diff gate at boundary |
| Deploy-unit edit changing live bridge behavior | Tampering | Behavior-preserving (defaults == explicit values); repo edit only, live redeploy out of scope + operator-gated |

## Sources

### Primary (HIGH confidence)
- `scripts/check-cleanup-boundary.sh` (read full) — manifest rows 108-140, policy semantics, exit contract; ran clean on current tree
- `scripts/phase225-safe13-boundary-check.sh` — controller path 68-74, diff mechanics; ran clean `--anchor v1.50`
- `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md:62-87` — cleanup policy + no-delete list
- `.planning/phases/232-.../232-VERIFICATION.md` — BOUND-01/FIX-01/FIX-02/SAFE-15 closeout (4/4)
- `.planning/REQUIREMENTS.md:22-89`, `.planning/ROADMAP.md:72-85`, `.planning/STATE.md:97,114-120`
- `deploy/systemd/cake-autorate-{spectrum,att}-state-bridge.service` + `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge` — diff (identical scripts), env-driven body
- Live `git` plumbing: `ls-files` (trials untracked), `check-ignore -v` (`.gitignore:12`), `grep -l` (zero tracked trial refs), `diff --quiet v1.50..HEAD` (controller zero-diff)

### Secondary (MEDIUM confidence)
- `docs/*.md` grep inventory for SWEEP-02 (file/line hits + per-file external-mode mention counts) — verified counts, but disposition (annotate vs leave) is judgment per doc

### Tertiary (LOW confidence)
- SWEEP-02 disposition for CABLE_TUNING/STEERING/SILICOM-BYPASS (historical-vs-current framing) — needs operator confirmation in discuss/plan

## Metadata

**Confidence breakdown:**
- Standard stack / tooling: HIGH — every gate script exists and was executed clean this session
- SWEEP-01 inventory + deletion safety: HIGH — untracked status and zero-reference both verified
- SWEEP-03 inventory: HIGH — identical-bridge + env-driven + Spectrum-default-reliance all verified
- SWEEP-02 inventory: MEDIUM — hits verified; per-doc disposition is judgment (LOW for 3 of 6)
- SAFE-15: HIGH — zero-diff proven, exact command + checker confirmed

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (stable repo-local domain; re-verify trial-dir contents and doc grep if the tree changes before planning)
