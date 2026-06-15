# Phase 241: fping Backend (Offline) + Reflector Quality - Research

**Researched:** 2026-06-15
**Domain:** fping 5.1 subprocess parsing, RTT backend seam implementation, offline fixture-driven testing, SAFE-17 boundary discipline
**Confidence:** HIGH (all source shapes read from tree; fping `-C` format verified against official manpage)

## Summary

Phase 241 builds a second `RttBackend` implementation — `fping_measurement.py` — that
satisfies the exact `probe(hosts) -> RttSample | None` contract Phase 239 landed. It runs
off the 50ms loop on an independent cadence, binds source IP with `-S`, fans out across
reflectors in a single `fping -C` process, parses real fping 5.1 output loss-safely, and
feeds per-reflector loss into the existing `ReflectorScorer.record_results(dict[str,bool])`
interface. Everything is proven offline against captured fixtures. All key decisions are
already locked in CONTEXT.md (D-01..D-08) — this research surfaces the implementation-level
facts to honor them, not alternatives.

Three findings materially shape the plan and are NOT obvious from CONTEXT.md alone:

1. **The SAFE-17 protected-body verifier freezes `BackgroundRTTThread._run` and
   `_ping_with_persistent_pool` byte-for-byte.** Both are icmplib-coupled (they call
   `rtt_measurement.ping_host` directly, never `probe()`). "Reuse `BackgroundRTTThread`"
   (D-07) therefore CANNOT mean editing that thread. The fping backend must drive its own
   `probe()` cadence via a thread that **rhymes with `IRTTThread`** (which is unprotected
   and not in the allowlist) — a small daemon-thread driver, not a modification of the
   icmplib thread. [VERIFIED: scripts/phase239-protected-body-diff.py PROTECTED dict]

2. **The REFL-01 scorer-feed call site lives in `wan_controller.py`, which is NOT in the
   v1.53 allowlist** (and `WANController.measure_rtt` is itself a protected body). The
   smallest-surface honoring of D-05 is to put the loss%→bool conversion **inside the fping
   backend / its thread**, and call `record_results` from there (or from the new thread),
   not by editing `measure_rtt`. The allowlist must be expanded to add
   `fping_measurement.py` and `reflector_scorer.py`; the planner must confirm exactly where
   the gated call site lands without touching a protected body. [VERIFIED: wan_controller.py:1095,1172;
   phase240 boundary regex]

3. **This phase builds the backend but does NOT wire it into the live control path.** The
   factory (`build_rtt_backend()`) and the construction-site swap are explicitly Phase 242.
   241 is "the backend exists, is selectable in principle, and is proven against fixtures."
   Keep the construction inert/test-reachable; do not edit `autorate_continuous.py`'s
   `RTTMeasurement(...)` site. [VERIFIED: ROADMAP.md Phase 242 entry]

**Primary recommendation:** Create `src/wanctl/fping_measurement.py` with an
`FpingMeasurement` class (mirroring `IRTTMeasurement`'s lifecycle: `subprocess.run` +
`timeout`, `TimeoutExpired`→`None`, `_log_failure`, advisory lock, failure-as-None) exposing
`probe(hosts) -> RttSample | None`, plus a small `FpingThread` (mirroring `IRTTThread`) for
the independent cadence. Build the parser from operator-captured real 5.1 fixtures. Feed
loss→bool to the unchanged scorer from inside the fping path. Expand the SAFE-17 allowlist to
`+fping_measurement.py +reflector_scorer.py` and ship a 241 boundary-check script.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `-C count` (per-target timestamped), not `-c` (summary). Each ping is a real
  RTT or a `-` loss token; parser counts `-` tokens for exact per-reflector loss. `-c`
  summary pre-aggregates and is where a bad parse silently turns loss into a number —
  **rejected**.
- **D-02:** Burst geometry `-C 5 -p 200ms` (~1s burst, 20%-resolution per-burst loss).
  Expose `-C`/`-p` as YAML knobs (defaults `5` / `200ms`).
- **D-02a:** fping single-process fanout means burst duration ≈ `C × period` regardless of
  reflector count (reflectors interleaved in one process) — the efficiency win and the basis
  for cadence/timeout math.
- **D-03:** Parser built from captured real fping 5.1 output (D-08), not a mental model.
  Required scenarios: reply, total loss, partial loss, partial line (truncated/interrupted),
  banner/stderr noise, process-death (killed mid-burst). Loss tokens (`-`) → "no sample"; a
  host with **all** pings lost → `per_host_results[host] = None`, `per_host_loss[host] =
  100.0`. A host with no reflectors yielding a sample → `probe()` returns `None`.
- **D-04:** Reuse `RTTAggregationStrategy.MEDIAN` for per-host (median of that host's received
  pings) and cross-host aggregation into `RttSample.rtt_ms`. Partial-loss-but-alive reflector
  still contributes its received-ping median. `RttSample.backend = "fping"`, `source_ip` =
  bound `-S` address, `per_host_loss` populated per reflector.
- **D-05:** Threshold loss%→bool, reuse existing `ReflectorScorer.record_results(dict[str,bool])`
  — scorer internals **not** modified. The controller-path touch is the fping-gated call site
  that converts each reflector's burst loss to a success/fail boolean.
- **D-05a:** Mapping is any-loss-in-burst → fail (default). Flaky-but-alive reflector is
  penalized in scoring but **still contributes its RTT** to `rtt_ms` (scoring and
  sample-usability decoupled). Expose loss→fail threshold as a YAML knob (default: any loss >
  0%). Feed is **gated to the fping backend** — icmplib path byte-unchanged.
- **D-06:** fping gets an independent `cadence_sec` knob, irtt-style (default ~10s) — NOT
  bound to the fast control interval. Subprocess timeout = `(C × period) + grace`, always <
  cadence so bursts never pile. `subprocess.TimeoutExpired` → `_log_failure`-style log →
  return `None` → recover-and-continue. Mirror `irtt_measurement.py`'s lifecycle shape.
