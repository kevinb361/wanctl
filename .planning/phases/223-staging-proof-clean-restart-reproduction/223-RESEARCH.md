# Phase 223 Research — Staging Proof + Clean-Restart Reproduction

**Phase:** 223 — Staging Proof + Clean-Restart Reproduction
**Milestone:** v1.48 Steering Runtime Drift Closure
**Date:** 2026-06-02
**Scope:** Offline / staging-only harness work. **No production mutation, no
controller-path source diff vs v1.47 close (SAFE-12).** Steering daemon source
(`src/wanctl/steering/*`, `check_steering_validators.py`) is the only
v1.48-mutable surface, and even there this phase prefers harness wiring over
behavior changes.

---

## 1. Problem Framing

Phase 222 closed with a single in-scope behavior-changing commit (`84ad6aa`,
"fix: harden steering and storage utility contracts") classified
`preserves` against all three steering spine invariants, with a disposition
of `go` and no required mitigation. Phase 223 must now turn that paper
verdict into runtime-grounded evidence by:

1. **PROOF-01**: Standing up an offline replay/fixture harness that
   exercises the post-drift source (v1.47-close steering daemon) against
   canonical pre-drift behavior captured from the running runtime
   (`v1.39`-deployed steering daemon at `1.39.0`).
2. **PROOF-02**: Either reproducing the folded
   `2026-04-17-investigate-steering-degraded-on-clean-restart` symptom in
   the harness, OR producing a fail-closed reason why reproduction is not
   feasible in an offline harness. The folded todo closes either way.
3. **PROOF-03**: Producing evidence that staging steering behavior preserves
   the spine contract (binary on/off, only-new-connections rerouted,
   autorate-baseline-RTT-authoritative) across every fixture in the replay
   corpus — not just at the diff level Phase 222 audited, but at observed
   runtime decision level.

Phase 224 (production canary + rollback discipline) depends on these
artifacts. If PROOF-01/02/03 cannot stand up cleanly, Phase 224 stops.

---

## 2. Audit Surface Inheritance

Phase 222 evidence anchors:

- `baseline_commit = d1c26de6fb284686caf32bebcd0e7c93c7c70476` (v1.39 peeled)
- `source_commit  = bee343b0c2f16207101aec82007a5e55fa9b6407` (v1.47 peeled)
- Single behavior-changing commit: `84ad6aa2d5bc7d03ef5069c0b65e7b1cdf930538`
- Steering surface paths: see `delta-baseline.json#surface_files`
- SAFE-12 allowlist: `wan_controller.py`, `queue_controller.py`,
  `cake_signal.py`, `backends/`, `alert_engine.py`, `fusion*.py`

This phase inherits all of those as locked inputs. No re-audit, no expansion
of surface, no re-classification.

---

## 3. Replay Corpus: What Counts as Canonical Pre-Drift Behavior

The post-drift code under test is `src/wanctl/steering/daemon.py` at the
v1.47-close source tree. The "pre-drift behavior" the corpus must capture is
the live `1.39.0` daemon's *decision behavior* across representative
operating conditions:

| Condition | Decision the daemon must make |
|-----------|------------------------------|
| Steady-good (low RTT delta, baseline frozen) | Stay in `SPECTRUM_GOOD`, mangle rule disabled |
| RTT delta sustained above degraded threshold | Transition `SPECTRUM_GOOD → SPECTRUM_DEGRADED`, mangle rule enabled |
| Recovery (RTT delta drops, good_count climbs) | Transition `SPECTRUM_DEGRADED → SPECTRUM_GOOD`, mangle rule disabled |
| Clean restart while persisted state = `SPECTRUM_DEGRADED` | First-cycle observable state — the symptom in scope for PROOF-02 |
| CAKE read failure under degraded | Daemon does not flap; preserves last state until measurement returns |

Canonical pre-drift behavior is sourced from:

1. **Existing production health-endpoint and journal evidence** captured under
   Phase 212 / Phase 222 (read-only — no new production probe).
2. **Synthesized fixtures** derived from the steering daemon's documented
   spine contract and existing `tests/steering/*` test corpus. Synthesized
   fixtures are acceptable *if and only if* they are derived from the spine
   contract; they MUST NOT be derived from the post-drift code's own
   behavior (that would make the proof circular).

The harness reads each fixture, drives the post-drift `WANSteeringDaemon` (or
the minimal subset of it that owns the decision pipeline) through one or
more cycles, and records the observed transitions, mangle-rule toggles, and
autorate-baseline reads. The comparison against the canonical decision is a
verdict per fixture: `matches | diverges | inconclusive`.

---

## 4. Harness Architecture

Three constraints set the architecture:

1. **Offline / no router mutation.** The harness must not call live RouterOS
   REST/SSH. RouterOS interactions go through a fake transport that returns
   pre-recorded responses to mangle-rule queries and accepts (asserts on)
   the daemon's enable/disable commands without forwarding them.
2. **No production state file mutation.** All `/var/lib/wanctl/*` paths used
   by the harness must be redirected to a tempdir under the staging
   workspace (e.g., `.planning/phases/223-.../evidence/staging-state/`).
   `SteeringStateManager` already takes an explicit `state_file: Path`, so
   redirection is one constructor argument.
