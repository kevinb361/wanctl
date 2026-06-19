# Phase 240: Config + Validator - Context

**Gathered:** 2026-06-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the RTT measurement backend operator-selectable in YAML and validate it
safely, with zero migration. Deliver three requirements:

1. **CFG-01** — Operator can set `measurement.backend: icmplib|fping` per
   WAN/consumer; an absent key resolves to `icmplib`.
2. **CFG-02** — The config validator rejects unknown backend values (ERROR) and
   WARNs (does not fail) when `fping` is selected but the binary is absent.
3. **CFG-03** — All existing deployment configs validate unchanged; no migration.

Plus the SAFE-17 boundary: config/validator wiring is inside the v1.53 allowlist;
no controller-path drift (state machine, thresholds, EWMA, dwell, deadband,
arbitration, fusion).

**Not in scope:** the fping backend itself and its sub-params (reflectors,
cadence, `-S` binding) — Phase 241; the backend factory + loud runtime fallback —
Phase 242; `/health` backend/source_ip attribution — Phase 244; reviving
steering's pinger construction site — Phase 242/245. This phase only adds the
**config key + validation**; the key is inert (resolves icmplib, nothing reads a
non-default value yet) until 242 wires the construction sites.

</domain>

<decisions>
## Implementation Decisions

### Consumer Scope (CFG-01 "per WAN/consumer")
- **D-01:** Wire `measurement.backend` + validation into **both** validators now —
  `check_config_validators.py` (autorate) and `check_steering_validators.py`
  (steering). Selection **A** was ratified in Phase 238
  (`238-PROVENANCE-MAP.md:13`), which makes steering a real RTT consumer once its
  dead `RTTMeasurement` (`daemon.py:2554`) is revived in Phase 242. The key is
  **additive and inert** until then — `absent → icmplib` means zero behavior
  change in either consumer regardless. Defining it in both validators now means
  Phase 242/245 only *consume* an already-validated key instead of also touching
  the validator (tighter per-phase SAFE-17 surface downstream). Per-WAN is already
  satisfied by wanctl's one-config-file-per-WAN layout.

### Key Shape / Placement
- **D-02:** **Minimal.** Register only the `measurement.backend` scalar (enum
  `icmplib|fping`) under a new top-level `measurement:` block. The block name
  matches the CFG-01 literal dotted path and the `/health` `measurement` block
  naming (Phase 244 consistency). Do **not** stub fping sub-params now — reflector
  list, cadence, and source binding have no validation semantics until Phase 241
  builds the backend, and 241 will touch the registry then anyway. YAGNI keeps the
  240 allow-list addition tight.

### fping-Absent Handling (CFG-02 WARN)
- **D-03:** The validator probes `shutil.which("fping")` at validate time and
  emits a **non-gating WARN** (a Severity that never fails the check) when
  `backend: fping` is selected but the binary is missing. **Document the
  env-dependence explicitly:** the probe reflects whichever host runs
  `check_config`, which may differ from the deploy target — so the validator WARN
  is **advisory**. The *authoritative* "binary absent" guarantee is the loud,
  observable runtime fallback in Phase 242 (FALL-01: WARN-once + fallback counter +
  `/health` attribution). 240 satisfies CFG-02 literally without pretending the
  validator host equals the prod host.

### CFG-03 Backward-Compat Evidence
- **D-04:** **Both** proof layers:
  1. **Real-config regression** — run the validator against the committed real
     YAMLs (`examples/`, `etc/`, `deploy/` configs that mirror prod) and assert
     **zero new warnings/errors** with `measurement.backend` absent. This is the
     direct "no deployment breaks" proof.
  2. **Unit fixtures for the 3 decision vectors** — (a) unknown value → ERROR,
     (b) `fping` + binary absent → WARN (non-gating), (c) absent key → silent
     `icmplib` resolution (no warning). Hermetic branch coverage of the new logic.
- **D-04a (registry requirement):** `measurement.backend` MUST be added to
  `KNOWN_AUTORATE_PATHS` (and the steering equivalent) so a *present, valid* key
  does not trip the existing "unknown key" warning — while an *absent* key
  continues to trip nothing. CFG-03 is therefore two facts: present→no
  unknown-key warning, absent→no warning→icmplib.

### Claude's Discretion
- Exact `measurement:` block nesting in the schema/`SCHEMA` field-spec mechanism,
  the precise WARN `Severity` constant reused, the enum-validation helper used for
  `icmplib|fping`, and the test file layout are at the planner/executor's
  discretion, provided D-01..D-04a hold and SAFE-17 stays green.
- Whether `icmplib|fping` enum lives as a shared constant referenced by both
  validators (vs duplicated) is open — a single source of truth is preferred but
  not mandated.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase + milestone scope
- `.planning/ROADMAP.md` — Phase 240 entry (goal, 2 success criteria, dependency
  spine: 239 seam → 240 config → 241 fping; 240/241 may overlap).
- `.planning/REQUIREMENTS.md` — CFG-01/02/03 and SAFE-17 definitions; the binding
  out-of-scope table (no controller threshold/algorithm/state-machine changes).
- `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md`
  — Selection **A** ratification (`:13`) that makes steering a live RTT consumer;
  the load-bearing reason D-01 wires both validators.

