#!/usr/bin/env bash
# Generate Phase 243 isolated benchmark configs.

set -euo pipefail

OUT_DIR=""
if [ "${1:-}" = "--output-dir" ]; then
  OUT_DIR="${2:?--output-dir requires a directory}"
  mkdir -p "$OUT_DIR"
elif [ "$#" -ne 0 ]; then
  echo "usage: $0 [--output-dir DIR]" >&2
  exit 2
fi

emit_config() {
  local wan="$1" backend="$2" health_port="$3" metrics_port="$4" source_ip="$5"
  local if_prefix="bench-${wan}"
  if [ "$wan" = "spectrum" ]; then
    if_prefix="bench-spec"
  fi
  local dl_iface="${if_prefix}-dl"
  local ul_iface="${if_prefix}-ul"

  cat <<YAML
wan_name: "${wan}"
ping_source_ip: "${source_ip}"

measurement:
  backend: "${backend}"
  fping:
    cadence_sec: 10.0
    timeout_sec: 0.5
    timeout_grace_sec: 0.2

health_check:
  host: "127.0.0.1"
  port: ${health_port}

metrics:
  enabled: false
  host: "127.0.0.1"
  port: ${metrics_port}

router:
  transport: "linux-cake"

queues:
  download: "WAN-Bench-${wan}-Download"
  upload: "WAN-Bench-${wan}-Upload"

cake_params:
  download_interface: "${dl_iface}"
  upload_interface: "${ul_iface}"
  overhead: "docsis"
  mpu: 64
  memlimit: "32mb"
  rtt: "100ms"
  diffserv: besteffort
  allow_wash: false

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 24
  download:
    floor_green_mbps: 100
    floor_yellow_mbps: 80
    floor_soft_red_mbps: 60
    floor_red_mbps: 40
    ceiling_mbps: 120
    step_up_mbps: 5
    factor_down: 0.90
    factor_down_yellow: 0.92
    green_required: 5
  upload:
    floor_mbps: 5
    ceiling_mbps: 20
    step_up_mbps: 1
    factor_down: 0.90
    green_required: 5
  thresholds:
    target_bloat_ms: 10
    warn_bloat_ms: 50
    hard_red_bloat_ms: 80
    dwell_cycles: 5
    deadband_ms: 3.0
    baseline_time_constant_sec: 50
    load_time_constant_sec: 0.10
  ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
  use_median_of_three: true

logging:
  main_log: "/var/tmp/wanctl-bench/${wan}-${backend}.log"
  debug_log: "/var/tmp/wanctl-bench/${wan}-${backend}-debug.log"

lock_file: "/run/wanctl/bench-${wan}-${backend}.lock"
lock_timeout: 300
state_file: "/var/tmp/wanctl-bench/${wan}-${backend}_state.json"

storage:
  db_path: "/var/tmp/wanctl-bench/${wan}-${backend}-metrics.db"
  maintenance_interval_seconds: 900
YAML
}

arms=(
  "spectrum icmplib 9201 9200 10.10.110.223"
  "spectrum fping 9202 9203 10.10.110.223"
  "att icmplib 9211 9210 10.10.110.227"
  "att fping 9212 9213 10.10.110.227"
)

for arm in "${arms[@]}"; do
  read -r wan backend health metrics source_ip <<<"$arm"
  if [ -n "$OUT_DIR" ]; then
    emit_config "$wan" "$backend" "$health" "$metrics" "$source_ip" >"${OUT_DIR}/${wan}-bench-${backend}.yaml"
  else
    printf -- '---\n'
    emit_config "$wan" "$backend" "$health" "$metrics" "$source_ip"
  fi
done
