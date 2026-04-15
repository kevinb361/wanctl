"""Tests for ReflectorScorer and ReflectorStatus in reflector_scorer module.

Covers REFL-01 through REFL-03 behaviors:
- Rolling quality scoring (success rate over count-based window)
- Deprioritization when score drops below min_score threshold
- Probe scheduling for deprioritized hosts (round-robin, interval-gated)
- Recovery after N consecutive probe successes
- Event draining for persistence (deprioritization/recovery transitions)
"""

import dataclasses
import logging
from unittest.mock import MagicMock

import pytest
import yaml

from wanctl.autorate_config import Config
from wanctl.reflector_scorer import ReflectorScorer, ReflectorStatus

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def logger():
    """Create a test logger."""
    return logging.getLogger("test_reflector_scorer")


@pytest.fixture
def hosts():
    """Standard 3-host reflector list."""
    return ["8.8.8.8", "1.1.1.1", "9.9.9.9"]


@pytest.fixture
def scorer(hosts, logger):
    """Create a default ReflectorScorer with standard hosts."""
    return ReflectorScorer(
        hosts=hosts,
        min_score=0.8,
        window_size=50,
        probe_interval_sec=30.0,
        recovery_count=3,
        logger=logger,
        wan_name="TestWAN",
    )


# =============================================================================
# TestReflectorStatus
# =============================================================================


class TestReflectorStatus:
    """Tests for ReflectorStatus frozen dataclass structure."""

    def test_frozen_dataclass(self):
        """ReflectorStatus is frozen -- assignment raises AttributeError."""
        status = ReflectorStatus(
            host="8.8.8.8",
            score=1.0,
            status="active",
            measurements=0,
            consecutive_successes=0,
        )
        with pytest.raises(AttributeError):
            status.score = 0.5  # type: ignore[misc]

    def test_slots_present(self):
        """ReflectorStatus uses __slots__ for memory efficiency."""
        assert hasattr(ReflectorStatus, "__slots__")

    def test_all_fields_present(self):
        """ReflectorStatus has exactly the 5 required fields."""
        field_names = {f.name for f in dataclasses.fields(ReflectorStatus)}
        expected = {"host", "score", "status", "measurements", "consecutive_successes"}
        assert field_names == expected


# =============================================================================
# TestReflectorScoring
# =============================================================================


class TestReflectorScoring:
    """Tests for basic scoring behavior."""

    def test_fresh_scorer_all_active(self, scorer, hosts):
        """Fresh scorer with no measurements: all hosts active."""
        active = scorer.get_active_hosts()
        assert active == hosts

    def test_fresh_scorer_score_1_0(self, scorer, hosts):
        """Fresh scorer with no measurements: all scores are 1.0."""
        statuses = scorer.get_all_statuses()
        for s in statuses:
            assert s.score == 1.0
            assert s.status == "active"
            assert s.measurements == 0

    def test_recording_successes_keeps_score_high(self, scorer):
        """Recording all successes keeps score at 1.0."""
        for _ in range(20):
            scorer.record_result("8.8.8.8", True)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].score == 1.0

    def test_recording_failures_lowers_score(self, scorer):
        """Recording failures lowers the score."""
        for _ in range(10):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].score < 1.0


# =============================================================================
# TestScoreCalculation
# =============================================================================


