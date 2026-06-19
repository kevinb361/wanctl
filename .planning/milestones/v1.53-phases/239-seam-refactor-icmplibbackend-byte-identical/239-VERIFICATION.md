---
phase: 239-seam-refactor-icmplibbackend-byte-identical
verified: 2026-06-16T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 12/12
  note: >-
    Prior report (2026-06-15T17:30:54Z) was produced at HEAD ff787d43 (the 239
    boundary). This backfill re-derives the 5 authoritative ROADMAP success
    criteria against current HEAD fcc2e15b, after Phase 242 landed on top.
  gaps_closed: []
  gaps_remaining: []
  regressions: []
deferred:
  - truth: >-
      The Phase 239 narrow SAFE-17 verifier (2-file allowlist) no longer passes
      against current HEAD; `WANController.measure_rtt` and `__init__` have
      drifted from v1.52, and wan_controller.py + 9 other files are now
      out-of-allowlist relative to the 239 boundary.
    addressed_in: "Phase 242"
    evidence: >-
      git blame attributes the measure_rtt/init drift to Phase 242 commits
      b58403c1/a640e778/a2512810/4e606540 (factory wiring + fping scorer skip).
      Phase 242 expands the SAFE-17 allowlist to include wan_controller.py and
      its boundary evidence evidence/safe17-boundary-242.json records
      passed:true with disallowed_paths:[]. The 239 verifier failing at HEAD is
      the 242 boundary surfacing, not a 239 deliverable regression. The 239
      seam files themselves (rtt_backend.py byte-identical to 239-01; the 7
      icmplib protected bodies in rtt_measurement.py identical to v1.52) are
      intact, and Phase 239's own boundary evidence (safe17-boundary-239.json,
      passed:true at commit ff787d43) remains valid.
---

# Phase 239: Seam Refactor + IcmplibBackend (Byte-Identical) Verification Report

