# Phase 205: Tin-agnostic CAKE signal + allow_wash gate — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 10 (5 src, 5 test)
**Analogs found:** 10 / 10 (every site has a closest in-tree match)

> All file paths absolute. Line numbers verified against working tree at HEAD = `b82abf0` (clean baseline, equal to v1.43 close `6508d68 + docs-only commits`).

---

## File Classification

| File | Status | Role | Data Flow | Closest Analog | Match Quality |
|------|--------|------|-----------|----------------|---------------|
| `/home/kevin/projects/wanctl/src/wanctl/cake_signal.py` | modify | service (signal processor) | transform (per-cycle stats → snapshot) | self (4 sibling aggregation sites) | exact |
| `/home/kevin/projects/wanctl/src/wanctl/cake_params.py` | modify | builder (config → tc params) | transform (YAML dict → params dict) | self (existing override loop at 150-157) | exact |
| `/home/kevin/projects/wanctl/src/wanctl/backends/linux_cake.py` | modify | backend adapter (subprocess tc) | request-response (cmd args → kernel) | self — `no-ack-filter` boolean-pair pattern at 396-400 | exact |
| `/home/kevin/projects/wanctl/src/wanctl/backends/netlink_cake.py` | modify | backend adapter (netlink tc) | request-response (kwargs → kernel) | self — `(tc_flag, pyroute2_kwarg)` mapping list at 478-484 | exact |
| `/home/kevin/projects/wanctl/src/wanctl/check_config_validators.py` | modify | config (allowlist) | static lookup | self — `KNOWN_AUTORATE_PATHS` cake_params block at 154-163 | exact |
| `/home/kevin/projects/wanctl/tests/test_cake_signal.py` | modify (extend) | test | unit (in-memory fixture) | self — `TestCakeSignalProcessorTinSeparation` at 322-348 | exact |
| `/home/kevin/projects/wanctl/tests/test_cake_params.py` | modify (extend) | test | unit (builder call + assert) | self — `TestBuildCakeParamsExcluded` at 189-202 | exact |
| `/home/kevin/projects/wanctl/tests/backends/test_linux_cake.py` | modify (extend) | test | unit (`subprocess.run` mock) | self — `test_initialize_cake_boolean_flags` at 700-715 | exact |
| `/home/kevin/projects/wanctl/tests/backends/test_netlink_cake.py` | modify (extend) | test | unit (`IPRoute` mock) | self — `test_initialize_cake_maps_boolean_flags` + `…_maps_false_boolean_flags` at 494-519 | exact |
| `/home/kevin/projects/wanctl/tests/test_check_config.py` | modify (extend) | test | unit (`check_unknown_keys` call + filter) | self — `test_cake_params_no_unknown_key_warnings` at 1306-1325 | exact |

> **Note on `test_check_config_validators.py`:** the research doc names this file, but it does not exist. The validator is exercised in `tests/test_check_config.py`. Plan should target the existing file rather than create a new one (consistency with the rest of the suite).

---

## Pattern Assignments

### `src/wanctl/cake_signal.py` (transform service)

**Analog:** self — the same `range(1, len(tins_raw))` aggregation appears **6 times** in `update()` (3 in cold-start at lines 254-280, 3 in steady-state at lines 343-369, plus 2 drop-sum sites at lines 307-308).

**Helper insertion point** — top of module after `u32_delta` (~line 65):

Pattern to write (Phase 205 design from RESEARCH.md §"Pattern 1"):
```python
def _active_tin_indices(tin_count: int) -> range:
    """Return the indices of tins that count as 'active load'.

    For multi-tin diffserv layouts, tin index 0 is Bulk and is intentionally
    deprioritised — its drops/backlog are expected under load and excluded
    from the active signal. For single-tin besteffort layouts, the one tin
    IS the active tin; there is no Bulk to exclude.
    """
    if tin_count >= 2:
        return range(1, tin_count)
    return range(tin_count)
```

**Aggregation sites to rewrite** (verbatim current code; only the iteration range changes):

1. **Cold-start backlog** (current lines 254-257):
```python
active_backlog = sum(
    tins_raw[i].get("backlog_bytes", 0) for i in range(1, len(tins_raw))
)
```
→ replace `range(1, len(tins_raw))` with `_active_tin_indices(len(tins_raw))`.

2. **Cold-start peak/avg/base delay** (lines 258-269): same substitution; `default=0` on `max(...)` already handles tin_count==0 correctly.

