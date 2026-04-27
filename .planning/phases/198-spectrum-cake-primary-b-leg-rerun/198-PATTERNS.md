# Phase 198: Spectrum cake-primary B-leg rerun on Phase 197 build — Pattern Map

**Mapped:** 2026-04-27
**Phase type:** OPERATIONAL — evidence/validation only. SAFE-05 forbids any source code change under `src/wanctl/`.
**Files (artifacts) classified:** 9 + (3 flent.gz)
**Analogs found:** 8 / 9 (one new artifact — `ab-comparison.json` — has no prior precedent in repo)

---

## Scope Note (read first)

Phase 198 produces **operator evidence artifacts**, not source code. Every "modified" item below is either:
- A JSON evidence file under `.planning/phases/198-*/soak/cake-primary/`,
- A flent raw capture (`.flent.gz`) under `.planning/phases/198-*/soak/cake-primary/flent/`,
- A markdown verification document at the phase root,
- (Optional) a thin shell wrapper under `scripts/` that orchestrates existing helpers — it MUST NOT touch controller code.

The planner does **not** plan Python changes. SAFE-05 is enforced by `safe05-diff.json` (item 7).

---

## File Classification

| New / Modified Artifact | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `soak/cake-primary/preflight.json` (Plan 01) | evidence (preflight summary) | batch JSON write | `196/soak/preflight/preflight-20260425T044045Z-summary.json` + `196/soak/preflight/mode-gate-proof.json` | role-match (compose deployment-proof + mode-already-set fields into one) |
| `soak/cake-primary/source-bind-egress-proof.json` | evidence (egress probe result) | batch JSON write | `196/soak/cake-primary/source-bind-egress-proof.json` | exact (re-emit same schema with fresh probe timestamps) |
| `soak/cake-primary/wanctl.sqlite` | data (SQLite metrics snapshot) | file-I/O (snapshot) | NONE — Phase 196 captured `.psv` exports via `phase196-soak-capture.sh`, not the raw `.sqlite` file | partial — recommend KEEPING `.psv` lineage (capture script already emits it). If a true `.sqlite` copy is required, scp from `/var/lib/wanctl/<spectrum-metrics-db>` after the soak finish-capture |
| `soak/cake-primary/primary-signal-audit-phase197.json` (Plan 02) | evidence (audit verdict) | batch-classify | `196/soak/cake-primary/raw-only-primary-signal-audit.json` (schema) + `primary-signal-audit-phase197.md` (predicate contract) | exact for schema; predicate is the new Phase 197 form |
| `soak/cake-primary/flent/*.flent.gz` (3 runs) | data (raw flent capture) | file-I/O (subprocess output) | `196/soak/cake-primary/throughput-spectrum-corrected-summary.json` + `~/flent-results/phase196/.../tcp_12down-*.flent.gz` | exact (same `phase191-flent-capture.sh --local-bind 10.10.110.226 --tests tcp_12down --duration 30`) |
| `soak/cake-primary/throughput-verdict.json` | evidence (3-run aggregate verdict) | batch JSON write | `196/soak/cake-primary/throughput-spectrum-corrected-summary.json` (single-run shape) | role-match (extends single-run shape to 3-run + median-of-medians + 2-of-3 acceptance) |
| `ab-comparison.json` (Plan 04) | evidence (cross-leg delta) | batch JSON write | NONE in repo (research §"Code Examples §6" notes Phase 196 listed but never emitted it) | NEW — use schema from `198-RESEARCH.md:399-490` |
| `safe05-diff.json` (Plan 04) | evidence (source-tree diff verdict) | batch JSON write + `git diff` | NONE in repo as a JSON artifact; the established pattern is `git diff --quiet` exit-code evidence in `196-PREFLIGHT.md:39-46` and `196-VERIFICATION.md:64-66` | role-match (wrap existing pattern in JSON; planner defines schema below) |
| `198-VERIFICATION.md` (Plan 04) | evidence (phase closeout) | document | `197/197-VERIFICATION.md` | exact (verbatim YAML-frontmatter + 11-truth table form) |
| `scripts/phase198-flent-3run.sh` (OPTIONAL) | shell helper | event-driven (3x sequential subprocess) | `scripts/phase191-flent-capture.sh` + `scripts/phase196-soak-capture.sh` | role-match (thin wrapper — three loop iterations of `phase191-flent-capture.sh`, no controller code touched) |

---

## Pattern Assignments

