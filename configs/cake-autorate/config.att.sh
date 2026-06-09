#!/usr/bin/env bash
# ATT VDSL cake-autorate external controller mode for cake-shaper.
# wanctl@att.service must be stopped while this service adjusts rates.

dl_if=att-router
ul_if=att-modem

# Bind probes to ATT-capable shaper address so route policy cannot leak over Spectrum.
pinger_method=fping
ping_extra_args="-S 10.10.110.227"
reflectors=("1.1.1.1" "8.8.8.8" "151.101.1.57")
no_pingers=3
reflector_ping_interval_s=0.2

# Tuned for AT&T bonded VDSL2 sold as 100/20. Evidence from dev-bound
# qdisc-validated A/B trials on 2026-06-05: 95/100 download keeps low latency
# while recovering a little throughput; 19M upload is the best safe upload
# ceiling; 20M produced severe upload-latency bloat.
adjust_dl_shaper_rate=1
adjust_ul_shaper_rate=0
min_dl_shaper_rate_kbps=60000
base_dl_shaper_rate_kbps=95000
max_dl_shaper_rate_kbps=100000
min_ul_shaper_rate_kbps=6000
base_ul_shaper_rate_kbps=19000
max_ul_shaper_rate_kbps=19000

connection_active_thr_kbps=1000
high_load_thr=0.75

# VDSL has a low RTT budget. Keep first trial moderately sensitive but do not
# combine with qdisc/ACK/reflector changes.
dl_owd_delta_delay_thr_ms=10.0
ul_owd_delta_delay_thr_ms=10.0
dl_avg_owd_delta_max_adjust_up_thr_ms=3.0
ul_avg_owd_delta_max_adjust_up_thr_ms=3.0
dl_avg_owd_delta_max_adjust_down_thr_ms=30.0
ul_avg_owd_delta_max_adjust_down_thr_ms=30.0
bufferbloat_detection_window=6
bufferbloat_detection_thr=3
bufferbloat_refractory_period_ms=300

# Conservative movement: ATT is already good under native wanctl, so the trial
# should prove parity before any migration.
shaper_rate_min_adjust_down_bufferbloat=0.98
shaper_rate_max_adjust_down_bufferbloat=0.85
shaper_rate_min_adjust_up_load_high=1.00
shaper_rate_max_adjust_up_load_high=1.02
shaper_rate_adjust_down_load_low=0.995
shaper_rate_adjust_up_load_low=1.005

log_to_file=1
log_file_path_override="/var/log/cake-autorate"
log_file_max_time_mins=60
log_file_max_size_KB=8192
output_cake_changes=1
output_processing_stats=0
output_load_stats=1
output_reflector_stats=0
output_summary_stats=1
output_cpu_stats=0
output_cpu_raw_stats=0
debug=0
