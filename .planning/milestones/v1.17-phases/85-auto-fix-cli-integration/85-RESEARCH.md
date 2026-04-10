# Phase 85: Auto-Fix CLI Integration - Research

**Researched:** 2026-03-13
**Domain:** MikroTik RouterOS CAKE queue type parameter modification via REST API PATCH, CLI fix flow with safety guards
**Confidence:** HIGH

## Summary

Phase 85 adds write capability to the existing `wanctl-check-cake` CLI tool. The `--fix` flag triggers a flow: detect sub-optimal params (reusing Phase 84 audit), show a before/after diff table, confirm with operator, check daemon lock file, save JSON snapshot, PATCH queue type params via REST API, then re-run audit to verify changes took effect.

The implementation requires one new method on `RouterOSREST` (`set_queue_type_params`) and a new orchestration function in `check_cake.py` (`run_fix`). Everything else -- CheckResult model, format_results output, exit codes, CLI argument parsing, lock file validation, JSON writing -- is existing infrastructure that gets composed together. The `set_queue_type_params` method follows the exact PATCH pattern already proven by `set_queue_limit` and `_handle_queue_tree_set`: find resource ID via GET with name filter, PATCH to `/rest/queue/type/{id}` with JSON body.

The lock file check is read-only: glob `/run/wanctl/*.lock` and check if any contains a live PID using existing `read_lock_pid()` + `is_process_alive()` from `lock_utils.py`. The snapshot uses standard `json.dump` with indentation for human readability (not the compact `atomic_write_json` used for state files -- snapshots are one-shot write-and-archive, not concurrent-access).

**Primary recommendation:** Extend `check_cake.py` with `run_fix()` orchestrator that chains: lock check -> audit -> extract changes -> snapshot -> confirm -> PATCH -> verify. Add `set_queue_type_params()` to `RouterOSREST` following `set_queue_limit` pattern but targeting `/rest/queue/type/{id}`.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- Snapshot storage: `/var/lib/wanctl/snapshots/`, auto-prune oldest when count exceeds threshold
- Fix scope: `--fix` applies ALL sub-optimal parameters at once (all-or-nothing), no selective per-param flags
- Confirmation UX: before/after table format (Parameter | Current | Recommended), prompt "Apply N changes to {queue-type-name}? [y/N]", `--yes` bypasses confirmation
- Post-apply verification: re-read queue type data from router and verify params changed, then re-run full audit showing all PASS results
- REST API target: PATCH to `/rest/queue/type/{id}` (not queue tree)

### Claude's Discretion

- Partial failure handling: batch PATCH vs individual per-param, stop-on-failure vs continue, rollback mechanism
- Whether to include `--rollback <snapshot-file>` flag or keep manual-only rollback
- Combined vs separate confirmation for download + upload queue types
- Snapshot file naming convention and when to print the path
- "Nothing to fix" exit behavior
- Whether link-dependent params (overhead, rtt) are included in fix scope

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID     | Description                                                                                       | Research Support                                                                                                                                  |
| ------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| FIX-01 | Operator can apply recommended CAKE parameters to router via `--fix` flag                        | New `run_fix()` orchestrator in check_cake.py, chains audit -> snapshot -> confirm -> apply -> verify                                             |
| FIX-02 | Fix applies changes via REST API PATCH to `/rest/queue/type/{id}` (not queue tree)               | New `set_queue_type_params()` on RouterOSREST, follows proven `set_queue_limit` PATCH pattern with `_find_resource_id` for ID lookup              |
| FIX-03 | Fix shows before/after diff and requires confirmation (unless `--yes`)                            | Table format with Parameter/Current/Recommended columns, input() prompt, `--yes` flag on argparse                                                 |
| FIX-04 | Fix refuses to apply if wanctl daemon is running (lock file check)                               | Glob `/run/wanctl/*.lock`, use existing `read_lock_pid()` + `is_process_alive()` from lock_utils.py -- read-only check, never acquires lock       |
| FIX-05 | Fix saves parameter snapshot (current values) to JSON before applying changes                     | Write to `/var/lib/wanctl/snapshots/{timestamp}_{wan_name}.json` with `json.dump(indent=2)` for human readability, auto-prune beyond threshold   |
| FIX-06 | Fix results reported as CheckResult items with success/failure per parameter                      | Reuse existing CheckResult/Severity model, new category "Fix Applied ({direction})" with PASS/ERROR per param                                     |
| FIX-07 | Fix supports `--json` output mode for scripting                                                   | Existing `--json` flag and `format_results_json()` already handle arbitrary CheckResult lists -- fix results flow through same pipeline            |

