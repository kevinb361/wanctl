---
phase: 191-netlink-apply-timing-stabilization
plan: 05
subsystem: verification
tags: [verification, flent, manual, soak, safe]
requires:
  - phase: 191-netlink-apply-timing-stabilization
    provides: "Plans 01-04 merged plus green local regression gates"
provides:
  - "Focused and full-suite regression evidence on the current working tree"
  - "SAFE-03 and SAFE-04 diff proof artifact"
  - "ATT minimum-coverage flent A/B manifests and pre-soak snapshots for both WANs"
affects: [VALN-02, SAFE-03, SAFE-04, TIME-03, TIME-04]
tech-stack:
  added: []
  patterns: [manual A/B evidence capture, phase-local safe proof fallback, pre-soak health snapshot]
key-files:
  created:
    - .planning/phases/191-netlink-apply-timing-stabilization/191-05-SUMMARY.md
  modified:
    - .planning/phases/191-netlink-apply-timing-stabilization/191-VERIFICATION.md
key-decisions:
  - "Recorded ATT-only minimum coverage instead of pretending both-WAN coverage happened."
  - "Marked VALN-02 as not closed because RRUL aggregate download throughput regressed materially vs baseline."
  - "Preserved both strict milestone-wide SAFE-03 evidence and phase-local SAFE-03 evidence because they disagree."
patterns-established:
  - "When flent grade output is unavailable, compare ping p99 under load and state that fallback explicitly."
  - "Pre-soak TIME-03/TIME-04 evidence should include both overlap payloads and journal warning counts."
requirements-completed: [SAFE-04]
duration: 3h20m
completed: 2026-04-20
---

# Phase 191 Plan 05: Verification Summary

**Manual ATT A/B and pre-soak capture completed, and a fresh ATT rerun reinforced the negative ATT verdict; the phase still does not close cleanly because ATT validation regressed and strict SAFE-03 remains dirty outside Phase 191 scope**

## Performance

- **Duration:** 3h 20m
- **Completed:** 2026-04-20
- **Coverage achieved:** ATT only, minimum C9 coverage

## Accomplishments

- Repaired the previously red local regression gates and reran:
  - focused slice: `462 passed`
  - full suite: `4564 passed, 2 deselected`
- Refreshed `191-VERIFICATION.md` with strict and phase-local SAFE-03 proofs plus SAFE-04 proof.
- Recreated the missing ATT baseline on live `v1.38` and captured:
  - `rrul`
  - `tcp_12down`
  - `voip`
- Restored current service state on the cake-shaper VM and captured the matching ATT current-side flent set.
- Added two ATT RRUL repeats plus one fresh full ATT current-side rerun to distinguish sample noise from a persistent ATT issue.
- Added a Spectrum RRUL baseline/current discriminator run to check whether the throughput issue generalized across WANs.
- Ran two ATT root-cause probes:
  - ATT-only no-coalescing code probe
  - current code with ATT config restored to `v1.38` `irtt`/`fusion` settings
- Captured pre-soak `/health` overlap payloads and slow-apply journal slices for both Spectrum and ATT.

## A/B Outcome

- **Coverage level:** `minimum (one WAN)`
- **WAN tested:** `att`
- **Baseline manifest:** `/home/kevin/flent-results/phase191/baseline_v1.38/att/20260420-102214/manifest.txt`
- **Current manifest:** `/home/kevin/flent-results/phase191/p191_head/att/20260420-102710/manifest.txt`
- **VALN-02 verdict:** `FAIL`

Key ATT results:

- RRUL ping p99 improved: `74.42ms -> 68.21ms`
- RRUL aggregate download throughput regressed: `77.46 Mbps -> 62.06 Mbps`
- RRUL aggregate upload throughput stayed close: `14.65 Mbps -> 13.95 Mbps`
- `tcp_12down` stayed flat on throughput and improved on latency
- VoIP jitter and one-way delay improved sharply, with `0%` packet loss on both runs
- Fresh ATT rerun later in the session was worse, not better:
  - RRUL download `77.46 Mbps -> 56.09 Mbps`
  - RRUL upload `14.65 Mbps -> 10.27 Mbps`
  - `tcp_12down` download `74.00 Mbps -> 66.98 Mbps`
  - VoIP packet loss `0.0% -> 0.03%`
  - VoIP one-way delay p99 `29.79ms -> 35.70ms`

