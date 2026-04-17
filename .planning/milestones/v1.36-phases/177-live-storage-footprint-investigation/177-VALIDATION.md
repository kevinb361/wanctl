---
phase: 177
slug: live-storage-footprint-investigation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-13
---

# Phase 177 — Validation Strategy

> Per-phase validation contract for storage-forensics execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `rg`, production file inventory, read-only `sqlite3`, optional shell syntax checks for any new helper |
| **Config file** | `configs/spectrum.yaml`, `configs/att.yaml` |
| **Quick run command** | `rg '<pattern>' <files...>` or `ssh ... 'sudo -n sqlite3 ...'` |
| **Full suite command** | none required unless execution adds a reusable helper script |
| **Estimated runtime** | under 30 seconds per validation sample |

---

## Sampling Rate

- **After every task commit:** run the task-local repo grep or production read-only query listed in the plan.
- **After every plan wave:** re-run the DB-path inventory plus any helper syntax checks introduced in that wave.
- **Before `/gsd-verify-work`:** confirm the evidence artifacts explain active DB files, retained time shape, and the legacy `metrics.db` role.
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 177-01-01 | 01 | 1 | STOR-04 | T-177-01 | code/config/runtime DB paths are inventoried without changing live state | repo+prod evidence | `rg -n 'db_path|metrics\\.db|metrics-' configs src/wanctl && ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n ls -lh /var/lib/wanctl/metrics*.db* /var/lib/wanctl/*metrics.db* 2>/dev/null'` | ✅ | ⬜ pending |
| 177-02-01 | 02 | 2 | STOR-04 | T-177-02 | DB composition evidence is collected using read-only sqlite access | prod evidence | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 /var/lib/wanctl/metrics-spectrum.db \".tables\" && echo --- && sudo -n sqlite3 /var/lib/wanctl/metrics-att.db \".tables\"'` | ✅ | ⬜ pending |
| 177-02-02 | 02 | 2 | STOR-04 | T-177-03 | retained time shape is measured from the active per-WAN DBs | prod evidence | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db \"SELECT timestamp, granularity FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity FROM metrics ORDER BY timestamp DESC LIMIT 1;\"'` | ✅ | ⬜ pending |
| 177-03-01 | 03 | 3 | STOR-04 | T-177-04 | findings and the Phase 178 recommendation are grounded in captured evidence | artifact | `rg -n 'metrics-spectrum\\.db|metrics-att\\.db|metrics\\.db|recommendation|Phase 178' .planning/phases/177-live-storage-footprint-investigation` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure is sufficient.

No new automated test harness is required because this phase is investigative and should rely on:

- repo grep checks
- read-only production commands
- evidence artifacts captured under the phase directory

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm the Phase 178 recommendation matches the measured evidence rather than a storage-size guess | STOR-04 | Human review is needed to judge whether the recommended next step follows from the captured evidence | Read the final findings doc and verify every recommendation cites a measured active DB fact |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or Wave 0 coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verification
- [x] Wave 0 covers all production-evidence dependencies
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-13

