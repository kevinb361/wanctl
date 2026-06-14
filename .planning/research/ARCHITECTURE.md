# Architecture Research — Pluggable RTT Measurement Backend (v1.53)

**Domain:** Integration architecture for a config-selectable RTT measurement backend in an existing 50ms adaptive-CAKE controller (wanctl)
**Researched:** 2026-06-13
**Confidence:** HIGH (grounded in source reads of `rtt_measurement.py`, `irtt_measurement.py`, `irtt_thread.py`, `wan_controller.py`, `steering/daemon.py`, `autorate_config.py`, validator + configs; fping behavior verified against fping.org/manpages)

> Scope guard: this documents how a NEW pluggable backend folds into the EXISTING controller. It does **not** redesign the control loop, thresholds, state machine, or steering spine. The recommendation deliberately reuses the existing `BackgroundRTTThread` GIL-swap pattern rather than inventing a new concurrency model.

---

## TL;DR for the roadmapper

1. **There is no shared measurement seam today.** `RTTMeasurement` (icmplib) and `IRTTMeasurement`/`IRTTThread` are two parallel silos. icmplib is wired through `BackgroundRTTThread` → `WANController.measure_rtt()`; IRTT is wired through `IRTTThread` → fusion. fping must NOT become a third silo. The first deliverable is a `RttBackend` Protocol that both icmplib and IRTT can sit behind; fping is then just the first *new* implementation.

2. **The live A/B is subtler than "swap icmplib for fping in steering."** In current production (both WANs on cake-autorate) the steering daemon does **not** ICMP-ping at all — `SteeringDaemon.rtt_measurement` is held but never called. Live steering RTT comes from the autorate `/health` payload field `measurement.raw_rtt_ms` (`BaselineLoader.load_live_rtt()`), which in cake-autorate mode is published by the **state bridge**, not by wanctl's `RTTMeasurement`. The roadmap must pick where the A/B actually lands (see "The A/B reality" section) — this is the single highest-risk ambiguity.

3. **Subprocess ownership for a 50ms loop must be a long-lived `fping -l` reader thread, NOT per-cycle spawn.** Per-cycle `subprocess.run` fork/exec is precisely the overhead icmplib was adopted to avoid (the code comments say so). fping in loop mode (`-l`) runs once for the process lifetime and streams stdout; a dedicated reader thread parses lines and publishes a frozen snapshot via the same GIL-swap the icmplib `BackgroundRTTThread` already uses. The control loop never touches the subprocess.

4. **Source binding is already a first-class concept** (`source_ip` → icmplib `source=`, `ping_source_ip` in config). fping preserves it with `-S <ip>` (and optionally `-I <iface>`). Policy routing is unchanged: the source IP still selects the WAN via the host's existing `ip rule`/policy-routing setup. No routing-table work in this milestone.

---

## Current State (what exists, before any change)

### Two parallel measurement mechanisms, no shared interface

```
┌──────────────────────── icmplib path (DEFAULT, hot) ────────────────────────┐
│ RTTMeasurement.ping_host(host)          # icmplib.ping(..., source=source_ip) │
│        ▲                                                                      │
│ BackgroundRTTThread._run()              # daemon thread, cadence-capped       │
│   → fans out per-host via persistent ThreadPoolExecutor                       │
│   → aggregates (median-of-3 / mean-of-2 / passthrough)                        │
│   → publishes frozen RTTSnapshot + RTTCycleStatus via GIL pointer swap        │
│        ▲                                                                      │
│ WANController.measure_rtt()             # lock-free get_latest(); staleness    │
│   (native autorate consumer)              5s hard / 0.5s soft; scorer update)  │
└───────────────────────────────────────────────────────────────────────────┘

┌──────────────────────── IRTT path (secondary, fusion) ──────────────────────┐
│ IRTTMeasurement.measure()               # subprocess.run("irtt client ...")   │
│   → per-burst fork/exec, flock-serialized, JSON parse → IRTTResult            │
│        ▲                                                                      │
│ IRTTThread._run()                       # daemon thread, fixed cadence (10s)  │
│   → publishes IRTTResult via GIL pointer swap (get_latest)                    │
│        ▲                                                                      │
│ WANController._irtt_thread              # fusion healer / deprioritization     │
└───────────────────────────────────────────────────────────────────────────┘
```

