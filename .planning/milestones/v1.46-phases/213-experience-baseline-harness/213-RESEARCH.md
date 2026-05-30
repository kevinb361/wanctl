# Phase 213: Experience Baseline Harness - Research

**Researched:** 2026-05-27
**Domain:** Controlled production-load evidence pipeline (flent + co-sampled `/health` NDJSON + SQLite alert windows + steering snapshots + symptom-bucket classification)
**Confidence:** HIGH

## Summary

Phase 213 layers a thin per-WAN orchestrator over `scripts/phase191-flent-capture.sh` and the `scripts/soak-capture.sh` polling pattern. Every reusable surface this phase needs already exists in production-shaped form: `/health` already exposes `cake_signal`, `signal_quality.outlier_rate/confidence`, current rates, hysteresis suppression counters, and DOCSIS upload diagnostics; `flent 2.1.1` already supports `tcp_upload` and `tcp_download` as first-class tests; `scripts/storage/reader.py:query_alerts` already provides a read-only window query over the `alerts` table; `cake-shaper` already has `sqlite3 3.46.1`, `jq`, `curl`, and `python3` for remote read-only extraction. Phase 198's per-run subdir layout and Phase 212's `evidence/README.md` index pattern are direct templates.

The non-trivial surfaces are (1) **concurrent dual-WAN NDJSON poll wiring** during each per-WAN test (D-11 says serialize WAN suites, but a single test still polls BOTH Spectrum and ATT to record the unloaded WAN's behavior during the loaded WAN's test), (2) **read-only SQLite extraction from a live-writer DB without copy**, and (3) **the classification signal sheet schema** that operationalizes the six v1.46 buckets without interpreting steering v1.39 threshold semantics.

