# Phase 235: Bypass Operator CLI + Boot Baseline - Research

**Researched:** 2026-06-12
**Domain:** Bash operator CLI + systemd oneshot over Silicom `bpctl_util`; offline pytest verification of shell artifacts; SAFE-16 controller-path zero-diff
**Confidence:** HIGH (all sources are in-repo and authoritative; one stale-naming correction flagged for planner)

## Summary

This phase is pure bash + systemd + docs + tests. There is no new external dependency, no Python controller change, and no novel algorithm. The work is: (1) a single guarded `silicom-bypass` bash CLI wrapping `bpctl_util`, (2) a `silicom-bypass-init` oneshot that applies and read-back-asserts a known-good baseline at boot, and (3) reconciliation of the existing partial bpctl surface so there are not two competing boot units. Everything the CLI must do is already proven by hand in `docs/SILICOM-BYPASS.md` (validated live 2026-04-28) — the phase converts hand-typed `bpctl_util` invocations into a guarded, idempotent, journaled, testable tool.

The repo already has the exact patterns this phase needs. Shell artifacts are verified **offline via pytest** in two established ways: static content assertions (`tests/test_att_cake_autorate_artifacts.py`) and subprocess-with-env-injection runtime tests (`tests/test_check_safe07_source_diff.py`, `tests/test_check_cake.py`). The existing watchdog scripts already use a `BPCTL_UTIL=` environment override as a tool-path seam — the new CLI must keep that seam so a fake `bpctl_util` can be injected in tests and the live host is never touched by an executor. SAFE-16 has a turnkey checker: `scripts/phase225-safe13-boundary-check.sh --anchor v1.51` produces the JSON evidence and exits non-zero on any controller-path diff.

**One load-bearing correction for the planner:** the seed and CONTEXT.md specify `PAIRS="att-modem sil-spare1"`. That is **stale**. The `sil-spare1`/`sil-spare2` ports were renamed to `spec-modem`/`spec-router` on 2026-04-28 when Spectrum migrated onto the Silicom pair (`docs/SILICOM-BYPASS.md` lines 256-271; live env file `deploy/scripts/bpctl-watchdog-spectrum.env.example` says `IFACE=spec-modem`). The correct live config is `PAIRS="att-modem spec-modem"`. Do not ship `sil-spare1` into config.

**Primary recommendation:** Build `scripts/silicom-bypass` (bash, `set -euo pipefail`), pair-map and tool-path from `/etc/silicom-bypass.conf` with `BPCTL_UTIL` override, parse the card's human-readable `get_*` strings already documented in `docs/SILICOM-BYPASS.md` for read-back assertion, make `silicom-bypass-init.service` call a `silicom-bypass baseline` subcommand (single source of truth for bpctl invocations), and verify everything offline with a `tests/test_silicom_bypass_cli.py` pytest that injects a fake `bpctl_util`. Gate every live-host step.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**CLI surface (TOOL-01..04):**
- Single bash CLI at `scripts/silicom-bypass` wrapping `bpctl_util`.
- Subcommands this phase: `status [pair|all]`, `on <pair>`, `off <pair>`, `disc <pair>`, `conn <pair>`, `mark <label>`.
- `status` reads live state back from bpctl per pair (NIC / bypass / disconnect) — never cached.
- Non-bypass-capable interfaces are refused with a clear error.
- Verbs are idempotent: re-running a verb already in the target state is a no-op (exit 0, says so).
- Destructive verbs (`on`, `disc`) require `--yes`.
- A destructive op that would put BOTH pairs simultaneously into a non-NIC state additionally requires `--both-wan-confirm` (TOOL-03).
- `mark <label>` writes to the journal AND appends to `/var/log/silicom-bypass-marks.log`.
- All state changes log to journal.

**Boot baseline (BOOT-01):**
- `silicom-bypass-init.service` (oneshot) applies to BOTH pairs, after `bpctl_mod` loads and after the pair interfaces exist:
  - `set_dis_bypass off`, `set_bypass_pwoff on`, `set_bypass_pwup off`, `set_disc_pwup off`, `set_std_nic off`
- Each setting is read back and asserted after apply; any mismatch fails the unit loudly (non-zero exit, journal error).
- Reconcile with the existing `deploy/systemd/bpctl-silicom.service` rather than duplicating its job — extend/replace coherently, no two competing boot units with overlapping responsibilities.

**Reconciliation (not rebuild):**
- Existing scripts `wanctl-bpctl-{init,dkms-install,watchdog-petter,watchdog-bypass}` and unit `bpctl-silicom.service` are the starting surface. Reuse/absorb their logic; do not create a parallel second implementation.
- Watchdog petter/bypass scripts and watchdog units are out of scope here beyond not breaking them — their reconciliation is Phase 236.

**Config:**
- `/etc/silicom-bypass.conf` with `PAIRS="att-modem sil-spare1"` (master interface per pair), plus `WD_TIMEOUT_MS=10000`, `HEARTBEAT_MS=3000` reserved for Phase 236.
- Pair-to-interface mapping lives in config, not hardcoded in the CLI.
  - ⚠️ See Open Question Q1 / Assumption A1: `sil-spare1` is the stale name; live config must be `spec-modem`.

**Safety / SAFE-16:**
- Zero controller-path source diff at the phase boundary, verified (e.g. `git diff` over the protected file list), not assumed.
- This phase ships scripts/units/docs/tests only.
- Any live-host verification step in plans must be operator-gated (`autonomous: false` or explicit checkpoint), rollback path = restore NIC mode on both pairs.

