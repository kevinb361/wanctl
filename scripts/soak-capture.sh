#!/usr/bin/env bash
# wanctl soak-capture harness (v1.43 Phase 203)
#
# Usage: HEALTH_URL=http://<host>:9101/health bash scripts/soak-capture.sh <SOAK_TS>
#
# Required env: HEALTH_URL  — full /health endpoint URL (no default; public-safe).
# Optional env: SOAK_DURATION_SEC (default 86400 = 24h)
#               CAPTURE_DIR        (default /var/tmp/wanctl-soak-${SOAK_TS})
#
# Writes one NDJSON row per second to ${CAPTURE_DIR}/soak-capture.ndjson.
# See docs/SOAK_HARNESS.md for the full per-row schema (created in plan 203-03).

set -euo pipefail

SOAK_TS="${1:?SOAK_TS positional arg required}"
: "${HEALTH_URL:?HEALTH_URL env var required (e.g. HEALTH_URL=http://<host>:9101/health)}"
SOAK_DURATION_SEC="${SOAK_DURATION_SEC:-86400}"
CAPTURE_DIR="${CAPTURE_DIR:-/var/tmp/wanctl-soak-${SOAK_TS}}"

mkdir -p "$CAPTURE_DIR"

T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

while [ "$(date +%s)" -lt "$SOAK_END" ]; do
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
        red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct,
        load_rtt_ms: .wans[0].load_rtt_ms,
        baseline_rtt_ms: .wans[0].baseline_rtt_ms,
        load_rtt_delta_us: (
          if (.wans[0].load_rtt_ms == null) or (.wans[0].baseline_rtt_ms == null)
          then null
          else ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)
          end
        ),
        last_zone: .wans[0].upload.hysteresis.last_zone,
        ul_hysteresis_window_start_epoch: .wans[0].upload.hysteresis.window_start_epoch,
        ul_suppressions_completed_window_count: .wans[0].upload.hysteresis.suppressions_completed_window_count,
        ul_suppressions_completed_window_by_cause: .wans[0].upload.hysteresis.suppressions_completed_window_by_cause,
        ul_suppressions_lifetime_by_cause: .wans[0].upload.hysteresis.suppressions_lifetime_by_cause
      }' >> "$CAPTURE_DIR/soak-capture.ndjson"
  sleep 1
done
