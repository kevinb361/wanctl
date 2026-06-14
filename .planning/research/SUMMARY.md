# Project Research Summary

**Project:** wanctl v1.53 — Pluggable RTT Measurement Backend (fping first alternate)
**Domain:** Subprocess RTT backend abstraction for a 50ms adaptive CAKE/steering control loop
**Researched:** 2026-06-13
**Confidence:** HIGH

## Executive Summary

v1.53 introduces a `RttBackend` Protocol that absorbs both the existing `icmplib` path and a new `fping` subprocess backend, then validates fping against the live steering consumer via a pre-registered A/B. The key architectural insight from all four researchers: there is no shared measurement seam today — icmplib (`BackgroundRTTThread`) and IRTT (`IRTTThread`) are two parallel silos — and fping must not become a third. The seam is the deliverable; fping is the proof of concept. The implementation pattern is fully prescribed by the existing IRTT wrapper: one-shot `subprocess.run` per burst on a background-thread cadence, never touching the 50ms control loop directly.

The single highest-risk ambiguity is the **RTT-provenance problem**. Architecture and Pitfalls researchers independently confirmed that `SteeringDaemon.rtt_measurement` is constructed but **never called** in the current cake-autorate production topology. Live steering RTT flows from the state bridge via `BaselineLoader.load_live_rtt()` reading autorate `/health` `measurement.raw_rtt_ms` — not from wanctl's Python `RTTMeasurement`. The stated "A/B on the live steering consumer" may not exercise the new seam at all unless the A/B target is explicitly disambiguated. **A read-only RTT-provenance verification is a mandatory entry gate before any code is written.**

The second critical finding, directly contradicting the STACK researcher's preference for a long-lived `fping -l` loop process, is that Pitfalls research root-caused the observed systemd STALL to **pipe block-buffering** (fping only gained native line-buffering in v4.3, changelog #179). The one-shot `subprocess.run` design used by `irtt_measurement.py` eliminates the entire buffering hazard class and is the correct design for v1.53. The risk surface is narrowly bounded: parser correctness, subprocess supervision on a background cadence, source-IP binding fidelity, and A/B methodology discipline — not the control algorithm.

---

## Key Findings

### Recommended Stack

No new Python dependencies. fping integrates via `subprocess` (stdlib), binary detected via `shutil.which("fping")` at construction, mirroring the IRTT availability gate. icmplib stays pinned at `>=3.0.4` as the unchanged default. Deploy baseline is fping 5.1 (Debian/Ubuntu main); all required flags (`-l`, `-e`, `-D`, `-p`, `-t`, `-B`, `-r`, `-S`, `-C`) are stable in 5.1. JSON output (`-J`) is alpha-schema in 5.5 upstream and absent from 5.1 — do not use. Parse stable text output only.

Privilege model requires no change: existing `AmbientCapabilities=CAP_NET_RAW` on `steering.service` is inherited by the fping subprocess. `setcap cap_net_raw+ep` on the binary is a non-systemd fallback only.

**Core technologies:**
- `fping` 5.1 (system binary): multi-reflector ICMP prober — kernel-paced C timing, no Python wheel dep, already in prod via cake-autorate's own pinger (`configs/cake-autorate/config.spectrum.sh` proves it viable on this host)
- `icmplib >=3.0.4` (unchanged default): in-process raw ICMP — no fork/exec, lowest jitter on hot loop
- `subprocess` + `threading` (stdlib): one-shot burst invocation on background cadence — eliminates pipe-buffer hazard class
- `re` + `shutil.which` (stdlib): fping output parser + binary availability gate — zero new runtime deps
- `statistics.median/mean` (stdlib, already used): aggregation — no scipy/numpy

### Expected Features

