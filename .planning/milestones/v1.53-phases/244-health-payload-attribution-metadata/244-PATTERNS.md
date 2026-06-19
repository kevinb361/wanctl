# Phase 244: Health-Payload Attribution Metadata - Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 8 (3 modify-Python, 1 modify-Python wiring, 2 modify-deploy-script, 2 create, 3 extend-test)
**Analogs found:** 8 / 8 (every touched file has a direct in-repo precedent; this is a clone-the-pattern phase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/wanctl/health_check.py` (`_build_measurement_section`) | health-payload builder | transform / request-response | itself @ Phase 242 (`backend_active` append, lines 514-532) | exact (same function, prior additive precedent) |
| `src/wanctl/wan_controller.py` (`get_health_data`) | controller backend-data source | transform / request-response | itself @ Phase 242 (`backend_active`/`fell_back` threading, lines 4496-4555) | exact |
| `src/wanctl/steering/health.py` (`_build_rtt_source_section`) | health-payload builder (steering) | transform / request-response | `health_check.py::_build_measurement_section` | role-match (different block name `rtt_source`, same shape discipline) |
| `src/wanctl/steering/daemon.py` (`_create_steering_components` → `SteeringDaemon.__init__`) | DI wiring / provider | request-response (carry data) | existing tuple-threading of `rtt_measurement`/`baseline_loader` (2547→2571→2709→2738→1126) | exact (same wiring spine, add one carried value) |
| `deploy/scripts/cake-autorate-spectrum-state-bridge` (`health_payload()`) | deploy-script health endpoint | request-response | itself (existing `measurement` block, lines 243 + 267-271) | exact |
| `deploy/scripts/cake-autorate-att-state-bridge` (`health_payload()`) | deploy-script health endpoint | request-response | spectrum bridge (byte-identical health region) | exact (keep both in lockstep) |
| `scripts/phase244-safe17-boundary-check.sh` | verification tooling | batch / git-diff gate | `scripts/phase242-safe17-boundary-check.sh` | exact (clone; NOT 243) |
| `tests/test_phase244_safe17_verifier.py` | test (verifier mirror) | batch | `tests/test_phase243_safe17_verifier.py` | exact (mirror) |
| `tests/test_health_check.py` (extend) | test (contract) | transform | existing `test_measurement_byte_preserved` (1960) + `test_measurement_backend_fallback_keys_are_per_wan` (1989) | exact |
| `tests/test_spectrum/att_cake_autorate_artifacts.py` (extend) | test (integration) | request-response | `test_state_bridge_serves_wanctl_compatible_health_endpoint` (164) | exact |

## Critical Correction to Research (load-bearing — read before planning SAFE-17)

The 244-RESEARCH.md §SAFE-17 assumed 244's health-builder edits would "trip the protected-body diff" and that the verifier must "widen the protected-body exception to the health-builder functions." **This is not true.** Verified against `scripts/phase239-protected-body-diff.py:21-32`:

```python
PROTECTED: dict[str, list[str]] = {
    "src/wanctl/rtt_measurement.py": [ ...7 seam functions... ],
    "src/wanctl/wan_controller.py": ["WANController.measure_rtt"],
}
```

`get_health_data`, `_build_measurement_section`, and `_build_rtt_source_section` are **NOT in the PROTECTED map** — the protected-body diff never inspects them. As long as 244:
- does not touch `WANController.measure_rtt` (it should not — `get_health_data` is a separate method), and
- does not touch any of the 7 protected `rtt_measurement.py` seam functions (it must not — R5 confirms data already exists),

the protected-body helper returns `all_identical: true` and the **existing** `protected_body_ok_with_measure_rtt_exception` is satisfied with zero changes. **No protected-body exception widening is needed.** The planner should keep the 242 protected-body machinery verbatim and rely on `all_identical` passing.

The real SAFE-17 work reduces to three small edits in the cloned 242 verifier (see Shared Pattern: SAFE-17 below).

## Pattern Assignments

### `src/wanctl/health_check.py` :: `_build_measurement_section` (builder, transform)

**Analog:** itself (Phase 242 additive precedent in the same return dict).

**Core pattern — append flat keys to the returned dict** (verified `health_check.py:514-532`):
```python
fallback_count_raw = measurement.get("fallback_count", 0)
fallback_count = fallback_count_raw if isinstance(fallback_count_raw, int) else 0
backend_active = measurement.get("backend_active", "icmplib")
if not isinstance(backend_active, str) or not backend_active:
    backend_active = "icmplib"

return {
    "available": raw_rtt is not None,                                # BYTE-PRESERVED (238)
    "raw_rtt_ms": round(raw_rtt, 2) if raw_rtt is not None else None,  # BYTE-PRESERVED
    "staleness_sec": round(staleness, 3) if staleness is not None else None,  # BYTE-PRESERVED
    "active_reflector_hosts": list(active_hosts),
    "successful_reflector_hosts": list(successful_hosts),
    "state": state,
    "successful_count": successful_count,
    "stale": stale,
    "backend_active": backend_active,    # Phase 242 — contract field (D-03 keeps it)
    "fell_back": bool(measurement.get("fell_back", False)),
    "fallback_count": fallback_count,
    # Phase 244 additive triple appends HERE (D-01/D-02/D-03/D-04):
    #   "producer": "wanctl-backend",
    #   "backend": <measurement.get("backend") sanitized to icmplib|fping|None>,
    #   "source_ip": <measurement.get("source_ip") sanitized to str|None>,
}
```
**Defensive-coercion pattern to copy (lines 514-518):** read with `.get(key, default)`, then type-guard with `isinstance(...)` and re-coerce to a safe default. Apply the same to `producer` (always the literal `"wanctl-backend"` here), `backend` (validate ∈ {`icmplib`,`fping`} else `None`), and `source_ip` (validate non-empty `str` else `None`).

---

### `src/wanctl/wan_controller.py` :: `get_health_data` (controller data source, transform)

**Analog:** itself (Phase 242 `backend_active` threading).

**Source-data threading pattern — `getattr` with safe default off a possibly-None status** (verified `wan_controller.py:4496-4511`):
```python
rtt_backend_status = self._rtt_backend_status
backend_active = (
    getattr(rtt_backend_status, "backend_active", "icmplib")
    if rtt_backend_status is not None
    else "icmplib"
)
fell_back = (
    bool(getattr(rtt_backend_status, "fell_back", False))
    if rtt_backend_status is not None
    else False
)
fallback_count = (
    int(getattr(rtt_backend_status, "fallback_count", 0))
    if rtt_backend_status is not None
    else 0
)
```
**Measurement dict the keys land in** (verified `wan_controller.py:4539-4556`): `backend_active`/`fell_back`/`fallback_count` are set at 4553-4555 inside the `"measurement": {...}` sub-dict. Phase 244 adds `producer`/`backend`/`source_ip` to this same sub-dict, threaded the same way.

**Autorate per-sample `backend`/`source_ip` gap (Pitfall 3 / R3a — planner decision):** `_record_live_rtt_snapshot` (wan_controller.py:1350) stores only `rtt_ms/ts/hosts`, NOT `RttSample.backend`/`source_ip`. Two analog-consistent options:
- **(a) Proxy:** reuse the already-threaded `backend_active` as the autorate-path `backend`, and read `source_ip` off the same `_rtt_backend_status` via `getattr(rtt_backend_status, "source_ip", None)` if present. Smallest touch; matches the existing 4496-4511 pattern exactly. Lower post-fallback fidelity.
- **(b) Faithful:** add additive `self._last_sample_backend`/`self._last_sample_source_ip` set in `_record_live_rtt_snapshot`, read in `get_health_data`. Larger touch — **must stay clear of `WANController.measure_rtt`'s protected body**; `_record_live_rtt_snapshot` is NOT protected, so this is allowlist-safe.
Research recommendation: proxy (a) on the non-A/B autorate path; reserve faithful per-sample fidelity for the steering path. Planner's D-03 call.

---

### `src/wanctl/steering/health.py` :: `_build_rtt_source_section` (builder, transform) — PRIMARY SURFACE (D-01)

**Analog:** `health_check.py::_build_measurement_section` (same discipline, different block).

**Core pattern — emits an `rtt_source` block, NOT a `measurement` block** (verified `steering/health.py:359-377`):
```python
def _build_rtt_source_section(self, health_data: dict[str, Any]) -> dict[str, Any]:
    """Build RTT source observability section for steering."""
    source = health_data.get("rtt_source", {})
    counts = source.get("counts", {})
    age = source.get("last_measurement_age_sec")
    last_rtt = source.get("last_rtt_ms")
    return {
        "current": source.get("current", "unknown"),
        "last_successful": source.get("last_successful", "unknown"),
        "last_rtt_ms": round(last_rtt, 2) if isinstance(last_rtt, (int, float)) else None,
        "last_measurement_age_sec": round(age, 3) if isinstance(age, (int, float)) else None,
        "counts": { ... },
        # Phase 244 additive triple appends HERE (uniform JSON keys, flat):
        #   "producer": "wanctl-backend",
        #   "backend": <self._<carried> | None>,
        #   "source_ip": <self._<carried source_ip> | None>,
    }
```
**Nuance (CONTEXT/Codex flag):** "uniform shape" means the same emitted JSON keys (`producer`/`backend`/`source_ip`), NOT a shared code path. Append them flat here so a Phase 245 scraper parses them identically across all three producers. The data must first be carried onto `SteeringHealthServer` from the daemon — see the daemon wiring assignment below.

---

### `src/wanctl/steering/daemon.py` :: wiring (provider/DI carry) — additive only

**Analog:** the existing tuple-threading of `rtt_measurement`/`baseline_loader` through the same spine.

**The discard to fix (verified daemon.py:2555-2571):** `source_ip` is already computed but dropped from the return tuple.
```python
primary_rtt_config, source_ip, warnings = _load_primary_wan_config_for_rtt_backend(config)
...
rtt_backend = build_rtt_backend(primary_rtt_config, source_ip=source_ip, logger=logger, wan_key=config.primary_wan)
rtt_measurement = rtt_backend.controller_measurement
baseline_loader = BaselineLoader(config, logger)
return state_mgr, router, rtt_measurement, baseline_loader   # ← source_ip (+ handle) dropped here
```
**Existing carry spine to mirror (verified):**
- `_create_steering_components` return tuple — daemon.py:2547 (signature) / 2571 (return)
- unpacked at the call site — daemon.py:2709
- passed to constructor — daemon.py:2738 `SteeringDaemon(config, state_mgr, router, rtt_measurement, baseline_loader, logger)`
- `SteeringDaemon.__init__` — daemon.py:1126; stores `self.rtt_measurement`/`self.baseline_loader` at 1138-1139

**Additive wiring plan (follow the existing pattern exactly):** add `source_ip` (and optionally `backend_active`/the handle) to the `_create_steering_components` return tuple → unpack at 2709 → pass into `SteeringDaemon.__init__` (extend signature additively, default `None` to stay backward-compatible with any other constructor caller) → store as `self._rtt_source_ip` (+ `self._rtt_backend_active`) alongside the existing `self._rtt_source_counts` field (1163) → read in `_build_rtt_source_section`. `steering/daemon.py` IS in the 242 allowlist; this is allowlist-safe.

**Backend reachability (verified daemon.py:2612):** `source_ip = primary_cfg.get("ping_source_ip")` then null-guard → matches D-04. The handle's `.backend_active` gives the selected backend for the steering `backend` key.

---

### `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge` :: `health_payload()` (deploy endpoint, request-response)

**Analog:** the existing `measurement` blocks in the same function. **Both scripts are byte-identical in the health region — edit both identically (Pitfall 4).**

**Healthy-path measurement block (verified spectrum:267-271):**
```python
"measurement": {
    "available": available,                                              # BYTE-PRESERVED
    "raw_rtt_ms": float(raw_rtt) if isinstance(raw_rtt, (int, float)) else None,  # BYTE-PRESERVED
    "staleness_sec": age,                                                # BYTE-PRESERVED
    # Phase 244 additive — bridge never ran the wanctl seam (238 D-04 / D-02 honesty):
    "producer": "cake-autorate-bridge",
    "backend": None,
    "source_ip": None,
},
```
**Degraded-path measurement block (verified spectrum:243)** — apply the identical triple so the shape is uniform across both code paths:
```python
"measurement": {"available": False, "raw_rtt_ms": None, "staleness_sec": None,
                "producer": "cake-autorate-bridge", "backend": None, "source_ip": None},
```
Top level already labels `source: "cake-autorate-state-bridge"` (spectrum:239/263) — leave it. **Do NOT add bridge env wiring to fake a source IP** (R1 resolved: bridge env carries only `WANCTL_EXTERNAL_*` DL_IF/UL_IF; null is the only honest value).

---

### `scripts/phase244-safe17-boundary-check.sh` (verifier, batch) — clone of phase242

**Analog:** `scripts/phase242-safe17-boundary-check.sh` (the full allowlist + protected-body + AST-guard template). **Do NOT clone phase243** — 243 is measurement-only and hard-rejects ANY `src/wanctl/` diff (`"no src/wanctl edits permitted"`), which would fail closed on 244's legitimate health edits.

See Shared Pattern: SAFE-17 below for the three required diffs against the 242 template.

---

### `tests/test_phase244_safe17_verifier.py` (test mirror, batch)

**Analog:** `tests/test_phase243_safe17_verifier.py` (109 lines, verified).

**Mirror structure to copy verbatim (re-pointed to 244):**
- module constants `VERIFIER` / `EVIDENCE` paths (243 test lines 7-16) → point at `phase244-safe17-boundary-check.sh` + `244-.../evidence/safe17-boundary-244.json`
- `PHASE_CLOSE_ANCHOR` (243 test line 22) → **pin to the resolved 243-close SHA `49fb1393`** (see Metadata), NOT HEAD, NOT the provisional `380fadbd` (which the 243 test comment flags `TODO(phase-close)`)
- `detached_worktree` fixture (lines 38-49), `commit_worktree_change` helper with `SKIP_DOC_CHECK=1` (lines 52-67)
- `test_script_is_executable` (86)
- `test_fails_on_out_of_allowlist_change` (91): edit a non-allowlisted file in the worktree (use e.g. `queue_controller.py`, matching the 242 self-test choice — `wan_controller.py` IS allowlisted in 244 so it would NOT trip), commit, assert non-zero exit + the violation message
- `test_fails_on_dirty_src_wanctl_change` (102): dirty-tree assert `"uncommitted, staged, or untracked src/wanctl/ edit"`
- A `test_static_phase244_script_contract` (analog of 243's line 70) asserting 244-specific strings ARE present (`safe17-boundary-244.json`, the 244 evidence dir, `V153_ALLOWLIST_RE`, `phase239-protected-body-diff.py`, `check_measure_rtt_fping_scorer_guard`) — i.e. the inverse of the 243 contract test, because 244 keeps the 242 machinery.

---

### `tests/test_health_check.py` (extend, contract) + `tests/test_{spectrum,att}_cake_autorate_artifacts.py` (extend, integration)

See Shared Pattern: Byte-Preservation Contract Test below.

## Shared Patterns

### SAFE-17 verifier (the load-bearing cross-cutting concern)
**Source:** `scripts/phase242-safe17-boundary-check.sh` (template) + `scripts/phase239-protected-body-diff.py` (helper, unchanged).
**Apply to:** the new `scripts/phase244-safe17-boundary-check.sh`.

Three minimal diffs against the 242 clone — everything else copied verbatim:

1. **Advance the anchor.** 242 uses `ANCHOR="v1.52"` with separate per-phase close anchors (242 lines 19-22). For 244, set the comparison anchor to the resolved **243-close SHA `49fb1393`** (verify at plan time; this is the last `243-`prefixed commit, `docs(243-05): backfill plan 05 execution summary`). Keep the chained `PHASE239/240/241_CLOSE_ANCHOR` byte-identity gates (lines 506-532) — 244 touches none of those frozen files. Update `OUT`/`ALLOWED_OUT_PREFIX` (242 lines 23-24) to the `244-.../evidence/` path.

2. **Add `steering/health.py` to the allowlist regex.** Verified: `steering/health` appears **0 times** in the 242 `V153_ALLOWLIST_RE` (line 25). Because D-01 surfaces attribution there, add `steering/health\.py` to the regex AND the `allowed_paths` set in the embedded Python (242 lines 120-132). Every other 244-touched src file (`health_check.py`, `wan_controller.py`, `steering/daemon.py`) is already allowlisted — confirmed.

3. **Keep the protected-body machinery verbatim — do NOT widen it.** Verified `phase239-protected-body-diff.py:21-32`: the PROTECTED map covers only `WANController.measure_rtt` + 7 `rtt_measurement.py` seam functions. 244's health builders (`get_health_data`, `_build_measurement_section`, `_build_rtt_source_section`) are NOT protected, so they do not trip the diff. Provided 244 leaves `measure_rtt` and the seam untouched, `phase239-protected-body-diff.py` returns `all_identical: true` and the existing `protected_body_ok_with_measure_rtt_exception` (242 lines 373-402) passes unchanged. Keep `check_measure_rtt_fping_scorer_guard` (242 lines 258-371) and its `FORBIDDEN_TOKENS` (`EWMA/ewma/dwell/deadband/arbitration/fusion/factor_down/step_up/ceiling/floor`) in force — this structurally proves no control-logic drift leaked in via the allowlisted files.

This supersedes the research's "widen the protected-body exception" guidance, which over-scoped the change.

### Byte-preservation contract test
**Source:** `tests/test_health_check.py::test_measurement_byte_preserved` (line 1960) and `::test_measurement_backend_fallback_keys_are_per_wan` (line 1989); `tests/test_spectrum_cake_autorate_artifacts.py::test_state_bridge_serves_wanctl_compatible_health_endpoint` (line 164).
**Apply to:** all three producers' tests.

**Direct-builder assertion pattern (no server needed — verified 1989-2026):** construct `HealthCheckHandler.__new__(HealthCheckHandler)`, call `_build_measurement_section({"measurement": {...}})`, assert exact keys+values. Extend with `producer`/`backend`/`source_ip` assertions and a strict-superset key check pinning the existing contract keys.

**End-to-end server assertion pattern (verified 1942-1958):** `start_health_server` → `urllib.request.urlopen` → `data["wans"][0]["measurement"]`; assert `available`/`raw_rtt_ms`/`staleness_sec`/`backend_active` byte-preserved, then assert the new triple. The existing `test_measurement_byte_preserved` (1960) already anticipates 244 in its docstring — extend, don't replace.

**Bridge integration pattern (verified spectrum 164-213):** spawns the bridge subprocess, polls `/health`, asserts `wan["measurement"]["raw_rtt_ms"] > 0` etc. Add `wan["measurement"]["producer"] == "cake-autorate-bridge"`, `wan["measurement"]["backend"] is None`, `wan["measurement"]["source_ip"] is None`. Mirror identically in `test_att_cake_autorate_artifacts.py`.

### Defensive `.get` + `isinstance` coercion
**Source:** `health_check.py:514-518`, `steering/health.py:368-371`, bridge `health_payload` (the `isinstance(raw_rtt, (int, float))` guards).
**Apply to:** every new key on every producer. Read with `.get(key, default)`, type-guard, re-coerce to a safe value; never let a malformed upstream payload raise inside a health builder.

### The attribution triple (uniform JSON contract across all three producers)
| Key | wanctl-backend paths (steering, autorate) | cake-autorate-bridge |
|-----|-------------------------------------------|----------------------|
| `producer` | `"wanctl-backend"` | `"cake-autorate-bridge"` |
| `backend` | `icmplib` \| `fping` \| `null` | `null` (seam never ran) |
| `source_ip` | configured per-WAN source \| `null` | `null` (no source-IP env) |

Flat keys (NOT a nested object — CONTEXT specifies parse-parity with `backend_active`). `backend_active` (Phase 242, factory-selected) is KEPT and byte-preserved; `backend` (per-sample, producing) is the additive newcomer (D-03) — they are distinct facts, not duplicates.

## No Analog Found

None. Every file in this phase extends an existing pattern, function, or sibling. There is no greenfield surface — this is the project's established additive-health + per-phase-SAFE-17-clone cadence.

## Metadata

**Analog search scope:** `src/wanctl/` (health builders, controller, steering daemon), `deploy/scripts/` (state bridges), `scripts/` (phase238-243 SAFE-17 verifiers + protected-body helper), `tests/`.
**Files scanned (read):** `health_check.py`, `wan_controller.py`, `steering/health.py`, `steering/daemon.py`, `cake-autorate-spectrum-state-bridge`, `phase242-safe17-boundary-check.sh`, `phase239-protected-body-diff.py`, `test_phase243_safe17_verifier.py`, `test_health_check.py`, `test_spectrum_cake_autorate_artifacts.py`.
**Resolved 243-close anchor:** `49fb1393` (verify with `git log` at plan time; supersedes the provisional `380fadbd` in `test_phase243_safe17_verifier.py:22`).
**Verified facts that correct the research:** (1) health builders are NOT in the protected-body map → no exception widening needed; (2) `steering/health.py` is absent from the 242 allowlist regex → must be added; (3) `_create_steering_components` returns a 4-tuple at daemon.py:2571 with `source_ip` already computed but dropped.
**Pattern extraction date:** 2026-06-18