class TestScoreCalculation:
    """Tests for score = sum(window) / len(window)."""

    def test_known_sequence_half(self, scorer):
        """5 successes + 5 failures = 0.5 score."""
        for _ in range(5):
            scorer.record_result("8.8.8.8", True)
        for _ in range(5):
            scorer.record_result("8.8.8.8", False)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].score == pytest.approx(0.5, abs=0.01)

    def test_known_sequence_quarter(self, scorer):
        """1 success + 3 failures = 0.25 score."""
        scorer.record_result("1.1.1.1", True)
        for _ in range(3):
            scorer.record_result("1.1.1.1", False)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["1.1.1.1"].score == pytest.approx(0.25, abs=0.01)

    def test_window_rolling(self, logger):
        """Window rolls: old results fall off, recent ones drive score."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8"],
            min_score=0.5,
            window_size=10,
            logger=logger,
            wan_name="TestWAN",
        )
        # Fill window with failures
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        # Now fill with successes (pushes out failures)
        for _ in range(10):
            scorer.record_result("8.8.8.8", True)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].score == 1.0


# =============================================================================
# TestWarmup
# =============================================================================


class TestWarmup:
    """Tests for warmup guard (measurements < 10 does not trigger deprioritization)."""

    def test_no_deprioritization_during_warmup(self, logger):
        """Fewer than 10 measurements does not trigger deprioritization even with 0.0 score."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8"],
            min_score=0.8,
            window_size=50,
            logger=logger,
            wan_name="TestWAN",
        )
        # 9 failures should not deprioritize (warmup guard)
        for _ in range(9):
            scorer.record_result("8.8.8.8", False)
        assert "8.8.8.8" in scorer.get_active_hosts()

    def test_deprioritization_after_warmup(self, logger):
        """After 10+ measurements with enough failures, deprioritization triggers."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=50,
            logger=logger,
            wan_name="TestWAN",
        )
        # 2 successes + 8 failures = score 0.2 < 0.8, with 10 measurements
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(8):
            scorer.record_result("8.8.8.8", False)
        assert "8.8.8.8" not in scorer.get_active_hosts()


# =============================================================================
# TestDeprioritization
# =============================================================================


class TestDeprioritization:
    """Tests for deprioritization when score drops below threshold."""

    def test_deprioritized_when_below_threshold(self, logger):
        """Host deprioritized when score < min_score after warmup."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        # 2 successes + 10 failures = score ~0.17 < 0.8
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        active = scorer.get_active_hosts()
        assert "8.8.8.8" not in active
        assert "1.1.1.1" in active

    def test_deprioritization_logs_warning(self, logger, caplog):
        """Deprioritization produces WARNING log with host and score."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        with caplog.at_level(logging.WARNING, logger="test_reflector_scorer"):
            for _ in range(2):
                scorer.record_result("8.8.8.8", True)
            for _ in range(10):
                scorer.record_result("8.8.8.8", False)
        assert any("deprioritized" in r.message.lower() for r in caplog.records)
        assert any("8.8.8.8" in r.message for r in caplog.records)

    def test_status_shows_deprioritized(self, logger):
        """get_all_statuses shows deprioritized status for affected host."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].status == "deprioritized"
        assert statuses["1.1.1.1"].status == "active"


# =============================================================================
# TestGracefulDegradation
# =============================================================================


