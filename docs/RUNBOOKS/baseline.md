# Phase 213 Baseline Harness Runbook

## Purpose

Phase 213 captures an evidence-only experience baseline for normal browsing,
upload, download, RRUL, and `tcp_12down`. It generates dev-VM traffic and reads
existing health/alert/steering surfaces; it does not change production state.

## Quick start

One command:

```bash
bash scripts/phase213-baseline-capture.sh \
  --bind-map spectrum=10.10.110.226,att=10.10.110.233 \
  --host dallas \
  --wans spectrum,att
```

Offline manifest check for pytest/schema work:

```bash
bash scripts/phase213-baseline-capture.sh --check-manifest
```

Live prereq check before a real operator run:

```bash
bash scripts/phase213-baseline-capture.sh \
  --bind-map spectrum=10.10.110.226,att=10.10.110.233 \
  --check-prereqs
```

Spectrum-only smoke/baseline:

```bash
bash scripts/phase213-baseline-capture.sh \
  --bind-map spectrum=10.10.110.226 \
  --wans spectrum
```

## Operational modes

| Mode | Production access | Purpose |
|------|-------------------|---------|
| `--check-manifest` | None | Offline schema-valid manifest emission for tests. No SSH and no curl. |
| `--check-prereqs` / `--dry-run` | Live read/probe only | Checks local tools, SSH, sudo, bind IPs, and per-WAN egress. |
| real run | Live evidence reads + dev-VM traffic | Creates `evidence/RUN-<ts>/` with per-test artifacts and signal sheet. |

## Mutation posture (D-10)

Allowed: dev-VM traffic generation and read-only evidence capture.

Forbidden: service restart, `/etc/wanctl` edits, steering control commands,
RouterOS writes, deploys, profiling harness changes, and controller config
changes.

Do NOT do this:

```text
systemctl restart wanctl@...
edit /etc/wanctl/*.yaml
change RouterOS queues
```

## Per-WAN bind map and egress probe

The harness uses `--bind-map`, not a single cross-WAN bind. A single bind would
invalidate per-WAN labels. Spectrum uses `10.10.110.226` and must egress as
`70.123.224.169`; ATT uses `10.10.110.233` and is recorded-only until an ATT
signature is promoted to a hard gate.

## D-11 serialized order

`--wans spectrum,att` is serialized: Spectrum's full suite completes before ATT
starts. `--wans att,spectrum` is also serialized; it only reverses which WAN runs
first. Calling either order concurrent is wrong. D-11 forbids dual-WAN concurrent
load.

## Files

| File | Role | Notes |
|------|------|-------|
| `scripts/phase213-baseline-capture.sh` | Orchestrator | One-command entry, bind map, mode split, poller cleanup. |
| `scripts/phase213-health-poller.sh` | NDJSON poller | 1Hz extended `/health` projection. |
| `scripts/phase213-browse-loop.sh` | Browse leg | Source-bound curl CSV loop. |
| `scripts/phase213-alert-window.sh` | Alert capture | Read-only SQLite window extraction. |
| `scripts/phase213-steering-snapshot.sh` | Steering snapshot | Redacted pre/post steering state. |
| `scripts/phase213-classify.py` | Classifier | Emits six-bucket signal sheet. |
| `docs/RUNBOOKS/baseline.md` | Operator guide | This file. |

## Per-run artifact tree (MEDIUM-5)

```text
evidence/RUN-<ts>/
├── manifest.json
├── signal-sheet.json
├── signal-sheet.md
├── spectrum/
│   ├── browse/
│   ├── tcp_upload/
│   ├── tcp_download/
│   ├── rrul/
│   └── tcp_12down/
└── att/
    ├── browse/
    ├── tcp_upload/
    ├── tcp_download/
    ├── rrul/
    └── tcp_12down/
```

Each `<wan>/<test>/` contains per-test health NDJSON, steering pre/post snapshots,
alert-window JSON, a manifest, and either `browse.curl.csv` or normalized
`flent/` symlink output. `signal-sheet.{json,md}` live inside the RUN dir, not at
the evidence root.

## Reading the signal sheet

The classifier emits six buckets: upload ceiling/setpoint, download recovery
lag, measurement collapse, steering drift, refractory semantics, and external
ISP/path. Each bucket includes evidence rows and an operator note. The
`recommended_next_phase.primary` field is one of 214, 215, or 216 with runners-up.

## Carrying forward

Plan 05 authors `213-REPORT.md` from `evidence/RUN-<ts>/signal-sheet.md`, citing
bucket rows and preserving the evidence-only boundary.
