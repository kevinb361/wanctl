# Pitfalls Research: CAKE Optimization & Bufferbloat Benchmarking

**Domain:** Adding CAKE parameter auto-fix via RouterOS REST API and flent/netperf-based bufferbloat benchmarking to a production 24/7 dual-WAN controller
**Researched:** 2026-03-13
**Confidence:** HIGH (grounded in codebase analysis of existing check_cake.py, routeros_rest.py, calibrate.py, load_generator.py, autorate_continuous.py, and MikroTik official documentation)
**Focus:** Router write safety, benchmark-controller interaction, CAKE parameter semantics, ATT/Spectrum link-layer correctness, production disruption prevention

---

## Critical Pitfalls

Mistakes that cause live traffic outages, router misconfiguration, or require significant rework.

---

### Pitfall 1: `--fix` Writes CAKE Parameters to Wrong RouterOS Endpoint

**What goes wrong:**
The auto-fix code modifies CAKE parameters (`cake-rtt`, `cake-overhead-scheme`, `cake-flowmode`, etc.) by PATCHing `/rest/queue/tree/{id}`. This silently succeeds (RouterOS ignores unknown properties on PATCH) or fails with a confusing error. The actual CAKE parameters are properties of the **queue type** (at `/rest/queue/type`), not the queue tree entry. Queue tree entries only reference a queue type by name (e.g., `queue=cake-down-spectrum`). The operator thinks the fix was applied, runs a benchmark, sees no improvement, and wastes hours debugging.

**Why it happens:**
The existing `check_cake.py` already audits queue tree entries (`/rest/queue/tree`) and reports the queue type name. The existing `routeros_rest.py` only has methods for `/queue/tree` operations (`_handle_queue_tree_set`, `set_queue_limit`, `get_queue_stats`). There is no code anywhere in the codebase that queries or modifies `/queue/type`. The developer naturally extends the existing queue tree PATCH code for `--fix`, not realizing CAKE parameters live on a different resource.

The RouterOS two-level queue model:
- **Queue tree** (`/queue/tree`): entries with `name`, `parent`, `max-limit`, `queue` (references a queue type by name)
- **Queue type** (`/queue/type`): type definitions with `name`, `kind=cake`, `cake-rtt`, `cake-overhead-scheme`, `cake-flowmode`, `cake-diffserv`, etc.

**How to avoid:**
- The `--fix` code MUST operate on `/rest/queue/type`, not `/rest/queue/tree`
- Two-step workflow: (1) GET `/rest/queue/tree?name=WAN-Download-Spectrum` to read `queue` field (e.g., `"cake-down-spectrum"`), then (2) PATCH `/rest/queue/type/{id}` where ID is found by GET `/rest/queue/type?name=cake-down-spectrum`
- Add a new method `_find_queue_type_id(type_name)` to the router client (similar pattern to existing `_find_queue_id`)
- Add a new method `get_queue_type(type_name)` that returns CAKE-specific parameters
- Test with a real RouterOS response: the queue tree entry does NOT contain `cake-rtt` or `cake-overhead-scheme` -- those are on the type
- The detection phase (extending `check_cake.py` for sub-optimal settings) also needs the queue type query

**Warning signs:**
- Fix code calls `client._find_queue_id()` instead of a queue type ID lookup
- Fix code PATCHes a URL containing `/queue/tree/` with CAKE parameter fields
- Test fixtures include `cake-rtt` in queue tree response data (not how RouterOS works)
- No GET request to `/rest/queue/type` anywhere in the implementation

**Phase to address:**
Detection phase (first phase). The queue type query must be implemented and tested before any fix logic is written. The detection and fix share the same query infrastructure.

---

### Pitfall 2: Benchmark Triggers Autorate Controller, Invalidating Results

**What goes wrong:**
The flent/netperf RRUL test generates 8 bidirectional TCP streams that saturate the link. The running wanctl autorate controller detects the resulting RTT spike as congestion within 50-100ms and aggressively reduces CAKE max-limit (down to floor_red_mbps). The benchmark measures throughput against a throttled link, not the connection's true capacity. Results show artificially low throughput and the operator incorrectly concludes the CAKE settings are wrong.

