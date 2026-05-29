# Phase 216: Recovery/Refractory Decision - Research

**Researched:** 2026-05-29
**Domain:** Evidence reconciliation / decision-only close-out (NOT control-path code)
**Confidence:** HIGH

## Summary

Phase 216 is a **decision-only** phase. It produces no code change — only an evidence-cited
verdict (no-change / config-tune / new code-design), a `216-REPORT.md`, a thread status flip
on the Phase 196 thread, and (if needed) a seeded follow-up phase. The research question is not
"how do I write controller code" but "is the evidence sufficient to close the Phase 196
queue-primary refractory-semantics thread, and on what framing."

All three CONTEXT exit criteria were investigated directly against source and against the raw
Phase 213 evidence (`RUN-20260527T222043Z`). **All three are met, and all line references in
CONTEXT/REVIEWS are accurate.** The headline finding for D-02 is decisive: the
`backlog_suppressed_delta=14451` that flagged `refractory_semantics` as a runner-up is a
**cross-WAN merge artifact of a cumulative lifetime counter**, not a per-event distress signal.
The refractory code path was never entered in the baseline (`arb_refractory_active=0` and
`dl_refractory_remaining` max `0` in every captured file), and every recovery-input window was
`GREEN` for 100% of samples — so the `time_to_green_after_red_sec=0.0` rows mean "no RED was
ever observed," exactly the WR-02 zero-conflation. The Phase 197 replay tests pass (21/21) and
assert exactly the refractory-active arbitration branches the verdict relies on.

**Primary recommendation:** The evidence supports a **no-change / resolved-by-197** verdict,
framed honestly: *Phase 197's shipped code + replay tests resolve the original Phase 196
throughput regression; Phase 213 shows no live symptom under baseline load; the 213 backlog
flag is a counter artifact and carries no weight.* Do NOT write "Phase 213 validated refractory
semantics." Record explicit reopen triggers because the close rests on absence-of-symptom, not
an exercised refractory window.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use the existing Phase 213 passive baseline (`RUN-20260527T222043Z`) to decide
  **no new production capture is justified** — NOT to claim it validates refractory-active
  semantics. No new active capture, no refractory provocation. Phase 213 had
  `pct_samples_refractory_active=0.0`: the refractory path was never exercised. 213 shows "no
  current symptom under this load," NOT "refractory behavior is correct." The
  `time_to_green_after_red_sec=0.0` rows are suspect (most likely "no RED observed"); per
  `213-REVIEW.md` §WR-02 a window that enters RED and never recovers also logs `0`. Do not read
  zeros as positive recovery evidence.
- **D-01a (RECOV-03 scope):** RECOV-03's "measured from production artifacts" bar is satisfied
  **only for a no-change decision** (no recovery/refractory tuning is being made, so no
  transient-congestion measurement is required). It is **NOT** satisfied as evidence supporting
  any *future* tuning — that needs a production artifact containing an actual transient/refractory
  event (`arb_refractory_active > 0`), which the 213 run does not contain.
- **D-02:** Before the `backlog_suppressed_delta` flag influences the verdict, PROVE (not assume)
  whether it is a real per-event distress counter or a per-cycle/per-window accumulation artifact.
  Show the counter provenance explicitly: classifier merges all `health-*.ndjson` per window
  (`scripts/phase213-classify.py:98`), computes delta as `max-min` over cumulative lifetime
  counters (`:271`/`:278`); underlying counter increments on backlog-suppressing GREEN recovery,
  not refractory (`src/wanctl/queue_controller.py:265`/`:274`). State whether any target-WAN-only
  per-file delta remains meaningful.
- **D-03:** Treat Phase 197 as the de-facto resolution of the Phase 196 conflict. The semantic
  proof is Phase 197's own code + replay tests (`tests/test_phase_197_replay.py`, asserting the
  `queue_during_refractory` / `rtt_fallback_during_refractory` branches), NOT the 213 baseline.
  213's role is narrow: confirm no current live symptom. The original `dl_cake_for_detection` /
  `dl_cake_for_arbitration` split design is NOT pursued on its own merits unless the 197 code/
  tests are shown insufficient.
- **D-04:** Produce `216-REPORT.md` with the evidence-cited verdict, then flip the thread status
  to `closed` and mark RECOV-01/02/03. If verdict is "config tune" or "code design," seed a
  follow-up phase in ROADMAP.md (do not implement here). Report mirrors the operator-first
  closeout of 212/213/214/215.
