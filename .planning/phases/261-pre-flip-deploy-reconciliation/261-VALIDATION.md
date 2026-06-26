---
phase: 261
slug: pre-flip-deploy-reconciliation
status: draft
nyquist_compliant: false
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
> source diffs). The planner refines the per-task map below.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Deployed proof harness (standalone `scripts/` scripts emitting a single greppable verdict token) + pytest 7.x (existing, for any repo-side helper) |
| **Config file** | `pyproject.toml` (existing); no new framework |
| **Quick run command** | `.venv/bin/pytest -o addopts='' <new-helper-test> -q` (only if a repo-side audit helper is added) |
| **Full suite command** | RECON audit script + smoke-assertion script + `scripts/phase260-observation.py` rerun (all read-only against `cake-shaper`) |
| **Estimated runtime** | ~bounded observation window of phase260 harness (point-in-time) + sub-minute audit/smoke |

---

## Sampling Rate

- **After every task commit:** Run the relevant proof verdict (audit manifest diff / drill sha256-match / smoke assertion) for that task.
- **After every plan wave:** Re-witness the live `:9102` snapshot (`mode`, `active_owner`, `ownership_inspection.{inspector_status,match}`) before proceeding.
- **Before close:** Smoke-assertion gate green AND confirmatory `phase260-observation.py` verdict still `ready-for-approval` on the reconciled tree.
- **Max feedback latency:** sub-minute for audit/smoke; phase260 harness is its own bounded window.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (planner fills) | — | — | RECON-01 | — | post-deploy `/opt/wanctl` == repo over D-01 set | proof | per-file sha256 manifest equality (0 mismatches) | ❌ W0 | ⬜ pending |
| (planner fills) | — | — | RECON-02 | — | scratch-dir restore byte-matches anchor; live tree untouched | proof | tarball restore + sha256-match verdict | ❌ W0 | ⬜ pending |
| (planner fills) | — | — | RECON-03 | — | services active; `mode=dry_run`; `active_owner=netwatch`; `inspector_status=ok`; `match=true` | proof | `:9102` smoke-assertion verdict token + phase260 rerun | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] RECON audit script (per-file sha256 manifest over the D-01 set; single greppable verdict line) — new standalone `scripts/` proof.
- [ ] Smoke-assertion script (reads `:9102/health`; asserts `mode`/`active_owner`/`ownership_inspection`; single greppable verdict line) — new standalone `scripts/` proof.
- [ ] `scripts/phase260-observation.py` — reused as-is for the confirmatory rerun (no rebuild).

*Existing pytest infrastructure is not the primary validation surface for this phase; deployed proof harnesses are.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full `deploy.sh` run against live `cake-shaper` (both-WAN bridges + steering, steering last, `:9102`-gated) | RECON-01/03 | Mutates the live production host; must be operator-run and witnessed, not CI-automated | Run full `deploy.sh` per plan; gate each restart on `:9102` health; capture pre/post evidence |
| Pre-deploy tarball anchor capture on `cake-shaper` | RECON-02 | Operates on the live `/opt/wanctl` tree on the production host | Capture timestamped tar; record path/timestamp in evidence packet |

*The sha256 audit, the scratch-dir restore drill, and the `:9102` smoke assertion are scriptable/automated; the live deploy + anchor capture are operator-witnessed by nature.*

---

## Validation Sign-Off

- [ ] Each RECON requirement has a deployed-proof verdict token (audit / drill / smoke) or a witnessed operator step
- [ ] Sampling continuity: live `:9102` re-witnessed between waves
- [ ] Wave 0 covers the audit + smoke proof scripts
- [ ] No watch-mode flags
- [ ] Feedback latency sub-minute for audit/smoke
- [ ] `nyquist_compliant: true` set in frontmatter once planner fills the per-task map

**Approval:** pending
