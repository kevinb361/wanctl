#!/usr/bin/env bash
set -euo pipefail
SOAK_TS="${1:?SOAK_TS positional arg required}"
SOAK_DURATION_SEC=86400  # 24h
HEALTH_URL="http://10.10.110.223:9101/health"
CAPTURE_DIR="/var/tmp/wanctl-soak-${SOAK_TS}"
mkdir -p "$CAPTURE_DIR"

T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

while [ $(date +%s) -lt $SOAK_END ]; do
  T_MONO=$(awk '{print $1; exit}' /proc/uptime)
  T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')
  curl -s "$HEALTH_URL" \
    | jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '{
        t_wall: $twall,
        t_monotonic: $tmono,
        version: .version,
        status: .status,
        floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
        suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
        max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
        red_streak: .wans[0].upload.red_streak,
        zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
        headroom_state: .wans[0].upload.headroom_state,
        headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
        anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
        rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
        docsis_mode_active: .wans[0].upload.docsis_mode_active,
        red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
        red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct
      }' >> "$CAPTURE_DIR/soak-capture.ndjson"
  sleep 1
done
