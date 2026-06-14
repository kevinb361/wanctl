# Stack Research

**Domain:** Pluggable RTT measurement backend (fping first alternate) for a Python 3.11+ systemd dual-WAN adaptive CAKE controller with a 50ms control loop
**Researched:** 2026-06-13
**Confidence:** HIGH (fping flags/versions verified against upstream `doc/fping.pod`, `CHANGELOG.md`, and `src/output.c`; integration points verified against the live tree)

## Scope Note

This is a **subsequent-milestone** stack delta. The bulk of the measurement stack already exists and is validated (`icmplib` hot path, IRTT subprocess+thread pattern, `RTTMeasurement`/`BackgroundRTTThread` abstractions). This file covers **only** what the new fping backend adds. It does NOT re-research icmplib internals or propose IRTT as a new backend (already present, out of scope).

The A/B target is the **live steering consumer** (`steering/daemon.py`), which currently uses a single-host `ping_host` + `ping_count` via `RTTMeasurement(aggregation=MEDIAN)`. Native autorate (`autorate_continuous.py`) inherits the seam but is dormant in production.

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `fping` (system binary) | 5.1 (Debian/Ubuntu repo) — 5.5 upstream | Alternate ICMP RTT source: one process pings many reflectors, parsed from text | Single fork/exec handles N reflectors with kernel-paced timing, vs icmplib's per-host thread-pool fan-out. Already in Debian/Ubuntu main. No Python build deps. |
| `icmplib` | `>=3.0.4` (already pinned) | **Default** backend; raw-socket ICMP in-process | Stays the default. No subprocess fork/exec per cycle; lowest jitter on the 50ms loop. fping only displaces it if the A/B clearly wins. |
| Python `subprocess` (stdlib) | 3.11+ | Spawn/manage the long-running `fping -l` process; read line-buffered stdout | Already the proven pattern in `irtt_measurement.py`. No new dependency. |
| Python `re` + `shutil.which` (stdlib) | 3.11+ | Parse fping per-packet lines; detect binary presence for fallback | `shutil.which("fping")` mirrors the exact IRTT availability/fallback pattern already in the tree. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new) | — | — | Deliberately zero new Python dependencies. Parsing is stdlib `re`/`str.split`; lifecycle is stdlib `subprocess`/`threading`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` (existing) | Unit tests built from **captured fping output samples** | Mirror `tests/test_irtt_measurement.py` — feed recorded stdout fixtures into the parser; never spawn real fping in unit tests. Capture real samples once (loaded + idle, with loss/partial-line/stall cases) and freeze them as fixtures. |
| `fping` on the dev/deploy host | Capture golden output fixtures + A/B benchmarking | `sudo apt install fping`. Capture with the exact production flag set so fixtures match the parser contract. |
| existing `OperationProfiler` | Cycle-budget + CPU benchmarking (idle and load) | Reuse the profiler already wired into `BackgroundRTTThread`/`IRTTThread`; the A/B harness compares p99 cycle ms icmplib vs fping. |

## fping: Exact Flag Set for a Source-Bound Multi-Reflector Loop

Verified against upstream `doc/fping.pod` and `src/output.c` (fping 5.x). Recommended invocation for a **long-running, source-bound, multi-target loop** feeding a daemon:

```
fping -l -e -D -p <period_ms> -t <timeout_ms> -B 1.0 -r 0 -S <source_ip> \
      <reflector1> <reflector2> <reflector3>
