# Phase 198: Spectrum cake-primary B-leg rerun on Phase 197 build — Research

**Researched:** 2026-04-27
**Domain:** Production validation / soak orchestration / flent throughput acceptance
**Confidence:** HIGH

## Summary

Phase 198 is a pure validation/closeout phase. Every code/config change required
to fix the underlying Spectrum throughput regression already shipped in Phase
197 (split `dl_cake_for_detection` from `dl_cake_for_arbitration`, new reasons
`queue_during_refractory` / `rtt_fallback_during_refractory`, new bool
`signal_arbitration.refractory_active`, new metric
`wanctl_arbitration_refractory_active`, capture-script extension, audit
predicate document). Phase 198 only needs to:

1. Prove the Phase 197 build is what is actually running on the Spectrum
   `cake-shaper` host (deployed binary version + git rev + presence of new
   reason constants + presence of new metric in `/health`).
2. Re-run the same B-leg harness used in Phase 196 (capture script, same
   deployment token, same 24h+ window, same audit predicate — but now with the
   Phase 197 accept-list).
3. Capture three Spectrum-bound flent `tcp_12down` runs with `--local-bind
   10.10.110.226` during the loaded portion and apply the new `2-of-3 medians
   ≥532 Mbps AND median-of-medians ≥532 Mbps` rule.
4. Diff the captured B-leg counters against the **already-passed** Phase 196
   rtt-blend A-leg control evidence (88373/88373 RTT-primary metric samples,
   28.2311h duration) and emit `ab-comparison.json`.
5. Run a SAFE-05 source-tree diff that proves nothing under `src/wanctl/`
   touching state-machine / EWMA / dwell / deadband / threshold / burst code
   has changed since the Phase 197 commit ship.

Almost every tool, predicate, and artifact path the planner needs already
exists. The phase reduces to scripted operator procedure plus three new JSON
artifacts (`deployment-proof.json`, `198-PREFLIGHT.md`, `ab-comparison.json`)
and three flent runs.

**Primary recommendation:** Plan as 4 plans — (1) Preflight + deployment proof,
(2) 24h cake-primary B-leg soak and audit, (3) Three corrected-bind flent
captures and acceptance, (4) ab-comparison.json + verification closeout for
196-VERIFICATION.md and 198-VERIFICATION.md.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deployment proof (Phase 197 binary on Spectrum host) | Operator + capture script | `/health` + git | Proven by reading `version` from `/health`, listing the new metric, and running git rev-parse on the deployed `/opt/wanctl/` |
| Mode-gate switch to cake-primary | YAML config + systemctl | — | `cake_signal.enabled=true` in `/etc/wanctl/spectrum.yaml`, then `systemctl restart wanctl@spectrum.service` |
| 24h soak evidence capture | Operator + `scripts/phase196-soak-capture.sh` | SSH + remote sqlite3 | Existing helper already extended for Phase 197 (refractory_active + new metric); operator runs start/finish captures |
| Primary-signal audit | Audit predicate doc + jq/Python | Raw SQLite metrics | Use the Phase 197 audit predicate (`primary-signal-audit-phase197.md`) on raw rows only |
| Flent throughput | Operator dev machine + `scripts/phase191-flent-capture.sh` | Spectrum source bind | Three runs with `--local-bind 10.10.110.226 --tests tcp_12down --duration 30 --output-dir ~/flent-results/phase198` |
| A/B comparison | New script or jq pipeline | Phase 196 rtt-blend artifacts | Compare cake-primary B-leg counters to Phase 196 A-leg control set |
| SAFE-05 source-tree diff | Operator + git diff | — | `git diff <phase-197-tag>..HEAD -- <protected-files>` must be empty |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VALN-04 | Spectrum cake-primary B-leg validation on the same deployment token as the accepted Phase 196 A-leg, under Phase 197 refractory split semantics; A/B comparison artifact emitted against accepted A-leg control evidence | A-leg artifact set is intact at `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/`; capture script already updated for Phase 197; audit predicate document already exists [VERIFIED: filesystem inspection 2026-04-27] |
| VALN-05a | Spectrum DL `flent tcp_12down` 30s throughput under `cake-primary` ≥ 90% of 591 Mbps floor (≥ 532 Mbps), 2-of-3 individual medians AND median-of-medians | `scripts/phase191-flent-capture.sh` supports `--local-bind`, `--duration`, `--tests`, `--output-dir`. Use `10.10.110.226` (Spectrum egress proven in source-bind-egress-proof.json) [VERIFIED: scripts/phase191-flent-capture.sh:159] |
| SAFE-05 | No state-machine / EWMA / dwell / deadband / threshold / burst-detection change between Phase 197 ship and Phase 198 acceptance | Protected file list documented in 196-PREFLIGHT.md; protocol established with `git diff --quiet -- <files>` evidence pattern [VERIFIED: 196-PREFLIGHT.md:39-44] |

## User Constraints (from ROADMAP Phase 198)

### Locked Decisions
- Same deployment token as Phase 196: `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`
- Source bind for Spectrum flent: `10.10.110.226` (NEVER `10.10.110.233` — that exits AT&T)
- Acceptance: 2-of-3 individual medians ≥532 Mbps AND median-of-medians ≥532 Mbps
- Re-use Phase 196 rtt-blend A-leg control evidence (88373/88373 metric samples) — DO NOT re-run rtt-blend
- DO NOT reuse Phase 196 A-leg flent throughput numbers as Spectrum baseline (wrong source bind in those captures per 196-12-SUMMARY.md)
- Use Phase 197 audit predicate (`primary-signal-audit-phase197.md`) — accept-list `{queue_distress, green_stable, queue_during_refractory}` with `rtt_fallback_during_refractory + refractory_active=true` as a separate documented-exception bucket
- Verdict consumes raw SQLite rows (`granularity = 'raw'`), not 1-minute aggregates

### Claude's Discretion
- Whether to add a thin Phase 198 wrapper script around the three flent runs (acceptable if it does not change controller code)
- Exact `ab-comparison.json` schema (proposed below)
- Plan count (recommend 4; 3 also defensible)
- Whether to fold deployment-proof into preflight or make it a separate plan

