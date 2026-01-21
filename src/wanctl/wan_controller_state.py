"""
WANController state persistence manager.

Handles loading and saving WANController state (hysteresis counters, EWMA values,
last applied rates) with atomic writes and error recovery. Follows the StateManager
pattern from steering/state_manager.py.
"""

import datetime
import logging
from pathlib import Path
from typing import Any

from .state_utils import atomic_write_json, safe_json_load_file


class WANControllerState:
    """
    Manages state persistence for WANController.

    Separates persistence concerns from business logic, enabling:
    - Isolated testing of state save/load without WANController
    - Consistent atomic write behavior
    - Clear schema documentation

    State Schema:
        {
            "download": {"green_streak", "soft_red_streak", "red_streak", "current_rate"},
            "upload": {"green_streak", "soft_red_streak", "red_streak", "current_rate"},
            "ewma": {"baseline_rtt", "load_rtt"},
            "last_applied": {"dl_rate", "ul_rate"},
            "timestamp": ISO-8601 string
        }
    """

    def __init__(self, state_file: Path, logger: logging.Logger, wan_name: str):
        """
        Initialize state manager.

        Args:
            state_file: Path to state JSON file
            logger: Logger for error/debug messages
            wan_name: WAN name for log context
        """
        self.state_file = state_file
        self.logger = logger
        self.wan_name = wan_name
        # Dirty tracking: store last saved state for comparison (excludes timestamp)
        self._last_saved_state: dict[str, Any] | None = None

    def _is_state_changed(
        self,
        download: dict[str, Any],
        upload: dict[str, Any],
        ewma: dict[str, float],
        last_applied: dict[str, int | None],
    ) -> bool:
        """Check if state has changed since last save (excludes timestamp).

        Uses direct field comparison instead of MD5 hashing for better performance
        at high cycle rates (50ms/20Hz).
        """
        if self._last_saved_state is None:
            return True

        current = {
            "download": download,
            "upload": upload,
            "ewma": ewma,
            "last_applied": last_applied,
        }
        return current != self._last_saved_state

    def load(self) -> dict[str, Any] | None:
        """
        Load state from disk.

        Also initializes dirty tracking state to prevent immediate rewrite.

        Returns:
            State dictionary if found and valid, None if missing or invalid.
            Caller should use defaults when None returned.
        """
        state = safe_json_load_file(
            self.state_file,
            logger=self.logger,
            default=None,
            error_context=f"{self.wan_name} state",
        )

        if state is not None:
            self.logger.debug(f"{self.wan_name}: Loaded state from {self.state_file}")
            # Initialize last saved state to prevent immediate rewrite
            if all(k in state for k in ["download", "upload", "ewma", "last_applied"]):
                self._last_saved_state = {
                    "download": state["download"],
                    "upload": state["upload"],
                    "ewma": state["ewma"],
                    "last_applied": state["last_applied"],
                }

        return state

    def save(
        self,
        download: dict[str, Any],
        upload: dict[str, Any],
        ewma: dict[str, float],
        last_applied: dict[str, int | None],
        force: bool = False,
    ) -> bool:
        """
        Save state to disk with atomic write and dirty tracking.

        Skips write if state unchanged from last save (dirty tracking).

        Args:
            download: Download controller state (streaks, current_rate)
            upload: Upload controller state (streaks, current_rate)
            ewma: EWMA state (baseline_rtt, load_rtt)
            last_applied: Last applied rates (dl_rate, ul_rate)
            force: If True, bypass dirty check and always write

        Returns:
            True if state was written, False if skipped (unchanged)
        """
        if not force and not self._is_state_changed(download, upload, ewma, last_applied):
            self.logger.debug(f"{self.wan_name}: State unchanged, skipping disk write")
            return False

        state = {
            "download": download,
            "upload": upload,
            "ewma": ewma,
            "last_applied": last_applied,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        atomic_write_json(self.state_file, state)
        # Update last saved state for dirty tracking
        self._last_saved_state = {
            "download": download,
            "upload": upload,
            "ewma": ewma,
            "last_applied": last_applied,
        }
        self.logger.debug(f"{self.wan_name}: Saved state to {self.state_file}")
        return True

    def build_controller_state(
        self, green_streak: int, soft_red_streak: int, red_streak: int, current_rate: int
    ) -> dict[str, int]:
        """Build controller state dict for save().

        Used for both download and upload controllers since they share
        the same state structure (hysteresis counters and current rate).
        """
        return {
            "green_streak": green_streak,
            "soft_red_streak": soft_red_streak,
            "red_streak": red_streak,
            "current_rate": current_rate,
        }
