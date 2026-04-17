---
phase: 178-retention-tightening-and-legacy-db-cleanup
verified: 2026-04-13T23:17:44Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Verify deployed DB footprint dropped versus the 2026-04-13 baseline"
    expected: "Live /var/lib/wanctl/metrics-spectrum.db and /var/lib/wanctl/metrics-att.db are materially smaller while storage.status remains explicit and non-failing"
    why_human: "Requires production DB sizes, live retained data, and host state that are not present in the repo"
  - test: "Verify deployed history readers follow the new topology end-to-end"
    expected: "wanctl-history and /metrics/history prefer per-WAN metrics-*.db files, while /var/lib/wanctl/metrics.db still reflects steering activity separately"
    why_human: "Requires running services and live DB contents; repo inspection can only verify code paths and tests"
deferred:
  - truth: "Production evidence that the footprint reduction held after rollout"
    addressed_in: "Phase 179"
    evidence: "Phase 179 goal: 'Verify in production that the new storage footprint holds and that operators can re-check it without guesswork'"
---

# Phase 178: Retention Tightening And Legacy DB Cleanup Verification Report

**Phase Goal:** Reduce the active metrics footprint safely and close out any unused legacy DB path
**Verified:** 2026-04-13T23:17:44Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Legacy `metrics.db` ambiguity is removed in repo-side code/config/docs. | ✓ VERIFIED | Steering now declares `storage.db_path: /var/lib/wanctl/metrics.db` in [configs/steering.yaml](/home/kevin/projects/wanctl/configs/steering.yaml:98); the compatibility-default intent is documented in [src/wanctl/config_base.py](/home/kevin/projects/wanctl/src/wanctl/config_base.py:133); the decision record classifies the active DB set in [178-storage-topology-decision.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-storage-topology-decision.md:8). |
| 2 | Steering storage intent is represented explicitly instead of relying on an inherited default. | ✓ VERIFIED | [configs/steering.yaml](/home/kevin/projects/wanctl/configs/steering.yaml:98) now carries the shared DB path and accompanying comments explaining the contract. |
| 3 | Cleanup scope is limited to clearly stale legacy artifacts; active DBs are not marked for speculative deletion. | ✓ VERIFIED | [178-storage-topology-decision.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-storage-topology-decision.md:42) classifies only `spectrum_metrics.db` and `att_metrics.db` as stale zero-byte candidates and explicitly excludes active DBs from cleanup. |
| 4 | The active per-WAN footprint reduction is implemented as a retention change, not a controller-behavior change. | ✓ VERIFIED | [configs/spectrum.yaml](/home/kevin/projects/wanctl/configs/spectrum.yaml:219) and [configs/att.yaml](/home/kevin/projects/wanctl/configs/att.yaml:207) reduce only storage retention; [178-retention-change-record.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md:28) states the reduction is limited to raw retention. |
| 5 | The chosen retention cut preserves the 24h aggregate window and keeps maintenance bounded. | ✓ VERIFIED | Shipped WAN configs keep `aggregate_1m_age_seconds: 86400` and `maintenance_interval_seconds: 900` in [configs/spectrum.yaml](/home/kevin/projects/wanctl/configs/spectrum.yaml:222) and [configs/att.yaml](/home/kevin/projects/wanctl/configs/att.yaml:210); tuner guardrails enforce `aggregate_1m_age_seconds >= lookback_hours * 3600` in [src/wanctl/config_validation_utils.py](/home/kevin/projects/wanctl/src/wanctl/config_validation_utils.py:68). |
| 6 | Shipped config and schema docs describe the same bounded retention contract. | ✓ VERIFIED | [docs/CONFIG_SCHEMA.md](/home/kevin/projects/wanctl/docs/CONFIG_SCHEMA.md:306) documents the 1h/24h/7d/900s profile and distinguishes production profile from universal defaults. |
| 7 | Reader paths follow the authoritative DB topology instead of hard-coding the shared legacy DB. | ✓ VERIFIED | Discovery precedence is implemented in [src/wanctl/storage/db_utils.py](/home/kevin/projects/wanctl/src/wanctl/storage/db_utils.py:1); `/metrics/history` uses that discovery path in [src/wanctl/health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:791); `wanctl-history` does the same in [src/wanctl/history.py](/home/kevin/projects/wanctl/src/wanctl/history.py:630). |
| 8 | Operator-facing validation paths remain usable after the storage-layout change. | ✓ VERIFIED | The runbook and deployment docs now point operators to `soak-monitor`, `wanctl-history`, and `/metrics/history` instead of a single guessed DB path in [docs/RUNBOOK.md](/home/kevin/projects/wanctl/docs/RUNBOOK.md:249) and [docs/DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md:72); shell syntax validates for [scripts/soak-monitor.sh](/home/kevin/projects/wanctl/scripts/soak-monitor.sh:1) and [scripts/canary-check.sh](/home/kevin/projects/wanctl/scripts/canary-check.sh:1). |
| 9 | The repo ends Phase 178 with a clear post-change verification path for DB role and footprint checks. | ✓ VERIFIED | [178-operator-verification-path.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md:31) provides read-only file inventory, storage-status, CLI-history, HTTP-history, and direct SQLite spot-check commands. |