### Config + validator (the files this phase edits)
- `src/wanctl/check_config_validators.py` — autorate validator: `validate_schema_fields`,
  `validate_cross_fields`, unknown-key detection, and the `KNOWN_AUTORATE_PATHS`
  allow-list registry (`measurement.backend` must be registered here — D-04a).
- `src/wanctl/check_steering_validators.py` — steering validator (second consumer
  per D-01).
- `src/wanctl/check_config.py` — validator CLI entrypoint / `CheckResult` +
  `Severity` plumbing (the WARN severity D-03 reuses).
- `src/wanctl/autorate_config.py` — `Config(BaseConfig)`, the `SCHEMA` field-spec
  mechanism, and `_load_*` loaders; `ping_source_ip` top-level handling (`:643`)
  as the precedent for an optional top-level key resolving to a default.
- `src/wanctl/config_base.py` — `BaseConfig`, `ConfigValidationError`,
  `validate_field`, `_get_nested` (schema-validation primitives).

### Seam (Phase 239 output — the vocabulary 240 plumbs into)
- `src/wanctl/rtt_backend.py` — `RttBackend` Protocol and `RttSample.backend`
  string field (default `"icmplib"`, values `icmplib|irtt|fping`). 240 is the
  config→string path feeding this; no new runtime type is introduced.

### Backward-compat corpus (CFG-03 — D-04)
- Committed real configs under `examples/`, `etc/`, and `deploy/` — the regression
  corpus the validator must pass unchanged with the key absent.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `KNOWN_AUTORATE_PATHS` registry + `validate_schema_fields` / `validate_field` —
  the existing additive-key pattern; register `measurement.backend` and add an
  enum check rather than inventing new validation machinery.
- `CheckResult` + `Severity` (PASS/WARN/ERROR) in `check_config.py` — D-03's
  non-gating WARN and CFG-02's ERROR-on-unknown reuse these directly.
- `_load_rate_limiter_config` (`autorate_config.py:656`) — precedent for "invalid
  values log a warning and are excluded (backend defaults apply)" — analogous to
  absent/invalid `measurement.backend` resolving to the icmplib default.
- `ping_source_ip = self.data.get("ping_source_ip", None)` (`:643`) — precedent
  for an optional top-level key with a safe default; `measurement.backend` follows
  the same absent→default shape.

### Established Patterns
- One config file per WAN — "per WAN" in CFG-01 needs no special machinery; it
  falls out of the existing per-WAN config layout.
- Two separate validators (autorate + steering) — there is no shared validator
  today; D-01's "both now" either duplicates the enum/WARN logic or factors a
  shared helper (planner's discretion).

### Integration Points
- Phase 242 (factory + fallback) consumes the validated `measurement.backend`
  string at the construction sites (`autorate_continuous.py`, and steering's
  revived `daemon.py:2554` site per Selection A). 240 must leave the key in a
  shape 242 can read without re-touching the validator.
- Phase 244 (`/health` attribution) surfaces `measurement.backend` — the block
  name chosen in D-02 should stay consistent with the `/health` `measurement`
  block.
- SAFE-17 boundary verifier (Phase 239 output) runs at the 240 phase boundary —
  all 240 edits must land inside the allowlisted measurement-seam files
  (`rtt_backend.py`, config/validator wiring) and prove zero controller-path drift.

</code_context>

<specifics>
## Specific Ideas

- The `measurement.backend` enum is exactly `icmplib|fping` for 240. `irtt` exists
  as an `RttSample.backend` value (seam) but is NOT a selectable config value this
  milestone (IRTT-MIG-01 deferred) — the validator should reject `irtt` as
  unknown, same as any other unrecognized string, unless the planner deliberately
  chooses to allow-list it (default: reject, keep the selectable set to the two
  milestone backends).
- CFG-02's WARN must be genuinely non-gating: a deploy host legitimately running
  `backend: fping` should pass `check_config` even when the validator runs
  somewhere `fping` isn't installed. Gating here would block valid deployments.

</specifics>

<deferred>
## Deferred Ideas

- **fping sub-params** (reflector list, probe cadence, `-S` source binding) —
  Phase 241. Intentionally excluded from the 240 `measurement:` block (D-02).
- **Backend factory + loud runtime fallback** (FALL-01) — Phase 242; the
  authoritative "binary absent" handling D-03 points to.
- **`/health` backend/source_ip attribution** (HEALTH-01) — Phase 244.
- **`--assume-fping-present` validator override flag** — considered for the
  validator-host-vs-deploy-host mismatch; deferred as premature (one knob for a
  documented advisory WARN). Revisit only if the false WARN proves noisy in
  practice.
- **`irtt` as a selectable backend** — IRTT-MIG-01, future milestone; the seam
  carries the value but config does not expose it in v1.53.

### Reviewed Todos (not folded)
- `2026-06-04-evaluate-fping-as-wanctl-rtt-measurement-backend.md` (score 0.6) —
  the milestone driver, broader than Phase 240 (it spans the whole fping backend
  evaluation across 241/245). Informs context but is not a 240-scoped task; it is
  satisfied across the v1.53 milestone, not here.

</deferred>

---

*Phase: 240-config-validator*
*Context gathered: 2026-06-15*
