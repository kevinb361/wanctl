---
phase: 209-spectrum-config-migration-production-canary-and-docs
verified: 2026-05-23T00:02:31Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
---

# Phase 209: Spectrum Config Migration, Production Canary, and Docs Verification Report

**Phase Goal:** Spectrum runs topology-correct `920Mbit besteffort wash` in production behind the two-snapshot rollback ritual, post-migration soak evidence clears rollback gates, ATT remains byte-identical, docs reflect the topology-correct contract, and SAFE-08/SAFE-09 close mechanically.
**Verified:** 2026-05-23T00:02:31Z
**Status:** passed
**Re-verification:** No — initial verification

> Note: `CHANGELOG.md` and `configs/spectrum.yaml` are dirty in the local working tree with user edits. Verification of closeout content used committed `HEAD` evidence where those files are phase artifacts; dirty local edits were not counted as phase evidence.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Spectrum committed config migrated to `ceiling_mbps: 920`, `diffserv: besteffort`, `allow_wash: true` | ✓ VERIFIED | `git show HEAD:configs/spectrum.yaml` contains all three keys; current working copy also contains them, but committed `HEAD` was the evidence source. |
| 2 | ATT config remained byte-identical to v1.43 close (`6508d68`) | ✓ VERIFIED | `git diff 6508d68..HEAD -- configs/att.yaml --exit-code` returned rc 0; SAFE-08 gate returned `SAFE-08 OK`. |
| 3 | Wash readback validation is implemented and wired for both CAKE backends | ✓ VERIFIED | `build_cake_params()` emits `params["wash"]`; `build_expected_readback()` emits `expected["wash"]`; netlink maps `"wash": "TCA_CAKE_WASH"`; both backends normalize omitted wash to `False` and raise `RuntimeError` only for wash mismatch. |
| 4 | Netlink diffserv readback supports production `besteffort` correctly | ✓ VERIFIED | `_DIFFSERV_NAME_TO_INT` pins `"besteffort": 3`, `"diffserv8": 2`, `"precedence": 4`; Phase 209 SAFE-05 count pins are present in `tests/test_phase_195_replay.py`. |
| 5 | Version bump propagated across package, module, and Docker surfaces | ✓ VERIFIED | `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile` contain `1.44.0`; closeout commit `e12202e` lists exactly the locked five files. |
| 6 | Two-snapshot production canary evidence exists and preserves rollback ordering | ✓ VERIFIED | Snapshot A evidence: health `1.43.0`, `ceiling_mbps: 940` count 1, `allow_wash` count 0, `diffserv besteffort` count 0. Snapshot B evidence: health `1.44.0`; metadata recorded `ISO_B=20260520T123555Z`. |
| 7 | Predeploy/deploy checks completed without wash-readback startup failure | ✓ VERIFIED | Controller-only predeploy gate log rc=0; post-deploy health version `1.44.0`; post-deploy wash RuntimeError log is empty. The broader predeploy log showing a baseline-shape abort is superseded by the controller-only gate evidence recorded for the executed path. |
| 8 | 24h production soak completed with rollback gates clear | ✓ VERIFIED | Quality report: 82,954 rows, 23.9997h span, parse errors 0, missing boundary rows 0, all rows `healthy`/`1.44.0`; post-soak gate rc file is `0`; stderr reports restart rate `0.00/h`, transition rate `49.83/h` vs baseline `77.17/h`, PASS. |
| 9 | Operator docs and changelog document `allow_wash`, besteffort/wash semantics, and topology rationale | ✓ VERIFIED | `docs/BRIDGE_QOS.md` is 73 lines with decision guide, Spectrum/ATT contrast, and DSCP topology rationale; `docs/CONFIGURATION.md` links `BRIDGE_QOS.md`; committed changelog contains v1.44.0 entries for TOPO-03/06/07 and SAFE-08/09. |
| 10 | SAFE-08 and SAFE-09 close mechanically, not by manual diff | ✓ VERIFIED | Fresh spot-checks: `bash scripts/check-safe07-source-diff.sh --att-config-whitelist 6508d68` → `SAFE-08 OK`; `bash scripts/check-safe07-source-diff.sh 6508d68` → `SAFE-09 OK`. Task4b rerun evidence records verifier tests `17 passed`. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `configs/spectrum.yaml` | Topology-correct Spectrum config: `920Mbit besteffort wash` | ✓ VERIFIED | Committed `HEAD` has `ceiling_mbps: 920`, `diffserv: besteffort`, `allow_wash: true`. |
| `configs/att.yaml` | Byte-identical to `6508d68` | ✓ VERIFIED | `git diff 6508d68..HEAD -- configs/att.yaml --exit-code` rc 0. |
| `src/wanctl/cake_params.py` | Always-emits wash into params; pass-through readback transform | ✓ VERIFIED | Lines 181-182 and 226-227 implement `params["wash"]` and `expected["wash"]`. |
| `src/wanctl/backends/netlink_cake.py` | TCA wash mapping, hard-fail, omitted-off normalization, besteffort enum fix | ✓ VERIFIED | Lines 68-86 and 540-581 contain the required implementation. |
| `src/wanctl/backends/linux_cake.py` | Wash hard-fail and omitted-off normalization | ✓ VERIFIED | Lines 447-474 contain normalization and wash-specific `RuntimeError`. |
| `scripts/check-safe07-source-diff.sh` | SAFE-08 ATT mode and SAFE-09 v1.44 allowlist mode | ✓ VERIFIED | `--att-config-whitelist`, `DEFAULT_PHASE_209_ATT_REF="6508d68"`, `V144_ALLOWLIST_RE`, `SAFE-08 OK`, and `SAFE-09 OK` present; both gates pass. |
| `scripts/phase206-gate-check.py` | Finite positive `--window-hours` guard | ✓ VERIFIED | `import math` and `not math.isfinite(args.window_hours)` guard present. |
| `docs/BRIDGE_QOS.md` | Standalone operator decision guide | ✓ VERIFIED | 73 lines; contains `allow_wash`, Spectrum/ATT contrast, and DSCP rationale. |
| `docs/CONFIGURATION.md` | Focused `allow_wash` entry linking to `BRIDGE_QOS.md` | ✓ VERIFIED | Entry present under `cake_params`. |
| `CHANGELOG.md` | v1.44.0 heading and Phase 209 entries | ✓ VERIFIED | Committed changelog has `## v1.44.0 — 2026-05-19` and Phase 209 entries. |
| Soak evidence directory | 24h capture, A/B summary, post-soak gate, quality report | ✓ VERIFIED | `soak/20260521T222622Z/` contains capture, summaries, gate outputs, quality report, and live health evidence. |
| `task4b-evidence/20260522T233944Z/safe-closeout-rerun.md` | Final SAFE closeout PASS evidence | ✓ VERIFIED | Records verifier tests passing plus SAFE-08/SAFE-09 OK outputs. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `configs/spectrum.yaml` | CAKE qdisc args/readback | `cake_params.allow_wash`, `diffserv`, `ceiling_mbps` consumed by config/controller path | ✓ WIRED | `build_cake_params()` allows wash only under strict `allow_wash is True` and always emits the readback expectation. |
| `build_cake_params()` | `build_expected_readback()` | `params["wash"]` | ✓ WIRED | Spot-check imported module and asserted Spectrum `True` and ATT/default `False` readback contracts. |
| `build_expected_readback()` | `netlink_cake.validate_cake()` | expected `wash` key and `_VALIDATE_KEY_TO_TCA` | ✓ WIRED | Netlink validator consumes expected keys, maps wash to `TCA_CAKE_WASH`, normalizes omitted off, and hard-fails mismatch. |
| `build_expected_readback()` | `linux_cake.validate_cake()` | expected `wash` key and `options.get(key)` | ✓ WIRED | Linux validator consumes `wash`, normalizes omitted off, and hard-fails mismatch. |
| SAFE-08 verifier | `configs/att.yaml` | `git diff <ref>..HEAD -- configs/att.yaml` | ✓ WIRED | Fresh gate run passed against `6508d68`. |
| SAFE-09 verifier | v1.44 source diff | `V144_ALLOWLIST_RE` and version anchor | ✓ WIRED | Fresh gate run passed against `6508d68`; allowlist includes Phase 208 `history.py` as approved non-controller TOOL-02 drift. |
| 24h soak capture | Phase 206 post-soak gate | `--soak-ndjson`, restart counters, finite window | ✓ WIRED | Gate rc file is `0`; stderr records all rollback gates clear. |
| Docs/config/changelog | Operator decision path | Relative links to `BRIDGE_QOS.md` | ✓ WIRED | `CONFIGURATION.md`, committed `CHANGELOG.md`, and `configs/spectrum.yaml` link/refer to `BRIDGE_QOS.md`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/wanctl/cake_params.py` | `params["wash"]` / `expected["wash"]` | YAML `cake_params.allow_wash` strict-bool gate | Yes | ✓ FLOWING |
| `src/wanctl/backends/netlink_cake.py` | `actual = options.get_attr("TCA_CAKE_WASH")` | Kernel/netlink CAKE readback | Yes | ✓ FLOWING |
| `src/wanctl/backends/linux_cake.py` | `actual_value = options.get("wash")` | `tc -j qdisc show` CAKE readback JSON | Yes | ✓ FLOWING |
| Soak summary/gate evidence | rows, versions, statuses, restart/transition metrics | 24h cake-shaper capture and Phase 206 gate outputs | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| SAFE-08 mechanical closeout | `bash scripts/check-safe07-source-diff.sh --att-config-whitelist 6508d68` | `SAFE-08 OK: no configs/att.yaml diff vs 6508d68` | ✓ PASS |
| SAFE-09 mechanical closeout | `bash scripts/check-safe07-source-diff.sh 6508d68` | `SAFE-09 OK: diff vs 6508d68 bounded to v1.44 allowlist` | ✓ PASS |
| Wash readback transform | Python import/assert spot-check for Spectrum and ATT/default wash expected values | `wash_readback_contract_ok` | ✓ PASS |

Additional orchestrator-observed verification: focused hot-path slice `673 passed`; full suite rerun `5116 passed, 6 skipped, 2 deselected`; verifier tests `17 passed`; code review status clean; schema drift gate non-blocking (`drift_detected=false`).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOPO-03 | 209-01, 209-04 | Spectrum config migrates to 920/besteffort/wash; ATT byte-identical | ✓ SATISFIED | Committed Spectrum config has 920/besteffort/allow_wash; ATT diff vs `6508d68` rc 0; wash readback validation implemented. |
| TOPO-06 | 209-04 | Production canary with two-snapshot rollback ritual and 24h verification soak vs v1.43 baseline | ✓ SATISFIED | Snapshot A/B evidence exists; 24h soak quality report passes; post-soak gate rc 0. |
| TOPO-07 | 209-03 | Changelog, BRIDGE_QOS, and CONFIGURATION updated for allow_wash/topology rationale | ✓ SATISFIED | Docs/changelog artifacts verified and linked. |
| SAFE-08 | 209-02, 209-04 | ATT config byte-identical to v1.43 close, mechanically verified | ✓ SATISFIED | `--att-config-whitelist 6508d68` gate passes; direct committed diff rc 0. |
| SAFE-09 | 209-01, 209-02, 209-04 | No threshold/algorithm drift; source diff bounded; wash readback validates live qdisc state | ✓ SATISFIED | SAFE-09 gate passes; source diff bounded to approved v1.44 set; wash readback hard-fail paths implemented. `history.py` allowlist inclusion is documented as approved Phase 208 TOOL-02 operator tooling drift, not controller threshold/algorithm drift. |

No additional Phase 209 requirement IDs appear orphaned in `.planning/REQUIREMENTS.md` / ROADMAP beyond TOPO-03, TOPO-06, TOPO-07, SAFE-08, and SAFE-09.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| — | — | None blocking found in verified phase artifacts | — | — |

### Human Verification Required

None pending. Production/operator-gated verification was already executed and preserved as phase evidence: Snapshot A/B, deploy health, 24h soak, post-soak gate, and SAFE closeout rerun.

### Gaps Summary

No blocking gaps found. The phase goal is achieved: Spectrum is committed and evidenced as `920Mbit besteffort wash`, wash readback validation is wired and tested, canary/soak evidence clears the rollback gates, docs are present, and SAFE-08/SAFE-09 close mechanically.

---

_Verified: 2026-05-23T00:02:31Z_
_Verifier: the agent (gsd-verifier)_
