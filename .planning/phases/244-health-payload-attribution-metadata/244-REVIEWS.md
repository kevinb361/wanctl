---
phase: 244
reviewers: [codex]
reviewed_at: 2026-06-18T21:14:21Z
plans_reviewed:
  - 244-01-safe17-and-contract-scaffold-PLAN.md
  - 244-02-autorate-attribution-PLAN.md
  - 244-03-steering-attribution-PLAN.md
  - 244-04-bridge-attribution-PLAN.md
---

# Cross-AI Plan Review — Phase 244

> Single external reviewer this cycle: **Codex** (`--codex`). Gemini not installed;
> Claude skipped for independence (review invoked from inside Claude Code). Codex is a
> distinct CLI, so the independence requirement is satisfied.

## Codex Review

**Summary**

The plans are generally disciplined: narrow file scope, additive payload changes, verifier-first sequencing, and strong D-02 bridge honesty. But as written, they do not fully guarantee "every RTT sample is attributable." The main blocker is Plan 244-03: current steering RTT still comes from autorate health/IRTT/history, not the constructed wanctl backend, so stamping `rtt_source.producer="wanctl-backend"` can mislabel bridge-derived RTT as A/B backend RTT. Plan 244-02 also likely fails `source_ip` for autorate because `RttBackendHandle` does not expose `source_ip`.

**Per-Plan Assessment**

- `244-01`: Mostly sound. Cloning the 242 verifier, anchoring to `49fb1393`, adding `steering/health.py` in both allowlists, and keeping protected-body machinery is the right shape.
- `244-02`: Scope is good, but `getattr(rtt_backend_status, "source_ip", None)` will likely always return `None`; `RttBackendHandle` fields do not include `source_ip`.
- `244-03`: Highest risk. Current steering code records `autorate_health`, `autorate_irtt`, or `history_fallback`, not direct backend samples. See `src/wanctl/steering/daemon.py:1756` and `:2558`.
- `244-04`: Strong D-02 design. Literal `None` values in both bridge scripts are honest; add runtime coverage for degraded/no-state path.

**Strengths**

- SAFE-17 sequencing is good: Wave 0 verifier/tests before producer edits.
- Anchor `49fb1393` is valid and matches the last 243-prefixed commit.
- Bridge D-02 invariant is conceptually clean: `producer="cake-autorate-bridge"`, `backend=null`, `source_ip=null`.
- Plans avoid controller algorithm/timing edits and stay within observed health-builder/wiring surfaces.
- The separate `producer` field is the right contract shape for downstream A/B filtering.

**Concerns**

- **HIGH — 244-03 misattributes steering RTT.** Current steering RTT comes from autorate state, autorate IRTT, or history fallback. Adding `producer="wanctl-backend"` based on the constructed future backend can let an A/B scraper mix bridge EWMA into `producer == "wanctl-backend"` data.
- **HIGH — 244-02 autorate `source_ip` source is wrong.** `RttBackendHandle` has `backend`, `controller_measurement`, `backend_active`, etc., but no `source_ip`; see `src/wanctl/rtt_backend_factory.py:90`. Use `controller_measurement.source_ip`, add a handle field, or read the config explicitly.
- **MEDIUM — "per-sample backend" is overstated.** Plans 02/03 mostly proxy `backend_active`, not the `RttSample.backend`. That may be acceptable if renamed/declared as selected backend, but it conflicts with D-03 wording.
- **MEDIUM — byte preservation tests may not prove byte/order preservation.** Strict superset and type assertions are useful, but they do not prove existing key order or serialized shape. Since JSON is emitted with dict order, key-order assertions matter.
- **MEDIUM — bridge degraded path lacks endpoint coverage.** Plan 04 edits both healthy and degraded blocks, but the current endpoint tests exercise healthy state. Grep counts help, but runtime coverage should hit `state is None`.
- **LOW — mirror-test instructions conflict slightly.** Plan 244-01 says the 243 mirror uses `queue_controller.py`; current `tests/test_phase243_safe17_verifier.py` uses `wan_controller.py`, while the 243 script self-test uses `queue_controller.py`.

**Suggestions**