### Deferred Ideas (OUT OF SCOPE)
- ATT cake-primary canary (VALN-05b — gated on Phase 191 closure, Phase 196-08 owns it)
- Re-enabling fusion on Spectrum or ATT
- Any algorithm / threshold / EWMA / dwell / deadband / burst-detection / state-machine change (SAFE-05)
- Tech debt cleanup (`scripts/phase196-soak-capture.sh` WR-01/WR-02; missing `195-VALIDATION.md`; `194-VALIDATION.md` nyquist=false)
- New replay tests (Phase 197 replay battery already covers refractory semantics)

## Project Constraints (from CLAUDE.md)

- Production 24/7 controller; priority is **stability > safety > clarity > elegance**
- Never refactor core logic / algorithms / thresholds / timing without approval
- Phase 198 is allowed to capture evidence and run flent. It is NOT allowed to edit controller source.
- All scripts must work on Linux (Ubuntu) operator machine
- Use `.venv/bin/...` for Python tooling
- Pre-commit hook may require `SKIP_DOC_CHECK=1` for evidence-only commits (Phase 197 precedent: 197-02-SUMMARY.md)
- Service-based deployment (NOT timer-based) — any restart goes through `systemctl restart wanctl@spectrum.service`
- Cycle interval is 50ms; 24h soak therefore generates ~1.7M cycles → expect ~70-90k raw metric rows over the window (rtt-blend got 88373; B-leg got 74697)

## Standard Stack

### Core Tools (already installed and proven on dev machine + cake-shaper)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `flent` | from PATH on dev machine | Throughput tests (tcp_12down) | Phase 191/196 used it — `scripts/phase191-flent-capture.sh` is the reusable wrapper [VERIFIED: scripts/phase191-flent-capture.sh:106] |
| `netperf` | from PATH | Backend for flent | flent invokes netperf — required by phase191-flent-capture.sh [VERIFIED: scripts/phase191-flent-capture.sh:111] |
| `curl` | system | `/health` reads | Used by phase196-soak-capture.sh [VERIFIED: scripts/phase196-soak-capture.sh:181] |
| `jq` | system | health JSON parsing + audit predicate | Phase 197 audit predicate is jq-shaped [VERIFIED: primary-signal-audit-phase197.md:28-40] |
| `ssh` (BatchMode) | system | journal + remote sqlite reads | Phase 196 capture pattern [VERIFIED: scripts/phase196-soak-capture.sh:103] |
| `sqlite3` (remote) | on cake-shaper | metrics DB read-only | Phase 196 capture pattern; required on `PHASE196_SPECTRUM_SSH_HOST` [VERIFIED: scripts/phase196-soak-capture.sh:104] |
| `git` | local | rev-parse, diff for SAFE-05 + deployment proof | Standard |
| `python3` (.venv) | 3.11+ | flent summary parsing if needed | Project convention |

### Reused Helpers (DO NOT reinvent)

| Helper | Path | What It Does |
|--------|------|--------------|
| Phase 196 soak capture | `scripts/phase196-soak-capture.sh` | Captures `/health`, journal, raw + aggregate SQLite; emits per-call summary JSON. Already Phase-197-aware (extracts `refractory_active`, includes `wanctl_arbitration_refractory_active` in metric exports) [VERIFIED: scripts/phase196-soak-capture.sh:116,148,219] |
| Phase 191 flent capture | `scripts/phase191-flent-capture.sh` | Runs flent with `--local-bind`, captures raw `.flent.gz`, plot, and summary; writes `manifest.txt` [VERIFIED: scripts/phase191-flent-capture.sh:1-192] |
| Phase 196 mode-gate procedure | `196-MODE-GATE.md` | YAML edit + restart procedure for `cake_signal.enabled` toggle. **Phase 198 inherits this verbatim** — already-restored-to-cake-primary state can be reused; no second restart should be needed [VERIFIED: 196-MODE-GATE.md:38-128] |

### Known Helper Limitations (from 196-REVIEW.md, not blocking Phase 198)

- WR-01: `scripts/phase196-soak-capture.sh` SQLite output is one snapshot, not timestamped per-row history (line 106). Phase 198 audit needs **timestamped raw rows over the full window** — same query the Phase 196 B-leg used (it generated 74697 rows over 24h). The query already filters `timestamp >= strftime('%s', 'now', '-24 hours')`, which works because the helper is run AT the finish capture moment. Confirmed working in 196-07.
- WR-02: requires `sqlite3` on the remote host. cake-shaper has it (Phase 196 used it). Not a Phase 198 blocker.

## Architecture Patterns

### System Architecture Diagram

```
┌──────────────────┐
│ Operator (dev VM)│
└────────┬─────────┘
         │
         ▼ ssh / curl / git
┌──────────────────────────────────────────────────────────────────┐
│ cake-shaper (Spectrum control host)                              │
│  ┌──────────────────────┐  ┌────────────────────────────────┐   │
│  │ /opt/wanctl/         │  │ /etc/wanctl/spectrum.yaml      │   │
│  │  (deployed binary,   │  │  cake_signal.enabled: true     │   │
│  │   must be Phase 197) │  │  (mode gate)                   │   │
│  └────────┬─────────────┘  └──────────────┬─────────────────┘   │
│           │                                │                     │
│  ┌────────▼─────────┐                      │                     │
│  │ wanctl@spectrum  │◄─────systemctl───────┘                     │
│  │  .service        │                                            │
│  │  (50ms cycle)    │                                            │
│  └────┬─────┬───────┘                                            │
│       │     │                                                    │
│       │     └──► /health (port 9101)                             │
│       │           {wans[0].signal_arbitration.{                  │
│       │            active_primary_signal,                        │
│       │            refractory_active,                            │
│       │            control_decision_reason,                      │
│       │            ...}}                                         │
│       │                                                          │
│       └─► /var/lib/wanctl/<spectrum-metrics-db>                  │
│            metrics table:                                        │
│             wanctl_arbitration_active_primary  (0/1/2)           │
│             wanctl_arbitration_refractory_active (0.0/1.0)       │
│             granularity in {raw, 1m, ...}                        │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────┐                ┌────────────────────┐
│ Operator dev machine │                │ Spectrum egress    │
│ flent --local-bind   │──tcp_12down───►│ 10.10.110.226      │
│ 10.10.110.226        │                │ → 70.123.224.169   │
│ -H dallas -l 30      │                │   (Charter)        │
│ 3 runs               │◄───────────────┤ NOT 10.10.110.233  │
└──────────────────────┘                │ (that's AT&T)      │
                                        └────────────────────┘
```

