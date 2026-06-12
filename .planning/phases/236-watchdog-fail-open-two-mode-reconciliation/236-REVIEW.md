---
phase: 236-watchdog-fail-open-two-mode-reconciliation
reviewed: 2026-06-12T21:47:18Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - tests/test_silicom_bypass_cli.py
  - deploy/systemd/silicom-bypass-watchdog@.service
  - deploy/scripts/bpctl-watchdog-att.env.example
  - deploy/scripts/bpctl-watchdog-spectrum.env.example
  - scripts/silicom-bypass
  - scripts/wanctl-bpctl-watchdog-petter
  - scripts/wanctl-bpctl-watchdog-bypass
  - scripts/deploy.sh
  - docs/SILICOM-BYPASS.md
  - scripts/phase231-rollback.sh
  - scripts/soak-monitor.sh
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 236: Code Review Report

**Reviewed:** 2026-06-12T21:47:18Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Phase 236 watchdog fail-open reconciliation surface: shell operator CLI, watchdog petter/bypass scripts, systemd/deploy artifacts, rollback/soak ops scripts, docs, and watchdog test coverage. No Critical blocking issue was found in the live fail-open implementation path, but three Warning-level risks should be addressed before treating the phase as fully clean: one stale runbook section still instructs raw watchdog systemctl stops/restarts, one arm failure path can leave a partial env file behind, and the retired-variant test does not actually model the ExecStop-masked path it claims to prove.

## Warnings

### WR-01: Stale docs still instruct raw watchdog stop/restart outside W-INV

**File:** `docs/SILICOM-BYPASS.md:593-632`
**Issue:** The Spectrum raw bridge procedure still tells operators to run `sudo systemctl stop silicom-bypass-watchdog@spectrum.service` and later `sudo systemctl restart silicom-bypass-watchdog@spectrum.service`. After Phase 236, raw watchdog lifecycle operations are explicitly forbidden because they can run fail-open ExecStop without the operator-disarm sentinel. This contradicts the new W-INV section and can lead an operator to bypass the safe `silicom-bypass disarm/arm` path.
**Fix:** Update the procedure to use the sanctioned CLI verbs, e.g. disarm before stopping the controller and re-arm after the controller is back and the env points at the intended watched unit:

```bash
sudo silicom-bypass disarm spec-modem
sudo systemctl stop wanctl@spectrum.service
# ...raw bridge isolation steps...
sudo systemctl restart wanctl@spectrum.service
sleep 3
sudo silicom-bypass arm spec-modem --yes
```

### WR-02: `arm` can create a partial watchdog env on missing/invalid env file

**File:** `scripts/silicom-bypass:270-298,350-351`
**Issue:** `cmd_arm` writes `TIMEOUT_MS` before validating `IFACE` and `WANCTL_UNIT`. If `/etc/wanctl/bpctl-watchdog/<instance>.env` is missing, `write_timeout_atomic` creates a file containing only `TIMEOUT_MS=...`, then `validate_watchdog_env` fails. Because deploy installs env examples only if absent, this partial file can persist and block later remediation/deploy attempts.
**Fix:** Fail closed before mutating when the env is missing or lacks required non-timeout keys, then write the timeout and revalidate before starting:

```bash
validate_watchdog_env_required_keys_before_timeout "$env_path" "$pair"
write_timeout_atomic "$env_path" "$timeout_ms"
validate_watchdog_env "$env_path" "$pair"
```

Keep the existing stale-`wanctl@` refusal unless `WD_ALLOW_NATIVE_UNIT=1`.

### WR-03: Retired-variant test does not model the ExecStop-masked retirement path

**File:** `tests/test_silicom_bypass_cli.py:1183-1208`
**Issue:** `test_retire_nobypass_sentinel_first_cleanup_is_load_bearing` invokes fake `systemctl disable --now silicom-bypass-watchdog-cake-autorate-att.service`, which runs the real ExecStop shim and consumes the sentinel. The planned live retirement is sentinel-first **and ExecStop-masked**, so the test does not prove that the blank `ExecStop=` mask prevents the retired unit from running fail-open, nor that sentinel cleanup occurs only after the unit is down while the sentinel remains present through the stop.
**Fix:** Extend `_fake_systemctl` or the test to explicitly simulate a masked ExecStop for the retired unit: assert the disable does not run the bypass script, assert the sentinel remains until the modeled post-disable cleanup, then remove it and verify the subsequent real `@att` ExecStop fail-opens. Keep the existing unmasked sentinel/non-vacuity checks as separate coverage.

---

_Reviewed: 2026-06-12T21:47:18Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
