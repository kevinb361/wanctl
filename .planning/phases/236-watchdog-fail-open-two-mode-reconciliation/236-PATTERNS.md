# Phase 236: Watchdog Fail-Open Two-Mode Reconciliation - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 9 (4 edit / 1 retire / 4 extend)
**Analogs found:** 9 / 9 (all in-repo; this phase is consolidation, not invention)

## Orientation

Every artifact in this phase already exists in-repo with a strong local analog. The
"analog" for most files is **a sibling that already does the thing correctly** (the ATT
variant already pets cake-autorate; the petter is already `WANCTL_UNIT`-driven; the CLI
already has a `case` dispatch + `--yes` gate; the deploy.sh already has install-if-absent
for `.conf`). The work is to **reconcile the data and fold the divergence**, copying the
correct sibling's shape onto the stale one. No new mechanism, no `src/wanctl` touch (SAFE-16).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `deploy/systemd/silicom-bypass-watchdog@.service` | systemd template (config) | event-driven (unit liveness) | `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` (the correct sibling) | exact — same shape, fold the `wanctl@%i` coupling out |
| `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` | systemd unit (config) | event-driven | folds INTO the reconciled `@.service` template | retire/fold |
| `deploy/scripts/bpctl-watchdog-att.env.example` | env/config | data (key=value) | `bpctl-watchdog-spectrum.env.example` (identical shape) | exact |
| `deploy/scripts/bpctl-watchdog-spectrum.env.example` | env/config | data (key=value) | the live ATT variant's inline `WANCTL_UNIT=cake-autorate-att.service` | exact |
| `scripts/silicom-bypass` | operator CLI (bash) | request-response (verb dispatch) | own `cmd_on`/`cmd_disc` (case-dispatch + `--yes` gate, lines 285-321, 340-355) | exact — add `arm`/`disarm` verbs |
| `scripts/wanctl-bpctl-watchdog-petter` | host daemon (bash) | event-driven loop | itself — already `WANCTL_UNIT`-parameterized (lines 5, 28) | no change / value-only |
| `scripts/deploy.sh` | deploy orchestrator (bash) | batch / file-I/O | own `deploy_silicom_bypass()` `.conf` install-if-absent (lines 555-557) | exact — copy for `.env` |
| `scripts/phase231-rollback.sh` | rollback procedure (bash) | batch | own existing watchdog `run_check` block (lines 231-237) | role-match — conservative refs update |
| `tests/test_silicom_bypass_cli.py` | test harness (pytest) | transform (subprocess + fake) | `_fake_bpctl` stub (lines 67-179) + `_run` injector (lines 198-221) + artifact asserts (lines 473-548) | exact — extend |
| `docs/SILICOM-BYPASS.md` | docs (markdown) | — | own `## Per-WAN Watchdog Fail-Open` (line 250) + `### ...Pitfalls` (line 435) | role-match — add RCA |

## Pattern Assignments

### `deploy/systemd/silicom-bypass-watchdog@.service` (systemd template, event-driven)

**Analog:** `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` — the bolted-on
variant is the *correct* shape (watches a non-`wanctl@` unit). The reconciliation copies its
decoupled `[Unit]`/`[Service]` posture onto the generic template while keeping `%i`/`EnvironmentFile`.

**Current (stale) template** (`silicom-bypass-watchdog@.service:1-19`) — the defect lives here:
```ini
[Unit]
Description=Silicom fail-open bypass watchdog for %i
Requires=bpctl-silicom.service
After=bpctl-silicom.service wanctl@%i.service      # <-- stale coupling
Wants=wanctl@%i.service                            # <-- stale coupling

[Service]
Type=simple
Environment=BPCTL_UTIL=/opt/bpctl-silicom/bpctl_util
Environment=TIMEOUT_MS=5000
Environment=HEARTBEAT_SECONDS=1
EnvironmentFile=/etc/wanctl/bpctl-watchdog/%i.env  # provides IFACE + WANCTL_UNIT
ExecStart=/usr/local/sbin/wanctl-bpctl-watchdog-petter
ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass
TimeoutStopSec=10
Restart=no

[Install]
WantedBy=multi-user.target                         # <-- review vs off-by-default (Pitfall 4)
```

**Target shape to copy** — drop both `wanctl@%i` lines; watched unit comes only from
`%i.env` (`WANCTL_UNIT=`). Note: the petter already requires `WANCTL_UNIT` (`petter:5`), so the
template must NOT also self-provide it; keep it env-only. Research §Pattern 1 target `[Unit]`:
```ini
[Unit]
Description=Silicom fail-open bypass watchdog for %i
Requires=bpctl-silicom.service
After=bpctl-silicom.service
# Watched unit configured in /etc/wanctl/bpctl-watchdog/%i.env (WANCTL_UNIT=),
# NOT assumed to be wanctl@%i. Off by default; operator enables per pair.
```