### Claude's Discretion
- bpctl_util output parsing strategy and exact read-back assertion mechanics.
- Unit ordering/dependency expression (After=/Wants=/udev settle vs. polling loop with timeout) for interface existence.
- Shellcheck/test approach for the bash CLI.
- Exact error message wording and exit codes.
- Whether `silicom-bypass-init.service` ExecStart calls the CLI (`silicom-bypass baseline`-style subcommand) or a dedicated script — prefer whichever keeps a single source of truth for bpctl invocations.

### Deferred Ideas (OUT OF SCOPE)
- Watchdog arm/disarm verbs + watchdog unit reconciliation → Phase 236 (WDOG-01..03)
- HIL test harness (`silicom-test`, scenarios, result capture) → Phase 237 (HARN-*)
- Health-endpoint bypass-state observability → future milestone (explicitly out of this phase)
- Warm-reboot bypass preservation live test → operator-run, documented procedure only
- Unpowered fail-open retest → permanently settled, out of scope per RCA
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | `silicom-bypass status [pair|all]` reads live per-pair state (NIC/bypass/disconnect) from bpctl, not cached | `status` runs `get_bypass`/`get_disc`/`get_std_nic` per pair each call; human-readable output strings to parse are documented in `docs/SILICOM-BYPASS.md` (see "bpctl_util Verb Surface"). |
| TOOL-02 | Idempotent guarded verbs `on/off/disc/conn`; `on`/`disc` require `--yes`; non-bypass-capable iface refused | Idempotency = read current state, no-op if already there. `get_bypass_slave` is the capability probe (a non-pair iface has no slave → refuse). `set_bypass on/off`, `set_disc on/off` are the mutators (`docs/SILICOM-BYPASS.md`). |
| TOOL-03 | Dual-pair → non-NIC requires `--both-wan-confirm` | CLI checks the other pair's current state before acting; if this op + current other-pair state = both non-NIC, demand the extra flag. Pure CLI logic, fully offline-testable. |
| TOOL-04 | `silicom-bypass mark <label>` anchors journal narrative | `logger`/journal write + append to `/var/log/silicom-bypass-marks.log`. Trivial; offline-testable with a temp log path env override. |
| BOOT-01 | Oneshot applies 5-verb baseline to both pairs and read-back-asserts each | The 5 set_* verbs + their get_* readbacks are all documented with expected output strings in `docs/SILICOM-BYPASS.md` "Fail-Open Configuration Tested" (lines 540-578). Apply-then-assert loop. |
| SAFE-16 | Controller-path zero-diff at phase boundary (cross-phase invariant) | Turnkey checker exists: `scripts/phase225-safe13-boundary-check.sh --anchor v1.51`. Phase produces no `src/wanctl/` change by construction. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-pair bypass state query/change | Host CLI (bash) → `bpctl_util` → kernel driver → card relays | — | Bypass data path skips Linux entirely; this is operator tooling over the card's char device (`/dev/bpctl0`), not a controller function. |
| Boot baseline application | systemd oneshot (host) | CLI subcommand | Boot-time card policy belongs to a oneshot ordered before WAN services, mirroring existing `bpctl-silicom.service`. |
| Read-back assertion | CLI / oneshot (bash string compare) | — | The card's `get_*` verbs are the only source of truth; never cache. |
| Pair → interface mapping | Config file (`/etc/silicom-bypass.conf`) | — | Portable-controller rule: deployment specifics in config, not Python/bash branching. |
| Offline verification | pytest (host dev) injecting fake `bpctl_util` | — | Production is a live dual-WAN shaper; CI/executor must never invoke the real tool. |
| Controller-path protection | git boundary checker (read-only) | — | SAFE-16 is a git-diff invariant; no runtime coupling. |

## Standard Stack

No external packages are installed by this phase. The "stack" is OS-resident tooling already on `cake-shaper` and the repo's existing dev toolchain.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `bash` | system (`#!/usr/bin/env bash`, `set -euo pipefail`) | CLI + baseline logic | Repo convention for non-trivial scripts (`scripts/phase225-safe13-boundary-check.sh` uses `#!/usr/bin/env bash` + `set -euo pipefail`). The existing `wanctl-bpctl-*` scripts use `#!/bin/sh` + `set -eu`; the new CLI needs bash for arrays/`[[`. [VERIFIED: in-repo grep] |
| `bpctl_util` | bundled (`/opt/bpctl-silicom/bpctl_util`, DKMS module `bpctl_mod/5.2.0.46`, firmware `0xaa`) | Card control | Only sanctioned mutation path for the card. Source: `ddos-mitigator/bpctl-silicom` (per `docs/SILICOM-BYPASS.md` line 107). [VERIFIED: docs/SILICOM-BYPASS.md] |
| `systemd` oneshot | system | Boot baseline service | Mirrors `bpctl-silicom.service` (Type=oneshot, RemainAfterExit=yes). [VERIFIED: deploy/systemd/bpctl-silicom.service] |
| `pytest` | repo `.venv` | Offline artifact + runtime verification | Repo is pytest-only; no bats. `make test` → `.venv/bin/pytest tests/ -v`. [VERIFIED: Makefile] |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `logger` (util-linux) | Journal-tag the `mark` and state changes | TOOL-04 + all state-change logging. Already standard. |
| `shellcheck` | Static bash lint | Discretionary; repo `make ci` does NOT currently run shellcheck (no shellcheck/bats targets in Makefile). Run manually or add a pytest that shells out to shellcheck if desired. [VERIFIED: Makefile grep — no shellcheck target] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `silicom-bypass-init.service` calling `silicom-bypass baseline` | A dedicated `silicom-bypass-baseline` script | CONTEXT discretion item. Calling the CLI keeps a single source of truth for bpctl invocations (recommended); a dedicated script duplicates parse/assert logic. Prefer the subcommand. |
| pytest subprocess + fake `bpctl_util` | bats | Repo has zero bats infrastructure; adding it is new surface. pytest already proves shell artifacts here. Stay pytest. |
| `#!/usr/bin/env bash` for the CLI | `#!/bin/sh` (matching existing bpctl scripts) | The CLI needs arg parsing, arrays, and `[[`; bash is the right tool and matches the repo's heavier scripts. Keep the simple existing `wanctl-bpctl-init` as `/bin/sh` when absorbing it. |

