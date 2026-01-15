"""
WANController state persistence manager.

Handles loading and saving WANController state (hysteresis counters, EWMA values,
last applied rates) with atomic writes and error recovery. Follows the StateManager
pattern from steering/state_manager.py.
"""

import datetime
import hashlib
import json
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
        # Dirty tracking: hash of last saved state (excludes timestamp)
        self._last_saved_hash: str | None = None

    def _compute_state_hash(
        self,
        download: dict[str, Any],
        upload: dict[str, Any],
        ewma: dict[str, float],
        last_applied: dict[str, int | None],
    ) -> str:
        """Compute hash of state for dirty tracking (excludes timestamp)."""
        state_for_hash = {
            "download": download,
            "upload": upload,
            "ewma": ewma,
            "last_applied": last_applied,
        }
        serialized = json.dumps(state_for_hash, sort_keys=True)
        return hashlib.md5(serialized.encode()).hexdigest()

    def load(self) -> dict[str, Any] | None:
        """
        Load state from disk.

        Also initializes dirty tracking hash to prevent immediate rewrite.

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
            # Initialize hash from loaded state to prevent immediate rewrite
            if all(k in state for k in ["download", "upload", "ewma", "last_applied"]):
                self._last_saved_hash = self._compute_state_hash(
                    state["download"],
                    state["upload"],
                    state["ewma"],
                    state["last_applied"],
                )

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
        current_hash = self._compute_state_hash(download, upload, ewma, last_applied)

        if not force and self._last_saved_hash == current_hash:
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
        self._last_saved_hash = current_hash
        self.logger.debug(f"{self.wan_name}: Saved state to {self.state_file}")
        return True

    def build_download_state(
        self, green_streak: int, soft_red_streak: int, red_streak: int, current_rate: int
    ) -> dict[str, int]:
        """Build download state dict for save()."""
        return {
            "green_streak": green_streak,
            "soft_red_streak": soft_red_streak,
            "red_streak": red_streak,
            "current_rate": current_rate,
        }

    def build_upload_state(
        self, green_streak: int, soft_red_streak: int, red_streak: int, current_rate: int
    ) -> dict[str, int]:
        """Build upload state dict for save()."""
        return {
            "green_streak": green_streak,
            "soft_red_streak": soft_red_streak,
            "red_streak": red_streak,
            "current_rate": current_rate,
        }
