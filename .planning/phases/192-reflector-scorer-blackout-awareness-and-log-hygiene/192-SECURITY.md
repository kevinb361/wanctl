---
phase: 192
slug: reflector-scorer-blackout-awareness-and-log-hygiene
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-24
---

# Phase 192 - Security

Per-phase security contract: threat register, accepted risks, and audit trail.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| kernel ICMP socket -> RTTMeasurement | Existing boundary; carrier-supplied timing remains untrusted and is consumed through the existing RTT measurement path. | RTT timing and per-host success/failure signals |
| WANController -> ReflectorScorer | Internal Python object boundary; Phase 192 adds a strict caller-side gate before scorer mutation. | `RTTCycleStatus` and per-host RTT success booleans |
| FusionHealer -> `_check_protocol_correlation()` | Internal Python object boundary; Phase 192 reads fusion actionability to select log cadence only. | Fusion enabled/healer state |
| Controller -> `/health` HTTP endpoint | Existing read-only observability endpoint; Phase 192 adds one integer download counter. | Health JSON counters |
| dev host -> journal-source host over SSH | Existing operator-controlled SSH boundary used by the soak helper. | Read-only journalctl output |
| flent test traffic | Existing validation harness boundary, unchanged by Phase 192. | Synthetic network validation traffic |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-192-01 | Tampering | `_should_skip_scorer_update` predicate | mitigate | Implemented as strict `successful_count == 0` in `src/wanctl/wan_controller.py`; tests cover zero-success, partial-success, and blocking fallback scorer behavior. | closed |
| T-192-02 | Repudiation | Scorer windows during blackout | accept | Blackout scoring suppression is intentional operational behavior; blackout logs remain in `measure_rtt()` for audit context. | closed |
| T-192-03 | Information disclosure | Plan 01 internal scorer gate | accept | No new external surface, auth path, or user input was introduced. | closed |
| T-192-04 | Denial of service | Seam gate | accept | The gate is O(1) branch logic on existing cycle status. No loops, I/O, or heavy allocation were added. | closed |
| T-192-05 | Elevation of privilege | Plan 01 internal scorer gate | accept | No privilege boundary is crossed. | closed |
| T-192-06 | Information disclosure | Stretched protocol-deprioritization cooldown | accept | The change reduces INFO log volume and preserves first-occurrence / transition logging; it does not expose new data. | closed |
| T-192-07 | Tampering | `fusion_not_actionable` predicate | mitigate | Implemented inline from live fusion state in `_check_protocol_correlation()`; tests cover `None`, disabled, `SUSPENDED`, `RECOVERING`, and `ACTIVE` cases plus latch isolation. | closed |
| T-192-08 | Repudiation | Protocol log volume reduction | accept | Ratio-transition latch semantics are preserved, and FusionHealer continues to emit its own transition logs. | closed |
| T-192-09 | Denial of service | Protocol-correlation hot path | accept | The added work is two attribute reads and a cooldown comparison. | closed |
| T-192-10 | Elevation of privilege | Plan 02 logging change | accept | No privilege boundary is crossed. | closed |
| T-192-11 | Information disclosure | Additive `/health` field | accept | `download.hysteresis.dwell_bypassed_count` is an integer operational counter with the same sensitivity class as existing hysteresis counters; upload is not expanded. | closed |
| T-192-12 | Tampering | `scripts/phase192-soak-capture.sh` | mitigate | Script uses `set -euo pipefail`, fail-fast env validation, `curl --fail --max-time 5`, `jq -e`, and env-driven WAN/endpoint configuration with no hardcoded defaults. | closed |
| T-192-13 | Repudiation | `192-VERIFICATION.md` soak evidence | mitigate | Raw timestamped side artifacts are preserved under `soak/{pre,post}/{wan}-raw/`; single-object `{wan}.json` files are derived summaries and `192-VERIFICATION.md` records the comparison. | closed |
| T-192-14 | Denial of service | Extra `/health` field compute | accept | One dict lookup plus `int()` coercion per download health render is negligible and outside the 50ms control loop. | closed |
| T-192-15 | Elevation of privilege | SSH-based journalctl read | accept | The helper uses the existing operator SSH boundary and does not create a new privilege path. | closed |
| T-192-16 | Information disclosure | `phase192-soak-capture.env.example` | accept | Production values appear only as comments, not script defaults; this matches the repository's documented public-safe operational context. | closed |

Status: open = unresolved; closed = mitigation verified or accepted risk documented.

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-192-02 | T-192-02 | Scorer blackout suppression is operational state, not evidentiary state; warning logs still document zero-success cycles. | Phase 192 security audit | 2026-04-24 |
| AR-192-03 | T-192-03 | No new external interface or user input was introduced by the internal scorer gate. | Phase 192 security audit | 2026-04-24 |
| AR-192-04 | T-192-04 | Added hot-path cost is constant-time branch logic only. | Phase 192 security audit | 2026-04-24 |
| AR-192-05 | T-192-05 | No privilege boundary is crossed. | Phase 192 security audit | 2026-04-24 |
| AR-192-06 | T-192-06 | Log hygiene reduces disclosure and preserves material transition logging. | Phase 192 security audit | 2026-04-24 |
| AR-192-08 | T-192-08 | Repudiation risk is bounded by preserved latch semantics and independent FusionHealer transition logs. | Phase 192 security audit | 2026-04-24 |
| AR-192-09 | T-192-09 | Added protocol-correlation work is negligible constant-time state inspection. | Phase 192 security audit | 2026-04-24 |
| AR-192-10 | T-192-10 | No privilege boundary is crossed. | Phase 192 security audit | 2026-04-24 |
| AR-192-11 | T-192-11 | The new health field is a non-sensitive counter and is download-only. | Phase 192 security audit | 2026-04-24 |
| AR-192-14 | T-192-14 | Health render overhead is a single lookup/coercion, not control-loop work. | Phase 192 security audit | 2026-04-24 |
| AR-192-15 | T-192-15 | The soak helper relies on the existing operator SSH boundary and grants no new authority. | Phase 192 security audit | 2026-04-24 |
| AR-192-16 | T-192-16 | The env example contains commented deployment examples only, consistent with the repo's public-safe operational documentation policy. | Phase 192 security audit | 2026-04-24 |

## Verification Evidence

| Threat | Evidence |
|--------|----------|
| T-192-01 | `src/wanctl/wan_controller.py` contains `_should_skip_scorer_update()` with `successful_count == 0`; `192-01-SUMMARY.md` records scorer seam tests and positive controls. |
| T-192-07 | `_check_protocol_correlation()` derives `fusion_not_actionable` from current fusion state; `192-02-SUMMARY.md` records the 11-case cooldown/latch regression class. |
| T-192-12 | `scripts/phase192-soak-capture.sh` contains `set -euo pipefail`, command checks, env validation, `curl --fail --max-time 5`, `jq -er`, and `ssh -o BatchMode=yes`. |
| T-192-13 | `soak/pre/*-raw/` and `soak/post/*-raw/` contain timestamped health, journal, and fusion-transition raw artifacts; `192-VERIFICATION.md` records pre/post derived JSON and comparison. |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-24 | 16 | 16 | 0 | Codex inline security audit |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-24