**Installation:** None. No `npm`/`pip`/`cargo` install. The Package Legitimacy Audit below is therefore N/A.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages. All tooling (`bash`, `bpctl_util`, `systemd`, `logger`, `pytest`) is already resident on the host or in the repo `.venv`. slopcheck/registry verification has no targets. No `[SLOP]`/`[SUS]` risk surface exists for this phase.

## Architecture Patterns

### System Architecture Diagram

```
                 ┌─────────────────────────────────────────────┐
 operator  ─────▶│  silicom-bypass  (scripts/silicom-bypass)    │
 (SSH, gated)    │  bash, set -euo pipefail                     │
                 │                                              │
                 │  parse args ─▶ load /etc/silicom-bypass.conf │
                 │     │            (PAIRS, BPCTL_UTIL path)     │
                 │     ▼                                         │
                 │  resolve <pair> ─▶ master iface              │
                 │     │   (refuse if not in PAIRS / no slave)  │
                 │     ▼                                         │
                 │  dispatch verb:                              │
                 │   status ─▶ read get_* ─▶ format             │
                 │   on/off/disc/conn ─▶ read current state     │
                 │        │  (idempotent: no-op if already)     │
                 │        │  (--yes gate on on/disc)            │
                 │        │  (--both-wan-confirm dual gate)     │
                 │        ▼                                      │
                 │   set_* ─▶ read-back ─▶ assert ─▶ journal    │
                 │   mark ─▶ logger + /var/log/...marks.log     │
                 │   baseline ─▶ 5×(set_*; get_*; assert) ×pair │
                 └───────────────┬──────────────────────────────┘
                                 │ exec
                                 ▼
                 $BPCTL_UTIL <iface> <verb> [arg]
              (real: /opt/bpctl-silicom/bpctl_util)
              (test:  fake script honoring $BPCTL_UTIL)
                                 │
                                 ▼
                   bpctl_mod ─▶ /dev/bpctl0 ─▶ card relays


  boot:  systemd ──▶ silicom-bypass-init.service (oneshot, RemainAfterExit)
           After=  bpctl module loaded + pair ifaces exist
           ExecStart=/usr/local/sbin/silicom-bypass baseline   (single source of truth)
           non-zero exit + journal error on any read-back mismatch
           Ordered Before= WAN/cake-autorate services
```

### Recommended Project Structure
```
scripts/
├── silicom-bypass                 # NEW: bash CLI (the single bpctl mutation path)
├── wanctl-bpctl-init              # EXISTING: module load + /dev/bpctl0 — keep, reference from baseline ordering
├── wanctl-bpctl-dkms-install      # EXISTING: leave alone (DKMS, not in this phase)
├── wanctl-bpctl-watchdog-petter   # EXISTING: Phase 236 — DO NOT MODIFY (don't break)
└── wanctl-bpctl-watchdog-bypass   # EXISTING: Phase 236 — DO NOT MODIFY

deploy/systemd/
├── bpctl-silicom.service          # EXISTING: module/dev oneshot — reconcile ordering with init service
└── silicom-bypass-init.service    # NEW: baseline oneshot (calls `silicom-bypass baseline`)

deploy/scripts/ (or configs/)
└── silicom-bypass.conf.example    # NEW: PAIRS="att-modem spec-modem", WD_TIMEOUT_MS, HEARTBEAT_MS

tests/
└── test_silicom_bypass_cli.py     # NEW: pytest — static asserts + subprocess w/ fake bpctl_util

docs/
└── SILICOM-BYPASS.md              # EXISTING: extend with CLI usage + operator-gated live procedures
```

### Pattern 1: Tool-path env seam for offline testability
**What:** Resolve the `bpctl_util` path from an overridable variable, exactly as the existing watchdog scripts already do.
**When to use:** Always — it is the mechanism that lets pytest inject a fake tool and keeps executors off the live card.
**Example:**
```bash
# Source: scripts/wanctl-bpctl-watchdog-petter (existing repo convention)
: "${BPCTL_UTIL:=/opt/bpctl-silicom/bpctl_util}"
util() { "$BPCTL_UTIL" "$IFACE" "$@"; }
```
The new CLI keeps this seam. A pytest fixture writes a fake `bpctl_util` (a bash stub that echoes canned `get_*` strings and records `set_*` calls), points `BPCTL_UTIL` at it via env, and asserts on the recorded calls and the CLI's exit code/output. [VERIFIED: tests/test_check_safe07_source_diff.py + tests/test_att_cake_autorate_artifacts.py establish the subprocess+env pattern]