- **D-04a (reopen criteria):** The closeout MUST record explicit reopen triggers (close is
  based on absence-of-symptom, not an exercised refractory window). Reopen if a natural
  production artifact later shows `arb_refractory_active > 0` accompanied by any of: RTT fallback
  during what should be queue-primary load, measurable recovery lag after RED/SOFT_RED, or
  throughput collapse during the refractory window.
- **D-05:** RECOV-02 / Phase 160 cascade safety is preserved by construction (216 changes no
  code), but any follow-up it seeds MUST keep refractory free of cascading CAKE drop/backlog
  reductions AND keep a valid queue-delay scalar available for queue-primary classification
  where needed.
- **D-06:** Do NOT interpret v1.39-shaped steering threshold field names as v1.45 semantics. The
  refractory decision relies on autorate `/health` + CAKE signal evidence, not steering
  threshold-name comparison.

### Claude's Discretion
- Exact report structure; whether the D-02 artifact check is a standalone analysis step or
  folded into the evidence review; precise thread-close wording; how a seeded follow-up phase
  (if any) is scoped — provided D-01 through D-06 hold.

### Deferred Ideas (OUT OF SCOPE)
- ATT cake-primary canary (`2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`) —
  active validation requiring an ATT cake-primary mode switch + flent load; conflicts with D-01
  passive-only posture and is gated on Phase 191. Defer to a dedicated cake-primary phase.
- Post-hotpath cycle-budget profiling (`2026-04-15-profile-...`) — Phase 217 owns it.
- Active refractory provocation / controlled congestion event — considered (D-01) and rejected
  in favor of the existing passive baseline; only a future-phase candidate if 216 evidence is
  ambiguous.
- Pursuing the thread's original `dl_cake_for_detection` / `dl_cake_for_arbitration` split design
  on its own merits — superseded by Phase 197; revisited only if 197 is shown insufficient.

**Hard boundary:** Do NOT propose threshold/bounds/timing changes inside 216. Any tune or code
change belongs in a SEPARATE gated follow-up phase (success criterion 4).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECOV-01 | Close the Phase 196 thread with a concrete decision (no change / config tune / code design). | All three exit criteria met (see Exit-Criteria Findings). Thread file is at `.planning/threads/phase-196-...md`, currently `status: in_progress`; closing = flip front-matter `status: closed`, append a verdict/reopen-criteria section. |
| RECOV-02 | If code design is approved, it preserves Phase 160 cascade safety while keeping valid queue-delay signal available for queue-primary classification. | Preserved by construction in 216 (no code). Phase 160 invariant is mechanically enforced and test-guarded today (`test_phase_197_replay.py::TestPhase197NoCascadeOnDetection`, `wan_controller.py:2937-2939`). Any seeded follow-up must keep `dl_cake_for_detection=None` during refractory while leaving `dl_cake_for_arbitration` live. |
| RECOV-03 | Recovery lag after transient congestion is measured from production artifacts before changing `green_required`, `step_up`, backlog suppression, or refractory behavior. | Satisfied **only in the narrow no-change sense** (no tuning is being made). The 213 artifacts contain ZERO transient/refractory events — every recovery-input window is 100% GREEN — so they cannot support future tuning. Any future tune phase must capture an `arb_refractory_active > 0` event first (D-01a). |
</phase_requirements>

## Architectural Responsibility Map

216 produces no runtime artifact, so this maps the *evidence* surfaces rather than control tiers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Refractory arm/decrement + arbitration regime | `wan_controller.py` | `queue_controller.py` (sets `dwell_bypassed_this_cycle`) | `wan_controller` owns `_dl_refractory_remaining`, masks detection, routes arbitration. |
| Backlog-suppression counter (the 213 flag source) | `queue_controller.py` | `health_check.py` / `wan_controller.py` payload | Counter is a per-direction monotonic lifetime field on the QueueController, surfaced via `/health`. |
| Evidence classification (the runner-up flag) | `scripts/phase213-classify.py` | — | The classifier merges per-WAN health files and deltizes cumulative counters; the merge is where the artifact is born. |
| Verdict + thread close + report | `.planning/` artifacts | ROADMAP (follow-up seed) | Pure planning-layer; no `src/` or `/etc/wanctl/` or RouterOS writes. |

