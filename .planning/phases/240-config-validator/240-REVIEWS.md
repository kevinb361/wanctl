---
phase: 240
reviewers: [codex]
reviewed_at: 2026-06-15T18:31:38Z
plans_reviewed: [240-01-PLAN.md, 240-02-PLAN.md]
---

# Cross-AI Plan Review — Phase 240

## Codex Review

## 240-01-PLAN.md

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

**Suggestions**
- Add tests in Task 3 for `measurement: "fping"`, `measurement: []`, `measurement: {"backend": None}`, and non-string backend values. Present-but-malformed should be `Severity.ERROR`; only absent should be silent.
- In Task 1, explicitly distinguish "missing path" from "present malformed block." Use direct shape checks before `_get_nested`, or inspect `data.get("measurement")`.
- State that `fping` absent produces WARN semantics and CLI exit `2`, not exit `0`, unless deployment tooling already treats `2` as acceptable.
- Add a small corpus discovery assertion, or document why only `configs/att.yaml`, `configs/spectrum.yaml`, and `configs/steering.yaml` are the complete real deployment corpus.

**Risk Assessment**
**MEDIUM.** Scope control is good, but the malformed `measurement` silent fallback is a real correctness gap because it can hide an operator config error and silently use `icmplib`.

## 240-02-PLAN.md

**Summary**
Good plan shape for SAFE-17: new Phase 240 script, no mutation of the Phase 239 script, expanded allowlist, and reuse of the protected-body helper. The biggest risk is that anchoring at `v1.52` with a union allowlist may not prove Phase 240 itself avoided new RTT seam edits, especially `rtt_backend.py`.

**Strengths**
- Correctly creates a new phase-specific verifier instead of editing Phase 239 evidence machinery.
- Preserves fail-closed dirty tree and output path guards.
- Keeps `check_config.py` and `autorate_config.py` out of the allowlist, matching Plan 01 scope.
- Reuses the existing protected-body AST layer, which is appropriate for `rtt_measurement.py`.

**Concerns**
- **HIGH:** Task 1's union allowlist anchored at `v1.52` allows `rtt_backend.py` changes in Phase 240, and the reused protected-body helper does not protect `rtt_backend.py`; its protected set covers `rtt_measurement.py` and `wan_controller.py` only in `scripts/phase239-protected-body-diff.py:21`. That can false-pass phase-local drift outside "config/validator surface only."
- **MEDIUM:** Task 2's minimum test list is mostly static. It does not require the same negative coverage as the Phase 239 test: out-of-allowlist committed drift, dirty `src/wanctl` fail-close, and protected-body drift.
- **MEDIUM:** The verifier test can fail during normal execution if Plan 01 source edits are still uncommitted. The plan says run after Plan 01 is committed, but this ordering should be made explicit in the test/workflow.

**Suggestions**
- Prefer a Phase 240 start anchor or Phase 239 close commit for phase-local verification. If keeping `v1.52`, add a second check proving no new diff in `rtt_backend.py`/`rtt_measurement.py` relative to the Phase 239 close anchor.
- Add negative tests mirroring the 239 verifier: committed `wan_controller.py` drift fails, uncommitted `src/wanctl` edit fails, protected `rtt_measurement.py` body drift fails.
- Static-test both allowlist mechanisms: shell regex and embedded Python `disallowed_paths` set.
- Make the Plan 02 execution precondition explicit: Plan 01 committed, clean `src/wanctl`, then run boundary script.

**Risk Assessment**
**MEDIUM-HIGH.** The script structure is sound, but the `v1.52` union allowlist leaves a meaningful false-pass hole for phase-local RTT seam edits unless a second anchor/check closes it.

---

## Consensus Summary

Single reviewer (Codex) this cycle. Both HIGH concerns are concrete, actionable, and consistent with the milestone's stated constraints (CFG-03 no-migration + SAFE-17 no controller-path drift). No retrospective or quoted-prior HIGHs — both are newly raised and unresolved.

### Agreed Strengths
- Tight, additive edit set: validator + config registry + tests only; no controller-path behavior change.
- Correct choice to avoid `SCHEMA choices=` so an absent key stays silent and CFG-03 baseline holds.
- New phase-specific SAFE-17 verifier (not an edit of the Phase 239 machinery), preserving fail-closed dirty-tree and output-path guards.

### Agreed Concerns
- **HIGH (Plan 01):** Malformed `measurement` shapes (`measurement: fping`, `measurement: []`, `{backend: None}`, non-string backend) can silently resolve to `icmplib` instead of erroring — a silent default change that hides operator config errors. Distinguish "absent" (silent → icmplib) from "present-but-malformed" (ERROR).
- **HIGH (Plan 02):** `v1.52`-anchored union allowlist lets `rtt_backend.py` change in Phase 240 while the reused protected-body helper only protects `rtt_measurement.py` / `wan_controller.py` — a false-pass hole for phase-local RTT-seam drift. Add a Phase-239-close anchor or a second diff check.

### Divergent Views
None — single reviewer.
