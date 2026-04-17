---
phase: 179
slug: verification-and-operator-evidence
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-13
---

# Phase 179 — Validation Strategy

> Per-phase validation contract for live production evidence and operator-proof capture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | production-safe SSH checks, `sqlite3`, `wanctl-history`, `/metrics/history`, `soak-monitor`, `git diff --check` |
| **Config file** | active deployed `/etc/wanctl/*.yaml` plus repo operator docs/artifacts |
| **Quick run command** | `ssh ... 'sudo -n stat ...'` or `./scripts/soak-monitor.sh --json` |
| **Full suite command** | none required unless execution adds helper code or changes scripts/docs |
| **Estimated runtime** | under 60 seconds per production evidence sample |

---

## Sampling Rate

- **After every task commit:** run the task-local live check or grep listed in the plan.
- **After every plan wave:** re-run the active DB inventory and storage-status snapshot.
- **Before `/gsd-verify-work`:** confirm the evidence artifacts capture live sizes, live reader behavior, and the operator re-check path.
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 179-01-01 | 01 | 1 | OPER-04 | T-179-01 | live DB inventory is captured read-only and compared to the fixed 2026-04-13 baseline | prod evidence | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-spectrum.db-wal /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics-att.db-wal /var/lib/wanctl/metrics.db /var/lib/wanctl/metrics.db-wal 2>/dev/null'` | ✅ | ⬜ pending |
| 179-01-02 | 01 | 1 | OPER-04 | T-179-02 | storage-status evidence is collected from the supported operator helper, not a custom ad hoc path | prod evidence | `./scripts/soak-monitor.sh --json` | ✅ | ⬜ pending |
| 179-02-01 | 02 | 2 | OPER-04 | T-179-03 | live CLI history follows the per-WAN discovery path when per-WAN DBs exist | prod evidence | `ssh -o BatchMode=yes kevin@10.10.110.223 'wanctl-history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'` | ✅ | ⬜ pending |
| 179-02-02 | 02 | 2 | OPER-04 | T-179-04 | live HTTP history follows the same topology and preserves response metadata | prod evidence | `ssh -o BatchMode=yes kevin@10.10.110.223 'curl -s http://127.0.0.1:9101/metrics/history?range=1h&limit=5 | python3 -m json.tool'` | ✅ | ⬜ pending |
| 179-02-03 | 02 | 2 | OPER-04 | T-179-05 | retained-window spot checks remain read-only and distinguish per-WAN DBs from the shared steering DB | prod evidence | `ssh -o BatchMode=yes kevin@10.10.110.223 'sudo -n sqlite3 -json /var/lib/wanctl/metrics-spectrum.db "SELECT timestamp, granularity FROM metrics ORDER BY timestamp ASC LIMIT 1; SELECT timestamp, granularity FROM metrics ORDER BY timestamp DESC LIMIT 1;"'` | ✅ | ⬜ pending |
| 179-03-01 | 03 | 3 | OPER-04 | T-179-06 | the final evidence artifact and docs tell operators exactly how to re-check footprint and topology without guesswork | artifact + repo check | `rg -n 'baseline|metrics-spectrum\\.db|metrics-att\\.db|metrics\\.db|wanctl-history|/metrics/history|storage.status' .planning/phases/179-verification-and-operator-evidence docs/DEPLOYMENT.md docs/RUNBOOK.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing tooling is sufficient.

No new harness is required before execution because this phase should rely on:

- production-safe operator commands already documented in Phase 178
- existing helper scripts
- evidence artifacts written under the phase directory

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm that the measured live DB sizes are materially smaller than the April 13 baseline in an operator-meaningful sense | OPER-04 | Human judgment is needed to interpret the delta and decide whether the reduction is materially meaningful for the deployment | Compare the captured live sizes to the 2026-04-13 baseline and record the delta in the final evidence doc |
| Confirm that the reader topology proof is operationally convincing, not just code-consistent | OPER-04 | Requires human review of the live CLI/HTTP outputs and direct SQLite spot checks together | Read the final evidence artifact and verify it demonstrates both supported readers and direct DB spot checks |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verification or Wave 0 coverage
- [x] Sampling continuity: no 3 consecutive tasks without automated verification
- [x] Wave 0 covers all production-evidence dependencies
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-13
