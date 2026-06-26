---
phase: 261
slug: pre-flip-deploy-reconciliation
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-26
---

# Phase 261 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> NOTE: This is an infrastructure reconciliation/proof phase, not a code-authoring phase.
> "Validation" here means observable evidence that each RECON requirement holds against the
> live `cake-shaper` host — sha256 audit verdicts, the rollback-drill match verdict, and the
> `:9102` smoke-assertion gate — NOT unit tests over new source (SAFE-22 forbids controller-path
> source diffs). The two new proof scripts (audit, smoke) are standalone `scripts/` artifacts.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Deployed proof harness (standalone `scripts/` scripts emitting a single greppable verdict token) + pytest 7.x (existing, for the confirmatory-harness logic the rerun depends on) |
| **Config file** | `pyproject.toml` (existing); no new framework |
| **Quick run command** | `.venv/bin/ruff check scripts/phase261-*.py` (new proof scripts) + `.venv/bin/pytest -o addopts='' tests/test_phase260_observation.py -q` (rerun-logic regression) |
| **Full suite command** | RECON audit script + smoke-assertion script + `scripts/phase260-observation.py` rerun (all read-only/on-host against `cake-shaper`) |
| **Estimated runtime** | sub-minute audit/smoke; phase260 harness is its own bounded ~636s window (point-in-time) |

---

## Sampling Rate

- **After every task commit:** Run the relevant proof verdict for that task (Plan 01 ruff on the
  new scripts + drill sha256-match; Plan 02 deploy transcript + audit manifest diff; Plan 03 smoke
  assertion + harness rerun).
- **After every plan wave:** Re-witness the live `:9102` snapshot (`mode`, `active_owner`,
  `ownership_inspection.{inspector_status,match}`) before proceeding to the next wave.
- **Before close:** Smoke-assertion gate green (Plan 03 Task 1) AND confirmatory
  `phase260-observation.py` verdict `ready-for-approval` with `MUTATION_TOKEN_HITS: []` on the
  reconciled tree (Plan 03 Task 2) AND full audit `PHASE261_AUDIT_SRC_TREE_EQUAL` (Plan 02 Task 2).
- **Max feedback latency:** sub-minute for audit/smoke; phase260 harness is its own bounded window.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 261-01-T1 | 01 | 1 | RECON-02 (tooling) | T-261-04 | proof scripts are CI-clean, no controller-path source diff | lint/parse | `.venv/bin/ruff check scripts/phase261-*.py` + ast parse | ❌ W1 | ⬜ pending |
| 261-01-T2 | 01 | 1 | RECON-02 (witness) | T-261-03 | read-only host probe + `--delete` set witnessed benign | proof (witness) | evidence-present grep (host-probe + dryrun-witness + readonly-commands) | ❌ W1 | ⬜ pending |
| 261-01-T3 | 01 | 1 | RECON-02 | T-261-01 | scratch-dir restore byte-matches anchor; live tree untouched, no service bounce | proof | grep `PHASE261_RESTORE_DRILL_PASS` in anchor evidence | ❌ W1 | ⬜ pending |
| 261-02-T1 | 02 | 2 | RECON-01 | T-261-05, T-261-06, T-261-07, T-261-08 | full deploy.sh; steering.yaml block preserved; steering-last `:9102`-gated; shaper units untouched | proof (transcript) | evidence grep (deploy-restart: `steering.yaml` + `state-bridge`) | ❌ W2 | ⬜ pending |
| 261-02-T2 | 02 | 2 | RECON-01 | T-261-08 | per-file sha256 `/opt/wanctl` == repo over D-01 set; scripts subset matches; extras disposed | proof | grep `PHASE261_AUDIT_SRC_TREE_EQUAL` + non-empty manifests | ❌ W2 | ⬜ pending |
| 261-03-T1 | 03 | 3 | RECON-03 (GATE) | T-261-09, T-261-10 | `mode=dry_run` (explicit), `active_owner=netwatch`, `inspector_status=ok`, `match=true`; units active | proof (gate) | grep `PASS route_management.mode==dry_run` + no `^FAIL ` | ❌ W3 | ⬜ pending |
| 261-03-T2 | 03 | 3 | RECON-03 (confirm) | T-261-11 | confirmatory harness rerun on reconciled on-host tree → `ready-for-approval`, no mutation tokens | proof | grep `OBSERVE_VERDICT: ready-for-approval` + `MUTATION_TOKEN_HITS: []` | ❌ W3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] RECON audit script `scripts/phase261-sha256-audit.py` (per-file sha256 manifest over the D-01
      set; single greppable verdict line `PHASE261_AUDIT_SRC_TREE_EQUAL/_MISMATCH`) — built in Plan 01 Task 1.
- [ ] Smoke-assertion script `scripts/phase261-smoke-assertion.py` (reads `:9102/health`; asserts
      `mode`/`active_owner`/`ownership_inspection` siblings, mode explicitly; bounded readiness poll;
      single greppable verdict) — built in Plan 01 Task 1.
- [ ] `scripts/phase260-observation.py` — reused as-is for the confirmatory rerun (no rebuild),
      staged on-host in Plan 03 Task 2.
- [ ] Read-only host probe (tar/mktemp/xargs present; fresh `:9102` baseline) — Plan 01 Task 2.

*Existing pytest infrastructure is not the primary validation surface; deployed proof harnesses are.
`tests/test_phase260_observation.py` must stay green to trust the confirmatory rerun verdict.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full `deploy.sh` run against live `cake-shaper` (both-WAN bridges + steering, steering last, `:9102`-gated) | RECON-01/03 | Mutates the live production host; operator-run and witnessed (CLAUDE.md "suggest, don't implement") | Plan 02 Task 1: preserve steering.yaml → two per-WAN deploys → restore block → sequenced steering-last restart, each `:9102`-gated |
| Pre-deploy tarball anchor capture on `cake-shaper` | RECON-02 | Writes a tarball to the live host filesystem (`/var/lib/wanctl`, additive, no service touch) | Plan 01 Task 3: capture timestamped tar; record path/timestamp + one-command revert |
| `:9102` smoke gate + confirmatory harness rerun on prod | RECON-03 | Reads/runs on the live production host post-deploy | Plan 03: smoke assertion gate (read-only) then on-host harness rerun |

*The sha256 audit, scratch-dir restore drill, and `:9102` smoke assertion are scriptable; the live
deploy + anchor capture + on-host harness run are operator-witnessed by nature.*

---

## Validation Sign-Off

- [ ] Each RECON requirement has a deployed-proof verdict token (audit / drill / smoke) or a witnessed operator step
- [ ] Sampling continuity: live `:9102` re-witnessed between waves
- [ ] Wave 0 covers the audit + smoke proof scripts (Plan 01 Task 1)
- [ ] No watch-mode flags
- [ ] Feedback latency sub-minute for audit/smoke
- [x] `nyquist_compliant: true` set in frontmatter (per-task map filled with real task IDs)

**Approval:** pending operator review of the 3-plan / 3-wave structure.
