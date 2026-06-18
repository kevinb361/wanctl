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
    - "Steering /health rtt_source block additively exposes producer='wanctl-backend', backend (icmplib|fping|null), source_ip (configured per-WAN source|null)."
    - "_create_steering_components no longer drops the already-computed source_ip + backend_active; they are carried to SteeringDaemon and into the rtt_source health section."
    - "Existing rtt_source keys (current, last_successful, last_rtt_ms, last_measurement_age_sec, counts) are byte-preserved."
    - "The additive edits stay inside the SAFE-17 allowlist (steering/daemon.py + the newly-allowlisted steering/health.py) and touch no protected body."
  artifacts:
    - path: "src/wanctl/steering/daemon.py"
      provides: "carries source_ip + backend_active from _create_steering_components → SteeringDaemon → rtt_source health dict"
      contains: "source_ip"
    - path: "src/wanctl/steering/health.py"
      provides: "_build_rtt_source_section appends the attribution triple"
      contains: "producer"
  key_links:
    - from: "src/wanctl/steering/daemon.py _create_steering_components"
      to: "SteeringDaemon.__init__"
      via: "extended return tuple → constructor arg → self._ field"
      pattern: "return state_mgr, router, rtt_measurement"
    - from: "src/wanctl/steering/health.py _build_rtt_source_section"
      to: "daemon.get_health_data()['rtt_source']"
      via: "reads carried producer/backend/source_ip off the rtt_source dict"
      pattern: "_build_rtt_source_section"
---

<objective>
Surface the attribution triple on the steering `/health` `rtt_source` block — the **primary
surface** (D-01 surface 1), because under Selection A this is where Phase 245's icmplib-vs-fping
A/B measures. This is the largest of the three producer touches: the steering daemon currently
COMPUTES `source_ip` in `_create_steering_components` but DROPS it from the 4-tuple return
(daemon.py:2571), so it never reaches the health builder. Additively carry `source_ip` (and the
selected `backend_active`) through the existing wiring spine to `SteeringDaemon`, expose them in
the `rtt_source` health dict, and append `producer`/`backend`/`source_ip` to
`_build_rtt_source_section`.

Purpose: HEALTH-01 — attributability of every RTT sample before the A/B; the steering path is
the A/B-critical surface (Selection A), so it gets TRUE per-sample/selected fidelity (the
daemon's actual carried `source_ip` + the handle's `backend_active`), not the autorate-path proxy.

Output: additive wiring in `src/wanctl/steering/daemon.py` and the triple append in
`src/wanctl/steering/health.py`, validated by the Wave 0 steering health test flipping GREEN.
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
<!-- Verified facts the executor needs — no codebase exploration required. -->

