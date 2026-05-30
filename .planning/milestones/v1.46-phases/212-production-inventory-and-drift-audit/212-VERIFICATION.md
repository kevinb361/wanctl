---
phase: 212-production-inventory-and-drift-audit
verified: 2026-05-27T19:10:36Z
status: passed
score: 16/16 must-haves verified
overrides_applied: 0
---

# Phase 212: Production Inventory And Drift Audit Verification Report

**Phase Goal:** Establish exact live production state before interpreting quality symptoms.  
**Verified:** 2026-05-27T19:10:36Z  
**Status:** passed  
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Spectrum, ATT, and steering deployed versions are captured. | ✓ VERIFIED | `health-spectrum.json` reports `1.45.0`; `health-att.json` reports `1.45.0`; `health-steering.json` reports `1.39.0`; all are summarized in `212-production-inventory.md` and `212-REPORT.md`. |
| 2 | Active health endpoints are captured from deployed/bound or discovered endpoints. | ✓ VERIFIED | Spectrum `http://10.10.110.223:9101/health` and ATT `http://10.10.110.227:9101/health` include deployed config provenance; steering is discovered at `http://127.0.0.1:9102/health` with searched sources recorded. |
| 3 | Service uptime, service status, restart count, watchdog, config path, and health summaries are captured for all three surfaces. | ✓ VERIFIED | `systemd-*.txt` contain `ActiveState`, `SubState`, `ExecMainStartTimestamp`, `NRestarts`, `ExecStart`, `FragmentPath`, `WatchdogUSec`, `User`, and `Group`; `health-*.json` contain `status`, `version`, `uptime_seconds`, and `summary`. |
| 4 | Operator can inspect saved read-only evidence without re-running production probes. | ✓ VERIFIED | `evidence/README.md` indexes all saved artifacts with timestamp/source/command purpose/redaction/posture; all referenced evidence files exist and JSON artifacts parse. |
| 5 | DRIFT-02 drift is classify-only and no production mutation is represented as performed. | ✓ VERIFIED | `212-production-inventory.md` states no deploy/restart/config write/RouterOS write; `212-REPORT.md` Production-Mutation Review marks deploy, restart, config write, RouterOS write, and controlled steering restart as not performed. |
| 6 | Drift classifications use expected staging, accidental drift, unknown drift, resolved by approved deployment, or not drift semantics. | ✓ VERIFIED | Inventory includes required vocabulary and rows classify Spectrum/ATT mostly `not drift`, ATT version as `resolved by approved deployment`, and steering runtime/thresholds as `unknown drift`. |
| 7 | Every mismatch includes expected value, live value, verdict, evidence path, and impact. | ✓ VERIFIED | `212-production-inventory.md` and `212-REPORT.md` tables use expected/live/verdict/evidence/impact columns; drift register carries non-`not drift` rows forward. |
| 8 | Repo config, deployed redacted configs, and live health critical operating points are compared without secrets. | ✓ VERIFIED | Config/health tables cover endpoints, floors, ceilings, setpoints, thresholds, cooldowns, measurement quality, and steering state using `configs/*.yaml`, `config-*.redacted.yaml`, and `health-*.json`. |
| 9 | D-01 through D-13 context decisions are honored. | ✓ VERIFIED | `212-REPORT.md` Source Coverage Closeout lines cover D-01 through D-13 with evidence/rationale; spot check confirms no omitted decision. |
| 10 | D-03 steering degraded-state persistence remains current inventory only. | ✓ VERIFIED | Steering rows cite `SPECTRUM_GOOD` current state and `current-state-good/reproduction-not-attempted`; report states no controlled degraded restart was staged and todo is not closed from one snapshot. |
| 11 | D-05 distinction between `/health` healthy/GREEN and user-perceived quality is preserved. | ✓ VERIFIED | Inventory repeats “healthy/GREEN is daemon-state evidence only”; final report states `/health.status == healthy` and GREEN are not proof of user-perceived internet quality and constrains Phase 213 accordingly. |
| 12 | D-06 systemd-vs-health disagreement handling is explicit. | ✓ VERIFIED | Report preserves systemd and health as separate evidence sources and states no current disagreement was found rather than collapsing one into the other. |
| 13 | D-08 artifacts exclude raw secrets/private key material while distinguishing labels/paths from values. | ✓ VERIFIED | Mechanical secret-like assignment scan returned no matches; deeper scan found only policy labels (`private key material`, `tokens`, `raw RouterOS passwords`) and `${DISCORD_WEBHOOK_URL}` placeholders, not raw URLs, passwords, tokens, or key blocks. |
| 14 | D-09 proof-relevant non-secret config values are preserved. | ✓ VERIFIED | Redacted configs retain WAN names, transport, router host, queue names, floors/ceilings/setpoints, DOCSIS mode, health/metrics ports, steering thresholds, state paths, and cooldowns. |
| 15 | Final report identifies downstream constraints for Phase 213/214/215. | ✓ VERIFIED | `212-REPORT.md` has dedicated Phase 213, Phase 214, and Phase 215 constraint sections covering bound endpoints, daemon-vs-UX distinction, measurement outlier risk, steering drift, and Spectrum upload operating points. |
| 16 | Deferred work is not pulled into Phase 212 scope. | ✓ VERIFIED | Report marks Phase 214 `tcp_12down`, Phase 217 profiling, Phase 218 watch-list, and ATT canary/refractory follow-up as excluded/deferred. |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `evidence/README.md` | Evidence command index and redaction/no-mutation policy | ✓ VERIFIED | Exists, substantive, indexes repo/systemd/health/config/state artifacts with source host and mutation posture. |
| `evidence/repo-expected-summary.json` | Repo expected version, units, paths, endpoints, proof fields | ✓ VERIFIED | JSON parses; includes `repo_version`, `units`, `config_paths`, `repo_health_endpoints`, `proof_relevant_fields`. |
| `evidence/systemd-spectrum.txt` | Spectrum systemd facts | ✓ VERIFIED | Contains active/running, start timestamp, PID, restarts, ExecStart, unit path, watchdog, user/group. |
| `evidence/systemd-att.txt` | ATT systemd facts | ✓ VERIFIED | Contains active/running, start timestamp, PID, restarts, ExecStart, unit path, watchdog, user/group. |
| `evidence/systemd-steering.txt` | Steering systemd facts | ✓ VERIFIED | Contains active/running, start timestamp, PID, restarts, ExecStart, unit path, watchdog, user/group. |
| `evidence/health-spectrum.json` | Spectrum health/version/state/rates/summary | ✓ VERIFIED | JSON parses; status `healthy`, version `1.45.0`, uptime present, endpoint provenance from deployed config, summary rows present. |
| `evidence/health-att.json` | ATT health/version/state/rates/summary | ✓ VERIFIED | JSON parses; status `healthy`, version `1.45.0`, uptime present, endpoint provenance from deployed config, summary rows present. |
| `evidence/health-steering.json` | Steering health/version/state/counters/summary | ✓ VERIFIED | JSON parses; status `healthy`, version `1.39.0`, uptime present, discovered endpoint and searched sources recorded. |
| `evidence/config-spectrum.redacted.yaml` | Redacted deployed Spectrum config | ✓ VERIFIED | Substantive YAML snapshot; proof-relevant fields retained; no raw D-08 values found. |
| `evidence/config-att.redacted.yaml` | Redacted deployed ATT config | ✓ VERIFIED | Substantive YAML snapshot; proof-relevant fields retained; no raw D-08 values found. |
| `evidence/config-steering.redacted.yaml` | Redacted deployed steering config | ✓ VERIFIED | Substantive YAML snapshot; topology/state/thresholds retained; no raw D-08 values found. |
| `evidence/steering-state.redacted.json` | Redacted steering state | ✓ VERIFIED | JSON parses; contains `current_state=SPECTRUM_GOOD` and `congestion_state=GREEN`; source metadata says read-only state read. |
| `212-production-inventory.md` | Inventory/drift classification | ✓ VERIFIED | Tables cover Spectrum, ATT, steering; rows cite evidence paths and impacts. |
| `212-REPORT.md` | Final operator report and downstream constraints | ✓ VERIFIED | Covers DRIFT-01/02/03, D-01..D-13, Evidence Index, Drift Register, mutation review, redaction review, and Phase 213/214/215 constraints. |

