# Phase 209: Spectrum config migration, production canary, and docs - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Flip Spectrum to topology-correct CAKE (`ceiling_mbps: 920`, `diffserv: besteffort`, `allow_wash: true`) in production behind the two-snapshot rollback ritual, prove post-migration soak distribution matches or improves on the v1.43 baseline (`20260509T183037Z`), keep ATT byte-identical to v1.43 close (`6508d68`), wire `wash` into controller-internal readback validation, publish `docs/BRIDGE_QOS.md` plus CHANGELOG / CONFIGURATION.md updates, and close SAFE-08 / SAFE-09 mechanically. Version bumps 1.43.0 → 1.44.0 across `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile`.

**In scope:** TOPO-03 (Spectrum YAML migration + ATT byte-identity), TOPO-06 (two-snapshot rollback canary + 24h soak A/B vs v1.43 baseline via Phase 206 harness), TOPO-07 (BRIDGE_QOS.md + CHANGELOG + CONFIGURATION.md), SAFE-08 (ATT-config whitelist verification), SAFE-09 (end-to-end control-path source-diff closeout, wash readback validation in `build_expected_readback()` + `_VALIDATE_KEY_TO_TCA`), version bump.

**Out of scope:** Any controller threshold/algorithm/EWMA/dwell/deadband/burst change (SAFE-09). Any ATT config or ATT-specific code path change (SAFE-08). New observability surfaces beyond what wash readback strictly requires. Any second migration target (only Spectrum). Anything blocked by SEED-002…SEED-005 (D-14 successor work — deferred to v1.45+).

</domain>

<decisions>
## Implementation Decisions

### SAFE-08 ATT-whitelist mode
- **D-01:** Extend `scripts/check-safe07-source-diff.sh` with a new `--att-config-whitelist` mode rather than introducing a sibling script or Python+shell pair. Single entry point for SAFE invariants, reuses HRDN-01 dirty-tree pre-check (unstaged + staged + untracked), reuses ref-resolution semantics. Lowest closeout-wiring cost.
- **D-02:** Reference SHA baked into the script default is `6508d68` (v1.43 close), matching SAFE-09 controller-source diff anchor and ROADMAP wording. Operator may override via positional arg or `PHASE_209_ATT_REF` env. No git-describe runtime resolution.
- **D-03:** Scope of byte-identity comparison is `configs/att.yaml` only. Examples (`configs/examples/att-*.yaml`) are NOT covered by SAFE-08 — they may evolve as documentation without breaking the invariant.
- **D-04:** Failure mode is fail-closed (exit 1, blocks Phase 209 closeout). No warn-and-continue, no documented-exception escape hatch. Matches HRDN-01 / SAFE-07 precedent; drift means stop.

### Wash readback validation scope
- **D-05:** Validation is symmetric: ATT (`allow_wash=false`) asserts the wash bit is NOT set in readback; Spectrum (`allow_wash=true`) asserts it IS set. Catches accidental ATT-side wash regressions at runtime, complementing SAFE-08's YAML-level check. Strengthens SAFE-08 with a behavioral assertion rather than just a config-diff assertion.
- **D-06:** Mismatch is a hard error at controller startup. Controller refuses to start (matches existing readback validation patterns) so operators reconcile before any traffic moves under drifted qdisc state. No /health-only soft signal, no "validate once, ignore at runtime" mode.
- **D-07:** Test fixtures are synthesized in pytest — minimal qdisc-state dicts shaped to what `build_expected_readback()` emits, matching Phase 205's tin-aggregation test style (synth diffserv4 and besteffort tin sets). No committed real-kernel netlink/tc captures; no integration-fixture pinning. Avoids brittleness across iproute2/kernel versions.
- **D-08:** Surface is controller-internal only. Wash readback is wired into the existing in-process validation path (`build_expected_readback()` + `_VALIDATE_KEY_TO_TCA`). No new CLI subcommand, no /health JSON addition, no operator-summary surface. Smallest blast radius; matches ROADMAP wording ("live readback validates the new qdisc state").

