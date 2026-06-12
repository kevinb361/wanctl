# Phase 237: HIL Failure-Injection Harness + Closeout - Research

**Researched:** 2026-06-12
**Domain:** Bash orchestration / systemd-aware HIL test harness over an existing operator CLI; milestone closeout (DEPLOY-03 finalization, SAFE-16 zero-diff proof)
**Confidence:** HIGH (all findings verified against in-repo code, tests, prior summaries, and live-proven Phase 235/236 artifacts; no external library dependencies)

## Summary

Phase 237 is a **composition + closeout** phase, not a greenfield build. The hard parts (the `silicom-bypass` CLI verbs, the watchdog arm/disarm path, the W-INV sentinel discipline, the standalone deploy seam, and the SAFE-16 boundary-check tooling) all already exist and are live-proven from Phases 235/236. The work here is (1) a thin `silicom-test` orchestrator that composes those verbs into `failover`/`ab-cake`/`chaos` scenarios with a bulletproof always-on NIC-restore trap, (2) a structured result-capture convention writing to `tests/silicom/<timestamp>-<scenario>/`, (3) finalizing the single documented repo-owned deploy path (DEPLOY-03 — the `--silicom-bypass-only` standalone mode already exists and is the obvious extension point), and (4) the routine SAFE-16 zero-diff proof at phase boundary and milestone close.

The state-capture machinery already exists too: `scripts/phase213-steering-snapshot.sh` reads the steering `/health` endpoint plus persisted state and writes redacted artifacts under an EXIT-trap-guarded `mktemp`; `scripts/phase213-health-poller.sh` polls a `/health` endpoint at 1Hz into NDJSON. The bridges expose `/health` on `127.0.0.1:9101`; the steering daemon's own health check is `9102`. Persisted state lives at `/var/lib/wanctl/<wan>_state.json`. The harness should **reuse these capture scripts**, not reinvent them.

**Primary recommendation:** Build `scripts/silicom-test` as a bash orchestrator that (a) registers an always-on `trap restore_all_touched EXIT` **before any mutation**, tracking every touched pair in an array; (b) composes existing `silicom-bypass` verbs (`disc`/`conn`/`on`/`off`/`status`/`mark`) rather than calling `bpctl_util` directly; (c) reuses `phase213-steering-snapshot.sh`/`phase213-health-poller.sh` for state capture; (d) extends the existing `deploy.sh --silicom-bypass-only` standalone path for DEPLOY-03; and (e) re-runs the established SAFE-16 boundary-check tool (`scripts/phase225-safe13-boundary-check.sh` pattern) with `--anchor v1.51`. Test the harness offline with the same pytest fake-`bpctl_util`/fake-`silicom-bypass` seam pattern already in `tests/test_silicom_bypass_cli.py`. Live runs are gated by explicit operator confirmation; the default-safe pair to exercise is **Spectrum (spec-modem)**, not ATT (ATT is the canary in other workstreams).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Failure injection (cable pull / raw-ISP bypass) | Silicom NIC hardware (via `silicom-bypass` CLI) | — | The card does the path switch in hardware; harness only invokes the proven CLI verb |
| Scenario orchestration / sequencing | `silicom-test` bash orchestrator (new) | — | Composition layer; owns trap, ordering, capture timing |
| NIC-mode restoration guarantee | `silicom-test` EXIT trap → `silicom-bypass off`/`conn` | — | Safety-critical; trap is the keeper mechanism, restore goes through the guarded CLI |
| Steering/health/bridge state capture | Reuse `phase213-steering-snapshot.sh` + `phase213-health-poller.sh` | steering daemon `/health` (9102), bridge `/health` (9101), `/var/lib/wanctl/<wan>_state.json` | Capture tooling already exists, EXIT-trap-clean, redaction-aware |
| Result persistence | `tests/silicom/<ts>-<scenario>/` (filesystem, repo-relative) | — | Per HARN-05; offline artifact, not a service |
| Deploy/install of all bypass tooling | `deploy.sh --silicom-bypass-only` standalone mode (extend) | — | DEPLOY-03; standalone seam already exists and is the documented path |
| SAFE-16 zero-diff verification | `phase225-safe13-boundary-check.sh` pattern (read-only git) | — | Established tool; per-phase copy with `--anchor`/`--out` |
| Controller data path during bypass | **None — Linux is out of path** | — | Bypass = traffic skips the host entirely; wanctl has zero role (SEED-006 Out of Scope) |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HARN-01 | `failover <pair>` scenario (simulated cable pull via `set_disc`) capturing steering/health/bridge state through failure and recovery | `silicom-bypass disc <pair> --yes` injects the pull; `phase213-steering-snapshot.sh` + `/health` capture before/during/after; `conn` restores. Both-WAN gate already prevents dual loss. |
| HARN-02 | `ab-cake <pair>` scenario (CAKE-shaped vs raw-ISP bypass, same hardware/minute/client) | `silicom-bypass off <pair>` = CAKE-shaped (NIC, host in path); `silicom-bypass on <pair> --yes` = raw-ISP bypass (host out of path). A/B = run a throughput/latency probe in each mode back-to-back, capture both. |
| HARN-03 | Named scenario files via `silicom-test chaos <name>`; operator-invoked only, no scheduling | Scenario file dispatch (`scripts/silicom-test-scenarios/<name>.sh`); NO systemd timer/cron — operator-invoked only (SEED-006 Out of Scope: continuous/scheduled runs) |
| HARN-04 | Always-on exit trap restoring all touched pairs to NIC mode regardless of success/failure | `trap restore_all_touched EXIT` registered before first mutation; touched-pair array; restore via `silicom-bypass off`/`conn`. Proven by inducing mid-run failure (the W-INV sentinel pattern from 236 is the precedent for "trap before mutation"). |
| HARN-05 | Structured results to `tests/silicom/<timestamp>-<scenario>/`: pre/post state, snapshots, tool output, journal extracts | Directory convention + capture helpers; `silicom-bypass mark` anchors journal; `journalctl --since` extracts at boundaries; redacted-state pattern from `phase213-steering-snapshot.sh` |
| DEPLOY-03 | All bypass tooling artifacts repo-owned, deployable via a documented path decided at plan time | Extend existing `deploy.sh --silicom-bypass-only <host>` standalone mode to also install `silicom-test` + scenarios. Recommendation: **reuse `deploy.sh` standalone mode** (not a separate installer) — see DEPLOY-03 decision below. |
| SAFE-16 | Zero controller-path source diff at phase boundary AND milestone close (10th consecutive milestone) | `phase225-safe13-boundary-check.sh` pattern, `--anchor v1.51`, emit `evidence/safe16-boundary-237.json` with `controller_path_diff_count: 0`. Harness is bash + tests only; trivially holds. |
</phase_requirements>

