---
phase: 244-health-payload-attribution-metadata
plan: 03
type: execute
wave: 1
depends_on: ["244-01"]
files_modified:
  - src/wanctl/steering/daemon.py
  - src/wanctl/steering/health.py
autonomous: true
requirements: [HEALTH-01, SAFE-17]
user_setup: []

must_haves:
  truths:
    - "Steering /health rtt_source block additively exposes producer, backend, source_ip — derived from the ACTUAL rtt_source.current, NOT unconditionally stamped."
    - "producer='wanctl-backend' is emitted ONLY when rtt_source.current names a value in the wanctl-backend seam set. Pre-245 that set is EMPTY: autorate_health, autorate_irtt, history_fallback, unknown, unavailable all yield producer=null, backend=null, source_ip=null."
    - "When (and only when) a future Phase 245 current-source flows through the wanctl RttBackend seam, producer='wanctl-backend', backend=carried selected backend_active, source_ip=carried per-WAN source_ip are emitted together."
    - "_create_steering_components no longer drops the already-computed source_ip + the handle's backend_active; they are carried to SteeringDaemon so they are READY for the seam path, but only surfaced under a seam-source current."
    - "Existing rtt_source keys (current, last_successful, last_rtt_ms, last_measurement_age_sec, counts) are byte-preserved."
    - "The additive edits stay inside the SAFE-17 allowlist (steering/daemon.py + the newly-allowlisted steering/health.py) and touch no protected body."
    - "D-02 backend-never-lies guarantee holds on the steering surface: a Phase 245 A/B scraper filtering on producer=='wanctl-backend' AND backend in {icmplib,fping} structurally CANNOT pick up autorate_health/autorate_irtt/history_fallback (bridge-derived EWMA) RTT, because those current sources can never produce producer='wanctl-backend' until the source path itself changes in 245."
    - "D-03/D-04 semantics on this surface are explicitly seam-gated: backend/source_ip reflect the daemon's carried selected backend_active + configured source_ip, and only when the current sample genuinely came through the wanctl seam (otherwise null) — reconciling D-03's per-sample intent with the verified reality that steering RTT does not flow through the seam pre-245."
  artifacts:
    - path: "src/wanctl/steering/daemon.py"
      provides: "carries source_ip + backend_active from _create_steering_components → SteeringDaemon; seam-gated triple derivation in get_health_data's rtt_source dict keyed on self._current_rtt_source"
      contains: "_WANCTL_BACKEND_RTT_SOURCES"
    - path: "src/wanctl/steering/health.py"
      provides: "_build_rtt_source_section passes through the daemon-derived producer/backend/source_ip"
      contains: "producer"
  key_links:
    - from: "src/wanctl/steering/daemon.py _create_steering_components"
      to: "SteeringDaemon.__init__"
      via: "extended return tuple → constructor arg → self._ field"
      pattern: "return state_mgr, router, rtt_measurement"
    - from: "src/wanctl/steering/daemon.py get_health_data"
      to: "self._current_rtt_source"
      via: "seam-source membership test gates producer/backend/source_ip"
      pattern: "_WANCTL_BACKEND_RTT_SOURCES"
    - from: "src/wanctl/steering/health.py _build_rtt_source_section"
      to: "daemon.get_health_data()['rtt_source']"
      via: "reads the daemon-derived producer/backend/source_ip off the rtt_source dict"
      pattern: "_build_rtt_source_section"
---

<objective>
Surface the attribution triple on the steering `/health` `rtt_source` block — the **primary
surface** (D-01 surface 1), because under Selection A this is where Phase 245's icmplib-vs-fping
A/B will measure ONCE the steering pinger is revived. The load-bearing correctness constraint
(Codex HIGH-1): steering RTT today does NOT flow through the wanctl `RttBackend` seam. It comes
from `autorate_health` (autorate `/health` poll), `autorate_irtt` (autorate IRTT poll), or
`history_fallback` (state history) — verified in `daemon.py` `measure_current_rtt` (~1756) and
`_measure_current_rtt_with_retry` (~1770). Unconditionally stamping `producer="wanctl-backend"`
would let a Phase 245 A/B scraper mislabel bridge-derived EWMA RTT (which feeds the autorate
`/health` the steering poll reads) as `wanctl-backend` A/B RTT — defeating attributability and
contradicting D-02's "backend never lies" guarantee.