## Exit-Criteria Findings (the core of this phase)

### D-02 — Backlog-counter artifact check: PROVEN ARTIFACT (HIGH confidence)

**Verdict: the `backlog_suppressed_delta` flag is a cross-WAN merge artifact of a cumulative
lifetime counter. It carries ZERO weight toward the refractory verdict.**

Counter provenance, verified by reading source (all line refs current and accurate):

1. **The counter is a monotonic lifetime counter, not per-event.**
   `src/wanctl/queue_controller.py:116` initializes `self._backlog_suppressed_count = 0`;
   `:274` does `self._backlog_suppressed_count += 1` inside the **GREEN branch** under the
   `DETECT-02: Suppress green_streak while backlog is high` comment (`:265`). A second identical
   increment site exists at `:639`. It is emitted via `get_health_data()` at `:733` as
   `backlog_suppressed_count`, surfaced through `wan_controller.py:4587-4592` as
   `dl_backlog_suppressed_count` / `ul_backlog_suppressed_count`, and projected into the 213
   ndjson by `scripts/phase213-health-poller.sh:188-189` as `cake_dl_backlog_suppressed_count` /
   `cake_ul_backlog_suppressed_count`. `[VERIFIED: source read]`
   It increments on **backlog-suppressing GREEN recovery**, NOT on refractory entry. (Refractory
   is armed separately at `wan_controller.py:3053-3054` from `dwell_bypassed_this_cycle`.)

2. **The classifier merges all per-WAN health files per window** —
   `scripts/phase213-classify.py:98` (`_all_health_rows`, glob `health-*.ndjson` at `:106-108`).
   Each `(wan, test)` window contains BOTH `health-spectrum.ndjson` AND `health-att.ndjson`.
   `[VERIFIED: source read]`

3. **The delta is `max-min` over the summed cumulative counter** —
   `scripts/phase213-classify.py:277-278`: `vals = [dl + ul for each row]`, then
   `delta = max(vals) - min(vals)`. `[VERIFIED: source read]`

**The decisive raw-data analysis (`RUN-20260527T222043Z`):** I computed per-file counter values
across all 20 health files. `[VERIFIED: data analysis of raw ndjson]`

| Window | spectrum file (dl+ul) | att file (dl+ul) | merged max-min (what classifier reports) | same-WAN delta |
|--------|----------------------|------------------|------------------------------------------|----------------|
| att/tcp_download | flat 14451 | flat 0 | **14451** | 0 |
| att/tcp_upload | flat 14451 | flat 0 | **14451** | 0 |
| att/rrul, att/browse, att/tcp_12down | flat 14451 | flat 0 | **14451** | 0 |
| spectrum/tcp_download | 13487→14003 | flat 0 | **14003** | 516 |
| spectrum/rrul | 14003→14451 | flat 0 | **14451** | 448 |
| spectrum/tcp_upload | 13097→13487 | flat 0 | **13487** | 390 |
| spectrum/browse | flat ~13077..13097 | flat 0 | **13097** | 20 |

Findings:
- **The constant `14451` (and `13097`, etc.) is Spectrum's cumulative lifetime counter.** When an
  `att/*` window merges Spectrum's `health-spectrum.ndjson` (sitting at 14451) with ATT's own
  `health-att.ndjson` (sitting at 0), `max-min = 14451 - 0 = 14451`. The "eerily constant 14451
  across unrelated ATT tests" is **entirely** this cross-WAN merge of a flat lifetime counter.
- **ATT's own counter is 0 in every window** — ATT showed zero backlog suppression at all.
- **The only genuine same-WAN deltas** (20, 390, 448, 516 on Spectrum) are the lifetime counter
  advancing a handful of ticks *during* the window on **GREEN-recovery backlog suppression**
  (`queue_controller.py:274`), with `arb_refractory_active=0` throughout. These are not refractory
  events; they are the normal backlog-suppress-during-GREEN-recovery mechanism doing its job.
- The flag fired because the classifier threshold is `BUCKET_5_BACKLOG_SUPPRESSED_DELTA=100`
  (`signal-sheet.json threshold_constants`), and the merged artifact `14451 >> 100`. Even the
  largest genuine same-WAN delta (516) is the GREEN-recovery counter, not a refractory signal.