class TestGracefulDegradation:
    """Tests for active host list degradation as hosts are deprioritized."""

    def test_3_healthy_3_returned(self, scorer, hosts):
        """3 healthy hosts -> 3 returned."""
        assert len(scorer.get_active_hosts()) == 3

    def test_2_healthy_2_returned(self, logger):
        """2 healthy, 1 deprioritized -> 2 returned."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize one host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        active = scorer.get_active_hosts()
        assert len(active) == 2

    def test_1_healthy_1_returned(self, logger):
        """1 healthy, 2 deprioritized -> 1 returned."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        for host in ["8.8.8.8", "1.1.1.1"]:
            for _ in range(2):
                scorer.record_result(host, True)
            for _ in range(10):
                scorer.record_result(host, False)
        active = scorer.get_active_hosts()
        assert len(active) == 1
        assert "9.9.9.9" in active

    def test_0_healthy_best_scoring_returned(self, logger):
        """0 healthy -> best-scoring returned (force-use fallback)."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize all hosts with different scores
        for host in ["8.8.8.8", "1.1.1.1", "9.9.9.9"]:
            for _ in range(2):
                scorer.record_result(host, True)
            for _ in range(10):
                scorer.record_result(host, False)
        active = scorer.get_active_hosts()
        assert len(active) == 1


# =============================================================================
# TestForceBestScoring
# =============================================================================


class TestForceBestScoring:
    """Tests for force-use fallback when all hosts deprioritized."""

    def test_returns_best_scoring_host(self, logger):
        """When all deprioritized, returns the host with highest score."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        # Give 9.9.9.9 a slightly better score (3 successes vs 2 for others)
        for host in ["8.8.8.8", "1.1.1.1"]:
            for _ in range(2):
                scorer.record_result(host, True)
            for _ in range(10):
                scorer.record_result(host, False)
        for _ in range(3):
            scorer.record_result("9.9.9.9", True)
        for _ in range(10):
            scorer.record_result("9.9.9.9", False)

        active = scorer.get_active_hosts()
        assert active == ["9.9.9.9"]

    def test_logs_warning_when_all_deprioritized(self, logger, caplog):
        """Force-use fallback produces WARNING log."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        for host in ["8.8.8.8", "1.1.1.1"]:
            for _ in range(2):
                scorer.record_result(host, True)
            for _ in range(10):
                scorer.record_result(host, False)
        with caplog.at_level(logging.WARNING, logger="test_reflector_scorer"):
            scorer.get_active_hosts()
        assert any("all reflectors deprioritized" in r.message.lower() for r in caplog.records)


# =============================================================================
# TestProbeScheduling
# =============================================================================


class TestProbeScheduling:
    """Tests for maybe_probe scheduling behavior."""

    def test_no_probe_when_none_deprioritized(self, scorer):
        """No probes when all hosts are active."""
        rtt_mock = MagicMock()
        result = scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        assert result == []
        rtt_mock.ping_host.assert_not_called()

    def test_probe_fires_after_interval(self, logger):
        """Probe fires when enough time has elapsed since last probe."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=30.0,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize a host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 25.0  # success
        result = scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        assert len(result) == 1
        assert result[0][0] == "8.8.8.8"
        rtt_mock.ping_host.assert_called_once_with("8.8.8.8", count=1)

    def test_probe_does_not_fire_before_interval(self, logger):
        """Probe does not fire when interval has not elapsed."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=30.0,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize a host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 25.0
        # First probe at t=100
        scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        rtt_mock.reset_mock()

        # Second probe at t=110 (only 10s later, need 30s)
        result = scorer.maybe_probe(now=110.0, rtt_measurement=rtt_mock)
        assert result == []
        rtt_mock.ping_host.assert_not_called()

    def test_probe_round_robin(self, logger):
        """Probes cycle through deprioritized hosts via round-robin."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=10.0,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize two hosts
        for host in ["8.8.8.8", "1.1.1.1"]:
            for _ in range(2):
                scorer.record_result(host, True)
            for _ in range(10):
                scorer.record_result(host, False)

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = None  # keep them deprioritized

        # First probe
        result1 = scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        probed_host_1 = result1[0][0]

        # Second probe at t=200 (well past interval)
        result2 = scorer.maybe_probe(now=200.0, rtt_measurement=rtt_mock)
        probed_host_2 = result2[0][0]

        # They should be different hosts (round-robin)
        assert probed_host_1 != probed_host_2

    def test_probe_one_host_at_a_time(self, logger):
        """Probes only one deprioritized host per call."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=10.0,
            logger=logger,
            wan_name="TestWAN",
        )
        for host in ["8.8.8.8", "1.1.1.1"]:
            for _ in range(2):
                scorer.record_result(host, True)
            for _ in range(10):
                scorer.record_result(host, False)

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = None
        result = scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        assert len(result) == 1


# =============================================================================
# TestRecovery
# =============================================================================


class TestRecovery:
    """Tests for recovery after N consecutive successful probes."""

    def test_recovery_after_consecutive_successes(self, logger):
        """Host recovers to active after recovery_count consecutive successes."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        assert "8.8.8.8" not in scorer.get_active_hosts()

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 20.0  # success

        # 3 consecutive successful probes
        for i in range(3):
            scorer.maybe_probe(now=100.0 + (i * 10.0), rtt_measurement=rtt_mock)

        # Host should be recovered
        assert "8.8.8.8" in scorer.get_active_hosts()

    def test_recovery_logs_info(self, logger, caplog):
        """Recovery produces INFO log."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 20.0
        with caplog.at_level(logging.INFO, logger="test_reflector_scorer"):
            for i in range(3):
                scorer.maybe_probe(now=100.0 + (i * 10.0), rtt_measurement=rtt_mock)
        assert any("recovered" in r.message.lower() for r in caplog.records)

    def test_recovery_resets_window_to_avoid_immediate_reflap(self, logger):
        """Recovered host stays active until it accumulates fresh post-recovery samples."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        assert "8.8.8.8" not in scorer.get_active_hosts()

        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 20.0
        for i in range(3):
            scorer.maybe_probe(now=100.0 + (i * 10.0), rtt_measurement=rtt_mock)

        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].status == "active"
        assert statuses["8.8.8.8"].measurements == 3
        assert statuses["8.8.8.8"].score == 1.0

        # A few fresh failures should not immediately push the reflector back
        # out because the warmup guard now applies to the re-qualified window.
        for _ in range(6):
            scorer.record_result("8.8.8.8", False)

        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].status == "active"
        assert statuses["8.8.8.8"].measurements == 9