### 1. `soak/cake-primary/preflight.json` (evidence, batch JSON write)

**Analog A (per-capture summary shape):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/preflight-20260425T044045Z-summary.json`

**Per-capture summary fields to mirror** (lines 1-28):

```json
{
  "mode": "preflight",
  "capture_group": "preflight",
  "wan_name": "spectrum",
  "captured_at_iso": "2026-04-25T04:40:45Z",
  "artifacts": { "health_json": "...", "journal_excerpt": "...", "fusion_transitions": "...",
                 "sqlite_metrics": "...", "sqlite_metrics_aggregate": "..." },
  "signal_arbitration": {
    "active_primary_signal": "queue",
    "rtt_confidence": 0.0,
    "cake_av_delay_delta_us": 4,
    "control_decision_reason": "green_stable"
  },
  "counters": { "dwell_bypassed_count": 0, "download_burst_trigger_count": 0,
                "upload_burst_trigger_count": 0, "fusion_transition_count_24h": 0,
                "sqlite_metric_rows": 283811, "sqlite_metric_aggregate_rows": 4,
                "journal_excerpt_lines": 5992 }
}
```

This is what `scripts/phase196-soak-capture.sh preflight` already emits. Phase 198 invokes it the same way.

**Analog B (mode-gate / deployment-proof composition):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/mode-gate-proof.json` (lines 1-20):

```json
{
  "gate_name": "spectrum-cake-signal-enabled-toggle",
  "rtt_blend": { "cake_signal_enabled": false, "active_primary_signal": "rtt",
                 "wanctl_arbitration_active_primary": 2, "capture_summary_path": "..." },
  "cake_primary": { "cake_signal_enabled": true, "active_primary_signal": "queue",
                    "wanctl_arbitration_active_primary": 1, "capture_summary_path": "..." },
  "restored_mode": "cake-primary",
  "mode_gate_verdict": "pass",
  "operator_no_concurrent_spectrum_experiments": true
}
```

**Phase 198 deviation:** Phase 196 mode-gate procedure already restored cake-primary; do NOT re-toggle. Instead, the preflight artifact composes:
- `mode_already_set: true` (verified via `/health.wans[0].cake_signal.enabled == true`)
- `deployment_proof` block (Phase 197 binary on disk + restart timestamp + new `/health` field present + new metric in SQLite — schema below per RESEARCH §"Code Example 2")

**Recommended composite schema (additive to capture-summary fields):**

```json
{
  "phase": 198,
  "mode_already_set": true,
  "deployment_proof": {
    "phase_197_ship_sha": "<short-sha-from-git-log>",
    "deployed_sha_on_cake_shaper": "<short-sha-from-/opt/wanctl/>",
    "sha_match": true,
    "service_active_enter_timestamp_utc": "<ISO 8601>",
    "rsync_timestamp_utc": "<ISO 8601 — must precede ActiveEnterTimestamp>",
    "restart_after_deploy": true,
    "health_has_refractory_active_field": true,
    "metric_wanctl_arbitration_refractory_active_recent_count": <int>
  },
  "operator_no_concurrent_spectrum_experiments": true,
  "preflight_capture_summary_path": "<path to phase196-soak-capture.sh preflight output>",
  "verdict": "pass"
}
```

---

### 2. `soak/cake-primary/source-bind-egress-proof.json` (evidence, batch JSON write)

