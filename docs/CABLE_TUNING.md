# Cable (DOCSIS) Tuning Guide

How to tune wanctl's autorate controller for cable connections. Cable has fundamentally different RTT characteristics than DSL or fiber, requiring a specific tuning philosophy.

## The Problem

DOCSIS cable modems introduce 5-15ms of inherent RTT jitter even when the link is completely idle. This comes from the CMTS (Cable Modem Termination System) scheduling via MAP intervals — it's a property of the shared medium, not congestion.

By contrast, DSL and fiber have near-zero idle jitter because they're point-to-point circuits.

If the autorate controller uses tight thresholds (e.g., 9ms) with aggressive rate decay (e.g., 8%/cycle), it will:

1. Detect DOCSIS jitter as "congestion"
2. Slam rates down 8% per 50ms cycle
3. Briefly recover when jitter subsides
4. Repeat — causing rate oscillation and wasted bandwidth

## The Solution: Sensitive Detection, Gentle Response

The correct approach for cable is:

- **Tight detection thresholds** — catch real congestion early
- **Gentle rate decay in YELLOW** — jitter resolves in 1-2 cycles with negligible rate impact
- **Slower recovery** — prevents oscillation from rapid GREEN/YELLOW transitions

### Why This Works

CAKE's AQM (Cobalt) is the primary anti-bufferbloat mechanism. It handles packet-level queue management instantly. The autorate controller's job is capacity tracking — detecting when the ISP-side bandwidth changes (DOCSIS node congestion) and adjusting the shaped rate to match.

With gentle YELLOW decay:

- **Jitter event (200ms):** 4 cycles × 3% = ~12% total. Rate: 940 → 830 Mbps. Barely noticeable.
- **Real congestion (2s):** 40 cycles × 3% = steady ramp-down. Rate: 940 → 290 Mbps. Proper response.
- **Severe congestion:** Escalates to SOFT_RED/RED with firmer 10% decay.

## Recommended Cable Parameters

```yaml
continuous_monitoring:
  download:
    factor_down: 0.90 # 10% RED backoff (firm for real congestion)
    factor_down_yellow: 0.97 # 3% YELLOW decay (gentle — jitter barely moves rates)
    green_required: 5 # Slower recovery prevents oscillation

  upload:
    factor_down: 0.93 # 7% backoff (upload is more sensitive on cable)
    green_required: 5 # Match download

  thresholds:
    target_bloat_ms: 12.0 # Sensitive — catches congestion early
    warn_bloat_ms: 30.0 # YELLOW→SOFT_RED boundary
    load_time_constant_sec: 0.25 # Smooths DOCSIS scheduling noise (5 cycles at 50ms)
```

### Note on factor_down_yellow

The 0.97 value above is a conservative starting point. On the production Spectrum link,
A/B testing (2026-04-02) via back-to-back 5-minute RRUL soaks showed that 0.92 (8%
decay) produces significantly better latency under heavy load:

| Metric              | 0.97 (3%) | 0.92 (8%) |
| ------------------- | --------- | --------- |
| ICMP median latency | 57.3ms    | 33.7ms    |
| ICMP 99th pct       | 235ms     | 90.7ms    |
| SOFT_RED/RED cycles | 23%       | 2%        |
| DL throughput       | 848 Mbps  | 852 Mbps  |

Throughput was identical — the gentler decay only added latency. Higher-bandwidth cable
links (500+ Mbps) may benefit from the more aggressive 0.92 value because RRUL-style
load overwhelms CAKE's queues faster at higher rates. Start with 0.97 and test with RRUL
to find the right value for your link.

### Note on green_required

The recommended `green_required: 5` was validated via RRUL A/B testing (2026-04-02).
Compared against `green_required: 3` (which was briefly deployed for faster recovery):

| Metric              | GR=3 (fast) | GR=5 (conservative) |
| ------------------- | ----------- | ------------------- |
| ICMP 99th pct       | 175ms       | 110ms               |
| ICMP max            | 643ms       | 255ms               |
| SOFT_RED/RED cycles | 11%         | 6%                  |
| Recovery to ceiling | ~2s         | ~3s                 |
| DL throughput       | 853 Mbps    | 854 Mbps            |

