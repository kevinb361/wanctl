# Phase 239: Seam Refactor + IcmplibBackend (Byte-Identical) - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 4 (2 src, 1 script, 1 test)
**Analogs found:** 4 / 4 (all exact in-repo analogs)

> Source of file list: `239-RESEARCH.md` §"Recommended Project Structure" (lines 150-165) + §"Phase Requirements → Test Map" + §"Wave 0 Gaps". This is a pure refactor phase — zero new deps. Every hard part has a direct in-repo analog; the discipline is "wrap, don't consolidate" to preserve byte-identity. RouterOS/live network is NOT touched (offline-proven only — RESEARCH §Open Question 3).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/wanctl/rtt_backend.py` | interface + value type (Protocol + frozen dataclass + adapter stub) | transform (probe → RttSample) | `src/wanctl/interfaces.py` (Protocol) + `src/wanctl/rtt_measurement.py:92-107` (RTTSnapshot) + `src/wanctl/irtt_measurement.py:26-46` (IRTTResult adapter source) | exact |
| `src/wanctl/rtt_measurement.py` | measurement seam (MODIFIED — add `probe()`, coerce at publish) | request-response (ping hosts → snapshot) | itself (RTTMeasurement / BackgroundRTTThread, lines 470-575) | self / exact |
| `scripts/phase239-safe17-boundary-check.sh` | verifier (NEW — fail-closed allowlist) | batch (git diff → JSON evidence) | `scripts/check-safe07-source-diff.sh:126-203` (allowlist regex) + `scripts/phase238-safe17-boundary-check.sh` (arg-hardening + JSON evidence + dirty-tree) | exact (two-source clone) |
| `tests/test_rtt_backend.py` | test (NEW — conformance + superset + snapshot equivalence + IRTT shape) | transform assertion | `tests/test_rtt_measurement.py:1-40` (structure, mock_logger, make_host_result) + `tests/test_health_check.py:1-30` (imports) | exact |

---

## Pattern Assignments

### `src/wanctl/rtt_backend.py` (NEW — Protocol + RttSample + IRTT adapter stub)

This file has three sub-patterns from three different analogs. SEAM-01 (Protocol), SEAM-03 (superset dataclass), SEAM-04 (IRTT adapter shape).

#### Sub-pattern A — Protocol seam (SEAM-01)

**Analog:** `src/wanctl/interfaces.py:11-13, 20-28, 85-105`

House style: `from __future__ import annotations`, `@runtime_checkable`, `class X(Protocol)`, method bodies are `...`, docstring names the implementers. RouterClient (lines 85-105) is the richest multi-method example.

**Imports + decorator pattern** (`interfaces.py:11-13, 20-21`):
```python
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HealthDataProvider(Protocol):
    """Component that provides health endpoint data...."""

    def get_health_data(self) -> dict[str, Any]: ...
```

**Apply to `rtt_backend.py`:**
```python
@runtime_checkable
class RttBackend(Protocol):
    """RTT measurement backend. icmplib (RTTMeasurement) is the default;
    fping (Phase 241) and IRTT-adapter (SEAM-04) satisfy the same shape."""

    def probe(self, hosts: list[str]) -> "RttSample": ...
