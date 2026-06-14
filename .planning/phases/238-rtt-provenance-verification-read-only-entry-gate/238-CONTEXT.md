# Phase 238: RTT-Provenance Verification (Read-Only Entry Gate) - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Read-only entry gate for v1.53. Deliver three things with **zero source changes and zero production mutation**:

1. **PROV-01** — an evidence-backed provenance map of which producer actually feeds live steering RTT in the current cake-autorate topology.
2. **PROV-02** — a selected-and-recorded A/B target interpretation (A = revive steering's own pinger as the live RTT source; B = evaluate at the autorate/bridge producer), backed by the phase's own evidence.
3. **PROV-03** — a read-only proof that `fping -S <source_ip>` would egress the intended WAN under the host's current `ip rule` policy routing.

Plus the SC-4 / SAFE-17 boundary: no controller-path drift.

**Not in scope:** any backend code, the `RttBackend` Protocol (Phase 239), config/validator (240), fping backend (241), the full fail-closed SAFE-17 verifier + narrowed allowlist (authored in 239), and standing up native autorate (NATIVE-AB-01, deferred out of v1.53). This phase only *maps and decides*.

</domain>

<decisions>
## Implementation Decisions

### A/B Target Decision Model (PROV-02)
- **D-01:** Evidence-first. The phase produces the provenance map **plus an A-vs-B recommendation with evidence**; the operator (Kevin) makes the binding A/B selection at phase execution/verification. CONTEXT captures the *decision criteria*, not a pre-baked verdict.
- **D-02:** Current leaning is **genuinely undecided** — let the provenance evidence and scope-fit drive the recommendation. The phase must present **both** interpretations honestly, including why each is or isn't viable.
- **D-03:** Decision rubric = **maximize A/B evidence fidelity.** The recommendation should favor whichever target yields the most trustworthy icmplib-vs-fping comparison on real traffic for Phase 245's verdict, even if that costs more change — over a more conservative minimal-blast-radius option. (Blast-radius / SAFE-17 cost is still documented as a tradeoff, not used as the primary selector.)
- **D-04 (load-bearing context for the recommendation):** Verified in source, the live steering RTT chain is `run_cycle → _measure_current_rtt_with_retry → measure_current_rtt → load_live_rtt`, reading autorate `/health` `measurement.raw_rtt_ms`. Steering's own `RTTMeasurement` (icmplib pinger) is **constructed but never called** (`daemon.py:2554`). In prod the `/health` `raw_rtt_ms` is produced by the deployed `cake-autorate-{wan}-state-bridge` binary parsing **upstream bash cake-autorate's** pinger output — a path the new wanctl `RttBackend` seam cannot reach. Because NATIVE-AB-01 (stand up native autorate) is deferred, interpretation B's only wanctl-owned variant is largely out of v1.53 scope. The phase must confirm/refute this map with live evidence and weigh it against the fidelity rubric.

### Provenance Map Deliverable (PROV-01)
- **D-05:** Single **phase-dir evidence artifact** — `238-*/PROVENANCE-MAP.md` (versioned phase evidence, consistent with prior read-only milestones 212/222/225). No separate `docs/` runbook this phase.
- **D-06:** The artifact must embed: (a) a **live `/health` capture** from the production cake-shaper host showing the `measurement` block consumed by steering; (b) the **verified code-path trace** proving which source steering uses (and that the constructed `RTTMeasurement` is dead in this topology); (c) the **deployed bridge identity** — confirm what `/usr/local/sbin/cake-autorate-{spectrum,att}-state-bridge` actually is and that it (not a repo Python module) is the live `raw_rtt_ms` producer. Repo-vs-prod reconciliation matters: the bridge runs as a deployed binary, not as a same-named repo source file.

### fping Egress Proof (PROV-03)
- **D-07:** Cover **both WANs** (Spectrum + ATT). Prove `ip route get <reflector> from <source_ip>` for each WAN's `ping_source_ip`, and also capture the host `ip rule` policy table for context. Both-WAN coverage is the safe call while the A/B target is undecided.
- **D-08:** Capture via a **committed read-only proof script** (e.g. `scripts/phase238-egress-proof.sh`) that the operator runs on the live host; stdout is captured into the evidence artifact. Reproducible and re-runnable, consistent with prior phases. Not ad-hoc paste.

### SAFE-17 / Read-Only Entry Proof (SC-4)
- **D-09:** **Lightweight controller-path git-diff assertion.** Phase 238 has no source changes by definition; prove it with an empty controller-path git diff plus an explicit "no production mutation" statement. The full fail-closed SAFE-17 source-diff verifier **and the narrowed allowlist are authored in Phase 239** per the roadmap — not built here.

### Claude's Discretion
- Exact filenames, section structure of `PROVENANCE-MAP.md`, and the shape of the egress-proof script output are at the planner/executor's discretion, as long as D-05..D-08 evidence is captured.
- How "live capture" is obtained read-only (operator runs a `! curl …`/`! ssh …` at the keyboard vs the committed script also fetching `/health`) is open — privileged/credentialed reads should be handed to the operator as `! <command>` rather than escalated.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase + milestone scope
- `.planning/ROADMAP.md` — Phase 238 entry (goal, 4 success criteria, dependency spine), v1.53 milestone framing, and the explicit RTT-provenance caveat (steering `rtt_measurement` constructed-but-never-called in the live cake-autorate topology).
- `.planning/REQUIREMENTS.md` — PROV-01/02/03 and SAFE-17 definitions; the binding out-of-scope table.
- `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` — two-mode (native + external cake-autorate) reality and "what not to delete yet"; governs the deployed-bridge vs repo-source distinction.

### Live RTT provenance (verified code-path)
- `src/wanctl/steering/daemon.py` — `load_live_rtt()` :1000–1024 (reads `/health` `measurement.raw_rtt_ms`, staleness-gated); `measure_current_rtt()` :1755–1767 (autorate health → autorate IRTT fallback, source labels); `_measure_current_rtt_with_retry()` :1769; `run_cycle()` RTT subsystem :2080–2089; dead `RTTMeasurement` construction :2554.
- `src/wanctl/rtt_measurement.py` — `RTTMeasurement`, `source_ip` handling :145–206 (the icmplib path the seam refactors behind, and the `-S`-equivalent source binding).
- `src/wanctl/autorate_continuous.py` — native autorate's `_create_wan_components` / `RTTMeasurement` construction :120–167 (the wanctl-owned producer that is **not running** in prod; relevant to interpretation B viability).
- `deploy/systemd/cake-autorate-spectrum-state-bridge.service`, `deploy/systemd/cake-autorate-att-state-bridge.service` — `ExecStart=/usr/local/sbin/cake-autorate-{wan}-state-bridge` (the deployed live `raw_rtt_ms` producer to identify and verify).
- `src/wanctl/health_check.py` — `/health` payload contract (`raw_rtt_ms`, `available`, `staleness_sec`) that the provenance map captures and that Phase 244 must byte-preserve.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Prior read-only milestone evidence pattern (Phases 212 inventory, 222 steering drift audit, 225 DSCP ingress trace) — same shape: capture live read-only evidence into a phase-dir artifact, prove zero mutation.
- Existing read-only proof scripts as templates for `scripts/phase238-egress-proof.sh`: `scripts/phase225-dscp-ingress-capture.sh`, `scripts/phase231-migration-held.sh`.
- `_record_rtt_source_success()` source labels (`autorate_health`, `autorate_irtt`, `history_fallback`, `unavailable`) — already name the exact provenance the map must document.

### Established Patterns
- `STALE_AUTORATE_MEASUREMENT_THRESHOLD_SECONDS` gating in `load_live_rtt()` — the map should note staleness handling as part of "what steering accepts as live RTT."
- Per-WAN `ping_source_ip` is the input to both the dead `RTTMeasurement(source_ip=…)` and the future `fping -S` binding — the egress proof validates the same value fping would use.

### Integration Points
- The provenance map is the **input contract** for the rest of v1.53: the A/B target it selects is consumed directly by Phase 245 (live A/B) and shapes Phase 239's seam placement and Phase 242's factory wiring (whether `steering/daemon.py` is a construction site).
- Repo-vs-prod reconciliation: the live bridge is a deployed binary under `/usr/local/sbin/`, not a same-named repo module — verify deployed reality, don't assume repo == prod (consistent with the both-WANs-on-cake-autorate operational note).

</code_context>

<specifics>
## Specific Ideas

- The provenance map must be honest about the "wrinkle": the live RTT originates in upstream **bash** cake-autorate, which the wanctl Python seam cannot touch — so the A/B target choice is genuinely constrained, not cosmetic. Surface this prominently; it is the crux of PROV-02.
- Fidelity-first rubric (D-03) means the recommendation should not default to "whatever changes the least" — it should argue for the target that makes Phase 245's icmplib-vs-fping verdict trustworthy on real traffic.

</specifics>

<deferred>
## Deferred Ideas

- **NATIVE-AB-01** — stand up native autorate to make interpretation B fully wanctl-owned and on a real control path. Explicitly deferred out of v1.53; informs but does not get built in Phase 238.
- **docs/ operator runbook for RTT provenance** — a durable `docs/RTT-PROVENANCE.md` was considered but deferred; this phase keeps evidence in the phase dir only. Promote later if the map proves operationally load-bearing.
- **Full SAFE-17 fail-closed verifier + narrowed allowlist** — Phase 239 scope, not 238.

</deferred>

---

*Phase: 238-rtt-provenance-verification-read-only-entry-gate*
*Context gathered: 2026-06-14*
