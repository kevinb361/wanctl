# Pitfalls Research: IRTT Integration, Container Networking, and Signal Processing

**Domain:** Adding IRTT as supplemental RTT source, container networking optimization, and RTT signal quality improvements to a production 24/7 dual-WAN traffic shaper running 50ms control loops
**Researched:** 2026-03-16
**Confidence:** HIGH (grounded in codebase analysis of autorate_continuous.py, rtt_measurement.py, baseline_rtt_manager.py, production profiling data, IRTT official documentation, and container networking research)
**Focus:** Hot-loop timing budget preservation, subprocess overhead in 50ms cycles, UDP reachability, dual-signal fusion correctness, container latency characterization, signal processing regression prevention

---

## Critical Pitfalls

Mistakes that degrade congestion detection, cause measurement regression, or require architectural rework.

---

### Pitfall 1: IRTT Subprocess Overhead Blows 50ms Cycle Budget

**What goes wrong:**
IRTT is a Go binary invoked via `subprocess.run()`. Each invocation requires process creation, Go runtime initialization, UDP socket creation, the IRTT handshake (open packet exchange to negotiate test parameters), the actual measurement, JSON serialization, and process teardown. On Linux, `subprocess.run()` costs 2-5ms for fork+exec alone. The Go runtime adds another 2-8ms for cold start. The IRTT handshake adds a full RTT to the server. Total overhead: 10-50ms per invocation.

The current cycle budget is already tight: profiling shows 41.76ms average for Spectrum RTT measurement (ICMP via icmplib), leaving only ~8ms headroom in the 50ms cycle. Adding a subprocess IRTT call serially would exceed the budget on every single cycle, causing 100% overrun rate and degraded congestion response.

**Why it happens:**
icmplib is an in-process library call with zero fork/exec overhead. IRTT is a compiled Go binary with no Python bindings. The natural implementation is `subprocess.run(["irtt", "client", ...])` with JSON output parsing, following the same pattern used for flent in the benchmark tool. But benchmarks run once; the autorate loop runs 20 times per second indefinitely. A 15ms subprocess overhead that is invisible in a CLI tool is catastrophic in a 50ms hot loop.

**Consequences:**
Every cycle overruns. The `sleep_time = max(0, CYCLE_INTERVAL_SECONDS - elapsed)` calculation goes to zero, meaning cycles run back-to-back with no sleep. Congestion detection still works but at reduced cadence (e.g., 65ms effective interval instead of 50ms). Watchdog timer margin shrinks. Under load (when RTT measurement itself takes longer), cycles could exceed 100ms, halving the control loop frequency at the worst possible time.

**Prevention:**
- NEVER call IRTT subprocess in the autorate hot loop. IRTT must run in a separate thread or process with its own timing.
- Use a "sidecar" measurement pattern: a background thread runs IRTT at its own interval (e.g., 200ms or 1s), stores the latest result in a thread-safe variable (e.g., `threading.Event` + atomic float), and the main loop reads the cached value each cycle with zero blocking.
- The sidecar pattern means IRTT results are "stale" by up to one IRTT interval. This is acceptable because IRTT is supplemental, not primary. The ICMP measurement via icmplib remains the primary hot-path signal.
- Use `subprocess.Popen` with persistent process (long-running IRTT client with `-d` duration flag) instead of spawning a new process per measurement. IRTT supports continuous measurement with `-i 200ms -d 0` (infinite duration) and JSON output on stdout.
- Parse IRTT's streaming JSON output incrementally rather than waiting for process completion.

**Warning signs:**
- IRTT subprocess call inside `measure_rtt()` or `run_cycle()`
- `subprocess.run(["irtt", ...])` called more than once per cycle
- No background thread or async wrapper for IRTT invocation
- Profiling shows `autorate_rtt_measurement` exceeding 50ms after IRTT addition
- No caching layer between IRTT process and the control loop

**Phase to address:**
IRTT integration phase (first phase). The sidecar/background measurement architecture must be the foundation. If IRTT is integrated synchronously into `measure_rtt()` first and then later refactored to async, the intermediate state risks production deployment with degraded performance.

**Confidence:** HIGH -- based on production profiling data (DAY_2_RESULTS.md: 41.76ms avg RTT measurement), Go binary startup benchmarks (2-8ms), and Python subprocess overhead measurements (2-5ms fork+exec).

