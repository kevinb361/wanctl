---
phase: 241
slug: fping-backend-offline-reflector-quality
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-15
---

# Phase 241 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_fping_measurement.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green + `scripts/phase241-safe17-boundary-check.sh` PASS
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T1 | 01 | 1 | FPING-01..04 | T-241-01/02 | argv list (no shell); `-` never 0.0ms | unit | `.venv/bin/pytest -o addopts='' tests/test_fping_measurement.py -k "parse or dash or total_loss or source_ip or multi_reflector or nonzero_exit or aggregation" -q` | ❌ Wave 0 | ⬜ pending |
| 01-T2 | 01 | 1 | FPING-01/05 | T-241-03 | bounded timeout; daemon survives stall/death | unit | `.venv/bin/pytest -o addopts='' tests/test_fping_measurement.py -k "thread or cadence or stall or death or timeout" -q` | ❌ Wave 0 | ⬜ pending |
| 01-T3 | 01 | 1 | REFL-01, FPING-04 | T-241-02 | loss→bool feed; scorer math untouched | unit | `.venv/bin/pytest -o addopts='' tests/test_fping_measurement.py -q` | ❌ Wave 0 | ⬜ pending |
| 02-T1 | 02 | 1 | SAFE-17 | T-241-05/06 | allowlist +2 files; fail-closed layers intact | unit | `.venv/bin/pytest -o addopts='' tests/test_phase241_safe17_verifier.py -k "contract or out_of_allowlist or dirty or protected or seam" -q` | ❌ Wave 0 | ⬜ pending |
| 02-T2 | 02 | 1 | FPING-01 (OQ1) | T-241-07 | additive range validators; absent keys no-op | unit | `.venv/bin/pytest -o addopts='' tests/test_check_config_validators_fping.py -q` | ❌ Wave 0 | ⬜ pending |
| 03-T1 | 03 | 2 | FPING-04 | T-241-08/09 | non-mutating capture; byte-identical command | static | `bash -n scripts/capture-fping-fixtures.sh` | ❌ Wave 0 | ⬜ pending |
| 03-T2 | 03 | 2 | FPING-04 / D-08 | T-241-10 | real 5.1 captures (operator-in-the-loop) | manual | operator-run on live host | n/a | ⬜ pending |
| 03-T3 | 03 | 2 | FPING-04, REFL-01 | T-241-02 | tests pass against real captures | unit | `.venv/bin/pytest tests/ -q` | ❌ Wave 0 | ⬜ pending |
| 04-T1 | 04 | 3 | SAFE-17 | T-241-13 | clean tree; byte-unchanged frozen files | gate | `git status --porcelain -- src/wanctl/` empty | ❌ Wave 0 | ⬜ pending |
| 04-T2 | 04 | 3 | SAFE-17 | T-241-11/12 | fail-closed boundary verifier passed:true | gate (blocking) | `bash scripts/phase241-safe17-boundary-check.sh` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

These artifacts do not yet exist and are created by the tasks that depend on them:

- [ ] `src/wanctl/fping_measurement.py` — backend + parser + FpingThread + scorer feed (Plan 01)
- [ ] `tests/test_fping_measurement.py` — fixture-driven parser + lifecycle + scorer-feed tests (Plan 01, re-pointed in Plan 03)
- [ ] `tests/fixtures/fping/{reply,total_loss,partial_loss,partial_line,banner_noise,process_death}.txt` — synthetic bootstrap (Plan 01) → real 5.1 captures (Plan 03 / D-08 operator-run)
- [ ] `scripts/phase241-safe17-boundary-check.sh` — expanded-allowlist boundary verifier (Plan 02)
- [ ] `tests/test_phase241_safe17_verifier.py` — verifier behavior test mirror (Plan 02)
- [ ] `tests/test_check_config_validators_fping.py` — fping sub-param validator tests (Plan 02)
- [ ] `scripts/capture-fping-fixtures.sh` — operator-run capture helper (Plan 03 / D-08)
- [ ] Framework install: none — pytest infra exists.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Capture real fping 5.1 output for the six D-03 scenarios | FPING-04 / D-08 | Operator-in-the-loop: must run on the live host against real reflectors; cannot be reproduced in CI (fping absent on dev VM) | Run `scripts/capture-fping-fixtures.sh` on the live host; commit captured samples as fixtures (Plan 03 Task 2, `autonomous: false`) |
| SAFE-17 boundary gate verdict | SAFE-17 | Blocking human-verify of the fail-closed verifier result before phase close | Run `bash scripts/phase241-safe17-boundary-check.sh`; confirm `passed:true` evidence (Plan 04 Task 2) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned 2026-06-15
