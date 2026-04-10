---
phase: 108-steering-dual-backend-observability
verified: 2026-03-25T15:57:56Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 108: Steering Dual-Backend & Observability Verification Report

**Phase Goal:** Steering daemon operates with split data sources (local CAKE stats, remote mangle rules) and per-tin stats are operator-visible
**Verified:** 2026-03-25T15:57:56Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

#### Plan 01 Truths (CONF-03, CAKE-07)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CakeStatsReader delegates to LinuxCakeBackend.get_queue_stats() when transport=linux-cake | VERIFIED | `cake_stats.py:261` — `self._linux_backend.get_queue_stats(queue_name)` called inside `_read_stats_linux_cake()` |
| 2 | CakeStatsReader still uses FailoverRouterClient when transport is rest or ssh | VERIFIED | `cake_stats.py:113` — `else: self.client = get_router_client_with_failover(config, logger)` |
| 3 | CakeStats dataclass return contract unchanged on linux-cake path | VERIFIED | `cake_stats.py:273-280` — dict converted to `CakeStats(packets, bytes, dropped, queued_packets, queued_bytes)`, all 5 fields preserved |
| 4 | Per-tin stats appear in health endpoint under congestion.primary.tins when linux-cake | VERIFIED | `health.py:191` — `health["congestion"]["primary"]["tins"] = tins_list` gated on `_is_linux_cake + last_tin_stats` |
| 5 | Health endpoint omits tins when transport is not linux-cake | VERIFIED | `health.py:169-172` — guard condition `raw_tin_stats and getattr(daemon.cake_reader, "_is_linux_cake", False)` |

#### Plan 02 Truths (CAKE-07)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | Per-tin metrics written to SQLite with tin label when linux-cake active | VERIFIED | `daemon.py:2021-2047` — 16 tuples (4 tins x 4 metrics) appended to `metrics_batch`, each with `{"tin": tin_name}` label |
| 7 | Per-tin metrics NOT written when transport is rest/ssh | VERIFIED | `daemon.py:2021-2023` — gated on `getattr(cake_reader, "_is_linux_cake", False) and cake_reader.last_tin_stats` |
| 8 | STORED_METRICS includes 4 new per-tin metric names | VERIFIED | `schema.py:32-35` — all 4 entries present: `wanctl_cake_tin_dropped`, `wanctl_cake_tin_ecn_marked`, `wanctl_cake_tin_delay_us`, `wanctl_cake_tin_backlog_bytes` |
| 9 | wanctl-history --tins displays per-tin statistics from the database | VERIFIED | `history.py:488,568-582` — `--tins` flag registered, queries `PER_TIN_METRICS`, prints `format_tins_table` or `format_tins_json` |

**Score:** 9/9 truths verified

---

### Required Artifacts

#### Plan 01 Artifacts

| Artifact | Expected | Level 1 (Exists) | Level 2 (Substantive) | Level 3 (Wired) | Status |
|----------|----------|------------------|-----------------------|-----------------|--------|
| `src/wanctl/steering/cake_stats.py` | Transport-aware CakeStatsReader | Yes | `_is_linux_cake`, `_read_stats_linux_cake`, `last_tin_stats`, `_AutorateConfigProxy` all present | Imported by daemon.py (CakeStatsReader instantiated at daemon init) | VERIFIED |
| `src/wanctl/steering/health.py` | Per-tin stats in health endpoint | Yes | `tins` key construction at line 191, `TIN_NAMES` import, 9-field dict per tin | Used by `start_steering_health_server()` called from daemon | VERIFIED |
| `tests/test_cake_stats.py` | Tests for linux-cake code path | Yes | `TestCakeStatsReaderLinuxCake` class with 8 tests | 169 tests pass | VERIFIED |
| `tests/test_steering_health.py` | Tests for per-tin health data | Yes | `TestPerTinHealth` class with 6 tests | 169 tests pass | VERIFIED |

#### Plan 02 Artifacts

| Artifact | Expected | Level 1 (Exists) | Level 2 (Substantive) | Level 3 (Wired) | Status |
|----------|----------|------------------|-----------------------|-----------------|--------|
| `src/wanctl/storage/schema.py` | 4 new STORED_METRICS entries | Yes | All 4 entries with label docs present at lines 32-35 | Imported by writer.py which validates against STORED_METRICS | VERIFIED |
| `src/wanctl/steering/daemon.py` | Per-tin batch writes in run_cycle | Yes | 16-tuple block at lines 2021-2046, gating on `_is_linux_cake` | `write_metrics_batch(metrics_batch)` called at line 2047 | VERIFIED |
| `src/wanctl/history.py` | --tins flag for per-tin history display | Yes | `--tins` flag at line 488, `PER_TIN_METRICS` constant, `format_tins_table`, `format_tins_json`, `No per-tin data found` message | `query_metrics` called from `main()` at line 568 | VERIFIED |
| `tests/test_steering_metrics_recording.py` | Tests for per-tin metric batch writes | Yes | `TestPerTinMetrics` class with 4 tests | 169 tests pass | VERIFIED |
| `tests/test_history_cli.py` | Tests for --tins flag | Yes | `TestPerTinHistory` class with 5 tests | 169 tests pass | VERIFIED |

