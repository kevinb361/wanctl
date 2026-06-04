# Phase 227: Candidate diffserv4-wash Deploy + Matched Capture - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy candidate `diffserv4 wash` (download + upload) on **Spectrum only** under the
Snapshot A anchor, then capture the **identical** Phase 226 evidence set under matched
load, plus add the realtime-flow protection comparison (marked EF UDP vs unmarked UDP vs
unmarked bulk TCP) — so the Phase 228 verdict reads a direct apples-to-apples
baseline-vs-candidate dataset.

The candidate deploy is a **one-line `configs/spectrum.yaml` change**: `diffserv: besteffort`
→ `diffserv: diffserv4`, with `allow_wash: true` unchanged. It is driven entirely by the
existing tin-agnostic CAKE signal / `allow_wash` gate (v1.44 Phase 205) — **no controller
algorithm change** is required to drive `diffserv4 wash`.

**Gating precondition (met):** Phase 226 complete — Snapshot A captured, baseline evidence
recorded on `920/18 besteffort wash`, GATE-01 thresholds locked in `phase226-thresholds.json`.

**Explicitly OUT of this phase:**
- The verdict / accept-reject decision (Phase 228).
- Any controller-path source change — frozen under SAFE-13. The cake-shaper bridge nftables
  rules MAY change if `diffserv4` requires it; the controller path MUST NOT.
- Any ATT config change (byte-identical the entire milestone).

</domain>

<decisions>
## Implementation Decisions

### Candidate deploy + flip-verification gate (AB-03)
- **D-01 — Deploy via standard path + post-deploy qdisc-verify gate.** Edit `configs/spectrum.yaml`
  (`besteffort` → `diffserv4`), deploy with `scripts/deploy.sh` to `cake-shaper`, restart
  `wanctl@spectrum.service`. Then a **new phase227 verify step** asserts `tc -s qdisc show`
  reports `diffserv4` on **both** `spec-router` AND `spec-modem` before any flent run starts.
  A mode mismatch aborts the capture — no evidence is collected on the wrong qdisc mode. This
  protects the A/B provenance: a silent restart failure or stale qdisc must never pollute the
  candidate dataset. The Phase 201 Spectrum predeploy gate (`scripts/phase201-predeploy-gate.sh`,
  wired into `deploy.sh`) still runs on the Spectrum deploy.

### Matched-load fidelity (AB-03)
- **D-02 — Reuse `phase226-baseline-capture.sh` verbatim into a new `candidate-<UTC>` dir.**
  Same SSH host, runs (3), duration (60s), off-peak window, ref host, and ref rates as the
  226 baseline. DOCSIS run-to-run variance is covered by the 3-run mean + spread and the
  GATE-01 noise band (inherits D-08 discipline). **No time-of-day pairing** constraint added —
  the locked noise band already absorbs diurnal variance, and pairing adds scheduling friction
  for marginal benefit.
- **D-03 — The marked-EF arm is PURELY ADDITIVE — do NOT fork the harness.** D-02 (verbatim
  reuse) and D-04 (add a marked-EF arm) coexist only if EF is a *third reference flow* alongside
  the unchanged RRUL + unmarked-UDP + unmarked-bulk-TCP. Implement as a minimal additive
  `--marked-ef` option on the existing harness (or a thin sibling that calls it), NOT a method
  change. The matched arms must stay byte-for-byte identical to 226; EF is bolted on. **Forking
  a `phase227-candidate-capture.sh` that re-implements the capture is rejected** — it introduces
  method drift against the locked baseline.

### Marked-EF realtime-protection comparison (AB-04)
- **D-04 — Capture marked-EF on BOTH a fresh besteffort capture AND the candidate capture.**
  Run the marked-EF arm under (a) a fresh `920/18 besteffort wash` capture — **no mode change
  needed, prod is already besteffort** — and (b) the `diffserv4` candidate capture. This is true
  apples-to-apples and **empirically proves whether besteffort wash strips the EF mark** rather
  than relying on the theory. Cost is one extra capture window, accepted as worth it for a clean
  verdict. (Rejected alternative: candidate-only EF + a documented besteffort-wash assumption —
  cheaper but unmeasured.)
- **D-05 — Degrade-to-best-effort fallback is mandatory, not optional.** Per AB-04, if the test
  rig cannot mark EF cleanly, the comparison degrades to a best-effort capture but the check is
  NOT dropped. Record the marking method and whether clean marking was achieved in the manifest.
- **D-06 — EF premise rests on the Phase 225 DSCP-03 verdict.** "Marks survive to CAKE ingress"
  is what makes the EF arm meaningful: CAKE on `spec-router` sees the LAN-side EF mark even
  though the DOCSIS CMTS strips DSCP downstream. The arm tests whether `diffserv4` *acts* on
  that mark locally vs `besteffort wash` ignoring it.

