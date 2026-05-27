# Phase 214: Measurement Collapse Investigation - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 11 new artifacts (5 scripts + 3 tests + 3 fixtures + 1 report)
**Analogs found:** 10 / 11 (the `214-REPORT.md` is documentation; no source analog needed)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/phase214-flent-matrix.sh` | orchestrator wrapper | request-response (bash → subscripts) | `scripts/phase198-rerun-flent-3run.sh` + `scripts/phase213-baseline-capture.sh` | exact (composition) |
| `scripts/phase214-extract.py` | analyzer (extractor) | file I/O + transform | `scripts/phase198-rerun-flent-3run.sh` lines 240-267 (`extract_median`) | role-match, same data flow |
| `scripts/phase214-align.py` | analyzer (joiner) | transform (multi-source → tabular) | `scripts/phase213-classify.py` lines 88-109 (`_read_ndjson` / `_all_health_rows`) | role-match |
| `scripts/phase214-classify.py` | analyzer (classifier) | transform + verdict | `scripts/phase213-classify.py` (whole file, with the explicit anti-pattern at lines 173-191) | role-match; AVOID zero-fill bug |
| `scripts/phase214-matrix-summary.py` | analyzer (roll-up) | aggregate | `scripts/phase213-classify.py` lines 339-365 (`build_signal_sheet` + `write_markdown`) | role-match |
| `tests/test_phase214_flent_extract.py` | test (subprocess + fixture) | request-response | `tests/test_phase213_classify.py` lines 1-87 | exact |
| `tests/test_phase214_align.py` | test (synthesized NDJSON) | request-response | `tests/test_phase213_classify.py` lines 37-62 (`_minimal_*_run` helper) | exact |
| `tests/test_phase214_classify.py` | test (rubric/verdict) | request-response | `tests/test_phase213_classify.py` parametrize block lines 75-86 | exact |
| `tests/fixtures/phase214/sample-tcp_12down.flent.gz` | test fixture | static binary | repo-root `tcp_ndown-2026-04-16T035903.274492.*.flent.gz` (already on disk) | exact (copy verbatim) |
| `tests/fixtures/phase214/sample-bad-p99-health.ndjson` | test fixture | synthesized NDJSON | `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/spectrum/tcp_12down/health-spectrum.ndjson` | exact (subset the live row shape) |
| `tests/fixtures/phase214/sample-journal-window.ndjson` | test fixture | synthesized NDJSON | journalctl `--output=json` shape (Research §Common Operation 3) | role-match |
| `.planning/phases/214-measurement-collapse-investigation/214-REPORT.md` | documentation | n/a | `.planning/phases/213-experience-baseline-harness/213-REPORT.md` | structural; no code excerpt needed |

## Pattern Assignments

### `scripts/phase214-flent-matrix.sh` (orchestrator wrapper, request-response)

**Primary analog:** `scripts/phase198-rerun-flent-3run.sh` (window-hour gate + dry-run discipline)
**Secondary analog:** `scripts/phase213-baseline-capture.sh` (the orchestrator this wraps; same `--bind-map`/`--wans`/`--tests`/`--evidence-root` surface)

**Shebang + strict-mode pattern** (`phase213-baseline-capture.sh` lines 1-16):
```bash
#!/usr/bin/env bash
#
# Phase 214 measurement-collapse matrix wrapper.
# Thin per-window invocation of phase213-baseline-capture.sh narrowed to
# --wans spectrum --tests tcp_12down. D-01/D-02/D-03 bounds. D-14 read-only.

