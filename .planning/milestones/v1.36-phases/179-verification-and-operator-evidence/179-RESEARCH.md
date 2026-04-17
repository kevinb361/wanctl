# Phase 179: Verification And Operator Evidence - Research

**Researched:** 2026-04-13
**Domain:** Production evidence capture, live storage verification, operator proof path
**Confidence:** HIGH

## Summary

Phase 179 is a production-verification phase. The repo-side storage work is already complete after Phase 178: the legacy shared `metrics.db` role is explicit, the per-WAN raw retention window has been reduced to 1 hour, `/metrics/history` and `wanctl-history` follow the per-WAN discovery path, and operator docs now describe the intended topology. What remains is proving that those changes actually held on deployed hosts.

Phase 178 verification already narrowed the remaining uncertainty to two live-only questions:

1. Are `metrics-spectrum.db` and `metrics-att.db` materially smaller on production than the 2026-04-13 baseline?
2. Do live reader surfaces (`wanctl-history`, `/metrics/history`) follow the new topology end-to-end while `metrics.db` continues to reflect steering activity separately?

That means Phase 179 should stay evidence-oriented:

1. Capture live DB size and `storage.status` evidence from production.
2. Run live reader-path checks against the authoritative DB layout.
3. Record the operator proof path in a form that closes `OPER-04` and supports milestone verification.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPER-04 | Operators have a documented and repeatable way to verify which DB files are active, what storage status means, and whether the footprint reduction actually held in production | Phase 178 already created the command path; Phase 179 must execute it on live systems and record the results |
</phase_requirements>

## Verified Current State

### 1. The authoritative active DB set is already defined in repo artifacts

Phase 178 established the production DB layout:

- `/var/lib/wanctl/metrics-spectrum.db`
- `/var/lib/wanctl/metrics-att.db`
- `/var/lib/wanctl/metrics.db` for steering

The operator verification path already documents this in:

- `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-operator-verification-path.md`
- `docs/RUNBOOK.md`
- `docs/DEPLOYMENT.md`

**Implication:** Phase 179 should validate the deployed host against this declared topology rather than redefine it.

### 2. The comparison baseline is fixed and evidence-backed

The pre-Phase-178 production sizes recorded on `2026-04-13` were approximately:

- Spectrum: `5.44 GB`
- ATT: `5.08 GB`

These values are cited in:

- Phase 177 DB composition/evidence docs
- Phase 178 verification
- current milestone state context

**Implication:** Phase 179 should use those numbers as the explicit before/after comparison point.

### 3. The expected retention shape is now narrower for per-WAN DBs

Shipped configs now set:

- `raw_age_seconds: 3600`
- `aggregate_1m_age_seconds: 86400`
- `aggregate_5m_age_seconds: 604800`

**Implication:** live retained-window checks should show a short raw frontier with longer 1m/5m aggregate coverage, not a 24h raw corpus.

### 4. Repo-side history readers already prefer per-WAN DBs

Both:

- `wanctl-history`
- `/metrics/history`

now follow `discover_wan_dbs()` precedence and should read only the per-WAN DB set when it exists.

**Implication:** Phase 179 should validate the deployed result, not re-argue the code path.

### 5. Remaining uncertainty is operational, not structural

Phase 178 verification passed all repo-side must-haves and explicitly deferred live evidence to Phase 179.

**Implication:** this phase should avoid broad repo edits unless production evidence forces a concrete follow-up correction.

## Standard Stack

| Surface | Role | Current Status | Phase 179 Need |
|---------|------|----------------|----------------|
| production `/var/lib/wanctl/*.db*` | source of truth for post-change footprint | not yet re-measured after Phase 178 | capture live sizes and compare to 2026-04-13 baseline |
| `./scripts/soak-monitor.sh --json` | storage status snapshot | available and read-only | record post-change `storage.status` for both WANs |
| `wanctl-history` | authoritative CLI reader | wired to per-WAN discovery in repo | prove deployed behavior matches repo intent |
| `/metrics/history` | authoritative HTTP reader | wired to per-WAN discovery in repo | prove deployed behavior matches repo intent |
| `.planning/phases/178-.../178-operator-verification-path.md` | operator proof procedure | already written | execute it and turn it into milestone evidence |
| milestone planning docs | closeout routing | Phase 179 still unplanned | update state and traceability once evidence is captured |

## Architecture Patterns

### Pattern 1: Live evidence over inferred success

This phase should cite production command outputs and measured deltas, not just restate what the code intends.

### Pattern 2: Reuse the existing operator proof path

Phase 178 already created the commands. Phase 179 should execute those exact read-only checks so the documentation and the operational truth stay aligned.

### Pattern 3: Keep production verification read-only

This phase should not mutate host state unless the evidence reveals a concrete issue that requires a separate fix phase.

## Recommended Plan Split

### Plan 01: Capture live footprint evidence against the Phase 177 baseline

Goal: record current DB sizes, WAL sizes, and `storage.status`, then compare them to the 2026-04-13 baseline.

### Plan 02: Prove the live reader topology and retained-history shape

Goal: verify that `wanctl-history`, `/metrics/history`, and direct SQLite spot-checks reflect the authoritative per-WAN layout and the tightened retention profile.

### Plan 03: Synthesize operator evidence and milestone-close proof

Goal: turn the live evidence into a repeatable operator artifact, close `OPER-04`, and leave the milestone ready for audit/complete flow.

## Common Pitfalls

### Pitfall 1: Declaring success from repo-side changes alone

Phase 178 already did that. Phase 179 exists specifically because that was not enough.

### Pitfall 2: Comparing live DB sizes without using the fixed April 13 baseline

Without the explicit baseline, "smaller" becomes subjective and hard to verify.

### Pitfall 3: Using direct SQLite checks as the only topology proof

Those checks are useful, but this phase also needs to prove the supported operator surfaces (`wanctl-history`, `/metrics/history`, `soak-monitor`) behave correctly.

## Validation Architecture

Phase 179 is primarily a live-evidence and documentation phase, so validation should be read-only and targeted:

- production-safe SSH `stat` and `sqlite3` commands
- `./scripts/soak-monitor.sh --json`
- live `wanctl-history` and `/metrics/history` checks
- `git diff --check` for any docs/artifacts written during execution

Recommended quick checks during execution:

- `ssh <host> 'sudo -n stat -c "%n %s %y" /var/lib/wanctl/metrics-spectrum.db /var/lib/wanctl/metrics-att.db /var/lib/wanctl/metrics.db 2>/dev/null'`
- `./scripts/soak-monitor.sh --json`
- `ssh <host> 'wanctl-history --last 1h --metrics wanctl_rtt_ms --json | python3 -m json.tool | head -n 40'`
- `ssh <host> 'curl -s http://127.0.0.1:9101/metrics/history?range=1h&limit=5 | python3 -m json.tool'`
