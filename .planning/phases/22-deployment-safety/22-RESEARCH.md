# Phase 22: Deployment Safety - Research

**Researched:** 2026-01-21
**Domain:** Deployment validation, configuration management, shell scripting
**Confidence:** HIGH

## Summary

Phase 22 addresses three deployment safety improvements: (1) renaming `steering_config.yaml` to `steering.yaml`, (2) making deploy scripts fail-fast on missing production config, and (3) creating a validation script for pre-startup checks. All three requirements have clear implementation paths with existing patterns to follow.

The codebase already has `configs/steering.yaml` (production config with correct values) alongside legacy `configs/steering_config_v2.yaml`. The config naming mismatch documented in `docs/STEERING_CONFIG_MISMATCH_ISSUE.md` confirms the rename is the recommended solution (Option 1). The deploy script (`scripts/deploy.sh`) and Docker entrypoint already check for config existence but don't fail-fast appropriately. Router reachability tests exist in `scripts/install.sh:618-700` that can be adapted.

**Primary recommendation:** Implement in order - rename first (breaks nothing), then deploy script hardening (adds safety), then validation script (comprehensive checks).

## Standard Stack

The established tools/patterns for this domain:

### Core
| Tool | Purpose | Why Standard |
|------|---------|--------------|
| bash | Shell scripting | Consistent with existing `scripts/deploy.sh`, `scripts/install.sh` |
| curl | REST API reachability | Already used in `scripts/install.sh:638` for router testing |
| python3 | YAML validation | Already used in `docker/entrypoint.sh:45` for config validation |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| ssh | SSH transport test | When validating SSH-based deployments |
| jq | JSON state file validation | Optional; python3 can handle JSON too |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| bash validation | Python validation script | More robust but adds dependency; bash sufficient for file/network checks |
| Manual state file check | State manager API | Over-engineered; simple file existence + JSON validity sufficient |

**Installation:**
No new dependencies required. All tools already present in deployment targets.

## Architecture Patterns

### Recommended Project Structure
```
scripts/
├── deploy.sh              # Main deploy script (MODIFY)
├── install.sh             # Installation wizard (REFERENCE for patterns)
└── validate-deployment.sh # NEW validation script
configs/
├── steering.yaml          # RENAME from steering_config.yaml
├── steering_config_v2.yaml # REMOVE (legacy)
└── examples/
    └── steering.yaml.example # Existing template (keep)
```

### Pattern 1: Fail-Fast Config Validation
**What:** Exit immediately with clear error when required config missing
**When to use:** Before any deployment actions in deploy scripts
**Example:**
```bash
# Source: scripts/install.sh pattern adapted
validate_required_config() {
    local config_file="$1"
    local config_name="$2"

    if [[ ! -f "$config_file" ]]; then
        print_error "Required config not found: $config_file"
        print_error "Create $config_name before deployment"
        exit 1
    fi

    # Basic YAML validation
    if ! python3 -c "import yaml; yaml.safe_load(open('$config_file'))" 2>/dev/null; then
        print_error "Invalid YAML in: $config_file"
        exit 1
    fi
}
```

### Pattern 2: Router Reachability Test
**What:** Verify router API accessible before startup
**When to use:** In validation script before daemon start
**Example:**
```bash
# Source: scripts/install.sh:618-700 (test_router_connection)
test_router_reachable() {
    local transport="$1"
    local router_ip="$2"

    if [[ "$transport" == "rest" ]]; then
        # Test REST API with timeout
        http_code=$(curl -s -k -o /dev/null -w "%{http_code}" \
            -u "admin:$ROUTER_PASSWORD" \
            --connect-timeout 5 \
            --max-time 10 \
            "https://${router_ip}/rest/system/resource" 2>/dev/null)
        [[ "$http_code" == "200" ]] && return 0
    elif [[ "$transport" == "ssh" ]]; then
        # Test SSH with timeout
        ssh -o ConnectTimeout=5 -o BatchMode=yes \
            "admin@${router_ip}" '/system resource print' &>/dev/null
        return $?
    fi
    return 1
}
```

### Pattern 3: State File Validation
**What:** Check state files exist and are valid JSON
**When to use:** Pre-startup validation
**Example:**
```bash
# Source: Based on state_utils.py patterns
validate_state_file() {
    local state_file="$1"

    # State file is optional on first run (will be created)
    if [[ ! -f "$state_file" ]]; then
        print_warning "State file not found: $state_file (will be created on first run)"
        return 0
    fi

    # If exists, must be valid JSON
    if ! python3 -c "import json; json.load(open('$state_file'))" 2>/dev/null; then
        print_error "Corrupted state file: $state_file"
        print_error "Remove or restore from backup: ${state_file}.backup"
        return 1
    fi
    return 0
}
```

