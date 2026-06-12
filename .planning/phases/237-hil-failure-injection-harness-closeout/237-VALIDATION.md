---
phase: 237
slug: hil-failure-injection-harness-closeout
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-12
---

# Phase 237 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `237-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (+ pytest-cov, pytest-timeout) — already configured |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_silicom_test_harness.py -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (quick), full suite per existing baseline |

Static gates (run alongside tests):
- `.venv/bin/ruff check scripts/ tests/`
- `shellcheck scripts/silicom-test`
- existing `-k invariant` W-INV gate must stay green if harness touches any watchdog surface

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_silicom_test_harness.py -x -q` + `shellcheck scripts/silicom-test`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -q` (full suite; includes W-INV `-k invariant` gate)
- **Before `/gsd:verify-work`:** Full suite green + SAFE-16 JSON `controller_path_diff_count: 0`
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| HARN-01 | failover injects `disc`, captures, recovers via `conn` | unit (fake seam) | `pytest tests/test_silicom_test_harness.py::test_failover_inject_and_recover -x` | ❌ W0 |
| HARN-02 | ab-cake flips off→on→off, runs both arms | unit | `pytest tests/test_silicom_test_harness.py::test_ab_cake_runs_both_arms -x` | ❌ W0 |
| HARN-03 | chaos dispatches named scenario; no timer/cron registered | unit + static | `pytest tests/test_silicom_test_harness.py::test_chaos_dispatch_no_scheduling -x` | ❌ W0 |
| HARN-04 | trap restores ALL touched pairs on mid-run failure/signal | unit (failure injection) | `pytest tests/test_silicom_test_harness.py::test_restore_on_midrun_failure -x` ; `::test_restore_on_signal -x` | ❌ W0 |
| HARN-05 | result dir has pre/post/snapshots/raw/journal | unit | `pytest tests/test_silicom_test_harness.py::test_result_dir_layout -x` | ❌ W0 |
| DEPLOY-03 | deploy.sh standalone installs silicom-test + scenarios; artifacts repo-owned | unit (source asserts) | `pytest tests/test_silicom_bypass_cli.py -k deploy -q` (extend) | ⚠️ extend |
| SAFE-16 | controller-path zero-diff vs v1.51 at boundary + close | evidence (git read-only) | `bash scripts/phase237-safe16-boundary-check.sh --anchor v1.51` → assert JSON | ❌ W0 (tool copy) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_silicom_test_harness.py` — covers HARN-01..05 with a fake `silicom-bypass` seam (mirror `_fake_bpctl`/`_run`/`_calls_for` from `tests/test_silicom_bypass_cli.py`)
- [ ] `scripts/phase237-safe16-boundary-check.sh` — copy/parameterize `phase225-safe13-boundary-check.sh` with `--anchor v1.51` and the 237 evidence out-path
- [ ] Extend `SILICOM_BYPASS_ARTIFACTS` / `test_artifacts_repo_owned` in `tests/test_silicom_bypass_cli.py` to include `scripts/silicom-test` + scenarios once DEPLOY-03 wiring lands
- [ ] (no framework install needed — pytest already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live-WAN failover restores NIC mode after real cable-pull simulation | HARN-01 / HARN-04 | Requires live Silicom hardware + production WAN; behind operator gate | Operator runs `silicom-test failover <pair>` on the host behind the explicit live-WAN gate; confirm `silicom-bypass status` shows NIC mode on all pairs post-run |
| ab-cake A/B comparison reflects real CAKE vs raw-ISP latency on same minute/client | HARN-02 | Needs live netperf + production link; numeric comparison is environment-dependent | Operator runs `silicom-test ab-cake <pair>`; inspect result dir A/B raw output |
| SAFE-16 zero-diff at milestone close | SAFE-16 | Close-time boundary check against shipped commits | Re-run `phase237-safe16-boundary-check.sh --anchor v1.51` at milestone close; assert `controller_path_diff_count: 0` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