Worse: the controller's rate changes happen mid-benchmark, creating a jagged throughput graph that is neither the shaped performance nor the unshaped performance -- it is a hybrid that is useless for analysis.

**Why it happens:**
wanctl runs at 20Hz (50ms cycles) with sub-second congestion detection. An RRUL test that ramps up over 2-5 seconds will trigger multiple state transitions (GREEN -> YELLOW -> SOFT_RED -> RED) within the first few seconds. The controller's `factor_down: 0.85` reduces bandwidth by 15% per cycle in RED state, potentially cutting throughput by 50%+ within 1-2 seconds of the test starting.

The existing `calibrate.py` already has this problem: it calls `set_cake_limit()` to set rates during binary search but does not coordinate with a running daemon. However, calibration is designed to run when the daemon is NOT running. The new benchmark tool needs to work while the daemon IS running to measure "how well is wanctl controlling bufferbloat."

**How to avoid:**
- Define two distinct benchmark modes:
  1. **Capacity test** (daemon paused): Measures raw link capacity and CAKE overhead. Daemon MUST be paused. Uses `systemctl stop wanctl@spectrum` or SIGUSR1 to enter a "benchmark mode" that freezes rate at ceiling.
  2. **Effectiveness test** (daemon running): Measures bufferbloat under load WITH the controller active. This is the useful test -- it shows the grade (A/B/C) of the active system.
- For capacity tests: add a `--pause-daemon` flag that sends SIGUSR1 to freeze rates at ceiling, runs the benchmark, then sends SIGUSR1 again to resume. Alternatively, require manual daemon stop.
- For effectiveness tests: do NOT touch the daemon. Let it react naturally. The latency-under-load measurement IS the result. Grade based on P95 RTT, not throughput.
- The CLI must clearly communicate which mode is running and what it means:
  - "Running bufferbloat grade test (daemon active, measuring latency control)..."
  - "Running capacity test (daemon paused at ceiling, measuring raw throughput)..."
- Never benchmark with the daemon running and then report the throughput as if it were uncontrolled

**Warning signs:**
- Benchmark tool does not check whether wanctl daemon is running before starting
- Benchmark tool reports throughput numbers without noting whether the daemon was active
- Test results show throughput far below ceiling_mbps without explanation
- No mechanism to pause or communicate with the running daemon during benchmarks

**Phase to address:**
Benchmarking phase. The daemon coordination strategy must be designed before any benchmark code is written.

---

### Pitfall 3: Auto-Fix Applies Wrong Overhead for ATT VDSL2 Link

**What goes wrong:**
The `--fix` command applies `cake-overhead-scheme=pppoe-ptm` (overhead 30) to the ATT link when the correct setting might be `bridged-ptm` (overhead 22), or vice versa. With the wrong overhead, CAKE miscalculates actual packet sizes on the wire, leading to either:
- **Too high overhead (30 when should be 22):** CAKE shapes more aggressively than needed, wasting 3-5% of available bandwidth
- **Too low overhead (22 when should be 30):** CAKE allows slightly more traffic than the link can handle, causing residual bufferbloat that defeats the purpose

The ATT connection uses a BGW320 gateway in IP passthrough mode. Whether this is bridged Ethernet or PPPoE depends on the AT&T provisioning and BGW320 configuration. The developer assumes one and hardcodes it.

**Why it happens:**
The difference between `pppoe-ptm` (overhead 30) and `bridged-ptm` (overhead 22) is the PPPoE encapsulation: 2B PPP + 6B PPPoE header = 8 bytes difference. In IP passthrough mode, the BGW320 terminates PPPoE and bridges Ethernet to the MikroTik, meaning `bridged-ptm` is likely correct. But if the BGW320 passes PPPoE through (some configurations), then `pppoe-ptm` is correct. There is no way to determine this from the wanctl side without examining the actual packet headers.

Additionally, PTM uses 64b/65b encoding which means the effective bandwidth should be derated by 64/65 (factor 0.984615). This encoding overhead is separate from the per-packet overhead and must be handled in the rate calculation, not the overhead parameter.