# =============================================================================
# TestRecoveryReset
# =============================================================================


class TestRecoveryReset:
    """Tests for consecutive_successes reset on probe failure."""

    def test_failure_resets_consecutive_successes(self, logger):
        """Failed probe resets consecutive_successes counter to 0."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        rtt_mock = MagicMock()

        # 2 successes
        rtt_mock.ping_host.return_value = 20.0
        scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        scorer.maybe_probe(now=200.0, rtt_measurement=rtt_mock)

        # 1 failure
        rtt_mock.ping_host.return_value = None
        scorer.maybe_probe(now=300.0, rtt_measurement=rtt_mock)

        # Check consecutive_successes is 0
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].consecutive_successes == 0
        assert statuses["8.8.8.8"].status == "deprioritized"

    def test_need_full_recovery_count_after_reset(self, logger):
        """After reset, need full recovery_count consecutive successes again."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        rtt_mock = MagicMock()

        # 2 successes then failure -> reset
        rtt_mock.ping_host.return_value = 20.0
        scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        scorer.maybe_probe(now=200.0, rtt_measurement=rtt_mock)
        rtt_mock.ping_host.return_value = None
        scorer.maybe_probe(now=300.0, rtt_measurement=rtt_mock)

        # Only 2 more successes -> not recovered yet
        rtt_mock.ping_host.return_value = 20.0
        scorer.maybe_probe(now=400.0, rtt_measurement=rtt_mock)
        scorer.maybe_probe(now=500.0, rtt_measurement=rtt_mock)
        assert "8.8.8.8" not in scorer.get_active_hosts()

        # Third success -> recovered
        scorer.maybe_probe(now=600.0, rtt_measurement=rtt_mock)
        assert "8.8.8.8" in scorer.get_active_hosts()


# =============================================================================
# TestDrainEvents
# =============================================================================