### Pattern 2: Read-back assertion against the card's human-readable strings
**What:** After every `set_*`, run the paired `get_*` and string-match the documented expected output; mismatch = loud failure.
**When to use:** BOOT-01 baseline and every CLI state change.
**Example:**
```bash
# Source: expected strings documented in docs/SILICOM-BYPASS.md lines 540-578
apply_assert() {            # apply_assert <iface> set_std_nic off get_std_nic "not in Standard NIC mode"
  local iface="$1" setverb="$2" setarg="$3" getverb="$4" want="$5"
  "$BPCTL_UTIL" "$iface" "$setverb" "$setarg"
  local got; got="$("$BPCTL_UTIL" "$iface" "$getverb")"
  case "$got" in *"$want"*) : ;; *)
    printf 'silicom-bypass: %s %s: read-back FAILED (want %q, got %q)\n' \
      "$iface" "$getverb" "$want" "$got" >&2
    return 1 ;;
  esac
}
```

### Pattern 3: systemd oneshot ordered after module + interfaces
**What:** Gate the baseline service on the bpctl module being loaded and the pair interfaces existing, then `Before=` the WAN/cake-autorate services.
**When to use:** `silicom-bypass-init.service`.
**Example:**
```ini
# Source: deploy/systemd/bpctl-silicom.service (existing pattern to mirror/reconcile)
[Unit]
Description=Silicom bypass known-good boot baseline
Requires=bpctl-silicom.service
After=bpctl-silicom.service systemd-networkd-wait-online.service
Before=cake-autorate-att.service cake-autorate-spectrum.service wanctl@att.service wanctl@spectrum.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/silicom-bypass baseline

[Install]
WantedBy=multi-user.target
```
Interface-existence wait: prefer ordering on `bpctl-silicom.service` (which already verifies `bpctl_util info` succeeds) plus a bounded poll loop inside `silicom-bypass baseline` for each pair's master iface (mirrors `wanctl-bpctl-init`'s 50×0.1s `/proc/devices` poll). Avoid `systemd-udev-settle` (deprecated); `bpctl-silicom.service` currently uses it — note for reconciliation but don't expand its use.

