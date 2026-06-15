# Phase 241: fping Backend (Offline) + Reflector Quality - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 6 new/modified (1 backend module, 2 scripts, 3 test/fixture sets)
**Analogs found:** 6 / 6 (all exact or near-exact)

## Orientation

The fping backend is, per RESEARCH.md, **~90% a structural clone of the irtt path**. The
novel code is only `_parse_fping` (text, not JSON) and the loss%→bool scorer gate. Everything
else — subprocess lifecycle, advisory lock, failure-as-`None`, cadence thread, aggregation —
is copy-with-rename from existing files. This map gives the planner the exact analog file,
line range, and SAFE-17 protection status per new file.

**SAFE-17 protection legend:**
- `FROZEN` = body is in `phase239-protected-body-diff.py` PROTECTED dict; byte-identical
  required; **COPY the shape into the new module, never edit the source**.
- `BYTE-UNCHANGED` = file is in the seam-no-drift layer; 241 must not touch it at all.
- `ALLOWLIST-EXTEND` = file must be ADDED to the path allowlist for 241 to legally edit it.
- `FREE` = unprotected, not in allowlist; safe to read/copy-from but not the edit target.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality | SAFE-17 |
|-------------------|------|-----------|----------------|---------------|---------|
| `src/wanctl/fping_measurement.py` (NEW) | service / backend | request-response (subprocess burst) | `src/wanctl/irtt_measurement.py` + `src/wanctl/irtt_thread.py` | exact (lifecycle clone) | ALLOWLIST-EXTEND (`+fping_measurement.py`) |
| `src/wanctl/reflector_scorer.py` (call site, gated) | service / scorer | event-driven (batch feed) | self — `record_results` interface unchanged | exact (interface reuse) | ALLOWLIST-EXTEND (`+reflector_scorer.py`); scoring math FROZEN by convention (D-05) |
| `tests/test_fping_measurement.py` (NEW) | test | fixture-driven unit | `tests/test_irtt_measurement.py` | exact (mock pattern) | FREE (tests not in allowlist) |
| `tests/fixtures/fping/*.txt` (NEW, 6 files) | fixture | file-I/O | none (D-08 operator capture) | no analog — operator-run | FREE |
| `tests/test_phase241_safe17_verifier.py` (NEW) | test | unit | `tests/test_phase240_safe17_verifier.py` | exact (mirror) | FREE |
| `scripts/phase241-safe17-boundary-check.sh` (NEW) | config / gate | batch (git-diff verify) | `scripts/phase240-safe17-boundary-check.sh` | exact (regex extend) | FREE |
| `scripts/capture-fping-fixtures.sh` (NEW) | utility | file-I/O | none (operator helper) | no analog | FREE |

**Files that must stay BYTE-UNCHANGED this phase (do NOT edit):**
- `src/wanctl/rtt_backend.py` — `RttSample`/`RttBackend` already carry every field fping needs
  (`per_host_loss`, `backend`, `source_ip`). Seam-no-drift layer. Read-only import target.
- `src/wanctl/rtt_measurement.py` — reuse `RTTAggregationStrategy.MEDIAN` and the
  median-of-3+/avg-2/passthrough rule by **copying the rule**, not importing/editing. Its
  `BackgroundRTTThread._run`, `_ping_with_persistent_pool`, `ping_hosts_with_results`,
  `RTTMeasurement.probe` etc. are FROZEN. The allowed-shape guard permits exactly one added
  qualname (`RTTMeasurement.probe`) already present — add nothing.
- `src/wanctl/wan_controller.py` — `WANController.measure_rtt` is FROZEN; the scorer feed must
  NOT be wired here.
- `src/wanctl/autorate_continuous.py` — backend construction is Phase 242; do not edit.
- `src/wanctl/autorate_config.py` — `ping_source_ip` is read-only precedent; the backend reads
  the resolved value, it does not re-touch this loader.

---

## Pattern Assignments

