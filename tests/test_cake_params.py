"""Tests for CakeParamsBuilder module.

CAKE-01, CAKE-02, CAKE-03, CAKE-05, CAKE-06, CAKE-08, CAKE-09, CAKE-10:
Direction-aware CAKE parameter construction with config overrides.

Coverage targets:
- build_cake_params upload defaults: split-gso, ack-filter, no ingress/ecn
- build_cake_params download defaults: split-gso, ingress, ecn, no ack-filter
- Tunable defaults: memlimit=32mb, rtt=100ms
- Overhead keyword handling: docsis, bridged-ptm, validation
- Config override semantics: False disables, string replaces
- Excluded params: nat, wash, autorate-ingress raise ConfigValidationError
- Bandwidth parameter: optional kbit formatting
- Full scenarios: Spectrum upload, ATT download
- build_expected_readback: keyword->numeric, rtt->microseconds, memlimit->bytes
- Invalid direction: ValueError
"""

import pytest

from wanctl.cake_params import (
    DOWNLOAD_DEFAULTS,
    EXCLUDED_PARAMS,
    MEMLIMIT_TO_BYTES,
    OVERHEAD_READBACK,
    RTT_TO_MICROSECONDS,
    TUNABLE_DEFAULTS,
    UPLOAD_DEFAULTS,
    VALID_OVERHEAD_KEYWORDS,
    YAML_TO_TC_KEY,
    build_cake_params,
    build_expected_readback,
)
from wanctl.config_base import ConfigValidationError

# =============================================================================
# UPLOAD DEFAULTS (CAKE-01, CAKE-03)
# =============================================================================


class TestBuildCakeParamsUploadDefaults:
    """Verify upload direction defaults match D-04."""

    def test_split_gso_enabled(self) -> None:
        params = build_cake_params("upload")
        assert params["split-gso"] is True

    def test_ack_filter_enabled(self) -> None:
        params = build_cake_params("upload")
        assert params["ack-filter"] is True

    def test_ingress_disabled(self) -> None:
        params = build_cake_params("upload")
        assert params["ingress"] is False

    def test_ecn_disabled(self) -> None:
        params = build_cake_params("upload")
        assert params["ecn"] is False

    def test_diffserv4(self) -> None:
        params = build_cake_params("upload")
        assert params["diffserv"] == "diffserv4"


# =============================================================================
# DOWNLOAD DEFAULTS (CAKE-01, CAKE-02, CAKE-08, CAKE-09)
# =============================================================================


class TestBuildCakeParamsDownloadDefaults:
    """Verify download direction defaults match D-05."""

    def test_split_gso_enabled(self) -> None:
        params = build_cake_params("download")
        assert params["split-gso"] is True

    def test_ack_filter_disabled(self) -> None:
        params = build_cake_params("download")
        assert params["ack-filter"] is False

    def test_ingress_enabled(self) -> None:
        params = build_cake_params("download")
        assert params["ingress"] is True

    def test_ecn_enabled(self) -> None:
        params = build_cake_params("download")
        assert params["ecn"] is True

    def test_diffserv4(self) -> None:
        params = build_cake_params("download")
        assert params["diffserv"] == "diffserv4"


# =============================================================================
# TUNABLE DEFAULTS (CAKE-06, CAKE-10)
# =============================================================================


class TestBuildCakeParamsTunableDefaults:
    """Verify tunable defaults for memlimit and rtt."""

    def test_memlimit_default(self) -> None:
        params = build_cake_params("upload")
        assert params["memlimit"] == "32mb"

    def test_rtt_default(self) -> None:
        params = build_cake_params("upload")
        assert params["rtt"] == "100ms"

    def test_memlimit_in_download(self) -> None:
        params = build_cake_params("download")
        assert params["memlimit"] == "32mb"

    def test_rtt_in_download(self) -> None:
        params = build_cake_params("download")
        assert params["rtt"] == "100ms"


# =============================================================================
# OVERHEAD KEYWORD HANDLING (CAKE-05)
# =============================================================================