**How to avoid:**
- NEVER auto-detect overhead scheme. Make it a required config parameter: `cake_overhead_scheme: bridged-ptm` in the YAML
- Provide a lookup table in the detection output that shows what each scheme means:
  ```
  Current: cake-overhead-scheme=none (0 bytes overhead)
  Recommended for DOCSIS cable: docsis (18 bytes, mpu=64)
  Recommended for VDSL2 bridged: bridged-ptm (22 bytes)
  Recommended for VDSL2 PPPoE: pppoe-ptm (30 bytes)
  ```
- The `--fix` command should read the target overhead from config, not auto-detect it
- Document how to determine the correct scheme: "If your gateway does IP passthrough (bridges Ethernet), use `bridged-ptm`. If PPPoE is passed through to your router, use `pppoe-ptm`."
- For ATT specifically: the BGW320 in IP passthrough terminates PPPoE, so `bridged-ptm` (overhead 22) is the baseline recommendation. But warn the operator to verify.
- The `cake-rtt` issue (ATT currently at 50ms, should be 30ms for regional) is simpler: `regional` preset = 30ms, which is correct for intra-country traffic

**Warning signs:**
- Code auto-detects link type from WAN name or config (e.g., `if "att" in wan_name: scheme = "pppoe-ptm"`)
- No config field for overhead scheme -- hardcoded in the fix logic
- Overhead scheme is applied without operator confirmation
- No documentation about how to choose between `pppoe-ptm` and `bridged-ptm`

**Phase to address:**
Detection phase. The config schema for CAKE parameters (overhead scheme, RTT target, flowmode) must be defined before fix logic. The fix phase reads from config, never guesses.

---

### Pitfall 4: Auto-Fix Disrupts Live Traffic by Changing Queue Type Mid-Session

**What goes wrong:**
The `--fix` command PATCHes the CAKE queue type while the autorate daemon is actively setting `max-limit` on queue tree entries that reference that type. RouterOS may briefly reset queue state during the type modification, causing:
- Momentary queue flush (all buffered packets dropped)
- Counter reset that breaks `CakeStatsReader` delta calculation (steering daemon sees a huge negative delta or zero, interprets as "no congestion" and makes wrong steering decisions)
- Brief period of uncontrolled traffic while the queue re-initializes with new parameters
- If the daemon writes `max-limit` in the same instant the type is being modified, the behavior is undefined

**Why it happens:**
RouterOS queue types are referenced by name from queue tree entries. Modifying a queue type affects all queue tree entries using it. The wanctl daemon writes to queue tree entries every cycle (50ms) when rates change. There is no coordination mechanism between the CLI fix tool and the running daemon.

**How to avoid:**
- The `--fix` command MUST coordinate with the running daemon:
  1. **Preferred:** Require the daemon to be stopped. Check for the lock file (`/run/wanctl/spectrum.lock`). If locked, refuse to proceed: "Error: wanctl daemon is running. Stop the daemon first: systemctl stop wanctl@spectrum"
  2. **Alternative:** If running, warn and require `--force` flag. Even with `--force`, the fix should: (a) Set max-limit to ceiling first (reduce controller activity), (b) Wait 1s for the daemon cycle to complete, (c) Apply the queue type change, (d) Log the change so the daemon can detect and handle it
- After applying queue type changes, the daemon's `CakeStatsReader.previous_stats` cache is stale. The daemon needs to reset its counters on next read. Consider writing a sentinel to the state file that the daemon checks.
- Document the procedure: "1. Stop the daemon. 2. Apply fix. 3. Run benchmark to verify. 4. Start daemon."
- The `--dry-run` flag MUST be the default. `--fix` without `--dry-run` applies changes. `--fix --dry-run` shows what would change without applying.

**Warning signs:**
- Fix code does not check for running daemon (no lock file check)
- Fix code applies changes without any coordination with the daemon
- No `--dry-run` mode for the fix
- Tests for fix do not simulate a concurrent daemon writing to the same queues

**Phase to address:**
Fix phase. The daemon coordination protocol (stop daemon vs. signal vs. lock check) must be decided before any fix code writes to the router.

---

### Pitfall 5: Benchmark Results Are Not Comparable (No Baseline/After Normalization)

