# Phase 261: Pre-Flip Deploy Reconciliation - Research

**Researched:** 2026-06-26
**Domain:** Production deploy reconciliation (rsync/scp deploy pipeline), per-file sha256 audit, tarball rollback anchor, sequenced systemd restart, steering `:9102` health smoke gate
**Confidence:** HIGH (all mechanics verified against repo source AND live `cake-shaper` reads)

## Summary

Phase 261 brings `/opt/wanctl` on `cake-shaper` to a repo-equal known state via a full `deploy.sh`, proves `repo == prod` with a per-file sha256 audit (D-01), captures a tarball rollback anchor proven by a non-disruptive scratch-dir restore drill (D-02), runs a sequenced steering-last health-gated restart (D-03), and gates on a targeted `:9102` smoke assertion before a confirmatory `phase260-observation.py` rerun (D-04). No ownership behavior changes; SAFE-22 holds.

The research surfaced **one decisive, plan-shaping landmine that the locked decisions do not yet account for**: the live `/etc/wanctl/steering.yaml` on `cake-shaper` carries a hand-added `route_management: {enabled: true, mode: "dry_run"}` block (injected directly on the host in Phase 256, **never committed to the repo**). The repo's `configs/steering.yaml` has **no `route_management` block at all**. A naive `deploy.sh --with-steering` would scp the repo config over the live one, wiping the `dry_run` state and reverting `route_management.mode` to `off` / `enabled: false` — which **directly fails the D-04 smoke gate** (`mode=dry_run` becomes `off`). The plan MUST either (a) not let the steering deploy clobber `/etc/wanctl/steering.yaml`, or (b) restore/re-add the `route_management` block after deploy and before the smoke gate. This is the single highest-risk item in the phase. See Pitfall 1.

Live reality also revised the drift narrative: `route_ownership_guard.py` content **already matches repo** (sha256 identical — the v1.57 surgical rsync did land the corrected bytes). The remaining real drift vs repo is **stale artifacts** that the full pipeline cleans up, not stale content. See Runtime State Inventory.