class TestBuildCakeParamsOverhead:
    """Verify overhead keyword handling per D-06, D-07, D-09."""

    def test_docsis_keyword(self) -> None:
        params = build_cake_params("upload", {"overhead": "docsis"})
        assert params["overhead_keyword"] == "docsis"
        assert "overhead" not in params

    def test_bridged_ptm_keyword(self) -> None:
        params = build_cake_params("upload", {"overhead": "bridged-ptm"})
        assert params["overhead_keyword"] == "bridged-ptm"
        assert "overhead" not in params

    def test_invalid_overhead_keyword(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"overhead": "foobar"})

    def test_ethernet_keyword(self) -> None:
        params = build_cake_params("download", {"overhead": "ethernet"})
        assert params["overhead_keyword"] == "ethernet"

    def test_no_overhead_no_keyword(self) -> None:
        params = build_cake_params("upload")
        assert "overhead_keyword" not in params
        assert "overhead" not in params


# =============================================================================
# CONFIG OVERRIDES (D-02)
# =============================================================================


class TestBuildCakeParamsConfigOverride:
    """Verify config override semantics per D-02."""

    def test_false_disables_ack_filter(self) -> None:
        params = build_cake_params("upload", {"ack_filter": False})
        assert params["ack-filter"] is False

    def test_memlimit_override(self) -> None:
        params = build_cake_params("download", {"memlimit": "64mb"})
        assert params["memlimit"] == "64mb"

    def test_rtt_override(self) -> None:
        params = build_cake_params("upload", {"rtt": "50ms"})
        assert params["rtt"] == "50ms"

    def test_underscore_to_hyphen_split_gso(self) -> None:
        params = build_cake_params("upload", {"split_gso": False})
        assert params["split-gso"] is False

    def test_false_disables_ecn_on_download(self) -> None:
        params = build_cake_params("download", {"ecn": False})
        assert params["ecn"] is False

    def test_false_disables_ingress_on_download(self) -> None:
        params = build_cake_params("download", {"ingress": False})
        assert params["ingress"] is False


# =============================================================================
# EXCLUDED PARAMS (D-08)
# =============================================================================


class TestBuildCakeParamsExcluded:
    """Verify excluded params raise ConfigValidationError."""

    def test_nat_excluded(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"nat": True})

    def test_wash_excluded(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"wash": True})

    def test_autorate_ingress_excluded(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"autorate_ingress": True})


# =============================================================================
# BANDWIDTH PARAMETER
# =============================================================================


class TestBuildCakeParamsBandwidth:
    """Verify bandwidth_kbit parameter handling."""

    def test_bandwidth_included(self) -> None:
        params = build_cake_params("upload", bandwidth_kbit=500000)
        assert params["bandwidth"] == "500000kbit"

    def test_no_bandwidth_by_default(self) -> None:
        params = build_cake_params("upload")
        assert "bandwidth" not in params

    def test_bandwidth_with_config(self) -> None:
        params = build_cake_params("upload", {"overhead": "docsis"}, bandwidth_kbit=300000)
        assert params["bandwidth"] == "300000kbit"
        assert params["overhead_keyword"] == "docsis"


# =============================================================================
# FULL SCENARIOS
# =============================================================================


class TestBuildCakeParamsFullScenarios:
    """Verify complete real-world parameter sets."""

    def test_spectrum_upload(self) -> None:
        params = build_cake_params("upload", {"overhead": "docsis"}, bandwidth_kbit=500000)
        assert params == {
            "diffserv": "diffserv4",
            "split-gso": True,
            "ack-filter": True,
            "ingress": False,
            "ecn": False,
            "memlimit": "32mb",
            "rtt": "100ms",
            "overhead_keyword": "docsis",
            "bandwidth": "500000kbit",
        }

    def test_att_download(self) -> None:
        params = build_cake_params("download", {"overhead": "bridged-ptm"}, bandwidth_kbit=300000)
        assert params == {
            "diffserv": "diffserv4",
            "split-gso": True,
            "ack-filter": False,
            "ingress": True,
            "ecn": True,
            "memlimit": "32mb",
            "rtt": "100ms",
            "overhead_keyword": "bridged-ptm",
            "bandwidth": "300000kbit",
        }


# =============================================================================
# EXPECTED READBACK BUILDER
# =============================================================================