**What goes wrong:**
The operator runs a benchmark, applies CAKE fixes, runs another benchmark, and tries to compare. But the two benchmarks ran at different times of day (ISP congestion varies), used different durations (30s vs 120s), targeted different servers (flent default vs wanctl test host), or the network conditions simply changed. The "improvement" or "regression" is noise, not signal. The operator makes CAKE changes based on meaningless data.

**Why it happens:**
Benchmarks are inherently noisy. Cable (DOCSIS) connections share spectrum with neighbors -- peak hours can add 20-30ms of baseline RTT. ATT VDSL2 performance varies with line noise and DSLAM load. A single RRUL run is a sample of 1. Without multiple runs and statistical analysis, any single comparison is unreliable.

The existing `calibrate.py` makes this mistake: it measures once and declares the result "optimal." The existing integration test framework has `rrul_standard.yaml` with SLA thresholds, but these thresholds were already adjusted once because the original strict SLAs were not achievable on DOCSIS (comment in the file: "Original strict SLAs (p95=50, p99=100) were not achievable on DOCSIS").

**How to avoid:**
- Store benchmark results in SQLite (following the existing `MetricsWriter` pattern) with timestamp, duration, WAN name, daemon status, and results
- Each benchmark run records: baseline RTT (pre-test), loaded RTT (P50/P95/P99), throughput (DL/UL), CAKE parameters at time of test, server used, duration, WAN name
- The grade (A/B/C/D/F) uses the Waveform/DSLReports scale: A = <5ms bloat, B = <30ms, C = <60ms, D = <200ms, F = >200ms
- Comparison mode: `wanctl-benchmark --compare` shows the last N runs with the same WAN and test parameters, highlighting trends
- Require minimum 3 runs for any before/after comparison: `wanctl-benchmark --runs 3`
- Warn if test conditions differ: "Warning: previous test used server X, current test uses server Y. Results may not be comparable."
- Pin the test server in config so all runs use the same target

**Warning signs:**
- Benchmark tool has no result storage (prints to stdout only)
- No mechanism to compare multiple runs
- Single-run results are presented as definitive
- Grade is assigned from a single sample without confidence interval
- No metadata stored (time of day, server, duration, WAN name)

**Phase to address:**
Benchmarking phase. Result storage and grading must be implemented before the comparison feature.

---

### Pitfall 6: Flent/Netperf Not Available in LXC Containers

**What goes wrong:**
The benchmark tool assumes `flent` and `netperf` are installed in the LXC containers where wanctl runs (`cake-spectrum`, `cake-att`). But these containers are minimal: they have Python, wanctl, and minimal system packages. Neither `flent` nor `netperf` is installed, and the containers may not have the package manager or permissions to install them. The benchmark tool exits with "flent is not installed" and the operator has to figure out how to install packages in the containers.

Alternatively, the operator runs the benchmark from the host machine (not the container), but then traffic may not traverse the CAKE queues on the MikroTik if it exits via a different path. The benchmark traffic must originate from the same container that has its traffic shaped by CAKE.

**Why it happens:**
The existing `FlentGenerator` and `NetperfGenerator` in `load_generator.py` use `shutil.which()` to check for the tools. They have no installation guidance. The containers run Ubuntu 22.04 minimal and use `pip3 install --break-system-packages` for Python packages -- there is no virtual environment.

**How to avoid:**
- The benchmark tool MUST check tool availability at startup and provide clear installation instructions:
  ```
  Error: netperf not installed.
  Install: sudo apt-get update && sudo apt-get install -y netperf
  Or run from the host with: lxc exec cake-spectrum -- wanctl-benchmark ...
  ```
- Consider a `--check-deps` flag that validates all dependencies without running the benchmark
- The Dockerfile should optionally include flent/netperf for development/testing containers
- Document which machine to run benchmarks from: the container, not the host, to ensure traffic traverses CAKE
- For the production containers, provide a one-time setup script: `scripts/install-benchmark-deps.sh`
- Netperf requires a server on the other end. The default `netperf.bufferbloat.net` may not always be available. Document alternatives (Linode, DigitalOcean, self-hosted)
- The flent tool requires `netperf` as a backend, plus `matplotlib` for graphing (optional). Document the full dependency chain.

