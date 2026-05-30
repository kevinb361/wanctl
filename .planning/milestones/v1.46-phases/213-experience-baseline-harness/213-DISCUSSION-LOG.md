# Phase 213: Experience Baseline Harness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 213-experience-baseline-harness
**Areas discussed:** Workload mix & tooling, Co-sampling design (BASE-02), Runbook surface & mutation posture, Symptom → bucket classification (BASE-03)

---

## Workload Mix & Tooling

### Q1 — Flent tooling approach

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse phase191 script as-is | Drive `scripts/phase191-flent-capture.sh` unchanged with extended `--tests` set; thin 213 wrapper per WAN. Lowest blast radius; inherits Phase 198-validated manifest format. | (Claude's default) |
| Fork phase191 into phase213 variant | Copy to `scripts/phase213-baseline-capture.sh` and edit for 213 defaults. Cleaner per-phase isolation; two near-identical scripts to maintain. | |
| New thin orchestrator, call flent directly | Skip phase191 wrapper; new 213 script calls `flent` directly. Most flexibility but loses phase191's argument hardening. | |
| Defer flent reuse decision to planner | Lock only the test set + netperf server identity; planner picks reuse/fork/new. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: reuse phase191 with thin wrapper).
**Notes:** Rationale logged in CONTEXT.md D-01: lowest blast radius, preserves Phase 191/198 evidence comparability.

### Q2 — Browsing leg approach

| Option | Description | Selected |
|--------|-------------|----------|
| Scripted multi-site curl loop | Fixed site list, TTFB + total per request, concurrent with /health poll. Reproducible. | ✓ |
| Headless browser (playwright/chromium) | Real browser navigation timings; closer to UX truth but heavier dependency. | |
| Operator-timed manual browse session | Subjective notes alongside continuous /health capture; no new tooling but not numerically reproducible. | |
| Skip browsing leg; cite irtt+RRUL as proxy | Argue flent+irtt already captures responsiveness. Conflicts with roadmap which names browsing. | |

**User's choice:** Scripted multi-site curl loop.
**Notes:** Locked as D-02. Curl loop records TTFB + total per request, runs concurrent with the same NDJSON /health poll wrapping flent tests.

### Q3 — Test origin

| Option | Description | Selected |
|--------|-------------|----------|
| Dev VM (same source as phase191) | `--local-bind` matching prior phase191 dev VM IP. Continuity; traverses LAN → steering → WAN path real users hit. | ✓ |
| cake-shaper itself | Eliminates LAN-segment variability; flows skip part of real LAN path. | |
| Dedicated LAN client (behemoth/pantera) | Most UX-faithful; adds host dependency. | |
| Claude's discretion | Planner picks based on tooling availability. | |

**User's choice:** Dev VM (same source as phase191).
**Notes:** Locked as D-03. Planner confirms current dev VM IP before run; preserves Phase 191/198 evidence comparability.

### Q4 — Netperf and curl-browse target endpoints

| Option | Description | Selected |
|--------|-------------|----------|
| Lock dallas + curl-browse list to planner | Flent server = dallas (phase191/198 parity); curl-browse site list at planner discretion. | ✓ |
| Dallas + explicit curl-browse list now | Lock both flent server and site list in CONTEXT.md. Most reproducible but list may rot. | |
| Multiple netperf servers (geographic spread) | 2–3 servers; separates ISP-local from path-distant signal. Multiplies test time. | |
| Claude's discretion | Defer endpoint choices; record constraint that targets should match phase191/198. | |

**User's choice:** Lock dallas + curl-browse list to planner.
**Notes:** Locked as D-04.

---

## Co-Sampling Design (BASE-02)

### Q5 — Sampling shape

| Option | Description | Selected |
|--------|-------------|----------|
| Continuous 1Hz NDJSON during each test (reuse soak-capture pattern) | Concurrent per-WAN NDJSON polls of both autorate + steering /health while test runs. Heaviest artifact, richest signal. | |
| Pre/during/post snapshot triplet | Three snapshots per test; smaller artifacts but loses sub-test dynamics. | |
| Continuous for autorate, snapshots for steering | 1Hz NDJSON for Spectrum + ATT; pre/post snapshots for steering. | |
| Claude's discretion | Planner picks per surface based on test duration. | (Claude's default) |

**User's choice:** "you decide" → recorded as Claude's discretion (default: continuous 1Hz NDJSON for both autorate endpoints, pre/post snapshots for steering + SQLite alerts).
**Notes:** Locked as D-05. `/health` already exposes `cake_signal` and measurement quality — no separate capture path needed.

### Q6 — Window alignment

