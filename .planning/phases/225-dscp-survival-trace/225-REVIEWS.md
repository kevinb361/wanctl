---
phase: 225
reviewers: [codex]
reviewed_at: 2026-06-03T19:07:05Z
plans_reviewed: [225-01-PLAN.md, 225-02-PLAN.md, 225-03-PLAN.md]
cycles:
  - cycle: 1
    reviewed_at: 2026-06-03T19:07:05Z
    high_raised: 6
    high_unresolved: 6
  - cycle: 2
    reviewed_at: 2026-06-03T19:40:00Z
    base_commit: e280697
    prior_high_resolved: 3
    prior_high_partial: 3
    new_high_raised: 3
    high_unresolved: 3
  - cycle: 3
    reviewed_at: 2026-06-03T20:05:00Z
    base_commit: 84cd844
    prior_high_resolved: 2     # HIGH-A, HIGH-B fully resolved
    prior_high_partial: 1      # HIGH-C (capture-point proof not yet falsifiable)
    new_high_raised: 1         # DL EF probe lacks source-side DSCP proof
    high_unresolved: 2
---

# Cross-AI Plan Review — Phase 225 (DSCP Survival Trace)

This file accumulates review history across cycles. Cycle 1 (below) reviewed the original plans and
raised 6 HIGH concerns. Cycle 2 (appended at the bottom) reviewed the revised plans (commit
`e280697`) that claimed to resolve all 6.

---

# ============================ CYCLE 1 (original plans) ============================

Cross-AI reviewer: **Codex** (codex-cli 0.135.0, default model). Claude was skipped for
independence (review invoked from inside Claude Code). The reviewer's three highest-leverage
factual claims were independently verified against the repo by the orchestrator and are annotated
`[VERIFIED]` below.

## Codex Review

**Summary**

The plans are directionally solid and mostly respect the "no config mutation" boundary, but Codex
would not approve them as-is. The weak spots are evidence validity, not basic scripting: the
bridge-counter premise may be false because the checked-in nft rules do not include explicit
`counter` statements, the SAFE-13 check is weaker than the Phase 224 precedent, and the verdict
logic has enough ambiguity to permit a false early-exit or reverse-fitting.

### Plan 225-01 — Path trace map + bridge/CRS/Ruckus DSCP inventory

**Strengths**
- Uses only read commands on `cake-shaper`: `nft list`, `tc show`, `ip -d link show`.
- Correctly avoids qdisc filter probes and CAKE mode changes.
- Good artifact discipline: non-empty output refusal, manifest, sha256, required-artifact loop.
- Correctly anchors the bridge path to `iif spec-modem oif spec-router jump spectrum_dl`.

**Concerns**
- **HIGH — nft counters may not exist.** The plan assumes per-rule packet/byte counters exist, but
  the repo rules in `deploy/nftables/bridge-qos.nft` contain NO explicit `counter` statements.
  `nft list table bridge qos` may emit no counters for the `ip dscp set` rules. Absence of counters
  must NOT be read as "negligible." `[VERIFIED]` — grep of `bridge-qos.nft` confirms the `ip dscp set`
  rules at L47-49, L53-85, L99-122 have no `counter` keyword. This is the load-bearing evidence
  channel for both 225-01 and the DSCP-03 verdict; if it is empty, the cheap "negligible marking"
  early-exit path is unfounded.
- **HIGH — single snapshot is not "under representative load."** If counters exist, the script needs
  before/after deltas over a bounded window; absolute counters are stale cumulative state, not a
  load measurement.
- **MEDIUM — CRS/Ruckus evidence is narrative-only.** DSCP-01 asks for an evidence-backed trace
  across CRS trust maps and Ruckus QoS mirroring; a vague "RouterOS REST reference at 10.10.99.1"
  does not prove CRS/Ruckus state and may not even be the relevant device.
- **MEDIUM — `tc filter show ... ingress/root` can fail when the hook does not exist.** With
  `set -e`, the "as available" variants need explicit `|| true` plus artifact text noting
  unavailability, or the script aborts.
