---
phase: 242
reviewers: [codex]
reviewed_at: 2026-06-16T07:05:00Z
plans_reviewed: [242-01-PLAN.md, 242-02-PLAN.md, 242-03-PLAN.md, 242-04-PLAN.md]
cycle: 4
prior_cycle_high: 1
current_cycle_high: 0
---

# Cross-AI Plan Review — Phase 242 (Cycle 4 / re-review of revised plans)

This is the fourth review cycle. The plans below are the REPLANNED versions authored to
close the Cycle-3 load-bearing HIGH (the fping-cadence wiring defect: `make_thread()` was
fed the controller background-RTT cadence ≈0.25s, which is `< fping timeout 3.0s`, forcing
`FpingThread.__init__` to raise `ValueError` and the loud timeout-vs-cadence fallback to fire
EVERY startup — leaving fping permanently dead in the live path). Codex was asked to (1)
confirm closure of the Cycle-3 HIGH, (2) confirm the two earlier load-bearing HIGHs stay
closed (Cycle-1 thread protocol, Cycle-2 measurement-object substitution), and (3) surface
any newly-introduced gap. The orchestrator independently re-verified the Cycle-3 closure
against live source.

## Prior-Finding Closure (Cycle 3 → Cycle 4)

| Prior finding | Status | Evidence |
|---|---|---|
| **HIGH (Cycle-3)** — fping wired to controller cadence (~0.25s) → `timeout(3.0s) >= cadence` → `ValueError` → loud fallback every startup → `backend_active` permanently `icmplib`; fping never runs live | **FULLY RESOLVED** | Plan 02 adds `RttBackendHandle.fping_cadence_sec`, RESOLVED from `measurement.fping.cadence_sec` (default `10.0`, Phase 241 D-06), and builds `FpingThread(... cadence_sec=self.fping_cadence_sec)` — NEVER the caller-supplied controller cadence (`242-02-PLAN.md:15-16,140-147,270,321-324`). Plan 03 keeps passing the controller cadence into `make_thread()` but the fping branch IGNORES it in favor of `handle.fping_cadence_sec` (`242-03-PLAN.md:22,243-244`). Plan 01 adds BOTH a unit cadence test (`test_fping_uses_resolved_cadence`) AND a real-path keeper (`test_start_background_rtt_keeps_fping_active`) asserting `backend_active == "fping"` after real thread construction (`242-01-PLAN.md:19-20,218-219,272-273`). Plan 04 adds a phase-local functional fping-active gate because SAFE-17 byte/path checks cannot catch this (`242-04-PLAN.md:16,85-93,156-164`). Orchestrator re-verified: validator recognizes `measurement.fping.cadence_sec` (`check_config_validators.py:258`); `FpingThread` guard is `timeout >= cadence → ValueError` (`fping_measurement.py:299-301`); default fping timeout `= count(5)*period_ms(200)/1000 + grace(2.0) = 3.0s` (`fping_measurement.py:51-57`); `10.0 > 3.0` holds the invariant with defaults. |
| **HIGH (Cycle-2)** — `WANController.rtt_measurement` bound to a `FpingMeasurement` → `AttributeError` on `ping_host`/`ping_hosts_with_results`/`maybe_probe` | **FULLY RESOLVED (stays closed)** | Plan 02 makes `controller_measurement` ALWAYS an icmplib `RTTMeasurement` (`242-02-PLAN.md:14,158-176`); Plan 03 binds `handle.controller_measurement`, never `handle.backend`, into the positional controller slot (`242-03-PLAN.md:20,253-257`). Matches live consumers at `wan_controller.py:1269/1474/3127`. |
| **HIGH (Cycle-1)** — raw `FpingThread` lacks the controller thread protocol (`get_cycle_status()`) | **FULLY RESOLVED (stays closed)** | Plan 02 requires an in-module adapter returning `get_cycle_status() -> None` and `get_latest() -> RttSample.to_snapshot()` (`242-02-PLAN.md:17,190-218`); Plan 03 assigns `_rtt_thread` from `handle.make_thread(...)`, never a raw `FpingThread` (`242-03-PLAN.md`). Source confirms raw `FpingThread` has no `get_cycle_status()` (`fping_measurement.py:316-322`). |

All three load-bearing HIGHs are closed in the revised plan design. This cycle surfaces NO
new HIGH. Residual concerns are MEDIUM/LOW execution-fidelity items.

## Codex Review

**Prior-Finding Closure**

