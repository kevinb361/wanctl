---
phase: 235
reviewers: [codex]
reviewed_at: 2026-06-12T14:51:07Z
plans_reviewed: [235-01-PLAN.md, 235-02-PLAN.md, 235-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 235

## Codex Review

**Summary**

The plans are directionally strong: tight scope, offline-first testing, explicit live-host gating, and good SAFE-16 discipline. The main gaps are not architectural; they are test-contract mismatches and a couple of operational edges that could let a correct implementation fail tests, or let a weak implementation pass. Overall I’d rate Phase 235 as **MEDIUM risk until tightened**, then **LOW-MEDIUM**.

**235-01: CLI + TOOL Tests**

**Strengths**
- Good use of the existing `BPCTL_UTIL` seam; executor-safe by default.
- Correctly rejects stale `sil-spare*` names and uses `att-modem spec-modem`.
- The CLI scope is right: bash wrapper, config-driven pairs, no controller path.
- `--yes` plus `--both-wan-confirm` matches the production risk.

**Concerns**
- **HIGH:** The fake `bpctl_util` design is not stateful. Tests like `on att-modem --yes` expect success after `set_bypass on`, but a canned `get_bypass="non-Bypass"` will make a correct read-back-asserting CLI fail.
- **HIGH:** The tests omit `get_bypass_slave` responses. Since the plan requires capability probing, most happy-path tests would fail unless the fake returns a non-empty slave.
- **MEDIUM:** TOOL-02 is under-tested: `disc` and `conn` behavior are mostly not covered.
- **MEDIUM:** TOOL-03 must treat “other pair already disconnected” as non-NIC, not only “other pair already bypassed.” The plan’s fake/test framing leans too much on `get_bypass`.
- **LOW:** `mark` only verifies flat-log append. It does not prove `logger` was invoked.

**Suggestions**
- Make the fake stateful per iface and verb, or allow sequential responses.
- Default fake `get_bypass_slave` to a valid paired iface.
- Add explicit tests for `disc --yes`, `disc` idempotency, `conn` idempotency, and configured-but-not-capable iface.
- Add a dual-WAN gate test where the other pair is `Disconnect` but not `Bypass`.
- Add a `LOGGER` seam or PATH-injected fake `logger` for `mark`.

**Risk Assessment**
**MEDIUM.** The implementation direction is safe, but the test plan currently has enough mismatches to create churn or false confidence.

**235-02: Baseline + Init Unit**

**Strengths**
- Good separation: `bpctl-silicom.service` owns module/device; `silicom-bypass-init.service` owns policy baseline.
- Correctly uses the documented double-negative string for `set_dis_bypass off`.
- Good static unit checks and no watchdog scope creep.
- Calling `silicom-bypass baseline` keeps one source of truth.

**Concerns**
- **HIGH:** Interface readiness polling is optional in Task 1. For a boot oneshot, it should be mandatory. `After=bpctl-silicom.service` proves device/module readiness, not necessarily that `att-modem` and `spec-modem` are ready for per-iface bpctl calls.
- **MEDIUM:** Reapplying persistent policy verbs every boot may write card policy repeatedly. If these map to EEPROM/NVRAM, read-before-set would be safer.
- **MEDIUM:** Unit ordering lists both cake-autorate and `wanctl@` units, which is fine, but no `Wants=` means ordering only applies when units are in the same transaction. That may be acceptable, but the plan should be explicit.
- **LOW:** `logger` failure during baseline could obscure whether the hardware mutation succeeded unless error handling is deliberately defined.

**Suggestions**
- Require bounded retry for each configured pair using `get_bypass_slave` or `ip link show` before applying baseline.
- Prefer read-current, set-only-if-mismatch, read-back-assert. This still satisfies BOOT-01 while reducing unnecessary card writes.
- Add a static or behavior test proving baseline touches both pairs and refuses when one pair never becomes capable.
- In docs/unit comments, clarify the ordering model: the init unit must be enabled alongside WAN services, not merely present.

**Risk Assessment**
**MEDIUM.** The service split is right, but boot race handling needs to be non-optional for this to be operationally solid.

**235-03: Deploy Seam + Docs + SAFE-16**

**Strengths**
- Keeps live-host actions behind an explicit operator checkpoint.
- Good install-if-absent behavior for `/etc/silicom-bypass.conf`.
- Correctly avoids enabling or starting the unit during deploy.
- SAFE-16 proof via the existing checker is the right posture.

**Concerns**
- **HIGH:** “Decoupled from the wanctl release/restart path” conflicts with current [scripts/deploy.sh](/home/kevin/projects/wanctl/scripts/deploy.sh:690) structure unless a true standalone mode is added. A normal flag inside the main flow still runs code/config/systemd deployment, verification, validation, and next-steps.
- **MEDIUM:** The runbook example `deploy.sh --with-silicom-bypass` is not valid for the current parser, which requires `wan_name target_host` except `--install-only`.
- **MEDIUM:** “Approving without running live steps is acceptable” weakens the roadmap criterion that the oneshot is proven after boot/manual run. If skipped, record it as an operator waiver, not as fully live-verified.
- **LOW:** The SAFE checker also enforces `configs/att.yaml` cleanliness, not only controller path. That is probably fine here, but worth noting because it is stricter than SAFE-16’s stated scope.

**Suggestions**
- Add a real standalone mode, e.g. `./scripts/deploy.sh --silicom-bypass-only cake-shaper`, handled before WAN validation and before normal deploy calls.
- If using an additive flag instead, document the full syntax and admit it runs the broader deploy path.
- Update dry-run output to include the Silicom path.
- In the checkpoint, distinguish “offline acceptance passed” from “live verification passed” or “live verification waived.”

**Risk Assessment**
**MEDIUM.** The safety intent is good, but deploy coupling is the biggest operational mismatch in the phase.

**Overall Risk**

**MEDIUM.** The phase is well scoped and avoids controller-path risk. Fix the fake harness, make interface readiness mandatory, and make the deploy seam truly standalone/operator-gated; after that, the plan is solid enough for execution.

---

## Consensus Summary

Single external reviewer (Codex) for this cycle — consensus is the Codex verdict itself.

### Agreed Strengths
- Tight phase scope: tooling/boot-guards only, no controller-path mutation; SAFE-16 discipline carried through all three plans.
- Offline-first testing via the `BPCTL_UTIL` seam; live-host actions kept behind explicit operator gates (`--yes`, `--both-wan-confirm`, deploy checkpoint).
- Correct service split (`bpctl-silicom.service` owns module/device; `silicom-bypass-init.service` owns policy baseline) with `silicom-bypass baseline` as single source of truth.

### Agreed Concerns
- **HIGH (235-01):** Fake `bpctl_util` is not stateful — canned `get_bypass` responses would fail a correct read-back-asserting CLI (e.g. `on att-modem --yes` after `set_bypass on`).
- **HIGH (235-01):** Test fixtures omit `get_bypass_slave` responses; capability probing would fail most happy-path tests unless the fake returns a non-empty slave.
- **HIGH (235-02):** Interface readiness polling is optional in Task 1 but must be mandatory for a boot oneshot — `After=bpctl-silicom.service` proves module/device readiness, not per-iface bpctl readiness.
- **HIGH (235-03):** "Decoupled from the wanctl release/restart path" conflicts with current `scripts/deploy.sh` structure unless a true standalone mode is added.
- **MEDIUM:** TOOL-02 under-tested (`disc`/`conn` coverage); TOOL-03 must treat Disconnect as non-NIC; repeated boot-time policy writes may hit card EEPROM/NVRAM (prefer read-before-set); ordering-only (no `Wants=`) unit relationship should be explicit; runbook `deploy.sh --with-silicom-bypass` example invalid for current parser; skipped live verification should be recorded as an operator waiver, not as verified.

### Divergent Views
None — single reviewer this cycle.
