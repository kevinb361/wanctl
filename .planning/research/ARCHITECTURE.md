# Architecture Patterns

**Domain:** CAKE parameter optimization (auto-fix) + bufferbloat benchmarking for existing wanctl CLI tools
**Researched:** 2026-03-13
**Overall confidence:** HIGH (existing codebase patterns well-understood, RouterOS REST API verified, flent CLI interface confirmed)

## Recommended Architecture

### High-Level: Extend check_cake + add optimizer module + add benchmark tool

```
src/wanctl/
  check_cake.py          [MODIFY] -- add --fix/--yes flags, sub-optimal detection
  cake_optimizer.py      [NEW]    -- CAKE parameter analysis + REST API apply
  benchmark.py           [NEW]    -- flent/netperf RRUL wrapper, grading, storage
  routeros_rest.py       [MODIFY] -- add queue type read/write methods
  storage/schema.py      [MODIFY] -- add benchmarks table
  storage/reader.py      [MODIFY] -- add benchmark query function
  history.py             [MODIFY] -- add --benchmarks subcommand
  check_config.py        [READ-ONLY] -- imports CheckResult/Severity (no changes)
```

### Design Principle: Extend, Don't Restructure

check_cake.py already connects to the router, audits queue tree entries, and reports CheckResult items. The auto-fix feature extends this by:
1. Reading queue type parameters (not just queue tree entries)
2. Comparing against known-optimal CAKE settings
3. Optionally applying changes via REST API PATCH

The benchmarking tool is fully independent -- it wraps flent, grades results, and stores them in SQLite. Zero coupling to check_cake or the autorate daemon.

### Component Boundaries

| Component | Responsibility | Communicates With | New/Modified |
|-----------|---------------|-------------------|--------------|
| `check_cake.py` (CLI) | CLI entry, `--fix` flag routing, user confirmation | cake_optimizer, routeros_rest | MODIFY |
| `cake_optimizer.py` | Optimal CAKE params, diff analysis, apply logic | routeros_rest | NEW |
| `benchmark.py` (CLI) | flent subprocess wrapper, result parsing, grading, storage | flent (subprocess), storage | NEW |
| `routeros_rest.py` | Queue type GET/PATCH via REST API | MikroTik router | MODIFY |
| `storage/schema.py` | Benchmark results table schema | SQLite | MODIFY |
| `storage/reader.py` | Benchmark query functions | SQLite | MODIFY |
| `history.py` | `--benchmarks` query/display | storage/reader | MODIFY |

### Data Flow: Auto-Fix

```
User runs: wanctl-check-cake spectrum.yaml --fix

1. check_cake.py parses YAML, creates router client       (existing)
2. check_cake.py calls run_audit()                         (existing)
3. check_cake.py calls cake_optimizer.analyze_queue_types() (NEW)
   a. Reads queue type from router: GET /rest/queue/type?name=<type_name>
   b. Compares each CAKE parameter against OPTIMAL_CAKE_PARAMS
   c. Returns list[CakeRecommendation] with current/recommended/rationale
4. Recommendations displayed as CheckResult items          (NEW)
5. If --fix AND recommendations exist:                     (NEW)
   a. Displays proposed changes with before/after
   b. Prompts for confirmation (unless --yes)
   c. Calls cake_optimizer.apply_recommendations(client, recs)
   d. PATCH /rest/queue/type/<id> {param: value}
   e. Reports success/failure per parameter
```

### Data Flow: Benchmark

```
User runs: wanctl-benchmark --host <netperf_server> --duration 30

1. Validate prerequisites (flent and netperf installed)
2. Build flent command: flent rrul -H <host> -l <duration> -o <output.json.gz>
3. Run via subprocess.run() with timeout
4. Parse gzipped JSON result file
5. Extract key metrics: avg dl/ul speed, avg/p95/p99 RTT under load
6. Compute latency increase: loaded_rtt - idle_rtt
7. Grade: A (<5ms increase), B (5-30ms), C (>30ms)
8. Store in SQLite benchmarks table
9. Display summary with grade, comparison to previous run if available
```

## Critical Architectural Decision: Queue Type vs Queue Tree

**CAKE parameters live on the queue type object (`/queue/type`), NOT on queue tree entries (`/queue/tree`).**