Therefore: derive the attribution triple from the ACTUAL `rtt_source.current`. Define a
WANCTL-seam current-source set; emit `producer="wanctl-backend"` (+ the carried selected
`backend_active` and configured `source_ip`) ONLY when `current` is in that set. Pre-245 the set
is EMPTY — every existing `current` value (`autorate_health`, `autorate_irtt`,
`history_fallback`, `unknown`, `unavailable`) yields `producer=null`, `backend=null`,
`source_ip=null`. The daemon STILL carries `source_ip` + `backend_active` (the previously-dropped
4-tuple values) so the values are READY the instant Phase 245 flips the source path — but they
are only surfaced under a seam-source current.

Purpose: HEALTH-01 — attributability of every RTT sample before the A/B, WITHOUT lying about
where the sample came from. The steering path is the A/B-critical surface (Selection A), so the
attribution must be exactly correct: null until the seam genuinely produces the sample.

Output: additive wiring + seam-gated derivation in `src/wanctl/steering/daemon.py`, a
pass-through append in `src/wanctl/steering/health.py`, and a negative test proving
`current="autorate_health"`/`autorate_irtt`/`history_fallback` CANNOT produce
`producer="wanctl-backend"` pre-245.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/244-health-payload-attribution-metadata/244-CONTEXT.md
@.planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md
@.planning/phases/244-health-payload-attribution-metadata/244-RESEARCH.md
@.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/238-PROVENANCE-MAP.md

<interfaces>
<!-- Verified facts the executor needs — VERIFY line numbers against daemon.py before editing; they may drift. -->

STEERING RTT SOURCE REALITY (verified at plan time — daemon.py):
- self._current_rtt_source is initialized "unknown" in _init_rtt_source_observability (~1157-1167).
- measure_current_rtt (~1756) sets it via _record_rtt_source_success to one of:
    "autorate_health"  — from self.baseline_loader.load_live_rtt()      (autorate /health poll)
    "autorate_irtt"    — from self.baseline_loader.load_live_irtt_rtt()  (autorate IRTT poll)
  and on total failure sets it directly to "unavailable" (~1767).
- _measure_current_rtt_with_retry (~1770) fallback sets "history_fallback" — from state["history_rtt"] —
  via _record_rtt_source_success (~1799), or "unavailable" on no history (~1805).
- _rtt_source_counts keys are exactly: "autorate_health", "autorate_irtt", "history_fallback" (~1163-1167).
- NONE of these go through the wanctl RttBackend seam (build_rtt_backend / RttBackend.poll).
  The steering pinger revival that WOULD route through the seam is Phase 245 / Selection A
  (238-PROVENANCE-MAP.md), and is OUT OF SCOPE here (CONTEXT Deferred Ideas).
- get_health_data (~1395) builds "rtt_source": {...} (~1425-1435) with keys
  current / last_successful / last_rtt_ms / last_measurement_age_sec / counts. The current value
  is self._current_rtt_source. ADD producer/backend/source_ip into THIS sub-dict, DERIVED from
  self._current_rtt_source (see derivation rule below), NOT hardcoded.

THE SEAM-SOURCE SET (the HIGH-1 fix — define this near _init_rtt_source_observability):
  _WANCTL_BACKEND_RTT_SOURCES: frozenset[str] = frozenset()   # EMPTY pre-245
  Rationale: no current rtt_source value flows through the wanctl seam today. Phase 245 (the
  steering-pinger revival) is the phase that adds a seam-routed current value (e.g. a future
  "wanctl_pinger" / "steering_backend" source string) to this set. Until then it is empty, so
  producer is null for every real sample. A short comment must name Phase 245 as the editor of
  this set. Do NOT pre-add a speculative string — leave the set empty and let 245 own it.