## Standard Stack

This phase adds **no external packages**. Everything is bash, systemd, the existing `bpctl_util`, and pytest (already present). The "stack" is the in-repo tooling the harness composes.

### Core (existing, reused)
| Component | Location | Purpose | Why Standard |
|-----------|----------|---------|--------------|
| `silicom-bypass` CLI | `scripts/silicom-bypass` | Guarded per-pair state verbs (`status/on/off/disc/conn/mark/arm/disarm/baseline`) | Live-proven Phase 235/236; the harness MUST compose these, never call `bpctl_util` directly |
| `phase213-steering-snapshot.sh` | `scripts/phase213-steering-snapshot.sh` | Reads steering `/health` + persisted state, writes `-health.json` + `-state.redacted.json`, EXIT-trap-clean raw `mktemp` | Already redaction-aware and trap-clean; exactly the capture HARN-01/05 need |
| `phase213-health-poller.sh` | `scripts/phase213-health-poller.sh` | Polls a `/health` endpoint at 1Hz → NDJSON, bounded-failure TSV sidecar, runs until SIGTERM | Continuous capture through a failure/recovery window |
| `phase225-safe13-boundary-check.sh` | `scripts/phase225-safe13-boundary-check.sh` | Read-only git evidence: per-file hash diff of controller path vs anchor | The SAFE-16 proof tool; copy per-phase with `--anchor`/`--out` |
| `deploy.sh --silicom-bypass-only` | `scripts/deploy.sh` (`deploy_silicom_bypass`, `deploy_watchdog_artifacts`) | Standalone repo-owned install of all bypass artifacts, exits before wanctl release path | The DEPLOY-03 extension point — already true-standalone, install-only, off-by-default |

### Supporting (existing observability surfaces)
| Surface | Address / Path | Purpose | When to Use |
|---------|----------------|---------|-------------|
| Bridge `/health` | `http://127.0.0.1:9101/health` | cake-autorate state-bridge health (`status: healthy/degraded`, RTT, age) | Capture bridge view of autorate state during a scenario |
| Steering daemon `/health` | `http://127.0.0.1:9102/health` (config `health_check_port`, default 9102) | Steering daemon's own health endpoint | Capture steering decision state |
| Persisted WAN state | `/var/lib/wanctl/<wan>_state.json` (e.g. `att_state.json`, `spectrum_state.json`) | Atomic-written autorate/steering state JSON | Pre/post snapshots (read via `sudo -n cat`, redact before storing — see `phase213-steering-snapshot.sh`) |
| journal | `journalctl -t silicom-bypass`, `journalctl -u steering.service`, `-u cake-autorate-<wan>.service`, `-u cake-autorate-<wan>-state-bridge.service` | Narrative of card changes + service behavior | `mark`-anchored journal extracts per HARN-05 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bash orchestrator | Python orchestrator | SEED-006 allows either. Bash is lower-ceremony, matches every existing bypass artifact (`silicom-bypass`, watchdog scripts, deploy.sh), and keeps the SAFE-16 surface obviously off `src/wanctl`. **Recommend bash.** Python would tempt importing `wanctl.*` and muddy the zero-diff boundary. |
| Bash scenario files (`.sh`) | YAML + interpreter | SEED-006 open question. Bash = max flexibility, low ceremony, no new parser code. YAML = declarative/uniform but more code to write and test. **Recommend bash scenario files** for v1.52; revisit if a uniform schema is later needed. |
| Reuse `deploy.sh` standalone | Separate `install-silicom.sh` | See DEPLOY-03 decision. **Recommend reuse** — the standalone mode already exists, is true-standalone (exits before wanctl release), and decoupling further would duplicate the mktemp/atomic-install/daemon-reload logic. |

**Installation:** No package install. The harness ships as `scripts/silicom-test` + `scripts/silicom-test-scenarios/*.sh`, deployed via the existing `deploy.sh --silicom-bypass-only` path (extended).

## Package Legitimacy Audit

**Not applicable.** This phase installs zero external packages. All tooling is in-repo bash/systemd plus the already-present pytest/ruff/mypy toolchain. No npm/PyPI/crates dependency is added, so there is nothing for slopcheck or registry verification to evaluate.

## Architecture Patterns

### System Architecture Diagram

