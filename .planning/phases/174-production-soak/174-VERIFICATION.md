---
phase: 174-production-soak
verified: 2026-04-13T19:22:54Z
status: verified
score: 2/2 requirements satisfied
---

# Phase 174: Production Soak Verification Report

## Phase Goal

> "The full observability stack runs cleanly in production for 24h, proving storage and runtime stability."

Source: `.planning/ROADMAP.md` Phase 174 goal.

## Soak Window

- Conservative all-services gate start: `2026-04-12T13:23:35-05:00`
- Closeout capture: `2026-04-13T13:45:22-05:00`
- Duration: `24h 22m`

Source: `.planning/phases/174-production-soak/174-01-SUMMARY.md`, which records the latest service activation as `steering.service` and the final evidence capture timestamp.

## Goal Achievement / Observable Truths

| Truth | Status | Evidence |
| --- | --- | --- |
| Storage pressure stays at `ok` or `warning` (not `critical`) for the full 24h soak period | VERIFIED | `.planning/phases/174-production-soak/174-soak-evidence-canary.json` shows `pass` for `spectrum`, `att`, and `steering` with `EXIT_CODE=0`; `.planning/phases/174-production-soak/174-soak-evidence-monitor.json` records `uptime_seconds: 87781.9` (>24h), top-level `storage.status: ok`, WAN storage `status: ok`, and `db_bytes: 5426155520` / `wal_bytes: 4474352`; `.planning/phases/174-production-soak/174-01-SUMMARY.md` records Spectrum DB/WAL `5.1G/4.3M`, ATT DB/WAL `4.8G/4.3M`, steering DB `621M`, and all storage statuses `ok`. |
| Zero unexpected service restarts and zero unhandled errors in journalctl for both WAN services over 24h | VERIFIED (with caveat) | `.planning/phases/174-production-soak/174-soak-evidence-journalctl.txt` contains `-- No entries --` for `journalctl -u wanctl@spectrum -u wanctl@att --since "24 hours ago" -p err --no-pager`, and `.planning/phases/174-production-soak/174-01-SUMMARY.md` interprets that as zero unhandled WAN-service errors over the closeout window. Caveat: `steering.service` was not included in the `-u` filter for this journal scan. `.planning/phases/174-production-soak/174-soak-evidence-canary.json` still shows steering `pass`, but the 24h err-level journal coverage explicitly covered only `wanctl@spectrum` and `wanctl@att`. This residual is tracked in Phase 176 success criterion 4. |
| All v1.34 operator surfaces (alerts, pressure monitoring, summaries, canary) produce valid output at soak end | VERIFIED | `.planning/phases/174-production-soak/174-soak-evidence-operator-spectrum.txt` and `.planning/phases/174-production-soak/174-soak-evidence-operator-att.txt` both render valid multi-line operator tables rather than tracebacks; `.planning/phases/174-production-soak/174-soak-evidence-canary.json` reports all checks passed with `EXIT_CODE=0`; `.planning/phases/174-production-soak/174-soak-evidence-monitor.json` records `status: healthy`, `version: 1.35.0`, `errors_1h: 0`, and Spectrum `storage.status: ok`. |

## Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
| --- | --- | --- | --- |
| `STOR-03` | `174-01` | SATISFIED | `.planning/phases/174-production-soak/174-soak-evidence-canary.json` shows non-failing storage checks for `spectrum`, `att`, and `steering`; `.planning/phases/174-production-soak/174-soak-evidence-monitor.json` records `storage.status: ok` with `uptime_seconds: 87781.9`; `.planning/phases/174-production-soak/174-01-SUMMARY.md` records soak-end DB/WAL sizes of `5.1G/4.3M` (Spectrum), `4.8G/4.3M` (ATT), and steering DB `621M`, all with status `ok`. |
| `SOAK-01` | `174-01` | SATISFIED (with documented residual) | `.planning/phases/174-production-soak/174-soak-evidence-canary.json` reports `EXIT_CODE=0`; `.planning/phases/174-production-soak/174-soak-evidence-journalctl.txt` contains `-- No entries --` for `wanctl@{spectrum,att}` over the last 24 hours; `.planning/phases/174-production-soak/174-soak-evidence-operator-spectrum.txt` and `.planning/phases/174-production-soak/174-soak-evidence-operator-att.txt` show rendered summaries instead of failures. Residual: `steering.service` was not included in the journalctl `-u` filter. Phase 176 success criterion 4 tracks closing that evidence gap. |

## Behavioral Spot-Checks

| Command | Observed Result |
| --- | --- |
| `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0 --json` | `.planning/phases/174-production-soak/174-soak-evidence-canary.json` shows `pass` for `spectrum`, `att`, and `steering`, followed by `EXIT_CODE=0`. |
| `./scripts/soak-monitor.sh --json` | `.planning/phases/174-production-soak/174-soak-evidence-monitor.json` records `status: healthy`, `uptime_seconds: 87781.9`, `version: 1.35.0`, Spectrum `DL GREEN`, `UL GREEN`, and `storage.status: ok`. |
| `journalctl -u wanctl@spectrum -u wanctl@att --since "24 hours ago" -p err --no-pager` | `.planning/phases/174-production-soak/174-soak-evidence-journalctl.txt` contains `-- No entries --`. |
| `sudo -u wanctl python3 operator_summary.py http://<health-endpoint>/health` (run once per WAN, per `.planning/phases/174-production-soak/174-01-SUMMARY.md`) | `.planning/phases/174-production-soak/174-soak-evidence-operator-spectrum.txt` and `.planning/phases/174-production-soak/174-soak-evidence-operator-att.txt` both contain valid multi-line summary tables with `Storage ok` and no traceback output. |

## Residual Debt / Known Gaps

- `steering.service` was not included in the captured `journalctl -u ... -p err` scan, so the 24h err-level journal evidence explicitly covers only `wanctl@spectrum` and `wanctl@att`.
- This is addressed in Phase 176 plan scope and is not a blocker for `STOR-03` or `SOAK-01` closeout because `.planning/phases/174-production-soak/174-soak-evidence-canary.json` and `.planning/phases/174-production-soak/174-01-SUMMARY.md` both show steering healthy at soak closeout.

## Verification Verdict

- `STOR-03`: PASS
- `SOAK-01`: PASS, with the steering journalctl coverage residual explicitly documented and tracked forward.

_Verified: 2026-04-13T19:22:54Z_
_Verifier: Claude (gsd-planner, Phase 175)_
