# Phase 240: Config + Validator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-15
**Phase:** 240-config-validator
**Areas discussed:** Consumer scope, Key shape/placement, fping-absent WARN, CFG-03 proof corpus

---

## Consumer Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Both now | Register + validate `measurement.backend` in autorate AND steering validators; key inert (absent→icmplib) until 242 wires steering's revived pinger | ✓ |
| Autorate-only now | Wire only autorate validator; steering key deferred to Phase 242 with the actual pinger revival | |
| Shared validator path | Factor a single shared backend-key validator used by both configs (more upfront refactor) | |

**User's choice:** Both now (Recommended)
**Notes:** Selection A (ratified Phase 238) makes steering a live RTT consumer. Key is additive/inert until 242, so wiring both validators now costs nothing behaviorally and lets 242/245 only consume an already-validated key.

---

## Key Shape / Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal: backend scalar only | Register just `measurement.backend` (enum icmplib\|fping); fping sub-params added by Phase 241 | ✓ |
| Stub full `measurement:` block | Define whole block shape now incl. placeholder fping keys so 241 doesn't re-touch the registry | |
| Flat key instead of block | Use flat `rtt_backend:` top-level key rather than nested `measurement:` block | |

**User's choice:** Minimal: backend scalar only (Recommended)
**Notes:** Block name `measurement:` matches CFG-01 literal dotted path and `/health` naming. fping params have no validation semantics until 241 builds the backend.

---

## fping-Absent WARN

| Option | Description | Selected |
|--------|-------------|----------|
| Probe + WARN, document env-dependence | `shutil.which('fping')` → non-gating WARN; documented as advisory (validator host may ≠ deploy host); authoritative absence-handling = Phase 242 fallback | ✓ |
| Validate value only; defer absence to runtime | 240 validates only the value; absence WARN moves entirely to 242 runtime factory | |
| Probe with override flag | Probe + WARN with `--assume-fping-present` suppression flag | |

**User's choice:** Probe + WARN, document env-dependence (Recommended)
**Notes:** Satisfies CFG-02 literally. WARN must be genuinely non-gating so a valid `fping` deployment passes even when validated on a box lacking the binary.

---

## CFG-03 Proof Corpus

| Option | Description | Selected |
|--------|-------------|----------|
| Both: real configs + fixture vectors | Validate committed real YAMLs unchanged (key absent → zero new warn/error) PLUS unit fixtures for 3 vectors (unknown→ERROR, fping+absent→WARN, absent→icmplib silent) | ✓ |
| Real configs only | Prove via real corpus; 3 vectors covered by inspection | |
| Fixture vectors only | Curated synthetic fixtures only; no run against real corpus | |

**User's choice:** Both: real configs + fixture vectors (Recommended)
**Notes:** Real configs prove no deployment breaks; fixtures prove branch logic deterministically. Registry requirement (D-04a): `measurement.backend` must be added to `KNOWN_AUTORATE_PATHS` (+ steering equivalent) so present-valid doesn't trip "unknown key".

---

## Claude's Discretion

- Exact `measurement:` schema nesting, the WARN `Severity` constant reused, the enum-validation helper, and test file layout.
- Whether the `icmplib|fping` enum is a shared constant vs duplicated across the two validators (shared preferred, not mandated).

## Deferred Ideas

- fping sub-params (reflectors, cadence, `-S` binding) — Phase 241.
- Backend factory + loud runtime fallback (FALL-01) — Phase 242.
- `/health` backend/source_ip attribution (HEALTH-01) — Phase 244.
- `--assume-fping-present` validator override flag — premature; revisit if false WARN proves noisy.
- `irtt` as a selectable backend — IRTT-MIG-01, future milestone.
- Reviewed-not-folded todo: `2026-06-04-evaluate-fping-as-wanctl-rtt-measurement-backend.md` — milestone driver, broader than 240.
