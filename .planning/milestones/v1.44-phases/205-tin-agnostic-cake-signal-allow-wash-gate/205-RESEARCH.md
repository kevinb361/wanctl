# Phase 205: Tin-agnostic CAKE signal + allow_wash gate — Research

**Researched:** 2026-05-13
**Domain:** wanctl control-path — CAKE signal aggregation + qdisc parameter builder
**Confidence:** HIGH (all claims [VERIFIED] from in-tree source, tests, pyroute2 introspection, or git diff against `6508d68`)

---

## Summary

Phase 205 is a surgical, control-path-bounded refactor of two files:
`src/wanctl/cake_signal.py` and `src/wanctl/cake_params.py`. SAFE-09 limits
the diff to those two files plus `__init__.py` (version bump) for the
entire v1.44 milestone — Phase 205 itself touches only the first two.

The first edit (TOPO-01) is smaller than the SEED-001 framing implies. The
existing aggregation in `cake_signal.py` **already iterates `range(len(tins_raw))`
and `range(1, len(tins_raw))`** — there is no `len() == 4` assertion or
`tins[0..3]` indexed access. What's broken is the **semantic** assumption
behind "active = exclude index 0": for a single-tin besteffort qdisc,
`range(1, 1)` is empty and `active_drops/backlog/peak_delay` collapse to
permanent zero. The fix is a small policy switch: "exclude the Bulk tin
when there is more than one tin; otherwise the only tin IS the active tin."
This preserves diffserv4 byte-identical behavior for ATT.

The second edit (TOPO-02) is a per-WAN config gate flipping `wash` from
unconditionally-excluded to conditionally-permitted. **Three call sites
need the gate**, not one: (1) `cake_params.build_cake_params()` —
EXCLUDED_PARAMS check; (2) `backends/linux_cake.py:initialize_cake()`
boolean-flag emission loop (currently has no `wash` token); (3)
`backends/netlink_cake.py:initialize_cake()` boolean-flag mapping loop
(currently maps only split-gso/ack-filter/ingress to pyroute2 kwargs).
Plus the validator allowlist in `check_config_validators.py:155-163`
needs `cake_params.allow_wash` added or daemon startup emits a WARN.

**Primary recommendation:** Keep TOPO-01 a literal three-line semantic
patch (helper function + replace `range(1, len(tins_raw))` with
`active_indices(tins_raw)`); keep TOPO-02 a single config flag that flows
through the existing `cake_config` override path with a one-token
exception added to the EXCLUDED_PARAMS gate. Add the new key to
`KNOWN_AUTORATE_PATHS` and to both backend init loops in the same commit
or the gate is half-wired.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOPO-01 | `src/wanctl/cake_signal.py` aggregation tin-agnostic at lines 13/173/306; identical for ATT diffserv4; new besteffort path covered by replay-oracle test | §"cake_signal.py current state" + §"Replay test pattern" + §"Architecture Patterns: tin-agnostic helper" |
| TOPO-02 | Per-WAN `cake_params.allow_wash: bool = false`; default false; D-08 EXCLUDED_PARAMS still excludes `nat` and `autorate-ingress` | §"cake_params.py current state" + §"Don't Hand-Roll" + §"Pitfalls: gate half-wired" |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- **Production stability priority:** stability > safety > clarity > elegance. No threshold/algorithm/EWMA/dwell/deadband/burst changes (SAFE-09).
- **Conservative on control path:** prefer targeted fixes over broad cleanup. Both files are core control path.
- **Portable controller:** deployment specifics in YAML, not Python branching. The `allow_wash` flag must live in YAML; no `if wan_name == "spectrum"` in Python.
- **Knowledge discovery:** RAG/intel/graph first before raw grep. (Used live source reading + git for this research because the affected files are tiny and the targets are exact line/symbol level.)
- **`make ci` (or `.venv/bin/pytest tests/test_cake_signal.py tests/test_cake_params.py -v`)** before commit; project-finalizer agent before commit.

---

## Architectural Responsibility Map

This phase is a single-tier code refactor; the responsibility map is trivial but documented for plan-checker sanity:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CAKE signal aggregation (cake_signal.py) | wanctl daemon control loop | — | Pure Python, runs in `WANController` per-cycle |
| qdisc parameter construction (cake_params.py) | wanctl daemon startup | — | Pure builder, called once per direction at `LinuxCakeAdapter.from_config` |
| qdisc tc args emission (linux_cake.py / netlink_cake.py) | wanctl daemon startup → kernel netlink/subprocess | kernel CAKE qdisc | Final consumer of `wash` flag — gate is wasted if these don't learn `wash` |
| YAML schema allowlist (check_config_validators.py) | wanctl daemon startup validation | — | Unknown-key detector; new YAML key must be registered or WARNs at every startup |

---

## Standard Stack

This is a maintenance phase on existing code; no new libraries are needed. Documenting the existing relevant surface:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyroute2 | >=0.9.5 (verified installed in `.venv`) | Netlink qdisc operations | Already a project dep via `linux-cake-netlink` transport; supports `wash` kwarg natively (verified: `pyroute2.netlink.rtnl.tcmsg.sched_cake.options.nla_map` contains `TCA_CAKE_WASH`) [VERIFIED: introspection 2026-05-13] |
| pytest | (per project) | Test runner | Already used by all `test_cake_*.py` files |
| pyyaml | (per project) | YAML parser | Already used in `cake_signal.py` test harness via `_make_controller_with_yaml` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest fixtures (`make_mock_stats`) | in-tree at `tests/test_cake_signal.py:29-68` | Synthetic CAKE stats dict factory | Reuse + parameterize for variable tin count |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New helper `_active_tin_indices(tins_raw)` in cake_signal.py | In-line `range(1 if len(tins_raw) > 1 else 0, len(tins_raw))` everywhere | Helper is more readable, single point of change, testable in isolation. Recommended. |
| `cake_config["allow_wash"]` flag-style | New top-level YAML section | Flag fits existing per-key cake_params shape; new section duplicates structure. Recommended: flag. |

