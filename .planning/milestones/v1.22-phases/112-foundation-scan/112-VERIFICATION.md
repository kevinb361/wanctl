---
phase: 112-foundation-scan
verified: 2026-03-26T23:30:00Z
status: human_needed
score: 5/5 must-haves verified (with one finding requiring human disposition)
human_verification:
  - test: "Confirm /etc/wanctl/secrets at 0640 satisfies FSCAN-04 intent"
    expected: "Requirement says 0600; production is 0640 (root:wanctl group-readable). If 0640 is accepted as correct, REQUIREMENTS.md FSCAN-04 description should be updated to match actual architecture."
    why_human: "The requirement text says '0600' but implementation was 0640 with technical justification. Automated checks cannot determine whether the requirement should be updated or the permission should be changed."
  - test: "Disposition of requests CVE-2026-25645 (MEDIUM, 4.4)"
    expected: "requests 2.32.5 has CVE-2026-25645 (MEDIUM, 4.4 CVSS) with a fix at 2.33.0. wanctl does not call extract_zipped_paths(). Operator should decide: upgrade to requests 2.33.0, or formally accept risk. This was not documented in 112-01-findings.md."
    why_human: "CVE was published 2026-03-25 and was available at scan time (modified 2026-03-26T15:13 UTC, scan ran ~22:24 UTC) but was not captured in the findings doc. MEDIUM severity with available fix warrants explicit operator disposition."
---

# Phase 112: Foundation Scan Verification Report

**Phase Goal:** All mechanical scanning tools have run and produced actionable inventories that unblock later phases
**Verified:** 2026-03-26T23:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                           | Status     | Evidence                                                                                                                                      |
| --- | ----------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | pip-audit reports zero critical/high CVEs in all Python dependencies                           | VERIFIED   | All 3 current CVEs are LOW/MEDIUM: pip (LOW 2.0), pygments (MEDIUM 4.8/LOW 3.3), requests (MEDIUM 4.4). None are HIGH or CRITICAL.           |
| 2   | Unused dependencies identified by deptry and removed from pyproject.toml                       | VERIFIED   | cryptography and pyflakes removed; grep confirms absence. uv sync completed. deptry output documented in 112-01-findings.md.                 |
| 3   | Dead code inventory from vulture exists as a structured report (identification only, no removals) | VERIFIED   | 112-04-findings.md exists with required sections. .vulture_whitelist.py (187 lines, 68 entries). git diff confirms zero source file deletions. |
| 4   | File permissions on /etc/wanctl/secrets (0600), state dirs (0750), and log dirs (0750) verified | PARTIAL    | State dir 0750 PASS, log dir 0750 PASS. secrets is 0640 (not 0600) — documented as architecturally correct (wanctl group must read). Needs human disposition on requirement text vs implementation. |
| 5   | Ruff expanded rule set (C901/SIM/PERF/RET/PT/TRY/ARG/ERA) enabled with findings triaged       | VERIFIED   | All 8 rule prefixes present in pyproject.toml [tool.ruff.lint] select. ruff check src/ tests/ exits 0. mccabe max-complexity=20 configured.  |

**Score:** 4/5 truths fully verified, 1 PARTIAL (human disposition needed on secrets permission spec)

---

## Required Artifacts

### Plan 01 Artifacts

| Artifact                                             | Expected                                                         | Status    | Details                                                                    |
| ---------------------------------------------------- | ---------------------------------------------------------------- | --------- | -------------------------------------------------------------------------- |
| `pyproject.toml`                                     | Cleaned dependency list (cryptography removed, pyflakes removed) | VERIFIED  | cryptography absent (grep returns 0), pyflakes absent from dep declarations |
| `.planning/phases/112-foundation-scan/112-01-findings.md` | 4 sections: pip-audit, deptry, pytest-deadfixtures, Log Rotation | VERIFIED  | All 4 sections present and substantive                                     |

### Plan 02 Artifacts

| Artifact                                             | Expected                                                           | Status    | Details                                                                            |
| ---------------------------------------------------- | ------------------------------------------------------------------ | --------- | ---------------------------------------------------------------------------------- |
| `.planning/phases/112-foundation-scan/112-02-findings.md` | "## File Permissions (FSCAN-04)" and "## systemd Security Assessment (FSCAN-05)" | VERIFIED  | Both sections present. 31 items audited. 4 service units assessed with exposure scores. |

### Plan 03 Artifacts

