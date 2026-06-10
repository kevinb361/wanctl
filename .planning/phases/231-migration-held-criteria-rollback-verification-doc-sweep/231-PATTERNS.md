# Phase 231 Pattern Map

**Generated:** 2026-06-10
**Purpose:** closest existing analogs for each file Phase 231 creates/modifies, with the concrete
conventions the executor must replicate.

## Files to create → analogs

### `scripts/phase231-migration-held.sh` ← `scripts/soak-monitor.sh` + `scripts/phase227-qdisc-verify.sh`

Conventions to replicate from `scripts/soak-monitor.sh`:
- `#!/bin/bash` + `set -euo pipefail`, header comment with Usage line.
- SSH invocation shape: `ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" '...'`.
- Read-only sudo on target: `sudo -n` (Phase 212 precedent), never interactive sudo.
- Per-WAN target tuple array: `"kevin@10.10.110.223|spectrum|10.10.110.223"`, `"kevin@10.10.110.223|att|10.10.110.227"`.
- `--json` flag emitting machine-readable output; jq-optional handling (`HAS_JQ` guard).
- External-mode detection: rely on Phase 230 generalized live-unit logic (`cake-autorate-{wan}.service`,
  `cake-autorate-{wan}-state-bridge.service`, ATT watchdog), not the legacy static `SERVICE_UNITS` array.

From `scripts/phase227-qdisc-verify.sh`: fail-closed exit codes — missing/ambiguous/SSH-failure
states exit non-zero; only a fully-proven state exits 0.

### `scripts/phase231-rollback.sh` ← `scripts/phase227-rollback.sh`

Replicate exactly:
- `usage()` heredoc; `--dry-run` (mutate nothing) and `--confirm` (required for real mutation) flags;
  `DRY_RUN="0"` / `CONFIRM="0"` string-flag convention.
- `print_plan()` heredoc that renders the full ordered command sequence before any action.
- `require_command()` guard; `json_string()` via python3 `json.dumps`; proof JSON written to an
  `--out` path under the phase evidence dir.
- Health verification step against `http://<ip>:9101/health` after mutation (only in confirm mode).
- Per-WAN parameterization: `--wan {spectrum|att}` selecting unit trio + qdisc restore commands
  (rollback source of truth: `WANCTL_CAKE_AUTORATE_FUTURE.md` ATT rollback block lines ~1136–1150).

### `tests/test_phase231_*.py` ← `tests/test_soak_monitor_att_coverage.py`

Conventions: pytest functions reading the script source as text and asserting literal command/flag
presence (no live SSH in tests); fake-ssh shim pattern from Phase 230 (`fake-ssh` PATH shim) if
behavioral assertions are needed; focused file runs in `<1s`.

### `231-SOAK01-EVIDENCE.md` / `231-SOAK02-EVIDENCE.md` ← `230-MON01-EVIDENCE.md`

Structure: title, **Captured:** ISO timestamp, **Scope:** read-only declaration, **Verdict:** line,
then per-check sections each with fenced Command block + fenced Captured-output block, closing
Finding/Verdict paragraph. Greppable verdict literals (e.g., `SOAK-01 PASS`).

### `231-SAFE14-BOUNDARY.md` ← `230-SAFE14-BOUNDARY.md`

Copy the exact section skeleton: Baselines table (SAFE_BASE 87980bdf + PHASE231_START), Protected
Controller-Path Diff (same 7-target `git diff --stat` command), Dirty-Tree Status, Scope Accounting
vs PHASE231_START, verification outputs re-recorded (shellcheck/pytest), Boundary Verdict. Protected
set must include `wan_controller_state.py` (decision [227-04]).

## Files to modify → in-place conventions

### `docs/DEPLOYMENT.md`, `docs/CONFIGURATION.md`, `README.md`, `docs/ARCHITECTURE.md`

- Markdown style: relative links like `[`deploy/systemd/wanctl@.service`](../deploy/systemd/wanctl@.service)`;
  fenced bash blocks for commands; `##`/`###` heading hierarchy.
- Prose source of truth for the two deployment modes: `CLAUDE.md` "Service Model" section.
- Public-safe: generic `<target_host>` / `wan1` placeholders in docs prose; do not copy LAN IPs
  from deploy units into docs.
- Do not delete generic wanctl@ documentation — it remains the valid native mode; add external
  cake-autorate mode alongside and correct any text that presents wanctl@ as the live
  Spectrum/ATT rate-control owner (DEPLOYMENT.md lines ~187/201 journalctl examples are the
  clearest stale claims).

## Anti-patterns (from project memory)

- Do not wire anything to `scripts/phase226-restore.sh` (dry-run-only proof, not a rollback).
- Do not reintroduce timer-era guidance into active docs.
- Do not swap default netperf validation to iperf without approval (not needed this phase).
- Do not touch controller thresholds/algorithms (SAFE-14 surface is deploy/test/ops/doc only).