- **LOW — mutation grep false-positive.** The acceptance mutation-grep can trip on forbidden verbs
  appearing inside comments (e.g. a comment containing `nft delete`).

**Suggestions**
- Add `COUNTERS_AVAILABLE=true|false` and `COUNTER_MODE=delta|snapshot|unavailable` to
  `bridge-mark-counters.txt`.
- Capture `nft list table bridge qos` before and after a timed window; compute deltas only if
  counters are present.
- If counters are absent, the verdict input should be `bridge_counter_signal=unknown`, NOT
  `negligible`.
- Replace generic CRS/Ruckus narrative with cited read-only artifacts, or explicitly label those
  stages "documented assumption, not live-verified."

**Risk: MEDIUM-HIGH** — read-only posture is good, but the main evidence channel may not exist
without forbidden nft mutation, which can directly corrupt DSCP-03.

### Plan 225-02 — CAKE-ingress DSCP distribution (representative + EF probe)

**Strengths**
- Correctly rejects `tc filter` probes and uses bounded packet capture.
- Correctly states production `besteffort` CAKE tin counters cannot answer DSCP survival.
- Includes both organic distribution and a deliberately marked EF probe.
- Treats probe degradation as evidence instead of silently dropping the check.

**Concerns**
- **HIGH — observation point not proven to be CAKE enqueue vs post-wash transmit.** Production
  Spectrum has `diffserv: besteffort` and `allow_wash: true`. If `tcpdump` on the egress interface
  sees the DSCP byte AFTER CAKE wash, EF can look stripped even though it reached CAKE intact —
  a false negative. `[VERIFIED]` — `configs/spectrum.yaml:44-45` confirms `diffserv: besteffort`
  and `allow_wash: true`, so wash is live and the capture-point ordering relative to wash is a real
  ambiguity.
- **HIGH — default `--probe ul` from cake-shaper bypasses the path under test.** A UL probe sourced
  on cake-shaper proves a local upload mark reaches `spec-modem`, but does NOT exercise the
  CRS/Ruckus/LAN endpoint preservation or the DL bridge classification path that the milestone is
  actually re-evaluating.
- **HIGH — "representative traffic" is not enforced.** A quiet 90s window can produce negligible
  histograms and a false negative that closes the milestone.
- **MEDIUM — probe endpoint unspecified.** `iperf3` needs a server, `nping` needs a target; the
  plan must not default to sending traffic to an implicit/arbitrary host.
- **MEDIUM — "grep histogram for DSCP 46" is too weak.** Background EF or one stray packet marks
  false success; no captured probe packets marks false failure. Survival should be decided on the
  probe 5-tuple by count/percentage.
- **MEDIUM — DSCP extractor underspecified.** "TOS byte >> 2" must handle Ethernet offsets, VLAN
  tags, IPv6 traffic class, and cooked captures.
- **LOW — `timeout tcpdump -c <cap>` exits 124** when duration expires before packet cap; with
  `set -e` the script may abort unless handled.

**Suggestions**
- Require `--probe-target`; record target, ports, protocol, packet count, duration.
- Generate a probe-only pcap filtered by 5-tuple; decide EF survival by count/percentage, not
  unfiltered histogram presence.
- Add minimum-sample gates (total IP packets + active seconds must exceed thresholds or the
  representative capture is invalid).
- Validate/record capture ordering relative to CAKE/wash, or state the limitation and prevent
  early-exit on an ambiguous capture point.
- Split verdict evidence by direction: DL survival, UL survival, organic DL marking, organic UL
  marking.

**Risk: HIGH** — this plan can produce clean-looking but misleading data: false negative from
post-wash capture, false positive from a local UL probe that bypasses the topology under test.

### Plan 225-03 — Gated DSCP-03 verdict + SAFE-13 boundary record

**Strengths**
- Correctly fails closed if SAFE-13 fails.
- Uses the correct committed controller-path names.
- Requires a single machine-readable `VERDICT:` line and explicit downstream consequence.
- Correctly cites the pre-registration requirement.