steering/daemon.py — the carry spine (verified line numbers, may drift; read_first to confirm):
- _create_steering_components def @ 2545; computes `primary_rtt_config, source_ip, warnings =
  _load_primary_wan_config_for_rtt_backend(config)` @ 2555; builds rtt_backend with
  source_ip=source_ip @ 2565; CURRENTLY returns a 4-tuple
  `return state_mgr, router, rtt_measurement, baseline_loader` @ 2571 — source_ip (and the
  handle's backend_active) are DROPPED here. This is the discard to fix.
- _load_primary_wan_config_for_rtt_backend: reads `source_ip = primary_cfg.get("ping_source_ip")`
  @ 2612, null-guards non-str/empty → None @ 2613-2618 (matches D-04). The rtt_backend handle's
  `.backend_active` gives the selected backend for the steering `backend` key.
- call site unpacks the tuple @ 2709: `state_mgr, router, rtt_measurement, baseline_loader =
  _create_steering_components(...)`.
- constructed @ 2738: `SteeringDaemon(config, state_mgr, router, rtt_measurement,
  baseline_loader, logger)`.
- SteeringDaemon.__init__ @ 1126; stores self.rtt_measurement/self.baseline_loader @ 1138-1139;
  calls self._init_rtt_source_observability() @ 1151.
- _init_rtt_source_observability @ 1157 initializes self._current_rtt_source (1159),
  self._rtt_source_counts (1163), etc.
- get_health_data @ 1395 builds the "rtt_source": {...} sub-dict @ 1425-1434 with keys
  current/last_successful/last_rtt_ms/last_measurement_age_sec/counts. ADD producer/backend/
  source_ip into THIS sub-dict from the carried self._ fields.

steering/health.py — the builder (verified):
- _build_rtt_source_section @ 359 reads `source = health_data.get("rtt_source", {})` and emits
  current/last_successful/last_rtt_ms/last_measurement_age_sec/counts (lines 359-377). It is
  reached via _populate_daemon_health @ 196: `health["rtt_source"] =
  self._build_rtt_source_section(health_data)` where `health_data = self.daemon.get_health_data()`
  @ 185. So the carried triple flows daemon.get_health_data()['rtt_source'] →
  _build_rtt_source_section. ADD producer/backend/source_ip to the returned dict, read from the
  rtt_source sub-dict with defensive .get/isinstance coercion.

PROTECTED bodies (must NOT change): WANController.measure_rtt + 7 rtt_measurement.py seam
functions. Nothing in steering/daemon.py or steering/health.py is in the PROTECTED map; these
edits are allowlist-safe. steering/health.py is newly allowlisted by Plan 01.

Backward-compat: extend SteeringDaemon.__init__ signature ADDITIVELY (new params default to
None) so any other constructor caller is unaffected.

Selection A context (238-PROVENANCE-MAP.md): steering's own pinger is the A/B RTT source;
this is why the steering path carries true backend_active/source_ip rather than a proxy.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Carry source_ip + backend_active through the steering wiring spine into the rtt_source dict</name>
  <files>src/wanctl/steering/daemon.py</files>
  <read_first>
    - src/wanctl/steering/daemon.py (_create_steering_components 2545-2571; _load_primary_wan_config_for_rtt_backend 2587-2628; call site 2709; constructor call 2738; SteeringDaemon.__init__ 1126-1151; _init_rtt_source_observability 1157-1166; get_health_data 1395 + rtt_source dict 1425-1434)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§steering/daemon.py wiring — the carry spine + the discard to fix)
    - .planning/phases/244-health-payload-attribution-metadata/244-RESEARCH.md (Pitfall 2 — daemon discards handle/source_ip)
  </read_first>
  <behavior>
    - _create_steering_components returns the already-computed source_ip AND the selected
      backend_active (read off the rtt_backend handle's .backend_active) in addition to the
      existing 4-tuple — additively, without breaking the unpack.
    - SteeringDaemon stores them as self._rtt_source_ip (str|None) and self._rtt_backend_active
      (str|None), defaulting to None when not supplied (backward-compatible constructor).
    - daemon.get_health_data()'s rtt_source sub-dict additively gains producer="wanctl-backend",
      backend (= self._rtt_backend_active coerced to icmplib|fping else None),
      source_ip (= self._rtt_source_ip, str|None) — existing rtt_source keys byte-preserved.
  </behavior>
  <action>
    Extend `_create_steering_components` to return `source_ip` and the handle's `backend_active`
    in addition to the existing 4 values (read `backend_active` off the rtt_backend handle built
    at ~2565 before extracting `.controller_measurement`). Update the return at ~2571 and the
    unpack at the call site ~2709 to carry the two new values. Extend `SteeringDaemon.__init__`
    (~1126) ADDITIVELY with two new keyword params (`rtt_source_ip=None`,
    `rtt_backend_active=None`), store them as `self._rtt_source_ip` and `self._rtt_backend_active`
    near the existing `self.rtt_measurement`/`self.baseline_loader` assignments (~1138-1139), and
    pass them at the constructor call ~2738. In `get_health_data` (~1395), add three keys to the
    existing `"rtt_source": {...}` sub-dict (~1425-1434): `"producer": "wanctl-backend"`,
    `"backend": <self._rtt_backend_active coerced to {"icmplib","fping"} else None>`,
    `"source_ip": <self._rtt_source_ip if non-empty str else None>`. Do NOT reorder existing keys.
    Touch no protected body. Run `.venv/bin/ruff format`.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/steering/daemon.py && .venv/bin/mypy src/wanctl/steering/daemon.py && grep -q '"producer": "wanctl-backend"' src/wanctl/steering/daemon.py && grep -q '_rtt_source_ip' src/wanctl/steering/daemon.py</automated>
  </verify>
  <acceptance_criteria>
    - `_create_steering_components` return + the call-site unpack carry `source_ip` and
      `backend_active`; the existing 4 values still unpack correctly.
    - `SteeringDaemon.__init__` accepts the two new params with `None` defaults (backward-compatible
      — other callers unaffected) and stores `self._rtt_source_ip` / `self._rtt_backend_active`.
    - `get_health_data`'s `rtt_source` dict adds `producer`/`backend`/`source_ip`; existing keys
      (current/last_successful/last_rtt_ms/last_measurement_age_sec/counts) byte-preserved.
    - `git diff` shows NO change to `measure_rtt` or any `rtt_measurement.py` seam function.
    - ruff + mypy clean on `steering/daemon.py`.
  </acceptance_criteria>
  <done>
    The steering daemon carries the previously-dropped `source_ip` + selected `backend_active`
    through the wiring spine and exposes the triple in the `rtt_source` health dict.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Append the triple to _build_rtt_source_section and turn the steering health test GREEN</name>
  <files>src/wanctl/steering/health.py</files>
  <read_first>
    - src/wanctl/steering/health.py (_build_rtt_source_section 359-377; the .get/isinstance coercion at 368-371; _populate_daemon_health 185-196 showing health_data = self.daemon.get_health_data() then health["rtt_source"] = self._build_rtt_source_section(health_data))
    - tests/steering/test_steering_health.py (the Wave-0-extended test_health_includes_rtt_source_section — the assertions this task must satisfy; fake-daemon harness rtt_source= at 39-58)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§steering/health.py _build_rtt_source_section)
  </read_first>
  <behavior>
    - _build_rtt_source_section returns a dict that is a strict superset of the existing rtt_source
      contract (current/last_successful/last_rtt_ms/last_measurement_age_sec/counts preserved),
      plus producer/backend/source_ip read from the rtt_source sub-dict.
    - producer is "wanctl-backend"; backend coerced to {"icmplib","fping"} else None;
      source_ip non-empty str else None — read from health_data["rtt_source"].
    - The Wave 0 steering test (test_health_includes_rtt_source_section + triple assertions) passes.
  </behavior>
  <action>
    In `_build_rtt_source_section`, append three keys to the END of the returned dict (after
    `counts`): `"producer": <source.get("producer") coerced; default "wanctl-backend">`,
    `"backend": <source.get("backend") coerced to {"icmplib","fping"} else None>`,
    `"source_ip": <source.get("source_ip") coerced to non-empty str else None>`, where `source =
    health_data.get("rtt_source", {})` is the existing local. Reuse the function's existing
    `.get`/`isinstance` defensive pattern (lines 368-371). Do NOT move or mutate any existing key.
    Run `.venv/bin/ruff format`.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/steering/test_steering_health.py -q && .venv/bin/ruff check src/wanctl/steering/health.py && .venv/bin/mypy src/wanctl/steering/health.py</automated>
  </verify>
  <acceptance_criteria>
    - `.venv/bin/pytest -o addopts='' tests/steering/test_steering_health.py -q` passes, including
      the Wave 0 triple assertions on `data["rtt_source"]`.
    - Returned dict keys are a strict superset of the pre-244 rtt_source contract; existing keys'
      types unchanged.
    - ruff + mypy clean on `steering/health.py`.
  </acceptance_criteria>
  <done>
    The steering `/health` `rtt_source` block emits the full attribution triple additively; the
    Wave 0 steering health test is GREEN.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → steering `/health` (127.0.0.1:9102) | localhost-bound observability endpoint; no untrusted network input. |