**Warning signs:**
- Benchmark code does not check for netperf/flent at startup
- No installation instructions in error messages
- Tests mock `shutil.which` but never test the "not installed" path
- No documentation about where (which machine/container) to run benchmarks

**Phase to address:**
Benchmarking phase. Dependency checking and installation documentation must be part of the first benchmark implementation.

---

### Pitfall 7: Benchmark Netperf Server is Unreachable or Rate-Limited

**What goes wrong:**
The benchmark uses `netperf.bufferbloat.net` (the community server) or `104.200.21.31` (the Dallas server from existing test profiles). These servers may be:
- Down for maintenance
- Rate-limited (community servers often limit concurrent connections)
- Far away (high baseline RTT makes bloat measurement less sensitive)
- Under load from other users (affecting throughput measurements)
- Blocking connections from the operator's ISP

The benchmark fails or produces unreliable results, and the operator blames CAKE settings instead of the test infrastructure.

**Why it happens:**
The existing `calibrate.py` defaults to `netperf.bufferbloat.net` and the RRUL profiles use `104.200.21.31`. These are third-party servers with no SLA. The existing `LoadProfile.from_yaml()` supports `WANCTL_TEST_HOST` env var override, but this is undocumented and easy to miss.

**How to avoid:**
- Support multiple netperf servers with fallback: try server A, if unreachable try server B
- Add a `--server` flag to the benchmark CLI: `wanctl-benchmark --server netperf.example.com`
- Pre-flight check: verify netperf server connectivity before starting the full benchmark (short 2s TCP_STREAM test)
- Document how to run a local netperf server for reliable testing: `docker run -d --name netperf-server ...` or `apt install netperf && netserver`
- For RRUL tests, the server needs both netperf and ICMP response. Test ICMP separately.
- Store server latency in benchmark results so high-baseline results can be flagged: "Warning: baseline RTT to server is 85ms. For accurate bufferbloat grading, use a server with <30ms baseline RTT."

**Warning signs:**
- Benchmark has only one hardcoded server with no fallback
- No pre-flight connectivity check before starting a multi-minute test
- Failure message is generic ("netperf failed") without diagnosing whether it is server, network, or local issue
- No documentation about self-hosting a netperf server

**Phase to address:**
Benchmarking phase. Server selection and pre-flight checks are part of the benchmark infrastructure.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding "optimal" CAKE parameters instead of reading from config | Quick fix implementation | Breaks portable controller architecture. Different deployments need different overhead schemes. | Never -- config is authoritative per established architecture |
| Auto-detecting link type from WAN name (`"att"` -> VDSL2, `"spectrum"` -> DOCSIS) | No new config fields needed | Wrong on any non-standard deployment. Cable on ATT Fiber, DSL on Spectrum, etc. | Never -- link type must be explicit in config |
| Reusing existing REST client for --fix writes | No new client code | Probe/audit functions sharing a client with write-capable methods violates the read-only audit principle from v1.16 | Only if the fix path uses a clearly separate code path with explicit "I am writing" semantics |
| Single netperf run for grading | Fast results | Noisy, unreliable grades that erode operator trust | Only for quick smoke tests, never for official grades |
| Storing benchmark results in flat files (JSON/text) | Simple implementation | No querying, no comparison, no trend analysis. Already have SQLite infrastructure. | Never -- use existing MetricsWriter pattern |
| Skipping PTM 64/65 encoding factor in rate calculations | Simpler math | 1.5% bandwidth waste on every VDSL2 packet (30 Mbps link loses 450 kbps) | Acceptable for cable/DOCSIS (no ATM/PTM encoding), never for DSL |

## Integration Gotchas