**Concerns**
- **HIGH — SAFE-13 boundary check is weaker than the SAFE-12 precedent it claims to mirror.**
  `git diff --name-only v1.48 HEAD -- ...` misses unstaged edits, staged edits, and untracked files
  under protected paths. `[VERIFIED]` — the v1.48 `safe12-boundary-check.json` recorded
  `per_path_diff` with per-file added/removed line counts plus `baseline_commit`/`head_commit`, a
  strictly stronger artifact than this plan's name-only diff count.
- **HIGH — pre-registered logic is internally inconsistent.** `225-RESEARCH.md:114` says
  MARKS_DO_NOT_SURVIVE fires "if ANY:" but then joins its two bullets with "AND". `[VERIFIED]` —
  the file literally reads "if ANY:" over two AND-joined bullets. This ANY/ALL contradiction must
  be resolved BEFORE evidence collection, or the negative branch is ambiguous and reverse-fittable.
- **HIGH — "meaningful" and "negligible" are unquantified**, leaving room for reverse-fitting the
  verdict to the desired branch.
- **HIGH — no safe branch for unavailable bridge counters.** If counters don't exist (see 225-01
  HIGH), the decision logic has no defined mapping; "unknown" must map to MARKS_SURVIVE_QUALIFIED,
  not silently to MARKS_DO_NOT_SURVIVE.
- **MEDIUM — `EF_SURVIVED=true|false|degraded` is too coarse** without packet counts and direction.
  A degraded DL probe plus a true UL probe should not auto-unblock a DL diffserv A/B.
- **LOW — path naming ambiguity** (`evidence/...` vs full `.planning/phases/225.../evidence/...`).
  Standardize the full path.

**Suggestions**
- SAFE-13 script should run all three channels: `git diff`, `git diff --staged`, and
  `git status --porcelain -- <paths>`, plus per-file sha equality against `v1.48`.
- Add `protected_paths` and `dirty_tree_clean` to the JSON.
- Resolve ANY vs ALL in the pre-registration before running live captures.
- Pre-register thresholds for `meaningful`, `negligible`, minimum sample size, EF survival
  percentage, and handling of unknown counters.
- Fire MARKS_DO_NOT_SURVIVE only when both required negative signals are valid, observed, and above
  sample-quality thresholds.

**Risk: HIGH** — the verdict gate is only as good as its evidence and boolean logic; as written it
can falsely close the milestone negative or falsely unblock Phase 226.

**Overall Risk Assessment: HIGH** — the change posture is conservative, but the evidence model is
not yet robust enough for a milestone gate. Top fixes: prove or downgrade the bridge counters,
strengthen SAFE-13 to include dirty/staged/untracked state, resolve the ANY/ALL contradiction, and
make the tcpdump/probe evidence direction-specific with sample-quality thresholds.

---

## Consensus Summary

Single external reviewer (Codex) this cycle; "consensus" reflects Codex findings cross-checked
against the repo by the orchestrator. The read-only posture and SAFE-13 *intent* are sound — the
problems are all in **evidence validity and verdict integrity**, which is exactly the part that
makes a milestone-closing gate trustworthy.

### Agreed Strengths
- Read-only posture is correctly designed: read-only nft/tc/ip commands, no qdisc filter probes, no
  CAKE-mode change, fail-closed SAFE-13.
- Good artifact hygiene (MANIFEST, sha256, non-empty-dir refusal, required-artifact assertion loop).
- Correctly recognizes that production `besteffort` (single tin) means per-tin CAKE counters cannot
  answer survival — the DSCP-byte-at-egress approach is the right instinct.
- The verdict requires a single machine-readable line, evidence citations, and a stated downstream
  consequence.

### Agreed Concerns (highest priority)
1. **Bridge counters may not exist (HIGH, VERIFIED).** No `counter` statements on the `ip dscp set`
   rules in `bridge-qos.nft`. The cheap "negligible marking → early exit" path is unfounded unless
   counters are present; absence must map to `unknown`, never `negligible`.
2. **tcpdump capture point ambiguity vs CAKE wash (HIGH, VERIFIED).** `allow_wash: true` is live; an
   egress capture taken after wash can falsely show EF as stripped — a false negative that closes
   the milestone.