class TestDrainEvents:
    """Tests for drain_events() event buffering."""

    def test_deprioritization_appends_event(self, logger):
        """Deprioritization appends event dict with event_type, host, score."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        events = scorer.drain_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "deprioritized"
        assert events[0]["host"] == "8.8.8.8"
        assert "score" in events[0]
        assert 0.0 <= events[0]["score"] <= 1.0

    def test_recovery_appends_event(self, logger):
        """Recovery appends event dict with event_type 'recovered'."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=3,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize and drain
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)
        scorer.drain_events()  # Clear deprioritization event

        # Recover
        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 20.0
        for i in range(3):
            scorer.maybe_probe(now=100.0 + (i * 10.0), rtt_measurement=rtt_mock)

        events = scorer.drain_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "recovered"
        assert events[0]["host"] == "8.8.8.8"

    def test_drain_returns_and_clears(self, logger):
        """drain_events returns events and clears the pending list."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        first = scorer.drain_events()
        assert len(first) == 1

        second = scorer.drain_events()
        assert len(second) == 0

    def test_no_events_without_transitions(self, scorer):
        """No events generated when no transitions occur."""
        for _ in range(5):
            scorer.record_result("8.8.8.8", True)
        events = scorer.drain_events()
        assert events == []


class TestRecordResults:
    """Tests for batched record_results()."""

    def test_record_results_matches_single_recording_behavior(self, logger):
        """Batch recording should match single-result recording for one-cycle inputs."""
        batch = {"8.8.8.8": True, "1.1.1.1": False}
        scorer_single = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        scorer_batch = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )

        for host, success in batch.items():
            scorer_single.record_result(host, success)

        scorer_batch.record_results(batch)

        statuses_single = {s.host: s for s in scorer_single.get_all_statuses()}
        statuses_batch = {s.host: s for s in scorer_batch.get_all_statuses()}
        assert statuses_batch["8.8.8.8"].score == statuses_single["8.8.8.8"].score
        assert statuses_batch["1.1.1.1"].score == statuses_single["1.1.1.1"].score
        assert statuses_batch["8.8.8.8"].measurements == statuses_single["8.8.8.8"].measurements
        assert statuses_batch["1.1.1.1"].measurements == statuses_single["1.1.1.1"].measurements


# =============================================================================
# TestGetBestHost
# =============================================================================


class TestGetBestHost:
    """Tests for get_best_host()."""

    def test_no_measurements_returns_first(self, scorer, hosts):
        """No measurements: returns first host."""
        assert scorer.get_best_host() == hosts[0]

    def test_returns_highest_scoring(self, logger):
        """Returns host with highest score."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1", "9.9.9.9"],
            min_score=0.5,
            window_size=20,
            logger=logger,
            wan_name="TestWAN",
        )
        # Give 1.1.1.1 best score (all successes)
        for _ in range(10):
            scorer.record_result("1.1.1.1", True)
        # Give 8.8.8.8 mixed score
        for _ in range(5):
            scorer.record_result("8.8.8.8", True)
        for _ in range(5):
            scorer.record_result("8.8.8.8", False)
        # Give 9.9.9.9 worst score
        for _ in range(2):
            scorer.record_result("9.9.9.9", True)
        for _ in range(8):
            scorer.record_result("9.9.9.9", False)

        assert scorer.get_best_host() == "1.1.1.1"


# =============================================================================
# TestGetAllStatuses
# =============================================================================


class TestGetAllStatuses:
    """Tests for get_all_statuses()."""

    def test_returns_all_hosts(self, scorer, hosts):
        """Returns status for every host."""
        statuses = scorer.get_all_statuses()
        assert len(statuses) == len(hosts)
        status_hosts = [s.host for s in statuses]
        for h in hosts:
            assert h in status_hosts

    def test_measurements_count(self, scorer):
        """measurements field reflects actual deque length."""
        for _ in range(15):
            scorer.record_result("8.8.8.8", True)
        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].measurements == 15
        assert statuses["1.1.1.1"].measurements == 0

    def test_consecutive_successes_tracked(self, logger):
        """consecutive_successes field reflects recovery counter for deprioritized hosts."""
        scorer = ReflectorScorer(
            hosts=["8.8.8.8", "1.1.1.1"],
            min_score=0.8,
            window_size=20,
            probe_interval_sec=1.0,
            recovery_count=5,
            logger=logger,
            wan_name="TestWAN",
        )
        # Deprioritize host
        for _ in range(2):
            scorer.record_result("8.8.8.8", True)
        for _ in range(10):
            scorer.record_result("8.8.8.8", False)

        # Record 2 consecutive successes via probe
        rtt_mock = MagicMock()
        rtt_mock.ping_host.return_value = 20.0
        scorer.maybe_probe(now=100.0, rtt_measurement=rtt_mock)
        scorer.maybe_probe(now=200.0, rtt_measurement=rtt_mock)

        statuses = {s.host: s for s in scorer.get_all_statuses()}
        assert statuses["8.8.8.8"].consecutive_successes == 2


