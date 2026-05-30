# Phase 214: Measurement Collapse Investigation - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 214 resolves the pending `tcp_12down` measurement-collapse issue: bad p99 latency can occur while autorate `/health` remains `healthy`/`GREEN`. The phase must run a bounded, source-bound reproduction matrix, extract real flent latency percentiles, correlate those results with `/health` measurement quality, reflector misses, protocol divergence, logs, steering state, and controller state, then either explain the bad-p99-while-GREEN case or close it as not reproduced with enough evidence.

This phase is evidence-first. It may propose a degraded-measurement health/alert signal, but any new signal is observational by default. It must not tune thresholds, change floors/ceilings/setpoints, restart services, deploy code, toggle steering, or add control-path behavior unless the phase output explicitly recommends a separate follow-up phase.

</domain>

<decisions>
## Implementation Decisions

### Matrix Bounds
- **D-01:** Use Spectrum as the primary reproduction target. The historical bad-p99 evidence and folded todo are Spectrum `tcp_12down` cases, and Phase 213 already selected Phase 214 as a runner-up rather than the primary next phase. ATT is contrast evidence, not a full parallel investigation unless Spectrum results are ambiguous.
- **D-02:** Minimum matrix is three Spectrum `tcp_12down` windows: off-peak, daytime, and prime-time. Run one valid attempt per window. Allow one retry only for invalid artifacts or netperf/no-data failure, not to chase a preferred result.
- **D-03:** Keep the Phase 198/213 comparability defaults: `dallas` netperf host, source-bound Spectrum IP `10.10.110.226`, 30s `tcp_12down` unless the planner finds Phase 213 harness reuse requires 60s for artifact consistency. Any duration choice must be recorded in the run manifest.
- **D-04:** Optional ATT contrast is a single `tcp_12down` run using the Phase 213 ATT bind `10.10.110.233`, only if Spectrum reproduces measurement collapse or if Spectrum is inconclusive and ATT can disambiguate path-wide versus Spectrum-specific behavior.

### Evidence Correlation
- **D-05:** Each run must capture flent raw artifacts plus p50/p95/p99 ping latency and throughput, 1Hz autorate `/health` NDJSON, CAKE signal/delay/rate fields, measurement state/count/stale/outlier/confidence fields, IRTT/fusion/protocol-correlation fields, steering pre/post snapshots, and journal/log evidence for reflector misses and protocol-deprioritization messages in the same time window.
- **D-06:** A reproduced bad case requires high flent ping tail latency while autorate remains `healthy`/`GREEN`. Use the folded todo gates as defaults: p99 `>1000ms` is a fail candidate, p99 `<500ms` with no three-reflector miss burst and no protocol churn is a pass candidate. Values between those are ambiguous and need evidence-based classification, not automatic closure.
- **D-07:** Explanation must classify whether bad p99 aligns most strongly with reflector loss/collapse, ICMP/UDP protocol divergence, stale cached RTT reuse, steering behavior, CAKE queue signal mismatch, or external path conditions. If no single driver is proven, report ranked likely causes and the missing evidence.
- **D-08:** Do not close the todo from `/health.status`, `GREEN`, or Phase 213's clear bucket alone. The phase must cite flent latency percentiles and aligned measurement-quality evidence from the Phase 214 matrix.

### Flent Parser Gap
- **D-09:** Repair or add Phase 214 latency extraction before interpreting matrix results. Phase 213's signal sheet emitted `flent_p99=0.0` / `flent_median=0.0` because the classifier looked for throughput-style summary fields, so it cannot be the p99 source of truth for this phase.
- **D-10:** Parse `.flent.gz` directly using Python stdlib `gzip`/`json` and extract the ping latency series plus TCP download throughput series. The analyzer should fail closed when expected series are missing instead of producing zero percentiles.
- **D-11:** Do not back-edit Phase 213 artifacts. Phase 213 remains coarse context; Phase 214 owns its own matrix analyzer and report.