3. **Cold-start max_delay_delta** (lines 270-280): same substitution.

4. **Steady-state active_drops** (line 307):
```python
active_drops = sum(deltas.get(i, 0) for i in range(1, len(tins_raw)))
total_drops = sum(deltas.get(i, 0) for i in range(len(tins_raw)))
```
Active line gets the helper; **total line stays as-is** (`range(len(tins_raw))` covers all tins by design — do not touch).

5. **Steady-state backlog/peak/avg/base** (lines 343-358): same substitution as #1-2.

6. **Steady-state max_delay_delta** (lines 359-369): same substitution as #3.

**Diffserv4 byte-identity invariant:** `_active_tin_indices(4) == range(1, 4)` — verify with `test_phase_193_replay.py` and any other replay test.

**Tin-name fallback** (lines 237 and 326) — already correctly handles single-tin case (`f"Tin{i}"`); per RESEARCH Q4, optional one-liner to set `["BestEffort"]` for `len(tins_raw) == 1` is *out of scope* unless the planner pulls it in.

---

### `src/wanctl/cake_params.py` (transform builder)

**Analog:** self — the existing override loop at lines 150-157.

**Current code** (verbatim, lines 150-157):
```python
if cake_config:
    for key, value in cake_config.items():
        tc_key = YAML_TO_TC_KEY.get(key, key)
        if tc_key in EXCLUDED_PARAMS:
            raise ConfigValidationError(
                f"Excluded CAKE parameter: {key!r} -- not valid for transparent bridge topology"
            )
        params[tc_key] = value
```

