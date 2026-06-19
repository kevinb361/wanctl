---
phase: 238-rtt-provenance-verification-read-only-entry-gate
plan: 04
subsystem: validation
tags: [rtt-provenance, prov-03, safe-17, egress-proof, read-only, gap-closure]

# Dependency graph
requires:
  - phase: 238-rtt-provenance-verification-read-only-entry-gate
    provides: Read-only egress proof script (Plan 02) and provenance map (Plan 03)
provides:
  - PROV-03 satisfied by corrected source-bound router-hop egress proof (both WANs PASS)
  - Corrected egress-proof criterion (host egress dev ens18 + distinct source-bound keys)
  - Refreshed SAFE-17 controller-path boundary evidence after gap closure
affects: [phase-241, phase-245, rtt-backend, fping-egress, live-ab]

# Tech tracking
tech-stack:
  added: []
  patterns: [topology-correct proof criterion, source-bound router-hop egress proof, plan-level criterion-error disclosure]

key-files:
  created:
    - .planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-04-SUMMARY.md
  modified:
    - scripts/phase238-egress-proof.sh
    - .planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/egress-proof-live-20260614T222118Z.json
    - .planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md
    - .planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/safe17-boundary-238.json

key-decisions:
  - "[238-04]: Corrected the PROV-03 criterion to the host-route topology — expected egress dev ens18 + distinct source-bound route keys — because spec-modem/att-modem are cake-autorate downstream ul_if labels that cannot appear in the shaper host's ip route get output."
  - "[238-04]: Disclosed the original non-pass as a plan-level criterion error (not topology drift) rather than hiding it; the provenance map records why the prior expected-dev labels were invalid."
  - "[238-04]: Scoped PROV-03 as a source-bound router-hop guarantee for Phase 245 — correct source IP + distinct route key, not a claim about named modem interfaces."

patterns-established:
  - "An egress proof for source-bound policy routing should assert host egress NIC + source-bound route-key distinctness, not downstream shaper interface labels."
  - "When a verification gap is a criterion error, fix the criterion and document the error in the evidence artifact instead of silently re-baselining."

requirements-completed: [PROV-03, SAFE-17]

# Metrics
duration: continuation
completed: 2026-06-15
---

# Phase 238 Plan 04: PROV-03 Gap Closure Summary

**Corrected the egress-proof criterion to the live host-route topology, re-ran the read-only proof (both WANs PASS), and refreshed SAFE-17 — closing the only open Phase 238 item.**

## Performance

- **Duration:** continuation
- **Completed:** 2026-06-15T11:31:32Z (corrected-criterion proof run)
- **Tasks:** 3 (1 auto pre-committed, 1 operator checkpoint, 1 auto)
- **Files modified:** 4

## Accomplishments

- Corrected `scripts/phase238-egress-proof.sh` so the PASS criterion is `src <wan-source> + dev ens18` plus distinct source-bound route keys, with `spec-modem`/`att-modem` documented as downstream `ul_if` context rather than expected host-route devs (Task 1, committed `4ebc72d0`).
- Operator re-ran the read-only proof against the live cake-shaper; both WANs returned top-level `PASS`, every reflector `pass:true`, `parsed_dev:"ens18"`, Spectrum source `10.10.110.223`, ATT source `10.10.110.227`, and `distinct_paths_check.pass:true` (Task 2).
- Replaced the evidence JSON with the passing run, updated `238-PROVENANCE-MAP.md` to mark PROV-03 satisfied and explain the criterion error, and refreshed SAFE-17 evidence (`passed:true`, zero controller-path diff) (Task 3).

## Task Commits

1. **Task 1: Correct PROV-03 criterion to current host-route topology** — `4ebc72d0` (fix)
2. **Task 2: Operator re-runs corrected PROV-03 proof** — operator-run read-only proof; JSON captured as evidence (no repo commit for the checkpoint input)
3. **Task 3: Commit passing evidence, update map, refresh SAFE-17** — this commit

## Files Created/Modified

- `scripts/phase238-egress-proof.sh` — Corrected expected host egress dev to `ens18`; updated header/usage/self-test fixtures; documented `spec-modem`/`att-modem` as downstream `ul_if` context (committed in Task 1).
- `.planning/.../evidence/egress-proof-live-20260614T222118Z.json` — Replaced with the passing corrected-criterion run (both WANs PASS).
- `.planning/.../238-PROVENANCE-MAP.md` — PROV-03 marked satisfied; corrected source-bound router-hop criterion and the prior criterion error documented; requirements row updated.
- `.planning/.../evidence/safe17-boundary-238.json` — Refreshed SAFE-17 boundary evidence, still `passed:true`.

## Verification

- `bash -n` and `--self-test` pass (corrected `ens18` fixtures + injection rejection).
- Evidence JSON asserts: both WANs PASS, every reflector `pass:true`/`parsed_dev:"ens18"`, ATT source `10.10.110.227`, Spectrum source `10.10.110.223`.
- Map contains `Satisfied by corrected read-only host-route evidence` and `source-bound router-hop`.
- SAFE-17 boundary check exits 0; evidence `passed:true`.
- `git status --porcelain -- src/wanctl/` empty (no controller-path drift).

## Decisions Made

- [238-04]: The root cause was a plan-level criterion error, not topology drift. `ip route get` on the shaper host always resolves egress `dev ens18`; WAN separation is by source IP + distinct source-bound route key. The `spec-modem`/`att-modem` labels are cake-autorate downstream `ul_if` values and were never valid host-route expected devs.
- [238-04]: PROV-03 is scoped for Phase 245 as a source-bound router-hop guarantee — `fping -S <source_ip>` egresses the intended WAN toward the router — not a claim about named modem interfaces.

## Deviations from Plan

None. Task 1's script fix was already committed (`4ebc72d0`) before this continuation; Tasks 2–3 executed as planned.

## Issues Encountered

- A markdown formatter hook reformatted `238-PROVENANCE-MAP.md` after edits; follow-up edits re-read the affected regions before applying.

## Known Stubs

None.

## Auth Gates

None.

## Threat Flags

None beyond the plan threat model. Live route output and internal IPs stayed inside the phase-dir evidence artifact; no public docs updated. Remote commands remained read-only `ip route get` / `ip rule` under the existing allowlist.

## User Setup Required

None.

## Next Phase Readiness

- PROV-03 closed: Phase 245 may treat source-bound `fping -S` egress as proven for both WANs (correct source IP + distinct route key on `ens18`).
- Phase 241's fping `-S` binding can rely on the verified per-WAN source IPs (Spectrum `10.10.110.223`, ATT `10.10.110.227`).
- Phase 238 is now fully complete (4/4 plans); ready for phase verification and Phase 239 (seam refactor).

## Self-Check: PASSED

- FOUND: `scripts/phase238-egress-proof.sh`
- FOUND: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/egress-proof-live-20260614T222118Z.json`
- FOUND: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md`
- FOUND: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/safe17-boundary-238.json`
- FOUND: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-04-SUMMARY.md`
- FOUND: `4ebc72d0`

---
*Phase: 238-rtt-provenance-verification-read-only-entry-gate*
*Completed: 2026-06-15*