DERIVATION RULE (in get_health_data, applied to the rtt_source sub-dict):
  current = self._current_rtt_source
  if current in _WANCTL_BACKEND_RTT_SOURCES:
      producer  = "wanctl-backend"
      backend   = self._rtt_backend_active  (coerced to {"icmplib","fping"} else None)
      source_ip = self._rtt_source_ip       (non-empty str else None)
  else:
      producer  = None     # NOT "wanctl-backend" — would lie (HIGH-1)
      backend   = None
      source_ip = None
  This is the ONLY place producer is decided. Do not stamp "wanctl-backend" anywhere else.

THE CARRY SPINE (the previously-dropped source_ip + backend_active — verified, lines may drift):
- _create_steering_components def @ ~2545; computes
    primary_rtt_config, source_ip, warnings = _load_primary_wan_config_for_rtt_backend(config)
  then builds rtt_backend = build_rtt_backend(primary_rtt_config, source_ip=source_ip, ...);
  CURRENTLY returns the 4-tuple `state_mgr, router, rtt_measurement, baseline_loader` (~2571) —
  source_ip and the handle's backend_active are DROPPED. This is the discard to fix.
- _load_primary_wan_config_for_rtt_backend reads source_ip = primary_cfg.get("ping_source_ip"),
  null-guards non-str/empty → None (~2612, matches D-04).
- rtt_backend (an RttBackendHandle from rtt_backend_factory.py) exposes .backend_active
  (the SELECTED backend — "icmplib"|"fping"); read it BEFORE extracting .controller_measurement.
  NOTE: RttBackendHandle has NO source_ip field (verified rtt_backend_factory.py:90-101) — that
  is why source_ip must come from the already-computed local in _create_steering_components, not
  off the handle.
- call site unpacks @ ~2709; constructed @ ~2738
  `SteeringDaemon(config, state_mgr, router, rtt_measurement, baseline_loader, logger)`.
- SteeringDaemon.__init__ @ ~1126; stores self.rtt_measurement/self.baseline_loader (~1138-1139);
  calls self._init_rtt_source_observability() (~1151).

steering/health.py — the builder (verified):
- _build_rtt_source_section @ ~359 reads `source = health_data.get("rtt_source", {})` and emits
  current/last_successful/last_rtt_ms/last_measurement_age_sec/counts (~359-377), reached via
  _populate_daemon_health (~196) with health_data = self.daemon.get_health_data() (~185).
- The producer/backend/source_ip are now ALREADY DERIVED on the daemon side (in get_health_data),
  so health.py simply PASSES THEM THROUGH from the rtt_source sub-dict with defensive coercion —
  it must NOT re-derive or hardcode producer. This keeps the single source of truth in the daemon.

PROTECTED bodies (must NOT change): WANController.measure_rtt + 7 rtt_measurement.py seam
functions. Nothing in steering/daemon.py or steering/health.py is in the PROTECTED map; these
edits are allowlist-safe. steering/health.py is newly allowlisted by Plan 01.

Backward-compat: extend SteeringDaemon.__init__ signature ADDITIVELY (new keyword params default
to None) so any other constructor caller is unaffected.