### Canary ritual sequencing
- **D-09:** Predeploy gate baseline is the Phase 206 committed golden NDJSON fixture (operator-accepted 2026-04-29 substitute for the missing 2026-04-22 finding, pinned at SHA256 `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda`). No fresh pre-migration capture. Deterministic, reproducible, validated through Phase 206 gap closures.
- **D-10:** Snapshot A (rollback-clean reference) is captured BEFORE the predeploy gate runs. A is the unconditional rollback target — `/opt/wanctl`, `/etc/wanctl/spectrum.yaml`, `/health.version`, deployment token. Matches Phase 201-15 contract: A is rollback-clean evidence; B is post-deploy evidence; the gate's outcome does not affect what A captures.
- **D-11:** Version bump `1.43.0 → 1.44.0` lands in a single closeout commit alongside the Spectrum YAML flip, BEFORE the canary deploy. The binary deployed for canary IS `1.44.0`; verdict captures that exact version; rollback restores `1.43.0` via Snapshot A. Matches Phase 198/201 precedent. Avoids temporary "1.43.x-with-1.44-YAML" intermediate state and the rollback artifact-naming confusion that would follow.
- **D-12:** 24h verification soak compares against the v1.43 baseline soak `20260509T183037Z` (corrected-boundary CALIB-01 rerun) via the Phase 206 A/B replay harness, with the new post-migration soak as the B-leg. Zone × cause-tag distributions per ROADMAP success criterion 2. The Phase 206 rollback gates (5% p99 latency / 10% restart-rate / 10% pressure-transition-rate, fail-closed) are the binding comparator. Snapshot A live capture is NOT used as the comparator basis.

### BRIDGE_QOS.md structure
- **D-13:** `docs/BRIDGE_QOS.md` is a new standalone doc. CONFIGURATION.md gets a focused `allow_wash` entry that cross-links to BRIDGE_QOS.md rather than carrying duplicate topology content. CHANGELOG.md references the new doc. Matches ROADMAP's explicit `docs/BRIDGE_QOS.md` naming and prevents drift between two source-of-truth docs.
- **D-14:** Scope of BRIDGE_QOS.md is topology rationale + per-WAN `allow_wash` operator guide. Covers: why DSCP doesn't survive most consumer ISP topologies (DOCSIS CMTS, transparent CPE behavior), when besteffort beats diffserv4 in practice, how to decide `allow_wash` per WAN, concrete Spectrum-vs-ATT contrast as the worked example. NOT a diffserv4-vs-besteffort tradeoff matrix and NOT a historical migration narrative — both age out fast and dilute the operator-decision focus.
- **D-15:** Primary audience is the operator deciding `allow_wash` for a new WAN. Tone matches CONFIGURATION.md / RUNBOOK.md — decision-driving, lead with "how to decide", end with "why". Short examples; explicit Spectrum (`allow_wash: true`, besteffort) vs ATT (`allow_wash: false`, diffserv4) contrast.
- **D-16:** CHANGELOG.md treatment is a dedicated `v1.44.0` heading (matching v1.43-dev pattern from Phase 202-04) noting `allow_wash` knob, besteffort/wash semantics shift on Spectrum, `ceiling_mbps: 940→920`, and an explicit link to `docs/BRIDGE_QOS.md`. No inline DSCP-rationale paragraph in CHANGELOG (avoids duplication with BRIDGE_QOS.md).

### Refinements (post-pattern-mapping, 2026-05-18)
- **D-17 (refines D-06):** The D-06 hard-fail on wash readback mismatch lives **inside the backends' `validate_cake()` methods** (`src/wanctl/backends/netlink_cake.py` and `src/wanctl/backends/linux_cake.py`), raising on wash-specific mismatch. `linux_cake_adapter.py:344` is NOT modified and is NOT added to the SAFE-09 allowlist. The wash-specific raise is the smallest delta; broader readback-mismatch behavior remains unchanged (soft-signal preserved for other params). Both backends are already in the SAFE-09 allowlist, so no allowlist expansion is required.
- **D-18 (refines D-05):** The "always-emit-wash for ATT" policy lives in **`build_cake_params`** (`src/wanctl/cake_params.py`). When `allow_wash` is false, `build_cake_params` emits `wash: False` into the params dict (mirroring the explicit-False precedent at `netlink_cake.py:478`). `build_expected_readback` remains a pure pass-through transform — no default-emission logic added there. Preserves the existing "build_cake_params owns policy, transforms own transform" separation.
- **D-19 (wave-merge / commit-shape policy, post-checker-review 2026-05-18):** Plans 209-01, 209-02, and 209-03 each ship as their OWN commit on plan completion. Plan 209-04's closeout commit contains EXACTLY 5 files: `configs/spectrum.yaml` + `pyproject.toml` + `src/wanctl/__init__.py` + `docker/Dockerfile` + `CHANGELOG.md` (date flip). No bundling of upstream-plan work into the 209-04 closeout commit. This locks D-11's "single closeout commit" shape and resolves the checker-flagged hedging in Plan 04. The 209-02 default-mode allowlist expansion (Plan 02 Task 3) ships in 209-02's own commit BEFORE 209-04 runs, so 209-04 Task 4b's SAFE-09 mechanical gate has the v1.44 allowlist available as a real exit-0 verifier.
- **D-20 (closes TOPO-05 fail-open on `inf` window-hours, post-review 2026-05-19):** Path-a (code fix). `scripts/phase206-gate-check.py:339` accepts `--window-hours=inf` because `inf > 0` is `True` (the existing `is None or <= 0` guard catches `nan` but not `inf`). Phase 209-02 adds a one-line `math.isfinite(args.window_hours)` guard plus a pytest `inf`-window wrapper case. This is a Phase 206 script extension (cross-phase tooling, `scripts/` only); SAFE-09 control-path allowlist is unaffected. The fix ships in 209-02's own commit per D-19. TOPO-05 remains formally owned by Phase 206 — Phase 209-02 closes the gap mechanically without taking on the requirement.

