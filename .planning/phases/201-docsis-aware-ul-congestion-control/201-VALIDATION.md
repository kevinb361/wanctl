---
phase: 201
slug: docsis-aware-ul-congestion-control
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-04
---

# Phase 201 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Skeleton populated by `/gsd-plan-phase 201`. Per-task rows are filled by the planner; Wave 0 entries (test stubs, fixtures) are derived from RESEARCH.md `## Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 s (quick), ~3 min (full) |

---

## Sampling Rate

- **After every task commit:** Run quick run command (focused hot-path slice from CLAUDE.md)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds (quick)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> **Planner fills this table.** Each plan task with `type: execute | tdd` MUST appear here with an automated command, OR be wired to a Wave 0 dependency that creates the test stub. Replay-based and canary-based tasks are recorded under Manual-Only Verifications below.

---

## Wave 0 Requirements

- [ ] *Pending — planner derives from RESEARCH.md `## Validation Architecture`*

*Wave 0 (test stubs + fixtures) MUST land before any classifier/setpoint-clamp/CAKE-corroborator code. Anti-shallow-execution: no `type: execute` task may write production code under `src/wanctl/queue_controller.py` or `src/wanctl/wan_controller.py` until the corresponding test stub exists in `tests/`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Spectrum UL canary `ul_floor_hits_during_load=0` | VALN-06 | Requires live ISP link + 10–15 min `iperf3 -P4` saturation; cannot run in CI | Operator runs `scripts/phase200-saturation-canary.sh` against deploy target after binary install; verdict.json `pass` required before continuing |
| 24h Spectrum UL regression soak `<5/60s` UL hysteresis suppression | VALN-06 | Requires 24h wall-clock against live ISP link | Operator starts soak watchdog after canary `pass`; soak watchdog gates milestone closure |
| Predeploy YAML reconcile gate | D-15 | Requires SSH to deploy target inspecting `/etc/wanctl/spectrum.yaml` for v1.41-only rejected-hypothesis keys | Operator runs predeploy gate script before canary; abort + reconcile if mismatch |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for unit/integration; canary + soak excluded (manual-only)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
