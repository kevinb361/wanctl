"""Tests for BackgroundCakeStatsThread shared-dump behavior."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from wanctl.cake_stats_thread import BackgroundCakeStatsThread


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
    ul_backend._parse_cake_msg.side_effect = parse_ul

    with patch("wanctl.backends.netlink_cake.NetlinkCakeBackend", side_effect=[dl_backend, ul_backend]):
        thread._run()

    mock_ipr.tc.assert_called_once_with("dump")
    dl_backend._parse_cake_msg.assert_called_once_with(dump_messages)
    ul_backend._parse_cake_msg.assert_called_once_with(dump_messages)
    assert thread.get_latest() is not None
    assert thread.get_latest().dl_stats == {"direction": "download"}
    assert thread.get_latest().ul_stats == {"direction": "upload"}
