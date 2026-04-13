---
phase: 173-clean-deploy-canary-validation
verified: 2026-04-13T19:22:39Z
status: verified
score: 3/3 must-haves verified
re_verification:
  previous_status: not_applicable
  previous_score: not_applicable
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 173: Clean Deploy & Canary Validation Verification Report

**Phase Goal:** "Production is running v1.35 with version bump and canary confirms all services healthy" ([.planning/ROADMAP.md:34](/home/kevin/projects/wanctl/.planning/ROADMAP.md:34))
**Verified:** 2026-04-13T19:22:39Z
**Status:** verified
**Re-verification:** No - first verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | deploy.sh completes without errors and deployed version reports v1.35.0 | ✓ VERIFIED | Phase 173 first established the canonical `1.35.0` version bump in the three release files ([173-01-SUMMARY.md:44](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:44), [.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:46](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:46)). The Spectrum deploy then fixed the deploy verifier defect in-flight and confirmed production health returned `version: 1.35.0` after restart ([173-02-SUMMARY.md:38](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:38), [.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:39](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:39), [.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:44](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:44)). The ATT rollout separately confirmed `version: 1.35.0` and `storage: ok` on the second WAN ([173-03-SUMMARY.md:38](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:38), [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:44](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:44)). |
| 2 | canary-check.sh returns exit 0 for Spectrum and ATT services | ✓ VERIFIED | The final production gate ran `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` and recorded `Errors: 0`, `Warnings: 0`, exit code `0`, after Spectrum, ATT, and `steering.service` were active ([173-03-SUMMARY.md:39](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:39), [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:48](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:48), [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:59](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:59)). |
| 3 | Per-WAN metrics DB split is live in production | ✓ VERIFIED | Spectrum production validation recorded `/var/lib/wanctl/metrics-spectrum.db` mtime advancing from `1776018164` to `1776018168` after deploy ([173-02-SUMMARY.md:39](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:39), [.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:48](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:48)). ATT validation then confirmed `metrics-att.db` mtime advanced and listed both `/var/lib/wanctl/metrics-spectrum.db` and `/var/lib/wanctl/metrics-att.db` as present under `/var/lib/wanctl` ([173-03-SUMMARY.md:38](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:38), [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:45](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:45)). |

**Score:** 3/3 truths verified

## Requirements Coverage

| Requirement | Source Plan IDs | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `DEPL-01` | 173-01, 173-02, 173-03 | A clean `deploy.sh` run deploys v1.35 with version bump, and canary-check.sh returns exit 0 on all services | ✓ SATISFIED | Requirement definition in [.planning/REQUIREMENTS.md:18](/home/kevin/projects/wanctl/.planning/REQUIREMENTS.md:18). Version bump provenance comes from [.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:44](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:44) and [.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:46](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-01-SUMMARY.md:46). Production deploy and Spectrum verification are recorded at [.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:38](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:38) and [.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:44](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:44). Final dual-WAN canary exit-0 evidence is recorded at [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:39](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:39) and [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:59](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:59). |

## Behavioral Spot-Checks

| Behavior | Command | Observed Result | Status |
| --- | --- | --- | --- |
| Final production canary across both WANs plus steering | `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0` | exit `0`, `Errors: 0`, `Warnings: 0` ([173-03-SUMMARY.md:39](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md:39)) | ✓ PASS |

## Gaps Summary

None. DEPL-01 is fully satisfied by recorded production evidence. Phase 176 separately tracks the `deploy.sh` false-negative verifier fix as an alignment concern, not a DEPL-01 gap ([.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:38](/home/kevin/projects/wanctl/.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md:38), [.planning/ROADMAP.md:76](/home/kevin/projects/wanctl/.planning/ROADMAP.md:76)).

---

_Verified: 2026-04-13T19:22:39Z_
_Verifier: Claude (gsd-planner, Phase 175)_
