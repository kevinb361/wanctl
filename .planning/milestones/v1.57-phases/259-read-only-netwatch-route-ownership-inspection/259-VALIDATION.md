---
phase: 259
slug: read-only-netwatch-route-ownership-inspection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-20
---

# Phase 259 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pyproject.toml) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` (note: ~34 pre-existing stale SAFE-17 boundary failures in full suite — scope verification to phase slice) |
| **Estimated runtime** | ~2 seconds (phase slice); ~10 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py tests/test_route_ownership_inspector_rest.py -q` + `.venv/bin/ruff check src/wanctl/steering tests`
- **After every plan wave:** Add `tests/test_steering_health.py tests/test_route_ownership_guard.py tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_phase259_ownership_proof.py` to the slice
- **Before `/gsd:verify-work`:** Phase slice green + live `INSPECT_PROOF_PASS` recorded in VERIFICATION.md
- **Max feedback latency:** ~5 seconds (phase slice)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 259-01-01 | 01 | 1 | INSPECT-01 | — | `entries_count` + `route_mutating_active_count` correctly counted from guard result | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -k netwatch -q` | ❌ W0 | ⬜ pending |
| 259-01-02 | 01 | 1 | INSPECT-02 | — | `observed_owner` attribution: netwatch/wanctl/none/unknown correctly derived from guard verdict + mode | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -k "owner or default_route" -q` | ❌ W0 | ⬜ pending |
| 259-01-03 | 01 | 1 | INSPECT-02 | — | over-mocked RouterOSREST: GET-only calls, route filter `0.0.0.0/0`, field projection | integration | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector_rest.py -q` | ❌ W0 | ⬜ pending |
| 259-01-04 | 01 | 1 | INSPECT-03 | — | `ownership_inspection` key present in health; `route_management` shape bit-identical | unit (regression) | `.venv/bin/pytest -o addopts='' tests/test_steering_health.py -k "ownership or route_management" -q` | partial — extend existing | ⬜ pending |
| 259-01-05 | 01 | 1 | INSPECT-03 | — | health handler reads cached result only; never calls `run_cmd` on request path | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -k cache -q` | ❌ W0 | ⬜ pending |
| 259-01-06 | 01 | 1 | SAFE-21 | T-SAFE21 | All issued commands contain `print`; none contain `enable`/`disable`/`set`/`add`/`remove` | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -k read_only -q` | ❌ W0 | ⬜ pending |
| 259-01-07 | 01 | 1 | SAFE-21 + D4 | T-SAFE21 | Fail-open: router error → `inspector_status="error"`, `observed_owner="unknown"`, `match=false`, health stays up | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_inspector.py -k fail_open -q` | ❌ W0 | ⬜ pending |
| 259-01-08 | 01 | 1 | SAFE-21 live | T-SAFE21 | `phase259-ownership-proof.py` mock: mutation rejection before live call; harness happy path | unit | `.venv/bin/pytest -o addopts='' tests/test_phase259_ownership_proof.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_route_ownership_inspector.py` — attribution, fail-open, thread/cache, read-only command assertion (covers INSPECT-01/02, SAFE-21, D4)
- [ ] `tests/test_route_ownership_inspector_rest.py` — over-mocked-`RouterOSREST` integration; confirms `request` method only sees GET (mirror `test_route_ownership_guard_rest_integration.py`)
- [ ] `tests/test_phase259_ownership_proof.py` — harness mock happy-path + mutation rejection gate (mirror `test_phase258_readonly_proof.py`)
- [ ] Extend `tests/test_steering_health.py` — add `ownership_inspection` key assertion AND `route_management` shape no-regression check

*No new framework install needed — pytest and ruff already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `INSPECT_PROOF_PASS` from `/opt/wanctl` on `cake-shaper` | INSPECT-01/02/03, SAFE-21 | Requires `ROUTER_PASSWORD` + live RouterOS; credential reads are operator-at-keyboard | Kevin runs `! python3 /opt/wanctl/scripts/phase259-ownership-proof.py` after deploying; records verdict line in VERIFICATION.md |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
