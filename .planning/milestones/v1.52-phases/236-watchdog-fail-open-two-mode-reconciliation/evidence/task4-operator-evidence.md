---
phase: 236-watchdog-fail-open-two-mode-reconciliation
plan: 02
task: 4
type: operator-evidence
recorded: 2026-06-12T21:40:03Z
host: cake-shaper
gate: human-verify
status: approved
---

# Task 4 Operator Evidence — ATT Variant Retirement + Live Env Gate

Operator checkpoint response: **approved**.

This records the live operator gate for the SENTINEL-FIRST + ExecStop-MASKED retirement of `silicom-bypass-watchdog-cake-autorate-att.service`, the HIGH-4 live env migration gate, the rollback diff review, and A1/HIGH-5 live-state verification.

## Initial Precondition Finding

The first precondition check failed because `cake-shaper` still had old deployed artifacts:

- `BYPASS_SENTINEL_BRANCH_COUNT=0`
- `CLI_DISARM_VERB_COUNT=0` due old CLI/PATH state
- Retired `silicom-bypass-watchdog-cake-autorate-att.service` was active/enabled
- Folded `silicom-bypass-watchdog@att.service` was inactive/disabled
- Active `/etc/wanctl/bpctl-watchdog/att.env` was stale: `WANCTL_UNIT=wanctl@att.service`

## Conservative Prerequisite Applied

The operator applied the prerequisite using the Silicom-only deploy path:

1. Ran `bash scripts/deploy.sh --silicom-bypass-only cake-shaper --dry-run`.
   - Dry-run scope: install Silicom scripts/units/envs install-if-absent and daemon-reload only.
   - No units enabled or started.
   - No wanctl code/config deploy.
2. Ran `bash scripts/deploy.sh --silicom-bypass-only cake-shaper`.
   - Completed successfully.
   - Did not enable/start units.

Post-deploy precondition passed:

- `/usr/local/sbin/wanctl-bpctl-watchdog-bypass` contains the `.disarm` sentinel branch.
- `/usr/local/sbin/silicom-bypass` usage includes `disarm <pair>`.
- `sudo silicom-bypass` resolves the `disarm` verb.

## Live Task 4 Sequence Performed

1. Migrated active `/etc/wanctl/bpctl-watchdog/att.env` from `WANCTL_UNIT=wanctl@att.service` to `WANCTL_UNIT=cake-autorate-att.service`, preserving backup `/etc/wanctl/bpctl-watchdog/att.env.pre-phase236-20260612T213903Z`.
2. Wrote root-owned `/run/wanctl/bpctl-watchdog/att-modem.disarm` sentinel and verified `SENTINEL_OK` before any stop.
3. Installed ExecStop blank-reset drop-in at `/etc/systemd/system/silicom-bypass-watchdog-cake-autorate-att.service.d/10-retire-mask-execstop.conf` with:

   ```ini
   [Service]
   ExecStop=
   ```

   Then ran `systemctl daemon-reload` before stopping the retired unit.
4. Disabled/stopped the retired unit with the sentinel and ExecStop mask in place. `silicom-bypass-watchdog-cake-autorate-att.service` became inactive/disabled.
5. Verified `att-modem` remained inline: `bpctl_util att-modem get_bypass` returned `The interface is in the non-Bypass mode.`
6. Removed `/run/wanctl/bpctl-watchdog/att-modem.disarm` only after the retired unit was down and verified `SENTINEL_GONE` / sentinel absent.
7. Armed folded `@att` using `/usr/local/sbin/silicom-bypass arm att-modem --yes`; final `silicom-bypass-watchdog@att.service` active/enabled.

## Final Live Verification Reads

- `RETIRED_ACTIVE=inactive`
- `RETIRED_ENABLED=disabled`
- `AT_ACTIVE=active`
- `AT_ENABLED=enabled`
- `SPECTRUM_ACTIVE=active`
- `SPECTRUM_ENABLED=enabled`
- `SENTINEL_ABSENT=yes`

Active `/etc/wanctl/bpctl-watchdog/att.env`:

```text
IFACE=att-modem
WANCTL_UNIT=cake-autorate-att.service
TIMEOUT_MS=10000
```

Active `/etc/wanctl/bpctl-watchdog/spectrum.env`:

```text
IFACE=spec-modem
WANCTL_UNIT=cake-autorate-spectrum.service
```

Relay/watchdog reads:

- `bpctl_util att-modem get_bypass` → `The interface is in the non-Bypass mode.`
- `bpctl_util att-modem get_bypass_wd` → `WDT is enabled with 12800 ms timeout value.`

Stale `WANCTL_UNIT=wanctl@` grep hits remain only in backup files:

- `/etc/wanctl/bpctl-watchdog/att.env.pre-phase236-20260612T213903Z`
- `/etc/wanctl/bpctl-watchdog/spectrum.env.pre-cake-autorate-watchdog-20260604T183631Z`

These are not active `%i.env` files loaded by the watchdog template; active envs are migrated.

## Rollback Diff Review

Accepted. The committed `92ba9a74` diff for `scripts/phase231-rollback.sh` changes only watchdog/env/disarm/restart surfaces.

- No `tc`/qdisc commands changed.
- No health URLs changed.
- No mutation gate lines changed.
- Per-WAN command order accepted:
  - ATT rewrites env to `wanctl@att.service` before `daemon-reload` and sentinel-clean disarm/start of `@att`, then stops cake services.
  - Spectrum uses sentinel-clean disarm before cake stop for native rollback and rewrites env before external return arm.
- Raw watchdog `disable --now` is not accepted as clean disarm and was removed from rollback surfaces.

## Gate Outcome

Task 4 is accepted:

- SENTINEL-FIRST + ExecStop-MASKED retirement was performed with root-correct sentinel write, pre-stop sentinel verification, ExecStop blank-reset drop-in, post-retirement inline relay read, and post-disable shared-sentinel removal + verify-absent.
- HIGH-4 active envs are migrated; stale `wanctl@` hits are backups only.
- A1/HIGH-5 live state confirmed: retired ATT variant inactive/disabled, folded `@att` active/enabled, Spectrum active/enabled, and no leaked shared sentinel.
- Executor did not perform live host mutations; all live actions were operator-run.
