# Phase 106: CAKE Optimization Parameters - Research

**Researched:** 2026-03-24
**Domain:** CAKE qdisc parameter construction, YAML config schema, tc command building
**Confidence:** HIGH

## Summary

Phase 106 bridges the gap between the existing `LinuxCakeBackend.initialize_cake(params)` method (Phase 105) and the ecosystem-validated CAKE parameters from the open-source research. The core deliverable is a parameter builder that constructs the correct `params` dict for each WAN link and direction, using a dual-layer approach: hardcoded ecosystem defaults for boolean flags + YAML-configurable tunables for overhead, memlimit, and rtt.

The main technical finding is that the current `initialize_cake()` handles overhead as a numeric key-value pair (`overhead 18`), but the locked decision D-09 specifies using tc overhead **keywords** (`docsis`, `bridged-ptm`), which are standalone tokens on the tc command line. The `initialize_cake()` method needs a minor extension to handle overhead keywords (a standalone token) in addition to the existing numeric overhead (key-value pair). This is the only change needed to the Phase 105 backend code.

**Primary recommendation:** Build a `CakeParamsBuilder` module that takes direction (upload/download) and YAML config, merges hardcoded defaults with operator overrides, and returns the params dict for `initialize_cake()`. Extend `initialize_cake()` to accept an `overhead_keyword` parameter (standalone token) alongside the existing numeric `overhead` parameter.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Dual-layer storage -- hardcoded ecosystem-validated defaults for boolean flags (split-gso always on, ack-filter on upload, ingress+ecn on download) PLUS YAML config for operator-tunable values (overhead keyword, memlimit, rtt, bandwidth limits).
- D-02: Config can override defaults. If YAML specifies `ack-filter: false`, it overrides the upload default. This allows operators to disable features if they cause problems.
- D-03: Default parameter construction builds a complete params dict by merging defaults + config, then passes to `initialize_cake()`.
- D-04: Upload CAKE (modem-side NIC egress): `diffserv4 split-gso ack-filter <overhead-keyword> memlimit 32mb rtt <rtt-value>`
- D-05: Download CAKE (router-side NIC egress): `diffserv4 split-gso ingress ecn <overhead-keyword> memlimit 32mb rtt <rtt-value>`
- D-06: Spectrum overhead: `docsis` keyword (= overhead 18, mpu 64, noatm)
- D-07: ATT overhead: `bridged-ptm` keyword (= overhead 22, noatm)
- D-08: Explicitly excluded: `nat` (no conntrack on bridge), `wash` (DSCP marks must survive), `autorate-ingress` (wanctl IS the autorate system)
- D-09: Use tc overhead keywords (`docsis`, `bridged-ptm`) in YAML config, not raw numeric values. Keywords are self-documenting and canonical per tc-cake(8). The keyword is a string in YAML: `overhead: "docsis"`.
- D-10: `rtt` is configurable in YAML with default `100ms`. Not hardcoded to 50ms.
- D-11: `rtt` is a candidate for adaptive tuning (v1.20 infrastructure). Not implemented in this phase -- just declared as tunable.
- D-12: Default `memlimit: "32mb"` for ~1Gbps links. Configurable per-link in YAML.

### Claude's Discretion
- YAML config schema structure (how cake_params section is organized)
- Builder function/class design for constructing params dict from config + defaults
- Test fixtures and assertion patterns
- Whether to add a helper for per-direction param construction

### Deferred Ideas (OUT OF SCOPE)
- Adaptive tuning of `rtt` parameter -- infrastructure exists in v1.20, integration deferred
- `diffserv8` mode for finer classification -- would require mangle rule expansion
- Per-tin bandwidth allocation tuning -- custom tin ratios
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAKE-01 | `split-gso` enabled to split TSO/GSO segments before queuing | Hardcoded default=True in builder; ecosystem-confirmed universal pattern |
| CAKE-02 | ECN marking enabled for explicit congestion notification (download CAKE) | Hardcoded default=True on download direction only; builder direction-aware |
| CAKE-03 | `ack-filter` enabled for ACK compression on upload | Hardcoded default=True on upload direction only; builder direction-aware |
| CAKE-05 | Precise `overhead`/`mpu` configured per-link (`docsis` for Spectrum, `bridged-ptm` for ATT) | Overhead keywords are standalone tc tokens; extend initialize_cake for keyword support |
| CAKE-06 | `memlimit` configured for bounded memory usage (32MB for ~1Gbps links) | YAML configurable with "32mb" default; pass as string to tc |
| CAKE-08 | `ingress` keyword on download CAKE for tighter drop accounting | Hardcoded default=True on download direction only |
| CAKE-09 | `ecn` on download CAKE for softer congestion signaling than drops | Same as CAKE-02; ecn on download direction only |
| CAKE-10 | `rtt` parameter configured per-link (candidate for adaptive tuning, default 100ms) | YAML configurable with "100ms" default; string passed to tc; marked tunable |
</phase_requirements>

