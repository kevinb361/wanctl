# Stack Research: v1.17 CAKE Optimization & Benchmarking

**Project:** wanctl v1.17
**Researched:** 2026-03-13
**Confidence:** HIGH

## Executive Summary

This milestone has two distinct capabilities:

1. **CAKE auto-fix** -- Extend existing `wanctl-check-cake` with `--fix` flag to apply optimal CAKE queue type parameters via the RouterOS REST API. Zero new dependencies. The existing `RouterOSREST` class already supports PATCH operations on queue tree; extending to `/rest/queue/type/{id}` is mechanical.

2. **Bufferbloat benchmarking CLI** -- Wrap flent/netperf into a new `wanctl-benchmark` CLI tool that runs RRUL tests, grades results (A/B/C/D/F), and stores results in SQLite for before/after comparison. The integration test framework (`tests/integration/framework/`) already has `FlentGenerator`, `NetperfGenerator`, `LoadProfile`, `SLAChecker` -- the new tool promotes this framework code to a user-facing CLI. Zero new Python package dependencies (flent and netperf are system binaries invoked via subprocess).

**Bottom line: Zero new Python package dependencies for either feature.** Both build on existing infrastructure.

---

## Recommended Stack

### Core Technologies (Already Present -- No Changes)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Python | 3.12 | Runtime | Existing |
| requests | >=2.31.0 | RouterOS REST API calls (PATCH to `/rest/queue/type/{id}`) | Existing dep |
| PyYAML | >=6.0.1 | Config file parsing, benchmark profile loading | Existing dep |
| SQLite (stdlib) | 3.12 built-in | Benchmark result storage for before/after comparison | Existing pattern (metrics_storage.py) |
| subprocess (stdlib) | 3.12 built-in | Invoke flent/netperf binaries | Existing pattern (load_generator.py) |

### System-Level Tools (External Binaries, NOT Python Packages)

| Tool | Version | Purpose | Installation | Confidence |
|------|---------|---------|-------------|------------|
| flent | >=2.2.0 | RRUL test orchestration (wraps netperf + ping concurrently) | `apt install flent` or `pip install flent` (system, not venv) | HIGH |
| netperf | >=2.6 | TCP/UDP throughput generation for RRUL tests | `apt install netperf` (already in Dockerfile) | HIGH |
| ping/fping | system | ICMP RTT measurement during RRUL | `iputils-ping` (already in Dockerfile) | HIGH |

**Critical distinction:** flent and netperf are CLI tools invoked via `subprocess.Popen`, not imported as Python libraries. They must be installed on the system running benchmarks (development machine or container), NOT in the project's venv. The project already has `netperf` in the Dockerfile and the integration test framework already wraps both tools.

### Existing Code to Reuse (Not New Dependencies)

| Component | Location | What It Provides for v1.17 |
|-----------|----------|---------------------------|
| `RouterOSREST` | `routeros_rest.py` | `_request()` PATCH method, `_find_resource_id()` with caching, session management |
| `CheckResult` / `Severity` | `check_config.py` | Shared result model for audit output |
| `check_cake.py` | `check_cake.py` | All audit logic: queue tree, CAKE type, max-limit, mangle rules |
| `_create_audit_client()` | `check_cake.py` | SimpleNamespace router client creation pattern |
| `FlentGenerator` | `tests/integration/framework/load_generator.py` | Flent subprocess wrapper, output collection |
| `NetperfGenerator` | `tests/integration/framework/load_generator.py` | Netperf subprocess wrapper, fallback |
| `LoadProfile` | `tests/integration/framework/load_generator.py` | YAML-based test profile loading |
| `SLAChecker` / `SLAConfig` | `tests/integration/framework/sla_checker.py` | Pass/fail evaluation against thresholds |
| RRUL profiles | `tests/integration/profiles/*.yaml` | Pre-configured RRUL test definitions |
| `MetricsWriter` | `metrics_storage.py` | SQLite storage singleton pattern |

---

## New Code Needed (NOT New Libraries)

### Feature 1: CAKE Auto-Fix (`--fix` Flag)

**What changes:**

1. **`routeros_rest.py`** -- Add `get_queue_type()` and `set_queue_type_params()` methods:
   - `GET /rest/queue/type?name={type_name}` to read current CAKE queue type parameters
   - `PATCH /rest/queue/type/{id}` to modify CAKE parameters (cake-diffserv, cake-flowmode, cake-overhead, cake-rtt, etc.)
   - Follow existing `_find_resource_id()` pattern with `_queue_type_id_cache`

