# Phase 261: Pre-Flip Deploy Reconciliation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-26
**Phase:** 261-pre-flip-deploy-reconciliation
**Areas discussed:** sha256 audit scope, Rollback anchor mechanism, Live-restart handling, Clean-proof depth

Discussion was run in condensed mode (one decision per area, recommended-default-first) per the
operator's stated preference for fewer, well-defended questions over the 4-turns-per-area default.
All four areas resolved on the recommended option.

---

## sha256 audit scope (RECON-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Deploy-managed code surface | rsync `--delete` tree (`src/wanctl/`→`/opt/wanctl/`, pyc-excluded) + installed `/opt/wanctl/scripts`; configs/secrets/state excluded by design. Where D-07 drift lives. | ✓ |
| Code tree only | Just `src/wanctl/`→`/opt/wanctl/`; deployed scripts not in the equality proof. | |
| Whole /opt/wanctl tree | sha256 everything incl. configs; needs an allowlist of expected env-substituted diffs — more noise. | |

**User's choice:** Deploy-managed code surface
**Notes:** Tightest set that still covers the drift and matches what `rsync --delete` makes authoritative.

---

## Rollback anchor mechanism (RECON-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Tarball + scratch-dir restore drill | Pre-deploy tar of `/opt/wanctl`; prove by restoring into a scratch dir + sha256-match. Non-disruptive on the live host. | ✓ |
| Tarball + full live restore/re-deploy | Restore over `/opt/wanctl` for real, verify, re-deploy. Most faithful but bounces steering twice. | |
| rsync sibling snapshot | Snapshot to `/opt/wanctl.preflip-<ts>`; revert = dir swap (swap itself untested unless exercised). | |

**User's choice:** Tarball + scratch-dir restore drill
**Notes:** Satisfies "proven, exercised revert path" without a second service bounce on the production host.

---

## Live-restart handling (RECON-01/03)

| Option | Description | Selected |
|--------|-------------|----------|
| Full deploy, sequenced restart, health-gated | Full `deploy.sh` (both-WAN bridges + steering); restart steering last with `:9102` health check between units. Sub-second dry-run blip, no ownership impact. | ✓ |
| Minimal-blast: restart only changed units | Full tree deploy but only restart steering; leave bridges running. Smallest impact, weaker full-deploy semantics. | |
| Full deploy, standard restart | Let `deploy.sh` restart everything its normal way. Simplest; simultaneous bounce. | |

**User's choice:** Full deploy, sequenced restart, health-gated
**Notes:** Honors RECON-01 "full deploy.sh" while keeping the live blip minimal and verifiable.

---

## Clean-proof depth (RECON-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Smoke gate + confirmatory 260 harness rerun | Gate on smoke assertion (services active, `mode=dry_run`, `active_owner=netwatch`, `ownership_inspection ok+match`); then re-run `phase260-observation.py` to confirm readiness on the reconciled tree. | ✓ |
| Smoke assertion only | Targeted smoke check; skip the 10-min window. Faster but doesn't re-confirm the readiness verdict. | |
| Full 260 observation window as the gate | Make the ~10-min window the RECON-03 gate itself. Heaviest; over-scoped for a deploy smoke test. | |

**User's choice:** Smoke gate + confirmatory 260 harness rerun
**Notes:** Smoke assertion is the pass/fail gate; harness rerun re-validates `ready-for-approval` on the post-reconcile tree (the v1.57 packet was produced pre-reconcile).

---

## Claude's Discretion

- sha256 manifest format + audit script CLI/flags
- tarball anchor path + timestamp convention
- exact `deploy.sh` invocation flags for "full prod surface"
- restart sequencing order among bridge units (steering stays last)
- evidence/packet filenames + layout (mirror 257/260 convention)
- smoke-assertion script shape

## Deferred Ideas

- The actual single-route owner flip, abort/auto-revert scaffolding, the route-flip rollback
  drill, the operator approval gate, and the soak entry-gate — all belong to Phases 262–264
  under SAFE-22, not to this RECON baseline phase.
