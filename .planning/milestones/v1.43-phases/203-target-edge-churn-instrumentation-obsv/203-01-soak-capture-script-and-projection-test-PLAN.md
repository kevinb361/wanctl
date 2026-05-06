---
id: 203-01
phase: 203
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/soak-capture.sh
  - tests/test_phase_203_capture_projection.py
autonomous: true
production_canary: false
created: 2026-05-06
requirements:
  - OBSV-05
  - OBSV-07
  - SAFE-07
must_haves:
  truths:
    - "scripts/soak-capture.sh exists as a versioned, executable bash script with `set -euo pipefail`."
    - "The script takes a positional SOAK_TS argument and reads HEALTH_URL from a mandatory environment variable; no IPs or hostnames are hardcoded into the script body."
    - "The jq projection emits all 14 v1.42 keys verbatim AND the 7 new Phase 203 keys: load_rtt_ms, baseline_rtt_ms, load_rtt_delta_us, last_zone, ul_suppressions_completed_window_count, ul_suppressions_completed_window_by_cause, ul_suppressions_lifetime_by_cause."
    - "load_rtt_delta_us is computed as `((load_rtt_ms - baseline_rtt_ms) * 1000 | floor)` and emitted as integer microseconds. When baseline_rtt_ms is null, the projection emits `null` for load_rtt_delta_us."
    - "tests/test_phase_203_capture_projection.py drives the projection against a synthesized /health payload via subprocess + jq, asserts each new key has the expected value, and asserts the v1.42 keys are preserved."
    - "No src/wanctl/** files modified by this plan."
  artifacts:
    - path: scripts/soak-capture.sh
      provides: "Canonical versioned soak-capture harness with the seven new v1.43 NDJSON projection keys"
      contains: "load_rtt_delta_us"
    - path: tests/test_phase_203_capture_projection.py
      provides: "OBSV-05 / OBSV-07 capture-projection contract test (synthesized /health → jq → asserted NDJSON row)"
      contains: "load_rtt_delta_us"
  key_links:
    - from: "scripts/soak-capture.sh jq projection"
      to: "tests/test_phase_203_capture_projection.py"
      via: "the test reads the script and runs the same projection via subprocess; OR the test hard-codes the projection and asserts the script body contains it verbatim"
      pattern: "load_rtt_delta_us"
    - from: "scripts/soak-capture.sh"
      to: "HEALTH_URL environment variable"
      via: "`: \"${HEALTH_URL:?HEALTH_URL env var required}\"` guard at top of script"
      pattern: "HEALTH_URL"
---

<objective>
Promote the v1.42 inline-evidence soak capture script to a versioned, parameterized `scripts/soak-capture.sh` and add the seven new Phase 203 projection keys (OBSV-05). Land the capture-projection contract test (`tests/test_phase_203_capture_projection.py`) that validates the projection against a synthesized `/health` payload — the OBSV-07 capture-side leg of the dual-fixture replay strategy.

Purpose: All five required `/health` inputs are exposed post-Phase-202 (verified in 203-RESEARCH.md §Field availability audit). This plan makes the capture script project them into NDJSON rows. The capture-projection contract test validates the schema deterministically without needing a 24h soak. Both deliverables are pure additions in `scripts/` and `tests/` — zero `src/wanctl/` change (SAFE-07).

Output: New `scripts/soak-capture.sh` (versioned harness, public-safe, env-var-driven HEALTH_URL); new `tests/test_phase_203_capture_projection.py` (synthesized `/health` → jq projection → assertions on each of the 7 new keys + spot checks on preserved v1.42 keys).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-RESEARCH.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-VALIDATION.md
@.planning/seeds/SEED-004-v143-target-edge-churn-instrumentation.md
@CLAUDE.md
@.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.sh

<interfaces>
<!-- Reference v1.42 capture script (the basis for the verbatim 14-key projection). Inspected directly. -->
<!-- The promoted scripts/soak-capture.sh keeps every existing key and adds 7 more. -->