```
> **Critical (RESEARCH Pitfall, Anti-pattern lines 226, A1):** the Protocol lives in the NEW `rtt_backend.py`, NOT in `interfaces.py`, even though `interfaces.py` is the documented house location. Putting it in `interfaces.py` widens the SAFE-17 allowlist to a high-traffic shared file. Cross-referencing docstring edits to `interfaces.py` would themselves trip SAFE-17 — do not touch `interfaces.py`.

#### Sub-pattern B — RttSample as strict superset of RTTSnapshot (SEAM-03)

**Analog:** `src/wanctl/rtt_measurement.py:92-107` (RTTSnapshot — the type being superset-extended; keep it byte-stable for the equivalence proof).

**RTTSnapshot fields (UNCHANGED — the coercion target)** (`rtt_measurement.py:92-106`):
```python
@dataclasses.dataclass(frozen=True, slots=True)
class RTTSnapshot:
    """Immutable RTT measurement result for GIL-protected atomic swap...."""

    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float  # time.monotonic() when measured
    measurement_ms: float  # How long measurement took (ms)
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
```

**Apply to `rtt_backend.py`** (RESEARCH §Pattern 2, lines 194-216): same `frozen=True, slots=True`, exact field order/types of RTTSnapshot first, then `backend` / `source_ip` / `per_host_loss` superset additions, plus `.to_snapshot()` returning the byte-stable legacy type:
```python
@dataclasses.dataclass(frozen=True, slots=True)
class RttSample:
    rtt_ms: float
    per_host_results: dict[str, float | None]
    timestamp: float
    measurement_ms: float
    active_hosts: tuple[str, ...] = ()
    successful_hosts: tuple[str, ...] = ()
    # --- strict superset additions (SEAM-03) ---
    backend: str = "icmplib"
    source_ip: str | None = None
    per_host_loss: dict[str, float | None] = dataclasses.field(default_factory=dict)

    def to_snapshot(self) -> RTTSnapshot:
        return RTTSnapshot(
            rtt_ms=self.rtt_ms, per_host_results=self.per_host_results,
            timestamp=self.timestamp, measurement_ms=self.measurement_ms,
            active_hosts=self.active_hosts, successful_hosts=self.successful_hosts,
        )
```
> Use explicit coercion (NOT subclass/alias). RESEARCH §Alternatives line 83: subclassing frozen+slots dataclasses is brittle; explicit `.to_snapshot()` keeps RTTSnapshot byte-stable for the proof.

#### Sub-pattern C — IRTT adapter stub (SEAM-04)

**Analog:** `src/wanctl/irtt_measurement.py:26-46` (IRTTResult — the source type the adapter maps FROM).

**IRTTResult fields available for mapping** (`irtt_measurement.py:34-46`):
```python
@dataclass(frozen=True, slots=True)
class IRTTResult:
    rtt_mean_ms: float
    rtt_median_ms: float          # -> RttSample.rtt_ms
    ipdv_mean_ms: float
    send_loss: float              # -> per_host_loss
    receive_loss: float           # -> per_host_loss
    packets_sent: int
    packets_received: int
    server: str                   # -> source_ip / per-host key
    port: int
    timestamp: float
    success: bool
    ...
```

**Apply to `rtt_backend.py`** (RESEARCH §Pattern 3, lines 219-222, Open Question 2): a shape-proving `class IrttRttBackend` that constructs the field mapping then `raise NotImplementedError("IRTT-MIG-01")` — proves the Protocol absorbs IRTT without doing the deferred migration. `IRTTThread` already mirrors `BackgroundRTTThread` (`get_latest()`/`start()`/`stop()`/`_cached`), so the threading seam is already symmetric — do NOT wire it.

---

### `src/wanctl/rtt_measurement.py` (MODIFIED — add `probe()`, coerce at publish boundary)

**Analog:** itself. The wrap targets already exist; the change is additive.

**Existing wrap targets (DO NOT MODIFY their bodies):**
- `ping_hosts_with_results()` — `rtt_measurement.py:287` (per-host dict producer)
- `ping_host()` — `rtt_measurement.py:174-258` (single-host icmplib call)
- `_aggregate_rtts()` — `rtt_measurement.py:259`

**The publish boundary — the ONLY edit in `_run` (SEAM-02 byte-identity hinge)** (`rtt_measurement.py:495-513`):
```python
if successful_rtts:
    # Same aggregation as WANController.measure_rtt():
    # median-of-3+, average-of-2, single pass-through
    if len(successful_rtts) >= 3:
        rtt_ms = statistics.median(successful_rtts)
    elif len(successful_rtts) == 2:
        rtt_ms = statistics.mean(successful_rtts)
    else:
        rtt_ms = successful_rtts[0]

    self._cached = RTTSnapshot(           # <-- KEEP type RTTSnapshot (Pitfall 3 / A2)
        rtt_ms=rtt_ms,
        per_host_results=per_host,
        active_hosts=tuple(hosts),
        successful_hosts=successful_hosts,
        timestamp=time.monotonic(),
        measurement_ms=elapsed_ms,
    )