**Conclusion for D-02:** No target-WAN-only, per-file delta remains meaningful as a refractory
distress signal. The flag is an artifact of (a) merging two WANs' files and (b) deltizing a
monotonic lifetime counter that increments on GREEN recovery rather than refractory. It must not
influence the verdict. (Secondary observation, out of scope for 216: the classifier's
per-WAN-merge + cumulative-counter deltization is a latent classifier bug — candidate note for a
classifier-hardening follow-up alongside WR-02, but NOT a control-path change.)

### D-03 — Phase 197 is the de-facto resolution; its tests are the semantic proof (HIGH confidence)

**Verdict: confirmed. `tests/test_phase_197_replay.py` asserts exactly the refractory-active
arbitration branches the verdict relies on. Targeted run: 21 passed.** `[VERIFIED: pytest run]`

`.venv/bin/pytest tests/test_phase_197_replay.py tests/test_phase213_classify.py -q` → `21 passed in 0.88s`.

Behaviors the Phase 197 replay tests actually cover (file:line verified):

| Behavior | Test | Asserts |
|----------|------|---------|
| Queue-primary held during refractory (valid snapshot) | `TestPhase197RefractoryQueueArbitration::test_refractory_window_keeps_queue_primary_with_valid_snapshot` (`:211`) | every one of 40 refractory cycles returns `primary=="queue"` + reason `queue_during_refractory`; refractory clears to 0 and reason reverts. |
| RTT fallback during refractory (None snapshot) | `TestPhase197RTTFallbackDuringRefractory::test_rtt_fallback_during_refractory_when_snapshot_none` (`:241`) | `primary=="rtt"` + reason `rtt_fallback_during_refractory`. |
| RTT fallback during refractory (cold_start snapshot) | `:253` | same as above for cold_start. |
| Phase 160 cascade safety preserved | `TestPhase197NoCascadeOnDetection::test_detection_path_does_not_recascade_during_refractory` (`:274`) | `adjust_4state` receives `cake_snapshot=None` for every refractory cycle. |
| Byte-identity outside refractory | `TestPhase197NonRefractoryByteIdentity` (`:127`), `...IntegratedNonRefractoryByteIdentity` (`:163`) | 24-row TRACE matches `EXPECTED_ZONES`/`EXPECTED_*_RATES`; refractory reasons never emit when remaining==0. |
| RTT-veto unreachable during refractory | `TestPhase197HealerBypassInteractions::test_rtt_veto_unreachable_during_refractory` (`:349`) | forced veto preconditions still return `queue` + `queue_during_refractory`. |
| Healer-bypass streak reset / non-increment during refractory | `:305`, `:326` | streak resets on entry, stays 0 during window. |

The shipped code these tests exercise is live in `src/wanctl/wan_controller.py`:
- Reason constants: `ARBITRATION_REASON_QUEUE_DURING_REFRACTORY="queue_during_refractory"` (`:101`),
  `ARBITRATION_REASON_RTT_FALLBACK_DURING_REFRACTORY="rtt_fallback_during_refractory"` (`:102`). `[VERIFIED]`
- Arbitration branch: `_select_dl_primary_scalar_ms` returns queue-primary during refractory at
  `:2889-2894` and RTT-fallback-during-refractory at `:2913-2920`. `[VERIFIED]`
- The split the thread proposed as a "candidate design" is what 197 actually shipped:
  `dl_cake_for_detection = self._dl_cake_snapshot` / `dl_cake_for_arbitration = self._dl_cake_snapshot`
  at `wan_controller.py:2932-2933`, detection masked to `None` during refractory at `:2937-2939`
  while arbitration keeps the live snapshot. This is precisely thread Next-Step line 66
  (`split dl_cake_for_detection from dl_cake_for_arbitration`). `[VERIFIED]`

**Gap (honest reporting):** These are replay/unit tests on synthetic traces. They prove the
*arbitration logic* is correct when refractory is active. They do NOT prove a real production
refractory event behaves identically end-to-end (no such event exists in the 213 baseline). That
is acceptable for a no-change close but is exactly why D-04a reopen criteria are required.

### D-01 — Phase 213 shows NO CURRENT SYMPTOM, not "validated" (HIGH confidence)

