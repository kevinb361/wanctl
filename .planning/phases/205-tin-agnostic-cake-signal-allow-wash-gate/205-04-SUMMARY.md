---
phase: 205
plan: 04
status: complete
completed: 2026-05-14
---

# Phase 205 Closeout — Plan 04 SUMMARY

## Outcome Banner

PASS — SAFE-09 boundary scope matches the operator-approved 5-file set; value-invariance, deferral, replay, full-suite, hot-path, lint, and type gates are green.

## SAFE-09 Cross-Plan Boundary Diff Scope

Operator decision (Plan 00): **approve / Option B**.

Expected file set:

- `src/wanctl/cake_signal.py`
- `src/wanctl/cake_params.py`
- `src/wanctl/backends/linux_cake.py`
- `src/wanctl/backends/netlink_cake.py`
- `src/wanctl/check_config_validators.py`

Actual diff scope (verbatim `git diff 6508d68 --name-only -- src/wanctl/ | sort -u`):

```text
src/wanctl/backends/linux_cake.py
src/wanctl/backends/netlink_cake.py
src/wanctl/cake_params.py
src/wanctl/cake_signal.py
src/wanctl/check_config_validators.py
```

Match: ✓

Automated verifier:

```text
SAFE-09-scope=5-OK
```

## Value-Invariance Grep

Command: `git diff 6508d68 -- <5 files> | grep -E '^[+-]' | grep -viE '^(\+\+\+|---)' | grep -iE 'threshold|ewma|dwell|deadband|burst|time_constant|alpha|beta'`

Output: empty.

SAFE-09 (behavioral) verdict: ✓ no threshold / EWMA / dwell / deadband / burst / time-constant / alpha / beta numeric literal changes.

## Deferral Confirmation (Pitfall 5 + MEDIUM-5 Option B)

| Item | Expected | Actual | Status |
|------|----------|--------|--------|
| `_DIFFSERV_NAME_TO_INT` in `netlink_cake.py` diff | 0 | 0 | ✓ deferred to Phase 209 |
| `_VALIDATE_KEY_TO_TCA` in `netlink_cake.py` diff (Option B) | 0 | 0 | ✓ deferred to Phase 209 |
| `TCA_CAKE_WASH` in `netlink_cake.py` diff (Option B) | 0 | 0 | ✓ deferred to Phase 209 |
| `build_expected_readback` in `cake_params.py` diff (Option B) | 0 | 0 | ✓ deferred to Phase 209 |

## Test Results

| Suite | Result | Pass Count |
|-------|--------|------------|
| Full pytest (`.venv/bin/pytest tests/ -q --tb=short`) | ✓ green | 4995 passed, 6 skipped, 2 deselected |
| Phase 193/194/195 replay | ✓ green | 48 passed, 6 skipped |
| `TestCakeSignalProcessorDiffserv4ByteIdentity` (MEDIUM-4 hard gate) | ✓ green | 1 passed |
| Hot-path slice | ✓ green | 673 passed |
| Ruff on 5 changed files | ✓ clean | — |
| Mypy on 4 .py files | ✓ clean | — |

## Codex Review Resolution Status (final)

All 9 concerns from `205-REVIEWS.md` addressed:

- HIGH-1 (RED-test framing): Plan 01 split into RED-BEHAVIOR (Tasks 1+2) and GREEN-INVARIANT (Task 3 byte-identity + Task 4 audit). Each test color-tagged in acceptance.
- HIGH-2 (SAFE-09 ordering): Plan 00 operator gate landed amendment BEFORE source mutation. Branch chosen: approve / Option B.
- HIGH-3 (broken grep): Plan 02 acceptance replaced with positive (`_active_tin_indices` exists + applied) + negative (no `range(1, len(tins_raw))` literal) + total-invariant (`range(len(tins_raw))` count = 4 — covers total aggregation sites).
- MEDIUM-4 (byte-identity not pinned): `TestCakeSignalProcessorDiffserv4ByteIdentity` asserts literal numeric output; still green after Plan 02 and at closeout.
- MEDIUM-5 (readback gap): Operator chose Option B in Plan 00 — readback in Phase 209. Confirmed untouched in this plan.
- MEDIUM-6 (docsis fallback): `test_initialize_cake_emits_wash_under_docsis_fallback` (linux_cake) + `test_initialize_cake_falls_back_to_subprocess_for_docsis` (netlink_cake) green.
- MEDIUM-7 (wave-2 diff race): Plans 02 + 03 used file-scoped diffs. Plan 04 safely ran the cross-cutting check after both plans completed.
- LOW-8 (tin-name attribute): `self._tin_names` used in Plan 02 Q4 heuristic. `test_single_tin_name_label_is_besteffort` green.
- LOW-9 (oracle naming): `TestCakeSignalProcessorBestEffortStructuralOracle` uses an honest structural-oracle name and docstring.

## Phase 209 Carry-Forward Notes

Items deferred from Phase 205 that Phase 209 plan MUST address:

1. `_DIFFSERV_NAME_TO_INT["besteffort"] = 2 → 3` in `src/wanctl/backends/netlink_cake.py:62-66` (RESEARCH §"Pitfall 5"). Without this, Phase 209 canary log will show `WARN CAKE param mismatch on spec-router: diffserv expected=2 actual=3` once Spectrum flips.
2. `OPTIMAL_WASH` per-WAN auditor in `src/wanctl/check_cake.py:65-68` (RESEARCH §"Pitfall 6"). Spectrum DL with wash=yes will report "suboptimal" against the current `{"download": "no"}` expectation.
3. Add `wash` to `build_expected_readback()` at `src/wanctl/cake_params.py:176` so live qdisc readback can validate the new state.
4. Add `("wash", "TCA_CAKE_WASH")` to `_VALIDATE_KEY_TO_TCA` at `src/wanctl/backends/netlink_cake.py:69-78`.
5. ATT remains untouched (SAFE-08 invariant); Spectrum YAML flips to `920Mbit besteffort wash` + `allow_wash: true` later, in Phase 209.

## Plan Map

| Plan | Wave | Files | Status |
|------|------|-------|--------|
| 00 | 1 | ROADMAP + VALIDATION + REVIEWS | ✓ complete (operator gate) |
| 01 | 2 | 5 test files | ✓ complete (RED-BEHAVIOR + GREEN-INVARIANT) |
| 02 | 3 | `cake_signal.py` | ✓ complete (TOPO-01) |
| 03 | 3 | `cake_params.py` + 2 backends + `check_config_validators.py` | ✓ complete (TOPO-02) |
| 04 | 4 | SUMMARY + VALIDATION | ✓ complete |

## Deviations from Plan

None - plan executed as a read-only source audit plus the two planned planning-artifact updates.

## Known Stubs

None found. This plan produced verification artifacts only; no UI/data-source stubs were introduced.

## Threat Flags

None. No network endpoints, auth paths, file access patterns, or schema trust boundaries were introduced outside the plan threat model.

## Ready for /gsd-verify-work

Phase 205 closeout complete. Milestone can progress to Phase 206 (A/B replay harness + rollback gates).

## Self-Check: PASSED

- FOUND: `.planning/phases/205-tin-agnostic-cake-signal-allow-wash-gate/205-04-SUMMARY.md`
- FOUND: `.planning/phases/205-tin-agnostic-cake-signal-allow-wash-gate/205-VALIDATION.md`
- Source mutation sanity: `git diff HEAD -- src/wanctl/ | wc -l` returned `0` before Task 2 commit.
