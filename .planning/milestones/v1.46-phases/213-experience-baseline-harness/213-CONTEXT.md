# Phase 213: Experience Baseline Harness - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 213 builds a repeatable, controlled evidence pipeline that turns "internet quality is not good enough" into operator-citable artifacts. It captures matching `/health`, CAKE state, SQLite alert counts, current rates, measurement quality, and steering state for each test window across normal browsing, isolated upload, isolated download, RRUL, and `tcp_12down`. It classifies observed symptoms into one of six v1.46 cause buckets (upload ceiling/setpoint, download recovery lag, measurement collapse, steering drift, refractory semantics, external ISP) and recommends which downstream phase (214 / 215 / 216) should run next.

Phase 213 is the first v1.46 phase that actively loads the production WAN with traffic. It is not read-only — but it is *evidence-only*: no service restart, no `/etc/wanctl/*.yaml` edit, no steering toggle, no RouterOS write, no deploy. It does not investigate `tcp_12down` (Phase 214), tune Spectrum upload (Phase 215), or resolve refractory semantics (Phase 216).

</domain>

<decisions>
## Implementation Decisions

### Workload Mix And Tooling
- **D-01:** Flent legs (RRUL, `tcp_12down`, isolated `tcp_upload`, isolated `tcp_download`) reuse `scripts/phase191-flent-capture.sh` via a thin 213 orchestrator wrapper. Rationale: lowest blast radius, preserves Phase 191/198 evidence comparability. Planner has discretion to fork only if co-sampling integration forces it.
- **D-02:** "Normal browsing" is captured as a scripted multi-site curl loop that records TTFB and total time per request, run concurrently with the same NDJSON `/health` poll that wraps the flent tests. Not a headless browser, not a human-timed manual session.
- **D-03:** All test flows originate from the dev VM with `--local-bind` matching the source IP Phase 191/198 used (`10.10.110.233` or current dev VM IP — planner confirms before run). Flows traverse the same LAN → steering → WAN path real users hit.
- **D-04:** Flent netperf server is locked to `dallas` (same as Phase 191/198) for geographic baseline continuity. The curl-browse site list (representative high-traffic hosts: Google, Cloudflare, GitHub, video CDN, news) is at gsd-planner discretion; pick sites known to be reachable and stable, document the list in the orchestrator script.

### Co-Sampling Design (BASE-02)
- **D-05:** Default sampling: continuous 1Hz NDJSON polls of both autorate `/health` endpoints (Spectrum `http://10.10.110.223:9101/health`, ATT `http://10.10.110.227:9101/health`) during each test. Pre/post snapshots only for steering `/health` (`http://127.0.0.1:9102/health` on `cake-shaper`) and SQLite alert queries. Rationale: `/health` already exposes `cake_signal`, measurement quality (`outlier_rate`, `confidence`, `successful_count`), and current rates — no separate CAKE/quality capture is needed.
- **D-06:** Window alignment uses per-test bracketing: orchestrator starts NDJSON poll, records `test_start_unix`, runs the test, records `test_end_unix`, stops poll. NDJSON poll brackets the test with a planner-chosen pre/post buffer (e.g., 10s on each side). All artifacts share ISO timestamps for cross-surface alignment.
- **D-07:** SQLite alert capture: dump alert rows (timestamp, type, severity, wan_name, details) for the test window AS WELL AS a summary count grouped by `alert_type` and `severity`, from `/var/lib/wanctl/metrics-spectrum.db` and `/var/lib/wanctl/metrics-att.db`. Steering alerts come from `/var/lib/wanctl/metrics.db` if present.
- **D-08:** Steering `/health` and persisted state at `/var/lib/wanctl/steering_state.json` are captured as raw evidence per test. Threshold field names are recorded verbatim but NOT interpreted in classification while runtime `1.39.0` drift remains unresolved (Phase 212 drift register carry-forward).