**Off-by-default decision (Pitfall 4 / WDOG-01):** The current template ships
`[Install] WantedBy=multi-user.target`. The compliant sibling for "installed-not-enabled"
posture is `silicom-bypass-init.service`, whose artifact test asserts "must be enabled"
language (`test_silicom_bypass_cli.py:482`). Plan must decide: keep `[Install]` but never
`systemctl enable` on deploy (deploy.sh already does not enable, line 580 "units not enabled
or started"), vs. drop `[Install]`. Research recommends installed-not-enabled (keep `[Install]`,
do not enable). Add a static test asserting no auto-enable.

---

### `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` (retire/fold)

**Analog:** the reconciled `@.service` template above absorbs it.

**Current inline env it carries** (`...cake-autorate-att.service:12-13`) — this is the value
that must migrate into `bpctl-watchdog-att.env.example`:
```ini
Environment=IFACE=att-modem
Environment=WANCTL_UNIT=cake-autorate-att.service
```

**Reference sites that name this unit (must update on retire — conservative):**
- `scripts/deploy.sh:71` — `ATT_CAKE_AUTORATE_SYSTEMD` array entry
- `scripts/phase231-rollback.sh:73,101,122,233` — enable/disable cmds + `run_check` assertions
- `docs/SILICOM-BYPASS.md` — references in watchdog/rollback sections