| Artifact                                             | Expected                                                   | Status    | Details                                                                            |
| ---------------------------------------------------- | ---------------------------------------------------------- | --------- | ---------------------------------------------------------------------------------- |
| `pyproject.toml`                                     | C901 in [tool.ruff.lint] select                            | VERIFIED  | All 8 new rule prefixes present, max-complexity=20, per-file-ignores for 4 high-complexity files |
| `.planning/phases/112-foundation-scan/112-03-findings.md` | Sections: Summary, Autofix Changes, Suppressed Rules, Deferred Findings, Complexity Baseline | VERIFIED  | All required sections present (Complexity Baseline is a subsection under Deferred Findings) |

### Plan 04 Artifacts

| Artifact                                             | Expected                                                             | Status    | Details                                                                    |
| ---------------------------------------------------- | -------------------------------------------------------------------- | --------- | -------------------------------------------------------------------------- |
| `.vulture_whitelist.py`                              | min 10 lines, covers RouterOS/routeros_ssh/LinuxCakeAdapter/_reload_fusion_config/_reset_instance | VERIFIED  | 187 lines, 68 entries across 10 categories. All 5 critical entries confirmed. |
| `.planning/phases/112-foundation-scan/112-04-findings.md` | Sections: Summary, False Positives Validated, Likely Dead Code, Entry Point Coverage | VERIFIED  | All required sections present. No Removal Policy stated explicitly.        |

---

## Key Link Verification

| From                                  | To                             | Via                                          | Status   | Details                                                                                              |
| ------------------------------------- | ------------------------------ | -------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| deptry scan                           | pyproject.toml                 | cryptography and pyflakes removed            | WIRED    | grep confirms both absent from dependency declarations                                               |
| SSH to cake-shaper (10.10.110.223)    | Production VM audit data       | ssh kevin@10.10.110.223                      | WIRED    | SSH access confirmed live; state dir 0750, log dir 0750 verified in real time                       |
| pyproject.toml [tool.ruff.lint]       | ruff check output              | Rule selection determines findings           | WIRED    | ruff check src/ tests/ exits 0 with all 14 rule categories active                                   |
| .vulture_whitelist.py                 | vulture scan                   | Whitelist suppresses known false positives   | WIRED    | .vulture_whitelist.py present, parseable; 68 false positive entries                                 |
| PITFALLS.md checklist                 | vulture findings               | All 15 "looks dead but isn't" patterns validated | WIRED    | All 15 patterns documented in 112-04-findings.md False Positives Validated table                    |

---

## Data-Flow Trace (Level 4)

Not applicable. Phase 112 produces analysis artifacts (findings docs, pyproject.toml config, whitelist file), not components that render or transform dynamic runtime data.

---

## Behavioral Spot-Checks

| Behavior                                      | Command                                          | Result               | Status  |
| --------------------------------------------- | ------------------------------------------------ | -------------------- | ------- |
| ruff exits 0 with expanded rule set           | `.venv/bin/ruff check src/ tests/`               | "All checks passed!" | PASS    |
| pip-audit finds zero critical/high CVEs       | pip-audit with NVD CVSS lookup                   | All 3 CVEs LOW/MEDIUM | PASS   |
| vulture with whitelist finds 0 items at 80%   | `.venv/bin/vulture src/wanctl/ .vulture_whitelist.py --min-confidence 80` | 0 findings (per SUMMARY) | PASS |
| production state dir is 0750                  | `ssh kevin@10.10.110.223 'sudo stat /var/lib/wanctl/'` | 750 wanctl:wanctl | PASS |
| production log dir is 0750                    | `ssh kevin@10.10.110.223 'sudo stat /var/log/wanctl/'` | 750 wanctl:wanctl | PASS |
| secrets file permission                        | `ssh kevin@10.10.110.223 'sudo stat /etc/wanctl/secrets'` | 640 root:wanctl | PARTIAL (see below) |

---

## Requirements Coverage

