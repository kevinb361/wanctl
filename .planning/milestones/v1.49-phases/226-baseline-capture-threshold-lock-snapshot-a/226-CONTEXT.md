# Phase 226: Baseline Capture + Threshold Lock + Snapshot A - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish a reversible, fully-instrumented starting line **before any production CAKE-mode change** on Spectrum. Three deliverables, no candidate deploy:

1. **Snapshot A rollback anchor** — Spectrum config (`configs/spectrum.yaml`) + live production CAKE/qdisc state, restorable to the exact pre-A/B `920/18 besteffort wash` state.
2. **Baseline evidence set** on the current `920/18 besteffort wash`: `tc -s qdisc` on spec-router and spec-modem, per-tin counters/drops/backlog/delay under load, Spectrum health/state, and RRUL/flent latency-under-load.
3. **Pre-registered GATE-01 thresholds** locked in a committed artifact at plan time, so the Phase 228 verdict reads fixed numbers it cannot reverse-fit.

**Gating precondition (met):** Phase 225 DSCP-03 verdict = *marks survive to CAKE ingress* → operator override → PROCEED (2026-06-04). If DSCP-03 had early-exited, this phase would not run and the milestone would close negative.

**Explicitly OUT of this phase:** deploying candidate `diffserv4 wash` (reserved for Phase 227); any controller-path source change (frozen under SAFE-13); any ATT config change.
</domain>

<decisions>
## Implementation Decisions

### GATE-01 Threshold Values (locked, pre-registration discipline)
Recorded as a committed `phase226-thresholds.json` mirroring `scripts/phase206-thresholds.json` (versioned JSON, named numeric thresholds, single-source-of-truth `_notes`, no numeric literals duplicated into prose).

- **D-01 — RRUL p99 latency-under-load regression tolerance: 5%.** Inherit `phase206-thresholds.json` `RRUL_P99_REGRESSION_PCT=5.0` — the v1.44 rollback gate the roadmap explicitly cites. Candidate p99 >5% worse than Snapshot A baseline = rollback trigger. Headline accept/reject gate; kept consistent across milestones.
- **D-02 — Daemon restart-rate gate: +10% relative.** Inherit `phase206` `RESTART_RATE_INCREASE_PCT=10`. Candidate fails if daemon restart-rate runs >10% above the baseline-window rate.
- **D-03 — Pressure-state transition-rate gate: +10% relative.** Inherit `phase206` `TRANSITION_RATE_INCREASE_PCT=10`. Candidate fails if pressure-state transition-rate runs >10% above the baseline-window rate. (Relative deltas chosen over absolute caps — DOCSIS baseline-window noise makes absolute caps brittle.)
- **D-04 — Upload stability: UL p99 + floor-churn.** UL is considered stable iff **(a)** UL p99 latency-under-load regression ≤ 5% **AND (b)** no increase in floor-hit-cycles / SOFT_RED dwell vs baseline. Both arms required — catches latency cost *and* the upload-collapse failure mode the latency-first 18 Mbit operating point is sensitive to. New criterion (no inherited definition).

### Tin-Separation Definition (the fuzziest GATE-01 criterion — operationalized now)
- **D-05 — "Useful non-BestEffort tin separation" = occupancy + delay gap.** Two-part, both required, measured from `tc -s qdisc` per-tin counters under saturating load:
  - **(a) Occupancy:** marked traffic actually lands in a non-BE tin (non-zero packets/sojourn in non-BE tins) — rules out classification with no effect.
  - **(b) Delay gap:** that non-BE tin shows measurably lower per-tin queue delay/backlog than the BE tin under load — this is what "useful" means; occupancy alone would be "classification theater."
- **D-06 — Separation magnitude = clear beyond noise (rule locked, number derived).** The non-BE vs BE per-tin delay gap must **exceed the baseline run-to-run variance** (3-run spread, see D-08). Locked as a *decision rule* at plan time (un-gameable, pre-registered); its concrete numeric threshold is *derived* from the Snapshot A baseline spread rather than guessed before path noise is known. **This is pre-registration, not reverse-fitting** — the rule is fixed before deploy; only the noise-band constant comes from baseline data.

### Baseline Capture Method (must be reproduced verbatim in Phase 227)
- **D-07 — Load profile: flent RRUL + unmarked reference flows.** flent RRUL (bidirectional saturating + latency probe, satisfies AB-02) **plus** unmarked-UDP and unmarked-bulk-TCP reference flows. The unmarked refs pre-stage the Phase 227 realtime-protection comparison (marked EF UDP vs unmarked UDP vs bulk TCP) — Phase 227 only adds the marked-EF arm against an already-captured matched unmarked baseline.
- **D-08 — Run count/duration: 3 runs × 60 s, mean + spread.** phase198 3-run precedent. Mean smooths DOCSIS variance; the **3-run spread supplies the baseline noise band the D-06 tin-separation gate keys off** (hard dependency — capture must compute per-tin queue-delay run-to-run spread, not just a point estimate).