**Verdict: confirmed on all points. The WR-02 bug exists as described, and the recovery-lag zeros
cannot be read as positive recovery evidence.**

1. **`pct_samples_refractory_active=0.0` everywhere; refractory path never entered.** Raw analysis:
   `arb_refractory_active` is true in **0 of all rows** across all 20 files, and
   `cake_dl_refractory_remaining` max is **0** in every file. The refractory window was never
   armed during the baseline. `[VERIFIED: data analysis]`

2. **Every recovery-input window is 100% GREEN.** download_state distribution for the
   `tcp_12down` and `rrul` windows (the inputs to `analyze_download_recovery`): `[VERIFIED]`
   - all 8 such files: `{'GREEN': 89}` or `{'GREEN': 94}` — **zero RED, zero SOFT_RED, ever.**

3. **The WR-02 bug exists exactly as documented** (`213-REVIEW.md` §WR-02,
   `scripts/phase213-classify.py:146-159`): `green_after` starts `None`, is only set on confirmed
   recovery (`:152-155`), and `lag = float(green_after or 0)` at `:158`. A window that enters RED
   and never recovers logs `0.0`. Combined with finding (2), the `time_to_green_after_red_sec=0.0`
   rows mean **"no RED/SOFT_RED was ever observed"** (`last_red_idx` stayed `None`) — NOT "RED
   recovered in zero seconds." `[VERIFIED: source + data]`

**What 213 can support:** A no-change close, framed as *"no current live symptom of the original
regression under this baseline load."* It CANNOT support "refractory semantics are correct" (the
path was never exercised) and CANNOT serve as recovery-lag evidence for future tuning (no
transient event occurred). This matches D-01/D-01a verbatim.

## Verdict Logic (for the planner — recommendation, not a locked verdict)

All three exit criteria pass:
- **EC1 (D-02):** backlog flag is a proven merge/cumulative-counter artifact → no weight. ✓
- **EC2 (D-03):** Phase 197 code + replay tests cover the refractory-active branches; 21 passed. ✓
- **EC3 (D-01):** Phase 213 confirms no current live symptom (and provably no exercised refractory
  window). ✓

→ Recommended verdict: **no-change / resolved-by-197.** No follow-up phase required for control
behavior. Optional, separate-from-control candidate follow-up: classifier hardening (fix the
per-WAN merge + cumulative-counter deltization in `phase213-classify.py:98/271/277` and the WR-02
zero-lag conflation at `:146-159`) — this is tooling, not the control path, and is the planner's
discretion to seed or skip. It does NOT count as a RECOV control-design follow-up.

## Mechanics: How to Close the Thread (HIGH confidence)

**Thread file:** `.planning/threads/phase-196-queue-primary-refractory-semantics-investigation.md`
- YAML front-matter currently: `status: in_progress`, `updated: 2026-04-27`. `[VERIFIED]`
- Closing mechanically = (a) flip `status: in_progress` → `status: closed`, (b) bump `updated`,
  (c) append a closeout section recording the verdict, the three exit-criteria findings (with
  evidence citations), and the D-04a reopen triggers. STATE.md "Deferred Items" table also lists
  this thread as `in_progress` (line ~72) — update that row to closed for consistency.
- The thread's "Current conclusion" (design conflict, line 47) is now superseded: Phase 197
  shipped the candidate split design (thread line 66). Note this explicitly in the closeout so the
  stale-open status is resolved rather than silently overwritten.

**Reopen trigger to record (D-04a), with the concrete field name:** Reopen if a natural
production `/health` artifact shows **`signal_arbitration.refractory_active == true`**
(`arb_refractory_active` in the 213 projection; source: `wan_controller`/health payload, projected
at `phase213-health-poller.sh:197`) ACCOMPANIED BY any of:
- `active_primary_signal == "rtt"` during what should be queue-primary load (RTT fallback), or
- measurable recovery lag after RED/SOFT_RED (a real `time_to_green_after_red_sec > 0` with
  `recovered: true`), or
- throughput collapse during the refractory window.

## Report Conventions (216-REPORT.md) — match 212/213/214/215 (HIGH confidence)