2. **`check_cake.py`** -- Extend with:
   - New `--fix` CLI flag
   - `check_cake_params()` function that detects sub-optimal settings (e.g., wrong overhead for DOCSIS/VDSL2, missing NAT flag, wrong flowmode)
   - `apply_fixes()` function that PATCHes only the parameters that differ from optimal
   - Dry-run output showing what would change before applying

3. **New YAML config section** -- Optional `cake_optimization:` block in autorate config:
   ```yaml
   cake_optimization:
     download:
       overhead: "docsis"     # or exact bytes, or "pppoe-ptm"
       flowmode: "triple-isolate"
       diffserv: "diffserv4"
       nat: true
       ack_filter: true
       rtt: "internet"       # or exact ms value
     upload:
       overhead: "docsis"
       flowmode: "triple-isolate"
       diffserv: "diffserv4"
       nat: true
       ack_filter: true
   ```

**RouterOS REST API for Queue Types:**

The queue type parameters are at `/rest/queue/type/{id}`, separate from queue tree entries at `/rest/queue/tree/{id}`. A queue tree entry references a queue type by name (the `queue` field). The CAKE-specific parameters (cake-bandwidth, cake-diffserv, cake-flowmode, cake-overhead, etc.) live on the queue type object, not the queue tree entry.

REST API pattern:
```
GET  /rest/queue/type?name=cake-down-spectrum  -->  [{".id": "*5", "name": "cake-down-spectrum", "kind": "cake", "cake-diffserv": "diffserv3", ...}]
PATCH /rest/queue/type/*5  body: {"cake-diffserv": "diffserv4", "cake-overhead": "docsis"}
```

All values are JSON strings (even numbers), per RouterOS REST API convention.

### Feature 2: Bufferbloat Benchmarking CLI (`wanctl-benchmark`)

**What changes:**

1. **New `benchmark.py`** -- CLI entry point:
   - `wanctl-benchmark run` -- Execute RRUL test with profile
   - `wanctl-benchmark grade` -- Grade a previous result file
   - `wanctl-benchmark compare` -- Compare two results (before/after)
   - `wanctl-benchmark history` -- Show stored results

2. **Promote integration framework code** -- Move relevant parts of `tests/integration/framework/` into `src/wanctl/`:
   - `load_generator.py` (FlentGenerator, NetperfGenerator, LoadProfile) -- or import from tests
   - SLA/grading logic adapted for CLI use

3. **Grading system** based on industry standard (Waveform/DSLReports):

   | Grade | Latency Increase Under Load | Meaning |
   |-------|----------------------------|---------|
   | A+ | < 5ms | Excellent -- virtually no bufferbloat |
   | A | < 15ms | Great -- minimal bufferbloat |
   | B | < 30ms | Good -- acceptable for gaming |
   | C | < 60ms | Fair -- noticeable lag under load |
   | D | < 200ms | Poor -- significant bufferbloat |
   | F | >= 200ms | Failing -- severe bufferbloat |

   Grade is computed from: `p90_latency_under_load - baseline_latency`

4. **SQLite storage** -- Follow existing `MetricsWriter` pattern:
   - `benchmark_results` table: timestamp, wan_name, profile, grade, p50/p90/p95/p99 latency, throughput, baseline_rtt, raw_data_path
   - `query_benchmarks()` for history and comparison

5. **Flent output parsing** -- Read `.flent.gz` files (gzipped JSON):
   ```python
   import gzip, json
   with gzip.open(path, "rt") as f:
       data = json.load(f)
   # data contains: x_values, results, metadata, raw_values
   ```

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `flent` as pip dependency | It's a system CLI tool, not a library to import. Installing in venv would pull matplotlib, PyQt5, and other heavy GUI deps. | Invoke via `subprocess.Popen` (existing pattern) |
| `iperf3` Python bindings | Adds complexity without benefit -- flent already wraps iperf3 if needed | Let flent handle tool selection |
| `matplotlib` / plotting libs | Report generation is text-based (CLI output, JSON). Plots are a user concern, not a daemon concern | Text-based grades and tabulate output |
| New HTTP client (httpx) | Only needed for dashboard (optional dep). REST API calls use `requests` session | `requests` (existing) |
| `dataclasses-json` / `pydantic` | Existing CheckResult/Severity model works. Project pattern is plain dataclasses + manual serialization | Existing patterns |
| `click` / `typer` | CLI framework. Project uses `argparse` everywhere. Stay consistent | `argparse` (existing pattern) |
| `rich` for CLI output | Project CLI tools use plain print + ANSI codes via format_results(). Stay consistent | Existing `format_results()` pattern |