| Prior HIGH | Status | Evidence |
|---|---:|---|
| Cycle-3 HIGH: fping wired to controller cadence, causing permanent fallback | **FULLY RESOLVED** | Plan 01 adds both unit and real-path keepers: `test_fping_uses_resolved_cadence` and `test_start_background_rtt_keeps_fping_active` (`242-01-PLAN.md:19-20`, `218-219`, `272-273`). Plan 02 requires `handle.fping_cadence_sec` from `measurement.fping.cadence_sec` and `FpingThread(... cadence_sec=self.fping_cadence_sec)` (`242-02-PLAN.md:15-16`, `127-147`, `270`, `321-324`). Plan 03 keeps passing controller cadence into `make_thread()` but requires fping to ignore it (`242-03-PLAN.md:22`, `142-153`, `243-244`, `313-314`). |
| Cycle-2 HIGH: `WANController.rtt_measurement` bound to `FpingMeasurement` | **FULLY RESOLVED** | Plan 02 makes `controller_measurement` always an icmplib `RTTMeasurement` (`242-02-PLAN.md:14`, `68-76`, `158-171`). Plan 03 binds `handle.controller_measurement`, never `handle.backend`, into the positional controller slot (`242-03-PLAN.md:20`, `253-257`, `310-315`). This matches source consumers at `src/wanctl/wan_controller.py:1269`, `1474`, `3127`, and `RTTMeasurement` methods at `src/wanctl/rtt_measurement.py:174`, `287`. |
| Cycle-1 HIGH: raw `FpingThread` lacks controller thread protocol | **FULLY RESOLVED** | Plan 01 pins the produced-thread protocol and `measure_rtt()` no-`AttributeError` path (`242-01-PLAN.md:16-17`, `221-222`, `275-276`). Plan 02 requires an adapter returning `get_cycle_status() -> None` and `get_latest() -> RttSample.to_snapshot()` (`242-02-PLAN.md:17`, `190-218`, `284-288`, `351-352`). Source confirms raw `FpingThread.get_latest()` returns `RttSample` and has no `get_cycle_status()` (`src/wanctl/fping_measurement.py:316-322`). |

**242-01-PLAN.md**

Summary: Strong TDD scaffold. It now pins the cadence bug with both a unit cadence test and a real `WANController.start_background_rtt()` path test.

Strengths:
- Directly covers all three historical HIGHs (`242-01-PLAN.md:16-21`).
- The real-path cadence keeper is the right regression shape; it would catch the old "manual unit test passes but live path falls back" defect (`242-01-PLAN.md:219`, `273`).
- Scorer non-use is now an executable assertion, not prose (`242-01-PLAN.md:220`, `274`).
- SAFE-17 self-test now commits the synthetic bad edit in a detached worktree (`242-01-PLAN.md:359-370`).

Concerns:
- **MEDIUM:** The tests pin fping cadence but not full fping config fidelity. `FpingMeasurement` consumes `source_ip`, `count`, `period_ms`, `loss_fail_threshold`, and `timeout_grace_sec` (`src/wanctl/fping_measurement.py:51-57`, `145-147`), and validators recognize those keys (`src/wanctl/check_config_validators.py:255-260`). Plan 01 only requires cadence assertions and a default-timeout misconfig test (`242-01-PLAN.md:218`, `223`, `233-249`). An executor could accidentally pass only `source_ip` plus defaults and still satisfy the current planned tests.
- **LOW:** The RED-state verifier is weak: `pytest ... | grep -qiE "error|failed|no module|cannot import|attributeerror"` can pass for the wrong failure mode (`242-01-PLAN.md:264-269`). The acceptance text is stricter, but the command itself is loose.
- **LOW:** The real-path fping test starts the real adapter path, but the plan does not explicitly say to patch `FpingMeasurement.probe()` or `subprocess.run`. `FpingThread.start()` launches a daemon thread that calls `probe()` (`src/wanctl/fping_measurement.py:324-352`). It will likely be harmless, but deterministic tests should avoid background subprocess attempts.

Suggestions:
- Add `test_fping_config_params_are_passed_without_scorer`: explicit non-default count/period/grace/loss/source values, assert the constructed `FpingMeasurement` reflects them and `_scorer is None`.
- Replace the RED verifier with explicit `py_compile`/test-name checks plus an expected import failure.

**242-02-PLAN.md**

Summary: The factory design now closes the cadence, thread-protocol, controller-measurement, and scorer non-use defects in the core construction layer.

Strengths:
- `controller_measurement` split is correct and explicit (`242-02-PLAN.md:14`, `158-176`).
- The fping cadence model is now explicit: resolve `measurement.fping.cadence_sec`, default `10.0`, and never use caller-supplied controller cadence for fping (`242-02-PLAN.md:140-147`, `264-270`, `347-348`).
- Timeout-vs-cadence misconfig fallback is coherent: replace `.backend` with icmplib on fallback (`242-02-PLAN.md:19`, `271`, `353`).
- `shutil.which` contradiction is resolved: factory probe authoritative, internal `FpingMeasurement` probe tolerated and patched in tests (`242-02-PLAN.md:224-232`, `303-306`, `355`).

