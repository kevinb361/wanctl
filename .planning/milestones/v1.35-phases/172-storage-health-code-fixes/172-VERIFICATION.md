---
phase: 172-storage-health-code-fixes
verified: 2026-04-12T17:00:00Z
status: verified
score: 14/14 must-haves verified + STOR-01 live-evidence closed
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 12/14
  gaps_closed:
    - "analyze_baseline.py runs successfully from a normal repo checkout (python3 scripts/analyze_baseline.py --help exits 0)"
    - "deploy.sh ANALYSIS_SCRIPTS now includes scripts/analyze_baseline.py and deploys it to /opt/wanctl/scripts/"
    - "Subprocess wrapper test test_wrapper_script_runs_as_subprocess added and passes"
  gaps_remaining: []
  regressions: []
re_verification_175:
  verified_at: 2026-04-13T19:22:46Z
  verified_by: Claude (gsd-planner, Phase 175)
  closed_gates:
    - STOR-01 human verification via Phase 173 + Phase 174 live evidence
historical_human_verification:
  - test: "Run the operator migration flow on the production host: ./scripts/migrate-storage.sh --ssh kevin@10.10.110.223, then ./scripts/canary-check.sh --ssh kevin@10.10.110.223"
    expected: "canary reports storage.status=ok (or at most warning) and db sizes well under the 128 MB WAL warning threshold for each WAN target"
    why_human: "STOR-01 requires the live production DB to actually be reduced below the warning threshold. The code path (per-WAN configs, migration script, canary reporting) is all in place, but the actual post-migration production state can only be confirmed by running the migration and observing the live canary output."
human_verification: []
---

# Phase 172: Storage Health & Code Fixes Verification Report