```
                          operator (explicit gate for live WAN)
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │   scripts/silicom-test  │  (new bash orchestrator)
                        │  failover | ab-cake |   │
                        │         chaos           │
                        └───────────┬─────────────┘
            register EXIT trap ─────┤  (BEFORE any mutation)
            track touched pairs ────┤
                                     ▼
              ┌──────────────────────┴───────────────────────┐
              │ compose proven verbs (never raw bpctl_util)   │
              ▼                      ▼                         ▼
   ┌──────────────────┐  ┌────────────────────┐   ┌────────────────────────┐
   │ silicom-bypass   │  │ phase213-steering- │   │ silicom-bypass mark    │
   │ disc/conn/on/off │  │ snapshot.sh +      │   │ journalctl --since     │
   │ status           │  │ health-poller.sh   │   │ (boundary anchors)     │
   └────────┬─────────┘  └─────────┬──────────┘   └───────────┬────────────┘
            │ bpctl_util             │ reads                    │
            ▼                        ▼                          ▼
   ┌──────────────────┐  ┌────────────────────────────────────────────────┐
   │ Silicom NIC      │  │ steering /health :9102 · bridge /health :9101  │
   │ (hardware path   │  │ /var/lib/wanctl/<wan>_state.json (redact)      │
   │  switch)         │  └────────────────────────────────────────────────┘
   └──────────────────┘
            │
            ▼  on EXIT (success | failure | signal)
   ┌─────────────────────────────────────────────────────────┐
   │ restore_all_touched: for each touched pair →            │
   │   silicom-bypass off <pair> ; silicom-bypass conn <pair>│
   │   → guaranteed NIC mode regardless of outcome (HARN-04)  │
   └─────────────────────────────────────────────────────────┘
            │
            ▼
   ┌─────────────────────────────────────────────────────────┐
   │ tests/silicom/<timestamp>-<scenario>/                   │
   │   pre-state.* · snapshots/* · raw-tool-output/* ·       │
   │   journal.txt · post-state.* · result.json (HARN-05)    │
   └─────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
scripts/
├── silicom-test                    # new: orchestrator (failover/ab-cake/chaos/status)
└── silicom-test-scenarios/         # new: named chaos scenario files
    ├── cake-ab-spectrum.sh
    ├── failover-spectrum-to-att.sh
    └── ...                          # operator-invoked only, no timer

tests/
├── test_silicom_test_harness.py    # new: offline pytest, fake silicom-bypass seam
└── silicom/                        # HARN-05 result store (runtime-written)
    └── <timestamp>-<scenario>/     # per-run; consider .gitignore (see Open Questions)

.planning/phases/237-.../evidence/
└── safe16-boundary-237.json        # SAFE-16 phase-boundary + milestone-close proof
```

### Pattern 1: Always-on restore trap registered before first mutation (HARN-04, SAFE-CRITICAL)
**What:** Register the EXIT trap and initialize the touched-pair tracker *before any state change*, so restoration runs on success, error (`set -e`), or signal (INT/TERM). This mirrors the W-INV `sentineled_stop` precedent from Phase 236, where the sentinel trap is set before the `systemctl` call.
**When to use:** Every harness command that touches card state.
**Example:**
```bash
# Source: pattern derived from scripts/silicom-bypass sentineled_stop() (236) + SEED-006 §Phase B
set -euo pipefail
SILICOM_BYPASS="${SILICOM_BYPASS:-/usr/local/sbin/silicom-bypass}"
declare -a TOUCHED_PAIRS=()

restore_all_touched() {
    local rc=$?              # preserve original exit status
    local pair
    for pair in "${TOUCHED_PAIRS[@]}"; do
        # best-effort: a restore failure must not mask the original failure,
        # but MUST be loud. off = leave bypass; conn = leave disconnect.
        "$SILICOM_BYPASS" off  "$pair" || journal_best_effort "restore off  $pair FAILED"
        "$SILICOM_BYPASS" conn "$pair" || journal_best_effort "restore conn $pair FAILED"
    done
    "$SILICOM_BYPASS" mark "silicom-test: EXIT restore complete (rc=$rc)" || true
    return "$rc"
}

trap restore_all_touched EXIT INT TERM   # set BEFORE any mutation

mark_touched() {                          # call right before mutating a pair
    local pair="$1" p
    for p in "${TOUCHED_PAIRS[@]}"; do [[ "$p" == "$pair" ]] && return 0; done
    TOUCHED_PAIRS+=("$pair")
}
```
**Key subtleties:**
- `off`/`conn` are the idempotent NIC-restoring verbs and are **no-ops if already NIC** (verified in `test_off_idempotent_noop`, `test_conn_idempotent_noop`) — so calling them unconditionally in restore is safe.
- `off`/`conn` do **not** require `--yes` (only `on`/`disc` do) — restore never blocks on a confirmation flag.
- Preserve `$?` at the top of the trap and return it, so the harness still exits non-zero on a real failure even after a clean restore.
- The both-WAN gate in `on`/`disc` means the harness physically cannot drive both pairs non-NIC without `--both-wan-confirm`; the harness should **never** pass that flag in a single-pair scenario, giving a second structural guarantee against dual-WAN loss.