**Score:** 9/9 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
| --- | --- | --- | --- |
| 1 | Production evidence that the smaller footprint actually holds after rollout | Phase 179 | Phase 179 goal: "Verify in production that the new storage footprint holds and that operators can re-check it without guesswork" |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-storage-topology-decision.md` | Topology decision and cleanup boundary | ✓ VERIFIED | Exists, substantive, and classifies active vs stale DB files in [178-storage-topology-decision.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-storage-topology-decision.md:8). |
| `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md` | Baseline-to-new retention delta and safety rationale | ✓ VERIFIED | Exists, substantive, and records the 24h->1h raw-retention cut plus safety boundary in [178-retention-change-record.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md:14). |
| `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md` | Repeatable operator verification path | ✓ VERIFIED | Exists, substantive, and documents topology and read-only checks in [178-operator-verification-path.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md:19). |
| `configs/steering.yaml` | Explicit steering DB role | ✓ VERIFIED | Shared DB path and intent are wired into shipped config at [configs/steering.yaml](/home/kevin/projects/wanctl/configs/steering.yaml:98). |
| `configs/spectrum.yaml` | Tightened per-WAN retention profile | ✓ VERIFIED | Shipped profile uses `raw_age_seconds: 3600` with unchanged aggregate windows at [configs/spectrum.yaml](/home/kevin/projects/wanctl/configs/spectrum.yaml:219). |
| `configs/att.yaml` | Tightened per-WAN retention profile | ✓ VERIFIED | Shipped profile mirrors Spectrum at [configs/att.yaml](/home/kevin/projects/wanctl/configs/att.yaml:207). |
| `src/wanctl/health_check.py` | `/metrics/history` reads authoritative DB set | ✓ VERIFIED | Endpoint resolves discovered DBs and preserves response metadata in [src/wanctl/health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:791). |
| `docs/RUNBOOK.md` and `docs/DEPLOYMENT.md` | Operator docs match topology and retention changes | ✓ VERIFIED | Both documents reflect the active DB set and supported verification commands in [docs/RUNBOOK.md](/home/kevin/projects/wanctl/docs/RUNBOOK.md:249) and [docs/DEPLOYMENT.md](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md:72). |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `configs/steering.yaml` | `178-storage-topology-decision.md` | explicit steering storage role | ✓ WIRED | Config and decision record both declare `metrics.db` as intentional steering storage; automated key-link check passed. |
| `configs/spectrum.yaml` + `configs/att.yaml` | `178-retention-change-record.md` | conservative footprint reduction | ✓ WIRED | Both configs use the exact 1h/24h/7d/900s profile recorded in [178-retention-change-record.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md:16); the gsd-tools failure here was a plan-path parsing issue (`configs/spectrum.yaml and configs/att.yaml` treated as one file), not a real wiring break. |
| `src/wanctl/storage/db_utils.py` | `src/wanctl/health_check.py` | discovered per-WAN DB precedence | ✓ WIRED | `discover_wan_dbs()` precedence is implemented in [src/wanctl/storage/db_utils.py](/home/kevin/projects/wanctl/src/wanctl/storage/db_utils.py:45) and consumed by `/metrics/history` in [src/wanctl/health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py:815). |
| `src/wanctl/storage/db_utils.py` | `src/wanctl/history.py` | shared reader topology | ✓ WIRED | CLI auto-discovery flows through `discover_wan_dbs()` and `query_all_wans()` in [src/wanctl/history.py](/home/kevin/projects/wanctl/src/wanctl/history.py:637). |
| `docs/RUNBOOK.md` + `docs/DEPLOYMENT.md` | `178-operator-verification-path.md` | operator verification path | ✓ WIRED | The same active DB set and verification commands appear in the decision artifact and operator docs. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/wanctl/health_check.py` | `db_paths` / `merged_results` | `discover_wan_dbs()` -> `query_all_wans(query_metrics, ...)` | Yes | ✓ FLOWING |
| `src/wanctl/history.py` | `db_paths` / `results` | `discover_wan_dbs()` -> `query_all_wans(query_metrics, ...)` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Focused regression suite for Phase 178 paths | `.venv/bin/pytest -o addopts='' tests/test_config_base.py tests/steering/test_steering_metrics_recording.py tests/storage/test_storage_maintenance.py tests/tuning/test_tuning_history_reader.py tests/test_health_check.py tests/test_history_multi_db.py tests/test_history_cli.py -q` | `435 passed in 41.09s` | ✓ PASS |
| Operator helper scripts remain syntactically valid | `bash -n scripts/soak-monitor.sh scripts/canary-check.sh` | Exit 0 | ✓ PASS |
| DB discovery prefers per-WAN DBs over legacy DB | `.venv/bin/python - <<'PY' ... discover_wan_dbs(...) ... PY` | `['metrics-att.db', 'metrics-spectrum.db']` | ✓ PASS |
| Shipped YAMLs carry the expected storage profile | `python3 - <<'PY' ... yaml.safe_load(...) ... PY` | `spectrum -> /var/lib/wanctl/metrics-spectrum.db 900 3600 86400`, `att -> /var/lib/wanctl/metrics-att.db 900 3600 86400`, `steering -> /var/lib/wanctl/metrics.db` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| STOR-05 | 178-01 | The runtime role of legacy `/var/lib/wanctl/metrics.db` is explicitly closed out as either active, ignored, or archived/retired | ✓ SATISFIED | Steering config, config-base comments, and the topology decision record explicitly retain `metrics.db` for steering in [configs/steering.yaml](/home/kevin/projects/wanctl/configs/steering.yaml:98), [src/wanctl/config_base.py](/home/kevin/projects/wanctl/src/wanctl/config_base.py:133), and [178-storage-topology-decision.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-storage-topology-decision.md:10). |
| STOR-06 | 178-02, 178-03 | Active per-WAN metrics DB footprint is materially reduced from the 2026-04-13 baseline without breaking health, canary, soak-monitor, operator-summary, or history workflows | ✓ SATISFIED (repo) | Repo-side implementation materially tightens shipped raw retention from 24h to 1h in both WAN configs and aligns history/docs/tests; actual post-rollout size reduction remains a production verification item for Phase 179. |
| STOR-07 | 178-02, 178-03 | Retention/downsampling/maintenance settings remain bounded and production-safe after the footprint reduction change | ✓ SATISFIED | Aggregate retention and maintenance cadence remain unchanged in shipped configs, and tuner compatibility is enforced in [src/wanctl/config_validation_utils.py](/home/kevin/projects/wanctl/src/wanctl/config_validation_utils.py:68). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | - | No TODO/stub/placeholder indicators found in the touched phase files | ℹ️ Info | No obvious repo-side stub indicators remain in the Phase 178 implementation path. |

