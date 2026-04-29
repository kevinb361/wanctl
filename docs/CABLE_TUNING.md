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

All values below validated via RRUL A/B testing on REST transport (2026-04-02, 30 soaks).
See "Note on" sections below for test data and rationale for each.

**linux-cake transport:** Values differ significantly. See [linux-cake Transport Results](#linux-cake-transport-results-2026-04) below for re-validated parameters.

```yaml
continuous_monitoring:
  download:
    step_up_mbps: 15 # Fast ramp (validated over 10)
    factor_down: 0.90 # 10% RED backoff (validated over 0.85)
    factor_down_yellow: 0.92 # 8% YELLOW decay (validated: 0.97 doubles latency)
    green_required: 5 # Conservative recovery (validated over 3)

  upload:
    step_up_mbps: 1 # Gentle climb (validated: 2 overshoots on constrained upstream)
    factor_down: 0.85 # 15% backoff (validated: UL needs MORE aggressive than DL's 0.90)
    green_required: 5 # Match download (validated independently)

  thresholds:
    target_bloat_ms: 9.0 # GREEN→YELLOW (validated over 12 — safe with dwell=5)
    warn_bloat_ms: 45.0 # YELLOW→SOFT_RED (validated: 30 too aggressive, 60 too loose)
    hard_red_bloat_ms: 60.0 # SOFT_RED→RED (validated over 80 — faster floor clamp)
    dwell_cycles: 5 # Hysteresis dwell (validated over default 3)
    deadband_ms: 3.0 # Hysteresis deadband (validated: 5.0 is worse)
    load_time_constant_sec: 0.25 # Smooths DOCSIS scheduling noise (5 cycles at 50ms)
```

## Spectrum Silicom Migration Findings (2026-04-28)

The 2026-04-28 Spectrum move onto the Silicom bypass NIC produced an important
diagnostic sequence that should guide future cable/DOCSIS tuning work.

What was ruled out:

- Direct Spectrum modem-to-router testing reached about `692 Mbps` down and
  `35 Mbps` up, so the ISP service, modem, RouterOS WAN port, and LAN/client path
  were capable.
- Corrected Silicom raw bridge testing reached `38.9 Mbit/s` upload to the
  Dallas test host after the path was allowed to stabilize, so the Silicom card,
  PCIe riser, and bridge path were not the remaining upload bottleneck.
- MBP Wi-Fi was not the primary cause; source-bound `iperf3` from `cake-shaper`
  reproduced the managed upload shortfall.

What caused the initial severe download symptom:

- The old-port fallback test had Spectrum physical roles reversed relative to
  `spectrum.yaml`.
- That placed the `32Mbit` upload qdisc on the download egress path and produced
  download speeds around `10-17 Mbps`.
- Direction must be confirmed with `ip -s link` and `tc -s qdisc`, not inferred
  from interface names after cable moves.

What changed upload behavior during the investigation:

- Disabling `gro`, `gso`, `tso`, and `hw-tc-offload` on `spec-modem` and
  `spec-router` changed CAKE `max_len` from GSO-sized packets back to MTU-sized
  packets and eliminated the severe ping-loss mode seen during shaped upload.
- Static CAKE with the old `rtt 25ms` setting underperformed badly. Increasing
  CAKE `rtt` changed upload behavior, with `rtt 1s` producing one high static
  result in this session. That value is not acceptable as an operating tune;
  treat it as a diagnostic artifact that masked another issue. Spectrum should
  use a sane WAN interval such as `100ms` unless a controlled A/B run proves a
  different bounded value.
- `cake_params.ack_filter: false` is still required for the current Spectrum
  Silicom deployment. A backend bug also had to be fixed so explicit false values
  actually produce `no-ack-filter` or netlink `ack_filter=False`.
- Download-side CAKE with the `ingress` keyword on `spec-router` collapsed upload
  tests, apparently by disturbing the return-ACK path. Removing `ingress` restored
  upload behavior in static isolation.
- Managed `wanctl@spectrum` still underperformed after isolating WAN-path
  measurement probe traffic. Disabling IRTT helped, but was not sufficient by
  itself: a single WAN ICMP reflector (`1.1.1.1`) still reproduced the upload
  collapse. Gateway-only probing (`10.10.110.1`) was useful only as a diagnostic
  control because it masks WAN congestion and does not give autorate a usable
  WAN-path RTT signal.

Current operational mitigation, not final tuning doctrine:

```yaml
cake_params:
  download_interface: "spec-router"
  upload_interface: "spec-modem"
  rtt: "100ms"
  ack_filter: false
  ingress: false

continuous_monitoring:
  cake_stats_cadence_sec: 1.0
  upload:
    ceiling_mbps: 28
  ping_hosts: ["1.1.1.1", "9.9.9.9", "208.67.222.222"]

irtt:
  enabled: false
```

Validated observations from 2026-04-28:

- Raw bridge capability was repeatedly observed around `34-39 Mbit/s` upload when
  public `iperf3` targets were behaving.
- Static upload CAKE at `28Mbit`, diagnostic `rtt 1s`, `no-ack-filter`, and no
  download `ingress` produced about `24-25 Mbit/s` receiver throughput with low
  qdisc drop counts in the cleanest runs. Do not carry the `1s` interval forward
  into normal operation.
- Managed `wanctl@spectrum` with gateway-only probing and IRTT disabled produced
  about `25.3 Mbit/s` receiver throughput with no ping loss in the best valid run,
  but this is not acceptable as an operating mode because it removes WAN-path RTT
  visibility from autorate.
- Managed `wanctl@spectrum` with IRTT enabled or WAN ICMP probing produced repeated
  upload collapse during public `iperf3` tests. This may be caused by probe traffic
  interacting with the inline bridge, CAKE classification, DOCSIS upstream request
  scheduling, or the specific test methodology; it is not yet proven that public
  ICMP must be disabled permanently.
- Static shaper isolation on 2026-04-28 showed upload-only `htb+fq_codel` at
  `28Mbit` outperforming upload-only CAKE in the same window (`22.48 Mbit/s` vs
  `6.70 Mbit/s` in speedtest upload-only). Follow-up found one systemd-specific
  HTB bug: `ProcSubset=pid` hides `/proc/net/psched`, causing tiny HTB burst
  readback during rate writes. Removing `ProcSubset=pid` preserved the intended
  `256Kb` burst, but managed HTB/fq_codel still only produced `12.32 Mbit/s` in
  an upload-only speedtest and triggered autorate down to the `8Mbit` floor before
  recovering. HTB/fq_codel is therefore not the operational Spectrum mode.
- Public `iperf3` targets became unreliable late in the investigation, including
  broken pipes and `0.00 Bytes` receiver reports even in raw bridge mode. Treat
  late-run public `iperf3` failures as inconclusive unless immediately bracketed by
  a healthy raw bridge control.
- A browser bufferbloat test after mitigation reported grade `B`, download
  `735.2 Mbps`, upload `25.4 Mbps`, unloaded latency `31 ms`, download active
  `+47 ms`, and upload active `+42 ms`. This shows the mitigation restored usable
  upload throughput but did not fully solve loaded latency.

Open questions before declaring a final Spectrum/Silicom tune:

- Is `100ms` the right CAKE interval for this Spectrum/Silicom path, or should a
  nearby bounded value such as `200ms` be used? Do not reintroduce `1s` except as
  an explicit diagnostic control.
- Which WAN-path reflector set and cadence gives autorate usable RTT visibility
  without reproducing the managed upload collapse?
- Is IRTT itself harmful, or only its current cadence/duration/packet pattern on
  this inline bridge and DOCSIS upstream?
- Should the download ceiling be lowered from `940Mbit` toward measured goodput
  (`735 Mbps` in the browser test) to improve the remaining `+47 ms` download
  active latency?
- Should upload ceiling be tested around `24-28Mbit` to trade a few Mbps for lower
  `+42 ms` upload active latency?

Do not treat this finding as permission to change thresholds or floors casually.
The next tuning step should be a controlled A/B run that waits for link/path
stabilization and compares:

- raw bridge, no CAKE
- static upload CAKE only
- static upload and download CAKE without `ingress`
- managed `wanctl@spectrum` with the WAN reflector set restored
- managed `wanctl@spectrum` with one WAN reflector at reduced cadence
- managed `wanctl@spectrum` with IRTT reintroduced at reduced cadence or duration

Capture `tc -s qdisc`, `ip -s link`, `/health`, controller logs, and external
bufferbloat results immediately after each run. Public `iperf3` runs must be
bracketed by raw bridge controls when they produce low throughput or broken pipes.

### Note on factor_down_yellow

On the production Spectrum link, A/B testing (2026-04-02) via back-to-back 5-minute RRUL
soaks showed that 0.92 (8% decay) produces significantly better latency than the
originally recommended 0.97 (3% decay):

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

The recommended `green_required: 5` was validated for both download AND upload via
independent RRUL A/B testing (2026-04-02). Each direction tested separately against
`green_required: 3` (which was briefly deployed for faster recovery).

**Download** (UL=3 held constant):

| Metric              | GR=3 (fast) | GR=5 (conservative) |
| ------------------- | ----------- | ------------------- |
| ICMP 99th pct       | 175ms       | 110ms               |
| ICMP max            | 643ms       | 255ms               |
| SOFT_RED/RED cycles | 11%         | 6%                  |
| Recovery to ceiling | ~2s         | ~3s                 |
| DL throughput       | 853 Mbps    | 854 Mbps            |

**Upload** (DL=5 held constant):

| Metric              | GR=3 (fast) | GR=5 (conservative) |
| ------------------- | ----------- | ------------------- |
| ICMP 99th pct       | 264ms       | 117ms               |
| ICMP max            | 529ms       | 207ms               |
| SOFT_RED/RED cycles | 18%         | 7%                  |
| UL throughput       | 19.5 Mbps   | 22.2 Mbps (+14%)    |

Upload improvement was even stronger than download. On DOCSIS upstream, GR=3 causes
oscillation (premature ramp-up, queue spike, slam back down) that hurts both latency
AND throughput. GR=5 lets each step-up stick, resulting in higher sustained throughput
with less variance.

### Note on step_up_mbps

The production value of `step_up_mbps: 15` (DL) was validated over the original `10` via
RRUL A/B testing (2026-04-02):

| Metric              | Step=10 (slow) | Step=15 (fast) |
| ------------------- | -------------- | -------------- |
| ICMP median latency | 55.3ms         | 41.8ms         |
| ICMP 99th pct       | 190ms          | 136ms          |
| ICMP max            | 654ms          | 219ms          |
| SOFT_RED/RED cycles | 19%            | 8%             |
| UL throughput       | 17.9 Mbps      | 23.6 Mbps      |

During heavy bidirectional load, TCP congestion avoidance creates brief dips. Faster
step-up (15 Mbps/cycle) exploits these dips to recover bandwidth before the next burst.
Slower step-up (10) can't keep up, leaving rates depressed and queues fuller.

**Key interaction:** `green_required=5` + `step_up=15` work as a pair — wait for genuine
clearance (5 cycles), then ramp aggressively (15 Mbps/step). Changing one without the
other may produce worse results than either alone.

### Note on dwell_cycles

The v1.24 hysteresis dwell timer defaults to 3 cycles (150ms at 50ms interval). For
cable/DOCSIS links, `dwell_cycles: 5` (250ms) was validated via RRUL A/B testing
(2026-04-02). Must be added explicitly under `thresholds:` — not present in YAML by default.

| Metric              | Dwell=3 (default) | Dwell=5 (validated) |
| ------------------- | ----------------- | ------------------- |
| ICMP median latency | 49.9ms            | 43.4ms              |
| ICMP 99th pct       | 150ms             | 126ms               |
| SOFT_RED/RED cycles | 14%               | 11%                 |
| UL throughput       | 19.2 Mbps         | 22.8 Mbps (+19%)    |

DOCSIS CMTS scheduling jitter can persist for 1-3 cycles (50-150ms). Dwell=3 is too
short to filter this noise — the controller commits to YELLOW on jitter, triggering
unnecessary rate decay. Dwell=5 waits long enough to distinguish jitter from sustained
congestion. DSL/fiber links with near-zero idle jitter may work fine with dwell=3.

### Note on factor_down (RED)

The cable tuning guide's `factor_down: 0.90` (10% RED decay) was validated over the
production value of 0.85 (15%) via RRUL A/B testing (2026-04-02):

| Metric              | 0.85 (15%) | 0.90 (10%) |
| ------------------- | ---------- | ---------- |
| ICMP median latency | 35.9ms     | 33.7ms     |
| ICMP max            | 241ms      | 148ms      |
| SOFT_RED/RED cycles | 2.5%       | 1.9%       |

Narrow win — RED is only entered 1-2% of cycles with proper dwell/green_required tuning.
The gentler 10% decay avoids overshooting the floor during severe congestion spikes.

### Note on deadband_ms

The default `deadband_ms: 3.0` was validated over 5.0 via RRUL A/B testing (2026-04-02).
**Wider is NOT better** for cable:

| Metric              | DB=3.0 (default) | DB=5.0 (wider) |
| ------------------- | ---------------- | -------------- |
| ICMP median latency | 31.4ms           | 32.5ms         |
| ICMP 99th pct       | 96.5ms           | 105.6ms        |
| GREEN cycles        | 67%              | 54%            |
| YELLOW cycles       | 29%              | 43%            |

Wider deadband requires delta to drop further below threshold to exit YELLOW (delta < 7ms
vs < 9ms). This traps the system in YELLOW during load fluctuations, keeping rates
depressed. With `dwell_cycles=5` already filtering jitter, a wider deadband is redundant
and counterproductive. Don't stack both — dwell handles entry filtering, deadband handles
exit hysteresis, and 3.0ms is sufficient for the exit side.

### Note on target_bloat_ms

The GREEN->YELLOW threshold was originally locked at 12ms because DOCSIS jitter (5-15ms)
caused false YELLOWs with the default `dwell_cycles=3`. With `dwell_cycles=5` now
filtering jitter, a tighter threshold is safe and produces better results.

Three-way RRUL A/B testing (2026-04-02) at 9ms, 12ms, and 15ms:

| Metric              | 9ms (tight) | 12ms (original) | 15ms (loose) |
| ------------------- | ----------- | --------------- | ------------ |
| ICMP median latency | 33.8ms      | 38.3ms          | 34.0ms       |
| ICMP 99th pct       | 116ms       | 174ms           | 182ms        |
| ICMP max            | 214ms       | 284ms           | 460ms        |
| SOFT_RED/RED cycles | 2.5%        | 6.6%            | 2.9%         |
| UL throughput       | 27.3 Mbps   | 24.4 Mbps       | 26.7 Mbps    |

9ms wins on every latency metric. It enters YELLOW more often (66% vs 56%), but with
dwell=5 filtering, each YELLOW entry represents real congestion caught 3ms earlier —
before queues build up. The 12ms threshold sat in a dead zone: not tight enough for early
detection, not loose enough to avoid YELLOW, resulting in the worst latency of all three.

**CRITICAL:** `target_bloat_ms=9` is ONLY safe because `dwell_cycles=5` filters jitter.
If dwell is reverted to 3, target_bloat MUST go back to 12. These parameters are coupled.

### Note on warn_bloat_ms

The YELLOW->SOFT_RED threshold was tested at 30ms, 45ms, and 60ms (2026-04-02). **45ms
confirmed** — test data was noisy (suspected CMTS congestion) but 45ms had the best
median (36.8ms). 30ms escalated too aggressively (21% SOFT_RED). 60ms allowed queue
buildup (2,454ms max latency). Unlike target_bloat_ms, tighter is not better here —
the YELLOW->SOFT_RED boundary manages transitions between active congestion states.

### Note on hard_red_bloat_ms

The SOFT_RED->RED threshold was tested at 60ms, 80ms, and 100ms (2026-04-02).
`hard_red_bloat_ms: 60` validated over original 80ms:

| Metric              | 60ms (tight) | 80ms (original) | 100ms (loose) |
| ------------------- | ------------ | --------------- | ------------- |
| ICMP median latency | 40.1ms       | 41.1ms          | 42.2ms        |
| SOFT_RED cycles     | 3.8%         | 8.4%            | 9.0%          |
| RED cycles          | 0%           | 0%              | 0%            |

**Key finding:** RED never fires at any threshold with the current tuning. YELLOW's 8%
per-cycle decay (factor_down_yellow=0.92) prevents delta from ever reaching the RED
boundary. hard_red_bloat_ms effectively controls how quickly the controller escapes
YELLOW by clamping to SOFT_RED's floor. Lower = faster SOFT_RED = faster stabilization.

### Note on UL vs DL parameter differences

Upload and download have DIFFERENT optimal values on DOCSIS cable. Do not assume DL
findings apply to UL. Tested independently via RRUL A/B (2026-04-02):

**UL factor_down: 0.85** (DL uses 0.90):

| Metric              | UL 0.85 (aggressive) | UL 0.90 (gentler) |
| ------------------- | -------------------- | ----------------- |
| ICMP median latency | 40.3ms               | 43.0ms            |
| ICMP 99th pct       | 162ms                | 223ms             |
| UL throughput       | 23.8 Mbps            | 23.0 Mbps         |

**UL step_up_mbps: 1** (DL uses 15):

| Metric              | UL step=1 (gentle) | UL step=2 (faster) |
| ------------------- | ------------------ | ------------------ |
| ICMP median latency | 49.5ms             | 64.1ms             |
| UL throughput       | 20.0 Mbps          | 15.7 Mbps          |
| SOFT_RED/RED cycles | 16%                | 27%                |

The asymmetry is fundamental to DOCSIS: downstream bandwidth is dedicated per-subscriber,
upstream is shared across the node with less headroom. UL needs more aggressive RED decay
(0.85 vs 0.90) and gentler recovery (1 Mbps/step vs 15) to avoid overshooting the
constrained upstream channel.

**linux-cake update (Phase 128):** On linux-cake transport, UL step_up=2 won over 1. UL green_required=3 confirmed (matching DL). See [UL Parameters (linux-cake)](#ul-parameters-linux-cake) for full results.

**Phase 135 update (2026-04-03):** Full 6-config matrix (step_up 3/4/5 x factor_down 0.80/0.90) with 21 RRUL runs reversed the Phase 128 finding on factor_down. **UL factor_down=0.90 now wins** (+17.6% UL throughput), and **step_up=5** is optimal. The earlier 0.85 vs 0.90 test on REST transport was correct for that transport; linux-cake's faster feedback makes gentler decay (0.90) superior.

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

## linux-cake Transport Results (2026-04)

After switching Spectrum from REST API to linux-cake transport (direct tc qdisc manipulation
on cake-shaper VM), all 9 DL parameters were re-tested via RRUL A/B testing (2026-04-02,
17:00-17:36 CDT), followed by a confirmation pass (18:18-18:50 CDT) that re-tested all
changed parameters with the full winner set active. **6 of 9 DL parameters changed, then
confirmation pass reverted target_bloat_ms back to 9.** Full results in
`.planning/phases/127-dl-parameter-sweep/127-DL-RESULTS.md` and
`.planning/phases/129-cake-rtt-confirmation-pass/129-CONFIRMATION-RESULTS.md`.

### REST vs linux-cake Comparison

| Parameter          | REST Winner | linux-cake Winner | Changed? | Key Finding                                                                         |
| ------------------ | ----------- | ----------------- | -------- | ----------------------------------------------------------------------------------- |
| factor_down_yellow | 0.92        | 0.92              | No       | DOCSIS-intrinsic, transport-independent                                             |
| green_required     | 5           | 3                 | YES      | Faster feedback = safe with fewer GREEN cycles                                      |
| step_up_mbps       | 15          | 10                | YES      | Smaller steps avoid overshoot with faster loop                                      |
| factor_down (RED)  | 0.90        | 0.85              | YES      | Deeper RED cuts resolve congestion faster                                           |
| dwell_cycles       | 5           | 5                 | No       | DOCSIS jitter filtering, transport-independent                                      |
| deadband_ms        | 3.0         | 3.0               | No       | Hysteresis margin, transport-independent                                            |
| target_bloat_ms    | 9           | 9                 | No       | Phase 127: 15 won; Phase 129 confirmation: FLIPPED back to 9 (CAKE rtt interaction) |
| warn_bloat_ms      | 45          | 60                | YES      | More headroom between GREEN->YELLOW and SOFT_RED                                    |
| hard_red_bloat_ms  | 60          | 100               | YES      | Needs operating room above warn_bloat_ms=60                                         |

### Recommended linux-cake Cable Parameters

```yaml
cake_params:
  rtt: "40ms" # Optimal ~2x baseline RTT (Phase 129: tested 25-100ms, 40ms dominated)

continuous_monitoring:
  download:
    step_up_mbps: 10 # Moderate ramp (REST used 15)
    factor_down: 0.85 # 15% RED backoff (REST used 0.90)
    factor_down_yellow: 0.92 # 8% YELLOW decay (same as REST)
    green_required: 3 # Faster recovery safe with direct tc (REST used 5)

  upload:
    ceiling_mbps: 32 # 80% of 40Mbps plan — prevents ISP buffer bloat (was 38, production investigation 2026-04-03)
    step_up_mbps: 5 # Phase 135 validated (was 2, +17.6% UL throughput with factor_down=0.90)
    factor_down: 0.90 # Phase 135 validated (was 0.85, gentler decay wins with faster step)
    green_required: 3 # Fast recovery safe with direct tc (REST used 5)

  thresholds:
    target_bloat_ms: 9.0 # GREEN->YELLOW (same as REST -- CAKE rtt=40ms restored tight threshold viability)
    warn_bloat_ms: 60.0 # YELLOW->SOFT_RED (REST used 45)
    hard_red_bloat_ms: 100.0 # SOFT_RED->RED (REST used 60)
    dwell_cycles: 5 # Hysteresis dwell (same as REST)
    deadband_ms: 3.0 # Hysteresis deadband (same as REST)
    load_time_constant_sec: 0.25
```

### Why linux-cake Differs from REST

linux-cake applies rate changes via direct `tc` system calls (~0.1ms) vs REST API HTTP
roundtrips (~15-30ms). This faster feedback loop shifts optimal tuning in two directions:

1. **Response parameters become less aggressive.** The controller acts on fresher data, so
   it can use smaller steps (10 vs 15 Mbps) and recover faster (3 vs 5 GREEN cycles) without
   losing responsiveness. Aggressive steps that were needed on REST to compensate for stale
   data now cause overshoot.

2. **Thresholds become wider** (warn_bloat, hard_red). CAKE's AQM (Cobalt) gets more cycles
   to manage queues before the autorate controller intervenes. The 45ms warn and 60ms hard_red
   thresholds that were necessary on REST now trigger unnecessary state transitions.

**Exception: target_bloat_ms stays at 9.** Phase 127 initially found 15ms winning on linux-cake
(with CAKE rtt=100ms). But Phase 129's confirmation pass -- after lowering CAKE rtt to 40ms --
showed 9ms winning again. The interaction: CAKE rtt=40ms makes the AQM more aggressive at queue
management, restoring the viability of the tight 9ms threshold. This demonstrates that CAKE rtt
and target_bloat_ms are coupled parameters.

The 4 unchanged parameters (factor_down_yellow, dwell_cycles, deadband_ms, target_bloat_ms) are
either DOCSIS-intrinsic or CAKE rtt-dependent -- they don't change with transport speed alone.

**Key interaction change:** On REST, `green_required=5 + step_up=15` worked as a pair (wait
long, ramp fast). On linux-cake, `green_required=3 + step_up=10` replaces it (recover
sooner, ramp gently). The pairing principle still applies -- don't mix REST and linux-cake
values.

### CAKE rtt (linux-cake)

The CAKE `rtt` parameter controls Cobalt AQM's target delay. Lower values make queue management
more aggressive. Tested at 25ms, 35ms, 40ms, 50ms, and 100ms via RRUL A/B testing (2026-04-02,
18:18-18:30 CDT).

| Metric        | 25ms     | 35ms     | 40ms     | 50ms     | 100ms (default) |
| ------------- | -------- | -------- | -------- | -------- | --------------- |
| ICMP median   | 51.20ms  | 49.85ms  | 46.55ms  | 48.90ms  | 55.30ms         |
| ICMP p99      | 135ms    | 128ms    | 113ms    | 141ms    | 184ms           |
| DL throughput | 498 Mbps | 510 Mbps | 522 Mbps | 505 Mbps | 490 Mbps        |

**Winner: 40ms** -- Dominated all metrics: median -16%, p99 -39%, throughput +7% vs default.

The optimal CAKE rtt is approximately 2x the baseline RTT (22-25ms to Dallas). At 40ms, Cobalt
has enough headroom to absorb normal RTT variation without premature drops, while being tight
enough to catch real queue buildup. Below 35ms, good packets start getting dropped (25ms showed
throughput loss). Above 50ms, too much queue slack increases tail latency.

**CRITICAL: CAKE rtt interacts with target_bloat_ms.** Lowering rtt from 100ms to 40ms made
the tight 9ms target_bloat threshold viable again (it had been loosened to 15ms under rtt=100ms).
Always re-test target_bloat_ms after changing CAKE rtt.

**Guideline for other links:** Start with rtt = 2x your baseline RTT. For Dallas at ~22ms,
that's 40-50ms. For a 10ms baseline, try 20-25ms. Always A/B test.

### Confirmation Pass (linux-cake)

After all individual parameter sweeps (Phases 127-128) and the CAKE rtt test (Phase 129), all 7
changed parameters were re-tested with the full winner set active to check for interaction
effects. This catches cases where parameters that won in isolation behave differently when
combined.

| Parameter            | Phase 127/128 Winner | Confirmation Result | Status    |
| -------------------- | -------------------- | ------------------- | --------- |
| DL green_required    | 3                    | 3                   | CONFIRMED |
| DL step_up_mbps      | 10                   | 10                  | CONFIRMED |
| DL factor_down       | 0.85                 | 0.85                | CONFIRMED |
| DL target_bloat_ms   | 15                   | **9** (reverted)    | FLIPPED   |
| DL warn_bloat_ms     | 60                   | 60                  | CONFIRMED |
| DL hard_red_bloat_ms | 100                  | 100                 | CONFIRMED |
| UL step_up_mbps      | 2                    | **5** (Phase 135)   | CHANGED   |

**6 of 7 confirmed, 1 flipped.** The target_bloat_ms flip is the most significant finding:
CAKE rtt=40ms (vs 100ms during Phase 127 testing) makes the AQM aggressive enough that the
tight 9ms threshold no longer triggers false YELLOWs. This validates the confirmation pass
methodology -- without it, production would have run target_bloat=15 which is suboptimal with
rtt=40ms.

Full confirmation results in `.planning/phases/129-cake-rtt-confirmation-pass/129-CONFIRMATION-RESULTS.md`.

### UL Parameters (linux-cake)

Upload parameters tested across 3 rounds: REST (v1.26), linux-cake confirmation (Phase 128), and full matrix (Phase 135).

| Parameter      | REST Winner | linux-cake (P128) | linux-cake (P135) | Current  | Key Finding                                                  |
| -------------- | ----------- | ----------------- | ----------------- | -------- | ------------------------------------------------------------ |
| factor_down    | 0.85        | 0.85              | **0.90**          | **0.90** | Phase 135 reversed P128: gentler decay wins with faster step |
| step_up_mbps   | 1           | 2                 | **5**             | **5**    | Larger step + gentler decay = +17.6% UL throughput           |
| green_required | 5           | 3                 | (not tested)      | 3        | Confirmed sufficient on linux-cake                           |

**Phase 135: UL factor_down=0.90 wins** (reversed Phase 128 finding of 0.85). Full 6-config
matrix (21 RRUL runs): factor_down=0.90 consistently beat 0.80 across all step_up values.
The Phase 128 test was a 2-value comparison (0.85 vs 0.90) with step_up=1-2. Phase 135's
broader matrix revealed that factor_down and step_up interact: gentler decay (0.90) + faster
recovery (step_up=5) produces the best UL throughput (18.34 Mbps avg vs 15.59 baseline, +17.6%).

**Phase 135: UL step_up_mbps=5** (changed from 2). At 13% of ceiling, no oscillation observed.
factor_down=0.90 prevents over-decay, and step_up=5 allows fast ramp-back. The combination
breaks the v1.26 pattern where UL only achieved 10% of ceiling during RRUL.

**UL green_required: 3** -- Not re-tested in Phase 135 (per D-01, not suspected as bottleneck).
Remains at 3 from Phase 128.

**UL vs DL asymmetry on linux-cake:** UL now uses factor_down=0.90 (matching DL), but
step_up=5 (vs DL step_up=15). As a percentage of ceiling: UL step=13.2%, DL step=1.6%.
UL needs proportionally larger steps because the 38 Mbps link has less absolute headroom.

Full Phase 135 results: `.planning/phases/135-upload-recovery-tuning/135-UL-RESULTS.md`

### UL Ceiling Discovery (Post-v1.27 Production Investigation)

**Critical finding:** UL ceiling_mbps has a massive impact on RRUL latency — bigger than any
other parameter change in v1.27.

| Ceiling            | RRUL Median   | vs Baseline | Notes                               |
| ------------------ | ------------- | ----------- | ----------------------------------- |
| 38 Mbps (original) | 173ms         | baseline    | Only 5% ISP headroom — buffer fills |
| 35 Mbps            | 89ms          | -49%        |                                     |
| **32 Mbps**        | **47-95ms**   | **-60%**    | **Winner: 80% of ISP plan**         |
| 30 Mbps            | 70ms + spikes | oscillation | Too low — wanctl fights to maintain |

**Why:** On a 40 Mbps DOCSIS upload plan, ceiling=38 leaves only 2 Mbps before the ISP's CMTS
buffer fills. Once the CMTS buffers, no amount of CAKE tuning can help — the latency is in the
ISP's equipment. At ceiling=32 (80% of plan), the CMTS buffer never fills during sustained upload.

**Rule of thumb:** Set UL ceiling to ~80% of ISP upload speed. The "lost" 20% of capacity is
headroom that prevents ISP-side bufferbloat. CAKE + wanctl can only control what happens BEFORE
the modem — ISP-side buffers are outside their control.

**Also confirmed:** wanctl UL rate management IS valuable. Disabling it (floor=ceiling=32, letting
CAKE handle everything) produced 126ms median vs 47ms with wanctl active. The dynamic rate
shedding during congestion prevents sustained ISP buffer fill that static CAKE can't handle.

Full investigation: `.planning/phases/135-upload-recovery-tuning/135-PRODUCTION-INVESTIGATION.md`

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

## Comprehensive Test Results (v1.26, 2026-04-02)

Tests run from dev machine (real LAN path: dev → MikroTik → cake-shaper bridge → internet).
Config: linux-cake rtt=40ms, all v1.26 validated params active. Afternoon cable plant.

### Results

| Test          | Duration | ICMP Median | ICMP p99    | DL Sum   | UL Sum   | Grade |
| ------------- | -------- | ----------- | ----------- | -------- | -------- | ----- |
| RRUL BE       | 5 min    | 63.00ms     | 269ms       | 420 Mbps | 4.0 Mbps | A-    |
| VoIP          | 60s      | RTT 21.56ms | RTT 39.90ms | —        | —        | A+    |
| tcp_12down    | 60s      | 42.25ms     | 185ms       | 320 Mbps | —        | A     |
| RRUL diffserv | 60s      | 78.90ms     | 844ms       | 602 Mbps | 8.2 Mbps | C-    |

### Analysis

**Strengths:**

- VoIP: zero loss, 2.15ms jitter median, 22ms RTT — flawless
- Download latency under 12-stream load: 42ms median, 185ms p99
- RRUL BE stream fairness: all 4 DL streams within 104-106 Mbps

**Known Issues (future work):**

1. **Cycle budget overrun:** 138% utilization (avg 69ms on 50ms cycle), 51k overruns under RRUL load
2. **UL over-constrained:** 3.9 Mbps under RRUL (10% of 38 Mbps ceiling) — recovery too slow
3. **Diffserv tins not separating:** EF/BE/BK all show same ~78ms latency under diffserv RRUL
4. **Hysteresis suppression:** 9,776 transitions suppressed (~37/min) — monitoring for false negatives
