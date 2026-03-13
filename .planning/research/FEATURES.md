# Feature Landscape: v1.17 CAKE Optimization & Benchmarking

**Domain:** CAKE qdisc parameter optimization and bufferbloat benchmarking for dual-WAN controller
**Researched:** 2026-03-13
**Confidence:** HIGH

## Table Stakes

Features users expect from a CAKE optimization and benchmarking tool. Missing = tool feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Detect sub-optimal CAKE queue type parameters | Core purpose -- extend existing audit tool. Must flag: wrong overhead for link type, missing cake-nat behind NAT, wrong flowmode, sub-optimal diffserv | Medium | Requires GET `/rest/queue/type` (new), compare to optimal per link type |
| Show diff before applying fixes | Safety -- never modify router without confirmation | Low | Text diff of current vs proposed values |
| `--fix` applies optimal parameters via REST API | Core purpose -- auto-remediation | Medium | PATCH `/rest/queue/type/{id}` with changed params only |
| `--dry-run` mode for --fix | Safety critical -- production router | Low | Show what would change without applying |
| Run RRUL bufferbloat test | Core purpose -- measure latency under load | Medium | Wrap flent subprocess, existing FlentGenerator code |
| Grade bufferbloat results (A-F) | Makes results actionable for non-experts | Low | Industry-standard thresholds (Waveform/DSLReports) |
| Store benchmark results for comparison | Essential for before/after CAKE optimization | Medium | SQLite, follows MetricsWriter pattern |
| Before/after comparison output | Proves optimization worked | Low | Query two results, show delta |
| Netperf server connectivity check | Fail fast before spending 30-60s | Low | TCP connect to port 12865 with 5s timeout |

## Differentiators

Features that set this apart. Not expected, but high value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Link-type-aware optimization profiles | Knows correct CAKE params for DOCSIS vs VDSL2 vs fiber. Cable: `docsis` overhead, DSL: `pppoe-ptm` overhead | Low | YAML config section, lookup table |
| Per-queue-direction parameters | Download and upload may need different overhead/ACK filter settings | Low | Separate DL/UL entries in cake_optimization config |
| Parameter snapshot before fix | Save current state to JSON for rollback | Low | GET before PATCH, serialize to timestamped file |
| Benchmark history timeline | Track bufferbloat grade over time | Medium | SQLite history query, tabulate output |
| Combined audit+benchmark workflow | "Check CAKE, fix, then verify with benchmark" in one session | Low | CLI subcommands, sequential execution |
| WAN-specific benchmark profiles | Different SLAs for Spectrum vs ATT | Low | Already have per-WAN RRUL profiles |
| JSON output for all operations | CI/scripting integration | Low | Existing format_results_json pattern |
| Separate DL/UL bufferbloat grades | Some links have good DL but bad UL control | Low | Parse flent for separate DL/UL latency deltas |
| Quick benchmark mode (--quick) | Fast iteration during tuning (10s instead of 60s) | Low | Short -l flag to flent, flagged as "quick" in storage |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Graphical plots / charts | Adds matplotlib dependency, not useful in CLI/SSH context | Text-based grades and tabulate tables. Users who want plots can feed JSON to external tools or use flent's own plotting |
| Continuous benchmark daemon | Benchmarks saturate the link -- cannot run alongside production traffic shaping | On-demand CLI tool only. Pause wanctl daemon during benchmarks or accept imprecise results |
| Auto-schedule benchmarks | Risk of running during production hours, saturating link | Manual invocation only. Document recommended workflow |
| Modify queue tree (not queue type) | Queue tree max-limit is dynamically managed by wanctl daemon. Modifying it would conflict | Only modify queue TYPE parameters (CAKE settings). Queue tree max-limit is daemon territory |
| Create/delete queue types | Destructive. Assumes queue types already exist (created during initial router setup) | Only modify existing queue type parameters. Error if queue type not found |
| Import flent as Python library | Unstable internal API, pulls heavy GUI deps (matplotlib, PyQt5) | subprocess.Popen (existing pattern) |
| Built-in netperf server | Netperf server must run on a DIFFERENT machine to measure the link | Document setup. Provide one-liner: `ssh remote 'netserver -D'` |
| Browser-based speed tests | Not reproducible, don't measure latency under load (bufferbloat) | Use flent RRUL with controlled netperf server |
| Auto-tune bandwidth ceiling | Requires iterative testing over hours/days, false precision | Document "10% below ISP speed" heuristic |
| DSCP/diffserv auto-classification | Massive scope increase for marginal benefit in home network | Recommend `besteffort` for home use, document when diffserv3/4 is appropriate |
| iperf3 as alternative | flent RRUL requires netperf. iperf3 lacks multi-stream timestamped output | Use netperf exclusively (already installed) |

## Feature Dependencies

