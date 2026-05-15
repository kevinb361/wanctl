---
phase: 206-a-b-replay-harness-rollback-gates
verified: 2026-05-15T02:34:00Z
status: passed
score: "5/5 success criteria verified"
requirements: [TOPO-04, TOPO-05]
---

# Phase 206: A/B Replay Harness + Rollback Gates — Verification Report

**Phase Goal:** A deterministic A/B replay harness captures pre-migration controller behavior against the 2026-04-22 out-of-band flent finding (substituted with 2026-04-29 per Locked Decision D1), and rollback criteria are encoded as a machine-readable predeploy gate script that fails closed.

**Status:** passed  
**Re-verification:** No — initial verification (incorporates 2026-05-14 cross-AI review revisions)

## Success Criteria

| # | Criterion (ROADMAP wording) | Status | Evidence |
|---|------------------------------|--------|----------|
| 1 | A/B replay harness reuses Phase 193/194/195 pattern; ingests deterministic golden fixture; emits RRUL p99 latency, throughput, jitter for pre + post in one run. | ✓ VERIFIED | Plan 01: `tests/test_phase_206_replay.py::TestPattern193Reuse` (Phase 193 primitives imported); `tests/test_phase_206_replay.py::TestReplaySamplesConsumesAllRows` (C2 fix: per-row CAKE trace consumed); `scripts/phase206-ab-replay.py::_parse_flent_rrul` parses real flent .gz when `--flent-gz-pre/--flent-gz-post` supplied (C1 fix); schema-v1 JSON emitted with `meta.metric_source ∈ {flent, controller_replay}`. |
| 2 | A/B summary JSON schema stable enough for one-line consumer change. | ✓ VERIFIED | Schema v1 frozen top-level keys: `schema_version, phase, fixture_provenance, fixture_sha256, meta, pre, post, delta, gates`. Per-side controller-replay keys always present; flent keys added when flent inputs supplied. Asserted by `TestSchemaV1Stability`. |
| 3 | PHASE-205-ROLLBACK-GATES.md documents three rollback triggers in operator-readable form. | ✓ VERIFIED | Plan 03 deliverable. Three trigger sections; thresholds reference `scripts/phase206-thresholds.json` as source of truth (W5); inlined values verified byte-identical to JSON (drift check below). |
| 4 | Predeploy gate exits non-zero when any of three triggers breaches; operator dry-run on v1.43 baseline exits zero. | ✓ VERIFIED | `tests/test_phase206_predeploy_gate.py` — `TestGateDryRun` passes, three block cases trip rc=1, abort cases trip rc=2, four post-soak mode tests prove M5 full-enforcement, `gate_baseline` schema tests prove M6 separation. Baseline carries REAL v1.43 numerics (`transition_rate_per_hour_baseline: 77.17`, `restart_rate_per_hour_baseline: 0.0` with `_provenance`) per C4 fix. |
| 5 | SAFE-09 phase-boundary check: zero control-path source diff introduced. | ✓ VERIFIED | See "SAFE-09 Four-Surface Boundary Diff" section below (C3 fix). |

**Score:** 5/5 success criteria verified

## SAFE-09 Four-Surface Boundary Diff (codex C3)

The pre-revision draft used only `git diff 6508d68..HEAD --name-only -- src/wanctl/`, which excludes uncommitted and untracked changes. This revision verifies ALL FOUR git surfaces.

### Surface 1 — Committed diff vs `6508d68`

```text
$ git diff 6508d68 --name-only -- src/wanctl/ | sort -u
src/wanctl/backends/linux_cake.py
src/wanctl/backends/netlink_cake.py
src/wanctl/cake_params.py
src/wanctl/cake_signal.py
src/wanctl/check_config_validators.py

$ git diff 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l
5
```

### Surface 2 — Staged-but-not-committed diff

```text
$ git diff --cached 6508d68 --name-only -- src/wanctl/ | sort -u
src/wanctl/backends/linux_cake.py
src/wanctl/backends/netlink_cake.py
src/wanctl/cake_params.py
src/wanctl/cake_signal.py
src/wanctl/check_config_validators.py

$ git diff --cached 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l
5
```

### Surface 3 — Working-tree unstaged edits

```text
$ git diff --name-only -- src/wanctl/ | sort -u

$ git diff --name-only -- src/wanctl/ | sort -u | wc -l
0
```

### Surface 4 — Untracked files

```text
$ git ls-files --others --exclude-standard -- src/wanctl/ | sort -u

$ git ls-files --others --exclude-standard -- src/wanctl/ | wc -l
0
```

### Diagnostic: short status

```text
$ git status --short -- src/wanctl/

```

Expected union of surfaces 1+2+4 (Phase 205 allowlist, unchanged):

- `src/wanctl/backends/linux_cake.py`
- `src/wanctl/backends/netlink_cake.py`
- `src/wanctl/cake_params.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/check_config_validators.py`

