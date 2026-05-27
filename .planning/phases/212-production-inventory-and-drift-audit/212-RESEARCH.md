# Phase 212: Production Inventory And Drift Audit - Research

**Researched:** 2026-05-27 [VERIFIED: system date]
**Domain:** Read-only production inventory, config/health drift audit, and operator evidence capture for `wanctl` [VERIFIED: .planning/phases/212-production-inventory-and-drift-audit/212-CONTEXT.md]
**Confidence:** HIGH for repo/runtime surfaces; MEDIUM for live-production command availability until executed against the production host [VERIFIED: repo inspection + local CLI probes]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Drift Handling
- **D-01:** Default behavior is classify-only. Phase 212 labels each mismatch as expected staging, accidental drift, unknown drift, or not drift. It does not mutate production by default.
- **D-02:** If a mismatch blocks correct interpretation of later quality work, the plan may include an explicit operator approval checkpoint for alignment. Without approval, record the drift and carry it forward instead of fixing it opportunistically.
- **D-03:** Steering restart/degraded-state persistence is folded into Phase 212 only as inventory/state evidence. Capture current steering service status, `/health`, and `/var/lib/wanctl/steering_state.json` shape if available. Do not stage a controlled degraded restart just to reproduce the old todo.

### Authoritative Inventory Surfaces
- **D-04:** Primary live evidence surfaces are systemd status/uptime, bound `/health` endpoints, deployed `/etc/wanctl/*.yaml`, repo `configs/*.yaml`, deployed package/version surfaces, and steering health/state.
- **D-05:** `/health` is authoritative for daemon-reported version, state, rates, measurement quality, and active status, but not sufficient proof of good user experience. Phase 212 must explicitly preserve that distinction for Phase 213.
- **D-06:** Systemd is authoritative for whether a daemon is currently active, restarted, watchdog-managed, and using the expected unit/config path. If systemd and `/health` disagree, report the disagreement rather than picking one silently.
- **D-07:** RouterOS readback is optional and read-only. Use it only for critical operating points where deployed YAML and `/health` are insufficient to prove the live queue/rule state.

### Secret Redaction And Artifact Safety
- **D-08:** Audit artifacts must not include secrets, tokens, private keys, raw router passwords, or full secret-bearing config dumps. Redact values for keys matching password, secret, token, credential, auth, key, or private material.
- **D-09:** Config comparisons should preserve proof-relevant non-secret values: WAN name, transport type, router host identity, queue names, floors/ceilings/setpoints, DOCSIS mode, health/metrics ports, steering thresholds, state paths, and cooldowns.
- **D-10:** If an unredacted command is needed for local operator use, place the command in the plan/runbook, not its sensitive output in the committed artifact.

### Report Shape
- **D-11:** Final output should optimize for operator decisions first: one compact table per surface with expected value, live value, verdict, evidence path, and impact on later phases.
- **D-12:** Raw evidence should be saved as redacted snapshots or summarized command output under the Phase 212 directory so later planners can cite stable artifacts without re-running production probes.
- **D-13:** The closeout summary must list constraints for Phase 213/214/215, especially any version/config drift, health endpoint binding quirks, steering uncertainty, and Spectrum upload operating points that later tests must account for.