3. **SAFE-13 check weaker than the SAFE-12 precedent (HIGH, VERIFIED).** `--name-only` misses
   staged/unstaged/untracked; the v1.48 artifact recorded per-file line-diff + commit anchors. Needs
   `git diff`, `git diff --staged`, `git status --porcelain`, per-file sha equality, and
   `dirty_tree_clean` in the JSON.
4. **Pre-registered decision logic is self-contradictory (HIGH, VERIFIED).** 225-RESEARCH.md says
   "if ANY" over AND-joined bullets. Must be resolved before any capture, or the negative branch is
   ambiguous and reverse-fittable.
5. **"Meaningful"/"negligible" unquantified + no representative-load floor (HIGH).** Without
   pre-registered numeric thresholds and minimum-sample gates, a quiet window or a vague counter read
   can drive an unjustified MARKS_DO_NOT_SURVIVE.
6. **Default UL probe from cake-shaper bypasses the DL CRS/Ruckus/bridge path under test (HIGH).**
   It can prove a local mark reaches spec-modem without exercising what the milestone re-evaluates;
   verdict evidence must be split by direction.

### Divergent Views
None — single reviewer. No internal contradictions in the Codex review.

### Recommended Next Step
Feed back into planning:
```
/gsd:plan-phase 225 --reviews
```
Priority before any live capture: (a) probe whether `nft list table bridge qos` actually emits
counters and define the `unknown` branch; (b) resolve the ANY/ALL contradiction in 225-RESEARCH.md;
(c) pre-register numeric thresholds for meaningful/negligible/sample-size/EF-percentage; (d)
strengthen the SAFE-13 script to the SAFE-12 standard; (e) pin the tcpdump capture point relative to
CAKE wash and make probe/verdict evidence direction-specific.

---

# ============================ CYCLE 2 (revised plans, commit e280697) ============================

Cross-AI reviewer: **Codex** (codex-cli, default model). Claude skipped for independence (review
invoked from inside Claude Code). Codex verified against `HEAD=e280697`. The orchestrator
independently re-verified each of Codex's three NEW HIGH claims against the actual file lines (all
confirmed; annotated `[VERIFIED]` below). The revised plans + research claimed to resolve all 6
cycle-1 HIGHs.

## Disposition of the 6 cycle-1 HIGH concerns

| # | Cycle-1 HIGH | Cycle-2 disposition | Evidence |
|---|--------------|---------------------|----------|
| 1 | nft counter absence read as "negligible" | **RESOLVED** | Absence → `bridge_counter_signal=unknown`, never `negligible` (225-RESEARCH.md:123, 225-01-PLAN.md:67-73). |
| 2 | tcpdump capture point vs CAKE wash | **PARTIALLY RESOLVED** | Pre-wash intent + `WASH_ORDERING_PROVEN` flag added, but method still leans on `tcpdump -Q in` with no real proof standard (225-02-PLAN.md:75-83). See NEW HIGH-C. |
| 3 | SAFE-13 weaker than SAFE-12 precedent | **RESOLVED** | Committed + staged + dirty/untracked + per-file sha + ATT + fail-closed, matching v1.48 shape (225-03-PLAN.md:59-81). |
| 4 | ANY-vs-AND decision-logic contradiction | **PARTIALLY RESOLVED** | The original ANY/AND contradiction is gone, but a NEW internal contradiction appeared around whether `bridge_counter_signal=unknown` blocks the negative branch. See NEW HIGH-A. |
| 5 | "meaningful"/"negligible" unquantified + no load floor | **PARTIALLY RESOLVED** | Packet thresholds (<1% / ≥5% / ≥90% / <10%) + sample floor (≥2000 pkts / ≥30 active s / ≥100 probe pkts) pre-registered, but the research's non-BestEffort **byte-fraction** half of NEGLIGIBLE is not carried into the 225-02/225-03 acceptance criteria (225-RESEARCH.md:146 vs 225-03-PLAN.md:133). See NEW MEDIUM. |
| 6 | UL probe bypasses DL path under test | **RESOLVED** | Four direction-split channels; UL-only positive can neither close negative nor unblock the DL A/B (225-02-PLAN.md:49, 225-03-PLAN.md:141). |

