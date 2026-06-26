# Phase 261: Pre-Flip Deploy Reconciliation - Context

**Gathered:** 2026-06-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring `/opt/wanctl` on `cake-shaper` to a repo-equal known state via a full, reversible
`deploy.sh`, prove `repo == prod` with a pre/post sha256 audit, capture an exercised
rollback anchor (the deploy itself is reversible), and prove the route-management surface
plus `127.0.0.1:9102` health come up clean in the **existing** dry-run/safe state
(`mode=dry_run`, `active_owner=netwatch`). This establishes the clean baseline every later
mutating phase (262–264) depends on.

**Why it exists:** the v1.57 D-07 cross-check fix was pushed to production by a *surgical
single-file rsync*, **not** `deploy.sh` (see 260 d07fix evidence). Prod therefore has the
corrected content but the full deploy pipeline was never exercised end-to-end against it.
Phase 261 reconciles the whole tree so `repo == prod` is provable and the deploy path is
known-good before any live flip.

**Forbidden (SAFE-22):** no CAKE/qdisc/rate/threshold change; no controller-path source diff
(`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, RTT backends, `alert_engine.py`,
fusion); no Netwatch enable/disable/delete; no route-owner flip; no active route-management
mode. This phase changes **no ownership behavior** — Netwatch remains the active/interim
owner throughout. The reconcile `deploy.sh` is one of SAFE-22's three permitted mutations;
the other two (the gated single-route flip and the auto-revert) belong to Phases 263–264.

</domain>

<decisions>
## Implementation Decisions

### sha256 audit scope (RECON-01)

- **D-01 — Audit the deploy-managed *code surface*, not the whole tree.** `repo == prod` is
  proven over the rsync-managed code tree (`src/wanctl/` → `/opt/wanctl/`, `__pycache__`/`*.pyc`
  excluded — matching `deploy.sh`'s own rsync excludes) **plus** the standalone scripts
  `deploy.sh` installs under `/opt/wanctl/scripts`. This is exactly where the D-07 drift lives
  and exactly what `rsync -av --delete` makes authoritative. Env-substituted configs, secrets,
  SSH keys, and runtime state under `/etc/wanctl` and `/var/lib/wanctl` are **excluded by
  design** — they are not byte-equal to repo and must not be. The audit is a strict
  per-file sha256 equality check over this defined set; any mismatch fails RECON-01.

### Rollback anchor mechanism (RECON-02)

- **D-02 — Pre-deploy timestamped tarball, proven by a non-disruptive scratch-dir restore
  drill.** Before the deploy, capture a timestamped tar of `/opt/wanctl` on `cake-shaper` as
  the rollback anchor. Satisfy RECON-02's "proven, exercised revert path" by restoring the
  anchor into a **scratch directory** and sha256-matching it against the anchor contents —
  this proves restore fidelity **without** touching the live `/opt/wanctl` tree or bouncing
  services a second time. Rejected: full live restore-over-`/opt/wanctl`-then-re-deploy
  (faithful end-to-end but bounces steering twice on the production host for negligible added
  assurance over the scratch-dir drill). The anchor path/timestamp convention is planner
  discretion; it must be recorded in evidence so a real revert is a one-command operation.

### Deploy + restart strategy on the live host (RECON-01/03)

- **D-03 — Full `deploy.sh`, sequenced restart (steering last), health-gated between units.**
  Run a *full* `deploy.sh` covering the complete production surface — both-WAN cake-autorate
  bridges + steering — to honor RECON-01's "full `deploy.sh`" and make the whole pipeline
  known-good (not just the one drifted file). Sequence the service restarts rather than a
  simultaneous bounce: restart with **steering last**, and gate each restart on a `:9102`
  health check before proceeding. Rationale: a steering restart in dry-run/safe mutates no
  routes (Netwatch owns the route; the cake-autorate *shaper proper* is a separate service
  from the `-state-bridge` units and is untouched), so the live impact is a sub-second blip
  with no ownership effect. The exact `deploy.sh` invocation/flags (e.g.
  `--with-{spectrum,att}-cake-autorate` + steering) are planner discretion within "full prod
  surface."

### Post-deploy clean-proof depth (RECON-03)

- **D-04 — Smoke-assertion gate, then a confirmatory Phase 260 harness rerun.** RECON-03 is
  *gated* on a targeted post-deploy smoke assertion: all expected services `active`,
  steering `mode=dry_run`, `active_owner=netwatch`, and `:9102` `ownership_inspection` with
  `inspector_status=ok` AND `match=true`. **After** the gate passes, re-run the Phase 260
  observation harness (`scripts/phase260-observation.py`) as confirmation that the
  `ready-for-approval` verdict still holds on the now-reconciled tree — the v1.57 readiness
  packet was produced on the *pre-reconcile* prod, so re-validating it post-deploy is the
  point. The smoke assertion is the pass/fail gate; the harness rerun is confirmatory
  evidence, not a second gate.

### Claude's Discretion

The planner/researcher may choose: the sha256 manifest format and audit script
CLI/flags; the exact tarball anchor path + timestamp convention; the precise `deploy.sh`
invocation flags for "full prod surface"; the restart sequencing order among the bridge
units (steering remains last); evidence/packet filenames and layout (mirror the 257/260
evidence convention); and the smoke-assertion script shape — provided all SAFE-22 boundaries
hold, the audit covers the D-01 set, the rollback drill is non-disruptive (D-02), and no
ownership behavior changes.

### Folded Todos

- `2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — this milestone (v1.58,
  SEED-008) is the active driver advancing that long-standing todo. Phase 261 folds **only**
  the baseline-reconciliation slice (clean known-state deploy + rollback anchor + clean
  dry-run proof). The actual ownership flip / Netwatch demotion is **not** folded here — it
  belongs to Phases 263–264 behind the operator approval gate.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — RECON-01, RECON-02, RECON-03 (Phase 261 scope) and the
  milestone-wide SAFE-22 invariant statement.
- `.planning/ROADMAP.md` — Phase 261 goal + success criteria; the v1.58 milestone goal,
  hard ordering dependencies, and the SAFE-22 permitted/forbidden mutation list.

### The drift this phase reconciles (v1.57 D-07)
- `.planning/milestones/v1.57-phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-readiness-packet-d07fix.md`
  — the post-D-07-fix readiness packet (`ready-for-approval`) produced on the surgically-patched prod.
- `.planning/milestones/v1.57-phases/260-dry-run-observation-rerun-canary-readiness/evidence/phase260-observation-transcript-d07fix.md`
  — record of the D-07 cross-check fix and the single-file (non-`deploy.sh`) live rerun that
  created the drift Phase 261 closes.
- `.planning/milestones/v1.57-phases/260-dry-run-observation-rerun-canary-readiness/260-CONTEXT.md`
  — Phase 260 decisions (D-01..D-10); the authoritative-signal choice and all-samples-clean
  rule that the confirmatory harness rerun (D-04) must preserve.

### Deploy + reconcile mechanics
- `scripts/deploy.sh` — unified deploy; `deploy_code` uses `rsync -av --delete` for
  `src/wanctl/` → `/opt/wanctl/` (excludes `__pycache__`/`*.pyc`), has a built-in `-n`
  dry-run; configs/scripts/systemd are scp'd individually. Defines the D-01 audit set and
  the D-03 restart surface.
- `scripts/install.sh`, `scripts/install-systemd.sh` — target-side install/systemd wiring
  invoked by `deploy.sh`.
- `.planning/codebase/INTEGRATIONS.md` — REST transport (port 443, `ROUTER_PASSWORD`,
  `router.verify_ssl`) and health-endpoint topology (`:9101` autorate bridge, `:9102`
  steering).

### Clean-proof / smoke surface (read-only consumers)
- `scripts/phase260-observation.py` — the confirmatory rerun harness (D-04); bounded
  observation window, samples `:9102` `ownership_inspection`, emits the readiness verdict.
- `src/wanctl/steering/health.py` — `_build_ownership_inspection_section()` /
  `_build_route_management_section()`; the exact `:9102/health` payload the smoke assertion
  and harness sample.
- `src/wanctl/steering/route_ownership_inspector.py` — the cached inspector producing
  `ownership_inspection` (one of the three files holding the shared D-07 detector).
- `src/wanctl/steering/route_ownership_guard.py` — the guard/detector file at the center of
  the D-07 drift now being reconciled.
- `src/wanctl/steering/route_manager.py` — `status_snapshot()` / `_active_owner()`; source of
  `active_owner=netwatch` and `mode=dry_run` for the smoke gate.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/deploy.sh` `--dry-run` (`-n`) rsync mode — exercise it pre-flight to preview the
  reconcile delta before the real run; the delta is also a useful witness to the D-07 drift.
- `scripts/phase260-observation.py` — re-run as-is for the D-04 confirmatory step; no rebuild,
  just point it at the reconciled tree and capture a fresh readiness packet.
- Phase 257/260 evidence layout (`evidence/` with timestamped packet + raw JSON + transcript +
  readonly-commands) — mirror it for the RECON audit manifest, anchor record, and clean-proof.

### Established Patterns
- **`rsync --delete` = tree equality** — post-deploy the `src/wanctl/` tree is byte-equal to
  repo (pyc excluded), which is what makes the D-01 sha256 audit a clean equality check rather
  than a fuzzy diff.
- **Deployed proof harness** — standalone `scripts/` script importing from `/opt/wanctl`,
  emitting a single machine-greppable verdict token (established by 258/259/260 proofs); the
  RECON audit + smoke assertion should follow the same single-verdict-line convention.
- **Additive, no-regression health** — `ownership_inspection` is a sibling of `route_management`
  in `:9102/health`; the smoke assertion must not assume one nests in the other.

### Integration Points
- Deploy target is `cake-shaper` (the production steering host): `/opt/wanctl` (code),
  `/etc/wanctl` (config/secrets, excluded from audit), systemd units for steering +
  cake-autorate bridges.
- Smoke gate + harness read `:9102/health` (steering) for `mode`, `active_owner`, and
  `ownership_inspection.{inspector_status,match}`.
- Audit + anchor operate on `cake-shaper:/opt/wanctl`; the scratch-dir restore drill stays
  off the live tree.

</code_context>

<specifics>
## Specific Ideas

- The deploy must exercise the **full** pipeline end-to-end, not re-patch the one file —
  the entire point of RECON is to retire the "surgical single-file rsync" shortcut that
  created the v1.57 drift.
- The rollback drill must be genuinely *exercised* (restore + sha256-match), not merely
  asserted — RECON-02 says "proven, exercised revert path."
- Re-validate `ready-for-approval` on the reconciled tree; do not assume the pre-reconcile
  readiness verdict carries over unchanged.

</specifics>

<deferred>
## Deferred Ideas

- The actual single-route owner flip (Netwatch → wanctl), abort/auto-revert scaffolding, the
  rollback drill *for the route flip*, the operator approval gate, and the soak entry-gate —
  all belong to Phases 262–264 under SAFE-22, not here.

None beyond the milestone's own later phases — discussion stayed within the RECON baseline scope.

</deferred>

---

*Phase: 261-pre-flip-deploy-reconciliation*
*Context gathered: 2026-06-26*