Concerns:
- **MEDIUM:** Same fping sub-config gap: Plan 02 says to build `FpingMeasurement` with a config dict that omits `"scorer"` (`242-02-PLAN.md:268`, `309-310`), but it never explicitly says to copy `source_ip`, `count`, `period_ms`, `loss_fail_threshold`, and `timeout_grace_sec` from `config.data["measurement"]["fping"]`. This can break source binding, burst shape, loss semantics, and the timeout calculation used by `FpingThread` (`src/wanctl/fping_measurement.py:51-57`, `145-147`, `299-301`).
- **LOW:** Factory hardcodes autorate `AVERAGE/log_sample_stats=True` while steering historically uses `MEDIAN/log_sample_stats=False`; the plan flags this as Phase 245 work (`242-02-PLAN.md:178-188`). Acceptable for dead steering in 242, but it should not be forgotten before A/B.

Suggestions:
- Add a `_build_fping_config(config, source_ip)` helper that copies all supported fping keys except `"scorer"`.
- Add acceptance criteria asserting non-default fping keys affect `_count`, `_period_ms`, `_timeout`, `_loss_fail_threshold`, and `_source_ip`.

**242-03-PLAN.md**

Summary: Correct call-site wiring. Autorate binds `controller_measurement`; `start_background_rtt()` delegates thread construction to the handle; steering now has an explicit primary-WAN config source.

Strengths:
- The live autorate path uses `handle.controller_measurement`, never `handle.backend` (`242-03-PLAN.md:20`, `241`, `253-257`).
- The live fping startup path is pinned: pass controller cadence to `make_thread()`, rely on handle's fping cadence internally, and test `backend_active == "fping"` after real thread construction (`242-03-PLAN.md:243-244`, `265-271`, `292-299`, `313-314`).
- Steering Config-shape concern is mostly closed: primary WAN YAML is wrapped into a Config-like object with `.data["measurement"]` and `.timeout_ping` (`242-03-PLAN.md:203-211`, `273-280`, `317`).
- `/health` fallback attribution is per-controller, not module-global (`242-03-PLAN.md:337-359`, `366-369`).

Concerns:
- **MEDIUM:** Missing `source_ip` disposition is internally muddy. The plan says steering passes a "non-None per-WAN source_ip" (`242-03-PLAN.md:24`), but also says to WARN if missing/None (`242-03-PLAN.md:245`, `280-281`, `317`). That leaves unclear whether missing source IP is fail-closed, warn-and-pass-None, or warn-and-use a fallback. For D-01a, make this exact.
- **LOW:** Plan 03 says steering "preserves the MEDIAN strategy intent" or documents the decision (`242-03-PLAN.md:245`, `282-283`), while Plan 02 hardcodes AVERAGE (`242-02-PLAN.md:178-188`). Since steering consumption is dead, this is not load-bearing now, but Phase 245 needs a real strategy parameter or explicit decision.

Suggestions:
- Define source-IP failure behavior as one sentence in acceptance: either raise/fail factory construction, or WARN and pass `None` with an explicit test for that path.
- Add a Phase 245 carry-forward note: factory must accept aggregation/log-sample strategy before steering consumes its own pinger.

**242-04-PLAN.md**

Summary: Good hard gate, now complemented with the functional fping-active assertion SAFE-17 cannot provide.

Strengths:
- Correctly treats changed paths as a subset of the full v1.53 allowlist, not "only five files" (`242-04-PLAN.md:95-102`, `139-144`, `187`).
- Requires committed tests/scripts/src before evidence (`242-04-PLAN.md:13`, `104-110`, `184`).
- Adds the live-fping functional gate because byte/path checks cannot catch cadence-wiring failure (`242-04-PLAN.md:16`, `85-93`, `156-164`, `188`).
- Requires explicit 241 frozen-file no-drift field (`242-04-PLAN.md:72-78`, `146-149`, `186`).

Concerns:
- **MEDIUM:** SAFE-17 still has a blind spot after allowlisting all of `src/wanctl/wan_controller.py`. The protected-body helper only protects `WANController.measure_rtt` in that file (`scripts/phase239-protected-body-diff.py:21-32`), while Plan 04 claims no classification/state/threshold/fusion drift (`242-04-PLAN.md:45-48`). Plan 03 narrows intent, but the verifier itself will not reject unexpected edits elsewhere in `WANController`.
- **LOW:** The automated verify command runs the two factory cadence tests but omits the Plan 03 `tests/test_wan_controller.py` real-path equivalent, even though the action and acceptance require it (`242-04-PLAN.md:156-164`, `181`, `188`).

Suggestions:
- Add a Phase 242 qualname-drift check for `wan_controller.py`: allow only `WANController.__init__`, `WANController.start_background_rtt`, and the health producer method to change, plus any explicitly named helper.
- Include the exact Plan 03 real-path test node in the Plan 04 verify command.

