---
phase: 244
slug: health-payload-attribution-metadata
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 244 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `244-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/pytest`); ruff + mypy for lint/type |
| **Config file** | `pyproject.toml` (has `addopts`; SAFE-17 verifiers run with `-o addopts=''`) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_phase244_safe17_verifier.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~15-30 seconds (focused slices); full suite longer |

> **NOTE:** the full suite carries ~34 pre-existing stale-boundary failures (SAFE-17 pinning
> caveat). Do **not** gate Phase 244 on full-suite green. Gate on the focused contract tests
> plus `phase244-safe17-boundary-check.sh`.

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_phase244_safe17_verifier.py -q`
- **After every plan wave:** Hot-path slice + both bridge artifact tests + `bash scripts/phase244-safe17-boundary-check.sh`
- **Before `/gsd:verify-work`:** Focused contract tests green AND `phase244-safe17-boundary-check.sh` passes
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| W0 verifier | TBD | 0 | SAFE-17 | — | Out-of-allowlist control-path drift rejected; control bodies byte-identical | script + unit | `bash scripts/phase244-safe17-boundary-check.sh` ; `.venv/bin/pytest -o addopts='' tests/test_phase244_safe17_verifier.py -q` | ❌ W0 | ⬜ pending |
| W0 steering test | TBD | 0 | HEALTH-01 | — | Steering `rtt_source` triple asserted | unit | `.venv/bin/pytest -o addopts='' tests/test_steering_health*.py -q` | ❌ W0 | ⬜ pending |
| W0 contract snapshot | TBD | 0 | HEALTH-01 | — | Existing measurement keys+types pinned; new keys strict-superset | unit/contract | `.venv/bin/pytest -o addopts='' tests/test_health_check.py -k "measurement or backend or contract" -q` | ✅ extend | ⬜ pending |
| Autorate surface | TBD | 1 | HEALTH-01 | — | `measurement` adds `producer`/`backend`/`source_ip`; existing byte-preserved | unit/contract | `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` | ✅ extend | ⬜ pending |
| Steering surface | TBD | 1 | HEALTH-01 | — | `rtt_source` adds the triple; daemon carries handle/source_ip | unit | `.venv/bin/pytest -o addopts='' tests/test_steering_health*.py -q` | ❌ W0 | ⬜ pending |
| Bridge surface | TBD | 1 | HEALTH-01 | — | `producer="cake-autorate-bridge"`, `backend=null`, `source_ip=null`; existing preserved | integration | `.venv/bin/pytest -o addopts='' tests/test_spectrum_cake_autorate_artifacts.py tests/test_att_cake_autorate_artifacts.py -q` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/phase244-safe17-boundary-check.sh` — cloned from `phase242`, anchor advanced to the resolved 243-close SHA, protected-body exception widened to the health builders, allowlist regex extended with `steering/health\.py` iff that file is touched.
- [ ] `tests/test_phase244_safe17_verifier.py` — mirror of `test_phase243_safe17_verifier.py`, pinned to the resolved 243-close anchor (NOT HEAD).
- [ ] Steering health test coverage for the attribution triple (confirm `tests/test_steering_health*.py` exists or add it; the daemon handle/source_ip carry needs a test).
- [ ] Contract-snapshot assertion in `tests/test_health_check.py` pinning existing keys+types and asserting strict-superset.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `/health` emits the triple on the production hosts | HEALTH-01 | Requires live prod hosts (both WANs on cake-autorate bridge) | `ssh <host> 'curl -s http://127.0.0.1:9101/health \| python3 -m json.tool'` — confirm `producer`/`backend`/`source_ip` present and existing fields unchanged |

*Live verification is post-merge / deploy-time; not a planning gate.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (SAFE-17 verifier + mirror test + steering test)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