# else: stale data preferred over no data -- do NOT overwrite _cached
```

**Pattern to apply:**
- Add a thin `probe(self, hosts) -> RttSample` on `RTTMeasurement` that wraps `ping_hosts_with_results()` + the existing aggregation rule and packages an `RttSample` (RESEARCH lines 184, 217).
- Keep `BackgroundRTTThread._cached` typed `RTTSnapshot | None`. If `probe()` is routed through `_run`, coerce with `.to_snapshot()` at line 505 so the assignment stays `RTTSnapshot`. Lowest-risk path is: leave `_run` aggregation block byte-identical; `probe()` is an additive method consumers can call directly.

> **Anti-patterns enforced (RESEARCH lines 224-228, Pitfall 2):**
> - Do NOT consolidate the duplicated median/mean/single aggregation (also at `wan_controller.py:1297-1304`). Wrap, don't DRY.
> - Do NOT retype `_cached` to `RttSample` — that cascades into `measure_rtt()`.
> - Do NOT create a parallel `IcmplibBackend` class. "IcmplibBackend" is a role `RTTMeasurement` already fills.

**Downstream consumer that must stay byte-identical — `wan_controller.py` `measure_rtt()` reads** (VERIFIED `wan_controller.py:1161, 1173, 1195, 1218-1235`): `snapshot.timestamp`, `snapshot.per_host_results`, `snapshot.rtt_ms`, `snapshot.active_hosts`, `snapshot.successful_hosts`. RESEARCH §Open Question 1 + A4: **keep `wan_controller.py` byte-unchanged** — its `rtt_measurement: RTTMeasurement` annotation (line 332) still satisfies `RttBackend` structurally; do not retype it (that puts the most sensitive file in the allowlist).

---

### `scripts/phase239-safe17-boundary-check.sh` (NEW — fail-closed allowlist verifier)

Two-source clone: allowlist-regex semantics from SAFE-09, hardening/evidence machinery from Phase 238.

**Analog 1 (allowlist regex + fail-closed logic):** `scripts/check-safe07-source-diff.sh:164-203`
```bash
DIFF_OUTPUT=$(git diff "${REF}..HEAD" -- src/wanctl/ 2>&1 || true)
if [ -n "${DIFF_OUTPUT}" ]; then
  CHANGED_PATHS=$(git diff --name-only "${REF}..HEAD" -- src/wanctl/)
  V144_ALLOWLIST_RE='^src/wanctl/(__init__\.py|cake_signal\.py|...)$'
  DISALLOWED_PATHS=$(printf '%s\n' "${CHANGED_PATHS}" | grep -Ev "${V144_ALLOWLIST_RE}" || true)
  if [ -z "${DISALLOWED_PATHS}" ] && <version-bump checks>; then
    echo "SAFE-09 OK: diff vs ${REF} bounded to v1.44 allowlist"; exit 0
  fi
  echo "SAFE-09 VIOLATION: ..." >&2
  printf '%s\n' "${DISALLOWED_PATHS}" >&2; exit 1