### `src/wanctl/fping_measurement.py` (NEW backend — service, request-response)

**Primary analog:** `src/wanctl/irtt_measurement.py` (lifecycle) + `src/wanctl/irtt_thread.py` (cadence).
Copy the class shapes; swap the command builder and the parser. The `FpingThread` lives in the
SAME new module (keeps the edit inside the allowlist — do NOT add it to `irtt_thread.py`).

**Imports pattern** — copy `irtt_measurement.py:12-23` (drop `json`, `hashlib` stays for lock key):
```python
from __future__ import annotations

import fcntl
import logging
import os
import shutil
import statistics      # NEW vs irtt: needed for median aggregation (D-04)
import subprocess
import tempfile
import time
```

**Subprocess + advisory-lock lifecycle (FPING-05)** — clone `irtt_measurement.py:160-189`
`_run_serialized` verbatim, rename lock prefix `irtt-` → `fping-`. This is the proven
flock + `subprocess.run(timeout=...)` + `LOCK_UN`-in-finally body. Keep the `# noqa: S603`:
```python
def _run_serialized(self, cmd: list[str]) -> subprocess.CompletedProcess[str] | None:
    if self._lock_path is None:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)  # noqa: S603
    deadline = time.monotonic() + self._lock_timeout
    with open(self._lock_path, "a+", encoding="utf-8") as lock_file:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return None
                time.sleep(0.05)
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)  # noqa: S603
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
```
**Lock-key note (RESEARCH.md:286):** incorporate `source_ip` + reflector set into the lock key
(clone `_build_lock_path` at `irtt_measurement.py:146-158`) so two WAN backends don't serialize
against each other.

**Probe / parse-on-nonzero discipline (FPING-04, FPING-05)** — clone `irtt_measurement.py:85-123`
`measure()` control flow. The load-bearing detail: parse stdout EVEN on non-zero exit
(`irtt_measurement.py:102-104` comment is the precedent — fping exit 1/2 on loss is normal):
```python
result = self._run_serialized(cmd)
if result is None:
    self._log_failure("lock timeout ..."); return None
sample = self._parse_fping(result.stdout, hosts)   # parse REGARDLESS of returncode
if sample is None:
    self._log_failure("empty or unparseable fping output"); return None
return sample
# except subprocess.TimeoutExpired: self._log_failure(...); return None
# except Exception as exc: self._log_failure(str(exc)); return None
```

**Failure-log throttling** — clone `irtt_measurement.py:229-240` `_log_failure` verbatim
(first WARNING, subsequent DEBUG, recovery INFO via `_consecutive_failures`/
`_first_failure_logged`). Rename "IRTT" → "fping" in the strings.

**Command builder (FPING-01/02/03)** — analogous to `irtt_measurement.py:129-144` `_build_command`,
but multi-host and `-C`/`-p`/`-S` (D-01/D-02). The capture script MUST build the identical
command (Pitfall 6):
```python
def _build_command(self, hosts: list[str]) -> list[str]:
    cmd = ["fping", "-C", str(self._count), "-p", str(self._period_ms), "-q"]
    if self._source_ip:
        cmd += ["-S", self._source_ip]
    cmd += hosts
    return cmd  # noqa: S603 -- fixed fping invocation, hosts are config reflectors
```

**Parser — `-` token never 0ms (FPING-04 keystone, NOVEL code)** — no analog; built from D-08
fixtures. The single highest-value regression. Loss token → skip, never append `0.0`:
```python
def _parse_target_line(self, line: str) -> tuple[str, list[float]] | None:
    # "host : 91.7 37.0 29.2 - 36.8"  (strip optional -D timestamp prefix first)
    host, _, rest = line.partition(" : ")
    if not rest:
        return None
    rtts: list[float] = []
    for tok in rest.split():
        if tok == "-":
            continue                 # LOSS: skip; do NOT append 0.0
        try:
            rtts.append(float(tok))
        except ValueError:
            return None              # partial/garbled line -> unparseable
    return host.strip(), rtts
```

