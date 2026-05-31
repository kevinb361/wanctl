# Phase 220 Matrix Runner

## Overview

Phase 220 ships two CLI tools: `scripts/phase220-target-path-matrix.sh` (per-cell evidence collector) and `scripts/phase220-matrix-aggregator.py` (cube verdict aggregator). Both compose existing Phase 213/214 surfaces without edits. The threshold and decision-rule fields used by the aggregator are pre-registered in `scripts/phase220-matrix.yaml` and locked at plan-commit time; this document describes how to use the tools, not how to adjust them.

## `phase220-target-path-matrix.sh` — per-cell wrapper

Usage from the script:

```text
Usage:
  scripts/phase220-target-path-matrix.sh --cell <cell_id> --replicate <N>
  scripts/phase220-target-path-matrix.sh --dry-run --test-hour <H> --cell <cell_id> --replicate <N>
  scripts/phase220-target-path-matrix.sh --help | -h

Runs one Phase 220 target/path/window matrix cell by resolving the cell from
scripts/phase220-matrix.yaml, refusing protected source drift, then delegating
traffic generation to scripts/phase213-baseline-capture.sh unchanged. Dry runs
execute gates and print the planned delegate command prefixed with DRY-RUN:.

Options:
  --cell <cell_id>          Required matrix cell id from scripts/phase220-matrix.yaml
  --replicate <N>           Required replicate index, positive integer
  --dry-run                 Print planned delegate command without network/delegate execution
  --test-hour <H>           Dry-run-only local hour override, 0..23
  --inter-cell-delay <S>    Sleep after live cell completion (default: 60)

Environment:
  PHASE220_MATRIX_YAML      YAML path override for tests (default: scripts/phase220-matrix.yaml)
  PHASE220_BASE_SHA         optional traceability echo; must match YAML base_sha if set
  PHASE214_FLENT_DURATION   flent duration seconds (default: 30)
  PHASE214_CAKE_SHAPER      inherited delegate/journal compatibility var (default: cake-shaper)

Exit codes:
  0  success
  2  refused: out-of-window hour, invalid CLI/window, or ATT egress mismatch
  3  refused: cell not found in YAML
  4  refused: src/wanctl or Phase 213/214 mutation guard failed; bad YAML/base_sha
  5  failed: mtr, delegated capture, or manifest validation failed
  7  refused: --test-hour without --dry-run
```

Required environment:

- `PHASE220_BASE_SHA` is optional for dry-run traceability, but if it is set it must match `base_sha` in `scripts/phase220-matrix.yaml`.
- The YAML `base_sha` is a source-floor anchor. Operators verify protected-source drift with `git diff --quiet <base_sha> HEAD -- src/wanctl/ scripts/phase213-* scripts/phase214-*`; HEAD may be ahead when those protected paths have no diff.

Exit-code quick reference:

| Exit | Meaning |
|------|---------|
| 0 | The wrapper completed or printed a valid dry run. |
| 2 | The requested cell is outside its local-hour window, the CLI/window is invalid, or ATT egress did not match the YAML signature. |
| 3 | The requested `--cell` is not listed in `scripts/phase220-matrix.yaml`. |
| 4 | YAML, base SHA, protected-source drift, or ATT signature preflight failed. |
| 5 | Live `mtr`, delegated capture, or sidecar manifest creation failed. |
| 7 | `--test-hour` was supplied without `--dry-run`. |

Example dry run:

```bash
export PHASE220_BASE_SHA=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('scripts/phase220-matrix.yaml'))['base_sha'])")
./scripts/phase220-target-path-matrix.sh --dry-run --test-hour 14 --cell dallas__spectrum__daytime --replicate 1
```

Expected stdout starts with:

```text
DRY-RUN: bash scripts/phase213-baseline-capture.sh --bind-map spectrum=10.10.110.226 --wans spectrum --tests tcp_12down --flent-duration 30 --host dallas
```

Example live command:

```bash
export PHASE220_BASE_SHA=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('scripts/phase220-matrix.yaml'))['base_sha'])")
./scripts/phase220-target-path-matrix.sh --cell dallas__spectrum__daytime --replicate 1
```

Live runs require Spectrum, the indicated target reflector, and the indicated local hour-of-day window.

