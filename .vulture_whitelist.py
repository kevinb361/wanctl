"""Vulture whitelist -- known false positives for wanctl dead code analysis.

These items appear unused to static analysis but are reachable through:
- Python protocol methods (__exit__, signal handlers) requiring specific signatures
- Runtime configuration (transport mode selection)
- Lazy/conditional imports
- Inter-process communication (autorate -> steering via state files)
- Test-only utilities
- Signal handler chains (SIGUSR1 reload)
- Framework lifecycle methods (Textual TUI, BaseHTTPRequestHandler)
- SQLite row_factory attribute assignment
- NamedTuple field declarations

See .planning/research/PITFALLS.md for detailed rationale.

Generated: 2026-03-26
Tool: vulture 2.16
"""

# =============================================================================
# PYTHON PROTOCOL: __exit__ and signal handler parameters (100% confidence)
# These are REQUIRED by Python's context manager and signal handler protocols.
# The parameters must exist in the signature even if not referenced in the body.
# =============================================================================

# Context manager __exit__ parameters (lock_utils.py, perf_profiler.py, storage/writer.py)
exc_type  # noqa
exc_val  # noqa
exc_tb  # noqa

# Signal handler parameters (signal_utils.py)
# _signal_handler(signum, frame) and _reload_signal_handler(signum, frame)
# Required by signal.signal() protocol -- handlers receive (signum, frame)
signum  # noqa
frame  # noqa

# =============================================================================
# PITFALL 1: RouterOS transport class (autorate_continuous.py:1204)
# Used when router_transport != "linux-cake" -- still needed for RouterOS mode
# =============================================================================
RouterOS  # autorate_continuous.py

# =============================================================================
# PITFALL 1: routeros_ssh.py -- lazy-imported by router_client.py
# Imported at module level AND inside functions for REST failover path.
# check_cake.py line 1116 also imports it conditionally.
# =============================================================================
routeros_ssh  # lazy import target in router_client.py

# =============================================================================
# PITFALL 1: LinuxCakeAdapter -- conditional import at runtime
# autorate_continuous.py:3474: from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter
# Only imported when config.router_transport == "linux-cake"
# =============================================================================
from wanctl.backends.linux_cake_adapter import LinuxCakeAdapter

# =============================================================================
# PITFALL 1: RouterOSController in steering/daemon.py:721
# MikroTik mangle rule controller for steering -- different from router_client.py
# =============================================================================
from wanctl.steering.daemon import RouterOSController

# =============================================================================
# PITFALL 2: SIGUSR1 reload targets -- called via threading.Event, no static caller
# autorate_continuous.py:4175-4176 calls these from run_cycle() event loop
# steering/daemon.py:2132-2134 calls these from its event loop
# =============================================================================
_reload_fusion_config  # autorate_continuous.py WANController method
_reload_tuning_config  # autorate_continuous.py WANController method
_reload_dry_run_config  # steering/daemon.py SteeringDaemon method
_reload_wan_state_config  # steering/daemon.py SteeringDaemon method
_reload_webhook_url_config  # steering/daemon.py SteeringDaemon method

# =============================================================================
# PITFALL 7/11: MetricsWriter._reset_instance() -- test-only singleton reset
# Only called by tests for isolation. Removing breaks test suite.
# =============================================================================
_reset_instance  # storage/writer.py

# =============================================================================
# PITFALL 11: MetricsWriter.__exit__ intentionally does NOT close (singleton)
# The context manager protocol requires __exit__ but closing would break singleton.
# (Already covered by exc_type/exc_val/exc_tb above)
# =============================================================================

# =============================================================================
# FRAMEWORK: BaseHTTPRequestHandler lifecycle methods
# do_GET and log_message are called by the HTTP server framework, not user code.
# health_check.py, metrics.py, steering/health.py
# =============================================================================
do_GET  # BaseHTTPRequestHandler override -- called by HTTP server
log_message  # BaseHTTPRequestHandler override -- suppress default logging

