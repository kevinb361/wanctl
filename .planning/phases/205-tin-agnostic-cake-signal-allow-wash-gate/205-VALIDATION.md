---
phase: 205
slug: tin-agnostic-cake-signal-allow-wash-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 205 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source-of-truth detail lives in `205-RESEARCH.md` § Validation Architecture; this file is the scoreboard the executor checks against.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` + `tests/conftest.py` |
| **Quick run command** | `.venv/bin/pytest tests/test_cake_signal.py tests/test_cake_params.py -v` |
| **Hot-path slice** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **SAFE-09 boundary verifier** | `git diff 6508d68 --name-only -- src/wanctl/ \| sort -u` (must list exactly 5 files: `cake_signal.py`, `cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py` — TOPO-02 is a 4-site gate per RESEARCH §"Pitfall 1" and PATTERNS §S1) |
| **Estimated runtime** | quick ~5s · hot-path ~30s · full ~3–5min |

---

## Sampling Rate

- **After every task commit:** Run quick command (~5s).
- **After every plan wave:** Run hot-path slice (~30s).
- **Before `/gsd-verify-work`:** Full suite green AND SAFE-09 boundary verifier green.
- **Max feedback latency:** 30 seconds.

---

## Per-Task Verification Map

*Planner populates rows during plan creation; executor flips Status during execution.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 205-00-01 | 00 | 1 | TOPO-01,02 | T-205-00-01 | operator approval of SAFE-09 file allowlist expansion captured before source mutation | checkpoint:human-verify | approve | n/a (checkpoint) | ✅ complete |
| 205-00-02 | 00 | 1 | TOPO-01,02 | T-205-00-02 | ROADMAP amended (or divergence documented); VALIDATION.md + REVIEWS.md updated | scripted | `grep -c "backends/linux_cake.py" .planning/ROADMAP.md` returns >= 1 (or REJECT branch divergence note present) | n/a (artifact) | ✅ complete |
| 205-01-01 | 01 | 1 | TOPO-01 | T-205-01-01 | fixture parameterization preserves 4-tin defaults | unit (RED) | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalProcessorBestEffort tests/test_cake_signal.py::TestCakeSignalProcessorBestEffortOracle -v` | ❌ W0 | ⬜ pending |
| 205-01-02 | 01 | 1 | TOPO-02 | T-205-01-02 | RED tests for allow_wash + wash emission + validator allowlist | unit/integration (RED) | `.venv/bin/pytest tests/test_cake_params.py::TestBuildCakeParamsAllowWash tests/backends/test_linux_cake.py -k "emits_wash or emits_nowash" tests/backends/test_netlink_cake.py -k "passes_wash" tests/test_check_config.py::TestLinuxCakeValidation::test_cake_params_allow_wash_no_unknown_key_warning -v` | ❌ W0 | ⬜ pending |
| 205-02-01 | 02 | 2 | TOPO-01 | T-205-02-01,02,03 | tin-agnostic _active_tin_indices helper; diffserv4 byte-identical; tin_names heuristic for besteffort | unit + replay (GREEN) | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | ✅ (after 205-01) | ⬜ pending |
| 205-03-01 | 03 | 2 | TOPO-02 | T-205-03-01,02 | strict-bool allow_wash gate; nat/autorate-ingress still unconditionally excluded | unit (GREEN) | `.venv/bin/pytest tests/test_cake_params.py -v` | ✅ (after 205-01) | ⬜ pending |
| 205-03-02 | 03 | 2 | TOPO-02 | T-205-03-03,05,07 | wash/nowash token + pyroute2 wash kwarg emission; symmetric explicit-false | unit/integration (GREEN) | `.venv/bin/pytest tests/backends/test_linux_cake.py tests/backends/test_netlink_cake.py -v` | ✅ (after 205-01) | ⬜ pending |
| 205-03-03 | 03 | 2 | TOPO-02 | — | KNOWN_AUTORATE_PATHS includes cake_params.allow_wash + cake_params.wash; no daemon startup WARN | unit (GREEN) | `.venv/bin/pytest tests/test_check_config.py::TestLinuxCakeValidation -v` | ✅ (after 205-01) | ⬜ pending |
| 205-04-01 | 04 | 3 | TOPO-01,02 | T-205-04-01,02 | SAFE-09 boundary diff scope = exactly 5 files; value-invariance grep empty; replay byte-identical; full suite green | scripted git + pytest | `git diff 6508d68 --name-only -- src/wanctl/ \| sort -u \| wc -l` returns 5; full suite + replay + hot-path slice all green | n/a (audit) | ⬜ pending |
| 205-04-02 | 04 | 3 | — | T-205-04-03 | operator decision on ROADMAP SAFE-09 wording amendment captured | checkpoint:human-verify | (operator resume-signal) | n/a (checkpoint) | ⬜ pending |
| 205-04-03 | 04 | 3 | — | — | ROADMAP amended (or divergence documented) + 205-04-SUMMARY.md written + VALIDATION.md finalized | scripted | `test -f .planning/phases/205-*/205-04-SUMMARY.md && grep -q SAFE-09 .planning/phases/205-*/205-04-SUMMARY.md` | n/a (artifact) | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_cake_signal.py::TestCakeSignalProcessorBestEffort` — single-tin layout produces non-zero active signal (TOPO-01)
- [ ] `tests/test_cake_signal.py::TestCakeSignalProcessorBestEffortOracle` — besteffort/diffserv4 oracle equivalence on matched load profile (TOPO-01)
- [ ] `make_mock_stats` parameterized for `tin_count=1` (test infrastructure)
- [ ] `tests/test_cake_params.py::TestBuildCakeParamsAllowWash` — true/false/absent permutations + `nat`/`autorate-ingress` still excluded (TOPO-02)
- [ ] `tests/backends/test_linux_cake.py::test_initialize_cake_emits_wash` and `…_emits_nowash_on_explicit_false` (TOPO-02 integration; mirrors `no-ack-filter`)
- [ ] `tests/backends/test_netlink_cake.py::test_initialize_cake_passes_wash_kwarg` (TOPO-02 integration)
- [ ] `tests/test_check_config_validators.py` — `cake_params.allow_wash` in KNOWN_AUTORATE_PATHS allowlist (no startup WARN)

*No framework install needed; no `conftest.py` change needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SAFE-09 control-path source diff bounded to the TOPO-01 + TOPO-02 set (5 files) | SAFE-09 phase-boundary | Git topology check; not a unit assertion | `git diff 6508d68 --name-only -- src/wanctl/ \| sort -u` should print exactly 5 lines: `cake_signal.py`, `cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py` (ROADMAP amendment landed in Plan 00 Task 2 per operator approval) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