Net: **3 fully RESOLVED, 3 PARTIALLY RESOLVED.** No cycle-1 HIGH regressed to fully unresolved, but
the partial-resolutions surfaced **3 NEW HIGH** concerns this cycle.

## Codex Review (cycle 2)

**New / remaining HIGH concerns**

- **HIGH-A — DSCP-03 is not deterministic when bridge counters are absent (internal contradiction).**
  `[VERIFIED]` 225-RESEARCH.md:188-190 (MARKS_DO_NOT_SURVIVE branch) says if `bridge_counter_signal=unknown`
  "it does not block this branch (the histogram is the source of truth)" — i.e. a negative close can
  fire with counters absent. But 225-RESEARCH.md:202-205 + 212-213 (QUALIFIED branch) say counters
  absent / `unknown` maps to QUALIFIED and "`unknown` ALWAYS maps here, never to MARKS_DO_NOT_SURVIVE."
  These two statements are mutually exclusive for the counters-absent case (the verified production
  case — the nft rules have no `counter` clause). The verdict function is non-deterministic exactly in
  the situation that will actually occur. Must pick one rule before any capture.

- **HIGH-B — `MARKS_SURVIVE_QUALIFIED` has no defined relationship to the roadmap's Phase 226 gate.**
  `[VERIFIED]` ROADMAP.md:44 gates Phase 226 on a "marks survive" verdict from Phase 225. RESEARCH.md:210-211
  says QUALIFIED means "proceed with caveat" and defers the unblock decision to "Phase 226's GATE-01
  tie-breaker." QUALIFIED is neither MARKS_SURVIVE nor MARKS_DO_NOT_SURVIVE, yet the research lets it
  advance toward the mutable A/B (Phase 226 builds Snapshot A + locks thresholds before any candidate
  deploy). Either QUALIFIED blocks Phase 226 (matching the roadmap gate) or the roadmap gate must be
  rewritten to admit a third "proceed-with-caveat" state — as written, the catch-all default can leak
  an ambiguous verdict into the phase that begins touching production config.

- **HIGH-C — pre-wash capture proof is underspecified and likely directionally wrong for DL.**
  `[VERIFIED]` 225-02-PLAN.md:76 captures the DL histogram on `spec-router` with `tcpdump ... -Q in`.
  DL packets bound for the LAN *egress* `spec-router`; `-Q in` captures host-inbound traffic, so it is
  not self-evidently the "DSCP byte as it arrives at the CAKE enqueue point" on the DL path. The plan
  treats setting `CAPTURE_POINT=pre_wash_ingress` as a flag the operator asserts rather than a proven
  property; without a concrete proof artifact (e.g. demonstrating the capture hook sits before the
  `spec-router` CAKE egress qdisc and before wash), the load-bearing DL survival channel rests on an
  unverified directional assumption. The plan's own fallback (`CAPTURE_POINT=unknown` → channel
  `unknown`) is the safety net, but combined with HIGH-A/HIGH-B an `unknown` DL channel has an
  ill-defined verdict consequence.

**Remaining MEDIUM**

- **MEDIUM — NEGLIGIBLE byte-fraction threshold not enforced in the plans.** 225-RESEARCH.md:146-148
  defines NEGLIGIBLE as non-BestEffort packets <1% **AND** non-BestEffort bytes <1% (where measurable),
  but 225-02 (`sample-quality.txt`, histograms) and 225-03 (verdict acceptance) only require packet
  fractions. The byte-fraction half of the pre-registered negative criterion is not carried into the
  implementing acceptance criteria — a partial implementation of the pre-registered logic.

