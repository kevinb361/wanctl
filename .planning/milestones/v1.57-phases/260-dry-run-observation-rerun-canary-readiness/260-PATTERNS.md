# Phase 260: Dry-Run Observation Rerun + Canary Readiness - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 3 (1 new script, 1 new test, 1 evidence bundle)
**Analogs found:** 3 / 3 (all exact or strong role-match)

> Read-only phase (SAFE-21). The harness samples existing health/inspector
> output and takes one validated read-only RouterOS cross-check. It MUST NOT
> mutate routes, Netwatch, scripts, CAKE/qdisc, or flip the route owner.
> The only file the executor writes outside `scripts/`, `tests/`, and the phase
> `evidence/` dir is none — all RouterOS interaction is read GET / print.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/phase260-observation.py` | utility (deployed proof harness) | batch / request-response (multi-sample poll + 1 cross-check + packet render) | `scripts/phase259-ownership-proof.py` | exact role, generalized data flow (259 is single-sample) |
| `tests/test_phase260_observation.py` | test | request-response (fake client + fake manager) | `tests/test_phase259_ownership_proof.py` | exact |
| `evidence/phase260-*` bundle (packet `.md` + raw `.json` + transcript `.md` + command file `.txt`) | config / evidence artifact | file-I/O | Phase 257 evidence bundle | exact format template (D-09) |

---

## Pattern Assignments

### `scripts/phase260-observation.py` (utility, batch poll + cross-check + render)

**Analog:** `scripts/phase259-ownership-proof.py` (read it whole; it is 146 lines).

Phase 260 is "259 generalized": same `/opt` bootstrap + validate-before-run_cmd +
single greppable verdict token, but it (a) samples `:9102/health` across a
bounded ~10-min window instead of refreshing one inspector locally, (b) adds one
independent direct RouterOS read-only cross-check (D-04), (c) renders a per-route
standing-intent-vs-live table (D-05), and (d) emits the 257-shaped readiness
packet (D-09) instead of a one-line proof.

**1. `/opt` import bootstrap + deployed-import assertion** — copy verbatim from analog (lines 11-23, 81-94):

```python
DEPLOYED_ROOT = Path("/opt/wanctl").resolve()
if DEPLOYED_ROOT.exists():
    sys.path.insert(0, str(DEPLOYED_ROOT.parent))

import wanctl  # noqa: E402
from wanctl.readonly_validator import iter_commands, validate_command  # noqa: E402
from wanctl.router_client import get_router_client  # noqa: E402
from wanctl.steering.daemon import SteeringConfig  # noqa: E402
from wanctl.steering.route_manager import RouteManager  # noqa: E402
from wanctl.steering.route_ownership_inspector import ROUTE_PRINT, RouteOwnershipInspector  # noqa: E402
```

`_assert_deployed_imports()` (analog lines 81-94) prints `wanctl.__file__=...` and
fails the run with a greppable token if imports did not resolve under
`/opt/wanctl`. Keep this — it proves the harness exercises deployed code, not the
repo checkout.

**2. Validate-before-run_cmd gate (D-08)** — copy the analog's call sequence exactly (lines 45-52, 113-115, 134-141):

```python
def validate_commands_before_run(client, commands) -> None:
    """Validate commands before any client.run_cmd can be reached."""
    _ = client
    for command in commands:
        validate_command(command)   # raises ValueError on any mutating/forbidden command

