---
phase: 244-health-payload-attribution-metadata
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - scripts/phase244-safe17-boundary-check.sh
  - tests/test_phase244_safe17_verifier.py
  - tests/test_health_check.py
  - tests/steering/test_steering_health.py
  - tests/test_spectrum_cake_autorate_artifacts.py
  - tests/test_att_cake_autorate_artifacts.py
autonomous: true
requirements: [SAFE-17, HEALTH-01]
user_setup: []

must_haves:
  truths:
    - "A 244-specific SAFE-17 verifier exists and passes against the current tree (additive-health-only baseline, zero out-of-allowlist drift)."
    - "The 244 verifier rejects an out-of-allowlist controller-path edit (e.g. queue_controller.py) and a dirty src/wanctl/ tree."
    - "steering/health.py is in the verifier allowlist regex AND embedded allowed_paths set."
    - "Contract-snapshot tests pin the EXACT existing measurement keys+types on all three producers and assert the new triple is a strict superset (RED until Wave 1 lands the additive keys)."
  artifacts:
    - path: "scripts/phase244-safe17-boundary-check.sh"
      provides: "Fail-closed controller-path drift verifier, anchor 49fb1393, allowlist incl. steering/health.py"
      contains: "phase239-protected-body-diff.py"
    - path: "tests/test_phase244_safe17_verifier.py"
      provides: "Mirror test pinned to PHASE_CLOSE_ANCHOR=49fb1393 (NOT HEAD)"
      contains: "49fb1393"
    - path: "tests/steering/test_steering_health.py"
      provides: "rtt_source triple contract assertions (extended)"
      contains: "producer"
  key_links:
    - from: "scripts/phase244-safe17-boundary-check.sh"
      to: "scripts/phase239-protected-body-diff.py"
      via: "subprocess invocation (--anchor, --json)"
      pattern: "phase239-protected-body-diff\\.py"
    - from: "tests/test_phase244_safe17_verifier.py"
      to: "scripts/phase244-safe17-boundary-check.sh"
      via: "subprocess executes verifier in detached worktree"
      pattern: "phase244-safe17-boundary-check\\.sh"
---

<objective>
Land the Wave 0 drift-detection and byte-preservation scaffolding BEFORE any health-shape edit
touches the controller path. This plan ships the 244 SAFE-17 boundary verifier (cloned from
phase242, anchor advanced to the resolved 243-close SHA), its mirror test (pinned to that
anchor, NOT HEAD), and the contract-snapshot / byte-preservation test extensions on all three
`/health` producers. The contract tests will be RED on the new triple until Wave 1 lands the
additive keys — that is intentional: the byte-preservation guard must exist first so any drift
in the existing contract fields is caught the instant Wave 1 edits land.