3. **SAFE-12 preserved.** No edit to controller-path files. Steering source
   may be edited only if a steering-side seam is required to make the daemon
   driveable from the harness; preferred approach is to inject doubles via
   constructor arguments and existing seams (config object, transport
   factory, state-file path) without touching the v1.47-close steering
   source. The phase plans should explicitly check this expectation before
   any steering-source edit lands.

**Recommended layout under** `tests/integration/steering_replay/`:

```
tests/integration/steering_replay/
  __init__.py
  conftest.py                       # Tempdir + fake transport fixtures
  fake_router_transport.py          # In-memory RouterOSController stand-in
  fixtures/
    steady-good.yaml                # Per-cycle inputs + expected decision
    onset-degraded.yaml
    recovery.yaml
    clean-restart-degraded.yaml     # PROOF-02 scenario
    cake-read-failure.yaml
  replay_harness.py                 # Drives daemon.run_cycle() per fixture
  test_replay_corpus.py             # Pytest entry; asserts spine invariants
```

`replay_harness.py` is the operator-runnable entry point. `test_replay_corpus.py`
gives CI gating without operator intervention.

If a steering-source seam is genuinely necessary (e.g., the daemon
unconditionally opens a network socket at startup), prefer minimal,
test-only injection that is independent of behavior — e.g., factoring the
already-built `RouterOSController` instance through an injected attribute.
Any such seam MUST be accompanied by a steering-source diff explanation in
the plan and a `tests/steering/test_*.py` regression covering the seam
contract.

---

## 5. Clean-Restart Reproduction (PROOF-02)

The folded todo
(`.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md`)
describes the symptom: at 2026-04-17 21:05:27 the daemon's very first cycle
loaded `state["current_state"] = "SPECTRUM_DEGRADED"` even though the link
was healthy, with auto-recovery to `SPECTRUM_GOOD` inside ~28s. Production
impact: zero. Open question: is the persisted-DEGRADED-then-recovered
behavior intentional (resume-after-crash), or is it persistence of a
transient degradation that should not have survived a restart?

The harness can reproduce this deterministically:

1. Pre-seed the harness state file with `current_state: "SPECTRUM_DEGRADED"`,
   `good_count: 0`, plausible `baseline_rtt` and history arrays.
2. Wire the harness to feed `SPECTRUM_GOOD`-consistent measurement inputs
   (low RTT delta, no CAKE drops) on every cycle.
3. Start the daemon cold (no in-memory state).
4. Run cycles forward, recording (a) cycle-1 observable `current_state`,
   (b) cycle at which the daemon recovers to `SPECTRUM_GOOD`, (c) whether
   the mangle rule is toggled to enabled during the recovery window.

Three outcomes are acceptable for PROOF-02 closure:

| Outcome | Disposition |
|---------|-------------|
| Harness reproduces the symptom (cycle 1 = `DEGRADED`, recovery within bounded cycles) | Document recovery-bound semantics; classify as **intentional**, fold notes into todo + phase summary. |
| Harness reproduces the symptom AND shows that the persisted-DEGRADED state caused a spurious mangle-enable + steering toggle | Document as a **bug** with proposed fix scope; record fix recommendation for v1.48 closure or Phase 224 hold. |
| Harness cannot reproduce the symptom because the persisted state never causes a first-cycle `DEGRADED` reading | Document fail-closed: "reproduction not feasible against post-drift code in this harness; behavior already changed", classify as **resolved-by-drift** if the symptom is gone in the post-drift source. |

In every outcome, PROOF-02 closes (per ROADMAP success criterion 2).
The harness does NOT pursue a "fix blind" path; if a fix is needed it is
named, scoped, and held against Phase 224's "no surprises pre-canary" gate
or a follow-up phase.

---

## 6. Spine-Contract Evidence (PROOF-03)

For each fixture in the replay corpus, the harness records:

- Cycles run.
- Final observable state (`current_state`).
- Mangle-rule toggle sequence the daemon issued (captured in the fake
  transport).
- Baseline-RTT reads (proves autorate-baseline authority — the daemon must
  not mint its own baseline; it must read the autorate-frozen baseline from
  the spectrum state file).
- Spine-invariant verdict per fixture against the three invariants:

  1. **Binary on/off**: At every cycle, the mangle rule the daemon attempted
     to set was strictly `enabled=True` or `enabled=False` (no partial /
     weighted / blended state).
  2. **Only new latency-sensitive connections rerouted**: This is a
     RouterOS-side property (mangle rules tag *new* connections, not
     existing ones), so the harness assertion is that the daemon only ever
     manipulates the documented mangle rule (`comment=ADAPTIVE: ...`) and
     never issues a connection-tracking flush, conntrack clear, or
     equivalent. The harness verifies *what the daemon would have sent*; it
     does not need a live router.
  3. **Autorate-baseline authority**: Every baseline-RTT read in the cycle
     came from the spectrum state file (mocked under the staging tempdir);
     the daemon did not compute a fresh baseline from its own measurement
     samples. The fake transport / fake state file makes this directly
     observable.

