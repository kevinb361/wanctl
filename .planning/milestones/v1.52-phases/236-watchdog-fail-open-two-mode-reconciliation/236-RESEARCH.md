# Phase 236: Watchdog Fail-Open Two-Mode Reconciliation - Research

**Researched:** 2026-06-12
**Domain:** systemd unit reconciliation + bash CLI extension + Silicom bpctl hardware watchdog + non-destructive shim testing
**Confidence:** HIGH (all findings verified against live repo files, git history, and the existing test harness; zero external dependencies)

## Summary

This phase reconciles the Silicom heartbeat-watchdog fail-open path to the post-2026-06-08 reality where both WANs run external cake-autorate and `wanctl@{spectrum,att}` are disabled. The reconciliation surface is small, well-understood, and entirely in-repo: four systemd units, two `.env` example files, two runtime shell scripts (`wanctl-bpctl-watchdog-petter`, `wanctl-bpctl-watchdog-bypass`), the `silicom-bypass` CLI (extend with `arm`/`disarm`), and the offline pytest harness. There is **zero new technology** — every artifact has a strong in-repo analog and the petter is **already parameterized** by `WANCTL_UNIT`, which is the crux of the reconciliation.

The core defect: the generic `silicom-bypass-watchdog@.service` template hardcodes `After=...wanctl@%i.service` / `Wants=wanctl@%i.service` and is fed by `/etc/wanctl/bpctl-watchdog/%i.env` files that still set `WANCTL_UNIT=wanctl@spectrum.service` / `wanctl@att.service`. During the ATT migration, the operator side-stepped this by **bolting on a one-off variant** (`silicom-bypass-watchdog-cake-autorate-att.service`) that pets against `cake-autorate-att.service` — but left Spectrum on the stale template. The result is an asymmetric, fragile two-unit reality where the Spectrum watchdog, if armed, would observe `wanctl@spectrum.service` as **inactive** (it's disabled) and immediately drive the pair into bypass. That is the WDOG-02 failure mode: **a watched-unit name that no longer matches the live controller makes the petter treat a healthy system as dead.**

**Primary recommendation:** Two plans. Plan 01 reconciles the units + env files + petter so both pairs watch their **live** controller unit (cake-autorate, configurable, no `wanctl@` assumption), ships off-by-default, and wires `arm`/`disarm` CLI verbs with a live-pair gate — proven offline by extending the existing fake-bpctl harness with a watchdog shim. Plan 02 documents the 2026-06-08 failure mode as understood/covered, runs the non-destructive heartbeat-death → relay-bypass shim proof, and closes the SAFE-16 boundary. Keep `arm`/`disarm` strictly opt-in; **never** let any executor/test step arm a live relay.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Heartbeat petting / watchdog reset loop | Host service (systemd `Type=simple` long-running) | — | Runs as a daemon on `cake-shaper`; resets hardware watchdog every `HEARTBEAT_SECONDS` |
| Relay fail-open actuation | Silicom card firmware (hardware watchdog timer) | Host service (`ExecStop` bypass script) | Hardware fires bypass on timer expiry independent of Linux; that is the whole point of fail-open |
| "Which controller is alive?" decision | Host service (petter, via `systemctl is-active $WANCTL_UNIT`) | systemd unit ordering | The petter polls the **configured** watched unit name; this is the stale-coupling surface |
| Arm/disarm policy + live gate | Operator CLI (`silicom-bypass`, bash) | — | Operator-driven; arming a live pair is an explicit, never-implicit action |
| Off-by-default + per-pair opt-in | systemd enablement state + `.env` presence | deploy.sh (install-if-absent) | Units installed but not enabled; operator enables per pair |
| Controller logic | `src/wanctl` (Python) — **OUT OF SCOPE, zero-diff** | — | SAFE-16: this phase touches failure/units only, never controller path |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WDOG-01 | Watchdog units cover both pairs under external cake-autorate mode; stale `wanctl@`-coupled generic template AND v1.50 ATT variant reconciled so neither assumes native `wanctl@` ownership; OFF by default, per-pair operator opt-in | Petter already parameterized by `WANCTL_UNIT`; reconciliation = correct the template's hardcoded `After=/Wants=wanctl@%i` + the `.env` `WANCTL_UNIT` values to point at the live controller, plus collapse the one-off ATT variant. Off-by-default = units installed-not-enabled + `.env` install-if-absent (deploy.sh currently doesn't deploy the `.env` files at all). See §Standard Stack, §Architecture Patterns. |
| WDOG-02 | Heartbeat-death → relay-bypass proven non-destructively (shim/test, no live arming); 2026-06-08 ATT migration failure mode documented as understood + covered | Failure mode fully reconstructed from git (`fc47a0c8`, `f3f47a92`) + `phase231-rollback.sh` + docs. Non-destructive proof = extend the existing stateful fake-bpctl harness with watchdog verbs + a simulated timer-expiry. See §Common Pitfalls, §Code Examples, §Validation Architecture. |
| WDOG-03 | Operator arms/disarms per pair via CLI (`arm <pair> [timeout]` / `disarm <pair>`); arming a LIVE pair requires explicit operator gate, never implicit | `arm`/`disarm` were pre-reserved in the seed CLI sketch and config (`WD_TIMEOUT_MS`, `HEARTBEAT_MS`). Extend the existing subcommand `case` dispatch. Gate model mirrors existing `--yes` / `--both-wan-confirm` pattern. See §Architecture Patterns, §Code Examples. |
| SAFE-16 | Controller-path zero-diff at phase boundary; single scoped exception (cake-shaper bypass FAILURE behavior) touches failure/units only, NOT `src/wanctl` | Turnkey boundary checker exists: `scripts/phase225-safe13-boundary-check.sh --anchor v1.51`. Reconciliation surface is units/scripts/CLI/docs/tests only; the SAFE-16 exception is the watchdog/relay failure path, which is not in the protected file list. See §Don't Hand-Roll, §Security Domain. |

