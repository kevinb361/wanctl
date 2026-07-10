# Graph Report - wanctl  (2026-04-27)

## Corpus Check
- 256 files · ~497,482 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 14597 nodes · 56874 edges · 69 communities detected
- Extraction: 29% EXTRACTED · 71% INFERRED · 0% AMBIGUOUS · INFERRED: 40151 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 77|Community 77]]

## God Nodes (most connected - your core abstractions)
1. `WANController` - 2467 edges
2. `Config` - 1524 edges
3. `MetricsWriter` - 1194 edges
4. `BaseConfig` - 919 edges
5. `SteeringDaemon` - 914 edges
6. `IRTTResult` - 880 edges
7. `CakeSignalSnapshot` - 871 edges
8. `SteeringConfig` - 804 edges
9. `BaselineLoader` - 802 edges
10. `HealthCheckHandler` - 765 edges

## Surprising Connections (you probably didn't know these)
- `Tests for RateLimiter class in rate_utils module - rate limiting for configurati` --uses--> `RateLimiter`  [INFERRED]
  tests/test_rate_limiter.py → src/wanctl/rate_utils.py
- `Tests for can_change method.` --uses--> `RateLimiter`  [INFERRED]
  tests/test_rate_limiter.py → src/wanctl/rate_utils.py
- `Test that changes are allowed when no prior changes.` --uses--> `RateLimiter`  [INFERRED]
  tests/test_rate_limiter.py → src/wanctl/rate_utils.py
- `Test that changes are allowed when under limit.` --uses--> `RateLimiter`  [INFERRED]
  tests/test_rate_limiter.py → src/wanctl/rate_utils.py
- `Test that changes are blocked when at limit.` --uses--> `RateLimiter`  [INFERRED]
  tests/test_rate_limiter.py → src/wanctl/rate_utils.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.0
Nodes (1530): AsymmetryAnalyzer, AsymmetryResult, Config, _configure_controller_flags(), Execute one adaptive tuning pass across all WAN controllers., Handle SIGUSR1 config reload. Returns updated retention config and interval., Force-save state for all WANs (preserve EWMA/counters on shutdown)., Stop IRTT thread, background RTT threads, and persistent pools. (+1522 more)

