# Phase 220 Wet Daytime Control Cell Rehearsal Protocol

## Purpose

ROADMAP Success Criterion #3 requires one wet daytime control cell run on the canonical Phase 214 `dallas` reflector via Spectrum to reproduce the Phase 214 canonical anchor verdict. This proves the Phase 220 harness composition (`phase220-target-path-matrix.sh` → `phase213-baseline-capture.sh` → unchanged Phase 214 extractor + aligner + classifier) is faithful before any supplemental cells run. The rehearsal evidence becomes the cross-check that Plan 02's aggregator and Plan 03's wrapper compose Phase 213/214 correctly.

## Preconditions

- Operator is on `dev`, the production-adjacent dev VM with access to `cake-shaper`.
- Local time is in 10..16 for the daytime window in `scripts/phase220-matrix.yaml`.
- Spectrum WAN is connected and reachable on the configured bind IP.
- The `dallas` reflector is reachable; the Phase 214 anchor used `RUN-20260528T150507Z`.
- `PHASE220_BASE_SHA`, when exported, is copied from the YAML `base_sha` field and must match it.
- SOURCE-FLOOR invariant uses corrected semantics: `base_sha` is a source-floor anchor, not exact HEAD equality. HEAD may be ahead of `base_sha` when forbidden paths have zero diff against `base_sha`.
- Plans 01, 02, and 03 are committed and their Phase 220 tests pass.

Precondition one-liners:

```bash
date +%H | .venv/bin/python -c 'import sys; h=int(sys.stdin.read()); raise SystemExit(0 if 10 <= h <= 16 else 1)'
```

```bash
BASE_SHA=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('scripts/phase220-matrix.yaml'))['base_sha'])") && git diff --quiet "$BASE_SHA" HEAD -- src/wanctl/ scripts/phase213-* scripts/phase214-*
```

```bash
git diff --quiet -- src/wanctl/ scripts/phase213-* scripts/phase214-* && git diff --quiet --cached -- src/wanctl/ scripts/phase213-* scripts/phase214-*
```

```bash
.venv/bin/pytest tests/test_phase220_*.py -q
```

Do not use HEAD equality against `BASE_SHA`; that would reject later Plan 02/03/04 commits even when protected sources are unchanged.

## Step-by-step

1. Verify the preconditions above.

2. Export the source-floor anchor from the YAML:

   ```bash
   export PHASE220_BASE_SHA=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('scripts/phase220-matrix.yaml'))['base_sha'])")
   ```

3. Run the wrapper for the `dallas__spectrum__daytime` cell, replicate 1:

   ```bash
   ./scripts/phase220-target-path-matrix.sh --cell dallas__spectrum__daytime --replicate 1
   ```

4. Verify the newest `RUN-*` directory was created under `.planning/phases/220-matrix-runner-scope-a1/evidence/` and contains:

   - `<RUN_DIR>/spectrum/tcp_12down/signal-sheet.json`
   - `<RUN_DIR>/phase220-cell.json`
   - `<RUN_DIR>/mtr-pre-1.txt`
   - `<RUN_DIR>/spectrum/tcp_12down/journal-window.ndjson`

5. Read the Phase 220 rehearsal verdict:

   ```bash
   jq -r '.verdict, .primary_driver, .latency.p99_ms' <RUN_DIR>/spectrum/tcp_12down/signal-sheet.json
   ```

6. Cross-reference the Phase 214 canonical daytime anchor:

   - Anchor path: `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/evidence/RUN-20260528T150507Z/spectrum/tcp_12down/signal-sheet.json`
   - Expected anchor fields: `verdict=ambiguous`, `primary_driver=reflector_loss`, `latency.p99_ms=606.0`
   - The archived path includes `phase214` in the historical phase slug and is the canonical daytime `dallas` Spectrum run for this rehearsal.

7. Write `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/REHEARSAL-VERDICT.md` with:

   - Heading: `# Phase 220 Wet Daytime Control Cell Rehearsal — Verdict`
   - Phase 220 rehearsal verdict, primary driver, and p99
   - Phase 214 anchor verdict and primary driver
   - Comparison line: `✓ MATCH` when verdict and primary driver match, or `✗ DIVERGENCE` when they do not
   - Source `RUN-*` directory and UTC rehearsal date

8. Copy or symlink friendly evidence paths:

   - `dallas__spectrum__daytime__r1/phase220-cell.json` from `<RUN_DIR>/phase220-cell.json`
   - `dallas__spectrum__daytime__r1/signal-sheet.json` from `<RUN_DIR>/spectrum/tcp_12down/signal-sheet.json`
   - Keep `mtr-pre-1.txt` with the source `RUN-*` directory, and copy it into the friendly directory if operator review needs one directory.

9. Stage and commit the evidence directory:

   ```bash
   git add .planning/phases/220-matrix-runner-scope-a1/evidence/
   git commit -m "evidence(220): wet daytime control cell rehearsal reproduces Phase 214 dallas anchor"
   ```

10. Run the final Phase 220 regression slice:

    ```bash
    .venv/bin/pytest tests/test_phase220_*.py -q
    ```

## Acceptance criteria for the rehearsal

- The Phase 220 rehearsal verdict matches the Phase 214 anchor verdict on the `verdict` field.
- The Phase 220 rehearsal `primary_driver` matches the Phase 214 anchor `primary_driver`, or both are null.
- The Phase 220 `mtr-pre-1.txt` is committed with the cell evidence.
- The Phase 220 cell manifest fields are populated: `target_name=dallas`, `target_kind=canonical`, `path_name=spectrum`, `window_name=daytime`, and `replicate_index=1`.

## Failure modes

- If the verdict diverges from the Phase 214 anchor, stop. The harness is not faithful; re-investigate Plan 03 wrapper composition before proceeding to Phase 221.
- If the `RUN-*` directory is not created, re-run with `--dry-run --test-hour 14` to inspect the delegated command and check `journalctl -u wanctl@spectrum` on `cake-shaper` for upstream service health.
- If `mtr` fails, install `mtr` on the dev VM and rerun; `mtr` is required for BGP path-change evidence.

## After the rehearsal

- Plan 04 Task 3 commits the evidence and verdict comparison.
- Phase 220 is ready for `/gsd:verify-work` after the checkpoint resumes and automated post-checks pass.
- Phase 221 may begin after the wet rehearsal evidence confirms the Phase 220 harness is faithful.

This protocol is operator-driven. The executor stops at the Plan 04 Task 3 human-action checkpoint until the operator confirms the live rehearsal evidence is committed and matches the Phase 214 anchor.