```

| Flag | Meaning | Why for this use |
|------|---------|------------------|
| `-l` (`--loop`) | Loop forever, one round per `-p` period. | Long-lived process; the daemon reads a continuous stdout stream instead of fork/exec per cycle. This is the whole point — amortize the subprocess cost. |
| `-e` (`--elapsed`) | Show round-trip time on each reply line. | Without `-e` there is no RTT in the per-packet line. **Required** for the parser. |
| `-D` (`--timestamp`) | Prefix each line with a Unix timestamp (only active in loop/count modes). | Lets the daemon stamp staleness/ordering from fping's own clock and detect stalls. Default format is `[%.5f] ` (epoch seconds, 5 decimals). |
| `-p <ms>` (`--period`) | Milliseconds between successive packets to an individual target. Default 1000; min 0.001 (or 10ms for non-root if built `--enable-safe-limits`). | Sets the reflector probe cadence. Keep it >= the steering cycle (e.g. 250-500ms) so fping cannot outrun the consumer — same discipline as `cadence_sec` binding in `BackgroundRTTThread`. |
| `-t <ms>` (`--timeout`) | Initial per-target reply timeout. Default 500ms non-loop. | Bound the wait for a lost packet. Keep well under the consumer's staleness threshold. |
| `-B 1.0` (`--backoff`) | Timeout backoff multiplier (default **1.5**). | **Set to 1.0** to disable exponential backoff. A growing timeout would make a flaky reflector's effective probe interval drift unpredictably — bad for a fixed-cadence congestion signal. |
| `-r 0` (`--retry`) | Retries beyond the first try (default **3**). | **Set to 0**. Retries conflate "lost once" with "lost"; for a congestion signal you want the raw per-period result, not a retried best-effort. Loss is signal, not noise to be papered over. |
| `-S <ip>` (`--src`) | Bind source address. | **Mandatory** for ATT/Spectrum policy routing — exactly the role `source_ip` plays in `icmplib.ping(source=...)` today. Maps directly to existing `ping_source_ip` config. |
| (`-I <iface>`) | Bind source interface (needs `SO_BINDTODEVICE`). | Alternative/complement to `-S` if a deployment routes by interface instead of source IP. `-S` is the established wanctl model; prefer it. |

**Flags to NOT use:**
- `-q` / `-Q`: quiet/summary-only modes suppress the per-packet lines you need to parse for per-reflector, per-period RTT. Use the default verbose per-packet output (with `-e -D`).
- `-c` / `-C`: counting modes terminate; we want `-l` continuous.
- `-J` (JSON, fping 5.5): tempting, but (a) **alpha schema, explicitly "subject to change"**, and (b) **not in Debian/Ubuntu 5.1**. Do not depend on it. Parse text. Revisit only if/when 5.5+ is the deploy baseline and the schema stabilizes.
- `-O` (TOS/DSCP): not needed; congestion signal is path RTT, not a marked-flow test.

### Output format the parser must handle (authoritative, from `src/output.c`)

Per-packet **reply** line (`-l -e -D`):
```
[1718294400.12345] 1.1.1.1 : [0], 64 bytes, 8.41 ms
```
Format string: `"%-*s : [%d], %d bytes, %s ms"` with the `-D` prefix `"[%.5f] "`.
- `[<epoch.fraction>]` prefix (from `-D`)
- left-justified host/IP, then ` : `
- `[<seq>]` sequence number
- `<bytes> bytes`
- `<rtt> ms` (the `-e` value)

Per-packet **timeout/lost** line (loss is printed per-packet since **fping 5.0** — #175):
```
[1718294400.62345] 9.9.9.9 : [0], timed out
```
Format string: `"%-*s : [%d], timed out"`.

**Parser contract (build the regex against these two shapes):**
- Extract host, seq, and either `rtt_ms` or a loss marker per line.
- A line that matches neither (startup banner, summary on SIGTERM, partial line from a non-newline-terminated read) must be ignored, not crash the consumer.
- Aggregate per reflector over a window, then median/mean across reflectors — same downstream aggregation the existing path uses (`median-of-3+, mean-of-2, single pass-through`).

## Subprocess vs Library: Two Viable fping Shapes

| Approach | Description | Tradeoff |
|----------|-------------|----------|
| **Long-running `-l` process + reader thread** (recommended) | One persistent `fping -l` per WAN; a daemon reader thread parses line-buffered stdout into the latest `RTTSnapshot`; control loop reads lock-free via `get_latest()`. | Amortizes fork/exec to once-per-process-lifetime. Matches `BackgroundRTTThread` exactly. Cost: must supervise the process (restart on death), guard against stdout stall, drain the pipe so it can't block. |
| **Per-cycle `fping -c1` invocation** (NOT recommended for 50ms loop) | Fork/exec fping each measurement, parse, exit — like the IRTT burst model. | Simpler lifecycle but pays fork/exec + ELF load every cycle. The IRTT thread runs on a **10s** cadence precisely because it forks; that's fine for IRTT, not for a sub-second steering probe. Avoid for the hot path. |

There is **no maintained Python binding for fping** worth adopting; fping is a CLI tool by design ("meant to be used in scripts"). Subprocess is the correct integration.

### Subprocess-lifecycle implications for the 50ms loop

- **Never block the control loop on subprocess I/O.** The control loop must only read a cached `RTTSnapshot` (GIL-protected pointer swap), exactly as it does for icmplib/IRTT today. The fping process and its stdout reader live in a background daemon thread.
- **Non-blocking / bounded stdout reads.** A long-running `-l` process produces a steady line stream; the reader iterates `proc.stdout` line by line. Guard against a wedged process with a stall watchdog (no line in `> N x period` -> treat as degraded, fall back to cached/None, restart the process). This is the fping analogue of the `_blackout_backoff_sec` logic already in `BackgroundRTTThread`.
- **Process death handling.** If fping exits (carrier flap, OOM, kill), `proc.poll()` is non-None; the thread must restart it with backoff and never silently stop publishing. Reuse the IRTT failure-tracking pattern (first failure WARNING, subsequent DEBUG, recovery INFO).
- **Clean shutdown.** Terminate the child on daemon stop (SIGTERM, then SIGKILL on timeout) so it does not leak. The 5s join pattern in `BackgroundRTTThread.stop()` / `IRTTThread.stop()` is the template.
- **No per-cycle allocation churn.** Pre-compile the line regex at module load (the existing `_RTT_PATTERN = re.compile(...)` pattern). Period pacing is fping's job (`-p`), not Python's.

## icmplib (default) vs fping (alternate): Comparison

| Dimension | `icmplib` (default, in-process) | `fping -l` (alternate, subprocess) |
|-----------|----------------------------------|------------------------------------|
| Mechanism | Raw ICMP socket inside the Python process | External binary, one process, ICMP from C |
| Fan-out to N reflectors | `ThreadPoolExecutor`, one ping call per host per cycle | One process pings all reflectors per round, kernel-paced |
| Fork/exec cost | None | Once per process lifetime (with `-l`); avoid per-cycle |
| Source binding | `icmplib.ping(source=source_ip)` | `-S <source_ip>` (equivalent); or `-I <iface>` |
| Privilege model | `privileged=True` raw socket, needs `CAP_NET_RAW` | Needs `CAP_NET_RAW` too (raw socket) — **inherited from the existing `AmbientCapabilities=CAP_NET_RAW` on `steering.service`**; subprocess inherits ambient caps. No `setcap` on the binary required. |
| Loss semantics | `result.is_alive` / empty `rtts` | per-packet `timed out` line (since 5.0) |
| Timing jitter on hot loop | Lowest (no exec) | Slightly higher; mitigated by long-running process + background thread |
| Parse surface | None (structured object) | Text lines (parser is the main new risk surface) |
| Dependency | Python wheel (pinned) | System package + fallback-when-missing |

**Net:** icmplib remains the safe default. fping's potential win is offloading multi-reflector ICMP pacing/timing to C and out of the GIL, and getting kernel-timestamped per-packet loss lines. Whether that materially improves the steering signal or cycle budget is exactly what the A/B is for. The privilege model is already satisfied, so adoption risk is concentrated in **parser robustness + subprocess supervision**, not deployment.

## Installation

```bash
# Deploy host (Debian/Ubuntu family) — system binary, optional
sudo apt-get install -y fping        # 5.1 on current Debian/Ubuntu