**Target shape** (from RESEARCH §"Pattern 2"; the `allow_wash` pop happens *before* the loop so it's never iterated as a tc param):
```python
# Pop the control flag before the override loop -- it's not a tc param.
allow_wash = bool(cake_config.get("allow_wash", False)) if cake_config else False

if cake_config:
    for key, value in cake_config.items():
        if key == "allow_wash":
            continue  # control flag, consumed above
        tc_key = YAML_TO_TC_KEY.get(key, key)
        if tc_key in EXCLUDED_PARAMS:
            # D-08 transparent-bridge protection still rejects nat / autorate-ingress
            # unconditionally; wash is the only param the operator may opt into via
            # the per-WAN allow_wash gate.
            if tc_key == "wash" and allow_wash:
                pass  # fall through to assignment
            else:
                raise ConfigValidationError(
                    f"Excluded CAKE parameter: {key!r} -- not valid for "
                    f"transparent bridge topology"
                )
        params[tc_key] = value
```

**Strict-bool guard** (per RESEARCH §"Security Domain"): the safer form is `cake_config.get("allow_wash") is True` — string `"false"` would be truthy under `bool(...)`. Plan should pick one and document; recommend strict-`is True` to match `cake_signal.py`'s isinstance(v, bool) parsing pattern.

**Defaults preserved:** `EXCLUDED_PARAMS = {"nat", "wash", "autorate-ingress"}` (line 60) **stays**. The gate is at the check site, not the membership site (per RESEARCH §"Anti-Patterns: Removing wash from EXCLUDED_PARAMS").

---

### `src/wanctl/backends/linux_cake.py` (backend, request-response)

**Analog:** self — the `no-ack-filter` symmetric-emission pattern at lines 396-400.

**Current code** (verbatim, lines 396-400):
```python
for flag in ("split-gso", "ack-filter", "ingress"):
    if params.get(flag):
        cmd_args.append(flag)
    elif flag == "ack-filter" and flag in params:
        cmd_args.append("no-ack-filter")
```

**Target shape** (mirror the `ack-filter` / `no-ack-filter` symmetry for `wash` per RESEARCH Q2):
```python
for flag in ("split-gso", "ack-filter", "ingress", "wash"):
    if params.get(flag):
        cmd_args.append(flag)
    elif flag == "ack-filter" and flag in params:
        cmd_args.append("no-ack-filter")
    elif flag == "wash" and flag in params:
        cmd_args.append("nowash")
```

**Token verification:** `tc-cake(8)` accepts `wash` and `nowash` (per `check_cake.py:55-68` direction-dependent wash audit; symmetric with `ack-filter`/`no-ack-filter`). RESEARCH §"Don't Hand-Roll" notes pyroute2 already supports `wash` natively.

**Docstring update** (lines 363-364): add `"wash"` to the listed boolean flags.

---

### `src/wanctl/backends/netlink_cake.py` (backend, request-response)

**Analog:** self — the `(tc_flag, pyroute2_kwarg)` mapping list at lines 478-484.

**Current code** (verbatim, lines 478-484):
```python
for tc_flag, pyroute2_kwarg in [
    ("split-gso", "split_gso"),
    ("ack-filter", "ack_filter"),
    ("ingress", "ingress"),
]:
    if tc_flag in params:
        kwargs[pyroute2_kwarg] = bool(params[tc_flag])
```

**Target shape** (one tuple addition; pyroute2 `wash` kwarg verified by RESEARCH introspection 2026-05-13):
```python
for tc_flag, pyroute2_kwarg in [
    ("split-gso", "split_gso"),
    ("ack-filter", "ack_filter"),
    ("ingress", "ingress"),
    ("wash", "wash"),
]:
    if tc_flag in params:
        kwargs[pyroute2_kwarg] = bool(params[tc_flag])
```

**Docstring update** (lines 416-426): add `wash -> wash=True/False` to the kwarg map list.

**Out of scope (defer to Phase 209):** `_DIFFSERV_NAME_TO_INT` besteffort=2 bug at lines 62-66 — RESEARCH §"Pitfall 5" + Q3 explicitly defer this fix to Phase 209's config flip. Do not touch in 205.

---

### `src/wanctl/check_config_validators.py` (config allowlist)

**Analog:** self — the existing `cake_params.*` block at lines 154-163.

**Current code** (verbatim, lines 154-163):
```python
# CAKE params (for linux-cake transport, Phase 107)
"cake_params",
"cake_params.upload_interface",
"cake_params.download_interface",
"cake_params.overhead",
"cake_params.mpu",
"cake_params.memlimit",
"cake_params.rtt",
"cake_params.ack_filter",
"cake_params.ingress",
```

**Target shape:** add `"cake_params.allow_wash",` and `"cake_params.wash",` (the latter is the actual tc flag, currently absent — operator setting `wash: true` under `cake_params:` would also WARN today; add both for full coverage):
```python
# CAKE params (for linux-cake transport, Phase 107)
"cake_params",
"cake_params.upload_interface",
"cake_params.download_interface",
"cake_params.overhead",
"cake_params.mpu",
"cake_params.memlimit",
"cake_params.rtt",
"cake_params.ack_filter",
"cake_params.ingress",
"cake_params.wash",         # ADDED (Phase 205) -- tc flag, gated by allow_wash
"cake_params.allow_wash",   # ADDED (Phase 205) -- per-WAN gate flag
```

> **Operator decision needed:** RESEARCH §"Pitfall 4" mentions only `allow_wash`. Adding `cake_params.wash` is consistent (same omission would WARN); planner should confirm with operator whether to bundle both in 205 or defer the bare `wash` key to Phase 209's config flip.

---

### `tests/test_cake_signal.py` (extend — unit tests)

**Analog:** self — `TestCakeSignalProcessorTinSeparation` class at lines 322-348, fixture `make_mock_stats` at lines 29-68.

**Fixture extension pattern** — parameterize on `tin_count` to preserve all existing 4-tin tests (verbatim current code 29-68 + the extension):
```python
def make_mock_stats(
    tin_drops: list[int] | None = None,
    tin_backlog: list[int] | None = None,
    tin_peak_delay: list[int] | None = None,
    tin_avg_delay: list[int] | None = None,
    tin_base_delay: list[int] | None = None,
    tin_count: int = 4,  # ADDED (Phase 205) -- 1 for besteffort, 4 for diffserv4
) -> dict[str, Any]:
    tin_drops = tin_drops or [0] * tin_count
    tin_backlog = tin_backlog or [0] * tin_count
    tin_peak_delay = tin_peak_delay or [0] * tin_count
    tin_avg_delay = tin_avg_delay or [0] * tin_count
    tin_base_delay = tin_base_delay or [0] * tin_count
    return {
        ...
        "tins": [ {...} for i in range(tin_count) ],   # was range(4)
    }
```

**New test class `TestCakeSignalProcessorBestEffort`** — analog: `TestCakeSignalProcessorTinSeparation::test_besteffort_drops_in_both_rates` at line 339-348. Mirror exactly with `tin_count=1`:
```python
class TestCakeSignalProcessorBestEffort:
    """Tests that single-tin besteffort layout produces non-zero active signals."""

    def test_single_tin_drops_in_active_rate(self) -> None:
        cfg = CakeSignalConfig(enabled=True, time_constant_sec=1.0)
        proc = CakeSignalProcessor(config=cfg)
        proc.update(make_mock_stats(tin_drops=[0], tin_count=1))   # cold start
        snap = proc.update(make_mock_stats(tin_drops=[100], tin_count=1))
        assert snap is not None
        assert snap.drop_rate > 0.0       # CRITICAL: was 0.0 before fix
        assert snap.total_drop_rate > 0.0

    def test_single_tin_backlog_aggregates(self) -> None:
        # Mirrors test_backlog_excludes_bulk at line 350-359
        ...

    def test_single_tin_peak_delay_aggregates(self) -> None:
        # Mirrors test_peak_delay_excludes_bulk at line 361-370
        ...
```

**New test class `TestCakeSignalProcessorBestEffortOracle`** — replay-equivalence between besteffort 1-tin and diffserv4 with the same logical load placed in the BestEffort tin (index 1 for 4-tin, index 0 for 1-tin). RESEARCH Q1 recommends synthesized fixture; pure dict comparison.

---

### `tests/test_cake_params.py` (extend — unit tests)

**Analog:** self — `TestBuildCakeParamsExcluded` at lines 189-202.

**Current code** (verbatim, lines 189-202):
```python
class TestBuildCakeParamsExcluded:
    """Verify excluded params raise ConfigValidationError."""

    def test_nat_excluded(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"nat": True})

    def test_wash_excluded(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"wash": True})

    def test_autorate_ingress_excluded(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params("upload", {"autorate_ingress": True})
```

**Critical:** `test_wash_excluded` MUST continue passing — it covers the `allow_wash` absent / false default.

**New class `TestBuildCakeParamsAllowWash`** — mirror exact shape:
```python
class TestBuildCakeParamsAllowWash:
    """Verify per-WAN allow_wash gate (Phase 205, TOPO-02)."""

    def test_allow_wash_true_permits_wash(self) -> None:
        params = build_cake_params(
            "download", {"allow_wash": True, "wash": True}
        )
        assert params.get("wash") is True
        assert "allow_wash" not in params  # control flag stripped

    def test_allow_wash_false_rejects_wash(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params(
                "download", {"allow_wash": False, "wash": True}
            )

    def test_allow_wash_absent_rejects_wash(self) -> None:
        # Identical to existing test_wash_excluded but documents the absent-default
        with pytest.raises(ConfigValidationError):
            build_cake_params("download", {"wash": True})

    def test_allow_wash_does_not_permit_nat(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params(
                "download", {"allow_wash": True, "nat": True}
            )

    def test_allow_wash_does_not_permit_autorate_ingress(self) -> None:
        with pytest.raises(ConfigValidationError):
            build_cake_params(
                "download", {"allow_wash": True, "autorate_ingress": True}
            )
```

---

### `tests/backends/test_linux_cake.py` (extend — integration test)

**Analog:** self — `test_initialize_cake_boolean_flags` at lines 699-715.

**Current code** (verbatim, lines 699-715):
```python
@patch("wanctl.backends.linux_cake.subprocess.run")
def test_initialize_cake_boolean_flags(self, mock_run, backend):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    backend.initialize_cake(
        {
            "split-gso": True,
            "ingress": True,
            "ecn": True,
        }
    )
    cmd = mock_run.call_args[0][0]
    assert "split-gso" in cmd
    assert "ingress" in cmd
    # ecn excluded -- not supported by iproute2-6.15.0, CAKE default anyway
    assert "ecn" not in cmd
```

**New tests** (same fixture, same patch target, same `cmd` extraction):
```python
@patch("wanctl.backends.linux_cake.subprocess.run")
def test_initialize_cake_emits_wash(self, mock_run, backend):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    backend.initialize_cake({"wash": True})
    cmd = mock_run.call_args[0][0]
    assert "wash" in cmd
    assert "nowash" not in cmd

@patch("wanctl.backends.linux_cake.subprocess.run")
def test_initialize_cake_emits_nowash_on_explicit_false(self, mock_run, backend):
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    backend.initialize_cake({"wash": False})
    cmd = mock_run.call_args[0][0]
    assert "nowash" in cmd
    assert "wash" not in (t for t in cmd if t != "nowash")  # no bare "wash"
```

---

### `tests/backends/test_netlink_cake.py` (extend — integration test)

**Analog:** self — `test_initialize_cake_maps_boolean_flags` (494-508) + `…_maps_false_boolean_flags` (511-519).

**Current code** (verbatim, lines 493-519):
```python
@patch("wanctl.backends.netlink_cake.IPRoute")
def test_initialize_cake_maps_boolean_flags(self, MockIPRoute, backend):
    """Boolean flags: split-gso, ack-filter, ingress map to pyroute2 kwargs."""
    mock_instance = MagicMock()
    mock_instance.link_lookup.return_value = [42]
    MockIPRoute.return_value = mock_instance

    backend.initialize_cake({
        "split-gso": True,
        "ack-filter": True,
        "ingress": True,
    })
    call_kwargs = mock_instance.tc.call_args[1]
    assert call_kwargs.get("split_gso") is True
    assert call_kwargs.get("ack_filter") is True
    assert call_kwargs.get("ingress") is True

@patch("wanctl.backends.netlink_cake.IPRoute")
def test_initialize_cake_maps_false_boolean_flags(self, MockIPRoute, backend):
    """Explicit false flags map to pyroute2 kwargs so overrides are applied."""
    mock_instance = MagicMock()
    mock_instance.link_lookup.return_value = [42]
    MockIPRoute.return_value = mock_instance

    backend.initialize_cake({"ack-filter": False})
    call_kwargs = mock_instance.tc.call_args[1]
    assert call_kwargs.get("ack_filter") is False
```

**New test** (clone the structure, add wash assertion):
```python
@patch("wanctl.backends.netlink_cake.IPRoute")
def test_initialize_cake_passes_wash_kwarg(self, MockIPRoute, backend):
    """wash flag maps to pyroute2 wash kwarg (Phase 205, TOPO-02)."""
    mock_instance = MagicMock()
    mock_instance.link_lookup.return_value = [42]
    MockIPRoute.return_value = mock_instance

    backend.initialize_cake({"wash": True})
    call_kwargs = mock_instance.tc.call_args[1]
    assert call_kwargs.get("wash") is True

@patch("wanctl.backends.netlink_cake.IPRoute")
def test_initialize_cake_passes_wash_false_kwarg(self, MockIPRoute, backend):
    mock_instance = MagicMock()
    mock_instance.link_lookup.return_value = [42]
    MockIPRoute.return_value = mock_instance

    backend.initialize_cake({"wash": False})
    call_kwargs = mock_instance.tc.call_args[1]
    assert call_kwargs.get("wash") is False
```

---

### `tests/test_check_config.py` (extend — allowlist coverage)

**Analog:** self — `test_cake_params_no_unknown_key_warnings` at lines 1306-1325 (in the relevant test class — likely `TestValidateLinuxCake`, planner should locate the parent class via grep).

**Current code** (verbatim, lines 1306-1325):
```python
def test_cake_params_no_unknown_key_warnings(self):
    """cake_params paths must be in KNOWN_AUTORATE_PATHS -- no false positives."""
    data = self._make_config(
        transport="linux-cake",
        cake_params={
            "upload_interface": "enp8s0",
            "download_interface": "enp9s0",
            "overhead": "docsis",
            "memlimit": "32mb",
            "rtt": "100ms",
        },
    )
    data["queues"] = {"download": "WAN-Download", "upload": "WAN-Upload"}
    data["continuous_monitoring"] = {"enabled": True}
    results = check_unknown_keys(data)
    unknown_cake = [
        r for r in results if r.severity == Severity.WARN and "cake_params" in r.field
    ]
    assert len(unknown_cake) == 0, f"Unexpected unknown key warnings: {unknown_cake}"
```

**New test** (same `_make_config` helper, add `allow_wash` and `wash` to the params, identical assertion shape):
```python
def test_cake_params_allow_wash_no_unknown_key_warning(self):
    """allow_wash and wash paths must be in KNOWN_AUTORATE_PATHS (Phase 205)."""
    data = self._make_config(
        transport="linux-cake",
        cake_params={
            "upload_interface": "enp8s0",
            "download_interface": "enp9s0",
            "allow_wash": True,
            "wash": True,
        },
    )
    data["queues"] = {"download": "WAN-Download", "upload": "WAN-Upload"}
    data["continuous_monitoring"] = {"enabled": True}
    results = check_unknown_keys(data)
    unknown = [
        r for r in results
        if r.severity == Severity.WARN
        and ("allow_wash" in r.field or r.field.endswith(".wash"))
    ]
    assert len(unknown) == 0, f"Unexpected unknown key warnings: {unknown}"
```

---

## Shared Patterns

### Pattern S1: "Gate-before-emit" symmetry

**Source:** RESEARCH §"Pitfall 1: Half-wired wash gate".
**Apply to:** all three of `cake_params.py` + `linux_cake.py` + `netlink_cake.py` in the **same commit / wave**.

If `cake_params.py` permits `wash` but the backend emission loops don't know about it, the params dict carries `wash: True` and it's silently dropped before reaching `tc`. The unit test for the params dict passes; the daemon log says "Initialized CAKE on … besteffort split-gso ingress" with no wash token. The plan must include all three edits as a single atomic wave.

### Pattern S2: Iteration-range-only refactor (byte-identity guarantee)

**Source:** RESEARCH §"Pitfall 3: Diffserv4 byte-identity regression" + §"Architecture Patterns: tin-agnostic helper".
**Apply to:** every aggregation site in `cake_signal.py`.

The refactor must change *only* the iteration range, not the inner expression structure or sum order. Diffserv4 path must remain bit-for-bit identical to v1.43. Verification: `tests/test_phase_193_replay.py`, `test_phase_194_replay.py`, `test_phase_195_replay.py` pass without modification. These are the SAFE-09 hard gate.

### Pattern S3: Mock-and-extract for backend integration tests

**Source:** existing pattern at `tests/backends/test_linux_cake.py:699-715` and `tests/backends/test_netlink_cake.py:494-519`.
**Apply to:** all new wash emission tests.

Standard shape:
1. Patch the I/O boundary (`subprocess.run` for linux_cake; `IPRoute` for netlink_cake).
2. Configure the mock return value.
3. Call `backend.initialize_cake({...})` with only the params under test.
4. Extract the recorded call args (`mock_run.call_args[0][0]` for cmd list; `mock_instance.tc.call_args[1]` for kwargs).
5. Assert presence/absence of expected tokens / kwargs.

No new fixtures, no new patch targets. Reuse the `backend` fixture already in `conftest.py` for each backend test directory.

### Pattern S4: Strict-bool guard for control flags

**Source:** RESEARCH §"Security Domain" (V5 Input Validation).
**Apply to:** `cake_params.py:allow_wash` parsing.

YAML coerces `true`/`false` → Python bool, but `bool("false") == True` (operator typo trap). Use either:
- `cake_config.get("allow_wash") is True` (strict — recommended)
- `bool(cake_config.get("allow_wash", False))` (permissive)

Plan must pick one explicitly. Strict is symmetric with how `cake_signal.py` handles its bool fields (RESEARCH cites `isinstance(v, bool)` precedent).

---

## No Analog Found

None — every file in scope has a clean in-tree analog.

---

## Cross-Phase Notes (informational, not actionable in 205)

| Item | Why deferred | Phase | Source |
|------|--------------|-------|--------|
| `_DIFFSERV_NAME_TO_INT` besteffort=2 → 3 fix | SAFE-09 bounds 205 to cake_signal.py + cake_params.py; netlink_cake.py is touched only for the wash mapping line, not the constants block | 209 | RESEARCH §"Pitfall 5", Q3 |
| `OPTIMAL_WASH` per-WAN auditor in `check_cake.py` | RouterOS-side audit, separate from Linux CAKE qdisc emission | 209 | RESEARCH §"Pitfall 6" |
| Tin-name override `["BestEffort"]` for 1-tin Prometheus label | Cosmetic; current `f"Tin{i}"` fallback is correct | 206 or 209 | RESEARCH Q4 |

Document in Phase 205 RETRO so Phase 209 plan picks them up explicitly.

---

## Metadata

**Analog search scope:** `src/wanctl/`, `src/wanctl/backends/`, `tests/`, `tests/backends/`
**Files scanned (Read):** 7 source/test files
**Files referenced via grep only:** 2 (test_check_config.py, check_config_validators.py upper region)
**Re-reads:** none
**Pattern extraction date:** 2026-05-13
**Working tree HEAD:** `b82abf0` (clean v1.44 baseline; equal-to-`6508d68` for src/wanctl/)
