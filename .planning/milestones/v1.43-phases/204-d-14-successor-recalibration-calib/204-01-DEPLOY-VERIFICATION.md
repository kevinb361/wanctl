# Phase 204 — Plan 204-01 Deploy Verification (METRIC-01 + OBSV-05 binary on cake-shaper)

timestamp: 2026-05-07T01:04:01+00:00
deploy_ts: 20260507T010313Z
verdict: pass
operator_approval: "Task 2 approved; user also approved bound Spectrum health endpoint"

---

## Deploy Summary

Deployed v1.43.0 binary to cake-shaper:/opt/wanctl. METRIC-01 (Phase 202) and OBSV-05 (Phase 203) `/health` fields now live in production. Two-snapshot rollback per Plan 201-15 pattern (Snapshot A == Snapshot B byte-identical because v1.43 ships zero new YAML keys, captured separately for evidence symmetry per 204-RESEARCH.md §Q7).

## Two-Snapshot Evidence

- Snapshot A (rollback-clean, pre-deploy v1.42.1):
  - `/opt/wanctl-prephase204-deploy1-20260507T010313Z-snapA.tar.gz`
  - `/etc/wanctl/spectrum.yaml.prephase204-deploy1-20260507T010313Z-snapA`
- Snapshot B (post-gate candidate, byte-identical to A):
  - `/opt/wanctl-prephase204-deploy1-20260507T010313Z-snapB.tar.gz`
  - `/etc/wanctl/spectrum.yaml.prephase204-deploy1-20260507T010313Z-snapB`

## Predeploy Gate

`bash scripts/check-safe07-source-diff.sh` exit code: 0
Default ref: `b72b463` (Phase 202 close)

The SAFE-07 helper was patched during this plan to allow exactly the planned `src/wanctl/__init__.py` version literal diff (`1.42.1` → `1.43.0`) while continuing to reject all other `src/wanctl/` changes.

## Post-Deploy /health Smoke

Health endpoint used: `http://10.10.110.223:9101/health` (Spectrum-bound endpoint on cake-shaper).

The five Phase 204 field paths verified present:
- `.version == "1.43.0"` ✓
- `.wans[0].upload.hysteresis.suppressions_completed_window_count` (METRIC-01) ✓
- `.wans[0].upload.hysteresis.suppressions_completed_window_by_cause` (METRIC-02) ✓
- `.wans[0].upload.hysteresis.suppressions_lifetime_by_cause` (METRIC-02 lifetime) ✓
- `.wans[0].load_rtt_ms` (OBSV-05 source) ✓
- `.wans[0].baseline_rtt_ms` (OBSV-05 source) ✓

Full /health JSON: see `204-01-postdeploy-health.json` (committed alongside this verdict file).

Excerpt at verification time:

```json
{
  "version": "1.43.0",
  "wans": [
    {
      "name": "spectrum",
      "load_rtt_ms": 21.83,
      "baseline_rtt_ms": 22.72,
      "upload": {
        "hysteresis": {
          "suppressions_completed_window_count": 0,
          "suppressions_completed_window_by_cause": {
            "dwell_hold": 0,
            "backlog_recovery": 0,
            "other": 0
          },
          "suppressions_lifetime_by_cause": {
            "dwell_hold": 16,
            "backlog_recovery": 0,
            "other": 0
          }
        }
      }
    }
  ]
}
```

## Deviations

- **Bound health endpoint:** The plan's stale localhost check (`127.0.0.1:9101`) failed because this deployment binds health on WAN-local addresses. Operator-approved continuation used Spectrum endpoint `http://10.10.110.223:9101/health`; ATT endpoint `10.10.110.227:9101` was not used for this Spectrum deploy.
- **Snapshot YAML verification:** The YAML snapshot is mode `0640`, so plain `ls` returned permission denied. Snapshot existence was verified with `sudo ls` instead.
- **SAFE-07 helper fix:** `scripts/check-safe07-source-diff.sh` had stale Phase 203 wording and rejected the planned version-only `src/wanctl/__init__.py` diff. It was patched and committed as `89b99be` before rerunning T1.
- **Discarded failed-attempt timestamp:** An earlier aborted attempt created rollback-clean Snapshot A for `20260507T005026Z`; after the script fix, the successful deploy used fresh evidence timestamp `20260507T010313Z` to avoid ambiguous snapshot evidence.

## Rollback Commands (kept for operator reference)

```bash
ssh cake-shaper "sudo tar -xzf /opt/wanctl-prephase204-deploy1-20260507T010313Z-snapA.tar.gz -C /"
ssh cake-shaper "sudo cp /etc/wanctl/spectrum.yaml.prephase204-deploy1-20260507T010313Z-snapA /etc/wanctl/spectrum.yaml"
ssh cake-shaper "sudo systemctl restart wanctl@spectrum.service"
ssh cake-shaper "curl -s http://10.10.110.223:9101/health | jq -r '.version'"   # MUST report 1.42.1
```

## References

- Plan 201-15 two-snapshot precedent: `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md`
- Phase 204 RESEARCH §Q7: `.planning/phases/204-d-14-successor-recalibration-calib/204-RESEARCH.md`
- Phase 204 PATTERNS deploy-verdict template: `.planning/phases/204-d-14-successor-recalibration-calib/204-PATTERNS.md` (lines 516-575)