### Pattern 2: Mid-run failure injection to prove HARN-04
**What:** The success criterion requires proving restoration *by inducing a mid-run failure*. The offline pytest harness should inject a failure after a pair is marked-touched and assert the fake `silicom-bypass` received the restoring `off`/`conn` calls.
**When to use:** The HARN-04 verification test.
**Example (pytest seam, mirrors `tests/test_silicom_bypass_cli.py`):**
```python
# Source: pattern from tests/test_silicom_bypass_cli.py (_fake_bpctl / _run / _calls_for)
# Inject failure via a fake silicom-bypass that exits non-zero on a chosen verb,
# OR run a scenario whose body calls `false` mid-way, then assert the calls log
# shows `off <pair>` and `conn <pair>` AFTER the injected failure point.
def test_failover_restores_on_midrun_failure(tmp_path):
    fake_cli, calls = _fake_silicom_bypass(tmp_path, fail_on="probe")
    result = _run_test(tmp_path, fake_cli, "failover", "spec-modem",
                       extra_env={"SILICOM_TEST_INJECT_FAIL": "probe"})
    assert result.returncode != 0                 # original failure preserved
    cli_calls = calls.read_text()
    assert "disc spec-modem" in cli_calls          # injection happened
    assert "off spec-modem" in cli_calls           # restore ran
    assert "conn spec-modem" in cli_calls
    assert cli_calls.index("off spec-modem") > cli_calls.index("disc spec-modem")
```
The same `BPCTL_UTIL`/`SILICOM_BYPASS`/`LOGGER`/`SYSTEMCTL` tool-path seams already used in 235/236 let this run with zero live hardware.

### Pattern 3: failover scenario (HARN-01)
**What:** Simulated cable pull = `disc` (disconnect, link down), captured through failure and recovery.
**Example flow:**
```bash
# failover <pair>  (default-safe pair = spec-modem; live gate required)
mark_touched "$pair"
"$SILICOM_BYPASS" mark "failover $pair: PRE"
capture_state "$RUNDIR/pre"                      # phase213-steering-snapshot.sh
start_health_poller "$RUNDIR/health.ndjson"      # phase213-health-poller.sh (bg)
"$SILICOM_BYPASS" disc "$pair" --yes             # simulated cable pull (link down)
"$SILICOM_BYPASS" mark "failover $pair: PULLED"
capture_state "$RUNDIR/during"
sleep "$RECOVERY_WINDOW"                          # observe steering reaction
"$SILICOM_BYPASS" conn "$pair"                    # restore link (also done by trap)
"$SILICOM_BYPASS" mark "failover $pair: RESTORED"
capture_state "$RUNDIR/post"
# trap restores to NIC on exit regardless
```

### Pattern 4: ab-cake scenario (HARN-02)
**What:** A/B between CAKE-shaped (host in path, NIC mode) and raw-ISP (host out of path, bypass mode) on the *same hardware/minute/client*.
**Example flow:**
```bash
# ab-cake <pair>
mark_touched "$pair"
"$SILICOM_BYPASS" off "$pair"                     # ensure NIC (CAKE-shaped) baseline
run_ab_probe "$RUNDIR/A-cake-shaped"              # iperf/netperf/flent — "A" arm
"$SILICOM_BYPASS" on "$pair" --yes                # raw-ISP bypass (host out of path)
run_ab_probe "$RUNDIR/B-raw-isp"                  # "B" arm, same client/minute
"$SILICOM_BYPASS" off "$pair"                     # back to CAKE (trap also restores)
```
*Note:* the A/B probe tool is the operator's existing latency/throughput rig (netperf to Dallas Linode per project memory, or flent/iperf). The harness orchestrates the card flip and capture; it does not need to ship a new probe.

### Anti-Patterns to Avoid
- **Calling `bpctl_util` directly from the harness.** Always go through `silicom-bypass` — that is where the idempotency, read-back assertion, both-WAN gate, and journaling live. Bypassing the CLI re-introduces every footgun 235 closed.
- **Registering the trap after the first mutation.** A failure between mutation and trap registration leaves a pair stuck non-NIC. Trap first, mutate second (the W-INV lesson from 236).
- **Importing `wanctl.*` Python into the harness.** Tempts a `src/wanctl` touch and blurs the SAFE-16 boundary. Capture state by reading the `/health` HTTP endpoints and the state JSON files, not by importing controller code.
- **Any systemd timer or cron for scenarios.** HARN-03 and SEED-006 Out of Scope both forbid scheduling. `chaos` is operator-invoked dispatch only.
- **Storing raw (unredacted) state JSON under the result dir.** `phase213-steering-snapshot.sh` deliberately keeps raw state in a process-lifetime `mktemp` and writes only a redacted artifact. Follow that — secrets/IPs must not land in `tests/silicom/`.
- **Passing `--both-wan-confirm` from a single-pair scenario.** Removes the structural dual-WAN-loss guard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-pair card state change + read-back + journaling | New bpctl wrapper logic | `silicom-bypass` verbs | Idempotency, read-back assertion, both-WAN gate, wording-variant matching all already solved and live-proven |
| Steering/health/state capture with redaction | New curl+jq+sudo cat capture | `phase213-steering-snapshot.sh` | Already EXIT-trap-clean, redaction-aware, raw-in-mktemp pattern |
| Continuous `/health` polling through a window | New polling loop | `phase213-health-poller.sh` | 1Hz NDJSON + bounded-failure TSV sidecar + signal-clean exit already built |
| SAFE-16 controller-path zero-diff evidence | New git-diff script | `phase225-safe13-boundary-check.sh` pattern | Per-file hash diff, fail-closed on add/delete, JSON schema the verifier already consumes |
| Repo-owned standalone deploy of bypass tooling | Separate installer | `deploy.sh --silicom-bypass-only` | True-standalone, mktemp+atomic-install, install-if-absent config, daemon-reload, off-by-default — all done |
| Watchdog stop discipline (if harness ever touches watchdog) | Raw `systemctl stop` | `silicom-bypass disarm` / `sentineled_stop` | W-INV invariant: no fail-open watchdog stop without a sentinel first; statically gated by `-k invariant` |

