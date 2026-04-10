# Phase 67: Production Config Audit

**Date:** 2026-03-11
**Purpose:** Complete inventory of legacy vs modern parameter usage across all production configs on cake-spectrum and cake-att. Consumed by Phase 68 (dead code removal) and Phase 69 (legacy fallback removal).
**Requirement:** LGCY-01

## Section 1: Container Config Inventory

### cake-spectrum `/etc/wanctl/`

| File | Status | Repo Counterpart | Notes |
|------|--------|------------------|-------|
| `spectrum.yaml` | ACTIVE | `configs/spectrum.yaml` | Modern params only |
| `steering.yaml` | ACTIVE | `configs/steering.yaml` | Modern params, `cake_aware: true` |
| `spectrum.yaml.bak` | INACTIVE | None (backup) | Contains `alpha_baseline`, `alpha_load` |
| `steering_config_v2.yaml` | INACTIVE | None (old config) | Contains `bad_samples`, `good_samples` |
| `wan1.yaml` | INACTIVE | None (old config) | Contains `alpha_baseline`, `alpha_load` |
| `secrets` | Config | N/A | Router credentials |
| `ssh/` | Config | N/A | SSH keys directory |

### cake-att `/etc/wanctl/`

| File | Status | Repo Counterpart | Notes |
|------|--------|------------------|-------|
| `att.yaml` | ACTIVE | `configs/att.yaml` | Modern params only |
| `att.yaml.bak` | INACTIVE | None (backup) | Contains `alpha_baseline`, `alpha_load` |
| `wan2.yaml` | INACTIVE | None (old config) | Contains `alpha_baseline`, `alpha_load` |
| `secrets` | Config | N/A | Router credentials |
| `ssh/` | Config | N/A | SSH keys directory |

**Key finding:** All 3 ACTIVE config files use modern parameter names exclusively. Legacy params exist only in old/backup files that are not loaded by the running daemons.

## Section 2: Category A Audit (Renamed Parameters)

Parameters that were renamed and have code fallback paths (the code silently maps old name to new if present).

| Parameter (Legacy) | Modern Replacement | spectrum.yaml | att.yaml | steering.yaml | Status |
|--------------------|--------------------|---------------|----------|---------------|--------|
| `alpha_baseline` | `baseline_time_constant_sec` | Not present (modern used) | Not present (modern used) | N/A | MIGRATED |
| `alpha_load` | `load_time_constant_sec` | Not present (modern used) | Not present (modern used) | N/A | MIGRATED |
| `bad_samples` | N/A (code default) | N/A | N/A | Not present (code defaults to 8) | NOT A FALLBACK |
| `good_samples` | N/A (code default) | N/A | N/A | Not present (code defaults to 15) | NOT A FALLBACK |

**Explanation of "NOT A FALLBACK" status:** `bad_samples` and `good_samples` are not renamed legacy parameters. They are optional config keys that the code provides built-in defaults for (8 and 15 respectively). Their absence from config is normal behavior, not a legacy migration gap. The fallback code in `steering/daemon.py:421-422` is a standard `.get()` with default, not a legacy compatibility shim.

**Container evidence:**
- `grep` for `alpha_baseline`, `alpha_load`, `bad_samples`, `good_samples` across all ACTIVE config files on both containers returned zero matches
- Legacy params found only in INACTIVE files: `spectrum.yaml.bak`, `wan1.yaml`, `wan2.yaml`, `att.yaml.bak`, `steering_config_v2.yaml`

## Section 3: Category B Audit (Mode Flag)

Mode flag that gates dead code vs live code path in the steering daemon.

| Parameter | File | Value | Implication |
|-----------|------|-------|-------------|
| `cake_aware` | `steering.yaml` | `true` | `_update_state_machine_legacy()` is dead code -- never executed in production |

**Evidence:** Production `steering.yaml` on cake-spectrum has `cake_aware: true`. This means:
- `_update_state_machine_cake_aware()` is the ACTIVE code path
- `_update_state_machine_legacy()` is DEAD code -- never executes
- The `cake_aware` mode flag check in `steering/daemon.py:230` always takes the `true` branch
- **Gates Phase 68:** Safe to remove `_update_state_machine_legacy()` and the mode flag branching (LGCY-02)
- **Gates Phase 69:** RTT-only mode (`cake_aware: false`) disposition can be resolved (LGCY-07)

## Section 4: Repo vs Container Diff

| Config File | Container | Diff Result | Details |
|-------------|-----------|-------------|---------|
| `spectrum.yaml` | cake-spectrum | CLEAN | Production matches repo exactly |
| `att.yaml` | cake-att | CLEAN | Production matches repo exactly |
| `steering.yaml` | cake-spectrum | 3 differences | See below |

