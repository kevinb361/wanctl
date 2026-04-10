# Phase 107: Config & Factory Wiring - Research

**Researched:** 2026-03-24
**Domain:** Config system integration, factory pattern, CLI validation
**Confidence:** HIGH

## Summary

Phase 107 wires the LinuxCakeBackend (built in Phases 105-106) into the existing config system and factory. Three concrete changes: (1) extend `get_backend()` factory to route `"linux-cake"` transport to `LinuxCakeBackend`, (2) update `LinuxCakeBackend.from_config()` to read `cake_params.upload_interface`/`download_interface` from config, (3) add linux-cake validators to `wanctl-check-config`.

The existing code is clean and well-factored. The factory (`get_backend()`) currently keys on `config.router.get("type", "routeros")` -- a dict field, not a Config attribute. The `get_router_client()` factory in `router_client.py` keys on `config.router_transport` (a Config attribute). These are two separate factory paths. The CONTEXT.md decisions specify adding a branch to `get_backend()`, which is correct since `LinuxCakeBackend` implements `RouterBackend` ABC.

**Primary recommendation:** Three surgical changes across three files: `backends/__init__.py` (factory branch), `backends/linux_cake.py` (from_config update), `check_config.py` (linux-cake validators + KNOWN_AUTORATE_PATHS). Keep changes minimal and backward-compatible.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Extend existing `router_transport` field to accept `"linux-cake"` as a third value alongside `"rest"` and `"ssh"`. No new transport field -- reuse the established pattern.
- D-02: Bridge interface names go under the `cake_params` YAML section (created in Phase 106): `upload_interface: "eth0"` and `download_interface: "eth1"`.
- D-03: The `cake_params` section is only required when `router_transport: "linux-cake"`. When transport is `rest` or `ssh`, its absence is not an error.
- D-04: Add `"linux-cake"` branch to `get_backend()` in `backends/__init__.py`. When selected, creates `LinuxCakeBackend.from_config(config)`.
- D-05: `LinuxCakeBackend.from_config(config)` reads `cake_params.upload_interface` or `cake_params.download_interface` from config to set the interface. Direction is determined by the daemon context (upload vs download instance).
- D-06: Factory change is surgical -- no changes to WANController, SteeringDaemon, or any existing code paths. Existing `routeros` path is unchanged.
- D-07: When `router_transport: "linux-cake"`, `wanctl-check-config` validates: (1) `cake_params` section exists and is a dict, (2) `upload_interface` and `download_interface` are specified (required strings), (3) `overhead` keyword is valid (one of: docsis, bridged-ptm, ethernet, raw), (4) `tc` binary exists at `/usr/sbin/tc` or in PATH.
- D-08: Interface existence checks (does the NIC exist on the system) are NOT performed -- `check-config` is an offline validator. Runtime checks happen in `test_connection()`.
- D-09: Existing check-config validations for `rest`/`ssh` transport are unchanged.

### Claude's Discretion
- `from_config()` parameter extraction patterns
- Test fixture structure for config validation tests
- Error message wording

### Deferred Ideas (OUT OF SCOPE)
- WANController integration with LinuxCakeBackend -- requires deeper wiring than factory alone
- Steering daemon dual-backend config -- Phase 108 scope
- Config migration tool from MikroTik to linux-cake YAML -- nice-to-have, not required
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONF-01 | `transport: "linux-cake"` config option with bridge interface names in YAML | Factory routing key, cake_params section with upload_interface/download_interface, KNOWN_AUTORATE_PATHS update |
| CONF-02 | Factory function selects LinuxCakeBackend based on transport config | get_backend() elif branch, from_config() interface extraction, import wiring |
| CONF-04 | `wanctl-check-config` validates linux-cake transport settings and interface existence | New validate_linux_cake() function, cake_params dict check, overhead keyword validation, tc binary check via shutil.which |
</phase_requirements>

## Architecture Patterns

### Current Factory Architecture (Two Separate Paths)

There are two distinct factory paths in the codebase. Understanding this is critical:

1. **`get_backend()` in `backends/__init__.py`** -- Keys on `config.router.get("type", "routeros")`. Returns a `RouterBackend` ABC implementation. Currently only returns `RouterOSBackend`. **This is where Phase 107 adds the linux-cake branch (D-04).**

2. **`get_router_client()` in `router_client.py`** -- Keys on `config.router_transport` attribute (string, defaults to `"rest"`). Returns `RouterOSSSH` or `RouterOSREST`. Used by the `RouterOS` class in `autorate_continuous.py` for queue tree commands. **NOT modified in Phase 107.**

