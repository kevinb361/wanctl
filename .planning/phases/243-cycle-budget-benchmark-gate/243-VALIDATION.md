---
phase: 243
slug: cycle-budget-benchmark-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-16
---

# Phase 243 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/pytest`), ruff, mypy per CLAUDE.md |
| **Config file** | `pyproject.toml` (project standard) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase243_safe17_verifier.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds (unit slice); benchmark soak is operator-gated, out-of-band |

---

## Sampling Rate

- **After every task commit:** Run the SAFE-17 mirror test + the new script's unit test (quick run).
- **After every plan wave:** Run `.venv/bin/pytest tests/ -q` + `bash scripts/phase243-safe17-boundary-check.sh --self-test`.
- **Before `/gsd:verify-work`:** Full suite must be green; `phase243-safe17-boundary-check.sh` PASS with evidence JSON.
- **Max feedback latency:** ~60 seconds (unit). The live 8-arm benchmark run is operator-gated on real WAN hosts and produces the verdict JSON out-of-band.
- **Live-run sampling floor (D-04c):** per arm `n >= max(10k cycles, 30 min)` ≈ 36k cycles at 20Hz; hygiene sampler at 1Hz over the same window.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (W0) | safe17 | 0 | SAFE-17 | — | any `src/wanctl/` edit fails the boundary verifier (pinned to 243 close anchor) | unit (git-diff harness) | `.venv/bin/pytest tests/test_phase243_safe17_verifier.py -x` | ❌ W0 (clone `test_phase241_safe17_verifier.py`) | ⬜ pending |
| (W0) | safe17 | 0 | SAFE-17 | — | verifier `--self-test` trips on a committed out-of-allowlist edit | shell self-test | `bash scripts/phase243-safe17-boundary-check.sh --self-test` | ❌ W0 | ⬜ pending |
| (W0) | rollup | 0 | BENCH-01 | — | cycle rollup parses `"Cycle timing"` NDJSON → avg/p99 per arm | unit | `.venv/bin/pytest tests/test_phase243_cycle_rollup.py -x` | ❌ W0 | ⬜ pending |
| (W0) | hygiene | 0 | BENCH-01 | — | hygiene sampler emits well-formed fd/zombie/Tasks NDJSON | unit | `.venv/bin/pytest tests/test_phase243_hygiene_sampler.py -x` | ❌ W0 | ⬜ pending |
| (W0) | gate | 0 | BENCH-02 | — | gate evaluator computes correct pass/fail vs frozen thresholds (delta%, ceiling, zombie, fd-trend, stall, n-floor) | unit | `.venv/bin/pytest tests/test_phase243_gate_eval.py -x` | ❌ W0 | ⬜ pending |
| (W0) | prereg | 0 | BENCH-02 | — | pre-registration thresholds JSON exists & committed before evidence | unit | `.venv/bin/pytest tests/test_phase243_prereg.py -x` | ❌ W0 | ⬜ pending |
| (manual) | run | — | BENCH-01/02 | — | 60s real-unit run produces non-empty `.profile.json` with `autorate_cycle_total` | manual (operator, WAN host) | operator runbook; collector errors if no cycle samples | manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase243_safe17_verifier.py` — clone of 241 mirror test, pinned to 243 `PHASE_CLOSE_ANCHOR`
- [ ] `tests/test_phase243_cycle_rollup.py` — NDJSON fixture → avg/p99 + stall-gap detector
- [ ] `tests/test_phase243_hygiene_sampler.py` — fd/zombie/Tasks NDJSON shape + trend test
- [ ] `tests/test_phase243_gate_eval.py` — frozen-threshold verdict logic on synthetic arms (pass + each fail mode)
- [ ] `tests/test_phase243_prereg.py` — pre-registration artifact presence/shape
- [ ] `scripts/phase243-thresholds.json` + `243-BENCHMARK-PREREGISTRATION.md` committed **before** the run (BENCH-02 discipline)
- [ ] Framework install: none (pytest already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 8-arm live benchmark run (icmplib/fping × idle/under-load × .226/.233) under a real systemd unit, journal-pipe stdout | BENCH-01 | Requires real WAN hosts (.226 Spectrum, .233 ATT), fping install, netperf reachability, `-S` source-IP binding — not reproducible on the dev VM | Operator runbook: launch transient unit per arm, drive load via flent RRUL (Dallas Linode `104.200.21.31`), sample ≥30 min / ≥10k cycles per arm |
| Gate verdict recorded against pre-committed thresholds | BENCH-02 | Verdict depends on live evidence captured above | Run `phase243-gate-eval` over collected evidence JSON; record verdict against `phase243-thresholds.json` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