## Standard Stack

### Core (all in-repo, no installs)
| Artifact | Path | Purpose | Reconciliation in 236 |
|----------|------|---------|------------------------|
| Generic watchdog template | `deploy/systemd/silicom-bypass-watchdog@.service` `[VERIFIED: file read]` | Per-pair watchdog instance | **Stale** — `After=...wanctl@%i.service`, `Wants=wanctl@%i.service`. Decouple from `wanctl@`; make watched-unit name come from env, not the unit name |
| ATT one-off variant | `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` `[VERIFIED: file read]` | Bolted-on ATT cake-autorate watchdog | Created in `fc47a0c8`; sets `WANCTL_UNIT=cake-autorate-att.service` inline. Reconcile: fold into the generic template so one shape covers both pairs |
| Petter (reset loop) | `scripts/wanctl-bpctl-watchdog-petter` `[VERIFIED: file read]` | Arms HW watchdog, pets while watched unit active, bypasses when inactive | **Already parameterized by `WANCTL_UNIT`** — minimal/no change needed; it is unit-name-agnostic by design |
| Bypass (ExecStop) | `scripts/wanctl-bpctl-watchdog-bypass` `[VERIFIED: file read]` | On stop: force expiry-mode bypass | Unit-agnostic; no change needed |
| Operator CLI | `scripts/silicom-bypass` `[VERIFIED: file read]` | status/on/off/disc/conn/mark/baseline | **Extend**: add `arm <pair> [timeout]` / `disarm <pair>` subcommands |
| CLI config | `deploy/scripts/silicom-bypass.conf.example` `[VERIFIED: file read]` | `PAIRS`, `WD_TIMEOUT_MS=10000`, `HEARTBEAT_MS=3000` (reserved) | WD keys already reserved in 235; this phase consumes them. May add per-pair watched-unit map |
| Per-pair env examples | `deploy/scripts/bpctl-watchdog-{att,spectrum}.env.example` `[VERIFIED: file read]` | `IFACE` + `WANCTL_UNIT` | **Spectrum is stale**: `WANCTL_UNIT=wanctl@spectrum.service` (disabled). Update both to live controller units |
| Offline test harness | `tests/test_silicom_bypass_cli.py` `[VERIFIED: 27 passed]` | Stateful fake-bpctl subprocess harness | **Extend**: add watchdog verbs to the fake + a timer-expiry simulation for the heartbeat-death proof |
| SAFE-16 boundary checker | `scripts/phase225-safe13-boundary-check.sh` `[VERIFIED: file read]` | Read-only controller-path diff proof | Run `--anchor v1.51` at phase gate; do NOT author a bespoke checker |

### Hardware watchdog verbs (bpctl_util) — the failure-behavior surface
From the petter and `docs/SILICOM-BYPASS.md` `[VERIFIED: file read]`:

| Verb | Meaning | Used by |
|------|---------|---------|
| `set_wd_exp_mode bypass` | On watchdog expiry, relay fires **bypass** (fail-to-wire) | petter arm, bypass ExecStop |
| `set_wd_autoreset 0` | Disable hardware auto-reset; software must pet | petter arm |
| `set_bypass_wd <ms>` | Arm/start the hardware watchdog timer (`0` = disarm) | petter arm; disarm = `set_bypass_wd 0` |
| `reset_bypass_wd` | Pet (reset) the timer — withholding this is what causes expiry | petter loop |
| `get_bypass_wd` / `get_wd_exp_mode` | Read-back verification | docs / arm verb |

**Hardware quirk** `[CITED: docs/SILICOM-BYPASS.md:289-292]`: requested `5000ms` rounds up to a **6400ms** hardware timeout (fixed timer steps). Arm verb should accept a timeout but document the rounding; do not promise exact ms.