**Overall risk: HIGH (as a milestone-gating plan).** Mutation risk remains LOW — read-only posture,
SAFE-13 hardening, and direction-split are genuinely solid. But the **verdict integrity** is not yet
trustworthy: the counters-absent path is internally contradictory (HIGH-A), the QUALIFIED default has
no defined gate relationship (HIGH-B), and the DL pre-wash capture rests on an unproven directional
assumption (HIGH-C). All three are evidence/verdict-logic issues, not scripting issues, and all three
are exactly the kind of ambiguity that lets a milestone gate close wrong or leak an ambiguous verdict
downstream.

## Consensus Summary (cycle 2)

Single external reviewer (Codex); orchestrator independently re-verified all three NEW HIGH claims
against the file lines (`[VERIFIED]`). The revised plans made real progress — the read-only posture,
SAFE-13 boundary check, counter-absence handling, and direction split are now sound — but the verdict
decision function still has internal and cross-document contradictions that must be resolved before
any capture runs.

### Agreed Strengths (carried + new)
- Counter absence correctly maps to `unknown`, never `negligible` (cycle-1 HIGH-1 closed).
- SAFE-13 now matches the v1.48 SAFE-12 standard: committed/staged/dirty/untracked + per-file sha +
  ATT + fail-closed (cycle-1 HIGH-3 closed).
- Evidence is direction-split; UL-only cannot close negative or unblock the DL A/B (cycle-1 HIGH-6 closed).
- Numeric packet thresholds + representative-load sample floor pre-registered (cycle-1 HIGH-5 mostly closed).

### Agreed Concerns (highest priority — must fix before capture)
1. **DSCP-03 counters-absent contradiction (NEW HIGH-A, VERIFIED).** RESEARCH.md:188-190 vs 202-213 give
   opposite rules for `bridge_counter_signal=unknown`. Pick one.
2. **QUALIFIED ↔ roadmap-gate mismatch (NEW HIGH-B, VERIFIED).** QUALIFIED "proceed with caveat" vs
   ROADMAP.md:44 "marks survive" gate for Phase 226. Define whether QUALIFIED blocks Phase 226.
3. **DL pre-wash capture proof underspecified (NEW HIGH-C, VERIFIED).** `-Q in` on `spec-router` is
   not self-evidently pre-CAKE/pre-wash on the DL egress path; require a concrete proof artifact.
4. **Byte-fraction NEGLIGIBLE threshold not implemented (MEDIUM, VERIFIED).** Pre-registered in
   RESEARCH.md:146 but absent from 225-02/225-03 acceptance.

### Divergent Views
None — single reviewer. No internal contradictions in the Codex cycle-2 review.

### Recommended Next Step
Feed back into planning:
```
/gsd:plan-phase 225 --reviews
```
Resolve HIGH-A (counters-absent determinism), HIGH-B (QUALIFIED gate relationship to the roadmap),
and HIGH-C (DL pre-wash capture proof) — then add the byte-fraction threshold (MEDIUM) — before any
live capture. These are verdict-logic/evidence-integrity fixes, not scripting changes.

---

# ============================ CYCLE 3 (twice-revised plans, commit 84cd844) ============================

Cross-AI reviewer: **Codex** (codex-cli 0.135.0, default model). Claude skipped for independence
(review invoked from inside Claude Code). Codex verified against `HEAD=84cd844`. The orchestrator
independently re-verified each disposition and both remaining HIGH claims against the actual file
lines (all confirmed; annotated `[VERIFIED]`). The cycle-2 replan claimed to resolve all 3 cycle-2
HIGHs (HIGH-A/B/C) plus the byte-fraction MEDIUM.

## Disposition of the 3 cycle-2 HIGH concerns + MEDIUM