fi
echo "SAFE-09 OK: no src/wanctl/ diff vs ${REF}"; exit 0
```
**Apply (RESEARCH §Code Examples lines 271-288, Pitfall 4):**
- `V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py|rtt_measurement\.py)$'` — Phase 239 surface only (the narrowest in the milestone; grows per phase).
- Invert from 238's zero-diff to allowlist: "any changed `src/wanctl/` path must match the regex; anything else is a violation."
- **Drop the `__version__` bump assertion** (RESEARCH Pitfall 5 / A3): v1.53 is mid-milestone; `__init__.py` is `1.47.0` (VERIFIED — version string lags tags); do NOT add `__init__.py` to the allowlist or require a bump.

**Analog 1 (dirty-tree fail-closed precheck — reuse verbatim):** `scripts/check-safe07-source-diff.sh:133-162`
```bash
DIRTY_UNSTAGED=0; DIRTY_STAGED=0; DIRTY_UNTRACKED_LIST=""
git diff --quiet -- src/wanctl/ || DIRTY_UNSTAGED=1
git diff --cached --quiet -- src/wanctl/ || DIRTY_STAGED=1
DIRTY_UNTRACKED_LIST=$(git ls-files --others --exclude-standard -- src/wanctl/ || true)
# any of the three set => VIOLATION (committed-diff check alone is not trustworthy)
```

**Analog 2 (arg-hardening + JSON evidence + realpath confinement):** `scripts/phase238-safe17-boundary-check.sh:11-80, 82-221`
```bash
ANCHOR="v1.52"
OUT=".planning/phases/239-.../evidence/safe17-boundary-239.json"
ALLOWED_OUT_PREFIX=".planning/phases/239-.../evidence/"
# --out must not target controller source paths
# --out must not contain '..' path components
out_realpath="$(realpath -m -- "$OUT")"
evidence_realpath="$(realpath -m -- "$ALLOWED_OUT_PREFIX")"
[[ "$out_realpath" != "$evidence_realpath"/* ]] && exit 2
# anchor resolved as a commit, never an attacker-controlled flag:
ANCHOR_SHA="$(git rev-parse --verify --end-of-options "${ANCHOR}^{commit}")"
# ... python3 heredoc emits the JSON evidence record with per_path_diff,
#     dirty_tree, passed, checked_at (ISO-Z) ...
```
**Apply:** `ANCHOR="v1.52"` (VERIFIED `git tag` → v1.50/v1.51/v1.52 present; the last clean controller-path commit — Pitfall 4 / A6). Reuse the `--anchor`/`--out` hardening, `realpath` confinement to the 239 evidence dir, `rev-parse --verify --end-of-options`, and the JSON evidence emitter verbatim. Evidence dir convention exists: `.planning/phases/238-.../evidence/safe17-boundary-238.json` (VERIFIED) → mirror as `.../239-.../evidence/safe17-boundary-239.json`.

> **The whole point (Pitfall 4):** do NOT reuse 238's zero-diff script unchanged — it FAILS the instant `rtt_measurement.py` is edited, which is the intended change. The 239 script must PASS on an in-allowlist edit and FAIL only on out-of-allowlist drift.

---

### `tests/test_rtt_backend.py` (NEW — conformance + superset + snapshot equivalence + IRTT shape)

**Analog:** `tests/test_rtt_measurement.py:1-40` (structure, fixtures, helpers) + `tests/test_health_check.py:1-30` (multi-symbol imports).

**Imports + fixtures pattern** (`test_rtt_measurement.py:1-40`):
```python
import dataclasses, statistics, threading, time
from unittest.mock import MagicMock, patch
import icmplib, pytest

from tests.helpers import make_host_result   # VERIFIED helper at tests/helpers.py:18
from wanctl.rtt_measurement import (
    BackgroundRTTThread, RTTAggregationStrategy, RTTCycleStatus,
    RTTMeasurement, RTTSnapshot, parse_ping_output,
)

class TestPingHostsWithResults:
    @pytest.fixture
    def mock_logger(self):
        return MagicMock()

    @pytest.fixture
    def rtt_measurement(self, mock_logger):
        return RTTMeasurement(logger=mock_logger, timeout_ping=1,
                              aggregation_strategy=RTTAggregationStrategy.AVERAGE)
```