v1.42 soak-capture.sh (full content, inspected at .planning/milestones/v1.42-phases/.../soak-capture.sh):
```bash
#!/usr/bin/env bash
set -euo pipefail
SOAK_TS="${1:?SOAK_TS positional arg required}"
SOAK_DURATION_SEC=86400  # 24h
HEALTH_URL="http://10.10.110.223:9101/health"   # <-- IP literal; MUST be parameterized in v1.43
CAPTURE_DIR="/var/tmp/wanctl-soak-${SOAK_TS}"
mkdir -p "$CAPTURE_DIR"

T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

while [ $(date +%s) -lt $SOAK_END ]; do
  T_MONO=$(awk '{print $1; exit}' /proc/uptime)
  T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')
  curl -s "$HEALTH_URL" \
    | jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '{
        t_wall: $twall,
        t_monotonic: $tmono,
        version: .version,
        status: .status,
        floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
        suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
        max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
        red_streak: .wans[0].upload.red_streak,
        zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
        headroom_state: .wans[0].upload.headroom_state,
        headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
        anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
        rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
        docsis_mode_active: .wans[0].upload.docsis_mode_active,
        red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
        red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct
      }' >> "$CAPTURE_DIR/soak-capture.ndjson"
  sleep 1
done
```

Phase 203 additive jq projection (per 203-RESEARCH.md §Capture script delta, locked):
```jq
load_rtt_ms: .wans[0].load_rtt_ms,
baseline_rtt_ms: .wans[0].baseline_rtt_ms,
load_rtt_delta_us: (
    if (.wans[0].load_rtt_ms == null) or (.wans[0].baseline_rtt_ms == null)
    then null
    else ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)
    end
),
last_zone: .wans[0].upload.hysteresis.last_zone,
ul_suppressions_completed_window_count: .wans[0].upload.hysteresis.suppressions_completed_window_count,
ul_suppressions_completed_window_by_cause: .wans[0].upload.hysteresis.suppressions_completed_window_by_cause,
ul_suppressions_lifetime_by_cause: .wans[0].upload.hysteresis.suppressions_lifetime_by_cause
```

The null-guard on `load_rtt_delta_us` implements gray-area-decision #8: if either source field is null, emit `null` for the delta (the aggregator in plan 203-02 filters these out and reports the count). This branch never fires on a healthy daemon — both fields are always populated post-WANController.__init__ — but the guard makes the projection robust to early-startup samples and to future `/health` schema changes.
</interfaces>
</context>

