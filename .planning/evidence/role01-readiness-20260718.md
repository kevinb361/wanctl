# ROLE-01 Readiness Assessment — 2026-07-18

Status: **NOT READY — TIME GATE OPEN**

Scope: read-only assessment. No service, controller, route, queue, qdisc, RouterOS, or traffic-generation mutation was performed.

## Decision

ROLE-01 native-controller retirement must not proceed yet. Both current cake-autorate services entered their uninterrupted active window at `2026-07-10T08:55:27-05:00`. At capture time (`2026-07-18T17:45:06-05:00`) the mechanically proven window was `8.367819` days. The strict 14-day gate matures no earlier than:

`2026-07-24T08:55:27-05:00`

This conservative anchor uses current systemd continuity rather than the earlier July 6 migration date because the services restarted on July 10. Earlier operation is useful history but does not prove one uninterrupted 14-day window.

## Live stability evidence

For both `cake-autorate-spectrum.service` and `cake-autorate-att.service`:

- `ActiveState=active`
- `SubState=running`
- `Result=success`
- `NRestarts=0`
- `ExecMainStartTimestamp=Fri 2026-07-10 08:55:27 CDT`

Both state bridges are active/running with `Result=success` and `NRestarts=0` since `2026-07-10 09:08:31 CDT`.

A journal scan from the stability anchor found:

- warning-or-higher entries: `0`
- starts/stops/failures after the anchor: `0`

Current steering health is `healthy`; route management is `active`, owner `wanctl`, guard `ok`, conflicts `0`, six routes reconciled, circuit breaker closed, and rollback readiness true.

## Rollback readiness

The repo-owned read-only preflight passed for both WANs:

- Spectrum: overall PASS; native instance disabled/inactive; native config/code present; cake-autorate and state bridge active; `Conflicts=wanctl@spectrum.service` present; Spectrum watchdog active and pointed at cake-autorate.
- ATT: overall PASS; native instance disabled/inactive; native config/code present; cake-autorate and state bridge active; `Conflicts=wanctl@att.service` present; folded ATT watchdog active and pointed at cake-autorate; retired watchdog inactive.

Both dry-run rollback and return-to-cake plans rendered successfully. Historical live ATT rollback drill evidence remains recorded in `~/.hermes/skills/devops/wanctl-operations/references/native-controller-rollback-drill-2026-07-09.md` and reports PASS.

Temporary read-only outputs:

- `/tmp/role01-spectrum-preflight-20260718.json`
- `/tmp/role01-spectrum-dryrun-20260718.txt`
- `/tmp/role01-att-preflight-20260718.json`
- `/tmp/role01-att-dryrun-20260718.txt`

## Deferred QoS counter observation

Vault-backed RouterOS read-only status proves both selectors remain applied at unchanged policy hash `4ad83ba7f60e060352e41e7c343af318aa314cf1f982b9076090d9ef3a92921e`.

A full authoritative `/ip firewall mangle print stats detail` capture showed:

- `CONTRACT: HIGH realtime UDP 3480`: `0 packets / 0 bytes`
- `CONTRACT: LOW NNTP`: `0 packets / 0 bytes`

No synthetic traffic was generated. Zero counters are retained as deferred natural-observation facts, not treated as classifier failures.

Read-only artifact:

`../infra-ansible/artifacts/network-readonly/20260718T224800Z-role01-qos-counters/main-router__role01-qos-counters.txt`

## Next gate

On or after `2026-07-24T08:55:27-05:00`:

1. Recheck both cake-autorate and state-bridge service continuity, results, restart counts, and warning/error journals.
2. Re-run both WAN rollback preflights and dry-run plans.
3. Verify health, CAKE qdiscs, watchdog wiring, and native fallback artifacts.
4. Recheck UDP/3480 and NNTP counters opportunistically.
5. If every check passes, prepare a separate approval packet defining exact retirement scope and rollback. Do not retire native controller assets as part of the readiness check.