# =============================================================================
# FRAMEWORK: Textual TUI lifecycle methods and class variables
# dashboard/app.py, dashboard/widgets/*.py
# These are called by the Textual framework, not by user code.
# =============================================================================
DEFAULT_CSS  # Textual Widget/App class variable
CSS_PATH  # Textual App class variable
BINDINGS  # Textual App class variable
compose  # Textual Widget.compose() lifecycle
on_mount  # Textual Widget.on_mount() lifecycle
on_resize  # Textual App.on_resize() lifecycle
on_unmount  # Textual App.on_unmount() lifecycle
action_refresh  # Textual action binding handler
_utilization_pct  # CycleBudgetGaugeWidget internal state
_maxlen  # SparklinePanelWidget internal state

# =============================================================================
# SQLite: row_factory attribute assignment
# conn.row_factory = sqlite3.Row is the standard way to get dict-like rows.
# storage/reader.py (4 occurrences), storage/writer.py (1 occurrence)
# =============================================================================
row_factory  # sqlite3.Connection attribute

# =============================================================================
# SQLite: requests.Session attributes set on construction
# routeros_rest.py:104-105 sets self.auth and self.verify on session
# =============================================================================
auth  # requests.Session attribute set for HTTP auth
verify  # requests.Session attribute set for SSL verification

# =============================================================================
# NamedTuple fields -- used by consumers via attribute access
# These are declared in NamedTuple definitions and accessed dynamically.
# =============================================================================
send_delay_ms  # asymmetry_analyzer.py OWDResult field
receive_delay_ms  # asymmetry_analyzer.py OWDResult field
rtt_median_ms  # irtt_measurement.py IRTTResult field
packets_sent  # irtt_measurement.py IRTTResult field
packets_received  # irtt_measurement.py IRTTResult field
consecutive_outliers  # signal_processing.py HampelState field
consecutive_successes  # reflector_scorer.py ReflectorScore field
last_decision  # steering/steering_confidence.py
last_decision_time  # steering/steering_confidence.py
Granularity  # storage/downsampler.py enum re-export

# =============================================================================
# Dashboard poller properties -- accessed by Textual widget refresh cycle
# =============================================================================
is_online  # dashboard/poller.py property
last_data  # dashboard/poller.py property
current_interval  # dashboard/poller.py property

# =============================================================================
# Metrics registry methods -- used by various callers dynamically
# =============================================================================
get_gauge  # metrics.py MetricsRegistry method
get_counter  # metrics.py MetricsRegistry method
is_running  # metrics.py MetricsServer property

# =============================================================================
# Steering daemon attributes -- set in __init__, used in run_cycle
# =============================================================================
primary_upload_queue  # steering/daemon.py -- used in CAKE stats collection
enable_yellow_state  # steering/daemon.py -- config flag for yellow state
log_cake_stats  # steering/daemon.py -- config flag for CAKE stats logging
MAX_TRANSITIONS_HISTORY  # steering/daemon.py -- constant for history deque
MAX_HISTORY_SAMPLES  # steering/daemon.py -- constant for sample history

# =============================================================================
# Error handling constants -- used as log level selectors
# =============================================================================
LOG_DEBUG  # error_handling.py
LOG_INFO  # error_handling.py
LOG_WARNING  # error_handling.py
LOG_ERROR  # error_handling.py
LOG_CRITICAL  # error_handling.py

# =============================================================================
# Config constants -- used by config loading and validation
# =============================================================================
STORAGE_SCHEMA  # config_base.py -- JSON schema for storage config validation
HEADER  # calibrate.py -- header constant for calibration output

# =============================================================================
# Timeout constants -- used by various modules
# =============================================================================
TIMEOUT_QUICK  # timeouts.py
TIMEOUT_THROUGHPUT_MEASUREMENT  # timeouts.py
DEFAULT_LOCK_TIMEOUT  # timeouts.py

# =============================================================================
# select_changed Textual event handler
# =============================================================================
on_select_changed  # dashboard/widgets/history_browser.py