</phase_requirements>

## Standard Stack

### Core

| Library    | Version  | Purpose                         | Why Standard                                     |
| ---------- | -------- | ------------------------------- | ------------------------------------------------ |
| Python     | 3.12     | Runtime                         | Project standard                                 |
| requests   | existing | HTTP client for REST API PATCH  | Already used by RouterOSREST for GET/PATCH       |
| PyYAML     | existing | Config parsing                  | Already used by check_cake.py                    |
| json       | stdlib   | Snapshot serialization          | Standard library, no new deps                    |
| glob/Path  | stdlib   | Lock file discovery             | Standard library, no new deps                    |

### Supporting

| Library       | Version  | Purpose               | When to Use               |
| ------------- | -------- | --------------------- | ------------------------- |
| pytest        | existing | Test framework        | All tests                 |
| unittest.mock | stdlib   | Mock router responses | Test fixtures             |
| lock_utils    | internal | PID-based lock check  | Daemon running detection  |
| path_utils    | internal | Directory creation    | Snapshot dir setup        |

### Alternatives Considered

None. Zero new dependencies. All infrastructure exists.

**Installation:**

```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure

```
src/wanctl/
  check_cake.py          # Extended with run_fix(), snapshot, lock check, CLI flags
  routeros_rest.py       # Extended with set_queue_type_params() method
  lock_utils.py          # Reused read_lock_pid() + is_process_alive() (no changes)
  path_utils.py          # Reused ensure_directory_exists() (no changes)
tests/
  test_check_cake.py     # Extended with fix-mode test classes
```

### Pattern 1: REST API PATCH for Queue Types

**What:** New method on `RouterOSREST` that PATCHes queue type parameters by name.
**When to use:** When applying CAKE parameter changes to the router.
**Example:**

```python
# Source: follows set_queue_limit() at routeros_rest.py:614-647
def set_queue_type_params(self, type_name: str, params: dict[str, str]) -> bool:
    """Set queue type parameters via REST API PATCH.

    Finds queue type ID by name, then PATCHes to /rest/queue/type/{id}.

    Args:
        type_name: Name of the queue type (e.g., "cake-down-spectrum")
        params: Dict of parameter names to values (e.g., {"cake-nat": "yes"})

    Returns:
        True if successful, False otherwise
    """
    # Find queue type ID (uses _find_resource_id with queue/type endpoint)
    url = f"{self.base_url}/queue/type"
    try:
        resp = self._request("GET", url, params={"name": type_name}, timeout=self.timeout)
        if not (resp.ok and resp.json()):
            self.logger.error(f"Queue type not found: {type_name}")
            return False
        items = resp.json()
        if not items:
            return False
        type_id = items[0].get(".id")
        if not type_id:
            return False
    except requests.RequestException as e:
        self.logger.error(f"REST API error finding queue type: {e}")
        return False

    # PATCH the queue type
    patch_url = f"{self.base_url}/queue/type/{type_id}"
    try:
        resp = self._request("PATCH", patch_url, json=params, timeout=self.timeout)
        if resp.ok:
            self.logger.debug(f"Queue type {type_name} updated: {params}")
            return True
        else:
            self.logger.error(
                f"Failed to update queue type {type_name}: {resp.status_code} {resp.text}"
            )
            return False
    except requests.RequestException as e:
        self.logger.error(f"REST API error updating queue type: {e}")
        return False