The queue tree entry references a queue type by name (e.g., `queue=cake-down-spectrum`) and only controls `max-limit`. The actual CAKE knobs (diffserv, flowmode, nat, ack-filter, wash, rtt, overhead) are properties of the queue type.

This means:
- Current `routeros_rest.py` has queue tree methods but NO queue type methods
- Auto-fix must add `get_queue_type()` and `set_queue_type_params()` to RouterOSREST
- The queue type name is extracted from the queue tree entry's `queue` field (already read during audit)
- REST API endpoint: `GET/PATCH /rest/queue/type`

**Confidence:** HIGH -- verified via MikroTik CAKE docs and Queues docs

### RouterOS REST API: Queue Type Endpoints

```
# List all queue types
GET /rest/queue/type

# Get specific queue type by name
GET /rest/queue/type?name=cake-down-spectrum

# Update queue type parameters by ID
PATCH /rest/queue/type/*3
Content-Type: application/json
{
    "cake-diffserv": "diffserv4",
    "cake-flowmode": "triple-isolate",
    "cake-nat": "yes"
}
```

The `_find_resource_id()` method in routeros_rest.py already supports this pattern -- it searches any endpoint with any filter key. Queue type lookup follows the exact same pattern as queue tree and mangle rule lookups:

```python
self._queue_type_id_cache: dict[str, str] = {}

def _find_queue_type_id(self, type_name: str) -> str | None:
    return self._find_resource_id(
        endpoint="queue/type",
        filter_key="name",
        filter_value=type_name,
        cache=self._queue_type_id_cache,
    )
```

## New Code: Component Specifications

### cake_optimizer.py

```python
"""CAKE queue type optimization for MikroTik RouterOS.

Analyzes CAKE qdisc parameters on the router, compares against optimal
settings, and optionally applies corrections via REST API.

Works with queue TYPE objects (/queue/type), not queue TREE entries.

Key types:
- OPTIMAL_CAKE_PARAMS: known-good defaults for home WAN CAKE
- CakeRecommendation: what to change, why, current vs recommended
- analyze_queue_types(): read router state, compute recommendations
- apply_recommendations(): PATCH queue type via REST API
"""

@dataclass
class CakeRecommendation:
    queue_type_name: str
    parameter: str
    current_value: str
    recommended_value: str
    rationale: str

# Optimal parameters for home WAN CAKE -- link-independent defaults
OPTIMAL_CAKE_PARAMS: dict[str, tuple[str, str]] = {
    "cake-diffserv": ("diffserv4", "4-tin priority separation for mixed traffic"),
    "cake-flowmode": ("triple-isolate", "Per-flow fairness with host isolation"),
    "cake-nat": ("yes", "NAT-aware flow tracking behind home router"),
    "cake-ack-filter": ("ack-filter", "Reduce ACK overhead on asymmetric links"),
    "cake-wash": ("yes", "Clear untrusted DSCP markings from ISP"),
}

# Link-type-dependent parameters -- these MUST come from config, not hardcoded
# cake-overhead-scheme: cable=docsis, DSL=varies, fiber=ethernet
# cake-rtt-scheme: depends on ISP baseline latency
# cake-atm: only for DSL/ATM links
LINK_DEPENDENT_PARAMS: set[str] = {
    "cake-overhead-scheme", "cake-overhead", "cake-rtt-scheme",
    "cake-rtt", "cake-atm", "cake-mpu",
}

def analyze_queue_types(
    client,  # RouterOSREST
    queue_type_names: list[str],
    overrides: dict[str, str] | None = None,
) -> list[CakeRecommendation]:
    """Read queue type params from router, compare against optimal."""

def apply_recommendations(
    client,  # RouterOSREST
    recommendations: list[CakeRecommendation],
) -> list[CheckResult]:
    """Apply recommended CAKE params via PATCH to queue type."""
```

### routeros_rest.py Additions (2 methods + 1 cache)