<locked_decisions>
- **Script parameterization (gray-area #4):** positional `SOAK_TS` arg (required); env-var `HEALTH_URL` (required, NO default — public-safe rule from CLAUDE.md prevents hardcoded IPs); env-var `SOAK_DURATION_SEC` (default 86400); env-var `CAPTURE_DIR` (default `/var/tmp/wanctl-soak-${SOAK_TS}`). `set -euo pipefail` mandatory.
- **Microsecond units (gray-area #3):** `load_rtt_delta_us` is integer microseconds, computed via `floor`. This matches `load_rtt_delta_us` axis units and aligns with existing `int(...)` casts in `health_check.py`.
- **Null handling (gray-area #8):** if `load_rtt_ms` OR `baseline_rtt_ms` is null in the source JSON, the projection emits `load_rtt_delta_us: null`. The aggregator (plan 203-02) filters nulls from histogram and percentile computation and reports the filtered count in summary metadata.
- **`ul_*` prefix on Phase 202 fields:** the three cause-tag fields are projected as `ul_suppressions_completed_window_count`, `ul_suppressions_completed_window_by_cause`, `ul_suppressions_lifetime_by_cause`. The prefix disambiguates upload-side from a future `dl_*` sibling without churning the schema.
- **All v1.42 keys preserved verbatim.** No deletion, no rewording. Phase 203 is purely additive (SAFE-07 invariant for the harness layer mirrors the source-layer invariant).
- **No production binary change.** All five required inputs are exposed at `/health` post-Phase-202 (203-RESEARCH.md §Field availability audit, verified at health_check.py:248-249, :319, :321-327).
</locked_decisions>

<tasks>

<task type="auto">
  <name>Task 1: Create scripts/soak-capture.sh as the canonical versioned harness with the seven new projection keys</name>
  <files>scripts/soak-capture.sh</files>
  <action>
    Create `scripts/soak-capture.sh` as a new file. Public-safe content only — no IPs, no hostnames. Use the v1.42 reference script as the structural basis but replace the hardcoded `HEALTH_URL` with an env-var requirement, and append the seven new Phase 203 projection keys to the jq object literal.

    Concrete file contents:

    ```bash
    #!/usr/bin/env bash
    # wanctl soak-capture harness (v1.43 Phase 203)
    #
    # Usage: HEALTH_URL=http://<host>:9101/health bash scripts/soak-capture.sh <SOAK_TS>
    #
    # Required env: HEALTH_URL  — full /health endpoint URL (no default; public-safe).
    # Optional env: SOAK_DURATION_SEC (default 86400 = 24h)
    #               CAPTURE_DIR        (default /var/tmp/wanctl-soak-${SOAK_TS})
    #
    # Writes one NDJSON row per second to ${CAPTURE_DIR}/soak-capture.ndjson.
    # See docs/SOAK_HARNESS.md for the full per-row schema (created in plan 203-03).

    set -euo pipefail

    SOAK_TS="${1:?SOAK_TS positional arg required}"
    : "${HEALTH_URL:?HEALTH_URL env var required (e.g. HEALTH_URL=http://<host>:9101/health)}"
    SOAK_DURATION_SEC="${SOAK_DURATION_SEC:-86400}"
    CAPTURE_DIR="${CAPTURE_DIR:-/var/tmp/wanctl-soak-${SOAK_TS}}"

    mkdir -p "$CAPTURE_DIR"

    T0_MONO=$(awk '{print $1; exit}' /proc/uptime)
    SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

    while [ "$(date +%s)" -lt "$SOAK_END" ]; do
      T_MONO=$(awk '{print $1; exit}' /proc/uptime)
      T_MONO_DELTA=$(awk -v a="$T_MONO" -v b="$T0_MONO" 'BEGIN{print a-b}')
      curl -s "$HEALTH_URL" \
        | jq -c --arg twall "$(date -u -Iseconds)" --argjson tmono "$T_MONO_DELTA" '{
            t_wall: $twall,
            t_monotonic: $tmono,
            version: .version,
            status: .status,
            floor_hit_cycles_total: .wans[0].upload.floor_hit_cycles_total,
            suppressions_per_min: .wans[0].upload.hysteresis.suppressions_per_min,
            max_delay_delta_us: .wans[0].upload.max_delay_delta_us,
            red_streak: .wans[0].upload.red_streak,
            zone_trace_tail: (.wans[0].upload.zone_trace | .[-5:]),
            headroom_state: .wans[0].upload.headroom_state,
            headroom_exhausted_streak: .wans[0].upload.headroom_exhausted_streak,
            anti_windup_triggers: .wans[0].upload.anti_windup_triggers,
            rtt_integral_ms_s: .wans[0].upload.rtt_integral_ms_s,
            docsis_mode_active: .wans[0].upload.docsis_mode_active,
            red_decay_step_pct: .wans[0].upload.red_decay_step_pct,
            red_decay_delta_max_pct: .wans[0].upload.red_decay_delta_max_pct,
            load_rtt_ms: .wans[0].load_rtt_ms,
            baseline_rtt_ms: .wans[0].baseline_rtt_ms,
            load_rtt_delta_us: (
              if (.wans[0].load_rtt_ms == null) or (.wans[0].baseline_rtt_ms == null)
              then null
              else ((.wans[0].load_rtt_ms - .wans[0].baseline_rtt_ms) * 1000 | floor)
              end
            ),
            last_zone: .wans[0].upload.hysteresis.last_zone,
            ul_suppressions_completed_window_count: .wans[0].upload.hysteresis.suppressions_completed_window_count,
            ul_suppressions_completed_window_by_cause: .wans[0].upload.hysteresis.suppressions_completed_window_by_cause,
            ul_suppressions_lifetime_by_cause: .wans[0].upload.hysteresis.suppressions_lifetime_by_cause
          }' >> "$CAPTURE_DIR/soak-capture.ndjson"
      sleep 1
    done
    ```

    Then `chmod +x scripts/soak-capture.sh`.

    Public-safe verification: `grep -nE '(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)|[a-zA-Z0-9-]+\.local|cake-shaper' scripts/soak-capture.sh` MUST return zero matches. The script body contains no IP, no hostname, no operator-identifying string.
  </action>
  <verify>
    <automated>test -x scripts/soak-capture.sh && bash -n scripts/soak-capture.sh && grep -q "HEALTH_URL:?HEALTH_URL env var required" scripts/soak-capture.sh && grep -q "load_rtt_delta_us:" scripts/soak-capture.sh && grep -q "ul_suppressions_completed_window_count" scripts/soak-capture.sh && grep -q "ul_suppressions_completed_window_by_cause" scripts/soak-capture.sh && grep -q "ul_suppressions_lifetime_by_cause" scripts/soak-capture.sh && ! grep -E '(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)' scripts/soak-capture.sh</automated>
  </verify>
  <done>
    scripts/soak-capture.sh exists, is executable, passes `bash -n` syntax check, contains all 7 new projection keys, requires HEALTH_URL via env-var guard, and contains zero IP/hostname literals.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests/test_phase_203_capture_projection.py with the OBSV-05/OBSV-07 capture-side contract tests</name>
  <files>tests/test_phase_203_capture_projection.py</files>
  <action>
    Create `tests/test_phase_203_capture_projection.py`. The test extracts the jq projection from `scripts/soak-capture.sh` (read script body, slice between the `'{` and the closing `}'`) and runs it via `subprocess.run(["jq", "-c", PROJECTION], input=health_json)`. Each test synthesizes a small `/health` payload, runs the projection, and asserts on the resulting NDJSON row.

    Module structure (mirror `tests/test_phase_202_replay.py` import + REPO_ROOT pattern):

    ```python
    """Phase 203 capture-projection contract tests (OBSV-05, OBSV-07 capture side).

    Validates that scripts/soak-capture.sh's jq projection emits the seven new
    Phase 203 keys with correct values when fed a synthesized /health payload.
    Does NOT require a live daemon, a soak fixture, or network access.

    The test extracts the projection from the script body so a future edit to
    the script is exercised here automatically (no double source of truth).
    """
    from __future__ import annotations

    import json
    import re
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    REPO_ROOT = Path(__file__).resolve().parents[1]
    CAPTURE_SCRIPT = REPO_ROOT / "scripts" / "soak-capture.sh"


    def _extract_projection(script_path: Path) -> str:
        """Slice the jq object literal out of the capture script.

        Returns the text between the first '{' and the matching closing '}' that
        appears on a line containing only whitespace + '}' + the closing quote.
        Conservative: relies on the script keeping the v1.42 layout (jq '{...}').
        """
        text = script_path.read_text()
        # The projection lives inside `jq -c ... '{ ... }'`. Match the '{' that
        # follows the opening quote and capture until the matching '}' on its own line.
        match = re.search(r"jq\s+-c[^']*'(\{.*?\})'\s*>>", text, re.DOTALL)
        if match is None:
            raise RuntimeError(
                "Could not extract jq projection from scripts/soak-capture.sh; "
                "did the script structure change?"
            )
        return match.group(1)


    SYNTHETIC_HEALTHY = {
        "version": "1.43-dev",
        "status": "healthy",
        "wans": [{
            "name": "spectrum",
            "load_rtt_ms": 18.42,
            "baseline_rtt_ms": 12.0,
            "upload": {
                "floor_hit_cycles_total": 0,
                "max_delay_delta_us": 56,
                "red_streak": 0,
                "rtt_integral_ms_s": 2.293,
                "docsis_mode_active": True,
                "red_decay_step_pct": 0.02,
                "red_decay_delta_max_pct": 0.10,
                "headroom_state": "AVAILABLE",
                "headroom_exhausted_streak": 0,
                "anti_windup_triggers": 0,
                "zone_trace": ["GREEN", "GREEN", "GREEN", "GREEN", "GREEN"],
                "hysteresis": {
                    "suppressions_per_min": 17,
                    "last_zone": "GREEN",
                    "suppressions_completed_window_count": 13,
                    "suppressions_completed_window_by_cause": {
                        "dwell_hold": 13, "backlog_recovery": 0, "other": 0,
                    },
                    "suppressions_lifetime_by_cause": {
                        "dwell_hold": 13, "backlog_recovery": 0, "other": 0,
                    },
                },
            },
        }],
    }


    def _run_projection(health_payload: dict) -> dict:
        """Run the capture script's jq projection against a synthesized /health blob.

        Substitutes the runtime jq vars ($twall, $tmono) via --arg/--argjson so the
        projection runs without the surrounding bash loop.
        """
        if shutil.which("jq") is None:
            pytest.skip("jq not on PATH; required for capture-projection contract test")
        projection = _extract_projection(CAPTURE_SCRIPT)
        result = subprocess.run(
            [
                "jq", "-c",
                "--arg", "twall", "2026-05-06T00:00:00Z",
                "--argjson", "tmono", "0",
                projection,
            ],
            input=json.dumps(health_payload),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)


    class TestNewFieldsProjection:
        """OBSV-05: the seven new Phase 203 keys are emitted with correct values."""

        def test_load_rtt_delta_us_computed_correctly(self) -> None:
            row = _run_projection(SYNTHETIC_HEALTHY)
            # (18.42 - 12.0) * 1000 = 6420.0 → floor → 6420
            assert row["load_rtt_delta_us"] == 6420

        def test_load_rtt_ms_and_baseline_rtt_ms_passed_through(self) -> None:
            row = _run_projection(SYNTHETIC_HEALTHY)
            assert row["load_rtt_ms"] == pytest.approx(18.42)
            assert row["baseline_rtt_ms"] == pytest.approx(12.0)

        def test_last_zone_projected(self) -> None:
            row = _run_projection(SYNTHETIC_HEALTHY)
            assert row["last_zone"] == "GREEN"

        def test_ul_suppression_fields_projected_with_prefix(self) -> None:
            row = _run_projection(SYNTHETIC_HEALTHY)
            assert row["ul_suppressions_completed_window_count"] == 13
            assert row["ul_suppressions_completed_window_by_cause"] == {
                "dwell_hold": 13, "backlog_recovery": 0, "other": 0,
            }
            assert row["ul_suppressions_lifetime_by_cause"] == {
                "dwell_hold": 13, "backlog_recovery": 0, "other": 0,
            }

        def test_new_fields_present_complete_set(self) -> None:
            """All seven new keys appear on every row."""
            row = _run_projection(SYNTHETIC_HEALTHY)
            for key in (
                "load_rtt_ms",
                "baseline_rtt_ms",
                "load_rtt_delta_us",
                "last_zone",
                "ul_suppressions_completed_window_count",
                "ul_suppressions_completed_window_by_cause",
                "ul_suppressions_lifetime_by_cause",
            ):
                assert key in row, f"missing new Phase 203 key: {key}"


    class TestV142KeysPreserved:
        """SAFE-07 / OBSV-08 implication: v1.42 keys remain byte-identical."""

        def test_v142_keys_all_present(self) -> None:
            row = _run_projection(SYNTHETIC_HEALTHY)
            for key in (
                "t_wall", "t_monotonic", "version", "status",
                "floor_hit_cycles_total", "suppressions_per_min",
                "max_delay_delta_us", "red_streak", "zone_trace_tail",
                "headroom_state", "headroom_exhausted_streak",
                "anti_windup_triggers", "rtt_integral_ms_s",
                "docsis_mode_active", "red_decay_step_pct",
                "red_decay_delta_max_pct",
            ):
                assert key in row, f"v1.42 key dropped: {key}"

        def test_zone_trace_tail_is_last_5(self) -> None:
            row = _run_projection(SYNTHETIC_HEALTHY)
            # SYNTHETIC_HEALTHY has 5 zones in zone_trace; tail is the last 5.
            assert row["zone_trace_tail"] == ["GREEN", "GREEN", "GREEN", "GREEN", "GREEN"]


    class TestNullHandling:
        """Gray-area decision #8: null source fields → null delta, no crash."""

        def test_null_load_rtt_ms_yields_null_delta(self) -> None:
            payload = json.loads(json.dumps(SYNTHETIC_HEALTHY))
            payload["wans"][0]["load_rtt_ms"] = None
            row = _run_projection(payload)
            assert row["load_rtt_delta_us"] is None

        def test_null_baseline_rtt_ms_yields_null_delta(self) -> None:
            payload = json.loads(json.dumps(SYNTHETIC_HEALTHY))
            payload["wans"][0]["baseline_rtt_ms"] = None
            row = _run_projection(payload)
            assert row["load_rtt_delta_us"] is None


    class TestNegativeDelta:
        """Realistic case: load_rtt below baseline (sub-baseline measurement)."""

        def test_negative_delta_floored_correctly(self) -> None:
            payload = json.loads(json.dumps(SYNTHETIC_HEALTHY))
            payload["wans"][0]["load_rtt_ms"] = 11.5
            payload["wans"][0]["baseline_rtt_ms"] = 12.0
            row = _run_projection(payload)
            # (11.5 - 12.0) * 1000 = -500.0 → floor → -500
            assert row["load_rtt_delta_us"] == -500
    ```

    Test design notes:
    - The `_extract_projection` regex slices the jq object out of the script body so the test never duplicates the projection. If the script structure changes (e.g. a future edit splits the jq into multiple stages), the regex fails loudly and the planner is forced to update the slicer rather than silently desync the test from the script.
    - `--arg twall ... --argjson tmono ...` substitutes the bash-loop runtime vars so the projection runs standalone.
    - `jq` is already standard project tooling (used in the v1.42 reference script and the inline-aggregator in 201-16). The `pytest.skip` guard handles minimal-shell test environments.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_phase_203_capture_projection.py -v</automated>
  </verify>
  <done>
    All capture-projection tests pass. Each of the seven new keys is asserted with expected value; v1.42 keys are confirmed preserved; null-handling and negative-delta edge cases pass; the test extracts the projection from the script body (no duplicate source of truth).
  </done>
</task>

<task type="auto">
  <name>Task 3: Hot-path regression slice + SAFE-07 source-diff verification</name>
  <files>(none — verification only)</files>
  <action>
    Run the hot-path regression slice (no production code changed; sanity check):
    ```
    .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
    ```

    Run the new test file standalone to confirm the OBSV-05 capture-side automated check is green:
    ```
    .venv/bin/pytest tests/test_phase_203_capture_projection.py -v
    ```

    SAFE-07 mechanical check — this plan modifies ZERO `src/wanctl/` files:
    ```
    git diff b72b463 -- src/wanctl/ | wc -l
    ```
    Expect: 0. Plans 203-01..03 collectively must keep this empty against the Phase 202 close commit (`b72b463`).

    SAFE-05 pin test still green (Phase 203 added no `src/` symbols, so no pin shift expected):
    ```
    .venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"
    ```

    If any of these checks fail, do NOT proceed to commit. Return findings to the operator.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_phase_203_capture_projection.py -v && .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q && .venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts" && test "$(git diff b72b463 -- src/wanctl/ | wc -l)" = "0"</automated>
  </verify>
  <done>
    Capture-projection tests green. Hot-path slice green. SAFE-05 pin test green. `git diff b72b463 -- src/wanctl/` empty. Plan-bounded diff includes only `scripts/soak-capture.sh` and `tests/test_phase_203_capture_projection.py`.
  </done>
</task>

</tasks>

<safe07_compliance>
This plan touches NO files under `src/wanctl/`. The complete diff is bounded to:

- `scripts/soak-capture.sh` (new file)
- `tests/test_phase_203_capture_projection.py` (new file)

Mechanical executor check at plan close:
```bash
git diff b72b463 -- src/wanctl/ | wc -l   # MUST be 0
```

If this returns non-zero at any point during this plan's execution, the executor MUST halt and surface the violation. The harness-only design has no exception path.
</safe07_compliance>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator → `scripts/soak-capture.sh` env vars | `HEALTH_URL`, `SOAK_DURATION_SEC`, `CAPTURE_DIR` come from the operator's environment. Operator-trusted; same trust domain as the deploy host. |
| Daemon `/health` HTTP endpoint → curl | Read-only JSON over HTTP. Same trust boundary as existing v1.42 capture script. |
| Test environment → jq subprocess | Synthesized JSON input from the test, deterministic. No untrusted input. |
| Repo content → public GitHub mirror | CLAUDE.md public-safe rule: NO IPs, hostnames, or operator identities in tracked files. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-203-01-01 | Tampering | `SOAK_TS` shell-substituted into `CAPTURE_DIR` path | low | mitigate | `set -euo pipefail` + `:?` guard; `CAPTURE_DIR="/var/tmp/wanctl-soak-${SOAK_TS}"` is double-quoted. A malicious `SOAK_TS` value containing path-traversal characters (`../`) could write outside `/var/tmp/`, but the operator controls SOAK_TS — same trust as choosing the deploy host. Documented in script header. |
| T-203-01-02 | Information Disclosure | Hardcoded IPs/hostnames in `scripts/soak-capture.sh` | high | mitigate | `HEALTH_URL` parameterized via mandatory env var (no default); script body contains zero IP literals. Task 1 verify clause runs a regex grep that fails loudly if any RFC1918 IP literal sneaks in. |
| T-203-01-03 | Tampering | `_extract_projection` regex desync from script body | low | mitigate | If a future edit changes the jq layout, the regex returns no match → `RuntimeError` raised in the test → CI fails loudly. Better than silent test-skip. |
| T-203-01-04 | Denial of Service | NDJSON line writes under SIGTERM | low | accept | jq emits one complete line per `curl` cycle; `>>` appends are atomic on POSIX for sub-PIPE_BUF writes. A SIGTERM mid-jq is at most a single dropped sample (1 second of soak data), tolerable for a 24h soak. Documented in 203-RESEARCH.md §Risk surfaces. |
| T-203-01-05 | Repudiation / drift | Capture script body diverging from test expectations | low | mitigate | Test extracts the projection from the script body via regex (single source of truth). Manual edit drift is impossible. |
| T-203-01-06 | SAFE-07 invariant violation | Any `src/wanctl/` change | high | mitigate | Task 3 mechanical `git diff b72b463 -- src/wanctl/` check at plan close. The harness-only design has no exception path. |

No high-severity threats remain unresolved. T-203-01-02 and T-203-01-06 are both `mitigate` with concrete mechanical checks.
</threat_model>

<verification>
1. `scripts/soak-capture.sh` exists, is executable, passes `bash -n` syntax check, contains the seven new projection keys, requires `HEALTH_URL` via env-var guard, contains zero RFC1918 IP literals.
2. `tests/test_phase_203_capture_projection.py` runs and all classes pass: `TestNewFieldsProjection`, `TestV142KeysPreserved`, `TestNullHandling`, `TestNegativeDelta`.
3. Hot-path slice green.
4. SAFE-05 pin test green (`.venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"`).
5. `git diff b72b463 -- src/wanctl/` returns empty.

Test commands (project venv per CLAUDE.md):
- `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v`
- Hot-path slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- SAFE-05 pin: `.venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"`
</verification>

<success_criteria>
1. **OBSV-05 mechanically satisfied:** `scripts/soak-capture.sh` projects `load_rtt_delta_us` plus the six supporting fields; `tests/test_phase_203_capture_projection.py::TestNewFieldsProjection` all green.
2. **OBSV-07 (capture side) satisfied:** capture-projection contract test passes; the schema is locked for plan 203-02's aggregator.
3. **SAFE-07 maintained:** `git diff b72b463 -- src/wanctl/` empty at plan close; SAFE-05 pin test green.
4. **Public-safe:** no IPs, hostnames, or operator identities in `scripts/soak-capture.sh`.
5. **All v1.42 keys preserved:** `TestV142KeysPreserved` confirms the existing 16 v1.42 projection keys are byte-identical.
</success_criteria>

<commit_message>
feat(203-01): promote soak-capture harness with v1.43 NDJSON projection keys

Adds canonical scripts/soak-capture.sh (versioned, parameterized, public-safe)
with the seven additive Phase 203 projection keys: load_rtt_ms, baseline_rtt_ms,
load_rtt_delta_us, last_zone, ul_suppressions_completed_window_count,
ul_suppressions_completed_window_by_cause, ul_suppressions_lifetime_by_cause.
HEALTH_URL is required via env var (no hardcoded IPs per CLAUDE.md public-safe
rule). load_rtt_delta_us computed as floor((load_rtt_ms - baseline_rtt_ms) * 1000)
with null-guard for early-startup samples.

Adds tests/test_phase_203_capture_projection.py — OBSV-05 / OBSV-07
capture-side contract test. Extracts the jq projection from the script body
and runs it against a synthesized /health payload, asserts each new key
plus null-handling and negative-delta edges.

No src/wanctl/ change (SAFE-07).
</commit_message>

<rollback>
Single-commit revert. Both files are new — the rollback simply removes them. No production behavior or schema consumers exist yet (the aggregator in plan 203-02 is the first consumer).
</rollback>

<output>
After completion, create `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-01-SUMMARY.md` documenting:
- Final `scripts/soak-capture.sh` content (or a diff vs the v1.42 reference) for plan 203-02 / 203-03 to reference.
- Test output: number of test cases passed, total runtime.
- Confirmed `git diff b72b463 -- src/wanctl/` empty at plan close.
- Any deviations from the locked projection (none expected).
</output>
</content>
</invoke>