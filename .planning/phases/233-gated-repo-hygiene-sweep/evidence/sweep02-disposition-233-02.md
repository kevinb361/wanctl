# SWEEP-02 disposition evidence (Plan 233-02)

## Pre-edit wanctl@ counts

Captured before any SWEEP-02 edits with:

```bash
grep -c 'wanctl@' docs/PROFILING.md docs/PERFORMANCE.md docs/RUNBOOK.md docs/CABLE_TUNING.md docs/STEERING.md docs/SILICOM-BYPASS.md
```

| Doc | Pre-edit `wanctl@` count |
|-----|--------------------------:|
| `docs/PROFILING.md` | 9 |
| `docs/PERFORMANCE.md` | 5 |
| `docs/RUNBOOK.md` | 3 |
| `docs/CABLE_TUNING.md` | 7 |
| `docs/STEERING.md` | 2 |
| `docs/SILICOM-BYPASS.md` | 18 |

## Task 1 status

- Baseline captured before edits.
- Mode-disambiguation notes were added to `docs/PROFILING.md`, `docs/PERFORMANCE.md`, and `docs/RUNBOOK.md` without deleting native examples.

## Task 2 operator decision

Decision: `annotate-steering-only`.

- Annotated `docs/STEERING.md` because it contains live operational stop/start commands for `wanctl@spectrum`.
- Left `docs/CABLE_TUNING.md` as-is because its references are historical tuning narrative or a native-mode restart example classified below.
- Left `docs/SILICOM-BYPASS.md` as-is because its references are by-design bypass-watchdog/native-unit interactions or historical validation evidence classified below.

## Post-edit wanctl@ counts

Captured after Task 3 edits with:

```bash
grep -c 'wanctl@' docs/PROFILING.md docs/PERFORMANCE.md docs/RUNBOOK.md docs/CABLE_TUNING.md docs/STEERING.md docs/SILICOM-BYPASS.md
```

| Doc | Pre-edit `wanctl@` count | Post-edit `wanctl@` count | Result |
|-----|--------------------------:|---------------------------:|--------|
| `docs/PROFILING.md` | 9 | 10 | PASS — note added; native examples retained |
| `docs/PERFORMANCE.md` | 5 | 6 | PASS — note added; native examples retained |
| `docs/RUNBOOK.md` | 3 | 4 | PASS — note added; native examples retained |
| `docs/CABLE_TUNING.md` | 7 | 7 | PASS — left as-is per decision; no examples deleted |
| `docs/STEERING.md` | 2 | 3 | PASS — note added; native examples retained |
| `docs/SILICOM-BYPASS.md` | 18 | 18 | PASS — left as-is per decision; no examples deleted |

## Per-hit disposition table

Captured after Task 3 edits with:

```bash
grep -n 'wanctl@' docs/PROFILING.md docs/PERFORMANCE.md docs/RUNBOOK.md docs/CABLE_TUNING.md docs/STEERING.md docs/SILICOM-BYPASS.md
```

