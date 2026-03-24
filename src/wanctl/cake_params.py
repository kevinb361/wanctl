"""CAKE parameter builder for LinuxCakeBackend.initialize_cake().

Constructs direction-aware CAKE qdisc parameter dicts using ecosystem-validated
defaults merged with YAML config overrides. Satisfies requirements:

- CAKE-01: split-gso enabled on both directions
- CAKE-02/CAKE-09: ECN enabled on download only
- CAKE-03: ack-filter enabled on upload only
- CAKE-05: Overhead keywords (docsis, bridged-ptm) as standalone tc tokens
- CAKE-06: memlimit default 32mb, configurable per-link
- CAKE-08: ingress keyword on download only
- CAKE-10: rtt default 100ms, configurable per-link (tunable candidate)

See docs/PORTABLE_CONTROLLER_ARCHITECTURE.md -- all link variability in config.
"""

from typing import Any

from wanctl.config_base import ConfigValidationError

# =============================================================================
# DIRECTION-AWARE DEFAULTS (D-01, D-04, D-05)
# =============================================================================

UPLOAD_DEFAULTS: dict[str, Any] = {
    "diffserv": "diffserv4",
    "split-gso": True,
    "ack-filter": True,  # Upload only (D-04)
    "ingress": False,  # Download only
    "ecn": False,  # Download only
}

DOWNLOAD_DEFAULTS: dict[str, Any] = {
    "diffserv": "diffserv4",
    "split-gso": True,
    "ack-filter": False,  # Upload only
    "ingress": True,  # Download only (D-05)
    "ecn": True,  # Download only (D-05)
}

DIRECTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "upload": UPLOAD_DEFAULTS,
    "download": DOWNLOAD_DEFAULTS,
}

# =============================================================================
# TUNABLE DEFAULTS (D-10, D-12)
# =============================================================================

TUNABLE_DEFAULTS: dict[str, str] = {
    "memlimit": "32mb",  # D-12: ~1Gbps links
    "rtt": "100ms",  # D-10: conservative default, tunable
}

# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

# Params that must never appear on a transparent bridge topology (D-08)
EXCLUDED_PARAMS: set[str] = {"nat", "wash", "autorate-ingress"}

# YAML underscore keys -> tc hyphen keys
YAML_TO_TC_KEY: dict[str, str] = {
    "split_gso": "split-gso",
    "ack_filter": "ack-filter",
    "autorate_ingress": "autorate-ingress",
}

# Valid tc-cake(8) overhead keywords (D-06, D-07, D-09)
VALID_OVERHEAD_KEYWORDS: set[str] = {
    "docsis",
    "bridged-ptm",
    "ethernet",
    "pppoe-ptm",
    "bridged-llcsnap",
    "pppoa-vcmux",
    "pppoa-llc",
    "pppoe-vcmux",
    "pppoe-llcsnap",
    "conservative",
    "raw",
}

# =============================================================================
# READBACK CONVERSION TABLES
# =============================================================================

# Keyword -> tc JSON readback numeric values (for validate_cake)
OVERHEAD_READBACK: dict[str, dict[str, int]] = {
    "docsis": {"overhead": 18},
    "bridged-ptm": {"overhead": 22},
    "ethernet": {"overhead": 38},
}

# Human-readable rtt string -> tc JSON microseconds integer
RTT_TO_MICROSECONDS: dict[str, int] = {
    "100ms": 100_000,
    "50ms": 50_000,
    "30ms": 30_000,
}

# Human-readable memlimit string -> tc JSON bytes integer
MEMLIMIT_TO_BYTES: dict[str, int] = {
    "32mb": 33_554_432,
    "16mb": 16_777_216,
    "64mb": 67_108_864,
}


# =============================================================================
# BUILDER FUNCTIONS
# =============================================================================


def build_cake_params(
    direction: str,
    cake_config: dict[str, Any] | None = None,
    bandwidth_kbit: int | None = None,
) -> dict[str, Any]:
    """Build CAKE params dict for LinuxCakeBackend.initialize_cake().

    Merges direction-aware hardcoded defaults with YAML config overrides.
    Boolean flags from config override defaults (D-02: False disables).

    Args:
        direction: "upload" or "download"
        cake_config: YAML cake_params section (operator overrides)
        bandwidth_kbit: Initial bandwidth in kbit/s

    Returns:
        Complete params dict ready for initialize_cake()

    Raises:
        ValueError: If direction is not "upload" or "download"
        ConfigValidationError: If config contains excluded params or
            invalid overhead keyword
    """
    if direction not in DIRECTION_DEFAULTS:
        raise ValueError(f"Invalid direction: {direction!r}")

    # Start with direction-specific defaults
    params: dict[str, Any] = dict(DIRECTION_DEFAULTS[direction])

    # Add tunable defaults
    params.update(TUNABLE_DEFAULTS)

    # Apply config overrides (D-02: explicit False disables default True)
    if cake_config:
        for key, value in cake_config.items():
            tc_key = YAML_TO_TC_KEY.get(key, key)
            if tc_key in EXCLUDED_PARAMS:
                raise ConfigValidationError(
                    f"Excluded CAKE parameter: {key!r} -- "
                    f"not valid for transparent bridge topology"
                )
            params[tc_key] = value

    # Handle overhead keyword: pop from params, validate, store as overhead_keyword
    overhead = params.pop("overhead", None)
    if overhead is not None and isinstance(overhead, str):
        if overhead not in VALID_OVERHEAD_KEYWORDS:
            raise ConfigValidationError(
                f"Invalid overhead keyword: {overhead!r} -- "
                f"valid keywords: {sorted(VALID_OVERHEAD_KEYWORDS)}"
            )
        params["overhead_keyword"] = overhead

    # Set bandwidth if provided
    if bandwidth_kbit is not None:
        params["bandwidth"] = f"{bandwidth_kbit}kbit"

    return params


def build_expected_readback(params: dict[str, Any]) -> dict[str, Any]:
    """Convert initialize_cake params to validate_cake expected values.

    Maps human-readable params to tc JSON numeric format:
    - overhead keyword -> numeric overhead (e.g., "docsis" -> 18)
    - rtt string -> microseconds (e.g., "100ms" -> 100000)
    - memlimit string -> bytes (e.g., "32mb" -> 33554432)
    - diffserv passes through unchanged

    Args:
        params: Params dict from build_cake_params()

    Returns:
        Dict of expected values matching tc -j qdisc show format.
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
        if rtt_str in RTT_TO_MICROSECONDS:
            expected["rtt"] = RTT_TO_MICROSECONDS[rtt_str]
        else:
            # Parse unknown rtt strings: strip "ms" suffix, multiply by 1000
            expected["rtt"] = int(rtt_str.rstrip("ms")) * 1000

    if "memlimit" in params:
        ml_str = str(params["memlimit"])
        if ml_str in MEMLIMIT_TO_BYTES:
            expected["memlimit"] = MEMLIMIT_TO_BYTES[ml_str]
        else:
            expected["memlimit"] = int(ml_str)

    return expected