Follow-up discriminator:

- Spectrum RRUL did **not** reproduce the ATT pattern:
  - baseline `288.41 Mbps` down / `75.11ms` p99
  - current `402.20 Mbps` down / `68.15ms` p99
- This points to an ATT-specific regression signal or ATT-specific condition, not a broad cross-WAN regression.

Root-cause probe outcome:

- ATT no-coalescing probe did **not** recover RRUL throughput:
  - `60.59 Mbps` down vs `78.29 Mbps` baseline
- Current code with ATT config restored to `v1.38` values **did** recover RRUL throughput:
  - `78.92 Mbps` down vs `78.29 Mbps` baseline
- That strongly suggests the red ATT validation is driven by ATT config/runtime drift after `v1.38`, not by the narrow Phase 191 overlap instrumentation itself.

## Phase 191.1 Restored-Config Rerun

Phase 191.1 restored the two ATT config keys identified in the live probe by returning `irtt.server=104.200.21.31` and `fusion.enabled=true` under deploy commit `d49b91469b019e4f7f7398811b902aa816a0514a`. The follow-up rerun stopped before ATT or Spectrum flent capture because the restored reflector path at `104.200.21.31:2112` was unreachable, so no new ATT RRUL download measurement was produced against the `78.29 Mbps` v1.38 baseline and no Spectrum discriminator measurement was recorded. `VALN-02 verdict: BLOCKED (reflector_unreachable)` remains the authoritative outcome, and the closure path now depends on the phase-local SAFE-03 comparator per Phase 191.1 `D-05` while preserving the milestone-wide comparator as contextual debt per `D-06`.

## SAFE / Soak Evidence

- **SAFE-04:** pass, no new waits/locks/sleeps in the apply-path diff set
- **SAFE-03 strict `v1.38..HEAD`:** still dirty from older milestone work in `linux_cake.py`
- **SAFE-03 phase-local:** clean since phase start
- **Pre-soak files:**
  - `/tmp/phase191-presoak/spectrum_p191_health_pre_soak.json`
  - `/tmp/phase191-presoak/att_p191_health_pre_soak.json`
  - `/tmp/phase191-presoak/spectrum_slow_apply_pre_soak.txt`
  - `/tmp/phase191-presoak/att_slow_apply_pre_soak.txt`
- **TIME-03 / TIME-04:** partial evidence only; final closure still requires a 24-hour post-merge soak

## Issues Encountered

- The original remote backup tarball only preserved `/opt/wanctl`; it did not include `/etc/wanctl` or systemd units, so current-state restoration had to be completed by redeploying the current workspace.
- ATT baseline deployment from the `v1.38` tag reported health version `1.37.0`; the git ref used for the baseline was still the `v1.38` tag.
- Because the ATT RRUL download delta was materially negative, this summary does not claim a PASS just because latency improved.
- The fresh ATT rerun strengthened the failure case by adding throughput regressions outside RRUL plus non-zero VoIP loss.
- The ATT config-drift probe narrowed the likely cause to ATT-specific `irtt` / `fusion` config changes introduced after `v1.38`.

## Next Phase Readiness

- `SAFE-04` evidence is ready.
- `TIME-03` / `TIME-04` pre-soak evidence is ready for a later 24-hour comparison.
- Phase 191.1 rerun could not produce a valid throughput verdict (outcome_class: `reflector_unreachable`). Phase 191 remains blocked on this sub-cause. See `191-VERIFICATION.md` Phase 191.1 Restored-Config Rerun section for details.

---
*Phase: 191-netlink-apply-timing-stabilization*  
*Completed: 2026-04-20*
