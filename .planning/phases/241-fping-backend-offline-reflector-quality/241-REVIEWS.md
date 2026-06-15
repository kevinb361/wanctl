---
phase: 241
reviewers: [codex]
reviewed_at: 2026-06-15T20:49:12Z
plans_reviewed: [241-01-PLAN.md, 241-02-PLAN.md, 241-03-PLAN.md, 241-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 241

## Codex Review

## Overall Summary

The phase plan is mostly well-scoped for a production controller-path milestone: it keeps live wiring out of Phase 241, isolates new behavior in `fping_measurement.py`, and preserves SAFE-17 boundary discipline. I would not execute it unchanged. Two issues are hard blockers: all-loss `fping` results appear to return `None` before feeding reflector failures into `ReflectorScorer`, and Plan 04's expected `changed_paths` does not match the verifier's actual `v1.52` anchor semantics. There are also parser robustness risks around stdout/stderr, partial process death, and host-key matching.

## Plan 01: `fping_measurement.py`

### Summary

Good isolation strategy. Cloning the IRTT-style subprocess/thread shape into a new allowlisted module is the right conservative choice for SAFE-17, even if it creates some short-term duplication. Main risk is that the proposed `probe()` API cannot both return `None` on all-fail and still feed all-fail loss into scorer unless parsing and scorer-feed are separated.

### Strengths

- Keeps all implementation in one new allowlisted module.
- Uses `-C`, not `-c`, which is the right loss-safe format.
- Parses non-zero fping exits instead of treating loss as subprocess failure.
- Keeps partial-loss RTT usability decoupled from scorer penalty.
- Avoids touching `BackgroundRTTThread`, `WANController.measure_rtt`, and scorer math.
- Copying the aggregation rule is acceptable here because `rtt_measurement.py` is intentionally frozen.

### Concerns

- **HIGH:** All-fail loss is likely dropped. The plan says `probe()` only calls scorer when a non-`None` sample is produced, but `RttBackend.probe()` must return `None` when no host yields RTT. That means total-loss bursts will not penalize reflectors.
- **HIGH:** Parser only consumes `result.stdout`. Real `fping -C -q` behavior may place the useful lines on stderr depending on version/options. Since `capture_output=True` captures both, parse a combined stream or prove with captures before locking this in.
- **MEDIUM:** Process death is under-specified. A killed process can return negative `returncode` with partial valid-looking lines. Parsing all non-zero exits as normal loss risks accepting truncated process-death output.
- **MEDIUM:** `ReflectorScorer.record_results()` indexes `_windows[host]` directly; unknown parsed host strings will raise. Current scorer also has no locking, so future live injection from `FpingThread` could mutate scorer state concurrently with controller use.
- **MEDIUM:** `_parse_target_line` using exact `" : "` is brittle. Use whitespace-tolerant parsing and restrict parsed hosts to the requested host set.
- **MEDIUM:** `measurement_ms=0.0` loses useful timing. Existing `RTTMeasurement.probe()` records elapsed measurement time.
- **LOW:** Lock-key design says source IP plus sorted reflectors, but `FpingMeasurement.__init__` does not know probe hosts if `hosts_fn` is dynamic.

### Suggestions

- Add an internal parse result, e.g. `FpingParseResult(per_host_results, per_host_loss, successful_rtts, successful_hosts)`, and let `probe()` feed scorer from loss data even when it returns `None`.
- Parse `stdout + "\n" + stderr`, or explicitly test real captures proving stdout-only is correct.
- Treat only expected fping return codes as parseable; handle negative/signal return codes as process death.
- Initialize per-host maps for every requested reflector; ignore or log unknown parsed host keys.
- Add tests for all-fail scorer feed, negative returncode, stderr-only valid output, unknown host line, and exact 1/2/3 aggregation behavior.
- Use a callback/queue abstraction for scorer feed, or document that live scorer mutation must be made thread-safe in Phase 242.

### Risk Assessment

**MEDIUM-HIGH.** The module is offline and isolated, but parser/scorer semantics are load-bearing for later live wiring. The all-fail scorer gap is the biggest correctness issue.

## Plan 02: SAFE-17 Verifier + Validators

### Summary

The verifier plan is directionally solid: clone the known-good Phase 240 gate, update the allowlist, and keep dirty-tree/protected-body checks intact. Validator additions are appropriate, but they need to include unknown-key registry coverage.

### Strengths

- Keeps fail-closed behavior from the Phase 240 verifier.
- Updates both the shell regex and Python `allowed_paths` set.
- Adds negative verifier tests instead of relying on static inspection only.
- Keeps fping config validation additive and inert.

### Concerns

- **MEDIUM:** New `measurement.fping.*` keys must be added to `KNOWN_AUTORATE_PATHS`; otherwise `check_unknown_keys()` can warn on valid fping config.
- **MEDIUM:** Plan 01 reads `timeout_grace_sec`, but Plan 02 does not validate or register it. Either make it internal-only or add `measurement.fping.timeout_grace_sec`.
- **LOW:** Adding `reflector_scorer.py` to the allowlist is acceptable only if Plan 04 explicitly proves it remained unchanged.
- **LOW:** `timeout >= cadence` as WARN is fine for check-config, but runtime should fail fast or refuse construction.

### Suggestions

- Add registry entries for `measurement.fping`, `count`, `period_ms`, `cadence_sec`, `loss_fail_threshold`, and any exposed `timeout_grace_sec`.
- Add tests that `_run_autorate_validators()` with valid fping config produces no unknown-key warnings.
- Keep a Plan 04 assertion that `reflector_scorer.py` has zero phase-local diff.

### Risk Assessment

**LOW-MEDIUM.** Mostly tooling risk. Fixing known-path coverage should make this solid.

## Plan 03: Capture Fixtures

### Summary

The human-in-the-loop capture requirement is correct; real fping 5.1 fixtures should be the binding parser proof. The main weakness is that "byte-identical command" is asserted by grep/script convention rather than mechanically compared to `_build_command`.

### Strengths

- Correctly blocks on real production-host fping captures.
- Explicitly avoids routing, CAKE, shaping, and `tc` mutation in the helper.
- Replaces synthetic bootstraps with real fixtures before closure.
- Captures the right scenarios, including partial lines and process death.

### Concerns

- **MEDIUM:** Grepping for `fping -C 5 -p 200` is not enough to prove byte identity with `_build_command`.
- **MEDIUM:** Process-death fixtures need returncode behavior in tests, not just truncated text.
- **MEDIUM:** If real useful output lands on stderr, tests that pass fixture text as stdout can still miss production behavior.
- **LOW:** Partial-loss capture via "distant/lossy target" may be flaky; define what qualifies as acceptable partial loss.

### Suggestions

- Add `--print-command` to the capture script and compare it against a Python call to `FpingMeasurement._build_command()`.
- Store fixture metadata for fping version, command, stdout/stderr split, and returncode, or encode those in test fixtures.
- Re-point tests to simulate real `CompletedProcess(stdout=..., stderr=..., returncode=...)`.

### Risk Assessment

**MEDIUM.** The safety posture is good, but fixture fidelity needs stronger mechanical checks.

## Plan 04: Boundary Gate

### Summary

The gate is necessary, but its expected `changed_paths` assertion is wrong for the current verifier. The Phase 240 evidence already shows `changed_paths` against `v1.52` includes `rtt_backend.py`, `rtt_measurement.py`, `check_config_validators.py`, and `check_steering_validators.py`. A Phase 241 run anchored the same way should not expect only two files.

### Strengths

- Keeps SAFE-17 as a blocking gate.
- Requires clean `src/wanctl` before evidence is accepted.
- Uses the protected-body checker and Phase 239 seam anchor.
- Separates human verification from implementation waves.

### Concerns

- **HIGH:** Acceptance criterion `changed_paths exactly {fping_measurement.py, check_config_validators.py}` conflicts with the verifier's `v1.52` anchor. Expect inherited Phase 239/240 paths plus `fping_measurement.py`, or change the evidence field semantics.
- **MEDIUM:** `git diff --quiet HEAD -- src/wanctl/wan_controller.py ...` only proves the working tree matches HEAD. It does not prove those files were unchanged by Phase 241 if changes are already committed.
- **MEDIUM:** Need a phase-local baseline for "unchanged this phase," likely the Phase 240 close commit, separate from the `v1.52` SAFE-17 anchor.
- **LOW:** Ensure the JSON evidence `head_commit` equals current `git rev-parse HEAD` to avoid reading stale evidence.

### Suggestions

- Change Plan 04 expected verifier `changed_paths` to the inherited SAFE-17 set plus `src/wanctl/fping_measurement.py`.
- Add a separate phase-local diff check from the Phase 240 close anchor proving only `fping_measurement.py` and `check_config_validators.py` changed in Phase 241.
- Replace tautological `git diff --quiet HEAD -- file` checks with comparisons to the correct pre-Phase-241 commit.

### Risk Assessment

**MEDIUM.** The gate concept is strong, but the current acceptance criteria can fail for the wrong reason or prove less than intended.

## Final Recommendation

Approve the plan only after tightening Plan 01 all-fail/scorer behavior and fixing Plan 04's anchor expectations. D-07 cloning is the right call under SAFE-17; just document that Phase 242 must resolve scorer thread ownership before any live wiring.

---

## Consensus Summary

Only one external reviewer (Codex) was invoked for this cycle, so "consensus" reflects Codex's findings plus an orchestrator-side verification of the load-bearing claims against repo evidence.

### Agreed Strengths

- The OFFLINE-only scoping and single-new-allowlisted-module isolation (`fping_measurement.py`) is the right conservative posture for the first controller-path-touching milestone in 10.
- `-C` over `-c` (loss-safe, per-target tokens) and parsing non-zero fping exits as normal-loss are correct.
- The D-07 divergence (clone a new `FpingThread` rather than edit `BackgroundRTTThread`/`irtt_thread.py`) is endorsed as the right call under SAFE-17 — cloning keeps protected bodies byte-identical.
- The human-in-the-loop real-capture requirement (D-08) and the non-mutating capture helper are the correct way to make FPING-04 proof genuine.

### Agreed Concerns (highest priority)

1. **HIGH — Plan 01 all-fail scorer gap.** `probe()` returns `None` on all-fail (the seam's documented all-fail contract) but the scorer feed is gated to the non-`None` path, so total-loss bursts never penalize reflectors in scoring. The plan as written cannot both honor the `None` all-fail return AND feed all-fail loss into `ReflectorScorer` without separating parse from scorer-feed (e.g. an internal `FpingParseResult` that `probe()` feeds the scorer from before returning `None`).
2. **HIGH — Plan 01 stdout-only parsing.** Parser consumes `result.stdout` only; real `fping -C -q` may emit useful lines on stderr. `capture_output=True` captures both, so this should parse a combined stream or be proven stdout-only against the real Plan-03 captures before locking in.
3. **HIGH — Plan 04 `changed_paths` acceptance criterion is wrong for the v1.52 anchor.** VERIFIED against `.planning/phases/240-config-validator/evidence/safe17-boundary-240.json`: the v1.52-anchored verifier reports the *cumulative* v1.53 diff, which at Phase 240 was `{check_config_validators.py, check_steering_validators.py, rtt_backend.py, rtt_measurement.py}`. Plan 04's criterion `changed_paths exactly {fping_measurement.py, check_config_validators.py}` would therefore fail for the wrong reason — the real expected set is the inherited Phase 239/240 paths PLUS `fping_measurement.py`. Plan 04 needs either corrected expectations or a separate phase-local diff (from the Phase 240 close anchor) proving only `fping_measurement.py` + `check_config_validators.py` changed *this phase*.

   Secondary Plan 04 issue (MEDIUM): the `git diff --quiet HEAD -- <file>` byte-unchanged checks are tautological once edits are committed (working tree always matches HEAD); they prove nothing about what Phase 241 changed. Use a pre-Phase-241 baseline commit.

4. **MEDIUM cluster — parser/scorer robustness for later live wiring:** process-death negative/signal returncodes vs truncated-but-valid-looking lines; `ReflectorScorer.record_results` raising on unknown host keys (and the scorer having no locking, deferred to Phase 242); brittle exact-`" : "` split; lost `measurement_ms` timing.
5. **MEDIUM — Plan 02 unknown-key registry coverage.** New `measurement.fping.*` keys (and Plan 01's `timeout_grace_sec`) must be registered in `KNOWN_AUTORATE_PATHS` or `check_unknown_keys()` will warn on valid fping config.
6. **MEDIUM — Plan 03 byte-identity is grep-asserted, not mechanical.** Add `--print-command` to the capture helper and compare against `FpingMeasurement._build_command()`; carry stdout/stderr/returncode into fixtures/tests.

### Divergent Views

None — single reviewer this cycle. The orchestrator independently confirmed the Plan 04 HIGH against committed Phase 240 evidence (it is grounded, not speculative). The two Plan 01 HIGHs (all-fail scorer feed, stdout-only parsing) are design-contradiction / format-fidelity risks that should be resolved in planning before execution; both are addressable inside the `fping_measurement.py` allowlist and do not threaten SAFE-17.
