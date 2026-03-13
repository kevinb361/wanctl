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
import logging
import os
import sys
from types import SimpleNamespace

import yaml

from wanctl.check_config import (
    CheckResult,
    Severity,
    detect_config_type,
    format_results,
    format_results_json,
)

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


def run_audit(data: dict, config_type: str, client: object | None) -> list[CheckResult]:
    """Run all audit checks in order.

    1. Environment variable check
    2. Connectivity -- if ERROR, skip remaining with 'Skipped: router unreachable'
    3. Queue tree audit (CAKE-02, CAKE-03, CAKE-04)
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
            remaining = ["Queue Tree", "CAKE Type"]
            if config_type == "steering":
                remaining.append("Mangle Rule")
            for category in remaining:
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
        remaining = ["Queue Tree", "CAKE Type"]
        if config_type == "steering":
            remaining.append("Mangle Rule")
        for category in remaining:
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