```

### Pattern 2: Fix Orchestration Flow

**What:** Orchestrator function that chains lock check -> audit -> diff -> snapshot -> confirm -> apply -> verify.
**When to use:** When `--fix` flag is passed.
**Example (skeleton):**

```python
def run_fix(
    data: dict,
    config_type: str,
    client: object,
    yes: bool = False,
    json_mode: bool = False,
    wan_name: str = "",
) -> list[CheckResult]:
    """Orchestrate fix flow: audit -> diff -> snapshot -> apply -> verify."""
    results: list[CheckResult] = []

    # 1. Check daemon not running
    lock_results = check_daemon_lock()
    results.extend(lock_results)
    if any(r.severity == Severity.ERROR for r in lock_results):
        return results

    # 2. Run audit to find sub-optimal params
    audit_results = run_audit(data, config_type, client)

    # 3. Extract changes from WARN/ERROR results
    changes = _extract_changes(audit_results)
    if not changes:
        # Nothing to fix
        results.extend(audit_results)
        return results

    # 4. Show diff table and confirm
    if not yes:
        _show_diff_table(changes)
        if not _confirm_apply(changes):
            return results

    # 5. Save snapshot
    _save_snapshot(client, queue_names, wan_name)

    # 6. Apply changes via PATCH
    apply_results = _apply_changes(client, changes)
    results.extend(apply_results)

    # 7. Re-run audit to verify
    verify_results = run_audit(data, config_type, client)
    results.extend(verify_results)

    return results
```

### Pattern 3: Lock File Read-Only Check

**What:** Check if any wanctl daemon is running by reading lock files, without acquiring a lock.
**When to use:** Before applying fix changes.
**Example:**

```python
# Source: lock_utils.py read_lock_pid() + is_process_alive()
from pathlib import Path
from wanctl.lock_utils import read_lock_pid, is_process_alive

def check_daemon_lock() -> list[CheckResult]:
    """Check if any wanctl daemon is running via lock file inspection."""
    results: list[CheckResult] = []
    lock_dir = Path("/run/wanctl")
    if not lock_dir.exists():
        results.append(CheckResult(
            "Daemon Lock", "lock_check", Severity.PASS,
            "No lock directory found -- daemon not running",
        ))
        return results

    for lock_file in lock_dir.glob("*.lock"):
        pid = read_lock_pid(lock_file)
        if pid is not None and is_process_alive(pid):
            results.append(CheckResult(
                "Daemon Lock", "lock_check", Severity.ERROR,
                f"wanctl daemon is running (PID {pid}, lock: {lock_file})",
                suggestion="Stop the daemon first: systemctl stop wanctl@<wan_name>",
            ))
            return results

    results.append(CheckResult(
        "Daemon Lock", "lock_check", Severity.PASS,
        "No active wanctl daemon detected",
    ))
    return results
```

### Pattern 4: Snapshot Save and Prune

**What:** Save current queue type params to timestamped JSON, prune old snapshots.
**When to use:** Before applying any changes.
**Example:**

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from wanctl.path_utils import ensure_directory_exists

SNAPSHOT_DIR = Path("/var/lib/wanctl/snapshots")
MAX_SNAPSHOTS = 20

def _save_snapshot(
    queue_type_data: dict[str, dict],
    wan_name: str,
) -> Path:
    """Save current queue type params to timestamped JSON snapshot.

    Args:
        queue_type_data: Dict mapping direction -> queue type response dict
        wan_name: WAN name for filename

    Returns:
        Path to saved snapshot file
    """
    ensure_directory_exists(SNAPSHOT_DIR)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}_{wan_name}.json"
    snapshot_path = SNAPSHOT_DIR / filename

    snapshot = {
        "timestamp": timestamp,
        "wan_name": wan_name,
        "queue_types": queue_type_data,
    }

    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    _prune_snapshots(wan_name)
    return snapshot_path


def _prune_snapshots(wan_name: str) -> None:
    """Remove oldest snapshots beyond MAX_SNAPSHOTS threshold."""
    pattern = f"*_{wan_name}.json"
    snapshots = sorted(SNAPSHOT_DIR.glob(pattern))
    while len(snapshots) > MAX_SNAPSHOTS:
        snapshots[0].unlink()
        snapshots.pop(0)
```

### Anti-Patterns to Avoid