## Architecture Patterns

### Critical Finding: Overhead Keyword vs Numeric Overhead

The current `initialize_cake()` in `linux_cake.py` handles overhead as a numeric key-value pair:
```python
if "overhead" in params:
    cmd_args.extend(["overhead", str(params["overhead"])])
```

This produces `tc qdisc replace ... overhead 18 ...`. However, the tc-cake(8) overhead **keywords** (`docsis`, `bridged-ptm`) are standalone tokens appended directly to the command line -- they are NOT preceded by `overhead`:

```bash
# CORRECT: keyword is standalone
tc qdisc replace dev eth0 root cake diffserv4 docsis memlimit 32mb

# INCORRECT: keyword is not a value of "overhead"
tc qdisc replace dev eth0 root cake diffserv4 overhead docsis memlimit 32mb
```

The keyword `docsis` expands internally to `overhead 18 mpu 64 noatm`. The keyword `bridged-ptm` expands to `overhead 22 noatm`.

**Action required:** Add `overhead_keyword` support to `initialize_cake()` as a standalone token, separate from the existing numeric `overhead` key-value handler.

### tc JSON Readback Values

When `docsis` keyword is used, `tc -j qdisc show` returns **numeric** values:
```json
{
    "overhead": 18,
    "rtt": 100000,
    "split_gso": true,
    "ack-filter": "ack-filter",
    "ingress": true,
    "memlimit": 33554432
}
```

Key mappings for `validate_cake()`:
- `overhead`: numeric (18 for docsis, 22 for bridged-ptm)
- `rtt`: microseconds integer (100000 = 100ms)
- `memlimit`: bytes integer (33554432 = 32MB)
- `split_gso`: boolean (note underscore, not hyphen)
- `ack-filter`: string "ack-filter" when enabled, "disabled" when disabled
- `ingress`: boolean
- `ecn`: not shown in test fixture -- needs verification on live system

### Overhead Keyword to Numeric Mapping

For `validate_cake()` readback verification:

| Keyword | overhead | mpu | atm |
|---------|----------|-----|-----|
| `docsis` | 18 | 64 | noatm |
| `bridged-ptm` | 22 | n/a | noatm |
| `ethernet` | 38 | 84 | noatm |
| `pppoe-ptm` | 30 | n/a | noatm |

The builder should provide both: the keyword (for `initialize_cake`) and the expected numeric readback (for `validate_cake`).

### Recommended Project Structure

```
src/wanctl/
├── backends/
│   └── linux_cake.py          # MODIFY: add overhead_keyword support to initialize_cake
├── cake_params.py             # NEW: CakeParamsBuilder + direction defaults + validation
└── config_validation_utils.py # EXISTS: reuse validation patterns
tests/
├── test_linux_cake_backend.py # EXISTS: extend for overhead_keyword tests
└── test_cake_params.py        # NEW: builder tests (defaults, overrides, validation)
```

### Pattern: CakeParamsBuilder

