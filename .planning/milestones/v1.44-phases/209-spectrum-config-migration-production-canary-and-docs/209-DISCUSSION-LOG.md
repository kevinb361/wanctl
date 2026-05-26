# Phase 209: Spectrum config migration, production canary, and docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 209-spectrum-config-migration-production-canary-and-docs
**Areas discussed:** SAFE-08 ATT-whitelist mode, Wash readback validation scope, Canary ritual sequencing, BRIDGE_QOS.md structure

---

## SAFE-08 ATT-whitelist mode

### Q1: How should ATT config byte-identity verification be wired into the SAFE-09 closeout gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing script | Add `--att-config-whitelist` mode to `scripts/check-safe07-source-diff.sh`. Same fail-closed semantics, one entry point, reuses HRDN-01 dirty-tree pre-check. | ✓ |
| Sibling check-safe08-att-config.sh | New script dedicated to TOPO-03/SAFE-08; duplicates ref-resolution and dirty-tree pre-check. | |
| Python core + thin shell wrapper | Mirror Phase 206's pattern: `safe08_att_config.py` + .sh wrapper; most testable, biggest cost. | |

**User's choice:** Extend existing script
**Notes:** Reuses HRDN-01 fail-closed infrastructure already in place; single SAFE-invariant entry point.

### Q2: What is the v1.43-close reference for ATT byte-identity comparison?

| Option | Description | Selected |
|--------|-------------|----------|
| `6508d68` (v1.43 close) | Per ROADMAP SAFE-09 spec; same ref as controller source diff. | ✓ |
| Latest tag matching `v1.43.*` | Resolve at runtime via git describe; more resilient if 6508d68 is rebased. | |
| `PHASE_209_ATT_REF` env override only | Force operator to pass ref; fail-closed if absent. | |

**User's choice:** `6508d68`
**Notes:** Matches ROADMAP anchor for the whole SAFE invariant set.

### Q3: What is the scope of files covered by the ATT-config whitelist?

| Option | Description | Selected |
|--------|-------------|----------|
| `configs/att.yaml` only | Matches ROADMAP success criterion 1 wording; tightest interpretation. | ✓ |
| `configs/att.yaml` + `configs/examples/att-*.yaml` | Covers operator-facing examples; adds friction. | |
| Any file matching `configs/att*.yaml` | Glob-based; catches future ATT variants automatically. | |

**User's choice:** `configs/att.yaml` only

### Q4: What is the failure mode when ATT byte-identity drifts?

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed: exit 1 + block closeout | Matches SAFE-07/HRDN-01 precedent. | ✓ |
| Warn + continue (operator override) | Print diff to stderr but exit 0 unless `PHASE_209_STRICT=1`. | |
| Fail-closed with documented exception path | Default fail-closed but accept signed exception file. | |

**User's choice:** Fail-closed: exit 1 + block closeout

---

## Wash readback validation scope

### Q1: Should wash readback validation be symmetric or opt-in?

| Option | Description | Selected |
|--------|-------------|----------|
| Symmetric: validate both wash and nowash | ATT asserts wash bit NOT set; Spectrum asserts IS set. | ✓ |
| Opt-in: only validate when `allow_wash=true` | Only Spectrum-style deployments get enforcement. | |
| Symmetric, but ATT-side as warning only | Spectrum hard-asserts; ATT logs warning on mismatch. | |

**User's choice:** Symmetric: validate both wash and nowash
**Notes:** Complements SAFE-08 YAML check with a behavioral runtime assertion.

### Q2: How should a wash readback mismatch be handled at controller startup / health?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard error: refuse to start / degrade `/health` | Matches existing readback validation pattern. | ✓ |
| Log + continue with degraded `/health` flag | Controller continues, exposes `wash_readback_mismatch=true`. | |
| Startup-only check, ignore at runtime | Validate once at boot; don't re-check mid-run. | |

**User's choice:** Hard error: refuse to start / degrade `/health`

### Q3: Test fixture source for wash readback validation tests?

| Option | Description | Selected |
|--------|-------------|----------|
| Synthesize netlink/tc dumps in tests | Minimal qdisc-state dicts in pytest; aligns with Phase 205 style. | ✓ |
| Capture real dumps from cake-shaper, commit as fixtures | Most realistic; risks brittleness across iproute2 versions. | |
| Both: synth for unit, captured for one integration test | Synth broadly; one captured-from-prod integration test pin. | |

**User's choice:** Synthesize netlink/tc dumps in tests

### Q4: Does Phase 209 also add a wash-presence assertion to existing readback CLI/check tool, or only controller-internal?

| Option | Description | Selected |
|--------|-------------|----------|
| Controller-internal only | Wire wash into `build_expected_readback()` + `_VALIDATE_KEY_TO_TCA`. | ✓ |
| Also expose via `wanctl-check` or operator-summary | Operator-callable command; adds surface area. | |
| Controller-internal + `/health` flag | Internal validation + `wash_readback_ok` bool in `/health`. | |

**User's choice:** Controller-internal only
**Notes:** Smallest blast radius; matches ROADMAP "live readback validates" wording.

---

## Canary ritual sequencing