**Apply (RESEARCH §Test Map lines 327-335, §Code Examples lines 299-312):** four test groups —
- `test_protocol_conformance` (SEAM-01): `assert isinstance(rtt_measurement, RttBackend)` via `@runtime_checkable`.
- `test_rttsample_to_snapshot_byte_identical` (SEAM-02): feed deterministic per-host results (use `make_host_result`), `assert sample.to_snapshot() == hand-built RTTSnapshot(...)` (frozen dataclass `==` is field-wise — byte-identity proof).
- `test_rttsample_superset_fields` (SEAM-03): assert RttSample has every RTTSnapshot field plus `backend`/`source_ip`/`per_host_loss`.
- `test_irtt_adapter_shape` (SEAM-04): assert the IRTT→RttSample field mapping compiles / stub raises `NotImplementedError("IRTT-MIG-01")`.

> Existing `tests/test_rtt_measurement.py` (61 tests) must stay green — modify only if the additive `probe()` needs coverage there.

---

## Shared Patterns

### Frozen value type (GIL-atomic pointer swap)
**Source:** `src/wanctl/rtt_measurement.py:92` and `src/wanctl/irtt_measurement.py:26`
**Apply to:** `RttSample` in `rtt_backend.py`
```python
@dataclasses.dataclass(frozen=True, slots=True)
```
House invariant: every RTT value type is `frozen=True, slots=True` — required for the lock-free `_cached` pointer swap (RESEARCH §Don't Hand-Roll line 237). Immutability is load-bearing, not stylistic.

### Protocol house style
**Source:** `src/wanctl/interfaces.py:13, 20-21`
**Apply to:** `RttBackend` Protocol (but in `rtt_backend.py`, not `interfaces.py`)
```python
from typing import Protocol, runtime_checkable
@runtime_checkable
class X(Protocol): ...   # bodies are `...`; docstring names implementers; structural, no inheritance
```

### Fail-closed verifier machinery
**Source:** `scripts/check-safe07-source-diff.sh:133-162` (dirty-tree) + `scripts/phase238-safe17-boundary-check.sh:46-80` (arg hardening)
**Apply to:** `scripts/phase239-safe17-boundary-check.sh`
- `set -euo pipefail`
- dirty-tree precheck (unstaged + staged + untracked) before trusting committed diff
- `git rev-parse --verify --end-of-options` for anchor resolution
- `--out` realpath-confined to the phase evidence dir, reject `..` and `src/wanctl` targets
- exit codes: 0 clean / 1 violation / 2 usage-or-git-error

### Test fixtures
**Source:** `tests/test_rtt_measurement.py:26-40` + `tests/helpers.py:18` (`make_host_result`)
**Apply to:** `tests/test_rtt_backend.py` — `MagicMock()` logger fixture, `make_host_result` for deterministic per-host inputs.

---

## No Analog Found

None. Every file has an exact in-repo analog (RESEARCH §Don't Hand-Roll line 239: "Every hard part of this phase already has an exact in-repo analog").

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | — |

---

## Metadata

**Analog search scope:** `src/wanctl/` (interfaces.py, rtt_measurement.py, irtt_measurement.py, wan_controller.py), `scripts/` (check-safe07-source-diff.sh, phase238-safe17-boundary-check.sh), `tests/` (test_rtt_measurement.py, test_health_check.py, helpers.py)
**Files scanned:** 9 (all cited with line numbers)
**Verified via tooling:** `git tag` → v1.52 present; `__version__ = "1.47.0"`; `ping_hosts_with_results`@287 / `_aggregate_rtts`@259 exist; `make_host_result`@helpers.py:18; 238 evidence dir present; `measure_rtt()` consumer fields confirmed at wan_controller.py:1161-1235
**Pattern extraction date:** 2026-06-15
