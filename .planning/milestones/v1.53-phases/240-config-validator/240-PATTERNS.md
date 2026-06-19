# Phase 240: Config + Validator - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 5 (3 modified, 2 created)
**Analogs found:** 5 / 5

> Every piece of machinery this phase needs already exists and is battle-tested
> in the validator. Net-new code is one small validator function, two registry
> additions per validator, a new test class, and a cloned boundary script. There
> are no novel patterns — this is a "copy the irtt registration + copy the tc
> probe + clone the 239 script" phase.

## File Classification

| New/Modified File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|---------|------|-----------|----------------|---------------|
| `src/wanctl/check_config_validators.py` | modified | validator (config) | transform / request-response | self (`irtt` registration block `:173-182`, `validate_linux_cake` shape) | exact (in-file) |
| `src/wanctl/check_steering_validators.py` | modified | validator (config) | transform / request-response | `validate_linux_cake` `:481-570` (same file) | exact |
| `tests/test_check_config.py` | modified | test | request-response | `TestLinuxCakeValidation` `:1157-1206` | exact |
| `configs/{att,spectrum,steering}.yaml` (read-only corpus) | read-only | config (regression fixture) | — | n/a (consumed, not edited) | n/a |
| `scripts/phase240-safe17-boundary-check.sh` | created | boundary verifier (script) | batch / git-inspection | `scripts/phase239-safe17-boundary-check.sh` | exact (clone) |

**Discretionary placement note (from RESEARCH A4 / Open Q1):** the shared
`validate_measurement_backend` helper + `MEASUREMENT_BACKENDS` constant should
live in `check_config_validators.py` and be imported by the steering dispatcher
via the existing local-import dodge. **Do NOT touch `check_config.py` or
`autorate_config.py`** — keeping both out of the edit set keeps the SAFE-17
allowlist minimal (D-02: no loader in 240; the key is validated, not loaded).

## Pattern Assignments

### `src/wanctl/check_config_validators.py` (validator, transform) — MODIFIED

**Analog:** self — the `irtt:` registration block (`:173-182`) for the registry
addition; `validate_linux_cake` (in `check_steering_validators.py:481-570`) for
the validator-function shape.

**Edit 1 — Register the new paths in `KNOWN_AUTORATE_PATHS`** (autorate has NO
`measurement` block today, so BOTH lines are new). Copy the `irtt` registration
style at lines 173-182:

```python
# Existing precedent — src/wanctl/check_config_validators.py:173-182
# IRTT measurement (_load_irtt_config)
"irtt",
"irtt.enabled",
"irtt.server",
# ... block registered as KNOWN even though NOT in Config.SCHEMA
```

Add (near line 248, after the continuous_monitoring block per RESEARCH §Code Examples):

```python
# Measurement backend selection (Phase 240, CFG-01) -- additive, inert until Phase 242
"measurement",
"measurement.backend",
```

**Edit 2 — Module-level shared enum constant** (D-disc single source of truth):

```python
MEASUREMENT_BACKENDS: tuple[str, ...] = ("icmplib", "fping")  # Phase 240; 'irtt' intentionally excluded (IRTT-MIG-01)
```