```python
# Source: CONTEXT.md decisions D-01 through D-12

# Direction-aware hardcoded defaults (D-01, D-04, D-05)
UPLOAD_DEFAULTS: dict[str, Any] = {
    "diffserv": "diffserv4",
    "split-gso": True,
    "ack-filter": True,    # Upload only (D-04)
    "ingress": False,       # Download only
    "ecn": False,           # Download only
}

DOWNLOAD_DEFAULTS: dict[str, Any] = {
    "diffserv": "diffserv4",
    "split-gso": True,
    "ack-filter": False,    # Upload only
    "ingress": True,        # Download only (D-05)
    "ecn": True,            # Download only (D-05)
}

# Tunable defaults (D-10, D-12)
TUNABLE_DEFAULTS: dict[str, str] = {
    "memlimit": "32mb",     # D-12
    "rtt": "100ms",         # D-10
}

# Valid overhead keywords (D-06, D-07, D-09)
VALID_OVERHEAD_KEYWORDS: set[str] = {
    "docsis", "bridged-ptm", "ethernet", "pppoe-ptm",
    "bridged-llcsnap", "pppoa-vcmux", "pppoa-llc",
    "pppoe-vcmux", "pppoe-llcsnap", "conservative", "raw",
}

# Keyword -> expected tc JSON readback values
OVERHEAD_READBACK: dict[str, dict[str, int]] = {
    "docsis": {"overhead": 18, "mpu": 64},
    "bridged-ptm": {"overhead": 22},
    "ethernet": {"overhead": 38, "mpu": 84},
}


def build_cake_params(
    direction: str,
    config: dict[str, Any] | None = None,
    bandwidth_kbit: int | None = None,
) -> dict[str, Any]:
    """Build CAKE params dict for initialize_cake().

    Merges direction-aware hardcoded defaults with YAML config overrides.
    Boolean flags from config override defaults (D-02).

    Args:
        direction: "upload" or "download"
        config: YAML cake_params section (may override defaults)
        bandwidth_kbit: Initial bandwidth in kbit (optional)

    Returns:
        Complete params dict for LinuxCakeBackend.initialize_cake()
    """
    ...


def build_expected_readback(
    params: dict[str, Any],
) -> dict[str, Any]:
    """Convert params dict to expected tc JSON readback values.

    Maps overhead keywords to numeric values, rtt strings to microseconds,
    memlimit strings to bytes -- for use with validate_cake().

    Returns:
        Dict of expected values matching tc -j qdisc show format.
    """
    ...
```

### Pattern: YAML Config Schema

The existing `cake_optimization` section name is already referenced in `check_cake.py` (`_extract_cake_optimization()`). The new config section should be compatible or replace it.

Recommended YAML schema (fits existing project patterns):

```yaml
# Per-link CAKE optimization parameters
cake_params:
  overhead: "docsis"        # or "bridged-ptm" -- tc keyword, not numeric
  memlimit: "32mb"          # tc memlimit value (default 32mb)
  rtt: "100ms"              # tc rtt value (default 100ms, tunable)
  # Boolean overrides (optional -- defaults are direction-aware)
  # split_gso: true         # default: true
  # ack_filter: true        # default: true on upload, false on download
  # ingress: false          # default: false on upload, true on download
  # ecn: false              # default: false on upload, true on download
```

**Note on naming:** Use `cake_params` (not `cake_optimization`) to avoid confusion with the existing `cake_optimization` section in `check_cake.py` which validates MikroTik CAKE queue types. The new section is for Linux CAKE. Alternatively, reuse `cake_optimization` but extend it -- this is Claude's discretion per CONTEXT.md.

### Pattern: initialize_cake Extension

```python
# Extend existing initialize_cake() to handle overhead_keyword
def initialize_cake(self, params: dict[str, Any]) -> bool:
    cmd_args = ["qdisc", "replace", "dev", self.interface, "root", "cake"]

    # Key-value params (existing)
    if "bandwidth" in params:
        cmd_args.extend(["bandwidth", str(params["bandwidth"])])
    if "diffserv" in params:
        cmd_args.append(str(params["diffserv"]))

    # NEW: overhead keyword as standalone token (D-09)
    if "overhead_keyword" in params:
        cmd_args.append(str(params["overhead_keyword"]))
    elif "overhead" in params:
        # Fallback: numeric overhead (existing behavior)
        cmd_args.extend(["overhead", str(params["overhead"])])
    if "mpu" in params:
        cmd_args.extend(["mpu", str(params["mpu"])])

    if "memlimit" in params:
        cmd_args.extend(["memlimit", str(params["memlimit"])])
    if "rtt" in params:
        cmd_args.extend(["rtt", str(params["rtt"])])

    # Boolean flags
    for flag in ("split-gso", "ack-filter", "ingress", "ecn"):
        if params.get(flag):
            cmd_args.append(flag)

    # ... rest unchanged
```

### Anti-Patterns to Avoid

- **Passing keyword as numeric `overhead` value:** `overhead docsis` is not valid tc syntax. Use standalone keyword.
- **Hardcoding link-specific parameters in Python:** Overhead keyword belongs in YAML config (per-link), not in code.
- **Conflating upload and download defaults:** ack-filter is upload-only; ingress/ecn are download-only. The builder must be direction-aware.
- **Ignoring validate_cake readback format:** tc returns numeric values for keywords (overhead=18, rtt=100000us, memlimit=33554432bytes). Validation must use the numeric equivalents.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Overhead byte calculations | Manual overhead arithmetic per link type | tc overhead keywords (`docsis`, `bridged-ptm`) | Keywords encapsulate correct overhead+mpu+atm settings; no room for error |
| YAML config loading | Custom YAML parser | `config_base.py` BaseConfig + validate_schema() | Existing project pattern with schema validation, type checking, range limits |
| Boolean flag override logic | Complex if/elif chains | Dict merge: `{**defaults, **config_overrides}` | Standard Python dict merge handles override semantics cleanly |
| Validation readback mapping | Hardcoded expected values per test | `OVERHEAD_READBACK` constant dict | Single source of truth for keyword-to-numeric mapping, reusable by tests |

