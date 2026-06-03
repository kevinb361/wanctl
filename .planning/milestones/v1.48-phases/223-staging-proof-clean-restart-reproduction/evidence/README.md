# Phase 223 Steering Replay Evidence

This directory contains PROOF-01 offline replay evidence for Phase 223.

## Operator Commands

```bash
.venv/bin/pytest -o addopts='' tests/integration/steering_replay/ -v
.venv/bin/python tests/integration/steering_replay/replay_harness.py --all
```

The harness is staging/offline only. It uses a fake RouterOS transport, fake CAKE reader, fixture-backed baseline/RTT loader, pytest tempdir state files, and defense-in-depth urlopen/socket seals. It must never call the live router and must never write under production runtime roots.

## Harness Mode Policy

Every fixture declares `harness_mode` explicitly:

- `hysteresis-only` — `SteeringConfig.use_confidence_scoring=False`; cycle counts are authored against the simple hysteresis state machine. This is the default for spine-contract fixtures.
- `confidence` — production confidence scoring remains enabled; cycle budgets are derived from `configs/steering.yaml` divided by `ASSESSMENT_INTERVAL_SECONDS = 0.05`.

For current production config, confidence-mode derived budgets are:

| field | seconds | cycles |
|---|---:|---:|
| `confidence.sustain_duration_sec` | 2.0 | 40 |
| `confidence.recovery_sustain_sec` | 3.0 | 60 |
| `confidence.hold_down_duration_sec` | 30.0 | 600 |

## Fixture Schema

Top-level fixture keys:

- `name` — fixture identifier.
- `description` — operator-readable purpose.
- `harness_mode` — `hysteresis-only` or `confidence`.
- `cycle_budget_derivation` — documents either hysteresis-only rationale or confidence-mode cycle math from production config.
- `corpus_source` — `synthesized-from-spine-contract` or `derived-from-phase-212-evidence`.
- `derivation` — cites the specific spine-contract clause used to author the fixture.
- `pre_state` — split object with `steering_pre_state` and `autorate_state_by_cycle`.
- `cycles` — per-cycle inputs and expected observable decision.

Example:

```yaml
name: steady-good
description: Low RTT delta stays GOOD and steering remains disabled.
harness_mode: hysteresis-only
cycle_budget_derivation:
  mode: hysteresis-only
  confidence_disabled: true
corpus_source: synthesized-from-spine-contract
derivation: binary on/off; autorate-baseline authority
pre_state:
  steering_pre_state:
    current_state: SPECTRUM_GOOD
    good_count: 0
    red_count: 0
    transitions: []
    last_transition_time: null
  autorate_state_by_cycle:
    default:
      ewma:
        baseline_rtt: 25.0
      congestion:
        dl_state: GREEN
cycles:
  - inputs:
      live_rtt_ms: 25.5
      cake_drops: 0
      queued_packets: 0
    expected_decision:
      current_state: SPECTRUM_GOOD
      effective_mangle_state: false
```

`autorate_state_by_cycle` uses the real spectrum-state shape: `{"ewma": {"baseline_rtt": float}, "congestion": {"dl_state": str}}`. The harness writes the `default` value, or a cycle-specific override when present, to `workspace/spectrum_state.json` before running that cycle.

## Corpus Source Policy

Fixtures are derived from the steering spine contract or from read-only Phase 212 / Phase 222 evidence. No fixture is derived from observing the post-drift code's own behavior; doing so would make the proof circular.

## Provenance: Anchored Fixtures

Phase 212 evidence is archived under `.planning/milestones/v1.46-phases/212-production-inventory-and-drift-audit/`, not `.planning/phases/212-*`.

The current checkout does not contain a concrete archived Phase 212 evidence row or active Phase 222 evidence row suitable for verbatim per-cycle extraction. Therefore `onset-degraded-from-phase212.yaml` includes a `provenance_note` and is explicitly labeled `corpus_source: synthesized-from-spine-contract` rather than silently claiming runtime evidence provenance.

## FULL I/O SEAL

Plan 01 selected option (a) FULL I/O SEAL. The harness drives `SteeringDaemon.run_cycle()` end-to-end and seals these paths:

- `RouterOSController` → `FakeRouterTransport`
- `cake_reader.read_stats()` → `FakeCakeReader`
- `BaselineLoader.load_baseline_rtt()` / `load_live_rtt()` / `load_live_irtt_rtt()` → `FixtureBaselineLoader`
- `state_mgr.save()` → pytest tempdir or explicit staging workspace
- metrics DB writes → disabled by empty `storage.db_path`
- defense-in-depth HTTP/socket calls → pytest autouse urlopen/socket seals

No steering-source seam edit was required for Plan 01; all wiring uses constructor injection or post-construction `daemon.cake_reader = fake_cake_reader`.

## SAFE-12 Posture

Plan 01 changes are limited to tests and evidence docs. Controller-path source remains out of scope and is verified by Plan 03's SAFE-12 boundary check.