---

### Key Link Verification

| From | To | Via | Pattern Found | Status |
|------|----|-----|---------------|--------|
| `src/wanctl/steering/cake_stats.py` | `src/wanctl/backends/linux_cake.py` | `LinuxCakeBackend.get_queue_stats()` | `cake_stats.py:261` — `self._linux_backend.get_queue_stats(queue_name)` | WIRED |
| `src/wanctl/steering/health.py` | `src/wanctl/steering/cake_stats.py` | `CakeStatsReader.last_tin_stats` | `health.py:167` — `getattr(self.daemon.cake_reader, "last_tin_stats", None)` | WIRED |
| `src/wanctl/steering/daemon.py` | `src/wanctl/storage/writer.py` | `write_metrics_batch` with per-tin tuples | `daemon.py:2031,2035,2039,2043` — `wanctl_cake_tin_*` tuples added to batch | WIRED |
| `src/wanctl/history.py` | `src/wanctl/storage/reader.py` | `query_metrics` with per-tin metric names | `history.py:568` — `query_metrics(..., metrics=PER_TIN_METRICS, ...)` | WIRED |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `health.py` per-tin tins[] | `raw_tin_stats` | `daemon.cake_reader.last_tin_stats` populated by `LinuxCakeBackend.get_queue_stats()` via `tc -j qdisc show` | Yes — `linux_cake.py` calls `tc` subprocess and parses JSON; no static fallback | FLOWING |
| `history.py` --tins table | `results` from `query_metrics` | SQLite query filtered to `wanctl_cake_tin_*` metric names written by daemon | Yes — daemon batch writes real tin data from backend | FLOWING |
| `daemon.py` per-tin metrics_batch | `cake_reader.last_tin_stats` | Set by `_read_stats_linux_cake()` from `get_queue_stats()` response | Yes — live tc data or None (skipped by gate condition) | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| --tins flag registered in CLI | `.venv/bin/python -m wanctl.history --help \| grep tins` | `--tins  Show per-tin CAKE statistics (drops, ECN, delay, backlog per tin)` | PASS |
| format_tins_table, format_tins_json, PER_TIN_METRICS exported | `python -c "from wanctl.history import format_tins_table, format_tins_json, PER_TIN_METRICS; ..."` | All 3 exported, PER_TIN_METRICS has 4 entries | PASS |
| CakeStatsReader has linux-cake attributes in __init__ | `python -c "... inspect.getsource(CakeStatsReader.__init__)"` | `_is_linux_cake=True`, `last_tin_stats=True`, `_linux_backend=True` | PASS |
| All phase 108 tests pass | `.venv/bin/pytest tests/test_cake_stats.py tests/test_steering_health.py tests/test_steering_metrics_recording.py tests/test_history_cli.py -x -q` | 169 passed in 28.49s | PASS |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CONF-03 | 108-01 | Steering daemon uses dual-backend — linux-cake for CAKE stats, REST for mangle rules | SATISFIED | `cake_stats.py` transport detection from autorate config YAML; linux-cake path uses `LinuxCakeBackend`, rest/ssh path uses `FailoverRouterClient`. Mangle rules remain on RouterOS path via `SteeringDaemon`'s main client. |
| CAKE-07 | 108-01, 108-02 | Per-tin statistics visible in health endpoint and wanctl-history | SATISFIED | `health.py` exposes `congestion.primary.tins[]` (4 tins, 9 fields each). `schema.py` registers 4 tin metrics. `daemon.py` writes 16 per-tin tuples per cycle. `history.py --tins` queries and displays the data. |

Both requirements marked Complete in REQUIREMENTS.md match implementation evidence.

---

### Anti-Patterns Found

No anti-patterns found across the 5 modified source files. No TODO/FIXME/placeholder comments. No empty implementations. No hardcoded empty data flowing to rendering.

---

### Human Verification Required

#### 1. Split Data Sources in Production

**Test:** Deploy to cake-spectrum container with linux-cake autorate config. Trigger a congestion cycle and confirm health endpoint at `http://127.0.0.1:9102/health` shows `congestion.primary.tins[]` populated with 4 tin entries, while mangle rule toggling still uses REST API to the MikroTik router.
**Expected:** tins[] array present in health JSON; MikroTik firewall address-list entries updated for steering.
**Why human:** Requires live container with tc qdiscs installed and MikroTik REST reachable — cannot verify without running infrastructure.

#### 2. wanctl-history --tins Live Output

**Test:** On a container that has been running linux-cake transport for at least one cycle interval, run `wanctl-history --tins --last 1h`.
**Expected:** Table output with Tin column showing Bulk/BestEffort/Video/Voice rows, populated with dropped, ECN, delay, backlog values.
**Why human:** Requires SQLite database with actual per-tin records written by a live daemon cycle.

---

### Gaps Summary

No gaps. All 9 must-have truths verified, all 9 artifacts pass all levels (exists, substantive, wired, data-flowing), all 4 key links confirmed wired, both requirements (CONF-03, CAKE-07) satisfied.

---

_Verified: 2026-03-25T15:57:56Z_
_Verifier: Claude (gsd-verifier)_