## Common Pitfalls

### Pitfall 1: Overhead Keyword Syntax in tc Command
**What goes wrong:** Passing `overhead docsis` (key-value) instead of just `docsis` (standalone)
**Why it happens:** The existing `initialize_cake` uses key-value pattern for all params
**How to avoid:** Add explicit `overhead_keyword` handling as standalone token before the numeric `overhead` fallback
**Warning signs:** tc returns `RTNETLINK answers: Invalid argument` at startup

### Pitfall 2: validate_cake Readback Type Mismatch
**What goes wrong:** Expecting `"100ms"` in readback but getting `100000` (microseconds integer)
**Why it happens:** tc JSON returns internal numeric representation, not the human-readable string
**How to avoid:** Build a `build_expected_readback()` function that converts params to tc JSON format: `"100ms" -> 100000`, `"32mb" -> 33554432`, `"docsis" -> {"overhead": 18}`
**Warning signs:** validate_cake always returns False despite correct CAKE setup

### Pitfall 3: Config Override Accidentally Enabling Excluded Parameters
**What goes wrong:** YAML config specifies `nat: true` or `wash: true` which are anti-features for the bridge topology
**Why it happens:** Operator copies config from a router-based setup
**How to avoid:** Validate config against excluded parameters (D-08): warn or error if `nat`, `wash`, or `autorate-ingress` are set
**Warning signs:** Unexpected CAKE behavior, DSCP marks stripped

### Pitfall 4: Missing Overhead Keyword Validation
**What goes wrong:** YAML specifies `overhead: "foobar"` which is not a valid tc keyword
**Why it happens:** No validation of the overhead string against known keywords
**How to avoid:** Validate overhead value against `VALID_OVERHEAD_KEYWORDS` set at config load time
**Warning signs:** `initialize_cake()` fails with cryptic tc error at daemon startup

### Pitfall 5: Boolean Override Semantics
**What goes wrong:** Operator sets `ack-filter: false` in YAML but it is still enabled
**Why it happens:** Dict merge uses truthy check; `False` is falsy and gets skipped
**How to avoid:** Explicitly handle `False` values in the builder -- if config sets a boolean to `False`, that must override the default. Use `if key in config` rather than `if config.get(key)`
**Warning signs:** Operator cannot disable features via config

### Pitfall 6: YAML Key Naming (Hyphens vs Underscores)
**What goes wrong:** YAML uses `split-gso: true` but Python dict access requires quotes for hyphens
**Why it happens:** YAML parses `split-gso` as a key just fine, but it looks odd and Python convention prefers underscores
**How to avoid:** Use underscore variants in YAML (`split_gso`, `ack_filter`) and translate to hyphen variants for tc commands. The builder handles the mapping.
**Warning signs:** KeyError when accessing config, or silent mismatches between YAML and tc params

## Code Examples

