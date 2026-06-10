---
phase: 231-migration-held-criteria-rollback-verification-doc-sweep
verified: 2026-06-10T14:40:41Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
---

# Phase 231: Migration-Held Criteria, Rollback Verification & Doc Sweep Verification Report

**Phase Goal:** The 2026-06-08 migration is provably held on both WANs against formal criteria, native-controller rollback is verified (exercised under operator approval or trivially provable via a documented preflighted procedure with evidence), stale native-ownership doc claims are swept, and SAFE-14 is proven at milestone close.
**Verified:** 2026-06-10T14:40:41Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Formal migration-held criteria are defined before evaluation with explicit thresholds/window anchored to 2026-06-08. | ✓ VERIFIED | `231-SOAK01-EVIDENCE.md:14-25` defines C1-C4, C3 constants, ingestion 24h window, and migration anchor before captured output. |
| 2 | C3 sustained-error criterion is objective and machine-checkable. | ✓ VERIFIED | `scripts/phase231-migration-held.sh:16-20`, `172-207`, `236-268` encode unit sets and pass/fail constants; evidence records rule and raw err lines. |
| 3 | SOAK-01 live capture completed before any rollback exercise. | ✓ VERIFIED | `231-SOAK01-EVIDENCE.md:12`; `231-SOAK02-EVIDENCE.md:141-145` records provable-path acceptance and ordering gate satisfaction; no confirm exercise was run. |
| 4 | Criteria evaluated against live evidence for both WANs through read-only channels. | ✓ VERIFIED | `231-SOAK01-EVIDENCE.md:27-451` contains `spectrum` and `att` live JSON, read-only safety boundary, and seven-active/three-inactive inventory. |
| 5 | Per-WAN PASS/FAIL verdicts with raw evidence are committed. | ✓ VERIFIED | `231-SOAK01-EVIDENCE.md:37-281` has both per-WAN JSON verdicts `PASS`; final line `SOAK-01 PASS`. |
| 6 | Rollback is verified by documented, preflighted, no-mutation provable path. | ✓ VERIFIED | `231-SOAK02-EVIDENCE.md:14-149`; both preflight JSON files report `overall_pass: true`; operator accepted provable path. |
| 7 | Live rollback exercise is explicit opt-in and never runs without approval; declining still satisfies SOAK-02. | ✓ VERIFIED | `scripts/phase231-rollback.sh:269-274` refuses `--confirm` without `--i-have-operator-approval`; spot-check produced refusal before remote call; evidence records no mutation. |
| 8 | Live rollback exercise option was gated behind SOAK-01 evidence. | ✓ VERIFIED | `231-SOAK02-EVIDENCE.md:145` cites existing `SOAK-01 PASS`; no live exercise was performed. |
| 9 | Silicom watchdog expected states are explicit per mode. | ✓ VERIFIED | `scripts/phase231-rollback.sh:116-131`, `230-238`; SOAK-02 dry-runs and preflight evidence record Spectrum watchdog untouched and ATT watchdog swap expectations. |
| 10 | Rollback script refuses all mutation without `--confirm`; dry-run/preflight are read-only. | ✓ VERIFIED | Dry-run performs no SSH; `--confirm` without approval fails; preflight commands are `systemctl cat/is-*` and `test -f/-x` only. |
| 11 | Preflight proves native unit/config/code, disabled native units, no dual-writer, and Conflicts guards. | ✓ VERIFIED | `rollback-preflight-att.json` and `rollback-preflight-spectrum.json` show native template/config/code present, native instances disabled/inactive, external units active, and `Conflicts=wanctl@...`. |
| 12 | Active docs describe both native `wanctl@` mode and external cake-autorate mode; stale Spectrum/ATT native ownership claims are swept. | ✓ VERIFIED | README, DEPLOYMENT, CONFIGURATION, and ARCHITECTURE all contain `cake-autorate`; grep found no `wanctl@spectrum`/`wanctl@att` hits in active docs. |
| 13 | Generic portable `wanctl@` documentation is preserved as native mode. | ✓ VERIFIED | `README.md:72-84`, `docs/DEPLOYMENT.md:10-25`, `55-90`, and `182-215` preserve/reframe native mode. |
| 14 | No timer-era guidance or new private IP prose was introduced. | ✓ VERIFIED | Grep found no `timer` in `docs/DEPLOYMENT.md`; `231-SAFE14-BOUNDARY.md:105-109` and summary report private-IP diff check passed. |
| 15 | SAFE-14 controller-path zero-diff is proven at Phase 231 boundary and milestone close against `SAFE_BASE=87980bdf`. | ✓ VERIFIED | `git diff --stat 87980bdf -- <protected set>` produced empty output; `231-SAFE14-BOUNDARY.md:20-70` records clean diff and dirty-tree checks. |
| 16 | Post-boundary allowlist holds after boundary tracking commit. | ✓ VERIFIED | `git log --name-only 2a2a1022..HEAD` shows only `.planning/**` paths (`231-03-SUMMARY`, ROADMAP/STATE/REQUIREMENTS, `231-REVIEW`). |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/phase231-migration-held.sh` | Read-only migration-held evaluator with JSON verdicts | ✓ VERIFIED | Exists; `gsd-sdk verify.artifacts` passed; shellcheck passed; contains C1-C4, config-sourced envelope parsing, bounded SSH/curl, no mutating remote commands. |
| `tests/test_phase231_migration_held.py` | Regression proof for read-only evaluator | ✓ VERIFIED | Exists; focused test included in `16 passed`. |
| `231-SOAK01-EVIDENCE.md` | Formal SOAK-01 evidence | ✓ VERIFIED | Exists with criteria, timestamps, both-WAN JSON, corroboration, and `SOAK-01 PASS`. |
| `scripts/phase231-rollback.sh` | Per-WAN rollback preflight/dry-run/confirm script | ✓ VERIFIED | Exists; shellcheck passed; dry-run and preflight are safe; confirm double-gated. Residual live-confirm risk noted below. |
| `tests/test_phase231_rollback.py` | Regression proof for rollback gating/rendering | ✓ VERIFIED | Exists; focused test included in `16 passed`. Review warning notes preflight read-only command-log assertion could be stronger. |
| `231-SOAK02-EVIDENCE.md` | Documented rollback procedure + preflight proof + operator decision | ✓ VERIFIED | Exists with dry-run procedures, both-WAN preflight proof, historical exercise, Kevin provable-path acceptance, and `SOAK-02 PROVABLE-PATH PASS`. |
| `docs/DEPLOYMENT.md` | Both deployment modes and external-mode deploy/monitor guidance | ✓ VERIFIED | Deployment Modes section and external flags present; stale `wanctl@spectrum`/`wanctl@att` live-path hits absent. |
| `docs/ARCHITECTURE.md` | External mode architecture beside native controller architecture | ✓ VERIFIED | Lines 23-51 describe external rate-controller mode and state bridge contract. |
| `docs/CONFIGURATION.md` | Native restart guidance and external cake-autorate equivalent | ✓ VERIFIED | Lines 232-246 and 294-298 distinguish native `wanctl@` restart from external cake-autorate restart. |
| `README.md` | User-facing mode summary and monitoring caveat | ✓ VERIFIED | Lines 72-84 and 263-280 label native examples and external monitoring path. |
| `231-SAFE14-BOUNDARY.md` | Phase/milestone SAFE-14 proof | ✓ VERIFIED | Exists with SAFE_BASE, PHASE231_START, empty protected diff, verification outputs, and post-boundary allowlist. |

### Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scripts/phase231-migration-held.sh` | `configs/cake-autorate/config.spectrum.sh` + `config.att.sh` | qdisc envelope parsed from config fields | ✓ VERIFIED | SDK link check passed; script parses `min_dl_shaper_rate_kbps`, `max_dl_shaper_rate_kbps`, `base_ul_shaper_rate_kbps`. |
| `scripts/phase231-rollback.sh` | `WANCTL_CAKE_AUTORATE_FUTURE.md` rollback procedure | ATT rollback command block | ✓ VERIFIED | SDK link check passed; dry-run renders ATT qdisc/bpctl/native rollback shape and cites historical exercise in evidence. |
| `docs/DEPLOYMENT.md` | `CLAUDE.md` Service Model | two-mode service prose | ✓ VERIFIED | SDK literal pattern check failed on brace form, but manual verification passes: `CLAUDE.md:123-145` and `docs/DEPLOYMENT.md:6-25` agree on native + external service modes. |
| `231-SAFE14-BOUNDARY.md` | Phase 230 SAFE-14 skeleton | two-baseline proof | ✓ VERIFIED | SDK failed due abbreviated source path, not substance. Boundary file exists and mirrors required sections: Baselines, protected diff, dirty-tree, scope accounting, verification, allowlist, verdict. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `phase231-migration-held.sh` | per-WAN `checks` JSON | live `curl`, `sqlite3 -readonly SELECT`, `journalctl`, `tc qdisc show` | Yes — evidence has rows, health payloads, qdisc text, journal lines | ✓ FLOWING |
| `phase231-rollback.sh` | preflight `checks` JSON | live bounded SSH `systemctl cat/is-*` + `test -f/-x` | Yes — committed JSON contains raw stdout/stderr and pass flags | ✓ FLOWING |
| Docs | N/A | Static documentation | N/A | ✓ N/A |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase scripts are shellcheck-clean | `shellcheck -S error scripts/phase231-migration-held.sh scripts/phase231-rollback.sh` | exit 0 | ✓ PASS |
| Focused Phase 231 tests pass | `.venv/bin/pytest tests/test_phase231_migration_held.py tests/test_phase231_rollback.py -q` | `16 passed in 1.01s` | ✓ PASS |
| Migration-held help has no network contact | `bash scripts/phase231-migration-held.sh --help` | printed usage, exit 0 | ✓ PASS |
| Rollback dry-run renders procedure locally | `bash scripts/phase231-rollback.sh --wan att --dry-run` | printed ATT rollback + return-to-cake plan | ✓ PASS |
| Confirm path refuses missing approval before remote call | `bash scripts/phase231-rollback.sh --wan att --confirm` | `REFUSED: --confirm requires --i-have-operator-approval before any remote call.` | ✓ PASS |
| SAFE-14 protected controller diff is empty | `git diff --stat 87980bdf -- src/wanctl/...` | empty output; dirty-tree checks clean | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SOAK-01 | `231-01-PLAN.md` | Formal migration-held criteria defined and evaluated against live evidence for both WANs. | ✓ SATISFIED | `231-SOAK01-EVIDENCE.md` has C1-C4 criteria, both-WAN PASS JSON, timestamps, and external-mode corroboration. |
| SOAK-02 | `231-02-PLAN.md` | Rollback verified by exercise or documented/preflighted provable path with evidence. | ✓ SATISFIED | `231-SOAK02-EVIDENCE.md` records dry-run procedures, live preflight proof, historical exercise citation, and Kevin's provable-path acceptance. |
| DOCS-04 | `231-03-PLAN.md` | Active docs describe both deployment modes; stale native Spectrum/ATT ownership swept. | ✓ SATISFIED | README, DEPLOYMENT, CONFIGURATION, ARCHITECTURE all describe external mode; grep found no `wanctl@spectrum`/`wanctl@att` active-doc hits. |
| SAFE-14 | `231-03-PLAN.md` | Controller-path zero-diff invariant at boundary and milestone close. | ✓ SATISFIED | Empty protected diff vs `87980bdf`, clean dirty-tree checks, post-boundary `.planning/**` only audit. |