**Observation that drives the whole design:** these two already use the *same shape* — a `*Measurement` class (the prober) + a `*Thread` class (daemon loop + GIL-swap publish + `get_latest()`). They just don't share a type. The seam writes itself: extract the shape they already share.

### Consumers and how RTT actually reaches them

| Consumer | File | How it gets RTT today | Status |
|----------|------|------------------------|--------|
| Native autorate `WANController` | `wan_controller.py` | `measure_rtt()` → `BackgroundRTTThread.get_latest()` (icmplib) | Dormant in prod (portable/RouterOS default) |
| Fusion healer | `wan_controller.py` | `_irtt_thread.get_latest()` (IRTT) | Dormant in prod |
| **Steering daemon (LIVE)** | `steering/daemon.py` | `BaselineLoader.load_live_rtt()` → autorate `/health` `measurement.raw_rtt_ms`; falls back to `load_live_irtt_rtt()` → `irtt.rtt_mean_ms`; then `history_fallback` | **LIVE; A/B target** |
| State bridge (cake-autorate mode) | deployed `/usr/local/sbin/cake-autorate-*-state-bridge` (generated by deploy; not in src tree) | Reads cake-autorate log, writes state JSON + serves `/health` incl. `measurement.raw_rtt_ms` | LIVE; produces what steering reads |

### Config / validation surface today

- `continuous_monitoring.ping_hosts`, `continuous_monitoring.use_median_of_three` — autorate reflector set (`autorate_config.py:617-618`).
- top-level `ping_source_ip` — autorate source bind (`autorate_config.py:643`).
- `irtt.*` block — IRTT config (`autorate_config.py:_load_irtt_config`, validated in `check_config_validators.py:173-182`).
- `measurement.ping_host`, `measurement.ping_count`, `timeout.ping` — **steering** config (`steering/daemon.py:168-169`).
- `check_config_validators.py` holds an allow-list of known keys and WARNs on unknown `continuous_monitoring.*` keys (SAFE-06 behavior).

---

## Recommended Architecture (target state)

### System overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        Consumers (UNCHANGED call sites)                     │
│  WANController.measure_rtt()        SteeringDaemon (via /health bridge)      │
│  Fusion healer (_irtt_thread)       autorate health payload builder          │
└───────────────┬───────────────────────────────────┬───────────────────────┘
                │ get_latest() -> RttSample           │ reads measurement.raw_rtt_ms
                ▼                                     ▼
┌───────────────────────────────────────────────────────────────────────────┐
│   RttBackendThread  (generic daemon: loop + GIL-swap publish + get_latest)  │
│   — owns the backend instance, the cadence, the snapshot                    │
└───────────────────────────────────────────────────────────────────────────┘
                │ drives
                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                       RttBackend  (Protocol / ABC)                          │
│   sample(hosts) -> RttSample        # one measurement cycle, all metadata    │
│   is_available() -> bool            # binary present / privileges ok         │
│   start()/stop()                    # optional: own a long-lived subprocess  │
│   name -> str                       # "icmplib" | "fping" | "irtt"           │
├──────────────────┬─────────────────────────┬──────────────────────────────┤
│  IcmplibBackend  │      FpingBackend        │        IrttBackend           │
│  (wraps existing │  (NEW: owns long-lived   │  (adapter over existing      │
│   RTTMeasurement)│   `fping -l` + reader)   │   IRTTMeasurement)           │
└──────────────────┴─────────────────────────┴──────────────────────────────┘
```

### The backend interface (concrete shape)

Two viable shapes. **Recommended: Shape A (prober + generic thread)** because it matches what both existing paths already do and lets the existing `BackgroundRTTThread` collapse into one generic thread.

**Shape A — prober Protocol + one generic daemon thread (RECOMMENDED)**

```python
# src/wanctl/rtt_backend.py  (NEW)