```python
# In __init__:
self._queue_type_id_cache: dict[str, str] = {}

def get_queue_type(self, type_name: str) -> dict | None:
    """Get queue type configuration including CAKE parameters.

    GET /rest/queue/type?name=<type_name>
    Returns full queue type object with all CAKE parameters.
    """

def set_queue_type_params(self, type_name: str, params: dict[str, str]) -> bool:
    """Update CAKE parameters on a queue type.

    Finds type by name, then PATCH /rest/queue/type/<id> with params.
    Returns True if all updates succeeded.
    """
```

These follow the exact same pattern as existing `get_queue_stats()` and `_handle_queue_tree_set()`.

### benchmark.py

```python
"""Bufferbloat benchmarking via flent/netperf RRUL test.

Wraps flent CLI to run Realtime Response Under Load (RRUL) tests,
parses gzipped JSON results, grades bufferbloat severity, and stores
results in SQLite for before/after comparison.

Usage:
    wanctl-benchmark --host <netperf_server>
    wanctl-benchmark --host <netperf_server> --duration 60
    wanctl-benchmark --host <netperf_server> --json
    wanctl-benchmark --history
    wanctl-benchmark --history --last 7d
"""

@dataclass
class BenchmarkResult:
    timestamp: int
    duration_sec: int
    avg_download_mbps: float
    avg_upload_mbps: float
    avg_rtt_idle_ms: float
    avg_rtt_loaded_ms: float
    p95_rtt_loaded_ms: float
    p99_rtt_loaded_ms: float
    latency_increase_ms: float   # loaded - idle
    grade: str                   # A, B, or C
    raw_data_path: str           # path to gzipped JSON file
    wan_name: str
    notes: str

class FlentRunner:
    """Subprocess wrapper for flent RRUL tests."""

    def check_prerequisites(self) -> list[CheckResult]:
        """Verify flent and netperf are installed and available."""

    def run_rrul(self, host: str, duration: int, output_dir: str) -> Path:
        """Run flent rrul test, return path to result JSON.gz file."""

    def parse_results(self, result_path: Path) -> BenchmarkResult:
        """Parse gzipped JSON output, extract key latency/throughput metrics."""

def grade_result(latency_increase_ms: float) -> str:
    """A/B/C grade based on latency increase under load.
    A: <5ms, B: 5-30ms, C: >30ms
    """
```

### storage/schema.py Addition

```sql
-- Benchmarks table for bufferbloat test results
CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    wan_name TEXT NOT NULL,
    duration_sec INTEGER NOT NULL,
    avg_download_mbps REAL,
    avg_upload_mbps REAL,
    avg_rtt_idle_ms REAL,
    avg_rtt_loaded_ms REAL,
    p95_rtt_loaded_ms REAL,
    p99_rtt_loaded_ms REAL,
    latency_increase_ms REAL NOT NULL,
    grade TEXT NOT NULL,
    raw_data_path TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_benchmarks_timestamp
    ON benchmarks(timestamp);
CREATE INDEX IF NOT EXISTS idx_benchmarks_wan
    ON benchmarks(wan_name, timestamp);
```

### pyproject.toml Changes

```toml
[project.scripts]
# ... existing entries ...
wanctl-benchmark = "wanctl.benchmark:main"

[project.optional-dependencies]
benchmark = ["flent"]  # optional, checked at runtime
```

## check_cake.py Changes (Detailed)

Changes are additive -- no modifications to existing audit functions.

### 1. CLI Parser Updates

```python
# In create_parser():
parser.add_argument("--fix", action="store_true",
    help="Apply recommended CAKE parameter optimizations")
parser.add_argument("--yes", action="store_true",
    help="Skip confirmation prompt (use with --fix)")
```

### 2. New Optimization Section in main()

After `run_audit()` completes and before formatting output:

```python
# After audit, run optimization analysis
if config_type == "autorate":
    queue_type_names = _extract_queue_type_names(client, queue_names)
    recommendations = analyze_queue_types(client, queue_type_names, overrides)

    # Add recommendations as CheckResult items
    for rec in recommendations:
        results.append(CheckResult(
            "Optimization", rec.parameter, Severity.WARN,
            f"{rec.parameter}={rec.current_value} (recommended: {rec.recommended_value})",
            suggestion=rec.rationale,
        ))

    # Apply if --fix
    if args.fix and recommendations:
        if not args.yes:
            confirm = input("Apply recommended changes? [y/N] ")
            if confirm.lower() != 'y':
                print("Aborted.")
                return 0
        fix_results = apply_recommendations(client, recommendations)
        results.extend(fix_results)
```