Sibling reports exist at `.planning/phases/21{2,3,4,5}-*/2*-REPORT.md`. The 213 report is the
closest model. Operator-first closeout shape to mirror:
- **Title + 1-paragraph Summary** stating the verdict and that no control-path change was made.
- **Requirement coverage table** (REQ | coverage note | verdict | evidence path | downstream
  impact) — RECOV-01/02/03 rows.
- **Per-exit-criterion findings** (D-02 artifact proof, D-03 test confirmation, D-01 no-symptom),
  each with concrete evidence paths and file:line citations.
- **Verdict** section (no-change / resolved-by-197) with the honest framing from CONTEXT
  `<specifics>`: "no NEW change; 197's shipped change stands and is validated by its own tests" —
  NOT "213 proved it correct."
- **Downstream constraints / reopen criteria** (D-04a triggers; D-05 cascade-safety carry-forward
  for any future follow-up; D-06 steering-name caveat).
- **Run metadata** referencing `RUN-20260527T222043Z`.

Use stable evidence paths (the `RUN-20260527T222043Z/...` ndjson and `signal-sheet.json`) exactly
as 213/214/215 reports do.

## Phase 160 Cascade-Safety Invariant (RECOV-02 / D-05) — what a follow-up must preserve

Authoritative description, verified:
- **The invariant:** during the 40-cycle refractory window, the *detection* path must see
  `cake_snapshot=None` so a single congestion event cannot re-fire dwell-bypass and cascade into
  repeated CAKE drop/backlog reductions. Enforced at `wan_controller.py:2937-2939` (mask detection,
  decrement remaining) and guarded by `test_phase_197_replay.py::TestPhase197NoCascadeOnDetection`.
  `[VERIFIED]`
- **`refractory_cycles=40` is a deliberate conservative choice.**
  `.planning/milestones/v1.33-phases/163-parameter-sweep/163-02-SUMMARY.md`: A/B tested 20/40/60;
  40 kept under the D-06 5%-noise rule ("20 only 3.1% better"); explicit rationale "shorter
  cooldown risks cascading reductions on single events." `[VERIFIED]` Refractory arms from
  `dwell_bypassed_this_cycle` → `_dl_refractory_remaining = refractory_cycles` at
  `wan_controller.py:3053-3054`. Default 40, clamped to `[1,200]` at `:962-969`.
- **The queue-primary requirement (the other half of RECOV-02):** a valid queue-delay scalar must
  remain available for queue-primary classification during refractory. Phase 197 satisfies this by
  keeping `dl_cake_for_arbitration` live while masking only detection. Any seeded follow-up MUST
  keep both halves: detection masked (no cascade) AND arbitration scalar live (queue-primary).

## Runtime State Inventory

Not applicable in the rename/migration sense — 216 changes no code, config, datastore, or
service. But the relevant "what is in runtime state" check for the verdict is the inverse: *what
runtime evidence exists vs. what the verdict claims.*

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Captured production evidence | `RUN-20260527T222043Z` — 20 `/health` ndjson files, `signal-sheet.{json,md}`, manifest | None — read-only; cite in report |
| Live refractory state in evidence | `arb_refractory_active=0` and `dl_refractory_remaining=0` in ALL files; 100% GREEN in recovery windows | None — confirms no-symptom framing |
| Thread state | `phase-196-...md` front-matter `status: in_progress`; mirrored in STATE.md Deferred Items | Flip both to closed |
| Code/config/service mutation | None — decision-only | None — boundary preserved by construction |
| Build artifacts | None | None |

## Common Pitfalls

### Pitfall 1: Treating "no symptom" as "validated"
**What goes wrong:** Writing "Phase 213 validated refractory semantics."
**Why it happens:** The bucket was flagged and the path "looks fine."
**How to avoid:** State plainly that `pct_samples_refractory_active=0.0` means the path was never
exercised; the semantic proof is Phase 197's tests. (Codex HIGH concern.)
**Warning signs:** Any sentence crediting 213 with proving correctness.

### Pitfall 2: Reading `time_to_green_after_red_sec=0.0` as fast recovery
**What goes wrong:** Citing the zeros as positive recovery evidence.
**Why it happens:** Zero looks like "instant."
**How to avoid:** Cite finding D-01: every recovery-input window is 100% GREEN, and WR-02 logs
non-recovery as zero. Zero here means "no RED observed."
**Warning signs:** Recovery-lag rows used to justify a tuning claim.