class TestBuildExpectedReadback:
    """Verify readback conversion for validate_cake()."""

    def test_docsis_overhead_to_numeric(self) -> None:
        expected = build_expected_readback({"overhead_keyword": "docsis"})
        assert expected["overhead"] == 18

    def test_bridged_ptm_overhead_to_numeric(self) -> None:
        expected = build_expected_readback({"overhead_keyword": "bridged-ptm"})
        assert expected["overhead"] == 22

    def test_rtt_100ms_to_microseconds(self) -> None:
        expected = build_expected_readback({"rtt": "100ms"})
        assert expected["rtt"] == 100000

    def test_rtt_50ms_to_microseconds(self) -> None:
        expected = build_expected_readback({"rtt": "50ms"})
        assert expected["rtt"] == 50000

    def test_rtt_1s_to_microseconds(self) -> None:
        expected = build_expected_readback({"rtt": "1s"})
        assert expected["rtt"] == 1_000_000

    def test_memlimit_32mb_to_bytes(self) -> None:
        expected = build_expected_readback({"memlimit": "32mb"})
        assert expected["memlimit"] == 33554432

    def test_diffserv_passthrough(self) -> None:
        expected = build_expected_readback({"diffserv": "diffserv4"})
        assert expected["diffserv"] == "diffserv4"

    def test_combined_readback(self) -> None:
        params = {
            "overhead_keyword": "docsis",
            "rtt": "100ms",
            "memlimit": "32mb",
            "diffserv": "diffserv4",
        }
        expected = build_expected_readback(params)
        assert expected == {
            "overhead": 18,
            "rtt": 100000,
            "memlimit": 33554432,
            "diffserv": "diffserv4",
        }

    def test_empty_params(self) -> None:
        expected = build_expected_readback({})
        assert expected == {}

    def test_unknown_overhead_keyword_skipped(self) -> None:
        expected = build_expected_readback({"overhead_keyword": "raw"})
        assert "overhead" not in expected


# =============================================================================
# INVALID DIRECTION
# =============================================================================


class TestBuildCakeParamsInvalidDirection:
    """Verify ValueError on invalid direction."""

    def test_invalid_direction_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid direction"):
            build_cake_params("sideways")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid direction"):
            build_cake_params("")


# =============================================================================
# CONSTANT INTEGRITY
# =============================================================================


class TestCakeParamsConstants:
    """Verify module-level constants are correct."""

    def test_excluded_params_complete(self) -> None:
        assert "nat" in EXCLUDED_PARAMS
        assert "wash" in EXCLUDED_PARAMS
        assert "autorate-ingress" in EXCLUDED_PARAMS

    def test_valid_overhead_keywords_include_docsis(self) -> None:
        assert "docsis" in VALID_OVERHEAD_KEYWORDS
        assert "bridged-ptm" in VALID_OVERHEAD_KEYWORDS
        assert "ethernet" in VALID_OVERHEAD_KEYWORDS
        assert "pppoe-ptm" in VALID_OVERHEAD_KEYWORDS

    def test_yaml_to_tc_key_mapping(self) -> None:
        assert YAML_TO_TC_KEY["split_gso"] == "split-gso"
        assert YAML_TO_TC_KEY["ack_filter"] == "ack-filter"
        assert YAML_TO_TC_KEY["autorate_ingress"] == "autorate-ingress"

    def test_overhead_readback_docsis(self) -> None:
        assert OVERHEAD_READBACK["docsis"] == {"overhead": 18}

    def test_overhead_readback_bridged_ptm(self) -> None:
        assert OVERHEAD_READBACK["bridged-ptm"] == {"overhead": 22}

    def test_rtt_to_microseconds(self) -> None:
        assert RTT_TO_MICROSECONDS["1s"] == 1_000_000
        assert RTT_TO_MICROSECONDS["100ms"] == 100_000
        assert RTT_TO_MICROSECONDS["50ms"] == 50_000

    def test_memlimit_to_bytes(self) -> None:
        assert MEMLIMIT_TO_BYTES["32mb"] == 33_554_432
        assert MEMLIMIT_TO_BYTES["64mb"] == 67_108_864

    def test_upload_defaults_ack_filter_true(self) -> None:
        assert UPLOAD_DEFAULTS["ack-filter"] is True

    def test_download_defaults_ingress_true(self) -> None:
        assert DOWNLOAD_DEFAULTS["ingress"] is True

    def test_download_defaults_ecn_true(self) -> None:
        assert DOWNLOAD_DEFAULTS["ecn"] is True

    def test_tunable_defaults(self) -> None:
        assert TUNABLE_DEFAULTS["memlimit"] == "32mb"
        assert TUNABLE_DEFAULTS["rtt"] == "100ms"