Common mistakes when connecting the new features to existing wanctl infrastructure.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| RouterOS queue type API | Assuming `/rest/queue/type` has the same response format as `/rest/queue/tree` | They are different resources with different fields. Queue type returns `kind`, `cake-rtt`, `cake-flowmode`, etc. Queue tree returns `name`, `max-limit`, `queue` (type reference). Test with real API responses. |
| `CakeStatsReader` counters after fix | Applying queue type change causes counter reset on router, `_calculate_stats_delta` computes negative deltas | After any queue type modification, reset `previous_stats` cache in CakeStatsReader. Or require daemon restart after fix. |
| Benchmark + alerting engine | RRUL test triggers sustained congestion alerts (v1.15) and steering transitions (v1.11). Discord gets flooded with alerts during a deliberate benchmark. | Add a `benchmark_active` flag or temporarily increase alert cooldowns. Or just document: "Expect alerts during benchmark. This is normal." |
| `set_limits()` in autorate daemon | The daemon's `set_limits()` writes both `queue=cake-down-{wan}` and `max-limit={bps}` in a single command. If the fix changed the queue type name, the daemon's hardcoded `cake-down-{wan}` reference breaks. | Fix code MUST NOT rename queue types. Only modify parameters of existing types. If renaming is needed, update config YAML too. |
| Portable controller architecture | Adding ISP-specific logic (DOCSIS vs PTM detection) to the controller code | All ISP-specific values go in YAML config. Controller code reads config, never infers link type. This is the NON-NEGOTIABLE portable architecture principle. |
| Health endpoint | Adding benchmark results to the health endpoint without versioning | Use a new top-level key (`"benchmark"`) similar to how `"wan_awareness"` was added in v1.11. Include last run time, grade, and result summary. |
| check_cake.py extension | Adding fix logic inside existing check functions (check_queue_tree, check_connectivity) | Fix logic belongs in a separate module (`fix_cake.py` or similar). check_cake.py stays read-only. Fix module imports and uses check functions for detection, then has its own write functions. |
| SIGUSR1 reload | Not considering whether CAKE config parameters should be hot-reloadable | CAKE overhead/RTT are router-side settings, not daemon config. They do NOT need SIGUSR1 reload -- they are applied via CLI tool, not daemon restart. |

## Performance Traps

Patterns that work in development but fail in production's 50ms cycle budget.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Querying `/rest/queue/type` every cycle to verify CAKE params | Cycle time jumps from 30ms to 100ms+ | CAKE params are static -- query once at startup or on demand via CLI. Never in the hot loop. | Immediately in production |
| Running flent from inside the daemon process | Main event loop blocks for 60-120s during benchmark | Benchmark is ALWAYS a separate process. Never import FlentGenerator into daemon code. | Immediately -- daemon misses thousands of cycles |
| Parsing flent JSON output synchronously | Blocks if flent output is large (>10MB for long tests with many streams) | Stream-parse or limit output size. Or just extract summary stats, not raw data. | With long tests (>5 min) |
| Benchmark storing raw per-packet latency data in SQLite | Thousands of rows per second for a 120s test = 240K rows | Store only summary stats (P50, P95, P99, avg, min, max) per benchmark run | After first benchmark fills SQLite with 200K+ rows |
| Pre-flight netperf check with 15s timeout | Benchmark appears hung for 15s if server is unreachable | Use 3s timeout for pre-flight. Full timeout only for the actual test. | When netperf server is down |

## Security Mistakes

Domain-specific security issues for router modification and benchmarking.

| Mistake | Risk | Prevention |
|---------|------|------------|
| `--fix` applies changes without confirmation | Operator runs `wanctl-check-cake --fix` expecting dry-run, gets live router modification | Default to dry-run. Require explicit `--apply` or `--yes` flag for actual changes. Show diff before applying. |
| Benchmark traffic bypasses firewall rules | RRUL test opens 8 TCP streams to external server, may trigger IDS/IPS or rate limiting | Document firewall implications. Benchmark uses standard ports (12865 for netperf). |
| Fix code exposes queue type parameters in logs | CAKE parameters themselves are not sensitive, but logging patterns could include router credentials | Use existing password-scrubbing pattern from v1.12. Fix log should show parameter names and values, never credentials. |
| `--fix` runs as root unnecessarily | CLI tool inherits daemon permissions but only needs queue type PATCH access | Document minimum RouterOS permissions: write access to `/queue/type` only. Read access to `/queue/tree` and `/queue/type`. |

## UX Pitfalls