**Installation:** No new packages.

**Version verification:** No new packages to verify. pyroute2 already pinned in `pyproject.toml`.

---

## Architecture Patterns

### System Architecture Diagram (Phase 205 scope)

```
                     YAML config (spectrum.yaml / att.yaml)
                                    |
                                    v
         +---------- cake_params section dict ----------+
         |                                              |
         v                                              v
  build_cake_params()                          _parse_cake_signal_config()
  (cake_params.py)                                  (wan_controller.py)
         |                                              |
         | EXCLUDED_PARAMS check                        v
         |  - nat: always reject                  CakeSignalConfig
         |  - autorate-ingress: always reject           |
         |  - wash: REJECT unless allow_wash=true       v
         |                                       CakeSignalProcessor
         v                                              |
  params dict {diffserv, wash?, ...}                    | per-cycle
         |                                              v
         v                                       NetlinkCakeBackend
  initialize_cake()                              .get_queue_stats()
  (linux_cake.py OR netlink_cake.py)                    |
         | tc args list / pyroute2 kwargs               | tins_raw: variable-length
         |   <- ADD: emit "wash" token                  v
         v   <- ADD: pyroute2 kwargs[wash]=True   CakeSignalProcessor.update()
  kernel CAKE qdisc                                     |
                                                        | tin-agnostic aggregation
                                                        v
                                                CakeSignalSnapshot
                                                  (drop_rate, backlog, peak_delay)
                                                        |
                                                        v
                                                 QueueController
```

### Component Responsibilities (Phase 205)

| File | Responsibility | Phase 205 edit |
|------|----------------|---------------|
| `src/wanctl/cake_signal.py` | EWMA-smooth per-tin CAKE stats; produce `CakeSignalSnapshot` | Replace 4 hard-coded `range(1, len(tins_raw))` with helper that respects single-tin layout |
| `src/wanctl/cake_params.py` | Build qdisc parameter dict from YAML overrides + direction defaults | Conditionally allow `wash` in EXCLUDED_PARAMS check based on `cake_config["allow_wash"]` |
| `src/wanctl/backends/linux_cake.py:347-412` | Emit subprocess `tc qdisc replace ... cake ...` with boolean flags | Add `wash` to the boolean-flag emission loop at line 396 |
| `src/wanctl/backends/netlink_cake.py:413-498` | Emit pyroute2 `ipr.tc("replace", kind="cake", ...)` with kwargs | Add `("wash", "wash")` to the boolean-flag mapping at line 478-484 |
| `src/wanctl/check_config_validators.py:155-163` | Track known YAML keys (cake_params.*) for unknown-key detection | Add `"cake_params.allow_wash"` to the allowlist |
| `tests/test_cake_signal.py` | Unit + parsing + reload tests for CAKE signal | Add tests for 1-tin layout (besteffort oracle) and parameterize `make_mock_stats` |
| `tests/test_cake_params.py` | Builder, override, EXCLUDED_PARAMS tests | Add `allow_wash=true` permits-wash and `allow_wash=false` (or absent) still rejects-wash tests |

### Pattern 1: Tin-agnostic active-index helper

**What:** Single function determines which tin indices are "active" based on tin count.

**When to use:** Every site in `cake_signal.py` that currently writes `range(1, len(tins_raw))` — there are 4 such sites in `update()` (cold-start backlog/peak/avg/base/max-delay-delta + steady-state backlog/peak/avg/base/max-delay-delta) and 2 sites for total/active drop sum.

**Example:**
```python
# Source: proposed addition to src/wanctl/cake_signal.py (Phase 205 design)
def _active_tin_indices(tin_count: int) -> range:
    """Return the indices of tins that count as 'active load'.

    For multi-tin diffserv layouts (diffserv3/diffserv4/diffserv8), tin index 0
    is Bulk and is intentionally deprioritised — its drops/backlog are expected
    under load and excluded from the active signal.

    For single-tin besteffort layouts, the one tin IS the active tin; there is
    no Bulk to exclude.

    Args:
        tin_count: len(tins_raw) from get_queue_stats().

    Returns:
        Index range to use for "active" aggregation.
        - tin_count >= 2: range(1, tin_count) — exclude Bulk
        - tin_count == 1: range(0, 1) — the only tin is active
        - tin_count == 0: range(0, 0) — empty (caller already early-returns)
    """
    if tin_count >= 2:
        return range(1, tin_count)
    return range(tin_count)
```

Then every aggregation becomes:
```python
active_indices = _active_tin_indices(len(tins_raw))
active_backlog = sum(tins_raw[i].get("backlog_bytes", 0) for i in active_indices)
active_peak_delay = max((tins_raw[i].get("peak_delay_us", 0) for i in active_indices), default=0)
# ...etc
```

**Diffserv4 invariance proof:** `_active_tin_indices(4) == range(1, 4)`, byte-identical to current `range(1, len(tins_raw))` when len == 4. ATT replay tests must remain byte-identical.

### Pattern 2: Conditional excluded-params

**What:** Per-WAN gate that conditionally re-permits a single excluded param while keeping the others unconditionally rejected.

