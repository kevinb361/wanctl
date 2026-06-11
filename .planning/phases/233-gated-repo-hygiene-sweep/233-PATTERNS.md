# Phase 233: Gated Repo Hygiene Sweep - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 11 (2 evidence JSONs created, 22+ trial files deleted, ~5 docs annotated, 1 systemd unit edited, optional 1 bridge script)
**Analogs found:** 11 / 11 (every touched surface has an in-repo analog — this is an *apply-the-pattern* phase, nothing novel)

> This is a deletion / doc-annotation / config-mirror phase. There is no new code logic. "Patterns" here means: which existing file each touched file should copy phrasing, structure, or env layout from. The controller path is zero-diff by invariant (SAFE-15) — no `src/wanctl/` pattern applies.

## File Classification

| Touched File | Op | Role | Data Flow | Closest Analog | Match Quality |
|--------------|----|------|-----------|----------------|---------------|
| `.planning/.../evidence/cleanup-boundary-233.json` | create (gate output) | evidence/config | transform (script-emitted) | `232-.../evidence/safe15-boundary-232.json` | exact (same emitter family) |
| `.planning/.../evidence/safe15-boundary-233.json` | create (gate output) | evidence/config | transform (script-emitted) | `232-.../evidence/safe15-boundary-232.json` | exact (same emitter, `phase225-safe13-boundary-check.sh`) |
| `.planning/cake-autorate-trials/run_*.{sh,py}` (22) | delete (untracked) | trial scripts | batch (one-off experiments) | n/a — pure filesystem removal, no analog needed | n/a |
| `docs/PROFILING.md` | annotate | docs | n/a | `README.md:263-266` (mode note) | exact phrasing template |
| `docs/PERFORMANCE.md` | annotate | docs | n/a | `README.md:263-266` | exact phrasing template |
| `docs/RUNBOOK.md` | annotate | docs | n/a | `README.md:263-266` | exact phrasing template |
| `docs/CABLE_TUNING.md` | annotate (operator call) | docs | n/a | `README.md:263-266` | template if edited |
| `docs/STEERING.md` | annotate (operator call) | docs | n/a | `README.md:263-266` | template if edited |
| `docs/SILICOM-BYPASS.md` | annotate (operator call) | docs | n/a | `README.md:263-266` | template if edited |
| `deploy/systemd/cake-autorate-spectrum-state-bridge.service` | edit (mirror ATT) | config (systemd unit) | event-driven (bridge service) | `deploy/systemd/cake-autorate-att-state-bridge.service` | exact (sibling unit) |
| `deploy/scripts/cake-autorate-spectrum-state-bridge` (defaults) | edit (optional) | utility/config | transform | `deploy/scripts/cake-autorate-att-state-bridge` (byte-identical) | exact (same file content) |

## Pattern Assignments

### Evidence JSONs (gate output — DO NOT hand-author)

**Analog:** `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json`

**These files are NOT written by the planner or implementer — they are emitted by the gate scripts via `--out`.** Mirror the Phase 232 path layout exactly: a phase-local `evidence/` dir holding one JSON per gate.

**SAFE-15 evidence — emit, don't write** (mirror `safe15-boundary-232.json` shape):
```bash
# Source: 233-RESEARCH.md:234-238 + Phase 232 evidence layout
mkdir -p .planning/phases/233-gated-repo-hygiene-sweep/evidence
bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/safe15-boundary-233.json
# expect stdout: "SAFE-13 boundary check passed"
# expect JSON: {"passed": true, "controller_path_diff_count": 0, "anchor": "v1.50", ...}
```

The emitted JSON shape (from `safe15-boundary-232.json`, verified) carries: `anchor`, `passed`, `controller_path_diff_count`, `expanded_protected_files[]` (12 controller files incl. all of `src/wanctl/backends/`), `per_file_object_ids{anchor_blob,worktree_blob}`, `per_file_sha256_equal{}`, `dirty_tree_clean`, `committed_clean`, `staged_clean`. The planner asserts `passed == true` and `controller_path_diff_count == 0`; it does NOT construct this by hand.

**BOUND-01 evidence — emit, don't write:**
```bash
# Source: 233-RESEARCH.md:245-246
bash scripts/check-cleanup-boundary.sh \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/cleanup-boundary-233.json
# expect exit 0; exit 1 = denylist violation (revert); exit 2 = usage/anchor error
```

**Layout rule:** Phase 232 stored both `evidence/safe15-boundary-232.json` and `evidence/fix02-digest-validation.md` in a phase-local `evidence/` dir. Phase 233 mirrors this: `evidence/cleanup-boundary-233.json` + `evidence/safe15-boundary-233.json`. Filename suffix tracks the phase number (`-232` → `-233`).

---

### SWEEP-01: trial-script deletion (`.planning/cake-autorate-trials/run_*`)

**Analog:** None — this is a pure filesystem operation on untracked files. No code pattern applies.

