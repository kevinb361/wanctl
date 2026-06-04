---
phase: 227
reviewers: [codex]
reviewed_at: 2026-06-04T13:35:33Z
plans_reviewed: [227-01-PLAN.md, 227-02-PLAN.md, 227-03-PLAN.md, 227-04-PLAN.md]
external_cli: codex-cli 0.135.0
---

# Cross-AI Plan Review — Phase 227

Phase 227 deploys candidate `diffserv4 wash` on Spectrum under the Snapshot A anchor and
captures a matched 226-vs-227 dataset (incl. a marked-EF realtime-protection arm) for the
Phase 228 verdict. Reviewed by Codex CLI as the external reviewer; this Claude Code session
verified the load-bearing HIGH claims against repository source before recording them (notes
inline under "Claude verification").

## Codex Review

## PLAN 227-01 — Marked-EF Arm

**Summary**
Good intent, but the plan underestimates how much an "additive" parallel iperf3 flow can perturb the matched-load contract. The existing harness already runs RRUL, unmarked UDP, and unmarked TCP concurrently against the same `REF_HOST:REF_PORT`; adding another UDP flow there risks server contention, port collision, invalid iperf artifacts, and non-apples-to-apples load.

**Strengths**
- Default-off `--marked-ef` preserves normal Phase 226 behavior.
- Mandatory degrade-to-best-effort record is the right failure posture.
- Reusing the existing harness avoids a forked capture path.

**Concerns**
- **HIGH:** Same `REF_HOST:REF_PORT` for unmarked UDP, TCP, and marked EF can collide on iperf3. Nonempty artifact checks will not prove the flow succeeded; iperf3 error text is also nonempty.
- **HIGH:** Adding EF traffic changes runtime load even if command lines are unchanged. The plan must define which dataset feeds GATE-01 versus AB-04.
- **MEDIUM:** `EF_CLEAN_MARK=true` is not meaningful unless verified by packet capture or CAKE tin/counter evidence, not just iperf accepting `--dscp` or `--tos`.
- **MEDIUM:** Current `phase226-baseline-summary.py` does not appear to parse unmarked UDP jitter/loss or TCP throughput today, so "marked EF vs unmarked UDP" is not actually available yet.

**Suggestions**
- Add real iperf JSON validation: fail or mark invalid if JSON has `error`, lacks `end.sum`, or lacks jitter/loss/throughput fields.
- Use separate iperf server ports or explicitly prove the reference server accepts concurrent tests.
- Record EF cleanliness from observed DSCP/tin evidence, not CLI success.
- Explicitly label EF-loaded captures as AB-04 inputs; avoid silently using them as the no-EF GATE-01 baseline unless that is intentional.

**Risk Assessment:** **MEDIUM-HIGH**. No production mutation, but high risk of producing misleading evidence.

> **Claude verification:** Confirmed — `phase226-baseline-summary.py` references unmarked UDP/TCP only in a provenance string; it does not parse jitter/loss/throughput today (the "marked EF vs unmarked UDP" comparison and several GATE-01 signals must be built, not just surfaced). The concurrency-contention concern is plausible but unverified against the live reference host; D-03's "byte-for-byte identical matched arms" goal is in tension with adding a third concurrent flow to the same `REF_HOST:REF_PORT`.

---

## PLAN 227-02 — Qdisc Verify Gate

**Summary**
The read-only gate is necessary and well scoped, but it needs fail-closed parsing and timeout behavior nailed down. This gate is the provenance lock for the whole candidate capture.

**Strengths**
- Checks both `spec-router` and `spec-modem`.
- Supports `besteffort` and `diffserv4`, which fits the D-07 sequence.
- SSH failure naturally fails closed if implemented carefully.

**Concerns**
- **HIGH:** CAKE mode parsing must tokenize only the `qdisc cake` line. Bare grep can false-pass on comments, stats, previous output, or unrelated text.
- **MEDIUM:** Missing NIC, no CAKE qdisc, sudo failure, or SSH hang must produce a clear mismatch/error, not an ambiguous shell exit.
- **MEDIUM:** Needs a bounded SSH/connect timeout so pre-capture gates do not hang during the off-peak window.
- **LOW:** Interface args should be constrained or safely quoted.

**Suggestions**
- Parse with Python or strict shell tokenization: find exactly one `qdisc cake` line per iface, then require one allowed mode token.
- Return `got: missing|ssh_failed|no_cake|ambiguous` in JSON proof.
- Add fixtures for `besteffort`, `diffserv4`, `diffserv3`, missing qdisc, multiple cake lines, and SSH failure simulation.

