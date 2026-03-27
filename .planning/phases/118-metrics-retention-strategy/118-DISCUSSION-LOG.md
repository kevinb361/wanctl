# Phase 118: Metrics Retention Strategy - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-27
**Phase:** 118-metrics-retention-strategy
**Areas discussed:** Retention config structure, Validation behavior, Prometheus-compensated mode

---

## Retention Config Structure

### Q1: Unified vs separate downsample/delete thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Unified | Each `*_age_seconds` controls both downsampling AND deletion for that tier | |
| Separate | Keep downsampling thresholds separate, add distinct retention/deletion thresholds | |
| You decide | Claude picks based on code complexity and operator simplicity | ✓ |

**User's choice:** You decide
**Notes:** None

### Q2: Backward compatibility for `storage.retention_days`

| Option | Description | Selected |
|--------|-------------|----------|
| Deprecate and translate | Old `retention_days` auto-translates to new format with deprecation warning (uses existing `deprecate_param()` pattern) | |
| Break cleanly | Remove `retention_days`, require new format with clear error | |
| You decide | Claude picks based on production safety and migration friction | ✓ |

**User's choice:** You decide
**Notes:** None

### Q3: YAML key naming

| Option | Description | Selected |
|--------|-------------|----------|
| Locked | Use exactly `raw_age_seconds`, `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds` from roadmap | |
| Flexible | Claude can rename to match codebase conventions as long as same granularities are configurable | |
| You decide | Claude picks what fits the existing schema style | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Validation Behavior

### Q4: When should cross-section validation fire?

| Option | Description | Selected |
|--------|-------------|----------|
| Config load only | Reject at startup if retention < lookback. Fail-fast, no runtime overhead | |
| Config load + SIGUSR1 reload | Same rejection, also re-validates on hot reload | |
| Config load + runtime warning | Accept config but log WARNING each tuning cycle if data insufficient | |
| You decide | Claude picks based on codebase patterns and safety | ✓ |

**User's choice:** You decide
**Notes:** Hard constraint: RETN-02 requires tuner data must never be silently broken

### Q5: Should validation account for persisted tuner `lookback_hours`?

| Option | Description | Selected |
|--------|-------------|----------|
| YAML only | Validate against declared config only | |
| Persisted value | Read `tuning_params` at startup, validate against larger of YAML or persisted lookback | |
| You decide | Claude picks based on safety and complexity trade-off | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Prometheus-Compensated Mode

### Q6: Which tiers get shortened?

| Option | Description | Selected |
|--------|-------------|----------|
| All tiers compressed | Raw stays 1h, but 1m/5m/1h all shortened. Maximum disk savings | |
| Only final retention | Keep downsampling tiers same, just shorten overall cleanup horizon | |
| You decide | Claude picks based on disk usage breakdown and tuner data safety | ✓ |

**User's choice:** You decide
**Notes:** None

### Q7: Preset profile vs validation modifier?

| Option | Description | Selected |
|--------|-------------|----------|
| Presets | `prometheus_compensated: true` activates curated retention profile. Operator doesn't think about numbers | |
| Modifier | Boolean that relaxes validation constraints so operators can set shorter thresholds | |
| You decide | Claude picks based on operator UX | ✓ |

**User's choice:** You decide
**Notes:** None

---

## Claude's Discretion

All 7 decisions deferred to Claude's judgment:
- D-01: Unified vs separate downsample/delete thresholds
- D-02: Backward compatibility strategy for `retention_days`
- D-03: YAML key naming conventions
- D-04: Validation timing (load, reload, runtime)
- D-05: Persisted tuner value in validation
- D-06: Prometheus-compensated tier scope
- D-07: Prometheus-compensated preset vs modifier

## Deferred Ideas

None -- discussion stayed within phase scope