@dataclass(frozen=True, slots=True)
class RttSample:
    """Backend-agnostic measurement result. Superset of today's RTTSnapshot."""
    rtt_ms: float | None                       # aggregated; None = no-success cycle
    per_host_results: dict[str, float | None]  # host attribution (scorer needs this)
    active_hosts: tuple[str, ...]
    successful_hosts: tuple[str, ...]
    timestamp: float                            # time.monotonic()
    measurement_ms: float
    backend: str                                # "icmplib" | "fping" | "irtt"
    source_ip: str | None                       # binding actually used
    loss_pct: float | None = None               # fping/irtt can fill; icmplib derives
    raw_reflector: str | None = None            # which reflector the aggregate came from (optional)

class RttBackend(Protocol):
    name: str
    def is_available(self) -> bool: ...
    def start(self) -> None: ...                # no-op for icmplib; spawns fping -l
    def stop(self) -> None: ...                 # no-op for icmplib; kills fping
    def sample(self, hosts: list[str]) -> RttSample: ...   # one cycle
```

- `RttSample` is a **strict superset** of today's `RTTSnapshot` — add `backend`, `source_ip`, `loss_pct`, keep every existing field so `WANController.measure_rtt()` and the scorer keep working untouched.
- `IcmplibBackend.sample()` is the body that's currently inside `BackgroundRTTThread._ping_with_persistent_pool` + the aggregation block. Move it; don't rewrite it.
- `FpingBackend` owns a long-lived process; `sample()` returns the latest fully-parsed per-host line set the reader has accumulated since the last call (it does **not** spawn). For fping the "thread" inside the backend (stdout reader) and the generic `RttBackendThread` cooperate — see subprocess section.
- `IrttBackend` adapts `IRTTMeasurement.measure()`; maps `IRTTResult` → `RttSample` (single synthetic host = server, `loss_pct` from send/receive loss).

**Shape B — backend owns its own thread + `get_latest()`** (each backend is a full `*Thread`). Rejected as primary: it preserves the silo shape (three independent threads) and duplicates the cadence/staleness/scorer wiring three times. Use it only if fping's streaming model proves impossible to fit Shape A's pull-`sample()` contract — but it isn't (the reader thread + last-snapshot pull fits cleanly).

### Where selection happens (config + validator)

Backend is selected **per WAN** (autorate: per config file) and **per role** (steering has its own config). Proposed keys:

```yaml
# autorate config (e.g. configs/spectrum.yaml), additive
measurement_backend:
  type: "icmplib"          # "icmplib" (default) | "fping" | "irtt"
  fallback: "icmplib"      # used when type backend is_available() == False
  fping:
    period_ms: 200         # fping -p ; min 10; bound to >= control cadence
    # source_ip inherited from top-level ping_source_ip; hosts from continuous_monitoring.ping_hosts
```

```yaml
# steering.yaml, additive (only if the A/B lands on steering's own pinger — see A/B section)
measurement:
  ping_host: "1.1.1.1"
  ping_count: 3
  backend: "icmplib"       # default; "fping" enables A/B leg
```

Validator changes (`check_config_validators.py`, `autorate_config.py`):
- Add `measurement_backend`, `measurement_backend.type`, `.fallback`, `.fping`, `.fping.period_ms` to the autorate known-key allow-list.
- Add `measurement.backend` to the steering validator path list.
- Validate `type`/`fallback` ∈ {`icmplib`,`fping`,`irtt`}; reject unknown; WARN (not fail) if `type: fping` but `shutil.which("fping")` is None at validate time (real fallback happens at runtime).
- Keep SAFE-06 unknown-key WARN behavior intact.

**Backwards compat:** absence of `measurement_backend` ⇒ `type: icmplib`. Zero-config existing deployments behave exactly as today (this protects the "icmplib stays default" milestone constraint).

### Backend construction seam (the factory)

A single factory replaces the two scattered `RTTMeasurement(...)` constructions:

```python
# src/wanctl/rtt_backend.py
def build_rtt_backend(spec, logger, *, source_ip, hosts_fn, timeout_ping, aggregation) -> RttBackend:
    requested = spec.type
    backend = _instantiate(requested, ...)        # icmplib | fping | irtt
    if not backend.is_available():
        logger.warning("RTT backend %s unavailable; falling back to %s", requested, spec.fallback)
        backend = _instantiate(spec.fallback, ...) # fallback wiring lives HERE, once
    return backend