**Sources:**
- [Python subprocess overhead (issue #11314)](https://bugs.python.org/issue11314)
- [IRTT GitHub](https://github.com/heistp/irtt)
- [IRTT client man page](https://www.mankier.com/1/irtt-client)
- Production profiling: `profiling_data/DAY_2_RESULTS.md`

---

### Pitfall 2: UDP Blocked by ISP or Firewall, No Fallback, Controller Stalls

**What goes wrong:**
IRTT uses UDP port 2112 (default) for its measurement protocol. Many ISPs, corporate firewalls, and even home router default rules block arbitrary outbound UDP ports. If the IRTT server is unreachable, the IRTT client hangs until its connection timeout (default varies but can be several seconds). If the controller depends on IRTT for any part of its decision-making and has no fallback, it either stalls waiting for the timeout or makes decisions with stale/missing data.

Spectrum and AT&T residential connections are known to have varying UDP filtering policies. Even if UDP 2112 works today, ISP-side policy changes can break it silently (exactly what happened with ICMP in v1.1.0 -- the "ICMP Blackout" that required the TCP RTT fallback).

**Why it happens:**
ICMP (used by icmplib) traverses most networks because routers use it for path MTU discovery and traceroute. UDP on non-standard ports has no such privileged status. The self-hosted IRTT server on Dallas (104.200.21.31) requires outbound UDP 2112 from both LXC containers through the host network stack and both ISP uplinks. Any layer that drops or rate-limits the UDP packets will cause measurement failures.

**Consequences:**
If IRTT is treated as a required signal and UDP is blocked:
- Background IRTT thread reports continuous failures, providing no useful data
- If the fusion algorithm requires both signals to be present, it falls back to icmplib-only mode (wasting the IRTT integration entirely) or worse, refuses to make decisions
- If the connection timeout is too long (>1s), the background thread consumes resources waiting
- If IRTT failures trigger alerts, the operator gets spammed with false WAN-offline notifications

**Prevention:**
- IRTT MUST be strictly supplemental ("nice to have"), never required. The controller must function identically with IRTT unavailable as it does today.
- Implement a connectivity check on startup: attempt one IRTT handshake per server. If all servers are unreachable, log a warning and disable IRTT measurement entirely (do not retry in the hot loop).
- Use exponential backoff for IRTT server reconnection attempts (similar to the existing `RouterConnectivityState` pattern for REST-to-SSH failover).
- Set aggressive IRTT client timeouts: connection timeout ~500ms, per-packet timeout ~200ms. An IRTT measurement that takes longer than ICMP provides no benefit for signal fusion.
- Make the IRTT server configurable (not just 104.200.21.31). Support a list of servers with fallback, similar to the existing `ping_hosts` list for ICMP reflectors.
- Consider using a non-standard port for the self-hosted IRTT server (e.g., 443 or 53) to reduce ISP filtering risk, though this trades off against discoverability.

**Warning signs:**
- IRTT failure causes `measure_rtt()` to return None
- No `irtt_available` boolean guard in the measurement path
- IRTT timeout exceeds 1 second
- No startup connectivity validation for IRTT servers
- Alert engine fires `wan_offline` when only IRTT (not ICMP) fails

**Phase to address:**
IRTT integration phase. The "supplemental, not required" architecture must be established in the very first implementation. If IRTT is initially wired as a primary signal and later demoted to supplemental, the fusion algorithm has to be redesigned.

**Confidence:** HIGH -- ICMP blackout precedent in this exact codebase (v1.1.0), UDP port filtering is well-documented ISP behavior.

**Sources:**
- [IRTT server man page - port 2112 default](https://www.mankier.com/1/irtt-server)
- [ISP UDP blocking discussion](https://forum.netgate.com/topic/152764/how-to-solve-isp-blocking-remote-udp-port)
- wanctl CHANGELOG.md (v1.1.0 ICMP Blackout fix)

---

### Pitfall 3: Dual-Signal Fusion Creates Oscillation or Decision Conflicts

**What goes wrong:**
When ICMP and IRTT disagree on network state, the fusion algorithm must decide which signal to trust. A naive approach (e.g., average the two RTTs) produces a value that represents neither the true ICMP path nor the true UDP path. If ICMP shows 30ms and IRTT shows 80ms, the average (55ms) triggers a moderate response when the correct action depends on WHY they disagree:
- If the ISP is prioritizing ICMP (common), IRTT is the more accurate signal and should be trusted.
- If the IRTT server is having issues, ICMP is correct and IRTT should be discarded.
- If both are valid but measuring different paths, neither average is meaningful.

Worse: if the fusion switches between "trust ICMP" and "trust IRTT" on a cycle-by-cycle basis, the effective RTT signal oscillates, causing the congestion state machine to flap between GREEN and YELLOW/RED. This produces the exact bufferbloat the system is designed to prevent (rapid rate changes cause queue drain/fill oscillation).

**Why it happens:**
ICMP and UDP take different kernel code paths and may be treated differently by QoS policies, ISP traffic management, and router queuing. ICMP packets are often prioritized or rate-limited separately from UDP. The two signals are not measuring the same thing even when they arrive at the same destination host.

The existing EWMA architecture assumes a single RTT input per cycle. The `update_ewma(measured_rtt)` method takes one float. Feeding it alternating ICMP and IRTT values without normalization will cause the EWMA to oscillate between two attractors, producing a noisy signal that triggers false state transitions.

**Consequences:**
- Congestion flapping (ALRT-07) fires repeatedly
- Rate oscillation: controller bounces between rate reduction and rate increase
- Baseline drift: if IRTT RTT is consistently higher than ICMP, baseline EWMA drifts upward, masking real congestion
- Dashboard shows unstable RTT sparklines that confuse the operator

**Prevention:**
- Maintain separate EWMA tracks for each signal source. Do not mix ICMP and IRTT values in the same EWMA chain. Each signal gets its own `load_rtt` and `baseline_rtt`.
- The congestion decision should be based on the PRIMARY signal (ICMP, as today) with IRTT providing a "confirmation" or "enhancement" role. Specifically: IRTT can make the congestion assessment WORSE (if IRTT shows high latency when ICMP is normal, trust IRTT) but should NOT make it BETTER (if IRTT shows low latency when ICMP shows congestion, do not override ICMP).
- This "max severity" fusion is analogous to the existing WAN-aware steering pattern where `WAN_RED=25` amplifies the confidence score but cannot cancel CAKE-detected congestion.
- Consider IRTT as a separate "congestion signal" alongside CAKE drops and queue depth, rather than as a replacement for the ICMP RTT input. The existing multi-signal detection architecture (RTT + CAKE drops + queue depth) already has a pattern for combining independent signals.
- Implement a disagreement detector: if ICMP and IRTT consistently disagree by >Xms for >Y seconds, log a warning and weight the more conservative signal. Do not silently average conflicting signals.

**Warning signs:**
- Single `measured_rtt` variable that alternates between ICMP and IRTT sources
- IRTT value fed directly into `update_ewma()` without separate tracking
- No "which signal is authoritative" logic in the fusion code
- Test suite does not cover ICMP/IRTT disagreement scenarios
- No alerting for sustained signal disagreement

**Phase to address:**
Signal processing phase (after IRTT integration). The fusion architecture should be designed before any IRTT data is wired into the congestion state machine. A clear protocol (what IRTT can and cannot influence) prevents ad-hoc fusion logic.

**Confidence:** HIGH -- the oscillation risk is a well-known problem in multi-signal control systems, and cake-autorate's development history documents extensive work on reflector disagreement handling.

**Sources:**
- [cake-autorate reflector rotation and signal quality](https://github.com/lynxthecat/cake-autorate)
- [TIMELY: RTT-based Congestion Control](https://conferences.sigcomm.org/sigcomm/2015/pdf/papers/p537.pdf)
- [Jitterbug: jitter-based congestion inference](https://www.caida.org/catalog/papers/2022_jitterbug/jitterbug.pdf)
- wanctl codebase: `autorate_continuous.py` lines 1239-1295 (EWMA update)

---

### Pitfall 4: Container Networking Optimization Disrupts Running Daemons

**What goes wrong:**
Changing the container networking mode (e.g., from veth/bridge to macvlan, or adjusting MTU, txqueuelen, or ring buffer sizes) on a running LXC container either requires container restart or causes a brief network interruption. During the interruption:
- All in-flight ICMP and IRTT probes fail
- The autorate daemon detects "all pings failed" and enters ICMP failure handling
- After `icmp_unavailable_threshold` consecutive failures, the controller enters freeze mode (holds current rates)
- If the interruption is long enough (>5s), the watchdog timer may fire, causing systemd to restart the service
- On service restart, the controller loads stale state from the JSON state file, potentially with an outdated baseline RTT

**Why it happens:**
LXC container networking changes (interface type, bridge configuration, IP addressing) often require tearing down and recreating the veth pair or switching to a macvlan interface. Even "online" MTU changes can cause brief packet loss. The wanctl daemon running inside the container has no way to distinguish "network reconfiguration in progress" from "WAN link failure" -- both look like ICMP timeout.

Research shows veth/bridge networking adds 10-17% latency overhead compared to macvlan. Switching from veth to macvlan would reduce measurement noise, but the transition itself is risky.

**Consequences:**
- Temporary loss of congestion detection during container networking change (30s-2min)
- Possible watchdog-triggered restart that resets EWMA state (baseline_rtt, load_rtt, streak counters)
- If optimization requires container restart, both WANs lose control simultaneously
- If macvlan is used, host-to-container communication changes (macvlan containers cannot communicate with the host via the macvlan interface -- must use a separate veth for management traffic)
- Health endpoint becomes unreachable during transition, dashboard shows WAN offline

**Prevention:**
- Characterize container networking FIRST (measure veth overhead without changing anything). The characterization data informs whether optimization is worth the risk.
- If switching to macvlan, plan a staged rollout: one WAN at a time, with the other WAN providing backup traffic shaping. Never change both containers simultaneously.
- Pre-flight the optimization on a test container (create a temporary LXC container with the target networking config, run a measurement comparison, then apply to production).
- Extend the daemon to detect "startup networking delay" (similar to the existing 30s WAN-aware steering grace period) and suppress alerts during the first 30s after a network interface change.
- Consider whether the veth overhead (10-17% latency, which is ~4-6ms on a 30ms baseline) actually matters for congestion DETECTION. The controller cares about RTT delta (not absolute RTT). If veth adds a consistent 5ms offset, the delta is unaffected and the overhead is irrelevant to control quality. Only variable overhead (jitter added by veth) affects detection quality.
- Document the existing container networking configuration BEFORE making changes. Capture: interface type, MTU, txqueuelen, bridge settings, IP configuration.

**Warning signs:**
- Both containers scheduled for networking changes at the same time
- No pre-change baseline measurement data
- No rollback plan documented
- Optimization focuses on absolute RTT reduction rather than jitter reduction
- macvlan adoption without considering host-to-container management communication

**Phase to address:**
Container networking phase (dedicated phase). Must include a characterization sub-phase before any optimization. The sequence is: measure current overhead, quantify jitter contribution, decide if optimization is warranted, plan staged rollout, execute.

**Confidence:** HIGH -- container networking overhead is well-documented in academic literature, and the production disruption risk is evident from the existing daemon architecture.

**Sources:**
- [Performance of Container Networking Technologies (ACM)](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406)
- [Container Networking Performance Analysis](https://www.scirp.org/html/95740_95740.htm)
- [Macvlan vs network bridge (Linux Containers Forum)](https://discuss.linuxcontainers.org/t/macvlan-vs-network-bridge/465)
- wanctl docs: `docs/DOCKER.md` line 174 ("Use --network host... Bridge networking adds latency")

---

## Moderate Pitfalls

Mistakes that waste development time, reduce measurement quality, or create maintenance burden.

---

### Pitfall 5: IRTT Long-Running Process Management Complexity

**What goes wrong:**
Using a persistent IRTT process (to avoid per-cycle subprocess overhead) introduces process lifecycle management: the background thread must detect IRTT process crashes, handle stderr output, parse incomplete JSON from a crashed process, restart the process with backoff, and clean up zombie processes. If the IRTT process hangs (e.g., server stops responding), the background thread must detect the hang (no output for N seconds) and force-kill the process.

This is the exact complexity that was avoided when icmplib replaced subprocess ping in v1.9: icmplib is an in-process library call with no process management overhead. Adding a persistent subprocess reintroduces the complexity that was deliberately eliminated.

**Why it happens:**
There is no Python IRTT library. IRTT is a Go binary. The only interface is subprocess. The sidecar pattern (Pitfall 1 prevention) requires a long-running subprocess, which requires lifecycle management.

**Prevention:**
- Use `subprocess.Popen` with `stdout=subprocess.PIPE` and non-blocking reads (via `select` or a dedicated reader thread).
- Implement a `IRTTProcess` class that encapsulates all lifecycle management: start, health check (is process alive?), restart with backoff, graceful shutdown, and zombie cleanup.
- Set a "liveness timeout": if no IRTT output received for >5 seconds, kill and restart the process.
- On daemon shutdown (SIGTERM), ensure the IRTT subprocess is terminated in the cleanup sequence (add to the existing `_cleanup_resources` shutdown handler).
- Register the IRTT process PID for cleanup via `atexit` as a safety net against unclean shutdown.
- Consider an alternative: instead of a persistent IRTT process, run short IRTT measurements (e.g., `-d 1s -i 50ms`) periodically from a background thread. Each measurement is self-contained with clean startup/teardown. The overhead per measurement (~20 packets, ~50ms Go startup) is acceptable at a 5-10 second cadence.

**Warning signs:**
- No process health monitoring (checking `process.poll()` for unexpected exit)
- No stderr capture (IRTT errors silently discarded)
- Zombie processes accumulating (visible in `ps aux` output)
- Daemon shutdown leaves orphaned IRTT processes
- No backoff on IRTT process restart (crash loop)

**Phase to address:**
IRTT integration phase. The `IRTTProcess` lifecycle manager should be a self-contained module with its own tests, developed and validated before wiring into the autorate daemon.

**Confidence:** MEDIUM -- the severity depends on whether the persistent-process or periodic-invocation approach is chosen. Periodic invocation is simpler but wastes the Go startup overhead.

---

### Pitfall 6: Signal Processing Changes Silently Degrade Congestion Detection

**What goes wrong:**
Adding outlier filtering, jitter tracking, or confidence intervals to the RTT signal processing chain changes the input to the existing congestion state machine. The state machine's thresholds (`target_delta`, `warn_delta`, `soft_red_threshold`, `hard_red_threshold`, `accel_threshold`) were tuned for raw ICMP RTT values processed through the existing EWMA. If a new filter (e.g., median filter, Hampel filter, or outlier clipper) is inserted upstream of the EWMA, the effective signal characteristics change:

- A median filter removes spikes, which means the `accel_threshold` spike detector becomes redundant or never fires (its purpose IS to catch spikes that EWMA smooths over).
- An outlier clipper that removes values >Xms above the rolling average will mask genuine congestion spikes, delaying RED state detection.
- A confidence interval that "holds" the previous value during low-confidence periods creates artificial plateaus that prevent the EWMA from tracking rapid changes.

The controller appears to work but responds 100-500ms slower to congestion, which defeats the purpose of the 50ms control loop.

**Why it happens:**
Signal processing improvements "feel" like they should make things better. Removing outliers and reducing noise sounds like it should improve decision quality. But the congestion state machine was designed and tuned for a signal that INCLUDES occasional spikes and noise. The spikes are not noise -- they are the first sign of congestion. Filtering them delays detection.

The existing `delta_accel` detector (lines 1650-1660 in autorate_continuous.py) is specifically designed to catch sharp RTT increases that the EWMA would smooth over. Adding an upstream filter that removes these sharp increases makes the acceleration detector useless while also making the EWMA slower to respond (because it never sees the spike).

**Consequences:**
- Congestion detection time increases from 50-100ms to 200-500ms (4-10x slower)
- Threshold recalibration needed (all production-tuned thresholds become wrong)
- A/B testing required to validate any signal processing change (cannot just "deploy and see")
- If the operator does not have profiling data from before the change, degradation is invisible

**Prevention:**
- Any signal processing change MUST be validated against recorded production data. Replay historical RTT sequences through the new filter and compare state machine outputs (zones, rates, transition timing) with the current processing chain.
- Never insert a filter upstream of the EWMA without simultaneously evaluating its impact on the acceleration detector (`delta_accel`).
- Outlier filtering should be per-cycle (within a single median-of-three measurement) rather than across cycles. The existing `median-of-three` reflector strategy already provides per-cycle outlier robustness. Cross-cycle filtering (e.g., "reject this cycle's RTT because it is >3 sigma from the rolling mean") removes the signal the controller needs.
- Jitter tracking should be observational (exposed via health endpoint and metrics) rather than filtering (modifying the signal). Track jitter as a separate metric for operator visibility without altering the control loop input.
- If confidence intervals are implemented, they should affect the RATE of response (e.g., less confident = slower rate changes) rather than the RTT value itself. This preserves the signal fidelity while allowing the controller to be cautious when measurement quality is low.
- Implement a "signal processing bypass" flag for A/B comparison: `signal_processing.enabled: false` in config disables all new processing and reverts to raw ICMP -> EWMA -> state machine.

**Warning signs:**
- RTT value fed to `update_ewma()` has been modified by a filter after `measure_rtt()` returns
- The acceleration detector (`delta_accel > self.accel_threshold`) never fires after signal processing changes
- Congestion detection time (measured by dashboard or profiling) increases after deployment
- State machine thresholds are changed to "compensate" for the new signal characteristics
- No before/after comparison data collected during development

**Phase to address:**
Signal processing phase (final phase). Must include a replay/simulation validation step using recorded production RTT data, and must include a bypass/disable mechanism for safe rollback.

**Confidence:** HIGH -- this is a fundamental control systems principle: changing the sensor characteristics requires re-tuning the controller.

**Sources:**
- [Jitterbug: jitter-based congestion inference](https://www.caida.org/catalog/papers/2022_jitterbug/jitterbug.pdf)
- [Generalized Hampel Filters](https://link.springer.com/article/10.1186/s13634-016-0383-6)
- [Online Outlier Detection in Time Series](https://www.baeldung.com/cs/time-series-online-outlier-detection)
- wanctl codebase: `autorate_continuous.py` lines 1649-1661 (acceleration detector)

---

### Pitfall 7: IRTT Server on Self-Hosted VPS Becomes Single Point of Failure

**What goes wrong:**
The IRTT server on Dallas (104.200.21.31) becomes the sole source of UDP RTT measurements. If the VPS goes down (maintenance, billing, DDoS, provider issue), has a routing change, or the IRTT daemon crashes, all IRTT measurements fail. If the fusion algorithm gives significant weight to IRTT data, this causes measurement quality degradation across both WANs simultaneously.

Unlike ICMP reflectors (1.1.1.1, 8.8.8.8, 9.9.9.9) which are operated by major infrastructure providers with >99.99% uptime, a self-hosted VPS has no SLA and no redundancy.

**Why it happens:**
IRTT requires a running server (`irtt server`) on the remote host. Public IRTT reflectors are rare (unlike ICMP, where any host responds to ping). The self-hosted server is the path of least resistance for getting IRTT working.

**Prevention:**
- Support multiple IRTT servers in configuration, similar to `ping_hosts`. If one server is unreachable, measure against the next.
- Consider running IRTT servers on multiple VPS providers for redundancy.
- IRTT measurement unavailability MUST NOT degrade the controller below its current icmplib-only performance. This is a restatement of the "supplemental, not required" principle from Pitfall 2.
- Monitor IRTT server uptime from outside the wanctl system (e.g., simple cron job that attempts IRTT handshake and alerts on failure).
- If only one IRTT server is available, set `irtt.weight` to a value where its absence has minimal impact on the fusion output (e.g., IRTT contributes a 10-15% adjustment, not a 50% blend).

**Warning signs:**
- Single IRTT server configured with no fallback
- IRTT server failures cause alert storms
- Fusion algorithm treats IRTT unavailability as "network problem"
- No monitoring of IRTT server availability independent of wanctl

**Phase to address:**
IRTT integration phase. Multi-server support should be in the initial implementation, not added later.

**Confidence:** MEDIUM -- the VPS is currently operational, but single-point-of-failure is a design issue, not an operational emergency.

---

### Pitfall 8: Baseline RTT Diverges Between ICMP and IRTT Tracks

**What goes wrong:**
If separate EWMA tracks are maintained for ICMP and IRTT (as recommended in Pitfall 3), their baselines will naturally differ because ICMP and UDP traverse different kernel paths and may be treated differently by ISP traffic management. The ICMP baseline might be 30ms while the IRTT baseline is 35ms. These are both "correct" baselines for their respective protocols.

The problem arises when the fusion algorithm compares deltas: ICMP delta of 10ms and IRTT delta of 10ms represent the same amount of congestion. But if the fusion compares raw RTT values (not deltas), the IRTT signal always looks "worse" because its baseline is higher. The controller overreacts to IRTT data, reducing rates when the network is actually fine.

**Why it happens:**
The existing architecture is entirely delta-based (all control decisions use `load_rtt - baseline_rtt`). But when adding a second signal source, the temptation is to compare absolute RTT values between sources ("IRTT shows 80ms, ICMP shows 50ms, something is wrong!"). Absolute comparison ignores that the two protocols have different baseline characteristics.

**Prevention:**
- Always fuse DELTAS, never absolute RTT values. ICMP delta and IRTT delta are comparable; ICMP RTT and IRTT RTT are not.
- Each signal source maintains its own baseline via its own EWMA with the same alpha parameters. The baselines are independent.
- The fusion algorithm operates on normalized deltas: `(load_rtt - baseline_rtt) / baseline_rtt` gives a percentage increase that is comparable across protocols regardless of baseline differences.
- Document the expected baseline difference between ICMP and IRTT for each WAN in operational notes. A consistent 5ms difference is normal; a 50ms difference suggests a routing or QoS anomaly.

**Warning signs:**
- Fusion code compares `icmp_rtt` to `irtt_rtt` (absolute values)
- IRTT consistently triggers congestion when ICMP does not
- Baseline RTT in health endpoint shows a single value (should show per-source baselines)
- No normalization of signals before fusion

**Phase to address:**
Signal processing phase. The delta normalization must be part of the fusion algorithm design.

**Confidence:** HIGH -- this is a direct consequence of the dual-signal architecture and is well-understood in multi-sensor fusion literature.

---

## Minor Pitfalls

Issues that create friction but do not cause production incidents.

---

### Pitfall 9: IRTT JSON Output Parsing Assumes Stable Format

**What goes wrong:**
IRTT's JSON output format has a `json_format` version number, but the format has not changed frequently. The parser hardcodes field paths like `stats.rtt.mean` or `round_trips[i].delay.rtt`. An IRTT binary update changes field names or nesting, and the parser silently returns None or crashes.

**Prevention:**
- Pin the IRTT binary version in deployment documentation and container images.
- Parse defensively with `.get()` chains and validation of expected structure.
- Include the IRTT version string in health endpoint output for debugging.
- Write a small integration test that runs `irtt client -o -` against a known server and validates the JSON structure matches expectations.

**Warning signs:**
- Direct dictionary key access (`result["stats"]["rtt"]["mean"]`) without `.get()` fallbacks
- No IRTT version validation on startup
- No schema/structure tests for IRTT JSON output

**Phase to address:**
IRTT integration phase. Defensive parsing is a one-time implementation effort.

**Confidence:** LOW -- IRTT JSON format has been stable, but the risk is non-zero.

---

### Pitfall 10: Container Networking Characterization Conflates Measurement Noise with Real Overhead

**What goes wrong:**
When characterizing veth/bridge overhead, the measurement methodology itself introduces noise. Running `ping` from inside the container to a local target measures veth + bridge + host networking + target latency. The veth/bridge component might be 0.1-0.5ms, but the measurement jitter is 1-5ms. The characterization concludes "veth overhead is 3ms" when actually veth overhead is 0.2ms and the rest is measurement noise.

This leads to premature optimization: switching to macvlan to "save 3ms" when the real savings is 0.2ms, and the complexity and risk of macvlan adoption are not justified.

**Prevention:**
- Use high-resolution timing (`time.perf_counter_ns()`) and statistical analysis (median of 1000+ samples, percentile analysis, not just mean).
- Measure veth overhead by comparing container-to-local-gateway vs host-to-local-gateway ping times (both bypass the WAN, isolating the container networking component).
- Focus on JITTER (variability) not absolute latency. For the congestion controller, consistent 5ms overhead does not matter (the baseline EWMA absorbs it). Variable 0-10ms overhead matters because it creates noise in the delta signal.
- Run characterization under different load conditions: idle, moderate traffic, heavy traffic. Veth overhead may increase non-linearly under load due to the single-kernel-thread bridge packet processing.

**Warning signs:**
- Characterization uses fewer than 100 samples
- Only mean is reported (not percentiles)
- No comparison between container and host measurements
- Jitter not separately quantified
- Characterization run only at idle (not under load)

**Phase to address:**
Container networking phase (characterization sub-phase, before any optimization).

**Confidence:** MEDIUM -- measurement methodology is a general best practice, specific to this system's sensitivity to jitter.

---

### Pitfall 11: IRTT HMAC Key Management Adds Operational Complexity

**What goes wrong:**
For a private IRTT server, HMAC authentication prevents unauthorized use. The HMAC key must be configured on both the server and all clients (both LXC containers). If the key rotates, both containers need to be updated. If the key is stored in the YAML config file, it is another secret to manage alongside the router password.

**Prevention:**
- If the IRTT server is on a private IP (unlikely since it is 104.200.21.31), skip HMAC.
- If HMAC is used, follow the existing pattern: store the key in `/etc/wanctl/secrets` alongside the router password, reference via `${IRTT_HMAC_KEY}` environment variable substitution.
- If the IRTT server only serves wanctl (not public), consider firewall-based access control (allow only the two WAN IP addresses) instead of HMAC. Simpler, no key management.

**Warning signs:**
- HMAC key hardcoded in config YAML (not in secrets file)
- No documentation for key rotation procedure

**Phase to address:**
IRTT integration phase. Decide HMAC vs firewall access control upfront.

**Confidence:** LOW -- operational complexity, not a correctness risk.

---

### Pitfall 12: EWMA Dual-Alpha Pattern from cake-autorate Applied Without Understanding

**What goes wrong:**
cake-autorate uses separate EWMA alpha values for baseline increase vs decrease (asymmetric smoothing). This pattern is useful for tracking the minimum OWD (one-way delay) by making baseline decrease fast (track new minimums quickly) and baseline increase slow (resist upward drift). Blindly copying this pattern into wanctl without understanding the existing baseline update architecture breaks the idle-only baseline invariant.

In wanctl, the baseline ONLY updates when `delta < baseline_update_threshold` (line is idle). Asymmetric alpha is irrelevant because updates only happen during idle periods when the delta is already small. Adding asymmetric alpha to the load EWMA would change the controller's response characteristics in ways that interact unpredictably with the existing hysteresis counters.

**Prevention:**
- Understand the difference between cake-autorate's architecture (OWD-based, continuous baseline tracking) and wanctl's architecture (RTT-based, idle-only baseline, delta-driven state machine).
- Do not import patterns from cake-autorate without validating they make sense in wanctl's context.
- If asymmetric alpha is desired, it should be applied to the IRTT-specific EWMA track (which may have different characteristics) rather than the existing ICMP track.

**Warning signs:**
- Separate `alpha_baseline_up` / `alpha_baseline_down` config params added to existing ICMP EWMA
- `_update_baseline_if_idle()` modified to use asymmetric alpha
- cake-autorate code patterns copied without adaptation

**Phase to address:**
Signal processing phase. Only relevant if EWMA tuning is part of the signal quality improvements.

**Confidence:** MEDIUM -- depends on whether the developer is familiar with cake-autorate patterns.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| IRTT integration | Subprocess overhead blows cycle budget (P1) | Sidecar pattern: background thread with cached result, never in hot loop |
| IRTT integration | UDP blocked by ISP (P2) | Supplemental-only architecture, startup connectivity check, exponential backoff |
| IRTT integration | Server single point of failure (P7) | Multi-server config, low IRTT fusion weight |
| IRTT integration | Process lifecycle complexity (P5) | Self-contained `IRTTProcess` class, periodic short runs vs persistent process |
| Container networking | Optimization disrupts running daemons (P4) | Characterize first, staged rollout, one WAN at a time |
| Container networking | Conflating noise with overhead (P10) | High-sample statistical analysis, focus on jitter not absolute latency |
| Signal processing | Dual-signal fusion oscillation (P3) | Separate EWMA tracks, max-severity fusion, IRTT amplifies only |
| Signal processing | Filter degrades congestion detection (P6) | Replay validation, preserve acceleration detector, observational jitter tracking |
| Signal processing | Baseline divergence (P8) | Fuse deltas not absolutes, normalize by baseline, independent EWMA per source |
| Signal processing | Importing cake-autorate patterns blindly (P12) | Understand idle-only baseline invariant, validate pattern applicability |

---

## Integration Risk Summary

The three features (IRTT, container optimization, signal processing) interact in cascading ways:

1. **IRTT depends on container networking**: IRTT UDP packets traverse the container veth/bridge. Container networking optimization changes IRTT measurement characteristics. IRTT integration should be validated BEFORE container changes, and re-validated AFTER.

2. **Signal processing depends on IRTT**: The fusion algorithm requires IRTT data to be available and characterized. Signal processing design should not start until IRTT is producing stable measurements.

3. **Container optimization is independent but disruptive**: It can be done in any order but disrupts both ICMP and IRTT measurements during the change. Best done as a middle phase with established measurement baselines from both ICMP and IRTT.

**Recommended phase order based on pitfall analysis:**
1. IRTT integration (establishes supplemental measurement, sidecar architecture)
2. Container networking characterization and optimization (uses both ICMP and IRTT to validate changes)
3. Signal processing and fusion (uses stable dual-signal data to design and validate fusion algorithm)

---

## Sources

- [IRTT GitHub - Isochronous Round-Trip Tester](https://github.com/heistp/irtt)
- [IRTT client man page](https://www.mankier.com/1/irtt-client)
- [IRTT server man page](https://www.mankier.com/1/irtt-server)
- [cake-autorate - CAKE adaptive bandwidth](https://github.com/lynxthecat/cake-autorate)
- [sqm-autorate - SQM bandwidth adjustment](https://github.com/sqm-autorate/sqm-autorate)
- [Performance of Container Networking Technologies (ACM 2017)](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406)
- [Container Networking Performance Analysis](https://www.scirp.org/html/95740_95740.htm)
- [Macvlan vs network bridge discussion](https://discuss.linuxcontainers.org/t/macvlan-vs-network-bridge/465)
- [TIMELY: RTT-based Congestion Control](https://conferences.sigcomm.org/sigcomm/2015/pdf/papers/p537.pdf)
- [Jitterbug: jitter-based congestion inference](https://www.caida.org/catalog/papers/2022_jitterbug/jitterbug.pdf)
- [Generalized Hampel Filters (signal processing)](https://link.springer.com/article/10.1186/s13634-016-0383-6)
- [Online Outlier Detection in Time Series](https://www.baeldung.com/cs/time-series-online-outlier-detection)
- [Python subprocess overhead (CPython issue #11314)](https://bugs.python.org/issue11314)
- [ISP UDP port blocking discussion](https://forum.netgate.com/topic/152764/how-to-solve-isp-blocking-remote-udp-port)
- Production profiling data: `profiling_data/DAY_1_RESULTS.md`, `profiling_data/DAY_2_RESULTS.md`
- wanctl codebase: `src/wanctl/autorate_continuous.py`, `src/wanctl/rtt_measurement.py`, `src/wanctl/baseline_rtt_manager.py`
- wanctl docs: `docs/PRODUCTION_INTERVAL.md`, `docs/DOCKER.md`
