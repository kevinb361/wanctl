# Phase 240: Config + Validator - Research

**Researched:** 2026-06-15
**Domain:** wanctl YAML config validation (additive enum key + dual validator wiring), SAFE-17 boundary
**Confidence:** HIGH (all claims verified against live code at named file:line anchors)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Wire `measurement.backend` + validation into **both** validators now — `check_config_validators.py` (autorate) AND `check_steering_validators.py` (steering). Additive and inert until Phase 242 (`absent → icmplib` = zero behavior change either way).
- **D-02:** **Minimal.** Register only the `measurement.backend` scalar (enum `icmplib|fping`) under a top-level `measurement:` block. Block name matches the CFG-01 dotted path and the `/health` `measurement` block (Phase 244). Do **not** stub fping sub-params (reflectors, cadence, `-S` binding) — Phase 241.
- **D-03:** Validator probes `shutil.which("fping")` at validate time and emits a **non-gating WARN** when `backend: fping` is selected but the binary is missing. Document env-dependence explicitly: the probe reflects the validator host, which may differ from the deploy target — advisory only. The authoritative absent-binary guarantee is Phase 242's runtime fallback (FALL-01).
- **D-04:** **Both** proof layers — (1) real-config regression: run validator against committed real YAMLs, assert zero new warnings/errors with key absent; (2) unit fixtures for 3 vectors: unknown→ERROR, fping+absent→WARN, absent→silent icmplib.
- **D-04a:** `measurement.backend` MUST be added to `KNOWN_AUTORATE_PATHS` and the steering equivalent so a present-valid key does not trip the "unknown key" WARN, while an absent key trips nothing.

### Claude's Discretion
- Exact `measurement:` block nesting in the schema/`SCHEMA` field-spec mechanism, the precise WARN `Severity` constant reused, the enum-validation helper for `icmplib|fping`, and test file layout — all at planner/executor discretion, provided D-01..D-04a hold and SAFE-17 stays green.
- Whether the `icmplib|fping` enum lives as a shared constant referenced by both validators (vs duplicated) is open — single source of truth preferred, not mandated.

### Deferred Ideas (OUT OF SCOPE)
- fping sub-params (reflector list, cadence, `-S` binding) — Phase 241.
- Backend factory + loud runtime fallback (FALL-01) — Phase 242.
- `/health` backend/source_ip attribution (HEALTH-01) — Phase 244.
- `--assume-fping-present` validator override flag — deferred premature.
- `irtt` as a selectable backend — IRTT-MIG-01, future milestone. The seam carries the `irtt` string value but config does NOT expose it in v1.53. **240 must REJECT `irtt` as unknown.**
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CFG-01 | Operator sets `measurement.backend: icmplib\|fping` per WAN/consumer; absent → icmplib | `measurement.backend` registered in both `KNOWN_*_PATHS`; enum validated by a new cross-field check (NOT a `SCHEMA` entry — see Pitfall 1). Per-WAN = one-config-file-per-WAN layout, no special machinery. |
| CFG-02 | Reject unknown backend (ERROR); WARN non-gating when fping selected + binary absent | `Severity.ERROR` for unknown value via cross-field check; `Severity.WARN` + `shutil.which("fping")` probe mirrors `validate_linux_cake` tc-binary pattern (`check_steering_validators.py:547`). |
| CFG-03 | All existing deploy configs validate unchanged, no migration | Corpus = `configs/{att,spectrum,steering}.yaml`. Proof must be a **delta** (no NEW Schema/Unknown-Keys results), NOT clean exit — corpus already FAILs on environmental path/env checks on dev host (see §Environment + Pitfall 3). |
| SAFE-17 | Additive config/validator surface only; no controller-path drift | Phase 239 verifier allowlist (`rtt_backend.py`, `rtt_measurement.py`) does NOT cover 240's files. Phase 240 needs a **new boundary-check script** with expanded allowlist. See §SAFE-17 Boundary. |
</phase_requirements>

## Summary

Phase 240 adds one inert enum scalar — `measurement.backend: icmplib|fping` — to wanctl's two
offline config validators, with zero migration. The mechanics are well-precedented: the codebase
already has (a) a `KNOWN_*_PATHS` allow-list registry per validator that gates the "unknown key"
WARN, (b) a `Severity` enum (PASS/WARN/ERROR) with WARN already used non-gating in multiple
validators, (c) a `shutil.which()` binary-probe → WARN pattern in `validate_linux_cake`, and (d) an
optional-nested-block precedent (`irtt:`) that is registered in `KNOWN_AUTORATE_PATHS` but
imperatively loaded with defaults rather than schema-validated.