**Risk Assessment:** **MEDIUM**. Read-only, but a false pass poisons the candidate dataset.

> **Claude verification:** The plan already mandates filtering to the `qdisc cake` line with a word-boundary match (interfaces note + T-227-04), so the HIGH here is a hardening reminder rather than a missed contract. The bounded-timeout and `got: missing|ssh_failed|no_cake|ambiguous` JSON suggestions are genuine gaps in the current plan text and worth folding in.

---

## PLAN 227-03 — Capture Sequence + Flip

**Summary**
This is the riskiest plan. The ordered sequence is right, and human checkpointing is appropriate, but the abort path is currently underspecified and appears to rely on `phase226-restore.sh`, which is dry-run proof only and explicitly does not restore runtime qdisc/config state.

**Strengths**
- Correct D-07 order: fresh besteffort+EF before flip, then candidate+EF.
- Keeps production mutation human-gated.
- Uses standard deploy path and qdisc verification.
- Leaves diffserv4 live per D-08 rather than doing hidden restore churn.

**Concerns**
- **HIGH:** `scripts/phase226-restore.sh` is dry-run only. It refuses mutation and says it does not restore runtime qdisc/service state. That is not an armed abort.
- **HIGH:** Health URL is inconsistent: the harness uses `http://10.10.110.223:9101/health`, while the plan references `127.0.0.1:9101`. From the operator host, localhost is likely wrong unless SSH-wrapped.
- **HIGH:** "daemon crashloop" and "/health RED" are not concretely defined. Need exact commands/fields.
- **MEDIUM:** Existing capture script always creates `baseline-<UTC>` under the output dir. The plan's `candidate-<UTC>` naming conflicts unless the runbook handles it deliberately.
- **MEDIUM:** Printing commands is safe, but the plan also lists `configs/spectrum.yaml` as modified. Be explicit about when the repo config is actually changed and recorded.

**Suggestions**
- Add a real Phase 227 abort procedure: restore Snapshot A config bytes, deploy/restart, verify `besteffort` on both NICs, verify health, record proof.
- Make health checks use the same endpoint as Phase 226, or SSH to cake-shaper before curling localhost.
- Add post-candidate guard: qdisc still `diffserv4`, health healthy, service active, no restart surge, capture validity retained.
- Record deployed config hash, qdisc-verify JSON, `systemctl is-active`, restart counters, and journal excerpt around the flip.

**Risk Assessment:** **HIGH**. This mutates the live WAN and the rollback path is not currently real enough.

> **Claude verification:** CONFIRMED against source. `scripts/phase226-restore.sh` hard-errors on any non-dry-run invocation (`"ERROR: Phase 226 restore proof is dry-run only; mutation-capable restore behavior is deferred to Phase 228."`) and its header states it "does not claim runtime qdisc restoration." D-09's armed abort therefore has no mutation-capable rollback to call — this is a genuine production-safety blocker for the Wave 2 checkpoint and must be resolved before the flip. The health-endpoint inconsistency is a real ambiguity (CONTEXT/plan say `127.0.0.1:9101`; the 226 harness uses a host:port) that needs a single defined source of truth.

---

## PLAN 227-04 — SAFE-13 + Evidence Completeness

**Summary**
The boundary closeout is necessary, but the plan can falsely certify readiness if it only checks top-level summary shape. The existing SAFE-13 script is strong, but its protected file list may not cover every controller-path module implied by the invariant.

**Strengths**
- Reuses an existing SAFE-13 script rather than inventing a new diff check.
- Correctly treats `configs/spectrum.yaml` as permitted drift and `configs/att.yaml` as protected.
- Separates readiness from Phase 228 verdict.

**Concerns**
- **HIGH:** `wan_controller_state.py` exists under `src/wanctl/` and is not protected by the current SAFE-13 script. If it is controller-path, SAFE-13 has a hole.
- **HIGH:** Current summary lacks some AB-04/GATE-01 signals unless 227-01 expands parsing substantially: unmarked UDP jitter/loss, TCP throughput/latency, and possibly UL p99.
- **MEDIUM:** Exact top-level shape matching is too weak; exact nested tin matching may be wrong because `besteffort` and `diffserv4` naturally expose different tin keys.
- **MEDIUM:** Completeness should validate artifact success and run count, not just field presence.

**Suggestions**
- Expand SAFE-13 protected paths or document why `wan_controller_state.py` is excluded.
- Make completeness check schema-aware: require stable top-level fields, allow mode-dependent tin names, but require BE/non-BE metrics needed for tin separation.
- Check `run_count == 3`, qdisc mode proof before/during/after, marked/unmarked iperf success, manifest validity, and summary fields.
- Fail with "not verdict-ready" rather than allowing Phase 228 to discover missing evidence.