### Anti-Patterns to Avoid
- **Two competing boot units.** Do not leave `bpctl-silicom.service` and `silicom-bypass-init.service` both trying to own card policy. `bpctl-silicom.service` owns module+`/dev/bpctl0`; the new init service owns *policy baseline* and `Requires=`/`After=` the former. Clear split, documented.
- **Caching status.** `status` must call `get_*` every invocation (TOOL-01 is explicit). No state file, no memoization.
- **Hardcoding pair interfaces in the CLI.** Mapping lives in `/etc/silicom-bypass.conf` (portable-controller rule). The CLI reads `PAIRS`.
- **Shipping `sil-spare1`.** Use `spec-modem` (see Assumption A1).
- **Executor running the real `bpctl_util`.** Every live-host step is operator-gated. Offline tests use the fake.
- **Touching `wanctl-bpctl-watchdog-*` or watchdog units.** Phase 236 scope. Only constraint here: don't break them.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Card mutation | Direct `/dev/bpctl0` ioctl | `bpctl_util <iface> <verb>` | The util is the documented, validated interface; ioctl is the driver's private ABI. |
| Module load + device node | New modprobe/mknod logic | Existing `wanctl-bpctl-init` (absorb/reference, don't reimplement) | Already handles DKMS fallback, major-number poll, `/dev/bpctl0` recreation. |
| Controller-path diff proof | A new bespoke git script | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51` | Turnkey, emits JSON evidence, per-file hash + numstat, fails closed. The SAFE-07..15 lineage all used it. |
| Capability detection (is iface a bypass pair?) | Heuristics on iface name | `bpctl_util <iface> get_bypass_slave` | Card-authoritative. `att-modem`/`spec-modem` return their slave; a non-pair iface does not. (`docs/SILICOM-BYPASS.md` lines 226-259, 533.) |
| Shell-artifact testing | bats + new CI wiring | pytest subprocess + fake tool (existing pattern) | Repo already proves shell scripts this way; no new framework. |

**Key insight:** Nearly every primitive this phase needs is already validated by hand in `docs/SILICOM-BYPASS.md` and partially scripted in `wanctl-bpctl-*`. The job is consolidation and guarding, not invention. The single biggest risk is *not* technical — it is shipping the stale `sil-spare1` interface name into config.

## Runtime State Inventory

This phase creates new artifacts; it does not rename existing runtime state. Still, two reconciliation-relevant items:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. CLI is stateless (status read-back is live). `mark` appends to `/var/log/silicom-bypass-marks.log` (new flat log, no migration). | None. |
| Live service config | `bpctl-silicom.service` is **enabled on the live host** (per `docs/SILICOM-BYPASS.md`) and orders `Before=wanctl@att/spectrum` — but those wanctl@ units are now disabled (cake-autorate mode). The new init service should `Before=` the cake-autorate units too. | Plan: reconcile ordering targets; operator-gated `systemctl enable silicom-bypass-init.service`. |
| OS-registered state | `bpctl_mod` DKMS module + `/dev/bpctl0` char device. Untouched by this phase (Phase manages policy, not the module). | None (DKMS install is `wanctl-bpctl-dkms-install`, out of scope). |
| Secrets/env vars | None. No secrets. `BPCTL_UTIL`, `PAIRS` etc. are non-secret config. | None. |
| Build artifacts / installed packages | The new `scripts/silicom-bypass` and `silicom-bypass-init.service` are **not yet wired into any deploy path** (see Open Question Q2). `bpctl-silicom.service` + `wanctl-bpctl-*` scripts are themselves **not deployed by repo automation today** — deploy.sh only *checks* for their presence (line 497); they reached the host manually. | Plan must decide minimal repo-owned deploy seam for the new artifacts (DEPLOY-03 is formally Phase 237, but 235 artifacts must be installable). |

## Common Pitfalls

### Pitfall 1: Stale Spectrum interface name (`sil-spare1`)
**What goes wrong:** Config ships `PAIRS="att-modem sil-spare1"`; baseline oneshot and `status spectrum` target a non-existent interface; baseline read-back fails or silently no-ops on the wrong pair.
**Why it happens:** Seed (2026-05-26) and CONTEXT predate / didn't propagate the 2026-04-28 port rename. The Silicom Spectrum ports are now `spec-modem`/`spec-router`.
**How to avoid:** Use `PAIRS="att-modem spec-modem"`. Corroborated by live `deploy/scripts/bpctl-watchdog-spectrum.env.example` (`IFACE=spec-modem`) and `docs/SILICOM-BYPASS.md` lines 256-271. Add a CLI startup check that each `PAIRS` master iface returns a `get_bypass_slave` (refuses unknown/renamed ifaces loudly).
**Warning signs:** `status all` errors on the second pair; baseline asserts pass for att but fail/skip spectrum.

### Pitfall 2: `set_dis_bypass off` reads as "Bypass mode enabled" (counterintuitive)
**What goes wrong:** Read-back assertion is written to expect `get_dis_bypass` == "disabled" after `set_dis_bypass off`, and fails on a correct card.
**Why it happens:** `set_dis_bypass off` clears the bypass-*disable* bit, so `get_dis_bypass` correctly reports `Bypass mode is enabled` (`docs/SILICOM-BYPASS.md` lines 537-539, 572). Double negative.
**How to avoid:** Encode the expected read-back string from the documented "Expected powered result" block (lines 566-575), not from intuition. For the baseline: `get_dis_bypass` → `Bypass mode enabled`; `get_bypass_pwoff` → `Bypass at power off`; `get_bypass_pwup` → `non-Bypass at power up`; `get_disc_pwup` → `non-Disconnect at power up`; `get_std_nic` → `not in Standard NIC mode`.
**Warning signs:** Baseline oneshot fails read-back on a card that `docs/SILICOM-BYPASS.md` says is correctly configured.

### Pitfall 3: Executor runs the real `bpctl_util` against live WANs
**What goes wrong:** An automated step issues `set_bypass on` / `set_disc on` on a live pair, dropping a WAN (live bypass removes the host from path; `disc` simulates a cable pull). On `att-modem` this kills ATT; on both pairs it kills both WANs.
**Why it happens:** No gating; tests or "verification" steps invoke the real tool.
**How to avoid:** All offline tests inject a fake `BPCTL_UTIL`. Every plan step that runs the real CLI on the host is `autonomous: false` / explicit operator checkpoint. Rollback for any live step = `silicom-bypass off <pair>` + `conn <pair>` (restore NIC) on both pairs. The `--both-wan-confirm` gate is the in-tool backstop.
**Warning signs:** A plan task without an operator gate that references `/opt/bpctl-silicom/bpctl_util` or the host.

### Pitfall 4: Output-string drift between firmware/tool versions
**What goes wrong:** Read-back parser matches an exact full string that a different `bpctl_util` build phrases differently.
**Why it happens:** The documented strings (`non-Bypass`, `not in Standard NIC mode`) come from this card/firmware (`0xaa`, module `5.2.0.46`). Upstream forks may phrase differently (web sources show some builds emit `0/1`).
**How to avoid:** Match on a stable substring (`*Bypass*` vs `*non-Bypass*` ordering matters — test `*non-Bypass*` first) rather than whole-line equality; centralize the want-strings in one place in the CLI so a future drift is a one-line fix. Confidence on exact strings: HIGH for this host (in-repo validated output), LOW that they generalize to other bpctl builds.

## Code Examples

### CLI skeleton (arg parse + config + dispatch)
```bash
#!/usr/bin/env bash
# Source: repo convention (scripts/phase225-safe13-boundary-check.sh header style)
set -euo pipefail

CONF="${SILICOM_BYPASS_CONF:-/etc/silicom-bypass.conf}"
: "${BPCTL_UTIL:=/opt/bpctl-silicom/bpctl_util}"
MARKS_LOG="${SILICOM_MARKS_LOG:-/var/log/silicom-bypass-marks.log}"
# shellcheck source=/dev/null
[ -r "$CONF" ] && . "$CONF"            # provides PAIRS="att-modem spec-modem"

die() { printf 'silicom-bypass: %s\n' "$*" >&2; exit "${2:-1}"; }
journal() { logger -t silicom-bypass -- "$*"; }
```

### Idempotent verb (read-then-act)
```bash
# off <pair>: ensure NIC (non-bypass). Idempotent, no --yes (non-destructive).
cmd_off() {                            # restoring to NIC is the safe direction
  local iface; iface="$(resolve_pair "$1")"
  local cur; cur="$("$BPCTL_UTIL" "$iface" get_bypass)"
  case "$cur" in *non-Bypass*)
    echo "$1 already non-bypass (NIC); no-op"; return 0 ;;
  esac
  "$BPCTL_UTIL" "$iface" set_bypass off
  assert_substr "$("$BPCTL_UTIL" "$iface" get_bypass)" "non-Bypass" \
    "$1 set_bypass off"
  journal "off $1: set_bypass off OK"
}
```

### pytest with fake bpctl_util (offline, the testability spine)
```python
# Source: pattern from tests/test_check_safe07_source_diff.py (subprocess) +
#         tests/test_att_cake_autorate_artifacts.py (static asserts)
import subprocess, os, textwrap
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
CLI  = REPO / "scripts" / "silicom-bypass"

