#!/usr/bin/env bash
# Spectrum DOCSIS cake-autorate external controller mode for cake-shaper.
# wanctl@spectrum.service must be stopped while this service adjusts rates.

dl_if=spec-router
ul_if=spec-modem

# Round-robin reflectors; bind probes to the Spectrum-capable shaper address.
pinger_method=fping
ping_extra_args="-S 10.10.110.223"
# Reflectors selected by source-bound Spectrum scan on cake-shaper.
# Avoid Cloudflare here: 1.1.1.1 / 1.0.0.1 were much slower/jitterier from this path.
reflectors=("8.8.8.8" "9.9.9.9" "76.76.2.0" "9.9.9.10" "8.8.4.4" "76.76.10.0" "9.9.9.11" "208.67.222.222")
no_pingers=4
reflector_ping_interval_s=0.2

# Conservative Spectrum DOCSIS production trial envelope.
adjust_dl_shaper_rate=1
adjust_ul_shaper_rate=1
min_dl_shaper_rate_kbps=500000
base_dl_shaper_rate_kbps=550000
max_dl_shaper_rate_kbps=600000
min_ul_shaper_rate_kbps=8000
base_ul_shaper_rate_kbps=30000
max_ul_shaper_rate_kbps=30000

connection_active_thr_kbps=2000
high_load_thr=0.75

# Latency-first DOCSIS thresholds from the Spectrum trial.
dl_owd_delta_delay_thr_ms=30.0
ul_owd_delta_delay_thr_ms=30.0
dl_avg_owd_delta_max_adjust_up_thr_ms=10.0
ul_avg_owd_delta_max_adjust_up_thr_ms=10.0
dl_avg_owd_delta_max_adjust_down_thr_ms=60.0
ul_avg_owd_delta_max_adjust_down_thr_ms=60.0
bufferbloat_detection_window=6
bufferbloat_detection_thr=3
bufferbloat_refractory_period_ms=300

# Avoid violent rate swings while still reacting faster than wanctl did on Spectrum.
shaper_rate_min_adjust_down_bufferbloat=0.98
shaper_rate_max_adjust_down_bufferbloat=0.75
shaper_rate_min_adjust_up_load_high=1.00
shaper_rate_max_adjust_up_load_high=1.03
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