- **D-07:** Reuse `BackgroundRTTThread` to drive fping `probe()` — fping is a second
  `RttBackend` implementing the same `probe(hosts) -> RttSample|None` contract.
  **(See Constraint Tension below — the protected-body verifier forbids editing
  `BackgroundRTTThread`; the practical reading is "drive `probe()` from a daemon thread of the
  same shape," via an `IRTTThread`-style driver.)**
- **D-08:** Phase ships a small capture helper script; operator (Kevin) runs it on the live
  host to capture real fping 5.1 output for the six D-03 scenarios; captured samples are
  committed as test fixtures. Operator-in-the-loop: flag the capture step clearly in the plan.

### Claude's Discretion (grounded)

- Exact extra fping flags (`-q` quiet, per-ping `-t` timeout, `-e` elapsed) — planner's choice
  provided D-01's per-ping `-C` output shape is preserved and parser fixtures match the exact
  invocation.
- Capture-script loss-induction method: unreachable/blackhole IP for total loss; deliberately
  lossy/distant target or `tc`-induced drop for partial loss; mid-burst `kill`/signal for
  process-death. Operator-run, safe and non-mutating to production routing.
- Module/file name for the new backend (allowlist names it `fping_measurement.py`) and the
  precise call-site wiring location for the REFL-01 boolean conversion, provided it stays
  fping-gated and inside the SAFE-17 allowlist.
- YAML key names/nesting for `-C`/`-p`/`cadence_sec`/loss-threshold under the fping backend
  config block — keep consistent with the 240 `measurement:` block naming and `/health`
  `measurement` naming (Phase 244 forward-consistency).

### Deferred Ideas (OUT OF SCOPE)

- Backend factory + loud observable runtime fallback when fping absent (FALL-01) — Phase 242.
- `/health` `measurement.backend` / `source_ip` attribution (HEALTH-01) — Phase 244.
- Live A/B (icmplib vs fping) on the steering consumer under rollback anchor — Phase 245.
- Conditional production default flip to fping — Phase 246.
- Extending `ReflectorScorer` to ingest loss *fractions* (vs the D-05 boolean) — rejected for
  this phase as a larger SAFE-17 surface; revisit only if the binary feed proves too coarse.
- `irtt` as a selectable backend (IRTT-MIG-01) — future milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FPING-01 | Operator-selectable fping backend probing via one-shot `subprocess.run` bursts on a background cadence, never on the 50ms loop | `IRTTMeasurement.measure()` + `IRTTThread` lifecycle template (irtt_measurement.py, irtt_thread.py); independent `cadence_sec` precedent (autorate_continuous.py:484) |
| FPING-02 | `-S <source_ip>` binding per WAN, matching `ping_source_ip` | `ping_source_ip` load (autorate_config.py:643); `RTTMeasurement.source_ip` precedent (rtt_measurement.py:172,206); `RttSample.source_ip` field |
| FPING-03 | Multiple reflectors in a single fping process, per-reflector results | `-C` single-process fanout (manpage); `ping_hosts_with_results` per-host attribution shape (rtt_measurement.py:287); `RttSample.per_host_results` dict |
| FPING-04 | Parser from captured real fping 5.1 samples; reply/total-loss/partial-loss/partial-line/banner/process-death; loss → "no sample", never 0ms | fping `-C` format verified (manpage: `host : 91.7 37.0 29.2 - 36.8`); irtt parse-on-nonzero-exit precedent (irtt_measurement.py:102-116); fixture-driven mock pattern (test_irtt_measurement.py:14-27) |
| FPING-05 | Tolerates subprocess stall/death without crashing daemon (bounded timeout, recover-and-continue) | `IRTTMeasurement._run_serialized`/`measure` exception handling + `TimeoutExpired`→None + `_log_failure` (irtt_measurement.py:85-241) |
| REFL-01 | Per-reflector fping loss feeds reflector-quality scoring (additive, fping-gated) | `ReflectorScorer.record_results(dict[str,bool])` unchanged (reflector_scorer.py:134); D-05/D-05a loss→bool gate |
| SAFE-17 | Controller-path edits stay inside v1.53 allowlist; fail-closed boundary verifier proves zero drift | phase240-safe17-boundary-check.sh + phase239-protected-body-diff.py model; allowlist must expand to `+fping_measurement.py +reflector_scorer.py` |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| fping subprocess invocation + parse | New backend module (`fping_measurement.py`) | — | Subprocess wrapper, mirrors `irtt_measurement.py`'s tier |
| Cadence-driven background probing | `FpingThread` (new, IRTTThread-shaped) | — | Off-hot-loop daemon thread; `BackgroundRTTThread._run` is frozen/icmplib-coupled |
| RTT sample shape / seam contract | `rtt_backend.py` (RttSample/RttBackend) | — | Already defined; fping is a structural second impl, **no edit to rtt_backend.py needed** |
| Per-reflector loss→bool → scoring | fping backend call site (gated) | `reflector_scorer.py` (interface only) | Scorer math untouched (D-05); conversion lives on the fping side |
| Source IP resolution (`-S`) | Config (`ping_source_ip`) → backend ctor | — | Existing per-WAN config key; backend reads resolved string |
| Backend selection / construction | **Phase 242** (`build_rtt_backend()`) | — | OUT OF SCOPE for 241; do not wire into live path |
| Offline proof / fixtures | `tests/` + captured fixture files | capture helper script | D-08 operator-run capture; committed text fixtures |

## Standard Stack

This is an internal phase: no new external dependencies. The "stack" is the existing wanctl
module surface plus the `fping` system binary (5.1, already part of the deploy baseline; absent
on this dev host, which is fine — offline/fixture-driven).

### Core (reused, in-tree)
| Component | Location | Purpose | Why Standard |
|-----------|----------|---------|--------------|
| `RttBackend` Protocol | `rtt_backend.py:20` | `probe(hosts) -> RttSample\|None` contract | Phase 239 seam; fping implements structurally |
| `RttSample` dataclass | `rtt_backend.py:36` | Carries rtt_ms, per_host_results, per_host_loss, backend, source_ip | Fields already exist for fping output; no new type |
| `IRTTMeasurement` | `irtt_measurement.py:49` | Subprocess-lifecycle template (timeout, lock, failure-as-None) | FPING-05 rhymes with this exactly |
| `IRTTThread` | `irtt_thread.py:19` | Cadence-driven daemon thread, GIL-protected pointer swap | The correct shape to copy for fping's independent cadence (D-06/D-07) |
| `RTTAggregationStrategy.MEDIAN` | `rtt_measurement.py:83` | Median aggregation enum | D-04 reuse for per-host + cross-host |
| `ReflectorScorer.record_results` | `reflector_scorer.py:134` | `dict[str,bool]` batch feed | REFL-01 target, interface unchanged |

### External binary
| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| `fping` | 5.1 (deploy baseline) | One-shot `-C` bursts | `shutil.which("fping")` for availability; ABSENT on dev host — parser is proven via fixtures only |

**No `npm/pip/cargo install` step.** `fping` is a system package already present on deploy
hosts; Phase 242 owns the absent-binary fallback. No Python dependency is added.

## Package Legitimacy Audit

Not applicable — this phase installs no external language packages. The only external
dependency is the `fping` system binary, already part of the Debian/Ubuntu deploy baseline
(referenced in existing cake-autorate artifacts and `tests/integration/conftest.py:60`).
slopcheck/registry verification does not apply to a pre-existing OS package.

## fping 5.1 `-C` Output Format (FPING-04 ground truth)

> [CITED: fping.org/fping.8.html] [VERIFIED: manpage cross-checked manpages.debian.org]
> **The committed fixtures (D-08) are the binding ground truth — these notes are the model
> the parser is built to, to be confirmed against real captured 5.1 output.**

### `-C count` per-target line shape
- Format: `host : rtt rtt rtt - rtt` — space-separated, one line per target, on **stdout**.
- Manpage canonical example: `somehost : 91.7 37.0 29.2 - 36.8` (5 values for `-C 5`; the
  `-` is the 4th request lost).
- Each token is **either** a float RTT in ms **or** a literal `-` (lost/no-response). The `-`
  is the load-bearing parser signal — **a `-` token must map to "no sample," never `0.0ms`.**
- Per-target loss% for a host = `(count of '-' tokens) / C × 100`. Total loss = all `-`.
- Multiple reflectors → multiple `host : ...` lines, interleaved by fping internally but each
  line is self-contained per target (parse line-by-line, key on the `host` prefix before `:`).

### Flags relevant to the invocation
| Flag | Effect | Parser implication |
|------|--------|--------------------|
| `-C N` | N pings per target, per-target line format | Primary mode (D-01) |
| `-p ms` | Period between pings to a target (min 10ms, default 1000) | Burst duration ≈ `C × period` (D-02a) |
| `-S addr` | Set source address | FPING-02 `-S <ping_source_ip>` |
| `-q` | Quiet: suppress per-probe results + ICMP error msgs, show final summary only | With `-C`, the per-target `host : ...` summary line is still produced; `-q` mainly silences noise |
| `-t ms` | Per-ping timeout (loop/count mode auto-adjusts to period, max 2000ms) | Bound per-ping wait |
| `-D` | Prefix Unix timestamp to output lines in `-l/-c/-C` modes | If used, parser must strip leading timestamp token before the `host :` |
| `-e` | Show elapsed (round-trip) time | Affects token shape — fix the invocation, then match fixtures to it |

**Recommended invocation skeleton (per CONTEXT specifics, exact extras at planner discretion):**
```
fping -S <ping_source_ip> -C 5 -p 200 -q <reflector1> <reflector2> ...
```
Whatever flags are chosen, the capture script (D-08) MUST use the **byte-identical**
invocation so fixtures match the parser's expected shape.

### Exit codes (FPING-05 / parse-on-nonzero discipline)
> [CITED: fping.org/fping.8.html]
- `0` all hosts reachable, `1` some unreachable, `2` IP not found, `3` invalid args, `4`
  syscall failure.
- **Non-zero exit on partial/total loss is NORMAL.** Mirror the documented irtt pitfall
  (irtt_measurement.py:102-116): **parse stdout even on non-zero exit**; do not treat
  returncode≠0 as "no data." Reserve `None` for genuinely unparseable/empty output and
  timeout/death.

### The six D-03 fixture scenarios (what each must exercise)
| Scenario | Capture method (operator, non-mutating) | Parser must produce |
|----------|------------------------------------------|---------------------|
| reply (clean) | normal reflectors | all floats → per-host median, loss 0.0 |
| total loss | blackhole/unrouted IP (e.g. `192.0.2.1` TEST-NET) | all `-` → `per_host_results[h]=None`, `per_host_loss[h]=100.0` |
| partial loss | distant/lossy target or `tc`-induced drop | mix → median of received, loss = `dash/C×100` |
| partial line | mid-burst capture / truncated stdout | tolerate incomplete final line, never crash, never fabricate 0ms |
| banner / stderr noise | stderr interleaving, ICMP error text | ignore non-`host :` lines; parse only valid target lines |
| process-death | mid-burst `kill`/SIGTERM | `TimeoutExpired`/short read → `probe()` returns `None`, daemon survives |

## Reusable-Asset Shapes (exact signatures for the planner)

### `RttBackend` Protocol — `rtt_backend.py:20`
```python
@runtime_checkable
class RttBackend(Protocol):
    def probe(self, hosts: list[str]) -> "RttSample | None": ...
```
`None` = no host yielded a successful measurement (all-fail contract). A returned `RttSample`
always carries a real, non-`None` `rtt_ms`.

### `RttSample` — `rtt_backend.py:36` (frozen, slots)
```python
@dataclasses.dataclass(frozen=True, slots=True)
class RttSample:
    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float                              # time.monotonic()
    measurement_ms: float
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
    backend: str = "icmplib"                      # set to "fping"
    source_ip: str | None = None                  # set to bound -S addr
    per_host_loss: dict[str, float | None] = field(default_factory=dict)  # 0.0=none,100.0=total,None=unmeasured
```
fping populates `backend="fping"`, `source_ip=<-S addr>`, `per_host_loss` per reflector. First
six fields are positionally/typewise identical to `RTTSnapshot` (verified by
test_rtt_backend.py:`test_rttsample_superset_fields`).

### `RTTMeasurement.probe` (icmplib reference impl) — `rtt_measurement.py:325`
The exact aggregation precedent to mirror in fping (D-04 cross-host):
```python
if len(successful_rtts) >= 3:   rtt_ms = statistics.median(successful_rtts)
elif len(successful_rtts) == 2: rtt_ms = statistics.mean(successful_rtts)
else:                           rtt_ms = successful_rtts[0]
# returns None if not successful_rtts
```
Note: this median-of-3+/avg-of-2/passthrough rule is the SAME rule frozen in
`BackgroundRTTThread._run` and `WANController.measure_rtt`. For fping cross-host aggregation,
reuse this exact rule (it is what "MEDIAN strategy" resolves to in the existing seam).
Per-host: median of that host's received `-C` RTTs.

### `IRTTMeasurement` lifecycle (FPING-05 template) — `irtt_measurement.py`
The shape to copy:
- `__init__`: `shutil.which(...)`, `_timeout = duration + grace`, advisory `_lock_path` under
  `WANCTL_RUN_DIR`/`/run/wanctl`, `_consecutive_failures`/`_first_failure_logged`.
- `measure()`: `is_available()` guard → `_run_serialized(cmd)` → parse-even-on-nonzero →
  recovery logging → return parsed-or-None. Wraps `subprocess.TimeoutExpired` →
  `_log_failure(...)` → `None`; bare `except Exception` → `_log_failure(str(exc))` → `None`.
- `_run_serialized(cmd)`: `fcntl.flock` LOCK_EX|LOCK_NB with deadline, then
  `subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)` in `try/finally`
  LOCK_UN. (Note `# noqa: S603` on the hardcoded invocation.)
- `_log_failure(reason)`: first failure WARNING, subsequent identical DEBUG; recovery INFO.

For fping the per-host advisory lock key should incorporate the source IP / reflector set so
two WAN backends don't serialize against each other unnecessarily — confirm in plan.

### `IRTTThread` cadence driver (D-06/D-07 template) — `irtt_thread.py:19`
```python
class IRTTThread:
    def __init__(self, measurement, cadence_sec, shutdown_event, logger): ...
    def start(self): ...   # daemon thread name "wanctl-irtt"
    def stop(self): ...    # join timeout=5.0
    def get_latest(self): ...
    def _run(self):        # loop: measure() -> cache if not None; shutdown_event.wait(cadence)
```
fping's thread is this shape with `probe(hosts_fn())` instead of `measure()`, caching the
latest `RttSample`. **`IRTTThread` is NOT protected and NOT in the allowlist** — but it is a
*template to copy into the new module*, not a file to edit. Adding a `FpingThread` class to
`fping_measurement.py` keeps the edit inside the allowlist.

### `ReflectorScorer.record_results` (REFL-01 target) — `reflector_scorer.py:134`
```python
def record_results(self, results: dict[str, bool]) -> None:
    for host, success in results.items():
        self._record_result(host, success)   # rolling window, score, deprioritize/recover
```
Constructor (`:76`): `ReflectorScorer(hosts, min_score=0.8, window_size=50, recovery_count=3,
wan_name=...)`. Scoring math is internal and **must not be touched** (D-05). REFL-01 only
constructs the `dict[str,bool]` and calls `record_results`. `reflector_scorer.py` is NOT
currently protected by the verifier and NOT in the allowlist → the allowlist must add it.

### `ping_source_ip` config (FPING-02) — `autorate_config.py:643`
```python
self.ping_source_ip: str | None = self.data.get("ping_source_ip", None)
```
Optional-key-with-default precedent. fping reads this resolved value for `-S`. icmplib already
uses it via `RTTMeasurement(source_ip=...)` (rtt_measurement.py:206).

### Independent cadence precedent — `autorate_continuous.py:484`
```python
cadence_sec = first_config.irtt_config.get("cadence_sec", 10.0)
```
Exact precedent for fping's `cadence_sec` knob (D-06).

## Architecture Patterns

### System Architecture Diagram

```
         operator config (per-WAN YAML)
         measurement.backend: fping
         measurement.fping: {count:5, period_ms:200, cadence_sec:10, loss_fail_threshold:0.0}
         ping_source_ip: <addr>
                    │
                    ▼  (resolved string + knobs; Phase 242 selects/constructs — NOT 241)
        ┌────────────────────────────────────────────┐
        │  FpingMeasurement (fping_measurement.py)    │   NEW (allowlist)
        │  .probe(hosts) -> RttSample | None          │
        │    ├─ build cmd: fping -S <ip> -C 5 -p 200  │
        │    ├─ _run_serialized (flock + subprocess.run│
        │    │   timeout=(C×period)+grace)             │
        │    ├─ TimeoutExpired / death -> None         │  ◀── FPING-05
        │    └─ _parse_fping(stdout) ──────────────┐   │
        └──────────────────────────────────────────┼───┘
                    ▲                               ▼
        ┌───────────┴──────────┐      per-host: list[float|'-'] tokens
        │ FpingThread          │      ├─ median(received) -> per_host_results[h]
        │ (IRTTThread-shaped)  │      ├─ dash_count/C×100 -> per_host_loss[h]   ◀── FPING-04
        │ NEW (allowlist)      │      └─ cross-host median-of-3+/avg-2/passthru -> rtt_ms (D-04)
        │ cadence_sec loop     │                     │
        │ caches latest sample │                     ▼
        └──────────┬───────────┘            RttSample(backend="fping",
                   │                          source_ip=<-S>, per_host_loss=...)
                   │ (fping-gated, D-05)
                   ▼
        loss% -> bool (any-loss->fail, threshold knob)
                   │
                   ▼
        ReflectorScorer.record_results({host: ok})   ◀── REFL-01 (interface UNCHANGED)
        reflector_scorer.py (allowlist; math untouched)

  NOT in this phase: build_rtt_backend() factory, live wiring into wan_controller/
  autorate_continuous, /health attribution, fallback, A/B, default flip.
```

### Recommended Module Structure
```
src/wanctl/
└── fping_measurement.py     # NEW: FpingMeasurement(.probe) + FpingThread + _parse_fping
                             #      mirrors irtt_measurement.py + irtt_thread.py shapes

tests/
├── fixtures/fping/          # NEW: committed real 5.1 captures (D-08), one file per scenario
│   ├── reply.txt
│   ├── total_loss.txt
│   ├── partial_loss.txt
│   ├── partial_line.txt
│   ├── banner_noise.txt
│   └── process_death.txt
├── test_fping_measurement.py    # NEW: fixture-driven parser + lifecycle tests
└── test_phase241_safe17_verifier.py  # NEW: verifier behavior test (mirror 240)

scripts/
├── capture-fping-fixtures.sh        # NEW: operator-run capture helper (D-08)
└── phase241-safe17-boundary-check.sh # NEW: expanded-allowlist boundary check
```

### Pattern 1: Parse-on-nonzero-exit
**What:** fping exits non-zero on any loss; stdout still holds valid `host : ...` lines.
**When:** every `probe()`.
**Example (rhymes with irtt_measurement.py:102-116):**
```python
result = self._run_serialized(cmd)            # may have returncode 1/2
if result is None:                            # lock timeout
    self._log_failure("lock timeout"); return None
sample = self._parse_fping(result.stdout, hosts)   # parse regardless of returncode
if sample is None:
    self._log_failure("empty or unparseable fping output"); return None
return sample
```

### Pattern 2: Loss token is never 0ms (the highest-value invariant)
```python
def _parse_target_line(line: str) -> tuple[str, list[float]] | None:
    # "host : 91.7 37.0 29.2 - 36.8"  (strip optional -D timestamp prefix first)
    host, _, rest = line.partition(" : ")
    if not rest:
        return None
    rtts: list[float] = []
    for tok in rest.split():
        if tok == "-":
            continue                 # LOSS: skip, do NOT append 0.0
        try:
            rtts.append(float(tok))
        except ValueError:
            return None              # partial/garbled line -> caller treats as unparseable
    return host.strip(), rtts        # len(rtts) < C implies loss = (C-len)/C
```

### Anti-Patterns to Avoid
- **Editing `BackgroundRTTThread._run` / `_ping_with_persistent_pool`** — frozen by the
  protected-body verifier; instant SAFE-17 violation. Use a new `FpingThread`.
- **Editing `WANController.measure_rtt` to feed the scorer** — protected body; put the
  loss→bool feed on the fping side.
- **Editing `autorate_continuous.py` to construct the backend** — that is Phase 242's factory.
- **Using `-c` summary mode** — pre-aggregates loss into a number (D-01 rejection).
- **Treating returncode≠0 as no-data** — drops legitimate partial-loss samples.
- **Appending `0.0` for a `-` token** — the exact bug FPING-04 exists to prevent.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bounded subprocess + timeout + recovery | Custom Popen/poll loop | `subprocess.run(..., timeout=...)` + `TimeoutExpired` (irtt pattern) | irtt already solved death/stall/zombie; copy it |
| Cross-process serialization | New lockfile scheme | `fcntl.flock` advisory lock (irtt `_run_serialized`) | Proven, same `/run/wanctl` convention |
| Cadence daemon thread | New scheduler | `IRTTThread`-shaped daemon + `shutdown_event.wait(cadence)` | GIL-protected pointer-swap pattern is established |
| RTT aggregation | New median logic | median-of-3+/avg-of-2/passthrough (rtt_measurement.py:343) | Must match the frozen seam rule exactly |
| Reflector scoring | New scoring/feed | `ReflectorScorer.record_results` (unchanged) | D-05; touching math = larger SAFE-17 surface |
| Sample type | New dataclass | `RttSample` (fields already present) | per_host_loss/backend/source_ip exist for fping |
| Failure log throttling | Custom rate limiter | `_log_failure` first-WARNING-then-DEBUG (irtt) | Avoids log spam under sustained loss |

**Key insight:** fping should be ~90% a structural clone of `irtt_measurement.py` +
`irtt_thread.py` with a different command builder and a text (not JSON) parser. The novel code
is `_parse_fping` and the loss→bool gate; everything else is copy-with-rename.

## Runtime State Inventory

This is a greenfield additive backend, but it touches a production control system. Explicit
inventory of runtime state that a grep audit would miss:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — fping backend stores no persistent state; `ReflectorScorer` windows are in-memory and reset on restart (verified: reflector_scorer.py uses in-memory deques). | None |
| Live service config | fping backend is NOT wired into any running service this phase (construction is Phase 242). No systemd unit, no `/health` field, no live config consumes it yet. | None — confirm no live wiring leaks in (boundary verifier) |
| OS-registered state | None — no new systemd units, timers, or scheduler registrations. `fping` binary must exist on deploy host at runtime (Phase 242 fallback owns absent-binary). | None this phase |
| Secrets/env vars | None new. `WANCTL_RUN_DIR` (existing) is read for the advisory lock path if the irtt lock pattern is copied. No new secret. | None |
| Build artifacts | New module `fping_measurement.py` ships in the package; no egg-info/binary rename. Installed via existing `scripts/install.sh`/`deploy.sh` (deferred to deploy phase). | None this phase (offline) |

**Note for the planner:** because nothing is wired live, the production-runtime risk this phase
is near-zero — the risk surface is entirely SAFE-17 boundary drift, not runtime behavior.

## SAFE-17 Boundary Discipline (the dominant constraint)

### Current allowlist (Phase 240 verifier) — MUST EXPAND for 241
```
V153_ALLOWLIST_RE = ^src/wanctl/(rtt_backend\.py|rtt_measurement\.py|
                                 check_config_validators\.py|check_steering_validators\.py)$
```
Phase 241 needs a NEW script `phase241-safe17-boundary-check.sh` (copy of
`phase240-safe17-boundary-check.sh`) with the regex extended to add:
- `fping_measurement\.py` (the new backend — the SAFE-17 requirement names it explicitly)
- `reflector_scorer\.py` (the REFL-01 accepted exception — named in SAFE-17 text)

### Protected bodies (phase239-protected-body-diff.py PROTECTED dict) — DO NOT TOUCH
```
src/wanctl/rtt_measurement.py:
  RTTSnapshot, RTTMeasurement.__init__, RTTMeasurement.ping_host,
  RTTMeasurement._aggregate_rtts, RTTMeasurement.ping_hosts_with_results,
  BackgroundRTTThread._run, BackgroundRTTThread._ping_with_persistent_pool
src/wanctl/wan_controller.py:
  WANController.measure_rtt
```
Plus the "allowed-shape" guard on `rtt_measurement.py` permits exactly ONE added qualname:
`RTTMeasurement.probe`. **Phase 241 should ideally add NOTHING to `rtt_measurement.py`** — the
fping backend lives entirely in `fping_measurement.py`, so the existing allowed-shape guard for
`rtt_measurement.py` continues to pass byte-identically. If the planner finds a reason to add
to `rtt_measurement.py`, the protected-body helper must be extended — flag as risk.

### How the verifier runs (model from phase240 script)
1. Fail closed if `src/wanctl/` tree is dirty/staged/untracked (run AFTER edits committed).
2. `git diff --name-only <anchor> HEAD -- src/wanctl/` ∖ allowlist must be empty.
3. RTT-seam (`rtt_backend.py`, `rtt_measurement.py`) drift since Phase 239 close anchor must be
   empty (NOTE: 241 likely needs to ADD to `rtt_backend.py`? — **NO**, RttSample already
   carries everything; 241 should leave `rtt_backend.py` byte-unchanged too. Confirm: if the
   `IrttRttBackend` placeholder or any seam edit is needed, the "no RTT-seam drift" layer must
   be re-anchored — flag).
4. `phase239-protected-body-diff.py` proves protected bodies byte-identical + allowed-shape ok.
5. Emit JSON evidence under the phase `evidence/` dir.

**Open question for planner (verifier extension):** the Phase 240 script hard-codes a
"no RTT-seam drift since Phase 239" layer keyed on `rtt_backend.py` + `rtt_measurement.py`. If
241 genuinely leaves both byte-unchanged (recommended), that layer passes as-is. The new
script must add `fping_measurement.py` + `reflector_scorer.py` to the *path* allowlist while
keeping the seam-no-drift and protected-body layers intact. A `test_phase241_safe17_verifier.py`
should mirror `test_phase240_safe17_verifier.py`.

## Common Pitfalls

### Pitfall 1: `-` loss token parsed as 0.0ms
**What goes wrong:** a naive `float(tok)` or a `split("time=")`-style parse turns a lost ping
into a real low RTT, masking loss and corrupting both `rtt_ms` and reflector scoring.
**Why:** the `-C` format interleaves real floats and `-` on one line; sloppy tokenizing.
**Avoid:** explicit `if tok == "-": continue` (skip), never append a number. Assert it in a
fixture test against a `-`-heavy line. **This is the single highest-value FPING-04 regression.**
**Warning signs:** loss scenarios producing non-None `per_host_results` or `per_host_loss==0.0`.

### Pitfall 2: Editing a frozen body to "reuse" the icmplib thread
**What goes wrong:** taking D-07 literally and editing `BackgroundRTTThread._run` to branch on
backend → instant protected-body verifier failure.
**Avoid:** add a separate `FpingThread` in `fping_measurement.py`; do not edit
`rtt_measurement.py` thread code.
**Warning signs:** boundary check reports `changed_nodes: [BackgroundRTTThread._run]`.

### Pitfall 3: Scorer feed via `wan_controller.py`
**What goes wrong:** wiring `record_results` from `measure_rtt` (the obvious place for icmplib)
edits a protected body AND a non-allowlisted file.
**Avoid:** convert loss→bool and call `record_results` from the fping backend/thread side,
fping-gated, inside `fping_measurement.py`.
**Warning signs:** diff touches `wan_controller.py`.

### Pitfall 4: Non-zero exit treated as failure
**What goes wrong:** `if result.returncode != 0: return None` drops every partial/total-loss
burst (exit 1/2 is normal). Loss data vanishes.
**Avoid:** parse stdout regardless of returncode (irtt precedent); reserve `None` for
empty/unparseable/timeout/death.
**Warning signs:** total-loss fixtures yield `probe()->None` instead of a sample with
`per_host_loss=100.0` (note: all-hosts-lost legitimately returns None per D-03; the bug is
*partial* loss vanishing).

### Pitfall 5: Burst piling / cadence < burst
**What goes wrong:** timeout ≥ cadence or burst longer than cadence → overlapping subprocesses.
**Avoid:** enforce `timeout = (C × period_ms/1000) + grace` and validate `timeout < cadence_sec`
(D-06). Default math: `(5 × 0.2) + grace ≈ 1.x s` ≪ 10s cadence.
**Warning signs:** rising subprocess count, zombies, FD growth (Phase 243 benchmark catches it,
but bound it here).

### Pitfall 6: Capture invocation drifts from runtime invocation
**What goes wrong:** the D-08 capture script uses different flags than the backend → fixtures
don't match the parser's expected shape (e.g. `-D` timestamp prefix present in fixtures but not
handled, or `-e` elapsed changing token shape).
**Avoid:** the capture script and the backend MUST build the identical command (share the
builder or assert equality). Fix the flag set in the plan before capture.

## Code Examples

### fping command builder (mirrors irtt `_build_command`)
```python
def _build_command(self, hosts: list[str]) -> list[str]:
    cmd = ["fping", "-C", str(self._count), "-p", str(self._period_ms), "-q"]
    if self._source_ip:
        cmd += ["-S", self._source_ip]
    cmd += hosts
    return cmd  # noqa: S603 -- fixed fping invocation, hosts are config-controlled reflectors
```

### Per-host loss + aggregation into RttSample (D-04)
```python
def _parse_fping(self, stdout: str, hosts: list[str]) -> "RttSample | None":
    from wanctl.rtt_backend import RttSample
    per_host_results: dict[str, float | None] = {}
    per_host_loss: dict[str, float | None] = {}
    successful: list[str] = []
    all_received: list[float] = []
    for line in stdout.splitlines():
        parsed = self._parse_target_line(line)   # see Pattern 2
        if parsed is None:
            continue                              # banner/noise/partial -> ignore line
        host, rtts = parsed
        loss_pct = (self._count - len(rtts)) / self._count * 100.0
        per_host_loss[host] = loss_pct
        if rtts:
            med = statistics.median(rtts)
            per_host_results[host] = med
            successful.append(host)
            all_received.append(med)
        else:
            per_host_results[host] = None         # total loss for this host
    if not all_received:
        return None                               # D-03: no host yielded a sample
    if len(all_received) >= 3:   rtt_ms = statistics.median(all_received)
    elif len(all_received) == 2: rtt_ms = statistics.mean(all_received)
    else:                        rtt_ms = all_received[0]
    return RttSample(
        rtt_ms=rtt_ms, per_host_results=per_host_results,
        timestamp=time.monotonic(), measurement_ms=0.0,
        active_hosts=tuple(hosts), successful_hosts=tuple(successful),
        backend="fping", source_ip=self._source_ip, per_host_loss=per_host_loss,
    )
```

### Loss→bool scorer feed (REFL-01, D-05a, fping-gated)
```python
def _scorer_results(self, sample: "RttSample") -> dict[str, bool]:
    # any-loss-in-burst -> fail (default); threshold is a YAML knob (loss_fail_threshold %)
    return {
        host: (loss is not None and loss <= self._loss_fail_threshold)
        for host, loss in sample.per_host_loss.items()
    }
# then: self._scorer.record_results(self._scorer_results(sample))   # called on fping side only
```

### Fixture-driven parser test (mirrors test_irtt_measurement.py:14-58)
```python
def test_dash_token_never_zero(tmp_path):
    stdout = (FIXTURES / "partial_loss.txt").read_text()
    fake = subprocess.CompletedProcess(args=["fping"], returncode=1, stdout=stdout, stderr="")
    with patch("wanctl.fping_measurement.subprocess.run", return_value=fake):
        sample = backend.probe(["198.51.100.10"])
    assert sample is not None
    # the load-bearing assertion: a '-'-heavy host is never 0.0ms
    assert all(v is None or v > 0.0 for v in sample.per_host_results.values())
```

## State of the Art

| Old Approach | Current Approach | When | Impact |
|--------------|------------------|------|--------|
| Long-lived `fping -l` loop | One-shot `subprocess.run` `-C` bursts | This milestone | Avoids pre-v4.3 pipe block-buffering STALL (REQUIREMENTS out-of-scope table) |
| `fping -c` summary parse | `fping -C` per-target tokens | D-01 | Exact per-reflector loss; `-` never silently becomes a number |
| icmplib ThreadPool-per-host | fping single-process fanout | D-02a | Burst ≈ `C×period` regardless of reflector count |
| fping text parse | `fping -J` JSON | **Deferred** (FPING-JSON-01) | 5.5 alpha schema absent from 5.1 baseline — parse stable text only |

**Deprecated/out of scope here:** `-J` JSON (fping 5.5 alpha), `-l` loop mode, per-cycle
subprocess inside the 50ms loop, hard fping dependency.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | fping 5.1 `-C` line is exactly `host : v v - v` on stdout, `-q` does not suppress the per-target summary line | fping Output Format | LOW — D-08 captures real 5.1 output; fixtures are binding ground truth. Parser is built from fixtures, so a format surprise is caught at capture time, not runtime. |
| A2 | Non-zero exit (1/2) carries valid stdout for partial/total loss | Exit codes | LOW — manpage-documented + mirrors verified irtt behavior; fixtures confirm |
| A3 | `reflector_scorer.py` and `fping_measurement.py` are the correct allowlist additions and the verifier extension is purely a path-regex change | SAFE-17 | MEDIUM — must be confirmed against the actual SAFE-17 requirement wording (it names rtt_backend/fping_measurement/rtt_measurement/factory/config/validator/health + reflector-scorer). Planner should verify the boundary script matches before committing edits. |
| A4 | 241 leaves `rtt_backend.py` and `rtt_measurement.py` byte-unchanged (no seam edit needed) | Reusable shapes / SAFE-17 | MEDIUM — depends on fping not needing a new seam helper. If a seam edit IS needed, the "no RTT-seam drift since Phase 239" verifier layer must be re-anchored. Recommend confirming the backend needs zero seam edits during planning. |
| A5 | The REFL-01 call site can live entirely on the fping side without editing any protected/ non-allowlisted file | Architecture / Pitfalls | MEDIUM — the obvious icmplib feed is in `measure_rtt` (protected). Putting it on the fping side is clean but must be designed so a not-yet-wired backend (Phase 242 wires it live) still has a sensible scorer instance to feed in tests. |
| A6 | Default invocation `-C 5 -p 200 -q -S <ip>` reproduces all six scenarios with capture-script loss induction | Fixture scenarios | LOW — operator-run capture validates empirically; flag exact flags before capture (Pitfall 6). |

## Open Questions

1. **fping sub-param validators — register now or defer?**
   - Known: `measurement.backend` enum is already validated (Phase 240) in
     `check_config_validators.py` (allowlisted). The new knobs (`count`/`period_ms`/
     `cadence_sec`/`loss_fail_threshold`) have NO validator yet.
   - Unclear: whether to add validators in 241 (touches `check_config_validators.py` — IN the
     allowlist, so permitted) or defer to 242 with the factory.
   - Recommendation: add **light** range validators in 241 (count≥1, period_ms≥10,
     timeout<cadence, threshold 0–100) since the file is already allowlisted and it keeps
     operator-typo safety with the feature. Confirm with operator; keep additive.

2. **Scorer instance ownership for an unwired backend.**
   - Known: the live `ReflectorScorer` is constructed in `wan_controller.py` (not allowlisted).
   - Unclear: in 241 (backend not wired live), how does the fping path obtain a scorer to feed?
   - Recommendation: design the backend to accept an optional scorer (or a results-callback)
     injected at construction; in 241 it's exercised via tests with a test scorer. Phase 242's
     factory injects the real one. Avoids any `wan_controller.py` edit this phase.

3. **`-D` timestamp prefix: include or not?**
   - If `-D` is used, every line gains a leading Unix-timestamp token the parser must strip.
   - Recommendation: OMIT `-D` for simplicity (we already timestamp the sample with
     `time.monotonic()`); but the parser should defensively tolerate a leading numeric token to
     survive a capture that included it. Lock the decision before capture (Pitfall 6).

## Environment Availability

| Dependency | Required By | Available (dev host) | Version | Fallback |
|------------|------------|----------------------|---------|----------|
| `fping` binary | live probing (runtime) | ✗ (not on dev VM) | — (deploy: 5.1) | Phase 242 owns absent-binary fallback; 241 is offline/fixtures |
| `subprocess`/`fcntl`/`shutil` | backend lifecycle | ✓ (stdlib) | py3.11+ | — |
| `.venv/bin/pytest` | offline proof | ✓ | per project | — |
| captured 5.1 fixtures | parser tests | ✗ until D-08 capture | — | **operator-run capture is a hard prerequisite for parser tests** |

**Missing with no fallback:** the six captured fixtures — they are produced by the D-08
operator-run capture step. The plan MUST flag this as an operator-in-the-loop gate; parser
tests cannot be authored/passed against real output until capture completes. (Synthetic
placeholder fixtures may bootstrap parser code, but D-03/D-08 require real 5.1 captures for the
binding proof.)

**Missing with fallback:** `fping` binary at dev time — irrelevant; this phase proves
everything against fixtures, not live invocation.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project standard) |
| Config file | `pyproject.toml` (`addopts` present; hot-path slice uses `-o addopts=''`) |
| Quick run command | `.venv/bin/pytest tests/test_fping_measurement.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FPING-04 | `-` token never 0ms (the keystone regression) | unit | `.venv/bin/pytest tests/test_fping_measurement.py -k dash_never_zero -q` | ❌ Wave 0 |
| FPING-04 | reply/total/partial/partial-line/banner/death fixtures each parse correctly | unit | `.venv/bin/pytest tests/test_fping_measurement.py -k parse -q` | ❌ Wave 0 |
| FPING-04 | total loss → per_host_results None, per_host_loss 100.0; all-fail → probe None | unit | `... -k total_loss -q` | ❌ Wave 0 |
| FPING-03 | multi-reflector single process → per-host attribution | unit | `... -k multi_reflector -q` | ❌ Wave 0 |
| FPING-02 | `-S <ip>` present in built command; RttSample.source_ip set | unit | `... -k source_ip -q` | ❌ Wave 0 |
| FPING-05 | `TimeoutExpired` → None, daemon survives; process-death fixture → None | unit | `... -k stall or -k death -q` | ❌ Wave 0 |
| FPING-01 | probe runs via subprocess.run (mocked), FpingThread caches latest, cadence honored | unit | `... -k thread or -k cadence -q` | ❌ Wave 0 |
| FPING-05 | non-zero exit still parsed (returncode 1/2) | unit | `... -k nonzero_exit -q` | ❌ Wave 0 |
| D-04 | per-host median + cross-host median-of-3+/avg-2/passthrough | unit | `... -k aggregation -q` | ❌ Wave 0 |
| REFL-01 | loss→bool feed shape (any-loss→fail, threshold knob); scorer math untouched | unit | `... -k scorer_feed -q` | ❌ Wave 0 |
| SAFE-17 | boundary verifier passes with expanded allowlist; rejects out-of-allowlist drift | unit | `.venv/bin/pytest tests/test_phase241_safe17_verifier.py -q` | ❌ Wave 0 |
| SAFE-17 | protected bodies byte-identical (BackgroundRTTThread._run etc.) | gate (script) | `scripts/phase241-safe17-boundary-check.sh` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_fping_measurement.py -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -q` + hot-path slice
  (`.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py
  tests/test_wan_controller.py tests/test_health_check.py -q`) to prove icmplib path unchanged
