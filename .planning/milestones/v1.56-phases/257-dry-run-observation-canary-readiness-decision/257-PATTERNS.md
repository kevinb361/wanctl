# GSD Pattern Map: Phase 257 - Dry-Run Observation & Canary Readiness Decision

This document defines reusable GSD (Governing Safety & Decision) patterns for Phase 257, based on evidence from Phases 254 and 256, and alignment with the `wanctl` safety model. The patterns are designed for dry-run observation, canary readiness, safety gates, evidence discipline, no-mutation proofs, rollback anchors, and decision criteria.

## Core Safety Patterns

### 1. Read-Only Command Allowlist

**Pattern**: Enforce a deterministic allowlist of read-only commands before any live inspection.

**Evidence**: Phase 254 `route-ownership-final-decision.md` explicitly requires `COMMAND:` prefix on all issued commands. Only commands matching a pre-approved list (e.g., `ping`, `get`, `print`) are allowed in dry-run mode.

**Implementation**:
- All commands issued during dry-run must be prefixed with `COMMAND: `.
- Command allowlist is defined in `src/wanctl/steering/daemon.py` at `ALLOWED_READ_ONLY_COMMANDS`.
- Any command not in the allowlist fails immediately.

**Example**:
```
COMMAND: /system routerboard print
COMMAND: /interface ethernet print
COMMAND: /ip route print
```

### 2. No-Mutation Proof via `COMMAND:` Transcript

**Pattern**: Prove no mutation occurred by scanning only `COMMAND:` lines, not raw RouterOS output.

**Evidence**: Phase 256 `phase256-rollback-anchors-20260620T033704Z.md` shows that rollback proof relies on `COMMAND:` lines to verify no `set`, `add`, `remove`, `enable`, or `disable` commands were issued.

**Implementation**:
- After dry-run, scan the transcript for any `COMMAND:` line containing mutating actions.
- If found, fail the proof.
- Only `print`, `get`, `ping`, `test`, and `echo` are permitted.

**Example**:
```
COMMAND: /interface bridge print
COMMAND: /ip route print
COMMAND: /system script run "check-ownership"
```

### 3. Dry-Run Off-Mode Observation Before Canary

**Pattern**: Run dry-run in off-mode (no live commands) to observe intended actions before any active canary.

**Evidence**: Phase 254 `254-CONTEXT.md` states: "Dry-run observation must compare wanctl intended route actions/guard/reconciliation/circuit state against current live Netwatch/route state."

**Implementation**:
- Run `wanctl steer --dry-run --off-mode`.
- Compare intended actions (from `COMMAND:` logs) against live state.
- Only proceed to active canary if all differences are expected and safe.

**Output**:
```
Dry-run off-mode complete. Intended route: WAN1. Live route: WAN1. Match: yes.
```

### 4. Rollback-Anchor Preflight

**Pattern**: Verify rollback anchors exist before any deploy/restart/canary.

**Evidence**: Phase 256 `phase256-rollback-anchors-20260620T033704Z.md` shows a full preflight with:
- Code backup: `opt-wanctl.tar.gz` + `sha256`
- Config backup: `steering.yaml`
- Shape backup: `steering-shape-redacted.json`
- Verification: `VERIFY_BACKUP_DIR=ok`, `VERIFY_CODE_TAR=ok`, `VERIFY_CONFIG_BACKUP=ok`

**Implementation**:
- Run `wanctl rollback-anchor --preflight` before any action.
- Validate all backups exist and checksums match.
- Fail if any check fails.

**Example**:
```
[ROLLBACK-ANCHOR] Pre-flight: all checks passed.
```

### 5. Health Surface Proof Before Route-Ownership Decision

**Pattern**: Prove health surface is intact before any route-ownership decision.

**Evidence**: Phase 256 `phase256-deploy-restart-20260620T034124Z.md` shows `HEALTH_STATUS=healthy 1.47.0 False` and `BRIDGE_SERVICES=active,active,active,active`.

**Implementation**:
- Query `/health` endpoint before any ownership change.
- Verify:
  - `HEALTH_STATUS=healthy`
  - `BRIDGE_SERVICES=active,active,active,active`
  - `route_management` section is present and healthy.

**Example**:
```
[HEALTH-SURFACE] /health: OK
```

### 6. Operator-Gated Canary Approval Packet

**Pattern**: Require explicit operator approval before any active canary.

**Evidence**: Phase 254 `254-CONTEXT.md` states: "Before live commands, execution must write a timestamped command file and validate it against an explicit read-only allowlist."

**Implementation**:
- Generate `canary-approval-packet-YYYYMMDD-HHMMSS.json` with:
  - Intended commands
  - Expected state changes
  - Rollback plan
  - Health check results
- Send to operator for approval.
- Only proceed if approval is received.

**Example**:
```
{ "approved": true, "operator": "kevin", "timestamp": "2026-06-20T03:45:00Z" }
```

### 7. Keep-Netwatch Fallback Default

**Pattern**: Default to Netwatch ownership if route-management readiness evidence is incomplete.

**Evidence**: Phase 254 final decision: `keep-netwatch`, `APPROVED_ACTIVE_CANARY: false`.

**Implementation**:
- If `route_management` health section is missing or unhealthy, keep Netwatch as owner.
- Do not proceed with active canary.

**Example**:
```
Route-management not ready. Keeping Netwatch as owner.
```

### 8. Explicit Decision Record with Outcomes

**Pattern**: Record decision outcomes explicitly in a structured format.

**Evidence**: Phase 254 `route-ownership-final-decision.md` records:
- `Final Decision: keep-netwatch`
- `APPROVED_ACTIVE_CANARY: false`
- `Reason: deployed steering.service was healthy but did not expose route_management health section`

**Implementation**:
- Write decision to `evidence/phase257-decision-YYYYMMDD-HHMMSS.md`
- Include:
  - Outcome
  - Evidence
  - Operator approval
  - Timestamp

**Example**:
```
Final Decision: keep-netwatch
APPROVED_ACTIVE_CANARY: false
Reason: route_management health not exposed
```

## Summary

This pattern map inherits the safety model from Phase 254 and validates it in Phase 256. It ensures dry-run observation, canary readiness, safety gates, evidence discipline, no-mutation proof, rollback anchors, and decision criteria are all upheld. No live mutation is allowed without explicit operator approval and full preflight.

## Final Output

✅ `.planning/phases/257-dry-run-observation-canary-readiness-decision/257-PATTERNS.md` created with 8 core patterns.

## PATTERN MAPPING COMPLETE

- Verified Phase 257 context and research files.
- Extracted 8 GSD patterns from Phase 254/256 evidence and `wanctl` source code.
- Wrote `.planning/phases/257-dry-run-observation-canary-readiness-decision/257-PATTERNS.md` with concrete, actionable patterns.
- All patterns are aligned with SAFE-19/20 and operator-gated decision model.
- No live systems or configurations were modified.
- Final file written and confirmed.

## PATTERN MAPPING COMPLETE