| Doc | Line | Excerpt | Disposition | Rationale |
|-----|-----:|---------|-------------|-----------|
| `docs/PROFILING.md` | 8 | `The examples below are for native \`wanctl@\` mode...` | covered by nearby external-mode note | The note itself disambiguates native vs external cake-autorate mode. |
| `docs/PROFILING.md` | 35 | `sudo systemctl edit wanctl@spectrum` | native-mode example | Profiling override command intentionally applies to native mode and is covered by the top note. |
| `docs/PROFILING.md` | 51 | `sudo systemctl restart wanctl@spectrum` | native-mode example | Native profiling restart command covered by the top note. |
| `docs/PROFILING.md` | 64 | `journalctl -u wanctl@spectrum -f` | native-mode example | Native profiling log command covered by the top note. |
| `docs/PROFILING.md` | 97 | `journalctl -u wanctl@spectrum -f` | native-mode example | Native profiling log command covered by the top note. |
| `docs/PROFILING.md` | 107 | `sudo systemctl revert wanctl@spectrum` | native-mode example | Native override rollback command covered by the top note. |
| `docs/PROFILING.md` | 109 | `sudo systemctl restart wanctl@spectrum` | native-mode example | Native restart command covered by the top note. |
| `docs/PROFILING.md` | 115 | `systemctl cat wanctl@spectrum` | native-mode example | Native service inspection command covered by the top note. |
| `docs/PROFILING.md` | 122 | ``systemctl cat wanctl@spectrum` shows...` | native-mode example | Native verification expectation covered by the top note. |
| `docs/PROFILING.md` | 151 | `journalctl -u wanctl@spectrum --since...` | native-mode example | Native log extraction command covered by the top note. |
| `docs/PERFORMANCE.md` | 7 | `The examples below are for native \`wanctl@\` mode...` | covered by nearby external-mode note | The note itself disambiguates native vs external cake-autorate mode. |
| `docs/PERFORMANCE.md` | 58 | `sudo systemctl edit wanctl@spectrum` | native-mode example | Native performance profiling override covered by the top note. |
| `docs/PERFORMANCE.md` | 66 | `sudo systemctl revert wanctl@spectrum` | native-mode example | Native override rollback command covered by the top note. |
| `docs/PERFORMANCE.md` | 67 | `sudo systemctl restart wanctl@spectrum` | native-mode example | Native restart command covered by the top note. |
| `docs/PERFORMANCE.md` | 73 | `journalctl -u wanctl@spectrum --since...` | native-mode example | Native profiling report log command covered by the top note. |
| `docs/PERFORMANCE.md` | 74 | `journalctl -u wanctl@spectrum -f` | native-mode example | Native live log command covered by the top note. |
| `docs/RUNBOOK.md` | 5 | `The examples below are for native \`wanctl@\` mode...` | covered by nearby external-mode note | The note itself disambiguates native vs external cake-autorate mode. |
| `docs/RUNBOOK.md` | 396 | ``compact-metrics-dbs.sh` stops the selected `wanctl@<wan>.service`...` | native-mode example | Maintenance command is explicitly scoped by the top native/external note. |
| `docs/RUNBOOK.md` | 403 | `journalctl -u wanctl@spectrum.service -u wanctl@att.service...` | native-mode example | Native journal inspection is covered by the top note; steering remains included in both modes. |
| `docs/RUNBOOK.md` | 426 | `journalctl -u wanctl@<wan_name> -f` | native-mode example | Native log command covered by the top note. |
| `docs/CABLE_TUNING.md` | 107 | `Managed \`wanctl@spectrum\` still underperformed...` | historical note | Past-tense 2026-04-28 tuning narrative; not a current ownership claim. |
| `docs/CABLE_TUNING.md` | 142 | `Managed \`wanctl@spectrum\` with gateway-only probing...` | historical note | Past-tense experiment result; not a current ownership claim. |
| `docs/CABLE_TUNING.md` | 146 | `Managed \`wanctl@spectrum\` with IRTT enabled...` | historical note | Past-tense experiment result; not a current ownership claim. |
| `docs/CABLE_TUNING.md` | 190 | `managed \`wanctl@spectrum\` with the WAN reflector set...` | historical note | Historical next-test matrix; not current operational guidance. |
| `docs/CABLE_TUNING.md` | 191 | `managed \`wanctl@spectrum\` with one WAN reflector...` | historical note | Historical next-test matrix; not current operational guidance. |
| `docs/CABLE_TUNING.md` | 192 | `managed \`wanctl@spectrum\` with IRTT reintroduced...` | historical note | Historical next-test matrix; not current operational guidance. |
| `docs/CABLE_TUNING.md` | 666 | `sudo systemctl restart wanctl@spectrum` | native-mode example | Native restart example in a cable tuning doc; left as-is per operator decision and not an external-mode ownership claim. |
| `docs/STEERING.md` | 5 | `The examples below are for native \`wanctl@\` mode...` | covered by nearby external-mode note | The note added by the selected disposition disambiguates the operational examples below. |
| `docs/STEERING.md` | 326 | `sudo systemctl stop wanctl@spectrum` | native-mode example | Operational stale-zone validation command now covered by the top external-mode note. |
| `docs/STEERING.md` | 336 | `sudo systemctl start wanctl@spectrum` | native-mode example | Operational stale-zone validation command now covered by the top external-mode note. |
| `docs/SILICOM-BYPASS.md` | 35 | `Before=wanctl@att.service wanctl@spectrum.service` | by-design bypass reference | Unit ordering intentionally targets native controller services in this runbook. |
| `docs/SILICOM-BYPASS.md` | 149 | `WANCTL_UNIT=wanctl@att.service` | by-design bypass reference | Watchdog env intentionally names the native unit to monitor/pet bypass state. |
| `docs/SILICOM-BYPASS.md` | 150 | `WANCTL_UNIT=wanctl@spectrum.service` | by-design bypass reference | Watchdog env intentionally names the native unit to monitor/pet bypass state. |
| `docs/SILICOM-BYPASS.md` | 155 | ``wanctl@...` service is active...` | by-design bypass reference | Watchdog behavior is defined relative to paired native service activity. |
| `docs/SILICOM-BYPASS.md` | 158 | `If a paired \`wanctl@...\` service stops...` | by-design bypass reference | Watchdog behavior intentionally responds to paired native service stop. |
| `docs/SILICOM-BYPASS.md` | 159 | `When the \`wanctl@...\` service comes back...` | by-design bypass reference | Watchdog recovery intentionally responds to paired native service start. |
| `docs/SILICOM-BYPASS.md` | 177 | `Stopping wanctl@att.service put only ATT into bypass...` | historical note | Historical validation evidence of bypass isolation behavior. |
| `docs/SILICOM-BYPASS.md` | 178 | `Restarting wanctl@att.service restored ATT...` | historical note | Historical validation evidence of bypass isolation behavior. |
| `docs/SILICOM-BYPASS.md` | 180 | `Stopping wanctl@spectrum.service put only Spectrum...` | historical note | Historical validation evidence of bypass isolation behavior. |
| `docs/SILICOM-BYPASS.md` | 181 | `Restarting wanctl@spectrum.service restored Spectrum...` | historical note | Historical validation evidence of bypass isolation behavior. |
| `docs/SILICOM-BYPASS.md` | 309 | `with CAKE and \`wanctl@spectrum\` removed...` | historical note | Historical diagnostic result; not current ownership guidance. |
| `docs/SILICOM-BYPASS.md` | 337 | `Stopping \`wanctl@spectrum.service\` while...` | by-design bypass reference | Procedure validates watchdog behavior around paired native service state. |
| `docs/SILICOM-BYPASS.md` | 348 | `sudo systemctl stop wanctl@spectrum.service` | by-design bypass reference | Explicit bypass-watchdog validation command for paired native service. |
| `docs/SILICOM-BYPASS.md` | 380 | `sudo systemctl restart wanctl@spectrum.service` | by-design bypass reference | Explicit bypass-watchdog recovery command for paired native service. |
| `docs/SILICOM-BYPASS.md` | 398 | `before \`wanctl@spectrum\` starts...` | by-design bypass reference | NIC tuning ordering relative to native service is intentional in this runbook. |
| `docs/SILICOM-BYPASS.md` | 452 | `sudo systemctl restart wanctl@spectrum.service` | by-design bypass reference | Explicit recovery command in bypass/NIC troubleshooting context. |
| `docs/SILICOM-BYPASS.md` | 455 | `systemctl is-active wanctl@spectrum.service...` | by-design bypass reference | Status check intentionally includes the paired native service and watchdog. |
| `docs/SILICOM-BYPASS.md` | 466 | `wanctl@spectrum.service: active` | by-design bypass reference | Expected output for the paired native service status check. |

## Closure assertion

Every post-edit `wanctl@` hit across the six candidate docs is classified above as `native-mode example`, `historical note`, `by-design bypass reference`, or `covered by nearby external-mode note`. Zero hits remain as uncovered stale current-ownership claims. Post-edit counts are greater than or equal to the pre-edit baseline for every candidate doc, proving annotation-only handling.
