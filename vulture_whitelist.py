"""Vulture whitelist -- intentional exceptions for dead code detection.

Grouped by category. Run: vulture src/wanctl/ vulture_whitelist.py
See: .planning/phases/142-dead-code-removal/142-RESEARCH.md for rationale.
"""

# --- Protocol parameters (required by Python protocols) ---
# __exit__(self, exc_type, exc_val, exc_tb) -- 3 params x 3 files
exc_type  # noqa
exc_val  # noqa
exc_tb  # noqa

# Signal handler(signum, frame) -- signal_utils.py
signum  # noqa
frame  # noqa

# --- sqlite3 Row factory (assigned for dict-like row access) ---
_.row_factory

# --- Dataclass fields (structural, stored for observability/serialization) ---
_.send_delay_ms
_.receive_delay_ms
rtt_median_ms  # noqa  -- IRTTResult dataclass field
packets_sent  # noqa  -- IRTTResult dataclass field
packets_received  # noqa  -- IRTTResult dataclass field
consecutive_outliers  # noqa  -- HampelFilterState dataclass field
consecutive_successes  # noqa  -- ReflectorScore dataclass field
measurement_ms  # noqa  -- RTTSample dataclass field

# --- Literal type alias (used as type annotation, not runtime value) ---
Granularity  # noqa  -- Literal["raw", "1m", "5m", "1h"] in downsampler.py

# --- Test infrastructure (called from tests/, not src/ -- alive per D-04) ---
_._reset_instance

# --- ABC interface methods (contract for all backends -- alive per D-05) ---
_.enable_rule
_.disable_rule
_.is_rule_enabled
_.reset_queue_counters

# --- ABC base class (inherited by concrete strategies -- alive) ---
TuningStrategy  # noqa  -- base class for tuning strategies

# --- Protocol definitions (interfaces.py -- structural subtyping, D-01/D-02) ---
HealthDataProvider  # noqa  -- Protocol for health data providers
Reloadable  # noqa  -- Protocol for SIGUSR1 reload support
TunableController  # noqa  -- Protocol for tunable parameter access
ThreadManager  # noqa  -- Protocol for thread lifecycle management
_.get_health_data  # Protocol method
_.reload  # Protocol method (Reloadable)
_.get_current_params  # Protocol method
_.shutdown_threads  # Protocol method

# --- Test-only utilities (imported by tests/, alive per D-04) ---
# config_validation_utils.py validators
validate_baseline_rtt  # noqa
validate_rtt_thresholds  # noqa
validate_sample_counts  # noqa

# state_manager.py validators
non_negative_int  # noqa
non_negative_float  # noqa
optional_positive_float  # noqa
bounded_float  # noqa
string_enum  # noqa

# state_utils.py
safe_read_json  # noqa

# signal_utils.py
wait_for_shutdown  # noqa
reset_shutdown_state  # noqa

# error_handling.py
safe_operation  # noqa
safe_call  # noqa

# path_utils.py
get_cake_root  # noqa
safe_file_path  # noqa

# metrics.py
_.get_gauge
_.get_counter
_.is_running

# dashboard/poller.py
_.is_online
_.last_data
_.current_interval

# rtt_measurement.py
_.ping_hosts_concurrent

# routeros_rest.py
_.set_queue_limit

# systemd_utils.py
notify_ready  # noqa
notify_status  # noqa
notify_stopping  # noqa

# webhook_delivery.py
_.delivery_failures

# perf_profiler.py
measure_operation  # noqa

# timeouts.py
get_ssh_timeout  # noqa
get_ping_timeout  # noqa

# rate_utils.py
_.changes_remaining

# router_command_utils.py
safe_parse_output  # noqa
handle_command_error  # noqa

# router_client.py
_create_transport  # noqa

# tuning/strategies
_extract_green_deltas  # noqa

# wan_controller.py (WANController)
_.update_ewma
_._last_tuning_ts  # test-only attribute (D-04) -- tests verify init value

# config_base.py
STORAGE_SCHEMA  # noqa  # test-only (D-04) -- imported and validated in test_config_base.py

# dashboard/widgets/cycle_gauge.py -- optional-dep Textual widget (D-03, D-04)
_._utilization_pct  # set in update_utilization, read in tests

# dashboard/widgets/sparkline_panel.py -- optional-dep Textual widget (D-03, D-04)
_._maxlen  # sparkline panel maxlen stored for test access

# steering/daemon.py -- config attributes loaded from YAML (D-04)
_.primary_upload_queue  # config attribute, tested in test_steering_daemon.py
_.enable_yellow_state  # config attribute, tested in test_steering_daemon.py
_.log_cake_stats  # config attribute, validated in check_config.py

# steering/steering_confidence.py -- dataclass fields (Pitfall 3)
_.last_decision  # SteeringState dataclass field
_.last_decision_time  # SteeringState dataclass field

# routeros_rest.py -- session attribute assignments (D-05)
# These are self._session.auth and self._session.verify (requests.Session attrs)
_.auth  # requests.Session.auth assignment
_.verify  # requests.Session.verify assignment

# timeouts.py -- test-only constants (D-04)
TIMEOUT_QUICK  # noqa  # tested in test_timeouts.py
DEFAULT_LOCK_TIMEOUT  # noqa  # tested in test_timeouts.py

# tuning/strategies/response.py -- dataclass fields (Pitfall 3, D-04)
_.pre_rate_mbps  # RecoveryEpisode dataclass field, tested
_.post_rate_mbps  # RecoveryEpisode dataclass field, tested

# --- Existing public/test/config/observability surfaces reported by vulture after CI sync (2026-07) ---
analyze_baseline  # noqa
check_detection_events  # noqa
_._upload_consecutive_yellow_decay_clamp_explicit
_._integral_window_seconds_explicit
_._integral_threshold_ms_s_explicit
_._cake_backlog_low_threshold_bytes_explicit
_._cake_delay_delta_low_threshold_us_explicit
_.get_both_queue_stats
dropped_packets  # noqa
ecn_marked_packets  # noqa
avg_delay_us  # noqa
base_delay_us  # noqa
delay_delta_us  # noqa
_._cold_start
HANDOFF_TEXT  # noqa
_._find_mangle_rule_id
_.to_snapshot
cycle_timestamp  # noqa
_.ping_count
_.route_management_migration_acknowledged
_.failover_enabled
_.failover_wan
_.failover_red_cycles
_.failover_green_cycles
_.route_decision_policy
_.route_decision_state
_._last_route_abort_log_ts
att_failed  # noqa
_._get_att_congestion_state
_.red_count
_.green_count
_.get_bridge
_.get_decisions
_.armed_count
route_actions  # noqa
alternate_route_key  # noqa
RouteMode  # noqa
_.reset_circuit
owner  # noqa
_detect_route_mutating_scripts  # noqa
detect_netwatch_route_conflicts  # noqa
_.enqueue_alert
DEFAULT_MAINTENANCE_LOCK_TIMEOUT  # noqa
_._encode_state