### Claude's Discretion
- Exact prose of BRIDGE_QOS.md — operator-decision-driving tone is the constraint; phrasing is open.
- Exact CONFIGURATION.md `allow_wash` entry text and section placement (under `cake_params` block) — planner/executor's call.
- Test layout for symmetric wash readback (one file vs split) — follow nearest existing readback-test convention.
- Phase 206 harness invocation flags for the verification A/B run — Phase 206 docs are the source of truth.
- Whether to add a `phase209_expected_counts` pin block to `tests/test_phase_195_replay.py` for the new wash readback line counts — PATTERNS.md recommends yes per Phase 202-03 / 204-02 precedent; planner's call to wire concretely.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements
- `.planning/ROADMAP.md` §"Phase 209: Spectrum config migration, production canary, and docs" — success criteria 1–5
- `.planning/ROADMAP.md` §"Cross-Cutting Notes" — SAFE-08/09 cadence, harness-before-deploy ordering, HRDN-01 dependency, ATT-untouched invariant
- `.planning/REQUIREMENTS.md` — TOPO-03, TOPO-06, TOPO-07, SAFE-08, SAFE-09
- `.planning/PROJECT.md` — current milestone context (v1.44 Topology-Correct CAKE)

### Prior-phase artifacts that bind Phase 209
- `.planning/phases/205-tin-agnostic-cake-signal-allow-wash-gate/205-04-PLAN.md` — emission-only contract; readback explicitly deferred to Phase 209
- `.planning/phases/206-a-b-replay-harness-rollback-gates/206-02-PLAN.md` — predeploy rollback-gate Python core + thresholds JSON
- `.planning/phases/206-a-b-replay-harness-rollback-gates/206-03-PLAN.md` — operator-readable rollback doc; golden fixture provenance (SHA256 `68f99440…`)
- `.planning/phases/206-a-b-replay-harness-rollback-gates/206-04-PLAN.md` — SAFE-09 phase-boundary verification pattern (committed/staged/unstaged/untracked surfaces)
- `.planning/phases/207-soak-harness-hardening-v1-43-closeout-routed/` — HRDN-01 fail-closed source-diff verifier (SAFE-09 closeout dependency)
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/` — two-snapshot rollback ritual reference implementation (Plan 201-15 / 201-16)

### Code touched by Phase 209
- `configs/spectrum.yaml` — `ceiling_mbps: 940→920`, `diffserv: diffserv4→besteffort`, `allow_wash: true`
- `configs/att.yaml` — MUST be byte-identical to `6508d68`; SAFE-08 enforces
- `scripts/check-safe07-source-diff.sh` — extended with `--att-config-whitelist` mode
- `scripts/phase206-predeploy-gate.sh` + `scripts/phase206-predeploy-gate.py` + `scripts/phase206-thresholds.json` — used as predeploy gate input (not modified)
- `src/wanctl/backends/netlink_cake.py` — `_VALIDATE_KEY_TO_TCA` gains wash entry, `build_expected_readback()` emits wash
- `src/wanctl/backends/linux_cake.py` — wash readback parsing path for tc-CLI deployments (mirror netlink coverage)
- `src/wanctl/__init__.py` — `__version__ = "1.44.0"`
- `pyproject.toml` — `version = "1.44.0"`
- `docker/Dockerfile` — version label bump
- `docs/BRIDGE_QOS.md` — new file
- `docs/CONFIGURATION.md` — `allow_wash` entry + BRIDGE_QOS link
- `CHANGELOG.md` — v1.44.0 heading

### Reference SHAs
- `6508d68` — v1.43 close commit; SAFE-08 ATT byte-identity reference and SAFE-09 controller-source-diff reference
- Golden fixture SHA256 `68f99440bd41be646dfa64abe77380791d4b2dd7b09722588c808e9749c0bbda` — Phase 206 predeploy gate baseline

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/check-safe07-source-diff.sh`** (v1.43-shipped via Phase 203, hardened by Phase 207 HRDN-01) — already has fail-closed dirty-tree pre-check (unstaged/staged/untracked) and operator-overridable ref via positional arg + env. Adding a `--att-config-whitelist` mode preserves all of that infrastructure; only the comparison target changes.
- **Phase 206 predeploy gate** (`scripts/phase206-predeploy-gate.sh` + `.py` + `phase206-thresholds.json`) — operator-callable, fail-closed, supports post-soak mode. Phase 209's canary calls this verbatim; no script change.
- **Phase 206 A/B replay harness** — already emits schema-v1 A/B summary JSON; one-line consumer-change away from Phase 209 verification soak comparator.
- **Phase 201-15 two-snapshot pattern** — Snapshot A as rollback-clean (`/opt/wanctl-prephase201-*.tar.gz` + `/etc/wanctl/spectrum.yaml.prephase201-*`) is the template for Phase 209 Snapshot A artifact naming (substitute "prephase209").

