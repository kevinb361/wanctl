# Phase 135: Upload Recovery Tuning - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 135-upload-recovery-tuning
**Areas discussed:** Parameters to test, Test methodology, Candidate values, Success threshold

---

## Parameters to Test

| Option | Description | Selected |
|--------|-------------|----------|
| step_up + factor_down | Two most impactful params. green_required=3 not suspected. 2 params keeps matrix manageable. | ✓ |
| All three | Comprehensive sweep. 12-27 flent runs. | |
| step_up only | Single param focus. 3-4 runs. | |

**User's choice:** step_up + factor_down

---

## Test Methodology

| Option | Description | Selected |
|--------|-------------|----------|
| 60s RRUL, 3 runs per config | Same proven v1.26 methodology. Apply via SIGUSR1. | ✓ |
| 120s RRUL, 2 runs per config | Longer runs, fewer reps. | |

**User's choice:** 60s RRUL, 3 runs per config

---

## Candidate Values: step_up_mbps

| Option | Description | Selected |
|--------|-------------|----------|
| 3, 4, 5 | Incremental from current 2. step_up=5 would be 13% of ceiling. | ✓ |
| 4, 6, 8 | More aggressive. step_up=8 = 21% of ceiling. | |

**User's choice:** 3, 4, 5

## Candidate Values: factor_down

| Option | Description | Selected |
|--------|-------------|----------|
| 0.80, 0.90 | One step each direction. 3x2 = 6 configs, 18 runs total. | ✓ |
| 0.80, 0.85, 0.90 | Include control. 3x3 = 9 configs, 27 runs. | |
| 0.90 only | Minimal, test DL winner on UL. 3 configs, 9 runs. | |

**User's choice:** 0.80, 0.90

---

## Success Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| 15%+ throughput OR 20%+ latency | v1.26 baseline: 3.9 Mbps. 15% = 4.5 Mbps. Latency threshold for non-throughput wins. | ✓ |
| Any measurable improvement | Low bar, cheap config change. | |
| Statistical significance | Claude determines noise floor. | |

**User's choice:** 15%+ throughput OR 20%+ latency improvement

---

## Claude's Discretion

- Test ordering (step_up sweep first vs interleaved)
- Whether to include baseline run in matrix
- Analysis document format
- Whether to capture DL metrics as regression check

## Deferred Ideas

None -- discussion stayed within phase scope
