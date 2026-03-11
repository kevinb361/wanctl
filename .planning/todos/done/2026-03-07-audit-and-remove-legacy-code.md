---
created: "2026-03-07T11:32:03.940Z"
title: Audit and remove legacy code
area: general
files:
  - src/wanctl/steering/daemon.py:192-225,292-298,694-721
  - src/wanctl/autorate_continuous.py:287-335
  - src/wanctl/config_validation_utils.py:322-364
  - src/wanctl/steering_logger.py:291-304
  - configs/
---

## Problem

The codebase has 12 legacy patterns accumulated across 10 milestones. These add complexity, test surface, and confusion for no value if production configs have already migrated to modern parameter names.

### Config fallbacks (remove if production configs use modern names)
- Legacy state names: `SPECTRUM_GOOD`, `WAN1_GOOD`, `WAN2_GOOD` in `_is_current_state_good()`
- `cake_state_sources.spectrum` -> `primary` mapping in config loading
- `spectrum_download`/`spectrum_upload` queue name fallbacks
- `bad_threshold_ms`/`recovery_threshold_ms` RTT-only thresholds
- `bad_samples`/`good_samples` hysteresis params
- `floor_mbps` single-floor config in autorate_continuous.py
- Legacy config validation in config_validation_utils.py

### Dead code (safe to remove now)
- `_update_state_machine_cake_aware()` and `_update_state_machine_legacy()` — replaced by `_update_state_machine_unified()`, never called
- ISP-specific config files in `configs/` (obsolete v2 formats)

### Needs investigation
- Is legacy RTT-only mode (`cake_aware: false`) still used by any deployment?
- Is `log_state_progress_legacy()` in steering_logger.py still needed?

## Solution

1. **Audit production configs** on cake-spectrum and cake-att for old parameter names
2. **Remove dead code** first (state machine methods, obsolete configs) — safe regardless
3. **Remove config fallbacks** only after confirming production uses modern names
4. **Update tests** — remove legacy-mode test fixtures if mode is retired
5. Fits naturally in **Phase 53 (Code Cleanup)** — CLEAN-01 through CLEAN-07