### Established Patterns
- **`_VALIDATE_KEY_TO_TCA` mapping** (`src/wanctl/backends/netlink_cake.py:69`) — config-key → netlink TCA constant. Phase 209 adds the wash entry here.
- **`linux_cake.py` boolean-flag emission** (lines 396–402) — handles `split-gso`/`ack-filter`/`ingress`/`wash`, emits explicit `nowash` when `wash` is present and false. Mirrors `no-ack-filter`; pattern is in place. Readback parsing must reverse this.
- **`allow_wash` strict-is-True parsing** (Phase 205-03 decision) — string/operator typos do not truthily bypass D-08 wash protection. Phase 209 readback validation inherits this.
- **SAFE-05 expected-counts drift pinning** — Phase 209 will likely need a pin block adjustment for the new wash readback code paths; follow the Phase 202-03 / 204-02 pattern of pinning exact line counts.
- **Two-snapshot artifact naming** (Phase 198-01 / 201-11) — `/opt/wanctl-prephase{N}-{ISO8601}.tar.gz` + `/etc/wanctl/spectrum.yaml.prephase{N}-{ISO8601}` is the established rollback artifact contract.

### Integration Points
- Wash readback wires into the existing controller startup validation path (call site of `build_expected_readback()`).
- SAFE-09 closeout calls extended `check-safe07-source-diff.sh --att-config-whitelist` from Phase 207's HRDN-01 verifier chain — no new top-level invocation.
- CHANGELOG `v1.44.0` heading lands in the same closeout commit as the YAML flip and version bump.
- Phase 206 predeploy gate runs against committed golden fixture as A-leg; no new corpus loader work.

</code_context>

<specifics>
## Specific Ideas

- **Two-snapshot rollback artifact naming:** `/opt/wanctl-prephase209-{ISO8601}.tar.gz` + `/etc/wanctl/spectrum.yaml.prephase209-{ISO8601}` — directly inherits Phase 201-11 / 198-01 naming convention.
- **`allow_wash` is per-WAN, default false** — Spectrum sets `allow_wash: true`; ATT keeps the default false and stays out of the wash code path. BRIDGE_QOS.md must make this Spectrum-vs-ATT contrast concrete.
- **Phase 206 golden fixture is the binding baseline**, not a fresh capture. ROADMAP language "post-migration soak evidence matches or improves on the v1.43 baseline distribution" binds to `20260509T183037Z` (corrected-boundary CALIB-01 rerun), not to any same-day pre-reconcile capture.
- **Phase 209 owns wash readback** — Phase 205-03 explicitly deferred `build_expected_readback()` and `_VALIDATE_KEY_TO_TCA` wash entries to Phase 209. Plan must cite Phase 205-03 closeout in the wash-readback work item to make the handoff explicit.

</specifics>

<deferred>
## Deferred Ideas

- **Operator-visible `/health` wash flag** — surfacing `wash_readback_ok` in `/health` JSON came up under the wash-validation question; decided controller-internal only for Phase 209. Reconsider in a future observability phase if wash drift becomes a recurring forensic question.
- **Rollback-trigger authority (auto vs operator-gated)** — Phase 209 inherits operator-gated verdicts per Phase 198/201 precedent. Automating rollback on Phase 206 gate-failure is a separate operability discussion, not Phase 209 scope.
- **`wanctl-check` / operator-summary wash surface** — adding an operator-callable wash-status command came up; deferred. Belongs in a future TOOL phase if needed.
- **CONFIGURATION.md broader cleanup** — only the `allow_wash` entry lands in Phase 209. Any wider CONFIGURATION.md reorganization is its own phase.
- **Diffserv4-vs-besteffort tradeoff matrix doc** — considered for BRIDGE_QOS.md scope; deferred to keep that doc operator-decision-driving. Could land as a separate architecture-facing doc later if needed.
- **Historical migration narrative in BRIDGE_QOS.md** — considered and deferred (ages out fast; archive-only value).

</deferred>

---

*Phase: 209-spectrum-config-migration-production-canary-and-docs*
*Context gathered: 2026-05-18*