Note: `gsd-sdk verify.artifacts` reported false negatives for two `contains` regexes and `verify.key-links` reported false negatives for glob/source-only paths. Manual inspection verified those patterns and links in the actual artifacts.

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Deployed `/etc/wanctl/*.yaml` | `evidence/config-*.redacted.yaml` | Redacted snapshots before persistence | ✓ VERIFIED | Config evidence files include source paths `/etc/wanctl/{spectrum,att,steering}.yaml`, D-08 omission policy, and proof-relevant fields. |
| Deployed health endpoint config | `evidence/health-*.json` | Bound endpoint or discovered endpoint capture | ✓ VERIFIED | Spectrum/ATT health artifacts include deployed config endpoint provenance; steering health records permission-blocked config read plus socket discovery and successful 9102 GET. |
| `evidence/*.json` | `212-production-inventory.md` | Evidence path cited per row | ✓ VERIFIED | Inventory rows cite health, repo summary, systemd, config, and steering-state artifacts. |
| `evidence/config-*.redacted.yaml` | `212-production-inventory.md` | Redacted config comparison | ✓ VERIFIED | Operating-point tables compare deployed redacted YAML against repo config and health. |
| `212-production-inventory.md` | `212-REPORT.md` | Final report summarizes classified drift rows | ✓ VERIFIED | Report carries every non-`not drift` row into the Drift Register and summarizes per-surface inventory. |
| `evidence/` | `212-REPORT.md` | Stable artifact citations | ✓ VERIFIED | Evidence Index and inventory tables cite stable `evidence/` paths. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `212-production-inventory.md` | service/version/endpoint/config rows | Saved `evidence/*` artifacts plus repo configs | Yes | ✓ FLOWING |
| `212-REPORT.md` | final verdicts, drift register, constraints | `212-production-inventory.md` and `evidence/*` paths | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| JSON evidence parses | `.venv/bin/python -m json.tool` on repo summary, health files, steering state | All parsed without output/errors | ✓ PASS |
| Health evidence critical fields exist | Python summary of `status`, `version`, `uptime_seconds`, `summary`, endpoint | Spectrum/ATT/steering all had status/version/uptime/summary/endpoint | ✓ PASS |
| Systemd evidence required fields exist | Python field check over `systemd-*.txt` | All required fields present for all three services | ✓ PASS |
| Raw secret-like assignments absent | `rg -n -i '(password|secret|token|credential|auth|key|private)[[:space:]]*[:=][[:space:]]*[^<{]' ...` | No matches | ✓ PASS |
| Deeper raw secret scan | `rg -n -i 'BEGIN .*PRIVATE KEY|PRIVATE KEY|ROUTER_PASSWORD|DISCORD_WEBHOOK_URL=https?://|token...|password...' ...` | Only policy labels/placeholders, no unredacted values | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| DRIFT-01 | Plans 01, 02, 03 | Exact live inventory of Spectrum, ATT, and steering versions, endpoints, uptime/status, health summaries. | ✓ SATISFIED | Evidence files plus `212-production-inventory.md` and `212-REPORT.md` cover all requested surfaces. |
| DRIFT-02 | Plans 02, 03 | Distinguish expected staged state from accidental/unknown/resolved/not drift without mutation. | ✓ SATISFIED | Inventory/Drift Register classify ATT resolved by approved deployment, steering as unknown drift, Spectrum/ATT config as not drift; mutation review says no Phase 212 mutation. |
| DRIFT-03 | Plans 01, 02, 03 | Compare repo config, deployed `/etc/wanctl/*.yaml`, and `/health` critical operating points without exposing secrets. | ✓ SATISFIED | Redacted config artifacts plus operating-point tables compare endpoints, rates, floors/ceilings/setpoints, thresholds, cooldowns, measurement quality, and steering state; secret scans passed. |