### Runbook Surface And Mutation Posture
- **D-09:** Phase 213 ships a single orchestrator script (e.g., `scripts/phase213-baseline-capture.sh`) that handles: starting per-WAN NDJSON polls, calling the phase191 flent suite, running the curl-browse loop, taking pre/post steering and SQLite snapshots, writing the per-run manifest, and emitting the classification signal sheet. Operator invokes one command. A thin `docs/RUNBOOKS/baseline.md` documents the command + how to read artifacts.
- **D-10:** Mutation posture: traffic generation from the dev VM is allowed. Forbidden in Phase 213: service restart, `/etc/wanctl/*.yaml` edit, steering toggle, RouterOS write, deploy, profiling harness changes, controller config changes.
- **D-11:** Per-WAN sequencing: never load Spectrum and ATT concurrently. Orchestrator runs the full flent + curl-browse suite against Spectrum to completion, then against ATT. Rationale: prevents steering from misinterpreting concurrent dual-link load as a steering-decision trigger and isolates per-WAN measurement evidence.
- **D-12:** Artifact layout inherits Phase 212's `evidence/` pattern with a per-run timestamp dir: `.planning/phases/213-experience-baseline-harness/evidence/RUN-<utc-ts>/<wan>/<test>/`. Each `evidence/README.md` (or per-run README) indexes the commands, sources, redaction posture, and mutation boundary, matching Phase 212 conventions. Phase 212's D-08/D-09/D-10 secret-redaction policy applies unchanged — no router passwords, tokens, private keys, or D-08-matching keys in committed artifacts.

### Symptom → Bucket Classification (BASE-03)
- **D-13:** Classification is hybrid. A script (`scripts/phase213-classify.py` or equivalent) reads the per-test artifacts and emits a per-bucket *signal sheet* listing the quantitative evidence for each of the six buckets (e.g., "upload ceiling/setpoint: Spectrum UL pegged at `18` Mbps for X% of the upload test"; "download recovery lag: post-RRUL DL took N seconds to return to baseline"). The operator reads the signal sheet and assigns the final bucket verdict(s) in the report, citing the rows that justify the call.
- **D-14:** Six buckets: upload ceiling/setpoint, download recovery lag, measurement collapse, steering drift, refractory semantics, external ISP. The "steering drift" bucket sheet shows raw steering state transitions and counters during tests but does NOT compare them to threshold field names while v1.39 semantics remain unresolved (D-08 carry-forward + Phase 212 drift register).
- **D-15:** Phase 213 success criterion 4 is satisfied by a single ranked next-phase recommendation (one of 214 / 215 / 216) in the final report, with evidence-cited rationale and explicit runners-up. Matches Phase 212's operator-first closeout style. Does not punt back to operator triage.

### Carry-Forward From Phase 212
- **D-16:** Bound autorate endpoints from Phase 212 are authoritative: Spectrum `http://10.10.110.223:9101/health`, ATT `http://10.10.110.227:9101/health`. Steering endpoint `http://127.0.0.1:9102/health` is reached from `cake-shaper`; remote capture must SSH to `cake-shaper` for the steering snapshot.
- **D-17:** `/health.status=healthy` and `GREEN` are daemon-state only. Phase 213's UX evidence comes from the active test artifacts (flent summaries, curl TTFB/total, observable rate behavior), never from `/health` alone. (Phase 212 D-05 carry-forward.)
- **D-18:** Spectrum upload operating points (`floor=8`, `ceiling=18`, `setpoint=12`, DOCSIS mode active) are intentional configuration, not drift. Phase 213 records observed UL behavior at those points and may flag the "upload ceiling/setpoint" bucket, but MUST NOT tune them.
- **D-19:** Phase 212 evidence (`212-REPORT.md`, `212-production-inventory.md`, `evidence/*`) is the inventory baseline. Phase 213 cites it for service identity, version state, endpoint provenance, and steering drift constraints rather than re-probing.

### Claude's Discretion
- User answered "you decide" or "Claude's discretion" on every gray-area question in this discussion. The defaults above are the recorded discretionary calls. Planner retains discretion on: exact orchestrator script name and layout, exact curl-browse site list, pre/post NDJSON buffer width, per-test duration (subject to flent defaults), and exact signal-sheet thresholds, provided the D-01 through D-19 decisions hold.

### Folded Todos
- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — folded as *capture-only*. Phase 213 captures a baseline `tcp_12down` sample (flent + co-sampling) so Phase 214 has data to start from. Phase 213 does NOT investigate the cause; Phase 214 owns the bounded matrix and the bad-p99-while-GREEN explanation. The todo remains open and is reassigned to Phase 214 ownership.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone And Phase Scope
- `.planning/ROADMAP.md` §"Phase 213: Experience Baseline Harness" — phase goal and success criteria.
- `.planning/REQUIREMENTS.md` §"Experience Baseline (BASE)" — BASE-01, BASE-02, BASE-03 requirements.
- `.planning/PROJECT.md` §"Current Milestone: v1.46 Internet Quality Recovery" — milestone goal and operating context.
- `.planning/STATE.md` §"Current Position" and §"v1.46 safety posture" — current phase, safety boundaries, and deferred VERIFY context.