GR=3 recovers 1 second faster but overshoots during brief lulls in heavy load, causing
tail latency spikes and more time in severe congestion states. GR=5 prevents premature
ramp-up. For latency-sensitive traffic (gaming, video calls), the 40% tail improvement
far outweighs 1 extra second of recovery.

### Autotuner Bounds for Cable

```yaml
tuning:
  bounds:
    target_bloat_ms:
      min: 11.0 # Safe floor with gentle response
      max: 30.0
    warn_bloat_ms:
      min: 20.0 # Safe floor with gentle response
      max: 80.0
```

## DSL Comparison

DSL connections have deterministic latency. Tight thresholds AND aggressive decay are appropriate:

```yaml
# DSL (ATT example) — these would be wrong for cable
thresholds:
  target_bloat_ms: 1.4 # DSL can be this tight
  warn_bloat_ms: 5.0
download:
  factor_down: 0.90 # Aggressive is fine on DSL
  green_required: 3 # Fast recovery is safe
```

## Key Metrics

The metric that matters is **latency under load**, not GREEN percentage.

| Metric                      | Good                      | Investigate         |
| --------------------------- | ------------------------- | ------------------- |
| Bufferbloat grade           | A or A+                   | B or below          |
| Ping increase under DL load | < 10ms                    | > 20ms              |
| Ping increase under UL load | < 5ms                     | > 10ms              |
| YELLOW % (idle)             | 20-40% (normal for cable) | > 60%               |
| Rate at idle                | Near ceiling              | Stuck below ceiling |

A cable connection spending 30% of idle time in YELLOW with 3% decay is healthy — it means the controller is monitoring actively while barely impacting throughput.

## Autotuner Interaction

The adaptive tuner (v1.20+) will attempt to optimize thresholds based on observed GREEN-state deltas. On cable, this creates a self-tightening spiral:

1. Tight thresholds → less GREEN time
2. GREEN samples skew toward quietest moments
3. Tuner sees low GREEN deltas → proposes tighter thresholds
4. Hits bound → waits an hour → tries again

This is a fundamental mismatch: the tuner assumes idle RTT is stable (true for DSL/fiber, false for DOCSIS). Threshold autotuning is **not appropriate for cable links**.

### Excluding Thresholds from Autotuning

Use `exclude_params` to skip threshold autotuning while keeping signal processing tuning (Hampel, baseline bounds) active:

```yaml
tuning:
  enabled: true
  exclude_params: # Skip autotuning — set by link physics, not adaptive
    - target_bloat_ms # DOCSIS jitter makes threshold autotuning counterproductive
    - warn_bloat_ms # See docs/CABLE_TUNING.md for rationale
```

Excluded parameters are completely skipped — no analysis, no proposals, no DB writes. The tuner continues optimizing Hampel filter settings, baseline bounds, fusion weights, and other parameters that are legitimately adaptive.

**Do not use `exclude_params` on DSL/fiber WANs.** Threshold autotuning works correctly on deterministic links.

## Tuning Param Persistence

The autotuner persists changes to the `tuning_params` table in `metrics.db`. These override YAML values on restart. When manually adjusting thresholds:

```bash
# 1. Edit config
sudo vi /etc/wanctl/spectrum.yaml

# 2. Clear stale tuner overrides
sudo python3 -c "
import sqlite3
db = sqlite3.connect('/var/lib/wanctl/metrics.db')
db.execute(\"DELETE FROM tuning_params WHERE wan_name='spectrum' AND parameter IN ('target_bloat_ms', 'warn_bloat_ms')\")
db.commit()
"

# 3. Restart
sudo systemctl restart wanctl@spectrum
```

## Validation

After tuning, run a full test suite:

```bash
# Single flow (tests CAKE AQM effectiveness)
flent tcp_download -H 104.200.21.31 -l 60 -t "cable-single-flow"

# RRUL (tests bufferbloat under multi-flow load)
flent rrul -H 104.200.21.31 -l 60 -t "cable-RRUL"

# Also run Waveform bufferbloat test from a client device:
# https://www.waveform.com/tools/bufferbloat
```

Target: A+ bufferbloat grade, < 10ms ping increase under download load.
