# Phase 226: Baseline Capture + Threshold Lock + Snapshot A - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 226-baseline-capture-threshold-lock-snapshot-a
**Areas discussed:** GATE-01 threshold values, Tin-separation definition, Baseline capture method, Snapshot A scope + restore

---

## GATE-01 Threshold Values

### RRUL p99 latency-under-load regression tolerance
| Option | Description | Selected |
|--------|-------------|----------|
| 5% (inherit v1.44) | Reuse phase206-thresholds.json RRUL_P99_REGRESSION_PCT=5.0; v1.44 rollback gate the roadmap cites | ✓ |
| Tighter — 3% | Less tolerance; stricter accept bar; diverges from established gate | |
| Looser — 10% | More tolerance; weakens latency-first stance | |

**User's choice:** 5% (inherit v1.44)

### Daemon restart-rate + pressure-state transition-rate gates
| Option | Description | Selected |
|--------|-------------|----------|
| Inherit +10% relative | phase206 RESTART_RATE_INCREASE_PCT=10 + TRANSITION_RATE_INCREASE_PCT=10 vs baseline window | ✓ |
| Absolute caps | Any restart fails; fixed transition-rate ceiling; brittle on DOCSIS noise | |
| Tighter relative (+5%) | Same shape, half tolerance | |

**User's choice:** Inherit +10% relative

### Upload stability metric (new — no inherited definition)
| Option | Description | Selected |
|--------|-------------|----------|
| UL p99 + floor-churn | UL p99 regression ≤5% AND no increase in floor-hit-cycles/SOFT_RED dwell | ✓ |
| UL p99 latency only | Simpler; misses floor/SOFT_RED churn | |
| UL throughput floor only | Throughput-centric; weak on latency | |

**User's choice:** UL p99 + floor-churn

**Notes:** All three GATE-01 sub-decisions take the precedent-grounded recommended option. Numeric values land in a committed `phase226-thresholds.json` mirroring `scripts/phase206-thresholds.json`; literals must not be duplicated into prose.

---

## Tin-Separation Definition

### Metric for "useful non-BestEffort tin separation"
| Option | Description | Selected |
|--------|-------------|----------|
| Occupancy + delay gap | Marked lands in non-BE tin AND that tin shows lower per-tin queue delay than BE under load | ✓ |
| Delay gap only | Single number; doesn't confirm classification | |
| Occupancy only | Confirms classification but not latency benefit ("theater" risk) | |

**User's choice:** Occupancy + delay gap

### Separation magnitude
| Option | Description | Selected |
|--------|-------------|----------|
| Clear beyond noise | Gap must exceed baseline 3-run variance; honest given path noise unknown pre-baseline | ✓ |
| Quantified floor (≥X ms / ≥X%) | Hard number now; risks being arbitrary | |
| Directional only | non-BE ≤ BE; vulnerable to noise | |

**User's choice:** Clear beyond noise

**Notes:** Creates a deliberate rule-vs-derived-constant split: the decision rule ("gap > baseline noise band") is pre-registered at plan time; the concrete constant derives from the captured baseline 3-run spread. Still pre-registration, not reverse-fitting. Couples to baseline capture (must compute per-tin queue-delay run-to-run spread).

---

## Baseline Capture Method

### Load profile (must be reproduced verbatim in Phase 227)
| Option | Description | Selected |
|--------|-------------|----------|
| RRUL + unmarked refs | flent RRUL + unmarked-UDP + unmarked-bulk-TCP; pre-stages Phase 227 EF comparison | ✓ |
| flent RRUL only | Minimal; no matched unmarked baseline for 227 | |
| RRUL + bulk-TCP only | Skips unmarked-UDP realtime reference | |

**User's choice:** RRUL + unmarked refs

### Run count and duration
| Option | Description | Selected |
|--------|-------------|----------|
| 3 runs × 60s | phase198 precedent; 3-run spread supplies tin-separation noise band | ✓ |
| 5 runs × 60s | Tighter estimate; ~67% more capture time | |
| 1 run × 300s | No run-to-run spread; breaks noise-band method | |

**User's choice:** 3 runs × 60s

**Notes:** The 3-run spread is load-bearing for the tin-separation gate (D-06), not just for smoothing.

---

## Snapshot A Scope + Restore

### Capture wrapper approach
| Option | Description | Selected |
|--------|-------------|----------|
| New sibling wrapper | phase226-snapshot-a.sh reusing phase224 pattern; captures spectrum.yaml + tc qdisc spec-router/spec-modem + bridge nft | ✓ |
| Extend phase224 with --spectrum | One tool; couples two capture domains under SAFE-13 scrutiny | |
| Manual + committed MANIFEST | No script; not reproducible for 228 rollback | |

**User's choice:** New sibling wrapper

### Restore-verification rigor
| Option | Description | Selected |
|--------|-------------|----------|
| Dry-run verified | Reproduces spectrum.yaml byte-for-byte + apply-command identical to 228 rollback path; no prod CAKE-mode change | ✓ |
| Captured-and-trusted | Restore proven only if rollback fires in 228 | |
| Live restore drill | Flip to diffserv4 then restore — REJECTED: that's a candidate deploy, violates criterion 4 + SAFE-13 | |

**User's choice:** Dry-run verified

**Notes:** Live restore drill explicitly marked out of bounds for this phase (would be a candidate deploy).

---

## Claude's Discretion

- Evidence artifact layout/naming (mirror Phase 225 `evidence/` tree; `baseline-<UTC>` dir + MANIFEST for trivial 227 diffing).
- SAFE-13 boundary verification via reuse of `scripts/phase225-safe13-boundary-check.sh`.
- Spectrum health/state sampling cadence within the load window (pre/during/post per AB-02).

## Deferred Ideas

None expanded phase scope. Todo cross-reference (`todo.match-phase 226`, 8 matches) reviewed — none folded; rationale recorded in CONTEXT.md `<deferred>`. Notable: "Retest Spectrum diffserv4 wash" is the milestone thesis (227/228), not a 226 fold.