### Snapshot A Scope + Restore
- **D-09 — New sibling capture wrapper `phase226-snapshot-a.sh`.** Reuse the proven `scripts/phase224-snapshot-a.sh` shape (redacted committable evidence + MANIFEST under `--output-dir`; unredacted raw restore artifacts mode 0600 under operator-private `--raw-dir` outside the git tree; read-only on target — `sudo -n cat` + `/health` only, no deploy/restart/mutate). Capture **Spectrum CAKE state** instead of steering daemon state: `configs/spectrum.yaml`, `tc -s qdisc` on spec-router + spec-modem, and cake-shaper bridge nft rules. Kept as a clean separate tool from the steering snapshot (avoids coupling two capture domains under SAFE-13 scrutiny).
- **D-10 — Restore proof: dry-run verified (no prod CAKE-mode change).** Prove the restore artifact reproduces current `configs/spectrum.yaml` byte-for-byte **AND** that the restore apply-command is identical to the Phase 228 rollback path — **without** mutating production CAKE mode (respects success-criterion 4 and the SAFE-13 boundary). A live restore drill (flip to `diffserv4` then restore) was explicitly **rejected** as an out-of-bounds candidate deploy for this phase.

### Claude's Discretion
- Evidence artifact layout/naming: mirror the Phase 225 `evidence/` tree under the phase dir, with a `baseline-<UTC>` capture directory + `MANIFEST.md`, named so Phase 227's matched capture is trivially diffable.
- SAFE-13 boundary verification: reuse `scripts/phase225-safe13-boundary-check.sh` at the phase boundary (controller-path zero-diff vs v1.48 close; ATT config byte-identical).
- Spectrum health/state capture cadence within the load window — pick a sane pre/during/post sampling per AB-02.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope, requirements, gating verdict
- `.planning/ROADMAP.md` — Phase 226 entry + success criteria; phase 225→226 gating; v1.49 milestone arc (226 baseline → 227 candidate → 228 verdict).
- `.planning/REQUIREMENTS.md` — AB-01 (Snapshot A anchor), AB-02 (baseline evidence set), GATE-01 (pre-registered thresholds), SAFE-13 (controller-path zero-diff cross-phase invariant).
- `.planning/phases/225-dscp-survival-trace/evidence/DSCP-03-VERDICT.md` — the "marks survive" verdict (operator override) that unblocks this phase.

### Threshold-lock format + gate-eval precedent (GATE-01)
- `scripts/phase206-thresholds.json` — **exact format to mirror** for `phase226-thresholds.json`; inherited numeric values (RRUL_P99=5.0, RESTART_RATE=10, TRANSITION_RATE=10).
- `scripts/phase206-gate-check.py` — threshold-evaluation precedent.
- `scripts/phase224-gate-eval.py` — gate-eval precedent (Phase 224 canary).
- `scripts/phase206-predeploy-gate.sh`, `scripts/phase201-predeploy-gate.sh` — pre-deploy gate wrappers.

### Snapshot / rollback precedent (AB-01, restore)
- `scripts/phase224-snapshot-a.sh` — **structural template** for `phase226-snapshot-a.sh` (redacted-evidence + operator-private-raw + read-only-on-target pattern).
- `scripts/phase224-rollback.sh` — rollback path precedent; Phase 228 restore must match the apply-command verified in D-10.

### Baseline capture precedent (AB-02)
- `scripts/phase213-baseline-capture.sh` — baseline capture precedent.
- `scripts/phase214-flent-matrix.sh`, `scripts/phase198-rerun-flent-3run.sh` — flent RRUL / 3-run capture precedent (D-07, D-08).
- `scripts/compare_ab.py` — A/B comparison helper (consumed in Phase 228, informs baseline artifact shape now).

### Config + state under test, closeout targets
- `configs/spectrum.yaml` — the `920/18 besteffort wash` config that IS the baseline and the Snapshot A subject (`diffserv: besteffort`, `allow_wash: true`, DL ceiling 920, UL ceiling 18, `docsis_mode: true`). Closeout edit target in Phase 228.
- `docs/BRIDGE_QOS.md` — DSCP/bridge QoS topology + DOCSIS DSCP-strip findings; closeout record target in Phase 228.
- `CHANGELOG.md` — closeout record target in Phase 228.

