---
phase: 209
slug: spectrum-config-migration-production-canary-and-docs
status: secured
asvs_level: 1
threats_total: 27
threats_closed: 27
threats_open: 0
updated: 2026-05-23
---

# Phase 209 — Security

Security audit verified the four Phase 209 `<threat_model>` registers from `209-01-PLAN.md` through `209-04-PLAN.md` against the implemented code, documentation, and execution evidence. No implementation files were modified during this audit.

## Summary

| Metric | Count |
|---|---:|
| Threats total | 27 |
| Threats closed | 27 |
| Threats open | 0 |
| Unregistered threat flags | 0 |

All four `## Threat Flags` sections in `209-01-SUMMARY.md` through `209-04-SUMMARY.md` state `None`; no unregistered flags were added.

## Threat Register Verification

| Threat ID | Category | Component | Disposition | Status | Evidence |
|---|---|---|---|---|---|
| T-209-01-01 | Denial of Service | `netlink_cake.validate_cake` / `linux_cake.validate_cake` | mitigate | CLOSED | Both backends normalize omitted wash to `False` only for `wash`: `src/wanctl/backends/netlink_cake.py:555-556`, `src/wanctl/backends/linux_cake.py:454-455`; tests passed in `209-01-SUMMARY.md:122-126`. |
| T-209-01-02 | Tampering / Spoofing | `build_cake_params` strict bool guard | mitigate | CLOSED | Strict `allow_wash is True` guard preserved and always-emits safe default: `src/wanctl/cake_params.py:149-182`; test coverage recorded in `209-01-SUMMARY.md:66-67`, `209-01-SUMMARY.md:122`. |
| T-209-01-03 | Information Disclosure | RuntimeError interface name in logs | accept | CLOSED | Accepted and justified in `209-01-PLAN.md:428`; no new secret surface because interface names are already in logs/health. |
| T-209-01-04 | Elevation of Privilege | `linux_cake_adapter.py` soft-signal preservation | mitigate | CLOSED | Hard-fail scoped inside backend validators; adapter intentionally unchanged per `209-01-SUMMARY.md:96-97`; validation confirmed empty diff at `209-01-SUMMARY.md:125`. |
| T-209-01-05 | Repudiation | SAFE-05 pin block drift | mitigate | CLOSED | Phase 209 SAFE-05 pins added and verified: `209-01-SUMMARY.md:71`, `209-VERIFICATION.md:27`. |
| T-209-02-01 | Tampering | `PHASE_209_ATT_REF` env override | mitigate | CLOSED | Process control closed by final evidence using anchor `6508d68`: `209-04-SUMMARY.md:89-102`, `task4b-evidence/20260522T233944Z/safe-closeout-rerun.md:28-32`. |
| T-209-02-02 | Denial of Service | Unknown mode flag rejection | mitigate | CLOSED | Unknown `-*` flags exit 2: `scripts/check-safe07-source-diff.sh:35-40`; tests recorded in `209-02-SUMMARY.md:81-84`, `209-02-SUMMARY.md:117-119`. |
| T-209-02-03 | Repudiation | Default-mode preservation | mitigate | CLOSED | Default SAFE-09 mode remains separate from ATT branch and passes final live gate: `scripts/check-safe07-source-diff.sh:126-203`, `209-04-SUMMARY.md:98-100`. |
| T-209-02-04 | Bypass via `--no-verify` | Operator skipping hook gate | accept | CLOSED | Accepted process risk documented in `209-02-PLAN.md:536`; explicit Task 4b gate evidence makes hooks non-authoritative: `209-04-SUMMARY.md:151-155`. |
| T-209-02-05 | Information Disclosure | First 20 lines of `att.yaml` diff on violation | accept | CLOSED | Accepted and justified in `209-02-PLAN.md:537`; `att.yaml` uses `${ROUTER_PASSWORD}` literal rather than stored secrets: `configs/att.yaml:22-31`. |
| T-209-02-06 | Tampering | `V144_ALLOWLIST_RE` regex | mitigate | CLOSED | Regex exists and fail-closed tests pass: `scripts/check-safe07-source-diff.sh:173-180`; verifier tests and final gates pass in `209-04-SUMMARY.md:91-100`. |
| T-209-03-01 | Information Disclosure | `docs/BRIDGE_QOS.md` / `CHANGELOG.md` | accept | CLOSED | Accepted as public-safe topology rationale in `209-03-PLAN.md:262`; reviewed docs/changelog contain no credentials: `docs/BRIDGE_QOS.md:1-73`, `CHANGELOG.md:14-27`. |
| T-209-03-02 | Tampering / Repudiation | CHANGELOG date placeholder | mitigate | CLOSED | Placeholder was finalized to a dated v1.44 heading: `CHANGELOG.md:14`; verification confirms committed changelog at `209-VERIFICATION.md:50`. |
| T-209-03-03 | Spoofing / misleading decision | `BRIDGE_QOS.md` decision tree | mitigate | CLOSED | Docs tell operators to keep default on transparent/marking-preserving links: `docs/BRIDGE_QOS.md:13-29`; load-bearing code rejects excluded `wash` unless strict `allow_wash` is true: `src/wanctl/cake_params.py:161-171`. |
| T-209-03-04 | Repudiation | TOPO-07 doc-vs-changelog drift | mitigate | CLOSED | CONFIGURATION and CHANGELOG link to BRIDGE_QOS instead of duplicating rationale: `docs/CONFIGURATION.md:387`, `CHANGELOG.md:18-19`; verification recorded at `209-03-SUMMARY.md:119-123`. |
| T-209-04-01 | Tampering | Two-snapshot ritual ordering | mitigate | CLOSED | Snapshot A rollback-clean evidence recorded: version `1.43.0`, `ceiling_mbps: 940` count 1, `allow_wash` count 0, `diffserv besteffort` count 0 in `task2-evidence/20260520T030313Z/*`; summarized in `209-VERIFICATION.md:29`. |
| T-209-04-02 | Denial of Service | Wash-readback production restart loop | mitigate | CLOSED | RuntimeError hard-fail exists only for real wash mismatch: `src/wanctl/backends/netlink_cake.py:562-572`, `src/wanctl/backends/linux_cake.py:456-464`; production journal check found zero wash/readback RuntimeErrors: `soak/20260521T222622Z/post-soak-verification-20260521T222622Z.stdout:1-5`. |
| T-209-04-03 | Predeploy-gate bypass | `scripts/phase206-predeploy-gate.sh` | mitigate | CLOSED | Binding pre/post-soak gates executed and passed; post-soak gate rc `0` and PASS lines in `soak/20260521T222622Z/post-soak-gate-20260521T222622Z.rc:1`, `soak/20260521T222622Z/post-soak-gate-20260521T222622Z.stderr:1-6`. |
| T-209-04-04 | Predeploy-gate bypass via env override | `PHASE_206_LOCAL_BASELINE_OVERRIDE` | mitigate | CLOSED | Production wrapper clears test-only override before invoking Python helper: `scripts/phase206-predeploy-gate.sh:188-194`. |
| T-209-04-05 | SAFE-08 verifier bypass | `--att-config-whitelist` ref | mitigate | CLOSED | Final SAFE-08 run explicitly used `6508d68` and passed: `task4b-evidence/20260522T233944Z/safe-closeout-rerun.md:28-32`; summary records same at `209-04-SUMMARY.md:95-102`. |
| T-209-04-06 | SAFE-09 verifier bypass via `--no-verify` | Closeout commit | mitigate | CLOSED | SAFE-09 was run explicitly after commit and passed, independent of hooks: `209-04-SUMMARY.md:91-100`; no manual diff substitute per `209-04-SUMMARY.md:151-155`. |
| T-209-04-07 | Misordered version + canary | Binary/config version skew | mitigate | CLOSED | Version/config checks passed: `configs/spectrum.yaml:44-45`, `configs/spectrum.yaml:68`; production soak rows all `1.44.0`/healthy in `soak/20260521T222622Z/quality-report-20260521T222622Z.json:17-24`. |
| T-209-04-08 | Information Disclosure | Snapshot tarballs in `/opt` | accept | CLOSED | Accepted in `209-04-PLAN.md:605`; snapshot paths and root-owned operational artifact context recorded in `task2-evidence/20260520T030313Z/metadata.env:1-5`. |
| T-209-04-09 | Operator confusion | Snapshot A vs Snapshot B | mitigate | CLOSED | Summary distinguishes Snapshot A rollback target from Snapshot B deploy evidence: `209-04-SUMMARY.md:56-58`; Snapshot A evidence paths recorded in `task2-evidence/20260520T030313Z/metadata.env:1-5`. |
| T-209-04-10 | Post-rollback verification skipped | Rollback grep checks | mitigate | CLOSED | PASS path did not require rollback; rollback checks remain specified in plan `209-04-PLAN.md:539-556`. No failed rollback path evidence required because Phase 206 gates passed. |
| T-209-04-11 | ATT silently affected | `configs/att.yaml` drift | mitigate | CLOSED | SAFE-08 gate and direct ATT diff passed: `209-04-SUMMARY.md:95-102`; `configs/att.yaml` has no Phase 209 `allow_wash`/`besteffort` changes in read evidence `configs/att.yaml:38-46`. |
| T-209-04-12 | Commit-shape drift | Task 4a closeout commit bundling | mitigate | CLOSED | Closeout commit was locked 5-file shape and verified: `209-04-SUMMARY.md:81-83`, `209-VERIFICATION.md:28`. |