The `get_backend()` factory is not yet called in production code -- it was built as infrastructure in earlier phases. Phase 108 (steering dual-backend) will likely integrate it. For Phase 107, we add the branch and ensure it works via unit tests.

### Factory Key Alignment Issue

The `get_backend()` factory currently keys on `config.router["type"]` (a raw dict lookup), while the decision D-01 specifies extending `router_transport` (a Config attribute loaded in `_load_router_transport_config`). The factory must be updated to check `router_transport` rather than `router.type` to align with the established transport pattern.

**Recommendation:** Update `get_backend()` to read `config.router_transport` (like `get_router_client()` does). This aligns both factory functions on the same config attribute. The function signature takes a Config object, so `getattr(config, "router_transport", "rest")` is the safe pattern (matches `router_client.py` line 77).

### from_config() Wiring

Current `LinuxCakeBackend.from_config()` reads:
```python
interface = config.router["interface"]  # single interface
tc_timeout = config.timeouts.get("tc_command", 5.0) if hasattr(config, "timeouts") else 5.0
```

Problems:
1. Config class has no `self.timeouts` dict attribute -- `hasattr(config, "timeouts")` is always False on a real Config object. The tc_timeout always falls back to 5.0. This is benign but should be fixed.
2. Single `interface` field does not match D-02 which specifies `cake_params.upload_interface` and `cake_params.download_interface`.
3. Per D-05, direction is determined by daemon context, not by from_config(). The from_config() method needs to accept an interface parameter or the direction must be passed in.

**Recommendation for from_config():**
```python
@classmethod
def from_config(cls, config: Any, direction: str = "download") -> "LinuxCakeBackend":
    cake_params = config.data.get("cake_params", {})
    if direction == "upload":
        interface = cake_params["upload_interface"]
    else:
        interface = cake_params["download_interface"]
    tc_timeout = config.data.get("timeouts", {}).get("tc_command", 5.0)
    return cls(interface=interface, tc_timeout=tc_timeout)
```

Or the factory could pass the interface directly:
```python
@classmethod
def from_config(cls, config: Any, interface: str | None = None) -> "LinuxCakeBackend":
    if interface is None:
        interface = config.data.get("cake_params", {}).get("download_interface", "eth0")
    tc_timeout = config.data.get("timeouts", {}).get("tc_command", 5.0)
    return cls(interface=interface, tc_timeout=tc_timeout)
```

### check-config Validator Pattern

The existing validator architecture in `check_config.py`:
1. Category-based validators: each returns `list[CheckResult]`
2. Dispatchers: `_run_autorate_validators()` and `_run_steering_validators()` aggregate all category results
3. Known paths: `KNOWN_AUTORATE_PATHS` set prevents false "unknown key" warnings
4. Transport-aware checks: `check_paths()` already reads `router.transport` to decide SSH key severity

**New validator function pattern:**
```python
def validate_linux_cake(data: dict) -> list[CheckResult]:
    """Validate linux-cake transport-specific settings."""
    results: list[CheckResult] = []
    transport = _get_nested(data, "router.transport", "rest")
    if transport != "linux-cake":
        return results  # Only validate when linux-cake is selected

    # 1. cake_params section exists
    cake_params = data.get("cake_params")
    if not isinstance(cake_params, dict):
        results.append(CheckResult("Linux CAKE", "cake_params", Severity.ERROR,
            "cake_params section required when router.transport is 'linux-cake'"))
        return results  # Can't validate sub-fields

    # 2. Required interface fields
    for field in ("upload_interface", "download_interface"):
        value = cake_params.get(field)
        if not value or not isinstance(value, str):
            results.append(CheckResult("Linux CAKE", f"cake_params.{field}", Severity.ERROR,
                f"cake_params.{field} is required (string)"))
        else:
            results.append(CheckResult("Linux CAKE", f"cake_params.{field}", Severity.PASS,
                f"cake_params.{field}: {value}"))

    # 3. Overhead keyword validation (reuse VALID_OVERHEAD_KEYWORDS from cake_params.py)
    overhead = cake_params.get("overhead")
    if overhead is not None:
        from wanctl.cake_params import VALID_OVERHEAD_KEYWORDS
        if overhead not in VALID_OVERHEAD_KEYWORDS:
            results.append(CheckResult("Linux CAKE", "cake_params.overhead", Severity.ERROR,
                f"Invalid overhead keyword: {overhead!r}",
                suggestion=f"Valid: {sorted(VALID_OVERHEAD_KEYWORDS)}"))

    # 4. tc binary existence
    import shutil
    if shutil.which("tc"):
        results.append(CheckResult("Linux CAKE", "tc binary", Severity.PASS,
            "tc binary found on PATH"))
    else:
        results.append(CheckResult("Linux CAKE", "tc binary", Severity.WARN,
            "tc binary not found on PATH",
            suggestion="Install iproute2 or verify PATH includes /usr/sbin"))

    return results
```