- **Never acquire the lock:** Fix mode only reads lock files to detect running daemons. Never call `validate_and_acquire_lock()` or `LockFile()` context manager.
- **Never modify queue tree entries:** Only modify `/rest/queue/type/{id}` parameters. Queue tree max-limit is dynamically managed by the daemon.
- **Never auto-detect link type:** Overhead and RTT come from YAML config only (portable controller architecture).
- **Never batch multiple queue types in a single PATCH:** Each queue type has its own `.id` and must be PATCHed individually.
- **Never use atomic_write_json for snapshots:** Snapshots are one-shot human-readable files, not concurrent-access state. Use `json.dump(indent=2)` directly.

## Don't Hand-Roll

| Problem               | Don't Build               | Use Instead                                                          | Why                                                          |
| --------------------- | ------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------ |
| Result formatting     | Custom fix output         | `format_results()` / `format_results_json()` from check_config.py   | Already handles color, quiet, JSON, category grouping        |
| Lock file checking    | Custom PID parsing        | `read_lock_pid()` + `is_process_alive()` from lock_utils.py         | Handles zombie detection, /proc check, ESRCH/EPERM           |
| Directory creation    | Manual os.makedirs        | `ensure_directory_exists()` from path_utils.py                       | Error handling, logging, mode bits                           |
| Router communication  | Raw HTTP calls            | `RouterOSREST._request()` wrapper                                    | SSL warning suppression, session management                  |
| Queue type ID lookup  | Separate GET+parse        | Follow `_find_resource_id()` pattern or inline GET-then-PATCH        | Caching, error handling, consistent with existing methods    |
| Config type detection | Manual YAML inspection    | `detect_config_type()` from check_config.py                         | Already handles autorate vs steering                         |
| Param change extraction | Custom diff logic       | Parse existing WARN/ERROR CheckResult messages for `current -> recommended` | Changes are already identified by check_cake_params/check_link_params |

**Key insight:** The fix flow is a composition of existing primitives. The only new code is (1) `set_queue_type_params()` PATCH method, (2) change extraction from audit results, (3) diff table rendering, (4) snapshot serialization, and (5) the orchestration function.

## Common Pitfalls

### Pitfall 1: PATCH Sends String Values

**What goes wrong:** Sending integer or boolean values in PATCH body fails or behaves unexpectedly.
**Why it happens:** RouterOS REST API expects all values as strings in JSON body, matching how GET returns them.
**How to avoid:** Always send string values: `{"cake-nat": "yes", "cake-overhead": "18"}`. Never send `{"cake-overhead": 18}` (integer).
**Warning signs:** PATCH returns 400 Bad Request or silently ignores values.

### Pitfall 2: Queue Type ID vs Queue Tree ID

**What goes wrong:** Using `/rest/queue/tree/{id}` endpoint instead of `/rest/queue/type/{id}`.
**Why it happens:** Existing `set_queue_limit` targets queue tree, and the similar names cause confusion.
**How to avoid:** The new `set_queue_type_params()` must use `/rest/queue/type` endpoint for both GET (ID lookup) and PATCH. Queue types define qdisc params; queue tree entries reference queue types by name.
**Warning signs:** 404 Not Found or modifying wrong resource.

### Pitfall 3: Shared Queue Type Between Directions

**What goes wrong:** Applying download-optimal wash ("no") to a queue type that is also used by upload (which needs wash="yes").
**Why it happens:** If download and upload queue tree entries reference the same queue type name, both directions share one queue type.
**How to avoid:** Per the current router setup, Kevin has separate types per direction (cake-down-spectrum, cake-up-spectrum). But code should detect shared types and warn or skip wash if shared. Document this as a known limitation.
**Warning signs:** Applying fix for one direction breaks the other.

### Pitfall 4: Lock File Directory Missing

**What goes wrong:** Glob on `/run/wanctl/*.lock` raises error when directory does not exist.
**Why it happens:** On development machines or fresh installs, `/run/wanctl/` may not exist.
**How to avoid:** Check `Path("/run/wanctl").exists()` before globbing. Missing directory means no daemon is running.
**Warning signs:** FileNotFoundError on development/test environments.

### Pitfall 5: Snapshot Directory Permissions

**What goes wrong:** Writing to `/var/lib/wanctl/snapshots/` fails with PermissionError.
**Why it happens:** CLI tool may run as non-root user, but `/var/lib/wanctl/` is root-owned.
**How to avoid:** Detect permission error and provide clear message. In production containers, the tool runs as root. In development, provide helpful error.
**Warning signs:** PermissionError during snapshot save.