## Accepted Risks

| Risk ID | Threat Ref | Rationale | Status |
|---|---|---|---|
| AR-209-01 | T-209-01-03 | Interface names in wash mismatch RuntimeErrors/logs are already exposed in existing warnings and `/health`; no credentials or new secret class. | CLOSED |
| AR-209-02 | T-209-02-04 | Hook bypass is not the security boundary; Task 4b runs SAFE gates explicitly after closeout. | CLOSED |
| AR-209-03 | T-209-02-05 | Diff preview may include `att.yaml` content, but the config stores password references as `${ROUTER_PASSWORD}`, not secrets. | CLOSED |
| AR-209-04 | T-209-03-01 | Bridge-QoS/changelog content is public-safe topology rationale and release metadata. | CLOSED |
| AR-209-05 | T-209-04-08 | Snapshot tarballs stay on cake-shaper under existing operational permissions; `/opt/wanctl` source contains no baked secrets. | CLOSED |

## Unregistered Flags

None. `209-01-SUMMARY.md`, `209-02-SUMMARY.md`, `209-03-SUMMARY.md`, and `209-04-SUMMARY.md` each report no additional threat flags.

## Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By | Notes |
|---|---:|---:|---:|---|---|
| 2026-05-23 | 27 | 27 | 0 | gsd-security-auditor | Read required plans, summaries, verification/review reports, implementation files, and evidence directories. Verified by declared dispositions only; no blind vulnerability scan performed. |

## Residual Notes

- `shellcheck` was unavailable during Plan 209-02 execution (`209-02-SUMMARY.md:101-104`), but bash syntax checks, pytest coverage, SAFE-08, and SAFE-09 final gates passed.
- `scripts/check-safe07-source-diff.sh` was corrected during Task 4b to include approved Phase 208 `src/wanctl/history.py` TOOL-02 drift; final verifier tests and both SAFE gates passed after the correction.
- No open threats remain.