**Primary recommendation:** Plan a config-preserving full deploy: capture the tarball anchor first; run `deploy.sh` per-WAN with steering, but treat `/etc/wanctl/steering.yaml` as host-owned state — back it up and restore (or re-inject) the `route_management` dry-run block before the smoke gate. Audit all 110 non-pyc files of the `src/wanctl/` tree plus the `/opt/wanctl/scripts` helper set with per-file sha256. Gate on live `:9102` `route_management.mode=dry_run` + `active_owner=netwatch` + `ownership_inspection.{inspector_status=ok, match=true}`, then rerun `phase260-observation.py` for the confirmatory `ready-for-approval`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — sha256 audit scope (RECON-01):** Audit the deploy-managed *code surface*, not the whole tree. `repo == prod` proven over the rsync-managed code tree (`src/wanctl/` → `/opt/wanctl/`, `__pycache__`/`*.pyc` excluded — matching `deploy.sh`'s rsync excludes) PLUS the standalone scripts `deploy.sh` installs under `/opt/wanctl/scripts`. Env-substituted configs, secrets, SSH keys, and runtime state under `/etc/wanctl` and `/var/lib/wanctl` are EXCLUDED by design (not byte-equal to repo and must not be). Strict per-file sha256 equality over this set; any mismatch fails RECON-01.

**D-02 — Rollback anchor (RECON-02):** Pre-deploy timestamped tarball of `/opt/wanctl` on `cake-shaper` as the rollback anchor. Prove RECON-02's "proven, exercised revert path" by restoring the anchor into a **scratch directory** and sha256-matching it against the anchor contents — NOT a live restore-over-`/opt/wanctl`. Rejected: full live restore-then-re-deploy (bounces steering twice for negligible added assurance). Anchor path/timestamp convention is planner discretion; record it in evidence so a real revert is one command.

**D-03 — Deploy + restart (RECON-01/03):** Full `deploy.sh` covering the complete production surface — both-WAN cake-autorate bridges + steering. Sequence service restarts (NOT a simultaneous bounce): restart with **steering last**, gate each restart on a `:9102` health check before proceeding. A steering restart in dry-run/safe mutates no routes (Netwatch owns the route; the cake-autorate shaper proper is separate from the `-state-bridge` units and untouched), so live impact is a sub-second blip with no ownership effect. Exact `deploy.sh` invocation/flags are planner discretion within "full prod surface."

**D-04 — Post-deploy clean-proof (RECON-03):** RECON-03 *gated* on a targeted post-deploy smoke assertion: all expected services `active`, steering `mode=dry_run`, `active_owner=netwatch`, and `:9102` `ownership_inspection` with `inspector_status=ok` AND `match=true`. AFTER the gate passes, re-run `scripts/phase260-observation.py` as confirmation that `ready-for-approval` still holds on the reconciled tree. The smoke assertion is the pass/fail gate; the harness rerun is confirmatory evidence, NOT a second gate.

### Claude's Discretion

sha256 manifest format and audit script CLI/flags; tarball anchor path + timestamp convention; precise `deploy.sh` invocation flags for "full prod surface"; restart sequencing order among bridge units (steering remains last); evidence/packet filenames and layout (mirror 257/260 convention); smoke-assertion script shape — provided all SAFE-22 boundaries hold, the audit covers the D-01 set, the rollback drill is non-disruptive (D-02), and no ownership behavior changes.

### Deferred Ideas (OUT OF SCOPE)

The actual single-route owner flip (Netwatch → wanctl), abort/auto-revert scaffolding, the rollback drill *for the route flip*, the operator approval gate, and the soak entry-gate — all belong to Phases 262–264 under SAFE-22, NOT here. No widening beyond the milestone's later phases.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECON-01 | Operator can run a full `deploy.sh` to `cake-shaper` bringing `/opt/wanctl` to repo-equal state (resolves `route_ownership_guard.py` drift), with pre/post sha256 audit proving repo==prod. | `deploy.sh` `deploy_code` (`rsync -av --delete`, excludes `__pycache__`/`*.pyc`) defines the audit set. Per-WAN invocation enumerated below. sha256 audit shape in Code Examples §Audit. NOTE: `route_ownership_guard.py` content already matches live (sha verified); remaining drift is stale artifacts (Runtime State Inventory). |
| RECON-02 | The reconcile captures a rollback anchor (pre-deploy `/opt/wanctl` snapshot) so the deploy is reversible. | Tarball-anchor + scratch-dir restore+sha256 drill in Code Examples §Anchor. Mirrors Phase 256 anchor convention (`/var/lib/wanctl/phase256-backups/<ts>/`). |
| RECON-03 | Post-deploy, route-management surface and `:9102` health come up clean in existing dry-run/safe state — reconcile alone changes no ownership behavior. | `:9102` smoke fields mapped to `health.py` builders + `route_manager.status_snapshot()`. Live target currently GREEN (verified). Confirmatory `phase260-observation.py` rerun → `ready-for-approval`. |
| SAFE-22 | Cross-cutting: only the reconcile `deploy.sh` is a permitted mutation. No CAKE/qdisc/threshold change, no controller-path source diff, no Netwatch change, no route-owner flip, no active route-management mode. | Deploy is config/code reconcile only; steering restarts in dry_run mutate no routes; audit/anchor/smoke are read-only. Controller-path files are not edited by this phase. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Production network control system — change conservatively.** Suggest, don't implement, for risky changes. Stability > safety > clarity > elegance.
- **Network projects (wanctl):** "Production-critical. Conservative: suggest, don't implement. Minimal changes only when approved." The live deploy + restart steps are operator-gated actions, not autonomous.
- **Portable controller architecture:** deployment-specific behavior belongs in YAML config, not Python branching. (Reinforces why `route_management` dry-run lives in host config, not repo code.)
- **Dev commands:** `.venv/bin/pytest`, `.venv/bin/ruff check src/ tests/`, `.venv/bin/mypy src/wanctl/`, `.venv/bin/ruff format`. Hot-path slice in CLAUDE.md.
- **Do not reintroduce timer-era guidance.** Active deployment is service-based.
- **Public-safe planning docs:** no live credentials/private IPs in `.planning` (memory: a prior milestone leaked a cred). cake-shaper is `10.10.110.223` (already in MEMORY/CLAUDE-adjacent docs; keep host specifics out of any public-facing artifact).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Code reconcile (`src/wanctl/` → `/opt/wanctl`) | Workstation (rsync push) | cake-shaper filesystem | `deploy.sh` runs from repo checkout, pushes over SSH with `--rsync-path='sudo rsync'`. |
| sha256 audit | Workstation (orchestrates) | cake-shaper (computes prod hashes via `sudo`) | Hashes must be computed on the host that holds the files; workstation compares manifests. |
| Tarball anchor + scratch restore drill | cake-shaper (filesystem) | — | Anchor is a snapshot of live `/opt/wanctl`; scratch restore stays on-host, off the live tree. |
| Service restart sequencing | cake-shaper (systemd) | Workstation (issues `ssh ... systemctl`) | Units are host-local; operator drives restart order from workstation. |
| `:9102` health smoke gate | cake-shaper (steering daemon serves) | Workstation (curl + assert) | Health server binds `127.0.0.1:9102` on cake-shaper; assertion reads it locally on-host or via ssh. |
| Confirmatory observation harness | cake-shaper (imports `/opt/wanctl`) | — | `phase260-observation.py` imports from deployed tree; must run on-host. |

## Standard Stack

No new external packages. This phase composes existing repo tooling + standard host utilities.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `scripts/deploy.sh` | repo HEAD | The reconcile mechanism (rsync code + scp scripts/configs/systemd) | [VERIFIED: repo] The only sanctioned deploy path; retiring the surgical-rsync shortcut is the entire point of RECON. |
| `rsync` | host-provided | `-av --delete` code sync, `--exclude=__pycache__ --exclude=*.pyc` | [VERIFIED: deploy.sh:224-233] Makes `/opt/wanctl/<src tree>` byte-equal to repo. |
| `sha256sum` (coreutils) | host-provided | Per-file hash manifest for the D-01 audit | [VERIFIED: live cake-shaper] Available; used in live verification this session. |
| `tar` | host-provided | Timestamped rollback anchor of `/opt/wanctl` (D-02) | [ASSUMED] Standard; mirrors Phase 256 anchor pattern. |
| `curl` + `python3` | host-provided | `:9102/health` smoke assertion (D-04) | [VERIFIED: live cake-shaper] Used this session to read the live gate target. |
| `scripts/phase260-observation.py` | repo HEAD | Confirmatory `ready-for-approval` rerun (D-04) | [VERIFIED: repo] Reused as-is; emits `OBSERVE_VERDICT:` token. |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `deploy.sh --dry-run` (`-n`) | Preview the rsync reconcile delta before the real run | Pre-flight witness of the `--delete` set (see Pitfall 2). |
| `scripts/validate-deployment.sh` | deploy.sh's own post-deploy validation (config sanity) | Runs automatically inside `deploy.sh`; not a substitute for the D-01 sha256 audit. |
| `diff -u` over sorted manifests | Cheap structural pre-check before per-file sha256 | Catches missing/extra files fast; deploy.sh `verify_deployment` already does a `*.py`-name-only diff (insufficient for D-01 — see Pitfall 4). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-file sha256 manifest | `rsync -ni --checksum` dry-run as the audit | rsync checksum dry-run proves "would not change" but produces no durable manifest artifact; D-01 wants an evidence-grade per-file manifest. Use rsync-checksum as a corroborating cross-check, not the primary proof. |
| `tar` anchor | `cp -a` / `rsync` snapshot dir | tar gives a single timestamped immutable artifact (easier to record as a one-command revert); Phase 256 used a directory snapshot. Either is acceptable per D-02 discretion; tar matches "timestamped tarball" wording. |
| Scratch-dir restore drill | Live restore-over-`/opt/wanctl` | Explicitly REJECTED by D-02 (double steering bounce). |

**Installation:** None. (No `## Package Legitimacy Audit` section required — this phase installs no external packages.)

## Architecture Patterns

### System Architecture Diagram

```
 WORKSTATION (repo checkout, ~/projects/wanctl)                CAKE-SHAPER (10.10.110.223, prod)
 ──────────────────────────────────────────                   ─────────────────────────────────
                                                               /opt/wanctl/        (code — AUDIT SCOPE)
 [0] tarball anchor  ──ssh sudo tar──────────────────────────▶ /var/lib/wanctl/<anchor-ts>/opt-wanctl.tgz
                                                                    │
 [0b] scratch restore drill (on-host) ─────────────────────────▶ /tmp scratch dir + sha256 vs anchor  (D-02 proof)
                                                                    │
 [1] deploy.sh --dry-run (-n)  ──rsync -ni──────────────────────▶ preview --delete set  (witness drift)
                                                                    │
 [2] deploy.sh spectrum cake-shaper --with-steering             │
        --with-spectrum-cake-autorate                           │
       deploy.sh att cake-shaper --with-att-cake-autorate       │
        rsync -av --delete src/wanctl/ ───────────────────────▶ /opt/wanctl/  (code reconciled)
        scp scripts/* configs/* systemd/* ────────────────────▶ /opt/wanctl/scripts, /etc/wanctl, /etc/systemd
                                                                    │  ⚠ steering.yaml scp CLOBBERS host route_management block
 [2b] PRESERVE/RESTORE /etc/wanctl/steering.yaml route_management dry-run block  (Pitfall 1)
                                                                    │
 [3] per-file sha256 audit  ──ssh sudo sha256sum──────────────▶ compare repo manifest vs prod manifest  (D-01 proof)
                                                                    │
 [4] sequenced restart (steering LAST), health-gated on :9102:  │
        cake-autorate-{spectrum,att}-state-bridge.service ─────▶ systemctl restart → gate :9101/:9102
        steering.service (LAST) ──────────────────────────────▶ systemctl restart → gate :9102
                                                                    │
 [5] smoke assertion (D-04 GATE) ──curl :9102/health───────────▶ route_management.mode=dry_run,
                                                                  active_owner=netwatch,
                                                                  ownership_inspection.{inspector_status=ok,match=true}
                                                                    │  PASS → proceed
 [6] confirmatory rerun  ──ssh python3 phase260-observation.py─▶ OBSERVE_VERDICT: ready-for-approval  (evidence)
```

### Recommended Evidence Structure (mirror 257/260)
```
.planning/phases/261-pre-flip-deploy-reconciliation/evidence/
├── phase261-rollback-anchor-<ts>.md          # D-02 anchor path + scratch-drill sha256 proof
├── phase261-sha256-audit-<ts>.md             # D-01 per-file manifest + repo==prod verdict
├── phase261-sha256-manifest-repo.txt         # raw repo-side sha256 manifest
├── phase261-sha256-manifest-prod.txt         # raw prod-side sha256 manifest
├── phase261-deploy-restart-<ts>.md           # D-03 deploy transcript + sequenced restart + :9102 gates
├── phase261-smoke-assertion-<ts>.md          # D-04 gate result (PASS/FAIL + raw :9102 JSON)
├── phase261-observation-raw.json             # confirmatory harness raw (harness writes this)
├── phase261-readiness-packet-<ts>.md         # confirmatory ready-for-approval packet
└── phase261-readonly-commands.txt            # COMMAND: lines for the harness (3 GET reads)
```

### Pattern 1: Per-WAN full-surface deploy (two invocations, not one)
**What:** `deploy.sh` couples `--with-spectrum-cake-autorate` to `WAN_NAME=spectrum` and `--with-att-cake-autorate` to `WAN_NAME=att` (asserted at deploy.sh:435/487 and re-validated at 947-955). There is NO single invocation that deploys both WANs' cake-autorate artifacts. "Full prod surface" = **two sequential invocations**.
**When to use:** Always for this phase — both WANs run cake-autorate bridges in prod.
**Example:** see Code Examples §Deploy.

### Pattern 2: Config-as-host-state (steering.yaml is NOT repo-equal)
**What:** `/etc/wanctl/steering.yaml` carries deployment-specific state (`route_management` dry-run block) that lives on the host, not in repo. The D-01 audit correctly excludes `/etc/wanctl` for exactly this reason — but the deploy STEP still scp's `configs/steering.yaml` over it. Treat the host config as authoritative state to preserve across deploy.
**When to use:** Any time the steering deploy runs. See Pitfall 1 for the concrete preserve/restore choreography.

### Anti-Patterns to Avoid
- **Trusting `deploy.sh verify_deployment` as the D-01 audit.** It diffs only `*.py` *filenames* (deploy.sh:656-669), not content, and not non-py files. Insufficient for "per-file sha256 equality."
- **Single `deploy.sh` call expecting both WANs.** Will error on the WAN_NAME guard.
- **Letting the steering deploy clobber the host `route_management` block.** Breaks the D-04 gate.
- **Live restore-over-`/opt/wanctl` to "prove" the anchor.** Rejected by D-02; bounces steering twice.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Code sync to prod | Custom scp loop / per-file copy | `scripts/deploy.sh` (`rsync -av --delete`) | The sanctioned path; `--delete` is what makes repo==prod provable. Hand-rolling re-creates the surgical-rsync shortcut RECON exists to retire. |
| Confirmatory readiness verdict | New observation script | `scripts/phase260-observation.py` as-is | Already emits `OBSERVE_VERDICT: ready-for-approval` and the SAFE no-mutation token block; reuse per D-04. |
| Route-ownership state read | Direct RouterOS scripting | `:9102/health` `route_management` + `ownership_inspection` sections | These are the contract surfaces; `route_manager.status_snapshot()` already computes `active_owner`/`mode`. |
| Smoke gate field extraction | Bespoke JSON walker with assumptions about nesting | Read `ownership_inspection` and `route_management` as **sibling** top-level keys | They are siblings in the payload (health.py:195-196); do not assume one nests in the other. |

**Key insight:** Every capability this phase needs already exists. The phase is choreography (anchor → deploy → audit → restart → gate → confirm) plus one config-preservation safeguard, not new code.

## Runtime State Inventory

> Rename/refactor/migration-style phase: this is a state-reconciliation deploy. The grep-finds-files vs runtime-state distinction is exactly what bit Phase 256/260 (the route_management block + surgical rsync), so this inventory is load-bearing.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None requiring migration. `/var/lib/wanctl/*` (state JSON, metrics DBs, phase256 anchors) is EXCLUDED from the D-01 audit by design and untouched by the reconcile. | None — verified excluded by D-01 and not in deploy.sh's `/opt/wanctl` rsync scope. |
| **Live service config** | **`/etc/wanctl/steering.yaml` carries a host-only `route_management: {enabled: true, mode: "dry_run", migration_acknowledged: false, routes: {spectrum, att, att_policy}}` block** (hand-added in Phase 256, [VERIFIED: Phase 256 evidence `phase256-deploy-restart-...md`]). Repo `configs/steering.yaml` has **no** `route_management` block [VERIFIED: repo grep — NONE]. `deploy.sh --with-steering` scp's repo config over it (deploy.sh:416-419). | **PRESERVE the live config across deploy** (backup + restore, or skip the steering.yaml scp, or re-inject the block) BEFORE the smoke gate. Highest-risk action item — see Pitfall 1. |
| **OS-registered state** | systemd units on cake-shaper: `steering.service`, `cake-autorate-{spectrum,att}.service`, `cake-autorate-{spectrum,att}-state-bridge.service`. deploy.sh re-scp's unit files + `daemon-reload`. Unit *content* is in the audit-adjacent surface but units live in `/etc/systemd/system` (not `/opt/wanctl`, so outside the strict D-01 set). | Confirm unit files unchanged or intentionally reconciled; `daemon-reload` is invoked by deploy.sh. No enable/disable changes (SAFE-22). |
| **Secrets/env vars** | `/etc/wanctl/secrets` (`ROUTER_PASSWORD`, `DISCORD_WEBHOOK_URL`), `/etc/wanctl/ssh/`. EXCLUDED from D-01 by design. deploy.sh does not overwrite `secrets`. | None — excluded; deploy.sh `verify_deployment` only *checks* secrets presence, never writes them. |
| **Build artifacts / stale files** | **Live drift vs repo is STALE ARTIFACTS, not stale content** [VERIFIED live 2026-06-26]: (1) `/opt/wanctl/.phase259-backup-20260625T014037Z/{steering/daemon.py, steering/health.py}` — 2 extra `.py` files `rsync --delete` WILL sweep; (2) `/opt/wanctl/scripts/phase259-ownership-proof.py` + its `__pycache__` — a stale evidence script OUTSIDE the rsync-managed `src/wanctl` tree, so the code rsync will NOT remove it (deploy.sh writes scripts/ via separate scp; the src rsync prunes `/opt/wanctl/scripts` via `verify_deployment`'s prune but does not delete it). `route_ownership_guard.py` content **already matches repo** (sha256 identical — surgical rsync landed it). | The full deploy `rsync --delete` removes the `.phase259-backup-*` dir. Decide whether the stale `/opt/wanctl/scripts/phase259-ownership-proof.py` should remain (it is not deploy-managed); if D-01 audit scope includes `/opt/wanctl/scripts`, it is an EXTRA file the audit will flag — plan an explicit disposition (sweep it, or scope the scripts-audit to deploy.sh's known installed set only). |

**The canonical question:** After `rsync -av --delete src/wanctl/` lands, the `src/wanctl` mirror is byte-equal to repo (pyc excluded) and the stale backup dir is gone. The two residual non-repo-equal surfaces are intentional/host-state: `/etc/wanctl/steering.yaml` (preserve) and `/opt/wanctl/scripts/phase259-ownership-proof.py` (decide disposition).

## Common Pitfalls

### Pitfall 1: Steering config clobber wipes the dry-run state (CRITICAL — breaks D-04)
**What goes wrong:** `deploy.sh ... --with-steering` scp's repo `configs/steering.yaml` (no `route_management` block) over the live `/etc/wanctl/steering.yaml` (which has `route_management: {enabled: true, mode: dry_run}`). After restart, `daemon.py:_load_route_management_config` reads no block → `enabled=False, mode="off"` → `:9102` reports `route_management.mode=off`, `enabled=false`. The D-04 smoke gate requires `mode=dry_run` and **FAILS**.
**Why it happens:** The dry-run block was hand-injected on the host in Phase 256 and never committed to repo. The repo config is genuinely behind the live config for this block.
**How to avoid (planner picks one, all SAFE-22-clean):**
  1. **Backup + restore** `/etc/wanctl/steering.yaml` around the deploy: `sudo cp` it to the anchor dir before deploy, and `sudo install -m0640 -o root -g wanctl` it back after the steering scp, before restarting steering. (Phase 256 used exactly this restore command — see evidence line 206.)
  2. **Re-inject the `route_management` block** post-deploy from a known-good snippet, before the steering restart.
  3. **Commit the `route_management` dry-run block to repo `configs/steering.yaml` FIRST** (a real repo edit, behavior-preserving for dry-run), so the deploy is idempotent and no host-state divergence remains. This is the cleanest long-term fix and makes `repo==prod` true for the config too — but it is a repo source change, so it must be an explicit, reviewed plan task (and re-run `make ci`). Recommended if the team wants to end the host-config drift permanently; otherwise option 1.
**Warning signs:** Post-deploy `:9102` shows `route_management.enabled=false` / `mode=off`; `active_owner` still `netwatch` (so easy to miss if you only check owner). Always assert `mode` explicitly.
**Note:** `active_owner=netwatch` is returned for BOTH `mode=off` and `mode=dry_run` (route_manager.py:`_active_owner` returns `"netwatch"` whenever mode != active). So `active_owner` alone does NOT detect the clobber — `mode` is the discriminating field.

### Pitfall 2: `rsync --delete` removes files present in prod but not repo
**What goes wrong:** The full deploy's `rsync -av --delete` deletes anything under `/opt/wanctl` (within the synced `src/wanctl` mirror) that isn't in repo. Live audit found `/opt/wanctl/.phase259-backup-20260625T014037Z/` (2 .py files) that WILL be swept.
**Why it happens:** Stale on-host backup/evidence directories accumulate under the deploy root.
**How to avoid:** Run `deploy.sh --dry-run` first and read the `deleting ...` lines as a witness (also satisfies the CONTEXT "useful witness to the D-07 drift" note). Confirm every deletion is an intended stale artifact, not live state, BEFORE the real run. (The `.phase259-backup-*` sweep is benign and desirable.)
**Warning signs:** dry-run shows `deleting` for a path you don't recognize → stop and inspect.

### Pitfall 3: `/opt/wanctl/scripts` is NOT covered by the src rsync `--delete`
**What goes wrong:** deploy.sh installs helper scripts under `/opt/wanctl/scripts` via individual scp (analyze_baseline.py, validate-deployment.sh, wanctl-history, wanctl-operator-summary, compact-metrics-dbs.sh) — NOT via the `src/wanctl/` rsync. `verify_deployment` explicitly **prunes** `/opt/wanctl/scripts` from its tree check (deploy.sh:659). So a stale script there (live: `phase259-ownership-proof.py`) is neither swept nor audited by deploy.sh.
**Why it happens:** The scripts dir is a separate, additive install surface.
**How to avoid:** Decide D-01's treatment of `/opt/wanctl/scripts` explicitly. The clean reading of D-01 ("the standalone scripts deploy.sh installs under /opt/wanctl/scripts") is to audit **only the deploy.sh-installed set** there, comparing each installed script's prod sha256 to its repo source — and to separately note/sweep any extra non-managed file. Don't audit the whole `/opt/wanctl/scripts` dir as if it must equal a repo dir (there is no 1:1 repo `scripts/` → `/opt/wanctl/scripts` mirror; repo `scripts/` is a flat dir, only a curated subset lands under `/opt/wanctl/scripts`).
**Warning signs:** Audit flags `phase259-ownership-proof.py` as "extra in prod" → expected; disposition = sweep or whitelist.

### Pitfall 4: `verify_deployment` is filename-only, not content (don't mistake it for the audit)
**What goes wrong:** deploy.sh's built-in `verify_deployment` passes when `*.py` *filenames* match — it never compares content and ignores non-py files (e.g. `dashboard/dashboard.tcss`). Relying on it gives false confidence of `repo==prod`.
**Why it happens:** It was written as a structural sanity check, not a byte-equality proof.
**How to avoid:** D-01 requires an independent per-file **sha256** manifest over all 110 non-pyc `src/wanctl` files (109 `.py` + `dashboard/dashboard.tcss`) plus the deploy-managed `/opt/wanctl/scripts` set. See Code Examples §Audit.

### Pitfall 5: steering restart → `:9102` readiness timing (health "starting"/"degraded" window)
**What goes wrong:** Immediately after `systemctl restart steering.service`, `:9102/health` may return `status: "starting"` (daemon up but state not yet populated — health.py:142-144) or transiently `degraded` (consecutive_failures, router not yet reached). Asserting the smoke gate too early yields a false FAIL.
**Why it happens:** The daemon builds full health only after the first cycle populates `state["current_state"]`; `ownership_inspection.last_inspected_at` must also advance.
**How to avoid:** Gate with a bounded poll loop: after each restart, poll `:9102` until `status` is `healthy`/`degraded` (not `starting`) AND `ownership_inspection.inspector_status=="ok"` with a fresh `last_inspected_at`, with a timeout. The `phase260-observation.py` `gate_sample` already encodes the fail-closed sample logic; the smoke assertion should reuse the same field checks.
**Warning signs:** First poll shows `{"status":"starting"}` with no `route_management` section yet → wait and re-poll, don't fail.

### Pitfall 6: cake-autorate *shaper* vs *state-bridge* units (don't restart the shaper)
**What goes wrong:** Restarting `cake-autorate-{spectrum,att}.service` (the shaper proper) would bounce live rate shaping on production WANs — a real traffic impact, and arguably a CAKE-path disturbance. The reconcile only needs the wanctl-side **state-bridge** + steering units restarted to pick up new `/opt/wanctl` code.
**Why it happens:** The two unit families have similar names.
**How to avoid:** D-03's "sequenced restart" should target the wanctl-side consumers of the deployed code: `cake-autorate-{spectrum,att}-state-bridge.service` (poll cake-autorate log → write state JSON, publish `:9101`) and `steering.service` LAST. The shaper units (`cake-autorate-{spectrum,att}.service`) run upstream cake-autorate's own `.sh` and import nothing from `/opt/wanctl` Python — restarting them is unnecessary and risk-additive. Confirm this scoping in the plan. [CONTEXT D-03 confirms: "the cake-autorate shaper proper is a separate service from the `-state-bridge` units and is untouched."]
**Warning signs:** A restart command list that includes `cake-autorate-spectrum.service` (no `-state-bridge`) → stop; that's the shaper.

## Code Examples

> All commands below are illustrative shapes for the planner. Live mutating steps are operator-gated. Read-only audit/anchor/smoke shapes were validated against live `cake-shaper` this session.

### Anchor (D-02): tarball capture + non-disruptive scratch-dir restore drill
```bash
TS=$(date -u +%Y%m%dT%H%M%SZ)
ANCHOR_DIR=/var/lib/wanctl/phase261-backups/$TS
# 1. Capture timestamped tarball of live /opt/wanctl (the rollback anchor)
ssh cake-shaper "sudo mkdir -p $ANCHOR_DIR && \
  sudo tar -C /opt -czf $ANCHOR_DIR/opt-wanctl.tgz wanctl && \
  sudo sha256sum $ANCHOR_DIR/opt-wanctl.tgz | sudo tee $ANCHOR_DIR/opt-wanctl.tgz.sha256"
# 2. Non-disruptive scratch restore + sha256 match (NEVER touches live /opt/wanctl)
ssh cake-shaper "SCRATCH=\$(mktemp -d /tmp/phase261-restore.XXXXXX) && \
  sudo tar -C \$SCRATCH -xzf $ANCHOR_DIR/opt-wanctl.tgz && \
  # per-file sha256 of restored scratch vs live anchor source
  diff <(cd \$SCRATCH/wanctl && sudo find . -type f -not -name '*.pyc' -not -path '*__pycache__*' -exec sha256sum {} + | sort -k2) \
       <(cd /opt/wanctl && sudo find . -type f -not -name '*.pyc' -not -path '*__pycache__*' -exec sha256sum {} + | sort -k2) \
  && echo PHASE261_RESTORE_DRILL_PASS || echo PHASE261_RESTORE_DRILL_FAIL; \
  sudo rm -rf \$SCRATCH"
# Record $ANCHOR_DIR in evidence so a real revert is one command:
#   sudo systemctl stop steering.service && sudo tar -C /opt -xzf $ANCHOR_DIR/opt-wanctl.tgz && sudo systemctl start steering.service
```
Source: pattern mirrors Phase 256 anchors at `/var/lib/wanctl/phase256-backups/<ts>/` [VERIFIED: Phase 256 evidence].

### Deploy (D-03): full prod surface = two per-WAN invocations + config preservation
```bash
# 0. (Pitfall 1) Preserve the host steering.yaml route_management dry-run block
ssh cake-shaper "sudo cp -a /etc/wanctl/steering.yaml $ANCHOR_DIR/steering.yaml.host-pre-deploy"

# 1. Dry-run witness of the --delete reconcile delta (Pitfall 2)
./scripts/deploy.sh spectrum cake-shaper --with-steering --with-spectrum-cake-autorate --dry-run

# 2. Real reconcile — Spectrum (code rsync + steering + spectrum bridge artifacts)
./scripts/deploy.sh spectrum cake-shaper --with-steering --with-spectrum-cake-autorate
# 3. Real reconcile — ATT (bridge artifacts; code already synced by step 2, idempotent)
./scripts/deploy.sh att cake-shaper --with-att-cake-autorate

# 4. (Pitfall 1) Restore host route_management block BEFORE restarting steering
ssh cake-shaper "sudo install -m 0640 -o root -g wanctl \
  $ANCHOR_DIR/steering.yaml.host-pre-deploy /etc/wanctl/steering.yaml"
#   (OR adopt the block into repo configs/steering.yaml first — Pitfall 1 option 3 — and skip restore)
```
Notes: `--with-spectrum-cake-autorate` requires `WAN_NAME=spectrum`; `--with-att-cake-autorate` requires `WAN_NAME=att` [VERIFIED: deploy.sh:435,487,947-955]. Both invocations run the `src/wanctl` rsync (idempotent on the 2nd). The Phase 201 predeploy gate runs only for `WAN_NAME=spectrum` (deploy.sh:204) — ensure `/etc/wanctl/spectrum.yaml` is reconciled or the Spectrum deploy fail-closes (exit ≠ 0).

### Sequenced restart (D-03): state-bridges, steering LAST, health-gated
```bash
# Restart wanctl-side code consumers only; NOT the cake-autorate shaper units (Pitfall 6)
gate_9102() {  # poll until ready or timeout
  for i in $(seq 1 30); do
    J=$(ssh cake-shaper "curl -fsS http://127.0.0.1:9102/health" 2>/dev/null) || { sleep 2; continue; }
    echo "$J" | python3 -c 'import sys,json; d=json.load(sys.stdin);
oi=d.get("ownership_inspection",{});
sys.exit(0 if d.get("status") in ("healthy","degraded") and oi.get("inspector_status")=="ok" else 1)' && return 0
    sleep 2
  done; return 1
}
ssh cake-shaper "sudo systemctl restart cake-autorate-spectrum-state-bridge.service"; gate_9102
ssh cake-shaper "sudo systemctl restart cake-autorate-att-state-bridge.service";      gate_9102
ssh cake-shaper "sudo systemctl restart steering.service";                            gate_9102  # LAST
```
Note: state-bridges publish `:9101` (LAN-bound `10.10.110.223:9101` / `.227:9101`), steering publishes `:9102` (localhost). The `:9102` gate is the cross-unit health check per D-03.

### Audit (D-01): per-file sha256 manifest, repo vs prod
```bash
# Repo-side manifest: all non-pyc files in src/wanctl (110 files: 109 .py + dashboard.tcss)
( cd src/wanctl && find . -type f -not -name '*.pyc' -not -path '*__pycache__*' \
    -exec sha256sum {} + | sort -k2 ) > phase261-sha256-manifest-repo.txt
# Prod-side manifest: same tree under /opt/wanctl, excluding the scripts/ helper dir
ssh cake-shaper "cd /opt/wanctl && sudo find . -path ./scripts -prune -o -type f \
    -not -name '*.pyc' -not -path '*__pycache__*' -print0 | sudo xargs -0 sha256sum | sort -k2" \
  > phase261-sha256-manifest-prod.txt
# Verdict
diff -u phase261-sha256-manifest-repo.txt phase261-sha256-manifest-prod.txt \
  && echo PHASE261_AUDIT_SRC_TREE_EQUAL || echo PHASE261_AUDIT_SRC_TREE_MISMATCH
# Deploy-managed scripts under /opt/wanctl/scripts: compare each installed script to its repo source
for f in analyze_baseline.py validate-deployment.sh wanctl-history wanctl-operator-summary compact-metrics-dbs.sh; do
  R=$(case $f in analyze_baseline.py) sha256sum scripts/analyze_baseline.py;; *) sha256sum scripts/$f;; esac | awk '{print $1}')
  P=$(ssh cake-shaper "sudo sha256sum /opt/wanctl/scripts/$f 2>/dev/null" | awk '{print $1}')
  [ "$R" = "$P" ] && echo "OK  $f" || echo "MISMATCH/MISSING $f repo=$R prod=$P"
done
# Note any EXTRA file under /opt/wanctl/scripts not in the managed set (live: phase259-ownership-proof.py) — Pitfall 3
```
Source: file set verified live this session (`find src/wanctl -type f -not -path '*__pycache__*' -not -name '*.pyc' | wc -l` = 110; prod `*.py` = 109 after stale-backup sweep) [VERIFIED: repo + live cake-shaper].

### Smoke gate (D-04): the PASS/FAIL assertion
```bash
ssh cake-shaper "curl -fsS http://127.0.0.1:9102/health" | python3 -c '
import sys, json
d = json.load(sys.stdin)
rm = d.get("route_management", {})            # sibling key
oi = d.get("ownership_inspection", {})        # sibling key
checks = {
  "route_management.mode==dry_run":        rm.get("mode") == "dry_run",
  "route_management.active_owner==netwatch": rm.get("active_owner") == "netwatch",
  "ownership_inspection.inspector_status==ok": oi.get("inspector_status") == "ok",
  "ownership_inspection.match==true":      oi.get("match") is True,
}
for k, v in checks.items(): print(("PASS" if v else "FAIL"), k)
sys.exit(0 if all(checks.values()) else 1)'
# Also assert all expected units active:
ssh cake-shaper "sudo systemctl is-active steering.service \
  cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service \
  cake-autorate-att.service cake-autorate-att-state-bridge.service"
```
Field provenance [VERIFIED: source]:
- `route_management.mode`, `route_management.active_owner`, `route_management.enabled` ← `RouteManager.status_snapshot()` (route_manager.py:280-315), surfaced by `health.py:_build_route_management_section` (health.py:354-391).
- `_active_owner` returns `"netwatch"` unless `mode=="active"` AND `active_allowed` (route_manager.py:398-403) — so it is `netwatch` for both `off` and `dry_run`; **assert `mode` to detect a clobber** (Pitfall 1).
- `ownership_inspection.{inspector_status,match,observed_owner,configured_owner,last_inspected_at}` ← `health.py:_build_ownership_inspection_section` (health.py:393-418), fed by `RouteOwnershipInspector`.

### Confirmatory rerun (D-04): phase260 harness → ready-for-approval
```bash
# Reuse the readonly command file shape (3 GET reads) and run on-host against the reconciled tree
ssh cake-shaper "cd /opt/wanctl/scripts && sudo python3 phase260-observation.py \
  /path/to/phase261-readonly-commands.txt \
  --config /etc/wanctl/steering.yaml \
  --health-url http://127.0.0.1:9102/health \
  --evidence-dir /path/to/evidence"
# Verdict token to grep: 'OBSERVE_VERDICT: ready-for-approval' (exit 0).
```
Verdict semantics [VERIFIED: phase260-observation.py:444-447, 870-908]: `compute_verdict` returns `ready-for-approval` only when there are **zero divergences AND zero mutation-token hits**; otherwise `not-ready`. `main()` returns exit 0 only on `ready-for-approval`. "ready-for-approval" is a *verdict*, explicitly NOT operator approval (that is Phase 263 / SAFE-21 D-10). The harness defaults: `--window-sec 636`, `--interval-sec 60`, `DEFAULT_CONFIG=/etc/wanctl/steering.yaml`, `DEFAULT_HEALTH_URL=http://127.0.0.1:9102/health`. The harness asserts its imports resolve under `/opt/wanctl` (`_assert_deployed_imports`) — so it must run on-host after the reconcile, which is the point (it re-validates the freshly-deployed tree).

**Caveat for the rerun:** `phase260-observation.py` is itself one of the files installed under `/opt/wanctl/scripts`... but live `/opt/wanctl/scripts/` currently contains `phase259-ownership-proof.py`, NOT `phase260-observation.py`. The harness is in repo `scripts/` but is NOT in deploy.sh's `ANALYSIS_SCRIPTS`/installed set, so the full `deploy.sh` will NOT place it under `/opt/wanctl/scripts`. The plan must explicitly copy `scripts/phase260-observation.py` to the host to run it (as Phase 260 did), OR run it with `PYTHONPATH=/opt` from a temp location. This is a concrete plan task, not an assumption.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Surgical single-file rsync to push a fix to prod | Full `deploy.sh` reconcile + sha256 audit | v1.57 D-07 fix exposed the gap; Phase 261 closes it | RECON exists specifically to retire the surgical shortcut. |
| `verify_deployment` filename diff as "proof" | Independent per-file sha256 manifest | This phase (D-01) | Byte-equality, not name-equality. |
| Phase 256 directory-snapshot anchor | Timestamped tarball + scratch-restore drill | This phase (D-02) | Single immutable artifact + exercised (not asserted) restore. |

**Deprecated/outdated:**
- Treating `route_ownership_guard.py` as the live content drift: **outdated** — its content already matches repo (sha verified live 2026-06-26). The residual drift is stale artifacts + the host-only config block.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tar`/`mktemp`/`xargs` available on cake-shaper for anchor + drill | Standard Stack / Code Examples | Low — standard Debian utils; `sha256sum`/`curl`/`python3` already verified present this session. Mitigate: probe in a Wave-0 read-only check. |
| A2 | The ATT deploy invocation (`att cake-shaper --with-att-cake-autorate`, no `--with-steering`) does NOT re-clobber steering.yaml | Code Examples §Deploy | Low — `deploy_steering_systemd` only runs under `--with-steering`. But the 2nd invocation DOES re-run the `src/wanctl` rsync and `deploy_config att` (which scp's `configs/att.yaml`, not steering.yaml). Confirm `att.yaml` host-vs-repo is acceptable (same class of config-state question as steering.yaml — likely env-substituted, excluded from D-01). Plan should witness via dry-run. |
| A3 | Restarting only the `-state-bridge` + steering units (not the shaper units) is sufficient to load new `/opt/wanctl` code | Pitfall 6 / Code Examples | Low — CONTEXT D-03 explicitly states the shaper is separate and untouched. Confirm bridge units import from `/opt/wanctl` (they are parameterized Python per CLAUDE.md service model). |
| A4 | Re-injecting/preserving the host `route_management` dry-run block is SAFE-22-clean (it is dry-run, not active) | Pitfall 1 | Low — `mode: dry_run` mutates no routes (route_manager dry_run path is record-only). Adopting it into repo (option 3) is a behavior-preserving config edit, not a controller-path source diff. |
| A5 | Disposition of `/opt/wanctl/scripts/phase259-ownership-proof.py` (sweep vs whitelist) is a planner choice, not a SAFE-22 concern | Pitfall 3 / Runtime State Inventory | Low — it is a read-only evidence script; removing or keeping it has no controller/route effect. |

## Open Questions (RESOLVED)

> Both questions were resolved at plan time and are baked into the Phase 261 plans (committed
> `98157a6f`). Q1 → **option 1** (host-only backup+restore of the `route_management` block;
> NO repo source edit) to keep Phase 261 strictly reconcile-only and SAFE-22-clean — the
> permanent repo-adopt (option 3) is deferred to a later phase. Q2 → audit the
> **deploy.sh-installed subset** of `/opt/wanctl/scripts` per-file vs repo sources, and
> separately enumerate/dispose extras.

1. **RESOLVED (option 1): Should the `route_management` dry-run block be committed to repo `configs/steering.yaml` (Pitfall 1, option 3)?**
   - What we know: Live config has it; repo does not; deploy clobbers it. Option 3 ends the drift permanently and makes `repo==prod` true for the config too.
   - What's unclear: Whether the team wants the dry-run block as a committed default (it would ship the route-management surface "on in dry_run" to any future deploy target) vs. keeping it host-specific.
   - Recommendation: Prefer option 3 IF the milestone intends cake-shaper to carry route-management going forward (it does — Phases 262-264). Make it an explicit reviewed plan task with `make ci`. Otherwise use option 1 (backup+restore) to keep the phase strictly reconcile-only. Surface this to the operator at plan/discuss time.

2. **RESOLVED (deploy.sh-installed subset): Does D-01's `/opt/wanctl/scripts` audit compare to a repo dir, or to the deploy.sh-installed set?**
   - What we know: There is no 1:1 repo↔prod `scripts/` mirror; deploy.sh installs a curated subset.
   - What's unclear: Exact intended audit set for the scripts portion.
   - Recommendation: Audit only the deploy.sh-installed subset (analyze_baseline.py, validate-deployment.sh, wanctl-history, wanctl-operator-summary, compact-metrics-dbs.sh) per-file vs their repo sources, and separately enumerate/dispose extras. Confirm with planner.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SSH to `cake-shaper` (`10.10.110.223`) | every step | ✓ | key auth (id_ed25519) | none — hard requirement |
| `sudo` on cake-shaper | anchor, audit (prod hashes), restart, config restore | ✓ (assumed; reads worked, mutating needs operator) | — | operator-at-keyboard for privileged mutation |
| `sha256sum`, `curl`, `python3` on cake-shaper | audit, smoke gate | ✓ | verified live this session | none needed |
| `tar`, `mktemp`, `xargs` on cake-shaper | anchor + scratch drill | ✓ (A1, standard) | — | probe in Wave 0 |
| `rsync` local + remote | deploy.sh | ✓ (deploy.sh checks both) | — | deploy.sh fail-closes if missing |
| Live `steering.service` serving `:9102` | smoke gate, harness | ✓ | version 1.47.0, `mode=dry_run`, `active_owner=netwatch` (verified live) | none — must be up post-restart |

**Missing dependencies with no fallback:** None identified. All required tooling verified present or standard.

## Validation Architecture

> nyquist_validation: enabled (not disabled in config). This section maps each RECON requirement to observable signals so a VALIDATION.md can be derived.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo `.venv/bin/pytest`) |
| Config file | `pyproject.toml` (per CLAUDE.md) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_phase260_observation.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

**Important:** RECON-01/02/03 are **live-evidence requirements**, not unit-test requirements. Their "tests" are the on-host audit/anchor/smoke/harness artifacts, not pytest cases. The relevant pytest coverage is the harness/guard logic that the confirmatory rerun depends on (`tests/test_phase260_observation.py`, route_manager/health unit tests), which must stay green to trust the rerun verdict.

### Phase Requirements → Observable Signal Map
| Req ID | Behavior | Proof Type | Observable Signal / Command | Artifact |
|--------|----------|-----------|------------------------------|----------|
| RECON-01 | repo==prod over D-01 set after full deploy | live audit | `diff` of repo vs prod sha256 manifests → `PHASE261_AUDIT_SRC_TREE_EQUAL`; per-script sha match for `/opt/wanctl/scripts` set | `phase261-sha256-audit-<ts>.md` + both manifests |
| RECON-01 | full `deploy.sh` pipeline exercised (not surgical) | deploy transcript | both per-WAN invocations complete; `--dry-run` witness of `--delete` set captured | `phase261-deploy-restart-<ts>.md` |
| RECON-01 | drift resolved | live sha | post-deploy `route_ownership_guard.py` (and full tree) sha == repo; `.phase259-backup-*` swept | audit manifest |
| RECON-02 | rollback anchor captured | live file | `$ANCHOR_DIR/opt-wanctl.tgz` exists + `.sha256` recorded | `phase261-rollback-anchor-<ts>.md` |
| RECON-02 | revert path proven/exercised (non-disruptive) | scratch drill | `PHASE261_RESTORE_DRILL_PASS` (scratch restore sha == anchor; live `/opt/wanctl` untouched) | anchor evidence |
| RECON-03 | route-mgmt + `:9102` clean in dry-run/safe (GATE) | smoke assertion | all 4 checks PASS: `route_management.mode==dry_run`, `active_owner==netwatch`, `ownership_inspection.inspector_status==ok`, `match==true`; all units `active` | `phase261-smoke-assertion-<ts>.md` (raw JSON included) |
| RECON-03 | reconciled tree still ready (confirmatory) | harness rerun | `OBSERVE_VERDICT: ready-for-approval` (exit 0) | `phase261-readiness-packet-<ts>.md` + `-observation-raw.json` |
| SAFE-22 | no forbidden mutation | token scan + diff | harness `MUTATION_TOKEN_HITS: []`; no controller-path source diff in deploy; no route-owner flip (`active_owner` stays `netwatch`); no CAKE/qdisc change | readiness packet SAFE block |

### Sampling Rate
- **Per task commit (planning/code tasks only, e.g. Pitfall-1 option 3 config edit):** `.venv/bin/pytest -o addopts='' tests/test_phase260_observation.py -q` + `ruff check` + `mypy src/wanctl/`.
- **Per live-action gate:** the smoke assertion (D-04) is the binary PASS/FAIL before proceeding to the confirmatory rerun.
- **Phase gate:** D-04 smoke PASS, then harness `ready-for-approval`, then full audit `EQUAL` before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] Read-only environment probe on cake-shaper: confirm `tar`/`mktemp`/`xargs` present (A1), and snapshot current `:9102` JSON as the pre-deploy baseline.
- [ ] Decide Pitfall-1 strategy (preserve/restore vs repo-adopt) — blocks the deploy task design.
- [ ] Decide `/opt/wanctl/scripts` audit scope (Open Q2) — blocks the audit task design.
- [ ] Stage `scripts/phase260-observation.py` + a `phase261-readonly-commands.txt` (3 GET reads, copy the Phase 260 file verbatim) onto the host for the confirmatory rerun (it is not deploy-installed).
- [ ] No new pytest files required; existing harness/route-manager/health tests cover the logic the live proofs depend on. Confirm they are green before the live run.

## Security Domain

> security_enforcement: enabled (absent = enabled).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | SSH key auth only (id_ed25519); no passwords in transit. `ROUTER_PASSWORD` stays in `/etc/wanctl/secrets`, excluded from audit/evidence. |
| V4 Access Control | yes | Privileged ops (`sudo` tar/rsync/restart/config restore) are operator-gated per CLAUDE.md "suggest, don't implement." `:9102` binds `127.0.0.1` only (health.py default host). |
| V5 Input Validation | yes | Confirmatory harness validates the local health URL is `http` + local host (`_validate_local_health_url`) and validates readonly command file before any run (`readonly_validator`). |
| V6 Cryptography | yes (integrity, not secrecy) | sha256 for file-integrity proofs (audit + anchor drill) — coreutils `sha256sum`, never hand-rolled. |
| V7 Error Handling/Logging | yes | `gate_sample` / `sample_health` fail **closed** on any error (bad-sample sentinel → not-ready). Smoke gate must adopt the same fail-closed posture. |

### Known Threat Patterns for this phase
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Config clobber silently disables dry-run safety state | Tampering / DoS-of-safety | Preserve/restore host steering.yaml; assert `mode` explicitly in smoke gate (Pitfall 1). |
| `rsync --delete` removes live state mistaken for stale | Tampering | `--dry-run` witness before real run; D-01 excludes `/etc/wanctl` + `/var/lib/wanctl` (no live state under the synced tree). |
| Credential leakage into planning evidence | Information Disclosure | Audit excludes `/etc/wanctl/secrets`; never paste secrets/host creds into `.planning` (MEMORY: prior leak incident). |
| Stale evidence script left executable on prod | minor (surface area) | Disposition decision for `/opt/wanctl/scripts/phase259-ownership-proof.py` (Pitfall 3). |
| Restarting the wrong cake-autorate unit disrupts live shaping | DoS (production traffic) | Restart only `-state-bridge` + steering, never the shaper proper (Pitfall 6). |

## Sources

### Primary (HIGH confidence — verified this session)
- `scripts/deploy.sh` (repo) — rsync excludes (`__pycache__`/`*.pyc`), `--delete`, per-WAN `--with-{spectrum,att}-cake-autorate` guards, `--with-steering` config scp, `verify_deployment` filename-only diff, Phase 201 predeploy gate. Lines cited inline.
- `scripts/phase260-observation.py` (repo) — `compute_verdict`, `gate_sample`, `_assert_deployed_imports`, defaults, `OBSERVE_VERDICT` token, exit semantics.
- `src/wanctl/steering/health.py` (repo) — `_build_route_management_section` (354-391), `_build_ownership_inspection_section` (393-418), sibling keys, `:9102` bind.
- `src/wanctl/steering/route_manager.py` (repo) — `status_snapshot` (280-315), `_active_owner` (398-403: `netwatch` unless active+allowed).
- `src/wanctl/steering/daemon.py` (repo) — `_load_route_management_config` (366-388: no block → off/disabled), `_init_route_management` (1199-1227).
- **Live `cake-shaper` reads (2026-06-26):** `route_ownership_guard.py` sha == repo (already reconciled); prod has 111 `.py` vs repo 109 → 2 extra = `.phase259-backup-*` dir (rsync `--delete` sweeps); `/opt/wanctl/scripts/` holds stale `phase259-ownership-proof.py`; live `:9102` `route_management.mode=dry_run`, `active_owner=netwatch`, `ownership_inspection.{inspector_status=ok, match=true}`, version 1.47.0; `src/wanctl` non-pyc file count = 110.
- Phase 256 evidence `phase256-deploy-restart-20260620T034124Z.md` — proves `route_management` block was hand-added to host `/etc/wanctl/steering.yaml` (not repo); records the `sudo install -m0640 -o root -g wanctl ... steering.yaml` restore command.
- `.planning/phases/261-.../261-CONTEXT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md` — locked decisions, RECON reqs, SAFE-22.

### Secondary (MEDIUM)
- `configs/examples/steering.yaml.example` (136-147) — canonical `route_management` block shape (`enabled/mode/routes`).
- Git history: drift commit `3075f85a` touches `route_ownership_guard.py` + `phase260-observation.py` + tests; live re-run `dd6043e0`.

### Tertiary (LOW)
- None. No claim rests on unverified web/training data.

## Metadata

**Confidence breakdown:**
- Deploy/audit mechanics: HIGH — read deploy.sh end-to-end; audit file set counted live.
- Smoke-gate field provenance: HIGH — traced every field to its source builder + confirmed live values.
- Config-clobber landmine: HIGH — confirmed repo has no block, host has the block, deploy scp's the repo config, Phase 256 evidence corroborates the hand-edit.
- Rollback anchor / restart sequencing: HIGH for the shape; the exact unit list and `att.yaml` config behavior should be witnessed via `--dry-run` at plan time (A2).
- SAFE-22 cleanliness: HIGH — every action is reconcile/read-only/dry-run; no controller-path edit, no route flip.

**Research date:** 2026-06-26
**Valid until:** 2026-07-10 (14 days) — but the LIVE facts (sha match, stale-artifact set, `:9102` state) are point-in-time; re-witness with the `--dry-run` and a fresh `:9102` snapshot at plan execution, since prod can change between now and the deploy.
