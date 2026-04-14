"""Pure regression coverage for history_state classifier + HISTORY_COPY.

Traces to Phase 183 contract
(.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md)
sections L1, L2, F1, F2, F3 (D-12) and Acceptance Criteria 1, 7, 8, 9, 10.
Phase 185 Plan 01 — DASH-04.
"""

from wanctl.dashboard.widgets.history_state import (
    HISTORY_COPY,
    KNOWN_SOURCE_MODES,
    HistoryState,
    classify_history_state,
)


class TestClassifyHistoryStateSuccess:
    def test_classify_history_state_success_returns_success(self) -> None:
        payload = {
            "data": [],
            "metadata": {
                "source": {
                    "mode": "local_configured_db",
                    "db_paths": ["/var/lib/wanctl/metrics-att.db"],
                }
            },
        }

        assert classify_history_state(payload) is HistoryState.SUCCESS

    def test_classify_history_state_success_merged_discovery(self) -> None:
        payload = {
            "data": [],
            "metadata": {
                "source": {
                    "mode": "merged_discovery",
                    "db_paths": ["/a.db", "/b.db"],
                }
            },
        }

        assert classify_history_state(payload) is HistoryState.SUCCESS
        assert payload["metadata"]["source"]["mode"] in KNOWN_SOURCE_MODES


class TestClassifyHistoryStateFailure:
    def test_classify_history_state_fetch_error_for_exception(self) -> None:
        assert classify_history_state(RuntimeError("boom")) is HistoryState.FETCH_ERROR

    def test_classify_history_state_fetch_error_for_httpx_timeout(self) -> None:
        assert classify_history_state(Exception("timeout")) is HistoryState.FETCH_ERROR

    def test_classify_precedence_fetch_error_beats_source_missing(self) -> None:
        assert classify_history_state(Exception()) is HistoryState.FETCH_ERROR


class TestClassifyHistoryStateAmbiguous:
    def test_classify_history_state_source_missing_when_payload_not_dict(self) -> None:
        assert classify_history_state("not a dict") is HistoryState.SOURCE_MISSING

    def test_classify_history_state_source_missing_when_metadata_not_dict(self) -> None:
        payload = {"metadata": "nope"}

        assert classify_history_state(payload) is HistoryState.SOURCE_MISSING

    def test_classify_history_state_source_missing_when_source_absent(self) -> None:
        payload = {"metadata": {}}

        assert classify_history_state(payload) is HistoryState.SOURCE_MISSING

    def test_classify_history_state_source_missing_when_source_not_dict(self) -> None:
        payload = {"metadata": {"source": "local_configured_db"}}

        assert classify_history_state(payload) is HistoryState.SOURCE_MISSING

    def test_classify_history_state_mode_missing_when_mode_absent(self) -> None:
        payload = {"metadata": {"source": {"db_paths": ["/a.db"]}}}

        assert classify_history_state(payload) is HistoryState.MODE_MISSING

    def test_classify_history_state_mode_missing_when_mode_unknown(self) -> None:
        payload = {
            "metadata": {"source": {"mode": "frankenmode", "db_paths": ["/a.db"]}}
        }

        assert classify_history_state(payload) is HistoryState.MODE_MISSING

    def test_classify_history_state_mode_missing_when_mode_not_string(self) -> None:
        payload = {"metadata": {"source": {"mode": 42, "db_paths": ["/a.db"]}}}

        assert classify_history_state(payload) is HistoryState.MODE_MISSING

    def test_classify_history_state_db_paths_missing_when_absent(self) -> None:
        payload = {"metadata": {"source": {"mode": "local_configured_db"}}}

        assert classify_history_state(payload) is HistoryState.DB_PATHS_MISSING

    def test_classify_history_state_db_paths_missing_when_empty_list(self) -> None:
        payload = {
            "metadata": {"source": {"mode": "local_configured_db", "db_paths": []}}
        }

        assert classify_history_state(payload) is HistoryState.DB_PATHS_MISSING

    def test_classify_history_state_db_paths_missing_when_not_list(self) -> None:
        payload = {
            "metadata": {
                "source": {"mode": "local_configured_db", "db_paths": "/a.db"}
            }
        }

        assert classify_history_state(payload) is HistoryState.DB_PATHS_MISSING


class TestHistoryCopyContract:
    def test_history_copy_handoff_mentions_python3_m_wanctl_history_verbatim(
        self,
    ) -> None:
        assert "python3 -m wanctl.history" in HISTORY_COPY.HANDOFF
        assert (
            HISTORY_COPY.HANDOFF
            == "For merged cross-WAN proof, run: python3 -m wanctl.history"
        )

    def test_history_copy_banner_success_is_endpoint_local(self) -> None:
        banner = HISTORY_COPY.BANNER_SUCCESS.lower()

        assert "endpoint-local" in banner
        assert "connected autorate daemon" in banner

    def test_history_copy_details_reference_merged_cli(self) -> None:
        assert "python3 -m wanctl.history" in HISTORY_COPY.DETAIL_FETCH_ERROR
        assert "python3 -m wanctl.history" in HISTORY_COPY.DETAIL_AMBIGUOUS

    def test_history_copy_no_parity_language_in_banners(self) -> None:
        banners = (
            HISTORY_COPY.BANNER_SUCCESS,
            HISTORY_COPY.BANNER_FETCH_ERROR,
            HISTORY_COPY.BANNER_SOURCE_MISSING,
            HISTORY_COPY.BANNER_MODE_MISSING,
            HISTORY_COPY.BANNER_DB_PATHS_MISSING,
        )

        for banner in banners:
            lowered = banner.lower()
            assert "authoritative" not in lowered
            assert "wanctl-history" not in lowered
            assert "cross-wan history" not in lowered