**Aggregation into RttSample (D-04)** — copy the EXACT cross-host rule frozen in
`rtt_measurement.py:343-348` (`RTTMeasurement.probe`); per-host = median of received pings:
```python
if len(all_received) >= 3:   rtt_ms = statistics.median(all_received)
elif len(all_received) == 2: rtt_ms = statistics.mean(all_received)
else:                        rtt_ms = all_received[0]
# per-host: per_host_results[host] = statistics.median(rtts) (received only)
# per_host_loss[host] = (count - len(rtts)) / count * 100.0   (None results -> 100.0)
# if not all_received: return None   (D-03 all-fail contract)
```
Construct `RttSample(... backend="fping", source_ip=self._source_ip, per_host_loss=...)` — the
field shape is fixed at `rtt_backend.py:46-54` (frozen, slots; do NOT edit that file).

**Cadence thread `FpingThread` (D-06/D-07)** — clone `irtt_thread.py:19-96` into this module.
Same daemon-thread + GIL-protected pointer swap + `shutdown_event.wait(cadence)` shape; call
`self._measurement.probe(hosts_fn())` instead of `measure()`, cache the latest `RttSample`.
Thread name → `"wanctl-fping"`. **`IRTTThread` is FREE (not protected) but is a template to
COPY, not edit** (editing `irtt_thread.py` is unnecessary and out of allowlist):
```python
def _run(self) -> None:
    while not self._shutdown_event.is_set():
        try:
            result = self._measurement.probe(self._hosts_fn())
            if result is not None:
                self._cached_result = result
        except Exception:
            self._logger.debug("fping measurement error", exc_info=True)
        self._shutdown_event.wait(timeout=self._cadence_sec)
```
**Cadence default precedent** — `autorate_continuous.py:484` (`cadence_sec = ...get("cadence_sec", 10.0)`).
**Timeout < cadence invariant (Pitfall 5):** `timeout = (count × period_ms/1000) + grace` and
validate `timeout < cadence_sec` so bursts never pile.

---

### `src/wanctl/reflector_scorer.py` (REFL-01 gated call site — service, event-driven)

**Analog:** self. The interface is reused **unchanged**; this is the smallest SAFE-17 surface.

**Target interface (DO NOT MODIFY — D-05)** — `reflector_scorer.py:134-144`:
```python
def record_results(self, results: dict[str, bool]) -> None:
    for host, success in results.items():
        self._record_result(host, success)   # rolling window, score, deprioritize/recover
```
Constructor shape for test wiring — `reflector_scorer.py:76-85`:
`ReflectorScorer(hosts, min_score=0.8, window_size=50, recovery_count=3, wan_name=...)`.
Scoring math (`_record_result`, `_score_for_host`, deprioritize/recover at `:146+`) is the
**frozen-by-convention** body — REFL-01 only constructs the `dict[str,bool]` and calls
`record_results`. The scorer file must be ADDED to the path allowlist; its math stays byte-identical.

**Loss→bool gate (D-05a, NOVEL, fping-gated)** — lives on the **fping side**
(`fping_measurement.py` or its `FpingThread`), NOT in `wan_controller.py` (FROZEN) and NOT in
`reflector_scorer.py` math. any-loss→fail default, threshold = YAML knob:
```python
def _scorer_results(self, sample: RttSample) -> dict[str, bool]:
    return {
        host: (loss is not None and loss <= self._loss_fail_threshold)
        for host, loss in sample.per_host_loss.items()
    }
# self._scorer.record_results(self._scorer_results(sample))  # fping path only
```
**Scorer-ownership note (RESEARCH.md Open Q2):** inject an optional scorer (or results-callback)
into the fping backend at construction; 241 exercises it with a test scorer (no live wiring —
Phase 242 injects the real one). This avoids any `wan_controller.py` edit.

---

### `tests/test_fping_measurement.py` (NEW — test, fixture-driven)

