"""
Config Snapshot - Record configuration state on startup and reload.

Stores a snapshot of relevant config values for debugging and audit.
"""

import time
from typing import Any

from wanctl.storage.writer import MetricsWriter


def record_config_snapshot(
    writer: MetricsWriter,
    wan_name: str,
    config_data: dict[str, Any],
    trigger: str = "startup",
) -> None:
    """Record a configuration snapshot to metrics storage.

    Extracts key configuration values and stores them as labeled metrics.
    Useful for tracking config changes and debugging historical behavior.

    Args:
        writer: MetricsWriter instance
        wan_name: WAN identifier
        config_data: Raw config dictionary
        trigger: What triggered the snapshot ("startup", "reload", "manual")
    """
    ts = int(time.time())

    # Extract key config values for autorate daemon
    autorate_config: dict[str, Any] = {}
    if "continuous_monitoring" in config_data:
        cm = config_data["continuous_monitoring"]
        autorate_config = {
            "baseline_rtt_initial": cm.get("baseline_rtt_initial"),
            "download_ceiling_mbps": cm.get("download", {}).get("ceiling_mbps"),
            "upload_ceiling_mbps": cm.get("upload", {}).get("ceiling_mbps"),
            "target_bloat_ms": cm.get("thresholds", {}).get("target_bloat_ms"),
            "warn_bloat_ms": cm.get("thresholds", {}).get("warn_bloat_ms"),
        }

    # Extract key config values for steering daemon
    steering_config: dict[str, Any] = {}
    if "thresholds" in config_data:
        thresh = config_data["thresholds"]
        steering_config = {
            "bad_threshold_ms": thresh.get("bad_threshold_ms"),
            "recovery_threshold_ms": thresh.get("recovery_threshold_ms"),
            "green_rtt_ms": thresh.get("green_rtt_ms"),
            "red_rtt_ms": thresh.get("red_rtt_ms"),
        }
    if "topology" in config_data:
        steering_config["primary_wan"] = config_data["topology"].get("primary_wan")
        steering_config["alternate_wan"] = config_data["topology"].get("alternate_wan")

    # Combine into snapshot
    snapshot: dict[str, Any] = {
        "trigger": trigger,
        "autorate": autorate_config if autorate_config else None,
        "steering": steering_config if steering_config else None,
    }

    # Record as a labeled metric (value is timestamp for easy ordering)
    writer.write_metric(
        timestamp=ts,
        wan_name=wan_name,
        metric_name="wanctl_config_snapshot",
        value=float(ts),  # Timestamp as value for ordering
        labels=snapshot,
        granularity="raw",
    )