**Deletion-safety pattern (copy this proof, not a code structure):**
```bash
# Source: 233-RESEARCH.md:100-104 (Pattern 2). Run per script name before rm.
git grep -l "run_one_trial" | grep -v cake-autorate-trials   # expect: no output (zero tracked refs)
```

**Critical constraints (from RESEARCH, not negotiable):**
- The boundary guard does **NOT** gate this deletion — trial files are untracked and not in the manifest. Deletion safety comes from `git grep -l`, never from "guard passed" (Pitfall 1, RESEARCH:141-146).
- **DO NOT delete:** `WANCTL_CAKE_AUTORATE_FUTURE.md` (BOUND-01 `must-exist` denylist source — deletion FAILS the guard), `SPECTRUM_CAKE_FINDINGS.md`, and any `*-review-*.md` findings docs (knowledge, not superseded tooling — operator-confirm, RESEARCH:176).
- Removal is destructive + `always_confirm_destructive: true` → gate the actual `rm` behind a `checkpoint:human-verify` task (RESEARCH:178).

---

### SWEEP-02: doc mode-disambiguation note

**Analog:** `README.md:263-266` (the canonical, already-in-tree mode-disambiguation note). Also `docs/ARCHITECTURE.md:41-49` and `docs/DEPLOYMENT.md:16-23` show the same external-mode framing.

**Exact phrasing template to copy** (`README.md:263-266`, verified):
```markdown
The examples below are for native `wanctl@` mode. In external cake-autorate mode,
monitor `cake-autorate-<wan>.service`,
`cake-autorate-<wan>-state-bridge.service`, and `steering.service`; the state JSON
and health endpoint contract remain wanctl-compatible.
```

**Quickstart-style variant** (`README.md:80-84`) for docs that introduce native units rather than monitor them:
```markdown
wanctl also supports an external cake-autorate deployment mode where
`cake-autorate-<wan>.service` owns the Linux CAKE rate decisions and a
wanctl-side `cake-autorate-<wan>-state-bridge.service` publishes the same state,
health, and metrics contract.
```

**Application rule:** Add ONE such note near the top of (or above the first `wanctl@<wan>` command block in) each target doc. Do **NOT** delete the native `systemctl`/`journalctl` examples — native mode is a real rollback/profiling procedure (Pitfall 2, RESEARCH:147-151).

**HIGH-value targets (clearly missing external-mode note, do these):** `docs/PROFILING.md`, `docs/PERFORMANCE.md`, `docs/RUNBOOK.md`.
**Operator-call targets (surface in discuss/plan, may need no edit):** `docs/CABLE_TUNING.md` (mostly historical past-tense narrative), `docs/STEERING.md`, `docs/SILICOM-BYPASS.md` (native-unit references are by-design — the bypass watchdog targets the native unit).

**Guard interaction:** None of these are `must-match-anchor` protected, so they are freely editable. `docs/DEPLOYMENT.md` and `docs/UPGRADING.md` ARE `must-exist`-protected (content-editable, deletion-forbidden) — do not delete them.

---

### SWEEP-03: Spectrum bridge unit — mirror the ATT unit

**Analog:** `deploy/systemd/cake-autorate-att-state-bridge.service` (the explicit sibling unit).

**The fix is a copy-the-sibling diff, no new abstraction.** The Spectrum unit currently sets only `CAKE_AUTORATE_BRIDGE_HEALTH_HOST` and leans on the shared script's Spectrum-flavored fallback defaults. Make it explicit by adding the same `WANCTL_EXTERNAL_*` env block the ATT unit already carries.

**ATT unit env block to mirror** (`cake-autorate-att-state-bridge.service:8-16`, verified):
```ini
Environment=WANCTL_EXTERNAL_WAN_NAME=att
Environment=WANCTL_EXTERNAL_DL_IF=att-router
Environment=WANCTL_EXTERNAL_UL_IF=att-modem
Environment=CAKE_AUTORATE_BRIDGE_LOG=/var/log/cake-autorate/cake-autorate.att.log
Environment=WANCTL_EXTERNAL_STATE_PATH=/var/lib/wanctl/att_state.json
Environment=WANCTL_EXTERNAL_METRICS_DB=/var/lib/wanctl/metrics-att.db
Environment=WANCTL_EXTERNAL_BASELINE_RTT=28.42043789020452
Environment=CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227
Environment=CAKE_AUTORATE_BRIDGE_HEALTH_PORT=9101
```

**Spectrum equivalent to insert** — values MUST equal the current script defaults so behavior is unchanged. Defaults read from `deploy/scripts/cake-autorate-spectrum-state-bridge:16-23` (verified):
```ini
Environment=WANCTL_EXTERNAL_WAN_NAME=spectrum
Environment=WANCTL_EXTERNAL_DL_IF=spec-router
Environment=WANCTL_EXTERNAL_UL_IF=spec-modem
Environment=CAKE_AUTORATE_BRIDGE_LOG=/var/log/cake-autorate/cake-autorate.spectrum.log
Environment=WANCTL_EXTERNAL_STATE_PATH=/var/lib/wanctl/spectrum_state.json
Environment=WANCTL_EXTERNAL_METRICS_DB=/var/lib/wanctl/metrics-spectrum.db
Environment=WANCTL_EXTERNAL_BASELINE_RTT=22.535852814520855
# CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.223 already present — keep it
# CAKE_AUTORATE_BRIDGE_HEALTH_PORT=9101 — ATT sets this explicitly; mirror it
```