No orphaned Phase 231 requirements were found: `.planning/REQUIREMENTS.md:77-80` maps exactly SOAK-01, SOAK-02, DOCS-04, SAFE-14 to Phase 231, and all four appear in PLAN frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/phase231-rollback.sh` | 277-280 | Confirm-mode remote script lacks `set -euo pipefail` before `bash -s` | ⚠️ Warning / residual risk | Code review CR-01 is real for any future live rollback exercise: intermediate mutation failure could be masked. It does not block SOAK-02 as completed because Kevin accepted the no-mutation provable path and no confirm exercise ran. Fix before using live confirm path. |
| `scripts/phase231-migration-held.sh` | 136 | Same-`local` assignment relies on bash expansion/dynamic scoping | ⚠️ Warning | Review WR-01: currently works from `evaluate_wan`, but fragile under future refactor. Not a phase-goal blocker. |
| `tests/test_phase231_rollback.py` | 104-119 | Preflight test does not inspect SSH shim log for mutation verbs | ⚠️ Warning | Review WR-02: safety regression coverage could be stronger; implementation evidence and preflight commands remain read-only now. |
| Phase security artifact | N/A | No phase-specific `SECURITY.md` | ℹ️ Info | No phase-specific security file exists; project-level `docs/SECURITY.md` exists. The phase threat models and evidence safety boundaries cover the relevant rollback/read-only risks. |

### Human Verification Required

None for current closeout. Human/operator checkpoints already occurred inside the phase artifacts: SOAK-01 evidence was operator-approved and SOAK-02 provable path was accepted by Kevin. No new visual, external mutation, or live rollback exercise is required for this verification pass.

### Gaps Summary

No blocking gaps found. The phase goal is achieved by committed evidence and executable checks. The optional future live rollback confirm path carries a known residual risk from code review and should be fixed before any future production rollback exercise, but it does not invalidate the accepted no-mutation SOAK-02 provable path.

---

_Verified: 2026-06-10T14:40:41Z_  
_Verifier: the agent (gsd-verifier)_