### Capture sequence (order is load-bearing)
- **D-07 — Sequence: besteffort+EF → flip → candidate+EF → leave live.**
  1. Fresh `besteffort wash` capture WITH the marked-EF arm, on the Snapshot A anchor state.
  2. Flip to `diffserv4` (D-01 deploy + verify gate).
  3. `diffserv4` candidate capture WITH the marked-EF arm.
  4. Leave `diffserv4` live (D-08).
  Capturing besteffort-EF *before* the flip keeps it on the same anchor state, not a
  post-experiment re-derived one.

### Post-capture production posture + abort path (AB-03, SAFE-13)
- **D-08 — Leave `diffserv4` live for the Phase 228 verdict; single deploy.** The candidate
  stays deployed in production between 227 and 228 so the 228 verdict reads the *actually
  deployed* mode, not a fresh redeploy. (Rejected: capture-then-restore-to-besteffort — doubles
  deploys and makes 228 verdict a different deploy than the one captured. Rejected: hard
  time-box auto-rollback — adds a timer mechanism for risk that the armed abort + 228 cadence
  already covers.)
- **D-09 — Armed mid-capture abort using the Snapshot A restore path.** If an objective failure
  fires during or shortly after the flip — daemon crashloop, `/health` RED, or the D-01 qdisc
  verify shows the wrong mode — immediately restore to Snapshot A via the `phase226-restore.sh`
  restore source (the apply-command verified equal in 226 D-10). This is the only in-phase
  mutation-rollback; the verdict-driven rollback proper is Phase 228.

### Claude's Discretion
- Marking mechanic for the EF flow (e.g. `iperf3 --dscp ef` / TOS byte) — pick the cleanest
  reproducible method; record it in the manifest per D-05.
- Candidate evidence dir layout/naming — mirror the 226 `evidence/` tree so the candidate
  capture is trivially diffable against baseline (the `BASELINE-SUMMARY.md` / `baseline-summary.json`
  shape from `phase226-baseline-summary.py` should carry over for direct comparison).
- SAFE-13 boundary verification — reuse `scripts/phase225-safe13-boundary-check.sh` at the
  phase boundary (controller-path zero-diff vs v1.48 close; ATT config byte-identical).
- Whether `diffserv4` requires any cake-shaper bridge nft change — SAFE-13 permits a bridge nft
  change but NOT a controller change; researcher/planner to confirm (expected: none, it's a CAKE
  qdisc param).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope, requirements, gating
- `.planning/ROADMAP.md` — Phase 227 entry + success criteria; the 226→227→228 arc (baseline → candidate → verdict).
- `.planning/REQUIREMENTS.md` — AB-03 (candidate deploy + matched capture), AB-04 (realtime-flow protection comparison), SAFE-13 (controller-path zero-diff cross-phase invariant; bridge nft MAY change, controller MUST NOT).
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/226-CONTEXT.md` — carried-forward decisions: D-07/D-08 capture method (must reproduce verbatim), D-09/D-10 snapshot/restore, GATE-01 threshold definitions.

### Capture harness to reproduce verbatim (AB-03, AB-04)
- `scripts/phase226-baseline-capture.sh` — **THE harness to reuse verbatim** into a candidate dir; already captures RRUL + unmarked-UDP + unmarked-bulk-TCP refs. The marked-EF arm is the only additive change (D-03).
- `scripts/phase226-baseline-summary.py` — summary generator; reuse so candidate summary is diffable against baseline.
- `scripts/compare_ab.py` — A/B comparison helper (verdict logic is Phase 228, but candidate artifact shape must stay eval-compatible).

### Deploy path + predeploy gate (AB-03)
- `scripts/deploy.sh` — Spectrum deploy path (rsync config + `systemctl daemon-reload` + `wanctl@spectrum` restart); contains the Phase 201 predeploy-gate hook (Spectrum-only).
- `scripts/phase201-predeploy-gate.sh` — predeploy gate that fires on Spectrum deploys; must pass with `diffserv4`.

### Snapshot / restore / abort (AB-03, D-09)
- `scripts/phase226-snapshot-a.sh` — Snapshot A anchor capture (already run in 226).
- `scripts/phase226-restore.sh` — restore source; the abort/rollback apply-command (verified equal in 226 D-10).
- `scripts/phase224-rollback.sh`, `scripts/phase224-snapshot-a.sh` — rollback/snapshot structural precedent.

### Locked thresholds (read for 228; informs capture completeness now)
- `scripts/phase226-thresholds.json` — GATE-01 locked accept/rollback gates (RRUL_P99=5.0, RESTART=10, TRANSITION=10, UL-stability, tin-separation rule + derived noise band). Capture MUST produce every signal these gates read.
- `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/GATE-01-THRESHOLDS.md` — human-readable threshold rationale.
- `scripts/phase224-gate-eval.py`, `scripts/phase206-gate-check.py` — gate-eval precedent (consumed in 228).

### Config under test + DSCP/topology premise
- `configs/spectrum.yaml` — the flip target (`diffserv: besteffort` → `diffserv4`, `allow_wash: true` unchanged; DL 920 / UL 18, `docsis_mode: true`, backend `linux-cake-netlink`).
- `docs/BRIDGE_QOS.md` — DSCP/bridge QoS topology + DOCSIS DSCP-strip findings; explains why the EF arm is meaningful at CAKE ingress (D-06).
- `.planning/phases/225-dscp-survival-trace/evidence/DSCP-03-VERDICT.md` — "marks survive to CAKE ingress" verdict underpinning the marked-EF arm.

### SAFE-13 boundary
- `scripts/phase225-safe13-boundary-check.sh` — controller-path zero-diff + ATT byte-identical boundary check to reuse at the 227 boundary.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase226-baseline-capture.sh`: full matched-capture machinery (3×60s flent RRUL + unmarked UDP + bulk TCP + per-run tc qdisc before/during/after + continuous health poller + redacted manifest + sha256). Reuse verbatim; add only an additive `--marked-ef` flow (D-03).
- `scripts/phase226-baseline-summary.py`: per-tin / spread summary generator → reuse for the candidate so summaries diff directly.
- `scripts/phase226-restore.sh` + `phase226-snapshot-a.sh`: Snapshot A anchor + restore source for the D-09 armed abort.
- `scripts/deploy.sh` (+ `phase201-predeploy-gate.sh`): the production deploy path for the one-line flip.
- `scripts/phase225-safe13-boundary-check.sh`: ready-made SAFE-13 boundary verification.

