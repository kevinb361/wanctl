"""Fixture-backed baseline and live RTT source for steering replay."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wanctl.steering.daemon import BaselineLoader


class FixtureBaselineLoader(BaselineLoader):
    """BaselineLoader subclass that reads replay-scripted values only."""

    def __init__(
        self,
        config: Any,
        logger: Any,
        spectrum_state_path: Path,
        *,
        live_rtt_by_cycle: dict[int, float | None] | None = None,
        live_irtt_rtt_by_cycle: dict[int, float | None] | None = None,
        baseline_rtt_by_cycle: dict[int, float | None] | None = None,
    ) -> None:
        super().__init__(config, logger)
        self.spectrum_state_path = Path(spectrum_state_path)
        self.live_rtt_by_cycle = live_rtt_by_cycle or {}
        self.live_irtt_rtt_by_cycle = live_irtt_rtt_by_cycle or {}
        self.baseline_rtt_by_cycle = baseline_rtt_by_cycle or {}
        self.current_cycle = -1
        self.live_rtt_calls: list[dict[str, Any]] = []
        self.live_irtt_calls: list[dict[str, Any]] = []
        self.baseline_calls: list[dict[str, Any]] = []

    def set_current_cycle(self, idx: int) -> None:
        self.current_cycle = int(idx)

    def _timestamp(self) -> str:
        cycle = max(self.current_cycle, 0)
        return f"2026-06-02T00:00:{cycle % 60:02d}Z"

    def _load_target_wan_health(self) -> dict[str, Any] | None:
        return None

    def load_baseline_rtt(self) -> tuple[float | None, str | None]:
        import json

        scripted = self.baseline_rtt_by_cycle.get(self.current_cycle)
        baseline = scripted
        wan_zone = "GREEN"
        if baseline is None:
            try:
                state = json.loads(self.spectrum_state_path.read_text())
                baseline = float(state["ewma"]["baseline_rtt"])
                wan_zone = state.get("congestion", {}).get("dl_state", "GREEN")
            except Exception:
                baseline = None
                wan_zone = None
        self.baseline_calls.append(
            {
                "cycle": self.current_cycle,
                "read_path": str(self.spectrum_state_path),
                "returned_value": baseline,
                "timestamp_iso": self._timestamp(),
            }
        )
        return baseline, wan_zone

    def load_live_rtt(self) -> float | None:
        value = self.live_rtt_by_cycle.get(self.current_cycle)
        self.live_rtt_calls.append(
            {
                "cycle": self.current_cycle,
                "read_path": f"fixture-script:cycle={self.current_cycle}",
                "returned_value": value,
                "timestamp_iso": self._timestamp(),
            }
        )
        return value

    def load_live_irtt_rtt(self) -> float | None:
        value = self.live_irtt_rtt_by_cycle.get(self.current_cycle)
        self.live_irtt_calls.append(
            {
                "cycle": self.current_cycle,
                "read_path": f"fixture-script:cycle={self.current_cycle}",
                "returned_value": value,
                "timestamp_iso": self._timestamp(),
            }
        )
        return value

    def get_wan_zone_age(self) -> float | None:
        return 0.0

    def is_wan_zone_stale(self) -> bool:
        return False
