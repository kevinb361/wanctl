---
phase: 247
slug: fping-shadow-capture-phase-245-evidence-review
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 247 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest tests/test_phase247_shadow_script.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/test_phase247_shadow_script.py tests/test_phase247_safe18_verifier.py -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_phase247_shadow_script.py -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/test_phase247_shadow_script.py tests/test_phase247_safe18_verifier.py -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 247-01-01 | 01 | 1 | PROF-02 | — | N/A | static | `grep -c "cycle_budget_nonregression" .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/247-METHODOLOGY-REVIEW.md` | ❌ W0 | ⬜ pending |
| 247-02-01 | 02 | 1 | SAFE-18 | — | SAFE-18 zero-diff invariant | shell | `bash scripts/phase247-safe18-boundary-check.sh --self-test` | ❌ W0 | ⬜ pending |
| 247-02-02 | 02 | 1 | SAFE-18 | — | pytest wrapper calls verifier | unit | `.venv/bin/pytest tests/test_phase247_safe18_verifier.py -v` | ❌ W0 | ⬜ pending |
| 247-03-01 | 03 | 2 | PROF-01 | — | test stubs created before implementation | unit | `.venv/bin/pytest tests/test_phase247_shadow_script.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 247-03-02 | 03 | 2 | PROF-01 | — | shadow script passes all unit tests | unit | `.venv/bin/pytest tests/test_phase247_shadow_script.py -v` | ❌ W0 | ⬜ pending |
| 247-04-01 | 04 | 3 | PROF-01 | — | preflight / deploy / smoke test (human) | manual | operator runs: `python phase247-fping-shadow.py --output /tmp/phase247-shadow.ndjson --dry-run` | ❌ W0 | ⬜ pending |
| 247-04-02 | 04 | 3 | PROF-01 | — | overnight soak produces NDJSON with probe_stats records (human) | manual | operator confirms: `wc -l /var/lib/wanctl/phase247-shadow.ndjson` > 100 after 12h | N/A | ⬜ pending |
| 247-04-03 | 04 | 3 | PROF-01 | — | summary JSON generated from NDJSON | unit | `python -c "import json; d=json.load(open('.planning/phases/247-.../evidence/phase247-shadow-summary.json')); assert 'soak_duration_h' in d"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase247_shadow_script.py` — unit tests for shadow capture script (config loading, NDJSON output, probe_stats periodic logging, shutdown final record)
- [ ] `tests/test_phase247_safe18_verifier.py` — pytest wrapper for SAFE-18 boundary check script (mirrors `tests/test_phase245_safe17_verifier.py` pattern)
- [ ] `scripts/phase247-safe18-boundary-check.sh` — SAFE-18 boundary verifier (new file, analogous to `scripts/phase245-safe17-boundary-check.sh`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| fping shadow soak runs 12h on cake-shaper without crashing | PROF-01 | Requires live cake-shaper SSH session; cannot be simulated locally | Deploy script to cake-shaper, start in nohup, check output file after 12h; confirm no error lines in stderr redirect |
| Methodology review finding matches raw Phase 245 evidence | PROF-02 | Operator must compare 247-METHODOLOGY-REVIEW.md gate rows against 245-AB-VERDICT.json manually | Read both files, confirm threshold/measured/margin/diagnosis columns are accurate vs git show 7e6844a2 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