Purpose: SAFE-17 requires a fail-closed verifier proving no out-of-allowlist controller-path
drift; HEALTH-01 requires the existing contract (`raw_rtt_ms`, `available`, `staleness_sec`,
plus 242's `backend_active`) to be byte-preserved. Both guarantees must be machine-checkable
before the additive edits, per VALIDATION.md Wave 0.

Output: `scripts/phase244-safe17-boundary-check.sh`, `tests/test_phase244_safe17_verifier.py`,
and extended contract/integration assertions in `tests/test_health_check.py`,
`tests/steering/test_steering_health.py`, `tests/test_spectrum_cake_autorate_artifacts.py`,
`tests/test_att_cake_autorate_artifacts.py`.
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
@.planning/phases/244-health-payload-attribution-metadata/244-VALIDATION.md

<resolved_anchor>
243-close anchor (verified via `git log --oneline | grep 243` at plan time):
`49fb1393` — `docs(243-05): backfill plan 05 execution summary` — the last `243-`prefixed commit.
This SUPERSEDES the provisional `380fadbd` flagged `TODO(phase-close)` in
`tests/test_phase243_safe17_verifier.py:22`. Pin the 244 verifier comparison anchor and the
mirror-test `PHASE_CLOSE_ANCHOR` to `49fb1393`, NOT HEAD.
</resolved_anchor>

<interfaces>
<!-- Verified facts the executor needs — no codebase exploration required. -->

phase242 verifier topology (scripts/phase242-safe17-boundary-check.sh — the clone template):
- Line 19:  ANCHOR="v1.52"               → 244: set comparison anchor to 49fb1393
- Lines 20-22: PHASE239/240/241_CLOSE_ANCHOR (03c82de0 / a181ca27 / d8179bb6) → KEEP verbatim (244 touches none of these frozen files)
- Line 23:  OUT=".planning/phases/242-.../evidence/safe17-boundary-242.json"  → 244: repoint to 244 evidence dir
- Line 24:  ALLOWED_OUT_PREFIX=".planning/phases/242-.../evidence/"           → 244: repoint to 244 evidence dir
- Line 25:  V153_ALLOWLIST_RE  → ADD `steering/health\.py` (currently ABSENT, verified 0 matches)
- Lines 120-132: embedded python `allowed_paths` set (rtt_backend.py, rtt_measurement.py, check_config_validators.py, check_steering_validators.py, fping_measurement.py, reflector_scorer.py, rtt_backend_factory.py, autorate_continuous.py, steering/daemon.py, health_check.py, wan_controller.py) → ADD "src/wanctl/steering/health.py"
- Line 239: self-test references queue_controller.py as the out-of-allowlist trip file → KEEP (queue_controller.py is NOT allowlisted; wan_controller.py IS, so it would not trip)
- Lines 258-371: check_measure_rtt_fping_scorer_guard + FORBIDDEN_TOKENS (EWMA/ewma/dwell/deadband/arbitration/fusion/factor_down/step_up/ceiling/floor) → KEEP verbatim
- Lines 373-402: protected_body_ok_with_measure_rtt_exception → KEEP verbatim
- Lines 506-532: RTT-seam / reflector-scorer / phase241-frozen byte-identity gates → KEEP verbatim
- Line 549: invokes scripts/phase239-protected-body-diff.py --anchor "$ANCHOR" --json → KEEP

phase239-protected-body-diff.py PROTECTED map (scripts/phase239-protected-body-diff.py:21-32):
  "src/wanctl/rtt_measurement.py": [7 seam functions]
  "src/wanctl/wan_controller.py": ["WANController.measure_rtt"]
  → get_health_data / _build_measurement_section / _build_rtt_source_section are NOT in this map.
  → As long as 244 leaves measure_rtt + the 7 seam functions untouched, all_identical:true holds
    and NO protected-body exception widening is needed. (Corrects 244-RESEARCH.md.)

Mirror-test template (tests/test_phase243_safe17_verifier.py, 109 lines):
- VERIFIER / EVIDENCE path constants
- PHASE_CLOSE_ANCHOR (line 22) — provisional 380fadbd → 244: pin 49fb1393
- detached_worktree fixture; commit_worktree_change helper with SKIP_DOC_CHECK=1
- test_script_is_executable; test_fails_on_out_of_allowlist_change (uses queue_controller.py);
  test_fails_on_dirty_src_wanctl_change

Existing contract-test anchors to extend:
- tests/test_health_check.py: test_measurement_byte_preserved (~line 1960),
  test_measurement_backend_fallback_keys_are_per_wan (~line 1989) — direct-builder pattern:
  HealthCheckHandler.__new__(HealthCheckHandler) then _build_measurement_section({...}).
- tests/steering/test_steering_health.py: test_health_includes_rtt_source_section (~line 1288)
  — fake daemon harness passing rtt_source={...}; section = data["rtt_source"].
- tests/test_spectrum_cake_autorate_artifacts.py: test_state_bridge_serves_wanctl_compatible_health_endpoint (~line 164)
  — spawns bridge subprocess, polls /health, asserts wan["measurement"]["raw_rtt_ms"] etc.
- tests/test_att_cake_autorate_artifacts.py: mirror of the spectrum test.

The attribution triple (uniform JSON contract across all three producers):
| Key         | wanctl-backend (steering, autorate) | cake-autorate-bridge |
| producer    | "wanctl-backend"                    | "cake-autorate-bridge" |
| backend     | icmplib | fping | null               | null |
| source_ip   | configured per-WAN source | null      | null |
backend_active (Phase 242, factory-selected) is KEPT + byte-preserved; backend (per-sample,
producing) is the additive newcomer (D-03) — distinct facts, not duplicates.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Clone the phase242 verifier into phase244 with three minimal diffs</name>
  <files>scripts/phase244-safe17-boundary-check.sh</files>
  <read_first>
    - scripts/phase242-safe17-boundary-check.sh (the clone template — read in full)
    - scripts/phase239-protected-body-diff.py (lines 21-32 — confirm PROTECTED map does NOT list the health builders)
    - scripts/phase243-safe17-boundary-check.sh (negative reference — do NOT clone this one; it hard-rejects ANY src/wanctl diff)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§Shared Pattern: SAFE-17 — the three diffs)
  </read_first>
  <action>
    Copy `scripts/phase242-safe17-boundary-check.sh` verbatim to
    `scripts/phase244-safe17-boundary-check.sh`, then apply exactly three diffs and nothing else:
    (1) Advance the comparison anchor: change the default `ANCHOR="v1.52"` (line 19) to the
    resolved 243-close SHA `49fb1393`. Verify with `git rev-parse --verify 49fb1393^{commit}`
    before pinning. KEEP the chained PHASE239_CLOSE_ANCHOR=03c82de0, PHASE240_CLOSE_ANCHOR=a181ca27,
    PHASE241_CLOSE_ANCHOR=d8179bb6 byte-identity gates verbatim — 244 touches none of those frozen
    files. Repoint `OUT` and `ALLOWED_OUT_PREFIX` to
    `.planning/phases/244-health-payload-attribution-metadata/evidence/safe17-boundary-244.json`
    and its directory.
    (2) Add `steering/health\.py` to the allowlist: insert `steering/health\.py|` into the
    `V153_ALLOWLIST_RE` regex (line 25) AND add the string `"src/wanctl/steering/health.py"` to the
    embedded-Python `allowed_paths` set (lines 120-132). steering/health.py is currently ABSENT
    (verified 0 matches); D-01 surfaces attribution there so it must be allowlisted.
    (3) Keep the protected-body machinery VERBATIM — do NOT widen it. Per PATTERNS.md correction,
    `get_health_data`, `_build_measurement_section`, `_build_rtt_source_section` are NOT in
    `phase239-protected-body-diff.py`'s PROTECTED map, so they never trip the protected-body diff;
    `protected_body_ok_with_measure_rtt_exception` and `check_measure_rtt_fping_scorer_guard`
    (with its FORBIDDEN_TOKENS set) stay unchanged and still prove zero control-logic drift.
    Make the script executable (`chmod +x`). Keep the self-test's queue_controller.py trip-file
    reference unchanged — wan_controller.py is allowlisted so it would not trip; queue_controller.py
    is the correct out-of-allowlist sentinel.
  </action>
  <verify>
    <automated>bash scripts/phase244-safe17-boundary-check.sh --anchor 49fb1393 && grep -q 'steering/health\\.py' scripts/phase244-safe17-boundary-check.sh && grep -vc '^#' scripts/phase244-safe17-boundary-check.sh | grep -q . && grep -q 'safe17-boundary-244.json' scripts/phase244-safe17-boundary-check.sh && grep -q 'phase239-protected-body-diff.py' scripts/phase244-safe17-boundary-check.sh</automated>
  </verify>
  <acceptance_criteria>
    - Script is executable (`test -x scripts/phase244-safe17-boundary-check.sh`).
    - Running `bash scripts/phase244-safe17-boundary-check.sh` exits 0 against the current tree
      (no health edits yet → zero out-of-allowlist drift, control bodies byte-identical, emitted
      `passed: true` in `.planning/phases/244-.../evidence/safe17-boundary-244.json`).
    - `V153_ALLOWLIST_RE` and the embedded `allowed_paths` set BOTH contain `steering/health.py`.
    - PHASE239/240/241 close anchors are byte-identical to the phase242 source (verified by `grep`
      for `03c82de0`, `a181ca27`, `d8179bb6`).
    - `phase239-protected-body-diff.py` is still invoked; no protected-body exception was widened.
  </acceptance_criteria>
  <done>
    `scripts/phase244-safe17-boundary-check.sh` exists, is executable, passes against the current
    tree, allowlists `steering/health.py`, advances the anchor to `49fb1393`, and keeps the
    242 protected-body/forbidden-token machinery verbatim.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create the 244 verifier mirror test pinned to the resolved anchor</name>
  <files>tests/test_phase244_safe17_verifier.py</files>
  <read_first>
    - tests/test_phase243_safe17_verifier.py (the mirror template — read in full, 109 lines; note line 22 PHASE_CLOSE_ANCHOR and its TODO(phase-close) comment)
    - scripts/phase244-safe17-boundary-check.sh (the script under test, from Task 1)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§tests/test_phase244_safe17_verifier.py — the mirror structure)
  </read_first>
  <action>
    Mirror `tests/test_phase243_safe17_verifier.py` into `tests/test_phase244_safe17_verifier.py`,
    repointed to phase244: set the `VERIFIER` constant to `scripts/phase244-safe17-boundary-check.sh`
    and `EVIDENCE` to `.planning/phases/244-health-payload-attribution-metadata/evidence/safe17-boundary-244.json`.
    Pin `PHASE_CLOSE_ANCHOR = "49fb1393"` (the resolved 243-close SHA — NOT HEAD, NOT the provisional
    `380fadbd`). Copy the `detached_worktree` fixture and the `commit_worktree_change` helper
    (with `SKIP_DOC_CHECK=1`) verbatim. Keep `test_script_is_executable`. Keep
    `test_fails_on_out_of_allowlist_change` using `src/wanctl/queue_controller.py` as the
    out-of-allowlist trip file (wan_controller.py is allowlisted in 244, so DO NOT use it — it
    would not trip). Keep `test_fails_on_dirty_src_wanctl_change` asserting the dirty-tree
    rejection message. Replace any 243 measurement-only contract test with a
    `test_static_phase244_script_contract` (inverse of 243's contract test) asserting the 244
    script CONTAINS the 242 machinery strings: `safe17-boundary-244.json`, the 244 evidence dir,
    `V153_ALLOWLIST_RE`, `phase239-protected-body-diff.py`, `check_measure_rtt_fping_scorer_guard`,
    and `steering/health` — because 244 KEEPS that machinery (unlike 243).
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_phase244_safe17_verifier.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/test_phase244_safe17_verifier.py` pins `PHASE_CLOSE_ANCHOR = "49fb1393"` (grep confirms,
      and the string `380fadbd` is ABSENT).
    - All mirror tests pass: script-executable, out-of-allowlist (queue_controller.py) rejected,
      dirty-tree rejected, static-contract assertions present.
    - The worktree fixtures pin to `49fb1393`, not `HEAD` (no `rev-parse HEAD` baseline).
  </acceptance_criteria>
  <done>
    The mirror test exists, is pinned to `49fb1393`, and all its cases pass against the Task 1
    verifier.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Pin byte-preservation contracts and the additive-triple superset on all three producers</name>
  <files>tests/test_health_check.py, tests/steering/test_steering_health.py, tests/test_spectrum_cake_autorate_artifacts.py, tests/test_att_cake_autorate_artifacts.py</files>
  <read_first>
    - tests/test_health_check.py (test_measurement_byte_preserved ~1960; test_measurement_backend_fallback_keys_are_per_wan ~1989 — direct-builder pattern via HealthCheckHandler.__new__)
    - tests/steering/test_steering_health.py (test_health_includes_rtt_source_section ~1288; fake-daemon harness passing rtt_source=, lines 39-58)
    - tests/test_spectrum_cake_autorate_artifacts.py (test_state_bridge_serves_wanctl_compatible_health_endpoint ~164-213)
    - tests/test_att_cake_autorate_artifacts.py (the spectrum mirror)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§Shared Pattern: Byte-preservation contract test)
    - .planning/phases/244-health-payload-attribution-metadata/244-VALIDATION.md (Phase Requirements → Test Map)
  </read_first>
  <behavior>
    - Autorate (test_health_check.py): a contract-snapshot test pins the EXACT existing measurement
      keys+types — `available: bool`, `raw_rtt_ms: float|None`, `staleness_sec: float|None`,
      `backend_active: str`, `fell_back: bool`, `fallback_count: int` — AND asserts the result is a
      strict superset adding `producer == "wanctl-backend"`, `backend in {"icmplib","fping",None}`,
      `source_ip` (str|None). Extend the existing byte-preserved test rather than replacing it.
    - Steering (test_steering_health.py): extend test_health_includes_rtt_source_section so the
      `rtt_source` section asserts the same triple keys (`producer == "wanctl-backend"`,
      `backend` in the allowed set, `source_ip` str|None) alongside the existing
      current/last_successful/last_rtt_ms/counts keys (byte-preserved).
    - Bridge (test_spectrum + test_att artifacts): extend the endpoint test so
      `wan["measurement"]["producer"] == "cake-autorate-bridge"`,
      `wan["measurement"]["backend"] is None`, `wan["measurement"]["source_ip"] is None`, AND the
      existing `available`/`raw_rtt_ms`/`staleness_sec` assertions remain unchanged. Mirror
      identically in both spectrum and att files (Pitfall 4 — keep them in lockstep).
    - These tests are EXPECTED RED until Wave 1 lands the additive keys — that is the intended
      drift guard. Mark the new triple assertions so the byte-preservation assertions on the
      existing keys stay GREEN now (they must never go red on the existing contract fields).
  </behavior>
  <action>
    Extend the four test files using the verified direct-builder / endpoint patterns above. In
    `test_health_check.py`, reuse the `HealthCheckHandler.__new__(HealthCheckHandler)` +
    `_build_measurement_section({"measurement": {...}})` direct-builder call; add an explicit
    strict-superset key check (`set(existing_contract_keys) <= set(result.keys())`) plus exact-type
    assertions on the six existing keys, then assert the three new triple keys/values. In
    `test_steering_health.py`, extend the fake-daemon `rtt_source=` harness to include
    producer/backend/source_ip and assert them off `data["rtt_source"]`. In both bridge artifact
    tests, add the three triple assertions to the existing `/health` endpoint poll. Keep all new
    triple assertions structured so the existing-contract assertions pass immediately (Wave 0) and
    only the new-key assertions flip GREEN once Wave 1 producers land. Run `.venv/bin/ruff format`
    on the four files.
  </action>
  <verify>
    <automated>.venv/bin/ruff check tests/test_health_check.py tests/steering/test_steering_health.py tests/test_spectrum_cake_autorate_artifacts.py tests/test_att_cake_autorate_artifacts.py && grep -q 'producer' tests/test_health_check.py && grep -q 'producer' tests/steering/test_steering_health.py && grep -q 'cake-autorate-bridge' tests/test_spectrum_cake_autorate_artifacts.py && grep -q 'cake-autorate-bridge' tests/test_att_cake_autorate_artifacts.py</automated>
  </verify>
  <acceptance_criteria>
    - All four test files reference `producer` / triple keys; spectrum + att both assert
      `producer == "cake-autorate-bridge"`, `backend is None`, `source_ip is None`.
    - The existing-contract assertions (available/raw_rtt_ms/staleness_sec/backend_active/fell_back/
      fallback_count keys+types) are present and pass NOW (Wave 0), independent of the new keys.
    - ruff is clean on all four files.
    - The new-triple assertions are RED until Wave 1 (this is expected; do NOT skip or xfail them
      in a way that hides Wave 1 drift — they should fail loudly on missing keys until producers land).
  </acceptance_criteria>
  <done>
    Contract-snapshot + byte-preservation + strict-superset assertions exist on all three producers'
    test surfaces; existing-contract assertions are green; new-triple assertions are the Wave 1
    target.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → `/health` (localhost) | `/health` is bound to `127.0.0.1:9101` (autorate/bridge) / `:9102` (steering); only local processes + operator-authenticated SSH reach it. No untrusted network input. |
| repo tree → SAFE-17 verifier | The verifier reads git history + working tree; it is a read-only diff gate (no mutation of src). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-244-01 | Information Disclosure | `source_ip` on `/health` | accept | `source_ip` is the operator's own configured per-WAN bind IP (already operator-known infra, not a secret); `/health` is localhost-bound. Low/info finding. No action. |
| T-244-02 | Tampering | controller-path drift slipping past the boundary gate | mitigate | `scripts/phase244-safe17-boundary-check.sh` fails closed on any out-of-allowlist `src/wanctl/` diff or dirty tree; `phase239-protected-body-diff.py` proves EWMA/dwell/deadband/arbitration/fusion bodies byte-identical; FORBIDDEN_TOKENS guard blocks control-logic tokens in allowlisted files. |
| T-244-03 | Repudiation | wrong/HEAD-drifting anchor masking real drift | mitigate | Anchor pinned to resolved 243-close SHA `49fb1393` (verified via `git rev-parse`); mirror test asserts the pin and rejects HEAD-relative baselines. |
| T-244-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — phase installs no external packages (RESEARCH §Standard Stack). No package-manager install tasks in this plan. |
</threat_model>

<verification>
- `bash scripts/phase244-safe17-boundary-check.sh` exits 0 against the current tree (no src edits
  in this plan → zero drift; `passed: true` evidence emitted).
- `.venv/bin/pytest -o addopts='' tests/test_phase244_safe17_verifier.py -q` passes.
- `.venv/bin/ruff check` clean on the four extended test files.
- Existing-contract byte-preservation assertions pass NOW; new-triple assertions are the Wave 1
  target (expected RED until producers land).
- Do NOT gate on full-suite green (RESEARCH: ~34 pre-existing stale-boundary failures).
</verification>

<success_criteria>
- The 244 SAFE-17 verifier exists, is executable, allowlists `steering/health.py`, pins anchor
  `49fb1393`, keeps the 242 protected-body/forbidden-token machinery verbatim, and passes clean.
- The mirror test pins `49fb1393` and all cases pass.
- Contract-snapshot + strict-superset assertions are in place on all three producers' tests, with
  existing-contract assertions green.
</success_criteria>

<output>
Create `.planning/phases/244-health-payload-attribution-metadata/244-01-SUMMARY.md` when done.
</output>
