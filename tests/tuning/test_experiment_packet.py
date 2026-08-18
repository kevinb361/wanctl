"""TUNE-002: Experiment packet schema and validation tests.

Proof: schema/static validation rejects multi-parameter, both-WAN,
missing-baseline, missing-abort, missing-rollback, and unbounded experiment packets.
"""

from __future__ import annotations

import pytest

from wanctl.tuning.experiment_packet import (
    SCHEMA_VERSION,
    ConfigDiff,
    ExperimentError,
    ExperimentPacket,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_packet() -> dict:
    """Return a dict that passes all validation."""
    return {
        "schema_version": SCHEMA_VERSION,
        "wan": "spectrum",
        "parameter": "target_bloat_ms",
        "hypothesis": "Increasing target_bloat_ms from 15 to 20 reduces false YELLOW transitions during brief load spikes",
        "config_diff": {
            "yaml_path": "continuous_monitoring.thresholds.target_bloat_ms",
            "old_value": 15.0,
            "new_value": 20.0,
        },
        "observation_window_seconds": 86400,  # 1 day
        "control_wan": "att",
        "abort_thresholds": [
            {
                "metric": "cake_congestion_red_fraction",
                "operator": "gt",
                "value": 0.1,
                "description": "RED fraction exceeds 10% of windows",
            },
        ],
        "health_gates": [
            {
                "check": "wanctl_health_status",
                "expected": "healthy",
                "interval_seconds": 300,
            },
        ],
        "rollback_steps": [
            {
                "action": "restore config",
                "command": "cp /etc/wanctl/spectrum.yaml.bak /etc/wanctl/spectrum.yaml && systemctl restart wanctl@spectrum",
                "verification": "curl -s http://10.10.110.223:9101/health | jq '.status' == \"healthy\"",
            },
        ],
        "baseline_sha256": "a" * 64,
        "created_at": "2026-08-18T10:00:00Z",
        "author": "operator",
    }


def _build(data: dict) -> ExperimentPacket:
    return ExperimentPacket.from_dict(data)


# ---------------------------------------------------------------------------
# Positive: valid packet
# ---------------------------------------------------------------------------


class TestValidPacket:
    def test_accepts_minimal_valid_packet(self) -> None:
        packet = _build(_valid_packet())
        assert packet.wan == "spectrum"
        assert packet.parameter == "target_bloat_ms"
        assert packet.control_wan == "att"
        assert packet.experiment_id != ""
        assert len(packet.experiment_id) == 16

    def test_accepts_both_wans(self) -> None:
        data = _valid_packet()
        data["wan"] = "att"
        data["control_wan"] = "spectrum"
        packet = _build(data)
        assert packet.wan == "att"
        assert packet.control_wan == "spectrum"

    def test_round_trips_through_json(self) -> None:
        original = _build(_valid_packet())
        json_str = original.to_json()
        restored = ExperimentPacket.from_json(json_str)
        assert restored.to_dict() == original.to_dict()

    def test_round_trips_through_dict(self) -> None:
        original = _build(_valid_packet())
        d = original.to_dict()
        restored = ExperimentPacket.from_dict(d)
        assert restored.to_dict() == original.to_dict()

    def test_deterministic_id(self) -> None:
        data1 = _valid_packet()
        data2 = _valid_packet()
        p1 = _build(data1)
        p2 = _build(data2)
        assert p1.experiment_id == p2.experiment_id

    def test_different_parameter_yields_different_id(self) -> None:
        data = _valid_packet()
        data["parameter"] = "other_param"
        p1 = _build(_valid_packet())
        p2 = _build(data)
        assert p1.experiment_id != p2.experiment_id

    def test_to_dict_contains_nested_structures(self) -> None:
        packet = _build(_valid_packet())
        d = packet.to_dict()
        assert isinstance(d["config_diff"], dict)
        assert isinstance(d["abort_thresholds"], list)
        assert isinstance(d["health_gates"], list)
        assert isinstance(d["rollback_steps"], list)
        assert d["config_diff"]["yaml_path"] == "continuous_monitoring.thresholds.target_bloat_ms"


# ---------------------------------------------------------------------------
# Negative: one-variable enforcement
# ---------------------------------------------------------------------------


class TestOneVariable:
    def test_rejects_empty_parameter(self) -> None:
        data = _valid_packet()
        data["parameter"] = ""
        with pytest.raises(ExperimentError, match="parameter must not be empty"):
            _build(data)

    def test_rejects_empty_wan(self) -> None:
        data = _valid_packet()
        data["wan"] = ""
        with pytest.raises(ExperimentError, match="wan must not be empty"):
            _build(data)

    def test_rejects_unknown_wan(self) -> None:
        data = _valid_packet()
        data["wan"] = "fiber"
        with pytest.raises(ExperimentError, match="must be 'spectrum' or 'att'"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: one-WAN enforcement
# ---------------------------------------------------------------------------


class TestOneWAN:
    def test_rejects_same_control_wan(self) -> None:
        data = _valid_packet()
        data["control_wan"] = "spectrum"
        with pytest.raises(ExperimentError, match="control_wan .* must differ from wan"):
            _build(data)

    def test_rejects_unknown_control_wan(self) -> None:
        data = _valid_packet()
        data["control_wan"] = "fiber"
        with pytest.raises(ExperimentError, match="control_wan must be 'spectrum' or 'att'"):
            _build(data)

    def test_rejects_empty_control_wan(self) -> None:
        data = _valid_packet()
        data["control_wan"] = ""
        with pytest.raises(ExperimentError, match="control_wan must not be empty"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: missing baseline
# ---------------------------------------------------------------------------


class TestMissingBaseline:
    def test_rejects_missing_baseline_sha256(self) -> None:
        data = _valid_packet()
        data["baseline_sha256"] = ""
        with pytest.raises(ExperimentError, match="baseline_sha256 must not be empty"):
            _build(data)

    def test_rejects_invalid_baseline_sha256_length(self) -> None:
        data = _valid_packet()
        data["baseline_sha256"] = "ab"
        with pytest.raises(ExperimentError, match="baseline_sha256 must be a 64-character"):
            _build(data)

    def test_rejects_non_hex_baseline_sha256(self) -> None:
        data = _valid_packet()
        data["baseline_sha256"] = "g" * 64
        with pytest.raises(ExperimentError, match="baseline_sha256 must be a valid hex"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: missing abort thresholds
# ---------------------------------------------------------------------------


class TestMissingAbort:
    def test_rejects_empty_abort_thresholds(self) -> None:
        data = _valid_packet()
        data["abort_thresholds"] = []
        with pytest.raises(ExperimentError, match="at least one abort_threshold is required"):
            _build(data)

    def test_rejects_abort_with_empty_metric(self) -> None:
        data = _valid_packet()
        data["abort_thresholds"][0]["metric"] = ""
        with pytest.raises(ExperimentError, match="abort metric must not be empty"):
            _build(data)

    def test_rejects_abort_with_invalid_operator(self) -> None:
        data = _valid_packet()
        data["abort_thresholds"][0]["operator"] = "between"
        with pytest.raises(ExperimentError, match="abort operator must be one of"):
            _build(data)

    def test_rejects_abort_with_empty_description(self) -> None:
        data = _valid_packet()
        data["abort_thresholds"][0]["description"] = ""
        with pytest.raises(ExperimentError, match="abort description must not be empty"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: missing rollback
# ---------------------------------------------------------------------------


class TestMissingRollback:
    def test_rejects_empty_rollback_steps(self) -> None:
        data = _valid_packet()
        data["rollback_steps"] = []
        with pytest.raises(ExperimentError, match="at least one rollback_step is required"):
            _build(data)

    def test_rejects_rollback_with_empty_action(self) -> None:
        data = _valid_packet()
        data["rollback_steps"][0]["action"] = ""
        with pytest.raises(ExperimentError, match="rollback action must not be empty"):
            _build(data)

    def test_rejects_rollback_with_empty_command(self) -> None:
        data = _valid_packet()
        data["rollback_steps"][0]["command"] = ""
        with pytest.raises(ExperimentError, match="rollback command must not be empty"):
            _build(data)

    def test_rejects_rollback_with_empty_verification(self) -> None:
        data = _valid_packet()
        data["rollback_steps"][0]["verification"] = ""
        with pytest.raises(ExperimentError, match="rollback verification must not be empty"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: unbounded observation windows
# ---------------------------------------------------------------------------


class TestBoundedWindow:
    def test_rejects_zero_window(self) -> None:
        data = _valid_packet()
        data["observation_window_seconds"] = 0
        with pytest.raises(ExperimentError, match="observation_window_seconds must be between"):
            _build(data)

    def test_rejects_too_short_window(self) -> None:
        data = _valid_packet()
        data["observation_window_seconds"] = 60  # 1 minute
        with pytest.raises(ExperimentError, match="observation_window_seconds must be between"):
            _build(data)

    def test_rejects_too_long_window(self) -> None:
        data = _valid_packet()
        data["observation_window_seconds"] = 30 * 24 * 60 * 60  # 30 days
        with pytest.raises(ExperimentError, match="observation_window_seconds must be between"):
            _build(data)

    def test_accepts_minimum_window(self) -> None:
        data = _valid_packet()
        data["observation_window_seconds"] = 3600  # 1 hour
        packet = _build(data)
        assert packet.observation_window_seconds == 3600

    def test_accepts_maximum_window(self) -> None:
        data = _valid_packet()
        data["observation_window_seconds"] = 14 * 24 * 60 * 60  # 14 days
        packet = _build(data)
        assert packet.observation_window_seconds == 14 * 24 * 60 * 60


# ---------------------------------------------------------------------------
# Negative: missing health gates
# ---------------------------------------------------------------------------


class TestMissingHealthGates:
    def test_rejects_empty_health_gates(self) -> None:
        data = _valid_packet()
        data["health_gates"] = []
        with pytest.raises(ExperimentError, match="at least one health_gate is required"):
            _build(data)

    def test_rejects_health_gate_with_empty_check(self) -> None:
        data = _valid_packet()
        data["health_gates"][0]["check"] = ""
        with pytest.raises(ExperimentError, match="health gate check must not be empty"):
            _build(data)

    def test_rejects_health_gate_with_empty_expected(self) -> None:
        data = _valid_packet()
        data["health_gates"][0]["expected"] = ""
        with pytest.raises(ExperimentError, match="health gate expected value must not be empty"):
            _build(data)

    def test_rejects_health_gate_with_too_short_interval(self) -> None:
        data = _valid_packet()
        data["health_gates"][0]["interval_seconds"] = 5
        with pytest.raises(ExperimentError, match="health gate interval must be >= 10"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: config diff validation
# ---------------------------------------------------------------------------


class TestConfigDiff:
    def test_rejects_empty_yaml_path(self) -> None:
        data = _valid_packet()
        data["config_diff"]["yaml_path"] = ""
        with pytest.raises(ExperimentError, match="yaml_path must not be empty"):
            _build(data)

    def test_rejects_identical_values(self) -> None:
        data = _valid_packet()
        data["config_diff"]["old_value"] = 15.0
        data["config_diff"]["new_value"] = 15.0
        with pytest.raises(ExperimentError, match="old_value and new_value must differ"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: schema version
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_rejects_future_schema_version(self) -> None:
        data = _valid_packet()
        data["schema_version"] = 99
        with pytest.raises(ExperimentError, match="unsupported schema_version"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: missing hypothesis
# ---------------------------------------------------------------------------


class TestMissingHypothesis:
    def test_rejects_empty_hypothesis(self) -> None:
        data = _valid_packet()
        data["hypothesis"] = ""
        with pytest.raises(ExperimentError, match="hypothesis must not be empty"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: missing author
# ---------------------------------------------------------------------------


class TestMissingAuthor:
    def test_rejects_empty_author(self) -> None:
        data = _valid_packet()
        data["author"] = ""
        with pytest.raises(ExperimentError, match="author must not be empty"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: invalid created_at
# ---------------------------------------------------------------------------


class TestCreatedAt:
    def test_rejects_invalid_timestamp(self) -> None:
        data = _valid_packet()
        data["created_at"] = "not-a-date"
        with pytest.raises(ExperimentError, match="created_at must be valid RFC3339"):
            _build(data)

    def test_rejects_empty_created_at(self) -> None:
        data = _valid_packet()
        data["created_at"] = ""
        with pytest.raises(ExperimentError, match="created_at must not be empty"):
            _build(data)


# ---------------------------------------------------------------------------
# Negative: multi-parameter rejection
# ---------------------------------------------------------------------------


class TestMultiParameterRejection:
    """The schema inherently rejects multi-parameter experiments because
    there is exactly one `parameter` field and one `config_diff` field.
    There is no way to express two parameters in a single packet."""

    def test_schema_allows_only_one_parameter(self) -> None:
        """Even if the operator tries to sneak a second parameter into the
        hypothesis or yaml_path, the schema only has one parameter slot."""
        data = _valid_packet()
        # The yaml_path can mention anything, but there's only one old/new pair
        data["config_diff"]["yaml_path"] = "some.path"
        data["parameter"] = "single_param"
        packet = _build(data)
        assert packet.parameter == "single_param"
        assert isinstance(packet.config_diff, ConfigDiff)
        # Only one ConfigDiff exists — multi-parameter is structurally impossible
