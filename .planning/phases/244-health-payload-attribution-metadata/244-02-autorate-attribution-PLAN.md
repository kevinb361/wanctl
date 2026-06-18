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
    - "Existing measurement keys (available, raw_rtt_ms, staleness_sec, backend_active, fell_back, fallback_count) are byte-preserved in keys, types, and position."
    - "The additive edits stay inside the SAFE-17 allowlist and touch no protected body (measure_rtt / RTT seam untouched)."
    - "D-03: a per-sample `backend` field is added (icmplib|fping|null) distinct from 242's selected `backend_active`; on this non-A/B autorate path it is the planner-chosen proxy (mirrors `backend_active`), with true per-sample fidelity reserved for the steering A/B surface (244-03)."
    - "D-04: `source_ip` reports the per-WAN configured/intended source IP the backend binds with, emitting null when none is configured, placed flat alongside `producer`/`backend` in the measurement block."
  artifacts:
    - path: "src/wanctl/health_check.py"
      provides: "_build_measurement_section appends the attribution triple to its return dict"
      contains: "producer"
    - path: "src/wanctl/wan_controller.py"
      provides: "get_health_data threads source_ip + per-sample backend proxy into the measurement dict"
      contains: "source_ip"
  key_links:
    - from: "src/wanctl/wan_controller.py"
      to: "src/wanctl/health_check.py"
      via: "measurement dict keys consumed by _build_measurement_section"
      pattern: "_build_measurement_section"
    - from: "src/wanctl/wan_controller.py get_health_data"
      to: "self._rtt_backend_status"
      via: "getattr with safe default (242 pattern)"
      pattern: "getattr\\(rtt_backend_status"
---

<objective>
Surface the attribution triple on the autorate controller `/health` path (D-01 surface 2),
purely additively. Thread `source_ip` and a per-sample `backend` proxy through
`wan_controller.get_health_data()`'s `measurement` dict, then append `producer`/`backend`/
`source_ip` to `health_check._build_measurement_section`'s return — without moving or mutating
the byte-preserved contract fields.

Purpose: HEALTH-01 requires `/health` to additively expose `backend` + `source_ip` for
attributability before the A/B. The autorate path is the consistency surface (242 already added
`backend_active` here); 244 adds the fuller triple. This is the first of the three producers.

Output: edits to `src/wanctl/wan_controller.py` (`get_health_data`) and
`src/wanctl/health_check.py` (`_build_measurement_section`), validated by the Wave 0
contract-snapshot test flipping GREEN.

D-03 fidelity call (planner decision): use the **proxy** approach on the autorate path —
`backend` mirrors the already-threaded `backend_active`, and `source_ip` is read off
`self._rtt_backend_status` (or the autorate config) via `getattr` with a `None` default. This
is the smallest touch, matches the verified 242 threading pattern (wan_controller.py:4496-4511),
and stays clear of `WANController.measure_rtt`'s protected body. True per-sample fidelity is
reserved for the steering path (Plan 03, the Selection-A A/B surface), per RESEARCH Open Q1.
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

<interfaces>
<!-- Verified facts the executor needs — no codebase exploration required. -->

health_check.py :: _build_measurement_section (return dict, verified lines 514-532):
Existing keys (BYTE-PRESERVED, do not reorder/mutate):
  available, raw_rtt_ms, staleness_sec, active_reflector_hosts, successful_reflector_hosts,
  state, successful_count, stale, backend_active, fell_back, fallback_count
Defensive-coercion pattern already present (lines 514-518): `.get(key, default)` then
`isinstance(...)` re-coerce. Apply the SAME to the new keys:
  producer  → always the literal "wanctl-backend" here
  backend   → validate measurement.get("backend") in {"icmplib","fping"} else None
  source_ip → validate measurement.get("source_ip") is a non-empty str else None
Append the triple at the END of the return dict (after fallback_count).