### 3. New Helper: Extract Queue Type Names

The queue tree audit already reads queue entries via `get_queue_stats()`. The `queue` field in the response contains the queue type name. Add a helper to extract it:

```python
def _extract_queue_type_names(client, queue_names: dict[str, str]) -> list[str]:
    """Extract queue type names from queue tree entries."""
    type_names = []
    for direction in ("download", "upload"):
        name = queue_names.get(direction, "")
        if name:
            stats = client.get_queue_stats(name)
            if stats and "queue" in stats:
                type_names.append(stats["queue"])
    return type_names
```

## Patterns to Follow

### Pattern 1: SimpleNamespace Config Wrapping (established in check_cake.py)

**What:** Wrap raw YAML dict in SimpleNamespace for RouterOSREST.from_config()
**When:** Any CLI tool needing router connectivity without daemon Config()
**Why:** Avoids daemon side effects (lock files, log dirs, systemd checks)

```python
router_cfg = _extract_router_config(data)
ns = SimpleNamespace(**router_cfg)
client = RouterOSREST.from_config(ns, logger)
```

### Pattern 2: CheckResult for All Output (established in check_config.py)

**What:** Every finding is a CheckResult with category/severity/message/suggestion
**When:** Any check, recommendation, or fix result
**Why:** Consistent formatting across CLI tools, --json and --quiet support

```python
CheckResult("Optimization", "cake-diffserv", Severity.WARN,
    "cake-diffserv=besteffort (recommended: diffserv4)",
    suggestion="4-tin priority separation for mixed traffic")
```

### Pattern 3: Read-Before-Write Safety for Router Mutations

**What:** Always read current state, show diff, require confirmation before writing
**When:** Any router configuration change (--fix flag)
**Why:** Production safety -- this is a live network device

```python
# 1. Read current
current = client.get_queue_type(type_name)
# 2. Compute diff
recommendations = analyze(current, optimal)
# 3. Display diff
for r in recommendations:
    print(f"  {r.parameter}: {r.current_value} -> {r.recommended_value}")
# 4. Confirm (unless --yes)
if not args.yes:
    confirm = input("Apply changes? [y/N] ")
# 5. Apply
results = apply_recommendations(client, recommendations)
```

### Pattern 4: Subprocess for External Tools

**What:** Run flent via subprocess.run() with timeout and output capture
**When:** External tool integration where no stable Python API exists
**Why:** Clean process isolation, timeout control, exit code handling

```python
result = subprocess.run(
    ["flent", "rrul", "-H", host, "-l", str(duration), "-o", output_path],
    capture_output=True, text=True, timeout=duration + 30,
)
if result.returncode != 0:
    # Handle failure
```

### Pattern 5: Optional Dependencies with Runtime Check

**What:** flent/netperf are optional -- check at runtime, not import time
**When:** benchmark.py prerequisite validation
**Why:** wanctl installs without flent; benchmarking is opt-in