set -euo pipefail
```

**Argument parsing + usage block** (`phase198-rerun-flent-3run.sh` lines 11-30, 49-109): use the `while [[ $# -gt 0 ]]` + `case` loop with `--help`/`-h` printing a heredoc. Mirror exactly — operators expect this shape.

**Window-hour gate with `--dry-run` + `--test-hour`** (`phase198-rerun-flent-3run.sh` lines 111-156). This is the **most important** pattern to copy verbatim, then extend with three windows instead of one:
```bash
if [[ -n "${TEST_HOUR}" && "${DRY_RUN}" != "1" ]]; then
    echo "REFUSED: --test-hour is only honored with --dry-run. Production runs read live wall clock." >&2
    exit 7
fi

if [[ "${DRY_RUN}" == "1" && -n "${TEST_HOUR}" ]]; then
    LOCAL_HOUR="${TEST_HOUR}"
else
    LOCAL_HOUR="$(date +%H)"
fi

case "$WINDOW" in
  off-peak)
    if (( 10#$LOCAL_HOUR < 1 || 10#$LOCAL_HOUR > 5 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside off-peak window 01..05 local" >&2
      exit 2
    fi ;;
  daytime)
    if (( 10#$LOCAL_HOUR < 10 || 10#$LOCAL_HOUR > 16 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside daytime window 10..16 local" >&2
      exit 2
    fi ;;
  prime-time)
    if (( 10#$LOCAL_HOUR < 19 || 10#$LOCAL_HOUR > 22 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside prime-time window 19..22 local" >&2
      exit 2
    fi ;;
esac
```

**Source-bind egress probe (refuse-on-mismatch)** (`phase198-rerun-flent-3run.sh` lines 270-289 — note phase198 uses `ipinfo.io/json` for org+ip; `phase213-baseline-capture.sh` lines 329-334 uses `ifconfig.io` for ip-only). Phase 214 inherits whichever its delegated orchestrator runs (probe is already inside `phase213-baseline-capture.sh:328-334`), so the wrapper itself does NOT re-probe — but it MUST still abort if the orchestrator exits nonzero. Pattern:
```bash
EVIDENCE_ROOT=".planning/phases/214-measurement-collapse-investigation/evidence"
bash scripts/phase213-baseline-capture.sh \
  --bind-map spectrum=10.10.110.226 \
  --wans spectrum \
  --tests tcp_12down \
  --flent-duration "$DURATION" \
  --host dallas \
  --evidence-root "$EVIDENCE_ROOT"
```

**Sidecar manifest write** (`phase213-baseline-capture.sh` lines 322-324 pattern for `jq -n` sidecar):
```bash
RUN_DIR="$(ls -1d "${EVIDENCE_ROOT}"/RUN-* | sort | tail -n 1)"
jq -n --arg window "$WINDOW" --arg duration "$DURATION" \
   '{phase: 214, window: $window, flent_duration_sec: ($duration|tonumber)}' \
   > "${RUN_DIR}/phase214-window.json"
```

**Failure trap + partial-summary** (`phase198-rerun-flent-3run.sh` lines 181-202, 210). Use `trap 'write_partial_summary' ERR` for any orchestrator step that can fail (gates / health preflight / flent / sqlite); record `failure_stage` so the operator knows which window-resource was burned.

**Read-only invariant grep guard (SAFE-05 mirror)** (`phase198-rerun-flent-3run.sh` lines 169-176). Phase 214's equivalent: assert `git diff` against the phase base SHA produces zero edits under `src/wanctl/` before any live run. This is the D-14 hard guard:
```bash
ATTEMPT_FAILED_STAGE="safe05"
if ! git diff --quiet "${PHASE214_BASE_SHA}..HEAD" -- src/wanctl/; then
    echo "REFUSED: D-14 violated — src/wanctl/ diff non-empty vs ${PHASE214_BASE_SHA}" >&2
    exit 4
fi
```

---

### `scripts/phase214-extract.py` (analyzer/extractor, file I/O + transform)

**Primary analog:** `scripts/phase198-rerun-flent-3run.sh` lines 240-267 (`extract_median()` inline Python heredoc) — proven stdlib-only `gzip` + `json` + `statistics` pattern. Phase 214 lifts this into a standalone module and extends with quantile computation.
**Reference (do NOT copy):** `scripts/phase213-classify.py` lines 173-191 (`_flent_summary`) is the **anti-pattern** — looks for non-existent `flent-summary.json` and silently returns `{}`, leading to `flent_p99=0.0` zero-fill at lines 200-203. Phase 214 MUST fail closed instead.

**Stdlib-only header + module docstring pattern** (`scripts/phase213-classify.py` lines 1-13):
```python
#!/usr/bin/env python3
"""Phase 214 flent latency/throughput extractor.

Reads a .flent.gz artifact, extracts ping latency series from raw_values
(authoritative) and TCP download throughput from results, computes
p50/p95/p99. Fails closed (FlentExtractionError) when expected keys are
missing — D-09/D-10.

Invariants: stdlib-only; no wanctl imports; never returns zero for a missing
series (the Phase 213 _flent_summary zero-fill bug).
"""
from __future__ import annotations
```

**Working extractor pattern** (synthesized from `phase198-rerun-flent-3run.sh:240-267` extended per Research §Pattern 1):
```python
import gzip
import json
import statistics
from datetime import datetime
from pathlib import Path


class FlentExtractionError(RuntimeError):
    """Raised when expected flent series is missing or empty (D-10 fail-closed)."""


def extract_flent_latency(path: Path) -> dict:
    with gzip.open(path, "rt") as fh:
        data = json.load(fh)

    raw = data.get("raw_values", {})
    series = raw.get("Ping (ms) ICMP")
    if not isinstance(series, list) or not series:
        raise FlentExtractionError(
            f"{path}: raw_values['Ping (ms) ICMP'] missing or empty"
        )

    values = [float(s["val"]) for s in series if isinstance(s, dict) and "val" in s]
    if not values:
        raise FlentExtractionError(f"{path}: ping series has no usable 'val' entries")

    values.sort()
    n = len(values)
    return {
        "p50_ms": values[n // 2],
        "p95_ms": values[min(n - 1, int(n * 0.95))],
        "p99_ms": values[min(n - 1, int(n * 0.99))],
        "min_ms": min(values), "max_ms": max(values),
        "mean_ms": statistics.mean(values),
        "sample_count": n,
        # ... + window_start_utc, window_end_utc from metadata.T0/TOTAL_LENGTH
    }
```

**Throughput extractor with key fallback chain** (mirror `phase198-rerun-flent-3run.sh:249-265` `preferred` loop; same `("TCP download sum", "TCP totals", "TCP download")` order, also try `"TCP download avg"`).

**argparse / main pattern** (`scripts/phase213-classify.py` lines 368-388):
```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flent-gz", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = {
        "latency": extract_flent_latency(args.flent_gz),
        "throughput": extract_flent_throughput(args.flent_gz),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

### `scripts/phase214-align.py` (joiner, multi-source → tabular)

**Primary analog:** `scripts/phase213-classify.py` lines 88-109 (`_read_ndjson`, `_all_health_rows`) for NDJSON ingestion.
**Reference for journal pull:** Research §Common Operation 3 (ssh `journalctl --output=json --since/--until`).
**Reference for /health row shape:** the live NDJSON file at `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/spectrum/tcp_12down/health-spectrum.ndjson` defines the exact key set — same projection as `scripts/phase213-health-poller.sh` lines 166-221 (verbatim list of consumable fields).

**NDJSON read pattern** (`scripts/phase213-classify.py` lines 88-95):
```python
def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
```

**Aligner core (Research §Pattern 3, plus per-second bucket)**: open `.flent.gz`, bucket raw_values pings by `int(p["t"])`, key health rows by `int(float(r.get("sampled_utc") or r.get("t_wall_unix") or 0))`, emit one row per integer second across `[t_start - pre_buf, t_end + post_buf]`. Field set MUST be a strict subset of what `phase213-health-poller.sh:166-221` emits — that is the contract.

**Critical fields to surface in each aligned row** (verified against `phase213-health-poller.sh` lines 166-220):
- `health_status`, `download_state`, `download_state_reason`
- `measurement_state`, `measurement_successful_count`, `measurement_stale`, `measurement_staleness_sec`
- `signal_outlier_rate`, `signal_confidence`, `signal_warming_up`
- `baseline_rtt_ms`, `load_rtt_ms`, `load_rtt_delta_us`
- `cake_dl_peak_delay_us`, `cake_dl_drop_rate`, `cake_dl_backlog_suppressed_count`
- `arb_active_primary_signal`, `arb_refractory_active`, `arb_rtt_confidence`
- `irtt_rtt_mean_ms`, `irtt_loss_up_pct`, `irtt_loss_down_pct`, `irtt_asymmetry_ratio`

**Clock-skew tolerance** (Research §Pitfall 4): when aligning journal events to per-second rows, use a ±1s tolerance and record `dev_vm_unix - ssh cake-shaper date +%s.%N` skew in the per-run sidecar.

---

### `scripts/phase214-classify.py` (classifier + verdict, transform)

**Primary analog (structure ONLY):** `scripts/phase213-classify.py` whole-file shape — module docstring, constant block, per-driver analyzer functions, `build_signal_sheet`/`recommend` aggregator, `write_markdown` + argparse / main.
**EXPLICIT ANTI-PATTERN — DO NOT COPY:** `scripts/phase213-classify.py` lines 173-191 (`_flent_summary`) and its caller at lines 200-203. That code returns `{}` on missing file then defaults to `0.0` for `flent_p99`/`flent_median`. Phase 214 MUST import `extract_flent_latency` from `phase214-extract.py` and let `FlentExtractionError` propagate.
**Reference for driver rubric:** Research §Pattern 4 (six-driver table) and Research §Common Operation 1 (skeleton).

**Constants block pattern** (`scripts/phase213-classify.py` lines 26-44):
```python
# Driver thresholds (mirrored from Phase 213 BUCKET_2_PEAK_DELAY_US=50000 etc.;
# Phase 214 may adjust against matrix evidence but stays observational).
DRIVER_P99_FAIL_MS = 1000          # D-06 fail gate
DRIVER_P99_PASS_MS = 500           # D-06 pass gate
DRIVER_REFLECTOR_LOSS_MIN_CYCLES = 1
DRIVER_STALE_RTT_MIN_CYCLES = 3
DRIVER_CAKE_PEAK_DELAY_US = 50000   # reuse Phase 213 BUCKET_2_PEAK_DELAY_US
```

**Per-driver analyzer signature** (mirror `scripts/phase213-classify.py` lines 124-205 shape; one function per driver returning `{"fired": bool, "evidence": str, "score": int, ...}`). Skeleton from Research §Common Operation 1.

**Pass/fail/ambiguous verdict gate** (Research §Pattern 4 table). Verdict per window:
```python
def verdict_for_window(latency: dict, drivers: dict) -> str:
    p99 = latency["p99_ms"]
    any_driver_fired = any(d["fired"] for d in drivers.values())
    if p99 < DRIVER_P99_PASS_MS and not drivers.get("reflector_loss", {}).get("fired") \
       and not drivers.get("icmp_udp_divergence", {}).get("fired"):
        return "pass"
    if p99 > DRIVER_P99_FAIL_MS and any_driver_fired:
        return "fail"
    return "ambiguous"
```

**Output pattern** (`scripts/phase213-classify.py` lines 339-388): emit `signal-sheet.json` + `signal-sheet.md` per window AND a top-level `driver-classification.json`. Reuse `write_markdown` shape.

---

### `scripts/phase214-matrix-summary.py` (roll-up, aggregate)

**Primary analog:** `scripts/phase213-classify.py` lines 339-365 (`build_signal_sheet` + `recommend` + `write_markdown`) plus Research §Open Question 4 schema sketch.

**Output schema (Research §Open Question 4 default — planner should adopt):**
```python
{
    "phase": 214,
    "verdict": "pass" | "fail" | "ambiguous",
    "primary_driver": str | None,
    "ranked_drivers": list[str],
    "windows": [
        {"window": "off-peak", "run_dir": "...", "p99_ms": float, "verdict": str, "drivers": [...]},
        {"window": "daytime", ...},
        {"window": "prime-time", ...},
    ],
    "signal_disposition": "form_b" | "form_c" | "none",
}
```

**Iteration pattern** (mirror `_all_health_rows` lines 98-109): walk `evidence/RUN-*/` directories in lexical order to preserve window discovery determinism.

---

### `tests/test_phase214_flent_extract.py` (unit, request-response)

**Primary analog:** `tests/test_phase213_classify.py` (entire file) — subprocess-driven classifier invocation with `pytest.skip` if script not yet built.

**Imports + REPO_ROOT pattern** (`tests/test_phase213_classify.py` lines 1-11):
```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR = REPO_ROOT / "scripts/phase214-extract.py"
FIXTURES = REPO_ROOT / "tests/fixtures/phase214"
```

**Subprocess runner with skip-when-missing pattern** (`tests/test_phase213_classify.py` lines 23-34):
```python
def _run_extractor(flent_gz: Path, tmp_path: Path) -> dict:
    if not EXTRACTOR.exists():
        pytest.skip("scripts/phase214-extract.py not built yet")
    out = tmp_path / "extracted.json"
    result = subprocess.run(
        [sys.executable, str(EXTRACTOR), "--flent-gz", str(flent_gz), "--output-json", str(out)],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(out.read_text())
```

**Required tests** (per Research §Phase Requirements → Test Map):
- `test_extract_known_good` — uses `tests/fixtures/phase214/sample-tcp_12down.flent.gz`, asserts `p50_ms > 0`, `p99_ms >= p50_ms`, `sample_count > 0`.
- `test_extract_missing_raw_fails_closed` — synthesize an empty `.flent.gz` (or one without `raw_values['Ping (ms) ICMP']`), assert the extractor exits nonzero AND stderr contains `FlentExtractionError` or `missing or empty`.
- `test_extract_throughput` — asserts `throughput_median_mbps > 0` and `series_key_used` is one of the documented keys.

---

### `tests/test_phase214_align.py` (unit, request-response)

**Primary analog:** `tests/test_phase213_classify.py` lines 37-62 (`_minimal_ul_ceiling_run` helper that synthesizes NDJSON inline).

**Synthesized NDJSON helper pattern** (adapt from lines 37-62):
```python
def _synthesize_health_ndjson(tmp_path: Path, t0_unix: int, duration: int) -> Path:
    out = tmp_path / "health-spectrum.ndjson"
    rows = []
    for i in range(duration):
        rows.append({
            "t_wall": ...,  # ISO8601
            "wan": "spectrum",
            "status": "healthy",
            "download_state": "GREEN",
            "measurement_state": "fresh" if i % 4 != 0 else "stale",
            "measurement_successful_count": 3 if i % 4 != 0 else 0,
            # ... full superset of phase213-health-poller jq projection
        })
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return out
```

**Required tests:**
- `test_align_basic` — produces one row per second, in_flent_window flag correct at boundaries.
- `test_align_ping_bucketing` — raw_values pings with non-integer `t` field bucket by `int(t)`; `ping_max_ms` is max within bucket.

---

### `tests/test_phase214_classify.py` (unit, request-response)

**Primary analog:** `tests/test_phase213_classify.py` lines 75-86 (parametrized per-bucket fixture flag test).

**Parametrize pattern**:
```python
@pytest.mark.parametrize(
    ("scenario", "expected_driver"),
    [
        ("reflector_loss_window", "reflector_loss"),
        ("protocol_divergence_window", "icmp_udp_divergence"),
        ("stale_rtt_window", "stale_cached_rtt"),
    ],
)
def test_classify_driver_identification(tmp_path, scenario, expected_driver):
    aligned = _synthesize_aligned_window(tmp_path, scenario)
    result = _run_classifier(aligned, tmp_path)
    assert result["primary_driver"] == expected_driver
```

**Verdict gate tests** (D-06 boundaries):
- `test_verdict_pass` — p99=300ms, no drivers → "pass"
- `test_verdict_fail` — p99=1500ms + reflector_loss fires → "fail"
- `test_verdict_ambiguous_zone` — p99=700ms → "ambiguous"
- `test_classify_multi_driver_ranking` — two drivers fire; assert ranked order by score.

---

### `tests/fixtures/phase214/sample-tcp_12down.flent.gz`

**Source:** Copy verbatim from `/home/kevin/projects/wanctl/tcp_ndown-2026-04-16T035903.274492.prod-tcp-ndown12-hammer-2026-04-16T0359.flent.gz` (already in repo root; verified by Research to contain real `raw_values['Ping (ms) ICMP']` with 647 entries).

**Provenance note:** Add a `tests/fixtures/phase214/README.md` (1-2 lines) recording the source path and date so future-me can re-derive it.

---

### `tests/fixtures/phase214/sample-bad-p99-health.ndjson`

**Source:** Synthesize. Use the live NDJSON at `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/spectrum/tcp_12down/health-spectrum.ndjson` as the schema reference (read one row, copy the key set, mutate values to create a 30-second window with `download_state=GREEN` throughout and `measurement_successful_count` cycling `0,0,0,2` to simulate collapse).

---

### `tests/fixtures/phase214/sample-journal-window.ndjson`

**Source:** Synthesize. Each line is the `journalctl --output=json` shape: `{"__REALTIME_TIMESTAMP": "1779920851000000", "MESSAGE": "Ping to 8.8.8.8 failed", "_SYSTEMD_UNIT": "wanctl@spectrum.service"}`. Include at least:
- 3 lines with `Ping to .* failed` from 3 distinct IPs within a 10s sub-window (drives `reflector_loss`)
- 1 line with `ICMP deprioritized` (drives `icmp_udp_divergence`)

---

### `.planning/phases/214-measurement-collapse-investigation/214-REPORT.md`

**Primary structural analog:** `.planning/phases/213-experience-baseline-harness/213-REPORT.md` (matrix verdict + ranked next-phase recommendation shape). No code excerpt needed; the planner sets the section structure.

**Required sections** (per MEAS-02, MEAS-03, D-12, D-13):
1. Matrix verdict (`pass` / `fail` / `ambiguous`) with per-window p99 table
2. Driver classification (primary + ranked) with cited evidence
3. **Signal Disposition** (Form B + Form C documented; Form A described as "future-phase candidate" only — D-12)
4. Folded todo decision (close as "not reproduced" OR carry forward with narrower scope)
5. v1.46 safety attestation: no `src/wanctl/` edits, no production mutation (D-14)

---

## Shared Patterns

### Pattern: Read-only invariant guard (cross-cutting)
**Source:** `scripts/phase198-rerun-flent-3run.sh` lines 169-176 (SAFE-05 protected-source diff)
**Apply to:** `scripts/phase214-flent-matrix.sh` (gate before any live run); also asserted by `tests/test_phase214_*.py` indirectly via the MEAS-03 structural grep test.
```bash
if ! git diff --quiet "${PHASE_BASE_SHA}..HEAD" -- src/wanctl/; then
    echo "REFUSED: src/wanctl/ diff non-empty vs ${PHASE_BASE_SHA}" >&2
    exit 4
fi
```

### Pattern: Source-bind egress refusal
**Source:** `scripts/phase213-baseline-capture.sh` lines 329-334 (Spectrum egress signature must equal `70.123.224.169`)
**Apply to:** Inherited automatically by phase214-flent-matrix.sh through its delegation. Do NOT re-implement in the wrapper — let the orchestrator refuse and propagate.
```bash
egress="$(curl -s --interface "$bind" --max-time 5 https://ifconfig.io || echo unknown)"
if [[ "$WAN" == "spectrum" && "$egress" != "70.123.224.169" ]]; then
  echo "REFUSED: spectrum egress signature mismatch via bind=$bind (got $egress, expected 70.123.224.169)" >&2
  exit 1
fi
```

### Pattern: Fail-closed stdlib analyzer
**Source:** Research §Pattern 1; extends `scripts/phase198-rerun-flent-3run.sh` lines 264-265 (`raise SystemExit("ERROR_NO_TCP_DOWNLOAD_SUM_SERIES")`).
**Apply to:** `phase214-extract.py`, `phase214-align.py`, `phase214-classify.py`. **Never** return zero or `{}` for a missing series. Always raise a typed exception with the file path in the message.
```python
class FlentExtractionError(RuntimeError):
    """Raised when expected flent series is missing or empty (D-10 fail-closed)."""
```

### Pattern: Subprocess-driven test with `pytest.skip` fallback
**Source:** `tests/test_phase213_classify.py` lines 23-34
**Apply to:** All `tests/test_phase214_*.py` files. Lets Wave 0 tests be checked in before the scripts exist (planner can stage tests-first development).

### Pattern: REPO_ROOT discovery
**Source:** `tests/test_phase213_classify.py` line 10 (`REPO_ROOT = Path(__file__).resolve().parent.parent`) and `scripts/phase213-classify.py` lines 47-48 (`_repo_root`)
**Apply to:** All Phase 214 Python scripts and tests for path-agnostic invocation.

### Pattern: `.venv/bin/python3` invocation (project CLAUDE.md mandate)
**Source:** CLAUDE.md "Development Commands"; `scripts/phase198-rerun-flent-3run.sh` line 241, 362, 401 always uses `.venv/bin/python3`.
**Apply to:** Any bash that invokes Python scripts in Phase 214 (the matrix wrapper if it post-processes; the planner's CI commands).

### Pattern: jq-emitted JSON manifests with explicit phase/run_id/window
**Source:** `scripts/phase213-baseline-capture.sh` lines 182-209 (`make_manifest`); `scripts/phase198-rerun-flent-3run.sh` lines 376-394 (per-attempt manifest)
**Apply to:** `phase214-flent-matrix.sh` sidecar manifest write; `phase214-matrix-summary.py` top-level roll-up. Always include `phase`, `started_utc`, `ended_utc`, `git_head_sha`, `mutation_posture`.

### Pattern: NDJSON poller reuse (DO NOT re-implement)
**Source:** `scripts/phase213-health-poller.sh` (already wired into `phase213-baseline-capture.sh` per-test via `start_pollers` lines 269-276)
**Apply to:** Phase 214 inherits this through the wrapper. The poller already emits the rich row shape phase214-align.py consumes — no new field projection is needed.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All 11 artifacts have analog patterns in the existing codebase. The 214-REPORT.md is documentation and uses Phase 213's report as a structural reference, not a code analog. |

---

## Metadata

**Analog search scope:** `scripts/phase{191,198,213,214}-*`, `scripts/soak-*`, `tests/test_phase213_*`, `tests/conftest.py`, `tests/fixtures/phase213/`, `src/wanctl/health_check.py` (read-only field reference).
**Files scanned:** 9 source files read; ~1900 LOC analyzed.
**Pattern extraction date:** 2026-05-27
**Key insight:** Phase 214 is ~85% composition of existing Phase 198/213 patterns. The two genuinely new patterns are (a) the corrected stdlib `.flent.gz` `raw_values`-based latency extractor and (b) the per-second multi-source aligner. Everything else has a working precedent in the codebase that the planner can cite verbatim.
