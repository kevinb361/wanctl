# Feature Research

**Domain:** Pluggable RTT measurement-backend abstraction for an adaptive dual-WAN CAKE controller (wanctl v1.53); `fping` as first alternate behind a config seam, validated against the live steering consumer via A/B.
**Researched:** 2026-06-13
**Confidence:** HIGH on existing-code integration points and fping output semantics (verified against fping manpage + source-behavior issue); MEDIUM on A/B evidence design (synthesized from wanctl's own prior evidence-milestone precedent, not an external standard).

## Context Anchors (what already exists — do NOT rebuild)

- `RTTMeasurement` (icmplib, raw ICMP, `source_ip` bind via `icmplib.ping(source=...)`) and `BackgroundRTTThread` in `src/wanctl/rtt_measurement.py`. This is the seam to refactor behind, not replace.
- `RTTSnapshot` / `RTTCycleStatus` frozen dataclasses are the sample contract. `RTTSnapshot` carries `rtt_ms`, `per_host_results: dict[str, float|None]`, `active_hosts`, `successful_hosts`, `timestamp`, `measurement_ms`. **Metadata additions land here.**
- Steering daemon (`steering/daemon.py`) constructs `RTTMeasurement` directly in `_create_steering_components()` with `MEDIAN` aggregation; it already has `_init_rtt_source_observability()` tracking `_current_rtt_source` / `_rtt_source_counts`. **Steering is the live A/B consumer.**
- IRTT thread (`irtt_thread.py`) is the proven "background daemon thread + GIL-atomic frozen-dataclass swap + start/stop" pattern. **A new fping backend should mirror this lifecycle, not invent a new one. IRTT itself is OUT of scope as a backend.**
- Production runs cake-autorate on both WANs; native autorate (`autorate_continuous.py`) is dormant but inherits the seam via the shared path. It is NOT stood up for validation.

---

## Feature Landscape

### Table Stakes (Required for the milestone to be coherent)

| Feature | Why Expected | Complexity | Notes / Dependency on existing path |
|---------|--------------|------------|-------------------------------------|
| **Backend abstraction seam (Protocol/ABC)** with `icmplib` refactored behind it as default | A "pluggable backend" milestone is meaningless without the seam; default behavior must be byte-for-byte unchanged | MEDIUM | Define a minimal interface matching what `BackgroundRTTThread` already calls: `ping_host(host, count) -> float|None` and per-host fanout. Keep `RTTMeasurement` as the icmplib implementation; do not widen the interface beyond current call sites (`ping_host`, `ping_hosts_with_results`). |
| **Config-selectable backend per WAN/config** | Milestone goal explicitly requires per-WAN selection for both steering and autorate; A/B needs to flip one WAN without touching the other | LOW–MEDIUM | New key e.g. `measurement.backend: icmplib\|fping` (default `icmplib`). Steering reads it in `_create_steering_components()`; autorate reads it where it builds `RTTMeasurement`. Must validate via existing config-validator path (unknown-key WARN precedent from v1.41 SAFE-06). |
| **fping source-IP binding (`-S <ip>`)** | wanctl relies on source-IP policy routing to pin ATT vs Spectrum; a backend that can't bind source IP is unusable here | LOW | `-S` is the icmplib `source=` equivalent. Must be passed for every invocation; missing `-S` silently routes via default WAN and corrupts per-WAN RTT. This is a correctness invariant, not a nicety. |
| **fping multi-reflector fanout** | Existing path pings N reflectors and aggregates (median-of-3+, mean-of-2, single passthrough); fping must produce the same per-host structure | LOW | fping is natively multi-target: pass all reflectors in one invocation (`fping -C <n> -S <ip> host1 host2 host3`). One process replaces N icmplib calls — a structural difference from the current per-host ThreadPool fanout. Must still produce `per_host_results: dict[host, float|None]`. |
| **Robust fping output parsing** | fping output has well-known footguns; naive parsing silently loses samples or misreads loss | MEDIUM–HIGH | See "fping parsing contract" below. Must handle: stats-on-stderr, `-` loss tokens, partial/interleaved lines, multi-target line attribution, decimal RTT, summary lines. |
| **Loss / partial-line / stall / process-death handling** | A subprocess backend introduces failure modes icmplib never had (hang, SIGKILL, truncated pipe); the 50ms loop must never block on a wedged child | HIGH | Hard wall-clock timeout on the child, `kill` on overrun, treat dead/timed-out process as a zero-success cycle (not an exception). Mirror `BackgroundRTTThread`'s "stale-prefer-none: do NOT overwrite `_cached` on zero-success" semantics. |
| **Automatic fallback when fping is missing** | Milestone forbids a hard fping dependency; binary may be absent on a host or after redeploy | LOW–MEDIUM | Resolve `fping` on PATH (or configured abs path) at backend construction. If absent/non-executable → log once, fall back to icmplib, set sample-metadata flag indicating fallback. Must NOT crash the daemon or silently produce no RTT. |
| **Backend-identifying metadata in RTT samples** | A/B and observability require knowing which backend/source/reflector produced each sample; without it the comparison is unattributable | LOW–MEDIUM | Extend `RTTSnapshot` (additively) with e.g. `backend: str` ("icmplib"\|"fping"\|"fping->icmplib-fallback"); `successful_hosts` already attributes reflectors; `source_ip` should be recoverable per sample. Wire into steering's existing `_rtt_source_counts` / `_current_rtt_source` observability, not a parallel mechanism. |
| **Unit tests from captured real fping output** | Parser correctness can only be trusted against real-world stdout/stderr captures, including loss and partial lines | MEDIUM | Capture `-C` output (with `-S`, multi-target, induced loss) as fixtures; mirror the v1.44/v1.47 "golden NDJSON / captured-evidence → deterministic test" precedent. Do NOT hand-author idealized output. |
| **Cycle-budget + CPU benchmark (idle + load) proving no 50ms regression** | The hot-path invariant is sacred; a subprocess fork/exec per cycle is the obvious regression risk vs icmplib's in-process sockets | MEDIUM | Compare against documented baseline (`cycle_total.avg_ms≈2.85`, `p99≈6.4–6.9` from Phase 217/219). fping forks a process per cycle — measure fork/exec + parse cost under load, not just idle. Gate, not nicety. |

### Differentiators (Earn their keep, but optional)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Single-process multi-reflector measurement** | One `fping` invocation pings all reflectors with controlled inter-packet pacing (`-p`/`-i`), potentially lower scheduler jitter than N concurrent icmplib threads | MEDIUM | fping's actual structural advantage worth A/B-ing: kernel-side batched ICMP vs Python ThreadPool fanout. If the A/B shows tighter measurement timing or lower CPU, that's the win that justifies the flip. |
| **Per-reflector loss visibility from fping** | fping `-C` natively reports per-probe success/`-` loss per target, cleaner per-reflector loss attribution than counting icmplib `None`s | LOW | Feeds steering's reflector-quality scoring and the existing blackout-backoff logic. Cheap once the parser exists. |
| **Backend-tagged metrics / health observability** | Operators see at a glance which backend a WAN uses and per-backend sample success rate during the A/B | LOW–MEDIUM | Additive `/health` field + metric; reuse the steering `_rtt_source_counts` pattern. Keeps the A/B observable in production without log spelunking. Do NOT break existing health payload shape (contract per CLAUDE.md). |
| **Pre-registered, scripted A/B harness on the live steering consumer** | A defensible flip decision needs locked accept/reject thresholds + rollback anchor, captured before the run, exactly like v1.44/v1.46/v1.47 evidence milestones | MEDIUM | See "A/B evidence requirements" below. The differentiator is rigor: same-deployment A then B, locked thresholds, Snapshot-A rollback anchor. |

### Anti-Features (Tempting, but wrong here)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Hard `fping` dependency (require binary, fail if absent)** | "Simpler" — no fallback code path | Violates the explicit milestone constraint; a missing/old binary after redeploy takes down RTT measurement on a production control path | Soft-detect at construction, automatic icmplib fallback with metadata flag + log-once |
| **Flip production default to fping without/ahead of A/B evidence** | fping "feels" lighter or is a familiar tool | Directly contradicts the milestone ("`icmplib` stays default unless A/B proves `fping`"); breaks the 10-milestone evidence-first discipline; risks a hot-path regression with no proof | Keep `icmplib` default; flip ONLY on a clear, pre-registered A/B win; otherwise document recommendation and stay |
| **Re-adding / reusing IRTT as "just another backend"** | IRTT thread already exists; looks like free reuse | Explicitly OUT of scope; IRTT is a different (UDP / owned-server two-way) measurement with its own semantics and would muddy the icmplib-vs-fping comparison | Borrow only IRTT's *threading lifecycle pattern* (daemon thread + GIL-atomic swap + start/stop), not the IRTT measurement itself |
| **Per-cycle `subprocess.run` fork for every reflector** | Mirrors the current per-host fanout mentally | Fork/exec per host per 20Hz cycle is the regression that kills the cycle budget; defeats fping's batching advantage | One fping process per cycle covering all reflectors, on the existing `BackgroundRTTThread` cadence (not per-control-cycle) |
| **Parsing fping stdout only** | "stats are the output" | fping writes `-C`/`-c`/`-s` per-target stats to **stderr**, not stdout (confirmed: schweikert/fping issue #9). Parsing stdout only yields empty results | Capture and parse **stderr** for `-C` per-target lines; capture both streams defensively |
| **Shelling out through a shell string** | Convenient for passing flags | Shell injection / quoting risk with reflector hostnames; harder to kill cleanly | `subprocess` with an argv list, explicit timeout, direct process handle for kill-on-stall |
| **Changing aggregation/threshold semantics "while we're in there"** | Refactor temptation | First controller-path-touching milestone in 10 — scope is the backend seam only; algorithm changes need separate approval per Change Policy | Backend produces the same per-host floats the current path produces; aggregation (median-of-3+/mean-of-2/single) stays in existing consumer code unchanged |
| **Auto-promoting the winner without operator sign-off** | "Let the data decide automatically" | The flip is a production control-path change under a rollback anchor; an operator decision, not an automated one | A/B emits verdict + recommendation; operator approves the config flip; rollback anchor armed |

---

## fping Parsing Contract (load-bearing detail)

Verified against the fping(8) manpage (Debian testing) and behavior issue schweikert/fping#9.

- **Recommended invocation:** `fping -C <count> -S <source_ip> -t <timeout_ms> -p <period_ms> -q <reflector...>` — `-C` gives per-target per-probe RTTs in a machine-friendly format; `-q` suppresses per-probe chatter; multi-target in one process.
- **Output destination:** `-C`/`-c`/`-s` summary and per-target statistics go to **stderr**, NOT stdout (issue #9). Parser must read stderr. Capture stdout too (defensive), but expect the data on stderr.
- **`-C` line shape:** `<target> : <rtt> <rtt> <rtt> - <rtt>` — space-separated per-probe RTTs in ms; `-` token = lost probe. One line per target; target name is the parse key for per-host attribution.
- **Loss handling:** count `-` tokens vs total for per-reflector loss; a target with all `-` = unreachable that cycle (maps to `per_host_results[host] = None`).
- **Exit codes:** 0 = all reachable, 1 = some unreachable, 2 = bad address resolution, 3 = bad args, 4 = syscall failure. **Do not treat exit 1 as failure** — partial loss is normal; only 3/4 (and process death/timeout) are hard errors.
- **`-D`** adds a Unix timestamp prefix in count/loop modes — useful if per-sample timing provenance is wanted in metadata.
- **Stall/death:** child can hang (DNS, kernel). Enforce a wall-clock timeout > `count*period` with margin; kill on overrun; missing target line → `None` for that host. Never let a wedged child block the background thread (and thus the consumer reading `get_latest()`).
- **Partial/interleaved lines:** read to process exit (or timeout) before parsing; do not parse a half-written stderr buffer. Multi-target output may interleave under loss — attribute strictly by the `<target> :` prefix, not by line order.

---

## A/B Evidence Requirements (icmplib vs fping on the live steering consumer)

A defensible flip needs ALL of the following, locked **before** the run (precedent: v1.44 Phase 206 gates, v1.46 Snapshot-A canary, v1.47 pre-registered matrix):

1. **Same-deployment A-then-B on one WAN** (the live steering consumer), other WAN untouched as control. Steering is the target because autorate is dormant in production.
2. **Pre-registered accept/reject thresholds** — committed before data collection. Candidate metrics: per-sample measurement duration distribution (avg/p99 cycle-budget contribution), CPU cost idle vs load, RTT-value agreement between backends (the two should measure the *same* path within noise — divergence is a red flag, not a win), per-reflector success/loss rate, steering decision stability (no new flapping / transition-rate increase), zero daemon restarts/instability.
3. **Equivalence first, then advantage** — fping must first prove it measures the same RTT as icmplib (no systematic bias) before any efficiency advantage counts. A "faster but different number" backend is a reject.
4. **Cycle-budget non-regression gate** — fping must not push `cycle_total` p99 past the documented icmplib baseline (~6.4–6.9ms) under load. Hard gate.
5. **Rollback anchor** — Snapshot-A style config capture + armed revert to `backend: icmplib`, provable without mutation (SOAK-02 precedent).
6. **Negative result is a valid close** — "keep icmplib, document why" is a clean milestone outcome (v1.46/v1.47 precedent). The flip is conditional, not assumed.
7. **Backend metadata in samples is a precondition** — without per-sample `backend`/`source`/`reflector` attribution the comparison can't be computed. (This is why the metadata feature is table stakes, not a differentiator.)

---

## Feature Dependencies

```
Backend abstraction seam (icmplib refactored behind it)
    └──requires──> RTTSnapshot/RTTCycleStatus contract preserved (additive only)

Config-selectable backend per WAN
    └──requires──> Backend abstraction seam
    └──requires──> config-validator key handling (WARN-on-unknown precedent)

fping backend
    ├──requires──> Backend abstraction seam
    ├──requires──> source-IP binding (-S)        [correctness invariant]
    ├──requires──> robust stderr parser           [load-bearing]
    └──requires──> stall/death/timeout handling   [hot-path safety]

Automatic fallback (fping missing)
    └──requires──> fping backend + config selection

Backend metadata in samples
    └──enables──> A/B comparison (precondition)
    └──enhances──> steering RTT-source observability (reuse _rtt_source_counts)

A/B harness on live steering consumer
    ├──requires──> config-selectable backend
    ├──requires──> backend metadata in samples
    ├──requires──> cycle-budget benchmark baseline
    └──requires──> rollback anchor

Conditional production default flip
    └──requires──> A/B clear win + operator sign-off + rollback anchor

[fping backend] ──conflicts──> [hard fping dependency]   (fallback required)
[icmplib-vs-fping A/B] ──conflicts──> [re-adding IRTT as backend]  (muddies comparison; out of scope)
```

### Dependency Notes

- **Seam before backend:** the abstraction + icmplib-behind-it refactor must land and prove zero-diff behavior *before* fping is introduced, so any later regression is unambiguously fping's.
- **Metadata is an A/B precondition, not polish:** sample attribution must exist before the A/B runs, which is why it sits in table stakes.
- **Cycle-budget gate is independent of the A/B verdict:** even a "better" fping that blows the 50ms budget is a reject; benchmark before live A/B.
- **Fallback conflicts with hard-dependency:** mutually exclusive designs; the milestone mandates fallback.

---

## MVP Definition

### Launch With (the v1.53 milestone core)

- [ ] Backend abstraction seam with icmplib refactored behind it, behavior-identical (zero-diff default) — defines the milestone
- [ ] Config-selectable backend per WAN/config (default `icmplib`) — needed for A/B and the "selectable" goal
- [ ] fping backend: `-S` source binding, multi-reflector single-process fanout — the actual feature
- [ ] Robust fping stderr parser (loss `-` tokens, per-target attribution, partial lines) — fping is useless without it
- [ ] Stall/death/timeout handling (kill wedged child, zero-success = stale-prefer-none) — hot-path safety
- [ ] Automatic fallback when fping absent + metadata flag — mandated (no hard dependency)
- [ ] Backend-identifying sample metadata wired into steering observability — A/B precondition
- [ ] Unit tests from captured real fping output (incl. induced loss) — parser trust
- [ ] Cycle-budget + CPU benchmark (idle + load) vs documented baseline — gate
- [ ] Pre-registered A/B on live steering + rollback anchor — the milestone thesis

### Add After Validation (conditional, same milestone)

- [ ] Production default flip to fping — only if A/B clearly wins, under rollback anchor + operator sign-off
- [ ] Backend-tagged `/health` field + metric — if useful for operating the A/B (additive, contract-safe)
- [ ] Per-reflector loss visibility feeding reflector scoring — if the parser exposes it cheaply

### Future Consideration (explicitly deferred / out of scope)

- [ ] IRTT as a selectable backend — OUT of scope this milestone
- [ ] Standing up native autorate for fping validation — not validated; inherits the seam passively
- [ ] Additional backends (raw-socket variants, other tools) — only if a future need is proven

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Backend seam + icmplib behind it (zero-diff) | HIGH | MEDIUM | P1 |
| Config-selectable backend per WAN | HIGH | LOW | P1 |
| fping `-S` source binding | HIGH | LOW | P1 |
| fping multi-reflector fanout | HIGH | LOW | P1 |
| Robust fping stderr parser | HIGH | MEDIUM | P1 |
| Stall/death/timeout handling | HIGH | HIGH | P1 |
| Automatic fallback when fping missing | HIGH | LOW | P1 |
| Backend sample metadata | HIGH | LOW | P1 |
| Unit tests from captured output | HIGH | MEDIUM | P1 |
| Cycle-budget/CPU benchmark gate | HIGH | MEDIUM | P1 |
| Pre-registered A/B + rollback anchor | HIGH | MEDIUM | P1 |
| Conditional production default flip | MEDIUM | LOW | P2 (gated on A/B) |
| Backend-tagged health/metrics | MEDIUM | LOW | P2 |
| Per-reflector loss visibility | LOW | LOW | P3 |

**Priority key:** P1 = must have for the milestone; P2 = conditional/should-have; P3 = nice to have.

## Sources

- `src/wanctl/rtt_measurement.py`, `src/wanctl/steering/daemon.py`, `src/wanctl/irtt_thread.py` (read directly — integration points, contracts, threading pattern). HIGH.
- `.planning/PROJECT.md` v1.53 milestone section + Current State (scope, constraints, baseline cycle-budget numbers). HIGH.
- fping(8) manpage, Debian testing — option semantics (`-S`, `-C`, `-c`, `-l`, `-p`, `-i`, `-t`, `-q`, `-D`, `-e`, `-B`, `-r`, exit codes): https://manpages.debian.org/testing/fping/fping.8.en.html. HIGH.
- schweikert/fping issue #9 — confirms `-C`/`-c`/`-s` statistics go to **stderr** by default: https://github.com/schweikert/fping/issues/9. HIGH (load-bearing parsing fact).
- A/B evidence design synthesized from wanctl's own prior evidence-milestone precedent (v1.44 Phase 206 gates, v1.46 Snapshot-A canary, v1.47 pre-registered matrix) per PROJECT.md, not an external standard. MEDIUM.

---
*Feature research for: pluggable RTT measurement backend (fping first alternate) in wanctl*
*Researched: 2026-06-13*