Surfaces 3 (unstaged) and 4 (untracked) are both empty (wc -l = 0).

No new entries → Phase 206 introduced zero control-path source diff across all four git surfaces (SAFE-09 invariant holds even when including uncommitted state).

## Cross-Plan Threshold Drift Check (W5)

Thresholds live in `scripts/phase206-thresholds.json` (Plan 02 source of truth). Plan 03's doc inlines them for operator readability. Verified equal:

```text
$ .venv/bin/python -c "import json; print(json.dumps(json.load(open('scripts/phase206-thresholds.json')), indent=2))"
{
  "thresholds_schema_version": 1,
  "RRUL_P99_REGRESSION_PCT": 5.0,
  "RESTART_RATE_INCREASE_PCT": 10.0,
  "TRANSITION_RATE_INCREASE_PCT": 10.0,
  "_notes": "TOPO-05 single source of truth. PHASE-205-ROLLBACK-GATES.md (Plan 03) references this file; do not duplicate numeric literals in documentation."
}

$ .venv/bin/python3 <inline drift check>
threshold drift check OK
```

| Constant | JSON value | Doc inlined value | Drift |
|----------|------------|-------------------|-------|
| `RRUL_P99_REGRESSION_PCT` | 5.0 | 5.0 | none |
| `RESTART_RATE_INCREASE_PCT` | 10.0 | 10.0 | none |
| `TRANSITION_RATE_INCREASE_PCT` | 10.0 | 10.0 | none |

## Fixture SHA256 Pin

Committed NDJSON sha256 (from `sha256sum tests/fixtures/phase206_golden_capture.ndjson`):

```text
68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda  tests/fixtures/phase206_golden_capture.ndjson
```

Pinned in `.planning/phases/206-a-b-replay-harness-rollback-gates/golden-fixture-provenance.md`. Drift between the doc value and the live file would indicate the fixture changed without a documentation update — verified equal at verification time.

## Test Evidence

Full pytest suite:

```text
$ .venv/bin/pytest tests/ -q
5027 passed, 6 skipped, 2 deselected in 202.91s (0:03:22)
```

Hot-path slice (per CLAUDE.md):

```text
$ .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
673 passed in 40.84s
```

Phase 206 focused slice:

```text
$ .venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -v
tests/test_phase_206_replay.py::TestReplaySamplesConsumesAllRows::test_per_sample_helper_consumes_every_row PASSED [ 18%]
tests/test_phase206_ab_replay_cli.py::TestAbReplayCli::test_flent_gz_parsing PASSED [ 43%]
tests/test_phase206_predeploy_gate.py::TestGateDryRun::test_baseline_vs_self_passes PASSED [ 50%]
tests/test_phase206_predeploy_gate.py::TestPostSoakRequiresAll::test_post_soak_full_inputs_passes PASSED [ 93%]
tests/test_phase206_predeploy_gate.py::TestGateBaselineSchema::test_gate_baseline_required_fields_present PASSED [100%]

============================== 32 passed in 3.92s ==============================
```

## Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|-------------|--------------|--------|----------|
| TOPO-04 (A/B replay harness + deterministic golden fixture) | 206-01 | ✓ SATISFIED | Plan 01 SUMMARY + tests passing. C1 fix wires real flent parsing; C2 fix consumes per-row CAKE trace via `_replay_samples`. |
| TOPO-05 (Rollback criteria + predeploy gate script) | 206-02, 206-03 | ✓ SATISFIED | Plan 02 + Plan 03 SUMMARYs; gate tests passing; M5 post-soak full-enforcement; M6 `gate_baseline` schema separation; M7 SSH owned by wrapper; W5 thresholds JSON-sourced; doc-vs-JSON drift check above. |

## Anti-Patterns Found

None. Phase 206 is scripts/tests/docs only — no `src/wanctl/` edits across any of the four git surfaces, no controller threshold/algorithm changes, no `/health` field additions.

## Human Verification Required

None. Phase 206 is offline harness + docs; no deploy or visual behavior to verify.

## Gaps Summary

No blocking gaps. Phase 206 achieves its goal: a deterministic A/B replay harness exists (with real flent parsing as an option), three rollback triggers are documented and enforced (with full-enforcement post-soak mode), SAFE-09 invariant holds across all four git surfaces at the phase boundary.

Operator follow-up before Phase 209's production canary (not blocking for Phase 206 close):

- Refresh the golden fixture with a fresh capture per the re-derivation procedure in golden-fixture-provenance.md (optional; the 2026-04-29 capture is acceptable as the design-time deterministic fixture).
- Re-derive `restart_rate_per_hour_baseline` if the v1.43 reference soak's zero-restart assumption no longer holds for the live host being canaried.

---

_Verified: 2026-05-15T02:34:00Z_  
_Verifier: Plan 04 closeout task (mechanical, 2026-05-14 revision)_
