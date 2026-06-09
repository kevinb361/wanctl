# Phase 229: ATT Deploy Path + Artifact Tests - Research

**Researched:** 2026-06-09
**Domain:** Bash deploy tooling + pytest artifact-contract testing + read-only remote drift verification (no external libraries)
**Confidence:** HIGH (entire surface is in-repo; verified by direct file reads, not training data)

## Summary

This phase is **repo-only, zero-production-risk plumbing**. Every artifact, test pattern, and tool precedent already exists in the repo — the work is *mechanical mirroring* of the proven Spectrum cake-autorate path onto ATT, plus two drift-proofing tests. There is no new technology, no external dependency, no library decision. The risk is not technical; it is **scope discipline** (SAFE-14 controller-path zero-diff, no `$wan` generic refactor) and **getting the ATT-specific asymmetries right** so the mirror is faithful rather than copy-paste-wrong.

The Spectrum path is fully built: `deploy_spectrum_cake_autorate()` in `scripts/deploy.sh` (lines 397-445), flag `--with-spectrum-cake-autorate` (parse at 627-630, gate at 694-697, dispatch at 741-743), and `tests/test_spectrum_cake_autorate_artifacts.py` (5 tests). The ATT artifacts are all in the repo already (hand-deployed 2026-06-08, committed `fc47a0c`). **The state-bridge script is byte-identical** between Spectrum and ATT (`deploy/scripts/cake-autorate-{spectrum,att}-state-bridge` are the same file, fully env-parameterized) — confirmed by `diff`. So the ATT deploy function and tests must mirror Spectrum while substituting the ATT-specific values and adding the **silicom watchdog unit**, which has *no Spectrum cake-autorate counterpart* and is currently deployed by nothing.

**Primary recommendation:** Add `deploy_att_cake_autorate()` as a near-exact mirror of `deploy_spectrum_cake_autorate()` (lines 397-445) plus the silicom watchdog unit; add `tests/test_att_cake_autorate_artifacts.py` mirroring the Spectrum test with ATT values; add a TEST-02 drift test that parses the `deploy.sh` ATT file list against `deploy/`+`configs/` on disk. Do DEPLOY-02 read-only via the `scripts/phase226-snapshot-a.sh` `ssh -o BatchMode=yes <host> "sudo -n cat ..." | sha256sum` precedent — never mutate cake-shaper. Keep `wanctl@att.service` Conflicts wiring intact.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| ATT artifact deploy (`--with-att-cake-autorate`) | Deploy tooling (`scripts/deploy.sh`) | Target host (cake-shaper, via scp+ssh) | Mirror of the Spectrum deploy function; owns scp+chown+chmod+daemon-reload |
| ATT artifact contract enforcement | Repo tests (`tests/`) | — | Pure on-disk reads + `deploy.sh` text parsing; no host contact |
| Deploy-list ↔ repo-artifact drift gate (TEST-02) | Repo tests | — | Parse `deploy.sh` file-list arrays, assert each referenced path exists |
| DEPLOY-02 live-vs-repo verification | Read-only remote audit script/proc | Target host (read-only) | `ssh ... sudo -n cat` + `sha256sum`; zero mutation, repo is source of truth |
| SAFE-14 controller-path zero-diff | Boundary verification (git diff) | — | `check-safe07-source-diff.sh`-style protected-path check vs prior boundary |

**Key insight:** Nothing here touches the running controller or production rates. The only production interaction permitted is *read-only* diffing for DEPLOY-02. ATT is already live under the hand-deployed artifacts; this phase makes the repo authoritative over what is already running — it does not redeploy or change ATT behavior.

## Standard Stack

No external libraries. Stack is the existing repo toolchain.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| bash | system | `deploy.sh` deploy functions | Existing deploy mechanism; mirror, don't replace [VERIFIED: scripts/deploy.sh] |
| pytest | repo-pinned | artifact-contract + drift tests | Existing test framework; `tests/test_spectrum_cake_autorate_artifacts.py` is the parity template [VERIFIED: pyproject.toml L163-165] |
| ssh / scp / sha256sum / sudo -n | system | read-only remote diff for DEPLOY-02 | Precedent in `scripts/phase226-snapshot-a.sh` (read-only target reads) [VERIFIED: scripts/phase226-snapshot-a.sh L188-200] |
| git diff | system | SAFE-14 boundary proof | Precedent `scripts/check-safe07-source-diff.sh` [VERIFIED: scripts/check-safe07-source-diff.sh] |

**Installation:** None. No package installs. **Package Legitimacy Audit is N/A** — this phase installs zero external packages.