**Behavior-preservation caveat (RESEARCH A2, RESEARCH:134/273):** the `WANCTL_EXTERNAL_BASELINE_RTT=22.535852814520855` value is the *script default* — confirm it is the intended live Spectrum baseline before pinning it in the unit. The ATT unit pins a different value (`28.42043789020452`), so the baseline is genuinely per-WAN. If the live Spectrum bridge runs on a different baseline, pinning the default would change behavior.

**Out-of-scope (would create a NEW abstraction — flag, do NOT do):**
- Merging the two byte-identical bridge scripts into one shared `$wan`-parameterized file (changes installed paths, requires reinstall) — Pitfall 4, RESEARCH:158-160, 213-214.
- Touching `cake-autorate-spectrum-qdisc-init`, `bridge-qos.nft`, `check-tuning-gate.sh`, `add_steering_rules.sh` — they have Spectrum literals but NO pre-existing generic `$wan` pattern, so removing them requires *building* an abstraction (RESEARCH:215).

**Optional follow-up (`deploy/scripts/cake-autorate-spectrum-state-bridge`):** once the unit is explicit, the script's Spectrum-flavored `os.environ.get(..., "spectrum"/"spec-router"/...)` fallbacks can be neutralized. Lower priority; do only after the unit is explicit so nothing breaks (RESEARCH:211).

**Repo ≠ prod:** this edit is repo-only. Live apply needs an operator-gated redeploy + `systemctl daemon-reload` — explicitly out of scope for the sweep (RESEARCH:132, 137).

---

## Shared Patterns

### Gate-before-and-after every commit (BOUND-01 + SAFE-15)
**Source:** `scripts/check-cleanup-boundary.sh` (header + manifest rows 108-140), `scripts/phase225-safe13-boundary-check.sh` (controller path 68-74)
**Apply to:** Every SWEEP task that deletes a file, edits a deploy artifact, or edits a doc.
```bash
# Source: 233-RESEARCH.md:88-94, 242-250
bash scripts/check-cleanup-boundary.sh --out /tmp/bound01-pre.json    # expect exit 0
# ... make the change ...
bash scripts/check-cleanup-boundary.sh \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/cleanup-boundary-233.json  # exit 0
bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 \
  --out .planning/phases/233-gated-repo-hygiene-sweep/evidence/safe15-boundary-233.json   # passed
# exit 1 on the guard = BOUND-01 VIOLATION → revert immediately
```

### Regression gate (per task commit)
**Source:** CLAUDE.md hot-path slice + `tests/test_cleanup_boundary_guard.py`
**Apply to:** Every SWEEP commit; the hot-path slice specifically on any deploy/script touch (SWEEP-03).
```bash
.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q          # 9 passed
# SWEEP-03 (deploy/script touch) additionally:
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py \
  tests/test_wan_controller.py tests/test_health_check.py -q
```

### Lint gate for touched scripts/units (SWEEP-03)
**Source:** Phase 232 script-edit workflow
**Apply to:** `deploy/scripts/cake-autorate-spectrum-state-bridge` (if edited) and the systemd unit.
```bash
shellcheck deploy/scripts/cake-autorate-spectrum-state-bridge   # or: bash -n / python -c for the .py bridge
# systemd unit: visual diff vs ATT sibling; no daemon-reload in repo
```

### Commit doc-hook handling
**Source:** Phase 232 (used `SKIP_DOC_CHECK=1` for task commits per repo research), RESEARCH:48
**Apply to:** Doc/script edit commits where the project-finalizer doc pre-commit hook fires on hygiene-only changes. project-finalizer remains MANDATORY; `SKIP_DOC_CHECK=1` is the established escape for task-level commits.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.planning/cake-autorate-trials/run_*.{sh,py}` (deletion) | trial scripts | batch | Pure filesystem removal of untracked files; deletion has no "pattern to copy" — only the `git grep -l` safety proof applies |

(Everything else has an exact or near-exact in-repo analog; this is an apply-the-pattern phase.)

## Metadata

**Analog search scope:** `.planning/phases/232-*/evidence/`, `deploy/systemd/`, `deploy/scripts/`, `docs/*.md`, `README.md`
**Files scanned:** 8 (2 sibling units, 1 bridge script, README, ARCHITECTURE, DEPLOYMENT, 1 evidence JSON, RESEARCH)
**Pattern extraction date:** 2026-06-11
**Key verified facts:** ATT unit env block (`:8-16`) is the SWEEP-03 template; Spectrum script defaults (`:16-23`) supply the behavior-preserving values; README `:263-266` is the SWEEP-02 note template; `safe15-boundary-232.json` is the evidence-shape template (emitted, not hand-written).