Common user experience mistakes in optimization and benchmarking tools.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Benchmark outputs raw numbers without interpretation | Operator sees "P95: 47.3ms" but does not know if that is good or bad | Always include a grade: "P95: 47.3ms (Grade B - Good)" with color coding |
| Fix reports "Applied 3 changes" without showing what changed | Operator cannot verify correctness or rollback | Show before/after: "cake-rtt: 50ms -> 30ms, cake-overhead-scheme: none -> docsis" |
| Detection lists all CAKE parameters as sub-optimal even when some do not matter | Alert fatigue -- operator ignores warnings including the important one (wrong overhead) | Prioritize: ERROR for overhead/RTT (affect shaping quality), INFO for flowmode/diffserv (defaults are usually fine) |
| Benchmark requires netperf server setup with no guidance | Operator gives up before running first test | Include a `--self-test` mode that tests only with ping (no netperf needed) for quick grade estimate |
| Before/after comparison shows raw numbers, not delta | Operator has to mentally calculate improvement | Show improvement: "Bloat P95: 47ms -> 12ms (74% improvement, grade B -> A)" |
| Benchmark runs for 120s with no progress indication | Operator thinks tool is hung | Show progress bar or periodic status: "[30s/120s] DL: 340 Mbps, RTT: 12ms" |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Queue type query:** Detection queries `/rest/queue/type` (not just `/rest/queue/tree`) to read actual CAKE parameters (cake-rtt, cake-overhead-scheme, cake-flowmode)
- [ ] **Fix target:** Fix code PATCHes `/rest/queue/type/{id}`, NOT `/rest/queue/tree/{id}` for CAKE parameters
- [ ] **Daemon coordination:** Fix code checks for running daemon (lock file or systemctl check) and refuses to modify queue types while daemon is active, or requires `--force`
- [ ] **Overhead config:** CAKE overhead scheme is a config parameter in YAML, not auto-detected or hardcoded
- [ ] **ATT overhead:** ATT link uses `bridged-ptm` (overhead 22) for IP passthrough, `pppoe-ptm` (overhead 30) for PPPoE -- config must specify which
- [ ] **Spectrum overhead:** Spectrum/DOCSIS link uses `docsis` (overhead 18, mpu 64) -- config must specify
- [ ] **RTT presets:** Detection maps CAKE RTT presets to ms values: `internet`=100ms, `regional`=30ms, `metro`=10ms, etc.
- [ ] **Benchmark mode clarity:** Benchmark CLI clearly indicates whether daemon is running or paused during the test
- [ ] **Benchmark storage:** Results stored in SQLite with timestamp, WAN name, server, grade, P50/P95/P99 RTT, throughput
- [ ] **Multi-run support:** Grade requires minimum 3 runs; single-run shows "preliminary" grade with warning
- [ ] **Netperf pre-flight:** Benchmark checks netperf server connectivity (3s timeout) before starting the full test
- [ ] **Container dependencies:** Benchmark checks for netperf/flent availability with clear install instructions
- [ ] **Dry-run default:** `--fix` shows proposed changes without applying. `--fix --apply` makes actual changes.
- [ ] **Counter reset handling:** After queue type modification, CakeStatsReader delta calculation is invalidated -- documented and handled
- [ ] **Alert suppression:** Benchmark mode or documentation addresses the fact that RRUL tests will trigger congestion/steering alerts

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| P1: Wrong API endpoint (tree vs type) | MEDIUM | Verify no changes were applied (queue tree PATCH ignores unknown fields). Implement correct `/queue/type` endpoint. Re-test. |
| P2: Benchmark triggers controller | LOW | Stop daemon, re-run benchmark, restart daemon. Document the procedure. |
| P3: Wrong overhead scheme applied | HIGH | SSH to router, inspect current queue type settings (`/queue/type/print`). Correct the overhead scheme. Re-run benchmark to verify. Wrong overhead may have been active for hours affecting all traffic. |
| P4: Fix disrupts live traffic | HIGH | Restart daemon (`systemctl restart wanctl@spectrum`). The daemon will re-read config and re-apply rates on next cycle. Check steering daemon state too -- `CakeStatsReader` needs counter reset. Monitor for 5 minutes for stability. |
| P5: Incomparable benchmarks | LOW | Re-run benchmarks under controlled conditions (same time, same server, same duration, 3+ runs). Discard old results. |
| P6: Tools not installed in container | LOW | Install netperf: `lxc exec cake-spectrum -- apt-get install -y netperf`. Document for future reference. |
| P7: Netperf server unreachable | LOW | Try alternate server. Or set up local netperf server: `docker run -d -p 12865:12865 ...`. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| P1: Wrong API endpoint | Detection phase (extending check_cake) | Test that detection code queries `/rest/queue/type` and reads CAKE parameters from the response |
| P2: Benchmark triggers controller | Benchmarking phase | Benchmark CLI checks daemon status, documents interaction, supports both modes |
| P3: Wrong overhead for ATT | Detection phase + Config schema | Config YAML has explicit `cake_overhead_scheme` field; no auto-detection in code |
| P4: Fix disrupts live traffic | Fix phase | Fix code checks lock file, requires `--apply` flag, shows diff before applying |
| P5: Non-comparable results | Benchmarking phase | Results stored in SQLite with metadata; comparison mode shows deltas |
| P6: Missing dependencies | Benchmarking phase | `--check-deps` flag; clear error messages with install instructions |
| P7: Server unreachable | Benchmarking phase | Pre-flight connectivity check with 3s timeout; `--server` flag for override |
| All | Every phase | Test coverage >=90% maintained; error paths tested; real RouterOS responses in fixtures |