# =============================================================================
# MERGED FROM test_reflector_quality_config.py
# =============================================================================


# =============================================================================
# HELPERS
# =============================================================================


def _make_minimal_config_yaml(reflector_quality=None):
    """Create a minimal valid YAML config dict for Config instantiation.

    Includes only the required sections for Config to load without errors.
    The reflector_quality key is set to the provided value if not None.
    """
    config = {
        "wan_name": "test",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25.0,
            "ping_hosts": ["1.1.1.1"],
            "download": {
                "floor_mbps": 400,
                "ceiling_mbps": 920,
                "step_up_mbps": 10,
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
            "thresholds": {
                "target_bloat_ms": 15,
                "warn_bloat_ms": 45,
                "baseline_time_constant_sec": 60,
                "load_time_constant_sec": 0.5,
            },
        },
        "logging": {
            "main_log": "/tmp/test_autorate.log",
            "debug_log": "/tmp/test_autorate_debug.log",
        },
        "lock_file": "/tmp/test_autorate.lock",
        "lock_timeout": 300,
    }
    if reflector_quality is not None:
        config["reflector_quality"] = reflector_quality
    return config


def _load_config_with(reflector_quality=None, tmp_path=None):
    """Create a Config object from a minimal YAML with the given reflector_quality."""
    config_dict = _make_minimal_config_yaml(reflector_quality)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_dict))
    return Config(str(config_path))


# =============================================================================
# TestReflectorQualityConfigDefaults
# =============================================================================


class TestReflectorQualityConfigDefaults:
    """Test that missing reflector_quality section uses all defaults."""

    def test_missing_section_defaults(self, tmp_path):
        """Missing reflector_quality section sets all defaults."""
        config = _load_config_with(reflector_quality=None, tmp_path=tmp_path)
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
        assert rq["window_size"] == 50
        assert rq["probe_interval_sec"] == 30.0
        assert rq["recovery_count"] == 3

    def test_empty_dict_defaults(self, tmp_path):
        """Empty reflector_quality dict uses all defaults."""
        config = _load_config_with(reflector_quality={}, tmp_path=tmp_path)
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
        assert rq["window_size"] == 50
        assert rq["probe_interval_sec"] == 30.0
        assert rq["recovery_count"] == 3


# =============================================================================
# TestReflectorQualityConfigValid
# =============================================================================


class TestReflectorQualityConfigValid:
    """Test that valid config passes through correctly."""

    def test_valid_config(self, tmp_path):
        """Valid reflector_quality values pass through."""
        config = _load_config_with(
            reflector_quality={
                "min_score": 0.7,
                "window_size": 100,
                "probe_interval_sec": 60,
                "recovery_count": 5,
            },
            tmp_path=tmp_path,
        )
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.7
        assert rq["window_size"] == 100
        assert rq["probe_interval_sec"] == 60.0
        assert rq["recovery_count"] == 5


# =============================================================================
# TestReflectorQualityConfigInvalidMinScore
# =============================================================================


class TestReflectorQualityConfigInvalidMinScore:
    """Test min_score validation: bool, string, out-of-range -> warns, defaults to 0.8."""

    def test_bool_min_score(self, tmp_path, caplog):
        """Bool min_score warns and defaults to 0.8."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"min_score": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["min_score"] == 0.8
        assert any("min_score" in r.message for r in caplog.records if r.levelno >= logging.WARNING)

    def test_string_min_score(self, tmp_path, caplog):
        """String min_score warns and defaults to 0.8."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"min_score": "high"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["min_score"] == 0.8

    def test_min_score_clamped_to_range(self, tmp_path):
        """min_score > 1.0 clamped to 1.0, < 0.0 clamped to 0.0."""
        config = _load_config_with(
            reflector_quality={"min_score": 1.5},
            tmp_path=tmp_path,
        )
        assert config.reflector_quality_config["min_score"] == 1.0

        config2 = _load_config_with(
            reflector_quality={"min_score": -0.5},
            tmp_path=tmp_path,
        )
        assert config2.reflector_quality_config["min_score"] == 0.0