### Pattern 4: Queue Existence Check
**What:** Verify RouterOS queue tree entries exist
**When to use:** Pre-startup validation (optional, warns only)
**Example:**
```bash
# Source: scripts/install.sh:703-768 (discover_queues) adapted
verify_queue_exists() {
    local transport="$1"
    local router_ip="$2"
    local queue_name="$3"

    if [[ "$transport" == "rest" ]]; then
        response=$(curl -s -k \
            -u "admin:$ROUTER_PASSWORD" \
            --connect-timeout 5 \
            "https://${router_ip}/rest/queue/tree?name=${queue_name}" 2>/dev/null)
        # Check if response contains the queue name
        echo "$response" | grep -q "\"name\":\"${queue_name}\"" && return 0
    fi
    return 1
}
```

### Anti-Patterns to Avoid
- **Silent fallback to template:** Current deploy.sh:354-361 uses example config as fallback. Must fail-fast instead.
- **Deployment without verification:** Always verify state after deployment, not just success of file copy.
- **Hardcoded paths in validation:** Use config paths from YAML, not hardcoded `/run/wanctl/` paths.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom parser | `python3 -c "import yaml; yaml.safe_load()"` | Already used in docker/entrypoint.sh |
| JSON validation | Custom checker | `python3 -c "import json; json.load()"` | Handles edge cases, encoding |
| Router connection test | Ping-based test | Existing `test_router_connection()` | Already handles REST/SSH, auth, timeouts |
| Queue discovery | Manual SSH | Existing `discover_queues()` | Parses RouterOS output correctly |

**Key insight:** The install.sh wizard already implements router testing, queue discovery, and config validation. Reuse these patterns rather than creating new ones.

## Common Pitfalls

### Pitfall 1: Template Fallback Silently Succeeds
**What goes wrong:** Deploy script uses `configs/examples/steering.yaml.example` when production config missing
**Why it happens:** Fallback intended as convenience, but masks config errors
**How to avoid:** Remove fallback behavior for production configs; fail with actionable error message
**Warning signs:** Log message "Using example steering config - customize..."

### Pitfall 2: State File Path Mismatch
**What goes wrong:** Config references `/run/wanctl/wan1_state.json` but actual file is `/run/wanctl/spectrum_state.json`
**Why it happens:** Generic template values not updated for deployment
**How to avoid:** Validation script extracts `cake_state_sources.primary` from config and checks file exists
**Warning signs:** Steering daemon logs "Primary WAN state file not found"

### Pitfall 3: Queue Name Mismatch
**What goes wrong:** Config references `WAN-Download-1` but actual queue is `WAN-Download-Spectrum`
**Why it happens:** Template placeholders not replaced
**How to avoid:** Validation queries router for queue names and warns if config values not found
**Warning signs:** "CAKE stats failed to read" in steering logs

### Pitfall 4: REST Password Not Set
**What goes wrong:** `${ROUTER_PASSWORD}` env var not set when REST transport used
**Why it happens:** Secrets file not sourced, or password not added
**How to avoid:** Validation checks ROUTER_PASSWORD is set before testing connection
**Warning signs:** HTTP 401 from router, "Authentication failed" errors

## Code Examples

Verified patterns from existing codebase:

### Config Validation (from docker/entrypoint.sh)
```bash
# Source: docker/entrypoint.sh:37-50
validate_config() {
    if [[ ! -f "$CONFIG" ]]; then
        log_error "Configuration file not found: $CONFIG"
        log_error "Mount your config: -v /path/to/wan.yaml:/etc/wanctl/wan.yaml"
        exit 1
    fi

    # Basic YAML validation
    if ! python3 -c "import yaml; yaml.safe_load(open('$CONFIG'))" 2>/dev/null; then
        log_error "Invalid YAML in configuration file: $CONFIG"
        exit 1
    fi

    log_info "Configuration validated: $CONFIG"
}
```

### Router Connection Test (from install.sh)
```bash
# Source: scripts/install.sh:618-700 (simplified)
test_router_connection() {
    local transport="$1"
    local router_ip="$2"
    local password="$3"

    if [[ "$transport" == "rest" ]]; then
        http_code=$(curl -s -k -o /dev/null -w "%{http_code}" \
            -u "admin:$password" \
            --connect-timeout 5 \
            --max-time 10 \
            "https://${router_ip}/rest/system/resource" 2>/dev/null)

        case "$http_code" in
            200) return 0 ;;
            401) print_error "Authentication failed"; return 1 ;;
            000) print_error "Connection failed"; return 1 ;;
            *)   print_error "HTTP $http_code"; return 1 ;;
        esac
    elif [[ "$transport" == "ssh" ]]; then
        ssh -i "$SSH_KEY" \
            -o ConnectTimeout=5 \
            -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes \
            "admin@${router_ip}" '/system resource print' &>/dev/null
        return $?
    fi
    return 1
}
```