**Example:**
```python
# Source: proposed addition to src/wanctl/cake_params.py (Phase 205 design)
def build_cake_params(direction, cake_config=None, bandwidth_kbit=None):
    # ... existing code ...
    allow_wash = bool(cake_config.get("allow_wash", False)) if cake_config else False

    if cake_config:
        for key, value in cake_config.items():
            if key == "allow_wash":
                continue  # control flag, not a tc param
            tc_key = YAML_TO_TC_KEY.get(key, key)
            if tc_key in EXCLUDED_PARAMS:
                # D-08 transparent-bridge protection still applies UNLESS
                # this is the wash flag and the operator explicitly opted in.
                if tc_key == "wash" and allow_wash:
                    pass  # fall through to assignment
                else:
                    raise ConfigValidationError(
                        f"Excluded CAKE parameter: {key!r} -- not valid for "
                        f"transparent bridge topology"
                    )
            params[tc_key] = value
    return params
```

**Default:** `allow_wash` absent or false → behavior is byte-identical to v1.43 (wash rejected).
**ATT protection:** `att.yaml` does not set `allow_wash` → wash stays rejected even if a future operator typo'd `wash: true` in att.yaml.
**Spectrum (Phase 209):** `allow_wash: true` + `wash: true` both in spectrum.yaml — wash flows through to the args list.

### Anti-Patterns to Avoid

- **Per-WAN branching in Python.** `if wan_name == "spectrum": allow_wash = True` violates the portable-controller invariant in CLAUDE.md. Use the YAML flag.
- **Removing `wash` from `EXCLUDED_PARAMS`.** That changes the default behavior to "wash permitted unless excluded elsewhere," which is the inverse of D-08. Keep wash in EXCLUDED_PARAMS; gate via the `allow_wash` flag at the check site.
- **Touching the EWMA / threshold logic.** SAFE-09 forbids it. The aggregation set changes; the smoothing math doesn't.
- **Half-wiring the gate.** If `build_cake_params` permits `wash` but `initialize_cake` doesn't emit it, the gate looks correct in tests and is silently broken in production. Both backend init paths must learn the token in the same phase as the builder change.
- **Silent fixture deletion.** Don't shrink `make_mock_stats` to 1-tin permanently — that breaks every existing 4-tin test. Add a parameter or a sibling factory.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Variable-length tin iteration | A polymorphic `TinAggregationStrategy` class | The `_active_tin_indices()` helper | Two layouts (1-tin, 4-tin) don't justify class hierarchy; helper is 4 lines and testable |
| YAML config flag plumbing | A new `CakeParamsConfig` dataclass mirroring `CakeSignalConfig` | Existing `cake_config: dict[str, Any]` override path in `build_cake_params()` | The dict-override path is the established pattern; adding a dataclass forces refactoring all callers |
| Per-WAN deployment branching | Python `if wan_name == ...` chain | YAML key per-WAN | Portable-controller invariant in CLAUDE.md |
| Backend dispatch for new flag | Two near-identical patches in linux_cake.py and netlink_cake.py with shared logic | Just add `wash` to both flag-emission loops | Symmetric edits, both already have a flag-emission loop pattern; sharing creates a coupling between subprocess and netlink code paths |
| Boolean coercion / typo tolerance | `str.lower() == "true"` parsing | `bool(cake_config.get("allow_wash", False))` | YAML already coerces `true/false` → Python bool; trust the parser |

---

## Runtime State Inventory

This phase is a pure-code refactor with **no deploy** in Phase 205 itself (per ROADMAP: "pure-code refactor; no deploy"). Spectrum config flip is Phase 209. ATT and Spectrum production daemons keep running v1.43.0 throughout Phase 205. Therefore most categories are N/A for Phase 205, but I'm documenting them anyway because the planner needs to know what NOT to do:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no schema/keys/IDs change | None |
| Live service config | n8n / Datadog / Tailscale: N/A. wanctl daemons keep reading their existing YAML; no YAML edit in Phase 205 (ATT and Spectrum unchanged this phase) | None |
| OS-registered state | systemd units `wanctl@spectrum.service` / `wanctl@att.service` / `steering.service` keep their existing names; service file `deploy/systemd/wanctl@.service` not touched | None |
| Secrets/env vars | `${ROUTER_PASSWORD}`, `${DISCORD_WEBHOOK_URL}` — neither name nor consumer changes | None |
| Build artifacts | `wanctl` package egg-info regenerates on `pip install -e .` (already standard); no egg-info path or distribution name change | None — `make ci` reinstalls test deps as-needed |

**Phase 205 deploy footprint: zero.** No production daemon restart required by Phase 205 alone. The first runtime change reaches a daemon at Phase 209 deploy.

---

## Common Pitfalls

### Pitfall 1: Half-wired wash gate

**What goes wrong:** TOPO-02 changes `cake_params.py` to permit `wash` when `allow_wash=true`, but the boolean-flag emission loops in `linux_cake.py:396` and `netlink_cake.py:478` only check for `split-gso`, `ack-filter`, `ingress`. The `wash: True` key sits in the params dict and is silently dropped before reaching `tc`.

**Why it happens:** EXCLUDED_PARAMS protection used to make wash impossible to reach the emission loops, so the loops never needed to know about wash. Removing the early gate exposes the missing emission code.

**How to avoid:** Phase 205 plan MUST modify all four files (cake_params.py, cake_signal.py, linux_cake.py, netlink_cake.py) in scope. The integration test for "allow_wash=true → wash in args list" must assert the actual subprocess command line (or pyroute2 kwargs), not just inspect the params dict.