| Option | Description | Selected |
|--------|-------------|----------|
| Unix-timestamp manifest + simple wallclock alignment | ISO timestamps everywhere; operator matches by timestamp. | |
| Per-test directory with strict bracketing | Each test gets its own subdir; orchestrator writes `test_start`/`test_end`, NDJSON poll explicitly brackets test with overlap. | (Claude's default) |
| Bracketing + pre-test /health warmup snapshot | Adds 30s pre-test baseline snapshot to distinguish "started bad" from "load made it bad". | |
| Claude's discretion | Planner picks based on script complexity. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: per-test subdir with bracketed NDJSON poll, planner-chosen pre/post buffer).
**Notes:** Locked as D-06.

### Q7 — SQLite alert capture scope

| Option | Description | Selected |
|--------|-------------|----------|
| Pre/post counts grouped by alert_type | Compact summary table. | |
| Full alert rows during window + summary count | Heavier but gives downstream phases raw data. | (Claude's default) |
| Counts grouped by type AND severity | Helps separate noise from action-worthy in classification. | |
| Claude's discretion | Default to dump rows + summary counts. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: dump rows + summary counts from both per-WAN metrics DBs).
**Notes:** Locked as D-07. Alerts table is small enough that artifact size isn't a real concern.

---

## Runbook Surface & Mutation Posture

### Q8 — Runbook delivery shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single orchestrator script + thin doc | One command runs entire baseline; doc shows command + how to read artifacts. | (Claude's default) |
| Runbook doc with per-step manual commands | No new orchestrator; doc lists each command operator pastes. | |
| Orchestrator + step-by-step doc (both) | Best operator UX, highest doc/maintenance cost. | |
| Claude's discretion | Default: orchestrator + thin doc. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: single orchestrator script + thin runbook doc).
**Notes:** Locked as D-09.

### Q9 — Mutation posture

| Option | Description | Selected |
|--------|-------------|----------|
| Traffic-only; everything else read-only | Allowed: flent + curl traffic + read-only health/SQLite/state. Forbidden: restart, YAML edit, steering toggle, RouterOS writes, deploys. No time-of-day guardrail. | |
| Traffic-only + time-of-day guardrail | Adds explicit allowed-window rule to reduce family WiFi disruption. | |
| Traffic-only + per-WAN sequencing | Adds rule: never load both WANs concurrently. Prevents steering misinterpretation. | (Claude's default) |
| Claude's discretion | Default: option 3 (traffic-only + per-WAN sequencing). | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: traffic-only + per-WAN sequencing, Spectrum first then ATT).
**Notes:** Locked as D-10 and D-11.

### Q10 — Artifact layout

| Option | Description | Selected |
|--------|-------------|----------|
| Inherit 212 pattern exactly | All artifacts under `evidence/`, `evidence/README.md` as index, D-08 redaction. | |
| Inherit + per-run timestamp dir | Same as option 1, plus `evidence/RUN-<ts>/<wan>/<test>/`. Supports multiple baseline runs. | (Claude's default) |
| Split: raw under evidence/, plots/manifests under reports/ | More structure; mirrors phase191 plot output convention. | |
| Claude's discretion | Default: per-run timestamp dirs under evidence/. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: per-run timestamp dirs under evidence/, inheriting 212's evidence/README.md index and D-08 redaction).
**Notes:** Locked as D-12.

---

## Symptom → Bucket Classification (BASE-03)

### Q11 — Classification mode

| Option | Description | Selected |
|--------|-------------|----------|
| Manual judgment from a decision table | Operator fills in verdict against a documented table. No automation. | |
| Scripted classifier emitting bucket verdicts | Script reads artifacts and emits bucket → verdict + evidence JSON. Reproducible. | |
| Hybrid: script summarizes signals, operator picks bucket | Script emits per-bucket signal sheet; operator assigns verdict citing rows. | (Claude's default) |
| Claude's discretion | Default: hybrid. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: hybrid — script emits per-bucket signal sheet, operator assigns bucket verdict(s) in report).
**Notes:** Locked as D-13. Matches Phase 212's operator-first table convention.

### Q12 — Steering drift bucket handling

| Option | Description | Selected |
|--------|-------------|----------|
| Capture steering state as evidence; do not interpret threshold fields | Raw transitions/counters only; no comparison to v1.39-shaped threshold names. | (Claude's default) |
| Suppress steering bucket entirely until Phase 216 resolves drift | Effectively 5-bucket classification in Phase 213. | |
| Capture + provisional interpretation with explicit caveat | Use v1.39 field names but stamp all findings PROVISIONAL. | |
| Claude's discretion | Default: option 1. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: capture steering state as evidence; do not interpret threshold field names while v1.39 drift unresolved).
**Notes:** Locked as D-14. Preserves auditability without making Phase 213 dependent on Phase 216.

### Q13 — Next-phase recommendation framing (success criterion 4)

| Option | Description | Selected |
|--------|-------------|----------|
| Single ranked recommendation with rationale | One named next phase + runners-up + evidence rationale. Matches Phase 212 closeout style. | (Claude's default) |
| Ranked list of candidate phases with evidence weights | Operator picks from ranked list with weights. | |
| Conditional gate: 'only proceed if X' per candidate phase | Per-phase evidence threshold; most rigorous, heavy authoring cost. | |
| Claude's discretion | Default: single ranked recommendation. | |

**User's choice:** "you decide" → recorded as Claude's discretion (default: single ranked next-phase recommendation with rationale and runners-up).
**Notes:** Locked as D-15.

---

## Claude's Discretion

User selected "you decide" / Claude's discretion on every gray-area question. Defaults recorded as D-01 through D-15 in CONTEXT.md. Planner retains residual discretion on: exact orchestrator script name and layout, exact curl-browse site list, pre/post NDJSON buffer width, per-test duration (subject to flent defaults), and exact signal-sheet thresholds, provided D-01 through D-19 hold.

## Folded Todos

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` — folded as capture-only. Phase 213 produces baseline `tcp_12down` sample for Phase 214; Phase 213 does not investigate.

## Reviewed Todos (not folded)

- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — requires controlled service restart (outside D-10 mutation boundary). Defer to later steering-focused phase (likely Phase 216).
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan.md` — Phase 217 owns one-hour cycle-budget profiling.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` — Phase 218 watch-list item depending on natural production flapping event.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — depends on Phase 196 refractory/cake-primary follow-up.

## Deferred Ideas

- Time-of-day matrix capture — Phase 214 owns this for `tcp_12down`. Phase 213 captures single representative window per WAN; operator may rerun with timestamped dirs if desired.
- Headless-browser browsing test — rejected in favor of scripted curl loop (reproducibility over UX fidelity).
- Multiple netperf servers (geographic spread) — locked to `dallas` for continuity; deferable to later phase if baseline ambiguous.
- Active steering toggle to force bucket evidence — outside D-10 mutation boundary; defer to Phase 216.