- **Phase gate:** full suite green + `scripts/phase241-safe17-boundary-check.sh` PASS before
  `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/fixtures/fping/{reply,total_loss,partial_loss,partial_line,banner_noise,process_death}.txt`
      — real 5.1 captures (D-08, operator-run; synthetic bootstrap allowed but real captures
      are the binding proof)
- [ ] `tests/test_fping_measurement.py` — parser + lifecycle + scorer-feed tests (covers
      FPING-01..05, REFL-01, D-04)
- [ ] `tests/test_phase241_safe17_verifier.py` — mirror `test_phase240_safe17_verifier.py`
- [ ] `scripts/phase241-safe17-boundary-check.sh` — expanded allowlist
      (`+fping_measurement.py +reflector_scorer.py`)
- [ ] `scripts/capture-fping-fixtures.sh` — operator-run capture helper (D-08)
- [ ] Framework install: none — pytest infra exists.

## Security Domain

`security_enforcement` is absent from config (treat as enabled), but this phase has a minimal
security surface: it is offline parsing of trusted-operator-configured reflector output, no
network listener, no auth, no crypto.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | The fping `-C` parser is the only untrusted-input surface (subprocess stdout). It must fail safe on malformed/partial/banner lines (return None / skip line), never crash, never fabricate values. This is exactly what FPING-04 enforces. |
| V6 Cryptography | no | none |
| V2/V3/V4 Auth/Session/Access | no | no auth surface |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess argument injection | Tampering | Hosts come from operator config (reflectors), passed as argv list (no shell); `# noqa: S603` justified as fixed invocation. Do not interpolate into a shell string. |
| Malformed/adversarial fping output | Tampering/DoS | Parser tolerates partial lines/noise, bounded by subprocess timeout; never unbounded read. |
| Subprocess stall/zombie | DoS | `subprocess.run(timeout=...)` + `TimeoutExpired`→None; advisory lock prevents pile-up (FPING-05). |