### KNOWN_AUTORATE_PATHS Updates

Must add to the set:
```python
# CAKE params (for linux-cake transport)
"cake_params",
"cake_params.upload_interface",
"cake_params.download_interface",
"cake_params.overhead",
"cake_params.memlimit",
"cake_params.rtt",
```

### Anti-Patterns to Avoid
- **Modifying WANController or RouterOS class:** D-06 explicitly forbids this. The factory wiring is limited to `get_backend()`.
- **Making cake_params required for all transports:** D-03 says it's only required when `router_transport: "linux-cake"`.
- **Runtime interface checks in check-config:** D-08 explicitly defers interface existence to `test_connection()`.
- **Changing get_router_client():** That's the SSH/REST client factory for RouterOS commands. Linux CAKE doesn't use it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Overhead keyword validation | Custom set of valid values | `VALID_OVERHEAD_KEYWORDS` from `cake_params.py` | Already defined and maintained in Phase 106 output |
| tc binary detection | Custom PATH search | `shutil.which("tc")` | stdlib, handles PATH resolution correctly |
| Config field extraction | Custom YAML traversal | `_get_nested(data, path)` from `config_base.py` | Established pattern used everywhere in check_config |
| CheckResult creation | Custom error types | `CheckResult(category, field, Severity, message, suggestion)` | Exact pattern used by all existing validators |

## Common Pitfalls

### Pitfall 1: Factory Key Mismatch
**What goes wrong:** `get_backend()` currently reads `config.router.get("type", "routeros")` but Config objects don't expose router settings as `config.router` dict -- they use `config.router_transport` string attribute.
**Why it happens:** `get_backend()` was written as infrastructure before Config integration. It assumed raw dict access.
**How to avoid:** Change `get_backend()` to use `getattr(config, "router_transport", "rest")` and route `"linux-cake"` to LinuxCakeBackend. Keep backward compat by also accepting `"rest"`/`"ssh"` for RouterOS (mapping both to RouterOSBackend).
**Warning signs:** Factory returns wrong backend or raises ValueError for valid configs.

### Pitfall 2: from_config() Attribute Access on Config
**What goes wrong:** `LinuxCakeBackend.from_config()` currently reads `config.router["interface"]` which doesn't exist on real Config objects. Config stores fields as individual attributes, not dicts.
**Why it happens:** from_config was written for Phase 105 testing with mock config objects.
**How to avoid:** Access `config.data.get("cake_params", {})` to read the raw YAML dict, matching how other `_load_*` methods work.
**Warning signs:** `KeyError: 'interface'` when using a real Config object.

### Pitfall 3: Circular Import from cake_params in check_config
**What goes wrong:** Importing `VALID_OVERHEAD_KEYWORDS` from `cake_params.py` at module level in `check_config.py` could create circular imports.
**Why it happens:** `check_config.py` imports from `autorate_continuous` and `steering.daemon` -- adding another import could create cycles.
**How to avoid:** Either inline the valid keywords set in check_config, or use a lazy import inside the validator function. The `VALID_OVERHEAD_KEYWORDS` set is small and stable -- duplicating it is acceptable if import issues arise.
**Warning signs:** ImportError on startup.

### Pitfall 4: Unknown Key False Positives
**What goes wrong:** Adding `cake_params` to YAML without adding paths to `KNOWN_AUTORATE_PATHS` causes wanctl-check-config to emit spurious "unknown key" warnings.
**Why it happens:** The `check_unknown_keys()` function walks all paths and compares against the known set.
**How to avoid:** Add all `cake_params.*` paths to `KNOWN_AUTORATE_PATHS` in the same change that adds the validator.
**Warning signs:** `wanctl-check-config` shows WARN for cake_params fields in a valid linux-cake config.

### Pitfall 5: tc Binary WARN vs ERROR Severity
**What goes wrong:** Making tc binary absence an ERROR fails configs run on dev machines without iproute2.
**Why it happens:** check-config is an offline validator, may run on machines without tc.
**How to avoid:** Use WARN (not ERROR) for tc binary check. The suggestion should say "Install iproute2 or verify PATH includes /usr/sbin". Only cake_params structure issues should be ERROR.
**Warning signs:** Users on macOS/dev machines get ERROR exit code for valid configs.

## Code Examples

