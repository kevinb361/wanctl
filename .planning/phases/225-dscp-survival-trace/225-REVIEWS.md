---
phase: 225
reviewers: [codex]
reviewed_at: 2026-06-03T19:07:05Z
plans_reviewed: [225-01-PLAN.md, 225-02-PLAN.md, 225-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 225 (DSCP Survival Trace)

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
