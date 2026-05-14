---
phase: 205
slug: tin-agnostic-cake-signal-allow-wash-gate
status: complete
nyquist_compliant: true
wave_0_complete: true
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
| 205-01-01 | 01 | 2 | TOPO-01 | T-205-01-01 | fixture parameterization preserves 4-tin defaults; single-tin besteffort RED behavior tests authored | unit (RED) | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalProcessorBestEffort tests/test_cake_signal.py::TestCakeSignalProcessorBestEffortStructuralOracle -v` failed as expected in Plan 01; later green after Plan 02 | ✅ | ✅ passed |
| 205-01-02 | 01 | 2 | TOPO-02 | T-205-01-02 | RED tests for allow_wash + wash emission + docsis fallback + validator allowlist authored | unit/integration (RED) | Plan 01 RED commands failed as expected; Plan 03 slices later green | ✅ | ✅ passed |
| 205-01-03 | 01 | 2 | TOPO-01, SAFE-09 | T-205-04-04 | literal diffserv4 byte-identity guard pins current numeric output | unit (GREEN invariant) | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalProcessorDiffserv4ByteIdentity -v` | ✅ | ✅ passed |
| 205-01-04 | 01 | 2 | TOPO-01,02 | T-205-01-01,02 | GREEN-invariant audit confirms source untouched and default D-08 guards still pass | scripted + unit | `git diff HEAD -- src/wanctl/` empty; D-08 guard subset green | ✅ | ✅ passed |
| 205-02-01 | 02 | 3 | TOPO-01 | T-205-02-01,02,03,04 | tin-agnostic `_active_tin_indices` helper; diffserv4 byte-identical; tin_names heuristic for besteffort | unit + replay (GREEN) | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | ✅ | ✅ passed |
| 205-03-01 | 03 | 3 | TOPO-02 | T-205-03-01,02 | strict-bool allow_wash gate; nat/autorate-ingress still unconditionally excluded | unit (GREEN) | `.venv/bin/pytest tests/test_cake_params.py -v` | ✅ | ✅ passed |
| 205-03-02 | 03 | 3 | TOPO-02 | T-205-03-03,05,07 | linux_cake wash/nowash subprocess emission including docsis fallback | unit/integration (GREEN) | `.venv/bin/pytest tests/backends/test_linux_cake.py -v` | ✅ | ✅ passed |
| 205-03-03 | 03 | 3 | TOPO-02 | T-205-03-03,05,07 | netlink_cake wash pyroute2 kwarg emission including docsis fallback | unit/integration (GREEN) | `.venv/bin/pytest tests/backends/test_netlink_cake.py -v` | ✅ | ✅ passed |
| 205-03-04 | 03 | 3 | TOPO-02 | — | `KNOWN_AUTORATE_PATHS` includes `cake_params.allow_wash` + `cake_params.wash`; no daemon startup WARN | unit (GREEN) | `.venv/bin/pytest tests/test_check_config.py::TestLinuxCakeValidation -v` | ✅ | ✅ passed |
| 205-04-01 | 04 | 4 | TOPO-01,02 | T-205-04-01,02,03,04 | SAFE-09 boundary diff scope = exactly 5 files; value-invariance grep empty; deferrals untouched; full suite + replay + hot-path green | scripted git + pytest | `SAFE-09-scope=5-OK`; full suite `4995 passed, 6 skipped, 2 deselected`; replay `48 passed, 6 skipped`; byte-identity `1 passed`; hot-path `673 passed` | n/a (audit) | ✅ passed |
| 205-04-02 | 04 | 4 | TOPO-01,02 | T-205-04-01,02,03,04 | 205-04-SUMMARY.md written and validation map finalized with wave-0 and Nyquist frontmatter flags enabled | scripted artifact check | `test -f .../205-04-SUMMARY.md && grep -q SAFE-09 .../205-04-SUMMARY.md && grep -q "wave_0_complete" .../205-VALIDATION.md` | ✅ | ✅ passed |

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
- [x] Nyquist-compliant frontmatter flag enabled

**Approval:** passed — Plan 04 closeout populated all task rows and verified the SAFE-09 boundary.