### Recommended Output Structure

```
.planning/phases/198-spectrum-cake-primary-b-leg-rerun/
├── 198-RESEARCH.md                                    (this file)
├── 198-CONTEXT.md                                     (planner produces)
├── 198-PREFLIGHT.md                                   (Plan 01 produces)
├── 198-VERIFICATION.md                                (Plan 04 produces)
├── 198-VALIDATION.md                                  (planner / Nyquist)
├── 198-NN-PLAN.md / 198-NN-SUMMARY.md                 (per plan)
└── soak/
    ├── deployment-proof/
    │   ├── deployment-proof.json
    │   └── git-diff-safe-05.txt
    ├── cake-primary/
    │   ├── manifest.json
    │   ├── cake-primary-start-<TS>-summary.json       (capture-script output)
    │   ├── cake-primary-finish-<TS>-summary.json
    │   ├── primary-signal-audit.json                  (Phase 197 predicate)
    │   ├── flent-spectrum-3run-summary.json
    │   ├── ab-comparison.json
    │   └── raw/                                       (capture-script output)
    └── safe-05/
        └── source-tree-diff.json
```

### Pattern: Mode-gate is already-set
The Phase 196 procedure restores cake-primary at the end of the mode-gate proof (`196-MODE-GATE.md:24-32`). Production has been running cake-primary since the Phase 196 B-leg started (2026-04-26T09:20:26Z). **The Phase 198 plan should NOT do a redundant mode-gate cycle** — it should verify current mode is cake-primary via `/health` and proceed. A SIGUSR1 reload is also rejected by the same gate (`196-MODE-GATE.md:13`) so deployment of Phase 197 code requires `systemctl restart wanctl@spectrum.service` (which clears process memory and is the correct way to bring the new `_dl_arbitration_used_refractory_snapshot` attribute online).

### Pattern: Restart on deploy (CRITICAL)
Phase 197 added new `self._*` attributes (`_dl_arbitration_used_refractory_snapshot`) and new module-level constants (`ARBITRATION_REASON_QUEUE_DURING_REFRACTORY`). These exist only in process memory after a restart. **Phase 198 deployment proof must include evidence that `wanctl@spectrum.service` was restarted AFTER the Phase 197 binary was rsynced to `/opt/wanctl/`** — otherwise a stale process is still running Phase 196 code despite source-on-disk being Phase 197.

### Anti-Patterns to Avoid

- **Re-running rtt-blend A-leg.** Already passed at 28.2311h with 0/88373 non-RTT samples. Re-running it costs 24h and adds nothing. Reuse it as the comparator.
- **Using `10.10.110.233` for Spectrum flent.** That exits AT&T. Documented in `source-bind-egress-proof.json`. The `scripts/phase191-flent-capture.sh` `--local-bind` validator (line 121) only checks the IP is configured locally — it does NOT verify which WAN it egresses through. The planner must add an explicit egress verification step BEFORE the flent runs.
- **Running flent during the unloaded portion of the window.** VALN-05a requires `tcp_12down` during the **loaded portion**. In Phase 196 B-leg the operator ran flent right at the end of the soak window. Same approach is acceptable — the soak provides the loaded environment, the flent runs themselves are the load.
- **Treating verdict pass on a single flent run.** The new acceptance rule is 2-of-3 + median-of-medians, specifically because the prior failures (307.92, 302.90) were repeatable.
- **Rebuilding the audit predicate.** `primary-signal-audit-phase197.md` is the contract. Use it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Health/journal/SQLite capture | New capture script | `scripts/phase196-soak-capture.sh` | Already Phase-197-aware; emits stable summary JSON shape |
| flent runner | Bespoke `flent` invocation | `scripts/phase191-flent-capture.sh` | Validates `--local-bind` is configured, captures raw + plot + summary, writes manifest |
| Mode-gate procedure | New YAML editor | `196-MODE-GATE.md` operator procedure | Already proven on cake-shaper |
| Audit predicate | New jq filter | `primary-signal-audit-phase197.md` | Locked accept-list, raw-row-only filter, regime buckets |
| Source-bind verification | Ad-hoc curl | `source-bind-egress-proof.json` pattern (Phase 196-11) | Pattern proven; planner just needs to re-run the same `curl ifconfig.me --interface 10.10.110.226` style probe |
| Per-cycle metric extraction | Custom SQL | `remote_sqlite_query()` in `scripts/phase196-soak-capture.sh:95-124` | Already filters to the five Phase 197-aware metric names |

**Key insight:** Phase 197 already paid the engineering cost of making Phase 198
mostly-mechanical. The biggest planner risk is reinventing helpers that exist;
the second biggest is treating the deployment-proof step as cosmetic and
shipping a soak against a stale process.

## Runtime State Inventory

> Phase 198 is a validation phase, not a rename/refactor. This section is
> nonetheless useful because Phase 197 added attributes/constants that exist
> only in restarted process memory, and stale state at restart time would
> silently invalidate the soak.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `metrics-spectrum.db` accumulating 74-88k raw rows / 24h on cake-shaper. New metric `wanctl_arbitration_refractory_active` will appear ONLY after Phase 197 binary restart. | Verify post-restart: `SELECT COUNT(*) FROM metrics WHERE metric_name='wanctl_arbitration_refractory_active' AND timestamp >= <restart_ts>` returns nonzero |
| Live service config | `/etc/wanctl/spectrum.yaml` already has `cake_signal.enabled=true` since Phase 196 B-leg start | Verify: `curl /health \| jq '.wans[0].cake_signal.enabled == true'` |
| OS-registered state | `wanctl@spectrum.service` running on cake-shaper | Verify after deploy: `systemctl status wanctl@spectrum.service` shows started AFTER deploy timestamp |
| Secrets / env vars | `/etc/wanctl/secrets` (untouched by Phase 198) | None — Phase 198 doesn't read or rotate secrets |
| Build artifacts / installed packages | `/opt/wanctl/` rsynced from Phase 197 commit; `/opt/wanctl/__pycache__/` may hold stale `.pyc` from Phase 196 build | A clean restart clears `__pycache__` only on Python's normal stale-detection. Phase 197 SUMMARY shows ruff/mypy passed clean, so a `rm -rf /opt/wanctl/__pycache__/` precaution is acceptable but not required since Python recompiles on import |

