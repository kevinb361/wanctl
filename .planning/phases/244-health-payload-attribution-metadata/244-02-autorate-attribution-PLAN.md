---
phase: 244-health-payload-attribution-metadata
plan: 02
type: execute
wave: 1
depends_on: ["244-01"]
files_modified:
  - src/wanctl/wan_controller.py
  - src/wanctl/health_check.py
autonomous: true
requirements: [HEALTH-01, SAFE-17]
user_setup: []

must_haves:
  truths:
    - "Autorate /health measurement block additively exposes producer='wanctl-backend', backend (icmplib|fping|null), source_ip (configured per-WAN source|null)."
    - "source_ip is sourced from rtt_backend_status.controller_measurement.source_ip (a real, populated attribute), NOT getattr(rtt_backend_status, 'source_ip', None) — RttBackendHandle has no source_ip field, so the getattr form would silently always be None (Codex HIGH-2 / D-04 violation)."
    - "Existing measurement keys (available, raw_rtt_ms, staleness_sec, backend_active, fell_back, fallback_count) are byte-preserved in keys, types, and position."
    - "The additive edits stay inside the SAFE-17 allowlist and touch no protected body (measure_rtt / RTT seam untouched)."
    - "MEDIUM-3 reconciliation: on this NON-A/B autorate path the per-sample RttSample.backend is NOT stored on the controller (_record_live_rtt_snapshot keeps only rtt_ms/ts/hosts), so the emitted `backend` is the planner-chosen proxy = the SELECTED backend_active. This is explicitly documented as the selected (not per-sample) value here; the true per-sample/seam fidelity that D-03 envisions is reserved for the Selection-A steering surface (244-03), which is the actual A/B target. The autorate `backend` and `backend_active` will therefore be equal on this surface by construction."
    - "D-04: `source_ip` reports the per-WAN configured/intended source IP the backend binds with (the value plumbed into RTTMeasurement at the factory call, 242 D-01a), emitting null when none is configured, placed flat alongside `producer`/`backend` in the measurement block."
  artifacts:
    - path: "src/wanctl/health_check.py"
      provides: "_build_measurement_section appends the attribution triple to its return dict"
      contains: "producer"
    - path: "src/wanctl/wan_controller.py"
      provides: "get_health_data threads source_ip (from controller_measurement) + selected-backend proxy into the measurement dict"
      contains: "controller_measurement"
  key_links:
    - from: "src/wanctl/wan_controller.py"
      to: "src/wanctl/health_check.py"
      via: "measurement dict keys consumed by _build_measurement_section"
      pattern: "_build_measurement_section"
    - from: "src/wanctl/wan_controller.py get_health_data"
      to: "self._rtt_backend_status.controller_measurement.source_ip"
      via: "getattr on the controller_measurement (real RTTMeasurement.source_ip)"
      pattern: "controller_measurement"
---

<objective>
Surface the attribution triple on the autorate controller `/health` path (D-01 surface 2),
purely additively. Thread `source_ip` and a selected-backend proxy through
`wan_controller.get_health_data()`'s `measurement` dict, then append `producer`/`backend`/
`source_ip` to `health_check._build_measurement_section`'s return — without moving or mutating
the byte-preserved contract fields.

Purpose: HEALTH-01 requires `/health` to additively expose `backend` + `source_ip` for
attributability before the A/B. The autorate path is the consistency surface (242 already added
`backend_active` here); 244 adds the fuller triple. This is the autorate (non-A/B) producer; the
A/B-critical surface is steering (244-03).

Output: edits to `src/wanctl/wan_controller.py` (`get_health_data`) and
`src/wanctl/health_check.py` (`_build_measurement_section`), validated by the Wave 0
contract-snapshot test flipping GREEN.