def _fake_bpctl(tmp_path, responses):   # responses: {get_verb: "string"}
    rec = tmp_path / "calls.log"
    f = tmp_path / "bpctl_util"
    cases = "\n".join(f'    {v}) echo "{s}";;' for v, s in responses.items())
    f.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        echo "$@" >> {rec}
        case "$2" in
{cases}
          *) exit 0;;
        esac
    """))
    f.chmod(0o755)
    return f, rec

def test_off_is_idempotent_noop(tmp_path):
    fake, rec = _fake_bpctl(tmp_path, {"get_bypass": "non-Bypass"})
    env = {**os.environ, "BPCTL_UTIL": str(fake),
           "SILICOM_BYPASS_CONF": "/dev/null"}  # inject PAIRS via env or temp conf
    r = subprocess.run(["bash", str(CLI), "off", "att-modem"],
                       env={**env, "PAIRS": "att-modem spec-modem"},
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "no-op" in r.stdout
    assert "set_bypass off" not in rec.read_text()   # proved idempotent
```

### SAFE-16 boundary proof (operator/CI runnable, read-only)
```bash
# Source: scripts/phase225-safe13-boundary-check.sh (existing, turnkey)
scripts/phase225-safe13-boundary-check.sh \
  --anchor v1.51 \
  --out .planning/phases/235-bypass-operator-cli-boot-baseline/evidence/safe16-boundary-235.json
# exit 0 + passed=true + controller_path_diff_count=0 == SAFE-16 holds
```

## bpctl_util Verb Surface (read-back pairing)

Authoritative source for *this card/firmware*: `docs/SILICOM-BYPASS.md`. Expected output strings below are from the validated "Expected powered result" block (lines 566-575) and the known-good state blocks (lines 229-240, 283-289). [VERIFIED: docs/SILICOM-BYPASS.md] [CITED for generic semantics: github.com/redBorder/bpctl readme.txt]

| set_* (BOOT-01) | paired get_* | expected read-back substring after baseline |
|-----------------|--------------|---------------------------------------------|
| `set_dis_bypass off` | `get_dis_bypass` | `Bypass mode enabled` (counterintuitive — clears disable bit) |
| `set_bypass_pwoff on` | `get_bypass_pwoff` | `Bypass at power off` |
| `set_bypass_pwup off` | `get_bypass_pwup` | `non-Bypass at power up` |
| `set_disc_pwup off` | `get_disc_pwup` | `non-Disconnect at power up` |
| `set_std_nic off` | `get_std_nic` | `not in Standard NIC mode` |

| CLI verb | set_* mutator | get_* read-back | target state string |
|----------|---------------|-----------------|---------------------|
| `on <pair>` (destructive, `--yes`) | `set_bypass on` | `get_bypass` | `Bypass` (NOT `non-Bypass`) |
| `off <pair>` | `set_bypass off` | `get_bypass` | `non-Bypass` |
| `disc <pair>` (destructive, `--yes`) | `set_disc on` | `get_disc` | `Disconnect` (NOT `non-Disconnect`) |
| `conn <pair>` | `set_disc off` | `get_disc` | `non-Disconnect` |
| `status` (read-only) | — | `get_bypass`, `get_disc`, `get_std_nic` | report all three per pair |
| capability probe | — | `get_bypass_slave` | non-empty slave (else refuse iface) |

Substring-match guidance: test the `non-` form first (`*non-Bypass*`), because `*Bypass*` matches both. Centralize these constants.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-typed `cd /opt/bpctl-silicom; sudo ./bpctl_util <iface> <verb>` | Guarded `silicom-bypass <verb> <pair>` | This phase | Removes typo-induced dual-WAN loss; adds idempotency, journal, read-back. |
| Spectrum on Supermicro I350 (`old-spec-modem`) | Spectrum on Silicom pair (`spec-modem`/`spec-router`) | 2026-04-28 | The naming correction this research flags. |
| `wanctl@`-coupled watchdog ownership | external cake-autorate two-mode | 2026-06-08 | Out of scope here (Phase 236), but affects `Before=` targets of the new init service (cake-autorate units, not wanctl@). |

**Deprecated/outdated:**
- `sil-spare1`/`sil-spare2` interface names — renamed to `spec-modem`/`spec-router`. Only a historical mention remains (`docs/SILICOM-BYPASS.md` line 526 describing the original validation).
- `systemd-udev-settle.service` — deprecated by systemd; `bpctl-silicom.service` still references it. Do not propagate to the new unit; order on `bpctl-silicom.service` + bounded poll instead.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Correct live Spectrum pair master iface is `spec-modem` (not `sil-spare1` as CONTEXT/seed state). | User Constraints / Pitfall 1 | HIGH — baseline + `status spectrum` target a dead iface. Mitigation: corroborated by live env file + docs; CLI should refuse ifaces without a `get_bypass_slave`. Recommend planner confirm `PAIRS="att-modem spec-modem"` with operator before locking config. |
| A2 | Expected `get_*` output substrings (e.g. `non-Bypass`, `not in Standard NIC mode`) are stable for this card/firmware (`0xaa`, module `5.2.0.46`). | bpctl_util Verb Surface | MEDIUM — drift breaks read-back parsing. Mitigation: substring match + centralized constants. Strings are from in-repo validated output (2026-04-28), so HIGH for this host. |
| A3 | `silicom-bypass-init.service` should `Before=` the cake-autorate units (att/spectrum), since wanctl@ is disabled. | Pattern 3 / Runtime State | LOW — wrong ordering only affects boot races, not correctness; the baseline is idempotent. Confirm at plan time against current live unit set. |
| A4 | New 235 artifacts can be made installable via a small extension to the existing deploy seam without finalizing the full DEPLOY-03 path (formally Phase 237). | Open Questions Q2 | LOW — the planner can scope a minimal install step; DEPLOY-03 finalization stays in 237. |

## Open Questions

1. **Spectrum pair interface name — `spec-modem` vs `sil-spare1`.**
   - What we know: Live env file + `docs/SILICOM-BYPASS.md` say `spec-modem`/`spec-router` (renamed 2026-04-28). CONTEXT/seed say `sil-spare1`.
   - What's unclear: Whether the operator wants the config keyed on the live name now.
   - Recommendation: Ship `PAIRS="att-modem spec-modem"`. Treat the seed value as stale. Surface this in discuss/plan for a 1-line operator confirm. (Assumption A1.)

2. **Deploy seam for the new 235 artifacts.**
   - What we know: `bpctl-silicom.service` + `wanctl-bpctl-*` are NOT deployed by repo automation today (deploy.sh only checks presence at line 497; install.sh has no bpctl handling). DEPLOY-03 (single documented path) is formally Phase 237.
   - What's unclear: Whether 235 adds a minimal install step now or relies on manual host placement until 237.
   - Recommendation: Add a small, explicitly operator-gated install step (scp → `/usr/local/sbin/silicom-bypass` + unit → `$TARGET_SYSTEMD_DIR`), mirroring the cake-autorate state-bridge deploy stanza (deploy.sh lines 480-501). Keep DEPLOY-03 *finalization* in 237. (Assumption A4.)

3. **`silicom-bypass-init.service` ordering target set.**
   - What we know: Old `bpctl-silicom.service` orders `Before=wanctl@att/spectrum` (now disabled). Live mode is cake-autorate.
   - Recommendation: `Before=` both wanctl@ and cake-autorate units (harmless if a unit is absent/disabled); `Requires=`/`After=bpctl-silicom.service`. Confirm live unit names at plan time. (Assumption A3.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `bash` | CLI + tests | ✓ (dev host) | system | — |
| `pytest` (`.venv`) | offline verification | ✓ | repo `.venv` | `make test` |
| `git` | SAFE-16 boundary checker | ✓ | system | — |
| `python3` | boundary checker internals | ✓ | system | — |
| `bpctl_util` + card | live verification ONLY | ✗ on dev host (lives on `cake-shaper`) | `5.2.0.46`/fw `0xaa` on host | Fake `bpctl_util` for all offline tests; real tool only in operator-gated host steps |
| `shellcheck` | optional bash lint | unknown on dev host | — | Not in `make ci`; skip or add as discretionary pytest-shellout |

**Missing dependencies with no fallback:** None for the in-repo deliverable. The live card is intentionally unavailable to executors — that is the design (offline tests + operator-gated host steps).

**Missing dependencies with fallback:** Live `bpctl_util`/card → fake-tool injection covers all automated acceptance criteria.

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation` not disabled).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo `.venv`); **no bats** |
| Config file | `pyproject.toml` / `tests/conftest.py` (existing) |
| Quick run command | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q` |
| Full suite command | `make test` (`.venv/bin/pytest tests/ -v`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command (offline) | File Exists? |
|--------|----------|-----------|------------------------------|-------------|
| TOOL-01 | `status` reads `get_*` live per pair, not cached | unit (fake tool) | `pytest tests/test_silicom_bypass_cli.py::test_status_reads_live -x` | ❌ Wave 0 |
| TOOL-02 | idempotent no-op; `--yes` gate on `on`/`disc`; non-pair iface refused | unit (fake tool) | `::test_off_idempotent_noop`, `::test_on_requires_yes`, `::test_refuses_non_pair_iface` | ❌ Wave 0 |
| TOOL-03 | dual-pair → non-NIC needs `--both-wan-confirm` | unit (fake tool, both pairs primed) | `::test_both_wan_confirm_gate` | ❌ Wave 0 |
| TOOL-04 | `mark` → journal + flat log | unit (temp log path env) | `::test_mark_appends_log` | ❌ Wave 0 |
| BOOT-01 | baseline applies 5 verbs + asserts read-back; fails loud on mismatch | unit (fake tool: good path + injected-mismatch path) | `::test_baseline_applies_and_asserts`, `::test_baseline_fails_on_mismatch` | ❌ Wave 0 |
| BOOT-01 (unit shape) | `silicom-bypass-init.service` is well-formed and calls `silicom-bypass baseline` | static asserts on unit file | `::test_init_service_artifact` | ❌ Wave 0 |
| DEPLOY (235 slice) | new artifacts referenced by chosen deploy seam + exist in repo | static (mirror `test_att_cake_autorate_artifacts.py`) | `::test_artifacts_repo_owned` | ❌ Wave 0 |
| SAFE-16 | controller-path zero-diff | git boundary check (read-only) | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out <evidence>` | ✅ exists |

### Fidelity ladder (offline mock vs operator-gated live)
- **Offline mock (full automation, executor-safe):** TOOL-01..04, BOOT-01 logic, artifact statics, SAFE-16 git proof. All via fake `bpctl_util` + git. **All Phase 235 acceptance criteria are satisfiable offline** — no live host needed to pass the phase gate.
- **Operator-gated live (post-merge, human-run, `autonomous: false`):** real `silicom-bypass status all` on `cake-shaper`; manual run of `silicom-bypass-init.service` and journal inspection; optional warm-reboot bypass-preservation procedure on `spec-modem` only (documented, not executed by plan). Rollback for any live verb = `off`+`conn` both pairs.

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q`
- **Per wave merge:** `make test`
- **Phase gate:** `make test` green + SAFE-16 boundary JSON `passed=true` before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_silicom_bypass_cli.py` — covers TOOL-01..04, BOOT-01; includes the fake-`bpctl_util` fixture helper
- [ ] Fake `bpctl_util` fixture (inline in the test or `tests/fixtures/`) — the offline seam
- [ ] No framework install needed (pytest present). No bats.

## Security Domain

`security_enforcement` is not configured for this project (treated as enabled by default, but the threat surface here is operational, not appsec). This phase has no network input, no auth, no crypto, no user-supplied data parsing beyond CLI args.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | CLI runs as root on host via SSH key (existing host auth) |
| V3 Session Management | no | — |
| V4 Access Control | partial | Destructive verbs gated by `--yes` / `--both-wan-confirm`; root-only host access |
| V5 Input Validation | yes | Validate `<pair>` against `PAIRS` allowlist + `get_bypass_slave` probe; reject unknown args; quote all expansions (`set -euo pipefail`, no `eval`) |
| V6 Cryptography | no | No secrets, no crypto |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator typo → both WANs into bypass/disc | Denial of Service | `--both-wan-confirm` dual gate (TOOL-03); idempotent no-ops; read-back assertion |
| Executor runs real tool on live card | Denial of Service | Fake `BPCTL_UTIL` in all tests; live steps `autonomous: false` |
| Unvalidated `<pair>` arg reaching `bpctl_util` | Tampering | Allowlist `PAIRS` + `get_bypass_slave` capability probe before any `set_*` |
| Shell injection via label/args | Tampering | `set -euo pipefail`, quoted expansions, `logger -- "$label"` (no `eval`, no unquoted word-splitting); shellcheck-clean |
| Controller-path mutation slips in | Tampering (against SAFE-16 invariant) | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51` at phase gate |

## Sources

### Primary (HIGH confidence)
- `docs/SILICOM-BYPASS.md` — card/firmware behavior, exact `get_*` output strings, baseline verb sequence, pair mappings (`spec-modem`/`spec-router`), counterintuitive `set_dis_bypass` semantics, live validation 2026-04-28.
- `scripts/wanctl-bpctl-init`, `wanctl-bpctl-watchdog-petter`, `wanctl-bpctl-watchdog-bypass`, `wanctl-bpctl-dkms-install` — existing surface to reconcile; `BPCTL_UTIL` env seam.
- `deploy/systemd/bpctl-silicom.service`, `silicom-bypass-watchdog@.service`, `silicom-bypass-watchdog-cake-autorate-att.service` — unit patterns + Phase 236 boundary.
- `deploy/scripts/bpctl-watchdog-spectrum.env.example` (`IFACE=spec-modem`) — corroborates A1.
- `scripts/phase225-safe13-boundary-check.sh` — turnkey SAFE-16 boundary proof.
- `tests/test_att_cake_autorate_artifacts.py`, `tests/test_check_safe07_source_diff.py` — offline shell-artifact verification patterns (static + subprocess/env).
- `scripts/deploy.sh` (lines 62-71, 480-501) — deploy file-list + bpctl presence check (line 497); deploy seam to mirror.
- `Makefile` — pytest-only, no bats/shellcheck targets.
- `.planning/milestones/v1.51-phases/234-.../234-VERIFICATION.md` — SAFE-15 verification mechanics (anchor-based boundary JSON + independent `git diff --quiet`).

### Secondary (MEDIUM confidence)
- `.planning/seeds/SEED-006-...md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` — scope/contract (note: SEED-006 carries the stale `sil-spare1` name).

### Tertiary (LOW confidence)
- github.com/redBorder/bpctl `readme.txt` / `bp_util.c`, github.com/ddos-mitigator/bp_ctl — generic `bpctl_util` verb semantics and that some builds emit `0/1`. Used only to confirm verb existence; the host's human-readable strings in `docs/SILICOM-BYPASS.md` are authoritative for parsing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all in-repo/OS-resident; no external packages.
- Architecture / patterns: HIGH — directly mirrors existing repo units, scripts, and test conventions.
- bpctl verb surface / read-back strings: HIGH for this host (validated in-repo), LOW that strings generalize to other bpctl builds.
- Pitfalls: HIGH — the `sil-spare1`→`spec-modem` rename and the `set_dis_bypass` double-negative are both documented and load-bearing.
- Deploy seam: MEDIUM — gap identified (235 artifacts not yet wired); minimal extension recommended, full path is Phase 237.

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (stable; revisit if the live unit set or pair naming changes, or if `bpctl_util`/firmware is upgraded)
