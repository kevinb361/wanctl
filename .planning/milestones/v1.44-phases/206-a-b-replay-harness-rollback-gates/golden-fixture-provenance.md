---
phase: 206
artifact: golden-fixture-provenance
fixture: tests/fixtures/phase206_golden_capture.ndjson
generator: tests/fixtures/_phase_206_generator.py
locked_by: Locked Decision D1 (2026-05-14)
---

# Golden Fixture Provenance — tests/fixtures/phase206_golden_capture.ndjson

## Source Artifact (Locked Decision D1)

Full path of the source flent capture:

```text
/home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/rrul-*.flent.gz
```

Test profile: RRUL (Realtime Response Under Load). Configuration under test: `920Mbit besteffort wash` — i.e., the POST-migration Spectrum config target.

## Date Substitution Rationale

The Phase 206 ROADMAP entry references “the 2026-04-22 out-of-band flent finding”. That specific 2026-04-22 artifact is not recoverable verbatim:

> “Out-of-band test details (date, flent profile, measured deltas) should be recovered from Kevin's test logs and added to the Phase 196 CONTEXT.md. If lost, Phase 196 must re-run the validation before landing.”
> — `SEED-001-spectrum-topology-correct-cake-mode.md:77` (2026-04-24 retroactive note)

The closest recoverable artifact of the same shape (920Mbit RRUL on besteffort) is the 2026-04-29 capture above. The operator accepted this substitution on 2026-05-14 (Locked Decision D1 in `206-RESEARCH.md`). No fresh flent re-run was scheduled.

Implication for Phase 209's canary: the operator should refresh the baseline before the production canary (see Re-Derivation Procedure below). The 2026-04-29 capture remains valid as the design-time deterministic fixture — Phase 206's harness behavior is the same regardless of which captured run the fixture derives from.

## Derivation Pipeline

1. **Source:** `*.flent.gz` files in the directory above.
2. **Generator:** `tests/fixtures/_phase_206_generator.py` (the underscore prefix marks it as a one-shot build tool, matching the Phase 203/204 generator naming convention).
3. **Output:** `tests/fixtures/phase206_golden_capture.ndjson` (committed).

Invocation:

```bash
.venv/bin/python tests/fixtures/_phase_206_generator.py \
    --source-dir /home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/ \
    --out tests/fixtures/phase206_golden_capture.ndjson
```

Deterministic: re-running the generator with the same input produces a byte-identical NDJSON. Verified in Plan 01 Task 1 acceptance criteria via a `diff` round-trip check.

## Field Schema

Each NDJSON line is a single JSON object with exactly these fields (no operator-identifying data — see “Scrubbing” below):

| Field | Type | Source in .flent.gz | Maps to GoldenSample |
|-------|------|---------------------|----------------------|
| `ts` | string | synthesized (`f"{i:06d}"`) | `GoldenSample.ts` |
| `baseline_rtt_ms` | float | min(non-zero values in first 5% of ping series) | `GoldenSample.baseline_rtt_ms` |
| `load_rtt_ms` | float | per-sample raw value from ping series | `GoldenSample.load_rtt_ms` |
| `cake_avg_delay_us` | int | synthesized: `max(0, round((load_rtt_ms - baseline_rtt_ms) * 1000))` | `GoldenSample.cake_avg_delay_us` |
| `cake_base_delay_us` | int | synthesized: `0` | `GoldenSample.cake_base_delay_us` |

Ping series key fallback order (the generator tries each in turn): `"Ping (ms) ICMP"`, `"Ping (ms) UDP BE"`, `"Ping (ms) avg"`. First non-empty numeric list wins.

CAKE-internal stats are not surfaced by flent's JSON output. The generator synthesizes `cake_avg_delay_us` / `cake_base_delay_us` from the RTT delta (documented in the generator docstring). **Revision 2026-05-14 (C2):** these per-row synthesized fields are now actually consumed by `scripts/phase206-ab-replay.py` via `_replay_samples` — one cycle per fixture row, not one snapshot reused. This addresses the codex review's observation that an earlier draft consumed only `samples[0]`.

## Scrubbing

The generator commits only the five fields above. Specifically excluded from the NDJSON:

- IP addresses (source, destination, gateway)
- Hostnames (test target, source host, router ID)
- MAC addresses
- Full ISO8601 timestamps that could correlate to other operator-side logs

Verified by acceptance criterion in Plan 01 Task 1:

```bash
grep -E '([0-9]{1,3}\.){3}[0-9]{1,3}' tests/fixtures/phase206_golden_capture.ndjson
# MUST produce no output
```

## Sample Count

Bounded `[24, 1024]`:

- Lower bound 24: matches the Phase 193 `TRACE` length convention so downstream `EXPECTED_*` tables can align if added.
- Upper bound 1024: keeps repo footprint small. Generator stride-samples deterministically when the source has more.

The committed fixture currently contains 350 rows.

## SHA256 of Committed Fixture

Current value: `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda`

Operator command to recompute:

```bash
sha256sum tests/fixtures/phase206_golden_capture.ndjson
```

Plan 04 also verifies this pin when it performs the phase closeout drift checks.

## Re-Derivation Procedure (for Phase 209 baseline refresh)

When Phase 209's canary preparation requires a freshly captured baseline:

1. Capture a new flent RRUL run against the live `920Mbit besteffort wash` Spectrum config. Save to `/home/kevin/flent-results/<run-id>/`.
2. Re-run the generator pointing at the new directory:
   ```bash
   .venv/bin/python tests/fixtures/_phase_206_generator.py \
       --source-dir /home/kevin/flent-results/<run-id>/ \
       --out tests/fixtures/phase206_golden_capture.ndjson
   ```
3. Update the SHA256 in this document.
4. Re-run the harness with the fresh flent `.gz` files to regenerate the baseline A/B summary:
   ```bash
   .venv/bin/python scripts/phase206-ab-replay.py \
       --flent-gz-pre /home/kevin/flent-results/<pre-run>/rrul-*.flent.gz \
       --flent-gz-post /home/kevin/flent-results/<post-run>/rrul-*.flent.gz \
       --out tests/fixtures/phase206_baseline_v143.json
   ```
   Note: the output will need hand-editing to inject the `gate_baseline` block — the harness emits the schema-v1 A/B summary; the `gate_baseline` block is appended manually per the procedure documented in `PHASE-205-ROLLBACK-GATES.md`.
5. Re-run the full test suite to confirm everything still passes:
   ```bash
   .venv/bin/pytest tests/ -q
   ```

## Why a Separate Provenance Doc

A docstring inside `tests/fixtures/phase206_replay_corpus.py` (the Phase 201 convention) would cover origin-pointer needs but not:

- the date-substitution rationale (audit-trail concern),
- the operator-facing re-derivation procedure (procedural concern),
- the SHA256 pin (drift-detection concern).

Hence this standalone markdown — same evidence-with-fenced-blocks shape as `205-04-SUMMARY.md`.