The PROOF-03 evidence artifact is a `spine-evidence.json` plus a
`spine-evidence.md` table, one row per fixture, three verdict columns plus
overall verdict.

---

## 7. SAFE-12 Boundary Check

Identical methodology to Phase 222 §10:

```
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- \
  src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
```

Expected: empty output across committed, staged, unstaged, untracked, and
porcelain checks. Result captured as `evidence/safe12-boundary-check.json`
plus `evidence/safe12-boundary-check.md`. Reuse the Phase 222 verification
script verbatim — same allowlist, same baseline, same expected-empty
contract.

---

## 8. Methodology Summary (per requirement)

| REQ-ID | Methodology | Artifact |
|--------|-------------|----------|
| PROOF-01 | Build offline replay harness + fixture corpus driving v1.47-close steering daemon decision pipeline with fake RouterOS transport and tempdir state files. | `tests/integration/steering_replay/` + `evidence/replay-results.json` + `evidence/replay-results.md` |
| PROOF-02 | Pre-seed staging state file to `SPECTRUM_DEGRADED`, run daemon cold against `GOOD`-consistent measurements, record cycle-1 observable state and recovery trajectory. Three acceptable closure outcomes per §5. | `evidence/clean-restart-reproduction.json` + `evidence/clean-restart-reproduction.md` + folded-todo close note |
| PROOF-03 | Per-fixture spine-invariant verdict using fake transport observations and tempdir-redirected state file reads. | `evidence/spine-evidence.json` + `evidence/spine-evidence.md` |
| SAFE-12 | Reuse Phase 222 boundary script; expected-empty diff against `bee343b` for controller-path allowlist; capture committed + dirty-tree state. | `evidence/safe12-boundary-check.json` + `evidence/safe12-boundary-check.md` |

---

## 9. Risks / Open Questions

| Risk | Mitigation |
|------|------------|
| The post-drift steering daemon cannot be exercised one-cycle-at-a-time without an extracted seam, forcing a steering-source edit that crosses the line between "harness wiring" and "behavior mutation" | Inspect `WANSteeringDaemon.run_cycle()` and its constructor for existing injection points (config, logger, state-file path, router transport) before designing the harness; if a new seam is required, plan it as an explicit, named source-level task with a regression test, and re-confirm SAFE-12 boundary AND no behavior change in steering decision path. |
| Canonical pre-drift behavior is hard to obtain at fixture granularity because production journal evidence is coarse | Acceptable to use synthesized fixtures derived from the spine contract (NOT from post-drift code behavior), explicitly labeled in the fixture YAML; the harness's job is to detect spine-contract divergence, which the synthesized corpus can validate. |
| Reproducing the clean-restart symptom may not be possible if the persisted-DEGRADED-with-GOOD-input never produces a first-cycle DEGRADED read in the post-drift source | This is itself an acceptable PROOF-02 outcome ("fail-closed: reproduction not feasible against post-drift code"); document with the exact behavior observed and the inferred reason. Folded todo still closes. |
| Staging tempdir leakage to real `/var/lib/wanctl/` paths | Harness MUST use `tmp_path` pytest fixture or an explicit staging workspace under `.planning/phases/223-.../evidence/staging-state/`; no env var, no default, no hidden fallback to `/var/lib/wanctl/`. Add a pytest assertion that the test never writes to `/var/lib/wanctl/`. |
| Fake RouterOS transport drift from real RouterOS protocol | Limit fake transport to the exact two interactions the daemon performs: `get_rule_status()` (read mangle disabled flag) and `set_rule_status()` (enable/disable mangle rule). Don't model the wider REST/SSH surface. Capture-and-replay rather than synthesize. |

---

## 10. Validation Architecture

Validation for Phase 223:

- **Source assertions** — every fixture file, harness module, and evidence
  artifact path exists in the working tree.
- **Schema assertions** — fixture YAML conforms to a documented schema
  (cycles, inputs per cycle, expected decision); harness output JSON parses
  with `json.tool`; markdown tables have expected columns.
- **Behavior assertions** — running `pytest tests/integration/steering_replay/`
  exits 0; every fixture's spine verdict is `matches` or has a documented
  `diverges` justification recorded under §5 outcome 2.
- **PROOF-02 closure assertion** — `evidence/clean-restart-reproduction.md`
  records exactly one of the three §5 outcomes with cited evidence rows
  from `clean-restart-reproduction.json`.
- **SAFE-12 assertion** — boundary-check JSON has `passed: true`,
  `committed_clean: true`, `dirty_tree_clean: true`, empty per-path diffs,
  and empty staged/unstaged/untracked/porcelain arrays. Identical contract
  to Phase 222.
- **Folded-todo closure** — `2026-04-17-investigate-steering-degraded-on-clean-restart.md`
  is updated with the PROOF-02 outcome and the link to the evidence
  artifacts; the todo file is either annotated with closure status or moved
  per project todo-close convention.

No new helper code outside the harness directory is expected. Any helper
introduced must ship with regression coverage under `tests/integration/`
before any plan task depends on it.

---

## RESEARCH COMPLETE
