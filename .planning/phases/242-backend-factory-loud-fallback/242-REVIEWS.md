---
phase: 242
reviewers: [codex]
reviewed_at: 2026-06-16T02:22:33Z
plans_reviewed: [242-01-PLAN.md, 242-02-PLAN.md, 242-03-PLAN.md, 242-04-PLAN.md]
cycle: 2
prior_cycle_high: 1
current_cycle_high: 1
---

# Cross-AI Plan Review — Phase 242 (Cycle 2 / re-review of revised plans)

This is the second review cycle. The plans below are the REPLANNED versions authored to
close the prior cycle's load-bearing HIGH (raw `FpingThread` → `AttributeError` in
`measure_rtt()` via missing `get_cycle_status()`) plus five MEDIUM findings. Codex was
asked to confirm closure of each prior finding and to surface any newly-introduced gap.

## Prior-Finding Closure (Cycle 1 → Cycle 2)

| Cycle-1 finding | Status | Evidence |
|---|---|---|
| **HIGH** — Raw `FpingThread` breaks `measure_rtt()` (`get_cycle_status()` absent) | **FULLY RESOLVED** | Plans 01/02/03 introduce `RttBackendHandle` + deferred `make_thread()` + an in-module fping adapter (`get_cycle_status()->None`, `get_latest()->RttSample.to_snapshot()`); `test_thread_protocol_contract` + `test_fping_selected_measure_rtt_no_attributeerror` pin it. A raw `FpingThread` is never assigned to `_rtt_thread`. |
| **MEDIUM** — Per-WAN vs process-global fallback state | **FULLY RESOLVED** | WARN-once keyed by `wan_key`; `fallback_count` per-handle; `/health` reads `self._rtt_backend_status` (per-controller), not a module global. Two-controller independence test required. |
| **MEDIUM** — fping timeout >= cadence: validator WARN vs `FpingThread` `ValueError` startup crash | **FULLY RESOLVED** | Plan 02 decides loud fallback to icmplib on `ValueError`; `test_fping_timeout_ge_cadence_falls_back` proves no propagated crash. |
| **MEDIUM** — Steering `source_ip` silently `None` defeats D-01a | **FULLY RESOLVED (for source IP)** | Plan 03 reads primary-WAN `ping_source_ip`, WARNs on missing/`None`, with a non-`None` plumbing test. (Backend source-of-truth ambiguity remains as a new MEDIUM, see below.) |
| **MEDIUM** — Plan 04 `changed_paths` expectation wrong vs v1.52 anchor | **FULLY RESOLVED** | Plan 04 now requires `changed_paths` ⊆ full v1.53 allowlist with the five 242 files present, not "only five files." |

All five Cycle-1 findings (including the load-bearing HIGH) are closed in the revised plans.
**However, the revision introduces one new load-bearing HIGH** of the same failure class.

## Codex Review

**Summary**

The replans materially improve the original design: the raw `FpingThread`/`measure_rtt()`
`AttributeError` failure is now directly addressed with a handle, deferred `make_thread()`,
an fping adapter, and regression tests. The prior per-WAN fallback, timeout-vs-cadence,
source-IP loudness, and changed-path expectation findings are also closed on paper. I would
not execute yet, though: the revised plans introduce one new load-bearing gap around
`WANController.rtt_measurement`. In live code it is still used for
`ping_hosts_with_results()`, `ping_host()`, and reflector probing
(`ReflectorScorer.maybe_probe()`), not only for `BackgroundRTTThread` construction. If Plan
03 binds `handle.backend` as `rtt_measurement` when fping is active, the live controller can
still `AttributeError`, just somewhere else.

### 242-01-PLAN.md

**Strengths**
- Explicitly tests the adapter protocol: `get_cycle_status()` and RTTSnapshot-shaped `get_latest()`.
- Adds the live `measure_rtt()` regression that would have caught the prior HIGH.
- Converts timeout-vs-cadence into an executable decision.
- Keeps `/health` preservation subset-based rather than full-dict brittle.
- Adds a negative SAFE-17 self-test — the right answer to the prior "grep-only" concern.

**Concerns**
- **HIGH:** The test contract does not assert what object remains in `WANController.rtt_measurement`. Live code calls `self.rtt_measurement.ping_hosts_with_results()` (blocking fallback), `ping_host()` (gateway checks), and passes it to `ReflectorScorer.maybe_probe()`; `FpingMeasurement` lacks those methods. `wan_controller.py:1269`, `:1474`, `:3127`.
- **MEDIUM:** The verifier `--self-test` can be short-circuited by the dirty-tree gate. If the synthetic out-of-allowlist edit is uncommitted in the throwaway worktree, the script proves "dirty tree fails," not "allowlist fails." Commit the synthetic edit inside a detached worktree first.
- **MEDIUM:** `test_fping_selected_builds_fping` monkeypatches the factory module's `shutil.which`, but `FpingMeasurement.__init__` also calls its own `shutil.which`. The "no WARN" assertion can become environment-dependent unless both are patched or the factory owns binary-path injection.
- **LOW:** `byte_preserved` is acceptable if it remains clearly subset/value preservation, not literal JSON bytes.