### the agent's Discretion
- User delegated the Phase 212 gray-area choices with "you decide." The planner has discretion over exact command shape, evidence filenames, and whether to split the audit into one plan or multiple plans, provided the read-only/default-no-mutation boundary holds.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` — belongs to Phase 214 measurement-collapse investigation after baseline context exists.
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan` — belongs to Phase 217 production cycle-budget baseline unless Phase 212 discovers immediate service health risk.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event` — belongs to Phase 218 watch-list closure when a natural qualifying event exists.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — depends on recovery/refractory and ATT canary context; do not pull into the inventory audit.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DRIFT-01 | Operator can see an exact live inventory of Spectrum, ATT, and steering deployed versions, active health endpoints, service uptime, service status, and health summary state. [VERIFIED: .planning/REQUIREMENTS.md] | Use systemd status/show plus bound `/health` JSON for each daemon; both health implementations expose `version`, `uptime_seconds`, `status`, and summary fields. [VERIFIED: deploy/systemd/wanctl@.service; deploy/systemd/steering.service; src/wanctl/health_check.py; src/wanctl/steering/health.py] |
| DRIFT-02 | Operator can distinguish expected staged deployment state from accidental version/config drift; any ATT/steering version mismatch is either upgraded or documented as intentionally held. [VERIFIED: .planning/REQUIREMENTS.md] | Compare repo version (`pyproject.toml`, `src/wanctl/__init__.py`), deployed code/version surfaces, systemd `ExecStart`, and health `.version`; classify-only unless an explicit approval checkpoint resolves drift. [VERIFIED: pyproject.toml; src/wanctl/__init__.py; 212-CONTEXT.md] |
| DRIFT-03 | Operator can verify repo config, deployed `/etc/wanctl/*.yaml`, and live `/health` critical operating points agree without exposing secrets. [VERIFIED: .planning/REQUIREMENTS.md] | Redact secret-like keys before saving artifacts; compare proof-relevant non-secret config keys to `/health` fields and systemd config paths. [VERIFIED: 212-CONTEXT.md; configs/spectrum.yaml; configs/att.yaml; configs/steering.yaml; src/wanctl/health_check.py; src/wanctl/steering/health.py] |
</phase_requirements>

## Summary

Phase 212 should be planned as a read-only evidence pipeline, not as a deployment or tuning phase. [VERIFIED: 212-CONTEXT.md] The central pattern is: capture repo expectations, capture live systemd facts, capture live bound `/health` JSON, capture redacted deployed YAML/state snapshots, compare critical operating points, then classify each mismatch with an explicit effect on Phase 213/214/215. [VERIFIED: 212-CONTEXT.md; .planning/ROADMAP.md]

The repo says current source version is `1.45.0` in both `pyproject.toml` and `src/wanctl/__init__.py`. [VERIFIED: pyproject.toml; src/wanctl/__init__.py] The project instruction block says `wanctl` is production, Python 3.11+, deployed to `/opt/wanctl`, uses `/etc/wanctl` for config/secrets, `/var/lib/wanctl` for state, `/var/log/wanctl` for logs, and `/run/wanctl` for runtime files. [VERIFIED: AGENTS.md] Spectrum and ATT repo configs bind autorate health to `10.10.110.223:9101` and `10.10.110.227:9101` respectively; prior v1.45 notes confirm loopback was not listening for those endpoints. [VERIFIED: configs/spectrum.yaml; configs/att.yaml; .planning/STATE.md]

**Primary recommendation:** Plan one conservative audit plan with reusable redaction helpers and separate evidence files, plus an explicit operator approval gate only if alignment is required before later quality work. [VERIFIED: 212-CONTEXT.md]

## Project Constraints (from AGENTS.md / CLAUDE.md)

- Treat `wanctl` as a production 24/7 network-control system and change conservatively. [VERIFIED: AGENTS.md; CLAUDE.md]
- Explain risky changes before changing behavior. [VERIFIED: AGENTS.md; CLAUDE.md]
- Do not refactor core logic, algorithms, thresholds, or timing without approval. [VERIFIED: AGENTS.md; CLAUDE.md]
- Prefer targeted fixes over broad cleanup in the control path. [VERIFIED: AGENTS.md; CLAUDE.md]
- Priority order is stability, then safety, then clarity, then elegance. [VERIFIED: AGENTS.md; CLAUDE.md]
- Controller logic must remain link-agnostic; deployment-specific behavior belongs in YAML config, not Python branching. [VERIFIED: AGENTS.md; CLAUDE.md]
- Active production model is service-based systemd, not timer-based; active units are `wanctl@.service` and `steering.service`. [VERIFIED: AGENTS.md; deploy/systemd/wanctl@.service; deploy/systemd/steering.service]
- Health and observability payload shapes are contractual and must not be broken casually. [VERIFIED: AGENTS.md; CLAUDE.md]
- Do not recommend threshold or bounds changes casually; pegged-at-bounds can be intentional. [VERIFIED: AGENTS.md]
- Use `.venv/bin/pytest`, `.venv/bin/ruff`, and `.venv/bin/mypy` for local validation commands. [VERIFIED: AGENTS.md; local CLI probe]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Production service inventory | OS / systemd | Application health API | systemd owns active/inactive state, restart metadata, watchdog settings, and exact `ExecStart`; `/health` reports daemon self-observed status. [VERIFIED: 212-CONTEXT.md; deploy/systemd/wanctl@.service; deploy/systemd/steering.service] |
| Deployed version inventory | Application runtime | Filesystem/package layout | `/health.version` comes from `wanctl.__version__`, while deployed files under `/opt/wanctl` prove what code is installed. [VERIFIED: src/wanctl/health_check.py; src/wanctl/steering/health.py; src/wanctl/__init__.py] |
| Config drift comparison | Filesystem config layer | Application health API | Repo `configs/*.yaml` and deployed `/etc/wanctl/*.yaml` are the config source comparison; `/health` proves the daemon's active operating points. [VERIFIED: 212-CONTEXT.md; configs/spectrum.yaml; configs/att.yaml; configs/steering.yaml] |
| Steering persisted-state audit | State persistence layer | Steering health API | `/var/lib/wanctl/steering_state.json` is the persisted-state surface; steering `/health` exposes current steering state, decision, counters, and WAN-awareness. [VERIFIED: .planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md; src/wanctl/steering/health.py] |
| Secret-safe artifacting | Evidence/report layer | Config parser expectations | Audit outputs must preserve proof-relevant values while redacting secret-like keys and avoiding raw secret-bearing dumps. [VERIFIED: 212-CONTEXT.md; AGENTS.md] |

## Standard Stack

### Core

| Tool / Library | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python | 3.12.3 local dev; project requires `>=3.11` | Redaction/summarization helper scripts and JSON/YAML parsing if needed | Project is Python-first and already depends on stdlib JSON plus PyYAML. [VERIFIED: local CLI probe; pyproject.toml] |
| PyYAML | 6.0.3 in `.venv` | Parse repo/deployed YAML for normalized comparison | Project already uses `yaml.safe_load()` for config parsing. [VERIFIED: local package probe; src/wanctl/config_base.py; .planning/codebase/INTEGRATIONS.md] |
| systemctl | systemd 255 locally | Capture active state, uptime metadata, restart/watchdog config, and `ExecStart` | Production units are systemd services with watchdog and restart policy. [VERIFIED: local CLI probe; deploy/systemd/wanctl@.service; deploy/systemd/steering.service] |
| curl | 8.5.0 locally | Fetch bound `/health` JSON endpoints | Health endpoints are HTTP JSON endpoints. [VERIFIED: local CLI probe; src/wanctl/health_check.py; src/wanctl/steering/health.py] |
| jq | 1.7 locally | Select non-secret JSON fields from `/health` and state snapshots | Local environment has `jq`; use Python fallback if unavailable on production host. [VERIFIED: local CLI probe] |
| OpenSSH client | OpenSSH_9.6p1 locally | Read-only remote probes if production state is on a remote host | Prior production checks used SSH and project docs list SSH journal/health commands. [VERIFIED: local CLI probe; AGENTS.md] |

### Supporting

| Tool / Library | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| GNU diff | 3.10 locally | Text diffs after redaction/normalization | Use only on redacted normalized snapshots, not raw secret-bearing YAML. [VERIFIED: local CLI probe; 212-CONTEXT.md] |
| pytest | 9.0.2 in `.venv` | Validate any added helper/redaction code | Required if the plan adds scripts or tests. [VERIFIED: local CLI probe; pyproject.toml] |
| ruff | 0.14.10 in `.venv` | Lint/format any added Python helper code | Required if code is added. [VERIFIED: local CLI probe; pyproject.toml] |
| mypy | 1.19.1 in `.venv` | Type-check any added Python helper code | Required if code is added under `src/` or typed helpers. [VERIFIED: local CLI probe; pyproject.toml] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python redaction helper | Shell-only `sed`/`grep` pipeline | Shell-only redaction is easier to make incomplete for nested YAML/JSON; use Python/PyYAML for structured redaction if writing artifacts. [ASSUMED] |
| One monolithic report | Separate redacted evidence files plus summary tables | Separate files preserve stable citations and reduce accidental secret exposure in the human summary. [VERIFIED: 212-CONTEXT.md] |
| RouterOS readback for everything | RouterOS readback only for unresolved critical operating points | RouterOS readback is optional and read-only; unnecessary router reads increase operational exposure without improving most config/health comparisons. [VERIFIED: 212-CONTEXT.md] |

**Installation:** No new runtime dependencies are recommended. [VERIFIED: pyproject.toml; local package probe]

**Version verification:** Python package versions were verified with `.venv/bin/python -c importlib.metadata...`; CLI versions were verified with local `--version` probes. [VERIFIED: local CLI/package probes]

## Architecture Patterns

### System Architecture Diagram

```text
Repo expectations
  ├─ pyproject.toml + src/wanctl/__init__.py ──┐
  ├─ configs/{spectrum,att,steering}.yaml ─────┼─> Redaction + normalization ──┐
  └─ deploy/systemd/*.service ─────────────────┘                               │
                                                                                 v
Production read-only probes                                             Drift classifier
  ├─ systemctl show/status wanctl@spectrum.service ───────┐               ├─ not drift
  ├─ systemctl show/status wanctl@att.service ────────────┼─> Evidence ──┼─ expected staging
  ├─ systemctl show/status steering.service ──────────────┤   snapshots   ├─ accidental drift
  ├─ curl bound autorate/steering /health endpoints ──────┤               └─ unknown drift
  ├─ redacted /etc/wanctl/*.yaml snapshots ───────────────┤
  └─ redacted /var/lib/wanctl/steering_state.json snapshot┘
                                                                                 v
                                                                    Operator report tables
                                                                                 v
                                                        Constraints for Phase 213/214/215
```

All production probes in this phase must be read-only unless an explicit operator approval checkpoint is reached. [VERIFIED: 212-CONTEXT.md]

### Recommended Phase Artifact Structure

```text
.planning/phases/212-production-inventory-and-drift-audit/
├── 212-RESEARCH.md
├── evidence/
│   ├── README.md                         # command timestamps and redaction notes
│   ├── repo-expected-summary.json         # non-secret repo expectations
│   ├── systemd-spectrum.txt               # redacted/summarized systemd facts
│   ├── systemd-att.txt
│   ├── systemd-steering.txt
│   ├── health-spectrum.json               # bound /health response, secret-safe
│   ├── health-att.json
│   ├── health-steering.json
│   ├── config-spectrum.redacted.yaml       # deployed /etc snapshot after redaction
│   ├── config-att.redacted.yaml
│   ├── config-steering.redacted.yaml
│   └── steering-state.redacted.json        # persisted steering state shape/value summary
└── 212-REPORT.md                           # final operator tables and phase constraints
```

The exact evidence filenames are at planner discretion as long as redacted snapshots and stable report tables exist. [VERIFIED: 212-CONTEXT.md]

### Pattern 1: Capture Before Compare

**What:** Save redacted evidence snapshots first, then compare from saved artifacts. [VERIFIED: 212-CONTEXT.md]
**When to use:** Use for every production surface so Phase 213/214/215 can cite the same facts later. [VERIFIED: 212-CONTEXT.md]
**Example:**
```bash
# Source: project context + service contracts [VERIFIED: 212-CONTEXT.md; deploy/systemd/*.service]
ssh <prod-host> 'systemctl show wanctl@spectrum.service --property=ActiveState,SubState,ExecMainStartTimestamp,ExecMainPID,NRestarts,ExecStart,FragmentPath,WatchdogUSec,Environment'
ssh <prod-host> 'curl -fsS http://10.10.110.223:9101/health'
```

### Pattern 2: Normalize and Redact Before Diff

**What:** Parse YAML/JSON, replace secret-like values with `"<REDACTED>"`, then compare selected proof-relevant keys. [VERIFIED: 212-CONTEXT.md]
**When to use:** Use before saving `/etc/wanctl/*.yaml`, `/var/lib/wanctl/*.json`, or command output that may contain environment variables. [VERIFIED: 212-CONTEXT.md]
**Example:**
```python
# Source: 212-CONTEXT.md redaction rules + project PyYAML dependency [VERIFIED]
SECRET_PATTERNS = ("password", "secret", "token", "credential", "auth", "key", "private")

def redact(obj):
    if isinstance(obj, dict):
        return {
            key: "<REDACTED>" if any(p in str(key).lower() for p in SECRET_PATTERNS) else redact(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [redact(value) for value in obj]
    return obj
```

### Pattern 3: Classify Drift by Operational Meaning

**What:** Every mismatch gets a verdict and downstream impact: `not drift`, `expected staging`, `accidental drift`, `unknown drift`, or `resolved by approved deployment`. [VERIFIED: 212-CONTEXT.md; .planning/ROADMAP.md]
**When to use:** Use for version, config, endpoint binding, service status, and state-file mismatches. [VERIFIED: 212-CONTEXT.md]

### Anti-Patterns to Avoid

- **Fixing drift while auditing:** Phase 212 default behavior is classify-only and must not tune, deploy, restart services, or silently align production. [VERIFIED: 212-CONTEXT.md]
- **Assuming loopback health endpoints:** Spectrum and ATT repo configs bind health to `10.10.110.223:9101` and `10.10.110.227:9101`; previous production notes observed loopback was not listening. [VERIFIED: configs/spectrum.yaml; configs/att.yaml; .planning/STATE.md]
- **Committing raw config dumps:** `/etc/wanctl/secrets`, router passwords, SSH key paths/material, webhook URLs, and auth-like values must not appear in artifacts. [VERIFIED: 212-CONTEXT.md; AGENTS.md]
- **Treating `healthy`/`GREEN` as UX proof:** v1.46 explicitly requires not treating `/health.status == healthy` or state `GREEN` as sufficient proof of good user experience. [VERIFIED: .planning/REQUIREMENTS.md; .planning/STATE.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Regex parser for YAML | PyYAML `safe_load()` in a small helper | The project already uses PyYAML and `safe_load()` for config parsing. [VERIFIED: pyproject.toml; .planning/codebase/INTEGRATIONS.md] |
| JSON field extraction | Fragile string slicing | Python `json` or `jq` | Health/state surfaces are JSON; structured extraction avoids leaking unrelated fields. [VERIFIED: src/wanctl/health_check.py; src/wanctl/steering/health.py; local CLI probe] |
| Service status inference | Guessing from process names | `systemctl show/status` | Systemd is the authoritative surface for active state, restart policy, watchdog, and `ExecStart`. [VERIFIED: 212-CONTEXT.md; deploy/systemd/*.service] |
| Version proof | Git branch name or changelog only | Repo version + deployed code + `/health.version` | `/health.version` is emitted from `wanctl.__version__`; repo version is in `pyproject.toml` and `src/wanctl/__init__.py`. [VERIFIED: src/wanctl/health_check.py; src/wanctl/steering/health.py; pyproject.toml; src/wanctl/__init__.py] |

**Key insight:** This phase is mostly about preserving trustworthy evidence boundaries; custom cleverness increases the chance of accidental mutation or secret leakage. [ASSUMED]

## Common Pitfalls

### Pitfall 1: Mutating Production During Inventory
**What goes wrong:** An audit command path turns into deploy/restart/tune work. [VERIFIED: 212-CONTEXT.md]
**Why it happens:** Version drift creates pressure to “just fix it” before the report is written. [ASSUMED]
**How to avoid:** Include an explicit approval checkpoint for any alignment and carry unresolved drift forward if approval is absent. [VERIFIED: 212-CONTEXT.md]
**Warning signs:** Commands include `systemctl restart`, `scripts/deploy.sh`, config writes, RouterOS `PATCH`, or YAML edits. [VERIFIED: deploy/systemd/*.service; .planning/codebase/INTEGRATIONS.md]

### Pitfall 2: Health Endpoint Binding Assumptions
**What goes wrong:** The plan probes `127.0.0.1:9101` and falsely concludes health is down. [VERIFIED: .planning/STATE.md]
**Why it happens:** Older codebase maps say localhost defaults, while current repo configs bind Spectrum/ATT to per-WAN IPs. [VERIFIED: .planning/codebase/INTEGRATIONS.md; configs/spectrum.yaml; configs/att.yaml]
**How to avoid:** Derive endpoints from deployed YAML first, then probe those endpoints. [VERIFIED: 212-CONTEXT.md]
**Warning signs:** `curl http://127.0.0.1:9101/health` fails while `systemctl` says the daemon is active. [VERIFIED: .planning/STATE.md]

### Pitfall 3: Leaking Secrets in Drift Artifacts
**What goes wrong:** Raw `/etc/wanctl/*.yaml`, `/etc/wanctl/secrets`, or systemd environment output exposes credentials. [VERIFIED: 212-CONTEXT.md; deploy/systemd/*.service]
**Why it happens:** systemd units load `/etc/wanctl/secrets`, and YAML references include `${ROUTER_PASSWORD}` and `${DISCORD_WEBHOOK_URL}`. [VERIFIED: deploy/systemd/*.service; configs/spectrum.yaml; configs/att.yaml; configs/steering.yaml]
**How to avoid:** Save only redacted snapshots and selected non-secret keys. [VERIFIED: 212-CONTEXT.md]
**Warning signs:** Artifact contains `password`, `token`, `webhook`, `ROUTER_PASSWORD`, private key material, or complete `Environment=` values. [VERIFIED: 212-CONTEXT.md; configs/*.yaml]

### Pitfall 4: Closing the Steering Restart Todo from One Healthy Snapshot
**What goes wrong:** A current `SPECTRUM_GOOD` state is treated as proof that degraded persistence cannot recur. [VERIFIED: .planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md]
**Why it happens:** The old todo requires catching or staging a restart during degraded state, which Phase 212 explicitly should not stage. [VERIFIED: 212-CONTEXT.md; pending todo]
**How to avoid:** Capture current state and classify as current-state-good-but-reproduction-not-attempted unless stronger evidence exists. [VERIFIED: 212-CONTEXT.md]
**Warning signs:** Report says “closed” without pre/post controlled restart evidence. [VERIFIED: pending todo]

## Code Examples

### Extract Expected Repo Version
```bash
# Source: repo version surfaces [VERIFIED: pyproject.toml; src/wanctl/__init__.py]
.venv/bin/python - <<'PY'
import pathlib, tomllib
pyproject = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
print({'pyproject_version': pyproject['project']['version']})
print({'init_version_line': pathlib.Path('src/wanctl/__init__.py').read_text().strip()})
PY
```

### Probe Bound Health Endpoint Read-Only
```bash
# Source: repo configs and health handlers [VERIFIED: configs/spectrum.yaml; src/wanctl/health_check.py]
curl -fsS --max-time 3 http://10.10.110.223:9101/health | jq '{status, version, uptime_seconds, summary, wans}'
```

### Capture Systemd Service Facts Read-Only
```bash
# Source: systemd service contracts [VERIFIED: deploy/systemd/wanctl@.service; deploy/systemd/steering.service]
systemctl show wanctl@spectrum.service \
  --property=ActiveState,SubState,ExecMainStartTimestamp,ExecMainPID,NRestarts,ExecStart,FragmentPath,WatchdogUSec
```

### Redact YAML Before Saving
```python
# Source: redaction requirement [VERIFIED: 212-CONTEXT.md]
import json, pathlib, yaml

SECRET_PATTERNS = ("password", "secret", "token", "credential", "auth", "key", "private")

def redact(obj):
    if isinstance(obj, dict):
        return {k: ("<REDACTED>" if any(p in str(k).lower() for p in SECRET_PATTERNS) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj

data = yaml.safe_load(pathlib.Path('/etc/wanctl/spectrum.yaml').read_text())
print(yaml.safe_dump(redact(data), sort_keys=True))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Timer-era operational guidance | Service-based systemd units | Current project instructions | Do not reintroduce timer-era docs or plan steps. [VERIFIED: AGENTS.md] |
| Loopback-only health assumption | Per-WAN bound health endpoints for Spectrum/ATT | Current repo configs and v1.45 production notes | Discover health endpoints from deployed YAML before probing. [VERIFIED: configs/spectrum.yaml; configs/att.yaml; .planning/STATE.md] |
| Treating health `GREEN` as sufficient quality proof | Health is daemon-state proof, not UX proof | v1.46 requirements | Phase 212 output must constrain but not replace Phase 213 experience baseline. [VERIFIED: .planning/REQUIREMENTS.md; 212-CONTEXT.md] |
| Steering restart bug investigation via controlled restart | Read-only current steering inventory only | Phase 212 decision D-03 | Do not stage degraded restart in Phase 212. [VERIFIED: 212-CONTEXT.md] |

**Deprecated/outdated:** Timer-based service guidance is outdated for active production docs/plans. [VERIFIED: AGENTS.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python structured redaction is safer than shell-only redaction for nested YAML/JSON. | Standard Stack / Alternatives | Planner might overbuild helper code; mitigate by keeping helper small and testable. |
| A2 | Custom cleverness increases accidental mutation or secret leakage risk in this audit domain. | Don't Hand-Roll | Planner might under-spec useful automation; mitigate by allowing small read-only helper scripts. |
| A3 | Version drift creates pressure to opportunistically fix drift during audit. | Common Pitfalls | If wrong, no harm; approval gate still protects production. |

## Open Questions

1. **Which production host should the plan target for remote probes?**
   - What we know: Project docs use production layout paths and SSH examples, and previous endpoints are `10.10.110.223` and `10.10.110.227`. [VERIFIED: AGENTS.md; configs/spectrum.yaml; configs/att.yaml; .planning/STATE.md]
   - What's unclear: The exact SSH target alias/host for the planner to use is not encoded in Phase 212 context. [VERIFIED: 212-CONTEXT.md]
   - Recommendation: Planner should leave `<prod-host>` explicit or use the operator-known host from prior deploy runbooks if already available in local/private context. [ASSUMED]

2. **What is the live steering health bind/port?**
   - What we know: Code example docstring says steering health server example uses port `9102`; older integration map says steering health is `127.0.0.1:9103`; Phase 212 context says steering may differ and must be discovered. [VERIFIED: src/wanctl/steering/health.py; .planning/codebase/INTEGRATIONS.md; 212-CONTEXT.md]
   - What's unclear: The deployed `/etc/wanctl/steering.yaml` and live service decide the actual current endpoint. [VERIFIED: 212-CONTEXT.md]
   - Recommendation: Do not hard-code steering health endpoint; discover from deployed config, service logs, or listening sockets read-only. [VERIFIED: 212-CONTEXT.md]

3. **Should RouterOS readback be used?**
   - What we know: RouterOS readback is optional and read-only, only for critical operating points where YAML and `/health` are insufficient. [VERIFIED: 212-CONTEXT.md]
   - What's unclear: Whether `/health` already proves every queue/rule operating point for this snapshot. [VERIFIED: 212-CONTEXT.md]
   - Recommendation: Plan RouterOS readback as conditional with an approval/credential-safe note, not as the default first probe. [VERIFIED: 212-CONTEXT.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Redaction/helper scripts | ✓ local | 3.12.3 | Use project `.venv/bin/python`; production Python expected by service unit. [VERIFIED: local CLI probe; deploy/systemd/*.service] |
| PyYAML | YAML normalization/redaction | ✓ local | 6.0.3 | Avoid YAML diffs or install project deps before helper use. [VERIFIED: local package probe] |
| systemctl | Service inventory | ✓ local | systemd 255 | Remote host must have systemd because production units are systemd. [VERIFIED: local CLI probe; deploy/systemd/*.service] |
| curl | `/health` capture | ✓ local | 8.5.0 | Python `urllib.request` can fetch JSON if curl missing. [VERIFIED: local CLI probe; src/wanctl/health_check.py; src/wanctl/steering/health.py] |
| jq | JSON selection | ✓ local | 1.7 | Python `json` fallback. [VERIFIED: local CLI probe] |
| ssh | Remote read-only production probes | ✓ local | OpenSSH_9.6p1 | Run commands locally on production host if already logged in. [VERIFIED: local CLI probe] |
| diff | Redacted comparison | ✓ local | GNU diffutils 3.10 | Python `difflib` fallback. [VERIFIED: local CLI probe] |

**Missing dependencies with no fallback:** None found locally. [VERIFIED: local CLI probe]

**Missing dependencies with fallback:** None found locally; production host availability still needs runtime confirmation. [VERIFIED: local CLI probe]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 in `.venv`; project config in `pyproject.toml`. [VERIFIED: local CLI probe; pyproject.toml] |
| Config file | `pyproject.toml` with pytest addopts and coverage config. [VERIFIED: pyproject.toml] |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_check_config.py -q` [VERIFIED: tests glob; AGENTS.md] |
| Full suite command | `.venv/bin/pytest tests/ -v` [VERIFIED: AGENTS.md] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRIFT-01 | Inventory report contains Spectrum/ATT/steering versions, endpoints, uptime, service status, and health summary. [VERIFIED: .planning/REQUIREMENTS.md] | Artifact/schema test if helper/report generator is added; otherwise manual evidence review. [ASSUMED] | `.venv/bin/pytest -o addopts='' tests/test_phase212_inventory.py -q` | ❌ Wave 0 if code helper is added. |
| DRIFT-02 | Drift classification distinguishes expected staging, accidental drift, unknown drift, resolved, and not drift. [VERIFIED: 212-CONTEXT.md] | Unit test for classifier if implemented. [ASSUMED] | `.venv/bin/pytest -o addopts='' tests/test_phase212_inventory.py::test_classifies_version_drift -q` | ❌ Wave 0 if code helper is added. |
| DRIFT-03 | Config comparison redacts secrets and preserves proof-relevant keys. [VERIFIED: 212-CONTEXT.md] | Unit test for redaction/normalization helper if implemented. [ASSUMED] | `.venv/bin/pytest -o addopts='' tests/test_phase212_inventory.py::test_redacts_secret_like_keys -q` | ❌ Wave 0 if code helper is added. |

### Sampling Rate
- **Per task commit:** Run quick helper tests if helper code exists; otherwise run no code tests and manually inspect redacted artifacts. [ASSUMED]
- **Per wave merge:** `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_check_config.py -q` if helper code touches health/config logic; otherwise artifact review is enough. [VERIFIED: tests glob]
- **Phase gate:** Final report must cite evidence artifact paths for each DRIFT requirement and show no unredacted secret-like values. [VERIFIED: 212-CONTEXT.md; .planning/REQUIREMENTS.md]

### Wave 0 Gaps
- [ ] `tests/test_phase212_inventory.py` — only needed if planner adds reusable helper code for redaction, normalization, or classifier behavior. [ASSUMED]
- [ ] Redaction fixture with keys matching password/secret/token/credential/auth/key/private. [VERIFIED: 212-CONTEXT.md]
- [ ] If no helper code is added, no new automated test file is required; use evidence review/checklist instead. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Do not capture or expose RouterOS credentials, SSH private keys, webhook URLs, or `/etc/wanctl/secrets`; use existing operator auth/SSH only for read-only inspection. [VERIFIED: 212-CONTEXT.md; deploy/systemd/*.service; configs/*.yaml] |
| V3 Session Management | no | No web session is introduced by this audit. [VERIFIED: phase scope in 212-CONTEXT.md] |
| V4 Access Control | yes | Treat production mutation as operator-gated; read-only probes only by default. [VERIFIED: 212-CONTEXT.md; AGENTS.md] |
| V5 Input Validation | yes | Parse YAML/JSON structurally and redact keys by name before writing artifacts. [VERIFIED: 212-CONTEXT.md; pyproject.toml] |
| V6 Cryptography | yes | Do not handle private key material; preserve only redacted paths or metadata if necessary. [VERIFIED: 212-CONTEXT.md; configs/*.yaml] |

### Known Threat Patterns for Phase 212

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leakage in committed artifacts | Information Disclosure | Redact secret-like keys before saving; never commit raw `/etc/wanctl/secrets` or raw secret-bearing dumps. [VERIFIED: 212-CONTEXT.md] |
| Accidental production mutation | Tampering / Availability | Use read-only commands; require explicit approval before deploy/restart/config writes/RouterOS write operations. [VERIFIED: 212-CONTEXT.md; AGENTS.md] |
| Misleading evidence from wrong endpoint | Spoofing / Integrity | Derive endpoint from deployed config and cross-check with systemd active service. [VERIFIED: 212-CONTEXT.md; configs/spectrum.yaml; configs/att.yaml] |
| Stale graph or docs overriding live reality | Integrity | Use live probes as evidence; note that the project graph is stale by 726h and returned no relevant nodes for Phase 212 queries. [VERIFIED: graphify status/query]

## Sources

### Primary (HIGH confidence)
- `.planning/phases/212-production-inventory-and-drift-audit/212-CONTEXT.md` — phase decisions, redaction rules, report shape, canonical refs. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` — DRIFT-01 through DRIFT-03 and v1.46 safety scope. [VERIFIED: file read]
- `.planning/STATE.md` — current v1.46 position, v1.45 deployment notes, endpoint lessons. [VERIFIED: file read]
- `.planning/ROADMAP.md` — Phase 212 goal and success criteria. [VERIFIED: file read]
- `AGENTS.md` / `CLAUDE.md` — production safety constraints and runtime layout. [VERIFIED: file read]
- `deploy/systemd/wanctl@.service` and `deploy/systemd/steering.service` — service contracts, ExecStart, watchdog, env file, paths. [VERIFIED: file read]
- `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` — repo expected health endpoints and proof-relevant config keys. [VERIFIED: file read]
- `src/wanctl/health_check.py` and `src/wanctl/steering/health.py` — health payload fields. [VERIFIED: file read]
- `pyproject.toml` and `src/wanctl/__init__.py` — repo version and dependency surface. [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- `.planning/codebase/STACK.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/INTEGRATIONS.md` — codebase maps dated 2026-03-10; useful but superseded by direct repo files where they differ. [VERIFIED: file read]
- Local CLI/package probes — confirm tool availability on the development VM, not necessarily production host. [VERIFIED: bash output]

### Tertiary (LOW confidence)
- Graphify project graph — exists but is stale by 726h and returned no nodes for Phase 212 discovery queries. [VERIFIED: graphify status/query]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for local/dev tools; MEDIUM for production host availability until probed. [VERIFIED: local CLI probes]
- Architecture: HIGH for repo/service/health surfaces; MEDIUM for live steering endpoint until discovered. [VERIFIED: repo inspection; 212-CONTEXT.md]
- Pitfalls: HIGH for production mutation, endpoint binding, and redaction pitfalls; MEDIUM for helper implementation tradeoffs. [VERIFIED: 212-CONTEXT.md; .planning/STATE.md]

**Research date:** 2026-05-27 [VERIFIED: system date]
**Valid until:** 2026-06-03 for live endpoint/deployment assumptions; 2026-06-26 for repo structure if no deployment changes occur. [ASSUMED]
