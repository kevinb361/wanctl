# Phase 176: Deployment And Soak Flow Alignment - Research

**Researched:** 2026-04-13
**Domain:** Deployment workflow alignment, install metadata parity, operator CLI surfacing, soak evidence coverage
**Confidence:** HIGH

## Summary

Phase 176 is not a new runtime feature phase. The audit already marked all milestone requirements satisfied; the remaining work is operational alignment so the repo's documented and scripted workflow matches what production actually required for v1.35. The concrete gaps are all in deploy/install/operator tooling and soak evidence capture.

The safest implementation path is conservative and script-first:

1. Keep the controller logic untouched.
2. Do not add deploy-time automation that restarts services or runs migration unprompted.
3. Make the required migration step explicit in the deploy operator flow.
4. Surface the existing `wanctl-operator-summary` capability through the same wrapper/symlink pattern already used for `wanctl-history`.
5. Extend soak evidence tooling so both WAN services and `steering.service` are covered by the repeatable evidence path.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STOR-01 | Metrics DB size remains reduced and migration path is repeatable | `deploy.sh` and docs must explicitly cover the migrate-storage checkpoint between code deploy and restart/canary |
| DEPL-01 | Clean deploy and canary path is repo-supported and version metadata is accurate | `install.sh` version string must match 1.35.0; operator-summary CLI must be deployed/surfaced; deploy guidance must match the real sequence |
| STOR-03 | Soak evidence remains non-critical and repeatable | Soak monitor must cover all claimed services and not stay Spectrum-only |
| SOAK-01 | Full observability stack clean for 24h | Error-scan path must include both WAN services and `steering.service` where enabled |
</phase_requirements>

## Verified Current State

### 1. `scripts/install.sh` still publishes stale release metadata

`scripts/install.sh` line 20 still sets:

```bash
VERSION="1.32.2"
```

while `pyproject.toml` and `src/wanctl/__init__.py` already ship `1.35.0`.

**Impact:** install-facing output is misleading and breaks deploy/install parity.

### 2. `wanctl-operator-summary` exists in Python packaging but is not placed on target hosts

`pyproject.toml` declares:

```toml
wanctl-operator-summary = "wanctl.operator_summary:main"
```

but the current deployment flow only explicitly deploys:

- `scripts/analyze_baseline.py` wrapper into `/opt/wanctl/scripts/`
- `scripts/validate-deployment.sh`
- `wanctl-history` symlinked into `/usr/local/bin`

There is no corresponding wrapper or deploy step for `wanctl-operator-summary`.

**Impact:** Phase 174 had to run `python3 operator_summary.py ...` directly instead of the intended CLI contract.

### 3. `deploy.sh` does not express the required migrate-before-restart path

The audit gap is accurate: `scripts/deploy.sh` deploys files, runs pre-startup validation, then prints next steps, but it does not make the required `deploy -> migrate-storage -> restart -> canary` flow explicit.

This should be fixed with operator guidance, not forced orchestration:

- `scripts/migrate-storage.sh` is a production-impacting operation
- repo instructions say to change conservatively
- AGENTS.md forbids risky changes without explanation

**Recommendation:** update `print_next_steps()` and deployment docs to show the exact migration gate and the service/canary sequence, rather than auto-running migration inside `deploy.sh`.

### 4. `scripts/soak-monitor.sh` is still Spectrum-centric

Current defaults show:

- only one target in `TARGETS`
- one journalctl error scan per `wanctl@${wan_name}`
- no `steering.service` coverage in the error path

**Impact:** the claimed 24h soak evidence path is incomplete for ATT and steering.

## Standard Stack

| Tool | Purpose | Current Status | Phase 176 Need |
|------|---------|----------------|----------------|
| `scripts/install.sh` | target host bootstrap | works but version string stale | update release metadata, keep Python/runtime assumptions aligned |
| `scripts/deploy.sh` | active remote deployment flow | mature, but migration/operator-summary flow incomplete | add explicit migration/operator-summary/steering guidance and CLI deployment |
| `scripts/migrate-storage.sh` | storage migration artifact from Phase 172 | already exists | reference it in the active operator flow, do not rewrite core behavior |
| `scripts/soak-monitor.sh` | soak status/evidence helper | hardcoded to Spectrum, incomplete service coverage | make multi-target and multi-service evidence repeatable |
| `src/wanctl/operator_summary.py` | existing operator summary CLI logic | sound | expose through a deployed wrapper/command |