### Signal Disposition
- **D-12:** If measurement collapse reproduces while `/health` remains GREEN, the default output is an observational proposal: a health/degraded-measurement field, signal-sheet rule, or alert recommendation. It should not change rate control in this phase.
- **D-13:** Recommend control-path work only if the evidence proves an observational signal is insufficient to protect operators/users. Even then, Phase 214 should create a follow-up design recommendation rather than slipping controller behavior changes into the investigation.
- **D-14:** Preserve v1.46 safety posture: no threshold/floor/ceiling tuning, no multi-knob canary, no RouterOS writes, no steering alignment, and no production service restarts as part of this phase.

### Claude's Discretion
- User answered "you decide" for todo folding and gray-area selection. Defaults selected: fold only the mapped `tcp_12down` todo; discuss all four gray areas; keep Phase 214 narrow, evidence-only, and observational-first.

### Folded Todos
- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` - folded as the spine todo. It defines the active problem: repeated bad `tcp_12down` p99 under multi-flow download while Spectrum remains healthy/GREEN, with reflector misses and protocol-correlation churn as leading suspects. Phase 214 owns the bounded reproduction matrix and closure/explanation.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone And Phase Scope
- `.planning/ROADMAP.md` - Phase 214 goal, success criteria, dependency on Phase 213, and v1.46 phase ordering.
- `.planning/REQUIREMENTS.md` - MEAS-01, MEAS-02, MEAS-03 plus v1.46 out-of-scope constraints against casual tuning and production mutation.
- `.planning/PROJECT.md` - v1.46 Internet Quality Recovery goal and current milestone context.
- `.planning/STATE.md` - current phase, safety posture, Phase 213 completion decision, and carried deferred items.

### Prior Phase Evidence
- `.planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` - authoritative endpoint/version/config facts; especially Spectrum bound health endpoint, ATT contrast, steering drift, and health-versus-UX distinction.
- `.planning/phases/212-production-inventory-and-drift-audit/212-CONTEXT.md` - Phase 212 read-only/default-no-mutation decisions and redaction policy.
- `.planning/phases/213-experience-baseline-harness/213-CONTEXT.md` - Phase 213 evidence-only harness decisions, serialized WAN order, endpoint/bind defaults, and folded todo handoff.
- `.planning/phases/213-experience-baseline-harness/213-REPORT.md` - final baseline verdict: Phase 215 primary, Phase 216 and 214 runners-up; high outlier rates and `tcp_12down` netperf warnings preserved for Phase 214.
- `.planning/phases/213-experience-baseline-harness/213-05-SUMMARY.md` - live run metadata, artifact count, run blockers, and Phase 214 runner-up rationale.
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/manifest.json` - serialized Spectrum/ATT run order, bind map, egress map, and run timestamps.
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/signal-sheet.md` - Phase 213 bucket rows; useful for outlier context but not a valid p99 source for Phase 214.

### Folded Todo
- `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` - canonical problem statement, historical p99 data, reproduction plan, pass/fail gates, and leading suspects.

### Reusable Harness And Analyzer Surfaces
- `scripts/phase213-baseline-capture.sh` - evidence tree orchestration, bind map handling, serialized WAN suites, health polling, steering snapshots, and mutation posture.
- `scripts/phase213-classify.py` - signal-sheet classifier to reuse carefully; contains the flent p99 extraction gap Phase 214 must fix or replace.
- `scripts/phase198-rerun-flent-3run.sh` - source-bound Spectrum `tcp_12down` matrix pattern with off-peak gate, health window, SSH SQLite extraction, and flent artifact handling.
- `scripts/phase191-flent-capture.sh` - existing flent runner for `tcp_12down` and related tests.
- `scripts/soak-capture.sh` - 1Hz `/health` NDJSON polling pattern with bounded transient-failure tolerance.

### Code Surfaces To Read
- `src/wanctl/wan_controller.py` - `measure_rtt()`, zero-success blackout logging, cached RTT reuse, reflector scorer update behavior, fusion RTT handling, and controller state/rate logic.
- `src/wanctl/health_check.py` - `/health` measurement, signal quality, IRTT, reflector quality, cake signal, state, and rate payload shape.
- `src/wanctl/reflector_scorer.py` - reflector scoring/deprioritization behavior that may explain active/successful host changes.
- `src/wanctl/fusion_healer.py` - protocol-correlation and fusion-healer semantics relevant to ICMP/UDP divergence.
- `src/wanctl/storage/schema.py` and `src/wanctl/storage/reader.py` - metrics/alert table shape and read-only query patterns.
- `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` - current repo baselines for operating points and steering drift context.

### Codebase Maps
- No `.planning/codebase/*.md` maps exist in this checkout. Use the prior phase contexts and source files above as the bounded codebase map for Phase 214.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase213-baseline-capture.sh` already creates per-run evidence directories, handles bind maps, captures `/health` NDJSON, snapshots steering, and records mutation posture. Phase 214 can reuse the layout or fork a narrower `tcp_12down` matrix wrapper.
- `scripts/phase198-rerun-flent-3run.sh` already has a conservative source-bound Spectrum `tcp_12down` pattern, off-peak window logic, health sampling, SSH SQLite extraction, and pass/fail summary artifacts.
- `src/wanctl/health_check.py` already emits `measurement.state`, `measurement.successful_count`, `measurement.stale`, `signal_quality.outlier_rate`, IRTT status, reflector quality, cake signal, and state/rate fields. Phase 214 can correlate from existing `/health` without adding runtime fields first.
- `src/wanctl/wan_controller.py` logs zero-success RTT cycles as measurement collapse while reusing cached RTT for bounded controller behavior. That is a likely explanatory seam for bad p99 while state remains GREEN.

### Established Patterns
- Production investigation phases create stable `.planning/phases/<phase>/evidence/` artifacts with manifests, redacted snapshots, command provenance, and explicit mutation-boundary notes.
- Controller behavior is link-agnostic. Any Spectrum/ATT difference belongs in command parameters, config facts, and evidence interpretation, not Python branches.
- `/health.status=healthy` and `GREEN` are daemon-state only. They are not sufficient proof of acceptable user experience.
- Production mutation requires operator approval. This phase should be traffic generation plus read-only capture only.

### Integration Points
- Spectrum autorate endpoint: `http://10.10.110.223:9101/health` from Phase 212; source bind `10.10.110.226` from Phase 213/198 evidence.
- ATT autorate endpoint: `http://10.10.110.227:9101/health`; source bind `10.10.110.233` if optional contrast is used.
- Steering endpoint: `http://127.0.0.1:9102/health` on `cake-shaper`; steering runtime/version drift remains unresolved and must be carried as context, not silently normalized.
- Metrics DBs live on `cake-shaper` under `/var/lib/wanctl/`; read with read-only SQLite/SSH patterns from Phase 213.

</code_context>

<specifics>
## Specific Ideas

- Treat Phase 214 as a closure-grade investigation, not a tuning phase. The deliverable is a defensible explanation or a defensible "not reproduced" decision.
- The most important technical correction is not a controller change; it is trustworthy latency extraction from flent artifacts. A zero-filled p99 field would make the whole phase untrustworthy.
- If the matrix reproduces bad p99, the useful output is likely an operator-facing degraded-measurement signal that says "GREEN but measurement quality collapsed" rather than a rate-control change.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` - deferred. Phase 212/213 found current steering state good and no raw counter/state movement; controlled restart reproduction is outside Phase 214 unless evidence newly implicates steering.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` - deferred to Phase 218. It depends on a natural flapping event and must not be induced by this investigation.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` - deferred to the Phase 216/refractory thread or later ATT canary work.
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` - deferred to Phase 217. Phase 214 may inspect cycle-budget fields in `/health`, but one-hour profiling is separate scope.

</deferred>

---

*Phase: 214-measurement-collapse-investigation*
*Context gathered: 2026-05-27*