**Must have (table stakes):**
- `RttBackend` Protocol + `RttSample` dataclass — backend-agnostic seam; icmplib refactored behind it with zero-diff default behavior
- `IcmplibBackend` wrapping existing `RTTMeasurement` verbatim — proves the seam is real, establishes the regression baseline
- `FpingBackend`: one-shot `subprocess.run` per burst, `-S <source_ip>` binding per WAN, multi-reflector single-process fanout
- Robust fping output parser from captured real samples (reply, timeout/loss, partial line, banner, stall, process-death)
- Loss tokens (`-`, `timed out`) map to `None`, never `0ms` — correctness invariant (controller raises rate on `0`, which is catastrophic during actual loss)
- Automatic fallback when fping binary absent: `shutil.which` gate, icmplib fallback, loud WARN-once + fallback counter
- `RttSample.backend` / `source_ip` / `loss_pct` metadata wired into existing `_rtt_source_counts` — A/B precondition, not polish
- Config key `measurement.backend: icmplib|fping` per WAN/consumer; validator allow-list + type check; default-to-icmplib on absence
- Unit tests from captured fping output including induced total-loss and partial-line fixtures
- Cycle-budget + CPU benchmark idle and under load vs documented p99≈6.9ms baseline — hard gate before live A/B
- Pre-registered A/B on the verified live RTT producer + rollback anchor

**Should have (differentiators):**
- Per-reflector loss visibility from fping feeding reflector-quality scoring (cheap once parser exists)
- `measurement.backend` additive field in `/health` payload — attributable A/B evidence without log spelunking
- Concurrent/interleaved A/B comparison within same window to mitigate diurnal confounding

**Defer / anti-features:**
- IRTT folded behind `IrttBackend` (protocol shaped to absorb it; migration deferred out of scope)
- Native autorate stood up for fping validation (dormant; inherits seam passively)
- `fping -J` JSON output (alpha schema; absent from 5.1 deploy baseline)
- Conditional production default flip to fping (gated on A/B clear win — may not happen in v1.53)
- Per-cycle `subprocess.run` per reflector inside the 50ms loop (would blow cycle budget)
- Hard fping dependency / flipping default without evidence / re-adding IRTT as a new backend

### Architecture Approach

The existing `BackgroundRTTThread` and `IRTTThread` already share the same shape: a `*Measurement` prober class plus a `*Thread` daemon-loop-and-GIL-swap class. The seam writes itself from this pattern. `RttBackendThread` is the generic form of `BackgroundRTTThread`; `IcmplibBackend` is the existing prober logic extracted; `FpingBackend` adds a prober running one-shot `subprocess.run` bursts on the same cadence. `build_rtt_backend()` factory centralizes the two scattered `RTTMeasurement(...)` construction sites in `autorate_continuous.py` and `steering/daemon.py`. `RttSample` is a strict superset of `RTTSnapshot` (adds `backend`, `source_ip`, `loss_pct`; keeps all existing fields) so `WANController.measure_rtt()` and the scorer are untouched.

