# Phase 167 Research

## Goal
Detect the production regressions that mattered in v1.33 without relying on manual flent runs.

## Current Code Reality
- `src/wanctl/alert_engine.py` already provides bounded per-(type, wan) cooldown suppression, severity handling, and SQLite-backed alert persistence.
- `src/wanctl/wan_controller.py` already emits alerts for cycle-budget issues, sustained congestion, flapping, baseline drift, and WAN offline/recovery.
- `src/wanctl/health_check.py` and `src/wanctl/metrics.py` already expose bounded operator-visible state for burst and storage telemetry.
- Phase 166 proved the production issue is not “missing data.” The gap is converting those health/metrics signals into stable alert rules and operator-facing severity policy.

## Planning Decisions
- Reuse `AlertEngine`; do not invent a second alerting path.
- Detect latency regression from existing controller health/metrics state first, not from new persistent raw-series storage.
- Keep Phase 167 focused on alert logic, rule wiring, and validation. Do not broaden into new dashboards, CLI rewrites, or canary scripting.
- Bound alert chatter explicitly with cooldowns and sustained-condition checks, especially for burst-related signals.

## Likely Touchpoints
- `src/wanctl/wan_controller.py`
- `src/wanctl/health_check.py` only if alert-relevant health accessors need minor normalization
- `src/wanctl/metrics.py` only if a missing bounded metric blocks alert evaluation
- `tests/test_alert_engine.py`
- targeted alert/health tests around controller behavior

## Risks
- Over-alerting on ordinary evening jitter or low-signal burst counters.
- Baking flent-specific assumptions into production alert logic.
- Expanding Phase 167 into full operator-surface redesign, which belongs in Phase 169.

## Recommended Split
- `167-01`: implement sustained latency/burst alert rules and tests.
- `167-02`: validate healthy vs degraded behavior, cooldowns, and non-chatter contracts.