### Complete Param Builder (Recommended Implementation)
```python
# Source: CONTEXT.md D-01 through D-12, OPENSOURCE-CAKE.md

from typing import Any

UPLOAD_DEFAULTS: dict[str, Any] = {
    "diffserv": "diffserv4",
    "split-gso": True,
    "ack-filter": True,
    "ingress": False,
    "ecn": False,
}

DOWNLOAD_DEFAULTS: dict[str, Any] = {
    "diffserv": "diffserv4",
    "split-gso": True,
    "ack-filter": False,
    "ingress": True,
    "ecn": True,
}

TUNABLE_DEFAULTS: dict[str, str] = {
    "memlimit": "32mb",
    "rtt": "100ms",
}

DIRECTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "upload": UPLOAD_DEFAULTS,
    "download": DOWNLOAD_DEFAULTS,
}

# Excluded params that must never appear (D-08)
EXCLUDED_PARAMS: set[str] = {"nat", "wash", "autorate-ingress"}

# YAML key (underscore) -> tc param key (hyphen)
YAML_TO_TC_KEY: dict[str, str] = {
    "split_gso": "split-gso",
    "ack_filter": "ack-filter",
    "autorate_ingress": "autorate-ingress",
}


def build_cake_params(
    direction: str,
    cake_config: dict[str, Any] | None = None,
    bandwidth_kbit: int | None = None,
) -> dict[str, Any]:
    """Build params dict for LinuxCakeBackend.initialize_cake().

    Args:
        direction: "upload" or "download"
        cake_config: YAML cake_params section (operator overrides)
        bandwidth_kbit: Initial bandwidth in kbit/s

    Returns:
        Complete params dict ready for initialize_cake()
    """
    if direction not in DIRECTION_DEFAULTS:
        raise ValueError(f"Invalid direction: {direction!r}")

    # Start with direction-specific defaults
    params: dict[str, Any] = dict(DIRECTION_DEFAULTS[direction])

    # Add tunable defaults
    params.update(TUNABLE_DEFAULTS)

    # Apply config overrides (D-02)
    if cake_config:
        for key, value in cake_config.items():
            tc_key = YAML_TO_TC_KEY.get(key, key)
            if tc_key in EXCLUDED_PARAMS:
                raise ConfigValidationError(
                    f"Excluded CAKE parameter: {key!r} -- "
                    f"not valid for transparent bridge topology"
                )
            params[tc_key] = value

    # Set overhead keyword (standalone token for tc)
    overhead = params.pop("overhead", None)
    if overhead and isinstance(overhead, str):
        params["overhead_keyword"] = overhead

    # Set bandwidth if provided
    if bandwidth_kbit is not None:
        params["bandwidth"] = f"{bandwidth_kbit}kbit"

    return params
```

### Readback Builder for validate_cake
```python
# Source: tc -j qdisc show output format (test_linux_cake_backend.py fixtures)

# Keyword -> tc JSON readback values
OVERHEAD_READBACK: dict[str, dict[str, int]] = {
    "docsis": {"overhead": 18},
    "bridged-ptm": {"overhead": 22},
    "ethernet": {"overhead": 38},
}

RTT_TO_MICROSECONDS: dict[str, int] = {
    "100ms": 100_000,
    "50ms": 50_000,
    "30ms": 30_000,
}

MEMLIMIT_TO_BYTES: dict[str, int] = {
    "32mb": 33_554_432,
    "16mb": 16_777_216,
    "64mb": 67_108_864,
}


def build_expected_readback(params: dict[str, Any]) -> dict[str, Any]:
    """Convert initialize_cake params to validate_cake expected values.

    Maps human-readable params to tc JSON numeric format.
    """
    expected: dict[str, Any] = {}

    if "overhead_keyword" in params:
        kw = params["overhead_keyword"]
        if kw in OVERHEAD_READBACK:
            expected.update(OVERHEAD_READBACK[kw])

    if "diffserv" in params:
        expected["diffserv"] = params["diffserv"]

    if "rtt" in params:
        rtt_str = str(params["rtt"])
        expected["rtt"] = RTT_TO_MICROSECONDS.get(rtt_str, int(rtt_str.rstrip("ms")) * 1000)

    if "memlimit" in params:
        ml_str = str(params["memlimit"])
        expected["memlimit"] = MEMLIMIT_TO_BYTES.get(ml_str, int(ml_str))

    return expected
```

