# Spectrum WAN Watchdog Restarts Issue

**Status:** Active Issue (Ongoing)
**Severity:** MEDIUM - Service auto-recovers but indicates underlying WAN instability
**Date Discovered:** 2026-01-11
**Affected:** cake-spectrum container only (ATT unaffected)

## Executive Summary

The Spectrum autorate daemon is experiencing periodic restarts (4-19 times per week) due to brief network outages where all ping targets fail simultaneously for 6+ seconds. The daemon's watchdog safety mechanism intentionally stops during sustained failures, triggering systemd to kill and restart the service. While the service auto-recovers within seconds, this indicates **actual Spectrum WAN instability** that may impact user experience during outages.

## Symptoms

### User-Visible
- Periodic 30-40 second gaps in CAKE rate adjustments during outages
- Service uptime: 3-6 hours between restarts (vs 18+ hours for ATT)
- No functional impact (service auto-recovers, rates resume from saved state)

### Logs
```
Jan 11 10:20:54,783 [spectrum] [WARNING] Ping to 1.1.1.1 failed (returncode 1)
Jan 11 10:20:54,782 [spectrum] [WARNING] Ping to 8.8.8.8 failed (returncode 1)
Jan 11 10:20:54,782 [spectrum] [WARNING] Ping to 9.9.9.9 failed (returncode 1)
Jan 11 10:20:54,783 [spectrum] [WARNING] spectrum: All pings failed (median-of-three)
Jan 11 10:20:54,783 [spectrum] [WARNING] Cycle failed (3/3)
Jan 11 10:20:54,783 [spectrum] [ERROR] Sustained failure: 3 consecutive failed cycles. Stopping watchdog - systemd will terminate us.
```

Followed ~30 seconds later by:
```
Jan 11 10:21:18 cake-spectrum systemd[1]: wanctl@spectrum.service: Main process exited, code=killed, status=6/ABRT
Jan 11 10:21:18 cake-spectrum systemd[1]: wanctl@spectrum.service: Failed with result 'watchdog'.
Jan 11 10:21:24 cake-spectrum systemd[1]: wanctl@spectrum.service: Scheduled restart job, restart counter is at 2.
```

## Root Cause Analysis

### Architecture
The wanctl containers use policy-based routing on the MikroTik router:
- Traffic from `10.10.110.246` (cake-spectrum) routes via **Spectrum WAN**
- Traffic from `10.10.110.247` (cake-att) routes via **ATT WAN**

This allows each container to measure RTT through its monitored WAN despite sharing the same default gateway (`10.10.110.1`).

### Failure Mechanism
1. **Spectrum WAN outage** causes all 3 ping targets (1.1.1.1, 8.8.8.8, 9.9.9.9) to fail
2. After **3 consecutive failures** (6 seconds total), daemon stops watchdog pings
3. After **30 seconds** without watchdog ping, systemd kills process (SIGABRT)
4. After **5 seconds** (RestartSec), systemd restarts service
5. Service resumes from last saved state (rates preserved)

### Why ATT Is Unaffected
- **ATT WAN:** 0 ping failures in past 24+ hours (very stable VDSL)
- **Spectrum WAN:** Multiple outage windows (cable network instability)

## Failure Timeline (Past 7 Days)

### Jan 8, 2026 - Major Outage
- **00:33 - 00:40:** 13 restarts in 7 minutes (sustained outage)
- Indicates extended Spectrum WAN failure, possibly maintenance or node issue

### Jan 9, 2026 - Minor Outages
- **18:56-18:57:** 2 restarts in 1 minute

### Jan 11, 2026 (Today) - Sporadic Outages
- **04:41:** 1 restart (overnight)
- **10:21:** 1 restart (mid-morning)
- **10:29:** 1 restart (8 minutes later - WAN still unstable)
- **16:29:** 1 restart (late afternoon)

**Total: 19 watchdog kills in past 7 days (~3 per day average)**

## Impact Assessment

### Network Performance
- ✅ **CAKE control maintained:** Service restarts in 5s, rates resume from state file
- ✅ **No rate resets:** Baseline RTT preserved, no "cold start" behavior
- ⚠️ **Brief gaps in control:** 35-40s without rate adjustments during restart
- ⚠️ **Outage correlation:** Restarts indicate actual user-impacting WAN failures

### System Health
- ✅ **Auto-recovery working:** systemd restart mechanism is reliable
- ✅ **State persistence working:** No data loss across restarts
- ✅ **Watchdog mechanism working:** Correctly detects sustained failures
- ⚠️ **Restart counter accumulating:** Currently at 4 (resets on successful start)

## Comparison: Spectrum vs ATT

| Metric | Spectrum | ATT | Notes |
|--------|----------|-----|-------|
| **Uptime** | 3-6 hours | 18+ hours | Spectrum restarts frequently |
| **Ping failures** | 19 events/week | 0 events/week | Cable vs DSL stability |
| **WAN type** | DOCSIS cable | VDSL | Cable more prone to outages |
| **Restart rate** | ~3/day | 0/day | Spectrum needs investigation |

