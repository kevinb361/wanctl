# Phase 162: Baseline Measurement - Research

**Researched:** 2026-04-10
**Domain:** CAKE signal baseline collection, idle drop rate/backlog measurement, health endpoint observability
**Confidence:** HIGH

## Summary

Phase 162 establishes a ground-truth idle baseline for CAKE drop rate and backlog before any v1.33 threshold tuning begins. The v1.32 milestone (Phases 159-161) built the complete CAKE signal infrastructure: per-tin netlink stats, EWMA-smoothed drop rate, backlog/peak_delay signals, health endpoint exposure, metrics DB storage, and detection logic (dwell bypass, backlog suppression, refractory periods, exponential probing). Phase 162 does not add new code features -- it enables the existing infrastructure in production, collects 24 hours of idle data, and verifies that the current thresholds do not cause false-positive detection events at rest.

The key concern: the `cake_signal` YAML config section is **absent from the git-tracked `configs/spectrum.yaml`**. The v1.32 code defaults to `CakeSignalConfig(enabled=False)` when the section is missing. To collect baseline data, two flags must be enabled: `enabled: true` (master switch) and `metrics_enabled: true` (DB persistence). The detection flags (`drop_rate_enabled`, `backlog_enabled`) should remain `false` during baseline -- we are measuring, not acting. Once the 24h window completes, the data can be queried via the existing `wanctl-history` CLI (`--last 24h --metrics wanctl_cake_drop_rate,wanctl_cake_backlog_bytes --summary`) or the `/metrics/history` HTTP endpoint, and analyzed using the existing `compute_summary()` function to produce mean/p50/p99 statistics.