```

Construction sites that change:
- `autorate_continuous.py:_create_wan_components` (line ~145): replace `RTTMeasurement(...)` with `build_rtt_backend(...)`; pass the resulting backend into `WANController`.
- `autorate_continuous.py:_start_irtt_thread` / `_setup_daemon_state`: IRTT becomes a backend choice rather than a hard-wired parallel thread (Shape A folds it; the fusion-specific consumer can keep reading an IRTT-typed snapshot via a typed accessor, see "Folding IRTT").
- `steering/daemon.py:_create_steering_components` (line ~2554): only changes **if** the A/B lands on steering's own pinger.

---

## Subprocess lifecycle for fping inside a 50ms loop (the critical design)

**Rule: the control loop never spawns, never blocks on, and never reads stdout of the fping process.** Same discipline as icmplib's `BackgroundRTTThread` and IRTT's flock-serialized subprocess.

### Long-lived `fping -l` loop process (RECOMMENDED) vs per-cycle spawn

| | Long-lived `fping -l` (RECOMMENDED) | Per-cycle `fping -C1` spawn |
|---|---|---|
| Fork/exec cost | Once per process lifetime | Every cycle — reintroduces the exact overhead icmplib removed |
| Cadence control | `-p period_ms` (min 10ms) | Loop sleep |
| p99 cycle impact | None on control loop (reader thread only) | High risk vs the 6.9ms p99 budget |
| Loss/stall handling | Reader sees gaps / `-` tokens; stall detector on read timeout | Each spawn independent |
| Failure mode | Process death → reader detects EOF → mark unavailable → fallback | Spawn failure per cycle |
| Complexity | Process supervision + stream parsing | Simpler parse, worse perf |

**Command shape:** `fping -l -e -D -p <period_ms> -S <source_ip> <host1> <host2> ...`
- `-l` loop forever (long-lived), `-e` show RTT, `-D` Unix timestamps per line, `-p` per-target period (bind to ≥ control cadence so probe rate can't outrun the loop, mirroring `_background_rtt_cadence_sec`), `-S` source bind. Optionally `-I <iface>`.
- Loop mode emits one line per response; loss shows as unreachable/no-line for that target in the interval. Parser must tolerate: partial lines (read buffering), interleaved targets, `-`/ICMP-unreachable tokens, and silence (stall).

### Ownership model

```
FpingBackend.start()
  └─ Popen(["fping","-l","-e","-D","-p",period,"-S",src, *hosts],
            stdout=PIPE, stderr=PIPE, text=True)        # long-lived
  └─ spawn reader thread: loop over proc.stdout lines
        parse -> update per-host last-RTT map + timestamps (publish frozen
        per-host dict via GIL swap, same as the snapshot pattern)
        detect EOF/return-code  -> set _alive = False

FpingBackend.sample(hosts)        # called by generic RttBackendThread on cadence
  └─ read the reader's accumulated per-host map (lock-free read of last frozen dict)
  └─ aggregate (reuse RTTMeasurement aggregation: median-of-3 / mean-of-2 / passthrough)
  └─ return RttSample(backend="fping", source_ip=src, loss_pct=..., ...)

FpingBackend.stop()
  └─ proc.terminate(); join reader (bounded timeout, mirror IRTTThread.stop 5s)