**Edit 3 — New cross-field validator function.** Pattern source is the tc-binary
probe in `validate_linux_cake` (see steering file excerpt below). **Do direct
shape discrimination via `data.get("measurement")` — do NOT rely on
`_get_nested(data, "measurement.backend")` alone (it returns `None` for BOTH a
truly-absent key AND a present-but-malformed `measurement` block, conflating the
two and silently falling back to icmplib on an operator typo — review HIGH #1).**
Only a truly-absent `backend` is silent; a non-dict `measurement` or a
present-but-invalid `backend` (None / non-string / unknown) is `Severity.ERROR`.
(Pitfall 1: do NOT use a `SCHEMA` `choices=` entry — it emits a PASS line for
absent keys and perturbs the CFG-03 delta.) Illustrative shape (executor
finalizes):

```python
import shutil
def validate_measurement_backend(data: dict) -> list[CheckResult]:
    measurement = data.get("measurement")
    if measurement is None and "measurement" not in data:
        return []  # CFG-01: truly absent -> icmplib, silent, NO result
    if not isinstance(measurement, dict):
        return [CheckResult(
            "Measurement Backend", "measurement", Severity.ERROR,
            f"measurement must be a mapping with a backend key, got {type(measurement).__name__}",
            suggestion="Use 'measurement:\\n  backend: icmplib' (or 'fping')",
        )]  # HIGH #1: present-but-malformed (non-dict) -> ERROR
    if "backend" not in measurement:
        return []  # backend sub-key absent (legit: measurement may hold other sub-keys) -> silent
    backend = measurement.get("backend")
    if not isinstance(backend, str) or backend not in MEASUREMENT_BACKENDS:
        return [CheckResult(
            "Measurement Backend", "measurement.backend", Severity.ERROR,
            f"Unknown measurement.backend: {backend!r}. Must be one of: {list(MEASUREMENT_BACKENDS)}",
            suggestion="Use 'icmplib' (default) or 'fping'",
        )]  # CFG-02 + HIGH #1: unknown / None / non-string (incl. 'irtt') -> ERROR
    results = [CheckResult(
        "Measurement Backend", "measurement.backend", Severity.PASS,
        f"measurement.backend: {backend}",
    )]
    if backend == "fping" and shutil.which("fping") is None:
        results.append(CheckResult(
            "Measurement Backend", "measurement.backend", Severity.WARN,
            "measurement.backend is 'fping' but fping binary not found on PATH "
            "(validator host may differ from deploy host -- advisory only)",
            suggestion="Install fping on the deploy host, or rely on Phase 242 runtime fallback",
        ))  # CFG-02: fping+absent -> non-gating WARN (CLI exit 2, not ERROR/exit 1), advisory
    return results
```

**Edit 4 — Wire into the autorate dispatcher** at `_run_autorate_validators`
(`:954-968`). Note this function already uses a local cross-import — add the new
call alongside `validate_linux_cake`:

```python
# src/wanctl/check_config_validators.py:954-968
def _run_autorate_validators(data: dict) -> list[CheckResult]:
    from wanctl.check_steering_validators import validate_linux_cake
    results: list[CheckResult] = []
    results.extend(validate_schema_fields(data))
    results.extend(validate_cross_fields(data))
    results.extend(check_unknown_keys(data))
    # ...
    results.extend(validate_linux_cake(data))
    results.extend(validate_measurement_backend(data))   # NEW (240)
    return results
```

---

### `src/wanctl/check_steering_validators.py` (validator, transform) — MODIFIED

**Analog:** `validate_linux_cake` (`:481-570`, same file) — the canonical
`shutil.which()` → non-gating WARN probe this phase clones; and its dispatcher
`_run_steering_validators` (`:578-592`).

**Asymmetry (Pitfall 2): steering ALREADY has a `measurement:` block.**
`KNOWN_STEERING_PATHS` already contains `measurement`, `measurement.interval_seconds`,
`measurement.ping_host`, `measurement.ping_count` at `:46-49`. So for steering add
**ONLY** the one new leaf — do NOT re-add `measurement`, and do NOT drop the
existing required sub-keys:

```python
# src/wanctl/check_steering_validators.py:46-49 (existing — DO NOT duplicate)
"measurement",
"measurement.interval_seconds",
"measurement.ping_host",
"measurement.ping_count",
```

Add ONLY:

```python
"measurement.backend",
```

**tc-binary probe — the exact pattern to clone for the fping WARN** (lines 547-568):

```python
# src/wanctl/check_steering_validators.py:547-568  (validate_linux_cake step 4)
import shutil
if shutil.which("tc"):
    results.append(CheckResult(
        "Linux CAKE", "tc binary", Severity.PASS, "tc binary found on PATH"))
else:
    results.append(CheckResult(
        "Linux CAKE", "tc binary", Severity.WARN,
        "tc binary not found on PATH",
        suggestion="Install iproute2 or verify PATH includes /usr/sbin",
    ))
```

The 240 fping probe is this verbatim with `tc`→`fping` (lives in the shared
`validate_measurement_backend` helper above, NOT duplicated here).

**Wire into the steering dispatcher** at `_run_steering_validators` (`:578-592`).
This function already locally imports from `check_config_validators` — import the
shared helper the same way:

```python
# src/wanctl/check_steering_validators.py:578-592
def _run_steering_validators(data: dict) -> list[CheckResult]:
    from wanctl.check_config_validators import check_env_vars, check_paths
    # add: validate_measurement_backend  (shared helper, same local-import dodge)
    results: list[CheckResult] = []
    results.extend(validate_steering_schema_fields(data))
    # ...
    results.extend(check_steering_cross_config(data))
    results.extend(validate_measurement_backend(data))   # NEW (240), shared helper
    return results
```

---

### `tests/test_check_config.py` (test, request-response) — MODIFIED

**Analog:** `TestLinuxCakeValidation` (`:1157-1206`) — same file. Mirror its
class structure: a `_make_config` helper plus per-vector tests filtering results
by `Severity`. Imports already present at `:23-35` (`CheckResult`, `Severity`,
`KNOWN_AUTORATE_PATHS`); add `validate_measurement_backend` and `MEASUREMENT_BACKENDS`
to the existing `from wanctl.check_config_validators import (...)` block. Use
`unittest.mock.patch` (already imported `:18`) to monkeypatch `shutil.which`.

**Class structure to mirror** (`:1157-1206`):

```python
class TestLinuxCakeValidation:
    def _make_config(self, transport="linux-cake", cake_params=None):
        data = {"wan_name": "test", "router": {...}}
        ...
        return data

    def test_skips_rest_transport(self):
        results = validate_linux_cake(self._make_config(transport="rest"))
        assert results == []

    def test_valid_cake_params_passes(self):
        results = validate_linux_cake(self._make_config(...))
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0
```

**New tests required (RESEARCH Wave 0 / D-04 vectors):**

- `TestMeasurementBackendValidation` — the 3 decision vectors:
  - absent key → `validate_measurement_backend({...}) == []` (CFG-01)
  - `backend: icmplib` / `fping` (binary present) → PASS, no ERROR (CFG-01)
  - unknown value AND `irtt` → `Severity.ERROR` (CFG-02a; `irtt` must reject)
  - `fping` + `patch("...shutil.which", return_value=None)` → `Severity.WARN`,
    and assert the WARN is non-gating (exit ≠ 1 / not ERROR) (CFG-02b)
- CFG-03 **delta** regression test (Pitfall 3 — do NOT assert exit 0): load real
  `configs/{att,spectrum,steering}.yaml` via `yaml.safe_load`, call
  `_run_autorate_validators(data)` / `_run_steering_validators(data)` directly
  (NOT the `python -m` CLI — Pitfall 4 enum-identity bug), compare key-absent vs
  key-present(valid), assert no NEW ERROR/WARN in Schema Validation + Unknown Keys
  + Measurement Backend categories. File-Paths/Env-Vars noise is constant across
  both runs and must be excluded from the delta.

---

### `scripts/phase240-safe17-boundary-check.sh` (boundary verifier, batch) — CREATED

**Analog:** `scripts/phase239-safe17-boundary-check.sh` (full clone). Reuse the
helper `scripts/phase239-protected-body-diff.py` AS-IS (those protected qualnames
— `RTTMeasurement.__init__`, `BackgroundRTTThread._run`, `WANController.measure_rtt`
— must still be byte-identical; 240 does not touch them).

**The single load-bearing change is the allowlist regex.** 239's regex
(`:15`) excludes all 240 files:

```bash
# scripts/phase239-safe17-boundary-check.sh:15  (TOO NARROW for 240)
V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py|rtt_measurement\.py)$'
```

240 expansion (union with 239 seam files, since anchor stays at `v1.52` and 239's
committed edits must remain in-allowlist — RESEARCH Open Q2 recommends union-at-v1.52):

```bash
V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py|rtt_measurement\.py|check_config_validators\.py|check_steering_validators\.py)$'
```

**Other changes when cloning** (mechanical):
- `ANCHOR="v1.52"` — keep (or anchor at the 239-close commit; union-at-v1.52 is
  more rebase-robust).
- `OUT` / `ALLOWED_OUT_PREFIX` → repoint to the 240 evidence dir
  (`.planning/phases/240-config-validator/evidence/...`).
- The hardcoded disallowed-paths set in the embedded Python (`:89-93`,
  `{"src/wanctl/rtt_backend.py", "src/wanctl/rtt_measurement.py"}`) and the
  error message at `:228` ("Allowed Phase 239 src/wanctl files: ...") must be
  updated to the 240 file set — they are independent of the regex.
- The `notes` string (`:143`) → "Phase 240 boundary check".
- Keep the three preserved guards verbatim: dirty/staged/untracked fail-closed
  (`:199-221`), `--out` path-traversal guards (`:165-180`), and the
  protected-body AST layer invocation (`:241-246`).

**Do NOT edit the 239 script in place** (Anti-pattern / Pitfall 5 — 239 evidence
integrity is anchored to 239's scope). Author a new file.

---

## Shared Patterns

### Binary-probe → non-gating WARN (applied to: fping probe in the shared helper)
**Source:** `src/wanctl/check_steering_validators.py:547-568` (`validate_linux_cake` step 4)
**Apply to:** the `fping` advisory WARN in `validate_measurement_backend`.
```python
import shutil
if shutil.which("tc"):
    results.append(CheckResult("Linux CAKE", "tc binary", Severity.PASS, "tc binary found on PATH"))
else:
    results.append(CheckResult(
        "Linux CAKE", "tc binary", Severity.WARN,
        "tc binary not found on PATH",
        suggestion="Install iproute2 or verify PATH includes /usr/sbin",
    ))
```
WARN never gates (exit 2, not 1) — this is exactly CFG-02's non-gating requirement.

### Severity / CheckResult plumbing (applied to: all new validator results)
**Source:** `src/wanctl/check_config.py:30-46`
**Apply to:** every result `validate_measurement_backend` emits.
```python
class Severity(Enum):
    PASS = "pass"; WARN = "warn"; ERROR = "error"

@dataclass
class CheckResult:
    category: str
    field: str
    severity: Severity
    message: str
    suggestion: str | None = None
```
Do NOT define a new result type or new Severity. **Do NOT import via
`python -m wanctl.check_config`** (Pitfall 4 — double-import creates two distinct
`Severity` enum objects → `KeyError(Severity.PASS)`); call dispatcher functions
directly in tests, use the `wanctl-check-config` console script for CLI evidence.

### Optional-block registry pattern (applied to: both `KNOWN_*_PATHS` additions)
**Source:** `src/wanctl/check_config_validators.py:173-182` (`irtt` block) +
`autorate_config.py:951-962` (`_load_irtt_config` — `.get(..., default)` style)
**Apply to:** registering `measurement` / `measurement.backend`. Register the
path to suppress the unknown-key WARN; do NOT add it to `Config.SCHEMA`
(Pitfall 1). For steering, register ONLY the new leaf (the block pre-exists).

### Local cross-import dodge (applied to: sharing the helper between validators)
**Source:** `_run_autorate_validators:958` and `_run_steering_validators:582` —
both already do function-local `from wanctl.check_* import ...` to avoid the
circular dependency. Import the shared `validate_measurement_backend` the same way.

## No Analog Found

None. Every file has a direct in-codebase analog (most in the same file being
edited). This phase is intentionally pattern-saturated — RESEARCH §Don't Hand-Roll
confirms zero net-new machinery beyond one helper function.

## Metadata

**Analog search scope:** `src/wanctl/` (validators, config base, check_config),
`tests/`, `scripts/` (phase boundary verifiers).
**Files scanned:** `check_config.py`, `check_config_validators.py`,
`check_steering_validators.py`, `tests/test_check_config.py`,
`scripts/phase239-safe17-boundary-check.sh` (+ RESEARCH-supplied anchors for
`config_base.py`, `autorate_config.py`).
**Pattern extraction date:** 2026-06-15