HIGH-2 fix (Codex): `source_ip` must NOT be read via `getattr(rtt_backend_status, "source_ip",
None)`. `self._rtt_backend_status` is an `RttBackendHandle` (verified rtt_backend_factory.py:90-101)
whose fields are `backend, controller_measurement, backend_active, fell_back, fallback_count,
fping_cadence_sec, _logger, _wan_key` — there is NO `source_ip` field, so that getattr would
silently always return None and violate D-04. The real, populated source IP lives on the handle's
`controller_measurement` (an `RTTMeasurement`, whose `.source_ip` is set at construction from the
factory's `source_ip=` arg — 242 D-01a). Read it via
`getattr(rtt_backend_status.controller_measurement, "source_ip", None)` guarded by a None-handle
check, then null-coerce.

MEDIUM-3 reconciliation (Codex): the autorate `backend` key is the SELECTED backend
(`backend_active`), NOT the per-sample `RttSample.backend`. `_record_live_rtt_snapshot`
(wan_controller.py ~1350) stores only rtt_ms/ts/hosts — the controller does not retain the
producing backend per sample. Rather than enlarge the controller touch on a non-A/B surface (and
risk the protected `measure_rtt` body), this plan emits the selected backend as the proxy and
documents it as such. True per-sample fidelity is delivered where it matters for the A/B: the
steering surface (244-03). On this autorate surface `backend == backend_active` by construction.
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
@.planning/phases/242-backend-factory-loud-fallback/242-CONTEXT.md

<interfaces>
<!-- Verified facts the executor needs — VERIFY line numbers against current source before editing. -->

RttBackendHandle field set (verified rtt_backend_factory.py:90-101) — the source of HIGH-2:
  backend, controller_measurement, backend_active, fell_back, fallback_count, fping_cadence_sec,
  _logger, _wan_key
  → NO `source_ip` field. `getattr(handle, "source_ip", None)` is ALWAYS None. DO NOT use it.
  controller_measurement is an RTTMeasurement; RTTMeasurement.source_ip is set at construction
  (rtt_measurement.py:172 `self.source_ip = source_ip`) from the factory's source_ip= arg
  (rtt_backend_factory.py: _build_controller_measurement passes source_ip → RTTMeasurement). This
  is the per-WAN configured source plumbed at the factory call (242 D-01a). So:
    source_ip = getattr(rtt_backend_status.controller_measurement, "source_ip", None)
                if rtt_backend_status is not None else None
    then: if not isinstance(source_ip, str) or not source_ip: source_ip = None

wan_controller.py :: get_health_data (verified):
- self._rtt_backend_status (the RttBackendHandle) set at __init__ line ~360.
- get_health_data def at ~4481; backend_active/fell_back/fallback_count derived via
  `getattr(rtt_backend_status, "<field>", default) if rtt_backend_status is not None else default`
  at ~4496-4511. backend_active/fell_back/fallback_count ARE real handle fields — keep those gets.
- The "measurement": {...} sub-dict is built at ~4539-4556; backend_active/fell_back/fallback_count
  are set at ~4553-4555. ADD producer/backend/source_ip into THIS sub-dict.
- _record_live_rtt_snapshot (~1350) stores only rtt_ms/ts/hosts — NOT RttSample.backend/source_ip.
  Hence the selected-backend proxy: backend := backend_active (the SELECTED backend), documented as
  the selected value per MEDIUM-3. Do NOT touch _record_live_rtt_snapshot or measure_rtt.

health_check.py :: _build_measurement_section (return dict, verified ~514-532):
Existing keys (BYTE-PRESERVED, do not reorder/mutate):
  available, raw_rtt_ms, staleness_sec, active_reflector_hosts, successful_reflector_hosts,
  state, successful_count, stale, backend_active, fell_back, fallback_count
Defensive-coercion pattern already present (~514-518): `.get(key, default)` then `isinstance(...)`
re-coerce. Apply the SAME to the new keys:
  producer  → always the literal "wanctl-backend" here (autorate IS a wanctl seam producer)
  backend   → validate measurement.get("backend") in {"icmplib","fping"} else None
  source_ip → validate measurement.get("source_ip") is a non-empty str else None
Append the triple at the END of the return dict (after fallback_count).

PROTECTED bodies (must NOT change): WANController.measure_rtt and the 7 rtt_measurement.py seam
functions. get_health_data and _build_measurement_section are NOT protected — additive edits there
are allowlist-safe and do not trip phase239-protected-body-diff.py.

PRODUCER NOTE: the autorate measurement IS produced through the wanctl RttBackend seam (the
controller's RTTMeasurement / fping backend), unlike the steering rtt_source which polls autorate.
So producer="wanctl-backend" is HONEST here. (Contrast 244-03, where producer is null pre-245.)

DOWNSTREAM SCRAPER CONTRACT (document for the Phase 245 A/B consumer): filter on
`producer == "wanctl-backend"` AND `backend in {"icmplib","fping"}`; ignore/reject any other
combination. On this autorate surface backend == backend_active (selected); it is the steering
surface (244-03) that carries the A/B-relevant samples once 245 routes them through the seam.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Thread source_ip (from controller_measurement) + selected-backend proxy into get_health_data's measurement dict</name>
  <files>src/wanctl/wan_controller.py</files>
  <read_first>
    - src/wanctl/wan_controller.py (get_health_data ~4481-4556; the backend_active/fell_back/fallback_count derivation at ~4496-4511; the measurement sub-dict at ~4539-4556; confirm _record_live_rtt_snapshot at ~1350 does NOT store backend/source_ip; confirm measure_rtt is a SEPARATE method that this plan does NOT touch; __init__ ~344-360 to confirm self._rtt_backend_status is the RttBackendHandle)
    - src/wanctl/rtt_backend_factory.py (RttBackendHandle dataclass ~90-101 — confirm NO source_ip field; _build_controller_measurement ~210-221 passes source_ip into RTTMeasurement)
    - src/wanctl/rtt_measurement.py (line ~172 self.source_ip = source_ip — confirm controller_measurement.source_ip is the real accessor)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§wan_controller.py get_health_data)
    - .planning/phases/244-health-payload-attribution-metadata/244-REVIEWS.md (Codex HIGH-2 + MEDIUM-3)
  </read_first>
  <behavior>
    - source_ip is derived from the handle's controller_measurement:
      `getattr(rtt_backend_status.controller_measurement, "source_ip", None)` under a
      `rtt_backend_status is not None` guard, then null-coerced (non-empty str else None). It is NOT
      read via `getattr(rtt_backend_status, "source_ip", None)`.
    - backend (the per-sample key) is set to the SELECTED backend_active on this autorate path
      (proxy, documented per MEDIUM-3) — so backend == backend_active here by construction.
    - producer is the literal "wanctl-backend" (autorate is a real wanctl seam producer).
    - The measurement sub-dict gains producer/backend/source_ip AFTER fallback_count; existing keys
      unchanged in name, type, and order.
  </behavior>
  <action>
    In `get_health_data`, keep the existing `backend_active`/`fell_back`/`fallback_count` gets
    (those ARE real RttBackendHandle fields). Add a `source_ip` derivation FROM THE
    controller_measurement, NOT the handle:
    `source_ip = getattr(rtt_backend_status.controller_measurement, "source_ip", None) if
    rtt_backend_status is not None else None`, then null-guard
    (`if not isinstance(source_ip, str) or not source_ip: source_ip = None`). Set the per-sample
    `backend` key to `backend_active` (the selected proxy — add a short inline comment that this is
    the SELECTED backend, not the per-sample RttSample.backend, which is not retained on the autorate
    controller; true per-sample fidelity lives on the steering surface 244-03). Add three keys to the
    existing `"measurement": {...}` sub-dict (~4539-4556) — `"producer": "wanctl-backend"`,
    `"backend": backend_active`, `"source_ip": source_ip` — appended AFTER the existing
    `fallback_count` key. Do NOT reorder or mutate any existing key. Do NOT use
    `getattr(rtt_backend_status, "source_ip", ...)`. Do NOT touch `_record_live_rtt_snapshot`,
    `measure_rtt`, or any RTT seam function.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/wan_controller.py && .venv/bin/mypy src/wanctl/wan_controller.py && grep -q '"producer": "wanctl-backend"' src/wanctl/wan_controller.py && grep -q 'controller_measurement.*source_ip\|controller_measurement,\s*"source_ip"' src/wanctl/wan_controller.py && ! grep -q 'getattr(rtt_backend_status, "source_ip"' src/wanctl/wan_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - `source_ip` is read from `rtt_backend_status.controller_measurement` (grep confirms
      `controller_measurement` appears in the get_health_data source_ip derivation), and the string
      `getattr(rtt_backend_status, "source_ip"` is ABSENT (the HIGH-2 anti-pattern is not present).
    - The `measurement` sub-dict contains `producer`, `backend`, `source_ip` after `fallback_count`;
      existing keys unchanged in name, type, and order.
    - `source_ip` resolves to a non-empty str or `None`; `backend` proxies the SELECTED
      `backend_active` (with an inline comment stating it is the selected value, per MEDIUM-3).
    - `git diff` shows NO change to `_record_live_rtt_snapshot`, `measure_rtt`, or any
      `rtt_measurement.py` seam function.
    - ruff + mypy clean on `wan_controller.py`.
  </acceptance_criteria>
  <done>
    `get_health_data` additively threads the triple into the measurement dict, with source_ip read
    from the real `controller_measurement.source_ip` accessor (not the non-existent handle field)
    and backend documented as the selected proxy. No protected body touched.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Append the attribution triple to _build_measurement_section and turn the contract test GREEN</name>
  <files>src/wanctl/health_check.py</files>
  <read_first>
    - src/wanctl/health_check.py (_build_measurement_section ~454-532; the return dict ~514-532; the defensive .get/isinstance coercion at ~514-518)
    - tests/test_health_check.py (the Wave-0-extended contract-snapshot test — the assertions this task must satisfy; ordered-key assertions added in Plan 01 Task 3)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§health_check.py _build_measurement_section)
  </read_first>
  <behavior>
    - _build_measurement_section returns a dict that is a strict superset of the existing contract:
      all existing keys preserved (name, type, AND position/order), plus producer/backend/source_ip.
    - producer is always the literal "wanctl-backend" on this path.
    - backend = measurement.get("backend") coerced to one of {"icmplib","fping"} else None.
    - source_ip = measurement.get("source_ip") coerced to a non-empty str else None.
    - The Wave 0 test_measurement_byte_preserved + ordered-key + strict-superset assertions pass.
  </behavior>
  <action>
    In `_build_measurement_section`, append three keys to the END of the returned dict (after
    `fallback_count`): `"producer": "wanctl-backend"`; `"backend": <coerced>` where coerced reads
    `measurement.get("backend")` and validates membership in `{"icmplib","fping"}` (else `None`),
    mirroring the existing `backend_active` coercion at ~514-518; `"source_ip": <coerced>` where
    coerced reads `measurement.get("source_ip")` and validates a non-empty `str` (else `None`).
    Reuse the exact `.get`/`isinstance` defensive pattern already in the function. The three new keys
    MUST be appended after all existing keys so the existing key ORDER (asserted by the Plan 01
    ordered-key test) is preserved. Do NOT move or mutate any existing key. Run `.venv/bin/ruff
    format` on the file.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py -q && .venv/bin/ruff check src/wanctl/health_check.py && .venv/bin/mypy src/wanctl/health_check.py</automated>
  </verify>
  <acceptance_criteria>
    - `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` passes, including the Wave 0
      ordered-key + strict-superset + byte-preservation assertions (producer/backend/source_ip now
      present and appended after the existing keys).
    - Returned dict keys are a strict superset of the pre-244 contract; existing keys' types AND
      order unchanged (the new triple is strictly appended).
    - ruff + mypy clean on `health_check.py`.
  </acceptance_criteria>
  <done>
    The autorate `/health` measurement block emits the full attribution triple additively, appended
    after the existing keys; the Wave 0 contract-snapshot test (including ordered-key assertions) is
    GREEN.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → autorate `/health` (127.0.0.1:9101) | localhost-bound observability endpoint; no untrusted network input crosses here. |