```

Failure / robustness requirements (these become test cases from captured fping output):
- **Process death:** reader sees EOF/non-zero exit → backend `is_available()` flips false → generic thread keeps publishing stale-prefer-none (existing `_cached` semantics) → next health window triggers `fallback` backend. Optionally auto-respawn with backoff (mirror `_blackout_backoff_sec`).
- **Stall (no lines for N×period):** reader watchdog marks per-host stale; `sample()` returns no-success cycle (RttSample with `rtt_ms=None`) → existing `RTTCycleStatus.successful_count==0` blackout path handles it. **Reuse, do not reinvent, the zero-success blackout logic in `measure_rtt()`.**
- **Partial line / malformed token:** parser skips the line, logs at DEBUG (first occurrence WARN, mirror IRTT `_log_failure` discipline), never raises into the reader loop.
- **`-D` timestamp drift:** trust the reader's own `time.monotonic()` for staleness (as today), use fping's timestamp only for diagnostics.

### Cadence binding

Reuse `_background_rtt_cadence_sec()` semantics: the fping `-p period_ms` and the generic thread cadence are both clamped to ≥ control cadence (and ≥ `BACKGROUND_RTT_MIN_CADENCE_SECONDS`). The probe rate cannot hammer public reflectors faster than the controller can consume — this is an existing invariant, preserve it.

---

## Source binding / policy routing preservation

**No routing changes in this milestone.** The host's existing policy routing (source-IP → WAN, the `FORCE_OUT_*` address-list and `ping_source_ip` machinery) is untouched. The backend just has to *emit packets from the right source IP*:

| Backend | Source-bind mechanism |
|---------|------------------------|
| icmplib | `icmplib.ping(..., source=self.source_ip)` — already done (`rtt_measurement.py:206`) |
| fping | `-S <source_ip>` (+ optional `-I <iface>`). `source_ip` threaded from config `ping_source_ip` exactly as icmplib gets it |
| irtt | (existing) server-targeted; binding is a known IRTT limitation, out of scope |

`RttSample.source_ip` records the binding actually used so the health payload / A/B evidence can prove each leg pinged via the correct WAN. This is new observability that directly serves the A/B audit.

**Verification requirement for the A/B (not a code change):** confirm `fping -S <ip>` egresses the intended WAN under the host's `ip rule` setup before trusting A/B numbers. fping `-S` sets the socket source address; the kernel policy-routing rule keyed on that source selects the link — identical assumption to icmplib `source=`.

---

## Folding both icmplib and IRTT behind the seam

### icmplib

`IcmplibBackend` wraps the existing `RTTMeasurement` instance verbatim. `sample()` = the body of `BackgroundRTTThread._ping_with_persistent_pool()` + the median/mean/passthrough aggregation currently in `_run()`. The persistent `ThreadPoolExecutor` moves into `IcmplibBackend` (it already lives beside the thread). `start()/stop()` are no-ops (no subprocess). **`BackgroundRTTThread` becomes the generic `RttBackendThread`** parameterized by a backend — its loop, profiler, `RTTCycleStatus`, blackout backoff, and `get_latest()` are kept as-is.

### IRTT

`IrttBackend` adapts `IRTTMeasurement`:
- `is_available()` = existing `IRTTMeasurement.is_available()`.
- `sample()` calls `measure()`, maps `IRTTResult` → `RttSample` (one host = server, `rtt_ms=rtt_median_ms`, `loss_pct` from send/receive loss, `backend="irtt"`).
- The fusion healer needs IRTT-specific fields (`ipdv_mean_ms`, ICMP/UDP ratio) that don't fit the generic `RttSample`. **Keep a typed escape hatch:** `IrttBackend` can still expose the raw `IRTTResult` via a backend-specific accessor for fusion, while presenting the generic `RttSample` to the common consumer. This means v1.53 does NOT have to rip out `IRTTThread` — it can keep running for fusion while *also* being expressible as a backend.

> Milestone discipline: v1.53 ships the `RttBackend` seam + `IcmplibBackend` + `FpingBackend`. The IRTT fold is *designed for* (the Protocol accommodates it) but not *fully implemented* — that keeps scope honest and matches the stated out-of-scope list ("IRTT backend" is out of scope). The seam must be *shaped* to absorb IRTT so fping isn't a third silo, even though the IRTT migration itself is deferred.

---

## The A/B reality (highest-risk integration decision — flag for roadmap)

The milestone says "controlled cake-shaper A/B (icmplib vs fping) on the live steering consumer." But in current production:

- Steering does **not** ICMP-ping. `SteeringDaemon.rtt_measurement` is constructed (`daemon.py:2554`) and stored (`:1137`) but **never called** — confirmed by grep: no `self.rtt_measurement.ping_host(...)` anywhere in the cycle.
- Live steering RTT = autorate `/health` `measurement.raw_rtt_ms` via `BaselineLoader.load_live_rtt()`. In cake-autorate mode that field is produced by the **state bridge** from cake-autorate's own pinger, not by wanctl's `RTTMeasurement`.

So "swap the backend in steering" has **three possible interpretations** the roadmap must disambiguate (recommend the roadmapper surface this as an explicit decision):

1. **Steering re-acquires its own pinger** (revive the dormant `self.rtt_measurement` path as a backend) and the A/B compares icmplib-vs-fping *as steering's own RTT source*. Cleanest A/B, but it changes steering's live data path (touches the LIVE consumer — higher risk, controller-adjacent).
2. **A/B at the producer**: stand up the backend seam in the RTT producer that feeds `raw_rtt_ms`. In cake-autorate mode that producer is the state bridge / cake-autorate, which is **outside the wanctl Python backend seam** — fping-vs-icmplib there is a cake-autorate config question, not a wanctl backend question. This likely does NOT exercise the new seam at all.
3. **A/B on native autorate path** (where the seam genuinely lives) and *observe steering's reaction*. The seam is real here, but the milestone explicitly says native autorate is "not stood up for validation," and prod steering doesn't read native autorate today.

**Recommendation to roadmapper:** the only interpretation where the new `RttBackend` seam is genuinely the thing under A/B *and* steering is the live observer is a hybrid: run the backend seam in the RTT producer that steering actually reads, in a measurement-only side-by-side (both backends sampling, only one feeding steering, the other logged), so the A/B is non-disruptive and reversible. This needs an explicit phase to (a) confirm which producer feeds prod steering, (b) decide whether fping is evaluated as steering's own pinger or as the autorate/bridge pinger. **Do not let roadmap phases assume the seam is in steering's hot path — verify the live data path first.**

---

## Data-flow change (a sample with backend/source/reflector metadata)

```
fping -l stdout line  ──parse──►  reader per-host map
        │
        ▼