```python
def check_prerequisites(self) -> list[CheckResult]:
    results = []
    for tool in ("flent", "netperf"):
        if shutil.which(tool) is None:
            results.append(CheckResult(
                "Prerequisites", tool, Severity.ERROR,
                f"{tool} not found in PATH",
                suggestion=f"Install: sudo apt install {tool}"))
    return results
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Instantiating Config() in CLI Tools

**What:** Creating Config() or SteeringConfig() in check/benchmark tools
**Why bad:** Config constructors create lock files, set up log dirs, check systemd
**Instead:** Use SCHEMA class attributes for validation, SimpleNamespace for router config

### Anti-Pattern 2: Modifying Queue Tree for CAKE Parameters

**What:** Trying to set CAKE params via `/queue/tree` PATCH
**Why bad:** CAKE parameters live on the queue TYPE, not the tree entry. Queue tree only has `queue` (type reference) and `max-limit`
**Instead:** Read queue tree to get type name, then GET/PATCH `/queue/type`

### Anti-Pattern 3: Importing flent as a Python Module

**What:** `from flent import ...` or direct API calls
**Why bad:** flent has no stable public Python API; internal structure changes between versions
**Instead:** Subprocess wrapper, parse gzipped JSON output file

### Anti-Pattern 4: Hardcoding Link-Dependent CAKE Parameters

**What:** Putting cake-overhead-scheme or cake-rtt-scheme in OPTIMAL_CAKE_PARAMS
**Why bad:** These depend on link type: cable=docsis, DSL=pppoe-ptm, fiber=ethernet
**Instead:** Provide link-independent defaults only; link-dependent params come from YAML config overrides via `optimization:` section

### Anti-Pattern 5: Auto-Applying Without Confirmation

**What:** `--fix` silently applying changes without showing what will change
**Why bad:** Production network device. Wrong CAKE params disrupt traffic
**Instead:** Show diff, require `--yes` for non-interactive mode, log all changes

## CAKE Parameters Reference (RouterOS)

| Parameter | REST API Key | Default | Values | Link-Dependent? |
|-----------|-------------|---------|--------|-----------------|
| Flow mode | cake-flowmode | flowblind | flowblind, srchost, dsthost, hosts, flows, dual-srchost, dual-dsthost, triple-isolate | No |
| DiffServ | cake-diffserv | besteffort | besteffort, precedence, diffserv3, diffserv4, diffserv8 | No |
| NAT | cake-nat | no | yes, no | No |
| ACK filter | cake-ack-filter | off | off, ack-filter, ack-filter-aggressive | No |
| Wash | cake-wash | no | yes, no | No |
| RTT scheme | cake-rtt-scheme | internet | datacentre, lan, metro, regional, internet, oceanic, satellite | YES |
| RTT manual | cake-rtt | (from scheme) | milliseconds | YES |
| Overhead scheme | cake-overhead-scheme | ethernet | ethernet, docsis, pppoe-ptm, bridged-ptm, etc. | YES |
| Overhead manual | cake-overhead | (from scheme) | -64 to 256 bytes | YES |
| ATM | cake-atm | off | on, off | YES (DSL only) |
| MPU | cake-mpu | 0 | bytes | YES |
| Bandwidth | cake-bandwidth-limit | (from queue) | Mbps | No (managed by autorate) |

## Suggested Build Order

### Phase 1: Optimizer Foundation

1. Add `get_queue_type()` and `set_queue_type_params()` to routeros_rest.py
2. Create `cake_optimizer.py` with OPTIMAL_CAKE_PARAMS, CakeRecommendation, analyze logic
3. Tests: mock router responses, verify recommendation generation

**Rationale:** Builds the core optimization engine. Independent of CLI changes.

### Phase 2: Auto-Fix Integration

1. Add `--fix` / `--yes` flags to check_cake.py
2. Wire optimization analysis into main() after audit
3. Add apply flow with confirmation
4. Tests: end-to-end CLI with --fix, mock router, verify PATCH calls

**Rationale:** Depends on Phase 1 optimizer. Extends existing CLI tool.

### Phase 3: Benchmarking

1. Create benchmark.py with FlentRunner, BenchmarkResult, grading
2. Add benchmarks table to storage/schema.py
3. Add query_benchmarks() to storage/reader.py
4. Add --benchmarks to history.py
5. Register wanctl-benchmark in pyproject.toml
6. Tests: mock subprocess, verify parsing/grading, verify SQLite storage

**Rationale:** Fully independent of Phases 1-2. Can be built in parallel.

### Phase ordering rationale:
- Phase 1 before Phase 2: optimizer module must exist before CLI can call it
- Phase 3 independent: benchmarking has zero dependency on optimization
- All phases share: CheckResult output model, SQLite storage patterns

## Sources

- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE)
- [MikroTik Queues Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues)
- [MikroTik REST API Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API)
- [Flent Documentation - Options](https://flent.org/options.html)
- [Flent Documentation - Tests](https://flent.org/tests.html)
- [RRUL Test Suite - Bufferbloat.net](https://www.bufferbloat.net/projects/codel/wiki/RRUL_test_suite/)
- [Flent Output Formats](https://flent.org/output-formats.html)
- Existing codebase: check_cake.py, routeros_rest.py, check_config.py, router_client.py, storage/schema.py, history.py
