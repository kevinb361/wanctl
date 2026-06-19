---
phase: 240
reviewers: [codex]
reviewed_at: 2026-06-15T19:05:00Z
plans_reviewed: [240-01-PLAN.md, 240-02-PLAN.md]
cycles: 2
current_high: 0
---

# Cross-AI Plan Review — Phase 240

## Cycle 2 (2026-06-15) — Post-Revision Verification

**Context:** Cycle 1 raised 2 HIGH concerns (240-01 silent-default coercion of
malformed `measurement` config; 240-02 SAFE-17 verifier false-pass on the
`rtt_backend.py` seam). Both plans were revised to address them. This cycle
verifies whether the fixes fully close the concerns and surfaces any new HIGHs
the revisions introduced.

**Verdict: both cycle-1 HIGHs FULLY RESOLVED; zero new HIGHs introduced.**

### Codex Review (Cycle 2)

#### Plan 240-01

**Summary:** The revised validator plan addresses the silent-default coercion
issue directly. It distinguishes truly absent `measurement.backend` from
malformed present shapes, wires the shared helper into both autorate and steering
validators, and adds unit vectors for the exact failure cases from cycle 1.

**Cycle-1 HIGH disposition: FULLY RESOLVED.**
Task 1 requires direct shape checks using `data.get("measurement")` plus
`"measurement" not in data`, avoiding the `_get_nested()` ambiguity in
`config_base.py:41`. Task 3 verifies `measurement: "fping"`, `measurement: []`,
`{backend: None}`, non-string backend, `irtt`, and unknown values as
`Severity.ERROR`.

**New Concerns:**
- **MEDIUM (NEW):** Add an explicit `{"measurement": None}` vector. The plan's
  logic covers it, but this is the exact `data.get()` edge case most likely to
  regress.
- **LOW (NEW):** The `fping` WARN behavior is tested at helper level, not CLI
  exit-code level. Since `check_config.py:326` owns exit `2`, this is acceptable,
  but a small `main()`/console-script regression would make the claim airtight.

**Suggestions:** Add `measurement: null -> ERROR` and optionally one patched CLI
test proving `fping` absent produces exit `2`, not `1`.

**Risk Assessment: LOW.**

#### Plan 240-02

**Summary:** The revised SAFE-17 plan closes the `rtt_backend.py` false-pass hole.
The new Phase 240 verifier keeps the v1.52 union allowlist but adds a second
Phase-239-close anchor check over `rtt_backend.py` and `rtt_measurement.py`, with
evidence fields and a direct negative test.

**Cycle-1 HIGH disposition: FULLY RESOLVED.**
Task 1 adds `PHASE239_CLOSE_ANCHOR` and requires
`git diff --name-only "$PHASE239_CLOSE_ANCHOR" HEAD -- src/wanctl/rtt_backend.py src/wanctl/rtt_measurement.py`
to be empty. Task 2 specifically commits an `rtt_backend.py` change and expects
verifier failure. That covers the blind spot in `phase239-protected-body-diff.py:21`,
which does not protect `rtt_backend.py`.

**New Concerns:**
- **MEDIUM (NEW):** Static tests should assert `PHASE239_CLOSE_ANCHOR` is a
  concrete SHA that resolves, not just that the variable exists. `03c82de0`
  exists in this repo as the Phase 239 close candidate.
- **MEDIUM (PRE-EXISTING / INHERITED):** If the cloned script keeps `--anchor`, a
  bad invocation like `--anchor HEAD` can weaken the v1.52 breadth proof for
  committed out-of-allowlist drift. Evidence records the anchor, but a boundary
  verifier should ideally pin v1.52 or reject non-default anchors outside tests.
- **LOW (NEW):** The `rtt_backend.py` negative test should assert the failure
  message mentions the Phase-239-close RTT-seam gate, not just non-zero exit.

**Suggestions:** Pin or constrain `--anchor`; add a regex/static assertion for
`PHASE239_CLOSE_ANCHOR`; assert the rtt-backend drift test fails through the
intended gate.

**Risk Assessment: MEDIUM.**

### Cycle 2 Consensus

Single reviewer (Codex). Both cycle-1 HIGHs are **FULLY RESOLVED** with concrete,
verifiable mitigations:
- **240-01:** absent-vs-malformed shape discrimination via direct `data.get("measurement")`
  checks (Task 1), with malformed-shape ERROR vectors in Task 3 — closes the
  silent-icmplib fallback.
- **240-02:** the `PHASE239_CLOSE_ANCHOR` second diff gate plus a committed
  `rtt_backend.py` negative test (Task 2) — closes the union-allowlist false-pass
  hole the `rtt_backend.py`-blind protected-body helper left open.