RttBackendThread cadence tick ──► FpingBackend.sample(hosts)
        │                              └─ RttSample{ rtt_ms, per_host_results,
        │                                            backend="fping", source_ip,
        ▼                                            loss_pct, successful_hosts, ts }
RttBackendThread publishes RttSample via GIL swap (get_latest)
        │
        ├─► WANController.measure_rtt()  (native; staleness + scorer + blackout)
        │
        └─► autorate /health builder  ──► measurement.raw_rtt_ms (+ NEW: measurement.backend)
                                                │
                                                ▼ (bridge / health url)
                                   SteeringDaemon.BaselineLoader.load_live_rtt()
```

New metadata to thread through for A/B evidence (additive, no payload-shape break — respect the health-contract invariant in CLAUDE.md):
- `measurement.backend` (string) in the autorate `/health` payload → lets steering / soak evidence attribute every RTT to the backend that produced it.
- `measurement.source_ip` (optional) for WAN-egress proof.
- Keep `raw_rtt_ms`, `available`, `staleness_sec` byte-for-byte compatible (steering reads them; `health_check.py:486-517` is the contract).

---

## New vs modified components (name the files)

### New
| File | Responsibility |
|------|----------------|
| `src/wanctl/rtt_backend.py` | `RttBackend` Protocol, `RttSample` dataclass, `build_rtt_backend()` factory, `IcmplibBackend`, `IrttBackend` adapter shell |
| `src/wanctl/fping_measurement.py` | `FpingBackend`: long-lived `fping -l` Popen, stdout reader thread, line parser, stall/death/loss handling (mirrors `irtt_measurement.py` structure) |
| `tests/test_fping_measurement.py` | Unit tests built from **captured fping output samples** (loss, partial line, stall, process death) — explicit milestone deliverable |
| `tests/test_rtt_backend.py` | Backend selection, fallback-when-unavailable, RttSample superset compatibility |
| `configs/examples/*` snippet | Documented `measurement_backend:` block |

### Modified
| File | Change | Risk |
|------|--------|------|
| `src/wanctl/rtt_measurement.py` | `BackgroundRTTThread` → generic `RttBackendThread` (parameterized by backend); aggregation extracted so `IcmplibBackend` reuses it; `RTTSnapshot` superseded by/aliased to `RttSample` | Medium — controller-path-adjacent; this ends the SAFE zero-diff streak by design |
| `src/wanctl/autorate_continuous.py` | `_create_wan_components` uses `build_rtt_backend`; `_start_irtt_thread`/`_setup_daemon_state` reconciled with backend selection | Medium |
| `src/wanctl/wan_controller.py` | `measure_rtt()` reads `RttSample` (superset) — ideally **zero behavior change** if RttSample preserves all RTTSnapshot fields; verify scorer + blackout untouched | High sensitivity — keep behavior-identical |
| `src/wanctl/autorate_config.py` | Load `measurement_backend.*`; keep `ping_source_ip`/`ping_hosts` as backend inputs | Low |
| `src/wanctl/check_config_validators.py` | Allow-list + type validation for new keys; runtime-vs-validate-time fping presence WARN | Low |
| `src/wanctl/health_check.py` | Additive `measurement.backend`/`source_ip` fields; preserve existing payload shape | Low-Medium (contract-sensitive) |
| `src/wanctl/steering/daemon.py` | **Only if A/B lands on steering's own pinger** — add `measurement.backend`, build backend in `_create_steering_components`. Otherwise untouched. | High (LIVE) — gate behind the A/B decision |
| `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` | Additive backend block for the A/B leg | Low |

---

## Suggested build order (respects deps + the A/B-on-steering constraint)

1. **Seam first, behavior-identical (the refactor).** Introduce `RttSample` (superset of `RTTSnapshot`), the `RttBackend` Protocol, generalize `BackgroundRTTThread` → `RttBackendThread`, and wrap icmplib as `IcmplibBackend`. Acceptance: full hot-path slice (`test_cake_signal`, `test_queue_controller`, `test_wan_controller`, `test_health_check`) green and **byte-identical RTT behavior** — prove the refactor changed nothing observable. This is the riskiest controller-path step; land it isolated so it can be reverted alone.
2. **Config + validator.** Add `measurement_backend.*` keys, validator entries, default-to-icmplib backwards-compat. Acceptance: `check_config_validators.py` accepts new keys, rejects bad types, WARNs on missing fping; existing configs still validate and still resolve to icmplib.
3. **FpingBackend (offline).** Implement long-lived `fping -l` Popen + reader + parser + failure handling. Build from captured fping output fixtures. Acceptance: `test_fping_measurement.py` covers loss/partial/stall/death; no live network needed.
4. **Factory + fallback wiring.** `build_rtt_backend` chooses backend, falls back when `is_available()` false. Acceptance: `test_rtt_backend.py` proves fping→icmplib fallback when binary absent.
5. **Cycle-budget + CPU benchmark (idle + load).** Prove no 50ms cycle regression vs the `p99≈6.9ms` baseline with fping selected on native autorate. Acceptance: documented cycle-budget evidence, fping reader thread cost isolated from control loop. **Gate: do not proceed to live A/B without this.**
6. **A/B data-path decision (DESIGN GATE, not code).** Resolve the "A/B reality" ambiguity: confirm which producer feeds prod steering's `raw_rtt_ms`, decide whether fping is evaluated as steering's own pinger or the autorate/bridge pinger, design a non-disruptive measurement-only side-by-side. Output: an explicit, reviewed A/B method + rollback anchor before any live config flip.
7. **Health-payload metadata (additive).** `measurement.backend`/`source_ip` in `/health`, preserving contract shape. Acceptance: steering still reads `raw_rtt_ms`; soak/A/B evidence can attribute backend.
8. **Live A/B on steering consumer + rollback anchor.** Pre-registered accept/reject thresholds; rollback anchor armed. Acceptance: A/B evidence captured, verdict computed.
9. **Conditional default flip.** Flip prod default to fping only if A/B clearly wins; else document recommendation and stay on icmplib (safe default).

Dependency notes: 1→2→3→4 are linear (seam before config before impl before wiring). 5 gates 8. 6 gates 8 and is independent of 3/4 (can run in parallel with impl). 7 is a prereq for 8's evidence attribution. Steering source edits (if any) are deferred to step 8 and gated by step 6's decision — keeping the LIVE consumer untouched until the seam, the budget proof, and the A/B method are all settled.

---

## Anti-patterns to avoid

- **fping as a third silo.** If `FpingBackend` doesn't sit behind the same `RttBackend` Protocol that absorbs icmplib (and is shaped to absorb IRTT), the milestone has made the existing problem worse. The seam is the deliverable; fping is the proof.
- **Per-cycle `subprocess.run(fping ...)`.** Reintroduces fork/exec into the 50ms loop — the exact cost icmplib was adopted to remove. Use `-l` loop mode + reader thread.
- **Reinventing blackout/staleness.** `measure_rtt()` already has zero-success blackout, 5s/0.5s staleness, stale-prefer-none. fping no-success cycles must flow through it, not around it.
- **Breaking the `/health` payload shape.** `raw_rtt_ms`/`available`/`staleness_sec` are a steering contract. Only add fields; never rename/remove.
- **Assuming the A/B seam is in steering's hot path.** It currently isn't. Verify the live data path before scoping A/B phases.
- **Changing aggregation semantics.** median-of-3 / mean-of-2 / passthrough must be identical across backends so the A/B compares measurement source, not aggregation math.

## Open questions for the roadmapper

1. **Which producer feeds prod steering's `raw_rtt_ms` today** — native autorate `/health` or the cake-autorate state bridge? This determines whether the new seam is even on the live path. (Strongly recommend a read-only verification phase.)
2. **A/B target choice:** steering's own (dormant) pinger revived as a backend, vs. fping evaluated where the producer lives. Affects whether `steering/daemon.py` (LIVE) is touched at all.
3. **fping source-bind egress proof:** does `fping -S <ip>` actually egress the intended WAN under the host's current `ip rule` setup? (Operator-verifiable; needed before trusting A/B numbers.)
4. **RttSample vs RTTSnapshot:** alias or replace? Aliasing minimizes diff to `wan_controller.py` (lower controller-path risk).

## Sources

- Source reads: `src/wanctl/rtt_measurement.py`, `irtt_measurement.py`, `irtt_thread.py`, `wan_controller.py`, `steering/daemon.py`, `autorate_config.py`, `check_config_validators.py`, `health_check.py`, `configs/{spectrum,steering}.yaml` (HIGH).
- [fping man page (fping.org)](https://www.fping.org/fping.8.html) — `-l`, `-p`, `-S`, `-I`, `-D`, `-e`, `-C`, `-q/-Q` semantics (HIGH).
- [fping(8) Ubuntu manpage](https://manpages.ubuntu.com/manpages/focal/en/man8/fping.8.html) — loop/count output behavior (MEDIUM).
- `.planning/PROJECT.md` v1.53 milestone definition and current production state (HIGH).