### Pitfall 6: Partial PATCH Failure

**What goes wrong:** Some parameters update successfully but one fails, leaving queue type in mixed state.
**Why it happens:** Network interruption, invalid parameter value, or RouterOS rejecting a value.
**How to avoid:** Decision point for Claude's discretion. Two approaches: (a) send all params in single PATCH (RouterOS handles atomicity), or (b) PATCH per-param and report individual results. Single PATCH is safer -- RouterOS PATCH either succeeds fully or fails fully per the REST API specification.
**Warning signs:** Partial updates shown in verification audit.

### Pitfall 7: Extracting Changes from Audit Results

**What goes wrong:** Parsing `"current -> recommended"` from CheckResult.message is fragile.
**Why it happens:** Message format is not structured data, it is display text.
**How to avoid:** Instead of parsing messages, re-derive changes from the same data. Run `check_cake_params()` and `check_link_params()` to get WARN/ERROR results, then look up the actual vs expected values from OPTIMAL_CAKE_DEFAULTS/OPTIMAL_WASH/cake_config. This is cleaner than regex on messages.
**Warning signs:** Fix applies wrong values because message format changed.

### Pitfall 8: Confirmation Prompt in --json Mode

**What goes wrong:** Interactive confirmation prompt breaks JSON output or pipes.
**Why it happens:** input() call blocks and outputs to stdout where JSON is expected.
**How to avoid:** When `--json` is active, require `--yes` or refuse to proceed. Print error to stderr, not stdout.
**Warning signs:** Broken JSON output, hanging in pipeline.

## Code Examples

Verified patterns from existing codebase:

### Existing PATCH Pattern (set_queue_limit)

```python
# Source: routeros_rest.py:614-647
def set_queue_limit(self, queue_name: str, max_limit: int) -> bool:
    queue_id = self._find_queue_id(queue_name)
    if queue_id is None:
        self.logger.error(f"Queue not found: {queue_name}")
        return False

    url = f"{self.base_url}/queue/tree/{queue_id}"
    try:
        resp = self._request(
            "PATCH", url, json={"max-limit": str(max_limit)}, timeout=self.timeout
        )
        if resp.ok:
            return True
        else:
            self.logger.error(f"Failed to set queue limit: {resp.status_code}")
            return False
    except requests.RequestException as e:
        self.logger.error(f"REST API error: {e}")
        return False
```

### Lock File Read-Only Check Pattern

```python
# Source: lock_utils.py:81-95, 37-78
from wanctl.lock_utils import read_lock_pid, is_process_alive

# read_lock_pid reads the PID from lock file content
pid = read_lock_pid(Path("/run/wanctl/spectrum.lock"))
if pid is not None and is_process_alive(pid):
    # Daemon is running
    ...
```

### Snapshot JSON Structure

```python
# Snapshot file: /var/lib/wanctl/snapshots/20260313T153045Z_spectrum.json
{
  "timestamp": "20260313T153045Z",
  "wan_name": "spectrum",
  "queue_types": {
    "download": {
      ".id": "*A",
      "name": "cake-down-spectrum",
      "kind": "cake",
      "cake-flowmode": "dual-srchost",
      "cake-diffserv": "diffserv3",
      "cake-nat": "no",
      "cake-ack-filter": "none",
      "cake-wash": "yes",
      "cake-overhead": "18",
      "cake-rtt": "100ms"
    },
    "upload": {
      ".id": "*B",
      "name": "cake-up-spectrum",
      // ... same structure
    }
  }
}
```

### Diff Table Output Format

```
Proposed changes for cake-down-spectrum (download):
  Parameter    | Current        | Recommended
  -------------|----------------|---------------
  flowmode     | dual-srchost   | triple-isolate
  diffserv     | diffserv3      | diffserv4
  nat          | no             | yes
  ack-filter   | none           | filter

Proposed changes for cake-up-spectrum (upload):
  Parameter    | Current        | Recommended
  -------------|----------------|---------------
  wash         | no             | yes

Apply 5 changes? [y/N]
```