wan_controller.py :: get_health_data (verified):
- self._rtt_backend_status set at line 360.
- get_health_data def at 4481; backend_active/fell_back/fallback_count derived via
  `getattr(rtt_backend_status, "...", default) if rtt_backend_status is not None else default`
  at lines 4496-4511.
- The "measurement": {...} sub-dict is built at 4539-4556; backend_active/fell_back/fallback_count
  are set at 4553-4555. ADD producer/backend/source_ip into THIS sub-dict.
- _record_live_rtt_snapshot (line 1350) stores only rtt_ms/ts/hosts — NOT RttSample.backend/
  source_ip. Hence the proxy approach: backend := backend_active; source_ip via
  getattr(rtt_backend_status, "source_ip", None) (guard non-str/empty → None). Do NOT touch
  _record_live_rtt_snapshot or measure_rtt.

PROTECTED bodies (must NOT change): WANController.measure_rtt and the 7 rtt_measurement.py seam
functions. get_health_data and _build_measurement_section are NOT protected — additive edits
there are allowlist-safe and do not trip phase239-protected-body-diff.py.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Thread source_ip + backend proxy into get_health_data's measurement dict</name>
  <files>src/wanctl/wan_controller.py</files>
  <read_first>
    - src/wanctl/wan_controller.py (get_health_data ~4481-4556; the backend_active/fell_back/fallback_count derivation at 4496-4511; the measurement sub-dict at 4539-4556; confirm _record_live_rtt_snapshot at 1350 does NOT store backend/source_ip; confirm measure_rtt is a SEPARATE method that this plan does NOT touch)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§wan_controller.py get_health_data — option (a) proxy)
    - .planning/phases/244-health-payload-attribution-metadata/244-RESEARCH.md (Pitfall 3 / R3a; Open Question 1)
  </read_first>
  <action>
    In `get_health_data`, alongside the existing `backend_active`/`fell_back`/`fallback_count`
    derivations (lines 4496-4511), derive a `source_ip` value:
    `getattr(rtt_backend_status, "source_ip", None) if rtt_backend_status is not None else None`,
    then null-guard it (`if not isinstance(source_ip, str) or not source_ip: source_ip = None`).
    Use the proxy for the per-sample `backend`: set the new `backend` key equal to `backend_active`
    (already computed). Add three keys to the existing `"measurement": {...}` sub-dict at
    4539-4556 — `"producer": "wanctl-backend"`, `"backend": backend_active`,
    `"source_ip": source_ip` — appended AFTER the existing `fallback_count` key. Do NOT reorder or
    mutate any existing key. Do NOT touch `_record_live_rtt_snapshot`, `measure_rtt`, or any RTT
    seam function.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/wan_controller.py && .venv/bin/mypy src/wanctl/wan_controller.py && grep -q '"producer": "wanctl-backend"' src/wanctl/wan_controller.py</automated>
  </verify>
  <acceptance_criteria>
    - The `measurement` sub-dict in `get_health_data` contains `producer`, `backend`, `source_ip`
      after `fallback_count`; existing keys unchanged in name, type, and order.
    - `source_ip` resolves to a non-empty str or `None`; `backend` proxies `backend_active`.
    - `git diff` shows NO change to `_record_live_rtt_snapshot`, `measure_rtt`, or any
      `rtt_measurement.py` seam function.
    - ruff + mypy clean on `wan_controller.py`.
  </acceptance_criteria>
  <done>
    `get_health_data` additively threads the triple into the measurement dict via the verified
    242 getattr-safe-default pattern, touching no protected body.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Append the attribution triple to _build_measurement_section and turn the contract test GREEN</name>
  <files>src/wanctl/health_check.py</files>
  <read_first>
    - src/wanctl/health_check.py (_build_measurement_section ~454-532; the return dict 514-532; the defensive .get/isinstance coercion at 514-518)
    - tests/test_health_check.py (the Wave-0-extended contract-snapshot test — the assertions this task must satisfy)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§health_check.py _build_measurement_section)
  </read_first>
  <behavior>
    - _build_measurement_section returns a dict that is a strict superset of the existing contract:
      all existing keys preserved (name, type, position), plus producer/backend/source_ip.
    - producer is always the literal "wanctl-backend" on this path.
    - backend = measurement.get("backend") coerced to one of {"icmplib","fping"} else None.
    - source_ip = measurement.get("source_ip") coerced to a non-empty str else None.
    - The Wave 0 test_measurement_byte_preserved + strict-superset assertions pass.
  </behavior>
  <action>
    In `_build_measurement_section`, append three keys to the END of the returned dict (after
    `fallback_count`): `"producer": "wanctl-backend"`; `"backend": <coerced>` where coerced reads
    `measurement.get("backend")` and validates membership in `{"icmplib","fping"}` (else `None`),
    mirroring the existing `backend_active` coercion at lines 514-518; `"source_ip": <coerced>`
    where coerced reads `measurement.get("source_ip")` and validates a non-empty `str` (else
    `None`). Reuse the exact `.get`/`isinstance` defensive pattern already in the function. Do NOT
    move or mutate any existing key. Run `.venv/bin/ruff format` on the file.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_health_check.py -q && .venv/bin/ruff check src/wanctl/health_check.py && .venv/bin/mypy src/wanctl/health_check.py</automated>
  </verify>
  <acceptance_criteria>
    - `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` passes, including the Wave 0
      strict-superset + byte-preservation assertions (producer/backend/source_ip now present).
    - Returned dict keys are a strict superset of the pre-244 contract; existing keys' types
      unchanged.
    - ruff + mypy clean on `health_check.py`.
  </acceptance_criteria>
  <done>
    The autorate `/health` measurement block emits the full attribution triple additively; the
    Wave 0 contract-snapshot test is GREEN.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → autorate `/health` (127.0.0.1:9101) | localhost-bound observability endpoint; no untrusted network input crosses here. |
