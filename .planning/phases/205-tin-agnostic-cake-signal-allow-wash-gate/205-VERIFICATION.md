---
phase: 205-tin-agnostic-cake-signal-allow-wash-gate
verified: 2026-05-14T18:55:04Z
status: passed
score: "4/4 must-haves verified"
overrides_applied: 0
---

# Phase 205: Tin-agnostic CAKE signal + allow_wash gate Verification Report

**Phase Goal:** The controller can ingest both single-tin besteffort and multi-tin diffserv4 CAKE state without per-deployment branching, and the qdisc args list can include `wash` only when an explicit per-WAN config gate is set.
**Verified:** 2026-05-14T18:55:04Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `src/wanctl/cake_signal.py` aggregation iterates over the actual tin set and preserves ATT multi-tin diffserv4 output. | ✓ VERIFIED | `_active_tin_indices(tin_count)` exists at `src/wanctl/cake_signal.py:66-86`; cold-start and steady-state active aggregation use helper-derived `active_indices` at lines 287 and 340. All-tin total iterations remain `range(len(tins_raw))` at lines 283, 331, 342, 374. Focused tests passed, including `TestCakeSignalProcessorDiffserv4ByteIdentity`. SAFE-09 keyword diff scan returned empty. |
| 2 | A replay/structural oracle exercises single-tin besteffort CAKE state and matches the diffserv4 oracle for the same load profile. | ✓ VERIFIED | `tests/test_cake_signal.py:429-512` contains single-tin besteffort tests and `TestCakeSignalProcessorBestEffortStructuralOracle`. The test uses synthesized one-tin CAKE stats, not a real captured router fixture; this matches the research recommendation and plan wording after review. Focused pytest passed: 15 tests passed. |
| 3 | `cake_params.allow_wash` defaults false; false/absent excludes wash; true allows wash; `nat` and `autorate-ingress` remain rejected. | ✓ VERIFIED | `src/wanctl/cake_params.py:149-172` extracts `allow_wash` with strict `is True`, strips it from tc params, permits only `wash` under the gate, and leaves `EXCLUDED_PARAMS = {"nat", "wash", "autorate-ingress"}` unchanged at line 60. `tests/test_cake_params.py:205-232` covers true/false/absent/nat/autorate-ingress. Direct spot-check passed. |
| 4 | SAFE-09 phase boundary: source diff is bounded to the approved 5-file set; no threshold/EWMA/dwell/deadband/burst value changes; wash readback remains deferred. | ✓ VERIFIED | `git diff 6508d68 --name-only -- src/wanctl/ | sort -u` returned exactly `linux_cake.py`, `netlink_cake.py`, `cake_params.py`, `cake_signal.py`, `check_config_validators.py`. SAFE-09 keyword diff scan returned empty. `build_expected_readback()` remains without wash at `cake_params.py:191-236`; `_VALIDATE_KEY_TO_TCA` has no wash/TCA_CAKE_WASH at `netlink_cake.py:69-78`, matching Phase 205 emission-only scope. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/cake_signal.py` | Tin-agnostic active aggregation helper; total aggregation untouched; single-tin BestEffort label. | ✓ VERIFIED | Exists and substantive. Helper wired into `CakeSignalProcessor.update`; controller wires processor at `wan_controller.py:813-826` and updates snapshots at `wan_controller.py:2807-2820`. |
| `src/wanctl/cake_params.py` | Strict-bool `allow_wash` gate in `build_cake_params`. | ✓ VERIFIED | Exists and substantive. `build_cake_params` is imported and used by `linux_cake_adapter.py:323-327`; params are passed to `backend.initialize_cake()` at line 336. |
| `src/wanctl/backends/linux_cake.py` | Emits `wash` and `nowash` subprocess tokens. | ✓ VERIFIED | Boolean loop includes `wash` at lines 396-402; docsis fallback path from netlink delegates here. |
| `src/wanctl/backends/netlink_cake.py` | Passes `wash` kwarg on non-docsis pyroute2 path; docsis fallback untouched. | ✓ VERIFIED | Kwarg mapping includes `("wash", "wash")` at line 483; docsis `overhead_keyword` fallback returns `super().initialize_cake(params)` at line 448. |
| `src/wanctl/check_config_validators.py` | Recognizes `cake_params.allow_wash` and `cake_params.wash`. | ✓ VERIFIED | `KNOWN_AUTORATE_PATHS` contains both at lines 164-165; unknown-key test passed. |
| Phase test files | Behavior tests for TOPO-01 and TOPO-02. | ✓ VERIFIED | Relevant tests exist in `tests/test_cake_signal.py`, `tests/test_cake_params.py`, `tests/backends/test_linux_cake.py`, `tests/backends/test_netlink_cake.py`, and `tests/test_check_config.py`; focused pytest passed. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| CAKE stats readback | `CakeSignalProcessor.update()` | `WANController` cached/inline stats update | ✓ WIRED | `wan_controller.py:2807-2820` passes dl/ul stats into the processor; processor now handles one-tin and multi-tin layouts. |
| `build_cake_params()` | backend `initialize_cake()` | `LinuxCakeAdapter.from_config()` params dict | ✓ WIRED | `linux_cake_adapter.py:323-336` builds params from `config.data["cake_params"]` and passes them to the selected backend. |
| `allow_wash` / `wash` params | Linux subprocess CAKE init | params dict with `wash: True/False` | ✓ WIRED | `linux_cake.py:396-402` emits `wash`/`nowash`; tests assert command tokens, including docsis-shaped input. |
| `allow_wash` / `wash` params | Netlink CAKE init | pyroute2 kwargs | ✓ WIRED | `netlink_cake.py:479-486` maps `wash` to `kwargs["wash"]`; tests assert true and false kwargs. |
| Netlink docsis initialization | Linux subprocess fallback | `super().initialize_cake(params)` | ✓ WIRED | `netlink_cake.py:443-448` falls back when `overhead_keyword` is present; test asserts netlink tc is not called and subprocess command includes `wash`. |
| Config unknown-key checker | `KNOWN_AUTORATE_PATHS` | `check_unknown_keys()` registry lookup | ✓ WIRED | `check_config_validators.py:705-721` checks paths against the set; `autorate_config.py:1694-1696` invokes `check_unknown_keys`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cake_signal.py` | `tins_raw` / `active_indices` | `LinuxCakeAdapter` backend queue stats via `WANController` | Yes — backend returns parsed CAKE tin stats; tests invoke realistic dict shape. | ✓ FLOWING |
| `cake_params.py` → backends | `params["wash"]` | YAML `cake_params` dict through `build_cake_params()` | Yes — strict gate preserves real bool and strips only control flag. | ✓ FLOWING |
| `check_config_validators.py` | config paths | loaded config dict via `check_unknown_keys()` | Yes — registry lookup on real path walk. | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-specific tests pass | `.venv/bin/pytest -q tests/test_cake_signal.py::TestCakeSignalProcessorBestEffort tests/test_cake_signal.py::TestCakeSignalProcessorBestEffortStructuralOracle tests/test_cake_signal.py::TestCakeSignalProcessorDiffserv4ByteIdentity tests/test_cake_params.py::TestBuildCakeParamsAllowWash tests/backends/test_linux_cake.py -k 'wash or boolean_flags' tests/backends/test_netlink_cake.py -k 'wash or boolean_flags or falls_back_to_subprocess_for_docsis' tests/test_check_config.py::TestLinuxCakeValidation::test_cake_params_allow_wash_no_unknown_key_warning` | `15 passed, 143 deselected in 0.41s` | ✓ PASS |
| Direct one-tin + allow_wash behavior | Inline `.venv/bin/python` script constructing one-tin stats and `build_cake_params()` permutations | `behavior-spot-checks-ok` | ✓ PASS |
| SAFE-09 source scope | `git diff 6508d68 --name-only -- src/wanctl/ | sort -u` | Exactly 5 approved files | ✓ PASS |
| SAFE-09 behavioral keyword scan | `git diff 6508d68 -- <5 files> | rg ... threshold|ewma|dwell|deadband|burst|time_constant|alpha|beta` | No output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TOPO-01 | Plans 01, 02, 04 | `cake_signal.py` aggregation is tin-agnostic; handles single-tin besteffort and multi-tin diffserv4 without per-deployment branching; ATT behavior preserved. | ✓ SATISFIED | ROADMAP SC #1/#2 verified; code helper and tests exist; Phase 193/194/195 replay and byte-identity gate reported green in closeout; focused tests passed during verification. |
| TOPO-02 | Plans 00, 01, 03, 04 | Per-WAN `cake_params.allow_wash: bool = false` permits `wash` only when explicitly enabled; default false; D-08 protections preserved. | ✓ SATISFIED | `cake_params.py` gate, Linux/netlink backend emission, docsis fallback coverage, and config allowlist all verified; focused tests and direct spot-check passed. |

