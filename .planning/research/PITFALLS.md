# Pitfalls Research

**Domain:** Adaptive CAKE controller for production dual-WAN — v1.47 read-only measurement evidence closure
**Researched:** 2026-05-29
**Confidence:** HIGH (drawn from concrete v1.45/v1.46 phase artifacts and shipped controller behavior)
**Scope:** v1.47 Scopes A (tcp_12down target/path sensitivity matrix) + D (ingestion-rate observability)

---

## Critical Pitfalls

### Pitfall 1: Confirmation bias on Vultr Dallas/Chicago supplemental evidence

**What goes wrong:**
The Phase 214 canonical Spectrum/Dallas matrix returned `ambiguous` / `reflector_loss` / `signal=none` and did NOT reproduce the historical catastrophic `p99 > 1000ms`. The off-peak supplemental Vultr Dallas (p99 `767ms`, median throughput `277.6 Mbit/s`) and Vultr Chicago (p99 `701ms`, `277.9 Mbit/s`) runs landed AFTER the official window closed clean (p99 `120ms`). v1.47 will be tempted to design a matrix that "obviously" reproduces those Vultr numbers — selecting target hosts, sizes, durations, and time windows that maximize the chance the supplemental anomaly reappears. The matrix then becomes a confirmation harness for the prior hypothesis, not a sensitivity test.

**Why it happens:**
The supplemental evidence is dramatic (severe p99, low throughput, LibreQoS bufferbloat grade B) and visceral — and it is already in the record (`214-REPORT.md` §Matrix Verdict). Phase 214 explicitly carried the folded `tcp_12down` todo **narrower**, not closed, which means humans now expect a follow-up to validate the supplemental signal. The matrix designer naturally biases cell selection toward conditions where the supplemental evidence was seen.