### Pytest config note
`addopts = "--cov-config=pyproject.toml --timeout=30 -m 'not integration'"` [VERIFIED: pyproject.toml L164]. New ATT tests should run under the default (non-integration) selection like the Spectrum test does — they are pure on-disk/subprocess tests with no host contact, so they stay in the default suite. The `--timeout=30` ceiling matters: the bridge health-endpoint test uses a 5s poll deadline (well under budget).

## Package Legitimacy Audit

**N/A — this phase installs no external packages.** All work uses the existing repo toolchain (bash, pytest, ssh/scp/sha256sum, git). No npm/PyPI/crates installs occur. slopcheck gate not applicable.

## Architecture Patterns

### System Architecture Diagram

```
                         REPO (source of truth)
  configs/cake-autorate/config.att.sh ─┐
  deploy/scripts/cake-autorate-att-qdisc-init ─┤
  deploy/scripts/cake-autorate-att-state-bridge ─┤ (byte-identical to spectrum)
  deploy/systemd/cake-autorate-att.service ─┤
  deploy/systemd/cake-autorate-att-state-bridge.service ─┤
  deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service ─┘
                    │
   ┌────────────────┼─────────────────────────────────┐
   │ DEPLOY-01      │ TEST-01 / TEST-02                │ DEPLOY-02
   ▼                ▼                                   ▼
 deploy.sh        pytest (on-disk reads,            read-only audit
 deploy_att_      deploy.sh text parse,             ssh sudo -n cat + sha256sum
 cake_autorate()  subprocess bridge run)            vs live cake-shaper
   │                │                                   │
   │ scp+sudo mv    │ assert artifact contents          │ compare hashes,
   │ +chown+chmod   │ + deploy.sh file-list ↔ disk      │ repo==live ? no-drift
   ▼                ▼                                   ▼
 TARGET: cake-shaper          PASS/FAIL (repo CI)       VERDICT: held / drift
 /etc/cake-autorate/config.att.sh
 /usr/local/sbin/cake-autorate-att-qdisc-init
 /usr/local/sbin/cake-autorate-att-state-bridge
 /etc/systemd/system/cake-autorate-att*.service
 /etc/systemd/system/silicom-bypass-watchdog-cake-autorate-att.service
 → systemctl daemon-reload
```

### Pattern 1: Mirror the Spectrum deploy function exactly
**What:** `deploy_att_cake_autorate()` is a structural copy of `deploy_spectrum_cake_autorate()` (deploy.sh L397-445).
**When to use:** Always — this is the binding parity requirement (DEPLOY-01).
**The Spectrum function's exact steps (mirror each):**
```bash
# Source: scripts/deploy.sh L397-445 [VERIFIED]
# 1. Guard: WAN_NAME must be "spectrum" (L400-403)   → ATT: must be "att"
# 2. Preflight: ssh test -x /opt/cake-autorate/cake-autorate.sh (L405-409)  → identical
# 3. ssh sudo mkdir -p /etc/cake-autorate /var/log/cake-autorate (L411)     → identical
# 4. scp config.spectrum.sh → /tmp → sudo mv /etc/cake-autorate/ chown root:root chmod 644 (L413-415)
#                                                          → ATT: config.att.sh
# 5. scp qdisc-init → /usr/local/sbin/ chown root:root chmod 755 (L417-419) → ATT: -att- variant
# 6. scp state-bridge → /usr/local/sbin/ chmod 755 (L421-423)               → ATT: -att- variant
# 7. loop SPECTRUM_CAKE_AUTORATE_SYSTEMD[] → /etc/systemd/system/ (L425-435), exit 1 if missing
#                                                          → ATT: ATT_CAKE_AUTORATE_SYSTEMD[]
# 8. rm trial drop-in cake-autorate-spectrum.service.d/qdisc-init.conf (L437-440)  → see Pitfall 3
# 9. ssh sudo systemctl daemon-reload (L442)                               → identical
```
**Flag wiring to mirror (3 sites):**
- Parse: L627-630 add `--with-att-cake-autorate) WITH_ATT_CAKE_AUTORATE=true; shift ;;`
- Var init: L617 add `WITH_ATT_CAKE_AUTORATE=false`
- WAN-name gate: L694-697 mirror — `--with-att-cake-autorate` valid only with `WAN_NAME=att`
- Dispatch: L741-743 add `if [[ "$WITH_ATT_CAKE_AUTORATE" == "true" ]]; then deploy_att_cake_autorate; fi`
- usage(): L99-101 add a `--with-att-cake-autorate` help block
- `print_next_steps()` L553-582: the Spectrum branch keys off `WITH_SPECTRUM_CAKE_AUTORATE` to print enable/rollback/monitor commands. Mirror an ATT branch (enable `cake-autorate-att.service cake-autorate-att-state-bridge.service`, log path `/var/log/cake-autorate/cake-autorate.att.log`, state `/var/lib/wanctl/att_state.json`).