## Sources

- Codebase: `src/wanctl/check_cake.py` -- existing read-only audit implementation, uses `/queue/tree` only (HIGH confidence)
- Codebase: `src/wanctl/routeros_rest.py` -- REST client with queue tree PATCH, no queue type support (HIGH confidence)
- Codebase: `src/wanctl/autorate_continuous.py` -- `set_limits()` writes `queue=cake-down-{wan} max-limit={bps}` to queue tree (HIGH confidence)
- Codebase: `src/wanctl/steering/cake_stats.py` -- `CakeStatsReader` delta calculation vulnerable to counter resets (HIGH confidence)
- Codebase: `src/wanctl/calibrate.py` -- binary search sets CAKE limits via SSH, no daemon coordination (HIGH confidence)
- Codebase: `tests/integration/framework/load_generator.py` -- FlentGenerator/NetperfGenerator with subprocess (HIGH confidence)
- Codebase: `tests/integration/profiles/rrul_standard.yaml` -- existing SLA thresholds, adjusted for DOCSIS (HIGH confidence)
- [MikroTik CAKE documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) -- CAKE parameters: cake-rtt presets (internet=100ms, regional=30ms), cake-overhead-scheme (docsis, pppoe-ptm, bridged-ptm), cake-flowmode, cake-diffserv (HIGH confidence)
- [MikroTik Queue Types documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345871/Queue+types) -- queue type vs queue tree separation, CAKE kind properties (HIGH confidence)
- [MikroTik REST API documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) -- PATCH for updates, GET for reads, path structure (HIGH confidence)
- [tc-cake(8) man page](https://man.archlinux.org/man/tc-cake.8.en) -- CAKE overhead keywords: docsis (overhead 18, mpu 64, noatm), pppoe-ptm (overhead 30, ptm), bridged-ptm (overhead 22, ptm) (HIGH confidence)
- [VDSL2 overheads and CAKE](https://allysmith.uk/vdsl2-overheads) -- PTM 64/65 encoding, PPPoE vs bridged overhead calculation (MEDIUM confidence)
- [Flent RRUL test suite](https://www.bufferbloat.net/projects/codel/wiki/RRUL_test_suite/) -- 8 TCP streams, concurrent latency measurement, designed to saturate links (HIGH confidence)
- [Waveform bufferbloat test grading](https://www.waveform.com/tools/bufferbloat) -- A/B/C/D/F grading scale based on latency under load (MEDIUM confidence)
- [cake-autorate project](https://github.com/lynxthecat/cake-autorate) -- reference implementation for CAKE auto-tuning on OpenWrt (MEDIUM confidence)

---
*Pitfalls research for: CAKE parameter optimization and bufferbloat benchmarking in production dual-WAN controller*
*Researched: 2026-03-13*