**Three asymmetries the planner must handle:**
1. **Steering already has a `measurement:` block** (`measurement.interval_seconds/ping_host/ping_count`,
   `check_steering_validators.py:46-49`); autorate does NOT. So `measurement.backend` is an *addition
   to an existing block* for steering but a *new top-level block* for autorate.
2. **Enum validation cannot use the `SCHEMA` `choices=` mechanism cleanly** — `validate_field`
   `choices` requires the field to be present-or-required, and a `SCHEMA` entry makes the path part of
   the iterated combined schema. The right pattern is a dedicated cross-field validator function
   (like `_validate_transport_consistency`) that reads `measurement.backend`, defaults absent→icmplib
   silently, ERRORs on unknown, and WARNs on fping+absent-binary. This keeps "absent → no result at
   all" clean. (See Pitfall 1.)
3. **The committed corpus already FAILs validation on the dev host** (missing `/var/log/wanctl`, SSH
   key, unset `${ROUTER_PASSWORD}`). CFG-03's "validate unchanged" must therefore be a **delta
   assertion** scoped to the Schema Validation + Unknown Keys categories — not a clean-exit assertion.
   (See Pitfall 3.)

**Primary recommendation:** Add `measurement.backend` to both `KNOWN_*_PATHS` registries (D-04a),
implement a single shared enum+probe validator helper (e.g. `validate_measurement_backend(data)`)
returning `list[CheckResult]`, call it from both `_run_autorate_validators` and
`_run_steering_validators`, and define the enum as one shared module-level constant
(`MEASUREMENT_BACKENDS = ("icmplib", "fping")`). Prove CFG-03 with a delta test over the real corpus
and 3 hermetic unit vectors. Author a `scripts/phase240-safe17-boundary-check.sh` with an expanded
allowlist covering the four config/validator files.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `measurement.backend` enum validation | Offline validator (`check_*_validators.py`) | — | This is the config-validation tier; no daemon/controller code runs at validate time. |
| Unknown-key gating for the new path | Allow-list registry (`KNOWN_*_PATHS`) | — | Registry is the established additive-key contract; D-04a mandates registration. |
| fping-binary advisory probe | Offline validator (`shutil.which`) | Runtime fallback (Phase 242, FALL-01) | Validator host ≠ deploy host; validator WARN is advisory, runtime fallback is authoritative. |
| absent→icmplib default resolution | Config loader (deferred to Phase 242) | — | 240 leaves the key inert; no loader reads a non-default value yet (D-02). |
| Boundary enforcement | SAFE-17 verifier script (new for 240) | git diff vs v1.52 anchor | Phase 239 verifier allowlist is too narrow; 240 needs its own. |

## Standard Stack

This is an internal-code phase — **no external packages installed.** All work uses the Python
stdlib (`shutil`, `enum`, `difflib` already imported) and the existing in-repo validation
primitives. The `## Package Legitimacy Audit` and most of the package-verification protocol are
**not applicable** (zero new dependencies).

### Reusable In-Repo Primitives (the actual "stack")

| Primitive | Location | Purpose for 240 |
|-----------|----------|-----------------|
| `Severity` (Enum: PASS/WARN/ERROR) | `check_config.py:30-35` | CFG-02 ERROR-on-unknown, D-03 non-gating WARN |
| `CheckResult` (dataclass) | `check_config.py:38-46` | Every validator result; `(category, field, severity, message, suggestion)` |
| `KNOWN_AUTORATE_PATHS: set[str]` | `check_config_validators.py:30-273` | Register `measurement.backend` (D-04a) |
| `KNOWN_STEERING_PATHS: set[str]` | `check_steering_validators.py:25-156` | Register `measurement.backend` (D-04a) — note `measurement` already present |
| `check_unknown_keys` / `check_steering_unknown_keys` | `check_config_validators.py:705`, `check_steering_validators.py:283` | The WARN these registries suppress |
| `validate_linux_cake` (tc probe) | `check_steering_validators.py:481-570` | **Closest analog** for `shutil.which("fping")` → WARN |
| `_get_nested(data, path, default)` | `config_base.py:41-58` | Read `measurement.backend` safely |
| `_run_autorate_validators` | `check_config_validators.py:954-968` | Autorate dispatcher — add the new validator call here |
| `_run_steering_validators` | `check_steering_validators.py:578-592` | Steering dispatcher — add the new validator call here |

## Architecture Patterns

### System Architecture Diagram