**Phase Goal:** A single `RttBackend` abstraction exists with the existing icmplib measurement refactored behind it, provably behavior-identical to the pre-refactor default so any later regression is unambiguously attributable to a backend, not the seam.
**Verified:** 2026-06-16 (backfill against HEAD fcc2e15b)
**Status:** passed
**Re-verification:** Yes — backfill re-derive of ROADMAP success criteria against current HEAD (prior report was at the 239 boundary HEAD ff787d43)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — authoritative)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A single `RttBackend` Protocol is consumed by both steering and autorate, with the existing icmplib path refactored behind it (no second silo introduced). | ✓ VERIFIED | One `@runtime_checkable class RttBackend(Protocol)` at `src/wanctl/rtt_backend.py:19-33` with `probe(hosts) -> "RttSample \| None"`. `RTTMeasurement.probe()` (`src/wanctl/rtt_measurement.py:325-359`) makes the existing icmplib class structurally conform — no parallel `IcmplibBackend` silo. The single seam is consumed via `rtt_backend_factory.py:34,94` (`backend: RttBackend`), which both autorate (`autorate_continuous.py:38` imports `build_rtt_backend`) and steering use through the shared factory landed in Phase 242. At the 239 boundary the conformance was structural; the factory consumer wiring is the natural downstream consumption of the same single protocol — no second silo at any point. |
| 2 | icmplib-default RTT behavior is byte-identical to pre-refactor, proven by the hot-path test slice plus snapshot equivalence. | ✓ VERIFIED | `scripts/phase239-protected-body-diff.py --anchor v1.52` reports all 7 icmplib protected bodies identical to v1.52: `RTTSnapshot`, `RTTMeasurement.__init__`, `ping_host`, `_aggregate_rtts`, `ping_hosts_with_results`, `BackgroundRTTThread._run`, `_ping_with_persistent_pool` (PASS each). `rtt_backend.py` is byte-identical to its 239-01 commit (`git diff 1df1aeb4 HEAD` empty). Snapshot-equivalence test `tests/test_rtt_backend.py` asserts `RttSample.to_snapshot()` equals a hand-built `RTTSnapshot`. Hot-path slice (`tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py`) ran clean: **678 passed**. (The verifier's 8th protected node, `WANController.measure_rtt`, now shows drift — attributed to Phase 242, see Deferred.) |
| 3 | RTT samples carry backend / source-IP / loss metadata (`RttSample` as a strict superset of `RTTSnapshot`) without breaking `WANController.measure_rtt()`, the scorer, or other existing consumers. | ✓ VERIFIED | `RttSample` (`rtt_backend.py:36-54`, frozen+slots) — first six fields (`rtt_ms, per_host_results, timestamp, measurement_ms, active_hosts, successful_hosts`) match `RTTSnapshot` (`rtt_measurement.py:101-106`) in order and type, then adds `backend`, `source_ip`, `per_host_loss` (documented 0.0–100.0 percent). `BackgroundRTTThread` still publishes `RTTSnapshot`, not `RttSample`. `measure_rtt` and the reflector scorer remain functional — `test_wan_controller.py` is part of the 678-pass hot-path slice; the scorer `record_results` consumer (`wan_controller.py:1196+`) still operates on `snapshot.per_host_results`. |
| 4 | The abstraction is shaped to absorb the existing IRTT path (adapter seam present), with full IRTT migration explicitly deferred. | ✓ VERIFIED | Pure mapper `sample_from_irtt_result(IRTTResult) -> RttSample` at `rtt_backend.py:70-91` (loss = max(send, receive), no I/O). `IrttRttBackend.probe()` at `rtt_backend.py:94-99` intentionally `raise NotImplementedError("IRTT-MIG-01")` — adapter seam present, live migration deferred. Covered by `tests/test_rtt_backend.py`. |
| 5 | The narrowed SAFE-17 allowlist is defined and the fail-closed source-diff verifier runs at the phase boundary, proving no out-of-allowlist controller-path drift. | ✓ VERIFIED (at 239 boundary) | `scripts/phase239-safe17-boundary-check.sh:15` defines the narrowed allowlist `V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py\|rtt_measurement\.py)$'`, fails closed on out-of-allowlist paths (`:224-227`), invokes the AST protected-body helper, and emits evidence. Phase-boundary evidence `evidence/safe17-boundary-239.json`: `passed:true`, `all_identical:true`, `allowed_shape_ok:true`, `changed_paths` = only the two seam files, `disallowed_paths:[]`, `added_qualnames:["RTTMeasurement.probe"]`, anchored at v1.52 (`anchor_sha 69f39db1…`, matches the annotated-tag deref), head_commit `ff787d43` (the 239 boundary). The verifier rerun at *current* HEAD reports drift — that is Phase 242 surfacing, see Deferred items. |

**Score:** 5/5 truths verified

### Deferred Items

Items observed at current HEAD that are owned by a later milestone phase, not Phase 239 deliverables.

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | `phase239-safe17-boundary-check.sh` fails at HEAD; `WANController.measure_rtt`/`__init__` drift from v1.52; wan_controller.py + 9 files out-of-allowlist vs the 239 narrow allowlist. `tests/test_phase239_safe17_verifier.py::test_verifier_passes_at_boundary` fails for the same reason. | Phase 242 | Drift attributed to Phase 242 commits (`b58403c1` factory fallback, `a640e778` wire call sites, `a2512810` fallback health signal, `4e606540` skip fping scorer). Phase 242's allowlist expands to include `wan_controller.py` (+9); `evidence/safe17-boundary-242.json` records `passed:true`, `disallowed_paths:[]`. Phase 239's own seam files are intact (rtt_backend.py byte-identical to 239-01; 7 icmplib protected bodies identical to v1.52), and 239's own boundary evidence at commit ff787d43 is valid. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/wanctl/rtt_backend.py` | `RttBackend` Protocol, `RttSample` superset, IRTT mapper, deferred adapter | ✓ VERIFIED | 99 lines; protocol (`:19-33`), frozen+slots sample (`:36-54`), `to_snapshot()` (`:56-67`), `sample_from_irtt_result()` (`:70-91`), `IrttRttBackend` raising IRTT-MIG-01 (`:94-99`). Byte-identical to 239-01 commit. |
| `src/wanctl/rtt_measurement.py` | Additive `RTTMeasurement.probe()`; legacy bodies untouched | ✓ VERIFIED | `probe()` `:325-359`, local `RttSample` import `:326`, returns `None` on zero success `:338-339`. 7 icmplib protected bodies identical to v1.52. |
| `scripts/phase239-protected-body-diff.py` | AST protected-body + allowed-shape verifier | ✓ VERIFIED | Run at HEAD: 7 icmplib bodies PASS, allowed-shape PASS (`added_qualnames:["RTTMeasurement.probe"]`). 8th node (`measure_rtt`) FAIL — Phase 242 drift (deferred). |
| `scripts/phase239-safe17-boundary-check.sh` | Fail-closed narrowed-allowlist boundary verifier | ✓ VERIFIED | Narrow 2-file allowlist (`:15`), fail-closed on disallowed paths (`:224-227`), v1.52 anchor, helper gate before evidence. |
| `tests/test_rtt_backend.py` | Conformance/superset/snapshot/IRTT/import tests | ✓ VERIFIED | Pass within the seam test run (part of 80 passed). |
| `tests/test_rtt_measurement.py` | probe empty/all-fail/partial/aggregation/source/import tests | ✓ VERIFIED | Pass within the seam test run. |
| `tests/test_phase239_safe17_verifier.py` | Positive/negative verifier tests | ⚠️ 7/8 PASS | `test_verifier_passes_at_boundary` FAILS at HEAD because Phase 242 changes are out-of-239-allowlist (deferred — see below). 7 negative/fail-closed tests pass. |
| `evidence/safe17-boundary-239.json` | Phase-boundary SAFE-17 evidence | ✓ VERIFIED | `passed:true`, `all_identical:true`, only 2 seam files changed, `disallowed_paths:[]`, head_commit ff787d43 (the 239 boundary). |
| `239-REVIEW.md` | Clean code-review artifact | ✓ VERIFIED | `findings.critical:0`; 7 files reviewed. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `RttSample.to_snapshot()` | `RTTSnapshot` | Local runtime import | ✓ WIRED | `rtt_backend.py:58` imports inside method; snapshot-equality test passes. |
| `RTTMeasurement.probe()` | `RttSample` | Local runtime import | ✓ WIRED | `rtt_measurement.py:326` local import; quoted return annotation keeps module acyclic. |
| `RttBackend` protocol | `rtt_backend_factory` | `backend: RttBackend` | ✓ WIRED | `rtt_backend_factory.py:34,94` — single protocol consumed by the shared factory used by both autorate and steering. No second silo. |
| `phase239-safe17-boundary-check.sh` | `phase239-protected-body-diff.py` | SCRIPT_DIR helper invocation | ✓ WIRED | Shell gates evidence pass on helper JSON. |
| 239 SAFE-17 verifier | v1.52 anchor | annotated-tag deref | ✓ WIRED | `v1.52` (tag) → `69f39db1…`, matching evidence anchor_sha. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| icmplib protected bodies identical to v1.52 | `.venv/bin/python scripts/phase239-protected-body-diff.py --anchor v1.52 --json` | 7 icmplib bodies PASS + allowed-shape PASS; `measure_rtt` FAIL (Phase 242 drift, deferred); exit 1 | ✓ PASS (239 scope) |
| Seam + measurement + verifier-negative tests | `.venv/bin/pytest -o addopts='' tests/test_rtt_backend.py tests/test_rtt_measurement.py tests/test_phase239_safe17_verifier.py -q` | 80 passed, 1 failed (`test_verifier_passes_at_boundary` — Phase 242 deferred) | ✓ PASS (239 scope) |
| Hot-path byte-identity slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | 678 passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| SEAM-01 | 239-01, 239-02 | Single `RttBackend` consumed by steering+autorate; icmplib behind it | ✓ SATISFIED | One protocol; `RTTMeasurement.probe()` conforms; factory consumes the single protocol; no second silo. |
| SEAM-02 | 239-01, 239-02 | icmplib-default byte-identical | ✓ SATISFIED | 7 icmplib bodies identical to v1.52; snapshot-equality; 678-pass hot-path slice. |
| SEAM-03 | 239-01 | `RttSample` strict superset, no consumer break | ✓ SATISFIED | Field-order superset; `BackgroundRTTThread` still emits `RTTSnapshot`; scorer/measure_rtt still pass. |
| SEAM-04 | 239-01 | IRTT adapter seam, migration deferred | ✓ SATISFIED | `sample_from_irtt_result()` + `IrttRttBackend` raising IRTT-MIG-01. |
| SAFE-17 | 239-03 | Fail-closed narrowed-allowlist boundary verifier + evidence | ✓ SATISFIED (at 239 boundary) | Narrow 2-file allowlist verifier + `safe17-boundary-239.json` passed:true at commit ff787d43. Later drift owned by Phase 242 (its allowlist + evidence). |

**Orphaned requirement check:** ROADMAP Phase 239 lists SEAM-01..04 + SAFE-17. All five present in plan frontmatter and verified. None orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/wanctl/rtt_backend.py` | 99 | `IrttRttBackend.probe()` raises `NotImplementedError("IRTT-MIG-01")` | ℹ️ Info | Intentional deferred-migration seam (SEAM-04). Marker references formal follow-up ID `IRTT-MIG-01` — not an unreferenced debt marker. Not a blocker. |

### Human Verification Required

None. Phase 239 is offline/code-verifier scoped; all truths are deterministically checkable via source inspection, AST protected-body diff vs v1.52, JSON evidence, and the test slices run above. No visual, live-network, or external-service behavior required.

### Gaps Summary

No gaps against Phase 239's deliverable. The single `RttBackend` protocol exists with icmplib refactored behind it via the additive `RTTMeasurement.probe()`; the 7 icmplib hot-path bodies are byte-identical to v1.52 and `rtt_backend.py` is byte-identical to its 239-01 commit; `RttSample` is a strict superset with backend/source/loss metadata while `BackgroundRTTThread` keeps publishing `RTTSnapshot`; the IRTT adapter seam is present and explicitly deferred; and the narrowed fail-closed SAFE-17 verifier produced passing phase-boundary evidence at the 239 commit.

The only at-HEAD anomaly — the 239 SAFE-17 verifier and `test_verifier_passes_at_boundary` now failing because `WANController.measure_rtt`/`__init__` (and 10 files total) are out-of-allowlist vs the 239 narrow allowlist — is fully attributable to Phase 242 (factory wiring + fping scorer skip), which intentionally expands the allowlist and carries its own passing boundary evidence (`safe17-boundary-242.json`, passed:true). This is later-phase progression, not a Phase 239 regression, and is recorded as a deferred item rather than a gap.

---

_Verified: 2026-06-16 (backfill)_
_Verifier: Claude (gsd-verifier)_