DOWNSTREAM SCRAPER CONTRACT (document for the Phase 245 A/B consumer): a consumer attributing an
RTT sample to the icmplib-vs-fping A/B MUST filter on `producer == "wanctl-backend"` AND
`backend in {"icmplib","fping"}`. Any other combination (producer null, producer
"cake-autorate-bridge", backend null) MUST be ignored/rejected — it is NOT A/B-attributable RTT.
Pre-245 the steering surface emits producer=null for every sample, so it contributes ZERO A/B
rows until 245 routes a current source through the seam. This is intentional and correct.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Carry source_ip + backend_active through the steering spine; define the seam-source set; derive the triple from rtt_source.current</name>
  <files>src/wanctl/steering/daemon.py</files>
  <read_first>
    - src/wanctl/steering/daemon.py — READ FROM CURRENT REALITY, do not trust line numbers:
      _init_rtt_source_observability (~1157-1167, the _rtt_source_counts keys); measure_current_rtt
      (~1756) and _measure_current_rtt_with_retry (~1770) to confirm the exact current-source string
      literals "autorate_health"/"autorate_irtt"/"history_fallback"/"unavailable"/"unknown";
      get_health_data (~1395) + the rtt_source sub-dict (~1425-1435); _create_steering_components
      (~2545-2571); _load_primary_wan_config_for_rtt_backend (~2587-2628, the source_ip read ~2612);
      call site (~2709); constructor call (~2738); SteeringDaemon.__init__ (~1126-1151)
    - src/wanctl/rtt_backend_factory.py (RttBackendHandle dataclass ~90-101 — confirm it has
      .backend_active but NO source_ip field; build_rtt_backend signature ~159 takes source_ip kwarg)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§steering/daemon.py wiring)
    - .planning/phases/244-health-payload-attribution-metadata/244-RESEARCH.md (Pitfall 2)
    - .planning/phases/244-health-payload-attribution-metadata/244-REVIEWS.md (Codex HIGH-1 — the load-bearing finding)
  </read_first>
  <behavior>
    - A module- or class-level `_WANCTL_BACKEND_RTT_SOURCES` frozenset exists and is EMPTY, with a
      comment naming Phase 245 as the editor that will add the seam-routed current-source string.
    - _create_steering_components returns the already-computed `source_ip` AND the handle's
      `backend_active` (read off the rtt_backend handle's .backend_active) in addition to the
      existing 4-tuple — additively, without breaking the unpack.
    - SteeringDaemon stores them as self._rtt_source_ip (str|None) and self._rtt_backend_active
      (str|None), defaulting to None when not supplied (backward-compatible constructor).
    - get_health_data's rtt_source sub-dict additively gains producer/backend/source_ip DERIVED
      from self._current_rtt_source per the derivation rule:
        * current in _WANCTL_BACKEND_RTT_SOURCES → producer="wanctl-backend",
          backend=self._rtt_backend_active (coerced icmplib|fping else None),
          source_ip=self._rtt_source_ip (non-empty str else None).
        * otherwise → producer=None, backend=None, source_ip=None.
    - Existing rtt_source keys (current/last_successful/last_rtt_ms/last_measurement_age_sec/counts)
      byte-preserved.
    - Negative behavior (asserted via the daemon directly): with self._current_rtt_source set to
      "autorate_health", "autorate_irtt", "history_fallback", "unavailable", or "unknown",
      get_health_data()["rtt_source"]["producer"] is None (NEVER "wanctl-backend").
  </behavior>
  <action>
    Define `_WANCTL_BACKEND_RTT_SOURCES: frozenset[str] = frozenset()` (empty) at module scope or as
    a class attribute near the rtt-source observability code, with a comment: "Current rtt_source
    values that genuinely flow through the wanctl RttBackend seam. EMPTY pre-245 — no steering RTT
    is seam-routed today (it comes from autorate_health/autorate_irtt/history_fallback). Phase 245
    (steering-pinger revival, Selection A) adds the seam-routed source string here." Extend
    `_create_steering_components` to additionally return `source_ip` (the already-computed local)
    and the rtt_backend handle's `.backend_active` (read it before extracting
    `.controller_measurement`). Do NOT read source_ip off the handle — RttBackendHandle has no such
    field; use the computed local. Update the return tuple and the call-site unpack (~2709) to carry
    the two new values. Extend `SteeringDaemon.__init__` ADDITIVELY with `rtt_source_ip=None` and
    `rtt_backend_active=None` keyword params, store as `self._rtt_source_ip` /
    `self._rtt_backend_active` near the existing rtt_measurement/baseline_loader assignments, and
    pass them at the constructor call (~2738). In `get_health_data`, compute the triple from
    `self._current_rtt_source`: if it is in `_WANCTL_BACKEND_RTT_SOURCES`, set
    `producer="wanctl-backend"`, `backend` = `self._rtt_backend_active` coerced to {"icmplib","fping"}
    else None, `source_ip` = `self._rtt_source_ip` if non-empty str else None; otherwise set all
    three to None. Add `producer`/`backend`/`source_ip` to the existing `"rtt_source": {...}`
    sub-dict (~1425-1435) using those derived values. Do NOT hardcode `producer="wanctl-backend"`.
    Do NOT reorder existing keys. Touch no protected body. Run `.venv/bin/ruff format`.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/steering/daemon.py && .venv/bin/mypy src/wanctl/steering/daemon.py && grep -q '_WANCTL_BACKEND_RTT_SOURCES' src/wanctl/steering/daemon.py && grep -q '_rtt_source_ip' src/wanctl/steering/daemon.py && test "$(grep -c '"wanctl-backend"' src/wanctl/steering/daemon.py)" -le 1</automated>
  </verify>
  <acceptance_criteria>
    - `_WANCTL_BACKEND_RTT_SOURCES` exists and is an EMPTY frozenset with a comment naming Phase 245
      (grep confirms the name; the literal `frozenset()` is present).
    - The string `"wanctl-backend"` appears AT MOST ONCE in daemon.py and only inside the seam-gated
      branch (not as an unconditional assignment) — verified by reading the get_health_data branch.
    - `_create_steering_components` return + the call-site unpack carry `source_ip` and
      `backend_active`; the existing values still unpack correctly.
    - `SteeringDaemon.__init__` accepts `rtt_source_ip=None` / `rtt_backend_active=None` (backward
      compatible) and stores `self._rtt_source_ip` / `self._rtt_backend_active`.
    - `get_health_data`'s rtt_source dict adds `producer`/`backend`/`source_ip` DERIVED from
      `self._current_rtt_source`; existing keys
      (current/last_successful/last_rtt_ms/last_measurement_age_sec/counts) byte-preserved.
    - source_ip is NOT read via `getattr(handle, "source_ip", ...)` (RttBackendHandle has no such
      field) — it comes from the computed local carried through the spine.
    - `git diff` shows NO change to `measure_rtt` or any `rtt_measurement.py` seam function.
    - ruff + mypy clean on `steering/daemon.py`.
  </acceptance_criteria>
  <done>
    The daemon carries the previously-dropped source_ip + selected backend_active, defines the empty
    seam-source set, and derives the rtt_source triple from self._current_rtt_source so producer is
    null (never "wanctl-backend") for every pre-245 current source.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Pass the daemon-derived triple through _build_rtt_source_section; add the HIGH-1 negative test</name>
  <files>src/wanctl/steering/health.py, tests/steering/test_steering_health.py</files>
  <read_first>
    - src/wanctl/steering/health.py (_build_rtt_source_section ~359-377; the .get/isinstance coercion
      at ~368-371; _populate_daemon_health ~185-196 showing health_data = self.daemon.get_health_data()
      then health["rtt_source"] = self._build_rtt_source_section(health_data))
    - tests/steering/test_steering_health.py (the _make_health_data helper ~39-60 — note its
      rtt_source defaults current="autorate_health"; the Wave-0-extended
      test_health_includes_rtt_source_section the contract assertions live in)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§steering/health.py)
    - .planning/phases/244-health-payload-attribution-metadata/244-REVIEWS.md (Codex HIGH-1 — the negative-test requirement)
  </read_first>
  <behavior>
    - _build_rtt_source_section returns a strict superset of the existing rtt_source contract
      (current/last_successful/last_rtt_ms/last_measurement_age_sec/counts preserved), plus
      producer/backend/source_ip READ THROUGH from health_data["rtt_source"] (NOT re-derived).
    - producer is passed through as-is when it is None or the literal "wanctl-backend"; any other
      value coerces to None (defensive). backend coerced to {"icmplib","fping"} else None; source_ip
      non-empty str else None.
    - HIGH-1 negative test: for each of current in {"autorate_health","autorate_irtt",
      "history_fallback","unavailable","unknown"}, a SteeringDaemon (or its get_health_data path)
      with that _current_rtt_source yields rtt_source["producer"] is None (NEVER "wanctl-backend"),
      rtt_source["backend"] is None, rtt_source["source_ip"] is None — even when the daemon carries a
      non-null _rtt_source_ip and _rtt_backend_active. This proves a pre-245 A/B scraper cannot pick
      up autorate/history RTT as wanctl-backend RTT.
    - Positive seam test (forward-looking, guarded): temporarily adding a sentinel value to
      _WANCTL_BACKEND_RTT_SOURCES (via monkeypatch) and setting _current_rtt_source to it yields
      producer="wanctl-backend" + the carried backend/source_ip — proving the gate is wired, not
      dead. (Use monkeypatch.setattr on the frozenset; do NOT edit the production empty set.)
  </behavior>
  <action>
    In `_build_rtt_source_section`, append three keys to the END of the returned dict (after
    `counts`), reading from `source = health_data.get("rtt_source", {})` (the existing local):
    `"producer"` = `source.get("producer")` passed through if it is None or `"wanctl-backend"` else
    coerced to None; `"backend"` = `source.get("backend")` coerced to {"icmplib","fping"} else None;
    `"source_ip"` = `source.get("source_ip")` coerced to non-empty str else None. Do NOT hardcode
    `producer="wanctl-backend"` and do NOT re-derive from `current` here — the daemon owns the
    derivation; health.py is a pass-through. Reuse the existing .get/isinstance defensive pattern.
    Do NOT move/mutate existing keys. In `tests/steering/test_steering_health.py`, extend the
    rtt_source contract test to assert the triple keys are present, then add a dedicated negative
    test (e.g. `test_non_seam_current_never_yields_wanctl_backend_producer`) that, for each current
    value in {"autorate_health","autorate_irtt","history_fallback","unavailable","unknown"},
    constructs the daemon health path (or the _make_health_data + builder path) with the daemon
    carrying non-null `_rtt_source_ip`/`_rtt_backend_active`, and asserts
    `rtt_source["producer"] is None` and `backend`/`source_ip` are None. Add a positive seam test
    using `monkeypatch.setattr` to inject a sentinel source string into
    `_WANCTL_BACKEND_RTT_SOURCES`, set `_current_rtt_source` to it, and assert
    `producer == "wanctl-backend"` plus the carried backend/source_ip surface. Run
    `.venv/bin/ruff format` on both files.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/steering/test_steering_health.py -q && .venv/bin/ruff check src/wanctl/steering/health.py tests/steering/test_steering_health.py && .venv/bin/mypy src/wanctl/steering/health.py</automated>
  </verify>
  <acceptance_criteria>
    - `_build_rtt_source_section` returns a strict superset of the pre-244 rtt_source contract;
      producer/backend/source_ip are passed through from health_data["rtt_source"] (health.py does
      NOT contain a hardcoded `"wanctl-backend"` literal — grep confirms 0 hardcoded assignments).
    - The negative test passes: every non-seam current value
      ({autorate_health,autorate_irtt,history_fallback,unavailable,unknown}) yields
      `rtt_source["producer"] is None`, `backend is None`, `source_ip is None`, EVEN when the daemon
      carries non-null _rtt_source_ip / _rtt_backend_active.
    - The positive seam test (monkeypatched sentinel source) yields `producer == "wanctl-backend"`
      with the carried backend/source_ip — proving the gate is live, not dead code.
    - ruff + mypy clean on `steering/health.py`; ruff clean on the test file.
  </acceptance_criteria>
  <done>
    The steering /health rtt_source block passes through the daemon-derived triple; the HIGH-1
    negative test proves autorate/history current sources can never produce producer="wanctl-backend"
    pre-245, and the positive seam test proves the gate is correctly wired.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → steering `/health` (127.0.0.1:9102) | localhost-bound observability endpoint; no untrusted network input. |