### Config Validation Pattern
```python
# Source: config_base.py validate_field pattern, config_validation_utils.py

VALID_OVERHEAD_KEYWORDS: set[str] = {
    "docsis", "bridged-ptm", "ethernet", "pppoe-ptm",
    "bridged-llcsnap", "pppoa-vcmux", "pppoa-llc",
    "pppoe-vcmux", "pppoe-llcsnap", "conservative", "raw",
}

CAKE_PARAMS_SCHEMA: list[dict] = [
    {
        "path": "cake_params.overhead",
        "type": str,
        "required": True,
        "choices": list(VALID_OVERHEAD_KEYWORDS),
    },
    {
        "path": "cake_params.memlimit",
        "type": str,
        "required": False,
        "default": "32mb",
    },
    {
        "path": "cake_params.rtt",
        "type": str,
        "required": False,
        "default": "100ms",
    },
]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| sqm-scripts STAB string (`stab mtu ... overhead ...`) | CAKE built-in keywords (`docsis`, `bridged-ptm`) | CAKE inclusion in kernel 4.19 (2018) | Keywords are simpler, self-documenting, less error-prone |
| IFB for ingress shaping | Bridge member port egress | Transparent bridge topology | Eliminates virtual device overhead (5% per MagicBox) |
| MikroTik queue types (cake overhead 18) | Linux tc overhead keywords | v1.21 CAKE offload | Direct tc control, no MikroTik queue type intermediary |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_cake_params.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAKE-01 | split-gso in both upload and download defaults | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k split_gso` | Wave 0 |
| CAKE-02 | ecn in download defaults only | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k ecn` | Wave 0 |
| CAKE-03 | ack-filter in upload defaults only | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k ack_filter` | Wave 0 |
| CAKE-05 | overhead keyword per-link from config | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k overhead` | Wave 0 |
| CAKE-06 | memlimit default 32mb, configurable | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k memlimit` | Wave 0 |
| CAKE-08 | ingress in download defaults only | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k ingress` | Wave 0 |
| CAKE-09 | ecn on download (same as CAKE-02) | unit | (covered by CAKE-02) | Wave 0 |
| CAKE-10 | rtt default 100ms, configurable | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k rtt` | Wave 0 |
| BACK-03 ext | overhead_keyword produces correct tc command | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py -x -k overhead_keyword` | Wave 0 |
| Validation | readback builder maps keyword to numeric | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k readback` | Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_cake_params.py tests/test_linux_cake_backend.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cake_params.py` -- covers CAKE-01 through CAKE-10 via builder tests
- [ ] `src/wanctl/cake_params.py` -- the builder module itself (test-first pattern)

*(Existing `tests/test_linux_cake_backend.py` covers backend; only needs overhead_keyword extension)*

## Open Questions

1. **YAML Section Naming: `cake_params` vs `cake_optimization`**
   - What we know: `check_cake.py` already uses `_extract_cake_optimization()` referencing `cake_optimization` section for MikroTik CAKE queue type validation. That section stores `overhead` (numeric) and `rtt` (string).
   - What's unclear: Should Phase 106 reuse `cake_optimization` or create a new `cake_params` section? Reusing avoids duplication but the semantics differ (MikroTik numeric overhead vs Linux keyword overhead).
   - Recommendation: Use `cake_params` for the new Linux CAKE builder. If needed later, `cake_optimization` can be deprecated and migrated via `deprecate_param()` pattern. This keeps the two use cases cleanly separated during the transition from MikroTik to Linux CAKE.

2. **ECN readback format in tc JSON**
   - What we know: Test fixture does not include an `ecn` field in the options JSON. The `ingress` field is a boolean; `ack-filter` is a string.
   - What's unclear: Whether tc JSON reports ECN as boolean, string, or not at all in the options dict.
   - Recommendation: Omit ECN from `validate_cake` expected readback initially; verify format on live system during Phase 109 deployment.

3. **Memlimit String Parsing**
   - What we know: tc accepts `memlimit 32mb` on command line. The JSON readback shows `"memlimit": 33554432` (bytes integer).
   - What's unclear: Whether tc accepts other suffixes (KB, GB) and what their exact byte conversions are.
   - Recommendation: Support the common set (`mb`, `kb`, `gb`) in the readback converter with explicit mapping. Use `32mb` default per D-12.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/backends/linux_cake.py` -- actual `initialize_cake()` implementation, params dict contract
- `tests/test_linux_cake_backend.py` -- tc JSON fixture data showing readback format (overhead=18, rtt=100000, memlimit=33554432)
- `.planning/research/OPENSOURCE-CAKE.md` -- ecosystem-validated tc command patterns per link type
- `src/wanctl/check_cake.py` -- existing `_extract_cake_optimization()` function and `check_link_params()` showing cake_optimization config pattern
- [tc-cake(8) Linux manual page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- authoritative CAKE parameter documentation, overhead keyword syntax

### Secondary (MEDIUM confidence)
- `src/wanctl/config_base.py` -- BaseConfig, validate_schema(), validate_field() patterns
- `src/wanctl/autorate_continuous.py` -- Config class showing SCHEMA, `_load_specific_fields()`, config loading patterns
- `configs/examples/cable.yaml.example` -- existing YAML config structure for reference

### Tertiary (LOW confidence)
- ECN readback format -- not confirmed on live system, inferred from pattern similarity to ingress/ack-filter

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new deps, all stdlib + existing patterns
- Architecture: HIGH -- CONTEXT.md decisions are exhaustive; only overhead keyword gap needed discovery
- Pitfalls: HIGH -- overhead keyword syntax verified against tc-cake(8) man page and existing test fixtures

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable domain -- tc-cake interface does not change frequently)
