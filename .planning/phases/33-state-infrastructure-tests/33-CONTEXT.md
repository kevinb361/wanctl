# Phase 33: State & Infrastructure Tests - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Add comprehensive test coverage for state management (`state_manager.py`) and infrastructure utilities (`error_handling.py`, `signal_utils.py`, `systemd_utils.py`, `path_utils.py`). Target: each module >= 90% coverage.

Plans:
- 33-01: State manager test coverage
- 33-02: Infrastructure utilities test coverage

</domain>

<decisions>
## Implementation Decisions

### State Persistence Testing
- Use pytest `tmp_path` fixture for real file I/O in isolated temp directories
- Real file operations preferred over mocking — tests actual behavior

### Claude's Discretion
The following areas are left to Claude's judgment based on what the actual code does:

**State persistence:**
- Corruption scenarios (truncated files, invalid JSON, wrong schema) — test if code handles them
- Atomic write verification (write-then-rename pattern) — test if implemented
- State versioning/migration — test migration paths if they exist

**Concurrency/locking:**
- Lock testing approach (real locks vs mocks) — based on what lock_utils actually does
- Lock contention testing — if practical with real multiprocessing
- Lock cleanup on abnormal exit — assess if in-scope
- Thread safety — check if threading is actually used in wanctl

**Error handling:**
- Exception injection approach — mix of mocks and real failure conditions as practical
- Error chaining/wrapping — test `__cause__` if error chaining is used
- Recovery path verification — determine what recovery paths exist
- Log output verification — include caplog checks where meaningful

**Signal/systemd:**
- Signal handler testing approach — based on what signal_utils does
- SIGHUP config reload — test if reload exists
- Systemd notification — mock sd_notify or socket as practical
- Watchdog keepalive — test if watchdog is implemented

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

Key pattern: Use real file I/O with tmp_path for authenticity, fall back to mocks only where real testing is impractical (signals, systemd socket).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 33-state-infrastructure-tests*
*Context gathered: 2026-01-25*
