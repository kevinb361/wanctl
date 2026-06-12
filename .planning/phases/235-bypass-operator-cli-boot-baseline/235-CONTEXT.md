# Phase 235: Bypass Operator CLI + Boot Baseline - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning
**Source:** Seed Express Path (.planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md) — discuss-phase skipped per operator instruction; open questions auto-resolved conservatively per the seed's "Recommended Defaults" and recorded as assumptions below.

<domain>
## Phase Boundary

Operator tooling and boot guards for the Silicom PE2G4BPI35A-SD bypass NIC on the live dual-WAN cake-shaper host:

1. A single guarded `silicom-bypass` CLI (`scripts/silicom-bypass`, bash) for per-pair query and state change (TOOL-01..04).
2. A `silicom-bypass-init` oneshot boot service that applies the known-good bpctl baseline to both pairs and asserts each setting via read-back (BOOT-01).
3. Reconciliation (not rebuild) of the existing partial bpctl surface: `scripts/wanctl-bpctl-{init,dkms-install,watchdog-petter,watchdog-bypass}`, `deploy/systemd/bpctl-silicom.service`.

**Hard boundary:** No production data-path behavior changes. No controller-path Python changes (SAFE-16 zero-diff on `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion). Watchdog arm/disarm (`silicom-bypass-watchdog@.service` reconciliation) is Phase 236 (WDOG-01..03). HIL harness is Phase 237 (HARN-*).

Production is a live dual-WAN host — any plan step that touches the live host (testing verbs, running the oneshot, enabling units) must be operator-gated, never run autonomously by an executor.

</domain>

<decisions>
## Implementation Decisions

### CLI surface (TOOL-01..04)
- Single bash CLI at `scripts/silicom-bypass` wrapping `bpctl_util`.
- Subcommands this phase: `status [pair|all]`, `on <pair>`, `off <pair>`, `disc <pair>`, `conn <pair>`, `mark <label>`.
- `status` reads live state back from bpctl per pair (NIC / bypass / disconnect) — never cached.
- Non-bypass-capable interfaces are refused with a clear error.
- Verbs are idempotent: re-running a verb already in the target state is a no-op (exit 0, says so).
- Destructive verbs (`on`, `disc`) require `--yes`.
- A destructive op that would put BOTH pairs simultaneously into a non-NIC state additionally requires `--both-wan-confirm` (TOOL-03).
- `mark <label>` writes to the journal (retrievable via journalctl) AND appends to `/var/log/silicom-bypass-marks.log` for easy grep during test analysis (seed default: "journal only for state changes; `mark` may also write to flat log").
- All state changes log to journal.

### Boot baseline (BOOT-01)
- `silicom-bypass-init.service` (oneshot) applies to BOTH pairs, after `bpctl_mod` loads and after the `att-modem` / `att-router` / `sil-spare1` / `sil-spare2` interfaces exist:
  - `set_dis_bypass off`
  - `set_bypass_pwoff on`
  - `set_bypass_pwup off`
  - `set_disc_pwup off`
  - `set_std_nic off`
- Each setting is read back and asserted after apply; any mismatch fails the unit loudly (non-zero exit, journal error).
- Reconcile with the existing `deploy/systemd/bpctl-silicom.service` (module load/init) rather than duplicating its job — extend/replace coherently, do not leave two competing boot units with overlapping responsibilities.

### Reconciliation (not rebuild)
- Existing scripts `wanctl-bpctl-{init,dkms-install,watchdog-petter,watchdog-bypass}` and unit `bpctl-silicom.service` are the starting surface. Reuse/absorb their logic; do not create a parallel second implementation of the same job.
- Watchdog petter/bypass scripts and watchdog units (`silicom-bypass-watchdog@.service`, `silicom-bypass-watchdog-cake-autorate-att.service`) are out of scope here beyond not breaking them — their reconciliation is Phase 236.

### Config
- `/etc/silicom-bypass.conf` with `PAIRS="att-modem sil-spare1"` (master interface per pair), plus `WD_TIMEOUT_MS=10000`, `HEARTBEAT_MS=3000` reserved for Phase 236 consumption.
- Pair-to-interface mapping lives in config, not hardcoded in the CLI.

### Safety / SAFE-16
- Zero controller-path source diff at the phase boundary, verified (e.g. `git diff` over the protected file list), not assumed.
- This phase ships scripts/units/docs/tests only.
- Any live-host verification step in plans must be marked operator-gated (`autonomous: false` or explicit checkpoint), with rollback path = restore NIC mode on both pairs.

### Claude's Discretion
- bpctl_util output parsing strategy and exact read-back assertion mechanics.
- Unit ordering/dependency expression (After=/Wants=/udev settle vs. polling loop with timeout) for interface existence.
- Shellcheck/test approach for the bash CLI (repo has bats/pytest conventions to discover).
- Exact error message wording and exit codes.
- Whether `silicom-bypass-init.service` ExecStart calls the CLI (`silicom-bypass baseline`-style subcommand) or a dedicated script — prefer whichever keeps a single source of truth for bpctl invocations.

</decisions>

<assumptions>
## Auto-Resolved Open Questions (recorded as assumptions, not operator decisions)

Resolved conservatively per seed "Recommended Defaults" because discuss-phase was skipped:

1. **Warm-reboot bypass preservation test (seed open question):** NOT automated in this phase. If a plan includes it at all, it is a documented operator-run procedure against the Spectrum pair (`sil-spare1`) only — ATT is the canary in other workstreams. Default: document, don't execute.
2. **Expose bypass state via wanctl health endpoint:** NO for this phase. Observability coupling is deferred; keeping it out preserves the "tooling only, zero controller-path diff" boundary (SAFE-16).
3. **Installer:** Do NOT couple bypass tooling installation to the wanctl release/restart path. Extend the existing deploy file-list mechanism (deploy.sh already carries silicom watchdog units and checks for `/usr/local/sbin/wanctl-bpctl-*`) or provide a small dedicated install step — but deployment to the live host remains an operator-gated action, not an automatic effect of this phase.
4. **`mark` destination:** journal + flat log append (seed default explicitly permits the flat log).
5. **`arm`/`disarm` subcommands:** listed in the seed's Phase A CLI sketch but deferred to Phase 236 — the roadmap maps watchdog scope (WDOG-01..03) to Phase 236 and Phase 235 requirements are TOOL-01..04 + BOOT-01 only. The CLI should not block Phase 236 from adding them (subcommand dispatch must be extensible).

</assumptions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Hardware behavior / settled constraints
- `docs/SILICOM-BYPASS.md` — full hardware RCA; settled: NO unpowered fail-open on this platform (monostable relays, AuxCurrent=0mA); do not retest.

### Existing surface to reconcile (not rebuild)
- `scripts/wanctl-bpctl-init` — current bpctl init logic
- `scripts/wanctl-bpctl-dkms-install` — DKMS driver install
- `scripts/wanctl-bpctl-watchdog-petter`, `scripts/wanctl-bpctl-watchdog-bypass` — watchdog runtime scripts (Phase 236 scope; do not break)
- `deploy/systemd/bpctl-silicom.service` — existing boot unit
- `deploy/systemd/silicom-bypass-watchdog@.service`, `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` — existing watchdog units (Phase 236 scope)
- `scripts/deploy.sh` — deploy file list + bpctl script presence checks (lines ~70, ~497)
- `scripts/install.sh` — install flow

### Planning artifacts
- `.planning/seeds/SEED-006-v145-silicom-bypass-tooling-and-harness.md` — seed with deliverable details and defaults
- `.planning/ROADMAP.md` — Phase 235 section (success criteria are the contract)
- `.planning/REQUIREMENTS.md` — TOOL-01..04, BOOT-01, SAFE-16 texts

</canonical_refs>

<specifics>
## Specific Ideas

- Baseline semantics (from seed): bypass relay engages on power loss (`set_bypass_pwoff on`) but boots into NIC mode (`set_bypass_pwup off`) with link connected (`set_disc_pwup off`); bypass-on-disconnect disabled; std-NIC mode disabled.
- Both WANs (ATT and Spectrum) run through the Silicom card since 2026-04-28; pairs are `att-modem`/`att-router` and `sil-spare1`/`sil-spare2`.
- bpctl operations are addressed via the master interface of each pair.
- Card state is scriptable in milliseconds from a single SSH session — the CLI is the only sanctioned mutation path going forward; raw `bpctl_util` hand-typing is what this phase retires.

</specifics>

<deferred>
## Deferred Ideas

- Watchdog arm/disarm verbs + watchdog unit reconciliation → Phase 236 (WDOG-01..03)
- HIL test harness (`silicom-test`, scenarios, result capture) → Phase 237 (HARN-*)
- Health-endpoint bypass-state observability → future milestone (explicitly out of this phase)
- Warm-reboot bypass preservation live test → operator-run, documented procedure only
- Unpowered fail-open retest → permanently settled, out of scope per RCA

</deferred>

---

*Phase: 235-bypass-operator-cli-boot-baseline*
*Context gathered: 2026-06-12 via Seed Express Path (operator-directed, discuss-phase skipped)*