## Project Constraints (from CLAUDE.md)

- **Production network control system — change conservatively.** This phase is offline/additive
  and does not wire into the live path; keep it that way (wiring is Phase 242).
- **Priority: stability > safety > clarity > elegance.** Favor the copy-irtt approach over a
  clever unified abstraction.
- **Controller spine is read-only unless explicitly requested.** RTT delta control, state
  machines, thresholds, EWMA/dwell/deadband/arbitration/fusion are off-limits (REQUIREMENTS
  out-of-scope table; SAFE-17 fails closed on any such drift).
- **Portable controller architecture (NON-NEGOTIABLE):** deployment-specific behavior in YAML,
  not Python branching. fping `-C`/`-p`/`cadence_sec`/threshold are YAML knobs (D-02/D-05a/D-06)
  — correct by construction.
- **Flash-wear / change-only semantics** apply to router writes, not to this phase (no router
  writes here).
- **Dev commands:** `.venv/bin/pytest`, `.venv/bin/ruff check src/ tests/`,
  `.venv/bin/mypy src/wanctl/`, `.venv/bin/ruff format`. Run `make ci`-equivalent + hot-path
  slice before commit; `project-finalizer` agent is MANDATORY before committing.

## Sources

### Primary (HIGH confidence)
- In-tree source (read directly this session): `rtt_backend.py`, `rtt_measurement.py`,
  `irtt_measurement.py`, `irtt_thread.py`, `reflector_scorer.py`, `autorate_config.py`,
  `autorate_continuous.py`, `check_config_validators.py`, `wan_controller.py`,
  `scripts/phase240-safe17-boundary-check.sh`, `scripts/phase239-protected-body-diff.py`,
  `tests/test_rtt_backend.py`, `tests/test_irtt_measurement.py` — signatures/shapes verified.
- fping(8) manpage — fping.org/fping.8.html (verified `-C`/`-c`/`-q`/`-D`/`-p`/`-t`/`-S`/`-e`,
  output format, exit codes) — [CITED]
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, CONTEXT.md (D-01..D-08, out-of-scope)

### Secondary (MEDIUM confidence)
- manpages.debian.org/unstable/fping/fping.8 (cross-check of `-C` example output) — [CITED]

### Tertiary (LOW confidence)
- None — all parser-shape claims are deferred to D-08 captured fixtures as the binding source.

## Metadata

**Confidence breakdown:**
- Reusable asset shapes: HIGH — read verbatim from tree.
- fping `-C` format: HIGH for the documented shape; **binding ground truth is the D-08
  captured fixtures** (deliberately, per D-03).
- SAFE-17 mechanics: HIGH — verifier scripts read directly; allowlist-extension reasoning
  MEDIUM (planner must confirm against SAFE-17 wording, A3/A4).
- Architecture / pitfalls: HIGH — grounded in the protected-body dict and call-site reads.

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable internal surface; fping 5.1 format is fixed by deploy baseline)
