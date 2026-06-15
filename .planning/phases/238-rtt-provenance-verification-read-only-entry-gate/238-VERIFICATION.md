---
phase: 238-rtt-provenance-verification-read-only-entry-gate
verified: 2026-06-15T13:20:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 3/4
  gaps_closed:
    - "Operator can confirm via ip route get <reflector> from <source_ip> that fping -S <source_ip> egresses the intended WAN under current ip rule policy routing (PROV-03)."
  gaps_remaining: []
  regressions: []
---

# Phase 238: RTT-Provenance Verification (Read-Only Entry Gate) Verification Report

**Phase Goal:** The operator has a documented, evidence-backed map of which producer feeds live steering RTT in the current cake-autorate topology, and the A/B target interpretation is selected and committed — before any backend code exists.
**Verified:** 2026-06-15T13:20:00Z
**Status:** passed
**Re-verification:** Yes — after Plan 04 PROV-03 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Documented provenance map showing live steering RTT source (state bridge / autorate `/health` `measurement.raw_rtt_ms` vs wanctl `RTTMeasurement`), read-only, zero production mutation. (PROV-01) | ✓ VERIFIED | `238-PROVENANCE-MAP.md` maps live steering RTT to bridge `/health measurement.raw_rtt_ms`, documents `RTTMeasurement` as dead, embeds spectrum/ATT `/health` JSON, bridge SHA reconciliation, and zero-production-mutation statement. Regression-checked clean — unchanged by Plan 04 except the PROV-03 section. |
| 2 | A/B target interpretation (A = revive steering's own pinger; B = evaluate at autorate/bridge producer) selected and recorded with evidence. (PROV-02) | ✓ VERIFIED | Map presents both interpretations, recommends A on fidelity grounds, records operator-ratified `Selection: A`. Requirements table row PROV-02 "Satisfied by operator Selection: A". Regression-checked clean. |
| 3 | Operator can confirm via `ip route get <reflector> from <source_ip>` that `fping -S <source_ip>` egresses the intended WAN under current `ip rule` policy routing. (PROV-03) — **prior gap** | ✓ VERIFIED | **Gap closed.** Corrected-criterion live evidence `egress-proof-live-20260614T222118Z.json` records `verdict: PASS` for BOTH WANs, all 6 reflectors `pass:true`, `parsed_dev:"ens18"`, Spectrum src `10.10.110.223`, ATT src `10.10.110.227`, `distinct_paths_check.pass:true`, distinct source-bound egress keys. Independently parsed and asserted by verifier. Script `--self-test` PASS (corrected `ens18` fixtures + wrong-src/wrong-dev FAIL + injection REJECTED). |
| 4 | No source files changed; SAFE-17 boundary verifier passes (no controller-path drift). (SAFE-17) | ✓ VERIFIED | `phase238-safe17-boundary-check.sh` exits 0, `passed:true`, `controller_path_diff_count:0`. Verifier independently confirmed `git status --porcelain -- src/wanctl/` empty and `git diff --numstat v1.52 HEAD -- src/wanctl/` empty. |

**Score:** 4/4 truths verified

### Gap Closure Detail (Truth #3 / PROV-03)

**Root cause was a plan-level criterion error, not topology drift.** The original Plan 02 criterion expected host `ip route get` to resolve egress `dev spec-modem` / `dev att-modem`. Those are cake-autorate **downstream `ul_if` labels** from `configs/cake-autorate/config.{spectrum,att}.sh` — they live below the host route lookup and cannot appear as `ip route get` host devs. The shaper host always egresses `dev ens18` (the NIC toward the router); WAN separation is expressed by **source-bound route-key distinctness** (Spectrum src `10.10.110.223` vs ATT src `10.10.110.227`), which was always passing.

**Closure verified independently:**
- `scripts/phase238-egress-proof.sh` criterion corrected to `src <wan-source> + dev ens18` + distinct source-bound keys; `spec-modem`/`att-modem` documented as downstream `ul_if` context (commit `4ebc72d0`, confirmed present).
- Evidence JSON parsed and asserted by verifier: 2 WAN blocks, both top `verdict:PASS`, every reflector `pass:true`/`verdict:PASS`/`parsed_dev:ens18`, per-WAN expected source matched, distinct egress keys `10.10.110.223|ens18|10.10.110.1` ≠ `10.10.110.227|ens18|10.10.110.1`.
- Provenance map PROV-03 section rewritten to "Satisfied by corrected read-only host-route evidence"; criterion error documented; requirements table row updated.
- REQUIREMENTS.md PROV-03: checkbox `[x]` + traceability table "Complete".

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/phase238-egress-proof.sh` | Read-only both-WAN egress proof, corrected criterion | ✓ VERIFIED | `bash -n` OK; `--self-test` PASS with corrected `ens18` fixtures; criterion asserts `src + dev ens18` + distinct source-bound keys; `spec-modem`/`att-modem` documented as `ul_if` context. |
| `.../evidence/egress-proof-live-20260614T222118Z.json` | PROV-03 live PASS evidence | ✓ VERIFIED | Both WANs `verdict:PASS`; all reflectors `pass:true`/`parsed_dev:ens18`; correct per-WAN sources; `distinct_paths_check.pass:true`. No residual FAIL/non-pass language. |
| `scripts/phase238-safe17-boundary-check.sh` | Lightweight SAFE-17 read-only git assertion | ✓ VERIFIED | Exits 0; resolves anchor SHA; `--out` constrained to phase evidence dir. Rewrites only `checked_at`/`head_commit` on run (expected churn; restored via `git checkout`). |
| `.../evidence/safe17-boundary-238.json` | Final SAFE-17 evidence | ✓ VERIFIED | `passed:true`, `anchor:v1.52`, `controller_path_diff_count:0`, empty dirty tree, all protected controller paths clean. |
| `.../238-PROVENANCE-MAP.md` | Provenance + A/B target artifact | ✓ VERIFIED | Steering trace, live `/health` JSON with `raw_rtt_ms`, bridge SHA reconciliation, A/B interpretations, `Selection: A`, PROV-03 marked satisfied with criterion-error disclosure, requirements table all four rows Satisfied. |
| `.../238-04-SUMMARY.md` | Gap-closure summary | ✓ VERIFIED | Documents criterion correction, both-WAN PASS, SAFE-17 refresh, `requirements-completed: [PROV-03, SAFE-17]`. |
| `.../238-REVIEW.md` | Code review artifact | ✓ VERIFIED | Carried forward; `status: clean`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `phase238-egress-proof.sh` verdict logic | per-WAN source-bound egress | `verdict_for_line` matches `src==expected_src AND dev==expected_dev` | ✓ WIRED | Self-test proves PASS on correct src+ens18, FAIL on wrong-src and wrong-dev (`att-modem`), injection REJECTED. |
| `phase238-safe17-boundary-check.sh` | `v1.52` tag / controller paths | resolved anchor SHA + `git diff --numstat` | ✓ WIRED | Exit 0, zero controller-path diff; verifier independently reproduced empty numstat + porcelain. |
| `238-PROVENANCE-MAP.md` A/B section | Phase 245 live A/B target | operator `Selection: A` | ✓ WIRED | `Selection: A` recorded; Phase 245 runs on the Phase-238-selected target. |
| PROV-03 evidence | Phase 241/245 source-bound `fping -S` | verified per-WAN source IPs | ✓ WIRED | Source IPs `10.10.110.223` / `10.10.110.227` proven distinct and source-bound; downstream phases may rely on source-bound router-hop guarantee. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Egress script parses | `bash -n scripts/phase238-egress-proof.sh` | exit 0 | ✓ PASS |
| Egress self-test (corrected) | `scripts/phase238-egress-proof.sh --self-test` | PASS incl. ens18 src/from-only PASS, wrong-src/wrong-dev FAIL, 3 injection REJECTED | ✓ PASS |
| Evidence JSON assertions | verifier python parse/assert | 2 WANs PASS, 6 reflectors pass, ens18, correct sources, distinct keys | ✓ PASS |
| SAFE-17 boundary check | `scripts/phase238-safe17-boundary-check.sh` | exit 0, `passed:true`, 0 controller diff | ✓ PASS |
| Controller-path drift | `git status --porcelain -- src/wanctl/` + `git diff --numstat v1.52 HEAD -- src/wanctl/` | both empty | ✓ PASS |
| Gap-closure commit present | `git log --oneline 4ebc72d0` | `fix(238-04): correct egress proof topology criterion` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan / Summary | Description | Status | Evidence |
|---|---|---|---|---|
| PROV-01 | Plan 03 / Summary 03 | Documented map of live steering RTT producer, read-only, no prod mutation | ✓ SATISFIED | Map maps steering to bridge `/health measurement.raw_rtt_ms`; REQUIREMENTS.md `[x]` Complete. |
| PROV-02 | Plan 03 / Summary 03 | A/B target selected and recorded with evidence | ✓ SATISFIED | `Selection: A` ratified; REQUIREMENTS.md `[x]` Complete. |
| PROV-03 | Plan 02 (criterion) + Plan 04 (closure) | Confirm `fping -S <source_ip>` egresses intended WAN under policy routing | ✓ SATISFIED | Corrected source-bound router-hop proof, both WANs PASS on `ens18` with distinct keys; REQUIREMENTS.md `[x]` Complete; traceability "Complete". |
| SAFE-17 | Plans 01/03/04 | Lightweight boundary proof, no controller-path drift (Phase 238 scope per D-09) | ✓ SATISFIED | `safe17-boundary-238.json` `passed:true`, zero diff; refreshed after Plan 04. Full fail-closed verifier remains Phase 239 by D-09. |

**Orphaned requirement check:** ROADMAP Phase 238 lists PROV-01, PROV-02, PROV-03, SAFE-17. All four declared in plan frontmatter and verified above. None orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| — | — | No debt markers (TBD/FIXME/XXX) in modified scripts | ℹ️ Info | Prior stale "SAFE-17 pending" map row and "FAIL/non-pass" evidence language are gone — both resolved by Plan 04. |

### Human Verification Required

None. The operator checkpoints (live read-only proof re-run on the cake-shaper, `Selection: A` ratification) already occurred and are captured as committed/staged evidence. The corrected PROV-03 result is a determinate PASS, independently re-asserted by the verifier from the evidence artifact and the script self-test. No visual/real-time/external-service uncertainty remains.

### Gaps Summary

No gaps. The sole prior gap (Truth #3 / PROV-03) is closed and independently verified:

- The non-pass was a plan-level criterion error (expected downstream `ul_if` modem labels as host route devs), not topology drift. The corrected criterion — per-WAN source IP + host egress `dev ens18` + distinct source-bound route keys — matches the real WAN-separation invariant.
- Live evidence now records both WANs PASS, all reflectors pass on `ens18`, correct distinct sources; verifier-parsed and asserted.
- The criterion correction is committed (`4ebc72d0`), the script self-test passes, the provenance map and REQUIREMENTS.md are updated to Complete, and SAFE-17 still passes with zero controller-path drift.

Phase goal achieved: documented evidence-backed provenance map exists, A/B target selected (`A`) and recorded, source-bound egress proven read-only, and zero production/controller mutation — all before any backend code. Ready to proceed to Phase 239.

**Note for committer:** `.planning/REQUIREMENTS.md` and `238-PROVENANCE-MAP.md` are modified in the working tree (the gap-closure doc updates) and not yet committed. This VERIFICATION.md is left staged for the main session to bundle and commit.

---

_Verified: 2026-06-15T13:20:00Z_
_Verifier: Claude (gsd-verifier) — re-verification after Plan 04 gap closure_