### SAFE-13 boundary
- `scripts/phase225-safe13-boundary-check.sh` — controller-path zero-diff boundary check to reuse at the 226 phase boundary.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/phase224-snapshot-a.sh`: redacted-evidence + operator-private-raw-restore + read-only-on-target capture pattern → template for `phase226-snapshot-a.sh` (swap steering `/health` capture for Spectrum CAKE/qdisc + spectrum.yaml + bridge nft).
- `scripts/phase206-thresholds.json`: versioned-JSON threshold-lock format with single-source-of-truth `_notes` → template for `phase226-thresholds.json`; reuse RRUL_P99=5.0 / RESTART=10 / TRANSITION=10 and add UL-stability + tin-separation entries.
- `scripts/phase213-baseline-capture.sh` + `phase214-flent-matrix.sh` + `phase198-rerun-flent-3run.sh`: baseline + flent RRUL 3-run capture machinery for D-07/D-08.
- `scripts/phase206-gate-check.py` / `phase224-gate-eval.py`: threshold-evaluation precedent (verdict logic lands in Phase 228 but the threshold schema must be eval-compatible now).
- `scripts/phase225-safe13-boundary-check.sh`: ready-made SAFE-13 boundary verification.

### Established Patterns
- **Pre-registration discipline (v1.44/v1.47):** thresholds committed before deploy; numeric literals live only in the JSON, never duplicated in docs.
- **Snapshot redaction split:** committable redacted evidence vs operator-private raw restore artifacts (mode 0600, outside git). Honor this — raw restore sources MUST NOT be committed.
- **Read-only capture on target:** `sudo -n cat` + `/health` only; no deploy/restart/mutate during capture.
- **SAFE-13 invariant:** controller path (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) byte-identical vs v1.48 close at the phase boundary; ATT config byte-identical.

### Integration Points
- Snapshot A target host: cake-shaper bridge VM (`spec-router` / `spec-modem` NICs); CAKE backend is `linux-cake-netlink` per `configs/spectrum.yaml`.
- The candidate flip in Phase 227 is a one-line `configs/spectrum.yaml` change (`diffserv: besteffort` → `diffserv4`, `allow_wash` stays) — so Snapshot A is small/clean and the restore target is unambiguous.
</code_context>

<specifics>
## Specific Ideas

- The baseline is the **literal current `configs/spectrum.yaml`** state — `920/18 besteffort wash`, verified at discussion time (`diffserv: besteffort`, `allow_wash: true`, DL 920 / UL 18, `docsis_mode: true`).
- Threshold artifact name: `phase226-thresholds.json` (sibling to `scripts/phase206-thresholds.json`), schema-versioned, eval-compatible with the Phase 228 gate-check.
- Tin-separation threshold is intentionally a **rule + derived constant** (D-06): the planner must wire baseline-spread computation into the capture so the constant is filled from data, with the rule frozen at plan time.
</specifics>

<deferred>
## Deferred Ideas

None raised that expand this phase — discussion stayed inside the baseline/anchor/threshold-lock boundary. Candidate deploy, the realtime-protection EF comparison, and the verdict all remain in Phases 227–228 by roadmap design.

### Reviewed Todos (not folded)
Surfaced by `todo.match-phase 226`; reviewed and deliberately **not** folded into Phase 226 scope:
- **Retest Spectrum diffserv4 wash after local QoS changes** (score 0.6) — this IS the v1.49 milestone thesis (Phases 225–228 collectively); the retest proper lives in Phase 227/228, not in 226's baseline/anchor work. Tracked at milestone level, not a 226 fold.
- **Investigate steering SPECTRUM_DEGRADED on clean restart** (0.6) — steering-path carry-forward (v1.48 Phase 223 lineage); unrelated to CAKE-mode baseline. Already in STATE.md carry-forward.
- **Monitor flapping peak_transition_count on next real DOCSIS event** (0.6) — Phase 218 VERIFY watch-list, event-gated; not 226 scope.
- **operator-summary --digest PermissionError handling** (0.6) — out-of-scope tooling hygiene; STATE.md carry-forward.
- **Resolve ATT cake-primary canary after Phase 196** (0.6) — ATT-side; SAFE-13 keeps ATT byte-identical this milestone — explicitly not touched here.
- **metrics.db write-rate tool** (0.4), **Silicom bypass NIC tooling** (0.4) — dormant seeds, unrelated.

</deferred>

---

*Phase: 226-baseline-capture-threshold-lock-snapshot-a*
*Context gathered: 2026-06-04*