**Analog (exact):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/source-bind-egress-proof.json` (lines 1-21):

```json
{
  "captured_at_utc": "2026-04-27T09:53:15Z",
  "purpose": "Verify which WAN each local source address uses before judging Phase 196 throughput evidence.",
  "checks": [
    { "local_bind": "10.10.110.233", "public_ip": "99.126.115.47",
      "hostname": "99-126-115-47.lightspeed.snantx.sbcglobal.net",
      "org": "AS7018 AT&T Enterprises, LLC", "conclusion": "att-egress" },
    { "local_bind": "10.10.110.226", "public_ip": "70.123.224.169",
      "hostname": "syn-070-123-224-169.res.spectrum.com",
      "org": "AS11427 Charter Communications Inc", "conclusion": "spectrum-egress" }
  ],
  "impact": "..."
}
```

**Phase 198 deviation:** Re-run the probe immediately before each of the three flent captures (RESEARCH §"Pitfall 1"). Either emit one combined file with three timestamped probe blocks, or one file per run. Recommend ONE file with a `pre_run_probes: [...]` array indexed by `run_index ∈ {1,2,3}`. Probe pattern:

```bash
EGRESS_JSON=$(curl --silent --max-time 10 --interface 10.10.110.226 https://ipinfo.io/json)
# assert .org matches Charter|AS11427 and .ip != 99.126.115.*
```

Source: RESEARCH §"Code Example 1".

---

### 3. `soak/cake-primary/wanctl.sqlite` (data, file-I/O snapshot)

**Analog:** NONE in repo. Phase 196 captured **`.psv` exports** via `scripts/phase196-soak-capture.sh:103-122`, not raw `.sqlite` files. The PSV exports already contain the rows needed for the audit predicate.

**Phase 198 recommendation:**

- DEFAULT path: do NOT add a raw `.sqlite` artifact. Re-use the PSV outputs from `scripts/phase196-soak-capture.sh cake-primary-finish` — both `cake-primary-finish-<TS>-sqlite-metrics.psv` (raw rows, filtered to 5 metric names) and `cake-primary-finish-<TS>-sqlite-metrics-aggregate.psv`. These are what the audit predicate consumes.
- IF the planner specifically wants a raw `.sqlite`: add a single `scp` step in Plan 02 after the finish capture, of the form:
  ```bash
  ssh "$PHASE196_SPECTRUM_SSH_HOST" "sudo -n cp '$PHASE196_SPECTRUM_METRICS_DB' /tmp/wanctl-spectrum-198.sqlite \
        && sudo -n chown $(id -u):$(id -g) /tmp/wanctl-spectrum-198.sqlite"
  scp "$PHASE196_SPECTRUM_SSH_HOST:/tmp/wanctl-spectrum-198.sqlite" \
      .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/wanctl.sqlite
  ```
  Note: this is operator-only evidence; downstream audit still keys off the PSV outputs to stay consistent with Phase 196 lineage.

**Bias toward PSV — do not invent a parallel sqlite-only audit path.**

---

### 4. `soak/cake-primary/primary-signal-audit-phase197.json` (evidence, batch-classify)

**Analog A (schema):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/raw-only-primary-signal-audit.json` (lines 1-63). Reuse the field shape:

```json
{
  "leg": "cake-primary",
  "source_audit_path": "...",
  "raw_metrics_path": "...",
  "aggregate_metrics_path": "...",
  "source_window": { "start_utc": "...", "end_utc": "...", "start_timestamp": <int>, "end_timestamp": <int> },
  "raw_metric_total_samples": 74697,
  "raw_metric_queue_samples": 74691,
  "raw_metric_non_queue_samples": 6,
  "raw_metric_non_queue_rate": 0.00008032451102453913,
  "raw_metric_non_queue_timestamps": [
    { "sampled_utc": "...", "timestamp": <int>, "value": 2.0,
      "rows_at_value": 1, "context": "raw row: 1 RTT-primary..." }
  ],
  "aggregate_metric_total_samples": 955,
  "aggregate_metric_note": "1-minute aggregate rows are averages over raw categorical values...",
  "verdict": "pass | pass_with_documented_exceptions | fail",
  "decision": "..."
}
```

**Analog B (predicate contract — MUST follow):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md` (lines 28-40, 60-71):

```jq
ACCEPT_LIST_QUEUE = ["queue_distress", "green_stable", "queue_during_refractory"]

def classify:
  if .active_primary_signal == "queue"
     and (.control_decision_reason | IN($accept_list_queue[]))
  then "queue_primary"
  elif .control_decision_reason == "rtt_fallback_during_refractory"
       and (.refractory_active == true)
  then "queue_primary_refractory_rtt_fallback"
  else "non_queue"
  end ;
```

Raw-row metric classification (lines 60-71):
- `wanctl_arbitration_active_primary == 1.0` → `metric_queue_samples`
- `wanctl_arbitration_active_primary == 2.0` AND `wanctl_arbitration_refractory_active == 1.0` → `metric_queue_samples_via_refractory_rtt_fallback`
- otherwise → `metric_non_queue_samples`

**Phase 198 deviations from the Phase 196 raw-only audit:**

1. **Add the new bucket** `metric_queue_samples_via_refractory_rtt_fallback` to the JSON output (Phase 196 raw-only audit predates this field; on Phase 197 build it WILL be non-zero during loaded windows).
2. **Mandatory `granularity = 'raw'` filter** before counting. The capture script's SQL does NOT filter on `granularity` (`scripts/phase196-soak-capture.sh:106-122`); the audit must filter at parse time. RESEARCH §"Pitfall 3" + Open Question #2 — Plan 01 should pin the schema (`sqlite3 .schema metrics`) once and document whether `granularity` is a column or part of `metric_name`.
3. **New optional `loaded_window` block** carrying per-flent-run sample counts (RESEARCH §"Pitfall 4"). Bracket queries by each flent run's start/end timestamps, expect ~600 raw cycles × 3 ≈ 1800 rows.

---

### 5. `soak/cake-primary/flent/*.flent.gz` (3 runs) (data, file-I/O subprocess output)

**Analog:** Phase 196 corrected-bind capture — `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-spectrum-corrected-summary.json` (lines 1-21):

```json
{
  "label": "phase196_cake_primary_tcp12_spectrum_corrected",
  "local_bind": "10.10.110.226",
  "public_egress_ip": "70.123.224.169",
  "public_egress_org": "AS11427 Charter Communications Inc",
  "tcp_12down_median_mbps": 307.9225832916394,
  "sample_count": 151,
  "acceptance_mbps": 532,
  "verdict": "fail",
  "raw_flent_path": "/home/kevin/flent-results/phase196/.../tcp_12down-...flent.gz",
  "summary_path": "...",
  "manifest_path": "...",
  "post_run_active_primary_signal": "queue",
  "post_run_download_state": "GREEN",
  "post_run_download_rate_mbps": 940.0
}
```

**Capture command (RESEARCH §"Code Example 4"):**

```bash
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
```

The flent helper (`scripts/phase191-flent-capture.sh:121-124,158-167`) validates `--local-bind` is locally configured AND captures raw + plot + per-run summary. The raw `.flent.gz` lives under `~/flent-results/phase198/...`; Phase 198 should symlink or copy them into `.planning/phases/198-*/soak/cake-primary/flent/run{1,2,3}.flent.gz` for repository-bundled evidence.

**Phase 198 deviations from Phase 196:**
1. Three sequential runs, not one (acceptance is 2-of-3 + median-of-medians).
2. PRE-EACH-RUN egress probe (item 2 above) — Phase 196 only ran the egress proof once after-the-fact.
3. `post_run_*` fields are still useful but the gate is the median-of-medians, captured in `throughput-verdict.json` (item 6).

---

### 6. `soak/cake-primary/throughput-verdict.json` (evidence, batch JSON write)

**Analog (single-run schema):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-spectrum-corrected-summary.json` (above).

**Phase 198 deviation:** Extend single-run shape into 3-run aggregate. Recommended shape (matches RESEARCH §"Code Example 6 — Proposed ab-comparison.json schema → throughput section"):

```json
{
  "label": "phase198_cake_primary_tcp12_3run",
  "local_bind": "10.10.110.226",
  "acceptance_mbps": 532,
  "rule": "VALN-05a: 2-of-3 individual medians >= 532 AND median-of-medians >= 532",
  "spectrum_tcp12_runs": [
    { "run": 1, "median_mbps": <float>, "raw_path": "soak/cake-primary/flent/run1.flent.gz",
      "egress_ip": "...", "egress_org": "AS11427 Charter Communications Inc" },
    { "run": 2, "median_mbps": <float>, "raw_path": "soak/cake-primary/flent/run2.flent.gz", ... },
    { "run": 3, "median_mbps": <float>, "raw_path": "soak/cake-primary/flent/run3.flent.gz", ... }
  ],
  "median_of_medians_mbps": <float>,
  "two_of_three_at_or_above_532_mbps": <bool>,
  "median_of_medians_at_or_above_532_mbps": <bool>,
  "verdict": "pass | fail"
}
```

---

### 7. `ab-comparison.json` (evidence, batch JSON write) — NEW, NO PRIOR PRECEDENT

**Analog:** NONE — research confirms `196-VERIFICATION.md:217` listed it but it was never produced.

**Schema source:** `198-RESEARCH.md` lines 399-490 (Code Example 6). The full proposed shape covers six deltas:

1. `rtt_distress_event_counts` (a_leg vs b_leg)
2. `burst_trigger_counts`
3. `dwell_bypass_responsiveness`
4. `fusion_state_transitions`
5. `queue_primary_coverage_pct` (rule: b_leg ≥ 99.9%)
6. `refractory_fallback_rate` (documented, not gated)

Plus a `throughput` section (mirrors item 6 above) and a top-level `comparison_verdict`.

**Inputs the planner must wire:**
- A-leg counters from `.planning/phases/196-*/soak/rtt-blend/rtt-blend-finish-20260426T090806Z-summary.json` and `.planning/phases/196-*/soak/rtt-blend/primary-signal-audit.json`.
- B-leg counters from this phase's `cake-primary-finish-<TS>-summary.json` and `primary-signal-audit-phase197.json`.
- Throughput from this phase's `throughput-verdict.json`.

**Recommendation:** Adopt the RESEARCH schema verbatim. The planner may rename fields for clarity but must keep the six-delta + throughput + verdict structure so 198-VERIFICATION.md can map truths 1:1.

---

### 8. `safe05-diff.json` (evidence, batch JSON write + `git diff`)

**Analog (pattern, not artifact):** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md:39-46` and `196-VERIFICATION.md:64-66` use:

```bash
git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py \
                    src/wanctl/fusion_healer.py src/wanctl/wan_controller.py
exit 0
```

**Phase 198 deviation:** Phase 197 ADDED `health_check.py` to the protected file list (it now contains the `refractory_active` relay; further edits would constitute a state-machine touch). Diff target list per RESEARCH §"Code Example 5":

```bash
PHASE_197_SHIP_SHA=$(git log --oneline --grep="Phase 197 Plan 02" -n1 | awk '{print $1}')
git diff "${PHASE_197_SHIP_SHA}..HEAD" -- \
    src/wanctl/queue_controller.py \
    src/wanctl/cake_signal.py \
    src/wanctl/fusion_healer.py \
    src/wanctl/wan_controller.py \
    src/wanctl/health_check.py
```

**Recommended JSON schema** (no prior JSON form exists — planner-defined):

```json
{
  "phase": 198,
  "captured_at_utc": "<ISO 8601>",
  "phase_197_ship_sha": "<short-sha>",
  "head_sha": "<short-sha-at-evaluation-time>",
  "protected_files": [
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/fusion_healer.py",
    "src/wanctl/wan_controller.py",
    "src/wanctl/health_check.py"
  ],
  "diff_summary": {
    "<file>": { "lines_added": 0, "lines_removed": 0, "diff_excerpt": "" }
  },
  "diff_empty": true,
  "verdict": "pass | fail"
}
```

`diff_empty: true` is the gate. Anything else triggers SAFE-05 investigation per RESEARCH §"Pitfall 5".

---

### 9. `198-VERIFICATION.md` (evidence, document)

**Analog (exact form):** `.planning/phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/197-VERIFICATION.md` (lines 1-80).

**YAML frontmatter to mirror:**

```yaml
---
phase: 198-spectrum-cake-primary-b-leg-rerun
verified: <ISO 8601>
status: passed | blocked | failed
score: <N>/<N> must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05a, SAFE-05]
---
```

**Sections to mirror from 197-VERIFICATION.md:**
- `## Goal Achievement` → `### Observable Truths` table (one row per VALN-04 / VALN-05a / SAFE-05 truth, with status + evidence path)
- `### Required Artifacts` table (preflight.json, source-bind-egress-proof.json, primary-signal-audit-phase197.json, throughput-verdict.json, ab-comparison.json, safe05-diff.json, the three flent.gz)
- `### Behavioral Spot-Checks` table (key commands run + their outputs)
- `### Requirements Coverage` table (VALN-04, VALN-05a, SAFE-05 with evidence pointers)

