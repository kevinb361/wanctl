---
phase: 197
slug: queue-primary-refractory-semantics-split-dl-cake-for-detecti
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-27
---

# Phase 197 Security Verification

**Phase:** 197 — queue-primary refractory semantics split DL CAKE for detection/arbitration  
**ASVS Level:** 1  
**Threats Open:** 0  
**Threats Closed:** 13/13  
**Verified:** 2026-04-27

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-197-01 | Tampering (controller-state desync) | mitigate | CLOSED | Stash captured before decrement at `src/wanctl/wan_controller.py:2754`; decrement follows at `src/wanctl/wan_controller.py:2755-2757`; selector includes the per-cycle stash in refractory classification at `src/wanctl/wan_controller.py:2695-2698`; non-refractory tests assert no false refractory state at `tests/test_phase_197_replay.py:143-155`. |
| T-197-02 | Information Disclosure (Phase 160 cascade-safety regression) | mitigate | CLOSED | Detection path is masked during refractory at `src/wanctl/wan_controller.py:2750-2757`; `download.adjust_4state` receives `cake_snapshot=dl_cake_for_detection` at `src/wanctl/wan_controller.py:2794-2801`; spy test asserts `cake_snapshot is None` at `tests/test_phase_197_replay.py:274-289`; no-touch evidence recorded in `197-01-SUMMARY.md:85` and `197-VERIFICATION.md:73`. |
| T-197-03 | Denial of Service (selector inconsistent reason vs primary) | mitigate | CLOSED | Valid refractory snapshot returns queue/`queue_during_refractory` at `src/wanctl/wan_controller.py:2707-2712`; invalid refractory snapshot returns rtt/`rtt_fallback_during_refractory` at `src/wanctl/wan_controller.py:2731-2738`; selector tests assert tuples at `tests/test_wan_controller.py:2885-2917`; renderer relays reason dict at `src/wanctl/health_check.py:779-786`. |
| T-197-04 | Spoofing (legacy MagicMock tests crash on new attr) | mitigate | CLOSED | Stash initialized false at `src/wanctl/wan_controller.py:692-696`; consumers use safe `getattr(..., False)` at `src/wanctl/wan_controller.py:3081-3084`, `src/wanctl/wan_controller.py:4230-4232`, and renderer default at `src/wanctl/health_check.py:786`. |
| T-197-05 | Repudiation (audit cannot distinguish refractory fallback) | mitigate | CLOSED | Distinct reason constants defined at `src/wanctl/wan_controller.py:94-95`; `/health` exposes `refractory_active` at `src/wanctl/wan_controller.py:4216-4232`; renderer defaults/relays at `src/wanctl/health_check.py:779-786`; health tests assert verbatim relay/default at `tests/test_health_check.py:4561-4610`. |
| T-197-06 | Elevation of Privilege (UL behavior change) | mitigate | CLOSED | DL-only metric emitted in DL block at `src/wanctl/wan_controller.py:3063-3091`; UL path remains `ul_cake` + `self.upload.adjust(... cake_snapshot=ul_cake)` at `src/wanctl/wan_controller.py:2759-2764` and `src/wanctl/wan_controller.py:2862-2865`; UL no-refractory metric test at `tests/test_wan_controller.py:2559-2588`; UL no-touch scan evidence in `197-02-SUMMARY.md:95`. |
| T-197-07 | Tampering (constants encoding map mutated) | mitigate | CLOSED | `ARBITRATION_PRIMARY_ENCODING = {"none": 0, "queue": 1, "rtt": 2}` remains unchanged at `src/wanctl/wan_controller.py:88`; verification evidence in `197-01-SUMMARY.md:86`. |
| T-197-08 | Tampering (metric value off-by-one) | mitigate | CLOSED | Metric is sourced from `refractory_active = getattr(self, "_dl_arbitration_used_refractory_snapshot", False)` and emitted as `1.0 if refractory_active else 0.0` at `src/wanctl/wan_controller.py:3081-3089`; tests assert 1.0/0.0 at `tests/test_wan_controller.py:2509-2557`. |
| T-197-09 | Elevation of Privilege (cascading control: refractory + healer bypass on single event) | mitigate | CLOSED | Refractory window guard resets streak/bypass at `src/wanctl/wan_controller.py:2823-2832`; refractory entry atomically resets `_healer_aligned_streak` at `src/wanctl/wan_controller.py:2871-2879`; D-12 tests cover reset/no-increment/RTT-veto unreachable at `tests/test_phase_197_replay.py:305-361`. |
| T-197-10 | Information Disclosure (audit drift between controller and predicate) | mitigate | CLOSED | Audit predicate accepts `queue_during_refractory` and buckets `rtt_fallback_during_refractory + refractory_active=true` at `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md:28-40`; metric classification includes refractory bucket at lines 65-71. |
| T-197-11 | Denial of Service (capture script omits refractory_active) | mitigate | CLOSED | Capture script extracts `refractory_active` with default false at `scripts/phase196-soak-capture.sh:219`, passes it with `--argjson` at line 240, and includes it in summary JSON at lines 262-268. |
| T-197-12 | Repudiation (raw vs aggregate categorical metric ambiguity) | mitigate | CLOSED | Audit doc mandates raw-only categorical metric filtering: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md:58-63`. |
| T-197-13 | Spoofing (UL refractory wiring accidentally modified) | mitigate | CLOSED | UL refractory wiring remains at `src/wanctl/wan_controller.py:2759-2764` and `src/wanctl/wan_controller.py:2880-2881`; upload adjust still consumes `ul_cake` at `src/wanctl/wan_controller.py:2862-2865`; UL no-touch/replay evidence recorded in `197-01-SUMMARY.md:85` and `197-02-SUMMARY.md:95`. |

## Accepted Risks

None.

## Transferred Risks

None.

## Unregistered Flags

None. `197-01-SUMMARY.md` has no explicit Threat Flags section and documents deviations/self-check; `197-02-SUMMARY.md:118-120` reports `Threat Flags: None` and says changed surfaces match T-197-08 through T-197-13.

## Notes

- Verification was limited to the provided threat register; no blind vulnerability scan was performed.
- Implementation files were read only. This file is the only artifact written by the security verification step.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-27 | 13 | 13 | 0 | gsd-security-auditor |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-27