**How to avoid:**
- Pre-register kill criteria for the hypothesis BEFORE the matrix runs. Write `KILL.md` or a §Kill Criteria block in the phase CONTEXT that names: "hypothesis killed if N of M off-peak runs against Dallas/Chicago Vultr produce p99 ≤ X ms with throughput ≥ Y Mbit/s."
- Include at least one **control cell** with a target known to be clean per the canonical matrix (the same Dallas reflector used in `RUN-20260529T060507Z`, which produced p99 `120ms` off-peak). If the control cell ALSO collapses in v1.47, the problem is local/path, not target-specific, and the hypothesis collapses too.
- Require **both** the canonical Phase 214 reflector AND the supplemental Vultr targets in every time window — never a Vultr-only matrix.
- Phase 215 bounded VOID is the template: declare upfront how many attempts equal exhausted, what counts as decisive vs. non-decisive evidence, and what the rollback (or in v1.47's case, the "kill" or "carry-narrower") looks like.

**Warning signs:**
- Cell list has only Vultr Dallas / Vultr Chicago and no canonical-matrix reflector.
- Time windows weighted toward off-peak (where supplemental fired) and skipping daytime (where canonical also showed ambiguity).
- Matrix CONTEXT.md references the supplemental p99 numbers but not the canonical p99 `120ms` off-peak result.
- "Sensitivity matrix" actually has 1 dimension (target) varied while time-of-day and load shape are pinned to the conditions where the prior fired.

**Phase to address:** Scope A primary matrix-design phase. Must be enforced in the phase CONTEXT/RESEARCH stage, before any live runs.

---

### Pitfall 2: Missing pre-registered kill criteria — "carried-narrower forever"

**What goes wrong:**
Phase 214 closed with `carried-narrower`, which was correct given the evidence. But v1.47 risks the same outcome by default: no matrix is "clean enough" to kill `tcp_12down`, and no matrix is "dirty enough" to declare a defect found, so the todo gets carried narrower a second time. Two milestones in, the todo is still live, the canonical evidence still shows ambiguous tail latency, and there is no path to closure.

**Why it happens:**
"Carry narrower" is the path of least resistance when evidence is mixed. It feels intellectually honest. It is also the way live investigations become institutionally permanent. Without explicit, pre-registered closure criteria, every ambiguous result is a reason to investigate more.

**How to avoid:**
- v1.47 must write **kill criteria AND defect criteria** before runs start, both quantitative and time-bound. Example: "Hypothesis killed if matrix produces ≥ 8 of 12 cells with p99 ≤ 200ms and no signal-disposition driver fires. Defect located if ≥ 4 cells produce p99 > 1000ms AND aligned-window evidence shows a single primary driver across them."
- Bound the carry-narrower outcome explicitly: "If verdict is again `ambiguous`, the folded todo is **closed-with-prejudice** — no v1.48+ follow-up without new independent evidence (production journal event, operator-reported incident, or external benchmark)." This forces the matrix to either prove something or release the hypothesis.
- The closeout decision report (already in milestone scope) must contain the explicit verdict statement — "defect located", "hypothesis killed", or "carried-narrower with the following close-with-prejudice rule" — and the rule must be machine-checkable for the next milestone.

**Warning signs:**
- CONTEXT.md describes the matrix design but has no §Kill Criteria / §Defect Criteria sections.
- The phase plan allows "iterate the matrix if results are ambiguous" without a stopping rule.
- The roadmap names a v1.48+ tcp_12down follow-up phase preemptively — that means the team already expects to carry-narrower again.

**Phase to address:** Scope A matrix-design phase (define criteria) + Scope A closeout decision report phase (apply criteria). Cross-cutting: also surface in milestone REQUIREMENTS as an explicit gate.

---

### Pitfall 3: Sampling clustered in time / replicates without independence

**What goes wrong:**
Phase 214 captured exactly one run per window (one daytime, one prime-time, one off-peak). Each cell is `n=1`, which makes "ambiguous" the only honest verdict but also means the matrix cannot distinguish between "this target is consistently bad" and "this target had one bad minute." v1.47 risks repeating the pattern: 3 windows × 3 targets = 9 cells, each `n=1`, with all runs back-to-back on the same evening. Result: replicates clustered in time and share daytime-pattern-of-life, BGP path state, target-side load, and even local DOCSIS upstream contention.

**Why it happens:**
- Flent runs are slow (30-60s each), live cellular setup is fiddly, and operators want to finish the matrix in one sitting.
- Phase 198 used a 3-run rerun pattern; v1.47 will be tempted to copy it without re-evaluating whether 3 back-to-back runs constitute independent replicates.
- "Replicates" sounds like the answer, but n=3 separated by 5 minutes is functionally n=1 against any minute-scale environmental confounder (BGP path change, CMTS scheduler state, remote target daytime load shift).

**How to avoid:**
- Replicates per cell must be separated by **at least one full envelope of the dominant confounder**. For prime-time DOCSIS, that's ≥ 30 minutes between replicates of the same (target, time-window) cell — not 5 minutes.
- Aim for **minimum n=3 per cell**, with replicates intentionally spread across multiple days for at least one cell as a "day-of-week" control.
- If matrix size makes that infeasible, **shrink the matrix**, not the per-cell n. A 2-target × 2-window × n=3 matrix with proper spacing beats a 4-target × 3-window × n=1 matrix.
- Record per-replicate provenance (BGP path snapshot via `mtr --json --no-dns -c 3 <target>`, time of day in local TZ, ATT or steering-state context) so cells can be diagnosed after the fact.

**Warning signs:**
- Matrix plan shows all cells completing in < 2 hours of wall-clock time.
- Cells with `n=1` and no plan to expand on disagreement.
- No path/route snapshot captured per replicate — only the flent .gz.
- Replicate timestamps cluster within minutes of each other.

**Phase to address:** Scope A matrix-design phase (sampling plan in CONTEXT) and the matrix-execution phase (operator-runbook discipline).

---

### Pitfall 4: Confounders ignored — BGP/anycast/DNS variance, MTU asymmetry, captive-portal/CAPTCHA

**What goes wrong:**
A "target/path sensitivity matrix" implicitly assumes the target is stable per-cell and only varies across cells. In reality:
- Anycast targets (Vultr public reflectors, LibreQoS endpoints) route to different POPs across minutes via BGP. Two consecutive runs against `zylone.org` may not hit the same physical host.
- DNS resolution itself varies (TTLs, recursive resolver caching). A run that resolves `zylone.org` once and reuses the IP across replicates is measuring something different than a run that re-resolves every time.
- MTU asymmetry between Spectrum DOCSIS upstream and Vultr datacenters (1500 vs typical 1500, but PPPoE/encapsulation may differ on ATT contrast or upstream peering) can produce path-MTU discovery storms that look like p99 outliers.
- Target hosts can drift (Vultr instance migrations, LibreQoS endpoint rotations, IP reassignment) between v1.46 (when supplemental evidence was captured) and v1.47.

**Why it happens:**
Network measurement matrices are usually designed by people who treat the network as a wire. The wire is not a wire — it's a stack of policy decisions that change without notice.

**How to avoid:**
- Pin the target by IP for the duration of a replicate window. Resolve once at run start, cache, log the IP, and use that IP for all sub-runs. Re-resolve only between replicates. Log the IP per replicate.
- Capture an `mtr --json --no-dns -c 5 <ip>` snapshot before and after each replicate. If path AS-sequence changes between snapshots, mark the replicate as `path_changed=true` and exclude it from cell aggregation (or flag it for separate analysis).
- Verify reflector availability with a low-noise probe before each replicate (e.g., 5 ICMP pings without load). If baseline RTT is > 2× the historical baseline for that target, skip and re-queue.
- Add a known-stable **anchor target** (e.g., `1.1.1.1` or a hard-pinned operator-controlled host) to the matrix as a control. If the anchor degrades simultaneously with the supplemental target, the issue is local; if not, the target itself is suspect.
- Document target host as `<hostname>@<resolved-ip>@<UTC-timestamp>` in matrix-summary.json; do not aggregate cells across IP rotations.

**Warning signs:**
- Same hostname produces wildly different baseline RTT across replicates (likely BGP/anycast rerouting).
- Matrix output reports cells by hostname only, not by resolved IP.
- LibreQoS or Vultr targets fail mid-matrix and the phase plan has no provision for substituting.
- Captive-portal HTTP 302 redirects appear in network captures (this would invalidate the entire run).

**Phase to address:** Scope A matrix-execution phase (operator-runbook discipline). Add target-pinning and path-snapshot capture to the matrix wrapper script.

---

### Pitfall 5: Self-perturbing ingestion-rate observability

**What goes wrong:**
Scope D ships per-WAN `metrics.db` write-rate visibility. The naive implementation queries the live `metrics.db` from inside the controller cycle (or via the same SQLite connection pool the controller uses) at high frequency and writes its own row counter back to a new table. Result: the tool's own queries lock the DB more often, the tool's own writes inflate the very metric it's measuring, and the cycle budget — currently `avg=2.883ms`, `p99=6.9ms` per Phase 217 — picks up a non-trivial new tail.

**Why it happens:**
- "Observe what's happening" feels harmless. SQLite SELECT COUNT seems cheap. It isn't, under DB pressure.
- Phase 217 confirmed `logging_metrics=8.26%` is already the dominant cycle category. Anything added to that path eats budget directly.
- v1.44 Phase 208 already shipped `wanctl-history --ingestion-rate` as a CLI surface that queries from outside the daemon. v1.47 must extend that, not bypass it.

**How to avoid:**
- **Snapshot-derived, not live-queried**: compute ingestion rate from row-count deltas across the existing per-cycle telemetry the controller already produces, not from independent SQLite scans on the hot path. If the controller already writes `metrics_db_rowcount` (or can with one numeric field added to the existing periodic-maintenance pass), the observability tool reads the snapshot — not the DB.
- **CLI tool vs `/health` boundary**: the CLI side (`wanctl-history --ingestion-rate`, or a new `wanctl-ingestion-rate`) runs out-of-band from the daemon and can be expensive. `/health` exposure (if any) must be O(1) — already-computed counters, never a live SELECT COUNT.
- **Budget the hot-path cost**: any new in-controller measurement must be measured against the Phase 217 baseline (`cycle_total.avg_ms=2.883`, `p99=6.9`). Acceptance threshold: < 0.1ms added to `avg_ms`, < 0.5ms added to `p99_ms`. If it exceeds, push it off the hot path entirely.
- **No new write paths in the cycle**: ingestion-rate observability MUST NOT introduce additional `metrics.db` writes inside the daemon. Compute deltas from existing rows, not from new tracker rows.

**Warning signs:**
- Design includes "the daemon records its own ingestion rate to a new table." Reject.
- Implementation plan adds a thread or scheduled callback to query SQLite at any rate > existing periodic maintenance cadence.
- Cycle budget profiling after deployment shows `cycle_total.avg_ms` > 3.0 or `p99_ms` > 7.5.
- New `/health` field requires a live SELECT to populate.

**Phase to address:** Scope D ingestion-rate observability design phase. Must be enforced in CONTEXT/RESEARCH and verified post-deploy with a small Phase 217-style profiling capture.

---

### Pitfall 6: Per-WAN vs per-metric vs per-table granularity hides the actual bottleneck

**What goes wrong:**
Scope D ships a single global `ingestion_rate_rows_per_sec`. The number is steady. Phase 218 audit needs to know whether spectrum or att caused a 24h flapping event's ingestion to spike, AND whether the spike was alerts or cycles or both. Single-number observability cannot answer those questions, so the tool ships and Phase 218 still has to query SQLite directly.

**Why it happens:**
"One number, easy to read" is a real UX pull. CLI tools in this project tend toward operator-friendly summaries. The dimension that matters for audit (per-WAN × per-table) is invisible from the summary.

**How to avoid:**
- Default CLI output is per-WAN × per-table at a useful cadence (e.g., 1-minute buckets over the last hour, 5-minute buckets over the last day).
- Provide a `--summary` flag for the operator-friendly single-number view, but the audit-grade output is the default.
- Tables that matter for Phase 218 evidence audits: `cycles`, `alerts`, `transitions`, `signal_quality`, `irtt_measurements` (per the v1.18/v1.19 schemas). Pin the table list in code, not config, so it doesn't drift.
- JSON output mode (consistent with Phase 208's `wanctl-history --ingestion-rate` table/object pattern) for scripted Phase 218 evidence collection.

**Warning signs:**
- Plan shows a single global counter and no per-WAN breakdown.
- Plan does not enumerate which SQLite tables count toward "ingestion."
- No JSON output mode (Phase 218 will need to consume the data programmatically).
- The Phase 218 evidence-audit example does not exercise this tool.

**Phase to address:** Scope D design phase, with a Phase 218 audit example as the design driver (work backward from "what does Phase 218 need to query?").

---

### Pitfall 7: Stale snapshots vs live counter drift

**What goes wrong:**
Scope D reports ingestion rate from a snapshot computed at maintenance cadence (say, every 60s). Operator runs the CLI at second 59, gets a 59-second-old snapshot showing 12 rows/sec. Operator restarts wanctl at second 60. CLI at second 61 shows the stale 12 rows/sec, masking the restart spike. Phase 218 audit pulls the wrong window and sees no incident.

**Why it happens:**
Pushing computation off the hot path (per Pitfall 5) means snapshots, not live counters. Snapshots are inherently stale. The implementer makes the staleness fixed but doesn't expose it.

**How to avoid:**
- Every snapshot field MUST be paired with a `_snapshot_age_sec` or `_snapshot_unix` field. CLI default output shows snapshot age inline.
- Snapshot cadence should match or beat the operator-relevant decision interval. If Phase 218 needs minute-resolution evidence, snapshot at ≤ 30s cadence. If 5-minute resolution is enough, snapshot at ≤ 90s.
- Provide a `--live` flag (CLI-only, never `/health`) that does an out-of-band live count for forensic use, with an explicit warning that it is more expensive.
- Document staleness semantics in the help text and in `docs/CONFIGURATION.md`. The v1.38 pattern (`measurement_stale`, `measurement_staleness_sec`) is the precedent — match it.

**Warning signs:**
- Snapshot field exposed without a staleness field.
- Snapshot cadence is hardcoded and not visible to the operator.
- CLI does not display snapshot age.
- The v1.38 measurement-staleness pattern is not referenced in the design.

**Phase to address:** Scope D design phase. Cross-cutting: applies to any `/health` exposure too.

---

### Pitfall 8: Mutation-boundary tests pass while behavioral assertions sneak in via fixtures/tests

**What goes wrong:**
Phase 214 enforced "zero `src/wanctl/` edits" via a passing mutation-boundary pytest. The boundary check looks at the source tree. But v1.47 could add a test fixture under `tests/fixtures/phase220/` that encodes "the controller SHOULD treat target X as degraded," and a follow-up phase quietly references that fixture as if it were a controller specification. The mutation boundary held; the behavioral commitment slipped in via the fixture / golden file.

**Why it happens:**
Read-only milestone discipline focuses on `src/wanctl/`. Tests, fixtures, golden files, and even YAML configs are easier to slip past the check because they "are not the controller."

**How to avoid:**
- Mutation-boundary tests in v1.47 must cover: `src/wanctl/**`, `configs/*.yaml` (production configs only), `deploy/systemd/*`, `scripts/*` that touch production. Test fixtures under `tests/fixtures/phase22*/` are allowed but flagged: PR review must confirm fixtures encode evidence, not specifications.
- Phase CONTEXT.md must state explicitly: "v1.47 fixtures and tests assert evidence-shape, not controller-behavior. Behavioral assertions belong in v1.48+ tuning milestones gated on this evidence."
- Closeout decision report cites every artifact and labels each as `evidence` or `analysis tool` — not `controller behavior change`. Any artifact that cannot be labeled cleanly is a smell.
- Phase 215 is the positive template: it changed YAML (an explicit, operator-approved one-knob change with rollback), proved bounded-VOID, and rolled back. v1.47 has no equivalent approved mutation; everything stays measurement-shape.

**Warning signs:**
- Test fixtures named `expected_*.json` for hot-path behavior (vs. `observed_*.json` for evidence).
- New tests added to the hot-path regression slice (`tests/test_cake_signal.py`, `tests/test_queue_controller.py`, `tests/test_wan_controller.py`, `tests/test_health_check.py`) — these are the controller-spec tests, not the evidence tests.
- Plan summaries that talk about "the controller will now…" instead of "the matrix shows…"
- Documentation under `docs/` (vs. `.planning/`) updated to pre-decide tuning before evidence lands.

**Phase to address:** Cross-cutting. Add to every v1.47 phase CONTEXT as a SAFE check. Mirror the v1.43/v1.44 SAFE-07/09 pattern.

---

### Pitfall 9: Documentation that pre-decides v1.47+ tuning before evidence lands

**What goes wrong:**
v1.47 is evidence-first read-only by mandate. But `docs/CONFIGURATION.md`, `CHANGELOG.md`, or `docs/PERFORMANCE.md` get edited mid-milestone with text like "future tuning may raise X threshold based on Phase 220 evidence" or "Vultr target sensitivity confirms the need for Y." This documentation commits the project to a position the matrix has not earned, and v1.48 inherits a foregone conclusion.

**Why it happens:**
Doc writers want to update operator-facing docs while the context is fresh. Evidence-first discipline doesn't usually feel like it applies to docs.

**How to avoid:**
- v1.47 docs/ edits are restricted to: (a) describing the new ingestion-rate CLI tool, (b) describing the matrix script's operator interface. No threshold-tuning language, no "future" predictions, no controller-behavior implications.
- The closeout decision report is the only place where verdicts are recorded. It lives under `.planning/`, not `docs/`. `CHANGELOG.md` cites the verdict by reference, not by paraphrase.
- Add a doc-mutation guard to the mutation-boundary check: `docs/` files matched against an allowlist for the milestone.

**Warning signs:**
- `docs/CONFIGURATION.md` diff includes any threshold value or any new YAML key not directly tied to Scope D's CLI.
- `docs/PERFORMANCE.md` diff references "expected future tuning" or "evidence suggests" without citing the closeout report.
- `CHANGELOG.md` v1.47 entry contains verdicts rather than artifact references.

**Phase to address:** Cross-cutting. Enforce in every v1.47 phase, especially the closeout decision report phase.

---

### Pitfall 10: Declaring "defect found" on a single ambiguous cell

**What goes wrong:**
One cell in the v1.47 matrix produces p99 `1100ms`. Everyone wants to call this the defect. The other 11 cells are clean (p99 < 200ms) or ambiguous (p99 300-600ms). The single hot cell is one (target, time, replicate) tuple and could trivially be a target-side garbage-collection event, a single BGP path flap, or a CMTS scheduler glitch. Declaring defect found on n=1 forces v1.48 into a tuning response based on noise.

**Why it happens:**
- Severe p99 numbers are visceral. So is the user-perceived "the internet feels slow" framing.
- The project has a known history (v1.40 cake-primary arbitration root cause) of carrier deprioritization producing real defects. Pattern-matching to that history is tempting.
- Phase 215 bounded-VOID set the precedent that severe outcomes warrant action; v1.47 may misapply the same instinct to a non-corroborated single cell.

**How to avoid:**
- "Defect found" requires **corroboration across at least one orthogonal axis**: same target on a different day, or different targets in the same time window, or matched journal-log evidence in `aligned-window.json` (the Phase 214 mechanism).
- Single-cell anomalies enter `signal_disposition=none` territory by default. Carry-narrower applies unless corroborated.
- The closeout decision report must include the table of cells with verdict per cell, and the aggregate verdict must be explicitly derived from the cell verdicts via the pre-registered rule (Pitfall 2).

**Warning signs:**
- Discussion log starts referring to "the defect" before the matrix is fully captured.
- Closeout report headline cites a single p99 number.
- Aggregate verdict is announced before per-cell verdicts are computed.
- Plan to skip remaining cells because "we already know."

**Phase to address:** Scope A closeout decision report phase. Reinforced in matrix-design phase via §Defect Criteria.

---

### Pitfall 11: Phase 218 watch-list interaction — coupling parallel work to v1.47 gates

**What goes wrong:**
Phase 218 is event-gated on a natural production DOCSIS flapping event with `peak_transition_count > 30`. It runs in parallel with v1.47. The risk is bidirectional coupling: (a) v1.47 phases wait on Phase 218 evidence that may never arrive in the milestone window, or (b) Phase 218 evidence audit needs Scope D's ingestion-rate tool before that tool has shipped, and Phase 218 fires before Scope D lands.

**Why it happens:**
"Ingestion-rate observability tool — sized for Phase 218 audit evidence" (per the milestone goal) creates an implicit dependency. The dependency is harmless if Scope D ships before Phase 218 fires; it is harmful if the order inverts.

**How to avoid:**
- Sequence Scope D before Scope A's matrix-execution phase, so the ingestion-rate tool is available the moment Phase 218 fires.
- If Phase 218 fires before Scope D ships, Phase 218 falls back to the existing `wanctl-history --ingestion-rate` from v1.44 Phase 208. Document this fallback in the milestone REQUIREMENTS so there is no surprise.
- v1.47 closeout decision report does NOT block on Phase 218. The report covers Scope A + Scope D outcomes. Phase 218 outcomes are tracked separately and may close after v1.47 ships-with-deferral.

**Warning signs:**
- Roadmap shows Scope A closeout depending on Phase 218 evidence.
- Scope D ships after the matrix-execution phase — too late to support Phase 218.
- Discussion log uses "Phase 218 will validate this" as a way to skip pre-registered kill criteria.

**Phase to address:** Roadmap-level phase ordering. Cross-cutting: explicit in milestone REQUIREMENTS.

---

### Pitfall 12: Treating `/health.status == healthy` or `GREEN` as good user experience

**What goes wrong:**
v1.46 close noted explicitly: "Do not treat `/health.status == healthy` or `GREEN` as sufficient proof of good user experience." Phase 214 showed exactly this: `/health` reported `healthy` while flent measured p99 `606ms` and the measurement state was `collapsed` on the same row. v1.47 closeout report risks reusing `/health`-derived signals as if they were quality signals — e.g., "during the matrix, `/health` showed no degradation, so the elevated p99 is a measurement artifact."

**Why it happens:**
`/health` is the canonical operator surface. It is what the daemon publishes. It is hard to remember it is a controller-state surface, not a user-experience surface.

**How to avoid:**
- Closeout report must derive user-experience claims **only** from flent-side measurements (or operator-reported incident evidence), never from `/health`-side claims.
- When `/health` is cited, it must be cited as controller-state context, not as a quality signal. Use language like "`/health` reported `download_state=GREEN` while flent measured p99 `X`ms" — paired, never sole.
- Aligned-window.json (Phase 214 mechanism) is the contract: it pairs flent and `/health` at 1Hz. Use it; do not abandon it.

**Warning signs:**
- Closeout report sentences like "the WAN was healthy during the matrix."
- Verdict text references `/health` without paired flent evidence.
- `aligned-window.json` is captured but not referenced in the verdict reasoning.

**Phase to address:** Scope A closeout decision report phase. Cross-cutting reminder in phase CONTEXT templates.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse Phase 198 3-run pattern as-is for matrix replicates | Familiar script, fast to deploy | n=3 clustered in time is functionally n=1; matrix is unfalsifiable | Never in v1.47 — replicates must be time-separated |
| Hardcode supplemental Vultr targets into matrix wrapper | Fast to script | Bakes confirmation bias into the harness | Never — targets must include a control cell and an anchor |
| Compute ingestion rate via live `SELECT COUNT(*)` on hot path | Simple, accurate | Self-perturbation; eats Phase 217 cycle budget | Never on hot path; acceptable in CLI tool out-of-band |
| Expose single global `ingestion_rate` number | Easy operator UX | Hides per-WAN × per-table dimension Phase 218 needs | Acceptable as `--summary` flag, never as default |
| Ship snapshot without `_snapshot_age_sec` field | Less schema bookkeeping | Stale snapshots mask incidents; Phase 218 audits wrong window | Never — match the v1.38 measurement-staleness pattern |
| Update `docs/CONFIGURATION.md` mid-milestone with "future tuning" language | Captures fresh thinking | Pre-commits to tuning the evidence hasn't earned | Never in v1.47 (evidence-first read-only) |
| Skip per-replicate path snapshots to save time | Faster runs | Cannot diagnose BGP/anycast confounders post-hoc | Never — cheap to capture, essential to interpret |
| Aggregate cells across hostname → IP rotations | Larger n per cell | Mixes measurements of different physical targets | Never — pin IP per replicate window |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Vultr Dallas/Chicago public reflectors | Assume hostname → stable host | Resolve once per replicate, pin IP, log IP, capture mtr snapshot |
| LibreQoS CLI endpoint | Treat its bufferbloat grade as ground truth | Use it as corroborating evidence only; do not derive verdicts from it solely |
| flent | Trust `.flent.gz` produced even with netperf warnings | Phase 214 showed off-peak Dallas wrote a flent with repeated netperf no-data warnings; flag and exclude from cell aggregation |
| SQLite `metrics.db` | Add a new ingestion tracker table | Compute deltas from existing rowcounts; no new write paths in the daemon |
| RouterOS REST | Touch it from a "read-only" phase | v1.47 must not issue any RouterOS writes; matrix wrapper must not call into router-mutation paths |
| systemd journal | Assume regex strings stable across versions | Phase 214 verified regex strings against v1.45.0 source; verify against current deployed source again before relying on them in classifier |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| New in-cycle SQLite query for ingestion rate | `cycle_total.avg_ms` rising above Phase 217 baseline 2.883ms | Move computation off hot path; snapshot from existing per-cycle telemetry | Immediately on deploy; visible in JSON Cycle samples |
| Ingestion-rate snapshot cadence too slow | Phase 218 audit windows show "no incident" during real incidents | Cadence ≤ operator decision interval; expose staleness | When operator/Phase 218 queries within snapshot interval of a real event |
| Matrix wrapper writes to production SQLite | metrics.db gets observation rows mixed with control rows | Matrix wrapper writes only to phase-local `evidence/` paths | Immediately — corrupts metrics.db semantics |
| Storing per-replicate raw flent .gz indefinitely | Disk pressure over months of matrix runs | Phase-local retention; cite `RUN-<UTC>/` paths in report; archive on milestone close | At ~50 runs × 30 MB each = 1.5 GB per matrix |
| `wanctl-history --ingestion-rate` queries full table for time-windowed views | CLI slow on production-sized DB | Use indexed time columns; bound query scope by `--since` | When `metrics.db` exceeds ~1 GB |

---

## Read-Only Discipline Mistakes

Domain-specific to v1.47's read-only mandate.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Adding behavioral assertion via test fixture | Sneaks controller-spec change past `src/wanctl/` mutation boundary | Phase CONTEXT labels every artifact as `evidence` or `tool`; PR review enforces |
| YAML edit "just to add an ingestion-rate config knob" | Production YAML edit equals mutation of operator-facing surface | Scope D's CLI must read from existing YAML or use defaults; no new keys in production configs |
| Pre-deciding v1.48 tuning in `docs/` | Documentation commits position the evidence didn't earn | Doc-mutation guard; closeout report under `.planning/` only |
| Running flent matrix on production routing path | Could induce real congestion incidents during prime-time captures | Use existing test windows; document the test load on production at run time; do not synthesize artificial load |
| Quietly extending `/health` payload shape | Breaks the v1.46 "do not break payload shape casually" contract | Any new `/health` field needs the same review as a v1.39+ schema change |
| Allowing `git checkout configs/spectrum.yaml` style rollback to be used | Loses targeted-rollback discipline (Phase 215 lesson) | Any v1.47 mutation that lands must roll back via targeted YAML edit, never branch reset |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Matrix design:** Often missing pre-registered kill/defect criteria — verify §Kill Criteria and §Defect Criteria blocks exist in CONTEXT before any live run.
- [ ] **Matrix design:** Often missing a control cell (canonical Phase 214 reflector) — verify cell list includes the off-peak `pass` baseline target.
- [ ] **Matrix design:** Often missing an anchor target (known-stable like `1.1.1.1`) — verify cell list includes a low-noise anchor.
- [ ] **Matrix execution:** Often missing per-replicate IP-pinning and mtr snapshots — verify operator runbook captures both.
- [ ] **Matrix execution:** Often missing time-separation of replicates — verify replicates of any cell are ≥ 30 minutes apart.
- [ ] **Ingestion-rate tool:** Often missing `_snapshot_age_sec` field — verify staleness exposed in every output mode.
- [ ] **Ingestion-rate tool:** Often missing per-WAN × per-table breakdown — verify default output is not the global single number.
- [ ] **Ingestion-rate tool:** Often missing Phase 217-style profiling capture after deploy — verify `cycle_total.avg_ms` ≤ 3.0 and `p99_ms` ≤ 7.5 on production.
- [ ] **Closeout decision report:** Often missing explicit verdict statement — verify verdict is one of "defect located" / "hypothesis killed" / "carried-narrower with close-with-prejudice rule."
- [ ] **Closeout decision report:** Often missing per-cell verdict table — verify aggregate verdict derived from cell verdicts via pre-registered rule.
- [ ] **Closeout decision report:** Often missing folded-todo decision — verify `2026-04-08-investigate-tcp-12down-...` todo is either closed or carried with a hard stopping rule for v1.48.
- [ ] **Mutation discipline:** Often missing fixture/test-level mutation check — verify mutation-boundary covers `tests/fixtures/phase22*/`, `configs/`, `deploy/systemd/`, `scripts/`, and `docs/` against allowlist.
- [ ] **Phase 218 coupling:** Often missing fallback when ingestion-rate tool ships after Phase 218 fires — verify REQUIREMENTS names the v1.44 Phase 208 `wanctl-history --ingestion-rate` fallback.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Confirmation-bias matrix shipped without control cell | MEDIUM | Run control cell separately; re-aggregate verdict; update closeout report with addendum citing the recovery scope |
| Carried-narrower for the second time without close-with-prejudice rule | MEDIUM | Write the close-with-prejudice rule retroactively into v1.47 closeout report's "carry-forward to v1.48" section; do not reopen the matrix |
| Self-perturbing ingestion-rate tool degrades cycle budget | HIGH | Roll back the in-controller portion immediately; ship CLI-only version; re-baseline with Phase 217-style capture |
| Single-cell defect declaration shipped | HIGH | Re-run the hot cell with n=5+ across days; if not reproducible, retract verdict in v1.48 closeout addendum; if reproducible, treat as v1.48 evidence opening |
| Test fixture encodes behavioral assertion that slipped past review | MEDIUM | Re-label fixture as `expected_evidence` not `expected_behavior`; remove any controller-spec implication from comments; flag in v1.47 retro |
| `docs/` pre-decided v1.48 tuning | LOW | Revert doc edits; route the prediction into v1.48 RESEARCH instead |
| Phase 218 fires before Scope D ships | LOW | Use v1.44 Phase 208 `wanctl-history --ingestion-rate` fallback; defer Scope D-style audit to v1.48 |
| Matrix wrapper accidentally wrote to production `metrics.db` | HIGH | Identify inserted rows by timestamp; quarantine; document contamination in closeout report; manually clean if rowcount semantics depend on it |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Confirmation bias on Vultr supplemental | Scope A matrix-design phase (CONTEXT) | CONTEXT contains §Kill Criteria, control cell, anchor target |
| 2. Carried-narrower forever | Scope A matrix-design + closeout decision report | Pre-registered kill/defect criteria; close-with-prejudice rule in closeout |
| 3. Sampling clustered in time | Scope A matrix-design + matrix-execution | Replicate spacing ≥ 30 min; n ≥ 3 per cell; per-replicate provenance |
| 4. Confounders ignored | Scope A matrix-execution (operator runbook) | Matrix wrapper pins IP, captures mtr per replicate; anchor cell present |
| 5. Self-perturbing ingestion observability | Scope D design + post-deploy verification | Phase 217-style cycle-budget capture after deploy; threshold gates |
| 6. Granularity hides bottleneck | Scope D design | Default output is per-WAN × per-table; JSON mode present; Phase 218 audit example exercised |
| 7. Stale snapshots | Scope D design | Every snapshot field paired with `_snapshot_age_sec`; CLI displays staleness |
| 8. Behavioral assertions in fixtures | Cross-cutting: every v1.47 phase CONTEXT | Mutation-boundary covers fixtures/configs/deploy/scripts/docs; PR review enforces labels |
| 9. Docs pre-decide tuning | Cross-cutting: every v1.47 phase | Doc-mutation guard with allowlist; verdicts only in `.planning/` |
| 10. Defect-found on single cell | Scope A closeout decision report | Per-cell verdict table; corroboration-axis requirement in §Defect Criteria |
| 11. Phase 218 coupling | Roadmap phase ordering | Scope D sequenced before matrix-execution; fallback documented in REQUIREMENTS |
| 12. `/health=healthy` treated as quality | Scope A closeout decision report | Verdict prose pairs flent + `/health` evidence; `aligned-window.json` referenced |

---

## Sources

- `.planning/PROJECT.md` — v1.46 close section, v1.47 milestone definition
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-REPORT.md` — canonical matrix verdict, supplemental Vultr evidence, signal disposition rationale
- `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/214-VALIDATION.md` — mutation-boundary pytest pattern, manual-only verification semantics
- `.planning/milestones/v1.46-phases/215-spectrum-upload-reclaim-canary/215-REPORT.md` — bounded VOID rollback pattern, targeted YAML edit discipline
- Phase 217 production cycle-budget baseline — `cycle_total.avg_ms=2.883`, `p99_ms=6.9` over 71,560 samples; `logging_metrics=8.26%` dominant category
- v1.46 close notes on `/health` vs user-experience distinction
- v1.44 Phase 208 — existing `wanctl-history --ingestion-rate` CLI surface (Scope D extension baseline)
- `/home/kevin/projects/wanctl/CLAUDE.md` — controller priorities (stability > safety > clarity > elegance); read-only architectural spine

---
*Pitfalls research for: wanctl v1.47 Measurement Evidence Closure*
*Researched: 2026-05-29*