**Major components:**
1. `src/wanctl/rtt_backend.py` (NEW) — `RttBackend` Protocol, `RttSample`, `RttBackendThread` generic loop, `IcmplibBackend`, `IrttBackend` adapter shell, `build_rtt_backend()` factory
2. `src/wanctl/fping_measurement.py` (NEW) — `FpingBackend`: one-shot subprocess bursts, text parser, loss/stall/death handling, mirrors `irtt_measurement.py` structure exactly
3. `src/wanctl/rtt_measurement.py` (MODIFIED) — `BackgroundRTTThread` generalized to `RttBackendThread`; aggregation extracted; `RTTSnapshot` aliased to `RttSample`
4. `src/wanctl/autorate_config.py` + `check_config_validators.py` (MODIFIED) — `measurement_backend.*` loading and allow-list
5. `src/wanctl/health_check.py` (MODIFIED, additive only) — `measurement.backend`/`source_ip` fields; existing contract byte-preserved
6. `src/wanctl/steering/daemon.py` (MODIFIED only if provenance decision routes A/B through steering's own pinger)

### Critical Pitfalls

1. **RTT-provenance mismatch (A/B on a dead code path)** — `SteeringDaemon.rtt_measurement` is constructed but never called in production; live steering RTT comes from the state bridge. Avoid: read-only provenance mapping before any A/B scoping; verify `rtt_source` in `/health` reflects the intended backend during the A/B window.
2. **Pipe-buffer STALL (the observed systemd failure)** — fping block-buffers stdout under systemd's pipe (not a TTY). Root cause: pre-v4.3 behavior, changelog #179. Avoid: use one-shot `subprocess.run` per burst (the IRTT pattern). Never use long-lived `fping -l` for v1.53.
3. **Source-IP binding breakage (`-S` mismatch = silently wrong WAN)** — missing or wrong `-S` lets fping egress the default WAN; pings succeed but measure the wrong link; the A/B "win" may be comparing icmplib-on-ATT vs fping-on-Spectrum. Avoid: seam contract carries `source_ip` per WAN; `-S <source_ip>` emitted unconditionally; binding-assertion test before live A/B.
4. **Loss parsed as 0ms (inverse-safe failure)** — `timed out` / `-` tokens misread as RTT values causes the controller to raise shaping rate into congestion. Avoid: parser built from captured real output including total-loss fixture; loss maps to `per_host_results[host] = None`; `LC_ALL=C` in subprocess env; never reuse existing `parse_ping_output()` regex.
5. **per-target stats go to STDERR, not stdout** — `-C`/`-c`/`-s` summary stats are written to stderr (fping issue #9). A parser reading only stdout returns empty. Capture/parse the correct stream.
6. **Cycle-budget regression** — fork/exec is ms-scale and jittery. Keep fping off the synchronous loop; benchmark idle+load under a real systemd unit vs `avg≈2.85ms / p99≈6.9ms` with a pre-registered no-regression gate.
7. **Silent fallback masking failure** — fallback to icmplib must be loud (WARN-once + counter + health attribution), never silent.
8. **A/B methodology traps** — confounded comparison, no rollback anchor, flipping default on weak/single-window evidence. Pre-register thresholds; rehearse rollback; "keep icmplib" is a valid close.
9. **SAFE discipline sprawl** — first controller-path-touching milestone in 10; "we're touching it anyway" tempts diff spread into state machine/thresholds/EWMA. Avoid: narrow (not abolish) the SAFE allowlist to RTT-measurement seam files; fail-closed source-diff verifier at every phase boundary; prove icmplib-default path byte-identical to pre-refactor.

---

## Implications for Roadmap

All four researchers converged on the same dependency-aware build order (9 phases, last conditional).

### Phase 1: RTT-Provenance Verification (READ-ONLY ENTRY GATE)
**Rationale:** `SteeringDaemon.rtt_measurement` is never called in production; live steering RTT comes from the state bridge / autorate `/health`. The A/B target may not exist on the live path. Must be resolved before any code changes. Three possible A/B interpretations to select from:
- (A) Steering re-acquires its own pinger (revive dormant `rtt_measurement` path as A/B source) — cleanest test of the seam; touches the LIVE consumer
- (B) A/B at the autorate/bridge producer — validates parser capability, but may not exercise the wanctl `RttBackend` seam at all
- (C) A/B on native autorate path, observe steering's reaction — seam is real; but prod steering is dormant on that path

**Delivers:** Documented provenance map; one interpretation selected and committed; scope claim boundaries defined.
**Avoids:** Pitfall 1 (A/B-ing a dead path). Live inspection, not code.

### Phase 2: Seam Refactor + IcmplibBackend (Behavior-Identical)
**Rationale:** Seam must land in isolation before any backend is introduced so any later regression is unambiguously attributable to the backend. Riskiest controller-path step; must be independently revertable. SAFE narrowed allowlist defined here.
**Delivers:** `rtt_backend.py` (Protocol, `RttSample`, `RttBackendThread`, `IcmplibBackend`); `BackgroundRTTThread` generalized; narrowed SAFE allowlist + verifier running; hot-path slice tests green and byte-identical to pre-refactor.
**Gate:** Hot-path slice green; source-diff verifier passes narrowed allowlist; icmplib-default output byte-identical.

### Phase 3: Config + Validator
**Rationale:** Depends on the seam; must exist before factory wiring. Additive only; existing deployments resolve to icmplib on absence.
**Delivers:** `measurement.backend` keys; validator allow-list; WARN on unknown types; WARN (not fail) on missing fping at validate time; existing configs pass unchanged.

### Phase 4: FpingBackend Offline
**Rationale:** Proceeds after Phase 2. Uses captured real fping output fixtures — no live network. One-shot `subprocess.run` design locked here (not `fping -l`), per Pitfalls root-cause.
**Delivers:** `fping_measurement.py`: one-shot subprocess per burst, `-S` per-WAN binding, multi-reflector single-process, text parser (reply + timeout), loss-to-None, stall/death handling mirroring IRTT; `LC_ALL=C`; `shutil.which` gate.
**Gate:** `tests/test_fping_measurement.py` with reply/total-loss/partial-loss/partial-line/process-death/stall fixtures passing; no live fping needed.
**Research flag:** Capture fping 5.1 output samples (`fping -C 3 -S <ip> -t 500 -p 200 host1 host2 host3`) before writing the parser.

### Phase 5: Factory + Fallback Wiring
**Delivers:** `build_rtt_backend()` with fallback-when-unavailable; loud WARN-once + fallback counter + health attribution; `autorate_continuous.py` and (if Phase 1 routes it here) `steering/daemon.py` using factory.
**Gate:** `tests/test_rtt_backend.py` proves fping→icmplib fallback when binary absent; `/health` `rtt_source` reflects which backend produced samples.

### Phase 6: Cycle-Budget Benchmark Gate
**Rationale:** Hard gate before live A/B. Must run under actual systemd unit (TTY-vs-pipe is the STALL fingerprint). A cycle-budget regression is a reject even if RTT quality is better.
**Delivers:** Documented benchmark: `cycle_total` avg/p99 idle and under load vs baseline; CPU% delta; zombie/fd/Tasks count over soak under real systemd unit.
**Gate:** fping p99 ≤ icmplib p99 + pre-registered threshold (committed before running); zero zombies; flat fd count; no STALL under real systemd unit.

### Phase 7: Health-Payload Metadata (Additive)
**Rationale:** `measurement.backend`/`source_ip` must exist in `/health` before the A/B — sample attribution is an A/B precondition. Additive only; `raw_rtt_ms`/`available`/`staleness_sec` contract byte-preserved.

### Phase 8: Live A/B on Verified RTT Producer + Rollback Anchor
**Rationale:** All prior phases gate this one. Method determined by Phase 1's provenance decision. Pre-registered thresholds and rollback anchor committed before any live config flip. "Keep icmplib" is a valid and clean outcome.
**Delivers:** Pre-registered threshold doc (RTT agreement within tolerance, cycle-budget non-regression, loss-detection non-regression, min intended-backend cycle fraction, zero daemon restarts, steering decision stability); Snapshot-A rollback anchor; A/B executed on one WAN with other as control; evidence captured; verdict computed.

### Phase 9: Conditional Default Flip (or Document and Stay)
**Rationale:** Conditional on Phase 8 verdict. Negative result is a valid close (v1.46/v1.47 precedent). The flip is an operator decision, not automated.

### Phase Ordering Rationale
- Phase 1 gates A/B scope — no code until provenance is answered
- Phase 2 (seam) before Phase 4 (fping backend) — regression attributability
- Phase 3 (config) before Phase 5 (factory) — key validation
- Phases 3 and 4 can overlap after Phase 2 — independent streams
- Phase 6 (cycle-budget gate) before Phase 8 (live A/B)
- Phase 7 (health metadata) before Phase 8 (attribution precondition)
- Phase 9 conditional on Phase 8 verdict

This order avoids the three most expensive failure modes: (a) completing the build and discovering the A/B path is dead, (b) conflating seam regression with backend regression, (c) discovering a cycle-budget regression mid-live-A/B.

### Research Flags
- **Phase 1:** Live inspection of deployed state bridge and `steering/daemon.py` call graph — outputs a design decision, not code.
- **Phase 4:** Captured fping 5.1 output samples are load-bearing — plan a capture task before parser implementation.
- **Phase 8:** A/B methodology pre-registration requires judgment on window length, concurrent vs sequential, minimum cycle fraction threshold.

Standard patterns (skip extra research): Phase 2 (extract behind Protocol; IRTT is the template), Phase 3 (SAFE-06 validator pattern in tree), Phase 5 (`shutil.which` + `is_available()` from IRTT), Phase 6 (`OperationProfiler`/`PerfTimer` already wired), Phase 7 (additive `/health` field; contract in `health_check.py`).

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | fping flags verified against upstream `doc/fping.pod` and `src/output.c`; Debian/Ubuntu 5.1 confirmed; privilege model confirmed against live `steering.service` unit |
| Features | HIGH | Integration points verified against live source tree; stderr vs stdout confirmed via fping issue #9; A/B evidence design from wanctl's own prior milestone precedents |
| Architecture | HIGH | Source reads of all six relevant files; `SteeringDaemon.rtt_measurement` never-called confirmed by grep; `BackgroundRTTThread`/`IRTTThread` shared shape confirmed |
| Pitfalls | HIGH | STALL root-cause traced to fping changelog v4.3 #179; production fping+source-binding confirmed live in `configs/cake-autorate/config.spectrum.sh`; all pitfalls grounded in in-repo code |

**Overall confidence:** HIGH

### Gaps to Address
- **RTT-provenance ambiguity:** The state bridge is a generated deployment artifact, not in the source tree. Live inspection required in Phase 1 before A/B scope is locked.
- **One-shot vs long-lived design decision:** STACK researcher preferred `fping -l`; Pitfalls researcher (with root-cause evidence) recommends one-shot. This synthesis recommends **one-shot decisively**. Record as an explicit design decision in Phase 4.
- **A/B comparison methodology:** Concurrent vs sequential depends on Phase 1's provenance decision. Pre-register before Phase 8.
- **fping source-bind egress proof:** Operator verification that `fping -S <ip>` egresses the intended WAN under the host's current `ip rule` setup (`ip route get <reflector> from <source_ip>`); needed before trusting A/B numbers.

---

## Sources

### Primary (HIGH confidence)
- Live source: `rtt_measurement.py`, `steering/daemon.py`, `irtt_measurement.py`, `irtt_thread.py`, `wan_controller.py`, `autorate_config.py`, `check_config_validators.py`, `health_check.py`
- Live production config: `configs/cake-autorate/config.spectrum.sh` (fping+source-binding in prod), `configs/att.yaml`, `configs/spectrum.yaml`, `configs/steering.yaml`
- `deploy/systemd/steering.service` — `AmbientCapabilities=CAP_NET_RAW`
- fping upstream `doc/fping.pod` (flag semantics), `src/output.c` (exact per-packet format strings), `CHANGELOG.md` (v4.3 line-buffering #179, v5.0 per-lost-packet #175), issue #9 (stderr vs stdout)
- Debian package tracker — fping 5.1-1
- `.planning/PROJECT.md` — v1.53 milestone definition, SAFE streak, cycle baseline, evidence-milestone precedents

### Secondary (MEDIUM confidence)
- fping.org / Ubuntu manpages — loop/count output behavior
- v1.44/v1.46/v1.47/v1.49 evidence-milestone precedent (matched windows, BGP-drift contamination, negative-result-is-valid-close)
- Unix stdout block-buffering under pipes vs TTY
- cake-autorate upstream README/CHANGELOG — fping pinger architecture in shell context