**Warning signs:** A unit test "params['wash'] == True after build_cake_params" passes but the daemon log at startup says "Initialized CAKE on spec-router (download): bandwidth ... besteffort ... split-gso ingress" with no "wash" token.

---

### Pitfall 2: Single-tin "active = empty"

**What goes wrong:** The current code uses `range(1, len(tins_raw))`. With a 1-tin besteffort qdisc, `len(tins_raw) == 1` and `range(1, 1)` is empty. `active_drops` becomes 0, `active_backlog` becomes 0, `active_peak_delay` becomes 0 (max of empty with default=0), and the controller never sees any congestion signal from the queue.

**Why it happens:** "Active = exclude Bulk = exclude index 0" is correct for diffserv*; for besteffort the only tin IS the active load.

**How to avoid:** Use `_active_tin_indices()` helper that returns `range(0, 1)` when there's only one tin. Add a new test case `test_single_tin_besteffort_drops_in_active_rate` mirroring `test_besteffort_drops_in_both_rates` but with a 1-element tin list.

**Warning signs:** A besteffort daemon shows "drops=12345 in raw stats but cake_signal.drop_rate=0.0" in `/health` output.

---

### Pitfall 3: Diffserv4 byte-identity regression

**What goes wrong:** A refactor that "works for both layouts" subtly changes the order of operations or floating-point accumulation order in the diffserv4 path, breaking the SAFE-09 promise that `git diff 6508d68 -- src/wanctl/cake_signal.py` is bounded to "tin-agnostic refactor" and **no semantic change for the existing diffserv4 traffic**.

**Why it happens:** Helper extraction temptation: factoring out the inner per-tin loop changes iteration order or sum() accumulation order; replay test produces a 1-bit difference in the EWMA chain.

**How to avoid:** Keep aggregation expressions byte-identical; only the **iteration range** changes. Confirm with `tests/test_phase_193_replay.py` and any other replay test that goes through `CakeSignalProcessor` — they should pass without modification. Run them as a hard gate in the plan's verify step.

**Warning signs:** `tests/test_phase_193_replay.py` or any `tests/test_phase_19*_replay.py` failure with "expected zone YELLOW, got GREEN" — the EWMA produced a slightly different value due to changed accumulation order, classifier flipped on a boundary.

---

### Pitfall 4: Validator unknown-key WARN spam

**What goes wrong:** `cake_params.allow_wash` is added to spectrum.yaml (in Phase 209, but operators may experiment in 205), `KNOWN_AUTORATE_PATHS` in `check_config_validators.py:155-163` is not updated, daemon startup emits `WARN Unknown config key: cake_params.allow_wash` every restart.

**Why it happens:** The allowlist was hand-written (Phase 107) and isn't auto-derived from the dataclass / YAML schema. Adding a YAML key without updating the allowlist is a known recurring miss (per Phase 200-03 STATE entry).

**How to avoid:** Add `"cake_params.allow_wash",` to the allowlist in the same edit that adds the gate. Add a unit test in `test_check_config_validators.py` (or wherever `check_unknown_keys` is exercised) confirming `cake_params.allow_wash` does not produce a warning.

**Warning signs:** Daemon startup log includes `WARN ... Unknown config key: cake_params.allow_wash`. `wanctl-check-config /etc/wanctl/spectrum.yaml` lists it as a fuzzy-match suggestion.

---

### Pitfall 5: `_DIFFSERV_NAME_TO_INT` besteffort=2 bug (out-of-scope but blocks Phase 209)

**What goes wrong:** `src/wanctl/backends/netlink_cake.py:62-66` defines `_DIFFSERV_NAME_TO_INT = {"diffserv3": 0, "diffserv4": 1, "besteffort": 2}`. The actual kernel constant is `CAKE_DIFFSERV_BESTEFFORT = 3` (verified via `pyroute2.netlink.rtnl.tcmsg.sched_cake.CAKE_DIFFSERV_BESTEFFORT`). This dict is consumed by `validate_cake` readback comparison (line 70 maps "diffserv" → "TCA_CAKE_DIFFSERV_MODE"). For diffserv4, `1 == 1` matches and validation passes. For besteffort, the kernel reports `3` and our expected dict says `2` — readback validation will FAIL the moment Spectrum flips to besteffort.

**Why it happens:** The dict was written by hand without verifying against the kernel header. diffserv8 is also wrong (we don't have it, but `_DIFFSERV_NAME_TO_INT` doesn't contain it either — unrelated). The bug never fired because nobody's ever deployed besteffort.