**Risk Assessment:** MEDIUM-HIGH — scaffolding is mostly strong but can still green-light an implementation that breaks live fping mode outside `measure_rtt()`.

### 242-02-PLAN.md

**Strengths**
- Correctly avoids building runtime threads before `hosts_fn`/pool/shutdown event exist.
- Keeps the adapter in the new factory module instead of modifying frozen Phase 241 files.
- Makes fallback loud and per-WAN; catches `FpingThread` timeout/cadence `ValueError` and degrades.

**Concerns**
- **HIGH:** The factory contract lacks a separate legacy `RTTMeasurement` for `WANController.rtt_measurement`. If Plan 03 passes `handle.backend` and the active backend is fping, controller helper paths can still fail with missing `ping_host()` / `ping_hosts_with_results()`.
- **MEDIUM:** Timeout fallback flips `fell_back`/`backend_active` but does not explicitly say to replace `handle.backend` with the icmplib `RTTMeasurement`. Leaving `backend` as `FpingMeasurement` while `backend_active == "icmplib"` is inconsistent.
- **MEDIUM:** Fping scorer semantics are not pinned. `FpingMeasurement` can feed a scorer via loss threshold, while `measure_rtt()` also records snapshot results — risk of lost loss-aware scoring or duplicated scoring depending on whether a scorer is passed.
- **MEDIUM:** Double `shutil.which("fping")` probing creates test/observability ambiguity unless handled deliberately.
- **LOW:** Invalid direct factory input should raise, not silently default, even if validators normally catch it.

**Risk Assessment:** HIGH until the legacy `RTTMeasurement` dependency is explicitly handled.

### 242-03-PLAN.md

**Strengths**
- Optional trailing constructor params avoid broad call-site churn.
- `start_background_rtt()` uses `make_thread()` while leaving `measure_rtt()` protected.
- `/health` signal is per-controller/per-WAN, not module-global.
- Steering source IP is intended to be non-`None` and loud on failure; preserves steering's current autorate-`/health` consumption.

**Concerns**
- **HIGH:** `_create_wan_components()` currently returns `(router, rtt_measurement)` and `ContinuousAutoRate` passes that into `WANController`. The plan says it "stops constructing `RTTMeasurement` directly" but does not clearly preserve a legacy `RTTMeasurement` for the controller helper methods (`ping_hosts_with_results`/`ping_host`/`maybe_probe`).
- **MEDIUM:** Steering backend source-of-truth is contradictory. The text says steering resolves `measurement.backend` from the primary WAN autorate config, but `build_rtt_backend(config, ...)` resolves from `config.data` — passing `SteeringConfig` would use steering.yaml, not the primary WAN config.
- **MEDIUM:** Plan metadata `files_modified` omits the test files, but the action says to add tests in `tests/test_wan_controller.py` / `tests/test_health_check.py`. Matters for reproducible execution and the SAFE-17 evidence diff.
- **MEDIUM:** Source-IP loading duplicates the raw-YAML pattern from `_derive_primary_health_url()`. A helper returning `(primary_cfg, warnings)` would reduce drift and ease testing the loud path.
- **MEDIUM:** Fping scorer/loss semantics still unspecified when the fping adapter is live.

**Risk Assessment:** HIGH — this is the live wiring plan, and the remaining ambiguity can still produce runtime `AttributeError`s when fping is selected.

### 242-04-PLAN.md

**Strengths**
- Corrects `changed_paths` to full-allowlist-subset semantics.
- Requires committed source before evidence generation.
- Asserts explicit `phase241_frozen_no_new_diff` rather than inferring from pass/fail.
- Requires named full-suite failure classification, not a bulk "legacy" waiver.
- Keeps protected-body and hot-path gates.

**Concerns**
- **MEDIUM:** The verifier dirty gate checks `src/wanctl`, but Plan 04 also depends on committed tests and scripts. Acceptance should require `git status --porcelain` clean for `scripts/`, `tests/`, and the relevant `.planning/` files before evidence.
- **MEDIUM:** Reproducing failures on old anchors should use a temporary `git worktree add --detach`; checkout/stash in the main worktree can invalidate the "evidence immediate next commit" discipline.
- **LOW:** The "HEAD^ == evidence.head_commit" convention should account for whether summaries are committed with evidence or separately.