---

## Installation Changes

### pyproject.toml

```toml
# NO changes to [project.dependencies] -- zero new runtime deps

# New CLI entry point only:
[project.scripts]
wanctl-benchmark = "wanctl.benchmark:main"
# ... existing scripts unchanged
```

### Dockerfile

```dockerfile
# Already has netperf. Add flent for benchmark capability:
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    iputils-ping \
    netperf \
    flent \          # NEW: for wanctl-benchmark RRUL tests
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean
```

**Note:** flent in apt may be older than PyPI version. For containers that need benchmarking, `pip install flent` (system pip, not venv) gets 2.2.0. But benchmarking will primarily run from the development machine, not from production containers -- production containers run the daemon, not benchmarks.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| subprocess flent | Import flent as Python module | flent's internal API is not stable or documented for programmatic use. subprocess is the correct integration pattern (flent's own docs say "wrapper around netperf") |
| RouterOS REST PATCH | RouterOS SSH commands | REST is 2x faster, already preferred transport, and PATCH is simpler than parsing SSH output. SSH fallback exists if REST fails. |
| SQLite for benchmark storage | JSON files | SQLite enables querying, comparison, history. Consistent with existing metrics_storage.py pattern. JSON files would need custom indexing. |
| Extend check_cake.py with --fix | New standalone tool | Reuses all existing audit logic, client creation, output formatting. --fix is a natural extension of audit (audit finds problems, --fix resolves them). |
| Text-based grading | HTML/PDF reports | CLI tool. Text output is grep-able, pipe-able, consistent with wanctl-history and wanctl-check-config patterns. |

---

## RouterOS REST API: Queue Type Parameters

These are the CAKE-specific parameters settable via `PATCH /rest/queue/type/{id}`:

| Parameter | Type | Values | Purpose |
|-----------|------|--------|---------|
| `cake-bandwidth` | string | e.g. "100M", "50k" | Bandwidth shaper limit |
| `cake-diffserv` | string | besteffort, precedence, diffserv3, diffserv4, diffserv8 | Traffic classification tins |
| `cake-flowmode` | string | flowblind, srchost, dsthost, hosts, flows, dual-srchost, dual-dsthost, triple-isolate | Flow isolation mode |
| `cake-nat` | string | "true"/"false" | NAT awareness for flow isolation |
| `cake-ack-filter` | string | "none", "filter", "aggressive" | TCP ACK optimization |
| `cake-overhead` | string | bytes (-64 to 256) or keyword | Per-packet overhead compensation |
| `cake-atm` | string | "none", "atm", "ptm" | ATM/PTM cell framing |
| `cake-mpu` | string | bytes | Minimum packet unit |
| `cake-rtt` | string | ms value or keyword | Target RTT for AQM |
| `cake-wash` | string | "true"/"false" | Clear external DSCP markings |
| `cake-memlimit` | string | bytes | Memory limit for queues |
| `cake-autorate-ingress` | string | "true"/"false" | Dynamic bandwidth adjustment |

**Overhead keywords** (shorthand for overhead + ATM/PTM + MPU):
- `raw` -- no overhead compensation
- `conservative` -- safe default (48 bytes overhead)
- `ethernet` -- standard Ethernet (14 byte overhead, 84 byte MPU)
- `ether-vlan` -- Ethernet with VLAN tag
- `pppoe-ptm` -- PPPoE over PTM (for VDSL2/ATT)
- `docsis` -- DOCSIS cable modem (for Spectrum)
- `bridged-ptm` -- bridged PTM
- `pppoa-vcmux` -- PPPoA over ATM

**Confidence:** HIGH -- verified against official MikroTik CAKE documentation.

---

## Optimal CAKE Settings Per Link Type

### Spectrum (DOCSIS Cable)

| Parameter | Optimal Value | Rationale |
|-----------|--------------|-----------|
| cake-overhead | Use `docsis` keyword | DOCSIS framing has specific per-packet overhead that differs from Ethernet |
| cake-flowmode | `triple-isolate` | Best flow isolation for residential multi-device use |
| cake-diffserv | `diffserv4` | 4-tin priority (voice, video, best-effort, bulk) -- matches typical home traffic |
| cake-nat | `true` | NAT is used (router does NAT before CAKE sees packets) |
| cake-ack-filter | `filter` | Reduces ACK overhead on asymmetric cable (high DL, low UL) |
| cake-rtt | `internet` (100ms) or measured value | Default is appropriate for cable |
| cake-wash | `true` | Clear external DSCP markings (ISP may not honor them) |

