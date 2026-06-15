"""Tests for RTT backend seam contracts."""

import dataclasses
import subprocess
import sys

import pytest

from tests.helpers import make_host_result
from wanctl.irtt_measurement import IRTTResult
from wanctl.rtt_backend import (
    IrttRttBackend,
    RttBackend,
    RttSample,
    sample_from_irtt_result,
)
from wanctl.rtt_measurement import RTTSnapshot


def test_protocol_conformance():
    """Probe-bearing objects satisfy RttBackend structurally."""

    class ProbeBearing:
        def probe(self, hosts: list[str]) -> RttSample | None:
            return None

    class NoProbe:
        pass

    assert isinstance(ProbeBearing(), RttBackend)
    assert not isinstance(NoProbe(), RttBackend)


def test_rttsample_superset_fields():
    """RttSample carries every RTTSnapshot field plus backend metadata."""

    snapshot_fields = {field.name for field in dataclasses.fields(RTTSnapshot)}
    sample_fields = {field.name for field in dataclasses.fields(RttSample)}

    assert snapshot_fields < sample_fields
    assert {"backend", "source_ip", "per_host_loss"} <= sample_fields


def test_rttsample_to_snapshot_byte_identical():
    """RttSample.to_snapshot() preserves the legacy snapshot subset exactly."""

    host = make_host_result(address="198.51.100.10", rtts=[12.5])
    per_host_results = {host.address: host.rtts[0], "203.0.113.20": None}
    sample = RttSample(
        rtt_ms=12.5,
        per_host_results=per_host_results,
        timestamp=12345.0,
        measurement_ms=3.25,
        active_hosts=("198.51.100.10", "203.0.113.20"),
        successful_hosts=("198.51.100.10",),
        backend="icmplib",
        source_ip="192.0.2.50",
        per_host_loss={"198.51.100.10": 0.0, "203.0.113.20": 100.0},
    )

    snapshot = sample.to_snapshot()

    assert isinstance(snapshot, RTTSnapshot)
    assert snapshot == RTTSnapshot(
        rtt_ms=12.5,
        per_host_results=per_host_results,
        timestamp=12345.0,
        measurement_ms=3.25,
        active_hosts=("198.51.100.10", "203.0.113.20"),
        successful_hosts=("198.51.100.10",),
    )


def test_sample_from_irtt_result_mapping():
    """IRTTResult maps to RttSample using median RTT and percent loss."""

    result = IRTTResult(
        rtt_mean_ms=15.0,
        rtt_median_ms=13.5,
        ipdv_mean_ms=0.75,
        send_loss=2.0,
        receive_loss=4.5,
        packets_sent=100,
        packets_received=95,
        server="198.51.100.30",
        port=2112,
        timestamp=45678.0,
        success=True,
    )

    sample = sample_from_irtt_result(result)

    assert sample.rtt_ms == 13.5
    assert sample.per_host_results == {"198.51.100.30": 13.5}
    assert sample.timestamp == 45678.0
    assert sample.measurement_ms == 0.0
    assert sample.active_hosts == ("198.51.100.30",)
    assert sample.successful_hosts == ("198.51.100.30",)
    assert sample.backend == "irtt"
    assert sample.source_ip == "198.51.100.30"
    assert sample.per_host_loss["198.51.100.30"] == 4.5


def test_irtt_backend_unwired():
    """The live IRTT adapter stays deferred behind IRTT-MIG-01."""

    with pytest.raises(NotImplementedError, match="IRTT-MIG-01"):
        IrttRttBackend().probe(["198.51.100.30"])


def test_imports_acyclic_both_orders():
    """rtt_backend and rtt_measurement import cleanly in either order."""

    backend_first = subprocess.run(
        [sys.executable, "-c", "import wanctl.rtt_backend; import wanctl.rtt_measurement"],
        check=False,
    )
    measurement_first = subprocess.run(
        [sys.executable, "-c", "import wanctl.rtt_measurement; import wanctl.rtt_backend"],
        check=False,
    )

    assert backend_first.returncode == 0
    assert measurement_first.returncode == 0