| daemon carried fields → health builder | in-process attribute reads; new self._ fields default None when wiring absent → degrade safely. |
| rtt_source.current → attribution derivation | the current-source string gates producer; an out-of-set value yields null attribution (fail-honest). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-244-08 | Spoofing | bridge-derived/autorate/history RTT mislabeled as wanctl-backend A/B RTT | mitigate | producer is derived from `self._current_rtt_source` against an EMPTY `_WANCTL_BACKEND_RTT_SOURCES` set; autorate_health/autorate_irtt/history_fallback/unavailable/unknown can NEVER yield producer="wanctl-backend" pre-245. Negative test enforces this. Directly resolves Codex HIGH-1 and upholds D-02 "backend never lies". |
| T-244-01 | Information Disclosure | `source_ip` exposed on steering `/health` | accept | `source_ip` is the operator's own configured per-WAN bind IP (operator-known infra, not a secret), and is null pre-245 anyway; endpoint is localhost-bound. Low/info finding. |
| T-244-04 | Denial of Service | malformed `rtt_source` upstream raising inside the health builder | mitigate | New keys use `.get`/`isinstance` coercion to safe `None`; a malformed value can never raise inside `_build_rtt_source_section` or `get_health_data`. |
| T-244-05 | Tampering | constructor-signature change breaking other SteeringDaemon callers | mitigate | New params are keyword args with `None` defaults (additive); existing call sites unaffected; mypy + the steering test suite gate this. |
| T-244-02 | Tampering | additive wiring perturbing the control path | mitigate | Edits confined to daemon wiring + the (newly-allowlisted) steering/health.py builder; `scripts/phase244-safe17-boundary-check.sh` (Plan 01) proves zero out-of-allowlist drift + byte-identical control bodies at the wave gate. |
| T-244-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — no external package installs in this plan. |
</threat_model>