### get_backend() Factory Update
```python
# Source: backends/__init__.py (modified)
from wanctl.backends.linux_cake import LinuxCakeBackend

def get_backend(config: Any) -> RouterBackend:
    transport = getattr(config, "router_transport", "rest")

    if transport in ("rest", "ssh"):
        return RouterOSBackend.from_config(config)
    elif transport == "linux-cake":
        return LinuxCakeBackend.from_config(config)
    else:
        raise ValueError(f"Unsupported router transport: {transport}")
```

### LinuxCakeBackend.from_config() Update
```python
# Source: backends/linux_cake.py (modified)
@classmethod
def from_config(cls, config: Any, direction: str = "download") -> "LinuxCakeBackend":
    cake_params = config.data.get("cake_params", {})
    if direction == "upload":
        interface = cake_params.get("upload_interface", "")
    else:
        interface = cake_params.get("download_interface", "")
    if not interface:
        raise ValueError(
            f"cake_params.{direction}_interface required for linux-cake transport"
        )
    tc_timeout = config.data.get("timeouts", {}).get("tc_command", 5.0)
    return cls(interface=interface, tc_timeout=tc_timeout)
```

### YAML Config Example
```yaml
# linux-cake transport config
wan_name: "Spectrum"
router:
  host: "10.10.99.1"       # Still needed for steering REST calls
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"
  transport: "linux-cake"
cake_params:
  upload_interface: "enp8s0"
  download_interface: "enp9s0"
  overhead: "docsis"
  memlimit: "32mb"
  rtt: "100ms"
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via .venv/bin/pytest) |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/pytest tests/test_linux_cake_backend.py tests/test_backends.py tests/test_check_config.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | transport: "linux-cake" config accepted, cake_params interfaces readable | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestFromConfig -x` | Partial -- needs update for new from_config signature |
| CONF-02 | get_backend() returns LinuxCakeBackend for linux-cake transport | unit | `.venv/bin/pytest tests/test_backends.py::TestGetBackendFactory -x` | No -- new test class needed |
| CONF-04 | check-config validates linux-cake settings | unit | `.venv/bin/pytest tests/test_check_config.py::TestLinuxCakeValidation -x` | No -- new test class needed |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_linux_cake_backend.py tests/test_backends.py tests/test_check_config.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_backends.py::TestGetBackendFactory` -- new test class for factory routing (CONF-02)
- [ ] `tests/test_check_config.py::TestLinuxCakeValidation` -- new test class for linux-cake check-config (CONF-04)
- [ ] Update `tests/test_linux_cake_backend.py` from_config tests for new direction parameter (CONF-01)

## Open Questions

1. **get_backend() vs get_router_client() long-term**
   - What we know: Two parallel factory functions exist. `get_backend()` returns `RouterBackend`, `get_router_client()` returns transport clients (SSH/REST).
   - What's unclear: Whether `get_backend()` will eventually replace `get_router_client()` + `RouterOS` class, or if both paths persist.
   - Recommendation: For Phase 107, add linux-cake branch to `get_backend()` only. Don't touch `get_router_client()`. Let Phase 108 (steering dual-backend) resolve the long-term architecture.

2. **from_config() direction parameter vs factory-passed interface**
   - What we know: D-05 says "direction is determined by daemon context." The daemon creates separate download and upload controller instances.
   - What's unclear: Whether `from_config(config, direction="upload")` or `from_config(config, interface="enp8s0")` is cleaner.
   - Recommendation: Use `direction` parameter. It's more semantic and matches how the daemon thinks (download/upload), and `from_config` can internally resolve the correct interface from cake_params.

## Sources

### Primary (HIGH confidence)
- `src/wanctl/backends/__init__.py` -- current get_backend() factory implementation
- `src/wanctl/backends/linux_cake.py` -- current LinuxCakeBackend including from_config()
- `src/wanctl/check_config.py` -- full validator architecture, KNOWN_AUTORATE_PATHS, dispatcher pattern
- `src/wanctl/config_base.py` -- BaseConfig, _get_nested(), validate_field()
- `src/wanctl/cake_params.py` -- VALID_OVERHEAD_KEYWORDS, build_cake_params()
- `src/wanctl/autorate_continuous.py` -- Config class, _load_router_transport_config()
- `src/wanctl/router_client.py` -- get_router_client() parallel factory (not modified)
- `tests/test_check_config.py` -- existing test patterns for check-config validators
- `tests/test_linux_cake_backend.py` -- existing from_config tests
- `tests/test_backends.py` -- existing backend test patterns

### Secondary (MEDIUM confidence)
- None needed -- all research is codebase-internal

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all changes use existing patterns
- Architecture: HIGH -- factory pattern, validator pattern, config loading all well-understood from codebase reading
- Pitfalls: HIGH -- identified from actual code reading (factory key mismatch, attribute access patterns, import chains)

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable codebase, no external dependency changes)
