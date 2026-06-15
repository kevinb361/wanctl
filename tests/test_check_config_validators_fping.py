import yaml

from wanctl.check_config import Severity
from wanctl.check_config_validators import (
    KNOWN_AUTORATE_PATHS,
    _run_autorate_validators,
    validate_measurement_fping,
)


def _config_with_fping(fping: dict) -> dict:
    return {
        "measurement": {
            "backend": "fping",
            "fping": fping,
        }
    }


def _measurement_fping_rows(data: dict):
    return [r for r in validate_measurement_fping(data) if r.category == "Measurement Fping"]


def _errors(data: dict):
    return [r for r in _measurement_fping_rows(data) if r.severity == Severity.ERROR]


def _warnings(data: dict):
    return [r for r in _measurement_fping_rows(data) if r.severity == Severity.WARN]


def test_known_autorate_paths_include_fping_keys():
    expected = {
        "measurement.fping",
        "measurement.fping.count",
        "measurement.fping.period_ms",
        "measurement.fping.cadence_sec",
        "measurement.fping.loss_fail_threshold",
        "measurement.fping.timeout_grace_sec",
    }
    assert expected <= KNOWN_AUTORATE_PATHS


def test_valid_fping_knobs_pass():
    rows = _measurement_fping_rows(
        _config_with_fping(
            {
                "count": 5,
                "period_ms": 200,
                "cadence_sec": 10.0,
                "loss_fail_threshold": 0.0,
                "timeout_grace_sec": 2.0,
            }
        )
    )
    assert [r.severity for r in rows] == [Severity.PASS]


def test_count_zero_rejected():
    errors = _errors(_config_with_fping({"count": 0}))
    assert any(r.field == "measurement.fping.count" for r in errors)


def test_period_ms_below_fping_minimum_rejected():
    errors = _errors(_config_with_fping({"period_ms": 5}))
    assert any(r.field == "measurement.fping.period_ms" for r in errors)


def test_loss_fail_threshold_above_100_rejected():
    errors = _errors(_config_with_fping({"loss_fail_threshold": 150}))
    assert any(r.field == "measurement.fping.loss_fail_threshold" for r in errors)


def test_absent_measurement_fping_block_emits_no_result():
    assert validate_measurement_fping({}) == []
    assert validate_measurement_fping({"measurement": {"backend": "icmplib"}}) == []


def test_timeout_at_or_above_cadence_warns_not_errors():
    data = _config_with_fping(
        {
            "count": 5,
            "period_ms": 200,
            "cadence_sec": 3.0,
            "timeout_grace_sec": 2.0,
        }
    )
    warnings = _warnings(data)
    errors = _errors(data)
    assert any(r.field == "measurement.fping.timeout_vs_cadence" for r in warnings)
    assert errors == []


def test_valid_fping_config_no_unknown_key_warnings():
    data = _config_with_fping(
        {
            "count": 5,
            "period_ms": 200,
            "cadence_sec": 10.0,
            "loss_fail_threshold": 0.0,
            "timeout_grace_sec": 2.0,
        }
    )
    rows = _run_autorate_validators(data)
    unknown_warnings = [
        r for r in rows if r.category == "Unknown Keys" and r.severity == Severity.WARN
    ]
    assert unknown_warnings == []


def test_existing_spectrum_config_has_no_fping_validator_rows():
    with open("configs/spectrum.yaml") as f:
        data = yaml.safe_load(f)
    assert validate_measurement_fping(data) == []