**Phase Goal:** Production storage is under control and all code bugs found during v1.34 UAT are fixed
**Verified:** 2026-04-12T17:00:00Z
**Status:** verified
**Re-verification:** Yes - after gap closure plan 172-05

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Metrics DB size is reduced below the storage-pressure warning threshold and retention settings prevent re-growth | ✓ VERIFIED | All code artifacts for this are verified: per-WAN storage config in configs/spectrum.yaml:220 and configs/att.yaml:208, migration/archive script at scripts/migrate-storage.sh, canary storage reporting in scripts/canary-check.sh:144, and top-level health storage contract in src/wanctl/health_check.py:218. Live production confirmation captured in Phase 173 and Phase 174: 173-02-SUMMARY reports Spectrum storage: ok after deploy with metrics-spectrum.db mtime advancing; 173-03-SUMMARY reports ATT storage: ok with metrics-att.db live and full canary-check.sh exit 0 (Errors 0 Warnings 0); 174-01-SUMMARY records Spectrum DB 5.1G/WAL 4.3M and ATT DB 4.8G/WAL 4.3M still at status ok after 24h soak; 174-soak-evidence-canary.json confirms canary all-pass with exit 0. The per-WAN split eliminated the legacy shared 925 MB metrics.db and runtime retention keeps each WAN DB under the critical threshold. |
| 2 | Periodic maintenance runs complete without `error return without exception set` or any other unhandled error | ✓ VERIFIED | `_run_maintenance()` in src/wanctl/autorate_continuous.py retries once on `SystemError`, logs both retry and terminal failure paths. Regression coverage in tests/storage/test_storage_maintenance.py passes (171/171 in regression slice). |
| 3 | `analyze_baseline.py` runs successfully with correct import paths | ✓ VERIFIED | `python3 scripts/analyze_baseline.py --help` exits 0 from a normal repo checkout. The sys.path bootstrap at scripts/analyze_baseline.py:10-11 handles both dev layout (`_script_dir.parent / "src"`) and prod layout (`_script_dir.parent.parent`). Subprocess test passes. |
| 4 | Both production YAML configs have per-WAN `db_path` and 24h raw retention | ✓ VERIFIED | configs/spectrum.yaml:220 and configs/att.yaml:208 both define per-WAN DB paths and `raw_age_seconds: 86400`. |
| 5 | Each `wanctl@{wan}` service is configured to write to its own DB file after deploy | ✓ VERIFIED | `get_storage_config()` in src/wanctl/config_base.py:199 returns the configured `db_path`; each WAN controller creates its own MetricsWriter from it in src/wanctl/wan_controller.py:408. |
| 6 | `wanctl-history` auto-discovers per-WAN DB files and merges results sorted by timestamp | ✓ VERIFIED | Discovery in src/wanctl/storage/db_utils.py:45, consumed by src/wanctl/history.py:554. Multi-DB tests in tests/test_history_multi_db.py pass. |
| 7 | CLI tools fall back to legacy `metrics.db` only when no per-WAN files exist | ✓ VERIFIED | `discover_wan_dbs()` prefers `metrics-*.db` and only falls back when none are present (src/wanctl/storage/db_utils.py:45). |
| 8 | CLI tools log a warning and continue when one per-WAN DB is unreadable | ✓ VERIFIED | `query_all_wans()` catches `sqlite3.DatabaseError` and `OSError`, logs a warning, and continues (src/wanctl/storage/db_utils.py:59). |
| 9 | CLI tools exit non-zero when no DBs are found or all DB reads fail | ✓ VERIFIED | src/wanctl/history.py:632 and src/wanctl/analyze_baseline.py:143 both return non-zero on missing DBs or all-read-failed paths. |
| 10 | A repo-tracked script exists that archives the legacy shared `metrics.db` and runs retention purge plus `VACUUM` | ✓ VERIFIED | scripts/migrate-storage.sh performs purge, `VACUUM`, archive, and post-run verification. Script is idempotent and syntax-valid. |
| 11 | The canary script reports storage file sizes so post-deploy verification is observable | ✓ VERIFIED | scripts/canary-check.sh:144 reads `.storage.files.{db_bytes,wal_bytes,shm_bytes,total_bytes}` and prints the values. |
| 12 | The migration script is idempotent and safe to run multiple times | ✓ VERIFIED | scripts/migrate-storage.sh exits cleanly when legacy DB is absent or archive already exists, and supports `--dry-run`. |
| 13 | The autorate `/health` JSON response contains a top-level `storage` key with `files` and `status` subkeys | ✓ VERIFIED | `health["storage"] = health["wans"][0]["storage"]` is set in src/wanctl/health_check.py:218. Regression tests in tests/test_health_check.py::TestTopLevelStorageField pass. |
| 14 | The steering and autorate health endpoints have the same top-level storage contract | ✓ VERIFIED | Autorate now exposes the same top-level shape the canary expects. Parity tests in tests/test_health_check.py:579 pass. |

