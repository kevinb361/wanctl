# VERIFY-01 Evidence — D-04(b) Early Operator Deferral

**Status:** VERIFY-01 deferred to v1.46/watch-list by explicit operator override before the full 7-day observation window elapsed.

BRANCH: D-04(b) deferral — plan 211-03 archive task MUST NOT execute git mv

## Summary

VERIFY-01 is not closed by production alert evidence in v1.45. The operator explicitly chose to stop waiting and defer the production observation gate to v1.46/watch-list: "Just defer. I am tired of waiting. We can circle back to it later if needed. I want to cleanly move to 1.446". `1.446` is interpreted as v1.46.

This is an operator-approved early deferral decision, not a 7-day-window expiry. At the time of the latest read-only SQL check, no qualifying `flapping_dl` / `flapping_ul` alert row existed with `details.peak_transition_count > 30` on either WAN.

## Observation Windows Actually Observed

| WAN | v1.45 rollout start | Observation status | Notes |
|-----|---------------------|--------------------|-------|
| Spectrum | 2026-05-26T18:48:06Z approx | Early-stopped by operator deferral before full 7d window | Spectrum was deployed first per canary order and remained healthy at final rollout check. |
| ATT | 2026-05-27T17:43:12Z approx | Early-stopped by operator deferral before full 7d window | ATT rollout itself was also operator-approved early, about 66 minutes before the original T+24h unblock time. |

## Rollout and Health Evidence

### Spectrum

- Deploy / observation start: approximately `2026-05-26T18:48:06Z`.
- Final rollout check: `version=1.45.0`, `status=healthy`, download `GREEN`, upload `GREEN`.
- Active cooldowns at final check: none (`[]`).
- Flapping journal count since deploy (`Alert fired: flapping_(dl|ul)`): `0`.

### ATT

- Preflight time: `2026-05-27T17:42:13Z`, approximately 66 minutes before original ATT unblock time `2026-05-27T18:48:06Z`.
- Operator explicitly approved early ATT rollout before T+24h: "can we just deploy 1.45 to att...".
- ATT preflight before rollout: `version=1.39.0`, `status=healthy`, `wanctl@att.service active`.
- Snapshot A ISO8601: `20260527T174231Z`.
- Canonical snapshot tar: `/opt/wanctl-prephase211-20260527T174231Z.tar.gz`, size `1524896`; `sudo tar -tzf` succeeded.
- Additional explicit ATT tar path: `/opt/wanctl-prephase211-att-20260527T174231Z.tar.gz`, size `1524896`.
- Config snapshot: `/etc/wanctl/att.yaml.prephase211-20260527T174231Z`, size `8549`.
- Deploy invocation used: `./scripts/deploy.sh att cake-shaper`.
- Deploy completed successfully with non-blocking warnings:
  - missing `docs/PROFILING.md`
  - missing `scripts/wanctl-history`
  - pre-startup validation warning for unknown transport `linux-cake-netlink`
- Deploy did not restart the already-running daemon; before restart ATT still reported `1.39.0 healthy`.
- Restart command executed: `sudo systemctl restart wanctl@att.service`.
- Post-restart ATT service: `active`.
- Post-restart ATT health endpoint: `http://10.10.110.227:9101/health` (host-bound, not loopback), `version=1.45.0`, `status=healthy`, download `GREEN`, upload `GREEN`.
- ATT rollout / observation start: approximately `2026-05-27T17:43:12Z` from journal startup time.

## Alerts Table Volume at Deferral

Read-only SQL counts taken from `cake-shaper` using the per-WAN metrics databases.

| WAN | Window start | Total alerts | Flapping alerts | Qualifying `peak_transition_count > 30` rows |
|-----|--------------|--------------|-----------------|---------------------------------------------|
| Spectrum | 2026-05-26T18:48:06Z | 131 | 10 | 0 |
| ATT | 2026-05-27T17:43:12Z | 0 | 0 | 0 |

SQL shape used for qualifying count:

```sql
SELECT COUNT(*)
FROM alerts
WHERE alert_type IN ('flapping_dl','flapping_ul')
  AND json_extract(details,'$.peak_transition_count') > 30
  AND timestamp >= <rollout_start_epoch>;
```

## Threshold and Payload Provenance

- VERIFY-01 closure bar remains `details.peak_transition_count > 30` unless a production `alerts.rules.congestion_flapping.flap_threshold` override exists.
- The v1.45 payload shape in `src/wanctl/wan_controller.py` is limited to:
  - `transition_count`
  - `peak_transition_count`
  - `window_sec`
  - `current_zone`
- `flap_threshold` is not in the payload; it is read via `alert_engine.get_rule_param("congestion_flapping", "flap_threshold", 30)`.
- Spectrum production `cooldown_sec` is explicitly configured as `600` in `configs/spectrum.yaml`.
- ATT has no `congestion_flapping` rule override in `configs/att.yaml`; effective cooldown falls through to the alert-engine default path and remains flagged for operator review in the v1.46 watch-list follow-up.

## Synthetic Proof Reference

Production evidence is deferred, but the implementation mechanism remains covered by Phase 210 synthetic proof:

- Phase 210 verification report passed 11/11 truths.
- Phase 210 alerting + integration regression slice passed (`132 passed`).
- Post-wave integration gate after 211-01 passed: `.venv/bin/python -m compileall -q src/wanctl tests` and `timeout 300 .venv/bin/pytest tests/ -q` produced `5123 passed, 6 skipped, 2 deselected`.

## Deferral Rationale

The operator decided the remaining VERIFY-01 production wait should not block moving cleanly toward v1.46. This branch intentionally preserves the unfinished production gate as a watch-list item rather than pretending the v1.45 production observation requirement was satisfied.

Plan 211-03 must treat this file as Branch B and must not archive the active phase directories with `git mv`.