**Settled constraint — DO NOT re-litigate** `[CITED: docs/SILICOM-BYPASS.md, REQUIREMENTS Out of Scope]`: this card cannot do **unpowered** fail-open (monostable relays, `AuxCurrent=0mA`). Watchdog covers controller/service death while the card stays powered. UPS + battery covers unpowered loss architecturally.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reconcile generic template + env `WANCTL_UNIT` | Keep two divergent units (generic + ATT variant) | Status quo is the bug — asymmetric, error-prone, Spectrum watches a dead unit name. Rejected. |
| Watched-unit name from `.env`/config | Hardcode `cake-autorate-{wan}.service` in the template | Breaks the portable/link-agnostic principle and re-introduces coupling (now to cake-autorate instead of wanctl@). Keep it env-driven so native-rollback mode still works. |
| Single generic `@.service` template | Per-pair concrete units | Template + per-pair `.env` is the established pattern; concrete units duplicate. Keep template. |

**Installation:** No packages. All artifacts repo-owned; deployment via the existing `deploy.sh --silicom-bypass-only <host>` path (extend its `SILICOM_BYPASS_SYSTEMD` array + add `.env` install-if-absent — currently deploy.sh does NOT ship the `.env` files at all).

## Package Legitimacy Audit

Not applicable — this phase installs **no external packages**. All artifacts are repo-owned bash/systemd/pytest. No npm/PyPI/crates surface. (slopcheck N/A.)

## Architecture Patterns

### System Architecture Diagram

```
                          OPERATOR (CLI, opt-in)
                                  │
          silicom-bypass arm <pair> [timeout]  /  disarm <pair>
                                  │  (live-pair gate: explicit, never implicit)
                                  ▼
                  systemctl enable/start  silicom-bypass-watchdog@<pair>
                                  │
                                  ▼
        ┌──────────────── wanctl-bpctl-watchdog-petter (Type=simple loop) ───────────────┐
        │  arm: set_wd_exp_mode bypass; set_wd_autoreset 0; set_bypass_wd <timeout_ms>    │
        │                                                                                  │
        │   every HEARTBEAT_SECONDS:                                                        │
        │     systemctl is-active $WANCTL_UNIT  ◄── RECONCILE: live controller unit name   │
        │        ├─ active   → reset_bypass_wd (pet)  + ensure inline                       │
        │        └─ inactive → set_bypass on  + WITHHOLD pet  ─────────┐                    │
        └─────────────────────────────────────────────────────────────┼────────────────────┘
                                                                       ▼
                                              HW watchdog timer expires (no pet)
                                                                       ▼
                                       Silicom relay fires BYPASS (fail-to-wire, raw ISP)
                                                                       ▲
                          ExecStop / disarm: wanctl-bpctl-watchdog-bypass OR set_bypass_wd 0

   $WANCTL_UNIT  ──►  cake-autorate-<wan>.service  (LIVE since 2026-06-08; was wanctl@<wan>)
```

The single load-bearing edge is `$WANCTL_UNIT`: it must name the **live** controller. The 2026-06-08 bug is that for Spectrum it still names `wanctl@spectrum.service` (disabled), so the petter reads inactive and bypasses a healthy link.

### Recommended Project Structure (no new dirs; edits to existing)
```
deploy/systemd/
├── silicom-bypass-watchdog@.service                       # RECONCILE: decouple from wanctl@%i
├── silicom-bypass-watchdog-cake-autorate-att.service      # FOLD INTO template (or retire)
deploy/scripts/
├── bpctl-watchdog-att.env.example                         # WANCTL_UNIT → cake-autorate-att.service
├── bpctl-watchdog-spectrum.env.example                    # WANCTL_UNIT → cake-autorate-spectrum.service (was stale)
├── silicom-bypass.conf.example                            # consume WD_TIMEOUT_MS/HEARTBEAT_MS
scripts/
├── silicom-bypass                                         # + arm/disarm subcommands
├── wanctl-bpctl-watchdog-petter                           # already WANCTL_UNIT-driven (likely no change)
├── deploy.sh                                              # + ship .env install-if-absent
tests/
├── test_silicom_bypass_cli.py                             # + watchdog verbs in fake + arm/disarm + expiry shim
docs/SILICOM-BYPASS.md                                     # + 2026-06-08 failure mode RCA + arm/disarm usage
```

### Pattern 1: Watched-unit decoupling (the core reconciliation)
**What:** Remove `wanctl@`-specific coupling from the generic template; drive the watched-unit name purely from env.
**When to use:** Both pairs, both deployment modes (external cake-autorate now; native wanctl@ on rollback).
**Example (target template `[Unit]` shape):**
```ini
[Unit]
Description=Silicom fail-open bypass watchdog for %i
Requires=bpctl-silicom.service
After=bpctl-silicom.service
# Watched unit is configured in /etc/wanctl/bpctl-watchdog/%i.env (WANCTL_UNIT=),
# NOT assumed to be wanctl@%i. Off by default; operator enables per pair.

[Service]
Type=simple
EnvironmentFile=/etc/wanctl/bpctl-watchdog/%i.env   # provides IFACE + WANCTL_UNIT
ExecStart=/usr/local/sbin/wanctl-bpctl-watchdog-petter
ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass
Restart=no
# No [Install] WantedBy until operator opts in — OR keep [Install] but ship disabled.
```
Note: drop `After=wanctl@%i.service` and `Wants=wanctl@%i.service`. The petter already reads `WANCTL_UNIT` from the env, so the template only needs ordering/Requires correctness.