```
                       wanctl-check-config <file.yaml>   (console script, check_config.py:main)
                                  │
                        yaml.safe_load(data: dict)
                                  │
                       detect_config_type(data)  ──►  "autorate" | "steering"
                                  │
                ┌─────────────────┴──────────────────┐
                ▼                                     ▼
   _run_autorate_validators(data)         _run_steering_validators(data)
   (check_config_validators.py:954)       (check_steering_validators.py:578)
                │                                     │
   validate_schema_fields ──┐         validate_steering_schema_fields ──┐
   validate_cross_fields    │         validate_steering_cross_fields    │
   check_unknown_keys ◄─ KNOWN_AUTORATE_PATHS  check_steering_unknown_keys ◄─ KNOWN_STEERING_PATHS
   check_paths / check_env_vars        check_paths / check_env_vars
   check_deprecated_params             check_steering_deprecated/cross_config
   validate_linux_cake                 validate_linux_cake (tc-probe analog)
                │                                     │
   ┌── NEW (240): validate_measurement_backend(data) ──┐   ◄── shared helper, called by BOTH
   │   • absent             → [] (no result; resolves icmplib downstream)               │
   │   • "icmplib"/"fping"  → PASS                                                       │
   │   • "irtt"/unknown     → Severity.ERROR  (CFG-02)                                   │
   │   • "fping" + !which   → Severity.WARN   (CFG-02, non-gating, advisory)             │
   └────────────────────────────────────────────────────────────────────────────────────┘
                │                                     │
          list[CheckResult] ───► format_results / format_results_json
                                  │
            exit: 0=clean, 1=any ERROR, 2=WARN-only  (check_config.py:326-334)
```

**File-to-implementation mapping:**
- New validator function: `validate_measurement_backend(data)` — placement is planner's discretion.
  Recommend it live in `check_config_validators.py` (autorate already imports steering helpers and
  vice-versa via local imports; either is fine) and be imported by the steering dispatcher, OR
  duplicated. Shared constant `MEASUREMENT_BACKENDS` recommended (D-disc).
- Registry edits: `KNOWN_AUTORATE_PATHS` (+`measurement`, +`measurement.backend`),
  `KNOWN_STEERING_PATHS` (+`measurement.backend`; `measurement` already present).

### Pattern 1: Optional nested block, registered-but-imperatively-loaded (`irtt:` precedent)

**What:** A YAML block that is optional, registered in `KNOWN_AUTORATE_PATHS` to suppress the
unknown-key WARN, but NOT placed in `SCHEMA` (which would force schema iteration / required-ish
handling). Values are read with `.get(..., default)` and invalid values warn-and-default.
**When to use:** `measurement.backend` for autorate — it is optional and inert.
**Example:**
```python
# Source: src/wanctl/autorate_config.py:951-962  (_load_irtt_config)
irtt = self.data.get("irtt", {})
if not isinstance(irtt, dict):
    logger.warning(f"irtt config must be dict, got {type(irtt).__name__}; using defaults")
    irtt = {}
enabled = irtt.get("enabled", False)   # absent → safe default, no error
```
```python
# Registry side — Source: src/wanctl/check_config_validators.py:173-182
# IRTT measurement (_load_irtt_config)
"irtt",
"irtt.enabled",
# ... block registered as KNOWN even though NOT in Config.SCHEMA
```
For 240, register exactly:
```python
# add to KNOWN_AUTORATE_PATHS (measurement block is NEW for autorate)
"measurement",
"measurement.backend",
# add to KNOWN_STEERING_PATHS ("measurement" already present at :46)
"measurement.backend",
```

### Pattern 2: Binary-probe → non-gating WARN (`validate_linux_cake` tc analog)

**What:** Probe for an external binary at validate time with `shutil.which`; emit WARN (never ERROR)
when absent, because the validator host may differ from the deploy host.
**When to use:** D-03 fping-absent advisory WARN — copy this pattern verbatim, swap `tc`→`fping`.
**Example:**
```python
# Source: src/wanctl/check_steering_validators.py:547-568
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
**240 adaptation (illustrative, executor finalizes):**
```python
import shutil
def validate_measurement_backend(data: dict) -> list[CheckResult]:
    backend = _get_nested(data, "measurement.backend")  # config_base._get_nested
    if backend is None:
        return []  # CFG-01: absent → icmplib, silent, no result emitted
    if backend not in MEASUREMENT_BACKENDS:   # ("icmplib", "fping")
        return [CheckResult(
            "Measurement Backend", "measurement.backend", Severity.ERROR,
            f"Unknown measurement.backend: {backend!r}. Must be one of: {list(MEASUREMENT_BACKENDS)}",
            suggestion="Use 'icmplib' (default) or 'fping'",
        )]  # CFG-02: unknown (incl. 'irtt') → ERROR
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
        ))  # CFG-02: fping+absent → non-gating WARN, advisory
    return results