### Human Verification Required

### 1. Production Footprint Re-check

**Test:** On a deployed host, run the Phase 178 read-only commands from [178-operator-verification-path.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md:33) and compare current `metrics-spectrum.db` / `metrics-att.db` sizes against the 2026-04-13 baseline captured in Phase 177.
**Expected:** Per-WAN DBs are materially smaller after the retention change, and `storage.status` remains explicit and non-failing.
**Why human:** Production DB growth and retained-window shape depend on live traffic and deployed maintenance runs, which the repo cannot observe.

### 2. Deployed Reader Topology Check

**Test:** On a deployed host, run `wanctl-history --last 1h --metrics wanctl_rtt_ms --json` and `curl -s http://127.0.0.1:9101/metrics/history?range=1h&limit=5`, then spot-check `metrics.db` separately with the read-only SQLite commands from [178-operator-verification-path.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md:55).
**Expected:** History readers return per-WAN data when `metrics-spectrum.db` and `metrics-att.db` exist, while the shared `metrics.db` still shows steering activity and is not mixed into autorate history reads.
**Why human:** This requires live services, live DB files, and the actual deployed topology.

### Gaps Summary

No repo-side implementation gaps were found for Phase 178. The remaining uncertainty is operational, not structural: the code, configs, tests, and operator docs support the intended storage topology and retention change, but the actual on-host footprint reduction and live DB behavior still need production verification.

---

_Verified: 2026-04-13T23:17:44Z_
_Verifier: Claude (gsd-verifier)_