### Community 1 - "Community 1"
Cohesion: 0.0
Nodes (942): Whether alerting is enabled., Total number of alerts fired (not suppressed) since startup., analyze_baseline(), Query and summarize CAKE signal baseline metrics., OWD asymmetric congestion detection from IRTT burst measurements.  Analyzes send, Log direction transitions at INFO, suppress repeated states., Directional congestion detection result from IRTT OWD analysis., Compute directional congestion from IRTT send/receive delay medians.      Args: (+934 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (953): AlertEngine, Fire an alert event, subject to enabled gates and cooldown suppression., Check if (type, wan) is still within cooldown window.          Args:, Persist alert event to SQLite alerts table.          Never raises -- logs warnin, Return active cooldowns with seconds remaining.          Returns:             Di, Core alert engine with per-event cooldown suppression and SQLite persistence., Initialize the alert engine.          Args:             enabled: Master switch., Enable a firewall/mangle rule by comment.          Used by the steering system (+945 more)

### Community 3 - "Community 3"
Cohesion: 0.0
Nodes (867): parse_args(), _parse_autorate_args(), _colorize(), create_parser(), format_json(), main(), _print_prerequisites(), Bufferbloat benchmarking via flent RRUL test.  Provides the ``wanctl-benchmark`` (+859 more)

### Community 4 - "Community 4"
Cohesion: 0.0
Nodes (830): main(), _init_storage(), BaseConfig, BenchmarkResult, build_result(), check_daemon_running(), check_prerequisites(), check_server_connectivity() (+822 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (707): CakeStats, CakeStatsReader, Parse CAKE stats from REST API JSON response.          Args:             out:, Parse CAKE stats from SSH CLI text response.          Args:             out:, Calculate delta from previous stats for cumulative counters.          Args:, Read CAKE stats via LinuxCakeBackend (local tc commands).          Converts th, CAKE queue statistics snapshot, Read CAKE statistics for a specific queue.          Returns delta stats since (+699 more)

### Community 6 - "Community 6"
Cohesion: 0.01
Nodes (684): Advanced tuning strategies -- fusion weight, reflector scoring, baseline bounds., Tune reflector min_score threshold from signal confidence proxy.      ADVT-02: U, Tune baseline RTT minimum bound from p5 of baseline history.      ADVT-03: Deriv, Tune baseline RTT maximum bound from p95 of baseline history.      ADVT-03: Deri, Tune fusion ICMP weight based on per-signal reliability scoring.      ADVT-01: C, tune_baseline_bounds_max(), tune_baseline_bounds_min(), tune_fusion_weight() (+676 more)

### Community 7 - "Community 7"
Cohesion: 0.01
Nodes (425): _build_summary(), _extract_cycle_utilization(), _extract_storage_section(), _load_json(), main(), _parse_metric_value(), Load and validate fusion healing parameters (Phase 119: FUSE-01 through FUSE-05), from_config() (+417 more)

### Community 8 - "Community 8"
Cohesion: 0.01
Nodes (366): ABC, AlertEngine - Per-event cooldown suppression and SQLite persistence.  Provides a, _acquire_daemon_locks(), _build_current_params(), _build_tuning_layers(), _cleanup_daemon(), _close_metrics_writer(), _close_router_connections() (+358 more)

### Community 9 - "Community 9"
Cohesion: 0.01
Nodes (307): App, DashboardApp, main(), Dashboard CLI entry point and Textual application.  Provides the wanctl-dashbo, Forward data update to the renderer and refresh display., Render via the SteeringPanel renderer., Textual Widget wrapper for StatusBar renderer.      Delegates rendering to the, Forward status update to the renderer and refresh display. (+299 more)

### Community 10 - "Community 10"
Cohesion: 0.01
Nodes (220): _notify_watchdog_with_distinction(), _run_maintenance(), _track_cycle_failures(), _run_steering_maintenance(), _aggregate_bucket(), downsample_metrics(), downsample_to_granularity(), get_downsample_thresholds() (+212 more)

### Community 11 - "Community 11"
Cohesion: 0.01
Nodes (249): _build_config_dict(), _build_config_header(), _classify_connection(), Colors, generate_config(), main(), binary_search_optimal_rate(), CalibrationResult (+241 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (71): build_runtime_section(), build_storage_section(), classify_memory_status(), classify_storage_status(), classify_swap_status(), get_storage_file_snapshot(), _max_status(), Bounded runtime and storage pressure helpers for health and metrics surfaces. (+63 more)

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (115): collect_window(), main(), print_comparison(), print_result(), Print comparison table from all recorded results., Collect latency, throughput, and state metrics for the last N minutes., Append result to the persistent results file., Print a single test result. (+107 more)

### Community 14 - "Community 14"
Cohesion: 0.02
Nodes (76): controller(), Tests for autorate structured logging and overrun detection.  Tests for WANCon, DEBUG log extra should contain state_management_ms., DEBUG log extra should contain router_communication_ms., DEBUG log extra should contain overrun boolean., overrun should be False when cycle completes within interval., overrun should be True when cycle exceeds interval., Extra field values should be rounded to 1 decimal place. (+68 more)

### Community 15 - "Community 15"
Cohesion: 0.02
Nodes (75): is_retryable_error(), measure_with_retry(), Retry utilities with exponential backoff for transient failures., Determine if an exception represents a transient/retryable error.      Retryable, Retry a check function until expected result is reached or retries exhausted., Retry a measurement function with fixed delay, falling back on exhaustion., Decorator that retries a function on transient failures with exponential backoff, retry_with_backoff() (+67 more)

### Community 16 - "Community 16"
Cohesion: 0.02
Nodes (74): check_command_success(), CommandResult, err(), extract_field_value(), extract_queue_stats(), handle_command_error(), ok(), Router command error handling utilities.  Consolidates common error handling p (+66 more)

### Community 17 - "Community 17"
Cohesion: 0.03
Nodes (87): _analyze_baseline_multi_db(), check_detection_events(), _check_detection_events_multi_db(), main(), Analyze recent CAKE signal baseline metrics from wanctl storage., Check for state transitions during the baseline window across multiple DBs., CLI entry point for baseline analysis., Check for state transitions during the baseline window. (+79 more)

### Community 18 - "Community 18"
Cohesion: 0.03
Nodes (67): ensure_directory_exists(), ensure_file_directory(), get_cake_root(), Path and file system utilities for wanctl.  Consolidates common path handling, Validate and optionally prepare a file path for use.      Args:         file_, Get the project root directory.      Uses CAKE_ROOT environment variable if se, Ensure a directory exists, creating it if necessary.      Creates parent direc, Ensure the directory containing a file exists.      Creates parent directories (+59 more)

### Community 19 - "Community 19"
Cohesion: 0.03
Nodes (52): _discover_logger(), _format_error_message(), handle_errors(), Error handling utilities for wanctl.  Provides decorators and context managers t, Context manager for safe operations with error handling.      Consolidates repet, Safely invoke a function with error handling and logging.      Provides a functi, Discover a logger from the first argument (self for methods).      Checks for co, Format an error message with template substitution.      Supports {exception} an (+44 more)

### Community 20 - "Community 20"
Cohesion: 0.04
Nodes (47): _make_controller_harness(), _make_irtt(), mock_controller(), Tests for IRTTThread background measurement coordinator and protocol correlation, Create a minimal WANController-like object for correlation testing.      Imports, Protocol correlation detection logic (IRTT-07)., ICMP/UDP ratio ~1.0 is normal., ICMP/UDP ratio > 1.5 means ICMP is throttled. (+39 more)

### Community 21 - "Community 21"
Cohesion: 0.03
Nodes (52): AutorateEvent, DailySummary, LogAnalyzer, LogParser, OutputGenerator, OverallSummary, _parse_timestamp(), _percentile() (+44 more)

### Community 22 - "Community 22"
Cohesion: 0.03
Nodes (48): Return a single parameter from a rule's config dict., autorate_config_dict(), _make_config(), mock_controller(), Tests for sustained congestion detection and recovery alerts in autorate daemon., Create a lightweight mock WANController with congestion alert attributes., Tests for download sustained congestion detection., DL zone RED for 60+ seconds fires congestion_sustained_dl with severity=critical (+40 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (43): Check if a change is allowed under current rate limits.          Removes stale, Record that a configuration change was made.          Should be called after a, Return number of changes still allowed in current window.          Useful for, Return seconds until next change is allowed (0 if available now).          Use, Tests for RateLimiter class in rate_utils module - rate limiting for configurati, Tests for record_change method., Test that record_change adds an entry., Test multiple record_change calls. (+35 more)

### Community 24 - "Community 24"
Cohesion: 0.04
Nodes (34): Unit tests for timeout configuration utilities., Test that unknown component raises ValueError., Test that component names are case-sensitive., Test that return value is always int., Test get_ping_timeout function., Test getting autorate ping timeout., Test getting steering ping timeout., Test getting calibrate ping timeout. (+26 more)

### Community 25 - "Community 25"
Cohesion: 0.07
Nodes (30): logger(), make_loader(), make_writer(), Behavioral integration tests for autorate-steering daemon state file interface., Autorate writes baseline_rtt=70.0 (above max 60.0), steering returns None., State file does not exist, steering returns (None, None) gracefully., State file contains corrupted JSON, steering returns (None, None) gracefully., Autorate writes twice (25.0 then 30.0), steering reads latest (30.0). (+22 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (24): memory_db(), Unit tests for storage schema module., Tests for STORED_METRICS constant., Test STORED_METRICS contains all expected metric names., Tests for BENCHMARKS_SCHEMA constant and benchmarks table creation., BENCHMARKS_SCHEMA is a non-empty string., Schema contains CREATE TABLE for benchmarks., Schema defines all 19 required columns. (+16 more)

### Community 27 - "Community 27"
Cohesion: 0.05
Nodes (33): check_dependencies(), integration_output_dir(), mock_autorate_config(), mock_steering_config(), pytest_addoption(), pytest_configure(), Tuning subpackage test fixtures.  Fixtures specific to tuning analyzer, applier,, Register custom markers. (+25 more)

### Community 28 - "Community 28"
Cohesion: 0.1
Nodes (19): _extract_pip_install_deps(), _load_dockerfile(), _load_pyproject(), _parse_dependency(), Contract tests for Dockerfile and runtime dependency validation.  These tests, Validate Dockerfile stays in sync with pyproject.toml., Every package from pyproject.toml dependencies appears in Dockerfile pip install, Version specs in Dockerfile match pyproject.toml exactly. (+11 more)

### Community 29 - "Community 29"
Cohesion: 0.1
Nodes (11): Tests for steering module boundary clarity (AUDIT-02).  Verifies that wanctl.s, CONFIDENCE_AVAILABLE must be True -- confidence steering is not optional., ConfidenceController must be importable directly from wanctl.steering., ConfidenceSignals must be importable directly from wanctl.steering., ConfidenceWeights must be importable directly from wanctl.steering., compute_confidence must be importable directly from wanctl.steering., Core classes must be importable from wanctl.steering., __all__ must include all confidence-based steering symbols. (+3 more)

### Community 30 - "Community 30"
Cohesion: 0.26
Nodes (11): calculate_percentages(), calculate_statistics(), generate_markdown_report(), identify_cycle_totals(), main(), parse_timing_lines(), Generate markdown analysis report.      Args:         stats: Statistics dicti, Extract timing measurements from log content.      Args:         log_content: (+3 more)

### Community 31 - "Community 31"
Cohesion: 0.31
Nodes (3): Compute delta between two u32 counters, handling wrap-around.      Returns 0 if, u32_delta(), TestU32Delta

### Community 32 - "Community 32"
Cohesion: 0.2
Nodes (5): controller(), Tests for autorate baseline RTT bounds validation.  Tests the baseline_rtt_bound, Tests for baseline_rtt_bounds constants., Verify default bounds constants are correct., TestBaselineBoundsConstants

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (9): calculate_statistics(), format_csv_output(), format_text_output(), main(), parse_timing_lines(), Format statistics as CSV.      Args:         stats: Dictionary of subsystem -, Extract timing measurements from log content.      Looks for log lines matchin, Calculate statistics for a list of samples.      Args:         samples: List (+1 more)

### Community 34 - "Community 34"
Cohesion: 0.29
Nodes (2): getCellValue(), rowComparator()

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (4): fetch_logs(), Run SSH command using password authentication, Fetch all steering logs from the past 7 days, run_ssh_command()

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Vulture whitelist -- intentional exceptions for dead code detection.  Grouped by

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Check if server is running.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Current configuration.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Update config (for SIGUSR1 reload). Recalculates alpha.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Validate a value is safe for use as a RouterOS identifier.          Used for: qu

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Validate a value is safe for use in a RouterOS mangle rule comment.          Arg

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Validate a ping host is a valid IPv4, IPv6 address, or hostname.          Preven

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Hampel filter sigma threshold.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Hampel filter window size.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Create a successful result with a value.          Args:             value: Th

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Create a failed result with an error message.          Args:             erro

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Whether the last poll was successful.

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Timestamp of the last successful poll.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Most recent successful response data.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Current polling interval in seconds.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Get the singleton instance, or None if not initialized.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Public access to database connection.          Returns:             sqlite3.C

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Reset singleton instance for testing.          This method exists ONLY for tes

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Number of items queued but not yet processed.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Whether the background thread is currently running.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Each runtime dependency from pyproject.toml is importable.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Each runtime dependency meets the minimum version from pyproject.toml.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Quick 30-second RRUL validation test.          Suitable for CI pipelines. Uses

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Standard 2-minute RRUL validation test.          Full validation with strict S

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Load profile from YAML file.          The host field can be overridden via WAN

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Start load generation, return process handle.

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Wait for completion and collect results.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Check if this tool is installed and working.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Whether controller detected congestion (any non-GREEN state).

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Provide an in-memory SQLite connection.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Provide an in-memory SQLite connection.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Create temporary database for testing.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Parse timestamp string to datetime

## Knowledge Gaps
- **1283 isolated node(s):** `Fetch all steering logs using pexpect`, `Run SSH command using password authentication`, `Fetch all steering logs from the past 7 days`, `Vulture whitelist -- intentional exceptions for dead code detection.  Grouped by`, `Parse duration string like '1h', '30m', '7d' into timedelta.      Args:` (+1278 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 34`** (8 nodes): `checkVisible()`, `debounce()`, `getCellValue()`, `on_click()`, `rowComparator()`, `sortColumn()`, `updateHeader()`, `coverage_html_cb_dd2e7eb5.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (2 nodes): `vulture_whitelist.py`, `Vulture whitelist -- intentional exceptions for dead code detection.  Grouped by`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Check if server is running.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Current configuration.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Update config (for SIGUSR1 reload). Recalculates alpha.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Validate a value is safe for use as a RouterOS identifier.          Used for: qu`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Validate a value is safe for use in a RouterOS mangle rule comment.          Arg`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Validate a ping host is a valid IPv4, IPv6 address, or hostname.          Preven`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Hampel filter sigma threshold.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Hampel filter window size.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Create a successful result with a value.          Args:             value: Th`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Create a failed result with an error message.          Args:             erro`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Whether the last poll was successful.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Timestamp of the last successful poll.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Most recent successful response data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Current polling interval in seconds.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Get the singleton instance, or None if not initialized.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Public access to database connection.          Returns:             sqlite3.C`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Reset singleton instance for testing.          This method exists ONLY for tes`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Number of items queued but not yet processed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Whether the background thread is currently running.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Each runtime dependency from pyproject.toml is importable.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Each runtime dependency meets the minimum version from pyproject.toml.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Quick 30-second RRUL validation test.          Suitable for CI pipelines. Uses`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Standard 2-minute RRUL validation test.          Full validation with strict S`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Load profile from YAML file.          The host field can be overridden via WAN`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Start load generation, return process handle.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Wait for completion and collect results.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Check if this tool is installed and working.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Whether controller detected congestion (any non-GREEN state).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Provide an in-memory SQLite connection.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Provide an in-memory SQLite connection.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Create temporary database for testing.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Parse timestamp string to datetime`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `WANController` connect `Community 0` to `Community 32`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 12`, `Community 14`, `Community 20`, `Community 22`, `Community 31`?**
  _High betweenness centrality (0.241) - this node is a cross-community bridge._
- **Why does `Config` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 12`, `Community 13`, `Community 22`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `BaseConfig` connect `Community 2` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Are the 2378 inferred relationships involving `WANController` (e.g. with `AlertEngine` and `AsymmetryAnalyzer`) actually correct?**
  _`WANController` has 2378 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1485 inferred relationships involving `Config` (e.g. with `WANController` and `WAN controller for adaptive CAKE bandwidth management.  Contains the core WANCon`) actually correct?**
  _`Config` has 1485 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1174 inferred relationships involving `MetricsWriter` (e.g. with `DiscordFormatter` and `WebhookDelivery`) actually correct?**
  _`MetricsWriter` has 1174 INFERRED edges - model-reasoned connections that need verification._
- **Are the 913 inferred relationships involving `BaseConfig` (e.g. with `RouterOSSSH` and `Shared RouterOS SSH client for executing commands on MikroTik routers.  This m`) actually correct?**
  _`BaseConfig` has 913 INFERRED edges - model-reasoned connections that need verification._