**Analog:** `tests/test_irtt_measurement.py:1-70`. Copy the mock shape:
`subprocess.CompletedProcess(args=["fping"], returncode=1, stdout=<fixture text>)` patched via
`patch("wanctl.fping_measurement.subprocess.run", ...)`. The irtt test also demonstrates the
`patch.dict("os.environ", {"WANCTL_RUN_DIR": str(tmp_path)})` + `shutil.which` patch pattern
(`test_irtt_measurement.py:55-59`) for lock-path and binary-availability isolation — reuse it.

**Keystone assertion (FPING-04, Pitfall 1)** — a `-`-heavy host is never `0.0ms`:
```python
def test_dash_token_never_zero():
    stdout = (FIXTURES / "partial_loss.txt").read_text()
    fake = subprocess.CompletedProcess(args=["fping"], returncode=1, stdout=stdout, stderr="")
    with patch("wanctl.fping_measurement.subprocess.run", return_value=fake):
        sample = backend.probe(["198.51.100.10"])
    assert sample is not None
    assert all(v is None or v > 0.0 for v in sample.per_host_results.values())
```
Cover the six D-03 scenarios (reply / total_loss / partial_loss / partial_line / banner_noise /
process_death) one fixture each (RESEARCH.md Test Map). Fixtures are read from
`tests/fixtures/fping/`.

### `tests/fixtures/fping/{reply,total_loss,partial_loss,partial_line,banner_noise,process_death}.txt`

**No analog.** D-08 operator-run capture via `capture-fping-fixtures.sh` on the LIVE host
(fping absent on dev VM). **Operator-in-the-loop hard gate** — flag clearly in the plan; parser
tests cannot pass against real output until capture completes. Synthetic placeholders may
bootstrap parser code, but real 5.1 captures are the binding proof (D-03/D-08). Capture
invocation MUST be byte-identical to `_build_command` (Pitfall 6).

### `tests/test_phase241_safe17_verifier.py` (NEW — test)

**Analog:** `tests/test_phase240_safe17_verifier.py` (mirror). Same structure; assert the
expanded allowlist passes and out-of-allowlist drift is rejected.

### `scripts/phase241-safe17-boundary-check.sh` (NEW — gate)

**Analog:** `scripts/phase240-safe17-boundary-check.sh`. Copy and extend ONLY the path regex.
Current (`phase240:22`):
```bash
V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py|rtt_measurement\.py|check_config_validators\.py|check_steering_validators\.py)$'
```
Add `fping_measurement\.py` and `reflector_scorer\.py` to the alternation. Keep the other
layers intact: fail-closed-on-dirty-tree (`:14`), no-RTT-seam-drift-since-Phase-239
(`RTT_SEAM_UNCHANGED_SINCE_PHASE239`, keyed on `rtt_backend.py`+`rtt_measurement.py` — passes
as-is IF 241 leaves both byte-unchanged, which is the recommendation), protected-body diff via
`phase239-protected-body-diff.py`, and JSON evidence emit.

### `scripts/capture-fping-fixtures.sh` (NEW — utility)

**No analog.** Operator-run helper (D-08). Must be safe/non-mutating to production routing:
total-loss via TEST-NET blackhole (`192.0.2.1`), partial-loss via distant/lossy target or
`tc`-induced drop, process-death via mid-burst `kill`/SIGTERM. Build the SAME command the
backend builds (share builder or assert equality).

---

## Shared Patterns

### Subprocess lifecycle (bounded, recover-and-continue)
**Source:** `src/wanctl/irtt_measurement.py:85-189` (`measure` + `_run_serialized`)
**Apply to:** `fping_measurement.py` probe path
- `subprocess.run(..., timeout=self._timeout)`, `TimeoutExpired` → `_log_failure` → `None`.
- `fcntl.flock` advisory lock under `WANCTL_RUN_DIR`/`/run/wanctl`, `LOCK_UN` in `finally`.
- Parse stdout even on non-zero exit; reserve `None` for empty/unparseable/timeout/death.

