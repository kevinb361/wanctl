# Phase 206: A/B replay harness + rollback gates — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 9 new files (0 modifications — SAFE-09 forbids any `src/wanctl/` edits in Phase 206)
**Analogs found:** 9 / 9

**SAFE-09 invariant respected:** Zero target files under `src/wanctl/`. All `src/wanctl/` references below are read-only imports from new harness/test code. The Phase 205 5-file allowlist (`cake_signal.py`, `cake_params.py`, `backends/linux_cake.py`, `backends/netlink_cake.py`, `check_config_validators.py`) is unchanged.

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `tests/test_phase_206_replay.py` | test (replay equivalence + A/B equivalence) | in-process replay, deterministic | `tests/test_phase_193_replay.py` (and 195's import pattern) | exact (role + data flow) |
| `tests/test_phase206_predeploy_gate.py` | test (subprocess gate invocation) | bash-shell-out, env-overridden, tmp-path fixtures | `tests/test_phase201_predeploy_gate.py` | exact |
| `tests/fixtures/phase206_replay_corpus.py` | fixture loader (frozen dataclass + NDJSON parser) | file-I/O → dataclass list | `tests/fixtures/phase201_replay_corpus.py` | exact |
| `tests/fixtures/phase206_golden_capture.ndjson` | committed deterministic NDJSON fixture | static data | `tests/fixtures/phase_203_synthetic_capture.ndjson` (shape) + `20260509T183037Z/soak-capture.ndjson` (field set) | role-match (synthetic-generated fixture vs derived-from-real fixture) |
| `scripts/phase206-ab-replay.py` | harness CLI + importable lib | NDJSON in → A/B summary JSON out | None exact in repo. Closest: `scripts/phase198-rerun-flent-3run.sh:240-267` (gzip+json+statistics flent parser) + Phase 193 `_replay()` shape | partial — plumbing of two existing primitives, no single analog |
| `scripts/phase206-predeploy-gate.sh` | operator-facing gate wrapper | bash exit-code contract, env override, subprocess into Python helper | `scripts/phase201-predeploy-gate.sh` | exact (operator must not relearn exit semantics) |
| `scripts/phase206-gate-check.py` | gate-trigger Python core (computes rates, compares to baseline) | JSON/NDJSON in → exit code + log line | None exact. Closest: the `yaml_probe()` embedded Python in `phase201-predeploy-gate.sh:81-105` (hoisted into a standalone file) | role-match (helper-called-from-bash; same exit-code semantics) |
| `.planning/phases/206-…/PHASE-205-ROLLBACK-GATES.md` | operator-readable rollback doc | static markdown | `.planning/phases/205-…/205-04-SUMMARY.md` (narrative-with-evidence shape, fenced-block evidence) | role-match (closeout/operator doc, not rollback-specific) |
| `.planning/phases/206-…/golden-fixture-provenance.md` | fixture provenance doc | static markdown | `tests/fixtures/phase201_replay_corpus.py:1-21` docstring (origin pointer) + `205-04-SUMMARY.md` evidence shape | role-match (no existing standalone provenance doc; closest is in-source docstring) |

**No analog (acceptable):** The two `.planning/` markdown docs are a new doc genre. The planner should follow the evidence-with-fenced-blocks shape from `205-04-SUMMARY.md` rather than invent a new format.

---

## Pattern Assignments

### `tests/test_phase_206_replay.py` (test, in-process replay)

**Analog:** `tests/test_phase_193_replay.py` (canonical primitives) + `tests/test_phase_195_replay.py:34-42` (the import-from-193 reuse pattern).

**Imports pattern** — Phase 195 already proved the reuse path. New file MUST follow exactly, swapping shape token from `"spectrum"`/`"att"` to `"diffserv4"`/`"besteffort"`:

```python
# Source: tests/test_phase_195_replay.py:14-42
from __future__ import annotations

# ruff: noqa: I001
import re
from pathlib import Path

import pytest

from wanctl.cake_signal import CakeSignalConfig, CakeSignalProcessor, CakeSignalSnapshot
from wanctl.queue_controller import QueueController

from tests.test_phase_193_replay import (
    EXPECTED_ATT_RATES,
    EXPECTED_SPECTRUM_RATES,
    EXPECTED_ZONES,
    TRACE,
    _fresh_controller,
    _replay,
    _snap,
)
```

For Phase 206, the new file imports `_replay` and `_snap` from 193 verbatim and adds Phase 206-specific `_pre_controller()` / `_post_controller()` factories (940 ceiling diffserv4 vs 920 ceiling besteffort). It MUST NOT redefine `_replay` or `_snap` — re-definition is behavior drift risk per RESEARCH §"Don't Hand-Roll".

**Core `_replay()` pattern (verbatim — REUSE, do not redefine)** — Source: `tests/test_phase_193_replay.py:188-204`:

```python
def _replay(
    controller: QueueController, trace: list[tuple[float, float]], snapshot: CakeSignalSnapshot
) -> tuple[list[str], list[int]]:
    zones: list[str] = []
    rates: list[int] = []
    for baseline_rtt, load_rtt in trace:
        zone, rate, _ = controller.adjust_4state(
            baseline_rtt=baseline_rtt,
            load_rtt=load_rtt,
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
            cake_snapshot=snapshot,
        )
        zones.append(zone)
        rates.append(rate)
    return zones, rates
```

**Controller-factory pattern** — Source: `tests/test_phase_193_replay.py:123-153`. New file's `_pre_controller()` / `_post_controller()` mirror the `"spectrum"`/`"att"` branching shape: same param names, only `ceiling` differs (940→pre, 920→post), all other knobs identical (SAFE-09: no threshold/dwell/deadband edits):

```python
# Source: tests/test_phase_193_replay.py:140-153 (spectrum factory — copy shape verbatim, vary only ceiling)
return QueueController(
    name="download",
    floor_green=800_000_000,
    floor_yellow=600_000_000,
    floor_soft_red=500_000_000,
    floor_red=400_000_000,
    ceiling=920_000_000,          # ← only this varies pre (940M) vs post (920M)
    step_up=10_000_000,
    factor_down=0.85,
    factor_down_yellow=0.96,
    green_required=5,
    dwell_cycles=2,
    deadband_ms=0.0,
)
```

**`_snap()` pattern with tin-count variance** — Source: `tests/test_phase_193_replay.py:156-185`. Phase 206 extends this by varying tin count (1 for besteffort, 4 for diffserv4); the per-tin field-set is unchanged. Per Phase 205's TOPO-01 refactor, `cake_signal.py` is already tin-agnostic, so the same kernel-level snapshot drives both layouts:

```python
# Source: tests/test_phase_193_replay.py:156-185 — single-tin BestEffort
return CakeSignalSnapshot(
    drop_rate=0.0,
    total_drop_rate=0.0,
    backlog_bytes=0,
    peak_delay_us=0,
    tins=(
        TinSnapshot(
            name="BestEffort",
            dropped_packets=0, drop_delta=0, backlog_bytes=0, peak_delay_us=0,
            ecn_marked_packets=0,
            avg_delay_us=avg_delay_us, base_delay_us=base_delay_us,
            delay_delta_us=max_delay_delta_us,
        ),
    ),
    cold_start=False,
    avg_delay_us=avg_delay_us,
    base_delay_us=base_delay_us,
    max_delay_delta_us=max_delay_delta_us,
)
```

For diffserv4, the planner should generate a 4-tuple of `TinSnapshot` (names `T0..T3` or `Bulk/BestEffort/Video/Voice`) with identical per-tin payloads; see RESEARCH §"A/B harness skeleton" `_snap_for()` sketch (lines 425-440).

**EXPECTED-table literal style** — Source: `tests/test_phase_193_replay.py:14-120`. The replay-equivalence assertion shape is a 24-element `TRACE` + parallel `EXPECTED_ZONES` (24 strings) + per-shape `EXPECTED_*_RATES` (24 ints). Phase 206's test MUST use the same literal-table style: a fresh `EXPECTED_DIFFSERV4_ZONES` / `EXPECTED_BESTEFFORT_ZONES` (likely identical given SAFE-09) + per-config `EXPECTED_*_RATES`. Assertion:

```python
# Source: tests/test_phase_193_replay.py:223-226
assert zones_b == EXPECTED_ZONES
assert rates_b == EXPECTED_SPECTRUM_RATES
```

---

### `tests/test_phase206_predeploy_gate.py` (test, subprocess gate invocation)

**Analog:** `tests/test_phase201_predeploy_gate.py` (verbatim scaffolding, only env-var name and gate-script path change).

**Path constants + fixture pattern** — Source: `tests/test_phase201_predeploy_gate.py:12-21`:

```python
GATE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "phase201-predeploy-gate.sh"
DEPLOY_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "deploy.sh"

@pytest.fixture
def fake_remote_yaml(tmp_path):
    """Create tmp YAML and short-circuit the gate's SSH probe via env override."""
    assert GATE_SCRIPT.exists()
    return tmp_path
```

Phase 206 replaces `GATE_SCRIPT` path with `phase206-predeploy-gate.sh` and the env-override name from `PHASE201_LOCAL_YAML_OVERRIDE` → `PHASE206_LOCAL_BASELINE_OVERRIDE` (the name already chosen in RESEARCH §"Pattern 2" and §"Locked Operator Decisions"). Drop the deploy-script integration fixture unless the planner explicitly wires Phase 206 into `deploy.sh` (per RESEARCH the gate is operator-invoked, not deploy-script-wired — Phase 209 is when it integrates).

**Subprocess invocation pattern** — Source: `tests/test_phase201_predeploy_gate.py:23-25`:

```python
def _run_gate(yaml_path: Path) -> subprocess.CompletedProcess[bytes]:
    env = {"PHASE201_LOCAL_YAML_OVERRIDE": str(yaml_path), "PATH": "/usr/bin:/bin"}
    return subprocess.run(["bash", str(GATE_SCRIPT)], env=env, capture_output=True, timeout=15)
```

Phase 206's `_run_gate()` accepts a baseline `Path` and a candidate `Path` (both A/B summary JSON), sets `PHASE206_LOCAL_BASELINE_OVERRIDE` to short-circuit the SSH/journalctl probe, and passes `--baseline` / `--candidate` as CLI args.

**Pass-case assertion shape** — Source: `tests/test_phase201_predeploy_gate.py:29-44`:

```python
class TestPredeployGate:
    def test_clean_yaml_passes(self, fake_remote_yaml):
        yaml_path = fake_remote_yaml / "spectrum.yaml"
        yaml_path.write_text(textwrap.dedent(...).strip())
        result = _run_gate(yaml_path)
        assert result.returncode == 0, result.stderr.decode()
```

Phase 206 must include the **dry-run-against-baseline-exits-zero** test required by Success Criterion 4 of the ROADMAP: `_run_gate(baseline=X, candidate=X)` exits 0 by construction (X compared to itself = 0% delta).

**Block-case assertion shape** — Source: `tests/test_phase201_predeploy_gate.py:46-61`:

```python
def test_target_bloat_ms_in_upload_blocks(self, fake_remote_yaml):
    ...
    result = _run_gate(yaml_path)
    assert result.returncode == 1
    assert b"target_bloat_ms" in result.stdout + result.stderr
```

Phase 206 needs three analogous block tests — one per rollback trigger (RRUL p99 >5%, restart-rate >10%, transition-rate >10%; thresholds per RESEARCH "Locked Operator Decisions" deferred-to-planner row).

---

### `tests/fixtures/phase206_replay_corpus.py` (fixture loader)

**Analog:** `tests/fixtures/phase201_replay_corpus.py` — verbatim shape (frozen dataclass + `_parse_line` + `_load_ndjson`).

**Module-docstring + path-constant pattern** — Source: `tests/fixtures/phase201_replay_corpus.py:1-21`:

```python
"""Phase 201 replay corpus loader and synthetic-trace generator.

Single source of truth for replay-test inputs. All Phase 201 test files
that need historical or synthetic UL traces import from this module.

Origin: RESEARCH.md Section 8 (Replay-Test Corpus); PATTERNS.md
'tests/test_phase_201_replay.py (NEW)'.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE200_ARCHIVE = REPO_ROOT / ".planning/milestones/v1.41-phases/200-per-direction-rtt-bloat-thresholds"
ATTEMPT3_NDJSON_PATH = PHASE200_ARCHIVE / "canary/20260504T133207Z/loaded_capture.ndjson"
```

Phase 206 swaps `PHASE200_ARCHIVE` for the in-tree `GOLDEN_NDJSON = Path(__file__).resolve().parent / "phase206_golden_capture.ndjson"` per RESEARCH §"Loading a deterministic NDJSON fixture" (lines 374-376) — the fixture is committed in-repo, not in `.planning/`.

**Frozen dataclass pattern** — Source: `tests/fixtures/phase201_replay_corpus.py:23-32`:

```python
@dataclass(frozen=True)
class ReplaySample:
    ts: str
    baseline_rtt_ms: float | None
    load_rtt_ms: float | None
    upload_state: str
    upload_current_rate_mbps: float
    cake_backlog_bytes: int | None
    cake_cold_start: bool | None
```

Phase 206 names this `GoldenSample` (per RESEARCH §"Loading a deterministic NDJSON fixture") with field set tuned for the A/B harness's `_snap_for(sample, tin_layout)` consumer: `ts`, `baseline_rtt_ms`, `load_rtt_ms`, `cake_avg_delay_us`, `cake_base_delay_us`. Frozen is required — RESEARCH §"Don't Hand-Roll" explicitly says "Frozen dataclasses avoid mutation surprises across two replay runs."

**NDJSON line-parse pattern** — Source: `tests/fixtures/phase201_replay_corpus.py:34-68`:

```python
def _parse_line(raw: str) -> ReplaySample | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    wans = obj.get("wans") or []
    ...

def _load_ndjson(path: Path) -> list[ReplaySample]:
    if not path.exists():
        return []
    out: list[ReplaySample] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            sample = _parse_line(line)
            if sample is not None:
                out.append(sample)
    return out
```

Phase 206 simplifies — the golden NDJSON is repo-controlled and well-formed, so `_load_ndjson` does NOT need the `.exists() → []` graceful path; it should hard-fail on missing fixture (the file is committed; absence means a regression).

---

### `tests/fixtures/phase206_golden_capture.ndjson` (committed deterministic NDJSON)

**Analog:** `tests/fixtures/phase_203_synthetic_capture.ndjson` (committed-NDJSON-as-fixture shape) for the file mechanics; `20260509T183037Z/soak-capture.ndjson` for the actual field semantics (per RESEARCH Sources line 700, that path is the verified baseline NDJSON shape).

**Per-line field shape (verified)** — Sample from `tests/fixtures/phase_203_synthetic_capture.ndjson:1`:

```
{"anti_windup_triggers": 0, "baseline_rtt_ms": 12.0, "docsis_mode_active": true, "floor_hit_cycles_total": 5, "headroom_exhausted_streak": 0, "headroom_state": "AVAILABLE", "last_zone": "GREEN", "load_rtt_delta_us": 142, "load_rtt_ms": 12.14, "max_delay_delta_us": 25, ..., "t_monotonic": 0.0, "t_wall": "2026-05-06T00:00:00Z", ..., "zone_trace_tail": ["GREEN", "GREEN", "GREEN", "GREEN", "GREEN"]}
```

For Phase 206 the field set is **smaller** — only what `GoldenSample` reads (`ts`, `baseline_rtt_ms`, `load_rtt_ms`, `cake_avg_delay_us`, `cake_base_delay_us`). The fixture is derived from `/home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/rrul-*.flent.gz` per **Locked Operator Decision D1**. RESEARCH §"Pitfall" warns against committing the raw `.flent.gz` (~MB, opaque, VCS-unfriendly) — commit the derived NDJSON only.

**Generation script convention** — Phase 203/204 used `tests/fixtures/_phase_203_generator.py` (the `_`-prefix marks it as a build-tool not a test). Phase 206 should follow this:

```
tests/fixtures/_phase_206_generator.py    # one-shot script — re-run to regenerate from .flent.gz
tests/fixtures/phase206_golden_capture.ndjson    # committed output
```

Provenance from `.flent.gz` to NDJSON belongs in `golden-fixture-provenance.md`, not in inline comments inside the NDJSON.

---

### `scripts/phase206-ab-replay.py` (harness CLI + importable)

**No exact analog.** The harness is plumbing of two existing primitives:

1. **In-process replay primitive** — `tests/test_phase_193_replay.py:_replay` (reused by import, not re-implemented; see Pattern 1 above).
2. **Flent `.flent.gz` parser primitive** — `scripts/phase198-rerun-flent-3run.sh:240-267` `extract_median()` (the gzip+json+statistics convention).

**Flent parser pattern (extend median → p99/p50)** — Source: `scripts/phase198-rerun-flent-3run.sh:240-267`:

```python
import gzip
import json
import statistics
import sys

with gzip.open(sys.argv[1], "rt") as fh:
    data = json.load(fh)
results = data.get("results", {})
preferred = []
for key in ("TCP download sum", "TCP totals", "TCP download"):
    values = results.get(key)
    if isinstance(values, list):
        preferred = [v for v in values if isinstance(v, (int, float))]
        if preferred:
            break
...
print(f"{statistics.median(preferred):.6f}")
```

Phase 206 extends this idiom — same `gzip.open` + `json.load` + filter-by-numeric, but uses `statistics.quantiles(data, n=100, method="exclusive")` to derive p99 and p50 in one pass (per RESEARCH §"A/B harness skeleton" lines 454-460):

```python
qs = statistics.quantiles(pings, n=100, method="exclusive")
return qs[98], qs[49]  # p99, p50
```

**Stdlib-only constraint** — RESEARCH §"Don't Hand-Roll" / §"Anti-Patterns": no numpy/pandas/scipy. `statistics.quantiles` is the right tool. CLAUDE.md says the venv is `.venv/bin/python3`; the harness shebang should match `scripts/phase198-rerun-flent-3run.sh` shebang convention (`#!/usr/bin/env bash` wrapping `.venv/bin/python3` OR direct `#!/usr/bin/env python3`; check existing precedent — none of the scripts directly shebang to `.venv/bin/python3`, so use `#!/usr/bin/env python3` and rely on test invocations via `.venv/bin/python3 scripts/phase206-ab-replay.py`).

**A/B summary schema (locked in RESEARCH §"Pattern 3")** — `schema_version: 1`, top-level `pre` / `post` / `delta` / `gates` / `meta`. Re-iterated here because the planner will reference both this PATTERNS.md and RESEARCH.md:

```python
SCHEMA_VERSION = 1
summary = {
    "schema_version": SCHEMA_VERSION, "phase": 206,
    "fixture_provenance": "tests/fixtures/phase206_golden_capture.ndjson",
    "fixture_sha256": "<computed>",
    "meta": {"generated_at_utc": ..., "head_sha": ..., "tool_version": "phase206-ab-replay/1.0"},
    "pre":   {"config": {...}, "rrul_p99_latency_ms": ..., "throughput_mbps": ..., "jitter_ms": ..., "zone_distribution": {...}, "rate_apply_count": ...},
    "post":  {"config": {...}, ...},  # identical shape to pre
    "delta": {"rrul_p99_latency_ms": ..., "rrul_p99_latency_pct": ..., ...},
    "gates": {"rrul_p99_latency_regression_pct_threshold": 5.0, "rrul_p99_latency_breach": False},
}
```

---

### `scripts/phase206-predeploy-gate.sh` (operator-facing wrapper)

**Analog:** `scripts/phase201-predeploy-gate.sh` (verbatim skeleton — operators must not relearn semantics).

**Exit-code contract (REUSE verbatim)** — Source: `scripts/phase201-predeploy-gate.sh:25-33`:

```bash
set -euo pipefail

EXIT_PASS=0
EXIT_BLOCK=1
EXIT_ABORT=2

log_info()  { printf '[predeploy-gate INFO]  %s\n' "$*" >&2; }
log_block() { printf '[predeploy-gate BLOCK] %s\n' "$*" >&2; printf '%s\n' "$*"; }
log_abort() { printf '[predeploy-gate ABORT] %s\n' "$*" >&2; }
```

This block is the operator contract. Phase 206 copies it byte-for-byte. The only deviations allowed: the log prefix may say `[phase206-predeploy-gate ...]` if distinguishability matters across concurrent operator runs — RESEARCH §"Pattern 2" does not require that.

**Env-override hatch for tests** — Source: `scripts/phase201-predeploy-gate.sh:43-49`:

```bash
read_yaml() {
    if [[ -n "${PHASE201_LOCAL_YAML_OVERRIDE:-}" ]]; then
        if [[ ! -f "$PHASE201_LOCAL_YAML_OVERRIDE" ]]; then
            log_abort "PHASE201_LOCAL_YAML_OVERRIDE=${PHASE201_LOCAL_YAML_OVERRIDE} does not exist"
            return $EXIT_ABORT
        fi
        cat -- "$PHASE201_LOCAL_YAML_OVERRIDE"
        return 0
    fi
    ...
}
```

Phase 206 follows the same shape with env var `PHASE206_LOCAL_BASELINE_OVERRIDE` (already named in RESEARCH §"Pattern 2" line 238). The override short-circuits the SSH probe — instead of `ssh ... 'systemctl show -p NRestarts ...'` (Locked Operator Decision D3), it reads pre-canned `(restart_counter_start, restart_counter_end)` from the override file or env. Test mode also stubs `journalctl` indirection.

**Path validation pattern (`set -euo pipefail`-safe)** — Source: `scripts/phase201-predeploy-gate.sh:36-39`:

```bash
validate_remote_yaml_path() {
    local p="$1"
    [[ "$p" =~ ^/[A-Za-z0-9._/-]+$ ]]
}
```

Phase 206 reuses this for any operator-supplied `--baseline` / `--candidate` JSON paths and the optional `--soak-ndjson` path.

**Main-loop "blocked" accumulator** — Source: `scripts/phase201-predeploy-gate.sh:137-152`:

```bash
local blocked=false
if [[ "$has_target" == "True" ]]; then
    log_block "BLOCK: target_bloat_ms present ..."
    blocked=true
fi
...
if [[ "$blocked" == "true" ]]; then
    exit $EXIT_BLOCK
fi
log_info "PASS: ..."
exit $EXIT_PASS
```

Phase 206 follows this exact accumulator shape with three checks instead of three (RRUL p99, restart-rate, transition-rate). All three are evaluated even if the first breaches — operators want the full picture of *which* gates tripped, not just the first one.

**SSH-into-cake-shaper for restart count (Locked D3)** — Source: `scripts/soak-monitor.sh:143-145`:

```bash
count=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" \
    "journalctl ${unit_args[*]} --since '1 hour ago' -p err --no-pager 2>/dev/null | grep -v '^-- No entries --$' | grep -c '.' || true" 2>/dev/null)
```

Phase 206 reuses this SSH pattern, but per **Locked Operator Decision D3** the actual remote command becomes `systemctl show -p NRestarts wanctl@spectrum.service` (cumulative integer, sampled twice for window-rate). Same `ssh -o ConnectTimeout=5 -o BatchMode=yes` flags — operators rely on those timing semantics.

---

### `scripts/phase206-gate-check.py` (gate-trigger Python core)

**No standalone analog in repo.** Closest pattern: the embedded `yaml_probe()` Python in `scripts/phase201-predeploy-gate.sh:81-105` (hoisted into a separate file). RESEARCH §"Gate script — Python helper" (lines 474-510) provides the canonical sketch.

**Exit-code constants must mirror the bash gate** — Source: `scripts/phase201-predeploy-gate.sh:27-29` (referenced above). In Python:

```python
# Source: RESEARCH.md §"Gate script — Python helper" line 480
EXIT_PASS, EXIT_BLOCK, EXIT_ABORT = 0, 1, 2
```

**Per-check function shape** — RESEARCH lines 482-509 give three function sketches: `check_rrul_p99(baseline, candidate, threshold_pct) -> tuple[bool, str]`, `check_restart_rate(ssh_target, since, baseline_rate_per_hour)`, `check_zone_transitions(soak_ndjson, baseline_rate_per_hour)`. The `(bool, str)` return tuple is the contract between checks and main — `False` means BLOCK, the string is the operator-readable line.

**Threshold constants must be named** — Per RESEARCH §"Locked Operator Decisions" deferred row: `RRUL_P99_REGRESSION_PCT = 5.0`, `RESTART_RATE_INCREASE_PCT = 10.0`, `TRANSITION_RATE_INCREASE_PCT = 10.0`. These are referenced from `PHASE-205-ROLLBACK-GATES.md`; both must agree byte-for-byte.

**NDJSON adjacency counter for transitions (Locked D2)** — RESEARCH §"Gate script" lines 495-509 already shows the loop. The `last_zone` field is verified present in `.../20260509T183037Z/soak-capture.ndjson` (RESEARCH Sources line 700). Counter is `sum(1 for i if last_zone[i] != last_zone[i-1])`, normalized by `t_monotonic / 3600.0`.

**Argparse + main pattern** — Standard Python pattern, no analog needed. Wire:
- `--baseline <path>` — A/B summary JSON OR `baseline-v143.json` (per Locked D3-deferred decision, gate accepts either)
- `--candidate <path>` — fresh A/B summary JSON
- `--soak-ndjson <path>` — for transition-rate check (optional; if absent, skip transition check OR ABORT)
- `--ssh-target <host>` — for restart-rate check
- `--journal-since <ISO8601>` — restart-rate window start (per Pitfall 4 guidance: `deploy_complete + 5min grace`)
- `--restart-counter <int> --restart-counter-end <int>` — test-mode injection (bypasses SSH)

---

### `.planning/phases/206-…/PHASE-205-ROLLBACK-GATES.md` (operator doc)

**No exact analog — new doc genre.** Closest shape: `.planning/phases/205-tin-agnostic-cake-signal-allow-wash-gate/205-04-SUMMARY.md` (narrative + fenced-block evidence + verdict banners).

**Section shape to copy** — Source: `205-04-SUMMARY.md:1-50`:

```markdown
---
phase: 205
plan: 04
status: complete
completed: 2026-05-14
---

# Phase 205 Closeout — Plan 04 SUMMARY

## Outcome Banner

PASS — SAFE-09 boundary scope matches the operator-approved 5-file set; ...

## SAFE-09 Cross-Plan Boundary Diff Scope

Operator decision (Plan 00): **approve / Option B**.

Expected file set:

- `src/wanctl/cake_signal.py`
...

Actual diff scope (verbatim `git diff 6508d68 --name-only -- src/wanctl/ | sort -u`):

```text
src/wanctl/backends/linux_cake.py
...
```
```

For Phase 206's rollback doc, the planner adapts this shape to **three rollback triggers** instead of one closeout verdict. Each trigger gets a section: definition → threshold (named constant) → measurement source → baseline derivation → example breach → example pass.

**Must include** (TOPO-05 verbatim from REQUIREMENTS.md line 23):
- RRUL p99 latency regression definition + threshold (>5%)
- Spectrum daemon restart-rate definition + measurement (Locked D3: `systemctl show -p NRestarts wanctl@spectrum.service`, diff over window with deploy-grace per Pitfall 4)
- Pressure-state transition-rate definition (Locked D2: any adjacent zone change, normalized per hour) + threshold

**Must NOT** include (RESEARCH §"Anti-Patterns"):
- New `/health` fields — that would be a `src/wanctl/` source diff = SAFE-09 violation.
- A "5%" threshold for restart/transition without rationale — per deferred-to-planner row, those are 10% with explicit rationale documenting the strict-binary alternative.

---

### `.planning/phases/206-…/golden-fixture-provenance.md` (fixture provenance doc)

**No exact analog — new doc genre.** Closest shape: the docstring header of `tests/fixtures/phase201_replay_corpus.py:1-8` (origin pointer convention).

**Origin-pointer pattern** — Source: `tests/fixtures/phase201_replay_corpus.py:1-8`:

```python
"""Phase 201 replay corpus loader and synthetic-trace generator.

Single source of truth for replay-test inputs. All Phase 201 test files
that need historical or synthetic UL traces import from this module.

Origin: RESEARCH.md Section 8 (Replay-Test Corpus); PATTERNS.md
'tests/test_phase_201_replay.py (NEW)'.
"""
```

The Phase 206 provenance doc expands this to a full markdown narrative covering:
1. **Source artifact** — full path: `/home/kevin/flent-results/cake-shaper-920-rrul/cake-shaper-920-rrul-20260429-231547/rrul-*.flent.gz` (Locked D1).
2. **Date substitution rationale** — ROADMAP says "2026-04-22 out-of-band flent finding"; that artifact was never committed (per SEED-001:17). The 2026-04-29 920-besteffort capture is the closest recoverable *shape*. Locked D1: operator accepted this substitution.
3. **Derivation steps** — pointer to `tests/fixtures/_phase_206_generator.py` (the `_`-prefix generator script convention from Phase 203/204).
4. **Schema** — list the fields kept in the NDJSON and which `GoldenSample` field each maps to.
5. **Re-derivation procedure** — how an operator regenerates the NDJSON from a fresh `.flent.gz` if Phase 209 needs a refreshed baseline.
6. **SHA256** — hash of the committed `phase206_golden_capture.ndjson` so any drift is detectable.

---

## Shared Patterns

### Pattern S1: Stdlib-only constraint (apply to all Python new files)

**Source:** RESEARCH §"Anti-Patterns to Avoid" line 298 + CLAUDE.md "Architectural Spine" implicit (no new deps in core flow).

**Rule:** No numpy / pandas / scipy. Use `statistics.quantiles(data, n=100, method="exclusive")` for percentiles; `statistics.median()` for medians; `gzip.open(path, "rt") + json.load()` for `.flent.gz`. Reference: `scripts/phase198-rerun-flent-3run.sh:240-267`.

### Pattern S2: SAFE-09 zero-`src/wanctl/`-diff (apply to all new files)

**Source:** `CLAUDE.md` "Architectural Spine"; ROADMAP Phase 206 Success Criterion 5; RESEARCH §"Pitfall 5".

**Rule:** No new file under `src/wanctl/`. No modification of any file under `src/wanctl/`. All `src/wanctl/` references are **read-only imports** — for example, `from wanctl.cake_signal import CakeSignalSnapshot, TinSnapshot` and `from wanctl.queue_controller import QueueController` are imports, not source edits. Verification one-liner at phase boundary: `git diff 6508d68 --name-only -- src/wanctl/ | sort -u | wc -l` returns **5** (the unchanged Phase 205 set).

### Pattern S3: `.venv/bin/pytest` invocation (apply to all test commands in PLANs)

**Source:** `CLAUDE.md` "Development Commands"; RESEARCH §"Test Framework" line 557.

**Rule:** All test commands invoke `.venv/bin/pytest`, never bare `pytest`. Phase 206 quick run: `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_predeploy_gate.py -q`. Hot-path regression slice (per CLAUDE.md): unchanged from current — Phase 206 does not edit the hot-path source files, so the existing slice continues to pass byte-for-byte.

### Pattern S4: env-override hatch for SSH/journalctl-dependent shell tests

**Source:** `scripts/phase201-predeploy-gate.sh:43-49`; `tests/test_phase201_predeploy_gate.py:24` (the env-dict pattern).

**Rule:** Any shell script that SSHes or invokes `journalctl`/`systemctl` MUST provide an env-var hatch that short-circuits the network call to a local file path. Env-var naming convention: `PHASE<N>_LOCAL_<KIND>_OVERRIDE`. For Phase 206: `PHASE206_LOCAL_BASELINE_OVERRIDE` (already named in RESEARCH §"Pattern 2"). Tests pass `env={"PHASE206_LOCAL_BASELINE_OVERRIDE": str(tmp_path), "PATH": "/usr/bin:/bin"}` to `subprocess.run`.

### Pattern S5: frozen-dataclass fixtures (apply to all new fixture loaders)

**Source:** `tests/fixtures/phase201_replay_corpus.py:23-32`; RESEARCH §"Don't Hand-Roll" row "NDJSON fixture loader".

**Rule:** All fixture-loader dataclasses are `@dataclass(frozen=True)`. Two replay runs against the same sample list must not be able to mutate samples between runs — frozen forbids that mechanically. Use `tuple` (not `list`) for nested fields like `tins`, mirroring `CakeSignalSnapshot.tins: tuple[TinSnapshot, ...]`.

---

## No Analog Found

| File | Role | Data Flow | Reason planner falls back to RESEARCH.md |
|------|------|-----------|------------------------------------------|
| `scripts/phase206-ab-replay.py` | harness CLI | NDJSON → A/B summary JSON | Phase 206 is the first repo file that *plumbs* the in-process replay primitive with the flent-parser primitive into a single CLI. RESEARCH §"A/B harness skeleton" lines 402-472 is the canonical sketch; PATTERNS.md cites the two underlying primitives. |
| `scripts/phase206-gate-check.py` | gate Python core | JSON+NDJSON → exit code | The yaml-probe in `phase201-predeploy-gate.sh:81-105` is *embedded* Python; Phase 206 needs a *standalone* Python file (importable for unit tests). RESEARCH §"Gate script — Python helper" lines 474-510 is the canonical sketch. |
| `PHASE-205-ROLLBACK-GATES.md` | operator doc | static markdown | New doc genre. Shape borrowed from `205-04-SUMMARY.md`. Content driven by TOPO-05 + Locked D2/D3 + Pitfall 4 in RESEARCH. |
| `golden-fixture-provenance.md` | provenance doc | static markdown | New doc genre. Origin-pointer convention borrowed from `phase201_replay_corpus.py:1-8` docstring; expanded to full markdown narrative. |

For the harness CLI and gate Python core, the planner should reference both this PATTERNS.md (for the two underlying primitives) AND RESEARCH.md §"Code Examples" (for the plumbing sketches).

---

## Metadata

**Analog search scope:**
- `/home/kevin/projects/wanctl/tests/` (all `test_phase_*_replay.py` + `test_phase201_predeploy_gate.py`)
- `/home/kevin/projects/wanctl/tests/fixtures/` (loader modules + NDJSON fixtures)
- `/home/kevin/projects/wanctl/scripts/` (all `phase*-*.{sh,py}` scripts + `soak-monitor.sh`)
- `/home/kevin/projects/wanctl/.planning/phases/205-…/` (SUMMARY.md shape)

**Files scanned:** 12 (read for excerpt extraction); plus directory listings for `tests/`, `tests/fixtures/`, `scripts/`, `.planning/phases/205-…/`.

**Files cited as `src/wanctl/` read-only references** (NOT targets — SAFE-09):
- `src/wanctl/cake_signal.py` (for `CakeSignalSnapshot`, `TinSnapshot`, `CakeSignalProcessor`, `CakeSignalConfig` imports)
- `src/wanctl/queue_controller.py` (for `QueueController` import + `.adjust_4state()` signature)
- `src/wanctl/wan_controller.py` (for `WANController` and arbitration constants, only if Phase 206 needs integration-shape tests — likely not for harness-only scope)

**Pattern extraction date:** 2026-05-14

---

## PATTERN MAPPING COMPLETE

**Phase:** 206 — A/B replay harness + rollback gates
**Files classified:** 9
**Analogs found:** 9 / 9

### Coverage
- Files with exact analog: 4 (`test_phase_206_replay.py`, `test_phase206_predeploy_gate.py`, `phase206_replay_corpus.py`, `phase206-predeploy-gate.sh`)
- Files with role-match analog: 5 (`phase206_golden_capture.ndjson`, `phase206-ab-replay.py`, `phase206-gate-check.py`, `PHASE-205-ROLLBACK-GATES.md`, `golden-fixture-provenance.md`)
- Files with no analog: 0 (all 9 have at least a role-match)

### Key Patterns Identified
- The Phase 193 `_replay()` / `_snap()` / `_fresh_controller()` primitives are the canonical A/B-able in-process replay shape; Phase 195's import pattern (`from tests.test_phase_193_replay import _replay, _snap, ...`) is the established reuse path — Phase 206 follows it verbatim.
- The Phase 201 predeploy-gate exit-code contract (`EXIT_PASS=0 / EXIT_BLOCK=1 / EXIT_ABORT=2`, `set -euo pipefail`, `log_info/log_block/log_abort` helpers, env-override hatch) is the operator contract — Phase 206 copies it byte-for-byte with only env-var name swap (`PHASE201_LOCAL_YAML_OVERRIDE` → `PHASE206_LOCAL_BASELINE_OVERRIDE`).
- The frozen-dataclass + per-line NDJSON parser pattern from `tests/fixtures/phase201_replay_corpus.py` is the fixture-loader shape; Phase 206 simplifies (no graceful-missing path) since the fixture is committed in-repo.
- Stdlib-only is enforced project-wide; `gzip+json.load+statistics.quantiles` (from `scripts/phase198-rerun-flent-3run.sh:240-267`) handles `.flent.gz` p99/p50 extraction without numpy/pandas.
- SAFE-09 (behavioral) bounds Phase 206 to **zero** `src/wanctl/` source edits — all references are read-only imports. The 5-file Phase 205 allowlist must remain at exactly 5 files at Phase 206 close.

### File Created
`/home/kevin/projects/wanctl/.planning/phases/206-a-b-replay-harness-rollback-gates/206-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files. Every new file has either an exact or role-match analog cited with file path + line numbers; the two .planning markdown docs fall back to RESEARCH.md sketches plus the `205-04-SUMMARY.md` evidence-shape convention.
