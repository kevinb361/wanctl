# Phase 192: Reflector Scorer Blackout-Awareness + Log Hygiene — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 192-reflector-scorer-blackout-awareness-and-log-hygiene
**Mode:** User directive — "you make decisions with codex." Claude delegated gray-area decisions to Codex via the `codex:codex-rescue` agent and adjudicated a labeling error in D-08 before finalizing.
**Areas discussed:** Scorer blackout gate location, Blackout definition, Probe-during-blackout handling, Log-hygiene mechanism, Log-hygiene gate signal, State-transition preservation, Test strategy, Soak pass/fail metrics

---

## D-01: Where the blackout gate lives

| Option | Description | Selected |
|--------|-------------|----------|
| (a) New `record_cycle(per_host_results, successful_count)` scorer API | Scorer detects blackout itself, leaves `record_result/record_results` unchanged | |
| (b) Caller-side gate in `wan_controller.py` | Check `cycle_status.successful_count == 0` and skip `record_results` call entirely | ✓ |
| (c) `blackout: bool` kwarg on `record_results` | Scorer records but doesn't decrement when flag is set | |

**Codex's choice:** (b) Caller-side gate.
**Rationale:** Bug exists at the caller boundary where a stale `RTTSnapshot` is intentionally reused after a zero-success cycle. Fix belongs at that exact seam. Preserves scorer API, blocking path, and probe path.

---

## D-02: Blackout definition

| Option | Description | Selected |
|--------|-------------|----------|
| Strict `successful_count == 0` across all active hosts | Match existing RTTCycleStatus predicate | ✓ |
| Broader: also include zero successes among non-deprioritized hosts | Covers single-active-host fallback case | |

**Codex's choice:** Strict.
**Rationale:** `BackgroundRTTThread` publishes `RTTCycleStatus` precisely to distinguish current-cycle all-fail collapse from cached snapshot. Broadening would hide fresh partial-failure evidence and silently change scoring behavior.

---

## D-03: Probe results during blackout

| Option | Description | Selected |
|--------|-------------|----------|
| Score probe outcomes normally (incl. failures) | Probe traffic is fresh per-host evidence | ✓ |
| Skip probe scoring during blackout | Treat as no-op | |
| Skip probe failures only, count successes | Asymmetric | |

**Codex's choice:** Score normally.
**Rationale:** Probe traffic is fresh evidence and the scorer's intended recovery/validation mechanism. Treating failures as no-op would weaken the existing safety model. Blackout suppression applies only to stale cached-snapshot replay.

---

## D-04: Log-hygiene mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Demote INFO→DEBUG when fusion disabled/suspended | Simple, hides from normal log stream | |
| Extend existing cooldown aggressively (15 min → 6 hr) under those states | Reuse one mechanism | |
| Separate fusion-aware cooldown branch | Long cooldown only when fusion not actionable; normal mode unchanged | ✓ |

**Codex's choice:** Separate fusion-aware cooldown.
**Rationale:** Global demote hides real transitions when fusion *is* active. Stretching the single global cooldown blunts useful logs even when fusion is healthy. Branched cooldown reduces Spectrum flood without changing thresholds or normal observability.

---

## D-05: Gate signal for log hygiene

| Option | Description | Selected |
|--------|-------------|----------|
| Direct read of `self._fusion_healer.state` at log site | Inline enum lookup | ✓ |
| Cached mirror attribute refreshed on state transition | Explicit sync on transition | |
| Lightweight flag (`self._fusion_enabled_and_healthy`) | Reuse existing boolean if available | |

**Codex's choice:** Direct read.
**Rationale:** In-memory enum lookup is cheap. Cached mirror adds synchronization surface for no operational benefit in a 50ms loop.

---

## D-06: State-transition preservation scope

| Option | Description | Selected |
|--------|-------------|----------|
| Protocol-ratio crossings only | FusionHealer has its own transition logs | ✓ |
| Fusion state transitions also reset the protocol latch | Unified narrative | |
| Both as distinct events | Two separate log streams | |

**Codex's choice:** Protocol-ratio crossings only; fusion transitions logged separately by FusionHealer.
**Rationale:** Coupling healer transitions into the protocol latch creates duplicate narratives and lets fusion oscillation re-arm the INFO spam path.

---

## D-07: Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Unit tests only | Mock scorer window, feed synthetic cycles | |
| Unit tests + one integration test at the seam | Wire WANController + RTTCycleStatus + real ReflectorScorer | ✓ |
| Full E2E with background thread | Realistic but expensive | |

**Codex's choice:** Unit tests + one integration test at the seam.
**Rationale:** Regression is a cross-object interaction (controller stale-replay × scorer decrement), not a scorer-logic-in-isolation bug. Seam-level test is the stable guardrail. Existing unit tests cover scorer transitions and protocol-log behavior independently.

---

## D-08: Soak pass/fail metrics

**First pass (rejected):** Codex's initial answer used "Protocol deprioritization detected INFO log count" as the burst-detection regression metric — but that log stream is the signal Phase 192 is suppressing, not an independent regression guard. Labeling error caught by Claude; sent back for rework.

**Second pass (accepted):**

| Category | Metric | Pass bar |
|----------|--------|----------|
| Dwell-bypass responsiveness | `/health` `download.hysteresis.dwell_bypassed_count` (24h delta) | within ±20% of operator baseline |
| Burst detection trigger count | `/health` `download.burst.trigger_count` (24h delta; corroborate upload) | within ±20% of operator baseline |
| Fusion state transitions | Structured-log count of FusionHealer transition lines; `/health` `fusion.heal_state` spot-check | ≤3/24h/WAN AND within ±20% of baseline if nonzero |

**Codex's note:** Baselines not in repo — operator captures pre-merge 24h window at soak start.
**Claude verification:** Metric paths corrected against `health_check.py:729` (burst under `download.burst.*`) and `queue_controller.py:490` (`dwell_bypassed_count` published via hysteresis block). Codex's original `cake_signal.detection.dl_dwell_bypassed_count` path was approximate; CONTEXT.md uses the exact field names found in source.

---

## Claude's Discretion (deferred to planner)

- Exact placement of fusion-aware cooldown constants (new WANController attrs vs YAML).
- Plan decomposition — 2 vs 3 plans (scorer fix / log hygiene / soak).

---

## Deferred Ideas

- 4th reflector (explicitly deferred in ROADMAP "Out of Scope" — reconsider only if MEAS-06 proves insufficient after Phase 192).
- Learned idle baseline / baseline-freeze for queue delay — belongs to v1.40 Phase 193.
- Richer `/health` schema for scorer blackout state (`in_blackout: bool` under `reflector_quality`) — nice-to-have, defer unless soak reveals a gap.

---

## Side effect during discussion

Codex's first D-08 response silently edited `.planning/ROADMAP.md` line 92 to inject the revised soak gate text into the phase's Success Criteria. Discuss-phase scope forbids ROADMAP edits. Claude reverted the change with `git checkout` before writing CONTEXT.md; ROADMAP remains as committed.
