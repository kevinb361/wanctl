# Phase 45: Graceful Shutdown

## Goal
Daemons terminate cleanly with consistent state and no orphaned resources.

## Success Criteria (from roadmap)
1. SIGTERM triggers clean shutdown (daemon exits 0, not killed)
2. In-flight router commands either complete or abort without partial state
3. State files are consistent after shutdown (no truncation, no corruption)
4. All router connections are closed before daemon exits
5. Shutdown completes within reasonable timeout (not hung indefinitely)

## Current State

### What Already Works
- Signal handling: thread-safe `threading.Event` in `signal_utils.py`
- autorate_continuous.py: comprehensive finally block (save state, close router, release locks, stop health server)
- Atomic state writes: `atomic_write_json()` uses temp-file + fsync + atomic rename
- Lock files: triple-layer protection (finally + atexit + PID validation on restart)
- Health server: clean shutdown with 5s thread join timeout
- Interruptible sleep: both daemons use `shutdown_event.wait(timeout=)` pattern

### Gaps Found
1. **steering/daemon.py missing router.close()** — finally block doesn't close SSH/REST connections
2. **No MetricsWriter cleanup** — neither daemon explicitly closes SQLite connection
3. **steering/daemon.py missing state save on shutdown** — only saves per-cycle, not on exit
4. **No shutdown timeout enforcement** — if cleanup hangs, relies on systemd's SIGKILL (90s default)

### Risk Assessment
- State corruption: LOW (atomic writes already handle this)
- Connection leaks: MODERATE (implicit cleanup at process exit works but isn't explicit)
- Hung shutdown: LOW (health server has 5s timeout, but router close has no timeout)

## Constraints
- No changes to signal_utils.py signal handling pattern (proven stable)
- No changes to atomic_write_json() (already correct)
- Must maintain backward compatibility with existing systemd service files
- Production system — conservative changes only