### Pitfall 3: Letting the 14451 backlog delta sway the verdict
**What goes wrong:** Treating 14451 as a per-event distress signal.
**How to avoid:** Cite the D-02 proof — it's a cross-WAN merge of a flat lifetime counter; ATT's
own counter is 0; genuine same-WAN deltas are tiny and are GREEN-recovery suppression, not
refractory. `[VERIFIED: data]`

### Pitfall 4: Slipping a control change into the decision phase
**What goes wrong:** Recommending `green_required`/`step_up`/refractory tuning inside 216.
**How to avoid:** Hard boundary — any tune/code goes in a separate seeded follow-up
(success criterion 4). 216 is decision-only.

### Pitfall 5: Mixing steering threshold-name drift into refractory reasoning
**What goes wrong:** Using v1.39 steering field names as v1.45 semantics (D-06).
**How to avoid:** Base the decision on autorate `/health` + CAKE signal evidence only.

## Code/Evidence Examples (verified citations)

```
# D-02 counter increments on GREEN recovery, NOT refractory:
src/wanctl/queue_controller.py:265   # "DETECT-02: Suppress green_streak while backlog is high"
src/wanctl/queue_controller.py:274   #   self._backlog_suppressed_count += 1   (monotonic lifetime)

# D-02 classifier merge + max-min over cumulative counters:
scripts/phase213-classify.py:98      # _all_health_rows: merges ALL health-*.ndjson per (wan,test)
scripts/phase213-classify.py:277-278 # vals = dl+ul per row; delta = max(vals) - min(vals)

# D-03 shipped 197 arbitration (the semantic proof's target):
src/wanctl/wan_controller.py:101-102 # queue_during_refractory / rtt_fallback_during_refractory
src/wanctl/wan_controller.py:2889-2894 / 2913-2920  # the two refractory arbitration branches
src/wanctl/wan_controller.py:2932-2939  # split detection(masked)/arbitration(live) + decrement
tests/test_phase_197_replay.py:211,241,253,274  # the asserting tests

# D-01 WR-02 zero-lag conflation:
scripts/phase213-classify.py:146-159 # lag = float(green_after or 0); non-recovery logs 0
```

## State of the Art

| Old (thread's view, 2026-04-27) | Current (verified 2026-05-29) | When Changed | Impact |
|---|---|---|---|
| "Design conflict between Phase 160 refractory safety and queue-primary goals; do not patch without a follow-up" | Phase 197 shipped the exact candidate split design (detection masked, arbitration live), tests pass 21/21 | Phase 197 (v1.40) | Thread is stale-open only because it was never updated; close as resolved-by-197 |
| Backlog delta 14451 is a runner-up distress signal | Proven cross-WAN merge artifact of a flat lifetime counter | This research | Flag carries no weight |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | (none) | — | All load-bearing claims were verified against source reads, raw evidence analysis, or a live pytest run. |

**This table is intentionally empty — every factual claim in this research is VERIFIED, not assumed.**

## Open Questions

1. **Should 216 seed a classifier-hardening follow-up?**
   - What we know: `phase213-classify.py` has two real bugs (per-WAN merge + cumulative deltization
     in `analyze_refractory`; WR-02 zero-lag in `analyze_download_recovery`). Both are tooling, not
     control path.
   - What's unclear: whether the operator wants tooling fixes tracked as a phase/todo now or left
     as a noted observation.
   - Recommendation: note both in the report as classifier observations; offer (planner discretion)
     a low-priority tooling follow-up/todo. Do NOT classify it as a RECOV control-design follow-up
     (it changes no control behavior, so RECOV-02 does not apply).

2. **Does "resolved-by-197" need post-197 production validation beyond the replay tests?**
   - What we know: 213 contains no refractory event; 197 tests are synthetic.
   - What's unclear: whether any post-197 production soak captured a real `arb_refractory_active>0`
     event historically.
   - Recommendation: the D-04a reopen trigger covers this — close now on test+no-symptom basis,
     reopen if a natural production refractory event later shows a symptom. (Optionally grep
     prior soak artifacts for `refractory_active=true`, but not required for the close.)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv + pytest | running 197 replay tests | ✓ | `.venv/bin/pytest` (21 passed) | — |
| 213 evidence corpus | D-01/D-02 analysis | ✓ | `RUN-20260527T222043Z` present, 20 health files | — |
| Live `/health` endpoints | NOT needed (D-01 passive) | n/a | — | 213 already captured |

No external dependency is missing. 216 needs no live probing, no RouterOS access, no services.

## Validation Architecture

> nyquist_validation is not disabled in config; included. 216 ships no code, so "validation" =
> confirming the cited evidence/tests, not writing new tests.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project `.venv`) |
| Config file | `pyproject.toml` (addopts present; use `-o addopts=''` for focused slices) |
| Quick run command | `.venv/bin/pytest tests/test_phase_197_replay.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RECOV-01/03 (D-03) | refractory arbitration branches correct | unit/replay | `.venv/bin/pytest tests/test_phase_197_replay.py -q` | ✅ (21 passed) |
| D-02 classifier behavior | classifier emits expected buckets | unit | `.venv/bin/pytest tests/test_phase213_classify.py -q` | ✅ |
| RECOV-02 (Phase 160) | detection masked during refractory | unit/replay | `...::TestPhase197NoCascadeOnDetection` | ✅ |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_phase_197_replay.py tests/test_phase213_classify.py -q`
- **Phase gate:** the above green (already verified 21 passed). No new tests required for a
  decision-only close.

