# Phase 182 ATT Reduction Execution

**Executed:** 2026-04-14T13:33:00Z  
**Host:** `kevin@10.10.110.223`

## Procedure

The existing helper was sufficient. No repo-side storage helper change was needed.

Commands run:

```bash
ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal 2>/dev/null'
./scripts/compact-metrics-dbs.sh --ssh kevin@10.10.110.223 --wan att
./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json
./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json
```

## Before And After

| File | Before | After | Delta |
|------|--------|-------|-------|
| `metrics-att.db` | `5,082,877,952` bytes | `201,723,904` bytes | `-4,881,154,048` bytes |
| `metrics-att.db-wal` | `7,127,632` bytes | `5,401,352` bytes | `-1,726,280` bytes |

Helper output:

- `att: 4.8GB -> 193MB (saved 4.6GB)`

## Service Outcome

- `wanctl@att.service` restarted cleanly
- service state after the run: `active (running)`
- `canary-check` result: pass for `spectrum`, `att`, and `steering`
- `soak-monitor` result: healthy for both WANs, `storage.status: ok`

## Anomalies

- none in the ATT compaction flow itself
- direct spot-checks of `/metrics/history` from the phase host still timed out, but Phase 182 did not modify the history path and the merged CLI history proof path remained working

## Conclusion

The ATT-only reduction run completed successfully and produced the material footprint reduction needed for milestone closure.
