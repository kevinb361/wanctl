# Phase 45: Research — Current Shutdown Handling

## Signal Handling (signal_utils.py)
- Thread-safe `threading.Event` (_shutdown_event, line 37)
- Handler sets event only, no logging (deadlock-safe, lines 40-53)
- SIGTERM (daemon) + SIGINT (all) registered (lines 56-71)
- `is_shutdown_requested()` checks event (lines 74-80)
- `get_shutdown_event()` returns event for timed waits (lines 83-100)

## autorate_continuous.py Shutdown (lines 2012-2064)
Finally block cleanup order:
1. save_state(force=True) per WAN (lines 2015-2020)
2. Release lock files via unlink(missing_ok=True) (lines 2023-2029)
3. Unregister atexit handler (lines 2031-2035)
4. Close router connections per WAN (lines 2037-2047)
5. Stop metrics server (lines 2049-2055)
6. Shutdown health server (lines 2057-2063)

## steering/daemon.py Shutdown (lines 1580-1594)
Finally block cleanup:
1. Shutdown health server (lines 1582-1587)
2. Release lock file (lines 1591-1593)
MISSING: router.close(), state save, MetricsWriter close

## Connection Cleanup Methods
- RouterOSSSH.close(): closes paramiko client, safe for multiple calls (routeros_ssh.py:251-264)
- RouterOSREST.close(): closes requests.Session, safe for multiple calls (routeros_rest.py:661-673)
- FailoverRouterClient.close(): closes both primary and fallback (router_client.py:206-214)
- MetricsWriter.close(): closes SQLite connection (storage/writer.py:195-200)

## Atomic State Writes (state_utils.py:20-66)
- atomic_write_json(): temp file -> json.dump -> flush -> fsync -> os.replace
- POSIX atomic rename guarantees no partial reads
- File locking via fcntl for concurrent access (state_manager.py:609-620)

## systemd Service Config
- WatchdogSec=30s, Restart=on-failure, RestartSec=5s
- StartLimitBurst=5, StartLimitIntervalSec=300
- Default SIGKILL timeout: 90s (systemd default TimeoutStopSec)
- Type=simple (PID is main process)

## Gap Summary
| Gap | Location | Impact | Fix Complexity |
|-----|----------|--------|----------------|
| No router.close() | steering/daemon.py finally | Connection leak until exit | LOW |
| No MetricsWriter.close() | Both daemons | SQLite connection leak | LOW |
| No state save on shutdown | steering/daemon.py | Stale state on restart | LOW |
| No shutdown timeout | Both daemons | Potential hung cleanup | MEDIUM |