**Open Question (research #2/#3):** fold ATT through `silicom-bypass-watchdog@att` instance
(env-driven) vs. keep a thin alias. Pair-token vocabulary (`att` vs `att-modem`) must be
resolved at plan time — the watchdog instance historically uses `att`/`spectrum` while the
CLI `PAIRS` uses `att-modem`/`spec-modem`.

---

### `deploy/scripts/bpctl-watchdog-{att,spectrum}.env.example` (env/config, data)

**Analog:** each other + the ATT variant's inline env (above). Both files are 2-line `KEY=value`.

**ATT current** (`bpctl-watchdog-att.env.example:1-2`):
```sh
IFACE=att-modem
WANCTL_UNIT=wanctl@att.service          # -> cake-autorate-att.service (live since 2026-06-08)
```

**Spectrum current — the WDOG-02 latent bug** (`bpctl-watchdog-spectrum.env.example:1-2`):
```sh
IFACE=spec-modem
WANCTL_UNIT=wanctl@spectrum.service     # names a DISABLED unit -> petter reads inactive -> spurious bypass
```

**Target:** point `WANCTL_UNIT` at the live controller (`cake-autorate-<wan>.service`). Keep
it env-driven so native-rollback mode can set it back (do NOT hardcode cake-autorate in the
template — research Anti-Pattern).

---

### `scripts/silicom-bypass` (operator CLI, request-response)

**Analog:** its own `cmd_on` / `cmd_disc` (the gated, idempotent, read-back verbs).

**Dispatch pattern to extend** (`silicom-bypass:340-355`) — add two `case` arms:
```bash
case "$cmd" in
    status) cmd_status "$@" ;;
    off) cmd_off "$@" ;;
    ...
    baseline) cmd_baseline "$@" ;;
    arm)     cmd_arm "$@" ;;       # ADD: cmd_arm <pair> [timeout_ms] --yes
    disarm)  cmd_disarm "$@" ;;    # ADD: cmd_disarm <pair>
    --help|-h) usage ;;
    *) die "unknown subcommand: $cmd" 2 ;;
esac
```

**Gate + idempotency + journal pattern to mirror** (`silicom-bypass:285-302`, `cmd_on`):
```bash
cmd_on() {
    [[ $# -ge 1 ]] || die "on requires a pair" 2
    local requested="$1" pair cur got
    shift
    parse_flags "$@"
    require_yes "$YES" "on"                 # <-- the explicit operator gate (reuse for arm-live)
    pair="$(resolve_pair "$requested")"     # <-- allowlist validation (reuse)
    cur="$(util "$pair" get_bypass)"
    if is_bypass_on_text "$cur"; then
        printf '%s already bypass; no-op\n' "$pair"   # <-- idempotent no-op grammar (reuse)
        return 0
    fi
    check_both_wan_gate "$pair" "$BOTH_WAN_CONFIRM"
    util "$pair" set_bypass on
    got="$(util "$pair" get_bypass)"
    assert_positive_bypass "$got" "$pair set_bypass on"
    journal "on $pair: set_bypass on OK"    # <-- journal verb (reuse)
}
```

**Helpers to reuse (do not re-implement):** `resolve_pair` (56-64), `pair_allowed` (48-54),
`require_yes` (210-213), `parse_flags` (226-237), `journal` (34-36), `die` with exit codes
(28-32). Config keys already reserved: `WD_TIMEOUT_MS`, `HEARTBEAT_MS` in
`silicom-bypass.conf.example:7-8` — `cmd_arm` reads `WD_TIMEOUT_MS` as the default timeout.

**arm/disarm mechanics** (research §Pattern 2): `arm` = `systemctl enable --now
silicom-bypass-watchdog@<pair>` (the unit/petter arms the HW timer — do NOT `set_bypass_wd`
direct from CLI per A5); arming a live pair requires `--yes`. `disarm` = `systemctl disable
--now ...` + petter's `set_bypass_wd 0` disarm path. **Timeout arg must be integer-validated**
(V5 input validation; no `eval`, quote all expansions). Exit-code grammar: 0 ok/no-op, 1
runtime, 2 usage (line 24).

---

### `scripts/wanctl-bpctl-watchdog-petter` (host daemon, event-driven loop)

**Analog:** itself. **Likely zero code change** (A2) — already `WANCTL_UNIT`-driven.

**The single load-bearing edge** (`petter:5`, `27-44`):
```sh
: "${WANCTL_UNIT:?missing WANCTL_UNIT}"      # required from env; the reconciliation surface
...
while :; do
  if /bin/systemctl is-active --quiet "$WANCTL_UNIT"; then    # <-- WDOG-02 decision point
    ...
    util reset_bypass_wd >/dev/null          # pet
    last_state=active
  else
    if [ "$last_state" != inactive ]; then
      util set_bypass on                     # <-- spurious bypass if WANCTL_UNIT names a dead unit
    fi
    last_state=inactive                      # withholds pet -> HW timer expires
  fi
  sleep "$HEARTBEAT_SECONDS"
done
```

This loop body IS the WDOG-02 test target — extract it for the offline expiry proof (assert:
`is-active` non-zero → `set_bypass on` + no `reset_bypass_wd`; `is-active` zero → `reset_bypass_wd`
+ inline restore). Arm verbs the petter uses (`petter:18-22`): `set_wd_exp_mode bypass`,
`set_wd_autoreset 0`, `set_bypass_wd <ms>`, `reset_bypass_wd`.

---

### `scripts/deploy.sh` (deploy orchestrator, batch/file-I/O)

**Analog:** its own `.conf` install-if-absent inside `deploy_silicom_bypass()`.

**install-if-absent pattern to copy for each watchdog `.env`** (`deploy.sh:555-557`):
```bash
scp "$PROJECT_ROOT/deploy/scripts/silicom-bypass.conf.example" "$TARGET_HOST:$remote_tmp/silicom-bypass.conf.example"
ssh "$TARGET_HOST" "if sudo test -e /etc/silicom-bypass.conf; then :; else sudo install -o root -g root -m 0644 '$remote_tmp/silicom-bypass.conf.example' /etc/silicom-bypass.conf; fi"
echo "  -> /etc/silicom-bypass.conf (install-if-absent)"
```
Apply to `bpctl-watchdog-{att,spectrum}.env.example` → `/etc/wanctl/bpctl-watchdog/{att,spectrum}.env`
(deploy.sh currently ships NEITHER `.env` file — research §Standard Stack). Must `mkdir -p
/etc/wanctl/bpctl-watchdog` first.

**systemd unit install loop to add the watchdog template to** (`deploy.sh:559-570`, array at
`74-77`): add `deploy/systemd/silicom-bypass-watchdog@.service` to `SILICOM_BYPASS_SYSTEMD`.
The loop already installs `0644 root:root` + `daemon-reload` (line 576) + **does not enable**
(line 580 message — preserve off-by-default).

**Conservative:** keep the no-enable posture; do not add `[Install]`-driven auto-enable
(Pitfall 4).

---

### `scripts/phase231-rollback.sh` (rollback procedure, batch) — CONSERVATIVE

**Analog:** its own watchdog `run_check` assertion block.

**Existing assertion grammar to update** (`phase231-rollback.sh:231-237`):
```bash
run_check "$checks_file" "spectrum_watchdog_active" "systemctl is-active silicom-bypass-watchdog@spectrum.service" "stdout exactly active" stdout-active "$tmpdir"
run_check "$checks_file" "att_cake_watchdog_active" "systemctl is-active silicom-bypass-watchdog-cake-autorate-att.service" "stdout exactly active" stdout-active "$tmpdir"
run_check "$checks_file" "att_native_watchdog_inactive" "systemctl is-active silicom-bypass-watchdog@att.service" "stdout exactly inactive" stdout-inactive "$tmpdir"
run_check "$checks_file" "att_watchdog_template" "systemctl cat silicom-bypass-watchdog@.service" "native watchdog template exists" rc0 "$tmpdir"
run_check "$checks_file" "att_watchdog_env_present" "sudo -n test -f /etc/wanctl/bpctl-watchdog/att.env" "native watchdog EnvironmentFile present" rc0 "$tmpdir"
```

**Encoded asymmetry to reconcile** (the comments are part of the bug — `phase231-rollback.sh:73,
100-101, 109, 120-122`): enable/disable lines reference
`silicom-bypass-watchdog-cake-autorate-att.service` and the comment
"silicom-bypass-watchdog@spectrum.service stays active in both modes". If the ATT variant is
retired (Open Question #2), these enable/disable cmds + `run_check` names must change to the
folded `@att` instance. **This file has live-rollback semantics — CLAUDE.md network/prod policy:
suggest, coordinate, minimal change.** Mark any edit here for explicit operator review.

---

### `tests/test_silicom_bypass_cli.py` (test harness, transform)

**Analog:** the existing stateful `_fake_bpctl` + `_run` + artifact-assert patterns. 27 tests
green; gaps are additive (research §Wave 0 Gaps).

**Fake bpctl `case "$verb"` block to extend** (`test_silicom_bypass_cli.py:107-173`) — add
watchdog verbs alongside `set_bypass`/`get_bypass`, using the same `read_state`/`write_state`
helpers (lines 92-105). Research §Code Examples shim:
```bash
set_wd_exp_mode)   write_state wd_exp_mode "$value" ;;
set_wd_autoreset)  write_state wd_autoreset "$value" ;;
set_bypass_wd)     write_state wd_armed_ms "$value"
                   [[ "$value" == "0" ]] && write_state wd_armed off || write_state wd_armed on ;;
reset_bypass_wd)   write_state wd_last_pet "$(date +%s%3N)" ;;
get_bypass_wd)     printf '%s\n' "$(read_state wd_armed_ms 0)" ;;
get_wd_exp_mode)   printf '%s\n' "$(read_state wd_exp_mode unknown)" ;;
```

**Fake-binary injection pattern to clone for `systemctl`** (`_fake_logger`,
`test_silicom_bypass_cli.py:50-64`) — a tmp script on `PATH` (the `_run` env sets
`PATH=f"{tmp_path}:..."`, lines 212, 205-214). Build a `_fake_systemctl` the same way so the
petter's `is-active` branch returns controllable rc offline. The petter calls
`/bin/systemctl` by absolute path (`petter:28`) — the expiry test should invoke the loop body
with `systemctl` resolved via a seam, OR test against a petter that the plan parameterizes;
flag this seam at plan time (the absolute path defeats `PATH` override).

**Static artifact-assert pattern to mirror** (`test_silicom_bypass_cli.py:473-487`,
`test_init_service_artifact`):
```python
def test_init_service_artifact() -> None:
    assert INIT_SERVICE.exists()
    text = INIT_SERVICE.read_text(encoding="utf-8")
    assert "Type=oneshot" in text
    assert "Requires=bpctl-silicom.service" in text
    ...
```
Add `test_watchdog_unit_*`: reconciled `@.service` contains NO `wanctl@%i`; `.env.example`
files name the live controller; no auto-enable. Mirror the deploy-array helpers
(`_silicom_systemd_array_entries`, lines 513-516) to assert the watchdog template is in
`SILICOM_BYPASS_SYSTEMD` and `.env` files ship install-if-absent.

**Subprocess `_run` pattern for arm/disarm behavior tests** (`test_silicom_bypass_cli.py:198-221`)
— same `bash CLI ... env=...` harness; add a fake `systemctl` to `extra_env`/`PATH`. Mirror
gate tests like `test_on_requires_yes` (256-269) for `arm` live-gate, and idempotent-no-op
tests like `test_disc_idempotent_noop` (288-296) for `disarm`.

---

### `docs/SILICOM-BYPASS.md` (docs) — RCA

**Analog:** existing `## Per-WAN Watchdog Fail-Open` (line 250) and `### Spectrum Migration
Validation And Pitfalls` (line 435) sections — same prose+codeblock structure.

**Hardware quirk already documented to cite** (`SILICOM-BYPASS.md:289-292`): requested 5000ms
rounds up to 6400ms hardware timeout (fixed timer steps). The `arm` verb doc must not promise
exact ms. **Settled constraint** (Out of Scope): no unpowered fail-open (monostable relay,
AuxCurrent=0mA) — do not re-litigate.

**Add:** 2026-06-08 ATT migration failure-mode RCA (WDOG-02) as understood + covered by the
reconciled units; `arm`/`disarm` usage; note the `RemainAfterExit`/manual-exercise doc-test
coupling exists (`test_silicom_bypass_cli.py:489-504`) so doc edits to procedure blocks must
stay test-consistent.

## Shared Patterns

### Operator gate (`--yes`, explicit-never-implicit)
**Source:** `scripts/silicom-bypass:210-213` (`require_yes`), `226-237` (`parse_flags`),
`215-224` (`check_both_wan_gate`).
**Apply to:** `cmd_arm` (arming a LIVE pair). Mirror `require_yes "$YES" "arm"`.
```bash
require_yes() {
    local yes="$1" verb="$2"
    [[ "$yes" == true ]] || die "$verb requires --yes"
}
```

### Pair allowlist validation (V5 input validation)
**Source:** `scripts/silicom-bypass:48-64` (`pair_allowed` / `resolve_pair`).
**Apply to:** `cmd_arm`/`cmd_disarm` pair arg. No `eval`, all expansions quoted. `arm` timeout
must add an integer check (new — research V5 / threat table).

### journal + exit-code grammar
**Source:** `scripts/silicom-bypass:34-36` (`journal`), `24` (exit codes 0/1/2), `28-32` (`die`).
**Apply to:** every new verb. 0 ok/no-op, 1 runtime/refusal, 2 usage.

### install-if-absent + installed-not-enabled (off-by-default)
**Source:** `scripts/deploy.sh:555-557` (`.conf` install-if-absent), `580` ("units not enabled
or started").
**Apply to:** watchdog `.env` files and the `@.service` template. Never `systemctl enable` on deploy.

### Offline fake-hardware seam (`BPCTL_UTIL` + `PATH` injection)
**Source:** `tests/test_silicom_bypass_cli.py:67-179` (`_fake_bpctl`), `50-64` (`_fake_logger`),
`198-221` (`_run` env). The `BPCTL_UTIL` env seam keeps every test off the live card.
**Apply to:** all watchdog verb + arm/disarm + expiry tests. Never set `BPCTL_UTIL` to the real
`/opt/bpctl-silicom/bpctl_util` (Pitfall 2 — never arm a live relay in any automated step).

### SAFE-16 controller-path zero-diff (turnkey, do not hand-roll)
**Source:** `scripts/phase225-safe13-boundary-check.sh` (235-03 usage).
**Apply to:** phase gate.
```bash
.venv/bin/python scripts/phase225-safe13-boundary-check.sh \
  --anchor v1.51 \
  --out .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/safe16-boundary-236.json
# expect passed=true, controller_path_diff_count=0
```

## No Analog Found

None. Every file has a strong in-repo analog (often the correct sibling of the stale file).
The only genuinely new code is additive — watchdog verbs in the fake, a fake `systemctl`
injector, and the `arm`/`disarm` verbs — all built by cloning existing patterns above.

## Metadata

**Analog search scope:** `deploy/systemd/`, `deploy/scripts/`, `scripts/`, `tests/`, `docs/`
**Files scanned (read in full or targeted):** `silicom-bypass-watchdog@.service`,
`silicom-bypass-watchdog-cake-autorate-att.service`, `wanctl-bpctl-watchdog-petter`,
`wanctl-bpctl-watchdog-bypass`, `silicom-bypass`, `bpctl-watchdog-{att,spectrum}.env.example`,
`silicom-bypass.conf.example`, `test_silicom_bypass_cli.py`, `deploy.sh` (targeted: 60-77,
540-581), `phase231-rollback.sh` (targeted: watchdog refs), `docs/SILICOM-BYPASS.md` (section map)
**Pattern extraction date:** 2026-06-12

**Live-state caveat (research A1):** Live enablement of `silicom-bypass-watchdog@spectrum.service`
on `cake-shaper` is unverified this session. Confirm `systemctl is-enabled/is-active` at plan
time. Live `.env` update + daemon-reload + re-enable are operator-gated checkpoints, never
executor-run.