### Prior Phase Context (authoritative inventory)
- `.planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` — final inventory and drift register; cite for service identity, version state, bound endpoints, steering drift constraint, and Spectrum upload operating points.
- `.planning/phases/212-production-inventory-and-drift-audit/212-CONTEXT.md` — Phase 212 implementation decisions (D-01 through D-13) that carry forward (especially D-05, D-07, D-08, D-09, D-10, D-11, D-12, D-13).
- `.planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` — per-surface inventory tables and verdicts.
- `.planning/phases/212-production-inventory-and-drift-audit/evidence/README.md` — Phase 212 evidence-index pattern that Phase 213's evidence dir must mirror.
- `.planning/phases/212-production-inventory-and-drift-audit/evidence/health-spectrum.json` — Spectrum `/health` shape (rates, CAKE signal, measurement quality, daemon summary).
- `.planning/phases/212-production-inventory-and-drift-audit/evidence/health-att.json` — ATT `/health` shape and clean measurement-quality contrast.
- `.planning/phases/212-production-inventory-and-drift-audit/evidence/health-steering.json` — steering `/health` shape, including v1.39-shaped threshold fields that Phase 213 must NOT interpret.

### Reusable Test Harness Surfaces
- `scripts/phase191-flent-capture.sh` — flent runner for `rrul`, `tcp_12down`, `voip` (extend test set to add `tcp_upload`, `tcp_download` for Phase 213); supports `--label`, `--wan`, `--local-bind`, `--ref`, `--host`, `--duration`, `--tests`, `--output-dir`.
- `scripts/soak-capture.sh` — 1Hz `/health` NDJSON poller with HRDN-02 bounded failure tolerance; reference pattern for the Phase 213 per-test NDJSON poll.
- `scripts/phase198-rerun-flent-3run.sh` — multi-run flent pattern (per-run subdirs, label discipline) Phase 213's per-run timestamp layout should mirror.
- `scripts/analyze_baseline.py` — existing baseline analysis surface; planner should check whether it can be extended for Phase 213 signal-sheet emission or if a new `phase213-classify.py` is cleaner.

### Folded Todo
- `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — folded as capture-only; Phase 213 produces the baseline `tcp_12down` sample, Phase 214 investigates.

### Code Surfaces To Read
- `src/wanctl/health_check.py` — autorate `/health` payload shape, including `cake_signal`, `autorate_cake_stats`, and measurement quality fields Phase 213 polls.
- `src/wanctl/steering/health.py` — steering `/health` payload shape and threshold field names (record verbatim; do not interpret per D-08/D-14).
- `src/wanctl/storage/schema.py` — `alerts` table schema (`timestamp`, `alert_type`, `severity`, `wan_name`, `details`); used for SQLite alert dump + summary count queries.
- `src/wanctl/storage/reader.py` — `query_alerts` reader pattern Phase 213 may reuse for in-window alert extraction.
- `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` — repo baselines for operating-point references and per-WAN DB paths (`metrics-spectrum.db`, `metrics-att.db`, `metrics.db`).

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — autorate/steering daemon architecture, state files, observability surfaces.
- `.planning/codebase/INTEGRATIONS.md` — RouterOS integration, SQLite metrics, JSON state files, health endpoints, secrets locations.
- `.planning/codebase/STACK.md` — runtime, config files, systemd deployment model, env vars, entry points.
- `.planning/codebase/TESTING.md` — existing test harness conventions Phase 213 should not duplicate.

### Documentation
- `docs/PERFORMANCE.md` — performance baseline context relevant to interpreting outlier rates and measurement quality.
- `docs/SOAK_HARNESS.md` — referenced by `scripts/soak-capture.sh`; per-row NDJSON schema Phase 213's polls should follow or extend.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase191-flent-capture.sh` already handles `rrul`, `tcp_12down`, `voip` with `--label`, `--wan`, `--local-bind`, `--ref`, per-run manifest output, and a `dallas` netperf default. Extending its `--tests` set or wrapping it for Phase 213 is cheaper than greenfielding.
- `scripts/soak-capture.sh` already does 1Hz NDJSON polling of one `/health` endpoint with HRDN-02 bounded failure tolerance (`SOAK_FAIL_RATE_THRESHOLD`, `MIN_SAMPLES_BEFORE_EVAL`). Phase 213's per-test poll either reuses it (parameterized for endpoint + duration) or follows the same pattern with concurrent per-WAN pollers.
- `/health` already exposes `cake_signal` (download/upload snapshots, detection, burst), `autorate_cake_stats`, and measurement quality (`outlier_rate`, `confidence`, `successful_count`). BASE-02 surfaces are mostly in `/health` already — no separate CAKE or measurement-quality capture path is needed.
- `src/wanctl/storage/reader.py` provides `query_alerts` for in-window alert extraction; Phase 213 can call it directly rather than hand-rolling SQL.
- Phase 198's per-run subdir layout is a working template for Phase 213's per-run timestamp dirs.