# No new Python packages. icmplib stays pinned as-is in pyproject.toml:
#   icmplib>=3.0.4

# Privilege: already covered by steering.service
#   AmbientCapabilities=CAP_NET_RAW
#   CapabilityBoundingSet=CAP_NET_RAW
# fping subprocess inherits CAP_NET_RAW; no setcap cap_net_raw+ep on the binary needed.
# (setcap on /usr/bin/fping is the FALLBACK only if a deployment runs fping outside the
#  ambient-cap unit; prefer the systemd ambient capability already present.)
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Text parse of `-l -e -D` | `fping -J` JSON (5.5) | Only once fping 5.5+ is the deploy floor AND the JSON schema leaves alpha. Not today (Debian/Ubuntu ship 5.1; schema "subject to change"). |
| Long-running `-l` process | Per-cycle `fping -c1` | Never for the steering hot path. Acceptable only for a slow background probe (IRTT-style 10s cadence), which is not this milestone's need. |
| `-S` source IP binding | `-I` interface binding | If a deployment routes by egress interface rather than source IP. wanctl's established model is `ping_source_ip`, so `-S` maps 1:1. |
| `fping` subprocess | A Python fping binding / `cffi` wrapper | Never. No maintained binding; fping is CLI-by-design; subprocess matches the proven IRTT pattern with zero new deps. |
| `fping` | Keep `icmplib` only (no alternate) | If the A/B shows no clear win — the milestone explicitly allows staying on icmplib. |