### Cadence daemon thread (GIL pointer-swap)
**Source:** `src/wanctl/irtt_thread.py:19-96`
**Apply to:** `FpingThread` (in `fping_measurement.py`)
- Daemon thread, `shutdown_event.wait(cadence)`, atomic `self._cached_result = sample` swap.
- `start()`/`stop(join timeout=5.0)`/`get_latest()` surface; cadence default precedent
  `autorate_continuous.py:484` (`get("cadence_sec", 10.0)`).

### RTT aggregation rule (must match the frozen seam exactly)
**Source:** `src/wanctl/rtt_measurement.py:343-348` (also frozen in `BackgroundRTTThread._run`,
`WANController.measure_rtt`)
**Apply to:** fping cross-host aggregation
- median-of-3+ / avg-of-2 / single passthrough. Per-host = median of that host's received pings.
- `RTTAggregationStrategy.MEDIAN` enum at `rtt_measurement.py:83,87` — reuse the concept; do NOT
  edit the file.

### Sample / seam contract (already complete — no edit)
**Source:** `src/wanctl/rtt_backend.py:36-54` (`RttSample`), `:19-33` (`RttBackend` Protocol),
`:70-91` (`sample_from_irtt_result` loss-mapping precedent)
**Apply to:** fping output construction — populate `backend="fping"`, `source_ip=<-S>`,
`per_host_loss` per reflector. `None` from `probe` = all-fail. File stays BYTE-UNCHANGED.

### Source-IP resolution (`-S`)
**Source:** `src/wanctl/autorate_config.py:643` (`ping_source_ip` optional-key-with-default)
**Apply to:** fping `-S` binding. Backend reads the resolved string; no re-touch of the loader.

### SAFE-17 boundary discipline
**Source:** `scripts/phase240-safe17-boundary-check.sh:22`, `scripts/phase239-protected-body-diff.py:21-35`
**Apply to:** every 241 edit. PROTECTED dict (do NOT touch): `rtt_measurement.py`
{`RTTSnapshot`, `RTTMeasurement.__init__/.ping_host/._aggregate_rtts/.ping_hosts_with_results`,
`BackgroundRTTThread._run/._ping_with_persistent_pool`}, `wan_controller.py`
{`WANController.measure_rtt`}. Allowed added qualname on `rtt_measurement.py` is exactly
`RTTMeasurement.probe` (already present) — add nothing to that file.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/fixtures/fping/*.txt` | fixture | file-I/O | D-08 operator-captured real fping 5.1 output; no in-tree precedent |
| `scripts/capture-fping-fixtures.sh` | utility | file-I/O | Operator-run live-host capture helper; no existing capture script analog |
| `_parse_fping` / `_parse_target_line` (within `fping_measurement.py`) | parser logic | transform | NOVEL: fping text format ≠ irtt JSON; built from fixtures (D-08). Planner uses RESEARCH.md Pattern 2 + fping `-C` format notes, validated against captured fixtures. |
| loss→bool scorer gate (`_scorer_results`) | transform | event-driven | NOVEL: D-05a any-loss→fail conversion; no existing loss→bool feed. RESEARCH.md Code Examples is the reference. |

## Metadata

**Analog search scope:** `src/wanctl/` (backend, thread, seam, scorer, config), `tests/`, `scripts/`
**Files scanned / read for excerpts:** `irtt_measurement.py`, `irtt_thread.py`, `rtt_backend.py`,
`rtt_measurement.py` (probe/aggregation region), `reflector_scorer.py` (ctor + record_results),
`test_irtt_measurement.py`, plus grep-verified refs in `phase240-safe17-boundary-check.sh`,
`phase239-protected-body-diff.py`, `autorate_config.py`, `autorate_continuous.py`.
**All line numbers verified against the live tree (2026-06-15).**
**Pattern extraction date:** 2026-06-15
</content>
</invoke>