**How to avoid:** Out of scope for Phase 205 strictly. **Phase 209's config flip will trigger this**. Recommend:
- Phase 205: document this in this RESEARCH.md (done) and in the phase RETRO so Phase 206 / 209 don't re-discover.
- Phase 209: include the one-line fix `"besteffort": 3` in the same commit that flips spectrum.yaml, OR wait for the readback warning, OR fix it as TOPO-02 sub-scope (since both touch this file ecosystem). **If included in 205, SAFE-09 closeout still passes** because netlink_cake.py is not under SAFE-09 protection (it's not in the cake_signal/cake_params/operator_summary/__init__.py allowed-diff set per ROADMAP §"SAFE-09 invariant"). Wait — actually, it IS in `src/wanctl/`, so SAFE-09 IS in question. **Recommend: defer this fix to Phase 209 and document loudly here.** Phase 209 already plans to touch backend integration anyway via the migration.

**Warning signs:** Phase 209 canary log: `CAKE param mismatch on spec-router: diffserv expected=2 actual=3 -- continuing anyway`.

---

### Pitfall 6: ATT-side OPTIMAL_WASH auditor (out-of-scope but cross-cutting)

**What goes wrong:** `src/wanctl/check_cake.py:65-68` defines `OPTIMAL_WASH = {"upload": "yes", "download": "no"}` for the RouterOS `/queue type` cake-wash audit (not the Linux CAKE qdisc — separate audit tool for the MikroTik side). Once Spectrum DL flips to wash=yes (Phase 209), this auditor will report "wash=yes (suboptimal, expected no)" for the Spectrum download queue.

**Why it happens:** This auditor predates the topology insight that DSCP isn't preserved across ISP. It's a separate tool from the live control loop.

**How to avoid:** Out of scope for Phase 205. Phase 209 needs to either (a) make `OPTIMAL_WASH` per-WAN-aware, or (b) deprecate this RouterOS-side cake-wash audit since the Linux CAKE qdisc is the authoritative shaper now. Document loudly here so the planner doesn't add it to 205.

**Warning signs:** None during Phase 205 (auditor not exercised by the daemon hot path).

---

## Code Examples

Verified patterns from the existing in-tree code:

### Existing aggregation site (cake_signal.py:254-280, cold-start branch — same shape repeated 4 sites total)

```python
# Source: src/wanctl/cake_signal.py:254-280 (current code, v1.43 close)
# Compute backlog and peak delay excluding Bulk (index 0)
active_backlog = sum(
    tins_raw[i].get("backlog_bytes", 0) for i in range(1, len(tins_raw))
)
active_peak_delay = max(
    (tins_raw[i].get("peak_delay_us", 0) for i in range(1, len(tins_raw))),
    default=0,
)
active_avg_delay = max(
    (tins_raw[i].get("avg_delay_us", 0) for i in range(1, len(tins_raw))),
    default=0,
)
active_base_delay = max(
    (tins_raw[i].get("base_delay_us", 0) for i in range(1, len(tins_raw))),
    default=0,
)
active_max_delay_delta = max(
    (
        max(0, tins_raw[i].get("avg_delay_us", 0) - tins_raw[i].get("base_delay_us", 0))
        for i in range(1, len(tins_raw))
    ),
    default=0,
)
```

The replacement just substitutes `range(1, len(tins_raw))` → `_active_tin_indices(len(tins_raw))`. Identical for `len == 4`; correct for `len == 1`.

### Existing builder override loop (cake_params.py:150-157)

```python
# Source: src/wanctl/cake_params.py:150-157 (current code, v1.43 close)
if cake_config:
    for key, value in cake_config.items():
        tc_key = YAML_TO_TC_KEY.get(key, key)
        if tc_key in EXCLUDED_PARAMS:
            raise ConfigValidationError(
                f"Excluded CAKE parameter: {key!r} -- not valid for transparent bridge topology"
            )
        params[tc_key] = value
```

Insertion point for the gate is inside this loop (see "Pattern 2" above).

### Existing backend boolean-flag emission (linux_cake.py:396-400)

```python
# Source: src/wanctl/backends/linux_cake.py:396-400 (current code, v1.43 close)
for flag in ("split-gso", "ack-filter", "ingress"):
    if params.get(flag):
        cmd_args.append(flag)
    elif flag == "ack-filter" and flag in params:
        cmd_args.append("no-ack-filter")
```

Phase 205 must add `"wash"` to the tuple (and decide whether `no-wash` is emitted on explicit False — recommend yes for symmetry with `no-ack-filter`).

### Existing netlink boolean-flag mapping (netlink_cake.py:478-484)

```python
# Source: src/wanctl/backends/netlink_cake.py:478-484 (current code, v1.43 close)
for tc_flag, pyroute2_kwarg in [
    ("split-gso", "split_gso"),
    ("ack-filter", "ack_filter"),
    ("ingress", "ingress"),
]:
    if tc_flag in params:
        kwargs[pyroute2_kwarg] = bool(params[tc_flag])
```

Phase 205 must add `("wash", "wash")` to this list. pyroute2 accepts `wash=True/False` directly [VERIFIED: `pyroute2.netlink.rtnl.tcmsg.sched_cake` docstring inspection 2026-05-13].

### Existing test fixture pattern (test_cake_signal.py:29-68)

```python
# Source: tests/test_cake_signal.py:29-68 (current code, v1.43 close)
def make_mock_stats(
    tin_drops: list[int] | None = None,
    tin_backlog: list[int] | None = None,
    tin_peak_delay: list[int] | None = None,
    tin_avg_delay: list[int] | None = None,
    tin_base_delay: list[int] | None = None,
) -> dict[str, Any]:
    """Build a mock get_queue_stats() return value."""
    tin_drops = tin_drops or [0, 0, 0, 0]
    # ...
    return {
        # ...
        "tins": [
            { "dropped_packets": tin_drops[i], ... } for i in range(4)
        ],
    }
```

**Phase 205 fixture extension:** Either parameterize on `tin_count` (default 4 for backward compat) or add a sibling `make_mock_stats_besteffort()` that returns a 1-element tins list. Recommend parameterize-on-default to avoid two fixtures drifting.

---

## State of the Art

This is wanctl-internal architecture; "state of the art" is the current in-tree shape. No external library/framework changes apply.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard-coded "active = tins[1:]" with Bulk-as-index-0 assumption | Tin-agnostic active-index helper | This phase (205) | Permits besteffort qdisc; preserves diffserv4 |
| Unconditional D-08 wash exclusion | Per-WAN `allow_wash` flag, default false | This phase (205) | Permits Spectrum besteffort wash (Phase 209); ATT and any future bridge deployment still protected |

**Deprecated/outdated:** None in scope for Phase 205. (The `_DIFFSERV_NAME_TO_INT` besteffort=2 bug in netlink_cake.py is dormant and only fires when besteffort is actually deployed in Phase 209.)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Phase 205 is pure-code, no deploy" | Runtime State Inventory | Low — explicitly stated in ROADMAP §"Phase 205" line 31; consistent with SAFE-09 phase-boundary check requiring zero src/wanctl diff outside the two files |
| A2 | "Replay test fixture for Spectrum besteffort can be hand-rolled / synthesized rather than captured from a real qdisc" | Open Questions | Medium — capturing from a real besteffort qdisc requires deploying besteffort somewhere, which is a chicken-and-egg with Phase 209. Synthesizing a 1-tin `tins_raw` dict with realistic byte/packet/delay values matches the existing `make_mock_stats` synthesis pattern and is likely sufficient for Phase 205's "signal values consistent with the diffserv4 oracle for the same load profile" success criterion. **Operator confirmation recommended** — see Open Questions Q1. |
| A3 | "`allow_wash` default-false in cake_config dict is the cleanest API shape" | Architecture Patterns 2 | Low — matches the existing pattern (`ack_filter`, `ingress`, etc. live as dict keys), no new dataclass surface, byte-identical to v1.43 when absent |
| A4 | "EXCLUDED_PARAMS stays a frozenset/set with `wash` still in it; gate is at the check site, not the membership site" | Anti-Patterns | Low — keeps the D-08 default semantics intact; safer than removing wash and re-adding via different mechanism |

---

## Open Questions

1. **Replay-oracle fixture: synthesize or capture?**
   - What we know: existing `make_mock_stats` synthesizes a 4-tin dict; replay tests `tests/test_phase_193_replay.py` and siblings build hard-coded TRACE arrays at the SnapshotConsumer layer (not at the kernel-stats layer); no captured-from-router CAKE-state JSON fixture exists in `tests/fixtures/`.
   - What's unclear: TOPO-01 success criterion #2 says "captured single-tin besteffort CAKE state fixture." Strictly read, "captured" implies a real router. There is no Spectrum or ATT instance currently running besteffort to capture from.
   - Recommendation: Treat "captured" loosely. **Synthesize** a 1-tin `tins_raw` dict matching the same shape that `NetlinkCakeBackend.get_queue_stats()` would return for a 1-tin qdisc (verified via `_parse_cake_msg` reads `TCA_CAKE_TIN_STATS_1` and breaks at None — for a besteffort qdisc, only `_1` is present). The fixture is a pure dict, committed to `tests/fixtures/` or inline in the test file. Operator should confirm at /gsd-discuss-phase whether synthesized is acceptable or if they want a real capture from a besteffort dev qdisc spun up specifically for Phase 205.

2. **`no-wash` emission on explicit `wash: false`?**
   - What we know: The current linux_cake.py emission loop emits `no-ack-filter` when `params["ack-filter"] == False AND "ack-filter" in params`. This pattern exists because tc CAKE has explicit no-X tokens for some flags.
   - What's unclear: Should `wash: false` (in YAML) emit `no-wash` to tc, or just omit `wash` and rely on the qdisc default (which IS no-wash)? `tc-cake(8)` does support `nowash` as an explicit token.
   - Recommendation: Mirror the `ack-filter` pattern — emit `nowash` when `wash` is in params and false, so operator-explicit-false produces an operator-visible-no-wash in the qdisc args. Symmetry beats minimality here.

3. **Should Phase 205 also fix the `_DIFFSERV_NAME_TO_INT` besteffort=2 bug?**
   - What we know: The bug exists, will fire on Phase 209's flip, and the one-character fix is `"besteffort": 3`.
   - What's unclear: SAFE-09 strictly bounds the diff to `cake_signal.py` and `cake_params.py` for v1.44. Touching `netlink_cake.py` violates that bound.
   - Recommendation: **Defer to Phase 209.** Document the bug in the Phase 205 RETRO so Phase 209's plan picks it up explicitly. The risk is small — the worst case is a `WARN CAKE param mismatch` log line during canary, not a control-loop break.

4. **Tin-name list for besteffort?**
   - What we know: `CakeSignalProcessor.__init__` accepts `tin_names: list[str] | None = None` and defaults to `["Bulk", "BestEffort", "Video", "Voice"]`. The fallback at line 237/326 is `f"Tin{i}"` when index is out of range. So besteffort already gets `Tin0` instead of `BestEffort`.
   - What's unclear: Does anything downstream care that the single tin's `name` field is "BestEffort" vs "Bulk" vs "Tin0"? Per `tests/test_history_cli.py:635` and `wanctl_cake_tin_backlog_bytes` Prometheus metric, tin name flows into the metric label.
   - Recommendation: Have the processor set `tin_names = ["BestEffort"]` for the single-tin case, OR pass it from the caller (WANController) based on YAML `cake_params.diffserv`. Either works. The simpler option — internal heuristic in `CakeSignalProcessor` — is a one-liner: if there's exactly 1 tin, use `["BestEffort"]`; else use the existing diffserv4 default. This is technically a behavioral change, but it only affects the besteffort path which is dead code on ATT and pre-Phase-209 Spectrum.

---

## Environment Availability

This phase has no external runtime dependencies beyond what wanctl already requires. Documenting for completeness:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | wanctl daemon | ✓ | 3.12 in `.venv` (verified) | — |
| pytest | test execution | ✓ | per project pyproject | — |
| pyroute2 | netlink_cake.py wash kwarg | ✓ | installed in `.venv`, supports `wash` kwarg | subprocess `tc` path also supports `wash` |
| `tc` (iproute2) | linux_cake.py subprocess fallback | not relevant on dev workstation; required on `cake-shaper` deploy host | n/a in dev | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (verified in pyproject.toml) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` if present) + `tests/conftest.py` |
| Quick run command | `.venv/bin/pytest tests/test_cake_signal.py tests/test_cake_params.py -v` |
| Hot-path slice (per CLAUDE.md) | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` (current full suite ~4976 passed per Phase 204 STATE entry) |
| SAFE-09 phase-boundary verifier | `git diff 6508d68 -- src/wanctl/ | grep -v '^+++\|^---' | grep '^[+-]' \| (only cake_signal.py + cake_params.py paths allowed)` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOPO-01 | Diffserv4 (4-tin) byte-identical aggregation preserved | unit | `.venv/bin/pytest tests/test_cake_signal.py -v` | ✅ existing tests (TestCakeSignalProcessorTinSeparation, TestCakeSignalProcessorEWMA) — no new file |
| TOPO-01 | Diffserv4 replay byte-identical | replay | `.venv/bin/pytest tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py -v` | ✅ existing |
| TOPO-01 | Single-tin besteffort 1-tin layout produces non-zero active signal | unit (NEW) | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalProcessorBestEffort -v` | ❌ Wave 0 — add to test_cake_signal.py |
| TOPO-01 | Besteffort and diffserv4 produce consistent signals for the same logical load (drops & backlog matched between layouts) | replay-oracle (NEW) | `.venv/bin/pytest tests/test_cake_signal.py::TestCakeSignalProcessorBestEffortOracle -v` | ❌ Wave 0 |
| TOPO-02 | `allow_wash=false` (or absent) still rejects `wash: true` | unit | `.venv/bin/pytest tests/test_cake_params.py::TestBuildCakeParamsExcluded::test_wash_excluded -v` | ✅ existing (must continue passing) |
| TOPO-02 | `allow_wash=true` permits `wash: true`; params dict includes wash | unit (NEW) | `.venv/bin/pytest tests/test_cake_params.py::TestBuildCakeParamsAllowWash -v` | ❌ Wave 0 |
| TOPO-02 | `allow_wash=true` permits `wash: true` AND args list emitted via tc subprocess includes "wash" | integration (NEW) | `.venv/bin/pytest tests/backends/test_linux_cake.py::test_initialize_cake_emits_wash -v` | ❌ Wave 0 — add to existing tests/backends/test_linux_cake.py |
| TOPO-02 | `allow_wash=true` AND netlink path: pyroute2 kwargs include `wash=True` | integration (NEW) | `.venv/bin/pytest tests/backends/test_netlink_cake.py::test_initialize_cake_passes_wash_kwarg -v` | ❌ Wave 0 — add to existing tests/backends/test_netlink_cake.py |
| TOPO-02 | `allow_wash` does not produce unknown-key warning | unit | `.venv/bin/pytest tests/test_check_config_validators.py -k allow_wash -v` (or wherever check_unknown_keys is tested) | ❌ Wave 0 — add to allowlist tests |
| TOPO-02 | EXCLUDED_PARAMS still unconditionally rejects `nat` and `autorate-ingress` even when `allow_wash=true` | unit (NEW) | `.venv/bin/pytest tests/test_cake_params.py::TestBuildCakeParamsAllowWash::test_allow_wash_does_not_permit_nat -v` | ❌ Wave 0 |
| SAFE-09 phase boundary | Control-path source diff bounded to cake_signal.py + cake_params.py | manual / scripted | `git diff 6508d68 --name-only -- src/wanctl/ | sort -u` should print exactly two paths (or three including `__init__.py` if version is also bumped this phase, but version bump is Phase 209) | manual gate at phase close |

### Sampling Rate
- **Per task commit:** Quick run command (cake_signal + cake_params unit tests, ~50 tests, < 5 seconds)
- **Per wave merge:** Hot-path slice including replay tests (~700 tests including Phase 193/194/195 replays, < 30 seconds)
- **Phase gate (before `/gsd-verify-work`):** Full suite green; SAFE-09 source-diff verifier green

### Wave 0 Gaps
- [ ] `tests/test_cake_signal.py::TestCakeSignalProcessorBestEffort` — single-tin layout produces non-zero active signal (TOPO-01)
- [ ] `tests/test_cake_signal.py::TestCakeSignalProcessorBestEffortOracle` — besteffort/diffserv4 oracle equivalence on matched load profile (TOPO-01)
- [ ] Either parameterize `make_mock_stats(tin_count=4)` or add `make_mock_stats_besteffort()` sibling factory (test infrastructure for above two)
- [ ] `tests/test_cake_params.py::TestBuildCakeParamsAllowWash` — class with `test_allow_wash_true_permits_wash`, `test_allow_wash_false_rejects_wash`, `test_allow_wash_absent_rejects_wash`, `test_allow_wash_does_not_permit_nat`, `test_allow_wash_does_not_permit_autorate_ingress` (TOPO-02 acceptance)
- [ ] `tests/backends/test_linux_cake.py::test_initialize_cake_emits_wash` — when `wash=True` in params, the constructed `cmd_args` list contains `"wash"` (TOPO-02 integration)
- [ ] `tests/backends/test_linux_cake.py::test_initialize_cake_emits_no_wash_on_explicit_false` — symmetry test mirroring `no-ack-filter` (Open Question Q2)
- [ ] `tests/backends/test_netlink_cake.py::test_initialize_cake_passes_wash_kwarg` — when `wash=True` in params, pyroute2 `tc("replace", ...)` is called with `wash=True` kwarg (TOPO-02 integration)
- [ ] `tests/test_check_config_validators.py` — assert `cake_params.allow_wash` is in `KNOWN_AUTORATE_PATHS` (or does not produce unknown-key WARN through `check_unknown_keys`)
- [ ] No framework install needed; no `conftest.py` change needed

---

## Security Domain

Per `.planning/config.json`, `security_enforcement` is not explicitly set → treated as enabled per template default. However, this phase modifies pure aggregation logic and a config flag — no new attack surface, no auth/session/access control change.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth change) |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (mild) | `bool(cake_config.get("allow_wash", False))` coerces; existing `ConfigValidationError` raised on excluded params; existing `_walk_leaf_paths` + `check_unknown_keys` provide YAML-key validation |
| V6 Cryptography | no | — (no crypto change) |

### Known Threat Patterns for {wanctl YAML config + tc subprocess + pyroute2 netlink}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator typo `allow_wash: yes` (string instead of bool) silently treated as truthy | Tampering / honest mistake | `bool(cake_config.get("allow_wash", False))` — `bool("yes") == True` (acceptable; YAML `yes` is canonically true anyway). For string `"false"`, `bool("false") == True` (BAD). Mitigation: cast via existing `cake_signal.py` pattern of `isinstance(v, bool)` guard. Recommend: `cake_config.get("allow_wash") is True` (strict bool) — symmetric with how `cake_signal.py` parses booleans (test_parse_invalid_types confirms non-bool → False). |
| YAML key injection via env-var expansion (`${...}`) | Tampering | Out of scope — `${}` expansion is for secrets values, not keys; not relevant here |
| tc subprocess argument injection | Injection | Already mitigated — `cmd_args.append("wash")` is a literal token, not user-controlled; pyroute2 path uses keyword args, not string concat |

---

## Sources

### Primary (HIGH confidence)
- `src/wanctl/cake_signal.py` (in-tree, full read 2026-05-13) — current aggregation shape, line 13/173/306 references, EWMA logic
- `src/wanctl/cake_params.py` (in-tree, full read 2026-05-13) — EXCLUDED_PARAMS, override loop, builder signature
- `src/wanctl/backends/linux_cake.py` (in-tree, lines 1-120 + 347-412 + 580-688) — initialize_cake subprocess emission
- `src/wanctl/backends/netlink_cake.py` (in-tree, lines 1-120 + 240-498) — initialize_cake netlink emission, pyroute2 kwargs, _DIFFSERV_NAME_TO_INT bug
- `src/wanctl/backends/linux_cake_adapter.py:280-360` — caller of `build_cake_params` and `build_expected_readback`
- `src/wanctl/check_config_validators.py:140-200, 700-732` — KNOWN_AUTORATE_PATHS allowlist + check_unknown_keys WARN behavior
- `src/wanctl/check_cake.py:55-68` — RouterOS-side OPTIMAL_WASH auditor (cross-cutting Phase 209 concern, out of 205 scope)
- `tests/test_cake_signal.py` (full read) — `make_mock_stats` fixture pattern, existing test classes
- `tests/test_cake_params.py` (full read) — existing EXCLUDED_PARAMS + builder tests
- `tests/test_phase_193_replay.py` (lines 1-80) — replay test pattern at SnapshotConsumer layer
- `configs/spectrum.yaml` + `configs/att.yaml` (full read) — current per-WAN cake_params shape
- `.planning/REQUIREMENTS.md` (v1.44) — TOPO-01/TOPO-02 wording, SAFE-08/SAFE-09 closeout invariants
- `.planning/ROADMAP.md` Phase 205 section — success criteria, SAFE-09 phase-boundary check
- `.planning/v1.44-THESIS-DRAFT.md` — SEED-001 file/line breadcrumbs, deployment model rationale
- `scripts/check-safe07-source-diff.sh` (full read) — existing source-diff guard pattern; HRDN-01 (Phase 207) generalizes it; Phase 205 uses ad-hoc `git diff 6508d68` per ROADMAP success criterion #4
- `pyroute2.netlink.rtnl.tcmsg.sched_cake` module introspection (2026-05-13) — `wash` kwarg confirmed; `CAKE_DIFFSERV_BESTEFFORT = 3` confirmed (vs in-tree dict's 2)
- `git rev-parse HEAD` = `b82abf0`; `git diff 6508d68 -- src/wanctl/` = empty (verified clean baseline)

### Secondary (MEDIUM confidence)
- `tc-cake(8)` `wash` / `nowash` token semantics — referenced from existing `check_cake.py` comments (line 62-64 documents direction-dependent wash rationale); not externally re-verified

### Tertiary (LOW confidence)
- None. All claims are direct in-tree reads or live tool introspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pyroute2 introspection confirmed `wash` kwarg; no new packages
- Architecture: HIGH — pattern is direct extension of existing helper-of-helpers shape; both edits map to single existing override loops
- Pitfalls: HIGH — five concrete pitfalls each verified against in-tree code; two cross-cutting (besteffort=2 bug, OPTIMAL_WASH auditor) explicitly scoped out
- Replay-oracle fixture: MEDIUM — synthesis approach recommended pending operator confirmation (Open Question Q1)

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (control-path code changes infrequently; replay test fixtures are stable; pyroute2 API is stable)