**Key insight:** Phase 237 is ~80% composition of solved problems. The only genuinely new code is the orchestrator's trap/tracking skeleton, the scenario dispatch, and the result-directory convention. If a task in the plan looks like it's reinventing card control, state capture, deploy, or SAFE-16 proof — it's wrong; redirect it to the existing artifact.

## Runtime State Inventory

Phase 237 is additive (new scripts/tests/docs) — it does **not** rename or migrate. There is no string-rename or datastore-key migration surface. Inventory for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — harness writes new `tests/silicom/<ts>-<scenario>/` artifacts; reads (not mutates) `/var/lib/wanctl/<wan>_state.json` | None |
| Live service config | None changed — harness reads bridge `/health` (9101) and steering `/health` (9102); does not reconfigure them | None |
| OS-registered state | None — HARN-03 explicitly forbids any timer/cron/systemd registration for scenarios | None (verified by HARN-03 + SEED-006 Out of Scope) |
| Secrets/env vars | Harness reads `/etc/silicom-bypass.conf` (`PAIRS`) and may read state JSON that contains sensitive fields → must redact before persisting (see `phase213-steering-snapshot.sh`) | Redact-on-capture only; no new secret keys |
| Build artifacts | None — bash scripts, no compiled/installed package | None |

**Nothing requires a data migration.** The one live-data interaction is *read-and-redact* of state JSON, already patterned.

## Common Pitfalls

### Pitfall 1: Trap doesn't fire on signal, leaving a pair stuck in bypass/disconnect
**What goes wrong:** `trap ... EXIT` alone does not always run on SIGINT/SIGTERM in every bash configuration; an operator Ctrl-C mid-scenario could skip restore.
**Why it happens:** EXIT trap semantics vs signal handling.
**How to avoid:** `trap restore_all_touched EXIT INT TERM` and preserve `$?`. Verify in the offline test by sending a signal to the harness subprocess and asserting `off`/`conn` calls landed.
**Warning signs:** A scenario aborted with Ctrl-C and `silicom-bypass status all` shows a pair still `bypass`/`disc`.

### Pitfall 2: Restore failure masks the original failure exit code
**What goes wrong:** A restore command that itself fails overwrites `$?`, so the harness exits 0 (or with the wrong code) after a real scenario failure.
**Why it happens:** Each command in the trap resets `$?`.
**How to avoid:** Capture `rc=$?` as the first line of the trap, make restore commands best-effort (`|| journal ...`), and `return "$rc"` at the end.
**Warning signs:** CI/operator sees green after a scenario that actually failed.

### Pitfall 3: Running a live scenario against ATT instead of Spectrum
**What goes wrong:** ATT is the canary WAN in multiple other workstreams (migration, watchdog RCA); chaos-testing it risks colliding with live operational state.
**Why it happens:** No default-pair guard.
**How to avoid:** Default the safe-to-exercise pair to **spec-modem (Spectrum)**; require the explicit live-WAN operator gate (and a louder confirmation for `att-modem`). SEED-006 §Phase A explicitly names Spectrum as the only safe pair to test against.
**Warning signs:** A live scenario invoked with `att-modem` and no extra confirmation.

### Pitfall 4: Capturing raw state JSON with secrets into the committed result dir
**What goes wrong:** `/var/lib/wanctl/<wan>_state.json` or `/health` payloads land verbatim under `tests/silicom/`, leaking IPs/auth/host detail into a repo-tracked path. Violates CLAUDE.md "public-safe, no IPs/hostnames."
**Why it happens:** Naive `cat state.json > result/pre-state.json`.
**How to avoid:** Reuse `phase213-steering-snapshot.sh`'s redacted-only output; keep raw in a process-lifetime `mktemp` cleaned by EXIT trap; decide `tests/silicom/` `.gitignore` policy at plan time (see Open Questions).
**Warning signs:** `git status` shows untracked files under `tests/silicom/` containing IPs.

### Pitfall 5: SAFE-16 anchor drift
**What goes wrong:** Using the wrong git anchor makes the zero-diff proof meaningless (false pass) or spuriously fails.
**Why it happens:** Anchor must be the milestone baseline. 235/236 evidence used `anchor: v1.51` (the prior shipped milestone tag).
**How to avoid:** Run `phase225-safe13-boundary-check.sh`-pattern tool with `--anchor v1.51` and confirm `controller_path_diff_count: 0` plus `per_file_sha256_equal` all true, at phase boundary AND milestone close.
**Warning signs:** `baseline_commit` in the JSON doesn't match `git rev-parse v1.51`.

## Code Examples

### SAFE-16 boundary proof (reuse established tool, new output)
```bash
# Source: scripts/phase225-safe13-boundary-check.sh (pattern), evidence/safe16-boundary-{235,236}.json
# Create scripts/phase237-safe16-boundary-check.sh (or parameterize the existing one) with:
#   ANCHOR="v1.51"
#   OUT=".planning/phases/237-hil-failure-injection-harness-closeout/evidence/safe16-boundary-237.json"
# controller_targets MUST be exactly:
#   src/wanctl/wan_controller.py, wan_controller_state.py, queue_controller.py,
#   cake_signal.py, alert_engine.py, fusion_healer.py, backends/  (+ configs/att.yaml witness)
# Assert in the result: controller_path_diff_count == 0, passed == true,
#   per_file_sha256_equal all true, dirty_tree_clean true.
```