## What NOT to Use / Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| SciPy / NumPy | Stdlib-only mandate carried since Phase 214/v1.47; aggregation is median/mean over a handful of values. | `statistics.median` / `statistics.mean` (already used). |
| pandas | Same — heavy dep for trivial windowed aggregation. | Plain lists + stdlib `statistics`. |
| A hard `fping` dependency | Milestone constraint: no hard fping dependency; must fall back when missing. | `shutil.which("fping")` gate + automatic fallback to `icmplib` (mirror `IRTTMeasurement` which warns and degrades when the binary is absent). |
| `fping -J` JSON output | Alpha schema (5.5), explicitly subject to change; absent from Debian/Ubuntu 5.1. | Parse the stable text per-packet format. |
| `fping -q` / `-Q` | Suppresses per-packet lines the parser needs. | Default verbose per-packet output with `-e -D`. |
| `-B` default (1.5 backoff) / `-r` default (3 retries) | They distort the per-period congestion signal (variable effective interval, masked loss). | `-B 1.0 -r 0` for raw fixed-cadence sampling. |
| Per-cycle subprocess fork in the 50ms loop | fork/exec + ELF load every 50ms is wasteful and jittery. | One long-running `-l` process + background reader thread + cached `RTTSnapshot`. |
| `setcap cap_net_raw+ep /usr/bin/fping` as the primary plan | File caps are sticky to the binary; anyone who can exec it gains the cap. | Inherit the existing `AmbientCapabilities=CAP_NET_RAW` from the systemd unit. setcap only as a non-systemd fallback. |
| Introducing IRTT as a "new" backend | Already present (`irtt_measurement.py`/`irtt_thread.py`); explicitly out of scope. | N/A — reuse its patterns, don't re-add it. |

## Integration Points (existing seam)

The pluggable seam lands in the shared `rtt_measurement` path so both steering and (dormant) native autorate inherit it:

- **`src/wanctl/rtt_measurement.py`** — `RTTMeasurement` is the de-facto interface today (`ping_host`, `ping_hosts_with_results`, `ping_hosts_concurrent`). Refactor `icmplib` behind a backend abstraction; add an fping backend producing the same `RTTSnapshot` / per-host dict shape. `BackgroundRTTThread` already provides the cached-snapshot, lock-free-read, persistent-pool lifecycle the fping reader should plug into.
- **`src/wanctl/steering/daemon.py`** — A/B target. `_create_steering_components()` constructs `RTTMeasurement(..., MEDIAN)` from `measurement.ping_host` + `ping_count`. Backend selection is a config switch here. Note steering today uses a **single** `ping_host`; fping's multi-reflector strength means the seam may also want a reflector-list path (the autorate side already has `ping_hosts: [...]`).
- **`src/wanctl/autorate_continuous.py`** — inherits the seam via the shared path; not stood up for validation this milestone.
- **Config** — new per-WAN/per-consumer `backend: icmplib|fping` selector; reuse existing `ping_source_ip` (-> `-S`) and reflector list (`ping_hosts`). Keep `icmplib` as the unset default.
- **Tests** — `tests/test_rtt_measurement.py` exists; add `tests/test_fping_measurement.py` built from captured stdout fixtures (reply, timeout, partial-line, banner, process-death), paralleling `tests/test_irtt_measurement.py`.
- **systemd** — `steering.service` already has `AmbientCapabilities=CAP_NET_RAW`; no unit change required for the fping subprocess to send ICMP. PATH must include fping's location (`/usr/bin`), which it does.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| fping 5.0+ | the per-packet `timed out` parser | Per-lost-packet line introduced in 5.0 (#175). Earlier (4.x) aggregated loss differently — parser should target 5.x, which is what Debian/Ubuntu ship. |
| fping 5.1 (Debian/Ubuntu) | `-l -e -D -p -t -B -r -S` | All target flags present and stable in 5.1. Safe baseline. |
| fping 5.5 (upstream) | `-J` JSON | JSON is alpha; do not target. Text path remains valid on 5.5. |
| `-D` predefined timestamp formats | fping 5.3+ | Default `[%.5f]` epoch prefix works on all 5.x; ISO/RFC3339 named formats are 5.3+. Parse the default epoch form for portability across 5.1. |
| icmplib `>=3.0.4` | unchanged | Default backend pin stays as-is. |

## Sources

- `https://raw.githubusercontent.com/schweikert/fping/develop/doc/fping.pod` — flag semantics for `-l/-p/-t/-r/-B/-S/-I/-q/-Q/-D/-e/-O` (HIGH)
- `https://raw.githubusercontent.com/schweikert/fping/develop/src/output.c` — exact per-packet format strings `"%-*s : [%d], %d bytes, %s ms"`, `"%-*s : [%d], timed out"`, timestamp prefix `"[%.5f] "` (HIGH)
- `https://github.com/schweikert/fping/blob/develop/CHANGELOG.md` — 5.0 per-lost-packet line (#175), 5.3 timestamp formats / cumulative `-Q`, 5.5 `-J` JSON alpha (HIGH)
- `https://github.com/schweikert/fping/releases/tag/v5.5` — latest upstream version (HIGH)
- `https://raw.githubusercontent.com/schweikert/fping/develop/doc/fping-json.md` — `-J` is NDJSON, alpha, schema subject to change (HIGH)
- `https://tracker.debian.org/pkg/fping` — Debian stable/testing/unstable 5.1-1; Ubuntu 5.1-1build1 (HIGH)
- `https://wiki.archlinux.org/title/Capabilities`, systemd-devel CAP_NET_RAW threads — ambient cap inheritance for subprocess ICMP; `ping_group_range` unprivileged fallback (MEDIUM)
- Live tree: `src/wanctl/rtt_measurement.py`, `irtt_measurement.py`, `irtt_thread.py`, `steering/daemon.py`, `deploy/systemd/steering.service`, `pyproject.toml`, `configs/{steering,att,spectrum}.yaml` (HIGH)

---
*Stack research for: pluggable fping RTT backend in wanctl*
*Researched: 2026-06-13*