### Established Patterns
- **Read-only capture, mutation only at the deploy step:** the 226 harness is strictly read-only on target; 227's only target mutation is the deploy/restart flip — keep capture read-only.
- **Verbatim reuse over forking:** matched-load fidelity demands the candidate run identical capture code; additive flags, never a forked re-implementation (D-03).
- **Pre-registration discipline (v1.44/v1.47):** thresholds already locked in `phase226-thresholds.json`; 227 only produces evidence, it does not touch thresholds.
- **SAFE-13 invariant:** controller path byte-identical vs v1.48 close; ATT byte-identical. Bridge nft MAY change for `diffserv4`; controller MUST NOT.

### Integration Points
- Deploy target: cake-shaper bridge VM; CAKE backend `linux-cake-netlink`; egress NICs `spec-router` (DL) / `spec-modem` (UL).
- The flip is a single `configs/spectrum.yaml` line driven by the existing `allow_wash` gate / tin-agnostic CAKE signal — so deploy + restart re-applies the qdisc in the new diffserv mode with no code change.

</code_context>

<specifics>
## Specific Ideas

- The candidate is the literal `diffserv: besteffort` → `diffserv: diffserv4` flip; `allow_wash: true`,
  DL 920 / UL 18, `docsis_mode: true` all unchanged.
- The qdisc-verify gate (D-01) is the new artifact specific to 227 — assert `diffserv4` present on
  both NICs via `tc -s qdisc show` before load; abort on mismatch.
- Capture sequence is fixed (D-07): besteffort+EF (on anchor) → flip → candidate+EF → leave live.
- Evidence dir mirrors 226's tree so a `candidate-<UTC>` vs `baseline-<UTC>` diff is trivial for the 228 verdict.

</specifics>

<deferred>
## Deferred Ideas

None raised that expand this phase — discussion stayed inside the candidate-deploy + matched-capture
boundary. The verdict, accept/reject decision, evidence-gated SAFE-13-lift call, and verdict-driven
rollback all remain in Phase 228 by roadmap design. A `diffserv4 nowash` follow-up stays in the
post-v1.49 backlog.

### Reviewed Todos (not folded)
Surfaced by `todo.match-phase 227`; reviewed and deliberately **not** folded (same out-of-scope set
226 reviewed):
- **Investigate steering SPECTRUM_DEGRADED on clean restart** (0.6) — steering-path carry-forward (v1.48 Phase 223 lineage); unrelated to CAKE-mode A/B. In STATE.md carry-forward.
- **operator-summary --digest PermissionError handling** (0.6) — tooling hygiene; out of scope.
- **Resolve ATT cake-primary canary after Phase 196** (0.6) — ATT-side; SAFE-13 keeps ATT byte-identical this milestone — explicitly not touched.
- **Add Silicom bypass NIC test harness** (0.4) — dormant seed, unrelated.
- **metrics.db write-rate tool / other dormant seeds** (0.4) — unrelated.

</deferred>

---

*Phase: 227-candidate-diffserv4-wash-deploy-matched-capture*
*Context gathered: 2026-06-04*