**Nothing found in category secrets/env vars:** None — Phase 198 does not
introduce or rotate any secrets; SOPS keys remain unchanged.

## Common Pitfalls

### Pitfall 1: Wrong source bind on flent
**What goes wrong:** flent runs with default routing or the wrong `--local-bind`, exits via the wrong WAN, and produces invalid throughput data.
**Why it happens:** Phase 196 already shipped this once: the first two B-leg captures used `10.10.110.233` and exited AT&T despite being labeled `wan=spectrum`. Median was 73.92 Mbps — completely wrong baseline.
**How to avoid:** Before each of the three flent runs, verify egress with a `curl --interface 10.10.110.226 https://ifconfig.me` style probe and assert the public IP belongs to Charter Communications (org `AS11427`). Pattern proven in `source-bind-egress-proof.json`.
**Warning signs:** Public IP starts with `99.126.115.*` (AT&T Lightspeed) or hostname contains `lightspeed.snantx.sbcglobal.net`.

### Pitfall 2: Process running Phase 196 code while disk has Phase 197
**What goes wrong:** rsync deploys new code, but `wanctl@spectrum.service` is not restarted; old process keeps running without `_dl_arbitration_used_refractory_snapshot`. New metric never appears, audit predicate sees 0 rows for `wanctl_arbitration_refractory_active`, refractory windows still drop to RTT, throughput still fails at ~307 Mbps.
**Why it happens:** SIGUSR1 reloads config but does not reload Python module state. `196-MODE-GATE.md:13` already documented this for the mode gate. Same logic applies to code deploys.
**How to avoid:** Deployment proof must record (a) git rev-parse of `/opt/wanctl/` matches the Phase 197 ship commit, AND (b) `systemctl show wanctl@spectrum.service --property=ActiveEnterTimestamp` is AFTER the rsync timestamp, AND (c) `/health` returns 200 with `signal_arbitration.refractory_active` field present (defaults `false`, but the KEY must exist).
**Warning signs:** `jq -e '.wans[0].signal_arbitration | has("refractory_active")'` returns false.

### Pitfall 3: Audit predicate counts 1-minute aggregate rows
**What goes wrong:** Phase 196-07 audit failed closed at 153 non-queue samples. 147 of those were 1-minute aggregate rows where the categorical encoding averaged to ~1.0008 (near-1 but not exactly 1). False failure.
**Why it happens:** SQLite store contains both `granularity = 'raw'` and `granularity = '1m'` rows; aggregating categorical metrics is meaningless.
**How to avoid:** The Phase 197 predicate explicitly filters `granularity = 'raw'` (`primary-signal-audit-phase197.md:60-65`). The capture script's `remote_sqlite_query()` does NOT include a `granularity` column filter — the audit script (downstream) must filter. Confirm the raw psv output includes a granularity column or filter at audit time.
**Warning signs:** Audit reports >100 non-queue samples but the 6-row pattern of "1 RTT-primary alongside 19 queue-primary at the same second" from `raw-only-primary-signal-audit.json:16-44` is not visible.

### Pitfall 4: Loaded-window definition is unclear
**What goes wrong:** Success Criterion 1 says "≥95% of loaded-window samples show queue primary" but "loaded window" needs an operational definition.
**Why it happens:** The 24h soak is mostly idle. The flent `tcp_12down` runs themselves are the canonical load. Sampling rate during load is critical for statistical validity.
**How to avoid:** Define loaded window as `[flent_start_ts, flent_end_ts]` for each of the three runs. With 50ms cycle interval and 30s flent, expect ~600 raw cycles per run × 3 = ~1800 raw active_primary rows during load. Health samples at start/finish capture won't suffice for this — need either continuous health polling during flent, or post-hoc SQLite query bracketed by flent run timestamps.
**Warning signs:** Audit returns <100 raw samples in loaded window — sampling not dense enough to make the 95% claim statistically meaningful.

### Pitfall 5: SAFE-05 source-tree drift between Phase 197 ship and Phase 198
**What goes wrong:** Some unrelated commit lands in `src/wanctl/queue_controller.py` between Phase 197 ship and Phase 198 verification. SAFE-05 fails not because of Phase 198 work, but because of unrelated drift.
**Why it happens:** Tag/commit boundaries are not enforced unless explicitly checked.
**How to avoid:** Capture the Phase 197 ship commit SHA at the start of Phase 198 (probably `068b804` based on 197-02-SUMMARY.md task commits — verify via `git log --oneline | grep -i "phase 197"`). Do `git diff <phase-197-ship-sha>..HEAD -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` and require empty output.
**Warning signs:** Unexpected lines in the diff — investigate before claiming SAFE-05.

## Code Examples (verified against repository)

### 1. Source-bind egress verification (Pitfall 1 mitigation)

```bash
# Verify 10.10.110.226 exits Spectrum (Charter, AS11427).
# Run from operator dev machine BEFORE each flent capture.
EGRESS_JSON=$(curl --silent --max-time 10 --interface 10.10.110.226 \
    https://ipinfo.io/json)
echo "$EGRESS_JSON" | jq -e '.org | test("Charter|AS11427")'
EGRESS_IP=$(echo "$EGRESS_JSON" | jq -r '.ip')
test "$EGRESS_IP" != "99.126.115.47"  # known AT&T public IP from source-bind proof
echo "Spectrum egress confirmed: $EGRESS_IP"
```

Source: pattern from `source-bind-egress-proof.json` and `196-MODE-GATE.md`.

### 2. Phase 197 deployment proof on cake-shaper