### Established Patterns
- Production is service-based systemd, not timer-based. Phase 213 must not introduce timer-era assumptions.
- Per-WAN metrics DBs at `/var/lib/wanctl/metrics-<wan>.db`; steering uses `/var/lib/wanctl/metrics.db`. Phase 213 reads these read-only.
- Phase 212 evidence pattern: redacted artifacts under `evidence/`, `evidence/README.md` as the command/source/redaction/mutation-posture index, operator-first per-surface tables, final report cites stable artifact paths.
- Controller behavior is link-agnostic; per-WAN differences must remain config facts, not code branches. Phase 213's harness must be WAN-parameterized via flags, not Spectrum/ATT-named branches.

### Integration Points
- Spectrum autorate at `http://10.10.110.223:9101/health` — bound endpoint, not loopback.
- ATT autorate at `http://10.10.110.227:9101/health` — bound endpoint, not loopback.
- Steering at `http://127.0.0.1:9102/health` on `cake-shaper` — Phase 213 must SSH to `cake-shaper` for steering snapshots.
- SQLite metrics DBs are on `cake-shaper` under `/var/lib/wanctl/`; Phase 213 reads remotely via SSH read-only commands.
- Phase 191/198 used `--local-bind 10.10.110.233` as the dev VM source IP. Phase 213 confirms current dev VM IP before run.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 213 as the "did the inventory match user experience?" gate for v1.46. Phase 212 said the system is healthy by daemon-state; Phase 213 says whether the *experience* matches that claim and which bucket explains any mismatch.
- The baseline must be useful even if all six buckets come back clean — a clean baseline is itself an outcome (suggests ISP-side or out-of-scope cause) and informs whether v1.46 should pivot scope.
- The browsing leg's value is mostly in catching cases where flent says "looks fine" but real workloads still feel bad. Keep the curl loop simple (fixed site list, TTFB + total time) so the signal it provides is interpretable, not noisy.
- Phase 191/198 evidence comparability matters: same netperf server, same source IP family, same flent args where possible, so v1.46 baseline can be compared against v1.38-era and v1.43-era runs already in the repo.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — Phase 212 already captured current state as `SPECTRUM_GOOD` (D-03 carry-forward). Reproducing the historical degraded-on-clean-restart behavior requires a controlled service restart, which is outside Phase 213's mutation boundary (D-10). Defer to a later steering-focused phase (likely Phase 216 territory or a dedicated steering investigation).
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` — Phase 217 owns one-hour cycle-budget profiling. Phase 213's NDJSON polls touch `/health` only and do not run the profiling harness.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` — Phase 218 watch-list item depending on a natural production flapping event. Phase 213's baseline traffic load is not expected to generate one and must not stage one.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — depends on Phase 196 refractory/cake-primary follow-up; not part of evidence baseline.

### Out-Of-Scope Suggestions Considered
- Time-of-day matrix capture — Phase 214's `tcp_12down` investigation explicitly owns this. Phase 213 captures a single representative window per WAN at one run time; if multiple runs happen (timestamped per-run dirs make that cheap), they are operator-initiated, not required by Phase 213.
- Headless-browser browsing test — rejected in favor of scripted curl loop (D-02). Reproducibility wins over UX fidelity for the baseline run.
- Multiple netperf servers (geographic spread) — Phase 213 locks `dallas` for continuity (D-04). A geographic matrix is a candidate later phase if baseline evidence is ambiguous about ISP-local vs path-distant signal.
- Active steering toggle to force bucket evidence — outside D-10 mutation boundary; defer to Phase 216.

</deferred>

---

*Phase: 213-experience-baseline-harness*
*Context gathered: 2026-05-27*
