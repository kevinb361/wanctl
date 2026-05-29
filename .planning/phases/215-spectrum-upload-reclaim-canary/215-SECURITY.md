---
phase: 215
slug: spectrum-upload-reclaim-canary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-29
verified: 2026-05-29
---

# Phase 215 — Security

Per-phase security contract: threat register, accepted risks, and audit trail for the Spectrum upload reclaim canary.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| deployed YAML over SSH -> gate preflight | Gate validates the live Spectrum upload ceiling before scoring a candidate leg. | Deployed config value, no secrets emitted |
| Flent artifact -> extractor/gate | Measurement artifacts feed latency and upload-throughput scoring. | Untrusted measurement JSON |
| leg-A baseline -> derived thresholds | Same-session baseline determines pass/fail bounds. | Latency/throughput metrics |
| production host -> evidence repo | Snapshot/deploy/rollback proof crosses from `cake-shaper` into committed artifacts. | Redacted config/state/health/DB/log evidence |
| repo config -> deployed config | Single upload ceiling canary crosses into the live 24/7 controller. | `continuous_monitoring.upload.ceiling_mbps` |
| gate verdict/exit code -> rollback branch | Nonzero gate outcomes must not skip rollback handling. | `verdict.json` and captured rc |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status | Evidence |
|-----------|----------|-----------|-------------|------------|--------|----------|
| T-215-01 | Tampering | gate verdict from stale deployed config | mitigate | SSH deployed-ceiling preflight aborts when loaded ceiling differs from expected. | closed | `scripts/phase215-reclaim-gate.sh`; clean code review |
| T-215-02 | Information Disclosure | gate script / evidence scaffold | mitigate | Gate reads config keys only; evidence scaffold contains no secret material. | closed | `215-01-SUMMARY.md`; clean evidence secret scans |
| T-215-03 | Spoofing/Repudiation | collapsed or malformed measurement scored pass | mitigate | Extractor and gate fail closed; collapsed windows and invalid metrics produce `void`/abort, not pass. | closed | `scripts/phase214-extract.py`; `scripts/phase215-reclaim-gate.sh`; `evidence/verdict.json` |
| T-215-04 | Denial of Service | tests consuming live production endpoint | accept | Tests are offline; live sampling occurred only in approved Plan 03 against read-only `/health`. | closed | `215-01-SUMMARY.md`; `215-03-SUMMARY.md` |
| T-215-05 | Information Disclosure | Snapshot A evidence | mitigate | Only `.redacted.*` artifacts committed; secret/placeholder grep passed. | closed | `evidence/snapshot-a/`; `215-02-SUMMARY.md` |
| T-215-06 | Tampering | accidental production mutation during Snapshot A | mitigate | Snapshot A used read-only `sudo -n cat`, readonly SQLite, and bound `/health`; no deploy/restart/traffic. | closed | `evidence/snapshot-a/*/MANIFEST.md` |
| T-215-08 | Tampering | stale loopback health baseline | mitigate | Snapshot used bound endpoint `10.10.110.223:9101`, not loopback. | closed | Snapshot A manifest and health artifact |
| T-215-09 | Tampering | wrong or multi-knob production mutation | mitigate | Semantic YAML delta asserted exactly one changed leaf before deploy. | closed | `215-REPORT.md`; `215-03-SUMMARY.md` |
| T-215-10 | Tampering/Repudiation | un-restarted daemon serving stale ceiling | mitigate | Mandatory restart plus DB row and CAKE `20000kbit` proof before leg-B. | closed | `evidence/leg-b-ceiling20/deploy-proof/` |
| T-215-11 | Spoofing | false pass keeping a regressing change | mitigate | Gate preflight, leg-A-derived bounds, numeric VOID, and rollback on non-pass. | closed | `evidence/verdict.json`; `215-REPORT.md` |
| T-215-12 | Information Disclosure | deploy/leg/verdict evidence | mitigate | D-08 redaction and evidence-wide secret scan passed. | closed | `215-03-SUMMARY.md`; `215-VERIFICATION.md` |
| T-215-13 | Denial of Service | live WAN degraded without clean recovery | mitigate | Snapshot A dependency, approval checkpoint, bounded-VOID safe rollback, DB/canary-check proof. | closed | `evidence/rollback-ceiling18/`; `215-REPORT.md` |
| T-215-14 | Elevation of Privilege | new network-facing surface | accept | No wanctl endpoint/auth path added; canary changed an existing YAML value and polled existing `/health`. | closed | `215-03-SUMMARY.md` |
| T-215-15 | Tampering/Repudiation | nonzero gate exit short-circuits rollback | mitigate | Exit-code contract pinned; Plan 03 captured rc and branched on parsed `verdict.json`. | closed | `scripts/phase215-reclaim-gate.sh`; `evidence/gate-rc.txt`; `215-REPORT.md` |
| T-215-16 | Tampering/Repudiation | over-broad revert discards worktree edits | mitigate | Rollback documented and executed as targeted single-key restore, not `git checkout`. | closed | Snapshot A manifest; `215-REPORT.md` |
| T-215-17 | Tampering | unrelated worktree drift deployed with canary | mitigate | `src/wanctl/` asserted clean and `configs/spectrum.yaml` allowlisted to the single ceiling change. | closed | `215-REPORT.md`; `215-03-SUMMARY.md` |
| T-215-18 | Repudiation | nonzero gate exit skips rollback under `set -e` | mitigate | Gate invoked under `set +e`, rc captured, verdict branch always ran. | closed | `evidence/gate-rc.txt`; `evidence/verdict.json`; rollback proof |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-215-04 | T-215-04 | Offline tests avoid live endpoint load; approved live sampling was limited to Plan 03. | Phase plan | 2026-05-29 |
| AR-215-14 | T-215-14 | No new wanctl endpoint or auth path was added; existing surfaces only. | Phase plan | 2026-05-29 |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-29 | 18 | 18 | 0 | gsd-security-auditor |

## Additional Notes

- `scripts/libreqos-cli.mjs` was committed after Phase 215 execution as a non-gating corroboration tool. It embeds only public LibreQoS endpoints, no local credentials/secrets, and does not touch the wanctl production control path.
- Code review was clean after the fix loop: `215-REVIEW.md` status `clean`, 0 critical/warning/info findings.

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-29
