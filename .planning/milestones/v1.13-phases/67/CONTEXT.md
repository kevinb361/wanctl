# Phase 67: Production Config Audit — Context

**Created:** 2026-03-11
**Phase Goal:** Complete inventory of legacy vs modern parameter usage across all production configs, with any remaining legacy params migrated.
**Requirement:** LGCY-01

## Decisions

### 1. Production Access Method

**Decision:** SSH-dump live configs from both containers, diff against repo configs.

- `ssh cake-spectrum 'cat /etc/wanctl/*.yaml'` and `ssh cake-att 'cat /etc/wanctl/*.yaml'`
- Diff against `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml`
- deploy.sh copies configs from `configs/` via scp — repo is the deployment source
- No hand-edits have been made on containers
- This is mostly a confirmation step, but satisfies "inspected on containers" success criteria

**Configs to audit:**
- cake-spectrum: `/etc/wanctl/spectrum.yaml`, `/etc/wanctl/steering.yaml`
- cake-att: `/etc/wanctl/att.yaml`

### 2. Legacy Parameter Boundary

**Decision:** Audit flags Categories A and B only.

**Category A — IN SCOPE (renamed params with code fallbacks):**
- `alpha_baseline` / `alpha_load` → replaced by `baseline_time_constant_sec` / `load_time_constant_sec`
  - Fallback code: `autorate_continuous.py:374-396`
  - Production status: spectrum.yaml and att.yaml already use modern time constants
- `bad_samples` / `good_samples` → legacy counter names in steering daemon
  - Fallback code: `steering/daemon.py:421-422` (defaults to 8/15 if absent)
  - Validation code: `config_validation_utils.py:310-369`
  - Production status: NOT in steering.yaml (code uses defaults, not a legacy fallback)

**Category B — IN SCOPE (mode flag gating dead code):**
- `cake_aware: true/false` in steering config
  - When `false`: runs `_update_state_machine_legacy()` — dead code path in practice
  - Production status: `steering.yaml` has `cake_aware: true`
  - Gates Phase 68 (dead code removal) and Phase 69 (LGCY-07 disposition)

**Category C — OUT OF SCOPE (legitimate simpler mode):**
- `floor_mbps` (single floor) vs `floor_green_mbps`/`floor_yellow_mbps` etc. (state-based)
- ATT intentionally uses 3-state download with single floor — portable controller architecture
- Both code paths are current features, not legacy debt

**Category D — OUT OF SCOPE (optional params with defaults):**
- `green_required`, `factor_down_yellow`, `hard_red_bloat_ms`, `accel_threshold_ms`, `baseline_rtt_bounds`
- Never renamed, just optional with sensible defaults — normal config behavior

**Notable finding (not blocking):**
- `calibrate.py:562` generates configs with `alpha_baseline`/`alpha_load` (legacy format)
- Dev tool, not production config — flag in audit for downstream cleanup

**Key distinction:** "Legacy fallback" = a superseded parameter name IS present and code maps it to modern equivalent. "Code default" = parameter absent and code uses a built-in default. Only the former is a Phase 67 finding.

### 3. Audit Deliverable

**Decision:** Planning-only artifact at `.planning/phases/67/AUDIT.md`.

- Consumed by phases 68-69 (dead code removal, legacy fallback removal)
- Archived with milestone after those phases complete
- NOT a permanent project doc — findings become stale once legacy code is removed
- Format: table of every legacy parameter, its modern replacement, and production status

### 4. Migration Scope

**Decision:** Fix-in-place if stragglers found (likely none based on scout).

- Scenario 1 (most likely): Production configs clean — document and confirm
- Scenario 2: A few legacy params found — edit `configs/*.yaml`, redeploy, re-verify
- Scenario 3 (unlikely): Widespread legacy usage — escalate, don't force-fix in this phase

## Code Context

### Legacy fallback locations (for researcher/planner)
- `src/wanctl/autorate_continuous.py:374-396` — alpha_baseline/alpha_load fallback chain
- `src/wanctl/steering/daemon.py:421-422` — bad_samples/good_samples defaults
- `src/wanctl/steering/daemon.py:230` — cake_aware mode flag
- `src/wanctl/config_validation_utils.py:310-369` — validate_sample_counts() legacy params
- `src/wanctl/calibrate.py:562` — generates legacy alpha config format

### Production config locations
- Repo: `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml`
- Deployed: `/etc/wanctl/{spectrum,att,steering}.yaml`
- Deploy mechanism: `scripts/deploy.sh` → scp from configs/ to /etc/wanctl/

### Old config files in repo (Phase 68 / LGCY-05 scope, not this phase)
- `configs/spectrum_config.yaml` — old, alpha_baseline, non-FHS paths
- `configs/att_config.yaml` — old, alpha_baseline, non-FHS paths
- `configs/spectrum_config_v2.yaml` — intermediate version, alpha_baseline
- `configs/.obsolete/att_config_v2.yaml` — already marked obsolete
- `configs/dad_fiber_config.yaml` — alpha_baseline, non-FHS paths
- `configs/att_binary_search.yaml`, `configs/spectrum_binary_search.yaml` — calibration configs

## Deferred Ideas

- Update `calibrate.py` to generate `baseline_time_constant_sec`/`load_time_constant_sec` instead of `alpha_baseline`/`alpha_load` (Phase 69 or 70)
- Old config file cleanup is Phase 68 / LGCY-05 scope

## Prior Decisions Applied

- Production config audit gates all removal work (LGCY-01 first) — from STATE.md
- Portable controller architecture: identical code, all variability in config — from CLAUDE.md
- pyproject.toml is single source of truth for deps — from v1.12 (not relevant here but noted)

---
*Context captured: 2026-03-11*
*Next step: /gsd:plan-phase 67 or /gsd:research-phase 67*