<verification>
- `.venv/bin/pytest -o addopts='' tests/steering/test_steering_health.py -q` passes, including the
  HIGH-1 negative test (no non-seam current yields producer="wanctl-backend") and the positive
  monkeypatched-seam test.
- `.venv/bin/ruff check` + `.venv/bin/mypy` clean on `steering/daemon.py` + `steering/health.py`.
- Steering daemon test suite green (`.venv/bin/pytest -o addopts='' tests/steering/test_steering_daemon.py -q`)
  to confirm the additive constructor change broke no caller.
- Wave-gate (after all Wave 1 plans land): `bash scripts/phase244-safe17-boundary-check.sh` passes
  (steering/health.py now allowlisted; control bodies byte-identical).
- Do NOT gate on full-suite green (pre-existing stale-boundary failures).
</verification>

<success_criteria>
- Steering `/health` `rtt_source` additively exposes `producer`/`backend`/`source_ip` DERIVED from
  the actual current source — producer is null for every pre-245 source, "wanctl-backend" only when
  the seam genuinely produces the sample (the gate is wired and proven live).
- A Phase 245 A/B scraper filtering on producer=="wanctl-backend" AND backend in {icmplib,fping}
  structurally cannot mix autorate/history RTT into the A/B (D-02 backend-never-lies upheld).
- Existing rtt_source contract byte-preserved; constructor change backward-compatible; SAFE-17
  verifier passes at the wave gate.
</success_criteria>

<output>
Create `.planning/phases/244-health-payload-attribution-metadata/244-03-SUMMARY.md` when done.
</output>