## `phase220-matrix-aggregator.py` — cube aggregator

Argparse-generated help:

```text
usage: phase220-matrix-aggregator.py [-h] [--evidence-root EVIDENCE_ROOT]
                                     [--yaml YAML] [--output OUTPUT]

Phase 220 target/path/window matrix aggregator. Reads Phase 220 per-cell
manifests plus Phase 214 signal-sheet outputs and rolls them into a
schema_version=1 cube summary. This file intentionally avoids ``src.wanctl``
imports; JSON output uses an inline tempfile + os.replace atomic write to
preserve the Phase 214 no-shared-helper precedent.

options:
  -h, --help            show this help message and exit
  --evidence-root EVIDENCE_ROOT
  --yaml YAML
  --output OUTPUT
```

Inputs:

- `--evidence-root`: directory containing per-cell `phase220-cell.json` and matching `signal-sheet.json` pairs.
- `--yaml`: matrix definition, defaulting to `scripts/phase220-matrix.yaml`.
- `--output`: optional JSON output path. If omitted, JSON is written to stdout.

Output:

- `matrix-summary.json` is a `schema_version=1` JSON envelope.
- The top-level verdict appears as both `verdict` and `matrix_verdict`.
- `per_cell` records median replicate p99, primary driver, replicate count, per-cell verdict, and cube coordinates.
- `per_target`, `per_path`, and `per_window` provide axis rollups.
- `orthogonal_corroboration`, `reproducing_defect_cells`, and `control_p99_per_window` preserve the evidence used by the decision tree.

Example:

```bash
.venv/bin/python scripts/phase220-matrix-aggregator.py \
  --evidence-root .planning/phases/220-matrix-runner-scope-a1/evidence/ \
  --yaml scripts/phase220-matrix.yaml \
  --output /tmp/matrix-summary.json
```

## `phase220-matrix.yaml` — pre-registered decision rules

Schema fields used by the wrapper and aggregator:

- `phase`, `schema_version`, `base_sha`, `locked_at`
- `driver_allowlist`
- `thresholds` with six locked fields: `canonical_control_p99_kill_ms`, `canonical_min_windows_kill`, `canonical_max_windows_kill_total`, `supplemental_defect_p99_ms`, `supplemental_defect_min_windows`, and `supplemental_carry_multiplier_of_control`
- `windows`: off-peak, daytime, and prime-time hour lists
- `targets`: canonical `dallas` plus supplemental target entries
- `paths`: path names, bind maps, and egress signatures
- `cells`: 18 explicit target/path/window entries
- `statistical`: `mwu` and `bootstrap_ci` settings

The threshold values are read-only inputs for the aggregator. They are pre-registered per CRITERIA-01, and the kill/defect/carry verdict logic reads them at runtime. Do not edit the YAML between cell runs.

## Statistical methods (read-only summary)

- Mann-Whitney U two-sided normal approximation with Wilcoxon mid-rank tie correction.
- Bootstrap 95% percentile CI on median difference with `B=2000` and seed `220`, giving seed-pinned reproducibility.
- Both methods are implemented with the Python standard library; no SciPy, NumPy, or pandas dependency is used.

## Workflow

1. Confirm the SOURCE-FLOOR invariant: `git diff --quiet <base_sha> HEAD -- src/wanctl/ scripts/phase213-* scripts/phase214-*` exits 0. `base_sha` is a source-floor anchor, not an exact-HEAD-equality requirement.
2. Confirm `src/wanctl/`, `scripts/phase213-*`, and `scripts/phase214-*` have no unstaged or staged diff.
3. Choose a cell id from the `cells:` list in `scripts/phase220-matrix.yaml`.
4. Run the wrapper in the appropriate local-hour window for the cell. The wrapper re-verifies source-floor state at every cell start and validates ATT egress when `path_name=att`.
5. Run the aggregator over the accumulated evidence. The aggregator collapses replicates by base cell id using `statistics.median` over replicate p99 values.
6. Read the `matrix-summary.json` `verdict` field.

## What this document does NOT do

- Does not recommend any controller threshold or algorithm change.
- Does not predict later project scope.
- Does not editorialize on whether a verdict is good or bad.
- Does not describe production controller policy.