**Overall Risk Assessment: MEDIUM**

The three load-bearing HIGH findings are closed in the revised plan design. The cadence defect specifically is now handled in the correct layer and backed by a real-path test.

Remaining risk is mainly execution fidelity: make sure the factory passes all fping sub-config keys, not only cadence, and tighten SAFE-17 around broad `wan_controller.py` drift. **Unresolved HIGH concerns: 0.**

---

## Consensus Summary

Single reviewer (Codex) this cycle; no cross-reviewer consensus to compute. The orchestrator
independently re-verified the Cycle-3 closure against live source.

### Agreed Strengths

- All three load-bearing HIGHs (Cycle-1 thread protocol, Cycle-2 measurement-object
  substitution, Cycle-3 fping-cadence wiring) are closed in the revised plan design.
- The Cycle-3 fix is in the correct layer: `build_rtt_backend` resolves the INDEPENDENT
  `measurement.fping.cadence_sec` (default `10.0`) once and stores it on
  `handle.fping_cadence_sec`; `make_thread`'s fping branch uses THAT, ignoring the
  controller's ~0.25s background cadence. Backed by both a unit cadence test and a real
  `start_background_rtt()` keeper asserting `backend_active == "fping"`.
- Plan 04 evidence discipline (full-allowlist subset, explicit 241 frozen-file no-drift
  field, per-failure classification, detached-worktree self-test, and the NEW phase-local
  functional fping-active gate that byte/path SAFE-17 cannot provide) is sound.

### Agreed Concerns (highest priority)

- **MEDIUM** — fping sub-config fidelity is not pinned. Plans 01/02 require cadence + scorer
  non-use, but do not explicitly require copying `source_ip`, `count`, `period_ms`,
  `loss_fail_threshold`, `timeout_grace_sec` from `config.data["measurement"]["fping"]` into
  the constructed `FpingMeasurement`. An executor could pass only `source_ip` + defaults and
  still pass the planned tests, silently breaking source binding / burst shape / loss
  semantics / the timeout calc that feeds the `FpingThread` invariant. Recommend a
  `_build_fping_config(config, source_ip)` helper that copies all supported keys except
  `"scorer"`, plus an acceptance test on non-default values.
- **MEDIUM** — steering `source_ip` disposition is internally muddy (non-None claimed vs
  WARN-if-None). Make D-01a's missing-source behavior exact (fail-closed vs warn-and-pass-None).
- **MEDIUM** — SAFE-17 blind spot: after allowlisting all of `wan_controller.py`, the
  protected-body helper only protects `WANController.measure_rtt`; unexpected edits elsewhere
  in `WANController` would not be rejected. Recommend a Phase-242 qualname-drift check
  restricting allowed `wan_controller.py` changes to `__init__`, `start_background_rtt`, and
  the named health producer.
- **LOW** — factory hardcodes autorate's `AVERAGE/log_sample_stats=True` while steering used
  `MEDIAN/log_sample_stats=False`; deferred to Phase 245 (steering dead in 242) but must not
  be forgotten before the A/B.
- **LOW** — Plan 04's automated verify command omits the Plan 03 real-path test node even
  though its action/acceptance require it; include the exact node.

### Divergent Views

None — single reviewer.

### Orchestrator Note (verification)

The Cycle-3 HIGH closure was independently re-confirmed against live source:
- `src/wanctl/check_config_validators.py:258` — `measurement.fping.cadence_sec` is a
  recognized config key (the Phase 241 D-06 independent fping cadence).
- `src/wanctl/fping_measurement.py:51-57` — default fping timeout
  `= count(5)*period_ms(200)/1000 + grace(2.0) = 3.0s`.
- `src/wanctl/fping_measurement.py:299-301` — `FpingThread.__init__` raises `ValueError` when
  `measurement._timeout >= cadence_sec`.
- Plan 02 (`242-02-PLAN.md:140-147`) resolves `fping_cadence_sec` from
  `measurement.fping.cadence_sec` (default `10.0`) ONCE on the handle; Plan 03
  (`242-03-PLAN.md:243-244`) confirms `make_thread`'s fping branch IGNORES the caller-supplied
  controller cadence and uses `handle.fping_cadence_sec`.

Net: `10.0 > 3.0` with the validated defaults, so the `timeout < cadence` invariant holds and
the live fping path stays `backend_active == "fping"` rather than deterministically falling
back. The Cycle-3 defect is fixed in the correct layer and backed by a real-path test. No new
HIGH this cycle.

**Recommendation:** No remaining HIGH blockers — plans are execution-ready. Optionally fold
the three MEDIUMs (fping sub-config fidelity helper + test, exact steering source_ip
disposition, `wan_controller.py` qualname-drift guard) before or during execution; none gate
the phase. Residual risk: MEDIUM (execution fidelity), not plan correctness.