# in main(), BEFORE constructing the live client:
commands = iter_commands(args.command_file)
validate_commands_before_run(_NoRunClient(), commands)
```

`_NoRunClient.run_cmd` raises `AssertionError("validate_commands_before_run must
not execute commands")` (analog lines 134-138) — this is the structural proof
that validation precedes any live I/O. Preserve it; the test slice asserts on it.

Also run the validator's negative self-test before live commands so the transcript
carries `READONLY_COMMANDS_VALIDATED` + `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED`
(see `readonly_validator.validate_path` / `self_test`, lines 104-126). The 257
packet's SAFE proof block explicitly cites these two tokens.

**3. Live client construction (read-only REST path)** — copy analog lines 117-129:

```python
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("phase260-observation")
config = SteeringConfig(str(args.config))      # default Path("/etc/wanctl/steering.yaml")
client = get_router_client(config, logger)     # transport="rest" -> RouterOSREST (258-proven)
try:
    ...
finally:
    close = getattr(client, "close", None)
    if callable(close):
        close()
```

`get_router_client` (`router_client.py:63-92`) dispatches on `config.router_transport`;
for this phase it returns `RouterOSREST` (port 443, `ROUTER_PASSWORD`). The
`try/finally close()` is mandatory — do not leak the session.

**4. Verdict token convention (generalize 259 -> 257 shape).** Analog emits one
line (`run_proof`, lines 54-78):

```python
return 0, "INSPECT_PROOF_PASS observed_owner=... match=... total_routes=... default_routes=..."
# or on inspector error:
return 1, f"INSPECT_PROOF_FAIL inspector_error={snap['inspector_error']}"
```

Phase 260 keeps the single-token discipline but uses the 257 packet header tokens
(from `phase257-readiness-packet`, lines 3-7 and the SAFE block 65-78):

```text
OBSERVE_VERDICT: ready-for-approval        # or: not-ready
APPROVED_ACTIVE_CANARY: false
NETWATCH_REMAINS_OWNER: true
NO_ROUTE_OWNER_FLIP: true
NO_ROUTEROS_ROUTE_MUTATION: true
NO_NETWATCH_MUTATION: true
NO_CAKE_QDISC_CHANGE: true
```

`ready-for-approval` requires (D-01/D-02): every sampled `ownership_inspection`
has `inspector_status == "ok"` AND `match == true`, the per-route table matches,
and the cross-check agrees. Any single bad sample -> `not-ready` (fail-closed,
mirroring analog's `INSPECT_PROOF_FAIL` on inspector error).

**5. Sampled health payload keys (what the harness reads each tick).** The
inspector section is built by `health.py:_build_ownership_inspection_section`
(lines 393-418) and produced by `route_ownership_inspector._compute` (lines 84-178).
Authoritative D-01 keys to gate on:

```python
ownership_inspection = {
    "observed_owner": str,            # expect "netwatch"
    "configured_owner": str,          # expect "netwatch"
    "match": bool,                    # D-01 authoritative; expect True every sample
    "inspector_status": str,          # D-01 authoritative; expect "ok" every sample
    "inspector_error": str | None,
    "last_inspected_at": str | None,  # ISO; D-spec: must ADVANCE across refreshes (staleness check)
    "netwatch": {"entries_count": int, "route_mutating_active_count": int},
    "routes": {
        "total_route_count": int,                 # baseline expect 17
        "default_routes": [                        # baseline expect 4 entries
            {"gateway": str|None, "disabled": bool, "distance": int|None, "comment": str|None},
        ],
    },
}
```

The `route_management` section (`health.py:354-391`) is the SUPPLEMENTARY signal
(D-01): the harness checks only that `guard.status` is not circuit-open / hard-fail,
NOT that it is `ok`. Relevant keys: `enabled`, `mode`, `active_owner`,
`active_allowed`, `guard.status`, `reconciliation.{status,route_count}`,
`circuit_breaker.open`, `last_intended_action`, `last_applied_action`,
`rollback_ready`.

**6. Standing per-route intent (D-05) — wanctl side of the comparison.**
`RouteManager.status_snapshot()` (`route_manager.py:280-315`) gives `active_owner`
(via `_active_owner`, lines 398-403: `"netwatch"` unless `mode=="active"` and
allowed) and `reconciliation.route_count`. The actual route targets/distances come
from `reconcile_startup()` (lines 136-181), which resolves each configured
`self.routes` key into a `RouteState(key, route_id, disabled, anchor_type,
anchor_value)`. Build the harness's standing-intent table from
`active_owner` + the reconciliation `routes` map, and compare it against live
`ownership_inspection.routes.default_routes[]` (gateway / disabled / distance /
comment). Do NOT drive a failover to force a non-null `last_intended_action`
(D-05 rejects that as bordering SAFE-21).

> Construct `RouteManager` the same way the analog does
> (`_route_manager_from_config`, analog lines 97-104): `enabled`, `mode`, `routes`
> from config, `router_client=client`, `ownership_guard_result=None`.

**7. Independent RouterOS cross-check (D-04) — 258-proven path.** Issue the
allowlisted read-only prints directly through the same client and compare against
the daemon's `ownership_inspection`:

```python
STATIC_READ_COMMANDS = (
    "/tool netwatch print detail",
    "/system script print detail",
    ROUTE_PRINT,                       # "/ip route print"
)
```

These dispatch to `routeros_rest._handle_netwatch_print` (lines 651-683) and
`_handle_route_print` (lines 617-649) — both pure GET against
`{base_url}/tool/netwatch` and `{base_url}/ip/route`, read-only. A disagreement
between this direct read and the cached `ownership_inspection` is a recorded
divergence (D-07 class 3), not a remediation trigger.

**8. Mutation-token scan.** 257 packet records `MUTATION_TOKEN_HITS: []`
(packet line 30). Scan the issued-command transcript for the same forbidden
classes the validator rejects (`readonly_validator.FORBIDDEN_ROUTEROS_ACTIONS`,
lines 28-45: ` set `/` add `/` remove `/` enable `/` disable `/` run `/` import `/
` reset ` and slash forms) and emit `MUTATION_TOKEN_HITS: []` into the packet.

**`main()` skeleton** (mirror analog lines 107-131, extend for window + packet):

```python
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_file", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    # Claude's discretion: --window-sec (~636 default), --interval-sec, --evidence-dir
    args = parser.parse_args(argv)

    _assert_deployed_imports()
    commands = iter_commands(args.command_file)
    validate_commands_before_run(_NoRunClient(), commands)   # gate BEFORE live client
    ...
    client = get_router_client(config, logger)
    try:
        # loop: sample :9102/health every interval across window; gate D-01/D-02 each tick
        # once: direct cross-check via STATIC_READ_COMMANDS; assert agreement (D-04)
        # render: standing-intent table (D-05), divergence union (D-07), 257-shaped packet (D-09)
        rc, verdict = run_observation(client, route_manager, ...)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(verdict)   # single greppable OBSERVE_VERDICT line
    return rc
```

---

### `tests/test_phase259_ownership_proof.py` -> `tests/test_phase260_observation.py` (test)

**Analog:** `tests/test_phase259_ownership_proof.py` (read whole; 108 lines).

**1. Load the script-with-a-dash by spec** (analog lines 10-15) — scripts use
hyphens, so import via `importlib.util`, not a normal import:

```python
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase260-observation.py"
spec = importlib.util.spec_from_file_location("phase260_observation", SCRIPT)
assert spec is not None
obs = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(obs)
```

**2. `FakeClient` returning RouterOS-shaped JSON per command** (analog lines 18-67)
— branch on `"netwatch"` / `"script"` / `"route"` in `cmd`, return
`(0, json.dumps([...]), "")`; support a `fail=` arg that returns `(1, "", "boom")`
to simulate inspector error. Reuse the analog's fixtures verbatim, plus add
default-route rows so the D-05 table has something to compare. `FakeRouteManager`
(analog lines 70-72) returns `{"active_owner": "netwatch", "mode": "dry_run"}` —
extend with reconciliation `routes` if the harness reads them directly.

**3. Mandatory test cases** (mirror analog, adapt to multi-sample/packet):

| Test (analog name) | What it pins | 260 adaptation |
|---|---|---|
| `test_run_proof_rejects_mutating_command_before_run_cmd` (lines 91-97) | `validate_commands_before_run(client, ["/ip route disable 0"])` raises `ValueError(match="mutating action")` AND `client.commands == []` | **keep as-is** — this is the D-08/SAFE-21 keeper. No live command may issue before validation. |
| `test_run_proof_fail_on_inspector_error` (lines 100-107) | `FakeClient(fail="netwatch")` -> `rc != 0`, verdict contains FAIL token + `inspector_error=` | adapt: a single `inspector_status=error` / `match=false` sample -> `OBSERVE_VERDICT: not-ready` (fail-closed, D-02). |
| `test_run_proof_happy_path` (lines 75-88) | clean inputs -> PASS token with expected counts | adapt: all-clean window + agreeing cross-check + matching table -> `OBSERVE_VERDICT: ready-for-approval`. |
| (new, D-02) | one bad mid-window sample forces not-ready even if it recovers | drive the fake to return one `match=false` sample among otherwise-clean ones; assert `not-ready` and the bad sample is the recorded blocker. |
| (new, D-04) | cross-check disagreement -> not-ready / recorded divergence | make the direct read disagree with `ownership_inspection`; assert divergence recorded. |

---

### `evidence/phase260-*` bundle (config/evidence, file-I/O)

**Analog:** Phase 257 evidence bundle
(`.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/evidence/`).

Mirror its four-artifact layout into
`.planning/phases/260-dry-run-observation-rerun-canary-readiness/evidence/`
(timestamped `YYYYMMDDTHHMMSSZ`, operator's discretion on exact names):

| 257 artifact | 260 equivalent | Source pattern |
|---|---|---|
| `phase257-readonly-commands-*.txt` | `phase260-readonly-commands-*.txt` | `COMMAND:`-prefixed lines, validated by `readonly_validator.iter_commands`. **Replace** the 257 SSH-key lines (7-10) — which returned 255 — with the now-working REST read-only prints (`/tool netwatch print detail`, `/system script print detail`, `/ip route print detail`). Keep the health/systemctl/journalctl `ssh cake-shaper '...'` lines (1-6). |
| `phase257-readonly-validator-*.py` | (reuse deployed `wanctl.readonly_validator`) | The deployed validator is now the enforcement layer (D-08); copy it as a frozen evidence snapshot if 257's convention is kept. |
| `phase257-observation-raw-*.json` | `phase260-observation-raw-*.json` | machine-readable per-sample dump (every `ownership_inspection` snapshot + cross-check). |
| `phase257-observation-transcript-*.md` | `phase260-observation-transcript-*.md` | human transcript of issued commands + validator tokens. |
| `phase257-readiness-packet-*.md` | `phase260-readiness-packet-*.md` | **the deliverable** — copy the 257 packet structure exactly (D-09). |

**Readiness packet structure (D-09 template)** — copy 257's section order verbatim
(`phase257-readiness-packet`, full file):

1. Header: `Verdict: ready-for-approval|not-ready` + `OBSERVE_VERDICT` token +
   `APPROVED_ACTIVE_CANARY: false` / `NETWATCH_REMAINS_OWNER: true` /
   `NO_ROUTE_OWNER_FLIP: true` (packet lines 1-7).
2. `## Evidence Inputs` — point at the four 260 artifacts + Phase 256 rollback
   anchors + plan summary (lines 9-16).
3. `## Readiness Criteria Matrix` — criterion / observed / status / readiness
   impact (lines 18-30). **Update the two rows 258/259 fixed:**
   - old "guard status ok/supported = fail (guard.status=error)" -> now gated on
     **`ownership_inspection.inspector_status=ok` + `match=true`** (D-01), pass.
   - old "live route/Netwatch inventory ... returned 255 ... router.key not
     accessible = fail" -> now **REST read-only inventory succeeded** (258
     ACCESS02_PROOF_PASS route=17 netwatch=3 script=20), pass.
4. `## Intended vs Live Summary` — render the D-05 standing-intent table here
   (lines 32-54).
5. `## SAFE-21 No-Mutation Proof` — the boolean block + "only the predeclared
   COMMAND: lines were issued" + validator tokens (lines 65-80; rename 257's
   SAFE-20 -> SAFE-21).
6. `## Rollback Evidence` — Phase 256 anchor path (lines 82-96).
7. `## Blockers and Remediation` — if `not-ready`, each divergence (D-07 union) as
   a concrete blocker with observed values (lines 98-110); if `ready-for-approval`,
   state none and that this is NOT approval (SAFE-21 / D-10).
8. `## Next Recommendation` — Netwatch stays owner; a separate future milestone may
   request canary approval (lines 112-117).

The packet MUST state it **supersedes** the 257 `not-ready` packet (CONTEXT
"Specific Ideas") and show the two previously-failing rows now passing.

---

## Shared Patterns

### Validate-before-execute (D-08, applies to harness + command file)
**Source:** `src/wanctl/readonly_validator.py` (`validate_command` lines 78-101; `iter_commands` 50-63; `self_test` 112-126).
**Apply to:** every live RouterOS command in the harness, before the live client is even constructed.
The validator rejects shell metacharacters (`FORBIDDEN_SUBSTRINGS`, lines 17-26) and
RouterOS mutating verbs (`FORBIDDEN_ROUTEROS_ACTIONS`, lines 28-45), and requires the
command to start with a recognized read-only object (`READ_ONLY_ROUTEROS_OBJECTS`,
lines 8-15). Emit `READONLY_COMMANDS_VALIDATED` + `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED`
before any live execution.

### Fail-closed verdict (D-02, applies to harness + test)
**Source:** `scripts/phase259-ownership-proof.py:run_proof` (lines 62-64, inspector error -> rc=1).
**Apply to:** the window gate. Any `inspector_status != "ok"`, any `match == false`,
any cross-check disagreement, any per-route mismatch, or any non-advancing
`last_inspected_at` -> `not-ready`. Never upgrade to readiness on partial/mixed
evidence (D-10).

### Deployed-import proof (applies to harness)
**Source:** `scripts/phase259-ownership-proof.py:_assert_deployed_imports` (lines 81-94).
**Apply to:** harness startup. Print and assert `wanctl.__file__` and the inspector
module resolve under `/opt/wanctl`, so the evidence reflects deployed code.

### Read-only REST cross-check (D-04, applies to harness)
**Source:** `routeros_rest._handle_netwatch_print` (651-683) + `_handle_route_print` (617-649); reached via `router_client.get_router_client` (63-92).
**Apply to:** the independent inventory snapshot. Pure GET; no mutation path is touched.

---

## No Analog Found

None. Every Phase 260 file has a strong analog. The only genuinely *new* logic
(multi-sample windowing, the per-route standing-intent table renderer, and the
divergence-union packet assembler) is a composition of existing, individually-analogged
pieces — the planner should assemble, not invent.

---

## Metadata

**Analog search scope:** `scripts/`, `tests/`, `src/wanctl/{steering/,}`,
`.planning/milestones/v1.56-phases/257-.../evidence/`.
**Files scanned:** 9 (CONTEXT, 2 analog harness/test, validator, inspector, health,
route_manager, router_client, routeros_rest, 257 packet, 257 command file).
**Pattern extraction date:** 2026-06-25
**Safety:** read-only / SAFE-21 — no source mutation; PATTERNS.md is the only file written.

## PATTERN MAPPING COMPLETE

**Phase:** 260 - Dry-Run Observation Rerun + Canary Readiness
**Files classified:** 3 (1 script, 1 test, 1 evidence bundle)
**Analogs found:** 3 / 3

### Coverage
- Files with exact analog: 3
- Files with role-match analog: 0
- Files with no analog: 0

### Key Patterns Identified
- The harness is "phase259-ownership-proof.py generalized": same `/opt` bootstrap + `validate_commands_before_run(_NoRunClient(), commands)` gate + deployed-import assertion + single greppable verdict token, extended to a multi-sample bounded window, an independent REST cross-check, and a 257-shaped packet.
- Authoritative readiness signal is `ownership_inspection.inspector_status=="ok"` AND `match==true` per sample (D-01), with `route_management.guard` demoted to supplementary; verdict is fail-closed on any single bad sample (D-02).
- Evidence bundle copies Phase 257's four-artifact layout and packet section order verbatim (D-09), updating only the two matrix rows that 258 (REST read-only) and 259 (live `ownership_inspection`) fixed, and stamping it as superseding the 257 `not-ready` packet.

### File Created
`.planning/phases/260-dry-run-observation-rerun-canary-readiness/260-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. The planner can reference each analog (with line numbers) directly in PLAN.md action sections.