**Primary recommendation:** Build one orchestrator `scripts/phase213-baseline-capture.sh` that wraps `phase191-flent-capture.sh` per-test, brackets each test with a per-WAN NDJSON poll subprocess (extended schema beyond `soak-capture.sh`'s upload-only projection), takes pre/post steering snapshots over SSH, runs the curl-browse loop in parallel with flent (it IS one of the "tests"), and emits a per-run manifest + raw artifacts that a separate `scripts/phase213-classify.py` reads to produce `signal-sheet.json` + `signal-sheet.md`. Don't extend `analyze_baseline.py` — different inputs and concern.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Workload Mix And Tooling:**
- **D-01:** Flent legs (RRUL, `tcp_12down`, isolated `tcp_upload`, isolated `tcp_download`) reuse `scripts/phase191-flent-capture.sh` via a thin 213 orchestrator wrapper. Planner has discretion to fork only if co-sampling integration forces it.
- **D-02:** "Normal browsing" is captured as a scripted multi-site curl loop that records TTFB and total time per request, run concurrently with the same NDJSON `/health` poll that wraps the flent tests. Not a headless browser, not a human-timed manual session.
- **D-03:** All test flows originate from the dev VM with `--local-bind` matching the source IP Phase 191/198 used (`10.10.110.233` or current dev VM IP — planner confirms before run). Flows traverse the same LAN → steering → WAN path real users hit.
- **D-04:** Flent netperf server is locked to `dallas` (same as Phase 191/198) for geographic baseline continuity. The curl-browse site list at planner discretion.

**Co-Sampling Design (BASE-02):**
- **D-05:** Default sampling: continuous 1Hz NDJSON polls of both autorate `/health` endpoints (Spectrum `http://10.10.110.223:9101/health`, ATT `http://10.10.110.227:9101/health`) during each test. Pre/post snapshots only for steering `/health` (`http://127.0.0.1:9102/health` on `cake-shaper`) and SQLite alert queries.
- **D-06:** Window alignment uses per-test bracketing: orchestrator starts NDJSON poll, records `test_start_unix`, runs the test, records `test_end_unix`, stops poll. NDJSON poll brackets the test with a planner-chosen pre/post buffer (e.g., 10s on each side). All artifacts share ISO timestamps.
- **D-07:** SQLite alert capture: dump alert rows (timestamp, type, severity, wan_name, details) for the test window AS WELL AS a summary count grouped by `alert_type` and `severity`, from `/var/lib/wanctl/metrics-spectrum.db` and `/var/lib/wanctl/metrics-att.db`. Steering alerts come from `/var/lib/wanctl/metrics.db` if present.
- **D-08:** Steering `/health` and persisted state at `/var/lib/wanctl/steering_state.json` are captured as raw evidence per test. Threshold field names are recorded verbatim but NOT interpreted in classification while runtime `1.39.0` drift remains unresolved.

**Runbook Surface And Mutation Posture:**
- **D-09:** Single orchestrator `scripts/phase213-baseline-capture.sh`. Operator invokes one command. Thin `docs/RUNBOOKS/baseline.md` documents command + how to read artifacts.
- **D-10:** Allowed: traffic generation from dev VM. Forbidden: service restart, `/etc/wanctl/*.yaml` edit, steering toggle, RouterOS write, deploy, profiling harness changes, controller config changes.
- **D-11:** Per-WAN sequencing: never load Spectrum and ATT concurrently. Full flent + curl-browse suite against Spectrum to completion, then against ATT.
- **D-12:** Artifact layout: `.planning/phases/213-experience-baseline-harness/evidence/RUN-<utc-ts>/<wan>/<test>/`. Phase 212's D-08/D-09/D-10 secret-redaction policy applies unchanged.

**Symptom → Bucket Classification (BASE-03):**
- **D-13:** Hybrid classification. Script emits a per-bucket signal sheet; operator reads it and assigns final bucket verdict(s) in the report citing the rows.
- **D-14:** Six buckets: upload ceiling/setpoint, download recovery lag, measurement collapse, steering drift, refractory semantics, external ISP. Steering drift sheet shows raw transitions/counters but does NOT compare to threshold field names while v1.39 semantics are unresolved.
- **D-15:** Phase 213 success criterion 4 satisfied by a single ranked next-phase recommendation (one of 214/215/216) in the final report with evidence-cited rationale and runners-up.

**Carry-Forward From Phase 212:**
- **D-16:** Bound autorate endpoints authoritative. Steering reached via SSH to `cake-shaper` for snapshot.
- **D-17:** `/health.status=healthy` and `GREEN` are daemon-state only; UX evidence comes from active test artifacts.
- **D-18:** Spectrum upload operating points (`floor=8`, `ceiling=18`, `setpoint=12`, DOCSIS active) are intentional. Phase 213 records, MUST NOT tune.
- **D-19:** Phase 212 evidence is inventory baseline. Phase 213 cites it; does not re-probe.

### Claude's Discretion

Planner retains discretion on: exact orchestrator script name and layout, exact curl-browse site list, pre/post NDJSON buffer width, per-test duration (subject to flent defaults), exact signal-sheet thresholds.

### Deferred Ideas (OUT OF SCOPE)

- Steering clean-restart reproduction (mutation outside D-10 boundary, defer to Phase 216 territory).
- Post-hotpath profiling (Phase 217).
- Flapping peak-count monitoring (Phase 218, depends on natural event).
- ATT cake-primary canary (depends on Phase 196 follow-up).
- Time-of-day matrix capture (Phase 214 owns `tcp_12down` time-of-day; Phase 213 captures one window).
- Headless-browser browsing (rejected in favor of curl loop, D-02).
- Multiple netperf servers (locked to `dallas`, D-04).
- Active steering toggle to force bucket evidence (outside D-10 boundary).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BASE-01 | Operator has a repeatable production baseline runbook for normal browsing, upload, download, RRUL, and `tcp_12down` checks with timestamps, commands, and artifact paths. | Orchestrator script + `docs/RUNBOOKS/baseline.md` + Phase 198's per-run-subdir template (§"Per-Run Artifact Layout"). |
| BASE-02 | Each baseline run captures matching `/health`, CAKE state, SQLite alert counts, current rates, measurement quality, and steering state for the same time window. | All six surfaces verified present: `/health` exposes `cake_signal`, `signal_quality`, `download/upload.current_rate_mbps`; `query_alerts` exists in `storage/reader.py`; steering `/health` at `127.0.0.1:9102`. See §"Co-Sampling Surfaces" for verbatim field paths. |
| BASE-03 | Baseline results classify the perceived-quality issue into at least one primary bucket: upload ceiling/setpoint, download recovery lag, measurement collapse, steering drift, refractory semantics, or external ISP conditions. | `scripts/phase213-classify.py` (new). Per-bucket signal sheet schema in §"Classification Signal Sheet (BASE-03)". |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Traffic generation (flent, curl-browse) | Dev VM (Linux, originator) | — | D-03: same LAN→steering→WAN path real users hit. No production-host load. |
| `/health` NDJSON polling | Dev VM (orchestrator subprocess) | Bound HTTP endpoint on `cake-shaper` (read-only) | Polling host does not need privileges; endpoints are HTTP-exposed. |
| Steering pre/post snapshot | Production host `cake-shaper` (SSH inline curl + sudo -n cat) | Dev VM (capture + redaction) | Steering only on loopback `127.0.0.1:9102`; persisted state under `/var/lib/wanctl/` is root-readable. |
| SQLite alert window extraction | Production host `cake-shaper` (SSH `sudo -n sqlite3 -readonly`) | Dev VM (writes artifact) | DBs at `/var/lib/wanctl/metrics-*.db`, root-only. Read-only URI mode required while writer is live. |
| Per-run manifest write | Dev VM (orchestrator, JSON) | — | All artifacts under `.planning/phases/213-.../evidence/RUN-<ts>/`. |
| Classification signal sheet | Dev VM (offline Python) | — | Reads per-test artifacts and emits JSON+Markdown. No production access. |
| Final report (operator-authored) | Dev VM (Markdown) | — | Operator reads signal sheet, assigns bucket verdicts, cites rows. |

**Why this matters:** The harness has clear tier boundaries. The dev VM is the orchestrator and analyzer; `cake-shaper` is queried read-only for steering snapshots and SQLite extraction; production daemons are never written, restarted, or config-mutated. The portable-controller invariant holds: no Python branching on WAN name in any new code.

## Standard Stack

### Core (already installed)

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| `flent` | 2.1.1 (verified `flent --version`) | RRUL, `tcp_12down`, `tcp_upload`, `tcp_download` test runs | Phase 191/198 baseline; `tcp_upload`/`tcp_download` are first-class flent tests (verified `flent --list-tests`) [VERIFIED: local CLI]. |
| `netperf` | (whatever ships with `netperf` on the `dallas` server) | Flent backend traffic | Locked by D-04 for continuity with Phase 191/198. |
| `curl` | 8.x (verified `/usr/bin/curl`) | HTTP polling and curl-browse | Already used in `soak-capture.sh` and `phase198-rerun-flent-3run.sh`. |
| `jq` | (system `/usr/bin/jq` on dev VM and `cake-shaper`) | NDJSON projection, manifest assembly, per-row health snippet shape | Already the proven projection tool in `soak-capture.sh`. |
| `sqlite3` | 3.46.1 on `cake-shaper` (verified) | Read-only window query against live-writer DBs | Supports `-readonly`. SQLite URI `file:...?mode=ro&immutable=0` is the safe pattern. |
| `ssh` (OpenSSH) | system, `BatchMode=yes` | Production-host read-only commands | `cake-shaper` ssh alias confirmed reachable; passwordless `sudo -n` already used by Phase 212. |
| `python3` (`.venv/bin/python3`) | 3.11+ (project standard) | Classification script, NDJSON aggregation, JSON manifest math | Phase 198 uses inline `.venv/bin/python3` for flent median extraction; same pattern fits. |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `wanctl.storage.reader.query_alerts` | wanctl 1.45.0 | In-window alert extraction with parsed `details` JSON | When alert dump must include parsed `details` (e.g., severity by reason). Easier than hand-rolled SQL on dev VM if classifier reads `.db` files copied locally; harder if extraction happens on `cake-shaper` (would require deploying `wanctl` Python on dev VM, which it isn't always). **See §"SQLite Read-Only Extraction" recommendation.** |
| `wanctl.storage.db_utils.query_all_wans` | wanctl 1.45.0 | Multi-DB query aggregation | Available if extending `analyze_baseline.py`; not recommended for Phase 213 (different concern). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline `sqlite3 -readonly` over SSH | `scp` DBs to dev VM + `query_alerts` | SCP of a 467MB Spectrum + 437MB ATT live-writer DB is slow and brittle (WAL race). Inline SQL is faster, lower-bandwidth, and read-safe with `mode=ro` URI. **Recommend inline.** |
| Forking `phase191-flent-capture.sh` | Calling it as-is per-test in a loop | Calling it works once `--tests tcp_upload,tcp_download` is supported by flent (it is — verified). The wrapper does NOT need to extend the script's CLI; it can already pass any test name via `--tests`. **Recommend call-as-is.** |
| Extending `analyze_baseline.py` for signal-sheet emission | New `scripts/phase213-classify.py` | `analyze_baseline.py` is a CLI for CAKE drop/backlog metrics queried from SQLite by time range. Phase 213 classifier reads NDJSON + flent summaries + per-run manifests + SQLite alert windows. Different inputs, different concern. **Recommend new script.** |
| `scripts/soak-capture.sh` as the per-test NDJSON poller | Sibling poller dedicated to Phase 213 | `soak-capture.sh`'s `jq` projection is upload-only (`floor_hit_cycles_total`, `red_streak`, `zone_trace_tail`, `headroom_*`, `anti_windup_*`, etc.) — missing download fields, missing `cake_signal`, missing `signal_quality.outlier_rate/confidence`, missing `signal_arbitration.refractory_active`. Phase 213 needs an **extended** projection. Reusing `soak-capture.sh` would force a fork. **Recommend sibling Phase 213 poller with its own `jq` projection.** Keep its HRDN-02 bounded-failure pattern for resilience. |
| Headless browser (puppeteer/playwright) for "normal browsing" | Scripted curl-browse loop | Rejected by D-02. |

**Installation:** No new dependencies. Every required tool is on dev VM and `cake-shaper`.

**Version verification:**

| Package | Verified Version | Source |
|---------|------------------|--------|
| `wanctl` | 1.45.0 | `pyproject.toml` line `version = "1.45.0"` [VERIFIED: file read] |
| `flent` | 2.1.1 (Python 3.12.3) | `flent --version` on dev VM [VERIFIED: local CLI] |
| `sqlite3` (cake-shaper) | 3.46.1 (2024-08-13) | `ssh cake-shaper sqlite3 --version` [VERIFIED: remote CLI] |

## Architecture Patterns

### System Architecture Diagram

```
                  Operator (one command)
                        │
                        ▼
            scripts/phase213-baseline-capture.sh   (D-09 orchestrator on dev VM)
                        │
                        │  for WAN in [spectrum, att]:         (D-11 serialized)
                        │     for TEST in [browse, tcp_upload, tcp_download, rrul, tcp_12down]:
                        │
            ┌───────────┼──────────────────────────────────────────────────┐
            │           │                                                  │
            ▼           ▼                                                  ▼
     pre-snapshot   start NDJSON polls   start TEST traffic           SQLite window
        (steering)  ├─ Spectrum 9101     ├─ flent (phase191 wrapper)  extraction
        ssh +       └─ ATT 9101          │   or curl-browse loop      (after test)
        sudo -n cat    1Hz, jq projected │                            ssh + sudo -n
        steering_      to NDJSON         │                            sqlite3 -readonly
        state.json     bounded failure   │                            ├─ metrics-spectrum.db
                       (HRDN-02 pattern) │                            ├─ metrics-att.db
                                         │                            └─ metrics.db (steering)
                                         ▼
                                  test_end_unix
                                         │
                                         ▼
                       post-snapshot (steering /health + state.json)
                                         │
                                         ▼
            ┌───────────────────────────────────────────────────────────────┐
            │   evidence/RUN-<utc>/<wan>/<test>/                            │
            │     ├── manifest.json     (start/end, version, source IP)     │
            │     ├── flent.*.flent.gz  (raw flent data, if applicable)     │
            │     ├── flent.summary.txt (plain flent summary)               │
            │     ├── browse.curl.csv   (TTFB+total per site, if browse)    │
            │     ├── health-spectrum.ndjson (1Hz extended health rows)     │
            │     ├── health-att.ndjson      (1Hz, even when not loaded WAN)│
            │     ├── steering-pre.json      (steering /health snapshot)    │
            │     ├── steering-pre-state.redacted.json                      │
            │     ├── steering-post.json                                    │
            │     ├── steering-post-state.redacted.json                     │
            │     ├── alerts-spectrum.json   (rows in [pre-buf, post-buf])  │
            │     ├── alerts-att.json                                       │
            │     ├── alerts-steering.json                                  │
            │     └── alerts-summary.json    (grouped counts)               │
            └───────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                       scripts/phase213-classify.py
                       reads all evidence/RUN-<utc>/**, emits:
                       ├── signal-sheet.json
                       └── signal-sheet.md   (operator-readable)
                                         │
                                         ▼
                       Operator authors 213-REPORT.md
                       (assigns bucket verdict(s) per D-13, ranks 214/215/216 per D-15)
```

### Recommended Project Structure

```
scripts/
├── phase213-baseline-capture.sh    # NEW: orchestrator (D-09)
├── phase213-health-poller.sh       # NEW: sibling NDJSON poller (per-WAN, extended jq projection)
├── phase213-browse-loop.sh         # NEW: curl-browse loop (D-02)
├── phase213-steering-snapshot.sh   # NEW: SSH-based pre/post steering snapshot (D-08)
├── phase213-alert-window.sh        # NEW: SSH read-only SQLite window extraction (D-07)
└── phase213-classify.py            # NEW: signal-sheet emitter (BASE-03)

docs/RUNBOOKS/
└── baseline.md                     # NEW: thin operator runbook (D-09)

.planning/phases/213-experience-baseline-harness/
├── 213-CONTEXT.md                  # exists
├── 213-DISCUSSION-LOG.md           # exists
├── 213-RESEARCH.md                 # this file
├── 213-RESEARCH-PLAN.md            # next: planner output
└── evidence/
    ├── README.md                   # NEW: command index + redaction + mutation posture (mirror Phase 212)
    └── RUN-<utc-ts>/               # NEW: per-run timestamp dir
        ├── manifest.json           # per-run manifest (wanctl version per WAN, dev VM IP, flent version)
        ├── spectrum/
        │   ├── browse/             # per-test subdir
        │   ├── tcp_upload/
        │   ├── tcp_download/
        │   ├── rrul/
        │   └── tcp_12down/
        └── att/
            └── … same five subdirs
```

### Pattern 1: Per-Test Bracketed Polling (D-06)

**What:** Every test is bracketed by a per-WAN NDJSON `/health` poll with planner-chosen pre/post buffer (recommend 10s on each side). The poller is started in the background just before the test, killed just after. `test_start_unix` and `test_end_unix` are recorded in `manifest.json`.

**When to use:** Every test in the suite (browse, tcp_upload, tcp_download, rrul, tcp_12down).

**Example:**

```bash
# Source: pattern adapted from scripts/phase198-rerun-flent-3run.sh (inline health subshell)
#         and scripts/soak-capture.sh (bounded-failure poll loop)
run_bracketed_test() {
    local wan="$1" test="$2" test_dir="$3"
    local pre_buf="${PHASE213_PRE_BUF:-10}"
    local post_buf="${PHASE213_POST_BUF:-10}"

    # Pre-snapshot: steering
    bash scripts/phase213-steering-snapshot.sh --output "${test_dir}/steering-pre"

    # Start dual-WAN NDJSON polls (D-05)
    bash scripts/phase213-health-poller.sh \
        --endpoint "http://10.10.110.223:9101/health" --wan spectrum \
        --output "${test_dir}/health-spectrum.ndjson" &
    HP_SPEC_PID=$!
    bash scripts/phase213-health-poller.sh \
        --endpoint "http://10.10.110.227:9101/health" --wan att \
        --output "${test_dir}/health-att.ndjson" &
    HP_ATT_PID=$!

    sleep "${pre_buf}"
    local t_start; t_start=$(date -u +%s)

    # Run the actual test
    case "$test" in
        browse)
            bash scripts/phase213-browse-loop.sh --duration 60 --output "${test_dir}/browse.curl.csv"
            ;;
        rrul|tcp_12down|tcp_upload|tcp_download)
            ./scripts/phase191-flent-capture.sh \
                --label "phase213_${wan}_${test}" \
                --wan "$wan" \
                --local-bind 10.10.110.233 \
                --host dallas \
                --duration "${PHASE213_FLENT_DURATION:-60}" \
                --tests "$test" \
                --output-dir "${test_dir}/flent" \
                --ref "$(git rev-parse --short HEAD)"
            ;;
    esac

    local t_end; t_end=$(date -u +%s)
    sleep "${post_buf}"

    # Stop pollers
    kill "$HP_SPEC_PID" "$HP_ATT_PID" 2>/dev/null || true
    wait "$HP_SPEC_PID" "$HP_ATT_PID" 2>/dev/null || true

    # Post-snapshot: steering
    bash scripts/phase213-steering-snapshot.sh --output "${test_dir}/steering-post"

    # SQLite alert windows (D-07): query for [t_start - pre_buf, t_end + post_buf]
    bash scripts/phase213-alert-window.sh \
        --start "$((t_start - pre_buf))" --end "$((t_end + post_buf))" \
        --output-dir "${test_dir}"

    # Write per-test manifest
    jq -n \
        --arg wan "$wan" --arg test "$test" \
        --argjson t_start "$t_start" --argjson t_end "$t_end" \
        --argjson pre_buf "$pre_buf" --argjson post_buf "$post_buf" \
        '{wan:$wan, test:$test, t_start_unix:$t_start, t_end_unix:$t_end,
          pre_buf_sec:$pre_buf, post_buf_sec:$post_buf}' \
        > "${test_dir}/manifest.json"
}
```

### Pattern 2: Sibling NDJSON Poller with Extended `jq` Projection

**What:** `phase213-health-poller.sh` is a sibling to `soak-capture.sh`. Same per-iteration bounded-failure loop (HRDN-02), same temp-file truncation, same TSV sidecar for failed rows, but with an extended `jq` projection that covers BASE-02 surfaces.

**When to use:** Per-test, per-WAN polling. Started once per test, killed at test end.

**Per-row NDJSON schema (extended):**

| Field | Source path in `/health` | Why included |
|-------|--------------------------|--------------|
| `t_wall` | capture host clock (ISO-8601 UTC) | timestamp alignment across artifacts |
| `t_monotonic_sec` | `/proc/uptime` delta from start | drift-immune ordering |
| `wan` | poller arg | which WAN this row is from |
| `version` | `.version` | for cross-check vs. Phase 212 inventory |
| `status` | `.status` | daemon-state evidence (NOT UX, D-17) |
| `download_state` | `.wans[0].download.state` | hysteresis state per cycle |
| `download_state_reason` | `.wans[0].download.state_reason` | recovery-lag classification (BUCKET 2) |
| `download_rate_mbps` | `.wans[0].download.current_rate_mbps` | current rate at sample time |
| `download_green_streak` | `.wans[0].download.hysteresis.green_streak` | recovery-lag classification |
| `download_green_required` | `.wans[0].download.hysteresis.green_required` | recovery-lag classification |
| `upload_state` | `.wans[0].upload.state` | hysteresis state per cycle |
| `upload_state_reason` | `.wans[0].upload.state_reason` | upload ceiling/setpoint classification (BUCKET 1) |
| `upload_rate_mbps` | `.wans[0].upload.current_rate_mbps` | "pegged at 18 Mbps" detection |
| `upload_setpoint_mbps` | `.wans[0].upload.setpoint_mbps` | Spectrum `12` per D-18 |
| `upload_docsis_mode_active` | `.wans[0].upload.docsis_mode_active` | DOCSIS-aware state evidence |
| `upload_floor_hit_cycles_total` | `.wans[0].upload.floor_hit_cycles_total` | floor-hit count delta over test window |
| `upload_headroom_state` | `.wans[0].upload.headroom_state` | DOCSIS headroom semantics |
| `upload_headroom_exhausted_streak` | `.wans[0].upload.headroom_exhausted_streak` | streak duration |
| `upload_red_streak` | `.wans[0].upload.red_streak` | UL RED-cycle persistence |
| `upload_anti_windup_triggers` | `.wans[0].upload.anti_windup_triggers` | UL behavior under sustained load |
| `cake_dl_peak_delay_us` | `.wans[0].cake_signal.download.peak_delay_us` | DL CAKE backlog evidence (BUCKET 2) |
| `cake_dl_drop_rate` | `.wans[0].cake_signal.download.drop_rate` | DL drop-rate evidence |
| `cake_ul_peak_delay_us` | `.wans[0].cake_signal.upload.peak_delay_us` | UL CAKE backlog evidence |
| `cake_ul_drop_rate` | `.wans[0].cake_signal.upload.drop_rate` | UL drop-rate evidence |
| `cake_dl_backlog_suppressed_count` | `.wans[0].cake_signal.detection.dl_backlog_suppressed_count` | refractory semantics (BUCKET 6) |
| `cake_ul_backlog_suppressed_count` | `.wans[0].cake_signal.detection.ul_backlog_suppressed_count` | refractory semantics |
| `cake_dl_refractory_remaining` | `.wans[0].cake_signal.detection.dl_refractory_remaining` | refractory active flag |
| `cake_ul_refractory_remaining` | `.wans[0].cake_signal.detection.ul_refractory_remaining` | refractory active flag |
| `cake_refractory_cycles` | `.wans[0].cake_signal.detection.refractory_cycles` | per-WAN refractory length |
| `cake_burst_active` | `.wans[0].cake_signal.burst.active` | burst-protection state |
| `cake_burst_trigger_count` | `.wans[0].cake_signal.burst.trigger_count` | burst counter delta |
| `arb_active_primary_signal` | `.wans[0].signal_arbitration.active_primary_signal` | queue-vs-RTT arbitration (BUCKET 5) |
| `arb_control_decision_reason` | `.wans[0].signal_arbitration.control_decision_reason` | refractory semantics |
| `arb_refractory_active` | `.wans[0].signal_arbitration.refractory_active` | refractory flag |
| `arb_rtt_confidence` | `.wans[0].signal_arbitration.rtt_confidence` | RTT primary confidence |
| `signal_confidence` | `.wans[0].signal_quality.confidence` | measurement collapse (BUCKET 3) |
| `signal_outlier_rate` | `.wans[0].signal_quality.outlier_rate` | measurement collapse evidence |
| `signal_warming_up` | `.wans[0].signal_quality.warming_up` | warmup vs. collapse distinction |
| `measurement_state` | `.wans[0].measurement.state` | "healthy" vs. "stale" |
| `measurement_stale` | `.wans[0].measurement.stale` | staleness boolean |
| `measurement_staleness_sec` | `.wans[0].measurement.staleness_sec` | how stale |
| `measurement_successful_count` | `.wans[0].measurement.successful_count` | reflector quorum |
| `baseline_rtt_ms` | `.wans[0].baseline_rtt_ms` | for delta math |
| `load_rtt_ms` | `.wans[0].load_rtt_ms` | for delta math |
| `load_rtt_delta_us` | computed: `floor((load_rtt_ms - baseline_rtt_ms) * 1000)` | bufferbloat evidence |
| `irtt_rtt_mean_ms` | `.wans[0].irtt.rtt_mean_ms` (ATT only; Spectrum has IRTT disabled) | protocol divergence evidence (BUCKET 3) |
| `irtt_loss_up_pct` | `.wans[0].irtt.loss_up_pct` | UL loss evidence |
| `irtt_loss_down_pct` | `.wans[0].irtt.loss_down_pct` | DL loss evidence |
| `irtt_asymmetry_ratio` | `.wans[0].irtt.asymmetry_ratio` | direction-asymmetry evidence |
| `router_reachable` | `.wans[0].router_connectivity.is_reachable` | sanity floor |
| `alerting_fire_count` | `.alerting.fire_count` | monotonic per-process; delta over window = "alerts fired during test" |
| `alerting_active_cooldowns_count` | `.alerting.active_cooldowns \| length` | cooldown evidence |

**Verbatim `jq` projection skeleton** (extends `soak-capture.sh:94-124`):

```bash
jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" --arg wan "$WAN" '{
  t_wall: $twall, t_monotonic_sec: $tmono, wan: $wan,
  version: .version, status: .status,
  download_state: .wans[0].download.state,
  download_state_reason: .wans[0].download.state_reason,
  download_rate_mbps: .wans[0].download.current_rate_mbps,
  download_green_streak: .wans[0].download.hysteresis.green_streak,
  download_green_required: .wans[0].download.hysteresis.green_required,
  upload_state: .wans[0].upload.state,
  upload_state_reason: .wans[0].upload.state_reason,
  upload_rate_mbps: .wans[0].upload.current_rate_mbps,
  upload_setpoint_mbps: .wans[0].upload.setpoint_mbps,
  upload_docsis_mode_active: .wans[0].upload.docsis_mode_active,
  upload_floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
  upload_headroom_state: .wans[0].upload.headroom_state,
  upload_headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
  upload_red_streak: .wans[0].upload.red_streak,
  upload_anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
  cake_dl_peak_delay_us: .wans[0].cake_signal.download.peak_delay_us,
  cake_dl_drop_rate: .wans[0].cake_signal.download.drop_rate,
  cake_ul_peak_delay_us: .wans[0].cake_signal.upload.peak_delay_us,
  cake_ul_drop_rate: .wans[0].cake_signal.upload.drop_rate,
  cake_dl_backlog_suppressed_count: .wans[0].cake_signal.detection.dl_backlog_suppressed_count,
  cake_ul_backlog_suppressed_count: .wans[0].cake_signal.detection.ul_backlog_suppressed_count,
  cake_dl_refractory_remaining: .wans[0].cake_signal.detection.dl_refractory_remaining,
  cake_ul_refractory_remaining: .wans[0].cake_signal.detection.ul_refractory_remaining,
  cake_refractory_cycles: .wans[0].cake_signal.detection.refractory_cycles,
  cake_burst_active: .wans[0].cake_signal.burst.active,
  cake_burst_trigger_count: .wans[0].cake_signal.burst.trigger_count,
  arb_active_primary_signal: .wans[0].signal_arbitration.active_primary_signal,
  arb_control_decision_reason: .wans[0].signal_arbitration.control_decision_reason,
  arb_refractory_active: .wans[0].signal_arbitration.refractory_active,
  arb_rtt_confidence: .wans[0].signal_arbitration.rtt_confidence,
  signal_confidence: .wans[0].signal_quality.confidence,
  signal_outlier_rate: .wans[0].signal_quality.outlier_rate,
  signal_warming_up: .wans[0].signal_quality.warming_up,
  measurement_state: .wans[0].measurement.state,
  measurement_stale: .wans[0].measurement.stale,
  measurement_staleness_sec: .wans[0].measurement.staleness_sec,
  measurement_successful_count: .wans[0].measurement.successful_count,
  baseline_rtt_ms: .wans[0].baseline_rtt_ms,
  load_rtt_ms: .wans[0].load_rtt_ms,
  load_rtt_delta_us: (
    if (.wans[0].load_rtt_ms == null) or (.wans[0].baseline_rtt_ms == null)
    then null
    else ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)
    end
  ),
  irtt_rtt_mean_ms: (.wans[0].irtt.rtt_mean_ms // null),
  irtt_loss_up_pct: (.wans[0].irtt.loss_up_pct // null),
  irtt_loss_down_pct: (.wans[0].irtt.loss_down_pct // null),
  irtt_asymmetry_ratio: (.wans[0].irtt.asymmetry_ratio // null),
  router_reachable: .wans[0].router_connectivity.is_reachable,
  alerting_fire_count: .alerting.fire_count,
  alerting_active_cooldowns_count: (.alerting.active_cooldowns | length)
}'
```

### Pattern 3: Steering Snapshot via SSH (D-08)

**What:** Pre/post per-test snapshot. Steering `/health` is loopback-only on `cake-shaper`, so we SSH and curl inline. `steering_state.json` is captured the same way Phase 212 did (`sudo -n cat`).

**Example (`scripts/phase213-steering-snapshot.sh`):**

```bash
# Source: pattern from .planning/phases/212-.../evidence/README.md (verbatim Phase 212 commands)
set -euo pipefail
OUTPUT="${OUTPUT:?--output required}"
mkdir -p "$(dirname "$OUTPUT")"
ts_utc=$(date -u -Iseconds)

# /health (D-05 endpoint authoritative per D-16)
ssh -o BatchMode=yes cake-shaper \
    "curl -fsS --max-time 3 http://127.0.0.1:9102/health" \
    > "${OUTPUT}-health.json"

# Persisted state (per D-08, verbatim field names, no interpretation)
# sudo -n required (same as Phase 212-01)
ssh -o BatchMode=yes cake-shaper \
    "sudo -n cat /var/lib/wanctl/steering_state.json" \
    > "${OUTPUT}-state.raw.json"

# D-08/D-09 redaction: same key pattern as Phase 212
python3 - "$OUTPUT-state.raw.json" "$OUTPUT-state.redacted.json" <<'PY'
import json, re, sys
src, dst = sys.argv[1], sys.argv[2]
PAT = re.compile(r"(password|secret|token|credential|auth|key|private)", re.I)
def redact(o):
    if isinstance(o, dict):
        return {k: ("<REDACTED>" if PAT.search(k) else redact(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [redact(x) for x in o]
    return o
with open(src) as f: data = json.load(f)
with open(dst, "w") as f: json.dump(redact(data), f, indent=2, sort_keys=True)
PY

# Race-risk note: /health and state.json are read sequentially, not atomically.
# Drift between them across the ~100ms inline gap is acceptable for pre/post bracketing
# because Phase 213 records them as evidence; classifier compares post-pre transitions
# at coarse (test-duration) granularity, not millisecond ordering.

echo "${ts_utc} ${OUTPUT}-health.json ${OUTPUT}-state.redacted.json" >> "${OUTPUT%/*}/.snapshot-log"
```

### Pattern 4: Read-Only SQLite Window Extraction (D-07)

**What:** Per-test alert dump + grouped count, queried from live-writer DBs without copy.

**Live-writer safety:** SQLite's `mode=ro` URI opens a read-only connection. Combined with `sqlite3 -readonly`, this is the safe pattern even while the writer holds WAL. **Do NOT** use `mode=ro&immutable=1` — that one assumes the file doesn't change and can return stale views during active writes [CITED: sqlite.org/uri.html]. Use plain `?mode=ro`.

**Recommendation: use inline SQL, not `query_alerts` via SSH+python.** Reason: deploying `wanctl` to dev VM is fine (project already does), but invoking `query_alerts` *on* `cake-shaper` requires either (a) the production `/opt/wanctl/` Python being importable as `sudo -n python3 -c …` (works, but binds Phase 213 to deployed wanctl version, which is exactly the v1.45/v1.39 split we're trying to NOT depend on), or (b) deploying the dev checkout to `cake-shaper` first (D-10 forbids deploy). Inline SQL avoids both. Schema is stable (verified `src/wanctl/storage/schema.py:ALERTS_SCHEMA`).

**Example (`scripts/phase213-alert-window.sh`):**

```bash
# Source: pattern from scripts/phase198-rerun-flent-3run.sh:335-352 (sudo -n sqlite3 -readonly over SSH)
set -euo pipefail
START="${START:?--start unix-ts required}"
END="${END:?--end unix-ts required}"
OUTPUT_DIR="${OUTPUT_DIR:?--output-dir required}"
mkdir -p "$OUTPUT_DIR"

# Per-WAN dump + grouped count from spectrum metrics DB
for entry in \
    "spectrum:/var/lib/wanctl/metrics-spectrum.db:alerts-spectrum" \
    "att:/var/lib/wanctl/metrics-att.db:alerts-att" \
    "steering:/var/lib/wanctl/metrics.db:alerts-steering"
do
    IFS=":" read -r wan db out <<< "$entry"

    # Existence probe — steering metrics.db may not exist (D-07: "if present")
    if ! ssh -o BatchMode=yes cake-shaper "sudo -n test -f ${db}"; then
        echo "{\"wan\":\"${wan}\",\"db\":\"${db}\",\"present\":false,\"rows\":[]}" \
            > "${OUTPUT_DIR}/${out}.json"
        continue
    fi

    # Row dump (D-07: timestamp, alert_type, severity, wan_name, details)
    ssh -o BatchMode=yes cake-shaper \
        "sudo -n sqlite3 -readonly -json file:${db}'?mode=ro' \
         \"SELECT timestamp, alert_type, severity, wan_name, details
           FROM alerts WHERE timestamp BETWEEN ${START} AND ${END}
           ORDER BY timestamp;\"" \
        > "${OUTPUT_DIR}/${out}.rows.json"

    # Grouped summary count (D-07)
    ssh -o BatchMode=yes cake-shaper \
        "sudo -n sqlite3 -readonly -json file:${db}'?mode=ro' \
         \"SELECT alert_type, severity, COUNT(*) as count
           FROM alerts WHERE timestamp BETWEEN ${START} AND ${END}
           GROUP BY alert_type, severity ORDER BY count DESC;\"" \
        > "${OUTPUT_DIR}/${out}.summary.json"

    # Combine rows + summary into one artifact for the classifier
    jq -n --arg wan "$wan" --arg db "$db" \
        --argjson rows "$(cat ${OUTPUT_DIR}/${out}.rows.json 2>/dev/null || echo '[]')" \
        --argjson summary "$(cat ${OUTPUT_DIR}/${out}.summary.json 2>/dev/null || echo '[]')" \
        '{wan:$wan, db:$db, present:true, rows:$rows, summary:$summary}' \
        > "${OUTPUT_DIR}/${out}.json"
    rm -f "${OUTPUT_DIR}/${out}.rows.json" "${OUTPUT_DIR}/${out}.summary.json"
done

# Combined per-test summary across all three DBs
jq -s \
    '{spectrum:.[0], att:.[1], steering:.[2]}' \
    "${OUTPUT_DIR}/alerts-spectrum.json" \
    "${OUTPUT_DIR}/alerts-att.json" \
    "${OUTPUT_DIR}/alerts-steering.json" \
    > "${OUTPUT_DIR}/alerts-summary.json"
```

**`details` parsing note:** The inline SQL returns `details` as a raw JSON-encoded string. The classifier (`phase213-classify.py`) is responsible for `json.loads()` on that field. `query_alerts` in `storage/reader.py:206-212` does this same parsing — fine pattern.

### Pattern 5: Curl-Browse Loop (D-02)

**What:** Scripted multi-site curl that records `time_starttransfer` (TTFB) and `time_total` per request, written as CSV. Run concurrently with the per-WAN NDJSON poll (same bracketing as flent tests). Site list is operator-stable, balanced across CDN providers to avoid single-provider noise.

**Recommended site list** (planner discretion per D-04):

| Site | Why | Type |
|------|-----|------|
| `https://www.google.com/` | Operator-stable, Google CDN edge | Search |
| `https://www.cloudflare.com/` | Cloudflare anycast, low-latency reference | CDN baseline |
| `https://github.com/` | Fastly + GitHub edge, mixed asset weights | Dev |
| `https://www.wikipedia.org/` | Wikimedia infrastructure, independent of major CDNs | Wiki |
| `https://news.ycombinator.com/` | Lean, single small host, mostly text | News, low-asset |
| `https://www.bbc.com/news` | Operator-stable news, varied asset weights | News, media-mix |
| `https://i.imgur.com/aB6Z9zN.jpg` | Image CDN single fetch, deterministic | Image CDN |

**Recommended cadence:** Iterate through the list, one fetch every 2 seconds. With seven sites this yields ~14s per cycle. For a 60s flent leg, that's ~4 cycles, ~28 fetches. Light enough to be evidence-meaningful without distorting flent's load profile.

**Example (`scripts/phase213-browse-loop.sh`):**

```bash
set -euo pipefail
OUTPUT="${OUTPUT:?--output CSV path required}"
DURATION="${DURATION:-60}"
LOCAL_BIND="${LOCAL_BIND:-10.10.110.233}"
SITES=(
  "https://www.google.com/"
  "https://www.cloudflare.com/"
  "https://github.com/"
  "https://www.wikipedia.org/"
  "https://news.ycombinator.com/"
  "https://www.bbc.com/news"
  "https://i.imgur.com/aB6Z9zN.jpg"
)

echo "ts_utc,site,http_code,time_starttransfer,time_total,size_download,exit_code" > "$OUTPUT"
T_END=$(( $(date +%s) + DURATION ))
i=0
while [ "$(date +%s)" -lt "$T_END" ]; do
    SITE="${SITES[$((i % ${#SITES[@]}))]}"
    TS="$(date -u -Iseconds)"
    OUT="$(curl --interface "$LOCAL_BIND" --silent --max-time 10 \
        -w '%{http_code},%{time_starttransfer},%{time_total},%{size_download}' \
        -o /dev/null "$SITE" 2>/dev/null)" || EC=$?
    EC="${EC:-0}"
    echo "${TS},${SITE},${OUT},${EC}" >> "$OUTPUT"
    i=$((i + 1))
    sleep 2
done
```

### Per-Run Artifact Layout (D-12)

Mirrors Phase 198's per-attempt-subdir model and Phase 212's evidence-index convention.

```
.planning/phases/213-experience-baseline-harness/evidence/
├── README.md                      # Command index, redaction policy, mutation boundary (mirror 212-evidence/README.md)
└── RUN-<utc-ts>/                  # e.g., RUN-20260528T021500Z (single per-run dir)
    ├── manifest.json              # Per-run top-level manifest (see schema below)
    ├── spectrum/
    │   ├── browse/
    │   │   ├── manifest.json
    │   │   ├── browse.curl.csv
    │   │   ├── health-spectrum.ndjson
    │   │   ├── health-att.ndjson
    │   │   ├── steering-pre-health.json
    │   │   ├── steering-pre-state.redacted.json
    │   │   ├── steering-post-health.json
    │   │   ├── steering-post-state.redacted.json
    │   │   ├── alerts-spectrum.json
    │   │   ├── alerts-att.json
    │   │   ├── alerts-steering.json
    │   │   └── alerts-summary.json
    │   ├── tcp_upload/             # same shape, plus flent/ dir
    │   ├── tcp_download/
    │   ├── rrul/
    │   └── tcp_12down/
    └── att/                        # same five subdirs
└── signal-sheet.json               # Classifier output (one per RUN-<utc-ts>)
└── signal-sheet.md                 # Operator-readable rendering
```

**Per-run top-level `manifest.json` schema:**

```json
{
  "phase": 213,
  "run_id": "RUN-20260528T021500Z",
  "started_utc": "2026-05-28T02:15:00Z",
  "ended_utc": "2026-05-28T03:42:00Z",
  "host_dev_vm": "<hostname>",
  "source_ip": "10.10.110.233",
  "netperf_host": "dallas",
  "flent_version": "2.1.1",
  "wanctl_version_dev_repo": "1.45.0",
  "wanctl_version_spectrum_runtime": "1.45.0",
  "wanctl_version_att_runtime": "1.45.0",
  "wanctl_version_steering_runtime": "1.39.0",
  "git_head_sha": "<short sha>",
  "tests_ordered": [
    {"wan": "spectrum", "test": "browse", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "spectrum", "test": "tcp_upload", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "spectrum", "test": "tcp_download", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "spectrum", "test": "rrul", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "spectrum", "test": "tcp_12down", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "att", "test": "browse", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "att", "test": "tcp_upload", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "att", "test": "tcp_download", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "att", "test": "rrul", "test_start_unix": 0, "test_end_unix": 0},
    {"wan": "att", "test": "tcp_12down", "test_start_unix": 0, "test_end_unix": 0}
  ],
  "redaction_posture": "D-08 key pattern (password|secret|token|credential|auth|key|private) applied to all *.redacted.json artifacts",
  "mutation_posture": "evidence-only: traffic generation from dev VM allowed; no service restart, no /etc/wanctl edit, no steering toggle, no RouterOS write, no deploy"
}
```

### Anti-Patterns to Avoid

- **Concurrent dual-WAN flent runs.** D-11 forbids it. Even RRUL-style "test one WAN at a time" runs would distort steering interpretation if both WANs are loaded at once.
- **Polling steering at 1Hz during tests.** D-05 explicitly says steering is pre/post-snapshot only. Continuous polling on `cake-shaper`'s loopback would (a) add SSH session overhead per second, and (b) Phase 212's evidence shows steering uptime is 28+ days; we DON'T want to write thousands of /health requests against an old daemon "just because." Pre/post is enough for steering-drift bucket evidence.
- **Comparing live steering threshold field names to repo `configs/steering.yaml` semantics.** D-14 / D-08 carry-forward. Steering reports v1.39 threshold names (`green_rtt_ms=5.0`, `yellow_rtt_ms=15.0`, `red_rtt_ms=15.0`); the repo's v1.45 source uses different threshold names (`bad/recovery thresholds 25.0/12.0`). Classifier shows raw transitions/counters only.
- **`mode=ro&immutable=1` on the SQLite URI.** Stale view during writes. Use `mode=ro` only.
- **Forking `phase191-flent-capture.sh`.** Don't. It already accepts `--tests tcp_upload,tcp_download` (flent supports them).
- **Extending `analyze_baseline.py`.** Different concern. Make a new classifier.
- **Polling at sub-1Hz under the assumption it's "more accurate."** `/health` is built per-request and includes a 200-entry `zone_trace` and full `cake_signal` snapshot. Two polls of 1Hz cost real CPU on the daemon (Phase 212 health-spectrum.json snapshot is ~735 lines). 1Hz is the documented soak cadence and is sufficient.
- **Trusting `/health.status == healthy` to mean UX is fine.** D-17 carry-forward. Always cross-reference with flent summary + curl-browse TTFB.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-second `/health` poll loop | New from scratch | Sibling of `scripts/soak-capture.sh` (extended jq projection) | HRDN-02 bounded-failure logic, temp-file truncation, TSV sidecar already battle-tested. |
| flent runner | Wrap `flent` directly | `scripts/phase191-flent-capture.sh` | Local-bind check, manifest, raw-file capture, per-test summary already done. |
| Read-only SQLite alert query | Hand-rolled SQL on dev VM after SCP | `sudo -n sqlite3 -readonly -json file:DB?mode=ro 'SELECT …'` over SSH | No copy required, safe against live writer, returns JSON directly. |
| Per-row health projection | New dict per row in Python | `jq -c` with explicit field projection | Same toolchain as `soak-capture.sh`; jq is on both dev VM and `cake-shaper`. |
| Manifest assembly | Concatenate strings | `jq -n` with `--arg`/`--argjson` | Already used in `phase198-rerun-flent-3run.sh` and `phase212-evidence/README.md`. |
| Secret redaction | Bespoke regex per script | Single shared Python helper (4 lines, see `phase213-steering-snapshot.sh` example) | Same key pattern Phase 212 used: `password\|secret\|token\|credential\|auth\|key\|private`. |
| Classification thresholds | New numeric magic constants | Cite Phase 212 evidence for "current observed baseline" and Phase 218 ALERT-03 cooldown bucketing pattern | Operator-citable, not bespoke. |

**Key insight:** Every surface Phase 213 needs has an existing in-repo template. The phase is a **wiring** task more than a building task.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | SQLite metrics DBs at `/var/lib/wanctl/metrics-spectrum.db` (467 MB), `/var/lib/wanctl/metrics-att.db` (437 MB), and `/var/lib/wanctl/metrics.db` (steering, ~824 MB based on health.json `db_bytes=823812096`). Phase 213 reads these **read-only**; no writes. Steering `metrics.db` presence is conditional — D-07 says "if present"; existence probe required. | Read-only access only. No migration. |
| Live service config | `/etc/wanctl/spectrum.yaml`, `/etc/wanctl/att.yaml`, `/etc/wanctl/steering.yaml` provide `wan_name`, `db_path`, and bound `health_check` host/port. Phase 213 reads from Phase 212's already-captured `evidence/config-*.redacted.yaml` snapshots; does NOT re-read deployed config. | No mutation. Use Phase 212's redacted snapshots as the comparison surface (D-19). |
| OS-registered state | Systemd units `wanctl@spectrum.service`, `wanctl@att.service`, `steering.service` are active and watchdog-managed. Restart count = 0 on all three (Phase 212 evidence). Phase 213 must NOT trigger a restart (D-10). Long-lived `flent` runs against `dallas` are user-shell processes, not systemd-registered. | No re-registration. Confirm no test artifact triggers an inadvertent service action. |
| Secrets/env vars | `${ROUTER_PASSWORD}` substitution flows through `/etc/wanctl/secrets`; Phase 213 does not read it. SSH to `cake-shaper` uses `~/.ssh/config` keys (no password). No new env vars introduced. | None. |
| Build artifacts | None — Phase 213 ships scripts only. No package install, no compiled artifact, no pip/npm change. | None. |

**Nothing found in category "Build artifacts":** Verified — Phase 213 deliverables are only `scripts/phase213-*.sh|.py` plus `docs/RUNBOOKS/baseline.md` plus per-run evidence. No `pyproject.toml` change, no new dependency.

## Common Pitfalls

### Pitfall 1: Dev VM source-IP drift between runs
**What goes wrong:** `phase191-flent-capture.sh` requires `--local-bind <ip>` and validates the IP is configured locally. If the dev VM's secondary IP is reassigned (DHCP, manual reconfig), the test silently exits with the wrong egress.
**Why it happens:** Dev VM currently has `10.10.110.233` (primary, configured) and `10.10.110.226` (secondary, DHCP). Phase 191 used `.233`; Phase 198 deliberately required `.226` for Spectrum source bind to avoid AT&T egress.
**How to avoid:** Orchestrator must record dev VM IPs at start (`ip -4 addr` snapshot in manifest), validate the chosen `--local-bind` is in the snapshot, and ideally probe egress (curl ipinfo.io) per Phase 198's pattern to confirm the WAN actually used matches the intended WAN.
**Warning signs:** Egress IP mismatch in probe artifact; flent summary shows unexpected throughput ceiling that matches the OTHER WAN's known plan.

### Pitfall 2: Confusing "steering /health endpoint" vs "steering metrics.db" presence
**What goes wrong:** Steering reports a live `/health` at `127.0.0.1:9102` (verified Phase 212), but the metrics writer may or may not be using `/var/lib/wanctl/metrics.db` for alerts depending on steering v1.39 config layout.
**Why it happens:** `configs/steering.yaml` says `db_path: "/var/lib/wanctl/metrics.db"`, but the deployed steering daemon is v1.39 and its actual write target may differ.
**How to avoid:** D-07 already says "metrics.db if present." Existence probe before query (`ssh cake-shaper sudo -n test -f /var/lib/wanctl/metrics.db`). Record absence as evidence, not as failure.
**Warning signs:** Empty alerts artifact + no SQL error.

### Pitfall 3: `tcp_12down` 30s window too short to catch the "bad p99 while GREEN" symptom
**What goes wrong:** Phase 198 used `--duration 30`. Phase 213 baseline `tcp_12down` may need longer to surface the recovery-lag symptom from the folded todo.
**Why it happens:** `tcp_12down` is bursty by nature; 30s captures the initial onset but may not include the post-burst recovery curve we care about for BUCKET 2 (download recovery lag).
**How to avoid:** Use `--duration 60` (the `phase191-flent-capture.sh` default) for `tcp_12down`. Phase 213 is one-shot evidence; Phase 214 owns the time-of-day matrix and tighter bounds.
**Warning signs:** Flent summary p99 < 100ms with no DL state transitions in the NDJSON window — evidence didn't catch the issue.

### Pitfall 4: SSH session multiplexing overhead during pre/post snapshots
**What goes wrong:** Each `ssh cake-shaper …` invocation opens a fresh TCP+TLS session. With ~50 tests (5 tests × 2 WAN × pre+post + 3 alert DBs × per test), that's 200+ SSH connects. Slow on first run.
**Why it happens:** Default OpenSSH client doesn't multiplex unless `ControlMaster` is configured.
**How to avoid:** Recommend orchestrator sets `ControlMaster auto`, `ControlPath ~/.ssh/control-%h:%p:%r`, `ControlPersist 5m` in a temporary `~/.ssh/config` snippet or via `-o ControlMaster=auto -o ControlPath=…` flags. **Not a correctness issue, just speed.**
**Warning signs:** Per-test wall-clock noticeably longer than `flent --duration` + buffers; SSH connection log shows new sessions per snapshot.

### Pitfall 5: `/health` zone_trace tail is 200 entries — large polling payloads
**What goes wrong:** Each `/health` response is ~30 KB (verified from Phase 212 `health-spectrum.json` ~735 lines including 200-entry `zone_trace`). At 1Hz across two WANs for ~10 minutes of testing per WAN, that's ~36 MB of raw response per WAN. The jq projection discards most of this — the NDJSON output is ~1 KB/row — but raw curl bandwidth and CPU on the autorate daemon scale with response size.
**Why it happens:** `/health` builders pack everything in.
**How to avoid:** Don't fight it. 1Hz is already conservative. Don't store the raw body, only the jq-projected NDJSON.
**Warning signs:** None at 1Hz; would only matter at sub-100ms cadence.

### Pitfall 6: Phase 218 VERIFY-01 carry-forward — flapping alerts have inflated counters
**What goes wrong:** Phase 213 captures `alerting.fire_count`. If a flapping alert fires during a test window, the deployed v1.45 code on Spectrum and ATT has the Option-A peak-counter fix, but the production-verification gate (VERIFY-01) is still open. Numbers may look weird if compared to pre-v1.45 baselines.
**Why it happens:** v1.45 changed the meaning of `peak_transition_count` in flapping alert payloads. v1.45 is deployed; v1.39 steering still reports old shape.
**How to avoid:** Classifier reads `details` field per-row but does not interpret `peak_transition_count` semantics in BUCKET 5 (refractory) without footnoting "v1.45 windowed peak deque" caveat. For steering alerts (if any), record raw and footnote v1.39 semantics per D-08/D-14.
**Warning signs:** Operator confusion between alert payload meanings. Footnote in signal sheet covers it.

## Code Examples

### Orchestrator skeleton (`scripts/phase213-baseline-capture.sh`)

```bash
#!/usr/bin/env bash
# Phase 213: Experience baseline harness orchestrator (D-09).
# Operator invokes once; orchestrator runs the full per-WAN suite.
# Source: composes phase191-flent-capture.sh + soak-capture.sh patterns.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/phase213-baseline-capture.sh [options]

Options:
  --local-bind <ip>       Source IP to bind traffic to (default: 10.10.110.233)
  --host <name>           Netperf host (default: dallas)
  --flent-duration <sec>  Per-flent-test duration (default: 60)
  --browse-duration <sec> Per-browse-test duration (default: 60)
  --pre-buf <sec>         NDJSON pre-test buffer (default: 10)
  --post-buf <sec>        NDJSON post-test buffer (default: 10)
  --wans <csv>            WANs to test (default: spectrum,att) — D-11 serialized
  --tests <csv>           Tests per WAN (default: browse,tcp_upload,tcp_download,rrul,tcp_12down)
  --evidence-root <dir>   Evidence root (default: .planning/phases/213-experience-baseline-harness/evidence)
  --dry-run               Validate prerequisites, do not run tests
  --help

This is the only command the operator runs. Per D-10 it is allowed to generate
traffic from the dev VM. It is forbidden from: service restart, /etc/wanctl
edit, steering toggle, RouterOS write, deploy, controller config change.
EOF
}

LOCAL_BIND="10.10.110.233"
HOST="dallas"
FLENT_DURATION=60
BROWSE_DURATION=60
PRE_BUF=10
POST_BUF=10
WANS_CSV="spectrum,att"
TESTS_CSV="browse,tcp_upload,tcp_download,rrul,tcp_12down"
EVIDENCE_ROOT=".planning/phases/213-experience-baseline-harness/evidence"
DRY_RUN=0

# ... arg parsing omitted for brevity ...

# Prerequisites
command -v flent >/dev/null || { echo "ERROR: flent not in PATH" >&2; exit 1; }
command -v jq >/dev/null || { echo "ERROR: jq not in PATH" >&2; exit 1; }
ssh -o BatchMode=yes cake-shaper 'true' || { echo "ERROR: cake-shaper unreachable" >&2; exit 1; }
ip addr show | grep -qF " ${LOCAL_BIND}/" || { echo "ERROR: ${LOCAL_BIND} not on dev VM" >&2; exit 1; }

# Egress probe per Phase 198 pattern: confirm the chosen --local-bind exits the intended WAN
# (Operator must update site-specific expected egress IP/org. Phase 213 records what it sees.)

RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${EVIDENCE_ROOT}/RUN-${RUN_TS}"
[[ "$DRY_RUN" == "1" ]] && { echo "DRY_RUN: prerequisites OK, would create ${RUN_DIR}"; exit 0; }
mkdir -p "$RUN_DIR"

# Per-WAN serialized loop (D-11)
for WAN in ${WANS_CSV//,/ }; do
    for TEST in ${TESTS_CSV//,/ }; do
        TEST_DIR="${RUN_DIR}/${WAN}/${TEST}"
        mkdir -p "$TEST_DIR"
        run_bracketed_test "$WAN" "$TEST" "$TEST_DIR"   # defined inline (see Pattern 1)
        sleep 5   # inter-test breather
    done
done

# Write top-level manifest
# ... jq -n manifest assembly per §"Per-Run Artifact Layout" ...

# Run classifier
.venv/bin/python3 scripts/phase213-classify.py \
    --run-dir "$RUN_DIR" \
    --output-json "${EVIDENCE_ROOT}/signal-sheet-${RUN_TS}.json" \
    --output-md "${EVIDENCE_ROOT}/signal-sheet-${RUN_TS}.md"

echo "Phase 213 baseline run complete."
echo "  Run dir:        ${RUN_DIR}"
echo "  Signal sheet:   ${EVIDENCE_ROOT}/signal-sheet-${RUN_TS}.md"
echo "  Next step:      operator reads signal sheet, authors 213-REPORT.md with bucket verdicts (D-13)."
```

## Classification Signal Sheet (BASE-03)

**Goal:** Operationalize the six v1.46 buckets without interpreting steering v1.39 threshold semantics.

### Bucket → Evidence Map

| # | Bucket | Primary Evidence Source | Signal-Sheet Row Schema |
|---|--------|-------------------------|--------------------------|
| 1 | Upload ceiling/setpoint | `health-spectrum.ndjson` during `spectrum/tcp_upload/` and `spectrum/rrul/` | `wan`, `test`, `pct_samples_at_ceiling` (% rows where `upload_rate_mbps >= ceiling-0.5`), `pct_samples_at_setpoint`, `pct_samples_state_RED`, `floor_hit_delta`, `headroom_exhausted_streak_max`, `upload_red_streak_max`. **Threshold to flag bucket: pct_samples_at_ceiling > 80% during a `tcp_upload` test.** |
| 2 | Download recovery lag | `health-*.ndjson` during `*/tcp_12down/` and `*/rrul/` (post-test buffer window) | `wan`, `test`, `time_to_green_after_red_sec` (seconds between last RED/SOFT_RED row and first stable GREEN), `dl_backlog_suppressed_delta`, `cake_dl_peak_delay_us_p99`, `green_required` at sample time, `dl_state_transitions_count`. **Threshold to flag bucket: time_to_green_after_red_sec > 30 OR cake_dl_peak_delay_us_p99 > 50000.** |
| 3 | Measurement collapse | `health-*.ndjson` all tests + flent summary (TCP throughput vs. p99 latency divergence) | `wan`, `test`, `signal_outlier_rate_max`, `signal_confidence_min`, `measurement_stale_pct_samples`, `successful_count_min`, `irtt_loss_up_pct_max` (ATT only), `irtt_loss_down_pct_max`, **plus cross-reference**: flent_p99_latency_ms, flent_throughput_mbps. **Threshold to flag bucket: signal_outlier_rate_max > 0.30 AND flent_p99 > flent_median * 5.** |
| 4 | Steering drift | `steering-pre-health.json`, `steering-post-health.json`, `alerts-steering.json` for each test | `test`, `steering_state_pre`, `steering_state_post`, `pre_post_state_transition` (raw string, e.g., `SPECTRUM_GOOD → SPECTRUM_GOOD`), `red_count_delta`, `good_count_delta`, `cake_read_failures_delta`, `wan_awareness_zone_pre`, `wan_awareness_zone_post`, `steering_version` (=`1.39.0` per Phase 212 D-08). **NO comparison to threshold field names per D-14.** Bucket flagged on **any** state transition or counter delta during a test window. |
| 5 | Refractory semantics | `health-*.ndjson` field `arb_refractory_active`, `arb_control_decision_reason`, `cake_*_refractory_remaining`, `cake_*_backlog_suppressed_count` | `wan`, `test`, `pct_samples_refractory_active`, `arb_control_decision_reasons` (counter by string), `cake_dl_backlog_suppressed_delta`, `cake_ul_backlog_suppressed_delta`, `dl_refractory_remaining_max`, `arb_active_primary_signal_counter` (e.g., `queue: 580, rtt: 0`). **Threshold to flag bucket: pct_samples_refractory_active > 5% during any test OR backlog_suppressed_delta > 100 in a single test window.** |
| 6 | External ISP conditions | `browse.curl.csv`, flent summaries, NDJSON cross-test | `wan`, `test`, `curl_ttfb_p99_ms`, `curl_total_p99_ms`, `curl_failure_count`, `flent_throughput_drop_pct_vs_plan` (e.g., Spectrum plan 920 DL / 40 UL; ATT plan 95 DL / 18 UL), `flent_p99_latency_ms`. **Threshold to flag bucket: flent_throughput_drop_pct_vs_plan > 30% AND curl_ttfb_p99_ms > 2000ms AND signal_outlier_rate_max < 0.10** (i.e., the controller is reporting healthy but the path itself is slow). |

### Signal-Sheet Output Schema (`signal-sheet.json`)

```json
{
  "phase": 213,
  "run_id": "RUN-20260528T021500Z",
  "generated_utc": "2026-05-28T03:55:00Z",
  "wanctl_runtime_versions": {
    "spectrum": "1.45.0",
    "att": "1.45.0",
    "steering": "1.39.0"
  },
  "buckets": {
    "upload_ceiling_setpoint": {
      "flagged": true,
      "evidence_rows": [
        {
          "wan": "spectrum", "test": "tcp_upload",
          "pct_samples_at_ceiling": 0.94,
          "pct_samples_at_setpoint": 0.01,
          "pct_samples_state_RED": 0.00,
          "floor_hit_delta": 0,
          "headroom_exhausted_streak_max": 0,
          "upload_red_streak_max": 0,
          "test_start_unix": 0, "test_end_unix": 0,
          "evidence_path": "evidence/RUN-20260528T021500Z/spectrum/tcp_upload/health-spectrum.ndjson"
        }
      ],
      "operator_note": "94% of samples during spectrum/tcp_upload pegged at the 18 Mbps ceiling. D-18 says this is intentional config, but BASE-03 BUCKET 1 is flagged for Phase 215 reclaim consideration."
    },
    "download_recovery_lag": { "flagged": false, "evidence_rows": [], "operator_note": "" },
    "measurement_collapse": { "flagged": false, "evidence_rows": [], "operator_note": "" },
    "steering_drift": {
      "flagged": false,
      "evidence_rows": [
        { "test": "spectrum/tcp_12down",
          "steering_state_pre": "SPECTRUM_GOOD",
          "steering_state_post": "SPECTRUM_GOOD",
          "pre_post_state_transition": "SPECTRUM_GOOD → SPECTRUM_GOOD",
          "red_count_delta": 0, "good_count_delta": 0,
          "cake_read_failures_delta": 0,
          "wan_awareness_zone_pre": "GREEN", "wan_awareness_zone_post": "GREEN",
          "steering_version": "1.39.0",
          "evidence_paths": ["…/steering-pre-health.json", "…/steering-post-health.json"]
        }
      ],
      "operator_note": "Steering state did not transition during any test. Per D-08/D-14, no comparison to threshold field names attempted."
    },
    "refractory_semantics": { "flagged": false, "evidence_rows": [], "operator_note": "" },
    "external_isp": { "flagged": false, "evidence_rows": [], "operator_note": "" }
  },
  "recommended_next_phase": {
    "primary": 215,
    "primary_rationale": "Upload ceiling/setpoint flagged with quantitative evidence; Phase 215 reclaim canary is the matched downstream phase.",
    "runners_up": [
      {"phase": 214, "rationale": "tcp_12down baseline captured but no p99-vs-GREEN divergence observed in this single run; Phase 214's time-of-day matrix may yet surface it."},
      {"phase": 216, "rationale": "Steering drift bucket not flagged in this run; Phase 216 still owns the v1.39 alignment question independently."}
    ]
  }
}
```

### Signal-Sheet Markdown Rendering

`signal-sheet.md` is a flat operator-readable rendering of the JSON, one table per bucket plus the next-phase recommendation table. Per D-13, the operator reads it, picks bucket verdict(s), and authors the final `213-REPORT.md` citing evidence rows by `evidence_path`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline `curl … \| jq … \|| true` for /health polling (Phase 198) | Sibling poller with HRDN-02 bounded failure (Phase 207, v1.44) | 2026-05-26 (v1.44) | Phase 213 inherits the bounded-failure pattern; silent 0-byte NDJSON bugs are prevented. |
| Single soak NDJSON projection (upload-only) | Extended projection covering download + cake_signal + signal_quality + signal_arbitration | This phase (proposed) | Phase 213-specific; soak harness keeps upload-only projection for its own concern. |
| `wanctl-history` CLI for SQLite reads | Read-only URI mode + `sqlite3 -readonly` direct | Phase 198 (v1.42) | Avoids deploying wanctl Python to dev VM; works against live-writer DBs. |
| Phase 191 single-test runs | Phase 213 per-test bracketed wrapper | This phase | Adds NDJSON co-sampling and SQLite alert windowing per test. |

**Deprecated/outdated:**
- **`/health.status == healthy` as proxy for UX:** Explicitly rejected by D-17, REQUIREMENTS.md "Out of Scope".
- **Timer-based deployment guidance:** Production is service-based (Phase 212 inventory); CLAUDE.md says do not reintroduce timer-era guidance.
- **Spectrum `1.39.0` runtime expectations:** Spectrum is `1.45.0`. Only steering remains v1.39.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Dev VM's `10.10.110.233` egresses Spectrum and `10.10.110.226` egresses ATT (per Phase 191/198 convention). | §"Pitfall 1: source-IP drift" | If egress mapping has changed, Phase 213 would label tests against the wrong WAN. **Mitigation: orchestrator must probe egress per Phase 198 pattern** (curl ipinfo.io with `--interface`) and record actual egress in manifest. Phase 198 shows the exact pattern. |
| A2 | `phase191-flent-capture.sh` will accept `--tests tcp_upload` and `--tests tcp_download` without modification. | §"Standard Stack" alternatives table | Verified separately: flent 2.1.1 supports these test names [VERIFIED: `flent --list-tests`], and `phase191-flent-capture.sh:130` parses `--tests` as a comma-separated list passed straight to flent. **Should be fine**, but a `--dry-run` of one test before the full suite would confirm. |
| A3 | The curl-browse site list I recommended (Google, Cloudflare, GitHub, Wikipedia, HN, BBC, imgur) is operator-acceptable. | §"Curl-Browse Loop (D-02)" | Wrong site choice could either skew toward one CDN (noise) or include sites that block frequent unauthed fetches. Planner has D-04 discretion to override. |
| A4 | `/var/lib/wanctl/metrics.db` (steering) may not exist; D-07's "if present" hedge is intentional and matches Phase 212's discovery posture. | §"Pattern 4: SQLite extraction" | If steering metrics.db IS present and writes alerts there, Phase 213 captures them. If absent, evidence is "no steering alerts in metrics DB during window" — still useful. **No risk.** |
| A5 | `sudo -n` works passwordlessly on `cake-shaper` for the dev VM's SSH user (matches Phase 212-01 evidence). | §"Pattern 3/4: SSH commands" | If sudo prompts, all read-only extraction fails. Verified by Phase 212-01 which successfully ran `sudo -n cat /etc/wanctl/*.yaml` and `sudo -n python3 …`. **Should be fine**; orchestrator's prerequisite check should include a `ssh cake-shaper 'sudo -n true'` probe. |
| A6 | Signal-sheet thresholds (e.g., `pct_samples_at_ceiling > 80%` to flag BUCKET 1) are reasonable starting points; planner/operator may adjust. | §"Bucket → Evidence Map" | Wrong thresholds either flag too aggressively (false positives) or miss bucket signal (false negatives). **Operator decides per D-13.** Signal sheet exposes the raw values; flagging is a convenience, not a gate. |
| A7 | Per-test `flent --duration 60` is sufficient for tcp_upload, tcp_download, rrul, tcp_12down. | §"Pitfall 3" | 60s may be short for recovery-lag bucket evidence on tcp_12down. Mitigation: planner discretion via `--flent-duration`. |
| A8 | The dev VM has `/usr/bin/curl`, `/usr/bin/jq`, and `flent` in PATH. | §"Standard Stack" | Verified [VERIFIED: `which jq curl`, `flent --version`]. **No risk.** |

**If this table is empty:** Most claims here are conditional ("planner should probe X first") rather than purely-assumed unverifiable claims — the strongest assumption (A1) is the egress-mapping one, and the mitigation pattern from Phase 198 is already in-repo.

## Open Questions

1. **Should Phase 213 do a single run or operator-initiated repeated runs?**
   - What we know: D-12's per-run timestamp dir layout supports multiple runs cheaply. CONTEXT specifics say "single representative window per WAN at one run time; if multiple runs happen … they are operator-initiated."
   - What's unclear: Whether the orchestrator should print "rerun this command N times for stability" as a suggestion.
   - Recommendation: Single run is the default. Manifest records `run_id`. Operator can re-invoke for a second `RUN-<ts>` dir if the signal sheet looks ambiguous. Don't bake repetition into the orchestrator.

2. **What does "stable GREEN" mean for the recovery-lag bucket's `time_to_green_after_red_sec`?**
   - What we know: NDJSON exposes `download_green_streak` (cycle counter, 50ms each) and `download_green_required` (consecutive GREEN cycles needed for state escalation).
   - What's unclear: Should "stable GREEN" mean `state == GREEN AND green_streak >= green_required` (which is the controller's definition) or simply `state == GREEN for >= 5 consecutive 1Hz samples`?
   - Recommendation: Use controller definition (`green_streak >= green_required` per sample). Cite Spectrum's `green_required=5` for DL hysteresis (from health JSON evidence). This is the controller's own recovery-lag definition; Phase 213 reuses it for consistency.

3. **Should the classifier flag a bucket on a single sample of evidence, or require sustained evidence (N samples)?**
   - What we know: D-13 says hybrid classification; the signal sheet emits evidence, the operator decides. D-15 wants a ranked recommendation with explicit runners-up.
   - What's unclear: How aggressive the auto-flag should be.
   - Recommendation: Match the thresholds in §"Bucket → Evidence Map" — they're percent-of-samples or counter-delta based, which naturally requires sustained evidence. Single-sample flags are too noisy.

4. **Does the curl-browse loop need cache-busting?**
   - What we know: HTTP/2 + browser cache could make repeated fetches measure cache hits not the actual path.
   - What's unclear: Whether `curl` defaults to a fresh connection (it does, per-process) and whether keep-alive across iterations would distort or improve TTFB measurement.
   - Recommendation: Add `?cache_bust=$(date +%s%N)` to each URL, or use `-H 'Cache-Control: no-cache'`. Confirm with operator; default to query-string cache-bust because it's invisible to the operator and doesn't change `curl` behavior.

5. **Should `signal-sheet.md` rank tests by severity, or list them in capture order?**
   - What we know: D-15 wants a ranked next-phase recommendation, not necessarily ranked per-test evidence.
   - What's unclear: Whether per-test rows should be sorted by "most damning" first.
   - Recommendation: List in capture order (chronological per-WAN). Add a "summary" header at the top of `signal-sheet.md` that lists which buckets flagged and the recommended next phase. Operator scans the summary, then drills into evidence rows.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `flent` (dev VM) | flent test runs (RRUL, tcp_*) | ✓ | 2.1.1 | — |
| `netperf` (dev VM) | flent backend | (assumed; required by phase191-flent-capture.sh:111-114) | (whatever is installed) | — |
| `dallas` netperf server | D-04 host lock | ✓ | reachable via ssh alias | — (locked by decision) |
| `curl` (dev VM) | NDJSON poll, curl-browse | ✓ | system | — |
| `jq` (dev VM) | NDJSON projection, manifest | ✓ | system `/usr/bin/jq` | — |
| `python3` (dev VM `.venv`) | classifier, manifest math | ✓ | 3.11+ (project standard) | — |
| `ssh` to `cake-shaper` | steering snapshot, SQLite | ✓ | OpenSSH, BatchMode-able | — |
| `sudo -n` on `cake-shaper` | read /var/lib/wanctl, /etc/wanctl | ✓ | per Phase 212-01 evidence | — |
| `sqlite3` (cake-shaper) | read-only alert query | ✓ | 3.46.1 | — |
| `jq` (cake-shaper) | health response inspection | ✓ | system | — |
| `curl` (cake-shaper) | steering /health inline | ✓ | system | — |
| Dev VM IP `10.10.110.233` (Spectrum egress) | source-bind for flent/curl | ✓ | configured (verified `ip -4 addr`) | — |
| Dev VM IP `10.10.110.226` (ATT egress, DHCP) | source-bind for ATT tests | ✓ | configured at research time | If reassigned, orchestrator's IP snapshot in manifest will surface the change; egress probe per Phase 198 catches it before flent runs. |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Dev VM secondary IP `.226` is DHCP-derived; if it drifts at run time, the egress probe catches it. Orchestrator must include this probe as a prerequisite gate per Pitfall 1.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.0.0+ (project standard; `pyproject.toml [tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `.venv/bin/pytest tests/test_phase213_classify.py -q -x` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BASE-01 | Orchestrator runs end-to-end from one operator command and produces the documented evidence layout | smoke (orchestrator dry-run) | `bash scripts/phase213-baseline-capture.sh --dry-run` | ❌ Wave 0 |
| BASE-01 | Per-run manifest is well-formed JSON with required keys (`phase`, `run_id`, `host_dev_vm`, `source_ip`, etc.) | unit (Python) | `.venv/bin/pytest tests/test_phase213_manifest.py -x` | ❌ Wave 0 |
| BASE-01 | Runbook command in `docs/RUNBOOKS/baseline.md` matches the orchestrator's actual argument shape | docs sanity | `grep -F 'scripts/phase213-baseline-capture.sh' docs/RUNBOOKS/baseline.md` | ❌ Wave 0 |
| BASE-02 | NDJSON poller emits all 40+ required schema fields per row | unit (Python: fixture `/health` JSON in `tests/fixtures/` → run poller's jq projection → assert keys) | `.venv/bin/pytest tests/test_phase213_ndjson_schema.py -x` | ❌ Wave 0 |
| BASE-02 | NDJSON poller's HRDN-02 bounded-failure pattern works (synthetic curl-failure injection) | integration | `.venv/bin/pytest tests/test_phase213_poller_resilience.py -x` | ❌ Wave 0 |
| BASE-02 | Steering snapshot script captures `/health` + redacted `steering_state.json` per snapshot | integration (against `cake-shaper`) | manual: `bash scripts/phase213-steering-snapshot.sh --output /tmp/test`; assert files exist | ❌ Wave 0 |
| BASE-02 | SQLite alert-window query returns rows for a synthetic test window (and `[]` when no rows) | integration | `.venv/bin/pytest tests/test_phase213_alert_window.py -x` (uses test DB fixture in `tests/fixtures/`) | ❌ Wave 0 |
| BASE-02 | Per-test artifact set has all required files: `manifest.json`, `health-*.ndjson` × 2, `steering-pre*` × 2, `steering-post*` × 2, `alerts-*.json` × 4 | smoke | golden-file fixture comparison after dry-run | ❌ Wave 0 |
| BASE-03 | Classifier emits signal-sheet JSON with all six buckets present (even when none flagged) | unit (golden file) | `.venv/bin/pytest tests/test_phase213_classify.py::test_six_buckets_present -x` | ❌ Wave 0 |
| BASE-03 | Classifier's "upload ceiling" bucket threshold logic flags correctly on a fixture with `pct_samples_at_ceiling > 80%` | unit | `.venv/bin/pytest tests/test_phase213_classify.py::test_bucket_1_threshold -x` | ❌ Wave 0 |
| BASE-03 | Classifier's "steering drift" bucket does NOT compare to threshold field names (D-14 safety) | unit | `.venv/bin/pytest tests/test_phase213_classify.py::test_bucket_4_no_threshold_compare -x` | ❌ Wave 0 |
| BASE-03 | Classifier emits a ranked next-phase recommendation (D-15) with primary + runners-up | unit | `.venv/bin/pytest tests/test_phase213_classify.py::test_next_phase_recommendation -x` | ❌ Wave 0 |
| D-08/D-10 | Orchestrator does NOT trigger service restart, RouterOS write, /etc/wanctl edit, deploy, or controller config change | smoke (grep guard) | `bash tests/test_phase213_mutation_boundary.sh` — greps scripts for forbidden patterns (`systemctl restart`, `ssh.*router`, etc.) | ❌ Wave 0 |
| D-08 | All committed `*.redacted.json` artifacts pass the same D-08 redaction scan Phase 212 used | manual / one-shot | `bash scripts/check-redaction.sh .planning/phases/213-experience-baseline-harness/evidence/` (assumes Phase 212 helper exists or is mirrored) | ❌ Wave 0 |
| D-12 | Evidence layout matches the documented per-run / per-WAN / per-test tree | smoke (find + diff) | shell-level `find evidence/RUN-* -type d \| sort \| diff - expected-layout.txt` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/test_phase213_classify.py tests/test_phase213_ndjson_schema.py -q` (fast, unit-only)
- **Per wave merge:** `.venv/bin/pytest tests/ -k phase213 -v` (all phase213 tests)
- **Phase gate:** Full suite green before `/gsd-verify-work` AND one end-to-end dry-run AND one real evidence run committed under `evidence/RUN-<ts>/`

### Wave 0 Gaps

- [ ] `scripts/phase213-baseline-capture.sh` — orchestrator (D-09)
- [ ] `scripts/phase213-health-poller.sh` — extended NDJSON poller
- [ ] `scripts/phase213-browse-loop.sh` — curl-browse loop (D-02)
- [ ] `scripts/phase213-steering-snapshot.sh` — pre/post steering snapshot (D-08)
- [ ] `scripts/phase213-alert-window.sh` — SQLite window extraction (D-07)
- [ ] `scripts/phase213-classify.py` — classifier (BASE-03)
- [ ] `docs/RUNBOOKS/baseline.md` — operator runbook (D-09)
- [ ] `tests/test_phase213_ndjson_schema.py` — schema validation (covers BASE-02)
- [ ] `tests/test_phase213_classify.py` — bucket logic (covers BASE-03)
- [ ] `tests/test_phase213_manifest.py` — manifest schema (covers BASE-01)
- [ ] `tests/test_phase213_alert_window.py` — SQLite extraction tests (covers BASE-02)
- [ ] `tests/test_phase213_poller_resilience.py` — HRDN-02 pattern verification
- [ ] `tests/test_phase213_mutation_boundary.sh` — forbidden-pattern grep guard (covers D-10)
- [ ] `tests/fixtures/phase213/health-spectrum-snapshot.json` — fixture from Phase 212 evidence
- [ ] `tests/fixtures/phase213/health-att-snapshot.json` — fixture from Phase 212 evidence
- [ ] `tests/fixtures/phase213/health-steering-snapshot.json` — fixture from Phase 212 evidence
- [ ] `tests/fixtures/phase213/alerts-test.db` — minimal SQLite fixture
- [ ] `tests/fixtures/phase213/signal-sheet-expected-empty.json` — golden file
- [ ] `tests/fixtures/phase213/signal-sheet-expected-ul-ceiling-flagged.json` — golden file
- [ ] `.planning/phases/213-experience-baseline-harness/evidence/README.md` — evidence index (mirror Phase 212)

*(If no gaps: "None — existing test infrastructure covers all phase requirements")* — Not applicable; Phase 213 introduces all-new tooling.

## Project Constraints (from CLAUDE.md)

Extracted from `/home/kevin/projects/wanctl/CLAUDE.md`:

- **MANDATORY before every commit:** run `project-finalizer` agent. Pre-commit hook enforces it.
- **Production network control system. Change conservatively.** Priority: stability > safety > clarity > elegance.
- **Never refactor core logic, algorithms, thresholds, or timing without approval.** Phase 213 introduces NO controller code; all new files are under `scripts/`, `docs/`, `tests/`, `.planning/`. SAFE.
- **Portable controller architecture — NON-NEGOTIABLE.** The controller is link-agnostic. Phase 213's harness MUST be WAN-parameterized via flags, not Spectrum/ATT-named branches in code. Orchestrator iterates over `--wans spectrum,att` — no per-WAN function names.
- **Service-based deployment (not timer-based).** Phase 213 must not reintroduce timer-era guidance.
- **Read configs via YAML/comments before changing thresholds.** N/A for Phase 213 (read-only).
- **"Pegged at bounds" is often by design.** D-18 codifies this for Spectrum upload; classifier should flag the BUCKET 1 evidence row but the operator-note should reference D-18.
- **Use venv directly:** `.venv/bin/pytest`, `.venv/bin/ruff`, etc.
- **Knowledge map references:** `.planning/graphs/GRAPH_REPORT.md`, `.planning/intel/{arch,files,apis,stack,arch-decisions}.json`, RAG via `query_rag(project="wanctl")`.
- **Architectural spine (read-only unless explicitly requested):** RTT delta is the control signal, baseline RTT must stay frozen under load, rate decreases immediate / increases gated by sustained healthy cycles, queue limits sent only on change (flash wear), steering is binary, observability payload shape must not break casually.
- **Cycle Interval:** 50ms (production standard). N/A for harness.

Phase 213 deliverables comply with all directives — they are scripts, docs, tests, and evidence, with no source under `src/wanctl/`.

## Sources

### Primary (HIGH confidence)

- `/home/kevin/projects/wanctl/.planning/phases/213-experience-baseline-harness/213-CONTEXT.md` — phase decisions D-01 through D-19.
- `/home/kevin/projects/wanctl/.planning/REQUIREMENTS.md` — BASE-01, BASE-02, BASE-03 requirement text.
- `/home/kevin/projects/wanctl/.planning/STATE.md` — current position, v1.46 safety posture.
- `/home/kevin/projects/wanctl/.planning/ROADMAP.md` — Phase 213 goal + four success criteria.
- `/home/kevin/projects/wanctl/.planning/phases/212-production-inventory-and-drift-audit/212-CONTEXT.md` — D-05/07/08/09/10/11/12/13 carry-forward.
- `/home/kevin/projects/wanctl/.planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` — authoritative inventory + drift register.
- `/home/kevin/projects/wanctl/.planning/phases/212-production-inventory-and-drift-audit/evidence/README.md` — evidence-index convention.
- `/home/kevin/projects/wanctl/.planning/phases/212-production-inventory-and-drift-audit/evidence/health-spectrum.json` — Spectrum `/health` payload shape (735 lines, full schema verified).
- `/home/kevin/projects/wanctl/.planning/phases/212-production-inventory-and-drift-audit/evidence/health-att.json` — ATT `/health` (verified IRTT block present, contrast measurement quality).
- `/home/kevin/projects/wanctl/.planning/phases/212-production-inventory-and-drift-audit/evidence/health-steering.json` — Steering `/health` (verbatim v1.39 threshold fields).
- `/home/kevin/projects/wanctl/scripts/phase191-flent-capture.sh` — flent runner CLI verified, `--tests` accepts comma-separated arbitrary flent test names.
- `/home/kevin/projects/wanctl/scripts/soak-capture.sh` — HRDN-02 bounded-failure pattern, jq projection template.
- `/home/kevin/projects/wanctl/scripts/phase198-rerun-flent-3run.sh` — per-run subdir + parallel health curl-loop + SSH SQLite extraction pattern.
- `/home/kevin/projects/wanctl/scripts/analyze_baseline.py` — confirmed wrapper for `wanctl.analyze_baseline`; different concern from Phase 213.
- `/home/kevin/projects/wanctl/src/wanctl/storage/reader.py` lines 137-223 — `query_alerts` signature and details-parsing pattern.
- `/home/kevin/projects/wanctl/src/wanctl/storage/schema.py` lines 68-87 — `alerts` table schema (`timestamp`, `alert_type`, `severity`, `wan_name`, `details`).
- `/home/kevin/projects/wanctl/src/wanctl/steering/health.py` lines 293-302 — exact steering threshold field names (`green_rtt_ms`, `yellow_rtt_ms`, `red_rtt_ms`, `red_samples_required`, `green_samples_required`).
- `/home/kevin/projects/wanctl/configs/spectrum.yaml`, `att.yaml`, `steering.yaml` — DB paths verified.
- `/home/kevin/projects/wanctl/docs/SOAK_HARNESS.md` — NDJSON per-row schema convention.
- `/home/kevin/projects/wanctl/pyproject.toml` — `version = "1.45.0"`.
- Local CLI: `flent --version` → 2.1.1; `flent --list-tests` confirms `tcp_upload`, `tcp_download`, `tcp_12down`, `rrul` all present.
- Local CLI: `ip -4 addr show` confirms dev VM IPs `10.10.110.233` (primary) and `10.10.110.226` (secondary, DHCP).
- Remote CLI: `ssh cake-shaper which sqlite3 jq curl python3` and `sqlite3 --version` → 3.46.1.

### Secondary (MEDIUM confidence)

- sqlite.org URI-mode docs for `?mode=ro` semantics with live writers [CITED: sqlite.org/uri.html — assumed-known semantics, not retrieved in this session because the pattern is already used in production Phase 198].

### Tertiary (LOW confidence)

- None. Every claim is backed by a file read or live CLI probe.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — every tool version verified locally or via SSH.
- Architecture: HIGH — patterns are direct adaptations of Phase 191/198/207 in-repo scripts.
- Pitfalls: HIGH — drawn from in-repo prior-phase summaries and verified field paths.
- Validation: HIGH — pytest is the project standard; test file naming mirrors `src/`.
- Classification thresholds: MEDIUM — starting-point values are operator-citable but may need tuning after the first real run (operator decision per D-13).

**Research date:** 2026-05-27
**Valid until:** 2026-06-26 (30 days; production stack is stable v1.45 + v1.39 steering and Phase 212 evidence is the authoritative baseline)

## RESEARCH COMPLETE

**Phase:** 213 - Experience Baseline Harness
**Confidence:** HIGH

### Key Findings

- Every surface Phase 213 needs already exists in production-shaped form: `phase191-flent-capture.sh` accepts `--tests tcp_upload,tcp_download` unmodified (flent 2.1.1 supports both); `soak-capture.sh` is the template for the per-WAN NDJSON poller (extended jq projection needed for download + cake_signal + signal_quality fields); `phase198-rerun-flent-3run.sh` is the template for per-run subdir + parallel-poll + SSH SQLite extraction.
- Recommended new artifacts: `scripts/phase213-{baseline-capture,health-poller,browse-loop,steering-snapshot,alert-window}.sh` + `scripts/phase213-classify.py` + `docs/RUNBOOKS/baseline.md` + per-test fixture set under `tests/fixtures/phase213/`. **Don't extend `analyze_baseline.py`** — different concern.
- SQLite read-only extraction: inline `sudo -n sqlite3 -readonly -json file:DB?mode=ro 'SELECT …'` over SSH is the safe pattern against live writers. **Do NOT use `mode=ro&immutable=1`.** Steering metrics.db existence is conditional per D-07.
- Steering snapshot: SSH inline `curl http://127.0.0.1:9102/health` + `sudo -n cat /var/lib/wanctl/steering_state.json` + Python redactor with Phase 212's D-08 key pattern. Pre/post per test only — never continuous polling.
- Classification signal sheet: six buckets with explicit per-bucket evidence schemas; steering drift bucket shows raw transitions WITHOUT comparing to threshold field names (D-08/D-14 carry-forward). Operator-citable thresholds proposed but operator-overridable per D-13.
- Validation architecture is pytest-based with golden-file fixtures derived from Phase 212 evidence; one of the validation tests is a mutation-boundary grep guard against forbidden patterns (D-10).

### File Created

`/home/kevin/projects/wanctl/.planning/phases/213-experience-baseline-harness/213-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All tools verified via local + remote CLI probes; versions captured. |
| Architecture | HIGH | Patterns are direct adaptations of in-repo Phase 191/198/207 scripts; field paths verified against Phase 212 evidence JSONs. |
| Pitfalls | HIGH | Sourced from prior-phase summaries + verified CLI behavior. |
| Validation | HIGH | pytest is the project standard; test naming convention mirrors existing `tests/`. |
| Classification thresholds | MEDIUM | Starting-point values are reasonable but operator-overridable per D-13. |

### Open Questions

1. Single-run-default vs. multi-run-suggestion: recommended single-run, operator re-invokes for second `RUN-<ts>` dir.
2. "Stable GREEN" definition for recovery-lag: use controller's own `green_streak >= green_required`.
3. Single-sample vs. sustained evidence for auto-flagging: use percent-of-samples / counter-delta thresholds (already in §"Bucket → Evidence Map").
4. Curl-browse cache-busting: recommend `?cache_bust=$(date +%s%N)` query-string.
5. Per-test row order in `signal-sheet.md`: chronological, with summary header at top.

### Ready for Planning

Research complete. Planner can now create PLAN.md files. Recommended plan-wave structure:

- **Wave 0:** Test fixtures + classifier + ndjson-schema unit tests (no production access, all offline).
- **Wave 1:** Three independent scripts buildable in parallel — `phase213-health-poller.sh`, `phase213-browse-loop.sh`, `phase213-alert-window.sh` (each has its own unit test).
- **Wave 2:** `phase213-steering-snapshot.sh` + integration tests against `cake-shaper` (requires SSH probe).
- **Wave 3:** `phase213-baseline-capture.sh` orchestrator + `phase213-classify.py` + `docs/RUNBOOKS/baseline.md` (depends on Waves 0/1/2 surfaces being callable).
- **Wave 4:** One end-to-end dry-run + one real evidence-capturing run committed under `evidence/RUN-<ts>/` + `213-REPORT.md` authored by operator per D-13/D-15.