# =============================================================================
# TestReflectorQualityConfigInvalidWindowSize
# =============================================================================


class TestReflectorQualityConfigInvalidWindowSize:
    """Test window_size validation: bool, string, < 10 -> warns, defaults to 50."""

    def test_bool_window_size(self, tmp_path, caplog):
        """Bool window_size warns and defaults to 50."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"window_size": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["window_size"] == 50

    def test_string_window_size(self, tmp_path, caplog):
        """String window_size warns and defaults to 50."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"window_size": "big"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["window_size"] == 50

    def test_too_small_window_size(self, tmp_path, caplog):
        """window_size < 10 warns and defaults to 50."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"window_size": 5},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["window_size"] == 50


# =============================================================================
# TestReflectorQualityConfigInvalidProbeInterval
# =============================================================================


class TestReflectorQualityConfigInvalidProbeInterval:
    """Test probe_interval_sec validation: bool, string, < 1 -> warns, defaults to 30."""

    def test_bool_probe_interval(self, tmp_path, caplog):
        """Bool probe_interval_sec warns and defaults to 30."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"probe_interval_sec": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["probe_interval_sec"] == 30.0

    def test_string_probe_interval(self, tmp_path, caplog):
        """String probe_interval_sec warns and defaults to 30."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"probe_interval_sec": "fast"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["probe_interval_sec"] == 30.0

    def test_too_small_probe_interval(self, tmp_path, caplog):
        """probe_interval_sec < 1 warns and defaults to 30."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"probe_interval_sec": 0.5},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["probe_interval_sec"] == 30.0


# =============================================================================
# TestReflectorQualityConfigInvalidRecoveryCount
# =============================================================================


class TestReflectorQualityConfigInvalidRecoveryCount:
    """Test recovery_count validation: bool, string, < 1 -> warns, defaults to 3."""

    def test_bool_recovery_count(self, tmp_path, caplog):
        """Bool recovery_count warns and defaults to 3."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"recovery_count": True},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["recovery_count"] == 3

    def test_string_recovery_count(self, tmp_path, caplog):
        """String recovery_count warns and defaults to 3."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"recovery_count": "many"},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["recovery_count"] == 3

    def test_too_small_recovery_count(self, tmp_path, caplog):
        """recovery_count < 1 warns and defaults to 3."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality={"recovery_count": 0},
                tmp_path=tmp_path,
            )
        assert config.reflector_quality_config["recovery_count"] == 3


# =============================================================================
# TestReflectorQualityConfigNonDict
# =============================================================================


class TestReflectorQualityConfigNonDict:
    """Test non-dict reflector_quality section warns and uses defaults."""

    def test_non_dict_section(self, tmp_path, caplog):
        """Non-dict reflector_quality (e.g., string) warns and uses all defaults."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality="invalid",
                tmp_path=tmp_path,
            )
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
        assert rq["window_size"] == 50
        assert rq["probe_interval_sec"] == 30.0
        assert rq["recovery_count"] == 3
        assert any("reflector_quality" in r.message and "dict" in r.message for r in caplog.records)

    def test_list_section(self, tmp_path, caplog):
        """List reflector_quality warns and uses all defaults."""
        with caplog.at_level(logging.WARNING):
            config = _load_config_with(
                reflector_quality=[1, 2, 3],
                tmp_path=tmp_path,
            )
        rq = config.reflector_quality_config
        assert rq["min_score"] == 0.8
