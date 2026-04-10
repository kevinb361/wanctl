# Phase 56: Integration Gap Fixes - Research

**Researched:** 2026-03-08
**Domain:** Configuration defaults, documentation accuracy
**Confidence:** HIGH

## Summary

Phase 56 closes two residual integration gaps identified by the v1.10 milestone audit. Both are small, well-understood fixes with zero risk to production logic.

**Gap 1 (OPS-01 integration):** Both daemon config loaders (`autorate_continuous.py:462` and `steering/daemon.py:174`) default `verify_ssl` to `False` when YAML omits the key. This contradicts the REST client (`RouterOSREST.__init__`) which defaults to `True`, and the documentation (`CONFIG_SCHEMA.md` line 51) which states the default is `true`. Because the config object always sets `router_verify_ssl` before `from_config` reads it, the REST client's secure fallback of `True` never activates. Net effect: production runs with SSL verification disabled by default despite all documentation claiming otherwise.

**Gap 2 (CLEAN-04 integration):** `docs/CONFIG_SCHEMA.md` still says the transport default is `"ssh"` in three places (lines 49, 55, 77), but Phase 50 changed all code paths to default to `"rest"`. The documentation is stale.

**Primary recommendation:** Change two `False` to `True` in config loaders, update three `"ssh"` to `"rest"` in CONFIG_SCHEMA.md, add targeted tests verifying the defaults match.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OPS-01 (integration) | verify_ssl semantic contradiction -- daemon config loaders default False, overriding REST client's secure True default | Exact lines identified: autorate_continuous.py:462 and steering/daemon.py:174. Fix: change `False` to `True`. Tests needed in test_autorate_config.py and test_steering_daemon.py. |
| CLEAN-04 (integration) | CONFIG_SCHEMA.md documents transport default as "ssh" but all code paths default to "rest" | Exact lines identified: CONFIG_SCHEMA.md lines 49, 55, 77. Fix: change `"ssh"` to `"rest"`. No test needed (documentation only). |
</phase_requirements>

## Standard Stack

Not applicable -- this phase modifies 3 existing files with no new dependencies.

### Files to Modify

| File | Line(s) | Current | Target | Requirement |
|------|---------|---------|--------|-------------|
| `src/wanctl/autorate_continuous.py` | 462 | `router.get("verify_ssl", False)` | `router.get("verify_ssl", True)` | OPS-01 |
| `src/wanctl/steering/daemon.py` | 174 | `router.get("verify_ssl", False)` | `router.get("verify_ssl", True)` | OPS-01 |
| `docs/CONFIG_SCHEMA.md` | 49 | `"ssh"` in Default column | `"rest"` | CLEAN-04 |
| `docs/CONFIG_SCHEMA.md` | 55 | `ssh` (default) description text | `rest` (default) | CLEAN-04 |
| `docs/CONFIG_SCHEMA.md` | 72,77 | "SSH transport (default)" comment and `transport: "ssh"  # Optional, this is the default` | "REST transport (default)" and `transport: "rest"` | CLEAN-04 |

## Architecture Patterns

### The verify_ssl Data Flow

Understanding why the bug exists requires tracing the full data flow:

```
YAML config (router section)
    |
    v
Daemon config loader (_load_router_transport_config / _load_router_transport)
    router.get("verify_ssl", False)  <-- BUG: defaults to False
    sets config.router_verify_ssl = False
    |
    v
RouterOSREST.from_config(config, logger)
    getattr(config, "router_verify_ssl", True)  <-- Fallback True NEVER triggers
    because config.router_verify_ssl is ALWAYS set (to False when YAML omits it)
    |
    v
RouterOSREST.__init__(verify_ssl=False)  <-- Insecure despite docs claiming True
```

**After fix:**
```
YAML config (router section) -- verify_ssl absent
    |
    v
Daemon config loader
    router.get("verify_ssl", True)  <-- Matches REST client default
    sets config.router_verify_ssl = True
    |
    v
RouterOSREST.from_config(config, logger)
    getattr(config, "router_verify_ssl", True)  <-- Consistent, secure
    |
    v
RouterOSREST.__init__(verify_ssl=True)  <-- Secure default, matches docs
```

### Anti-Patterns to Avoid

- **Changing existing explicit `verify_ssl: false` in YAML configs:** The fix only affects the *default* when the key is omitted. Production configs that explicitly set `verify_ssl: false` (common for MikroTik self-signed certs) will continue to work unchanged.
- **Modifying `router_client.py:76` get_router_client default:** The audit noted this defaults to `"ssh"` but it is unused by production daemons (tech debt, not in scope for this phase).

## Don't Hand-Roll

Not applicable -- no libraries or custom solutions involved. This is a 2-character code change and a documentation update.

## Common Pitfalls

### Pitfall 1: Forgetting the Production Context

**What goes wrong:** MikroTik RouterOS uses self-signed certificates by default. Changing the verify_ssl default to True means any production deployment that omits `verify_ssl` from YAML will start getting SSL errors.

**Why it matters:** This is the *correct* behavior (secure by default), but the CONFIG_SCHEMA.md already documents this scenario and explains how to set `verify_ssl: false` for self-signed certs. Kevin's production configs likely already have `verify_ssl: false` explicitly set (the `router_client.py` docstring example on line 43 shows `verify_ssl: false`).

