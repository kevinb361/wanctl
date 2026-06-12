# Requirements: wanctl v1.52 Silicom Bypass Operationalization

**Defined:** 2026-06-12
**Core Value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Milestone Goal:** Turn the validated-but-unused Silicom bypass card into an operated capability — safe operator verbs, watchdog-driven fail-open, and a hardware-in-the-loop failure harness — without touching the controller path.

## v1.52 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Operator CLI (TOOL)

- [ ] **TOOL-01**: Operator can query live bypass card state per pair (`silicom-bypass status [pair|all]`) with values read back from bpctl, not cached
- [ ] **TOOL-02**: Operator can change pair state via idempotent guarded verbs (`on/off/disc/conn`); destructive ops (`on`/`disc`) require `--yes`; non-bypass-capable interfaces are refused
- [ ] **TOOL-03**: A destructive op that would put BOTH pairs simultaneously into non-NIC state requires an additional `--both-wan-confirm` gate
- [ ] **TOOL-04**: Operator can anchor the journal narrative with `silicom-bypass mark <label>` at test/transition boundaries

### Watchdog Fail-Open (WDOG)

- [ ] **WDOG-01**: Watchdog fail-open units cover both pairs under the current external cake-autorate mode — the stale wanctl@-coupled generic `silicom-bypass-watchdog@.service` template is reconciled; off by default, operator opt-in per pair
- [ ] **WDOG-02**: Heartbeat-death → relay-bypass behavior is proven non-destructively (shim/test), and the live bypass-watchdog failure mode hit during the ATT migration is understood and covered
- [ ] **WDOG-03**: Operator can arm/disarm the watchdog per pair via the CLI (`arm <pair> [timeout]` / `disarm <pair>`)

### Boot Baseline (BOOT)

- [ ] **BOOT-01**: A oneshot boot service applies the known-good bpctl baseline to both pairs (`set_dis_bypass off`, `set_bypass_pwoff on`, `set_bypass_pwup off`, `set_disc_pwup off`, `set_std_nic off`) and asserts each setting via read-back

### HIL Harness (HARN)

- [ ] **HARN-01**: Operator can run a `failover <pair>` scenario (simulated cable pull via `set_disc`) capturing steering/health/bridge state through failure and recovery
- [ ] **HARN-02**: Operator can run an `ab-cake <pair>` scenario (CAKE-shaped vs raw-ISP bypass, same hardware/minute/client)
- [ ] **HARN-03**: Named scenario files run via `silicom-test chaos <name>`; operator-invoked only, no scheduling
- [ ] **HARN-04**: Every harness command registers an always-on exit trap restoring all touched pairs to NIC mode regardless of success/failure
- [ ] **HARN-05**: Each run captures structured results (`tests/silicom/<timestamp>-<scenario>/`: pre/post state, snapshots, tool output, journal extracts)

### Deployment & Safety (DEPLOY/SAFE)

- [ ] **DEPLOY-03**: All bypass tooling artifacts are repo-owned and deployable via a documented path (install/deploy flow decided at plan time)
- [ ] **SAFE-16**: Zero controller-path source diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) at every phase boundary AND milestone close — 10th consecutive milestone holding the SAFE-07..15 discipline

## Future Requirements

Deferred to later milestones. Tracked but not in v1.52.

- **ROLE-01**: Native controller retirement/retention decision — Codex gate (2026-06-12): ≥14 consecutive stable cake-autorate days PLUS one exercised rollback drill; the v1.52 HARN harness enables that drill
- **TAIL-01**: Spectrum loaded-latency tail evidence — NOT exhausted; better after v1.52 (bypass/disconnect verbs make evidence collection repeatable)
- **SEED-007**: Storage hygiene fire-on-change — must be reshaped for bridge writers; consumer audit required first
- **SEED-005**: Conservative UL tuning sweep — native wanctl remains first-class on RouterOS deployments
- **fping RTT backend evaluation** — reduced relevance while native controller not live

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Unpowered fail-open re-litigation | Settled per RCA in `docs/SILICOM-BYPASS.md` (monostable relays, `AuxCurrent=0mA`); UPS coverage compensates architecturally |
| ROLE-01 retirement decision | ~4 days soak is not "matured"; needs ≥14 stable days + rollback drill (which this milestone's harness enables) |
| TAIL-01 Spectrum tail investigation | Different milestone shape; harness-first ordering per joint Codex decision |
| SEED-007 storage hygiene | Bridge-writer reshape + consumer audit is its own thesis; biggest scope-explosion risk |
| wanctl Python control-loop integration | Bypass data path skips Linux entirely; wanctl has no role in that path — observability-only health exposure is a plan-time question, not control coupling |
| Steering policy or algorithm changes | SEED-006 is infrastructure/failure tooling, not steering behavior work |
| Scheduled / continuous chaos runs | Initial scope is operator-invoked only |
| pytest harness unification | System-level HIL vs unit/integration — different lifecycles, intentionally not unified |
| Controller threshold/algorithm changes | SAFE-16 — surface is scripts/units/docs/tests only |
| Broad production failure drills | Harness primitives only; full operational drills belong after tooling is proven |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TOOL-01 | TBD | Pending |
| TOOL-02 | TBD | Pending |
| TOOL-03 | TBD | Pending |
| TOOL-04 | TBD | Pending |
| WDOG-01 | TBD | Pending |
| WDOG-02 | TBD | Pending |
| WDOG-03 | TBD | Pending |
| BOOT-01 | TBD | Pending |
| HARN-01 | TBD | Pending |
| HARN-02 | TBD | Pending |
| HARN-03 | TBD | Pending |
| HARN-04 | TBD | Pending |
| HARN-05 | TBD | Pending |
| DEPLOY-03 | TBD | Pending |
| SAFE-16 | TBD | Pending |

**Coverage:**
- v1.52 requirements: 15 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 15

---
*Requirements defined: 2026-06-12 (joint Claude + Codex scope decision; SEED-006 selected, Codex ranked #1)*