## Options for Resolution

### Option 1: Accept as Cable Reality (Recommended)
**Action:** Document as known behavior, no code changes
**Rationale:**
- Spectrum cable networks inherently less stable than DSL
- Watchdog mechanism is working as designed (safety feature)
- Auto-recovery within 35-40s is acceptable
- No functional impact (state preserved, rates resume correctly)

**Pros:** No changes, proven mechanism
**Cons:** Periodic restarts continue

### Option 2: Increase Failure Tolerance
**Action:** Change consecutive failure threshold from 3 to 5-10 cycles
**File:** `src/wanctl/autorate_continuous.py` (search for "3 consecutive")
**Rationale:**
- Reduce restart frequency for brief transient outages
- Allow more time for WAN to recover before giving up

**Pros:** Fewer restarts, more tolerant of brief hiccups
**Cons:** May delay detection of real sustained failures, longer blind period

### Option 3: Disable Watchdog
**Action:** Remove `WatchdogSec=30s` from `/etc/systemd/system/wanctl@.service`
**Rationale:**
- Eliminate restarts entirely
- Trust daemon's internal error handling

**Pros:** No more restarts
**Cons:** Loss of systemd's process health monitoring, daemon could hang without recovery

### Option 4: Improve Ping Retry Logic
**Action:** Add retry-with-backoff before declaring total failure
**Example:** Try each host 2-3 times with 100ms delays before giving up
**Rationale:**
- Distinguish brief transients from sustained outages
- Reduce false positives from single-packet loss

**Pros:** More resilient to packet loss, fewer spurious failures
**Cons:** Increases cycle time during failures (200-300ms), more complex

### Option 5: Fallback to Single-Host Mode
**Action:** If all 3 fail, retry with just 1.1.1.1 and accept its RTT
**Rationale:**
- Even during partial WAN degradation, maintain some RTT measurement
- Avoid complete failure if 1+ host is reachable

**Pros:** Continue operation during partial failures
**Cons:** Less reliable RTT during degraded mode, adds complexity

## Recommended Action

**Accept as cable reality (Option 1)** for now, with monitoring:

1. **Document behavior** - This is normal for cable networks
2. **Monitor frequency** - Alert if restarts exceed 5/day (indicates major issue)
3. **Correlate with user reports** - Do users notice Spectrum slowdowns during restart windows?
4. **Consider Option 4** if frequency increases or user complaints arise

The current behavior is **correct by design** - the daemon is accurately detecting real Spectrum WAN outages and recovering cleanly. The watchdog mechanism prevents hung processes and ensures fresh starts after failures.

## Investigation Questions

### For Network Team
1. **Are these known Spectrum outages?** Check ISP status pages during failure times
2. **DOCSIS signal quality?** Check downstream/upstream SNR, errors on modem
3. **Node congestion?** Spectrum cable nodes can have peak-time issues
4. **Router logs?** Check MikroTik logs for WAN state changes during failures

### For User
1. **Do you notice Spectrum slowdowns** around 4am, 10am, 4pm?
2. **Any pattern to failures?** Time of day, day of week, weather-related?
3. **Is Spectrum WAN primary or backup?** If backup, restarts less critical

## Monitoring Recommendations

### Short-Term (Manual)
```bash
# Check restart frequency
ssh cake-spectrum 'sudo journalctl -u wanctl@spectrum.service --since "24 hours ago" | grep -c "Failed with result .watchdog"'

# View failure windows
ssh cake-spectrum 'sudo journalctl -u wanctl@spectrum.service --since "24 hours ago" | grep "Failed with result .watchdog"'

# Check if currently failing
bash scripts/soak-monitor.sh
```

### Long-Term (Automated)
- Add Prometheus metric: `wanctl_watchdog_restarts_total{wan="spectrum"}`
- Alert if >5 restarts in 24 hours
- Graph restart times to identify patterns (maintenance windows, peak usage, etc.)

## Related Files

- `/etc/systemd/system/wanctl@.service` - Watchdog configuration (WatchdogSec=30s)
- `src/wanctl/autorate_continuous.py` - Failure threshold (3 consecutive)
- `/var/log/wanctl/spectrum_debug.log` - Detailed ping failure logs
- `docs/STEERING_CONFIG_MISMATCH_ISSUE.md` - Related deployment issue from same timeframe

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-11 | Issue documented | User reported frequent restarts via soak monitor |
| TBD | Implementation | Pending user feedback on impact and priority |

---

**Next Steps:**
1. Confirm with user whether Spectrum WAN is primary or backup
2. Check Spectrum modem signal quality (SNR, errors)
3. Correlate restart times with user-perceived outages
4. Decide on Option 1-5 based on business impact
5. If implementing changes, test on non-production first

**Status:** Awaiting user input on priority and preferred approach