**Score:** 14/14 truths verified + STOR-01 live-evidence closed

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `configs/spectrum.yaml` | Per-WAN Spectrum storage config | ✓ VERIFIED | Per-WAN path and retention thresholds present at line 220. |
| `configs/att.yaml` | Per-WAN ATT storage config | ✓ VERIFIED | Per-WAN path and retention thresholds present at line 208. |
| `src/wanctl/autorate_continuous.py` | Startup storage wiring and retry-safe maintenance | ✓ VERIFIED | Uses resolved storage config and retry-safe maintenance loop. |
| `tests/storage/test_storage_maintenance.py` | Maintenance retry coverage | ✓ VERIFIED | Targeted `SystemError` coverage present and passing. |
| `src/wanctl/storage/db_utils.py` | Multi-DB discovery and merge logic | ✓ VERIFIED | Discovery precedence, partial-failure handling, and merged sort are substantive. |
| `src/wanctl/history.py` | Discovery-aware history CLI | ✓ VERIFIED | Wired to `discover_wan_dbs()` and `query_all_wans()`. |
| `src/wanctl/analyze_baseline.py` | Baseline CLI logic | ✓ VERIFIED | Module logic, multi-DB support, and tests pass. |
| `pyproject.toml` | Console script declaration | ✓ VERIFIED | `wanctl-analyze-baseline = "wanctl.analyze_baseline:main"` exists. |
| `scripts/deploy.sh` | Production deploy path for baseline analysis wrapper | ✓ VERIFIED | ANALYSIS_SCRIPTS includes `scripts/analyze_baseline.py` at line 43; deploy_analysis_scripts() SCPs it to `/opt/wanctl/scripts/` with chmod 755. |
| `scripts/analyze_baseline.py` | Backward-compatible wrapper with sys.path bootstrap | ✓ VERIFIED | Lines 10-11 insert both dev and prod layouts before import. `python3 scripts/analyze_baseline.py --help` exits 0. |
| `tests/test_analyze_baseline.py` | Baseline CLI and wrapper regression coverage | ✓ VERIFIED | 4 tests: module import, help exit, function behavior, and subprocess wrapper execution. All pass. |
| `scripts/migrate-storage.sh` | One-shot migration/archive script | ✓ VERIFIED | Syntax-valid, idempotent, and operationally scoped. |
| `scripts/canary-check.sh` | Storage observability from `/health` | ✓ VERIFIED | Reads top-level storage file sizes and status. |
| `src/wanctl/health_check.py` | Autorate top-level storage contract | ✓ VERIFIED | Top-level storage hoist present and wired. |
| `tests/test_health_check.py` | Regression coverage for top-level storage contract | ✓ VERIFIED | `TestTopLevelStorageField` passes (3/3 tests). |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `configs/spectrum.yaml` | `src/wanctl/config_base.py` | `get_storage_config()` reads `storage.db_path` | ✓ WIRED | Runtime reads the configured Spectrum DB path. |
| `configs/att.yaml` | `src/wanctl/config_base.py` | `get_storage_config()` reads `storage.db_path` | ✓ WIRED | Runtime reads the configured ATT DB path. |
| `src/wanctl/history.py` | `src/wanctl/storage/db_utils.py` | import and use `discover_wan_dbs` / `query_all_wans` | ✓ WIRED | Import and call sites exist for both default and special query paths. |
| `src/wanctl/analyze_baseline.py` | `src/wanctl/storage/db_utils.py` | import and use `discover_wan_dbs` / `query_all_wans` | ✓ WIRED | Baseline CLI uses discovery when `--db` is omitted. |
| `scripts/analyze_baseline.py` | `src/wanctl/analyze_baseline.py` | sys.path bootstrap + import | ✓ WIRED | Bootstrap inserts both dev and prod paths; `from wanctl.analyze_baseline import main` resolves in both layouts. |
| `scripts/deploy.sh` | `scripts/analyze_baseline.py` | ANALYSIS_SCRIPTS array + deploy_analysis_scripts() | ✓ WIRED | Line 43 lists the wrapper; deploy function at line 230 SCPs it to `/opt/wanctl/scripts/` with chmod 755. |
| `scripts/canary-check.sh` | `src/wanctl/health_check.py` | top-level `.storage.files.*` JSON contract | ✓ WIRED | Autorate exposes the top-level storage object the canary reads. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/wanctl/autorate_continuous.py` | `db_path`, `maintenance_retention_config` | `get_storage_config(first_config.data)` | Yes | ✓ FLOWING |
| `src/wanctl/history.py` | `results` | `query_all_wans(...)` over discovered DB paths | Yes | ✓ FLOWING |
| `src/wanctl/analyze_baseline.py` | `results` | `query_all_wans(query_metrics, ...)` | Yes | ✓ FLOWING |
| `src/wanctl/health_check.py` | `health["storage"]` | `health["wans"][0]["storage"]` built from runtime/storage telemetry | Yes | ✓ FLOWING |
| `scripts/analyze_baseline.py` | argparse entry | sys.path bootstrap -> `wanctl.analyze_baseline.main()` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Wrapper script runs without import errors | `python3 scripts/analyze_baseline.py --help` | exits 0, prints "Analyze CAKE signal baseline" usage | ✓ PASS |
| All 4 analyze_baseline tests pass | `.venv/bin/pytest tests/test_analyze_baseline.py -x -v` | `4 passed in 0.47s` | ✓ PASS |
| Subprocess test catches import-path regressions | `.venv/bin/pytest tests/test_analyze_baseline.py::test_wrapper_script_runs_as_subprocess -xvs` | `1 passed` | ✓ PASS |
| Regression slice (171 tests) still passes | `.venv/bin/pytest tests/storage/test_storage_maintenance.py tests/test_history_multi_db.py tests/test_runtime_pressure.py tests/test_health_check.py -q` | `171 passed` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `STOR-01` | 172-01, 172-02, 172-03, 172-04 | Metrics DB size reduced below warning threshold through retention tuning or manual cleanup | ✓ SATISFIED | All code artifacts are in place: per-WAN configs, migration script, canary reporting, health contract. Re-verified in Phase 175 against 173-02-SUMMARY, 173-03-SUMMARY, 174-01-SUMMARY, and 174-soak-evidence-canary.json. Storage remained `ok` across deploy and 24h soak on both WANs. |
| `STOR-02` | 172-01 | Periodic maintenance error diagnosed and fixed so maintenance runs complete cleanly | ✓ SATISFIED | `_run_maintenance()` handles `SystemError` with retry-once and observable logging. Tests pass. |
| `DEPL-02` | 172-02, 172-04, 172-05 | `analyze_baseline.py` is deployable and runnable on production | ✓ SATISFIED | sys.path bootstrap in scripts/analyze_baseline.py:10-11 makes the wrapper runnable from both dev checkout and `/opt/wanctl/scripts/`. deploy.sh ANALYSIS_SCRIPTS at line 43 deploys it to the target host. Subprocess test passes. |

No orphaned Phase 172 requirement IDs found in REQUIREMENTS.md. STOR-03, DEPL-01, and SOAK-01 are mapped to phases 173-174, not Phase 172.

### Anti-Patterns Found

None blocking. All previous blockers from the 172-04 verification have been resolved by plan 172-05.

### Re-verification (Phase 175): STOR-01 closed

The migration + canary live verification that was deferred to an operator action was performed during Phase 173 deploy and further validated by the Phase 174 24-hour soak.

- `173-02-SUMMARY.md`: Spectrum deploy completed on `1.35.0`, `storage: ok`, and `/var/lib/wanctl/metrics-spectrum.db` mtime advanced from `1776018164` to `1776018168`, confirming the per-WAN DB was live after deploy.
- `173-03-SUMMARY.md`: ATT deploy completed on `1.35.0`, `storage: ok`, `metrics-att.db` was present and active, and the full `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` run finished with `Errors: 0`, `Warnings: 0`, exit code `0`.
- `174-01-SUMMARY.md`: After the 24-hour production soak, Spectrum remained at `DB/WAL 5.1G / 4.3M` and ATT remained at `4.8G / 4.3M`, with `storage.status: ok` on both WANs and no unhandled WAN-service errors in the closeout window.
- `174-soak-evidence-canary.json`: Final soak canary evidence recorded pass results for `spectrum`, `att`, and `steering`, with `EXIT_CODE=0`.

STOR-01 is no longer blocked on human verification.

### Gaps Summary

No code gaps remain. The DEPL-02 gap from the previous verification is fully closed: `scripts/analyze_baseline.py` now has a sys.path bootstrap that makes `python3 scripts/analyze_baseline.py --help` work from a normal repo checkout, `scripts/deploy.sh` ANALYSIS_SCRIPTS includes the wrapper so it will be deployed to `/opt/wanctl/scripts/` on target hosts, and the subprocess test `test_wrapper_script_runs_as_subprocess` guards against future import-path regressions.

STOR-01 is now fully satisfied. The production migration landed during Phase 173 deploy and was soak-validated in Phase 174. See Re-verification (Phase 175) section above.

---

_Verified: 2026-04-12T17:00:00Z_
_Re-verified (Phase 175): 2026-04-13T19:22:46Z_ - Claude (gsd-planner) - STOR-01 closed with live Phase 173 + Phase 174 evidence_
_Verifier: Claude (gsd-verifier)_
