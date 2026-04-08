"""CAKE audit fix infrastructure for applying configuration corrections.

Provides snapshot management, diff display, and interactive fix application
workflow for CAKE queue parameter corrections identified by the audit.
"""

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from wanctl.check_config import CheckResult, Severity
from wanctl.interfaces import RouterClient
from wanctl.path_utils import ensure_directory_exists

# =============================================================================
# FIX INFRASTRUCTURE CONSTANTS
# =============================================================================

SNAPSHOT_DIR = Path("/var/lib/wanctl/snapshots")
MAX_SNAPSHOTS = 20


# =============================================================================
# FIX INFRASTRUCTURE FUNCTIONS
# =============================================================================


def save_snapshot(queue_type_data: dict[str, dict], wan_name: str) -> Path:
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


def show_diff_table(
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


def confirm_apply(total_changes: int) -> bool:
    """Prompt user to confirm applying changes.

    Args:
        total_changes: Number of changes to apply.

    Returns:
        True if user confirms, False otherwise. Default (empty) is False.
    """
    response = input(f"Apply {total_changes} changes? [y/N] ")
    return response.strip().lower() in ("y", "yes")


def _apply_changes(
    client: RouterClient,
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
    # Local import to avoid circular dependency (check_cake imports from check_cake_fix)
    from wanctl.check_cake import OPTIMAL_CAKE_DEFAULTS, OPTIMAL_WASH

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


def run_fix(
    data: dict,
    config_type: str,
    client: RouterClient,
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
    from wanctl.check_cake import check_daemon_lock, run_audit

    results: list[CheckResult] = []

    # 1. Check daemon lock
    lock_results = check_daemon_lock()
    results.extend(lock_results)
    if any(r.severity == Severity.ERROR for r in lock_results):
        return results

    # 2. Gather changes
    changes_by_direction, queue_names, queue_type_data_by_direction = (
        _gather_fix_changes(data, config_type, client)
    )

    # 3-5. Validate and confirm
    early_exit = _validate_and_confirm_fix(
        changes_by_direction, queue_names, yes, json_mode, results
    )
    if early_exit:
        return results

    # 6-8. Apply and verify
    _apply_and_verify_fix(
        data, config_type, client, changes_by_direction,
        queue_names, queue_type_data_by_direction, wan_name, results, run_audit,
    )
    return results


def _gather_fix_changes(
    data: dict, config_type: str, client: RouterClient
) -> tuple[dict, dict, dict]:
    """Gather CAKE parameter changes by direction. Returns (changes, queue_names, queue_type_data)."""
    from wanctl.check_cake import _extract_cake_optimization, _extract_queue_names

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

        queue_names[direction] = queue_type_name
        queue_type_data_by_direction[queue_type_name] = queue_type_data

        changes = _extract_changes_for_direction(queue_type_data, direction, cake_config)
        if changes:
            changes_by_direction[direction] = changes

    return changes_by_direction, queue_names, queue_type_data_by_direction


def _validate_and_confirm_fix(
    changes_by_direction: dict,
    queue_names: dict,
    yes: bool,
    json_mode: bool,
    results: list[CheckResult],
) -> bool:
    """Validate preconditions and get confirmation. Returns True if should exit early."""
    if not changes_by_direction:
        results.append(CheckResult("Fix", "status", Severity.PASS, "All CAKE parameters are optimal -- nothing to fix."))
        return True

    if json_mode and not yes:
        results.append(CheckResult(
            "Fix", "mode", Severity.ERROR, "Fix in --json mode requires --yes flag",
            suggestion="Add --yes flag: wanctl-check-cake config.yaml --fix --yes --json",
        ))
        return True

    if not yes:
        show_diff_table(changes_by_direction, queue_names)
        if not confirm_apply(sum(len(c) for c in changes_by_direction.values())):
            results.append(CheckResult("Fix", "status", Severity.PASS, "Fix cancelled by user."))
            return True

    return False


def _apply_and_verify_fix(
    data: dict, config_type: str, client: RouterClient,
    changes_by_direction: dict, queue_names: dict,
    queue_type_data_by_direction: dict, wan_name: str,
    results: list[CheckResult], run_audit_fn: Callable[[dict, str, RouterClient], list[CheckResult]],
) -> None:
    """Save snapshot, apply changes, and re-run audit for verification."""
    snapshot_path = save_snapshot(queue_type_data_by_direction, wan_name or "unknown")
    print(f"Snapshot saved: {snapshot_path}", file=sys.stderr)

    results.extend(_apply_changes(client, changes_by_direction, queue_names))
    results.extend(run_audit_fn(data, config_type, client))