### ATT (VDSL2)

| Parameter | Optimal Value | Rationale |
|-----------|--------------|-----------|
| cake-overhead | Use `pppoe-ptm` keyword (if PPPoE) or `bridged-ptm` (if bridged) | VDSL2 uses PTM framing, PPPoE adds overhead |
| cake-flowmode | `triple-isolate` | Best flow isolation |
| cake-diffserv | `diffserv4` | 4-tin priority |
| cake-nat | `true` | NAT is used |
| cake-ack-filter | `filter` | Helpful on asymmetric DSL |
| cake-rtt | `internet` or measured baseline | Appropriate for DSL |
| cake-wash | `true` | Clear external DSCP markings |

**Confidence:** MEDIUM -- overhead keywords are well-documented, but the exact optimal combination depends on actual link characteristics. The `--fix` tool should show a diff before applying and allow `--dry-run` preview.

---

## Version Compatibility

| Component | Compatible With | Notes |
|-----------|-----------------|-------|
| RouterOS REST API for queue/type | RouterOS >= 7.1beta3 | CAKE queue types available since this version |
| flent 2.2.0 | Python 3.6+ | System install, not project dep |
| netperf 2.6+ | Ubuntu 22.04+ | Already in Dockerfile |
| requests (existing) | RouterOS REST API | PATCH method for queue/type is standard REST |

---

## Integration Points

### Auto-Fix Integration with Existing Code

```
check_cake.py (existing)
  |-- _create_audit_client()     --> creates RouterOSREST or RouterOSSSH
  |-- check_queue_tree()          --> verifies queue exists, type is CAKE
  |-- check_connectivity()        --> verifies router reachable
  |
  NEW:
  |-- check_cake_params()         --> reads queue type params, compares to optimal
  |-- apply_cake_fixes()          --> PATCHes queue type with optimal params
  |-- main() + --fix flag         --> orchestrates audit + optional fix

routeros_rest.py (existing)
  |-- _find_resource_id()         --> generic ID lookup with caching
  |-- _request("PATCH", ...)      --> HTTP PATCH with SSL handling
  |
  NEW:
  |-- get_queue_type()            --> GET /rest/queue/type?name={name}
  |-- set_queue_type_params()     --> PATCH /rest/queue/type/{id}
```

### Benchmark Integration with Existing Code

```
tests/integration/framework/ (existing, test code)
  |-- FlentGenerator              --> subprocess flent wrapper
  |-- NetperfGenerator            --> subprocess netperf wrapper
  |-- LoadProfile.from_yaml()     --> profile loading
  |-- SLAChecker                  --> pass/fail evaluation

NEW src/wanctl/benchmark.py:
  |-- Promoted/adapted framework code for CLI use
  |-- BenchmarkResult dataclass   --> grade + stats + metadata
  |-- BenchmarkStorage            --> SQLite persistence (follows MetricsWriter pattern)
  |-- grade_result()              --> A+/A/B/C/D/F grading
  |-- main()                      --> argparse CLI
```

---

## Sources

- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) -- CAKE parameters, overhead keywords, queue type options (HIGH confidence)
- [MikroTik Queue Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues) -- queue type vs queue tree distinction (HIGH confidence)
- [MikroTik REST API Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) -- PATCH method, URL structure, JSON body format (HIGH confidence)
- [Flent Official Site](https://flent.org/) -- test descriptions, CLI options, output formats (HIGH confidence)
- [Flent on PyPI](https://pypi.org/project/flent/) -- version 2.2.0, Python 3 only (HIGH confidence)
- [Flent man page](https://manpages.debian.org/testing/flent/flent.1.en.html) -- CLI options -f, -o, -l, -H (HIGH confidence)
- [Bufferbloat.net RRUL Spec](https://www.bufferbloat.net/projects/bloat/wiki/RRUL_Spec/) -- RRUL test methodology (HIGH confidence)
- [Waveform Bufferbloat Test](https://www.waveform.com/tools/bufferbloat) -- grading criteria (A < 5ms, B < 30ms, etc.) (MEDIUM confidence -- proprietary thresholds)
- Existing wanctl integration test framework (`tests/integration/framework/`) -- already-implemented flent/netperf wrappers (HIGH confidence, verified in codebase)
- Existing `routeros_rest.py` -- PATCH operations, resource ID caching (HIGH confidence, verified in codebase)

---
*Stack research for: wanctl v1.17 CAKE Optimization & Benchmarking*
*Researched: 2026-03-13*