- Fix Plan 03 before execution: derive `producer/backend/source_ip` from the actual `rtt_source.current`. For `autorate_health`, `autorate_irtt`, and `history_fallback`, do not emit `producer="wanctl-backend"` unless the RTT actually came through the wanctl backend seam.
- In Plan 02, retrieve source IP via `rtt_backend_status.controller_measurement.source_ip` or add `source_ip` to `RttBackendHandle`.
- Add tests asserting incompatible combinations fail, e.g. `current="autorate_health"` must not produce `producer="wanctl-backend"` unless Phase 245 changes the source path.
- Strengthen byte-preservation tests with `list(section.keys())[:N] == old_key_order` and value/type checks for old fields.
- Add bridge no-state/degraded endpoint tests for both Spectrum and ATT.
- Document downstream scraper rules explicitly: filter on `producer == "wanctl-backend"` and `backend in {"icmplib","fping"}`, and reject/ignore contradictory combinations.

**Risk Assessment**

**HIGH as written for evidence correctness**, not controller stability. The control-path mutation risk is low because edits are narrow and SAFE-17 is well designed. The phase-goal risk is high because Plan 03 can make `/health` attribution lie about the actual RTT producer, which directly threatens Phase 245 A/B evidence. Fixing the steering attribution semantics and autorate `source_ip` source would bring this down to **MEDIUM/LOW**.

---

## Consensus Summary

Single reviewer (Codex); "consensus" reflects Codex findings weighted against the locked
Phase 244 design decisions (D-01..D-05).

### Agreed Strengths

- Verifier-first sequencing (Wave 0 SAFE-17 verifier + contract tests before producer edits).
- SAFE-17 anchor `49fb1393` validated as the last 243-prefixed commit.
- D-02 bridge honesty invariant (`producer="cake-autorate-bridge"`, `backend=null`,
  `source_ip=null`) is the right shape and structurally keeps bridge EWMA out of the A/B filter.
- Narrow file scope; no controller algorithm/timing edits.

### Agreed Concerns (highest priority)

1. **HIGH — Steering attribution can lie (Plan 244-03).** Steering RTT today comes from
   `autorate_health` / `autorate_irtt` / `history_fallback`, NOT the wanctl `RttBackend` seam
   (the steering pinger revival is Phase 245 / Selection A). Unconditionally stamping
   `producer="wanctl-backend"` would let a Phase 245 A/B scraper mix bridge-derived EWMA RTT
   into the `wanctl-backend` bucket — defeating the entire attributability goal. Attribution
   must be derived from the actual `rtt_source.current`, not the constructed-but-unconsumed
   backend handle. **This is the load-bearing finding and directly contradicts D-02's "backend
   never lies" guarantee for the steering surface.**
2. **HIGH — Autorate `source_ip` plumbing is wrong (Plan 244-02).** `RttBackendHandle` exposes
   no `source_ip` field, so `getattr(..., "source_ip", None)` silently returns `None`,
   violating D-04. Must source it from `controller_measurement.source_ip`, add a handle field,
   or read config explicitly.
3. **MEDIUM — `backend` (D-03 per-sample) vs `backend_active` (selected) conflation.** Plans
   02/03 proxy `backend_active` while D-03 specifies the per-sample `RttSample.backend`. Either
   wire the true per-sample value or re-document the field semantics — don't silently ship the
   selected backend under a per-sample name.
4. **MEDIUM — Byte-preservation tests prove superset/types but not key ORDER / serialized
   shape.** Add ordered-key assertions on the existing fields.
5. **MEDIUM — Bridge degraded/no-state (`state is None`) path lacks runtime endpoint coverage.**

### Divergent Views

None — single reviewer. Note the two HIGH findings are *evidence-correctness* risks (the
attribution could mislead the Phase 245 A/B), not controller-stability risks; Codex explicitly
rates control-path mutation risk as low and SAFE-17 design as sound.

### Recommended Action

Both HIGHs are pre-execution plan fixes, well within Phase 244's additive scope:
- 244-03: derive the attribution triple from `rtt_source.current`; only emit
  `producer="wanctl-backend"` when RTT genuinely flows through the wanctl seam (otherwise
  reflect the real producer / null). Add a test asserting `autorate_*` / `history_fallback`
  current values cannot produce `producer="wanctl-backend"` pre-245.
- 244-02: fix the `source_ip` accessor to a real source.

Re-plan via `/gsd:plan-phase 244 --reviews` before executing.