### Result directory layout (HARN-05)
```
tests/silicom/20260613T101500Z-failover-spec-modem/
├── result.json              # scenario, pair, start/end ts, exit code, arms run
├── pre-state-health.json    # phase213-steering-snapshot.sh output (redacted)
├── pre-state-state.redacted.json
├── during/                  # intermediate snapshots at each `mark` boundary
│   ├── pulled-health.json
│   └── pulled-state.redacted.json
├── health.ndjson            # phase213-health-poller.sh continuous 1Hz capture
├── health.failures.tsv      # bounded-failure sidecar
├── journal.txt              # journalctl -t silicom-bypass + relevant units, --since run-start
├── raw-tool-output/         # iperf/netperf/flent stdout for ab-cake arms
└── post-state-health.json   # post-restore snapshot
```

### journal extract anchored by mark (HARN-05)
```bash
RUN_START="$(date -u -Iseconds)"
# ... scenario runs, calling `silicom-bypass mark "<scenario>: <boundary>"` at each step ...
journalctl --since "$RUN_START" \
    -t silicom-bypass \
    -u steering.service \
    -u "cake-autorate-${WAN}.service" \
    -u "cake-autorate-${WAN}-state-bridge.service" \
    --no-pager > "$RUNDIR/journal.txt"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw hand-typed `bpctl_util` with no status/guards | `silicom-bypass` guarded CLI | Phase 235 (2026-06-12) | Harness composes verbs; no raw card calls |
| `wanctl@`-coupled watchdog template | Two-mode cake-autorate reconciled template + `arm`/`disarm` + W-INV sentinel | Phase 236 (2026-06-12) | Harness never raw-stops a watchdog; uses `disarm` if needed |
| Per-phase bespoke deploy snippets | `deploy.sh --silicom-bypass-only` true-standalone mode | Phase 235 (2026-06-12) | DEPLOY-03 = extend this, not a new installer |
| Both WANs on `wanctl@` controllers | Both WANs on external cake-autorate; bridges feed steering/health since 2026-06-08 | v1.50/v1.51 migration | State capture targets the bridge `/health` (9101) + steering `/health` (9102), not `wanctl@` |

**Deprecated/outdated (do not reintroduce):**
- Timer-based deployment guidance (project is service-based).
- `sil-spare1`/`sil-spare2` pair names — the shipped config uses `att-modem spec-modem` (235-01 decision); the SEED-006 example `PAIRS="att-modem sil-spare1"` is stale.
- Native `wanctl@<wan>.service` ownership assumptions in any watchdog env.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Steering daemon `/health` is reachable on `127.0.0.1:9102` (config `health_check_port`, default 9102 in `daemon.py`); bridges on 9101 | Standard Stack / Supporting | LOW — capture script reads whatever endpoint it's pointed at; confirm live ports at plan/exec time via `curl -s 127.0.0.1:910x/health` |
| A2 | The A/B probe in `ab-cake` is the operator's existing rig (netperf/flent/iperf), not something the harness ships | Pattern 4 | LOW — if a probe must ship, it's a small additive bash wrapper, still SAFE-16-clean. Confirm operator's preferred probe at plan time. |
| A3 | `tests/silicom/` result artifacts are runtime-generated and likely should be `.gitignore`d (no current gitignore entry) | Open Questions | MEDIUM — if committed, redaction becomes mandatory and disk/retention policy matters; decide at plan time |
| A4 | SAFE-16 anchor for v1.52 is `v1.51` (matches 235/236 evidence `anchor: v1.51`) | Pitfall 5 / Code Examples | LOW — both prior phases used it and passed; confirm `git rev-parse v1.51` matches `baseline_commit` |
| A5 | DEPLOY-03 is satisfied by extending `deploy.sh --silicom-bypass-only` rather than a separate installer | DEPLOY-03 decision | LOW — recommended default; this is an explicit SEED-006 plan-time question, operator may prefer separate. Present as recommendation, not locked. |

## DEPLOY-03 Decision (recommended default, carried from SEED-006)

**Question (SEED-006 open):** Reuse `scripts/install.sh`/`deploy.sh` deployment flow, or keep a separate installer to avoid coupling bypass tooling to the wanctl release cadence?

**Finding:** `deploy.sh` already has a **true-standalone** `--silicom-bypass-only <host>` mode (added Phase 235-03, hardened 235-04) that:
- short-circuits **before** `deploy_code` (the wanctl release/restart path) — so it is already decoupled from wanctl release cadence (`test_silicom_standalone_short_circuits`);
- stages artifacts in a per-deploy private `mktemp -d` with `chmod 700` + atomic `sudo install -o root -g root` (`test_silicom_deploy_uses_private_atomic_staging`);
- installs config install-if-absent (won't clobber `/etc/silicom-bypass.conf`);
- installs all CLI + watchdog + init + bpctl artifacts off-by-default, no unit enabled (`test_deploy_watchdog_off_by_default`);
- fails closed on extra positionals / incompatible WAN flags (`test_silicom_standalone_rejects_*`).

**Recommendation: REUSE the `deploy.sh --silicom-bypass-only` standalone path.** Extend `deploy_silicom_bypass()` to also stage+install `scripts/silicom-test` and `scripts/silicom-test-scenarios/*` (and add them to the artifact arrays + the `test_artifacts_repo_owned` / `SILICOM_BYPASS_ARTIFACTS` set). Rationale: the standalone mode already provides the exact decoupling the SEED-006 concern wanted, *without* duplicating the mktemp/atomic-install/daemon-reload/fail-closed logic a separate installer would re-implement. A separate installer would be net-new untested surface for zero benefit. This is a recommended default, not a locked decision — flag for operator confirmation at discuss/plan time.

## Open Questions

1. **`tests/silicom/` git tracking + retention policy**
   - What we know: no `.gitignore` entry today; SEED-006 raised a 30-day rolling window idea and a "fill disk" concern; CLAUDE.md forbids committing IPs/hostnames.
   - What's unclear: commit redacted results as evidence, or `.gitignore` the whole tree and treat as ephemeral local artifacts?
   - Recommendation: `.gitignore tests/silicom/` by default (ephemeral HIL artifacts), allow opt-in committing of *redacted* result.json summaries under the phase evidence dir if a run is operator-significant. Decide at plan time.

2. **Scenario file format: bash vs YAML**
   - What we know: SEED-006 open question; every existing bypass artifact is bash.
   - Recommendation: bash scenario files for v1.52 (low ceremony, no new parser). Revisit only if a uniform output schema is later required.

3. **Pcap capture default**
   - What we know: SEED-006 flags full pcaps as useful-but-expensive.
   - Recommendation: off by default, explicit `--pcap` opt-in. Decide at plan time.

4. **Refuse-to-run-if-degraded vs allow-compounding-chaos**
   - What we know: SEED-006 asks whether the harness should refuse if `cake-autorate-<wan>` / steering is already failed.
   - Recommendation: capture current health into `result.json` and warn loudly; do NOT hard-refuse (chaos may want to compound), but require the live gate. Decide at plan time.

5. **A/B probe tool selection**
   - What we know: project memory notes Spectrum hourly uses Dallas Linode netperf (104.x); "don't swap default netperf to iperf without approval."
   - Recommendation: use the operator's existing netperf path for `ab-cake`; confirm exact probe command at plan time (A2).

## Environment Availability

> Harness runs on `cake-shaper` (the host with the Silicom card + bridges + steering). Offline pytest runs anywhere.

| Dependency | Required By | Available (offline/dev) | Notes / Fallback |
|------------|------------|--------------------------|------------------|
| `bpctl_util` (`/opt/bpctl-silicom/bpctl_util`) | live scenarios | ✗ on dev VM (card is on cake-shaper) | Offline tests use fake `bpctl_util` seam (`BPCTL_UTIL` env) — no live card needed |
| `silicom-bypass` CLI | all scenarios | ✓ (repo `scripts/silicom-bypass`) | Composed via `SILICOM_BYPASS` path seam |
| `phase213-steering-snapshot.sh` / `phase213-health-poller.sh` | HARN-01/05 capture | ✓ (repo `scripts/`) | Reused as-is |
| bridge `/health` 9101 / steering `/health` 9102 | state capture | ✗ on dev (live on cake-shaper) | Confirm live via `curl` at exec time (A1); offline tests stub |
| `journalctl` | HARN-05 journal extracts | ✓ (systemd host) | — |
| netperf/flent/iperf | `ab-cake` A/B arms | operator rig on cake-shaper | Confirm probe at plan time (A2) |
| pytest/ruff/mypy | offline harness tests | ✓ (`.venv`) | `pyproject.toml` addopts include `--timeout=30 -m 'not integration'` |
| `git`, `python3` | SAFE-16 boundary tool | ✓ | Read-only git inspection |

**Missing dependencies with no fallback:** none that block planning — all live-only deps (card, bridges) are exactly what the fake-seam pytest pattern was built to stub. Live execution requires cake-shaper + operator gate.

## Validation Architecture

> nyquist_validation is enabled (config `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (+ pytest-cov, pytest-timeout) — already configured |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_silicom_test_harness.py -x -q` (new file) |
| Full suite command | `.venv/bin/pytest tests/ -q` |
| Static gates | `.venv/bin/ruff check scripts/ tests/` ; `shellcheck scripts/silicom-test` ; existing `-k invariant` W-INV gate must stay green if harness touches any watchdog surface |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HARN-01 | failover injects `disc`, captures, recovers via `conn` | unit (fake seam) | `pytest tests/test_silicom_test_harness.py::test_failover_inject_and_recover -x` | ❌ Wave 0 |
| HARN-02 | ab-cake flips off→on→off, runs both arms | unit | `pytest ...::test_ab_cake_runs_both_arms -x` | ❌ Wave 0 |
| HARN-03 | chaos dispatches named scenario; no timer/cron registered | unit + static | `pytest ...::test_chaos_dispatch_no_scheduling -x` | ❌ Wave 0 |
| HARN-04 | trap restores ALL touched pairs on mid-run failure/signal | unit (failure injection) | `pytest ...::test_restore_on_midrun_failure -x` ; `...::test_restore_on_signal -x` | ❌ Wave 0 |
| HARN-05 | result dir has pre/post/snapshots/raw/journal | unit | `pytest ...::test_result_dir_layout -x` | ❌ Wave 0 |
| DEPLOY-03 | deploy.sh standalone installs silicom-test + scenarios; artifacts repo-owned | unit (source asserts, mirrors `test_artifacts_repo_owned`) | `pytest tests/test_silicom_bypass_cli.py -k deploy -q` (extend) | ⚠️ extend existing |
| SAFE-16 | controller-path zero-diff vs v1.51 at boundary + close | evidence (git read-only) | `bash scripts/phase237-safe16-boundary-check.sh --anchor v1.51` → assert JSON | ❌ Wave 0 (tool copy) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_silicom_test_harness.py -x -q` + `shellcheck scripts/silicom-test`
- **Per wave merge:** `.venv/bin/pytest tests/ -q` (full suite; includes W-INV `-k invariant` gate)
- **Phase gate:** full suite green + SAFE-16 JSON `controller_path_diff_count: 0` before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_silicom_test_harness.py` — covers HARN-01..05 with a fake `silicom-bypass` seam (mirror `_fake_bpctl`/`_run`/`_calls_for` from `tests/test_silicom_bypass_cli.py`)
- [ ] `scripts/phase237-safe16-boundary-check.sh` — copy/parameterize `phase225-safe13-boundary-check.sh` with `--anchor v1.51` and the 237 evidence out-path
- [ ] Extend `SILICOM_BYPASS_ARTIFACTS` / `test_artifacts_repo_owned` in `tests/test_silicom_bypass_cli.py` to include `scripts/silicom-test` + scenarios once DEPLOY-03 wiring lands
- [ ] (no framework install needed — pytest already present)

## Security Domain

> `security_enforcement` not set in config → treat as default. This phase is a local operator HIL harness, not a network-exposed service, so the ASVS surface is narrow but two items matter.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface; harness is local + operator-invoked |
| V3 Session Management | no | — |
| V4 Access Control | yes (light) | Live-WAN scenarios gated behind explicit operator confirmation; ATT requires louder gate; deploy needs `sudo install` (root) — already the pattern |
| V5 Input Validation | yes | Scenario name / pair args validated against `PAIRS` (the CLI already rejects unknown pairs); reject path-traversal in `chaos <name>` dispatch (constrain to `scripts/silicom-test-scenarios/<name>.sh`, no `..`) |
| V6 Cryptography | no | No crypto |
| V-Logging/Privacy | yes | Redact state JSON / `/health` payloads before persisting under `tests/silicom/` (CLAUDE.md public-safe rule; `phase213-steering-snapshot.sh` redaction pattern) |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Scenario name path traversal (`chaos ../../etc/...`) | Tampering/EoP | Resolve against fixed scenario dir, reject `/` and `..`, require file to exist under `scripts/silicom-test-scenarios/` |
| Dual-WAN loss via mis-typed scenario | DoS (self-inflicted) | both-WAN gate in `on`/`disc` (never pass `--both-wan-confirm` from single-pair scenarios) + default-safe pair = spec-modem |
| Pair stuck non-NIC after abort | DoS | always-on EXIT+INT+TERM restore trap (HARN-04) |
| Secret/IP leak into repo-tracked result dir | Information Disclosure | redact-on-capture; `.gitignore tests/silicom/` (recommended) |
| Unintended live arming of watchdog during a scenario | Tampering | harness composes `disarm`/W-INV-clean stops only; never raw `systemctl stop` watchdog (static `-k invariant` gate) |

## Sources

### Primary (HIGH confidence — in-repo, verified this session)
- `scripts/silicom-bypass` — full verb surface, idempotency, both-WAN gate, `sentineled_stop` trap pattern, restore verbs
- `tests/test_silicom_bypass_cli.py` — fake `bpctl_util`/`systemctl`/`logger` seam, call-log assertion pattern, W-INV gate, deploy-artifact assertions
- `scripts/deploy.sh` (`deploy_silicom_bypass`, `deploy_watchdog_artifacts`, `--silicom-bypass-only` handler) — DEPLOY-03 extension point
- `scripts/phase213-steering-snapshot.sh`, `scripts/phase213-health-poller.sh` — state/health capture, redaction, EXIT-trap-clean mktemp
- `scripts/phase225-safe13-boundary-check.sh` — SAFE-16 boundary-check tool pattern
- `.planning/phases/235-*/evidence/safe16-boundary-235.json`, `.../236-*/evidence/safe16-boundary-236.json` — exact evidence schema + `anchor: v1.51`
- `.planning/phases/235-*/235-0{1..4}-SUMMARY.md`, `.../236-0{1,2}-SUMMARY.md` — what 235/236 built and decided
- `deploy/scripts/cake-autorate-att-state-bridge` / `...-spectrum-state-bridge` — `/health` on 9101, state at `/var/lib/wanctl/<wan>_state.json`
- `src/wanctl/steering/daemon.py` — steering health port 9102 (poll target 9101)
- `.planning/ROADMAP.md` (Phase 237 section, DEPLOY-03/SAFE-16 notes), `.planning/REQUIREMENTS.md`, `.planning/seeds/SEED-006`, `.planning/STATE.md`
- `pyproject.toml` — pytest config (`--timeout=30 -m 'not integration'`)

### Secondary (MEDIUM)
- Project MEMORY.md / CLAUDE.md — Spectrum-as-safe-canary, both-WAN-on-cake-autorate, netperf Dallas Linode probe, public-safe doc rule

### Tertiary (LOW)
- None — no external/web sources needed; this phase is fully in-repo composition.

## Metadata

**Confidence breakdown:**
- Standard stack (reused artifacts): HIGH — every component read directly and is live-proven in 235/236
- Architecture (trap/compose/capture patterns): HIGH — trap pattern is the W-INV precedent; capture scripts already exist
- Pitfalls: HIGH — derived from the exact safety lessons encoded in 235/236 tests and W-INV
- DEPLOY-03 recommendation: HIGH on facts (standalone mode exists), MEDIUM on decision (operator may prefer separate)
- Live port/probe specifics (A1/A2): MEDIUM — confirm live at exec time

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (stable; all in-repo, no fast-moving external deps). Re-verify only if 235/236 artifacts change before 237 executes.