### Extract Value from YAML (for validation script)
```bash
# Source: docker/entrypoint.sh pattern, extended
extract_yaml_value() {
    local file="$1"
    local path="$2"
    python3 -c "
import yaml
config = yaml.safe_load(open('$file'))
keys = '$path'.split('.')
val = config
for k in keys:
    val = val.get(k, {}) if isinstance(val, dict) else None
print(val if val else '')
" 2>/dev/null
}

# Usage: extract_yaml_value "/etc/wanctl/steering.yaml" "cake_state_sources.primary"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `steering_config.yaml` | `steering.yaml` | v1.3 (this phase) | Matches deploy script expectations |
| Silent template fallback | Fail-fast validation | v1.3 (this phase) | Prevents wrong config deployment |
| Manual post-deploy checks | Automated validation script | v1.3 (this phase) | Catches errors before daemon start |

**Deprecated/outdated:**
- `configs/steering_config.yaml`: Should be `configs/steering.yaml` (this phase)
- `configs/steering_config_v2.yaml`: Legacy, can be removed (already have `steering.yaml`)

## Current File Locations

### Files to Modify
| File | Current State | Change Required |
|------|---------------|-----------------|
| `configs/steering.yaml` | Exists, production config | None (already named correctly) |
| `configs/steering_config_v2.yaml` | Legacy duplicate | Remove |
| `scripts/deploy.sh:350-364` | Falls back to template | Add fail-fast for `--with-steering` |
| `docker/entrypoint.sh:121-128` | Already validates steering config | None needed |

### Files to Create
| File | Purpose |
|------|---------|
| `scripts/validate-deployment.sh` | Pre-startup validation script |

### References to Update
| Location | Reference | Update To |
|----------|-----------|-----------|
| `docs/STEERING_CONFIG_MISMATCH_ISSUE.md` | `steering_config.yaml` | Mark as resolved |
| `docs/FASTER_RESPONSE_INTERVAL.md` | `steering_config_v2.yaml` references | Update to `steering.yaml` |
| `.planning/codebase/CONCERNS.md` | Naming inconsistency | Mark as resolved |

## Open Questions

All research questions resolved:

1. **Where is `steering_config.yaml` referenced?** - Found in `.planning/`, `docs/`, and `configs/` (legacy). Production uses `steering.yaml` already.

2. **What deploy scripts exist?** - `scripts/deploy.sh` (main), `scripts/deploy_clean.sh` (legacy), `docker/entrypoint.sh` (container). Only `deploy.sh` needs modification.

3. **What state files exist?** - Defined in config YAML: `state_file` for autorate, `cake_state_sources.primary` for steering. Typical paths: `/var/lib/wanctl/<wan>_state.json` and `/run/wanctl/<wan>_state.json`.

4. **Router reachability checks?** - Exist in `scripts/install.sh:618-700` via `test_router_connection()`. Also `src/wanctl/autorate_continuous.py:969-1090` for runtime checks.

5. **Queue names?** - Configured in YAML: `queues.download`, `queues.upload`. Discovery via `discover_queues()` in `install.sh:703-768`.

6. **Existing validation logic?** - `docker/entrypoint.sh` validates YAML, `install.sh` has connection tests, `config_validation_utils.py` has bandwidth/threshold validators.

## Sources

### Primary (HIGH confidence)
- `scripts/deploy.sh` - Read lines 350-568 for steering deployment logic
- `scripts/install.sh` - Read lines 618-768 for router testing, queue discovery patterns
- `docker/entrypoint.sh` - Read lines 37-128 for config validation patterns
- `configs/steering.yaml` - Read full file for current production config structure
- `docs/STEERING_CONFIG_MISMATCH_ISSUE.md` - Read full file for root cause analysis and recommended fix

### Secondary (MEDIUM confidence)
- `src/wanctl/config_validation_utils.py` - Validation patterns for config values
- `src/wanctl/state_utils.py` - State file handling patterns

### Tertiary (LOW confidence)
- None - all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Config rename: HIGH - `steering.yaml` already exists with correct values; rename is documented solution
- Deploy script changes: HIGH - Patterns exist in `docker/entrypoint.sh`, straightforward modification
- Validation script: HIGH - All required patterns exist in `install.sh`, composition task

**Research date:** 2026-01-21
**Valid until:** 60 days (stable domain, shell scripting patterns)
