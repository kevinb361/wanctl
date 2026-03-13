"""Live router audit for CAKE queue configuration.

Connects to a MikroTik router and verifies CAKE queue tree setup,
qdisc types, max-limit values, and mangle rules against what the
wanctl config expects. Strictly read-only -- never modifies router state.

Auto-detects config type (autorate vs steering) and runs appropriate
validators. Reports results in the same category-grouped format as
wanctl-check-config.

Usage:
    wanctl-check-cake spectrum.yaml
    wanctl-check-cake steering.yaml
    wanctl-check-cake spectrum.yaml --type autorate
    wanctl-check-cake spectrum.yaml --no-color
    wanctl-check-cake spectrum.yaml --json
    wanctl-check-cake spectrum.yaml -q
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

from wanctl.check_config import (
    CheckResult,
    Severity,
    detect_config_type,
    format_results,
    format_results_json,
)
from wanctl.lock_utils import is_process_alive, read_lock_pid
from wanctl.path_utils import ensure_directory_exists

# =============================================================================
# CAKE OPTIMAL DEFAULTS
# =============================================================================

# Link-independent optimal CAKE parameters.
# Values are RouterOS REST API string representations.
# cake-ack-filter: "yes" in discussion = "filter" in RouterOS (the enabled value).
OPTIMAL_CAKE_DEFAULTS: dict[str, str] = {
    "cake-flowmode": "triple-isolate",
    "cake-diffserv": "diffserv4",
    "cake-nat": "yes",
    "cake-ack-filter": "filter",
}

# Direction-dependent wash optimal values.
# Upload: wash=yes (strip DSCP before ISP -- ISP ignores marks anyway;
#   CAKE classifies BEFORE washing so diffserv4 still works).
# Download: wash=no (preserve DSCP marks for LAN/WiFi WMM QoS).
OPTIMAL_WASH: dict[str, str] = {
    "upload": "yes",
    "download": "no",
}

# =============================================================================
# FIX INFRASTRUCTURE CONSTANTS
# =============================================================================

LOCK_DIR = Path("/run/wanctl")
SNAPSHOT_DIR = Path("/var/lib/wanctl/snapshots")
MAX_SNAPSHOTS = 20

# =============================================================================
# CONFIG EXTRACTION (pure functions)
# =============================================================================


def _extract_router_config(data: dict) -> dict:
    """Extract router connection fields from raw YAML data.

    Returns a dict with keys needed to create a router client:
    router_host, router_user, router_transport, router_password,
    router_port, router_verify_ssl, ssh_key, timeout_ssh_command.
    """
    router = data.get("router", {})
    timeouts = data.get("timeouts", {})
    return {
        "router_host": router.get("host", ""),
        "router_user": router.get("user", "admin"),
        "router_transport": router.get("transport", "rest"),
        "router_password": router.get("password", ""),
        "router_port": router.get("port", 443),
        "router_verify_ssl": router.get("verify_ssl", True),
        "ssh_key": router.get("ssh_key", ""),
        "timeout_ssh_command": timeouts.get("ssh_command", 15),
    }


def _extract_queue_names(data: dict, config_type: str) -> dict[str, str]:
    """Extract expected queue names from raw YAML data.

    Returns dict with 'download' and 'upload' keys.

    For autorate: reads queues.download / queues.upload.
    For steering: reads cake_queues.primary_download / primary_upload,
    with defaults derived from topology.primary_wan. Also supports
    deprecated spectrum_download/spectrum_upload keys.
    """
    if config_type == "autorate":
        queues = data.get("queues", {})
        return {
            "download": queues.get("download", ""),
            "upload": queues.get("upload", ""),
        }
    else:  # steering
        topology = data.get("topology", {})
        primary_wan = topology.get("primary_wan", "wan1")
        cake_queues = data.get("cake_queues", {})
        default_dl = f"WAN-Download-{primary_wan.capitalize()}"
        default_ul = f"WAN-Upload-{primary_wan.capitalize()}"

        # Support deprecated spectrum_download/spectrum_upload keys
        dl = cake_queues.get("primary_download", cake_queues.get("spectrum_download", default_dl))
        ul = cake_queues.get("primary_upload", cake_queues.get("spectrum_upload", default_ul))
        return {
            "download": dl,
            "upload": ul,
        }


def _extract_ceilings(data: dict, config_type: str) -> dict[str, int | None]:
    """Extract expected ceiling values (bps) from raw YAML data.

    Returns dict with 'download' and 'upload' keys (None if not found).
    For autorate: continuous_monitoring.download.ceiling_mbps * 1_000_000
    For steering: no ceiling in steering config (steering doesn't set limits)
    """
    if config_type == "autorate":
        cm = data.get("continuous_monitoring", {})
        dl = cm.get("download", {})
        ul = cm.get("upload", {})
        dl_ceiling = dl.get("ceiling_mbps")
        ul_ceiling = ul.get("ceiling_mbps")
        return {
            "download": int(dl_ceiling * 1_000_000) if dl_ceiling else None,
            "upload": int(ul_ceiling * 1_000_000) if ul_ceiling else None,
        }
    else:  # steering has no ceiling config
        return {"download": None, "upload": None}


def _extract_mangle_comment(data: dict) -> str | None:
    """Extract mangle rule comment from steering config data."""
    mangle = data.get("mangle_rule", {})
    return mangle.get("comment")


def _extract_cake_optimization(data: dict) -> dict | None:
    """Extract cake_optimization config section from raw YAML data.

    Returns the cake_optimization dict if present and non-None,
    or None if the key is absent or its value is None (empty YAML key).

    Expected config format:
        cake_optimization:
            overhead: 18
            rtt: 100ms
    """
    value = data.get("cake_optimization")
    if value is not None and isinstance(value, dict):
        return value
    return None


# =============================================================================
# ENV VAR CHECK
# =============================================================================


def check_env_vars(data: dict) -> list[CheckResult]:
    """Check if router password contains unresolved ${VAR} references.

    Detects unset environment variables before connection attempt to provide
    clear error messages instead of confusing auth failures.

    Returns list of CheckResult.
    """
    results: list[CheckResult] = []
    router = data.get("router", {})
    password = router.get("password", "")

    if (
        password
        and isinstance(password, str)
        and password.startswith("${")
        and password.endswith("}")
    ):
        env_var = password[2:-1]
        if os.environ.get(env_var):
            results.append(
                CheckResult(
                    "Environment",
                    "router_password",
                    Severity.PASS,
                    f"Environment variable {env_var} is set",
                )
            )
        else:
            results.append(
                CheckResult(
                    "Environment",
                    "router_password",
                    Severity.ERROR,
                    f"Environment variable {env_var} is not set",
                    suggestion=f"Set {env_var} before running: export {env_var}=<password>",
                )
            )
    return results


# =============================================================================
# CONNECTIVITY
# =============================================================================


def check_connectivity(client: object, transport: str, host: str, port: int) -> list[CheckResult]:
    """Test router reachability and authentication.

    For REST: uses client.test_connection() (GET /system/resource).
    For SSH: uses client.run_cmd() with a simple command.

    Returns list of CheckResult.
    """
    results: list[CheckResult] = []
    try:
        if hasattr(client, "test_connection"):
            ok = client.test_connection()
        else:
            # SSH transport: no test_connection method
            rc, _, _ = client.run_cmd("/system/resource/print", capture=True, timeout=5)
            ok = rc == 0

        if ok:
            results.append(
                CheckResult(
                    "Connectivity",
                    "router",
                    Severity.PASS,
                    f"Router connectivity ({transport}, {host}:{port})",
                )
            )
        else:
            results.append(
                CheckResult(
                    "Connectivity",
                    "router",
                    Severity.ERROR,
                    f"Router connectivity failed ({transport}, {host}:{port}): "
                    f"authentication or access denied",
                )
            )
    except Exception as e:
        results.append(
            CheckResult(
                "Connectivity",
                "router",
                Severity.ERROR,
                f"Router connectivity failed ({transport}, {host}:{port}): {e}",
            )
        )
    return results


# =============================================================================
# QUEUE AUDIT (CAKE-02, CAKE-03, CAKE-04)
# =============================================================================


def check_queue_tree(
    client: object,
    queue_names: dict[str, str],
    ceilings: dict[str, int | None],
    config_type: str,
) -> list[CheckResult]:
    """Audit queue tree configuration on router.

    For each direction (download, upload):
      - Check queue exists (CAKE-02)
      - Check qdisc type starts with 'cake' (CAKE-03)
      - For autorate with ceiling: compare ceiling to max-limit (CAKE-04)

    Returns list of CheckResult. Reports each direction independently
    (no bail-out on partial failure).
    """
    results: list[CheckResult] = []

    for direction in ("download", "upload"):
        queue_name = queue_names.get(direction, "")
        if not queue_name:
            results.append(
                CheckResult(
                    "Queue Tree",
                    f"{direction}_queue",
                    Severity.ERROR,
                    f"No {direction} queue name configured",
                )
            )
            continue

        # Get queue stats from router
        stats = client.get_queue_stats(queue_name)

        if stats is None:
            # CAKE-02: queue not found
            results.append(
                CheckResult(
                    "Queue Tree",
                    f"{direction}_queue",
                    Severity.ERROR,
                    f"Queue not found: {queue_name}",
                    suggestion=f"Create queue tree entry '{queue_name}' on router",
                )
            )
            continue

        # CAKE-02: queue exists
        results.append(
            CheckResult(
                "Queue Tree",
                f"{direction}_queue",
                Severity.PASS,
                f"Queue exists: {queue_name}",
            )
        )

        # CAKE-03: verify qdisc type
        qdisc_type = stats.get("queue", "")
        if qdisc_type.startswith("cake"):
            results.append(
                CheckResult(
                    "CAKE Type",
                    f"{direction}_type",
                    Severity.PASS,
                    f"CAKE qdisc type: {qdisc_type} ({direction})",
                )
            )
        else:
            results.append(
                CheckResult(
                    "CAKE Type",
                    f"{direction}_type",
                    Severity.ERROR,
                    f"Wrong qdisc type for {direction}: '{qdisc_type}' (expected cake*)",
                    suggestion="Set queue type to a CAKE qdisc on router",
                )
            )

        # CAKE-04: ceiling comparison (autorate only, when ceiling is available)
        ceiling = ceilings.get(direction)
        if ceiling is not None:
            actual_limit = int(stats.get("max-limit", "0"))
            if actual_limit == ceiling:
                results.append(
                    CheckResult(
                        "Queue Tree",
                        f"{direction}_max_limit",
                        Severity.PASS,
                        f"Max-limit matches ceiling: {actual_limit} ({direction})",
                    )
                )
            else:
                # Different is expected during congestion -- informational PASS
                results.append(
                    CheckResult(
                        "Queue Tree",
                        f"{direction}_max_limit",
                        Severity.PASS,
                        f"Max-limit {actual_limit} (current), ceiling {ceiling} (config) "
                        f"-- max-limit changes dynamically during congestion ({direction})",
                    )
                )

    return results


# =============================================================================
# CAKE PARAM CHECKS
# =============================================================================

# Rationale strings for sub-optimal link-independent params.
_RATIONALE: dict[str, str] = {
    "cake-flowmode": "Sub-optimal: triple-isolate provides per-host + per-flow isolation for multi-device networks",
    "cake-diffserv": "Sub-optimal: diffserv4 provides 4-tier priority (Bulk / Best Effort / Video / Voice)",
    "cake-nat": "Sub-optimal: NAT-aware host isolation is required behind NAT routers",
    "cake-ack-filter": "Sub-optimal: ACK filtering compresses TCP ACKs to save upload bandwidth",
}


def check_cake_params(queue_type_data: dict, direction: str) -> list[CheckResult]:
    """Check link-independent CAKE parameters against optimal defaults.

    Compares 4 fixed params (flowmode, diffserv, nat, ack-filter) plus
    direction-dependent wash against OPTIMAL_CAKE_DEFAULTS and OPTIMAL_WASH.

    Returns PASS for optimal, WARNING for sub-optimal with rationale.
    """
    results: list[CheckResult] = []
    category = f"CAKE Params ({direction})"

    # Check fixed link-independent params
    for key, expected in OPTIMAL_CAKE_DEFAULTS.items():
        actual = queue_type_data.get(key, "")
        short_name = key.removeprefix("cake-")
        if actual == expected:
            results.append(
                CheckResult(
                    category,
                    short_name,
                    Severity.PASS,
                    f"{short_name}: {actual} (optimal)",
                )
            )
        else:
            results.append(
                CheckResult(
                    category,
                    short_name,
                    Severity.WARN,
                    f"{short_name}: {actual} -> {expected}",
                    suggestion=_RATIONALE.get(key, "Sub-optimal value"),
                )
            )

    # Check wash (direction-dependent)
    expected_wash = OPTIMAL_WASH[direction]
    actual_wash = queue_type_data.get("cake-wash", "")
    if actual_wash == expected_wash:
        results.append(
            CheckResult(
                category,
                "wash",
                Severity.PASS,
                f"wash: {actual_wash} (optimal)",
            )
        )
    else:
        if direction == "upload":
            wash_rationale = (
                "Sub-optimal: sends DSCP marks to ISP that ignores them; "
                "wash is safe because CAKE classifies before stripping"
            )
        else:
            wash_rationale = (
                "Sub-optimal: clears your own DSCP marks before "
                "LAN/WiFi WMM devices see them"
            )
        results.append(
            CheckResult(
                category,
                "wash",
                Severity.WARN,
                f"wash: {actual_wash} -> {expected_wash}",
                suggestion=wash_rationale,
            )
        )

    return results


def check_link_params(
    queue_type_data: dict, direction: str, cake_config: dict | None
) -> list[CheckResult]:
    """Check link-dependent CAKE parameters against YAML config values.

    Compares overhead and rtt from router queue type data against
    cake_optimization config section. Returns ERROR for mismatch, PASS
    for match, or informational PASS if no config section present.
    """
    results: list[CheckResult] = []

    if cake_config is None:
        results.append(
            CheckResult(
                "Link Params",
                "config",
                Severity.PASS,
                "No cake_optimization config -- add cake_optimization: "
                "section to check overhead and rtt",
            )
        )
        return results

    category = f"Link Params ({direction})"

    # Compare overhead (YAML int -> str for comparison)
    expected_overhead = str(cake_config.get("overhead", ""))
    actual_overhead = queue_type_data.get("cake-overhead", "")
    if actual_overhead == expected_overhead:
        results.append(
            CheckResult(
                category,
                "overhead",
                Severity.PASS,
                f"overhead: {actual_overhead} (optimal)",
            )
        )
    else:
        results.append(
            CheckResult(
                category,
                "overhead",
                Severity.ERROR,
                f"overhead: {actual_overhead} -> {expected_overhead}",
                suggestion="Wrong overhead wastes bandwidth or causes incorrect shaping",
            )
        )

    # Compare rtt (YAML str/int -> str for comparison)
    expected_rtt = str(cake_config.get("rtt", ""))
    actual_rtt = queue_type_data.get("cake-rtt", "")
    if actual_rtt == expected_rtt:
        results.append(
            CheckResult(
                category,
                "rtt",
                Severity.PASS,
                f"rtt: {actual_rtt} (optimal)",
            )
        )
    else:
        results.append(
            CheckResult(
                category,
                "rtt",
                Severity.ERROR,
                f"rtt: {actual_rtt} -> {expected_rtt}",
                suggestion="Incorrect RTT hint affects CAKE shaper response time",
            )
        )

    return results


# =============================================================================
# MANGLE RULE (CAKE-05)
# =============================================================================


def check_mangle_rule(client: object, mangle_comment: str) -> list[CheckResult]:
    """Verify steering mangle rule exists on router.

    For REST: uses client._find_mangle_rule_id(comment).
    For SSH: runs mangle print with comment filter.

    Returns list of CheckResult.
    """
    results: list[CheckResult] = []

    try:
        if hasattr(client, "_find_mangle_rule_id"):
            rule_id = client._find_mangle_rule_id(mangle_comment)
            found = rule_id is not None
        else:
            # SSH fallback
            rc, stdout, _ = client.run_cmd(
                f'/ip firewall mangle print where comment~"{mangle_comment}"',
                capture=True,
                timeout=5,
            )
            found = rc == 0 and len(stdout.strip()) > 0

        if found:
            results.append(
                CheckResult(
                    "Mangle Rule",
                    "mangle_rule",
                    Severity.PASS,
                    f"Mangle rule found: {mangle_comment}",
                )
            )
        else:
            results.append(
                CheckResult(
                    "Mangle Rule",
                    "mangle_rule",
                    Severity.ERROR,
                    f"Mangle rule not found: {mangle_comment}",
                    suggestion="Create mangle rule with matching comment on router",
                )
            )
    except Exception as e:
        results.append(
            CheckResult(
                "Mangle Rule",
                "mangle_rule",
                Severity.ERROR,
                f"Mangle rule check failed: {e}",
            )
        )

    return results


# =============================================================================
# ORCHESTRATOR
# =============================================================================


def _skippable_categories(config_type: str) -> list[str]:
    """Return categories to skip when router is unreachable."""
    categories = [
        "Queue Tree",
        "CAKE Type",
        "CAKE Params (download)",
        "CAKE Params (upload)",
        "Link Params (download)",
        "Link Params (upload)",
    ]
    if config_type == "steering":
        categories.append("Mangle Rule")
    return categories


def run_audit(data: dict, config_type: str, client: object | None) -> list[CheckResult]:
    """Run all audit checks in order.

    1. Environment variable check
    2. Connectivity -- if ERROR, skip remaining with 'Skipped: router unreachable'
    3. Queue tree audit (CAKE-02, CAKE-03, CAKE-04)
    3.5. CAKE queue type parameter checks
    4. Mangle rule check (CAKE-05, steering only)

    Args:
        data: Parsed YAML config data.
        config_type: 'autorate' or 'steering'.
        client: Router client instance (RouterOSREST or RouterOSSSH), or None
                if env var check failed.

    Returns:
        List of all CheckResult.
    """
    results: list[CheckResult] = []
    router_cfg = _extract_router_config(data)

    # 1. Environment variable check
    env_results = check_env_vars(data)
    results.extend(env_results)

    # If env var check has errors, skip connectivity (can't authenticate)
    if any(r.severity == Severity.ERROR for r in env_results) or client is None:
        if any(r.severity == Severity.ERROR for r in env_results):
            for category in _skippable_categories(config_type):
                results.append(
                    CheckResult(
                        category,
                        "skipped",
                        Severity.ERROR,
                        "Skipped: router unreachable (environment variable not set)",
                    )
                )
        return results

    # 2. Connectivity check
    transport = router_cfg["router_transport"]
    host = router_cfg["router_host"]
    port = router_cfg["router_port"]
    connectivity_results = check_connectivity(client, transport, host, port)
    results.extend(connectivity_results)

    # If connectivity failed, skip remaining checks
    if any(r.severity == Severity.ERROR for r in connectivity_results):
        for category in _skippable_categories(config_type):
            results.append(
                CheckResult(
                    category,
                    "skipped",
                    Severity.ERROR,
                    "Skipped: router unreachable",
                )
            )
        return results

    # 3. Queue tree audit (CAKE-02, CAKE-03, CAKE-04)
    queue_names = _extract_queue_names(data, config_type)
    ceilings = _extract_ceilings(data, config_type)
    results.extend(check_queue_tree(client, queue_names, ceilings, config_type))

    # 3.5 CAKE queue type parameter checks
    cake_config = _extract_cake_optimization(data)
    for direction in ("download", "upload"):
        queue_name = queue_names.get(direction, "")
        if not queue_name:
            continue
        # Get queue tree entry to extract queue type name
        stats = client.get_queue_stats(queue_name)
        if stats is None:
            continue
        queue_type_name = stats.get("queue", "")
        if not queue_type_name or not queue_type_name.startswith("cake"):
            continue
        # Fetch queue type details
        queue_type_data = client.get_queue_types(queue_type_name)
        if queue_type_data is None:
            results.append(
                CheckResult(
                    f"CAKE Params ({direction})",
                    "queue_type",
                    Severity.ERROR,
                    f"Queue type not found: {queue_type_name}",
                    suggestion="Verify queue type exists on router",
                )
            )
            continue
        # Run checks
        results.extend(check_cake_params(queue_type_data, direction))
        results.extend(check_link_params(queue_type_data, direction, cake_config))

    # 4. Mangle rule check (CAKE-05, steering only)
    if config_type == "steering":
        mangle_comment = _extract_mangle_comment(data)
        if mangle_comment:
            results.extend(check_mangle_rule(client, mangle_comment))
        else:
            results.append(
                CheckResult(
                    "Mangle Rule",
                    "mangle_comment",
                    Severity.ERROR,
                    "No mangle_rule.comment configured",
                    suggestion="Add mangle_rule.comment to steering config",
                )
            )

    return results


# =============================================================================
# FIX INFRASTRUCTURE
# =============================================================================


def check_daemon_lock() -> list[CheckResult]:
    """Check if a wanctl daemon is currently running via lock files.

    Globs /run/wanctl/*.lock and checks each lock file's PID for liveness.
    A running daemon must be stopped before applying fixes to avoid conflicts
    with the autorate controller's queue management.

    Returns:
        List with single CheckResult: PASS if no live daemon, ERROR if daemon running.
    """
    if not LOCK_DIR.exists():
        return [
            CheckResult(
                "Daemon Lock",
                "lock_check",
                Severity.PASS,
                "No wanctl daemon lock files found",
            )
        ]

    lock_files = list(LOCK_DIR.glob("*.lock"))
    for lock_file in lock_files:
        pid = read_lock_pid(lock_file)
        if pid is not None and is_process_alive(pid):
            wan_name = lock_file.stem
            return [
                CheckResult(
                    "Daemon Lock",
                    "lock_check",
                    Severity.ERROR,
                    f"wanctl daemon is running (PID {pid}, lock: {lock_file.name})",
                    suggestion=f"Stop the daemon first: systemctl stop wanctl@{wan_name}",
                )
            ]

    return [
        CheckResult(
            "Daemon Lock",
            "lock_check",
            Severity.PASS,
            "No running wanctl daemon detected",
        )
    ]


def _save_snapshot(queue_type_data: dict[str, dict], wan_name: str) -> Path:
    """Save current queue type parameters as a JSON snapshot.

    Creates a timestamped snapshot in SNAPSHOT_DIR for rollback purposes.
    Automatically prunes old snapshots beyond MAX_SNAPSHOTS.

    Args:
        queue_type_data: Dict mapping queue type names to their parameter dicts.
        wan_name: WAN name for file naming (e.g., "spectrum").

    Returns:
        Path to the created snapshot file.
    """
    ensure_directory_exists(SNAPSHOT_DIR)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}_{wan_name}.json"
    snapshot_path = SNAPSHOT_DIR / filename

    snapshot = {
        "queue_types": queue_type_data,
        "timestamp": timestamp,
        "wan_name": wan_name,
    }

    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    _prune_snapshots(wan_name)
    return snapshot_path


def _prune_snapshots(wan_name: str) -> None:
    """Remove oldest snapshot files when count exceeds MAX_SNAPSHOTS.

    Only prunes snapshots matching the given WAN name. Files are sorted
    by name (timestamp prefix ensures chronological order).

    Args:
        wan_name: WAN name to filter snapshots (e.g., "spectrum").
    """
    if not SNAPSHOT_DIR.exists():
        return

    files = sorted(SNAPSHOT_DIR.glob(f"*_{wan_name}.json"))
    while len(files) > MAX_SNAPSHOTS:
        oldest = files.pop(0)
        oldest.unlink()


def _show_diff_table(
    changes_by_direction: dict[str, dict[str, tuple[str, str]]],
    queue_names: dict[str, str],
) -> int:
    """Print proposed parameter changes as a table grouped by direction.

    Outputs to stderr so --json stdout stays clean.

    Args:
        changes_by_direction: Dict mapping direction to {param: (current, recommended)}.
        queue_names: Dict mapping direction to queue type name.

    Returns:
        Total number of parameter changes across all directions.
    """
    total = 0
    for direction, changes in changes_by_direction.items():
        if not changes:
            continue
        queue_name = queue_names.get(direction, "unknown")
        print(f"\nProposed changes for {queue_name} ({direction}):", file=sys.stderr)
        print(f"  {'Parameter':<20} {'Current':<20} {'Recommended':<20}", file=sys.stderr)
        print(f"  {'-' * 20} {'-' * 20} {'-' * 20}", file=sys.stderr)
        for key, (current, recommended) in changes.items():
            display_name = key.removeprefix("cake-")
            print(f"  {display_name:<20} {current:<20} {recommended:<20}", file=sys.stderr)
            total += 1
    return total


def _confirm_apply(total_changes: int) -> bool:
    """Prompt user to confirm applying changes.

    Args:
        total_changes: Number of changes to apply.

    Returns:
        True if user confirms, False otherwise. Default (empty) is False.
    """
    response = input(f"Apply {total_changes} changes? [y/N] ")
    return response.strip().lower() in ("y", "yes")


def _apply_changes(
    client: object,
    changes_by_direction: dict[str, dict[str, tuple[str, str]]],
    queue_names: dict[str, str],
) -> list[CheckResult]:
    """Apply parameter changes to router via PATCH.

    Sends a single PATCH per queue type (all changed params in one call).
    RouterOS PATCH is atomic per resource.

    Args:
        client: Router client with set_queue_type_params method.
        changes_by_direction: Dict mapping direction to {param: (current, recommended)}.
        queue_names: Dict mapping direction to queue type name.

    Returns:
        List of CheckResult: PASS per param on success, ERROR per param on failure.
    """
    results: list[CheckResult] = []

    for direction, changes in changes_by_direction.items():
        if not changes:
            continue
        queue_name = queue_names.get(direction, "unknown")
        category = f"Fix Applied ({direction})"

        # Build params dict: {key: recommended_value}
        params = {key: recommended for key, (_current, recommended) in changes.items()}

        # Single PATCH per queue type
        success = client.set_queue_type_params(queue_name, params)

        for key, (_current, recommended) in changes.items():
            display_name = key.removeprefix("cake-")
            if success:
                results.append(
                    CheckResult(
                        category,
                        display_name,
                        Severity.PASS,
                        f"{display_name}: applied {recommended}",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        category,
                        display_name,
                        Severity.ERROR,
                        f"{display_name}: failed to apply {recommended}",
                    )
                )

    return results


def run_fix(
    data: dict,
    config_type: str,
    client: object,
    yes: bool = False,
    json_mode: bool = False,
    wan_name: str = "",
) -> list[CheckResult]:
    """Orchestrate the complete fix flow: lock -> audit -> diff -> confirm -> snapshot -> apply -> verify.

    Args:
        data: Parsed YAML config data.
        config_type: 'autorate' or 'steering'.
        client: Router client instance.
        yes: If True, skip confirmation prompt.
        json_mode: If True, output mode is JSON (requires yes=True).
        wan_name: WAN name for snapshot naming.

    Returns:
        List of all CheckResult from the fix flow.
    """
    results: list[CheckResult] = []

    # 1. Check daemon lock
    lock_results = check_daemon_lock()
    results.extend(lock_results)
    if any(r.severity == Severity.ERROR for r in lock_results):
        return results

    # 2. Gather changes by direction (same data-fetching as step 3.5 in run_audit)
    queue_names = _extract_queue_names(data, config_type)
    cake_config = _extract_cake_optimization(data)
    changes_by_direction: dict[str, dict[str, tuple[str, str]]] = {}
    queue_type_data_by_direction: dict[str, dict] = {}

    for direction in ("download", "upload"):
        queue_name = queue_names.get(direction, "")
        if not queue_name:
            continue
        stats = client.get_queue_stats(queue_name)
        if stats is None:
            continue
        queue_type_name = stats.get("queue", "")
        if not queue_type_name or not queue_type_name.startswith("cake"):
            continue
        queue_type_data = client.get_queue_types(queue_type_name)
        if queue_type_data is None:
            continue

        # Store queue type name in queue_names for PATCH targeting
        queue_names[direction] = queue_type_name
        queue_type_data_by_direction[queue_type_name] = queue_type_data

        changes = _extract_changes_for_direction(queue_type_data, direction, cake_config)
        if changes:
            changes_by_direction[direction] = changes

    # 3. Nothing to fix?
    if not changes_by_direction:
        results.append(
            CheckResult(
                "Fix",
                "status",
                Severity.PASS,
                "All CAKE parameters are optimal -- nothing to fix.",
            )
        )
        return results

    # 4. JSON mode requires --yes
    if json_mode and not yes:
        results.append(
            CheckResult(
                "Fix",
                "mode",
                Severity.ERROR,
                "Fix in --json mode requires --yes flag",
                suggestion="Add --yes flag: wanctl-check-cake config.yaml --fix --yes --json",
            )
        )
        return results

    # 5. Confirmation
    if not yes:
        _show_diff_table(changes_by_direction, queue_names)
        if not _confirm_apply(sum(len(c) for c in changes_by_direction.values())):
            results.append(
                CheckResult(
                    "Fix",
                    "status",
                    Severity.PASS,
                    "Fix cancelled by user.",
                )
            )
            return results

    # 6. Save snapshot
    snapshot_path = _save_snapshot(queue_type_data_by_direction, wan_name or "unknown")
    print(f"Snapshot saved: {snapshot_path}", file=sys.stderr)

    # 7. Apply changes
    apply_results = _apply_changes(client, changes_by_direction, queue_names)
    results.extend(apply_results)

    # 8. Re-run audit for verification
    verify_results = run_audit(data, config_type, client)
    results.extend(verify_results)

    return results


def _extract_changes_for_direction(
    queue_type_data: dict, direction: str, cake_config: dict | None
) -> dict[str, tuple[str, str]]:
    """Derive sub-optimal params by comparing router data against optimal defaults.

    Compares each key in OPTIMAL_CAKE_DEFAULTS and OPTIMAL_WASH against
    queue_type_data. When cake_config is provided, also compares overhead
    and rtt. Returns only the mismatches.

    Args:
        queue_type_data: Router queue type response dict.
        direction: "download" or "upload".
        cake_config: cake_optimization config section, or None.

    Returns:
        Dict of {param_key: (actual_value, expected_value)} for mismatches.
        Empty dict if all params are optimal.
    """
    changes: dict[str, tuple[str, str]] = {}

    # Check link-independent CAKE defaults
    for key, expected in OPTIMAL_CAKE_DEFAULTS.items():
        actual = queue_type_data.get(key, "")
        if actual != expected:
            changes[key] = (actual, expected)

    # Check wash (direction-dependent)
    expected_wash = OPTIMAL_WASH[direction]
    actual_wash = queue_type_data.get("cake-wash", "")
    if actual_wash != expected_wash:
        changes["cake-wash"] = (actual_wash, expected_wash)

    # Check overhead and rtt (only when cake_config is provided)
    if cake_config is not None:
        expected_overhead = str(cake_config.get("overhead", ""))
        actual_overhead = queue_type_data.get("cake-overhead", "")
        if actual_overhead != expected_overhead:
            changes["cake-overhead"] = (actual_overhead, expected_overhead)

        expected_rtt = str(cake_config.get("rtt", ""))
        actual_rtt = queue_type_data.get("cake-rtt", "")
        if actual_rtt != expected_rtt:
            changes["cake-rtt"] = (actual_rtt, expected_rtt)

    return changes


# =============================================================================
# CLIENT CREATION
# =============================================================================


def _create_audit_client(router_cfg: dict) -> object:
    """Create a router client from extracted config dict.

    Uses SimpleNamespace to satisfy the config interface expected by
    RouterOSREST.from_config() and RouterOSSSH.from_config().
    """
    ns = SimpleNamespace(**router_cfg)
    logger = logging.getLogger("wanctl.check_cake")

    transport = router_cfg["router_transport"]
    if transport == "rest":
        from wanctl.routeros_rest import RouterOSREST

        return RouterOSREST.from_config(ns, logger)
    elif transport == "ssh":
        from wanctl.routeros_ssh import RouterOSSSH

        return RouterOSSSH.from_config(ns, logger)
    else:
        raise ValueError(f"Unsupported transport: {transport}")


# =============================================================================
# CLI
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="wanctl-check-cake",
        description="Audit CAKE queue configuration on MikroTik router against wanctl config",
    )
    parser.add_argument("config_file", help="Path to YAML config file")
    parser.add_argument(
        "--type",
        choices=["autorate", "steering"],
        default=None,
        help="Override auto-detection of config type",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only show warnings and errors")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    return parser


def main() -> int:
    """Main entry point for wanctl-check-cake CLI.

    Returns:
        Exit code: 0=pass, 1=errors, 2=warnings-only
    """
    parser = create_parser()
    args = parser.parse_args()

    # Load YAML
    config_path = args.config_file
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        return 1
    except yaml.YAMLError as e:
        print(f"Error: invalid YAML in {config_path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(
            f"Error: config file must contain a YAML mapping, got {type(data).__name__}",
            file=sys.stderr,
        )
        return 1

    # Determine config type
    if args.type:
        config_type = args.type
    else:
        try:
            config_type = detect_config_type(data)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Check env vars first -- if env var missing, run_audit handles skip logic
    # but we still need a client for the non-error path
    env_results = check_env_vars(data)
    env_has_errors = any(r.severity == Severity.ERROR for r in env_results)

    client = None
    if not env_has_errors:
        router_cfg = _extract_router_config(data)
        try:
            client = _create_audit_client(router_cfg)
        except Exception as e:
            print(f"Error: failed to create router client: {e}", file=sys.stderr)
            return 1

    try:
        results = run_audit(data, config_type, client)
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()

    # Format and print
    if args.json:
        output = format_results_json(results, config_type=config_type)
    else:
        output = format_results(
            results,
            no_color=args.no_color,
            quiet=args.quiet,
            config_type=config_type,
        )
    print(output)

    # Determine exit code
    has_errors = any(r.severity == Severity.ERROR for r in results)
    has_warnings = any(r.severity == Severity.WARN for r in results)

    if has_errors:
        return 1
    if has_warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
