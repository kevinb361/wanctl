"""Tests for BackgroundCakeStatsThread shared-dump behavior."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from wanctl.cake_stats_thread import BackgroundCakeStatsThread


def test_get_overlap_snapshot_initial_state_is_none() -> None:
    shutdown_event = threading.Event()
    thread = BackgroundCakeStatsThread(
        dl_interface="if-dl",
        ul_interface="if-ul",
        shutdown_event=shutdown_event,
        cadence_sec=0.05,
    )

    snap = thread.get_overlap_snapshot()

    assert snap.last_dump_started_monotonic is None
    assert snap.last_dump_finished_monotonic is None
    assert snap.last_dump_elapsed_ms is None


def test_background_thread_reads_both_directions_from_single_dump() -> None:
    """One netlink dump should feed both DL and UL parses in each cycle."""
    shutdown_event = threading.Event()
    thread = BackgroundCakeStatsThread(
        dl_interface="if-dl",
        ul_interface="if-ul",
        shutdown_event=shutdown_event,
        cadence_sec=0.05,
    )

    dump_messages = [object()]
    mock_ipr = MagicMock()
    mock_ipr.tc.return_value = dump_messages

    dl_backend = MagicMock()
    dl_backend._get_ipr.return_value = mock_ipr
    dl_backend._parse_cake_msg.return_value = {"direction": "download"}

    def parse_ul(msgs):
        shutdown_event.set()
        return {"direction": "upload"}

    ul_backend = MagicMock()
    ul_backend._get_ipr.return_value = MagicMock()
    ul_backend._parse_cake_msg.side_effect = parse_ul

    with patch("wanctl.backends.netlink_cake.NetlinkCakeBackend", side_effect=[dl_backend, ul_backend]):
        thread._run()

    dl_backend._get_ipr.assert_called()
    ul_backend._get_ipr.assert_called()
    mock_ipr.tc.assert_called_once_with("dump")
    dl_backend._parse_cake_msg.assert_called_once_with(dump_messages)
    ul_backend._parse_cake_msg.assert_called_once_with(dump_messages)
    assert thread.get_latest() is not None
    assert thread.get_latest().dl_stats == {"direction": "download"}
    assert thread.get_latest().ul_stats == {"direction": "upload"}


def test_overlap_snapshot_populated_after_single_dump_cycle() -> None:
    shutdown_event = threading.Event()
    thread = BackgroundCakeStatsThread(
        dl_interface="if-dl",
        ul_interface="if-ul",
        shutdown_event=shutdown_event,
        cadence_sec=0.05,
    )

    dump_messages = [object()]
    mock_ipr = MagicMock()
    mock_ipr.tc.return_value = dump_messages

    dl_backend = MagicMock()
    dl_backend._get_ipr.return_value = mock_ipr
    dl_backend._parse_cake_msg.return_value = {"direction": "download"}

    def parse_ul(msgs):
        shutdown_event.set()
        return {"direction": "upload"}

    ul_backend = MagicMock()
    ul_backend._get_ipr.return_value = MagicMock()
    ul_backend._parse_cake_msg.side_effect = parse_ul

    with patch("wanctl.backends.netlink_cake.NetlinkCakeBackend", side_effect=[dl_backend, ul_backend]):
        thread._run()

    snap = thread.get_overlap_snapshot()

    assert snap.last_dump_started_monotonic is not None
    assert snap.last_dump_finished_monotonic is not None
    assert snap.last_dump_started_monotonic <= snap.last_dump_finished_monotonic
    assert snap.last_dump_elapsed_ms is not None
    assert snap.last_dump_elapsed_ms >= 0.0


def test_cadence_sec_constructor_param_is_honored() -> None:
    shutdown_event = threading.Event()
    thread = BackgroundCakeStatsThread(
        dl_interface="if-dl",
        ul_interface="if-ul",
        shutdown_event=shutdown_event,
        cadence_sec=0.25,
    )

    assert thread._cadence_sec == 0.25