| Item | Cycle-2 concern | Cycle-3 disposition | Evidence |
|------|-----------------|---------------------|----------|
| HIGH-A | Counters-absent non-determinism (RESEARCH:188-190 vs 202-213 contradiction) | **RESOLVED** | `bridge_counter_signal` is now corroborating-only / non-gating; only `organic_dl_histogram` + `dl_ef_probe` gate; absent counter (verified production case — nft rules carry no `counter` clause) neither blocks nor forces any branch. 225-RESEARCH.md:123,138,223; 225-03-PLAN.md:150. The prior contradiction is gone. |
| HIGH-B | QUALIFIED had no defined relationship to the ROADMAP Phase 226 "marks survive" gate | **RESOLVED** | `MARKS_SURVIVE_QUALIFIED` is now an explicit HOLD state that BLOCKS Phase 226 by default; only `MARKS_SURVIVE` satisfies ROADMAP.md:44,65; proceed-with-caveat requires an explicit recorded operator override never taken automatically. 225-RESEARCH.md:265,271,275; 225-03-PLAN.md:60,181. Internally consistent and matches the roadmap gate. |
| HIGH-C | DL pre-wash capture proof underspecified / directionally wrong | **PARTIALLY RESOLVED** | `-Q in` correctly rejected; default `CAPTURE_POINT=unknown`; unproven point → `unknown` channel that cannot drive a negative verdict (fail-safe). BUT the prescribed "correct" DL point ("inbound on the spec-router bridge member facing spec-modem", 225-RESEARCH.md:197 / 225-02-PLAN.md:83) is still asserted prose and remains directionally suspect for `iif spec-modem oif spec-router` (DL egresses spec-router); `capture-point-proof.txt` cites topology text but does NOT require a *falsifiable* check proving the hook fires before the CAKE-egress wash qdisc. Still a HIGH because the load-bearing DL gating channel rests on an unfalsifiable directional claim. |
| MEDIUM | NEGLIGIBLE byte-fraction not carried into 225-02/225-03 acceptance | **RESOLVED** | `NONBE_BYTE_PCT` now emitted alongside `NONBE_PKT_PCT` and applied to the full NEGLIGIBLE criterion. 225-02-PLAN.md:20,105; 225-03-PLAN.md:53,162. |

Net: **2 of 3 cycle-2 HIGHs FULLY RESOLVED (HIGH-A, HIGH-B); 1 PARTIALLY RESOLVED (HIGH-C); MEDIUM
RESOLVED.** One NEW HIGH surfaced this cycle.

## Codex Review (cycle 3)

**Remaining / new HIGH concerns**

- **HIGH-C (carried, PARTIALLY RESOLVED) — DL pre-wash capture point is asserted, not falsifiably
  proven.** `[VERIFIED]` 225-RESEARCH.md:197 + 225-02-PLAN.md:83 prescribe the DL observation point as
  "inbound on the spec-router bridge member facing spec-modem." For the stated bridge path
  `iif spec-modem oif spec-router`, DL is forwarded *out* spec-router, so "inbound on spec-router" is
  still directionally suspect. `capture-point-proof.txt` is required to cite topology text but no
  falsifiable check (e.g. observing the byte both pre-wash-marked and post-wash-stripped, or proving
  the capture hook fires before the egress CAKE qdisc) is mandated. The `unknown`-default fail-safe
  prevents a wrong negative close, so this is not a *new* contradiction — but the load-bearing DL
  gating channel's pre-wash claim cannot yet be falsified.

- **HIGH (NEW) — DL EF probe can be counted `STRIPPED` without proving the DL packets were EF before
  the shaper.** `[VERIFIED]` 225-RESEARCH.md:89 describes the DL probe as a LAN-client `--tos 0xb8`
  flow "toward an external endpoint (DL return path)." A client's TOS marking marks its *outbound*
  (UL) packets; it does not establish that the *return-path DL* packets carry EF. 225-02-PLAN.md:125-127
  records `PROBE_PKTS_SENT`, `PROBE_PKTS_CAPTURED`, `EF_PKTS_AT_ENQUEUE`, `EF_SURVIVAL_PCT`,
  `EF_SURVIVED` — but NO `EF_PKTS_AT_SOURCE` / source-side DL DSCP proof for the DL 5-tuple. The sample
  gate (225-02-PLAN.md:19) counts source-side *packets* but does not assert they were DSCP-46 on the DL
  leg. This leaves a false-negative path: DL packets that were never EF can be counted `STRIPPED`, and
  combined with a NEGLIGIBLE organic histogram that is exactly the logical-AND that fires
  `MARKS_DO_NOT_SURVIVE` and closes the milestone negative. The same gating channel that HIGH-C touches
  thus has a second, independent integrity gap on the source side.

