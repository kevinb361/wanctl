"""Offline fping RTT backend implementation.

This module intentionally mirrors the bounded-subprocess shape used by the
IRTT wrapper while keeping the fping backend inert until Phase 242 wires the
factory/fallback path.  The parser consumes ``fping -C`` target lines from the
combined stdout+stderr stream and preserves loss as loss -- a ``-`` token is
never converted to ``0.0``.
"""

from __future__ import annotations

import fcntl
import hashlib
import logging
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from wanctl.rtt_backend import RttSample


@dataclass(frozen=True, slots=True)
class FpingParseResult:
    """Parsed fping burst result before scorer feed / sample construction."""

    per_host_results: dict[str, float | None]
    per_host_loss: dict[str, float | None]
    successful_rtts: list[float]
    successful_hosts: list[str]
    observed_hosts: list[str]


class _ScorerLike(Protocol):
    def record_results(self, results: dict[str, bool]) -> None: ...


class FpingMeasurement:
    """Run one bounded ``fping -C`` burst and return an RTT sample."""

    def __init__(self, config: dict, logger: logging.Logger) -> None:
        self._source_ip: str | None = config.get("source_ip")
        self._count: int = int(config.get("count", 5))
        self._period_ms: int = int(config.get("period_ms", 200))
        self._loss_fail_threshold: float = float(config.get("loss_fail_threshold", 0.0))
        self._scorer: _ScorerLike | None = config.get("scorer")
        grace = float(config.get("timeout_grace_sec", 2.0))
        self._timeout: float = (self._count * self._period_ms / 1000.0) + grace
        self._binary_path: str | None = shutil.which("fping")
        self._logger = logger
        self._lock_timeout: float = min(5.0, self._timeout)
        self._lock_path: str | None = self._build_lock_path([])

        self._consecutive_failures: int = 0
        self._first_failure_logged: bool = False

        if self._binary_path is None:
            self._logger.warning("fping binary not found. Install with: sudo apt install -y fping")

    def is_available(self) -> bool:
        """Return whether fping measurements can be performed."""
        return bool(self._binary_path)

    def probe(self, hosts: list[str]) -> RttSample | None:
        """Run one fping burst for all reflectors and return a sample or ``None``."""
        if not self.is_available() or not hosts:
            return None

        start = time.monotonic()

        try:
            self._lock_path = self._build_lock_path(hosts)
            result = self._run_serialized(self._build_command(hosts))
            if result is None:
                self._log_failure(f"lock timeout after {self._lock_timeout:.1f}s")
                return None

            if result.returncode < 0:
                self._log_failure(f"fping process death (signal returncode {result.returncode})")
                return None
            if result.returncode > 2:
                self._log_failure(f"fping config/usage error (returncode {result.returncode})")
                return None

            combined = (result.stdout or "") + "\n" + (result.stderr or "")
            parsed = self._parse_fping(combined, hosts)
            if self._scorer is not None:
                try:
                    self._scorer.record_results(self._scorer_results(parsed))
                except Exception:
                    self._logger.debug("fping scorer feed failed", exc_info=True)

            if not parsed.successful_rtts:
                self._log_failure("all reflectors lost (all-fail)")
                return None

            if len(parsed.successful_rtts) >= 3:
                rtt_ms = statistics.median(parsed.successful_rtts)
            elif len(parsed.successful_rtts) == 2:
                rtt_ms = statistics.mean(parsed.successful_rtts)
            else:
                rtt_ms = parsed.successful_rtts[0]

            from wanctl.rtt_backend import RttSample

            if self._consecutive_failures > 0:
                self._logger.info(
                    f"fping recovered after {self._consecutive_failures} consecutive failures"
                )
                self._consecutive_failures = 0
                self._first_failure_logged = False

            return RttSample(
                rtt_ms=rtt_ms,
                per_host_results=parsed.per_host_results,
                timestamp=time.monotonic(),
                measurement_ms=(time.monotonic() - start) * 1000.0,
                active_hosts=tuple(hosts),
                successful_hosts=tuple(parsed.successful_hosts),
                backend="fping",
                source_ip=self._source_ip,
                per_host_loss=parsed.per_host_loss,
            )

        except subprocess.TimeoutExpired:
            self._log_failure(f"subprocess timed out after {self._timeout}s")
            return None
        except Exception as exc:
            self._log_failure(str(exc))
            return None

    def _build_command(self, hosts: list[str]) -> list[str]:
        """Build the fixed fping argv list for one multi-reflector burst."""
        if self._binary_path is None:
            raise RuntimeError("fping binary path unavailable")
        cmd = [self._binary_path, "-C", str(self._count), "-p", str(self._period_ms), "-q"]
        if self._source_ip:
            cmd += ["-S", self._source_ip]
        cmd += hosts
        return cmd  # noqa: S603 -- fixed fping argv list; hosts are operator-configured reflectors.

    def _build_lock_path(self, hosts: list[str]) -> str | None:
        """Return a process-shared lock path for this source/reflector set."""
        identity = "|".join([self._source_ip or "", *sorted(hosts)])
        lock_key = hashlib.sha256(identity.encode()).hexdigest()[:16]
        lock_dir = os.environ.get("WANCTL_RUN_DIR", "/run/wanctl")
        try:
            os.makedirs(lock_dir, exist_ok=True)
        except OSError:
            lock_dir = os.path.join(tempfile.gettempdir(), "wanctl")
            os.makedirs(lock_dir, exist_ok=True)
        return os.path.join(lock_dir, f"fping-{lock_key}.lock")

    def _run_serialized(self, cmd: list[str]) -> subprocess.CompletedProcess[str] | None:
        """Run fping under a source/reflector advisory file lock."""
        if self._lock_path is None:
            return subprocess.run(  # noqa: S603 -- fixed fping invocation, no shell.
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

        deadline = time.monotonic() + self._lock_timeout
        with open(self._lock_path, "a+", encoding="utf-8") as lock_file:
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        return None
                    time.sleep(0.05)

            try:
                return subprocess.run(  # noqa: S603 -- fixed fping invocation, no shell.
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                )
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _parse_target_line(self, line: str, requested: set[str]) -> tuple[str, list[float]] | None:
        """Parse one requested-host fping target line, ignoring noise and unknown hosts."""
        host_part, separator, rest = line.partition(":")
        if not separator:
            return None

        host_tokens = host_part.strip().split()
        if len(host_tokens) > 1 and _is_float_token(host_tokens[0]):
            host_tokens = host_tokens[1:]
        if len(host_tokens) != 1:
            return None
        host = host_tokens[0]
        if host not in requested:
            return None

        tokens = rest.split()
        if len(tokens) != self._count:
            return None

        rtts: list[float] = []
        for tok in tokens:
            if tok == "-":
                continue
            try:
                rtts.append(float(tok))
            except ValueError:
                return None
        return host, rtts

    def _parse_fping(self, combined_text: str, hosts: list[str]) -> FpingParseResult:
        """Parse combined stdout+stderr into per-host RTT/loss maps."""
        requested = set(hosts)
        per_host_results: dict[str, float | None] = {host: None for host in hosts}
        per_host_loss: dict[str, float | None] = {host: None for host in hosts}
        successful_rtts: list[float] = []
        successful_hosts: list[str] = []
        observed_hosts: list[str] = []

        for line in combined_text.splitlines():
            parsed = self._parse_target_line(line, requested)
            if parsed is None:
                continue
            host, rtts = parsed
            if host in observed_hosts:
                continue
            observed_hosts.append(host)
            per_host_loss[host] = (self._count - len(rtts)) / self._count * 100.0
            if rtts:
                median_rtt = statistics.median(rtts)
                per_host_results[host] = median_rtt
                successful_hosts.append(host)
                successful_rtts.append(median_rtt)

        return FpingParseResult(
            per_host_results=per_host_results,
            per_host_loss=per_host_loss,
            successful_rtts=successful_rtts,
            successful_hosts=successful_hosts,
            observed_hosts=observed_hosts,
        )

    def _scorer_results(self, parse: FpingParseResult) -> dict[str, bool]:
        """Convert observed-host loss percentages into scorer success booleans."""
        results: dict[str, bool] = {}
        for host in parse.observed_hosts:
            loss = parse.per_host_loss[host]
            results[host] = loss is not None and loss <= self._loss_fail_threshold
        return results

    def _log_failure(self, reason: str) -> None:
        """Log measurement failure with first-warning, subsequent-debug throttling."""
        if not self._first_failure_logged:
            self._logger.warning(f"fping measurement failed: {reason}")
            self._first_failure_logged = True
        else:
            self._logger.debug(f"fping measurement failed: {reason}")
        self._consecutive_failures += 1


def _is_float_token(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True