```bash
# (a) Source-on-disk matches Phase 197 ship commit
PHASE_197_SHIP_SHA=$(git log --oneline --grep="Phase 197 Plan 02" -n1 | awk '{print $1}')
ssh -o BatchMode=yes "$PHASE196_SPECTRUM_SSH_HOST" \
    "cd /opt/wanctl && git rev-parse --short HEAD" \
    | grep -qx "$PHASE_197_SHIP_SHA"

# (b) Service was restarted after deploy
ssh -o BatchMode=yes "$PHASE196_SPECTRUM_SSH_HOST" \
    "systemctl show wanctl@spectrum.service --property=ActiveEnterTimestamp"

# (c) /health exposes Phase 197 fields
curl --silent --fail --max-time 5 "$PHASE196_SPECTRUM_HEALTH_URL" \
    | jq -e '.wans[0].signal_arbitration | has("refractory_active") and has("control_decision_reason")'

# (d) New metric is being emitted
ssh -o BatchMode=yes "$PHASE196_SPECTRUM_SSH_HOST" \
    "sudo -n sqlite3 -readonly '$PHASE196_SPECTRUM_METRICS_DB' \
     \"SELECT COUNT(*) FROM metrics WHERE metric_name='wanctl_arbitration_refractory_active' \
       AND timestamp >= strftime('%s', 'now', '-1 hour');\"" \
    | awk '$1 > 0 {print "ok"}'
```

Sources: `wan_controller.py:88-95`, `wan_controller.py:3081-3090`,
`health_check.py:779-786`, `scripts/phase196-soak-capture.sh:103-104`.

### 3. Phase 197-aware audit predicate (run as a Python or jq script over raw psv)

```python
# Pseudocode — input is psv from scripts/phase196-soak-capture.sh.
# Filter to granularity='raw' rows (1-minute aggregates excluded by query above
# only by the timestamp filter — granularity column needs explicit filter
# either in the SQL or in the audit script).

ACCEPT_LIST_QUEUE = {"queue_distress", "green_stable", "queue_during_refractory"}

def classify_metric_row(row: dict) -> str:
    """Classify per-cycle SQLite metric row. Caller must pre-filter to raw rows."""
    primary = row["wanctl_arbitration_active_primary"]
    refractory = row.get("wanctl_arbitration_refractory_active", 0.0)
    if primary == 1.0:
        return "metric_queue_samples"
    if primary == 2.0 and refractory == 1.0:
        return "metric_queue_samples_via_refractory_rtt_fallback"
    return "metric_non_queue_samples"

def classify_health_sample(sample: dict) -> str:
    arb = sample["signal_arbitration"]
    if (arb["active_primary_signal"] == "queue"
        and arb["control_decision_reason"] in ACCEPT_LIST_QUEUE):
        return "queue_primary"
    if (arb["control_decision_reason"] == "rtt_fallback_during_refractory"
        and arb.get("refractory_active") is True):
        return "queue_primary_refractory_rtt_fallback"
    return "non_queue"
```

Source: `primary-signal-audit-phase197.md:14-75`.

### 4. Three-run flent acceptance (VALN-05a)

```bash
# Run from operator dev machine, after deployment proof + source-bind verification.
# Three runs with 30s duration each, sequential not concurrent.
for i in 1 2 3; do
    ./scripts/phase191-flent-capture.sh \
        --label "phase198_cake_primary_tcp12_run${i}" \
        --wan spectrum \
        --local-bind 10.10.110.226 \
        --duration 30 \
        --output-dir ~/flent-results/phase198 \
        --tests tcp_12down \
        --ref "$(cd ~/projects/wanctl && git rev-parse --short HEAD)"
done

# Parse medians from each run's summary.txt; compute median-of-medians.
# Acceptance: at least 2 of (m1, m2, m3) >= 532 AND median(m1, m2, m3) >= 532.
```

Sources: `scripts/phase191-flent-capture.sh:55-99,147-187`, ROADMAP Success
Criterion 2.

### 5. SAFE-05 source-tree diff target list

```bash
# Run from local repo. Must be empty for SAFE-05 to pass.
PHASE_197_SHIP_SHA=$(git log --oneline --grep="Phase 197 Plan 02" -n1 | awk '{print $1}')
git diff "${PHASE_197_SHIP_SHA}..HEAD" -- \
    src/wanctl/queue_controller.py \
    src/wanctl/cake_signal.py \
    src/wanctl/fusion_healer.py \
    src/wanctl/wan_controller.py \
    src/wanctl/health_check.py
```

Source: `196-PREFLIGHT.md:39-44` plus Phase 197 added `health_check.py` to the
implicit no-touch list (Phase 197 modifications are now the baseline). The
planner should treat the post-197 commit state as the new baseline; only files
listed above need a clean diff for SAFE-05.

### 6. Proposed `ab-comparison.json` schema

No prior phase produced an `ab-comparison.json` — Phase 196 listed it as
required but it was never created (`196-VERIFICATION.md:217`,
`throughput-spectrum-corrected-summary.json` blocked it). Phase 198 is
producing this artifact for the first time. Recommended schema:

```json
{
  "phase": 198,
  "comparator": {
    "a_leg": {
      "leg": "rtt-blend",
      "phase": 196,
      "manifest": ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/manifest.json",
      "primary_signal_audit": ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/primary-signal-audit.json",
      "duration_hours": 28.2311,
      "metric_total_samples": 88373,
      "metric_rtt_samples": 88373,
      "metric_non_rtt_samples": 0
    },
    "b_leg": {
      "leg": "cake-primary",
      "phase": 198,
      "manifest": "./manifest.json",
      "primary_signal_audit": "./primary-signal-audit.json",
      "duration_hours": <captured>,
      "metric_total_samples": <captured>,
      "metric_queue_samples": <captured>,
      "metric_queue_samples_via_refractory_rtt_fallback": <captured>,
      "metric_non_queue_samples": <captured>
    }
  },
  "deltas": {
    "rtt_distress_event_counts": {
      "a_leg": <int from journal "rtt_veto"|"healer_bypass" + dwell-bypass log>,
      "b_leg": <int>,
      "delta": <b_leg - a_leg>,
      "verdict": "pass | fail",
      "rule": "b_leg <= a_leg (cake-primary must NOT grow RTT-distress events vs rtt-blend)"
    },
    "burst_trigger_counts": {
      "a_leg": <int from /health.download.burst.trigger_count finish - start>,
      "b_leg": <int>,
      "delta": <int>,
      "verdict": "pass | fail",
      "rule": "b_leg burst counts at least as healthy as a_leg (i.e., not materially higher)"
    },
    "dwell_bypass_responsiveness": {
      "a_leg_count": <int from /health.download.hysteresis.dwell_bypassed_count finish - start>,
      "b_leg_count": <int>,
      "delta": <int>,
      "verdict": "pass | fail",
      "rule": "b_leg responsive enough that dwell_bypassed_count does not balloon vs a_leg"
    },
    "fusion_state_transitions": {
      "a_leg": <int from journal "Fusion healer.*->" line count>,
      "b_leg": <int>,
      "delta": <int>,
      "verdict": "pass | fail",
      "rule": "b_leg fusion stability at least as healthy as a_leg"
    },
    "queue_primary_coverage_pct": {
      "a_leg_pct": 0.0,
      "b_leg_pct": <(metric_queue_samples + metric_queue_samples_via_refractory_rtt_fallback) / metric_total_samples * 100>,
      "verdict": "pass | fail",
      "rule": "b_leg >= 99.9% (Phase 196 raw audit had 74691/74697 = 99.992%)"
    },
    "refractory_fallback_rate": {
      "b_leg_count": <metric_queue_samples_via_refractory_rtt_fallback>,
      "b_leg_total": <metric_total_samples>,
      "rate": <count / total>,
      "verdict": "documented",
      "rule": "documented exception bucket; rate is reported, not gated. Phase 197 design accepts this."
    }
  },
  "throughput": {
    "spectrum_tcp12_runs": [
      {"run": 1, "median_mbps": <float>, "raw_path": "..."},
      {"run": 2, "median_mbps": <float>, "raw_path": "..."},
      {"run": 3, "median_mbps": <float>, "raw_path": "..."}
    ],
    "median_of_medians_mbps": <float>,
    "two_of_three_at_or_above_532_mbps": <bool>,
    "median_of_medians_at_or_above_532_mbps": <bool>,
    "verdict": "pass | fail",
    "rule": "VALN-05a: 2-of-3 individual medians >= 532 AND median-of-medians >= 532"
  },
  "comparison_verdict": "pass | fail",
  "comparison_rule": "All operational counter deltas pass AND throughput verdict is pass."
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single accept-list `{queue_distress, green_stable}` for primary-signal audit (Phase 196-07) | Three-value accept-list + separate `rtt_fallback_during_refractory` regime bucket + raw-only filter | Phase 197 (`primary-signal-audit-phase197.md`) | Refractory-driven RTT fallback no longer counts as a verdict failure; aggregate rows excluded |
| Single flent run for VALN-05 acceptance | Three-run, 2-of-3 + median-of-medians (VALN-05a) | Phase 198 (this phase) | Resilient to single-run link variance; Phase 196 produced the prior failure precedent |
| `signal_arbitration` block ends at `control_decision_reason` | Adds `refractory_active` boolean | Phase 197 (`health_check.py:779-786`) | Audit can distinguish refractory regime without recomputing from `_dl_refractory_remaining` |
| Single primary metric `wanctl_arbitration_active_primary` | Plus `wanctl_arbitration_refractory_active` (DL-only) | Phase 197 (`wan_controller.py:3081-3090`) | Categorical regime classification at SQLite-row granularity |

**Deprecated/outdated:**
- Treating `value=2.0` (RTT) raw rows during refractory as a verdict failure — superseded by Phase 197 audit predicate (regime bucket).
- Phase 196 A-leg flent throughput numbers as Spectrum baseline — invalidated by `source-bind-egress-proof.json`. They remain valid as A-leg control evidence only because the soak counters (not the throughput numbers) are what Phase 198 reuses.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 197 ship commit is the latest commit on `main` whose subject contains "Phase 197" — operator should confirm exact SHA at preflight time | Pitfall 5, Code Example 5 | If wrong SHA, SAFE-05 diff window is wrong; could mask drift or false-fail |
| A2 | `cake_signal.enabled=true` is currently set in `/etc/wanctl/spectrum.yaml` because Phase 196 mode-gate procedure restored cake-primary at the end | Pattern: Mode-gate is already-set | If operator manually toggled it back to rtt-blend, plan must restore before deploy. Verify via `/health.wans[0].cake_signal.enabled` |
| A3 | `metrics-spectrum.db` SQLite has a `granularity` column that distinguishes raw from 1m-aggregated rows (implied by Phase 197 audit predicate but not directly inspected in this research) | Code Example 3, Pitfall 3 | If schema differs, audit must use a different filter (e.g., timestamp uniqueness or row count against expected raw rate) |
| A4 | The three flent runs themselves provide enough load to sustain refractory windows during the loaded portion. Phase 196 runs at 30s duration produced 151 samples per run (`throughput-spectrum-corrected-summary.json:11`), implying sufficient density. | Pitfall 4 | If load is too brief to trigger refractory, the queue-primary-during-refractory invariant won't be exercised — but throughput would also pass trivially if no refractory event occurs |
| A5 | `ipinfo.io` (or equivalent) is reachable from the dev machine for source-bind verification | Code Example 1 | If not, alternate probe: SSH to a known-Spectrum reflector and verify peer IP |

**If this table feels long:** A1 and A3 are the most important. A1 is trivial to verify (`git log`), A3 is verifiable by inspecting one PSV from a recent capture. The planner should resolve both before plan execution starts.

## Open Questions

1. **Should Phase 198 do a fresh `systemctl restart wanctl@spectrum.service` even if production has been continuously running cake-primary since Phase 196 B-leg start?**
   - What we know: Phase 197 binary needs to be on disk + loaded into process memory.
   - What's unclear: Whether the Phase 197 binary is already deployed (it ships when 197 closeout merged to main; deploy.sh still needs to run on cake-shaper).
   - Recommendation: Deployment proof MUST verify both (a) git rev on `/opt/wanctl/` matches Phase 197 ship SHA AND (b) `ActiveEnterTimestamp` is after rsync. If either fails, rsync + restart is the fix; if both pass, no second restart needed.

2. **Does the SQLite `metrics` table have a `granularity` column, or do we need to identify raw rows by timestamp pattern?**
   - What we know: Phase 197 audit predicate document specifies `granularity = 'raw'` filter. The capture script's SQL queries don't reference `granularity`.
   - What's unclear: Whether `granularity` is a SQL column or part of a row metadata.
   - Recommendation: Plan 01 inspects the schema once and pins the filter form in plan-01 evidence (single SSH + `sqlite3 .schema metrics`). All downstream audits use the pinned form.

3. **Should the operator open a new Phase 198 deployment token, or continue using the Phase 196 token?**
   - What we know: ROADMAP says "same Spectrum deployment token used for the accepted Phase 196 rtt-blend A-leg" → `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`.
   - What's unclear: Token reuse is operationally fine, but Phase 197 deployment is a code change; whether that constitutes a "new token" for VALN-04 purposes.
   - Recommendation: Use the same token. The deployment-proof captures the new code SHA, which is sufficient version distinction. ROADMAP wording ("same deployment token") supports this.

4. **Does flent's `--local-bind` actually steer egress, or just bind the source IP without affecting routing decisions?**
   - What we know: Phase 196 source-bind-egress-proof.json proved that `10.10.110.226` egresses through Spectrum AND `10.10.110.233` egresses through AT&T. So policy routing is in place upstream.
   - What's unclear: Whether the dev machine has a fresh routing table since Phase 196 (e.g., a `wg` or `tailscale` change could break it).
   - Recommendation: Pre-each-run egress verification (Code Example 1) catches this. Don't assume routing is unchanged.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `flent` (dev machine) | VALN-05a tcp_12down runs | unknown — verify | — | None — phase blocked without it |
| `netperf` (dev machine) | flent backend | unknown — verify | — | None — phase blocked without it |
| `dallas` netperf server reachable | flent destination | known good (Phase 191/196 used it) | — | Alternate flent server with comparable BDP |
| `curl`, `jq`, `ssh`, `git` (dev) | preflight + audit + deploy proof | system standard | — | None |
| `sqlite3` on `cake-shaper` | metric queries | proven in Phase 196 | — | None — capture script requires it |
| `~/.venv` Python 3.11+ | optional flent summary parsing | project standard | 3.11 | Use Python module on dev machine |
| Phase 197 binary deployed at `/opt/wanctl/` | every part of soak | unknown — verify in Plan 01 | should match Phase 197 ship SHA | Re-run `./scripts/deploy.sh` (may not exist on cake-shaper as one-shot) |
| `10.10.110.226` configured on dev machine | flent source bind | proven in Phase 196-12 | — | Configure if missing — operator action |

**Missing dependencies with no fallback:** flent and netperf must be on the dev machine. Phase 191 used them, so likely already present, but planner must include a `command -v flent` precheck.

**Missing dependencies with fallback:** None.

## Validation Architecture

> Phase 198 is operator-evidence validation, not pytest validation.
> `nyquist_validation` should remain enabled; this section maps phase
> requirements to the runnable checks.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest via project virtualenv (regression slice) + shell + operator evidence |
| Config file | `pyproject.toml` |
| Quick run command | `bash -n scripts/phase196-soak-capture.sh && bash -n scripts/phase191-flent-capture.sh` |
| Full suite command | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py tests/test_phase_197_replay.py tests/test_fusion_healer.py -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VALN-04 | Spectrum cake-primary B-leg primary-signal audit verdict pass under Phase 197 predicate | manual + scripted audit | `./scripts/phase196-soak-capture.sh cake-primary-finish` then run audit predicate over raw psv | helper exists |
| VALN-04 | A/B comparison emits `ab-comparison.json` with all 6 deltas + comparison_verdict | scripted | New audit/comparison script (or jq pipeline) reading rtt-blend artifacts + cake-primary artifacts | new — Plan 04 produces |
| VALN-05a | 2-of-3 Spectrum tcp_12down medians ≥532 Mbps AND median-of-medians ≥532 Mbps | manual + scripted parse | `scripts/phase191-flent-capture.sh ... --tests tcp_12down --duration 30` × 3, then median parser | helper exists |
| SAFE-05 | No protected-file diff between Phase 197 ship and Phase 198 closeout | scripted | `git diff ${PHASE_197_SHIP_SHA}..HEAD -- <files>` returns empty | command standard |
| Deployment proof | Phase 197 binary actually running on `wanctl@spectrum.service` | scripted | jq + ssh checks per Code Example 2 | new — Plan 01 produces |
| Source-bind | `10.10.110.226` exits Spectrum (Charter, AS11427) | scripted | Code Example 1 (`curl --interface ... ipinfo.io`) | new — Plan 03 produces |

### Sampling Rate
- **Per task commit:** `bash -n` on any modified shell helper; `.venv/bin/pytest -o addopts='' tests/test_phase_197_replay.py -q` if controller code is touched (it should NOT be — SAFE-05).
- **Per wave merge:** Full suite command above.
- **Phase gate:** Full suite green AND all soak/flent/audit artifacts produced AND `ab-comparison.json` verdict pass before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] None — Phase 197 already shipped: capture script Phase-197-aware (`scripts/phase196-soak-capture.sh:116,148,219`), audit predicate documented (`primary-signal-audit-phase197.md`), Phase 197 replay tests in `tests/test_phase_197_replay.py`, all needed helpers exist.
- [ ] Optional: a thin wrapper script `scripts/phase198-flent-3run.sh` that runs `phase191-flent-capture.sh` three times and parses medians into a single summary JSON. Not required — operator can run sequentially. Add only if it reduces operator error.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (operator SSH) | SSH key auth to `cake-shaper`; `BatchMode=yes` rejects interactive prompts |
| V3 Session Management | no | No web sessions involved |
| V4 Access Control | yes (sudo on cake-shaper for sqlite + journal) | `sudo -n` (non-interactive) — operator must have sudoers entry; capture script already follows this pattern |
| V5 Input Validation | yes (capture script env vars) | Existing `require_var` / `require_command` checks in `scripts/phase196-soak-capture.sh:34-49` |
| V6 Cryptography | no | Phase 198 doesn't introduce crypto |

### Known Threat Patterns for soak capture

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator commits secrets in evidence (e.g., `/etc/wanctl/secrets` content in journal log) | Information Disclosure | Capture script already filters journal lines with `grep -E` to known control-related patterns; operator review of every `*-summary.json` and `*-journal.log` before commit |
| Operator runs flent during a concurrent Spectrum experiment, polluting evidence | Tampering | Mode-gate document already requires "no concurrent Spectrum experiment" operator confirmation; preflight assertion required |
| Stale Phase 196 binary running but operator believes Phase 197 is deployed | Spoofing | Deployment proof (Code Example 2) explicitly checks `ActiveEnterTimestamp` and presence of new fields |
| `ssh` to wrong host (e.g., att-shaper instead of cake-shaper) | Tampering | `PHASE196_SPECTRUM_SSH_HOST` env var + capture script's required-var assertions |

## Sources

### Primary (HIGH confidence)
- `src/wanctl/wan_controller.py:88-95` (Phase 197 reason constants)
- `src/wanctl/wan_controller.py:691-696` (`_dl_arbitration_used_refractory_snapshot` init)
- `src/wanctl/wan_controller.py:2677-2739` (`_select_dl_primary_scalar_ms` Phase 197 branches)
- `src/wanctl/wan_controller.py:3081-3090` (refractory metric emission)
- `src/wanctl/health_check.py:779-786` (refractory_active relay)
- `scripts/phase196-soak-capture.sh:1-281` (capture helper, Phase 197-aware)
- `scripts/phase191-flent-capture.sh:1-192` (flent helper)
- `.planning/phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-CONTEXT.md` (Phase 197 decisions)
- `.planning/phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-VERIFICATION.md` (Phase 197 closeout)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md` (audit predicate)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-MODE-GATE.md` (mode toggle procedure)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/source-bind-egress-proof.json` (egress evidence)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md` (Phase 196 status)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/primary-signal-audit.json` (A-leg control evidence)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-12-SUMMARY.md` (root cause Phase 197 was built to fix)
- `.planning/REQUIREMENTS.md` (VALN-04, VALN-05a, SAFE-05 wording)
- `.planning/ROADMAP.md` (Phase 198 entry, success criteria)

### Secondary (MEDIUM confidence)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/raw-only-primary-signal-audit.json` (74691/74697 raw queue metric pattern from B-leg)
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-RESEARCH.md` (operational evidence shape conventions)

### Tertiary (LOW confidence)
- None — all claims trace to repository files inspected this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all helpers proven in Phase 196/197
- Architecture: HIGH — entire Phase 198 sits on top of already-shipped infrastructure
- Pitfalls: HIGH — every pitfall traces to a documented Phase 196 failure mode
- Audit predicate: HIGH — Phase 197 already locked the predicate document
- ab-comparison schema: MEDIUM — no prior precedent in the repo, schema proposed here. Planner can adjust field names.

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days; valid as long as no SAFE-05 drift occurs)

---

## RESEARCH COMPLETE

**Phase:** 198 - Spectrum cake-primary B-leg rerun on Phase 197 build
**Confidence:** HIGH

Phase 198 is mostly mechanical — Phase 197 already shipped the controller fix,
the Phase-197-aware capture script, and the audit predicate document. The
remaining work is operator procedure (deployment proof, 24h soak, three flent
runs with corrected source bind, ab-comparison.json emission, SAFE-05 diff)
plus 198-VERIFICATION.md.

### Key Findings

- All required tooling exists; no new helper scripts are mandatory (one optional 3-run flent wrapper).
- Phase 197 audit predicate (`primary-signal-audit-phase197.md`) is the contract — accept-list `{queue_distress, green_stable, queue_during_refractory}`, separate `rtt_fallback_during_refractory + refractory_active=true` regime bucket, raw-only metric filter.
- Phase 196 rtt-blend A-leg control evidence (88373/88373 RTT-primary samples, 28.2311h) is reused as the comparator; A-leg flent throughput numbers are NOT reused (wrong source bind per `source-bind-egress-proof.json`).
- Three biggest planner risks: (1) running soak against stale Phase 196 process — deployment proof must verify `ActiveEnterTimestamp` and presence of new `/health` fields; (2) flent egress drift — pre-run `curl --interface 10.10.110.226 ipinfo.io` egress check is mandatory; (3) audit predicate counting 1-minute aggregate rows — must filter `granularity='raw'`.
- `ab-comparison.json` has no prior repository precedent — proposed schema covers all 6 deltas (RTT-distress events, burst triggers, dwell-bypass, fusion transitions, queue-primary coverage, refractory fallback rate) plus the three-run throughput acceptance.
- Recommended plan structure: 4 plans (Preflight + Deployment Proof, 24h Soak + Audit, 3-run Flent + Acceptance, A/B Comparison + Closeout).

### File Created
`.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack (helpers) | HIGH | Both phase196-soak-capture.sh and phase191-flent-capture.sh exist, are bash-syntax-clean, and were used in Phase 196/197 |
| Architecture | HIGH | Phase 197 closeout already wired the data path end-to-end; 198 is observational |
| Audit predicate | HIGH | Locked document at primary-signal-audit-phase197.md |
| ab-comparison schema | MEDIUM | First-of-its-kind in this repo; planner may adjust field shapes |
| Open question on `granularity` SQL column | MEDIUM | Plan 01 should pin the filter form once via `sqlite3 .schema metrics` |

### Open Questions Forwarded to Planner
1. Identify the exact Phase 197 ship commit SHA at preflight time (`git log --oneline | grep "Phase 197"`).
2. Inspect SQLite metrics schema once to pin the raw-row filter (column or timestamp-pattern).
3. Decide whether Phase 198 uses the same operator deployment token as Phase 196 (recommend YES per ROADMAP wording).
4. Decide whether to add a thin 3-run flent wrapper script (optional, planner discretion).

### Ready for Planning
Research complete. Planner can now create PLAN.md files. Recommend 4 plans matching the workstream split documented under "Architecture Patterns → Recommended Output Structure" and "Validation Architecture → Phase Requirements → Test Map".