## Architecture Patterns

### Pattern 1: Use wrapper scripts for operator CLIs

The repo already uses lightweight wrappers for deploy-facing tools (`scripts/analyze_baseline.py`) and deploy-time symlink surfacing (`wanctl-history`). Phase 176 should follow that pattern instead of adding packaging/build complexity to target installs.

**Recommended target state:**

- add `scripts/wanctl-operator-summary` wrapper
- deploy it into `/opt/wanctl/scripts/wanctl-operator-summary`
- symlink `/usr/local/bin/wanctl-operator-summary`
- document the health-URL-based invocation shape actually supported by `src/wanctl/operator_summary.py`

### Pattern 2: Make risky production steps explicit, not implicit

`migrate-storage.sh` affects live services and data paths. The repo should not hide that behind automatic deploy behavior.

**Recommended target state:**

- `deploy.sh` keeps doing file deployment only
- printed next steps and docs show:
  1. stop/restart flow
  2. when to run `scripts/migrate-storage.sh --ssh <host>`
  3. canary after restart
  4. operator-summary and soak-monitor follow-ups

### Pattern 3: Treat soak evidence as a multi-service contract

The soak evidence chain now needs to cover:

- `wanctl@spectrum.service`
- `wanctl@att.service`
- `steering.service` when steering is enabled

The least risky implementation is to enhance the shell script’s target/service configuration rather than inventing a new tool.

## Recommended Plan Split

### Plan 01: Install metadata and operator-summary CLI surfacing

Files likely touched:

- `scripts/install.sh`
- `scripts/deploy.sh`
- `scripts/wanctl-operator-summary` (new)
- docs that reference operator tools if needed

### Plan 02: Migration-aware deploy flow documentation and operator guidance

Files likely touched:

- `scripts/deploy.sh`
- `docs/DEPLOYMENT.md`
- `docs/GETTING-STARTED.md`

Goal: make `deploy -> migrate-storage -> restart -> canary` explicit and repeatable without auto-running migration.

### Plan 03: Multi-service soak evidence coverage

Files likely touched:

- `scripts/soak-monitor.sh`
- `docs/RUNBOOK.md`
- `docs/DEPLOYMENT.md` or related operational docs

Goal: cover ATT plus `steering.service` in the repeatable evidence path.

## Common Pitfalls

### Pitfall 1: Auto-running migration from `deploy.sh`

**Why risky:** migration is production-impacting and may stop multiple services.

**Avoidance:** keep migration as an explicit operator step with exact commands and timing.

### Pitfall 2: Documenting a CLI shape the code does not support

Phase 174 evidence showed that `operator_summary.py` does not support the stale `--wan` invocation path.

**Avoidance:** document and surface the actual interface:

```bash
wanctl-operator-summary http://<health-1>/health http://<health-2>/health
```

### Pitfall 3: Calling soak coverage complete while `steering.service` is omitted

**Avoidance:** make the journal/error path service-aware, and keep steering optional/configurable rather than implied.

## Validation Architecture

Phase 176 is a script/docs alignment phase, so Nyquist coverage should rely on fast artifact and syntax checks rather than large test suites.

Recommended feedback loop:

- After Plan 01 changes:
  - `bash -n scripts/install.sh scripts/deploy.sh scripts/wanctl-operator-summary`
  - `rg -n 'VERSION=\"1.35.0\"|wanctl-operator-summary' scripts/install.sh scripts/deploy.sh docs`
- After Plan 02 changes:
  - `bash -n scripts/deploy.sh`
  - `rg -n 'migrate-storage|canary|steering.service' scripts/deploy.sh docs/DEPLOYMENT.md docs/GETTING-STARTED.md`
- After Plan 03 changes:
  - `bash -n scripts/soak-monitor.sh`
  - `rg -n 'att|spectrum|steering.service' scripts/soak-monitor.sh docs/RUNBOOK.md docs/DEPLOYMENT.md`

Manual-only verification is acceptable for any final operator wording review, but the phase should remain primarily grep/syntax verified.