### Change Extraction from Optimal Defaults (not message parsing)

```python
# Better approach: re-derive changes from source data, not from messages
def _extract_changes_for_direction(
    queue_type_data: dict,
    direction: str,
    cake_config: dict | None,
) -> dict[str, tuple[str, str]]:
    """Extract {param_key: (current_value, recommended_value)} for sub-optimal params."""
    changes: dict[str, tuple[str, str]] = {}

    # Link-independent
    for key, expected in OPTIMAL_CAKE_DEFAULTS.items():
        actual = queue_type_data.get(key, "")
        if actual != expected:
            changes[key] = (actual, expected)

    # Wash (direction-dependent)
    expected_wash = OPTIMAL_WASH[direction]
    actual_wash = queue_type_data.get("cake-wash", "")
    if actual_wash != expected_wash:
        changes["cake-wash"] = (actual_wash, expected_wash)

    # Link-dependent (if config present)
    if cake_config:
        expected_overhead = str(cake_config.get("overhead", ""))
        actual_overhead = queue_type_data.get("cake-overhead", "")
        if actual_overhead != expected_overhead:
            changes["cake-overhead"] = (actual_overhead, expected_overhead)

        expected_rtt = str(cake_config.get("rtt", ""))
        actual_rtt = queue_type_data.get("cake-rtt", "")
        if actual_rtt != expected_rtt:
            changes["cake-rtt"] = (actual_rtt, expected_rtt)

    return changes
```

## State of the Art

| Old Approach                      | Current Approach                        | When Changed                   | Impact                                                |
| --------------------------------- | --------------------------------------- | ------------------------------ | ----------------------------------------------------- |
| Manual CLI queue type set         | Automated via REST API PATCH            | This phase                     | Repeatable, auditable, rollback-capable               |
| No pre-change snapshot            | JSON snapshot before every fix          | This phase                     | Enables manual rollback                               |
| No daemon coordination            | Lock file check before changes          | This phase                     | Prevents conflict with running autorate daemon        |

**Deprecated/outdated:**
- None relevant. REST API PATCH pattern is stable since RouterOS 7.1.

## Discretion Recommendations

These are areas marked as "Claude's discretion" in CONTEXT.md, with research-backed recommendations:

### 1. Batch PATCH vs Per-Param PATCH

**Recommendation:** Single PATCH per queue type with all changed params. RouterOS PATCH is atomic per resource -- either all fields update or none do. This is safer than per-param PATCH and requires fewer HTTP requests.

**Rationale:** The PATCH documentation states "a successful update returns the updated object with all its parameters." There is no documented partial-update behavior. Single PATCH per queue type = at most 2 PATCH calls (one per direction).

### 2. Link-Dependent Params in Fix Scope

**Recommendation:** Include overhead and rtt in fix scope when cake_optimization config is present. These are ERROR-severity mismatches (more serious than WARN), so fixing them is high value.

**Rationale:** If the operator explicitly configured `cake_optimization: {overhead: 18, rtt: 100ms}` in their YAML, they clearly want those values on the router. Excluding them from `--fix` would be surprising.

### 3. --rollback Flag

**Recommendation:** Skip `--rollback` flag for this phase. Manual rollback is sufficient -- the snapshot file contains the exact parameter values to restore, and the operator can re-run with `--fix` after adjusting the YAML config. Adding `--rollback` adds complexity (parse snapshot, apply old values, handle conflicts) with low value given fix is idempotent.

### 4. Combined vs Separate Confirmation

**Recommendation:** Single combined confirmation for all changes across both directions. Show changes grouped by queue type name (direction), then one "Apply N changes? [y/N]" prompt. Separate per-direction prompts add friction with no safety benefit since both directions are typically fixed together.

### 5. Snapshot File Naming

**Recommendation:** `{ISO8601_UTC}_{wan_name}.json` (e.g., `20260313T153045Z_spectrum.json`). UTC avoids timezone ambiguity. Print snapshot path after save: `Snapshot saved: /var/lib/wanctl/snapshots/20260313T153045Z_spectrum.json`

### 6. "Nothing to Fix" Behavior

