# Phase 193 Verification

## Scope

Phase 193 is observability-only. The verification target is `SAFE-05`: the new
queue-delay telemetry fields added in `193-01` and surfaced in `193-02` must
not change download 4-state classifier transitions or rate-apply sequences.

## Replay Proof

The canonical equivalence proof is `tests/test_phase_193_replay.py`.

It replays a fixed 24-row RTT trace that covers:

- `GREEN`, `YELLOW`, `SOFT_RED`, and `RED`
- repeated boundary rows at `15ms`, `20ms`, `45ms`, and `80ms`
- dwell-sensitive `GREEN -> YELLOW` transitions
- post-`RED` re-entry through `SOFT_RED` and `YELLOW`

The harness enforces the Phase 193 review requirement that each replay variant
uses its own freshly-constructed `QueueController` instance. It includes an
explicit identity guard proving the compared variants do not share controller
state.

## Assertion Set

- Spectrum-shaped controller replay with zeroed snapshot fields matches the
  exact expected zone sequence and rate sequence.
- Spectrum-shaped controller replay with populated
  `avg_delay_us/base_delay_us/max_delay_delta_us` fields matches the same exact
  zone sequence and rate sequence.
- ATT-shaped controller replay with zeroed snapshot fields matches its own
  exact expected rate sequence.
- ATT-shaped controller replay with populated queue-delay fields matches the
  same exact zone sequence and rate sequence.
- Replays across wildly different `max_delay_delta_us` values still produce the
  same zone and rate sequences, proving the classifier does not consume the new
  fields in Phase 193.

## Verification Run

Executed on 2026-04-24:

```bash
.venv/bin/pytest -o addopts='' \
  tests/test_cake_signal.py \
  tests/backends/test_linux_cake.py \
  tests/backends/test_netlink_cake.py \
  tests/test_health_check.py \
  tests/test_wan_controller.py \
  tests/test_phase_193_replay.py -q
```

Result:

- `503 passed in 41.39s`

## Dependencies

This verification depends on both earlier plans being present:

- `193-01` provides the additive snapshot fields and authoritative
  `max_delay_delta_us`
- `193-02` provides the observability surfaces that consume those fields

`193-03` therefore closes the phase only after both plans have landed.

## Nyquist Note

Phase 193 research did not define a separate `VALIDATION.md` architecture for
this phase. The replay-equivalence harness above is the intended Dimension-8
proof for `SAFE-05`, and this file records that explicitly so the phase does
not carry a false validation-gap signal.