| RTT-backend status → health builder | in-process attribute read; status may be `None` (no factory) → degrades to safe defaults via guarded getattr. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-244-01 | Information Disclosure | `source_ip` exposed on autorate `/health` | accept | `source_ip` is the operator's own configured per-WAN bind IP (operator-known infra, not a secret); endpoint is localhost-bound. Low/info finding. |
| T-244-09 | Spoofing | source_ip silently null (HIGH-2) making autorate samples look source-less | mitigate | source_ip read from the REAL `controller_measurement.source_ip` accessor (verified populated), not the non-existent `RttBackendHandle.source_ip`; verify-step greps assert the correct accessor and the absence of the HIGH-2 anti-pattern. |
| T-244-04 | Denial of Service | malformed upstream `measurement` dict raising inside the health builder | mitigate | All three new keys use `.get(key, default)` + `isinstance` coercion to a safe `None`/literal; a malformed value can never raise inside `_build_measurement_section` or `get_health_data`. |
| T-244-02 | Tampering | additive edit perturbing the control path | mitigate | Edits confined to `get_health_data` + `_build_measurement_section` (NOT protected bodies); `scripts/phase244-safe17-boundary-check.sh` (Plan 01) proves zero out-of-allowlist drift and byte-identical control bodies at the wave gate. |
| T-244-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — no external package installs in this plan. |
</threat_model>

<verification>
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` passes (Wave 0 triple + ordered-key assertions GREEN).
- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/health_check.py` clean.
- `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/health_check.py` clean.
- The HIGH-2 anti-pattern `getattr(rtt_backend_status, "source_ip"` is ABSENT from wan_controller.py.
- Wave-gate (run after all Wave 1 plans land): `bash scripts/phase244-safe17-boundary-check.sh`
  passes, plus the hot-path slice
  (`.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`).
- Do NOT gate on full-suite green (pre-existing stale-boundary failures).
</verification>

<success_criteria>
- Autorate `/health` measurement additively exposes `producer="wanctl-backend"`/`backend`/`source_ip`,
  with source_ip from the real controller_measurement accessor and backend documented as the
  selected proxy (MEDIUM-3).
- Existing contract fields byte-preserved (keys, types, order); SAFE-17 verifier passes at the wave gate.
</success_criteria>

<output>
Create `.planning/phases/244-health-payload-attribution-metadata/244-02-SUMMARY.md` when done.
</output>
