# Phase 227: Candidate diffserv4-wash Deploy + Matched Capture - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 227-candidate-diffserv4-wash-deploy-matched-capture
**Areas discussed:** Deploy + verify gate, Matched-load fidelity, Marked-EF arm (AB-04), Post-capture posture + abort

---

## Deploy + verify gate

| Option | Description | Selected |
|--------|-------------|----------|
| deploy.sh + restart + verify gate | Flip spectrum.yaml, deploy.sh to cake-shaper, restart wanctl@spectrum, then a new phase227 verify step asserts `tc qdisc show` reports diffserv4 on both spec-router+spec-modem before any flent run. Abort on mismatch. | ✓ |
| deploy.sh, trust the restart | Deploy + restart, no explicit qdisc-verify gate. Risk of capturing the wrong mode. | |
| Manual edit + manual tc check | Operator applies by hand, eyeballs tc. Lowest reproducibility. | |

**User's choice:** deploy.sh + restart + verify gate
**Notes:** Protects A/B provenance — a silent restart failure must never pollute the candidate dataset. Phase 201 Spectrum predeploy gate still runs.

---

## Matched-load fidelity

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse 226 harness verbatim, same window | phase226-baseline-capture.sh unchanged into candidate-<UTC> dir; same host/runs/duration/window. DOCSIS variance covered by 3-run spread + GATE-01 noise band. | ✓ |
| Reuse harness + pair time-of-day | Same script, scheduled at the same local hour as the 226 baseline. Adds a scheduling constraint. | |
| Fork phase227-candidate-capture.sh | Copy + modify. Method-drift risk against locked baseline. | |

**User's choice:** Reuse 226 harness verbatim, same window
**Notes:** Reconciled with the EF arm (next area) — the marked-EF flow must be PURELY ADDITIVE (a `--marked-ef` flag), not a fork, so the matched arms stay byte-for-byte identical.

---

## Marked-EF arm (AB-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Marked-EF on BOTH a fresh besteffort + candidate | Add a marked-EF UDP flow to both a fresh besteffort capture (no mode change — already besteffort) and the candidate capture. True apples-to-apples; empirically proves the wash. Cost: one extra capture window. | ✓ |
| Candidate-only EF + documented wash assumption | Marked-EF only under candidate; 226 unmarked as besteffort reference, documenting besteffort-washes-mark theory. Cheaper, unmeasured. | |

**User's choice:** Marked-EF on BOTH a fresh besteffort + candidate
**Notes:** Degrade-to-best-effort fallback mandatory (AB-04). EF premise rests on Phase 225 DSCP-03 verdict (marks survive to CAKE ingress). Implied sequence: besteffort+EF (on anchor) → flip → candidate+EF.

---

## Post-capture posture + abort

| Option | Description | Selected |
|--------|-------------|----------|
| Leave diffserv4 live for 228 + armed abort | Candidate stays live for the 228 verdict (verdict reads the deployed mode). Mid-capture abort: daemon crashloop / health RED / wrong qdisc → immediate phase226-restore to Snapshot A. Single deploy. | ✓ |
| Capture-then-restore to besteffort | Restore immediately after capture; 228 re-deploys. Doubles deploys; 228 verdicts a fresh redeploy. | |
| Leave live + hard time-box auto-rollback | Auto-rollback if 228 hasn't run within N hours. Adds a timer mechanism. | |

**User's choice:** Leave diffserv4 live for 228 + armed abort
**Notes:** Single deploy keeps 228 verdict on the actually-captured mode. Armed abort is the only in-phase mutation-rollback; the verdict-driven rollback proper is Phase 228.

---

## Claude's Discretion

- EF marking mechanic (iperf3 --dscp ef / TOS byte) — pick cleanest reproducible method, record in manifest.
- Candidate evidence dir layout/naming — mirror 226 tree for trivial baseline-vs-candidate diff.
- SAFE-13 boundary verification — reuse phase225-safe13-boundary-check.sh.
- Whether diffserv4 needs a bridge nft change — researcher/planner to confirm (expected: none).

## Deferred Ideas

None expand this phase. Verdict / accept-reject / SAFE-13-lift call / verdict-driven rollback all remain Phase 228. `diffserv4 nowash` follow-up stays post-v1.49 backlog. Reviewed-not-folded todos listed in CONTEXT.md (steering-degraded, operator-summary, ATT canary, Silicom harness, dormant seeds).