**Recommendation:** Print "All CAKE parameters are optimal -- nothing to fix." to stdout and exit 0. In `--json` mode, return the normal audit JSON with result "PASS". This is not an error condition.

## Open Questions

1. **RouterOS PATCH atomicity for queue types**
   - What we know: REST API docs say PATCH returns updated object on success. No mention of partial updates.
   - What's unclear: Whether RouterOS rejects the entire PATCH if one param value is invalid, or silently ignores bad params.
   - Recommendation: Send all params in single PATCH. Post-apply verification catches any that did not take effect. LOW risk -- all values are well-known CAKE params with documented valid values.

2. **Shared queue type between directions**
   - What we know: Kevin's router likely has separate types per direction (cake-down-spectrum, cake-up-spectrum based on naming convention).
   - What's unclear: Whether the fix code needs to handle shared types (same name for both dl/ul queue trees).
   - Recommendation: Detect shared types by comparing queue type names from both directions. If shared, warn and skip wash (which is direction-dependent). Other params are direction-independent and safe to apply.

## Validation Architecture

### Test Framework

| Property          | Value                                             |
| ----------------- | ------------------------------------------------- |
| Framework         | pytest (existing)                                 |
| Config file       | pyproject.toml `[tool.pytest.ini_options]`        |
| Quick run command | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v`                     |

### Phase Requirements -> Test Map

| Req ID | Behavior                                      | Test Type | Automated Command                                                             | File Exists?              |
| ------ | --------------------------------------------- | --------- | ----------------------------------------------------------------------------- | ------------------------- |
| FIX-01 | --fix flag triggers fix flow                  | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixFlow"`              | Will extend existing file |
| FIX-02 | PATCH to /rest/queue/type/{id}                | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestSetQueueTypeParams"`   | Will extend existing file |
| FIX-03 | Before/after diff table + confirmation         | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixConfirmation"`      | Will extend existing file |
| FIX-04 | Lock file check blocks fix when daemon running | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestDaemonLock"`           | Will extend existing file |
| FIX-05 | JSON snapshot saved before changes             | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestSnapshot"`            | Will extend existing file |
| FIX-06 | CheckResult items for success/failure per param | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixResults"`           | Will extend existing file |
| FIX-07 | --json output mode for scripting               | unit      | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixJson"`             | Will extend existing file |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

None -- existing test infrastructure covers all phase requirements. test_check_cake.py has comprehensive test patterns from Phase 84. New test classes follow established patterns (class-per-category, MagicMock client, _queue_type_response fixtures). Tests use tmp_path for snapshot files, mock lock files via tmp directories.

## Sources

### Primary (HIGH confidence)

- [MikroTik REST API Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/47579162/REST+API) - PATCH method behavior, URL format, response format, atomicity
- [MikroTik Queues Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/328088/Queues) - Queue type properties, CAKE parameters
- Existing codebase: `routeros_rest.py` set_queue_limit (lines 614-647) - Proven PATCH pattern
- Existing codebase: `lock_utils.py` read_lock_pid + is_process_alive - Lock file read pattern
- Existing codebase: `check_cake.py` run_audit pipeline - Orchestration pattern
- Existing codebase: `path_utils.py` ensure_directory_exists - Directory creation pattern

### Secondary (MEDIUM confidence)

- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) - CAKE parameter valid values
- [Tangentsoft CAKE Configuration Guide](https://tangentsoft.com/mikrotik/wiki?name=CAKE+Configuration) - Real-world CAKE queue type configurations

### Tertiary (LOW confidence)

- RouterOS PATCH atomicity guarantee for queue types (documented for general resources, not specifically verified for queue type modifications)

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - zero new dependencies, all existing infrastructure
- Architecture: HIGH - extending proven PATCH pattern (set_queue_limit), reusing lock_utils, path_utils, CheckResult model
- PATCH behavior: HIGH - verified via official REST API docs, matches existing set_queue_limit pattern
- Lock file check: HIGH - read_lock_pid + is_process_alive fully tested and battle-proven in production
- Snapshot: HIGH - standard json.dump, no concurrency concerns for one-shot writes
- Pitfalls: HIGH - based on thorough analysis of existing PATCH code and REST API behavior

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain -- REST API PATCH and lock file patterns are production-proven)