### Wave 0 Gaps
- None — existing test infrastructure fully covers the D-03/RECOV-02 claims. If the planner seeds
  a classifier-hardening follow-up, that follow-up (not 216) owns new classifier tests.

## Security Domain

> `security_enforcement` posture: 216 is a strictly read-only / planning-artifact phase (no code,
> config, service, network, or secret surface). Phase 214 set precedent (`[214 UAT]`: security gate
> waived for a strictly read-only investigation per operator).

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | 216 touches no auth surface |
| V5 Input Validation | no | no new input handling; reads existing evidence |
| V6 Cryptography | no | no crypto; D-08 redaction already applied to 213 steering artifacts |

No threat surface introduced. The only handling note: any evidence quoted in the report must
preserve the D-08 redaction already applied in 213 (no secrets, no private host detail beyond what
sibling reports already publish).

## Sources

### Primary (HIGH confidence — verified this session)
- `src/wanctl/queue_controller.py:116,244,265,274,639,732-733` — backlog counter provenance.
- `src/wanctl/wan_controller.py:101-102,2879-2921,2932-2939,3050-3064,962-969,4587-4592` —
  arbitration reasons, refractory split, arm/decrement, payload emission.
- `scripts/phase213-classify.py:98,146-159,271-281` — merge, WR-02 zero-lag, refractory analysis.
- `scripts/phase213-health-poller.sh:188-197` — health field projection (confirms captured fields).
- `tests/test_phase_197_replay.py` — full read; 21 passed via `.venv/bin/pytest`.
- `RUN-20260527T222043Z` raw ndjson — per-file counter/state/refractory analysis (this session).
- `.planning/phases/213-experience-baseline-harness/213-REVIEW.md` §WR-02 — bug confirmed.
- `.planning/phases/213-experience-baseline-harness/213-REPORT.md` — report format + bucket §5.
- `.planning/threads/phase-196-...md` — thread status + candidate design (line 66).
- `.planning/milestones/v1.33-phases/163-parameter-sweep/163-02-SUMMARY.md` — `refractory_cycles=40` rationale.

### Secondary
- `216-CONTEXT.md`, `216-REVIEWS.md` (Codex review), `REQUIREMENTS.md`, `STATE.md` — scope/constraints.

### Tertiary (LOW confidence)
- None — no unverified claims were relied upon.

## Metadata

**Confidence breakdown:**
- D-02 artifact proof: HIGH — proven by source read + per-file raw-data analysis (the 14451 is
  fully explained as a cross-WAN merge of a flat lifetime counter).
- D-03 test coverage: HIGH — tests read line-by-line; 21 passed live.
- D-01 no-symptom + WR-02: HIGH — source read + 100%-GREEN data confirmation.
- Thread-close mechanics + report format: HIGH — file structure and sibling reports inspected.
- Phase 160 invariant: HIGH — code + test guard + 163 sweep rationale verified.

**Research date:** 2026-05-29
**Valid until:** ~30 days (evidence corpus is frozen; code is production-stable). Re-verify only if
a new production capture with `arb_refractory_active > 0` appears (which would itself be a reopen
trigger).