**No new HIGH concerns.** Remaining items are MEDIUM/LOW polish:
- Add a `{"measurement": None}` ERROR vector (MEDIUM, 240-01).
- Static-assert `PHASE239_CLOSE_ANCHOR` resolves to a concrete SHA (MEDIUM, 240-02).
- Pin/constrain `--anchor` so a bad invocation can't weaken the v1.52 breadth
  proof (MEDIUM, inherited from the 239 clone source).
- Optional CLI exit-2 regression for fping-absent; gate-specific failure-message
  assertion for the rtt_backend drift test (LOW).

**REMAINING_HIGH (cycle 2): 0**

---

## Cycle 1 (2026-06-15) — Initial Review

### Codex Review (Cycle 1)

#### 240-01-PLAN.md

**Summary**
Strong plan overall. It keeps Phase 240 scoped to validator/config registry wiring, avoids runtime/controller construction changes, and has the right CFG-01/02/03 test shape. Main gap: malformed `measurement` shapes can silently resolve as absent if the helper only uses `_get_nested(data, "measurement.backend")`.

**Strengths**
- Tight edit set: validators plus tests only. No `check_config.py`, `autorate_config.py`, or controller-path behavior changes.
- Correctly wires both consumers now while keeping the key inert until Phase 242.
- Good choice to avoid `SCHEMA choices=` so absent `measurement.backend` emits no PASS and preserves CFG-03 baseline.
- Explicitly rejects `irtt`, which matches v1.53 scope.
- Good host-dependent `fping` handling: `shutil.which("fping")`, no subprocess execution.

**Concerns**
- **HIGH:** Task 1 likely misses malformed shape handling. If YAML says `measurement: fping` or `measurement: []`, `_get_nested()` returns default `None`, so the helper would return `[]`. Since `measurement` is registered as known, this silently falls back to `icmplib` instead of erroring. That is a silent default change. See `_get_nested` behavior in `src/wanctl/config_base.py:41`.
- **MEDIUM:** "Non-gating WARN" needs precise wording. The CLI returns exit code `2` for warnings-only in `src/wanctl/check_config.py:330`. That is non-ERROR, but still non-zero for shell gates.
- **LOW:** CFG-03 corpus is hard-coded to three real configs. Probably fine today, but the context mentions broader committed config locations. This could drift.

**Risk Assessment**
**MEDIUM.** Scope control is good, but the malformed `measurement` silent fallback is a real correctness gap because it can hide an operator config error and silently use `icmplib`.

#### 240-02-PLAN.md

**Summary**
Good plan shape for SAFE-17: new Phase 240 script, no mutation of the Phase 239 script, expanded allowlist, and reuse of the protected-body helper. The biggest risk is that anchoring at `v1.52` with a union allowlist may not prove Phase 240 itself avoided new RTT seam edits, especially `rtt_backend.py`.

**Concerns**
- **HIGH:** Task 1's union allowlist anchored at `v1.52` allows `rtt_backend.py` changes in Phase 240, and the reused protected-body helper does not protect `rtt_backend.py`; its protected set covers `rtt_measurement.py` and `wan_controller.py` only in `scripts/phase239-protected-body-diff.py:21`. That can false-pass phase-local drift outside "config/validator surface only."
- **MEDIUM:** Task 2's minimum test list is mostly static. It does not require the same negative coverage as the Phase 239 test: out-of-allowlist committed drift, dirty `src/wanctl` fail-close, and protected-body drift.
- **MEDIUM:** The verifier test can fail during normal execution if Plan 01 source edits are still uncommitted. The plan says run after Plan 01 is committed, but this ordering should be made explicit in the test/workflow.

**Risk Assessment**
**MEDIUM-HIGH.** The script structure is sound, but the `v1.52` union allowlist leaves a meaningful false-pass hole for phase-local RTT seam edits unless a second anchor/check closes it.

### Cycle 1 Consensus

Single reviewer (Codex) this cycle. Both HIGH concerns are concrete, actionable, and consistent with the milestone's stated constraints (CFG-03 no-migration + SAFE-17 no controller-path drift). Both were newly raised and unresolved at cycle 1.

- **HIGH (Plan 01):** Malformed `measurement` shapes silently resolve to `icmplib` instead of erroring. **→ Addressed in cycle 2 revision; FULLY RESOLVED.**
- **HIGH (Plan 02):** `v1.52`-anchored union allowlist false-passes phase-local `rtt_backend.py` drift. **→ Addressed in cycle 2 revision; FULLY RESOLVED.**

**REMAINING_HIGH (cycle 1): 2**