### Pattern 2: Artifact-contract test mirrors `test_spectrum_cake_autorate_artifacts.py`
**What:** `tests/test_att_cake_autorate_artifacts.py` with the same 5 test shapes, ATT values substituted.
**Source template:** `tests/test_spectrum_cake_autorate_artifacts.py` (5 tests) [VERIFIED]:
1. `test_deploy_script_has_external_*_mode` — assert deploy.sh contains `--with-att-cake-autorate`, `deploy_att_cake_autorate`, `cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`.
2. `test_*_artifacts_are_repo_owned` — assert all 6 ATT files exist + content assertions (see ATT-specific values below).
3. `test_state_bridge_parses_*_writes_wanctl_state` — subprocess-run the bridge oneshot; since the script is shared, this can pass `WANCTL_EXTERNAL_WAN_NAME=att` + ATT ifaces and assert `att` state. **Note:** the shared bridge script defaults `STATE` tmpfile prefix to `spectrum_state.` (L109) regardless of WAN_NAME — the test writes to an explicit `WANCTL_EXTERNAL_STATE_PATH` so this does not matter, but flag it (see Pitfall 4).
4. `test_state_bridge_writes_metrics_database_when_configured` — assert `wan_name == "att"` in the metrics rows.
5. `test_state_bridge_serves_*_health_endpoint` — assert `wan["name"] == "att"`, `qdisc_bandwidth` values for ATT.

### Pattern 3: TEST-02 deploy-list drift gate
**What:** A test that the artifacts referenced by the `deploy.sh` ATT path all exist on disk, so the list and the repo cannot silently diverge.
**Why no manifest exists:** `deploy.sh` has **no central file-list manifest**. The Spectrum path uses one bash array (`SPECTRUM_CAKE_AUTORATE_SYSTEMD`, L62-65) for the *systemd units only*; the config/qdisc-init/state-bridge are scp'd by **hardcoded inline paths** inside the function (L413/417/421), not via an array. So TEST-02 must **parse `deploy.sh` text** for the artifact path strings (the systemd array entries + the inline `scp "$PROJECT_ROOT/..."` source paths in `deploy_att_cake_autorate`) and assert each resolves to an existing repo file. This is the only robust drift gate given the current structure.
**Recommended approach:** read `deploy.sh`, regex/extract `$PROJECT_ROOT/...` source paths and `ATT_CAKE_AUTORATE_SYSTEMD[]`/`deploy/systemd/...` entries that appear within the ATT function, build the expected ATT artifact set, assert set equality (or subset+nonempty) against the known 6 repo artifacts. Failing in *either* direction (deploy references a missing file / a repo ATT artifact is unreferenced by deploy) is the drift signal.

### Pattern 4: DEPLOY-02 read-only live diff
**What:** Compare repo ATT artifacts against the live hand-deployed copies on cake-shaper, read-only.
**Source precedent:** `scripts/phase226-snapshot-a.sh` L188-200 [VERIFIED]:
```bash
# read-only target read, no mutation:
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat /etc/wanctl/spectrum.yaml" > "$raw_config"
# sha256sum compare (L119, L251-262): sha256sum "$f" | cut -d' ' -f1
```
**Apply to ATT (6 live paths, all read-only):**
| Repo file | Live path on cake-shaper |
|-----------|--------------------------|
| `configs/cake-autorate/config.att.sh` | `/etc/cake-autorate/config.att.sh` |
| `deploy/scripts/cake-autorate-att-qdisc-init` | `/usr/local/sbin/cake-autorate-att-qdisc-init` |
| `deploy/scripts/cake-autorate-att-state-bridge` | `/usr/local/sbin/cake-autorate-att-state-bridge` |
| `deploy/systemd/cake-autorate-att.service` | `/etc/systemd/system/cake-autorate-att.service` |
| `deploy/systemd/cake-autorate-att-state-bridge.service` | `/etc/systemd/system/cake-autorate-att-state-bridge.service` |
| `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` | `/etc/systemd/system/silicom-bypass-watchdog-cake-autorate-att.service` |

Compare `ssh sudo -n cat <live>` ⇒ `sha256sum` vs local `sha256sum <repo>`. **SSH host is `cake-shaper`** [VERIFIED: phase226 default `SSH_HOST="cake-shaper"`]. Per CLAUDE.md/USER.md: read-only is safe to run directly; any non-`cat`/`sha256sum` (i.e., any write) is out of scope and requires operator approval. If hashes differ, the verdict is "drift found — reconcile repo to live OR document intentional divergence," with the **repo as the declared source of truth** (DEPLOY-02 wording). Expect a possible mismatch on the state-bridge: the live copy was hand-deployed 2026-06-08; the repo copy may carry later edits — surface honestly rather than assume zero-diff.