| Requirement | Source Plan | Description                                                              | Status    | Evidence                                                                              |
| ----------- | ----------- | ------------------------------------------------------------------------ | --------- | ------------------------------------------------------------------------------------- |
| FSCAN-01    | 112-01      | pip-audit scan with zero critical/high CVEs                              | SATISFIED | All current CVEs confirmed LOW/MEDIUM via NVD API: pip (LOW), pygments (MEDIUM/LOW), requests (MEDIUM) |
| FSCAN-02    | 112-01      | Unused dependencies identified and removed via deptry                   | SATISFIED | cryptography and pyflakes removed from pyproject.toml; uv sync succeeded             |
| FSCAN-03    | 112-04      | Dead code inventory via vulture (identification only, no removal)        | SATISFIED | 112-04-findings.md exists with categorized inventory; .vulture_whitelist.py committed; zero source deletions confirmed |
| FSCAN-04    | 112-02      | File permissions verified (/etc/wanctl/secrets 0600, dirs 0750)         | PARTIAL   | State/log dirs confirmed 0750. secrets is 0640 (not 0600) — determined architecturally correct but diverges from written requirement spec |
| FSCAN-05    | 112-02      | systemd-analyze security score for all 3 service units                   | SATISFIED | All 4 services documented: wanctl@spectrum (8.4 EXPOSED), wanctl@att (8.4), steering (8.4), nic-tuning (9.6 UNSAFE). Hardening opportunities cataloged. |
| FSCAN-06    | 112-03      | Ruff rule expansion (C901/SIM/PERF/RET/PT/TRY/ARG/ERA) applied         | SATISFIED | All 8 categories in pyproject.toml select list; ruff exits 0; 839 findings resolved (138 autofix, 17 manual, 22 rules suppressed, 49 deferred) |
| FSCAN-07    | 112-01      | Orphaned test fixtures identified via pytest-deadfixtures                | SATISFIED | 8 orphaned fixtures cataloged in 112-01-findings.md with file/line locations         |
| FSCAN-08    | 112-01      | Log rotation verified                                                    | SATISFIED | RotatingFileHandler documented (10MB/3 backups); production VM shows 95MB total active rotation |

**Orphaned requirements check:** No requirements mapped to Phase 112 in REQUIREMENTS.md that are not claimed by one of the 4 plans.

---

## Anti-Patterns Found

| File                                                     | Line | Pattern          | Severity   | Impact                                              |
| -------------------------------------------------------- | ---- | ---------------- | ---------- | --------------------------------------------------- |
| 112-01-findings.md                                       | —    | Missing CVE      | Info       | requests CVE-2026-25645 (MEDIUM 4.4) present at scan time but not documented in findings report. Discovered in verification. |

No stub patterns found in production code changes. Plan 03 committed 120 files of ruff autofix/manual fixes — no return null, placeholder, or TODO/FIXME anti-patterns introduced.

---

## Human Verification Required

### 1. Secrets File Permission: 0640 vs Required 0600

**Test:** Review `/etc/wanctl/secrets` permission architecture
**Expected:** Either (a) confirm 0640 is the correct permission and update FSCAN-04 requirement description from "0600" to "0640 (group-readable by wanctl group)" — OR — (b) restructure service credentials so secrets is readable by root only (0600) with some other mechanism for service access.
**Why human:** The technical case for 0640 is sound (wanctl service user belongs to wanctl group, runs as wanctl user, must read the secrets file). Changing to 0600 would break the service. However, the written requirement explicitly says "0600" and the ROADMAP success criterion says "0600". This is a requirement defect discovered during execution, not a permission defect — but only the operator can formally close it.

### 2. requests CVE-2026-25645 Disposition

**Test:** Evaluate whether to upgrade requests or formally accept risk
**Expected:** One of: (a) upgrade `requests>=2.33.0` in pyproject.toml and run `uv sync`, or (b) add explicit risk acceptance note to 112-01-findings.md explaining wanctl does not call `extract_zipped_paths()`
**Why human:** This CVE was published before the scan ran (2026-03-25) but was not captured in the findings report. It has a fix available (requests 2.33.0). MEDIUM severity (CVSS 4.4). wanctl confirmed not to call the affected function. Operator should decide upgrade vs accept, and the findings doc should be updated to close the documentation gap.

---

## Gaps Summary

No blockers. The phase goal — "all mechanical scanning tools have run and produced actionable inventories that unblock later phases" — is achieved. All 8 tools ran. All 8 requirements have findings documents. All downstream phases (113-116) have the data they need.

Two items require human disposition before the phase can be formally closed:

1. **FSCAN-04 permission spec vs reality:** The requirement says 0600, production is 0640. Both are correct — the requirement description needs updating to match the discovered architecture. This is a documentation fix, not a code fix.

2. **requests CVE-2026-25645 documentation gap:** A MEDIUM-severity CVE with a fix available was not captured in the scan findings. Either an upgrade to requests 2.33.0 or explicit risk acceptance documentation should be added to 112-01-findings.md.

Neither item blocks Phase 113 from beginning.

---

_Verified: 2026-03-26T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