**Risk Assessment:** **MEDIUM-HIGH**. No direct production mutation, but it could falsely close the phase.

> **Claude verification:** CONFIRMED against source. `src/wanctl/wan_controller_state.py` exists and is imported directly by `wan_controller.py` (`from wanctl.wan_controller_state import WANControllerState`) — it is controller-path state. The SAFE-13 boundary check (`phase225-safe13-boundary-check.sh`) protects `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `alert_engine.py`, `fusion_healer.py`, and `configs/att.yaml`, but NOT `wan_controller_state.py`, and `expand_protected_files()` only expands directory-suffixed targets — so a change there would pass the boundary check while altering controller behavior. This is a real SAFE-13 hole. The mode-dependent tin-keys concern (besteffort vs diffserv4 expose different tins) is a correct caution against an over-strict nested shape match.

---

## Overall Risk

**HIGH until fixed.** The phase design is directionally sound, but two issues are blockers for a production-critical WAN change: the armed abort path is not actually mutation-capable, and the additive EF arm can invalidate evidence unless iperf concurrency, marking proof, and summary parsing are tightened. Fix those before Wave 2.

---

## Consensus Summary

Single external reviewer (Codex) this cycle, cross-checked against repository source by the
executing Claude Code session. The review is grounded — three of the four most load-bearing
HIGH claims were independently verified against the actual code, not taken on faith.

### Agreed Strengths
- The phase architecture is directionally correct: verbatim 226 harness reuse + additive EF
  arm, a provenance-locking qdisc-verify gate, correct D-07 capture order, human-gated
  production flip, single deploy left live for the 228 verdict, and reuse of an existing
  SAFE-13 boundary check rather than a new diff path.

### Agreed Concerns (highest priority — verified)
- **D-09 armed abort is not real (227-03, HIGH, CONFIRMED).** `phase226-restore.sh` is
  dry-run only and explicitly does not restore runtime qdisc/service state. The only in-phase
  rollback for a live-WAN flip has no mutation-capable path. Must be fixed before the Wave 2
  checkpoint.
- **SAFE-13 protected-file hole (227-04, HIGH, CONFIRMED).** `wan_controller_state.py` is
  controller-path (imported by `wan_controller.py`) but is not in the boundary check's
  protected list. SAFE-13 can pass while controller state logic changes.
- **Summary/evidence parsing doesn't exist yet (227-01 + 227-04, HIGH, CONFIRMED).**
  `phase226-baseline-summary.py` does not parse unmarked-UDP jitter/loss or TCP throughput
  today, so AB-04's "marked EF vs unmarked UDP" comparison and several GATE-01 signals the
  completeness gate reads must be built, not merely surfaced — larger than "additive fields."
- **iperf concurrency / matched-load integrity (227-01, HIGH, plausible-unverified).** Adding
  a third concurrent flow on the same `REF_HOST:REF_PORT` risks port collision, server
  contention, and stealing bandwidth from the unmarked-UDP arm — undermining D-03's
  byte-for-byte matched-arm contract and the apples-to-apples premise. Needs a defined
  separation (distinct ports / proven concurrent-capable reflector) and which dataset feeds
  GATE-01 vs AB-04.
- **qdisc-gate parse + fail-closed hardening (227-02, HIGH→hardening).** Tokenize only the
  `qdisc cake` line (already in plan intent), bounded SSH timeout, and an explicit
  `got: missing|ssh_failed|no_cake|ambiguous` proof state so a false pass cannot poison the
  candidate dataset.
- **Health-endpoint ambiguity (227-03, HIGH).** Plan/CONTEXT reference `127.0.0.1:9101` while
  the 226 harness uses a host:port endpoint; "/health RED" and "daemon crashloop" abort
  triggers are not concretely defined. One source of truth + exact field/command definitions
  needed.

### Divergent Views
None — single external reviewer. No reviewer-vs-reviewer disagreement to adjudicate. Where
Codex's framing was hedged ("appears to", "if it is controller-path"), Claude's source
verification removed the hedge: the abort-path, SAFE-13-hole, and summary-parsing HIGHs are
confirmed real; the iperf-concurrency HIGH remains plausible-but-unverified against the live
reference host.

### Recommended Action
Feed back into planning before Wave 2 executes:
`/gsd:plan-phase 227 --reviews`

The 227-03 abort path and the 227-04 SAFE-13 hole are production-safety blockers and should be
resolved (or explicitly risk-accepted with operator sign-off) before the checkpoint-gated flip.
