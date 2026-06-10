---
phase: quick
plan: 260503-cfs
type: execute
status: complete
completed: 2026-05-03
duration: ~5min (split: repo fix at 41d4a1f earlier in session, prod fix at session end)
---

# Quick Task 260503-cfs: Spectrum Alerting Severity Fix

**Surfaced:** 2026-05-03 during Phase 200 Plan 06 deploy work — every wanctl@spectrum.service restart emitted `alerting.rules.congestion_flapping missing required 'severity'; disabling alerting`, which silently disabled ALL alerting on Spectrum.

**Root cause:** `configs/spectrum.yaml` and `/etc/wanctl/spectrum.yaml` carried `congestion_flapping` rule with `cooldown_sec: 600` (added 2026-04-17 during a cooldown bump for the 2026-04-16 DOCSIS event) but no `severity` field. Validator at `autorate_config.py:707-713` fail-closes the entire alerting subsystem on any per-rule schema error.

## Tasks Completed

### Task 2 (auto, Claude-driven) — repo-side YAML fix

- File: `configs/spectrum.yaml`
- Change: added `severity: warning` line under `alerting.rules.congestion_flapping` with explanatory comment pointing at the validator and discovery date.
- Commit: `41d4a1f fix(config): restore Spectrum alerting and close Phase 200 FAIL`
- CHANGELOG.md updated with operator-facing notice under v1.41.0 → Fixed.

### Task 1 (operator-driven) — production YAML fix on cake-shaper

- Backup created: `/etc/wanctl/spectrum.yaml.bak.20260503T224402Z` (root-owned, 11K)
- Change applied via sed: inserted `severity: warning` line before the existing `cooldown_sec: 600` line, preserving 6-space indentation.
- YAML validation post-edit: `python3 -c 'yaml.safe_load(...)'` confirmed the rule parses with `severity = warning, cooldown_sec = 600`.
- Service restart: `sudo systemctl restart wanctl@spectrum.service` at `2026-05-03T22:44:12Z`.
- Post-restart verification:
  - `sudo systemctl is-active wanctl@spectrum.service` → `active`
  - `sudo journalctl --since '1 minute ago' | grep -c 'missing required'` → **0** (was non-zero on every prior restart)
  - `/health.alerting.enabled` → **true**
  - `/health.alerting.fire_count` → **1** (a `hard_red_ul` alert fired on Spectrum within the first minute post-restart, with 41s of 600s cooldown remaining; confirms alerting is actively wired and firing real events that would have been silently dropped pre-fix).

## Verification

### Spectrum

- ✓ Validator no longer rejects the rule.
- ✓ Alerting subsystem is enabled in `/health.alerting`.
- ✓ Real alert (`hard_red_ul`) fired post-restart and is in cooldown — proves the alerting path is end-to-end live, not just declared enabled.
- ✓ Repo and production carry semantically equivalent severity values (comment text differs between repo and prod; functional severity is identical: `warning`).

### ATT (verify-only, per Plan)

- ATT YAML at `/etc/wanctl/att.yaml` has `alerting.enabled: true` + `webhook_url` but **no `rules:` block at all**.
- Validator behavior with missing rules: `alerting.get("rules", {})` returns empty dict; rule loop iterates zero times; alerting validates as enabled with zero rules. No schema error. No fix required.
- `wanctl@att.service` has been active for 5 days with no severity-missing journal warnings.

## Files Created/Modified

- (Repo) `configs/spectrum.yaml` — committed at `41d4a1f`.
- (Repo) `CHANGELOG.md` — operator-facing entry under v1.41.0 Fixed at `41d4a1f`.
- (Production) `/etc/wanctl/spectrum.yaml` on cake-shaper — sed-inserted `severity: warning` line. Backup at `/etc/wanctl/spectrum.yaml.bak.20260503T224402Z`.
- (This file) `.planning/quick/260503-cfs-fix-spectrum-alerting-severity/260503-cfs-SUMMARY.md`.

## Notes

- Comment text on production differs slightly from repo (production was sed-inserted with a shorter explanatory comment; repo has a longer one). Functionally identical. Operator can sync on next full deploy or leave as-is.
- Prior production state: alerting silently disabled since the 2026-04-17 cooldown bump (≈ 16 days). No alerts fired during that window.
- The hard_red_ul fire_count=1 within minutes of restart suggests the hard_red_ul condition is currently active in some form on the v1.40 Spectrum baseline — worth a separate investigation if it keeps firing, but unrelated to this quick task.

---
*Quick task closed: 2026-05-03*