| RTT-backend status → health builder | in-process attribute read; status may be `None` (no factory) → degrades to safe defaults via getattr. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-244-01 | Information Disclosure | `source_ip` exposed on autorate `/health` | accept | `source_ip` is the operator's own configured per-WAN bind IP (operator-known infra, not a secret); endpoint is localhost-bound. Low/info finding. |
| T-244-04 | Denial of Service | malformed upstream `measurement` dict raising inside the health builder | mitigate | All three new keys use `.get(key, default)` + `isinstance` coercion to a safe `None`/literal; a malformed value can never raise inside `_build_measurement_section` or `get_health_data`. |
| T-244-02 | Tampering | additive edit perturbing the control path | mitigate | Edits confined to `get_health_data` + `_build_measurement_section` (NOT protected bodies); `scripts/phase244-safe17-boundary-check.sh` (Plan 01) proves zero out-of-allowlist drift and byte-identical control bodies at the wave gate. |
| T-244-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — no external package installs in this plan. |
</threat_model>

<verification>
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` passes (Wave 0 triple assertions GREEN).
- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/health_check.py` clean.
- `.venv/bin/mypy src/wanctl/wan_controller.py src/wanctl/health_check.py` clean.
- Wave-gate (run after all Wave 1 plans land): `bash scripts/phase244-safe17-boundary-check.sh`
  passes, plus the hot-path slice
  (`.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`).
- Do NOT gate on full-suite green (pre-existing stale-boundary failures).
</verification>

<success_criteria>
- Autorate `/health` measurement additively exposes `producer`/`backend`/`source_ip` with the
  bridge-honest semantics inapplicable here (this is a wanctl-backend path).
- Existing contract fields byte-preserved; SAFE-17 verifier passes at the wave gate.
</success_criteria>

<output>
Create `.planning/phases/244-health-payload-attribution-metadata/244-02-SUMMARY.md` when done.
</output>
