"""Phase 201 Wave 0 replay scaffolding for DOCSIS-aware UL control."""

from __future__ import annotations

import pytest

from tests.fixtures.phase201_replay_corpus import ATTEMPT3_VERDICT_PATH, load_attempt3_trace


# Phase 201 Wave 0 RED scaffolding — Plan 201-02 stubs.
# Implementation lands in Plans 201-03 (config/validator),
# 201-04 (controller core), 201-05 (telemetry / wan_controller),
# 201-07 (predeploy gate), 201-08 (canary extension).


class TestAttempt3ReplayWithDocsisMode:
    @pytest.mark.xfail(strict=True, reason="Wave 0 stub — Plan 201-04 Task 3 (REVIEWS HIGH-3)")
    def test_no_floor_hits_with_setpoint_12_cycle_fidelity(self, phase201_attempt3_trace):
        """REVIEWS HIGH-4 (2026-05-04): cycle-fidelity replay contract.

        Replays Attempt 3's load_rtt + cake samples through the DOCSIS-mode
        controller, EXPANDING each 1 Hz NDJSON sample into 20 synthetic
        50ms cycles via hold-last interpolation (load_rtt and cake fields
        held constant across the 20 cycles). This makes the integral window
        (2.0s = 40 cycles) and YELLOW dwell counters operate at the same
        cadence as production (50ms cycle interval).

        Contract: floor_hits == 0 across the expanded loaded window.
        """
        assert ATTEMPT3_VERDICT_PATH.exists()
        assert phase201_attempt3_trace, "Attempt 3 trace empty — corpus loader missing or NDJSON moved"
        raise AssertionError("Wave 0 stub — replay harness wired in Plan 201-04 Task 3")


class TestLegacyByteIdentity:
    @pytest.mark.xfail(strict=True, reason="Wave 0 stub — Plan 201-04 Task 3 (REVIEWS HIGH-3)")
    def test_no_docsis_key_byte_identical_3state(self, phase201_sustained_load_trace):
        """When `docsis_mode` key is absent from YAML, the (zone, rate)
        sequence on a synthetic trace MUST match the legacy 3-state
        controller exactly (D-17 invariant).
        """
        assert phase201_sustained_load_trace
        assert load_attempt3_trace()
        raise AssertionError("Wave 0 stub — implementation in Plan 201-04 Task 3")