| daemon carried fields → health builder | in-process attribute reads; new self._ fields default None when wiring absent → degrade safely. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-244-01 | Information Disclosure | `source_ip` exposed on steering `/health` | accept | `source_ip` is the operator's own configured per-WAN bind IP (operator-known infra, not a secret); endpoint is localhost-bound. Low/info finding. |
| T-244-04 | Denial of Service | malformed `rtt_source` upstream raising inside the health builder | mitigate | New keys use `.get`/`isinstance` coercion to safe `None`/literal; a malformed value can never raise inside `_build_rtt_source_section` or `get_health_data`. |
| T-244-05 | Tampering | constructor-signature change breaking other SteeringDaemon callers | mitigate | New params are keyword-only with `None` defaults (additive); existing call sites unaffected; mypy + the steering test suite gate this. |
| T-244-02 | Tampering | additive wiring perturbing the control path | mitigate | Edits confined to daemon wiring + the (newly-allowlisted) steering/health.py builder; `scripts/phase244-safe17-boundary-check.sh` (Plan 01) proves zero out-of-allowlist drift + byte-identical control bodies at the wave gate. |
| T-244-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — no external package installs in this plan. |
</threat_model>

<verification>
- `.venv/bin/pytest -o addopts='' tests/steering/test_steering_health.py -q` passes (Wave 0 triple GREEN).
- `.venv/bin/ruff check` + `.venv/bin/mypy` clean on `steering/daemon.py` + `steering/health.py`.
- Steering daemon test suite green (`.venv/bin/pytest -o addopts='' tests/steering/test_steering_daemon.py -q`)
  to confirm the additive constructor change broke no caller.
- Wave-gate (after all Wave 1 plans land): `bash scripts/phase244-safe17-boundary-check.sh` passes
  (steering/health.py now allowlisted; control bodies byte-identical).
- Do NOT gate on full-suite green (pre-existing stale-boundary failures).
</verification>

<success_criteria>
- Steering `/health` `rtt_source` additively exposes `producer`/`backend`/`source_ip` with TRUE
  carried fidelity (selected backend_active + computed source_ip), the A/B-critical surface.
- Existing rtt_source contract byte-preserved; constructor change backward-compatible; SAFE-17
  verifier passes at the wave gate.
</success_criteria>

<output>
Create `.planning/phases/244-health-payload-attribution-metadata/244-03-SUMMARY.md` when done.
</output>