**Phase 196 fallback** (only if blocked): `196/196-VERIFICATION.md` shows the `gaps:` block in frontmatter for documenting blocking reasons. Phase 198 should NOT need this — research projects pass — but the form is there if a flent run misses.

---

### 10. `scripts/phase198-flent-3run.sh` (OPTIONAL helper, event-driven)

**Analog (entry-point shape):** `scripts/phase191-flent-capture.sh:55-99` (arg parsing) + `scripts/phase196-soak-capture.sh:34-49` (require_var/require_command).

**Imports/style (mirror these from phase191-flent-capture.sh:1-22):**

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() { cat <<'EOF'
Usage:
  scripts/phase198-flent-3run.sh --output-root <dir> [--ref <git-ref>]
EOF
}
```

**Core pattern (3-run loop wrapping `phase191-flent-capture.sh`):**

```bash
for i in 1 2 3; do
    # Pre-run egress probe — fail fast if 10.10.110.226 doesn't exit Spectrum.
    EGRESS=$(curl --silent --max-time 10 --interface 10.10.110.226 https://ipinfo.io/json)
    echo "$EGRESS" | jq -e '.org | test("Charter|AS11427")' >/dev/null

    ./scripts/phase191-flent-capture.sh \
        --label "phase198_cake_primary_tcp12_run${i}" \
        --wan spectrum \
        --local-bind 10.10.110.226 \
        --duration 30 \
        --output-dir "$OUTPUT_ROOT" \
        --tests tcp_12down \
        --ref "$REF"
done
```

**Hard rule (SAFE-05):** This script reads `src/wanctl/` only via `git rev-parse`. It must NOT modify any file under `src/wanctl/`. The ruff/mypy regression slice (`tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py`) should still pass unchanged.

**Decision rule:** Add this wrapper ONLY if the planner believes it reduces operator error. Three sequential `phase191-flent-capture.sh` invocations are equally valid and have less surface area. RESEARCH §"Wave 0 Gaps" calls this optional.

---

## Shared Patterns

### A. Capture-script invocation (used by Plan 01 preflight + Plan 02 start/finish)

**Source:** `scripts/phase196-soak-capture.sh:1-281`. Already Phase-197-aware (extracts `refractory_active` at line 219; SQL filters now include `wanctl_arbitration_refractory_active` at lines 116, 148).

**Invocation env vars (lines 17-31):**

```bash
PHASE196_OUT_DIR=.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak \
PHASE196_SPECTRUM_HEALTH_URL=http://<cake-shaper>:9101/health \
PHASE196_SPECTRUM_SSH_HOST=<cake-shaper-ssh-alias> \
PHASE196_SPECTRUM_METRICS_DB=/var/lib/wanctl/<spectrum-metrics-db> \
./scripts/phase196-soak-capture.sh {preflight|cake-primary-start|cake-primary-finish}
```

**Note:** The script writes to `${PHASE196_OUT_DIR}/${CAPTURE_GROUP}/...`, so pointing `PHASE196_OUT_DIR` at the Phase 198 phase soak directory yields the correct layout without any code change. `CAPTURE_GROUP` is `cake-primary` for the start/finish modes (`scripts/phase196-soak-capture.sh:69-75`).

**Apply to:** Plan 01 (preflight invocation), Plan 02 (start + 24h-later finish).

---

### B. Phase 197 audit predicate (used by Plan 02 audit step + Plan 04 ab-comparison)

**Source:** `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-phase197.md` (lines 28-40, 60-71). This document is the contract — DO NOT rebuild.

**Hard rules:**
- `granularity = 'raw'` filter on metric rows BEFORE counting (Pitfall 3).
- Accept-list = `{queue_distress, green_stable, queue_during_refractory}`.
- `rtt_fallback_during_refractory + refractory_active=true` is the documented-exception bucket — counted separately, NOT a verdict failure.
- Verdict thresholds inherit from Phase 196 lineage (`pass`, `pass_with_documented_exceptions`, `fail`).

**Apply to:** Plan 02 (audit emission), Plan 04 (ab-comparison feeds the queue-primary coverage delta).

---

### C. SAFE-05 enforcement (used by Plan 01 preflight + Plan 04 closeout)

**Source:** `196-PREFLIGHT.md:39-46`, `196-VERIFICATION.md:64-66`, RESEARCH §"Code Example 5".

**Pattern:**

```bash
PHASE_197_SHIP_SHA=$(git log --oneline --grep="Phase 197 Plan 02" -n1 | awk '{print $1}')
git diff --quiet "${PHASE_197_SHIP_SHA}..HEAD" -- \
    src/wanctl/queue_controller.py \
    src/wanctl/cake_signal.py \
    src/wanctl/fusion_healer.py \
    src/wanctl/wan_controller.py \
    src/wanctl/health_check.py
echo "exit=$?"  # must be 0
```

**Plan 01 use:** Sanity check at preflight (no drift expected; gate the soak start).
**Plan 04 use:** Final emission of `safe05-diff.json` with `diff_empty: true`.

**Apply to:** Plan 01, Plan 04.

---

### D. Egress probe (used by Plan 03 before each flent run)

**Source:** RESEARCH §"Code Example 1", `196/soak/cake-primary/source-bind-egress-proof.json`.

```bash
EGRESS_JSON=$(curl --silent --max-time 10 --interface 10.10.110.226 https://ipinfo.io/json)
echo "$EGRESS_JSON" | jq -e '.org | test("Charter|AS11427")'
EGRESS_IP=$(echo "$EGRESS_JSON" | jq -r '.ip')
test "$EGRESS_IP" != "99.126.115.47"
```

**Hard rule:** Run BEFORE each of the three flent captures (RESEARCH §"Pitfall 1" and §"Open Question 4"). Append the probe result to `source-bind-egress-proof.json` as a `pre_run_probes[]` entry.

**Apply to:** Plan 03.

---

### E. Verification document form (used by Plan 04 closeout)

**Source:** `.planning/phases/197-*/197-VERIFICATION.md:1-80`. Uses YAML frontmatter, observable-truths table, required-artifacts table, behavioral-spot-checks table, and requirements-coverage table.

**Apply to:** Plan 04.

---

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `ab-comparison.json` | evidence (cross-leg delta) | Phase 196 listed it as required but never emitted (`196-VERIFICATION.md:217` blocked on throughput failure). Use the schema proposed in `198-RESEARCH.md:399-490` verbatim. |
| `wanctl.sqlite` (raw SQLite copy) | data | Phase 196 lineage uses `.psv` exports via the capture script. Recommend NOT introducing a parallel `.sqlite` artifact — see item 3 above. If kept, simple `scp` is sufficient. |

`safe05-diff.json` had no JSON-form analog but the underlying `git diff --quiet` evidence pattern is well-established from `196-PREFLIGHT.md` — schema is planner-defined per item 8.

---

## Cross-Cutting Constraints (must apply to every plan)

1. **No `src/wanctl/` edits.** SAFE-05 (research and ROADMAP). Any controller/state-machine change invalidates the phase.
2. **Phase 196 capture script is already Phase-197-aware** — re-use as-is. WR-01/WR-02 noted in research are NOT blockers for Phase 198.
3. **Mode-gate is already-set** (research §"Pattern: Mode-gate is already-set"). Do NOT add a redundant `cake_signal.enabled` toggle cycle. Verify via `/health` and proceed.
4. **Restart-after-deploy is mandatory** if Phase 197 binary was just rsynced (research §"Pitfall 2"). Preflight artifact must record `service_active_enter_timestamp_utc > rsync_timestamp_utc`.
5. **Pre-commit hook may need `SKIP_DOC_CHECK=1`** for evidence-only commits (project CLAUDE.md + Phase 197 precedent at `197-02-SUMMARY.md`).
6. **Use `.venv/bin/...`** for any Python tooling invocation (project convention).
7. **Operator-only commands.** No automated deploy/restart from the agents — those are operator-prompted (consistent with Phase 196 plan style).

---

## Metadata

**Analog search scope:**
- `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/` (whole tree — primary source of artifacts)
- `.planning/phases/197-queue-primary-refractory-semantics-split-dl-cake-for-detecti/` (whole tree — verification template, audit predicate context)
- `scripts/` (phase191-flent-capture.sh, phase196-soak-capture.sh, phase192-soak-capture.sh)

**Files scanned (key):**
- `198-RESEARCH.md`
- `196-PREFLIGHT.md`, `196-VERIFICATION.md`, `196-MODE-GATE.md`
- `196/soak/preflight/preflight-20260425T044045Z-summary.json`
- `196/soak/preflight/mode-gate-proof.json`
- `196/soak/cake-primary/source-bind-egress-proof.json`
- `196/soak/cake-primary/manifest.json`
- `196/soak/cake-primary/cake-primary-finish-20260427T092154Z-summary.json`
- `196/soak/cake-primary/raw-only-primary-signal-audit.json`
- `196/soak/cake-primary/primary-signal-audit.json`
- `196/soak/cake-primary/primary-signal-audit-phase197.md`
- `196/soak/cake-primary/throughput-spectrum-corrected-summary.json`
- `196/soak/cake-primary/throughput-summary.json`
- `196/soak/cake-primary/throughput-rerun-summary.json`
- `196/soak/cake-primary/b-leg-documented-exceptions-acceptance.json`
- `196/soak/rtt-blend/manifest.json`, `196/soak/rtt-blend/flent-summary.json`
- `197-VERIFICATION.md`, `197-PATTERNS.md`
- `scripts/phase191-flent-capture.sh`, `scripts/phase196-soak-capture.sh`

**Pattern extraction date:** 2026-04-27