**Risk Assessment:** MEDIUM — gate concept is solid; residual issues are execution hygiene, not design-breaking.

**Overall Risk:** HIGH until the `WANController.rtt_measurement` legacy-method dependency is
explicitly resolved. After that, drops to MEDIUM (controller-path wiring + evidence
discipline, with fping scorer semantics still needing a clear decision before live A/B).

---

## Consensus Summary

Single reviewer (Codex) this cycle; no cross-reviewer consensus to compute. The orchestrator
independently verified the new HIGH finding against live source (see below).

### Agreed Strengths

- The Cycle-1 load-bearing HIGH (raw `FpingThread` in `measure_rtt()`) is now genuinely closed: handle + deferred `make_thread()` + fping adapter + a live `measure_rtt()`-no-`AttributeError` regression.
- Per-WAN fallback state, loud timeout-vs-cadence fallback, loud steering source_ip, subset `/health` byte-preservation, and the negative SAFE-17 self-test are all sound.
- Plan 04 evidence expectations (full-allowlist subset, explicit 241-close-guard field, per-failure classification) are corrected.

### Agreed Concerns (highest priority)

- **HIGH (NEW, verified) — Incomplete `rtt_measurement` substitution.** The revision fixed the
  *thread* contract but not the *measurement object* contract. `WANController` consumes
  `self.rtt_measurement` for more than thread construction:
  - `self.rtt_measurement.ping_hosts_with_results(...)` — `wan_controller.py:1269` (blocking fallback)
  - `self.rtt_measurement.ping_host(...)` — `wan_controller.py:1474` (gateway connectivity check)
  - `self._reflector_scorer.maybe_probe(now, self.rtt_measurement)` — `wan_controller.py:3127`

  `FpingMeasurement` implements only `probe()`; it has neither `ping_host` nor
  `ping_hosts_with_results`. Plan 03 says autorate "stops constructing `RTTMeasurement`
  directly" and constructs `WANController(..., rtt_thread_factory=handle,
  rtt_backend_status=handle)` but **never specifies what object fills the existing positional
  `rtt_measurement` slot.** If `handle.backend` (the `FpingMeasurement`) is bound there when
  fping is selected, the live autorate path `AttributeError`s in the blocking-fallback,
  gateway-check, and reflector-probe paths — the same failure class as the Cycle-1 HIGH, new
  call sites. Unit tests that assert only on `measure_rtt()` stay GREEN while live fping mode
  breaks. **Verified by orchestrator against live code.**

- **MEDIUM** — fping scorer/loss semantics unspecified for live fping mode (single scorer
  writer not decided; risk of lost `per_host_loss` threshold semantics or duplicated scoring).
- **MEDIUM** — steering backend source-of-truth ambiguity (`build_rtt_backend` reads
  `config.data`; passing `SteeringConfig` would read steering.yaml, not the primary WAN config).
- **MEDIUM** — Plan 03 `files_modified` omits the test files it directs the executor to add.
- **MEDIUM** — verifier `--self-test` and Plan 04 reproduction must commit synthetic/anchor
  edits in detached worktrees, and the dirty-tree precheck should cover `tests/`+`scripts/`.

### Divergent Views

None — single reviewer.

### Orchestrator Note (verification)

The new HIGH was independently confirmed against live source:
- `grep 'self\.rtt_measurement\.' src/wanctl/wan_controller.py` → `:1269 ping_hosts_with_results`, `:1474 ping_host`.
- `src/wanctl/wan_controller.py:3127` passes `self.rtt_measurement` into `ReflectorScorer.maybe_probe`.
- `FpingMeasurement` (`src/wanctl/fping_measurement.py`) defines only `probe()`; `RTTMeasurement` (`src/wanctl/rtt_measurement.py:174,287,325,361`) defines `ping_host`, `ping_hosts_with_results`, `probe`, `ping_hosts_concurrent`.
- `src/wanctl/autorate_continuous.py:152` returns `(router, rtt_measurement)` and `:167` constructs `WANController(config.wan_name, config, router, rtt_measurement, logger)`.

Recommended remediation (consistent with the SAFE-17 allowlist): have the factory expose a
legacy/controller `RTTMeasurement` on the handle (e.g. `RttBackendHandle.controller_measurement`)
and keep `WANController.rtt_measurement` bound to that icmplib object even when the *background
RTT thread* runs fping via the adapter — OR explicitly scope fping mode so those helper paths
are not exercised, with a test exercising `verify_local_connectivity()` / `maybe_probe()` under
a fping-selected config. Also keep the timeout-fallback handle coherent (replace `backend` with
the icmplib object, not just flip `backend_active`). Replanning Plans 02 and 03 to pin the
measurement-object contract before execution is warranted.
