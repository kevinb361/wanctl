---
phase: 238-rtt-provenance-verification-read-only-entry-gate
plan: 02
subsystem: validation
tags: [rtt-provenance, fping, policy-routing, read-only, egress-proof, non-pass-evidence]

# Dependency graph
requires:
  - phase: 238-rtt-provenance-verification-read-only-entry-gate
    provides: SAFE-17 boundary proof from Plan 01
provides:
  - Read-only both-WAN egress proof script for future fping source-IP validation
  - Operator-provided live egress-proof stdout captured as non-pass topology-drift evidence
  - Parser hardening for Linux source-bound `ip route get ... from <source>` output without a separate `src` token
affects: [phase-238, phase-245, PROV-03, rtt-provenance, fping-egress]

# Tech tracking
tech-stack:
  added: []
  patterns: [read-only SSH command allowlist, shared remote-command generator, non-pass live evidence artifact]

key-files:
  created:
    - .planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/egress-proof-live-20260614T222118Z.json
    - .planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-02-SUMMARY.md
  modified:
    - scripts/phase238-egress-proof.sh
    - .claude/context.md

key-decisions:
  - "[238-02]: Treated the operator capture as valid non-pass evidence because the live host resolved both WAN proofs on dev ens18 instead of the repo-derived spec-modem/att-modem uplinks; the plan explicitly says non-zero verdicts surface drift rather than being overridden."
  - "[238-02]: Fixed the proof parser to treat `from <source>` as source-bound evidence when Linux omits a separate `src <source>` token, while preserving the dev mismatch as a real FAIL."

patterns-established:
  - "Live routing evidence can be committed as a non-pass artifact when it falsifies a plan assumption; do not force expected topology labels onto actual kernel route output."
  - "For `ip route get <dst> from <source>`, parse `from` as the source fallback when `src` is omitted."

requirements-completed: []

# Metrics
duration: 3min continuation
completed: 2026-06-14
---

# Phase 238 Plan 02: Both-WAN Egress Proof Summary

**Read-only fping egress proof captured a real non-pass topology result: both WAN route queries resolved on `dev ens18`, not the repo-derived `spec-modem` / `att-modem` uplinks**

## Performance

- **Duration:** 3 min continuation
- **Started:** 2026-06-14T22:22:59Z
- **Completed:** 2026-06-14T22:25:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Verified the prior Task 1 commit exists: `51cc3ac9` authored `scripts/phase238-egress-proof.sh` and updated `.claude/context.md`.
- Consumed the operator-provided live read-only stdout from `scripts/phase238-egress-proof.sh --json` and preserved it verbatim in `evidence/egress-proof-live-20260614T222118Z.json`.
- Diagnosed the output instead of treating it as success: distinctness passed, but both WANs failed the mechanical expected-dev criteria because live `ip route get` resolved `dev ens18` for Spectrum and ATT.
- Fixed one script false-fail component: ATT source-bound route output may include `from 10.10.110.227` without a separate `src` token, so the parser now treats `from` as the parsed source fallback. The live evidence still fails due the egress-dev mismatch.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author phase238-egress-proof.sh** - `51cc3ac9` (feat)
2. **Task 2 continuation fix: Parse source-bound route output** - `f498979e` (fix)
3. **Task 2: Capture operator non-pass evidence** - `7b9787df` (test)

## Files Created/Modified

- `scripts/phase238-egress-proof.sh` - Read-only both-WAN route proof; parser now handles source-bound `from` output.
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/egress-proof-live-20260614T222118Z.json` - Operator-provided live stdout showing both-WAN FAIL verdicts.
- `.claude/context.md` - Project-local validation note updated for parser behavior and non-pass evidence location.
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-02-SUMMARY.md` - This completion/non-pass evidence record.

## Live Evidence Result

The captured stdout is a valid evidence artifact, but it does **not** satisfy the original PASS acceptance criteria.

| WAN | Expected src | Expected dev | Observed source evidence | Observed dev | Distinct path | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| spectrum | `10.10.110.223` | `spec-modem` | `src 10.10.110.223` | `ens18` | yes | FAIL |
| att | `10.10.110.227` | `att-modem` | query/output `from 10.10.110.227` | `ens18` | yes | FAIL |

The `ip rule` table was also captured and contains only `local`, `main`, and `default` rules. This disproves the plan assumption that the live cake-shaper route proof would show repo-derived uplink interface names (`spec-modem` / `att-modem`) in kernel route output.

## Decisions Made

- [238-02]: Treated the operator capture as a non-pass evidence artifact, not a failed execution to paper over. The plan explicitly states that a non-zero verdict caused by live egress dev/src drift is real drift to surface in Plan 03.
- [238-02]: Did not run additional live network reads or mutate routing/service state. The only live data used was the operator-provided read-only stdout.
- [238-02]: Did not mark `PROV-03` complete because the captured verdict does not confirm the planned expected-dev criteria.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Accepted source-bound `from` output as parsed source fallback**
- **Found during:** Task 2 (Operator runs the egress proof)
- **Issue:** Linux `ip route get <dst> from 10.10.110.227` can print `from 10.10.110.227` without a separate `src 10.10.110.227` token. The script recorded `parsed_src: null`, making the ATT source check noisier than the actual kernel output warranted.
- **Fix:** Updated `verdict_for_line` to use `after("src") or after("from")` and added a no-network self-test fixture for the from-only ATT pass shape.
- **Files modified:** `scripts/phase238-egress-proof.sh`, `.claude/context.md`
- **Verification:** `bash -n scripts/phase238-egress-proof.sh`; `scripts/phase238-egress-proof.sh --self-test`; `scripts/phase238-egress-proof.sh --print-commands`
- **Committed in:** `f498979e`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** The parser fix removes a false source-parsing failure mode. It does not convert the live evidence to PASS; both WANs still fail the expected-dev criterion because the observed dev is `ens18`.

## Issues Encountered

- The operator capture does not meet the plan's PASS criteria. This is recorded as an intended non-pass evidence artifact because the plan explicitly says live egress drift should be surfaced rather than overridden.
- The repository pre-commit hook required `.claude/context.md` documentation updates for the script/evidence commits; hooks passed after real documentation updates, with no hook bypass.

## Known Stubs

None introduced by this plan. Existing unrelated `placeholder` wording in older `.claude/context.md` notes predates this work and is not part of the Phase 238 Plan 02 deliverable.

## Threat Flags

None beyond the plan threat model. The script continues to use the shared generator plus full-line allowlist before live SSH; no new network mutation surface was introduced.

## User Setup Required

None for this plan. If Plan 03 needs a passing PROV-03 proof rather than a drift artifact, it should first decide whether the expected-dev criterion should be updated for the actual live host route-output topology or whether the live topology/config should be reconciled outside this read-only phase.

## Next Phase Readiness

- Plan 03 can embed `evidence/egress-proof-live-20260614T222118Z.json` as the PROV-03 evidence, but it must label it **non-pass/topology-drift**, not a successful egress proof.
- Downstream Phase 245 should not assume `fping -S` egress is proven on `spec-modem` / `att-modem` until this mismatch is resolved or the proof criterion is reinterpreted with evidence.

## Self-Check: PASSED

- FOUND: `scripts/phase238-egress-proof.sh`
- FOUND: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/egress-proof-live-20260614T222118Z.json`
- FOUND: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-02-SUMMARY.md`
- FOUND: `51cc3ac9`
- FOUND: `f498979e`
- FOUND: `7b9787df`

---
*Phase: 238-rtt-provenance-verification-read-only-entry-gate*
*Completed: 2026-06-14*
