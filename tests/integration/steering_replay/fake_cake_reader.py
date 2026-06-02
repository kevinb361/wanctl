"""Fake CAKE reader for offline steering replay tests."""

from __future__ import annotations

import logging
from typing import Any

from wanctl.steering.cake_stats import CakeStats


class FakeCakeReader:
    """CakeStatsReader-shaped fake keyed by replay cycle."""

    def __init__(
        self,
        script: dict[int, CakeStats | None | type[Exception]] | None = None,
        default_stats: CakeStats | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.script = script or {}
        self.default_stats = default_stats or CakeStats()
        self.current_cycle = -1
        self.reads_log: list[dict[str, Any]] = []
        self.is_linux_cake = False
        self.last_tin_stats = None
        self.logger = logger or logging.getLogger(__name__)

    def set_current_cycle(self, idx: int) -> None:
        self.current_cycle = int(idx)

    def _timestamp(self) -> str:
        cycle = max(self.current_cycle, 0)
        return f"2026-06-02T00:00:{cycle % 60:02d}Z"

    def read_stats(self, queue_name: str) -> CakeStats | None:
        value = self.script.get(self.current_cycle, self.default_stats)
        result_type = "stats"
        if isinstance(value, type) and issubclass(value, Exception):
            result_type = "exception"
            self.reads_log.append(
                {
                    "cycle": self.current_cycle,
                    "queue_name": queue_name,
                    "result_type": result_type,
                    "timestamp_iso": self._timestamp(),
                }
            )
            raise value(f"scripted CAKE exception at cycle {self.current_cycle}")
        if value is None:
            result_type = "none"
        self.reads_log.append(
            {
                "cycle": self.current_cycle,
                "queue_name": queue_name,
                "result_type": result_type,
                "timestamp_iso": self._timestamp(),
            }
        )
        return value

    def __getattr__(self, name: str) -> Any:
        def denied(*_args: Any, **_kwargs: Any) -> Any:
            self.logger.error(
                "FakeCakeReader: denied call to undocumented method %r at cycle %s",
                name,
                self.current_cycle,
            )
            raise RuntimeError(
                f"FakeCakeReader: no live CAKE calls allowed "
                f"(attempted: {name!r} at cycle {self.current_cycle})"
            )

        return denied