**How to avoid:** Verify that production YAML configs already have `verify_ssl: false` explicitly set. If they do, the default change is safe. If they don't, this fix will change runtime behavior. Either way, the fix is correct -- the documentation already says the default is True.

### Pitfall 2: Missing the Example Config in CONFIG_SCHEMA.md

**What goes wrong:** Updating the table and description but missing the YAML example block that says `# SSH transport (default)` and `transport: "ssh"  # Optional, this is the default`.

**How to avoid:** All three locations in CONFIG_SCHEMA.md must be updated: the table (line 49), the description paragraph (line 55), and the YAML example comments (lines 72, 77).

## Code Examples

### OPS-01 Fix: autorate_continuous.py

```python
# Before (line 462):
self.router_verify_ssl = router.get("verify_ssl", False)

# After:
self.router_verify_ssl = router.get("verify_ssl", True)
```

### OPS-01 Fix: steering/daemon.py

```python
# Before (line 174):
self.router_verify_ssl = router.get("verify_ssl", False)

# After:
self.router_verify_ssl = router.get("verify_ssl", True)
```

### CLEAN-04 Fix: CONFIG_SCHEMA.md

```markdown
# Before (line 49):
| `transport`  | string  | no       | `"ssh"`      | Transport type: `"ssh"` or `"rest"`           |

# After:
| `transport`  | string  | no       | `"rest"`     | Transport type: `"rest"` or `"ssh"`           |
```

```markdown
# Before (line 55):
- `ssh` (default): Uses SSH/Paramiko for RouterOS communication

# After:
- `rest` (default): Uses RouterOS REST API (faster, requires password instead of ssh_key)
```

```markdown
# Before (lines 72, 77):
# SSH transport (default)
  transport: "ssh"  # Optional, this is the default

# After:
# REST transport (default)
  transport: "rest"  # Optional, this is the default
```

### Test: verify_ssl default in autorate config

```python
# Add to tests/test_autorate_config.py in new class TestConfigVerifySslDefault

def test_verify_ssl_defaults_to_true_when_omitted(self, tmp_path):
    """Config defaults router_verify_ssl to True when verify_ssl key is missing."""
    # Write YAML without verify_ssl key
    # Load config
    # Assert config.router_verify_ssl is True
```

### Test: verify_ssl default in steering daemon config

```python
# Add to tests/test_steering_daemon.py

def test_verify_ssl_defaults_to_true_when_omitted(self, tmp_path, valid_config_dict):
    """Steering config defaults router_verify_ssl to True when verify_ssl key is missing."""
    # Remove verify_ssl from config dict if present
    # Write YAML, load config
    # Assert config.router_verify_ssl is True
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SSH transport default | REST transport default | Phase 50 (v1.10) | Code changed, CONFIG_SCHEMA.md not updated |
| verify_ssl not considered | REST client defaults True | Phase 52 (v1.10) | REST client correct, daemon loaders not aligned |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `.venv/bin/pytest tests/test_autorate_config.py tests/test_steering_daemon.py -v -k "verify_ssl or transport_default"` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPS-01 | autorate config defaults verify_ssl to True | unit | `.venv/bin/pytest tests/test_autorate_config.py -x -k "verify_ssl"` | No -- Wave 0 |
| OPS-01 | steering config defaults verify_ssl to True | unit | `.venv/bin/pytest tests/test_steering_daemon.py -x -k "verify_ssl"` | No -- Wave 0 |
| CLEAN-04 | CONFIG_SCHEMA.md transport default matches code | manual-only | Visual inspection of docs/CONFIG_SCHEMA.md | N/A |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_autorate_config.py tests/test_steering_daemon.py tests/test_routeros_rest.py -v -x`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_autorate_config.py::TestConfigVerifySslDefault` -- covers OPS-01 (autorate side)
- [ ] `tests/test_steering_daemon.py::test_verify_ssl_defaults_to_true_when_omitted` -- covers OPS-01 (steering side)

*(Both test files exist; only the specific verify_ssl default test methods are missing.)*

## Open Questions

None. Both gaps are fully characterized by the milestone audit with exact file paths, line numbers, and prescribed fixes. The changes are mechanical.

## Sources

### Primary (HIGH confidence)
- **Source code inspection** -- `src/wanctl/autorate_continuous.py:462`, `src/wanctl/steering/daemon.py:174`, `src/wanctl/routeros_rest.py:25,73,151`
- **docs/CONFIG_SCHEMA.md** -- lines 49, 55, 72, 77
- **v1.10-MILESTONE-AUDIT.md** -- integration gaps OPS-01 and CLEAN-04

### Secondary (MEDIUM confidence)
- **Existing tests** -- `tests/test_routeros_rest.py` (4 verify_ssl tests passing), `tests/test_autorate_config.py` (2 transport tests passing), `tests/test_steering_daemon.py` (transport default test passing)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, exact changes known
- Architecture: HIGH -- data flow traced end-to-end, root cause confirmed
- Pitfalls: HIGH -- production impact assessed (self-signed cert configs likely explicit)

**Research date:** 2026-03-08
**Valid until:** indefinite (fixes are version-pinned to current codebase)