```

### Anti-Patterns to Avoid
- **Adding `measurement.backend` to `Config.SCHEMA` / `SteeringConfig.SCHEMA` with `choices=`:**
  the combined schema is iterated by `validate_schema_fields` (`check_config_validators.py:297-316`)
  and `validate_field` with `required=False` returns `default` when absent — but a `SCHEMA` entry
  emits a PASS result on every config (changing baseline output) and complicates the "absent → no
  result" contract. Prefer a dedicated cross-field validator (Pattern 2 shape). (See Pitfall 1.)
- **Asserting the corpus validates with exit 0:** it does not on the dev host (Pitfall 3).
- **Allow-listing `irtt` as a selectable backend:** explicitly forbidden (deferred IRTT-MIG-01);
  `irtt` must hit the ERROR branch.
- **Editing the Phase 239 verifier script in place to widen its allowlist:** SAFE-17 evidence
  integrity prefers a new per-phase script; the 239 regex is anchored to 239's scope.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unknown-key detection for new path | Custom path-walker | `KNOWN_*_PATHS` registry + existing `check_unknown_keys` | Already walks + fuzzy-matches (`difflib`); just register the path |
| Binary presence check | `os.system("which fping")` | `shutil.which("fping")` (stdlib) | Already the established pattern (tc probe); no subprocess |
| Nested value read with default | Manual `data.get().get()` chains | `_get_nested(data, "measurement.backend")` | `config_base.py:41`; handles non-dict intermediates safely |
| Severity / result plumbing | New result type | `CheckResult` + `Severity` | Already feeds `format_results` + JSON + exit codes |
| Enum membership check | Schema `choices` (forces SCHEMA entry) | `backend not in MEASUREMENT_BACKENDS` tuple | Keeps absent→no-result clean (Pitfall 1) |

**Key insight:** Every piece of machinery 240 needs already exists and is battle-tested in the
validator. The only net-new code is one small validator function and two registry-line additions.

## Runtime State Inventory

> 240 is additive config/validator surface. It introduces a config KEY but no datastore, service,
> OS, secret, or build-artifact state. The key is inert (nothing reads a non-default value until
> Phase 242). Inventory is near-empty by design.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore keys, IDs, or collection names introduced. Verified: no DB/state-file schema touches in scope. | none |
| Live service config | None — `measurement.backend` is absent from all live configs today; deploying 240 does not require any config edit (absent→icmplib). Verified: `grep measurement.backend configs/` → no hits. | none |
| OS-registered state | None — no systemd units, task names, or process names reference the new key. | none |
| Secrets/env vars | None — `measurement.backend` is a plain enum string, not a secret or env-var name. | none |
| Build artifacts | None — pure-Python addition; no compiled artifacts or egg-info renames. `wanctl-check-config` console script unchanged. | none |

**The canonical question** ("after every file is updated, what runtime systems still cache the old
string?"): N/A — this is an *additive* key with no prior value anywhere. There is no rename. Nothing
to migrate; CFG-03 guarantees absent-key configs are unaffected.

## Common Pitfalls

### Pitfall 1: Using `SCHEMA` `choices=` for the enum (breaks "absent → no result")
**What goes wrong:** Putting `{"path": "measurement.backend", "type": str, "required": False, "choices": ["icmplib","fping"]}`
into `Config.SCHEMA` adds the path to the combined schema iterated by `validate_schema_fields`. With
`required=False` and absent value, `validate_field` returns the default and the iterator emits a
`Severity.PASS` "valid" result (`check_config_validators.py:312`) — so an *absent* key now produces a
new PASS line in baseline output, perturbing the CFG-03 delta and contradicting D-02's "inert".
**Why it happens:** `validate_field` treats `required=False` + absent as "return default, no error"
— which is correct, but the schema iterator still records a PASS per field unconditionally.
**How to avoid:** Implement enum validation as a standalone cross-field validator (Pattern 2 shape)
that returns `[]` when the key is absent. ERROR/WARN/PASS only when the key is present.
**Warning signs:** New PASS lines appear in `format_results` output for configs that don't set the key.

### Pitfall 2: Steering `measurement:` block already exists — don't re-register or shadow it
**What goes wrong:** Treating `measurement` as a brand-new block for steering and re-adding
`measurement` / `measurement.interval_seconds` etc., or forgetting that steering's `measurement`
fields are `required: True` (`steering/daemon.py:161-169`). Adding `measurement.backend` to a
steering config that already has the required `interval_seconds/ping_host/ping_count` is purely
additive and safe.
**Why it happens:** Autorate has no `measurement` block, so the two validators are asymmetric.
**How to avoid:** For steering, add ONLY `"measurement.backend"` to `KNOWN_STEERING_PATHS`
(`measurement` is already at `:46`). For autorate, add BOTH `"measurement"` and `"measurement.backend"`.
**Warning signs:** Duplicate `measurement` entries in `KNOWN_STEERING_PATHS`; steering config fails
because a required sub-key was accidentally dropped.

### Pitfall 3: Treating CFG-03 as "corpus validates with exit 0" (it does NOT on dev host)
**What goes wrong:** Writing the CFG-03 regression as "run validator, assert exit 0 / no errors."
**Verified live:** `configs/att.yaml` → FAIL (4 errors, 2 warns); `spectrum.yaml` → FAIL (4 errors,
3 warns); `steering.yaml` → FAIL (2 errors, 2 warns). All errors are environmental on the dev box:
missing `/var/log/wanctl`, missing `/var/lib/wanctl`, missing SSH key `/etc/wanctl/ssh/router.key`,
unset `${ROUTER_PASSWORD}` / `${DISCORD_WEBHOOK_URL}`. These are File-Paths and Environment-Variables
category results, unrelated to schema/unknown-key logic.
**Why it happens:** The offline validator checks real filesystem paths and env vars that only exist
on the deploy host.
**How to avoid:** Make the CFG-03 proof a **delta** assertion: collect results with `measurement.backend`
absent vs. present (valid), and assert no NEW `ERROR`/`WARN` in the **Schema Validation** and
**Unknown Keys** categories (and no new Measurement-Backend ERROR/WARN for a *valid* key). The
File-Paths/Env-Vars noise is constant across both runs and must be excluded from the delta. Run the
validator programmatically (`_run_autorate_validators(data)` / `_run_steering_validators(data)`)
rather than via the CLI to compare `list[CheckResult]` directly. Recommend parsing real corpus via
`yaml.safe_load(open("configs/att.yaml"))` in the test.
**Warning signs:** A green test on CI that would go red the moment it runs on a clean deploy host, or
a test that asserts exit==0 against the committed corpus.

### Pitfall 4: Enum-identity bug when invoking via `python -m wanctl.check_config`
**What goes wrong:** Running `.venv/bin/python -m wanctl.check_config <file>` raises
`KeyError: <Severity.PASS>` in `_marker` (verified live) because the `-m` invocation can import
`check_config` twice, creating two distinct `Severity` enum objects.
**Why it happens:** Module double-import under `-m` with the local-import circular-dependency dance
between `check_config` and the two validator modules.
**How to avoid:** Invoke the **console script** `wanctl-check-config <file>` (defined in
`pyproject.toml`) for any CLI-level evidence, and call the dispatcher functions directly in tests.
Do NOT use `python -m wanctl.check_config` in plans or evidence scripts.

### Pitfall 5: SAFE-17 — the Phase 239 verifier rejects 240's edits
**What goes wrong:** Running `scripts/phase239-safe17-boundary-check.sh` after 240 edits FAILS,
because its allowlist regex is `^src/wanctl/(rtt_backend\.py|rtt_measurement\.py)$`
(`phase239-safe17-boundary-check.sh:15`) — it does not permit `check_config_validators.py`,
`check_steering_validators.py`, `check_config.py`, or `autorate_config.py`.
**How to avoid:** See §SAFE-17 Boundary — author a new `scripts/phase240-safe17-boundary-check.sh`
with an expanded allowlist, anchored at v1.52 (or v1.53-cumulative), and confirm no controller-path
(state machine / thresholds / EWMA / dwell / deadband / arbitration / fusion) files are touched.

## Code Examples

### Registering the path (both validators)
```python
# Source: src/wanctl/check_config_validators.py (add near line 248, after continuous_monitoring block)
# Measurement backend selection (Phase 240, CFG-01) -- additive, inert until Phase 242
"measurement",
"measurement.backend",
```
```python
# Source: src/wanctl/check_steering_validators.py:46  ("measurement" already present)
# add ONLY:
"measurement.backend",
```

### Wiring into dispatchers
```python
# Source: src/wanctl/check_config_validators.py:954-968  (_run_autorate_validators)
results.extend(validate_measurement_backend(data))   # NEW (240)
# Source: src/wanctl/check_steering_validators.py:578-592  (_run_steering_validators)
results.extend(validate_measurement_backend(data))   # NEW (240), shared helper
```

### Shared enum constant (D-disc, single source of truth)
```python
# Recommended: module-level in check_config_validators.py, imported by steering validator
MEASUREMENT_BACKENDS: tuple[str, ...] = ("icmplib", "fping")  # Phase 240; 'irtt' intentionally excluded (IRTT-MIG-01)
```

## SAFE-17 Boundary

**Verifier located:** `scripts/phase239-safe17-boundary-check.sh` (+ helper
`scripts/phase239-protected-body-diff.py`, test `tests/test_phase239_safe17_verifier.py`).

**How it proves no drift:** three layers — (1) git `diff --name-only v1.52 HEAD -- src/wanctl/`
filtered against an allowlist regex; any path outside the allowlist = VIOLATION (exit 1); (2)
AST-level protected-body byte-identity for named qualnames (`RTTMeasurement.__init__`,
`BackgroundRTTThread._run`, `WANController.measure_rtt`, etc. — `phase239-protected-body-diff.py:21-32`);
(3) allowed-shape check that only `RTTMeasurement.probe` was added. It also fail-closes on any
dirty/staged/untracked `src/wanctl/` tree.

**The blocking fact:** the 239 allowlist regex is
`^src/wanctl/(rtt_backend\.py|rtt_measurement\.py)$` (`phase239-safe17-boundary-check.sh:15`). Phase
240 edits four files NOT in that set:
- `src/wanctl/check_config_validators.py`
- `src/wanctl/check_steering_validators.py`
- `src/wanctl/check_config.py` (only if a constant/helper is added here — minimize)
- `src/wanctl/autorate_config.py` (only if an inert loader is added — D-02 says NO loader in 240, so
  ideally autorate_config.py is **NOT** touched this phase; the key is validated, not loaded)

**Recommended 240 allowlist** (planner finalizes; keep as tight as the actual edits):
```
^src/wanctl/(rtt_backend\.py|rtt_measurement\.py|check_config\.py|check_config_validators\.py|check_steering_validators\.py)$
```
The milestone-level SAFE-17 text (REQUIREMENTS.md:69) already blesses "factory/config/validator/health
wiring" as in-scope for v1.53, so widening the *per-phase* allowlist to the validator files is
consistent with the milestone allowlist — but the 239 *script* hardcodes the narrower 239 scope.

**Action for planner:** create `scripts/phase240-safe17-boundary-check.sh` (clone the 239 structure:
anchor v1.52, dirty-tree fail-closed, name-only allowlist filter) with the expanded regex, and
EXCLUDE all controller-path files. The protected-body AST layer from 239 can be reused as-is (those
qualnames must still be byte-identical — 240 doesn't touch them). Emit evidence JSON under the 240
evidence dir. **Strongly prefer NOT editing `autorate_config.py`** this phase to keep the allowlist
minimal and avoid any appearance of loader/controller drift — validation does not require a loader.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| RTT measurement hardwired to icmplib | `RttBackend` Protocol + `RttSample.backend` string (`icmplib\|irtt\|fping`) | Phase 239 (v1.53) | 240 plumbs the config→string path; no new runtime type |
| SAFE-07..16 zero-diff controller streak | Narrowed SAFE-17 allowlist (controller-path touches permitted within named seam) | v1.53 milestone open | 240 must stay inside config/validator slice of that allowlist |

**Deprecated/outdated:** none relevant to 240.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A new `validate_measurement_backend` cross-field validator is preferable to a `SCHEMA` `choices` entry | Pitfall 1, Pattern 2 | If planner uses SCHEMA choices, an absent key emits a new PASS line — minor baseline perturbation, caught by the CFG-03 delta test. Low risk; both work, this is the cleaner one. |
| A2 | Recommended per-phase SAFE-17 allowlist regex (5 files) | SAFE-17 Boundary | If the actual edit set differs (e.g. no `check_config.py` edit), tighten the regex. Verified by the executor's real diff; the boundary script enforces it. Low risk — script is the ground truth. |
| A3 | CFG-03 delta should scope to Schema Validation + Unknown Keys (+ Measurement Backend) categories | Pitfall 3 | If a deploy host has clean paths, a stricter exit-0 assertion could also work there — but it would be non-portable. Delta is strictly safer. Low risk. |
| A4 | `measurement.backend` placement (which module hosts the helper) is discretionary | Architecture | Both modules already cross-import locally; either placement compiles. Low risk. |

**All other claims in this research are VERIFIED against the named file:line anchors or live tool runs.**

## Open Questions (RESOLVED)

1. **Should the shared enum/helper live in `check_config_validators.py` or a new small module?** **(RESOLVED — helper + `MEASUREMENT_BACKENDS` live in `check_config_validators.py`; steering imports via the existing function-local cross-import dodge. No new module; `check_config.py`/`autorate_config.py` untouched.)**
   - What we know: both validators already do local cross-imports to dodge circular deps; placing
     the helper in `check_config_validators.py` and importing it from the steering dispatcher works.
   - What's unclear: whether the planner prefers a tiny new module (e.g. `measurement_backend.py`)
     to avoid touching `check_config.py` at all.
   - Recommendation: keep the constant + helper in `check_config_validators.py`; import into the
     steering validator. Avoid touching `check_config.py` and `autorate_config.py` to keep the
     SAFE-17 allowlist as small as possible.

2. **Anchor for the 240 boundary check — v1.52 or cumulative HEAD-of-239?** **(RESOLVED — keep `ANCHOR="v1.52"` with the union allowlist {239 seam files} ∪ {240 validator files} for rebase robustness, AND add a SECOND `PHASE239_CLOSE_ANCHOR` diff check proving zero new diff in `rtt_backend.py`/`rtt_measurement.py` relative to the Phase-239 close. The union-at-v1.52 allowlist alone left a false-pass hole — it permits `rtt_backend.py` edits the protected-body helper does not catch [review HIGH #2]; the second anchor closes it.)**
   - What we know: 239 anchored at v1.52 and allowed `rtt_backend.py`/`rtt_measurement.py`. If 240
     anchors at v1.52 too, its allowlist must ALSO include the 239 files (else 239's committed edits
     show as out-of-allowlist drift).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv (`.venv`) | tests, validator | ✓ | 3.11+ | — |
| `wanctl-check-config` console script | CLI evidence | ✓ | installed | call dispatchers directly in tests |
| `fping` binary | D-03 probe (advisory) | (host-dependent) | — | **By design absent-tolerant** — WARN only, never blocks; Phase 242 runtime fallback is authoritative |
| `git` + tag `v1.52` | SAFE-17 anchor | ✓ | tag exists | — |
| pytest / ruff / mypy | `make ci` | ✓ | per pyproject | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `fping` — intentionally optional; its absence is the WARN
path under test, not a blocker.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (per `pyproject.toml`) |
| Config file | `pyproject.toml` (`[tool.pytest]`) + `Makefile` |
| Quick run command | `.venv/bin/pytest tests/test_check_config.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` (or `make ci`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01 | absent key → no result (icmplib resolution); valid key → PASS | unit | `pytest tests/test_check_config.py -k measurement_backend -x` | ❌ Wave 0 (new tests in existing file) |
| CFG-02a | unknown value (incl. `irtt`) → ERROR | unit | same | ❌ Wave 0 |
| CFG-02b | `fping` + binary absent → WARN, non-gating (exit ≠ 1) | unit (monkeypatch `shutil.which`) | same | ❌ Wave 0 |
| CFG-03 | corpus delta: no NEW Schema/Unknown-Keys results with key present | regression | `pytest tests/test_check_config.py -k cfg03 -x` | ❌ Wave 0 |
| SAFE-17 | only allowlisted files changed; protected bodies byte-identical | boundary script | `scripts/phase240-safe17-boundary-check.sh` | ❌ Wave 0 (new script) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_check_config.py -q`
- **Per wave merge:** `make ci` (ruff + mypy + full pytest)
- **Phase gate:** full suite green + `scripts/phase240-safe17-boundary-check.sh` PASS before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test class in `tests/test_check_config.py` (e.g. `TestMeasurementBackendValidation`) —
      covers CFG-01/02a/02b. Mirror `TestLinuxCakeValidation` style; monkeypatch `shutil.which`.