**Primary recommendation:** Add a `cake_signal:` section to `configs/spectrum.yaml` with `enabled: true` and `metrics_enabled: true` (all detection booleans `false`), deploy to production via `deploy.sh`, verify data flows via health endpoint, wait 24h, then query and record baseline statistics. Write a small analysis script to automate the summary computation.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VALID-02 | Baseline drop rate and backlog measured at idle for 24h before any tuning begins | CAKE signal infrastructure fully built (P159-161). Enabling `cake_signal.enabled=true` + `metrics_enabled=true` starts data collection. `wanctl_cake_drop_rate` and `wanctl_cake_backlog_bytes` metrics written every cycle (50ms) to metrics.db. `wanctl-history --last 24h --summary` computes mean/p50/p99. Health endpoint `/health` shows real-time cake_signal section. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12 | Statistics computation (mean, quantiles) | Already used by compute_summary() in storage/reader.py [VERIFIED: source code] |
| wanctl.cake_signal | local | CakeSignalProcessor, CakeSignalConfig | Phase 159 output, production-ready [VERIFIED: src/wanctl/cake_signal.py] |
| wanctl.storage.reader | local | query_metrics(), compute_summary() | Existing reader with mean/p50/p95/p99 stats [VERIFIED: src/wanctl/storage/reader.py] |
| wanctl.history | local | wanctl-history CLI | Existing CLI with --summary mode [VERIFIED: src/wanctl/history.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Unit tests | Already in dev deps [VERIFIED: pyproject.toml] |
| sqlite3 | stdlib | Metrics DB queries | Already used throughout storage layer [VERIFIED: storage/reader.py] |
| jq | system | Health endpoint JSON parsing | Already used in soak-monitor.sh [VERIFIED: scripts/soak-monitor.sh] |

**No new dependencies required.** All baseline collection uses existing infrastructure.

## Architecture Patterns

### Data Flow: Idle Baseline Collection

```
LinuxCakeAdapter.dl_backend.get_queue_stats()   [netlink, 0.3ms]
  -> CakeSignalProcessor.update()                [EWMA smoothing]
  -> CakeSignalSnapshot (drop_rate, backlog_bytes, peak_delay_us)
     -> WANController._dl_cake_snapshot          [per-cycle storage]
     -> health endpoint: /health -> cake_signal.download  [real-time]
     -> metrics batch: wanctl_cake_drop_rate, wanctl_cake_backlog_bytes  [DB]
```

### YAML Config Section Required

The `cake_signal` section is **currently absent** from `configs/spectrum.yaml`. It must be added to enable data collection. The parser in `wan_controller.py:_parse_cake_signal_config()` reads from the `cake_signal:` top-level key in the YAML file.

```yaml
# CAKE signal processing (v1.32+, Phase 159-161)
cake_signal:
  enabled: true              # Master switch - enables reading stats every cycle
  metrics_enabled: true      # Persist to metrics.db (needed for 24h baseline)
  drop_rate_enabled: false   # Detection DISABLED during baseline
  backlog_enabled: false     # Detection DISABLED during baseline
  peak_delay_enabled: false  # Not yet integrated
  time_constant_sec: 1.0     # EWMA time constant (default)
  # Detection thresholds (defaults, not active during baseline)
  detection:
    drop_rate_threshold: 10.0     # drops/sec [VERIFIED: CakeSignalConfig default]
    backlog_threshold_bytes: 10000  # bytes [VERIFIED: CakeSignalConfig default]
    refractory_cycles: 40          # cycles [VERIFIED: CakeSignalConfig default]
  # Recovery parameters (defaults, not active during baseline)
  recovery:
    probe_multiplier: 1.5
    probe_ceiling_pct: 0.9
```

[VERIFIED: config parsing at wan_controller.py lines 632-718]

### Metrics Written Per Cycle (when enabled + metrics_enabled)

Per direction (download and upload), each cycle writes 4 metrics:
- `wanctl_cake_drop_rate` (EWMA drops/sec, excludes Bulk tin) with label `{"direction": "download"}`
- `wanctl_cake_total_drop_rate` (all tins including Bulk) with label `{"direction": "download"}`
- `wanctl_cake_backlog_bytes` (sum of BestEffort+Video+Voice backlog) with label `{"direction": "download"}`
- `wanctl_cake_peak_delay_us` (max peak delay across BestEffort+Video+Voice) with label `{"direction": "download"}`

At 20Hz (50ms cycle), this is **8 metric rows per cycle** (4 DL + 4 UL), or **160 rows/sec**, or **~13.8M rows in 24h**. The deferred I/O worker batches these efficiently. [VERIFIED: wan_controller.py lines 2412-2438]

**DB size concern:** At ~13.8M raw rows for CAKE metrics alone (plus existing RTT metrics), the hourly downsampling/cleanup maintenance cycle will aggregate older data. The `select_granularity()` function returns `"1m"` for 24h queries, which reduces the result set by ~1200x. [VERIFIED: storage/reader.py lines 400-430]

### Querying Baseline Data

Three approaches exist in the codebase:

1. **wanctl-history CLI** (on production host):
   ```bash
   wanctl-history --last 24h --metrics wanctl_cake_drop_rate,wanctl_cake_backlog_bytes --summary --wan spectrum
   ```
   This uses `compute_summary()` which returns min/max/avg/p50/p95/p99. [VERIFIED: history.py:181-232]

2. **Health endpoint** (real-time snapshot):
   ```bash
   curl -s http://10.10.110.223:9101/health | jq '.wans[0].cake_signal'
   ```
   Shows current cycle's drop_rate, backlog_bytes, detection state. [VERIFIED: health_check.py:488-531]

3. **Metrics history API** (HTTP):
   ```bash
   curl -s "http://10.10.110.223:9101/metrics/history?range=24h&metrics=wanctl_cake_drop_rate&wan=spectrum"
   ```
   Returns JSON with pagination. [VERIFIED: health_check.py:647-706]

### Pattern: Baseline Analysis Script

A small analysis script should:
1. Query 24h of `wanctl_cake_drop_rate` and `wanctl_cake_backlog_bytes` from metrics.db
2. Compute mean, p50, p99 using `compute_summary()`
3. Check for any `wanctl_state` transitions (detection events) during the window
4. Output results in a format suitable for recording in the phase summary

```python
# Source: proposed pattern based on existing storage/reader.py
from wanctl.storage.reader import query_metrics, compute_summary

# Query 24h window
results = query_metrics(
    db_path="/var/lib/wanctl/metrics.db",
    start_ts=start_ts,
    end_ts=end_ts,
    metrics=["wanctl_cake_drop_rate", "wanctl_cake_backlog_bytes"],
    wan="spectrum",
)

# Separate by metric name and direction
dl_drop_rates = [r["value"] for r in results
                 if r["metric_name"] == "wanctl_cake_drop_rate"
                 and '"download"' in (r["labels"] or "")]
dl_backlog = [r["value"] for r in results
              if r["metric_name"] == "wanctl_cake_backlog_bytes"
              and '"download"' in (r["labels"] or "")]

print("DL Drop Rate:", compute_summary(dl_drop_rates))
print("DL Backlog:", compute_summary(dl_backlog))
```

### Anti-Patterns to Avoid

- **Enabling detection during baseline:** Setting `drop_rate_enabled: true` or `backlog_enabled: true` would cause CAKE signals to alter rate decisions during the measurement window, contaminating the baseline. Detection must stay disabled.
- **Querying raw granularity for 24h:** A 24h query at raw granularity would return ~13.8M CAKE metric rows. Always use `--summary` mode or let `select_granularity()` auto-select `1m` aggregation.
- **Assuming zero drops at idle:** CAKE's Cobalt AQM may produce sporadic drops even at idle due to memory management or background traffic. The baseline exists to measure this noise floor, not to assume it's zero.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Summary statistics | Custom mean/percentile code | `compute_summary()` from `storage/reader.py` | Already handles empty/single-value edge cases [VERIFIED: reader.py:345-397] |
| Metrics querying | Direct SQLite queries | `query_metrics()` from `storage/reader.py` | Read-only connection, proper index usage, label parsing [VERIFIED: reader.py:19-99] |
| Time range parsing | Custom duration parser | `parse_duration()` from `history.py` or `_parse_duration()` from `health_check.py` | Already validated and tested [VERIFIED: history.py:38-64] |
| Health data formatting | Custom JSON builder | `_build_cake_signal_section()` in `health_check.py` | Already rounds, handles None, includes per-tin detail [VERIFIED: health_check.py:488-531] |

## Common Pitfalls

### Pitfall 1: Metrics Not Written Because metrics_enabled Is False
**What goes wrong:** CAKE stats are read and exposed via health endpoint, but not persisted to metrics.db.
**Why it happens:** The metrics write path is gated by `self._dl_cake_signal.config.metrics_enabled` (wan_controller.py:2413). Setting `enabled: true` alone is insufficient.
**How to avoid:** Always set both `enabled: true` AND `metrics_enabled: true` in the YAML config.
**Warning signs:** Health endpoint shows live cake_signal data, but `wanctl-history --metrics wanctl_cake_drop_rate` returns no results.

### Pitfall 2: deploy.sh Syncs Config -- Diff Before Deploying
**What goes wrong:** `deploy.sh` syncs the entire `configs/` directory to `/etc/wanctl/`. If other config changes were made directly on production (not in git), they could be overwritten.
**Why it happens:** Standard deploy path uses rsync.
**How to avoid:** Always `diff` production config against git config before running deploy.sh. [VERIFIED: user memory feedback_diff_config_before_deploy.md]
**Warning signs:** Unexpected config changes in journal logs after deploy.

### Pitfall 3: DB Size Growth at 20Hz
**What goes wrong:** 24h of raw CAKE metrics at 20Hz generates ~13.8M rows (8 metrics/cycle x 20 cycles/sec x 86400 sec). This could stress the hourly maintenance cycle.
**Why it happens:** Existing hourly maintenance (downsample + cleanup + VACUUM) may take longer with the additional volume.
**How to avoid:** Monitor DB size during the first few hours. The downsampler aggregates raw data older than 6h into 1m buckets, which will manage growth. If needed, the `memlimit` for the deferred I/O worker handles batching.
**Warning signs:** Watchdog timeout during hourly maintenance, growing disk usage.

### Pitfall 4: SIGUSR1 Reload Required After Config Change
**What goes wrong:** Adding the `cake_signal` section to the YAML on disk does not take effect until the service is restarted or receives SIGUSR1.
**Why it happens:** Config is read at startup and on SIGUSR1. No file-watch mechanism.
**How to avoid:** After deploying the new config via deploy.sh, either restart the service or send SIGUSR1. deploy.sh typically restarts the service.
**Warning signs:** Health endpoint still shows `cake_signal: null` after config deployment.

### Pitfall 5: Cold Start Suppresses First Cycle
**What goes wrong:** First cycle after enabling CAKE signal always produces `cold_start: true` with `drop_rate: 0.0`. This is by design but could confuse initial verification.
**Why it happens:** `CakeSignalProcessor.update()` needs a previous counter value for delta computation. First call stores counters and returns zero-rate snapshot. [VERIFIED: cake_signal.py:213-248]
**How to avoid:** Expect the first health endpoint read after enable to show `cold_start: true`. The second cycle onward shows real data.

## Code Examples

### Verifying CAKE Signal is Active (post-deploy)

```bash
# Source: existing soak-monitor.sh pattern [VERIFIED: scripts/soak-monitor.sh:79-81]
ssh kevin@10.10.110.223 'curl -s http://10.10.110.223:9101/health' | \
  jq '.wans[0].cake_signal'
```

Expected output when enabled:
```json
{
  "download": {
    "drop_rate": 0.0,
    "total_drop_rate": 0.0,
    "backlog_bytes": 0,
    "peak_delay_us": 0,
    "cold_start": false,
    "tins": [...]
  },
  "upload": { ... },
  "detection": {
    "dl_refractory_remaining": 0,
    "ul_refractory_remaining": 0,
    "refractory_cycles": 40,
    "dl_dwell_bypassed_count": 0,
    "ul_dwell_bypassed_count": 0,
    "dl_backlog_suppressed_count": 0,
    "ul_backlog_suppressed_count": 0,
    ...
  }
}
```

### Querying 24h Baseline (after collection window)

```bash
# Source: existing wanctl-history CLI [VERIFIED: history.py:433-534]
# Run on production host (has access to /var/lib/wanctl/metrics.db)
ssh kevin@10.10.110.223 'cd /opt/wanctl && \
  python3 -m wanctl.history --last 24h \
    --metrics wanctl_cake_drop_rate,wanctl_cake_backlog_bytes \
    --wan spectrum --summary'
```

### Checking for Detection Events During Baseline

```bash
# Source: existing wanctl-history CLI [VERIFIED: history.py]
# Any state transitions during the 24h window indicate false positives
ssh kevin@10.10.110.223 'cd /opt/wanctl && \
  python3 -m wanctl.history --last 24h \
    --metrics wanctl_state --wan spectrum'
```

Detection event counters are also available in real-time:
```bash
ssh kevin@10.10.110.223 'curl -s http://10.10.110.223:9101/health' | \
  jq '.wans[0].cake_signal.detection | {
    dl_dwell_bypassed: .dl_dwell_bypassed_count,
    ul_dwell_bypassed: .ul_dwell_bypassed_count,
    dl_backlog_suppressed: .dl_backlog_suppressed_count,
    ul_backlog_suppressed: .ul_backlog_suppressed_count
  }'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RTT-only congestion detection | RTT + CAKE queue signal detection | v1.32 (2026-04-10) | CAKE drops/backlog augment RTT-based zone classification |
| No CAKE metrics in DB | Per-cycle CAKE metrics stored | v1.32 Phase 159 | Enables retrospective analysis like this baseline phase |
| Manual threshold selection | A/B testing with baseline reference | v1.26 pattern (2026-04-02) | Data-driven parameter selection, not guesswork |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 with xdist + timeout |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_cake_signal.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VALID-02 | CAKE metrics written to DB when enabled+metrics_enabled | unit | `.venv/bin/pytest tests/test_wan_controller.py -k cake -v` | Existing |
| VALID-02 | Health endpoint shows cake_signal section | unit | `.venv/bin/pytest tests/test_health_check.py -k cake -v` | Existing |
| VALID-02 | compute_summary returns mean/p50/p99 | unit | `.venv/bin/pytest tests/test_metrics_reader.py -k summary -v` | Existing |
| VALID-02 | No detection events at idle (manual observation) | manual-only | Check health endpoint detection counters after 24h | N/A |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_cake_signal.py tests/test_health_check.py -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** 24h production observation + health endpoint verification

### Wave 0 Gaps
None -- existing test infrastructure covers all code paths. The core validation for VALID-02 is a production observation (24h idle measurement), not a unit test.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cake_signal` YAML section is absent from production `/etc/wanctl/spectrum.yaml` (same as git-tracked config) | Architecture Patterns | LOW -- if already present, skip config step; health endpoint check will reveal |
| A2 | Idle drop rate will be near zero (CAKE not dropping at rest) | Summary | MEDIUM -- if idle drops are high, thresholds may need immediate adjustment before Phase 163 |
| A3 | Hourly maintenance cycle handles the additional 13.8M raw rows per 24h | Common Pitfalls | LOW -- downsampler already handles RTT/state metrics at same frequency; CAKE adds ~4x volume |

## Open Questions (RESOLVED)

1. **What is the current detection counter state?** — RESOLVED: Check health endpoint in Task 2 pre-deploy step. If cake_signal already shows data, adjust accordingly. If disabled (expected), counters will be 0.

2. **Should the analysis script be a standalone tool or inline commands?** — RESOLVED: Standalone analysis script chosen (`scripts/analyze_baseline.py`) for richer output format and reuse in Phase 163 comparison.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| cake-shaper VM (10.10.110.223) | Production data collection | Must verify via SSH | VM 206 | None -- production host is required |
| wanctl v1.32+ | CAKE signal infrastructure | Must verify via health endpoint | Expected 1.32.2 | None -- must have v1.32+ deployed |
| jq | Health endpoint parsing | Likely available | -- | Python JSON parsing fallback in soak-monitor.sh |
| wanctl-history CLI | Baseline analysis | Bundled with wanctl | -- | Direct SQLite queries |

**Missing dependencies with no fallback:**
- None expected -- all infrastructure was deployed in v1.32.

## Project Constraints (from CLAUDE.md)

- **Conservative changes:** Production network system. Explain before changing.
- **Never refactor core logic** without approval. This phase adds config only, no core changes.
- **Priority:** stability > safety > clarity > elegance
- **Diff production config before deploy** (memory: feedback_diff_config_before_deploy.md)
- **Always bump version** on deploy (memory: feedback_always_bump_version.md) -- not needed here since no code changes
- **Verify transport backend** before tuning (memory: feedback_verify_transport_before_tuning.md) -- linux-cake confirmed
- **Skip tests for config-only changes** (memory: feedback_skip_tests_config.md) -- this phase is config + observation
- **project-finalizer mandatory** before commits

## Sources

### Primary (HIGH confidence)
- `src/wanctl/cake_signal.py` -- CakeSignalProcessor, CakeSignalConfig, EWMA computation
- `src/wanctl/wan_controller.py` -- CAKE config parsing (lines 632-718), metrics write path (lines 2412-2438), health data (lines 3049-3066)
- `src/wanctl/health_check.py` -- `_build_cake_signal_section()` (lines 488-531)
- `src/wanctl/storage/reader.py` -- `query_metrics()`, `compute_summary()`, `select_granularity()`
- `src/wanctl/history.py` -- CLI with --summary mode
- `configs/spectrum.yaml` -- current production config (no cake_signal section)

### Secondary (MEDIUM confidence)
- `.planning/milestones/v1.32-phases/159-cake-signal-infrastructure/159-RESEARCH.md` -- Phase 159 design context
- `.planning/milestones/v1.32-phases/160-congestion-detection/160-RESEARCH.md` -- Phase 160 detection design
- `.planning/milestones/v1.32-phases/161-adaptive-recovery/161-VERIFICATION.md` -- v1.32 verification confirms all wired

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all infrastructure exists, verified in source code
- Architecture: HIGH -- data flow verified through source, config parsing confirmed
- Pitfalls: HIGH -- based on known codebase patterns and user memory items

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable infrastructure, no expected changes)