No orphaned Phase 212 requirements were found in `.planning/REQUIREMENTS.md`; traceability maps only DRIFT-01, DRIFT-02, and DRIFT-03 to Phase 212.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `evidence/README.md` | 14 | D-08 terms such as `tokens`, `private key material` | ℹ️ Info | Policy labels only; no unredacted secret value. |
| `evidence/repo-expected-summary.json` | 133 | `private key material` | ℹ️ Info | Excluded-surface label only. |
| `212-REPORT.md` | 90 | `tokens`, `private keys` | ℹ️ Info | Redaction review text only. |
| `evidence/config-spectrum.redacted.yaml` / `config-att.redacted.yaml` | 15 / 11 | `${DISCORD_WEBHOOK_URL}` placeholder | ℹ️ Info | Placeholder env-var reference, not raw webhook URL. |

No blocker anti-patterns, raw secrets, private key blocks, raw router passwords, deploy/restart commands represented as executed, stubs, or hollow artifacts were found.

### Human Verification Required

None.

### Gaps Summary

No gaps found. Phase 212 achieved the goal: saved evidence and final reports establish exact live production state before later quality interpretation, preserve read-only/default-no-mutation posture, account for DRIFT-01/02/03, honor D-01 through D-13, keep raw secrets out of artifacts, and carry downstream constraints for Phases 213/214/215.

---

_Verified: 2026-05-27T19:10:36Z_  
_Verifier: the agent (gsd-verifier)_