- [ ] CFG-03 delta test loading real `configs/{att,spectrum,steering}.yaml` via `yaml.safe_load`,
      comparing `_run_*_validators(data)` results key-absent vs key-present, asserting no new
      Schema/Unknown-Keys/Measurement-Backend ERROR/WARN. (Excludes File-Paths/Env-Vars noise.)
- [ ] `scripts/phase240-safe17-boundary-check.sh` + evidence dir; optional
      `tests/test_phase240_safe17_verifier.py` mirroring `tests/test_phase239_safe17_verifier.py`.
- No framework install needed — pytest infra exists.

## Project Constraints (from CLAUDE.md)

- **Production network control system — change conservatively.** 240 is additive/inert; no control-path behavior change. Honor priority **stability > safety > clarity > elegance**.
- **Portable controller architecture (NON-NEGOTIABLE):** deployment-specific behavior belongs in YAML, not Python branching. `measurement.backend` is exactly this — a YAML knob, no per-link Python branching. The validator must remain link-agnostic (no Spectrum/ATT-specific logic).
- **Never refactor core logic / algorithms / thresholds / timing without approval.** 240 touches none of these; SAFE-17 enforces it.
- **Prefer targeted fixes over broad cleanup in the control path.** Keep the SAFE-17 allowlist minimal — ideally avoid touching `autorate_config.py` and `check_config.py`.
- **Dev commands:** `.venv/bin/pytest`, `.venv/bin/ruff check src/ tests/`, `.venv/bin/mypy src/wanctl/`, `.venv/bin/ruff format`. Run `project-finalizer` agent before any commit (MANDATORY).
- **Public-safe docs:** no secrets/IPs/hostnames in committed artifacts.