No orphaned Phase 205 requirements found: `.planning/REQUIREMENTS.md` maps only TOPO-01 and TOPO-02 to Phase 205, and both appear in plan frontmatter and are verified above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/wanctl/check_config_validators.py` | multiple existing lines | `return []` matches generic empty-return scan | ℹ️ Info | Existing validator no-finding returns, not stubs; not part of changed behavior. |
| `205-REVIEW.md` | WR-01/WR-02 | Advisory config-validation warnings | ⚠️ Warning | Valid follow-up concerns for broader config validation (`linux-cake-netlink` validation and additional known `cake_params` keys). They do not block Phase 205's TOPO-01/TOPO-02 goal because `allow_wash`/`wash` paths and runtime emission are verified. |

No TODO/FIXME/placeholder/hardcoded-empty blocker was found in the changed Phase 205 runtime artifacts.

### Human Verification Required

None. Phase 205 is pure code with no deploy; no visual, live production, or external-service behavior is required to establish this phase goal.

### Gaps Summary

No blocking gaps found. The Phase 205 goal is achieved: `cake_signal.py` is layout-agnostic for single-tin and multi-tin CAKE stats, `allow_wash` is default-deny and end-to-end wired through params and backend emission, and SAFE-09 scope is mechanically bounded. Phase 209 correctly carries live wash readback and deployment/config migration work.

---

_Verified: 2026-05-14T18:55:04Z_
_Verifier: the agent (gsd-verifier)_