### Pattern 2: arm/disarm CLI verbs (extend existing dispatch)
**What:** Add `arm <pair> [timeout]` and `disarm <pair>` to the `silicom-bypass` `case` dispatch in `main()`.
**When to use:** Operator-driven enablement. `arm` against a **live** pair requires an explicit gate (mirror `--yes` / `--both-wan-confirm`).
**Mechanics:** `arm` = `systemctl enable --now silicom-bypass-watchdog@<pair>` (or set `set_bypass_wd <ms>` + start the unit); `disarm` = `systemctl disable --now ...` + `set_bypass_wd 0`. Reuse `resolve_pair`, `pair_allowed`, `journal`. The live-pair gate: refuse to arm unless `--yes` (and document that arming live = the watchdog will bypass that pair if the controller dies — desired behavior, but must be intentional).

### Anti-Patterns to Avoid
- **Re-coupling to cake-autorate:** Don't replace `wanctl@%i` with a hardcoded `cake-autorate-%i` in the template — that just moves the coupling. Keep the watched-unit name in `.env`/config (portable principle, supports native rollback).
- **Two divergent watchdog units:** Don't leave the ATT one-off variant alongside the reconciled template. Fold to one shape (CLAUDE.md: "do not maintain two divergent files").
- **Arming in a test/executor step:** Never `set_bypass_wd <nonzero>` against the live card in any automated step. The shim proves expiry with a fake.
- **Default-on enablement:** Don't add `[Install] WantedBy=multi-user.target` and enable on install. Off-by-default is WDOG-01.
- **Touching `src/wanctl`:** SAFE-16. The failure-behavior exception is units/scripts only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Controller-path zero-diff proof | Bespoke git-diff checker | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out .../safe16-boundary-236.json` | Turnkey, already produces JSON evidence; 235 used it identically |
| Hardware watchdog timer | Software sleep/kill loop | bpctl `set_bypass_wd` + `reset_bypass_wd` (firmware timer) | Fail-open must survive Linux death; only the card's timer does that |
| Fake hardware for tests | New mock framework | Extend the existing stateful `_fake_bpctl` stub in `tests/test_silicom_bypass_cli.py` | Proven pattern (27 tests green); records `set_*`, reads back `get_*` |
| Subprocess test runner | New harness | Existing `_run()` / `subprocess.run(["bash", CLI, ...], env=...)` pattern | `BPCTL_UTIL` env seam keeps every test off the live card |
| Per-pair config | Hardcode interfaces | `/etc/silicom-bypass.conf` `PAIRS` + per-pair `.env` | Established 235 pattern; portable/link-agnostic |

**Key insight:** This phase is consolidation, not invention. The petter is already correctly abstracted (`WANCTL_UNIT`); the bug is in the **data** feeding it (unit names) and the **template** that hardcodes ordering. Fix the inputs, fold the divergent unit, extend the CLI dispatch, extend the fake. No new mechanism.

## Runtime State Inventory

> This is a reconciliation phase — runtime state matters more than file edits.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — watchdog state is hardware register state on the card, not persisted in any DB. `set_bypass_wd 0` disarms. | None |
| Live service config | **(1)** `/etc/wanctl/bpctl-watchdog/spectrum.env` on `cake-shaper` sets `WANCTL_UNIT=wanctl@spectrum.service` (disabled). **(2)** `/etc/wanctl/bpctl-watchdog/att.env` likewise stale for native mode; ATT currently covered by the one-off cake-autorate variant. **(3)** systemd enablement state of `silicom-bypass-watchdog@spectrum.service` and `silicom-bypass-watchdog-cake-autorate-att.service` on the live host — `phase231-rollback.sh` asserts spectrum watchdog "active in both modes". | Repo edit to `.env.example` + reconcile template; **live `.env` update + unit re-enable is operator-gated, not autonomous**. Verify live enablement state during planning (operator-run `systemctl is-active/is-enabled`). |
| OS-registered state | systemd unit files at `/etc/systemd/system/silicom-bypass-watchdog@.service` and `.../silicom-bypass-watchdog-cake-autorate-att.service`; per-pair instances enabled/disabled. `daemon-reload` needed after unit edits. | Operator-gated `systemctl daemon-reload` + re-enable per pair; never autonomous |
| Secrets/env vars | None — no secrets in watchdog path. `.env` files carry only `IFACE`/`WANCTL_UNIT`. | None |
| Build artifacts | None — bash/systemd, nothing compiled. bpctl module owned by `bpctl-silicom.service`, untouched here. | None |

**The canonical question answered:** After every repo file is updated, the live host still has stale `/etc/wanctl/bpctl-watchdog/*.env` files and possibly an armed Spectrum watchdog watching a dead unit name. Repo reconciliation does NOT fix the live host — an **operator-gated apply step** (update `.env`, daemon-reload, re-enable per pair) must be in the plan, separate from the code edit.

## Common Pitfalls

### Pitfall 1: The 2026-06-08 ATT migration failure mode (WDOG-02 — must document)
**What goes wrong:** The petter decides "is the controller alive?" via `systemctl is-active "$WANCTL_UNIT"`. When both WANs migrated from `wanctl@` to cake-autorate (`fc47a0c8`, live 2026-06-08, `wanctl@{spectrum,att}` disabled), the watched-unit name `wanctl@<wan>.service` went **permanently inactive**. An armed watchdog reading that name sees the controller as dead on a perfectly healthy system → `set_bypass on` + withhold pet → relay fires bypass (raw ISP, CAKE shaping gone) within the ~6400ms timeout.
**Why it happened:** The migration commit (`fc47a0c8`) created a **one-off** `silicom-bypass-watchdog-cake-autorate-att.service` that pets against `cake-autorate-att.service` for ATT, but **left Spectrum on the stale generic template** still pointing at `wanctl@spectrum.service`. The `phase231-rollback.sh` comments even encode the asymmetry: "silicom-bypass-watchdog@spectrum.service stays active in both modes" — but in external mode it watches a disabled unit, so if armed it would mis-fire. The reconciliation was never done; a divergent second unit was bolted on instead.
**How to avoid:** Make the watched-unit name a configured value that names the **live** controller in the active mode, identical shape for both pairs. Add a test that proves: watched-unit-inactive → bypass; watched-unit-active → pet/inline.
**Warning signs:** A `silicom-bypass-watchdog@spectrum` unit enabled while `WANCTL_UNIT=wanctl@spectrum.service` and `wanctl@spectrum` is disabled — that pair is one arm away from a spurious bypass.

### Pitfall 2: Accidentally arming a live relay during reconciliation
**What goes wrong:** A plan/executor step runs `set_bypass_wd <nonzero>` or `systemctl start silicom-bypass-watchdog@<live-pair>` on the live host, withholds pet, and drops the WAN into raw-ISP bypass mid-day.
**Why it happens:** Treating "reconcile the unit" as "enable the unit." WDOG-01 says off-by-default; WDOG-03 says live arming is explicit operator action only.
**How to avoid:** All proof is offline via the fake-bpctl shim. Any live `systemctl enable/start` or `set_bypass_wd` against `cake-shaper` is an operator-gated checkpoint, never autonomous. The CLI `arm` verb refuses without an explicit `--yes` gate.
**Warning signs:** Any test or plan action that sets `BPCTL_UTIL` to the real `/opt/bpctl-silicom/bpctl_util`, or any `ssh cake-shaper ... set_bypass_wd`.

### Pitfall 3: `set_dis_bypass`/read-back string inversion (carried from 235)
**What goes wrong:** bpctl read-back wording is counterintuitive and has live-wording variants (`Bypass mode enabled` vs `Bypass mode is enabled`).
**How to avoid:** Reuse the centralized `matches_want()` / `is_bypass_on_text()` matchers already in `silicom-bypass`; match `non-` forms first. The watchdog verbs (`get_bypass_wd`, `get_wd_exp_mode`) add their own strings — capture live wording in the matcher, don't fight it (235 Decision [235-03]).

### Pitfall 4: Off-by-default not actually achieved
**What goes wrong:** Shipping `[Install] WantedBy=multi-user.target` on the watchdog template makes `systemctl enable` pull it in, defeating opt-in; or deploy.sh auto-enables.
**Why it happens:** Copying the boot-baseline unit shape (`silicom-bypass-init.service` IS WantedBy by design) onto the watchdog.
**How to avoid:** Watchdog units install but are NOT enabled on deploy. `deploy.sh` currently does NOT ship the watchdog `.env` files at all — keep install-if-absent and do not enable. Operator opt-in = `silicom-bypass arm <pair>` or explicit `systemctl enable`.

## Code Examples

### Watchdog shim for the fake-bpctl (non-destructive heartbeat-death proof)
Extend the existing `_fake_bpctl` stub (`tests/test_silicom_bypass_cli.py:67`) with watchdog verbs and a simulated timer. The fake records arm/pet, and a test drives "no pet → expiry → bypass" purely in the fake's state files:
```bash
# add to the case "$verb" block of the fake bpctl_util stub:
set_wd_exp_mode)   write_state wd_exp_mode "$value" ;;
set_wd_autoreset)  write_state wd_autoreset "$value" ;;
set_bypass_wd)     write_state wd_armed_ms "$value"
                   [[ "$value" == "0" ]] && write_state wd_armed off || write_state wd_armed on ;;
reset_bypass_wd)   write_state wd_last_pet "$(date +%s%3N)" ;;   # records a pet
get_bypass_wd)     printf '%s\n' "$(read_state wd_armed_ms 0)" ;;
get_wd_exp_mode)   printf '%s\n' "$(read_state wd_exp_mode unknown)" ;;
```
The **expiry proof** is a pure-logic test of the petter loop body, not a wall-clock wait: assert that when `systemctl is-active $WANCTL_UNIT` returns non-zero (fake `systemctl`), the petter calls `set_bypass on` and does NOT call `reset_bypass_wd`. Inject a fake `systemctl` the same way the harness injects fake `bpctl_util`/`logger` (env-path override). No real timer, no sleep, no live card.

### arm/disarm dispatch (extend `silicom-bypass` main case)
```bash
# Source: scripts/silicom-bypass main() case block (extend)
arm)     cmd_arm "$@" ;;       # cmd_arm <pair> [timeout_ms] [--yes]
disarm)  cmd_disarm "$@" ;;    # cmd_disarm <pair>
```
`cmd_arm` resolves the pair (reuse `resolve_pair`), reads `WD_TIMEOUT_MS` default from config, requires the explicit live gate before enabling/starting the per-pair watchdog unit, and journals via `journal`. `cmd_disarm` stops/disables the unit and `set_bypass_wd 0`. Mirror the idempotency + exit-code grammar (0 ok/no-op, 1 runtime, 2 usage) already in the CLI.

### SAFE-16 boundary proof at phase gate
```bash
# Source: scripts/phase225-safe13-boundary-check.sh (235-03-SUMMARY usage)
.venv/bin/python scripts/phase225-safe13-boundary-check.sh \
  --anchor v1.51 \
  --out .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/safe16-boundary-236.json
# expect passed=true, controller_path_diff_count=0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Watchdog pets against `wanctl@<wan>.service` | Watchdog pets against the live external controller (cake-autorate) | 2026-06-08 migration | Generic template + spectrum.env stale; ATT got a one-off variant. 236 reconciles. |
| One watchdog unit shape | Two divergent units (generic template + ATT variant) | 2026-06-08 (`fc47a0c8`) | Asymmetric/fragile; 236 folds back to one configurable shape |
| `wanctl@` is the controller | cake-autorate is the live controller; `wanctl@` is rollback path | 2026-06-08 | Watched-unit name must be mode-aware via `.env`, not assumed |

**Deprecated/outdated:**
- Hardcoded `After=/Wants=wanctl@%i.service` in `silicom-bypass-watchdog@.service` — stale coupling.
- `/etc/wanctl/bpctl-watchdog/spectrum.env` `WANCTL_UNIT=wanctl@spectrum.service` — names a disabled unit.
- `silicom-bypass-watchdog-cake-autorate-att.service` as a separate file — should fold into the reconciled template.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The live `silicom-bypass-watchdog@spectrum.service` is currently **enabled/active** on `cake-shaper` (per `phase231-rollback.sh` comments), watching the disabled `wanctl@spectrum.service`. Not confirmed against live host this session. | Runtime State Inventory, Pitfall 1 | If it's actually disabled, the mis-fire risk is latent not active — but reconciliation is still required. Operator should confirm live `systemctl is-enabled/is-active` during planning. |
| A2 | The petter requires **no logic change** — only `WANCTL_UNIT` value + template ordering change — because it is already env-driven. | Standard Stack, Pattern 1 | If the plan wants per-pair multi-unit watching or a different liveness signal, the petter needs edits. Low risk; current petter is sufficient. |
| A3 | The reconciled watched-unit value should be `cake-autorate-<wan>.service` (live mode). Native-rollback mode would set it back to `wanctl@<wan>.service`. | Pattern 1, env examples | If a future plan wants the watchdog to track the **state-bridge** instead of cake-autorate itself, the value differs. Discuss-phase should confirm which unit is the authoritative liveness signal. |
| A4 | "Off by default + per-pair opt-in" = units installed-not-enabled + `.env` install-if-absent + `arm`/`disarm` (or `systemctl enable`) as the opt-in. | WDOG-01, Pitfall 4 | If operator wants a different opt-in mechanism (e.g., a config flag gating the petter), adjust. Low risk; matches 235 install-if-absent pattern. |
| A5 | `arm <pair>` semantics = enable+start the per-pair watchdog unit (which arms the HW timer via the petter), not a direct `set_bypass_wd` from the CLI. | Pattern 2 | If operator prefers the CLI to arm the HW timer directly without going through the unit, the verb is simpler but loses the systemd-managed pet loop. Discuss-phase decision. |

## Open Questions

1. **Which unit is the authoritative liveness signal for cake-autorate mode — `cake-autorate-<wan>.service` or `cake-autorate-<wan>-state-bridge.service`?**
   - What we know: cake-autorate does the shaping; the state-bridge tails its log and serves health. The migration commit says the watchdog "pets against cake-autorate-att".
   - What's unclear: whether watching the bridge (which proves the whole pipeline including health) is a better liveness proxy than watching cake-autorate alone.
   - Recommendation: default to `cake-autorate-<wan>.service` (matches the existing ATT variant); flag for discuss-phase.

2. **Fold the ATT variant vs. retire it?**
   - What we know: CLAUDE.md forbids two divergent files; the variant duplicates the generic template with inline env.
   - What's unclear: whether to delete `silicom-bypass-watchdog-cake-autorate-att.service` (and update `deploy.sh ATT_CAKE_AUTORATE_SYSTEMD` + `phase231-rollback.sh` references) or keep it as a thin alias.
   - Recommendation: retire it; route ATT through `silicom-bypass-watchdog@att-modem` (or `@att`) with `att.env` pointing at cake-autorate-att. Update the two referencing scripts. Confirm at plan time — this touches `phase231-rollback.sh` which has live-rollback semantics (handle conservatively).

3. **Pair identity token: `att`/`spectrum` vs `att-modem`/`spec-modem`?**
   - What we know: the CLI `PAIRS="att-modem spec-modem"` (interface names); the watchdog template instance is `%i` and env path is `/etc/wanctl/bpctl-watchdog/%i.env` with `%i ∈ {att, spectrum}` historically.
   - What's unclear: whether `arm <pair>` takes `att` or `att-modem`. The CLI already uses `att-modem`/`spec-modem`; the watchdog units use `att`/`spectrum`.
   - Recommendation: have `arm`/`disarm` accept the CLI's existing pair token (`att-modem`/`spec-modem`) and map to the watchdog instance name internally, OR normalize the instance naming. Resolve at plan time to avoid a confusing dual vocabulary.

## Environment Availability

> All artifacts are repo-owned; the only external dependency is the live `cake-shaper` host + Silicom card, which is OUT of the automated path (operator-gated only).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| bash | CLI + petter + fake | ✓ | system | — |
| pytest (.venv) | offline test harness | ✓ | repo `.venv` (pytest 9.0.2 observed) | — |
| `scripts/phase225-safe13-boundary-check.sh` | SAFE-16 gate | ✓ | in-repo | — |
| Live `cake-shaper` + bpctl_util | live apply / arm (operator-gated only) | N/A in CI | — | **All proof is offline via fake; live steps are operator checkpoints, never autonomous** |

**Missing dependencies with no fallback:** None — the phase is fully provable offline.
**Missing dependencies with fallback:** Live card access is intentionally excluded from the automated path; the fake-bpctl shim is the standing fallback for all proof.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo `.venv`, pytest 9.0.2) |
| Config file | `pyproject.toml` (repo standard) |
| Quick run command | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WDOG-01 | Reconciled template has no `wanctl@%i` coupling; `.env` examples name live controller; off-by-default (no auto-enable) | static artifact assert | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k watchdog_unit -q` | ❌ Wave 0 (add to existing file) |
| WDOG-01 | ATT variant folded / deploy.sh + rollback refs updated | static artifact assert | same file, `-k deploy_watchdog` | ❌ Wave 0 |
| WDOG-02 | Heartbeat-death (watched unit inactive) → `set_bypass on` + no `reset_bypass_wd`; watched-unit active → pet + inline | behavior (fake bpctl + fake systemctl) | same file, `-k petter_expiry` | ❌ Wave 0 |
| WDOG-03 | `arm <pair> [timeout]` requires live gate; `disarm <pair>` is idempotent; non-pair refused | behavior (subprocess + fake) | same file, `-k arm` / `-k disarm` | ❌ Wave 0 |
| SAFE-16 | controller-path zero-diff at boundary | git boundary check (read-only) | `python scripts/phase225-safe13-boundary-check.sh --anchor v1.51` | ✅ exists |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -q` plus the hot-path regression slice (CLAUDE.md) — unchanged since this phase doesn't touch the control path.
- **Phase gate:** Full suite green + SAFE-16 boundary `passed=true` before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] Watchdog verbs (`set_wd_exp_mode`, `set_wd_autoreset`, `set_bypass_wd`, `reset_bypass_wd`, `get_bypass_wd`, `get_wd_exp_mode`) added to the `_fake_bpctl` stub in `tests/test_silicom_bypass_cli.py`.
- [ ] A fake `systemctl` injector (env-path override, like the fake `logger`) so the petter's `is-active` branch is testable offline.
- [ ] Static asserts: reconciled `silicom-bypass-watchdog@.service` contains NO `wanctl@%i`; `.env.example` files name the live controller unit; no `[Install]`-driven auto-enable.
- [ ] Behavior tests: petter-body expiry proof; `arm`/`disarm` verbs + live gate.
- *(Existing harness fully covers the subprocess+env+fake pattern; gaps are additive, not new infrastructure.)*

## Security Domain

> `security_enforcement` not explicitly false in config — included. Surface is local root-only systemd/bash on a single trusted host; no network/auth surface added.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface; local root systemd |
| V3 Session Management | no | None |
| V4 Access Control | yes | Units installed root:root 0644; CLI/scripts 0755 root-owned (235 deploy pattern); `/dev/bpctl0` is 0600 root |
| V5 Input Validation | yes | CLI pair args validated against `PAIRS` allowlist (`pair_allowed`/`resolve_pair`), no `eval`, all expansions quoted (reuse 235 patterns); `arm` timeout must be integer-validated |
| V6 Cryptography | no | None |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Spurious live bypass (controller mis-detected dead) | Denial of Service (drops CAKE shaping) | Watched-unit name names the **live** controller (the WDOG-02 fix); off-by-default; explicit arm gate |
| Executor/test arms a live relay | Denial of Service | All proof offline via fake; live arm is operator-gated checkpoint only; `BPCTL_UTIL` seam |
| Controller-path tampering smuggled in | Tampering | SAFE-16 boundary check at phase gate (read-only git diff over protected list) |
| Unquoted/injected pair or timeout arg | Tampering / RCE | Allowlist validation, quoted expansions, integer check on timeout, no `eval` (235 precedent) |

## Recommended Planning Approach

**Two plans, two waves (serial — Plan 02 proves what Plan 01 builds):**

- **Plan 01 — Unit + CLI reconciliation (WDOG-01, WDOG-03):**
  - Reconcile `silicom-bypass-watchdog@.service` (drop `wanctl@%i` coupling).
  - Update `bpctl-watchdog-{att,spectrum}.env.example` to name the live controller; fold/retire the ATT variant (update `deploy.sh ATT_CAKE_AUTORATE_SYSTEMD` + `phase231-rollback.sh` references conservatively).
  - Extend `deploy.sh` to ship watchdog `.env` install-if-absent, units installed-not-enabled (off by default).
  - Add `arm <pair> [timeout]` / `disarm <pair>` to `silicom-bypass` with the live gate.
  - Extend the fake-bpctl with watchdog verbs + add a fake `systemctl`; static + behavior tests for the above.

- **Plan 02 — Non-destructive proof + RCA doc + boundary (WDOG-02, SAFE-16):**
  - Petter-body heartbeat-death → relay-bypass shim proof (watched-unit-inactive → `set_bypass on` + no pet; active → pet + inline).
  - Document the 2026-06-08 ATT migration failure mode in `docs/SILICOM-BYPASS.md` as understood and covered by the reconciled units.
  - Run `phase225-safe13-boundary-check.sh --anchor v1.51` → `evidence/safe16-boundary-236.json`, `passed=true`.

**Dependency structure:** 235 (done) → 236 Plan 01 → 236 Plan 02. Within Plan 01, unit edits and CLI edits are independent and can be tasks in one wave; tests gate the wave.

**Operator-gated (non-autonomous) steps to mark explicitly in the plan:** any live `.env` update on `cake-shaper`, any `systemctl daemon-reload`/`enable`/`start` of a watchdog unit on the live host, and any `silicom-bypass arm <live-pair>`. None of these may be executor-run; all are checkpoints with rollback = `disarm` + restore inline.

**Risk flags for the planner:**
- `phase231-rollback.sh` references the watchdog units and has live-rollback semantics — edits there are conservative-change territory (CLAUDE.md: network/prod, suggest-don't-implement; the rollback path is double-gated). Coordinate the unit-name change with its expectations.
- Confirm live enablement state (A1) before assuming the Spectrum watchdog is or isn't currently armed against the dead unit.
- Do NOT introduce a hardcoded cake-autorate coupling — keep the watched-unit name configurable to preserve native-rollback mode and the portable/link-agnostic principle.

## Sources

### Primary (HIGH confidence — verified this session)
- `deploy/systemd/silicom-bypass-watchdog@.service`, `silicom-bypass-watchdog-cake-autorate-att.service`, `silicom-bypass-init.service`, `bpctl-silicom.service` — read in full.
- `scripts/wanctl-bpctl-watchdog-petter`, `wanctl-bpctl-watchdog-bypass`, `wanctl-bpctl-init`, `silicom-bypass`, `deploy.sh`, `phase231-rollback.sh` — read.
- `deploy/scripts/bpctl-watchdog-{att,spectrum}.env.example`, `silicom-bypass.conf.example` — read.
- `tests/test_silicom_bypass_cli.py` — read structure; `27 passed in 0.66s` confirmed.
- `docs/SILICOM-BYPASS.md` lines 250-360 (watchdog semantics, hardware quirk, validation) — read.
- git: `fc47a0c8` (migration commit message + stat), `f3f47a92` (watchdog services add) — confirm the one-off ATT variant origin and the wanctl@→cake-autorate switch.
- `.planning/REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `235-CONTEXT.md`, `235-PATTERNS.md`, `235-0{1..4}-SUMMARY.md` — read for contract + decisions.

### Secondary (MEDIUM)
- `scripts/phase225-safe13-boundary-check.sh` (protected file list, usage) — read; SAFE-16 mechanism confirmed.

### Tertiary (LOW)
- None. Graph query for "silicom bypass watchdog" returned 0 nodes (graph predates the silicom work); raw file reads used instead.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every artifact read directly; no external deps.
- Architecture / reconciliation surface: HIGH — petter's `WANCTL_UNIT` parameterization and the stale template coupling are directly observable in the files.
- Failure mode (WDOG-02): HIGH — reconstructed from the migration commit message ("silicom watchdog variant pets against cake-autorate-att"), the petter's `is-active` logic, the stale spectrum.env, and `phase231-rollback.sh` asymmetry comments. The one unverified point (live enablement state) is logged as A1.
- Pitfalls / test approach: HIGH — the existing 27-test harness gives a proven shim pattern.

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (stable; in-repo only). Re-verify A1 (live watchdog enablement state) at plan time since it reflects live-host state, not repo state.