## Sources

### Primary (HIGH confidence — live code at named anchors)
- `src/wanctl/check_config.py:30-46` — `Severity` enum, `CheckResult`; `:269-334` — `main()` exit codes (0/1/2)
- `src/wanctl/check_config_validators.py:30-273` — `KNOWN_AUTORATE_PATHS`; `:173-182` — `irtt` registration precedent; `:290-316` — `validate_schema_fields`; `:705-733` — `check_unknown_keys`; `:954-968` — `_run_autorate_validators`
- `src/wanctl/check_steering_validators.py:25-156` — `KNOWN_STEERING_PATHS` (`measurement` at :46-49); `:481-570` — `validate_linux_cake` (tc-probe analog at :547); `:578-592` — `_run_steering_validators`
- `src/wanctl/config_base.py:41-126` — `_get_nested`, `validate_field` (choices semantics); `:360-390` — `BASE_SCHEMA`, `SCHEMA` mechanism
- `src/wanctl/autorate_config.py:96` — `Config.SCHEMA`; `:637-643` — `ping_source_ip` optional-top-level precedent; `:943-962` — `_load_irtt_config` optional-block precedent
- `src/wanctl/steering/daemon.py:153-175` — `SteeringConfig.SCHEMA` (`measurement.*` required fields); `:248-254` — `_load_rtt_measurement`
- `src/wanctl/rtt_backend.py:36-54` — `RttSample.backend` (`icmplib` default; `irtt` value exists but not config-selectable)
- `scripts/phase239-safe17-boundary-check.sh:15` — allowlist regex (proves 239 verifier excludes 240 files); `scripts/phase239-protected-body-diff.py:21-36` — protected qualnames (reusable)
- `tests/test_check_config.py:467-548` (exit codes, unknown keys), `:1157-1246` (linux-cake/tc WARN style) — test patterns to mirror
- Live runs: `wanctl-check-config configs/{att,spectrum,steering}.yaml --json` → all FAIL on environmental path/env errors (confirms Pitfall 3); `python -m wanctl.check_config` → `KeyError(Severity.PASS)` (confirms Pitfall 4); `git tag` → `v1.52` exists

### Secondary (planning artifacts)
- `.planning/REQUIREMENTS.md` — CFG-01/02/03, SAFE-17 (:69 milestone allowlist text), out-of-scope table
- `.planning/ROADMAP.md:76-85` — Phase 240 entry + 4 success criteria
- `.planning/phases/240-config-validator/240-CONTEXT.md` — D-01..D-04a (authoritative)

### Tertiary (LOW confidence)
- none — all findings verified against live code or tool output.

## Metadata

**Confidence breakdown:**
- Validator mechanics (registry, Severity, dispatch): HIGH — read every relevant function end-to-end.
- Enum-validation approach (cross-field vs SCHEMA): HIGH — verified `validate_field`/iterator behavior; A1 flagged as the recommended-of-two valid options.
- CFG-03 corpus reality: HIGH — ran the validator live against all three configs.
- SAFE-17 boundary: HIGH — read the verifier script; confirmed allowlist excludes 240's files; recommended new script.
- fping probe pattern: HIGH — direct analog (`tc`) exists and is quoted.

**Research date:** 2026-06-15
**Valid until:** 2026-07-15 (stable internal codebase; re-verify only if validator files change before planning)