### Q1: What is the predeploy gate's baseline source?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 206 golden fixture (committed) | Operator-accepted 2026-04-29 NDJSON, SHA256 `68f99440…`. | ✓ |
| Fresh pre-migration capture | Brand-new soak on cake-shaper just before reconcile. | |
| Both: golden as primary, fresh as confounder check | Most rigorous; most ceremony. | |

**User's choice:** Phase 206 golden fixture (committed)
**Notes:** Deterministic, reproducible, validated through Phase 206 gap closures.

### Q2: When is Snapshot A captured relative to the predeploy gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Before predeploy gate runs | Pure rollback-clean snapshot; matches Phase 201-15. | ✓ |
| After predeploy gate passes | Only snapshot once approved-for-deploy. | |
| Both: A-pre (rollback) + A-gate (approved) | Two A-snapshots; cleanest forensics, doubles overhead. | |

**User's choice:** Before predeploy gate runs

### Q3: When does the 1.43.0 → 1.44.0 version bump commit land?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-deploy (single closeout commit) | Bump alongside YAML flip, before canary deploy. | ✓ |
| Post-canary-pass commit | Only bump after 24h soak verdict passes. | |
| Two commits: bump pre-deploy, ship-tag post-pass | Separate code state from release tagging. | |

**User's choice:** Pre-deploy (single closeout commit)
**Notes:** Binary deployed for canary IS 1.44.0; rollback restores 1.43.0 via Snapshot A.

### Q4: What is the 24h soak's comparison target for verification?

| Option | Description | Selected |
|--------|-------------|----------|
| v1.43 baseline `20260509T183037Z` via Phase 206 harness | Per ROADMAP success criterion 2; deterministic. | ✓ |
| Snapshot A live capture (pre-reconcile) as comparator | Same-day pre-reconcile soak as A-leg. | |
| Both: v1.43 baseline as primary, A-snapshot as secondary | Most informative; most operator interpretation surface. | |

**User's choice:** v1.43 baseline `20260509T183037Z` via Phase 206 harness

---

## BRIDGE_QOS.md structure

### Q1: What is the structural form of `docs/BRIDGE_QOS.md`?

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone new doc + cross-links | Focused doc; CONFIGURATION.md gets a one-paragraph entry linking out. | ✓ |
| Section in CONFIGURATION.md, no new doc | All content in CONFIGURATION.md; conflicts with ROADMAP naming. | |
| Standalone doc + duplicated CONFIGURATION.md section | Both files carry full coverage; drift risk. | |

**User's choice:** Standalone new doc + cross-links
**Notes:** Matches ROADMAP's explicit `docs/BRIDGE_QOS.md` naming.

### Q2: What scope does BRIDGE_QOS.md cover?

| Option | Description | Selected |
|--------|-------------|----------|
| Topology rationale + `allow_wash` operator guide | DSCP-across-ISP + per-WAN decision guide; Spectrum-vs-ATT contrast. | ✓ |
| Above + diffserv4 vs besteffort tradeoff matrix | Side-by-side decision matrix; broader scope. | |
| Above + historical migration narrative | Also include v1.43→v1.44 migration why-now. | |

**User's choice:** Topology rationale + `allow_wash` operator guide

### Q3: Primary audience and tone for BRIDGE_QOS.md?

| Option | Description | Selected |
|--------|-------------|----------|
| Operator-facing, decision-driving | Reader is deciding `allow_wash` for a new WAN; CONFIGURATION.md tone. | ✓ |
| Architecture/rationale-facing | Reader is contributor/auditor; ARCHITECTURE.md tone. | |
| Hybrid: operator TL;DR + deep-dive section | Decision flowchart up top, theory below. | |

**User's choice:** Operator-facing, decision-driving

### Q4: CHANGELOG.md treatment for the migration?

| Option | Description | Selected |
|--------|-------------|----------|
| v1.44.0 heading + new BRIDGE_QOS link | Match v1.43-dev pattern; single entry point. | ✓ |
| Above + inline DSCP rationale paragraph | Boosts discoverability; duplicates BRIDGE_QOS.md content. | |
| Minimal: keys-changed bullet list, link to BRIDGE_QOS for context | Cleanest separation; risk: scanners miss topology context. | |

**User's choice:** v1.44.0 heading + new BRIDGE_QOS link

---

## Claude's Discretion

- Exact prose of BRIDGE_QOS.md (operator-decision-driving tone is the constraint; phrasing is open)
- Exact CONFIGURATION.md `allow_wash` entry text and section placement
- Test layout for symmetric wash readback (one file vs split — follow nearest existing readback-test convention)
- Phase 206 harness invocation flags for verification A/B run (Phase 206 docs are source of truth)

## Deferred Ideas

- Operator-visible `/health` wash flag — reconsider in future observability phase if wash drift becomes a recurring forensic question
- Rollback-trigger authority (auto vs operator-gated) — separate operability discussion, not Phase 209 scope
- `wanctl-check` / operator-summary wash surface — future TOOL phase if needed
- CONFIGURATION.md broader cleanup — its own phase
- Diffserv4-vs-besteffort tradeoff matrix doc — could land as separate architecture-facing doc later
- Historical migration narrative in BRIDGE_QOS.md — ages out fast; archive-only value