### Anti-Patterns to Avoid
- **Generic `$wan` symmetry refactor:** OUT OF SCOPE (REQUIREMENTS.md Out-of-Scope table). Do NOT collapse Spectrum+ATT into one parameterized function. Mirror as a sibling function. Premature abstraction explicitly excluded.
- **Touching the controller path:** SAFE-14. No edits to `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `backends/`, `alert_engine.py`, `fusion_healer.py`.
- **Redeploying/restarting ATT in production:** This phase makes the repo authoritative; it does not re-push to the live host. DEPLOY-02 is read-only.
- **Assuming the silicom watchdog has a Spectrum sibling to copy:** it does not (see Pitfall 1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Remote read-only diff | New SSH/sudo framework | `phase226-snapshot-a.sh` `ssh -o BatchMode=yes ... sudo -n cat` + `sha256sum` pattern | Proven read-only contract, operator-safe, already used against cake-shaper |
| State-bridge logic for ATT | A second ATT-specific bridge script | The existing **byte-identical shared script** driven by `WANCTL_EXTERNAL_*` env in the unit | Confirmed identical via `diff`; the att unit already injects `WAN_NAME=att`, ifaces, baseline RTT |
| Deploy mechanics | New deploy path | Mirror `deploy_spectrum_cake_autorate()` step-for-step | Battle-tested scp+chown+chmod+daemon-reload sequence |
| Controller-path boundary proof | New invariant checker | `check-safe07-source-diff.sh`-style git protected-path diff vs prior boundary | Established SAFE-07..13 precedent; SAFE-14 is its successor |

**Key insight:** Almost nothing should be *built*. The phase is mirror + two new tests + one read-only audit. The shared state-bridge means the bridge already supports ATT today; the gap is purely deploy-path + test coverage.

## Runtime State Inventory

> This is a deploy/test surface phase, not a rename/migration. ATT is already live. Inventory covers what already exists on the host that the repo must become authoritative over.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None renamed/migrated. ATT metrics DB `/var/lib/wanctl/metrics-att.db` + state `/var/lib/wanctl/att_state.json` already written by the live bridge. | None — repo does not alter them; bridge env already points at them. |
| Live service config | 6 ATT artifacts hand-deployed to cake-shaper 2026-06-08 (`/etc/cake-autorate/config.att.sh`, `/usr/local/sbin/cake-autorate-att-{qdisc-init,state-bridge}`, 3 systemd units). NOT guaranteed byte-equal to repo. | DEPLOY-02 read-only diff to confirm/surface drift; repo declared source of truth. |
| OS-registered state | systemd units enabled on cake-shaper (`cake-autorate-att.service`, `-state-bridge.service`, silicom watchdog). | None this phase — no enable/disable; deploy function only `daemon-reload`s (matches Spectrum). |
| Secrets/env vars | Bridge env vars are inline in the unit file (`WANCTL_EXTERNAL_*`, `CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227`). Watchdog uses inline `IFACE=att-modem`, `WANCTL_UNIT=cake-autorate-att.service` (NOT an EnvironmentFile — differs from the `@`-template). | None — all in repo artifacts already; tests assert them. |
| Build artifacts | None. No compiled/installed package carries an ATT name. | None. |

**The canonical question — what runtime state still has old/divergent values after the repo is updated?** Only the live hand-deployed artifact *bytes* on cake-shaper. DEPLOY-02 measures exactly that, read-only. No data migration, no re-registration.

## Common Pitfalls

### Pitfall 1: The silicom watchdog ATT unit is an orphan with no Spectrum sibling and references repo scripts
**What goes wrong:** Copy-pasting the Spectrum cake-autorate deploy function leaves the silicom watchdog out entirely — there is **no `silicom-bypass-watchdog-cake-autorate-spectrum.service`** to mirror; the att variant is unique. Worse, it `ExecStart`s `/usr/local/sbin/wanctl-bpctl-watchdog-petter` and `ExecStop`s `...-bypass`, which live in the repo as `scripts/wanctl-bpctl-watchdog-petter` and `scripts/wanctl-bpctl-watchdog-bypass` [VERIFIED] but **are not deployed by any current deploy path** (no `silicom`/`bpctl` refs in `deploy.sh` — verified by grep). It also `Requires=bpctl-silicom.service` (which ExecStarts `/usr/local/sbin/wanctl-bpctl-init`).
**Why it happens:** The Spectrum cake-autorate path never needed the watchdog; ATT did (Silicom bypass NIC). The unit was hand-deployed without a deploy-script home.
**How to avoid:** DEPLOY-01 success criterion explicitly lists "silicom watchdog variant" — the ATT deploy function MUST scp the `silicom-bypass-watchdog-cake-autorate-att.service` unit. **Open decision (planner/operator):** does DEPLOY-01 scope also include deploying the watchdog's exec scripts (`wanctl-bpctl-watchdog-petter`, `-bypass`, `wanctl-bpctl-init`) and `bpctl-silicom.service`, or only the cake-autorate-att watchdog *unit file* (parity with how the Spectrum function only ships cake-autorate units, not their `cake-autorate.sh` runtime which it preflight-checks)? The conservative reading matching the Spectrum precedent: ship the unit, preflight-check the bpctl runtime exists, do not own the bpctl tooling install. Confirm with operator. `[ASSUMED]`
**Warning sign:** Deploying the watchdog unit to a host without `/usr/local/sbin/wanctl-bpctl-watchdog-petter` ⇒ unit fails on enable. TEST-01 should assert the unit's `ExecStart`/`Requires`/`IFACE=att-modem`/`WANCTL_UNIT=cake-autorate-att.service` content, not deploy-time enablement.

### Pitfall 2: ATT-specific artifact values differ from Spectrum — a mechanical copy with wrong values is silent drift
**What goes wrong:** Test assertions copy Spectrum constants. The ATT contract differs materially:
| Assertion | Spectrum (template) | ATT (correct) | Source |
|-----------|--------------------|----------------|--------|
| Conflicts | `wanctl@spectrum.service` | `wanctl@att.service` | [VERIFIED: cake-autorate-att.service L6] |
| ExecStart config | `config.spectrum.sh` | `config.att.sh` | [VERIFIED: L11] |
| ExecStartPre | `cake-autorate-spectrum-qdisc-init` | `cake-autorate-att-qdisc-init` | [VERIFIED: L10] |
| qdisc DL dev/bw | `spec-router 550000Kbit ... egress wash rtt 25ms noatm overhead 18 memlimit 64Mb` | `att-router 95000Kbit ... **ingress** nowash rtt 35ms **ptm** overhead 22 memlimit 32Mb` | [VERIFIED: qdisc-init files] |
| qdisc UL dev/bw | `spec-modem 18000Kbit egress wash` | `att-modem 19000Kbit egress nowash ack-filter` | [VERIFIED] |
| config dl_if/ul_if | `spec-router`/`spec-modem` | `att-router`/`att-modem` | [VERIFIED: config.att.sh L5-6] |
| config rates | dl base implicit | `base_dl_shaper_rate_kbps=95000`, `max=100000`, `base_ul=19000` | [VERIFIED: config.att.sh L20-26] |
| ping bind | `-S 10.10.110.223` | `-S 10.10.110.227` | [VERIFIED: config.att.sh L9] |
| bridge health host | `10.10.110.223` | `10.10.110.227` | [VERIFIED: att bridge unit L15] |
**ATT qdisc invariants worth asserting (DOCSIS→VDSL2/PTM shift):** `ptm` (vs Spectrum `noatm`), `overhead 22 mpu 64` (vs `18`), `rtt 35ms` (vs `25ms`), `nowash` (vs `wash`), and crucially **DL uses `ingress` on att-router** while Spectrum DL uses `egress` on spec-router — this is an ATT-topology-specific keyword, not a typo. Assert it explicitly so a future careless edit can't silently flip it.
**How to avoid:** Build the ATT assertion table from the *actual repo files* (done above), not from the Spectrum test.

### Pitfall 3: The Spectrum-only trial drop-in cleanup line must NOT be blindly copied
**What goes wrong:** deploy.sh L437-440 removes `cake-autorate-spectrum.service.d/qdisc-init.conf` (a Spectrum-specific trial drop-in). Copying it verbatim into the ATT function would target the wrong path.
**How to avoid:** Either drop the line for ATT (the ATT unit already carries `ExecStartPre` inline, L10, so no drop-in cleanup is needed) or retarget to `cake-autorate-att.service.d/` only if a known ATT trial drop-in exists. Conservative: omit it for ATT and note why. `[ASSUMED]` no ATT trial drop-in exists — verify against live host during DEPLOY-02 if cheap.

### Pitfall 4: Parity asymmetries in the bridge unit env block
**What goes wrong:** The ATT bridge unit (`cake-autorate-att-state-bridge.service`) sets a **full** env block — `WANCTL_EXTERNAL_WAN_NAME/DL_IF/UL_IF/STATE_PATH/METRICS_DB`, `CAKE_AUTORATE_BRIDGE_LOG`, and **`WANCTL_EXTERNAL_BASELINE_RTT=28.42043789020452`** [VERIFIED L8-16]. The **Spectrum bridge unit sets only the health host/port** [VERIFIED: spectrum bridge L8-9] and relies on the shared script's defaults (`spectrum`, `spec-router`, `spec-modem`, baseline `22.535...`, L16-23 of the script). So the two units are *not* structurally parallel — ATT is explicit, Spectrum is implicit. The Spectrum *test* (`test_*_artifacts_are_repo_owned`) asserts `Environment=CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.223` and `ExecStart=...state-bridge`; the ATT test should additionally assert the ATT-specific env wiring (`WANCTL_EXTERNAL_WAN_NAME=att`, `WANCTL_EXTERNAL_DL_IF=att-router`, `WANCTL_EXTERNAL_UL_IF=att-modem`, health host `10.10.110.227`, and the pinned baseline RTT) because TEST-01 explicitly calls out "bridge env wiring."
**Also:** the shared bridge script hardcodes the atomic-write tmpfile prefix `spectrum_state.` (script L109) regardless of WAN. Harmless (the final path is `WANCTL_EXTERNAL_STATE_PATH`), but a faithful reviewer may flag it. Note it; do not "fix" it (out of scope, and it's in the shared script which is effectively controller-adjacent deploy tooling — a change would create Spectrum/ATT diff risk).
**How to avoid:** Assert the ATT env block from the actual att bridge unit (table above), not by analogy to Spectrum.

### Pitfall 5: TEST-02 needs to parse, not array-read — no manifest exists
**What goes wrong:** Assuming a single canonical file-list array to validate. deploy.sh only arrays the **systemd units** (`SPECTRUM_CAKE_AUTORATE_SYSTEMD`); config/qdisc-init/state-bridge are inline `scp` paths. A test that only checks the array misses 3 of the 6 ATT artifacts.
**How to avoid:** TEST-02 parses the deploy.sh text for the ATT function's `$PROJECT_ROOT/...` source paths plus its systemd array, builds the full referenced set, and asserts each exists. See Pattern 3.

## Code Examples

### DEPLOY-02 read-only hash compare (adapt from phase226)
```bash
# Source: scripts/phase226-snapshot-a.sh L188, L119 [VERIFIED]
# read-only — sudo -n cat only, never write to the target
SSH_HOST="cake-shaper"
live_hash=$(ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat /etc/cake-autorate/config.att.sh" | sha256sum | cut -d' ' -f1)
repo_hash=$(sha256sum configs/cake-autorate/config.att.sh | cut -d' ' -f1)
[[ "$live_hash" == "$repo_hash" ]] && echo "match" || echo "DRIFT: config.att.sh"
```

### TEST-01 ATT contract assertions (mirror of Spectrum test)
```python
# Source: tests/test_spectrum_cake_autorate_artifacts.py L37-67 [VERIFIED], ATT values substituted
service = ATT_CAKE_SERVICE.read_text(encoding="utf-8")
assert "Conflicts=wanctl@att.service" in service
assert "ExecStart=/opt/cake-autorate/cake-autorate.sh /etc/cake-autorate/config.att.sh" in service
assert "ExecStartPre=/usr/local/sbin/cake-autorate-att-qdisc-init" in service

qdisc = ATT_QDISC_INIT.read_text(encoding="utf-8")
assert "dev att-router root cake bandwidth 95000Kbit" in qdisc
assert "dev att-modem root cake bandwidth 19000Kbit" in qdisc
assert "ptm" in qdisc and "overhead 22 mpu 64" in qdisc and "rtt 35ms" in qdisc
assert "ingress" in qdisc  # ATT DL uses ingress; Spectrum DL uses egress

bridge = ATT_BRIDGE_SERVICE.read_text(encoding="utf-8")
assert "Environment=WANCTL_EXTERNAL_WAN_NAME=att" in bridge
assert "Environment=WANCTL_EXTERNAL_DL_IF=att-router" in bridge
assert "Environment=WANCTL_EXTERNAL_UL_IF=att-modem" in bridge
assert "Environment=CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227" in bridge

watchdog = ATT_WATCHDOG_SERVICE.read_text(encoding="utf-8")
assert "WANCTL_UNIT=cake-autorate-att.service" in watchdog
assert "IFACE=att-modem" in watchdog
```

### SAFE-14 controller-path zero-diff boundary check
```bash
# Source pattern: scripts/check-safe07-source-diff.sh [VERIFIED]
# Boundary baseline candidate: prior phase boundary / milestone close.
# Current HEAD at research time: 58ef4ff8 (v1.49-3-g58ef4ff8).
# Protected set (SAFE-14): wan_controller.py queue_controller.py cake_signal.py
#   backends/ alert_engine.py fusion_healer.py  [VERIFIED files exist]
git diff --stat <baseline-ref> -- \
  src/wanctl/wan_controller.py src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py src/wanctl/backends/ \
  src/wanctl/alert_engine.py src/wanctl/fusion_healer.py
# MUST be empty at the phase boundary.
```
**Note:** Per Decision [227-04], `wan_controller_state.py` was explicitly added to the SAFE protected set because `wan_controller.py` imports it. The planner should include it in the SAFE-14 protected list for continuity. `[CITED: .planning/STATE.md Decisions(v1.49) 227-04]`

## State of the Art

Not applicable — no fast-moving external ecosystem. The "old vs new" here is project-internal:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `wanctl@att.service` native controller owns ATT rates | cake-autorate external-controller owns ATT DL rates; bridge feeds wanctl state | 2026-06-08 (`fc47a0c`) | ATT artifacts hand-deployed; this phase makes repo authoritative |
| Spectrum-only `--with-spectrum-cake-autorate` deploy path | + `--with-att-cake-autorate` parity path | This phase | Reproducible ATT deploy |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | DEPLOY-01 scope = ship the cake-autorate-att watchdog *unit file* + preflight bpctl runtime, NOT own the bpctl exec-script/`bpctl-silicom.service` install (mirrors Spectrum's "ship units, preflight cake-autorate.sh" boundary) | Pitfall 1 | If operator wants full watchdog tooling deploy, scope expands (petter/bypass/init scripts + bpctl-silicom unit) |
| A2 | No ATT trial systemd drop-in (`cake-autorate-att.service.d/`) exists on the live host needing cleanup | Pitfall 3 | A stale ATT drop-in could cause duplicate ExecStartPre after deploy; cheap to verify read-only in DEPLOY-02 |
| A3 | Live state-bridge bytes on cake-shaper may differ from repo (hand-deployed 2026-06-08, repo may have later edits) — DEPLOY-02 should expect and surface this, not assume zero-diff | Pattern 4 | If treated as must-be-equal, a legitimate repo-newer state would read as failure instead of "repo is source of truth, reconcile live" |
| A4 | SAFE-14 boundary baseline = prior phase/milestone boundary ref (operator/planner picks exact SHA); HEAD at research = `58ef4ff8` | Code Examples | Wrong baseline ref gives a misleading diff; planner must pin the ref explicitly per SAFE-07..13 precedent |

## Open Questions

1. **Watchdog deploy depth (A1).** Ship only the cake-autorate-att watchdog unit, or the full bpctl tooling chain (`wanctl-bpctl-watchdog-petter`, `-bypass`, `wanctl-bpctl-init`, `bpctl-silicom.service`)?
   - What we know: the unit references those execs; they exist in `scripts/` but no deploy path ships them; the Spectrum cake-autorate function only ships units and preflight-checks the runtime.
   - Recommendation: mirror Spectrum's boundary — ship the unit, preflight `bpctl` presence, defer tooling install. Confirm with operator at plan/discuss time.
2. **DEPLOY-02 expected verdict on state-bridge.** Is the live bridge byte-equal to repo, or repo-newer?
   - What we know: shared script, hand-deployed 2026-06-08; repo file mtime is 2026-06-05.
   - Recommendation: run the read-only hash compare early; report honestly; "repo is source of truth" means reconcile *to* repo, documenting any intentional live-only divergence.
3. **TEST-02 strictness direction.** Should an *unreferenced* repo ATT artifact (exists in repo but not scp'd by deploy.sh) also fail the drift test, or only *missing* referenced files?
   - Recommendation: bidirectional set-equality against the known 6-artifact ATT set is the strongest anti-drift gate; weaker subset check is acceptable if set-equality proves brittle.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| ssh / scp | deploy + DEPLOY-02 | ✓ (assumed in dev env) | — | — |
| sha256sum | DEPLOY-02 | ✓ | — | — |
| cake-shaper SSH reachability + `sudo -n` read | DEPLOY-02 only | ✗ verify at runtime | — | If unreachable/unprivileged: capture as blocker, DEPLOY-02 deferred to a host-reachable session (read-only, operator-present per MEMORY credential-read rule) |
| pytest (repo venv) | TEST-01/02 | ✓ | repo-pinned | — |

**Missing dependencies with no fallback:** none for the repo-side work (DEPLOY-01/TEST-01/TEST-02 are fully offline).
**Runtime-gated:** DEPLOY-02 needs read-only access to cake-shaper; if `sudo -n cat` is denied, per MEMORY ("credential reads → operator at keyboard") hand Kevin a `! <command>` rather than escalating. Not a blocker for the other three requirements.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo-pinned) [VERIFIED: pyproject.toml L163] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (L163-165) |
| Quick run command | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | `deploy.sh --with-att-cake-autorate` deploys full ATT set with Spectrum-parity rigor | unit (deploy.sh text) + bash dry-run | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py::test_deploy_script_has_external_att_mode -x`; `bash scripts/deploy.sh att cake-shaper --with-att-cake-autorate --dry-run` | ❌ Wave 0 (new test + new deploy func) |
| DEPLOY-02 | live ATT bytes match repo (read-only) | read-only ssh+sha256 diff | new read-only audit script/step `ssh ... sudo -n cat | sha256sum` vs repo | ❌ Wave 0 (new audit step) |
| TEST-01 | ATT artifact contract at Spectrum parity (+watchdog, +ATT qdisc invariants, +bridge env) | unit + subprocess | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py -x` | ❌ Wave 0 (new test file) |
| TEST-02 | deploy.sh ATT file list ↔ repo artifacts cannot drift | unit (deploy.sh parse) | `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py::test_deploy_att_file_list_matches_repo -x` | ❌ Wave 0 (new test) |
| SAFE-14 | controller-path zero-diff at boundary | git diff gate | `git diff --stat <baseline> -- src/wanctl/{wan_controller,queue_controller,cake_signal,alert_engine,fusion_healer}.py src/wanctl/wan_controller_state.py src/wanctl/backends/` (must be empty) | ✓ pattern exists (`check-safe07-source-diff.sh`) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_att_cake_autorate_artifacts.py -q`
- **Per wave merge:** focused slice + `.venv/bin/ruff check` + `bash scripts/deploy.sh att cake-shaper --with-att-cake-autorate --dry-run`
- **Phase gate:** full `.venv/bin/pytest tests/` green + SAFE-14 git-diff empty + DEPLOY-02 verdict recorded before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_att_cake_autorate_artifacts.py` — covers TEST-01, TEST-02, DEPLOY-01 (deploy.sh text assertions). Mirror of `test_spectrum_cake_autorate_artifacts.py`.
- [ ] `deploy_att_cake_autorate()` + flag wiring in `scripts/deploy.sh` — implementation under DEPLOY-01 (not a test, but the on-disk thing TEST-01/02 assert against).
- [ ] DEPLOY-02 read-only audit step (script or documented `ssh sudo -n cat | sha256sum` procedure) — new, modeled on `phase226-snapshot-a.sh`.
- Framework install: none — pytest already present.

## Security Domain

> `security_enforcement` is not explicitly `false` in config.json, so included. This is a network production system; the relevant surface is deploy/host access, not app input validation.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (host access) | SSH key auth only (CLAUDE.md mandate); `ssh -o BatchMode=yes` (no password prompt) |
| V4 Access Control | yes | DEPLOY-02 strictly read-only (`sudo -n cat`, `tc/nft show`-class); any write requires operator approval (RouterOS/WAN mutation policy) |
| V5 Input Validation | low | deploy.sh args; mirror existing WAN-name gate. No new untrusted input surface. |
| V6 Cryptography | no | sha256sum used for integrity comparison only, not security crypto. Don't hand-roll — use `sha256sum`. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental production mutation via deploy/audit script | Tampering | DEPLOY-02 read-only contract; deploy path operator-gated; phase is repo-only |
| Secret/IP leak into public-safe docs | Information Disclosure | Per CLAUDE.md, project CLAUDE.md is public-safe; `.planning/` artifacts may carry the `10.10.110.x` shaper IPs (already present in committed unit files) — keep new docs consistent with what's already committed, don't expand exposure |
| Privileged read denial mid-audit | DoS (self) | Per MEMORY: hand operator a `! <command>` rather than escalating creds |

## Sources

### Primary (HIGH confidence — direct repo reads, 2026-06-09)
- `scripts/deploy.sh` — Spectrum deploy function (L397-445), flag parsing (L617/627-630/694-697/741-743), systemd array (L62-65), print_next_steps Spectrum branch (L553-582)
- `tests/test_spectrum_cake_autorate_artifacts.py` — 5-test parity template
- `deploy/systemd/cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, `silicom-bypass-watchdog-cake-autorate-att.service` — ATT unit contracts
- `deploy/scripts/cake-autorate-att-qdisc-init`, `configs/cake-autorate/config.att.sh` — ATT qdisc + config values
- `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge` — confirmed **byte-identical** via `diff`; env-parameterized (script L16-31)
- `scripts/phase226-snapshot-a.sh` — read-only remote diff precedent (L119, L188-200, L251-262)
- `scripts/check-safe07-source-diff.sh` — SAFE-N controller-path protected-diff precedent
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` (Decisions v1.49 227-04), `pyproject.toml` (pytest config)

### Secondary / Tertiary
- None — no external sources needed; entire surface is in-repo.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no external deps; all tooling verified present in repo.
- Architecture (mirror pattern, read-only diff, drift test): HIGH — every pattern has a verified in-repo precedent.
- Pitfalls: HIGH — derived from direct artifact comparison (silicom orphan, qdisc ingress/ptm asymmetry, bridge env asymmetry, no-manifest parsing) rather than inference.
- Open questions (watchdog deploy depth, DEPLOY-02 expected verdict, TEST-02 directionality): MEDIUM — scope/operator decisions, flagged in Assumptions Log.

**Research date:** 2026-06-09
**Valid until:** ~30 days (stable, in-repo; invalidated only if deploy.sh or the ATT artifacts change before planning)