```
CAKE Parameter Detection and Auto-Fix
    |-- get_queue_type() in routeros_rest.py  (new REST method)
    |       requires: existing RouterOSREST._find_resource_id()
    |-- set_queue_type_params() in routeros_rest.py  (new REST method)
    |       requires: existing RouterOSREST._request("PATCH")
    |-- detect_suboptimal_params()
    |       requires: get_queue_type() result + optimal param lookup table
    |-- --fix / --dry-run CLI flags
    |       requires: detect_suboptimal_params (to know what to fix)
    |       requires: set_queue_type_params (to apply fix)
    |-- parameter_snapshot()
    |       requires: get_queue_type() (save before fix)
    |-- before_after_diff()
            requires: get_queue_type() before and after fix

Bufferbloat Benchmarking (independent of optimization)
    |-- Netperf server connectivity check
    |       requires: nothing (TCP connect)
    |-- flent RRUL subprocess wrapper
    |       requires: Netperf server check + flent/netperf system binaries
    |-- flent output parser (latency extraction from .flent.gz)
    |       requires: flent wrapper output
    |-- Bufferbloat grading (A+/A/B/C/D/F)
    |       requires: flent output parser
    |-- SQLite result storage
    |       requires: Grading + existing MetricsWriter pattern
    |-- Grade comparison / history
            requires: SQLite storage

Cross-feature operational link (not technical dependency):
    --fix (optimization) ──then──> benchmark (prove improvement)
```

## CAKE Parameter Optimization Rules

Sub-optimal settings the detection engine should flag.

| Parameter | Sub-Optimal | Optimal | Condition | Severity |
|-----------|-------------|---------|-----------|----------|
| `cake-nat` | `no` | `yes` | Router performs NAT (virtually all home routers) | WARN |
| `cake-ack-filter` | disabled | `filter` | Upload queue (TX direction -- reduces ACK overhead on asymmetric links) | WARN |
| `cake-ack-filter` | `filter` | disabled | Download queue (RX direction -- ACK filtering on download is counterproductive) | WARN |
| `cake-flowmode` | `flowblind` | `triple-isolate` | Any config (flowblind disables flow isolation entirely) | WARN |
| `cake-diffserv` | `diffserv3/4/8` | `besteffort` | No DSCP marking rules exist (wastes CPU classifying un-marked traffic) | INFO |
| `cake-rtt-scheme` | `internet` (100ms) | `regional` (30ms) | US domestic traffic | INFO |
| `cake-rtt-scheme` | `datacentre` | `regional`/`internet` | WAN link (datacentre is for 10GigE LANs) | WARN |
| `overhead` | unset/`raw` | link-type-specific | Cable link missing DOCSIS overhead compensation | WARN |
| `overhead` | `ethernet` | `docsis` | Cable (DOCSIS) link specifically | INFO |
| `overhead` | `ethernet` | `pppoe-ptm`/`bridged-ptm` | VDSL2 link specifically | INFO |

## Bufferbloat Grading Thresholds

Industry-standard (DSLReports/Waveform):

| Grade | Max Latency Increase | Interpretation |
|-------|---------------------|----------------|
| A+ | < 5 ms | Excellent -- no perceptible bufferbloat |
| A | < 15 ms | Great -- minimal bufferbloat |
| B | < 30 ms | Good -- acceptable for gaming |
| C | < 60 ms | Fair -- noticeable lag under load |
| D | < 200 ms | Poor -- significant bufferbloat |
| F | >= 200 ms | Failing -- unusable during load |

Grade = max(download_latency_increase, upload_latency_increase) mapped to thresholds.
Latency increase = p90_loaded_rtt - baseline_idle_rtt.

## MVP Recommendation

### Phase 1: CAKE Parameter Detection and Auto-Fix

Prioritize:
1. REST API methods for queue type (get_queue_type, set_queue_type_params)
2. Sub-optimal parameter detection with diff output
3. `--fix` flag with `--dry-run` preview
4. Parameter snapshot before applying changes
5. JSON output mode

### Phase 2: Bufferbloat Benchmarking CLI

Prioritize:
1. `wanctl-benchmark run` (promote FlentGenerator to CLI)
2. Flent output parsing and grading
3. SQLite result storage
4. `wanctl-benchmark compare` (before/after)

### Phase 3: Integration and Polish

Prioritize:
1. Combined workflow documentation
2. Benchmark history query
3. Per-WAN benchmark profiles
4. Quick benchmark mode

Defer: Health endpoint benchmark summary, auto pre/post benchmark around --fix

## Sources

- Existing `check_cake.py` -- current audit capabilities (verified in codebase)
- Existing `tests/integration/framework/` -- flent/netperf wrapper code (verified in codebase)
- Existing RRUL profiles (`tests/integration/profiles/*.yaml`) (verified in codebase)
- [Waveform Bufferbloat Test](https://www.waveform.com/tools/bufferbloat) -- grading standard
- [DSLReports Bufferbloat FAQ](https://www.dslreports.com/faq/17930) -- grade thresholds
- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) -- parameter reference
- [Bufferbloat.net RRUL Spec](https://www.bufferbloat.net/projects/bloat/wiki/RRUL_Spec/) -- test methodology
- CAKE optimization todo (`2026-03-12-audit-cake-qdisc-configuration-for-spectrum-and-att-links.md`)

---
*Feature research for: CAKE optimization and bufferbloat benchmarking*
*Researched: 2026-03-13*