### steering.yaml differences (production vs repo)

```diff
69c69
<   dry_run: false  # VALIDATION MODE - logs only, no routing changes
---
>   dry_run: true  # VALIDATION MODE - logs only, no routing changes
75c75
<   enabled: true              # Set true to activate WAN zone signal
---
>   enabled: true               # Set true to activate WAN zone signal
79c79
<   wan_override: true         # When true, WAN RED alone can trigger failover
---
>   wan_override: false         # When true, WAN RED alone can trigger failover
```

**Analysis of differences:**

1. **`dry_run: false` (production) vs `dry_run: true` (repo):** Intentional operational tunable. Production has live steering enabled; repo preserves safe default for fresh deployments. This is Phase 71 (CONF-01) scope -- the plan will update the repo to match production.

2. **`enabled: true` whitespace difference (line 75):** Cosmetic only -- extra space in repo version. Not a functional difference.

3. **`wan_override: true` (production) vs `wan_override: false` (repo):** Intentional operational tunable. Production allows WAN RED alone to trigger failover; repo preserves conservative default. This may be Phase 72 (WANE-01) scope.

**Conclusion:** All 3 differences are intentional operational tunables or cosmetic whitespace, not legacy parameter issues. No remediation needed for LGCY-01.

## Section 5: Notable Findings (Non-blocking)

### 5.1 calibrate.py generates legacy format

`calibrate.py:562` generates configs with `alpha_baseline`/`alpha_load` (legacy parameter names) instead of `baseline_time_constant_sec`/`load_time_constant_sec`. This is a development/calibration tool, not a production config generator. Deferred to Phase 69 or 70 for cleanup.

### 5.2 Old config files in repo `configs/` directory

The following files in the repo `configs/` directory are obsolete and candidates for Phase 68 removal (LGCY-05):

| File | Contains Legacy Params | Notes |
|------|----------------------|-------|
| `spectrum_config.yaml` | `alpha_baseline`, non-FHS paths | Old format, superseded by `spectrum.yaml` |
| `att_config.yaml` | `alpha_baseline`, non-FHS paths | Old format, superseded by `att.yaml` |
| `spectrum_config_v2.yaml` | `alpha_baseline` | Intermediate version, superseded |
| `.obsolete/att_config_v2.yaml` | Already marked obsolete | In `.obsolete/` subdirectory |
| `dad_fiber_config.yaml` | `alpha_baseline`, non-FHS paths | ISP-specific template |
| `att_binary_search.yaml` | Calibration config | Calibration artifact |
| `spectrum_binary_search.yaml` | Calibration config | Calibration artifact |

### 5.3 Inactive config files on containers

Both containers retain old/backup config files that are not loaded by running daemons:
- cake-spectrum: `spectrum.yaml.bak`, `steering_config_v2.yaml`, `wan1.yaml`
- cake-att: `att.yaml.bak`, `wan2.yaml`

These are harmless (not loaded) but could be cleaned up during a future deployment maintenance window. Not blocking for any v1.13 phase.

## Section 6: Conclusion

### LGCY-01 Status: SATISFIED

Both containers are confirmed running with modern-only parameters. No legacy fallbacks are exercised in any ACTIVE configuration file.

**Evidence summary:**
- `spectrum.yaml`: Uses `baseline_time_constant_sec` and `load_time_constant_sec` (modern). Zero legacy params.
- `att.yaml`: Uses `baseline_time_constant_sec` and `load_time_constant_sec` (modern). Zero legacy params.
- `steering.yaml`: Uses `cake_aware: true` (modern path). No `bad_samples` or `good_samples` in config (code defaults apply, not legacy fallbacks).
- All 3 active configs verified via SSH dump + diff against repo configs.
- `grep` across all ACTIVE config files on both containers found zero legacy parameter names.

### Gate Status

| Gate | Status | Unlocked For |
|------|--------|--------------|
| Phase 68 (Dead Code Removal) | UNLOCKED | `cake_aware: true` confirmed -- `_update_state_machine_legacy()` is provably dead code |
| Phase 69 (Legacy Fallback Removal) | UNLOCKED | All active configs use modern params -- fallback code paths in `autorate_continuous.py:374-396` are never triggered |

### No Remediation Required

Scenario 1 confirmed: production configs are clean. No config edits or redeployments needed.

---
*Audit completed: 2026-03-11*
*Auditor: Claude Code (SSH evidence provided by operator)*
*Method: SSH dump + diff + grep on live containers*