**Remaining MEDIUM**

- **MEDIUM — stale counter prose contradicts the non-gating taxonomy.** `[VERIFIED]` 225-RESEARCH.md:76
  still calls the bridge counters "the single most valuable read-only signal" and says near-zero
  counters mean "theater confirmed cheaply." The verdict logic now correctly makes counters non-gating,
  so this is NOT a residual HIGH-A — but the stale paragraph should be removed/rewritten to avoid
  implementer confusion.
- **MEDIUM — SAFE-13 per-file hash for `src/wanctl/backends/` (a directory) underspecified.**
  `[VERIFIED]` 225-03-PLAN.md:81 lists a directory in the protected set; 225-03-PLAN.md:89 then specifies
  per-file `<anchor>:<file>` / worktree hash comparison. The script must explicitly expand tracked files
  under `backends/`, or implementation may hash a tree / fail closed / miss the intended per-file proof.

**Overall risk: HIGH (as a milestone-gating plan).** Mutation risk remains LOW — read-only posture,
SAFE-13 hardening, gating/corroborating taxonomy, and the QUALIFIED hold-state are genuinely solid and
cycle-2's HIGH-A and HIGH-B are closed. But **verdict integrity** is still not fully trustworthy: both
DL gating channels (`organic_dl_histogram` via capture-point proof, and `dl_ef_probe` via source-side
DSCP proof) rest on claims that are not yet falsifiable, and both feed the negative-close AND.

**Convergence verdict: NOT CONVERGED (2 HIGH remain).**

## Consensus Summary (cycle 3)

Single external reviewer (Codex); orchestrator independently re-verified the dispositions and both
remaining HIGH claims against the file lines (`[VERIFIED]`). Cycle-2's two verdict-architecture HIGHs
are genuinely closed: the gating/corroborating taxonomy makes the counters-absent case deterministic
(HIGH-A), and QUALIFIED is now a hold-state that blocks Phase 226 by default (HIGH-B). The byte-fraction
MEDIUM is resolved. What remains is narrower and concentrated entirely on the two **DL gating channels**
that drive the negative close.

### Agreed Strengths (carried + new this cycle)
- HIGH-A closed: bridge counters corroborating-only; counters-absent (verified production case) is
  deterministic and benign.
- HIGH-B closed: QUALIFIED blocks Phase 226 by default; only MARKS_SURVIVE unblocks; operator override
  is explicit and never automatic.
- Byte-fraction NEGLIGIBLE criterion now fully wired into 225-02/225-03.
- Read-only posture and SAFE-13 at the full SAFE-12 standard remain sound.

### Agreed Concerns (highest priority — must fix before capture)
1. **DL EF probe source-side DSCP proof missing (NEW HIGH, VERIFIED).** Add `EF_PKTS_AT_SOURCE` /
   source-side DL DSCP verification so a never-EF DL packet cannot be counted `STRIPPED` and feed a
   negative close. A DL EF probe whose source-side DL marking is unproven must be `unknown`/`degraded`,
   not a clean negative.
2. **DL capture-point proof not falsifiable (HIGH-C carried, VERIFIED).** Require a concrete falsifiable
   check that the capture hook sits before the CAKE-egress wash qdisc (not just cited topology text),
   or keep the channel `unknown` (which the fail-safe already does).
3. **Stale counter prose (MEDIUM) + SAFE-13 `backends/` per-file expansion (MEDIUM).** Cleanups, not
   gating issues.

### Divergent Views
None — single reviewer. No internal contradictions in the Codex cycle-3 review.

### Recommended Next Step
Feed back into planning:
```
/gsd:plan-phase 225 --reviews
```
Both remaining HIGHs are evidence-integrity gaps on the two DL gating channels (capture-point proof +
DL EF source-side proof), not scripting or architecture issues. Resolve both — and the two MEDIUM
cleanups — before any live capture, since both feed the milestone-closing negative-close AND.
