---
id: 203-03
phase: 203
plan: 03
type: execute
wave: 3
depends_on:
  - 203-01
  - 203-02
files_modified:
  - docs/SOAK_HARNESS.md
  - CHANGELOG.md
  - scripts/check-safe07-source-diff.sh
autonomous: true
production_canary: false
created: 2026-05-06
requirements:
  - OBSV-08
  - SAFE-07
must_haves:
  truths:
    - "docs/SOAK_HARNESS.md exists and documents: (1) purpose of the soak harness, (2) the three scripts (soak-capture.sh, soak_summary_aggregate.py, soak-monitor.sh — last is cross-reference only), (3) the full per-row NDJSON schema including the seven Phase 203 additions, (4) the soak-summary.json schema including diagnostic_distribution.load_rtt_delta_us and load_rtt_delta_us_by_zone_cause, (5) the histogram bucket interpretation and CLI override flags, (6) the dual-attribution cause-tag rule, (7) the zone-axis-upload-only limitation, (8) the no-control-path-change invariant (harness-only)."
    - "CHANGELOG.md v1.43-dev section is extended with the Phase 203 additions: scripts/soak-capture.sh promotion, scripts/soak_summary_aggregate.py promotion, NDJSON schema additions (seven keys), soak-summary.json schema additions (load_rtt_delta_us block + matrix), docs/SOAK_HARNESS.md, and the harness-only invariant note."
    - "scripts/check-safe07-source-diff.sh exists and exits non-zero if `git diff <phase-202-close>..HEAD -- src/wanctl/` produces any output. Phase 202 close ref is the commit hash recorded in the script (b72b463 at planning time, but the script accepts a CLI arg or env override)."
    - "OBSV-08 doc-presence grep verification passes: `grep -E 'load_rtt_delta_us|load_rtt_delta_us_by_zone_cause|harness-only' docs/SOAK_HARNESS.md CHANGELOG.md` returns ≥1 hit per file per pattern."
    - "SAFE-07 mechanical verification at phase close: `git diff <phase-202-close-sha>..HEAD -- src/wanctl/` empty. SAFE-05 pin test (`tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged`) green and unchanged. No Phase 203 dict added to the pin block."
    - "No src/wanctl/** files modified by this plan."
  artifacts:
    - path: docs/SOAK_HARNESS.md
      provides: "Operator-facing soak harness documentation. Full NDJSON + soak-summary.json schema. Cause-attribution rule. Zone-axis limitation. Harness-only invariant."
      contains: "load_rtt_delta_us"
    - path: CHANGELOG.md
      provides: "v1.43-dev section extended with Phase 203 deliverables under Added/Notes."
      contains: "soak-capture.sh"
    - path: scripts/check-safe07-source-diff.sh
      provides: "Mechanical SAFE-07 verification script. Configurable phase-202 close ref. Used at phase close and re-runnable on demand."
      contains: "git diff"
  key_links:
    - from: "docs/SOAK_HARNESS.md"
      to: "scripts/soak-capture.sh + scripts/soak_summary_aggregate.py"
      via: "script-name cross-references with usage examples"
      pattern: "soak-capture.sh"
    - from: "scripts/check-safe07-source-diff.sh"
      to: "Phase 202 close commit (b72b463)"
      via: "default ref encoded in script; CLI override via positional arg or PHASE_202_CLOSE env var"
      pattern: "b72b463"
    - from: "CHANGELOG.md v1.43-dev section"
      to: "the Phase 202 entry"
      via: "extension of the existing v1.43-dev block, not a new version block"
      pattern: "v1.43-dev"
---

<objective>
Land the documentation and SAFE-07 closure deliverables for Phase 203. Create `docs/SOAK_HARNESS.md` (no canonical soak-harness operator doc exists today). Extend the existing `CHANGELOG.md` v1.43-dev section with the Phase 203 additions. Land an automated SAFE-07 source-diff verification script (`scripts/check-safe07-source-diff.sh`) so the cross-cutting invariant ("no `src/wanctl/` source diff between Phase 201 close and v1.43 close") is mechanically re-runnable on demand and at every future phase close.

Purpose: Phase 203 closes ONLY when (1) the new fields and schema are documented for operators, (2) the CHANGELOG records the additive contract, and (3) the SAFE-07 invariant is verified. OBSV-08 covers (1) and (2); SAFE-07 covers (3). This plan is the docs+verification half of the phase that plans 203-01 and 203-02 set up the code for.

The doc-presence verification (`grep` for `load_rtt_delta_us` etc.) is per 203-VALIDATION.md "manual-only" — it lives in the manual-only section deliberately because doc-presence tests churn on legitimate edits. Plan 203-03's automated checks cover (a) file existence, (b) the SAFE-07 source-diff, (c) the SAFE-05 pin test. The grep verification is documented and re-runnable but not in CI.

Output: `docs/SOAK_HARNESS.md` (~250-400 lines of markdown), extended `CHANGELOG.md` v1.43-dev section (~20-30 new lines), and `scripts/check-safe07-source-diff.sh` (~30 lines of bash). Plus phase-close artifact stubs (`203-VERIFICATION.md` is mentioned as a downstream deliverable but is owned by the orchestrator's `/gsd-verify-work` step, NOT this plan).
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
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-01-soak-capture-script-and-projection-test-PLAN.md
@.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-02-soak-summary-aggregator-and-replay-PLAN.md
@CHANGELOG.md
@docs/CONFIGURATION.md
@CLAUDE.md

<interfaces>
<!-- Existing CHANGELOG.md v1.43-dev section (head, verified by inspection): -->
```
## v1.43-dev

### Added

- /health.wans[].upload.hysteresis and /health.wans[].download.hysteresis now expose three additive fields ...
  (Phase 202 entries — DO NOT modify; this plan EXTENDS this section)

### Changed

- None. v1.43 Phase 202 is additive-only ...

### Notes

- suppressions_per_min is a live counter ...
- backlog_recovery accounting is per-cycle ...
```

This plan APPENDS Phase 203 entries to `### Added` and `### Notes`. It does NOT create a new version block; it does NOT modify the Phase 202 entries.

<!-- Phase 202 close commit (HEAD on main at planning time): b72b463 -->
<!-- This is the git ref the SAFE-07 source-diff is computed against. -->
<!-- The exact SHA may shift if `/gsd-checker` makes pre-execute commits — the script accepts a CLI override so any drift is operator-correctable. -->

<!-- docs/CONFIGURATION.md already has a "Suppression metric semantics (v1.43)" section from Phase 202. -->
<!-- docs/SOAK_HARNESS.md does not exist. This plan creates it. -->
<!-- Cross-reference: docs/RUNBOOK.md soak section (lines 259-353) currently points at scripts/soak-monitor.sh; -->
<!-- a future cross-link from RUNBOOK.md to SOAK_HARNESS.md is OPTIONAL — out of scope here. -->
</interfaces>
</context>

<locked_decisions>
- **Doc location (gray-area #5):** `docs/SOAK_HARNESS.md`. Aligns with `docs/STEERING.md`, `docs/RUNBOOK.md`, `docs/PERFORMANCE.md` precedent. Operators look in `docs/`. NOT `scripts/soak-harness/README.md`.
- **CHANGELOG style:** extend the existing v1.43-dev block (do NOT create a new version block, do NOT mark v1.43 as released — Phase 204 closes the milestone).
- **SAFE-07 verification mechanism (gray-area #9):** `scripts/check-safe07-source-diff.sh` is automated and re-runnable. The Phase 202 close SHA is encoded as the default; CLI override allows operators to re-verify against any historical reference.
- **Public-safe content only.** Per CLAUDE.md: no IPs, hostnames, operator identities, or company names in `docs/SOAK_HARNESS.md` or `CHANGELOG.md` or the verification script. The example `HEALTH_URL` in the doc must be a generic placeholder (e.g. `http://<host>:9101/health`).
- **No `203-VERIFICATION.md` / `203-RETRO.md` in this plan.** Those are downstream phase-close artifacts produced by `/gsd-verify-work` and `/gsd-retro` orchestrators, NOT this plan. Plan 203-03 stops at docs + CHANGELOG + SAFE-07 mechanism.
- **No update to `.planning/REQUIREMENTS.md` or `.planning/ROADMAP.md` here.** Those updates happen at phase close via `/gsd-verify-work` (mark OBSV-05..08 as `[x]` in REQUIREMENTS, set Phase 203 to Complete in ROADMAP). Plan 203-03 is implementation-side only.
- **Cross-link from `docs/RUNBOOK.md` is OPTIONAL.** If the executor sees a clean place to add `See docs/SOAK_HARNESS.md` near the soak-monitor.sh section, do it. If the section is structured awkwardly for a one-line cross-link, defer to a future docs PR. NOT a gating criterion.
</locked_decisions>

<tasks>

<task type="auto">
  <name>Task 1: Create docs/SOAK_HARNESS.md with all eight required content elements</name>
  <files>docs/SOAK_HARNESS.md</files>
  <action>
    Create `docs/SOAK_HARNESS.md`. Structure the document with the eight required content elements (203-RESEARCH.md §Documentation surface). Match the heading hierarchy and prose style of `docs/STEERING.md` / `docs/PERFORMANCE.md` (reference those for tone before writing).

    Required content (each section MUST appear; exact heading wording can flex to match project conventions):

    ## 1. Purpose
    Brief statement: what the soak harness does (24h capture, aggregate, verdict). Cross-references Phase 201's secondary-gate watchdog as the use case. 2-3 paragraphs.

    ## 2. Files
    Three scripts:
    - `scripts/soak-capture.sh` — uploaded to deploy target, runs as tmux/long-running session, writes NDJSON. Created in Phase 203 (this plan's predecessor 203-01). Public-safe: requires `HEALTH_URL` via env var.
    - `scripts/soak_summary_aggregate.py` — reads NDJSON, writes `soak-summary.json`. Created in Phase 203 (predecessor 203-02). Stdlib-only Python.
    - `scripts/soak-monitor.sh` — live operator dashboard. Existing; cross-reference only. NOT in Phase 203 scope.

    ## 3. NDJSON per-row schema
    Full table of all 23 keys (16 v1.42 + 7 Phase 203). For each: name, type, source path in `/health`, semantics. The seven new keys MUST be called out explicitly:
    - `load_rtt_ms` (float, ms): `wans[0].load_rtt_ms` raw value.
    - `baseline_rtt_ms` (float, ms): `wans[0].baseline_rtt_ms` raw value.
    - `load_rtt_delta_us` (int microseconds, may be null): `floor((load_rtt_ms - baseline_rtt_ms) * 1000)`. Null when either source is null.
    - `last_zone` (string): one of `GREEN`, `YELLOW`, `SOFT_RED`, `RED`. Upload-side only.
    - `ul_suppressions_completed_window_count` (int): mirror of Phase 202's `/health.wans[].upload.hysteresis.suppressions_completed_window_count`.
    - `ul_suppressions_completed_window_by_cause` (dict): same, broken down by cause.
    - `ul_suppressions_lifetime_by_cause` (dict): monotonic per-cause lifetime counters since process start.

    ## 4. soak-summary.json output schema
    Full output shape including:
    - `diagnostic_distribution.load_rtt_delta_us` block: `p50`, `p95`, `p99`, `max`, `histogram` (with `buckets_us` + `counts`), `samples_total`, `samples_filtered_null`.
    - `load_rtt_delta_us_by_zone_cause` matrix: 4 zones × 3 causes = 12 cells, each with `p50/p95/p99/max/count/histogram`.
    - `phase_203_metadata`: `attribution_policy`, `buckets_us`, `zone_axis`.
    - Preserved v1.42 fields (rtt_integral_ms_s, max_delay_delta_us, red_streak, headroom_exhausted_samples, total_samples).

    ## 5. Histogram bucket interpretation
    Default bucket array (microseconds):
    ```
    [0, 1000, 3000, 6000, 10000, 15000, 20000, 30000, 45000, 60000, 100000, 250000]
    ```
    Aligned with Spectrum v1.42 thresholds (`target_bloat_ms=15` → 15000 µs; `warn_bloat_ms=30` → 30000 µs; `hard_red_bloat_ms=60` → 60000 µs).

    Bucket [i] contains values in `[buckets[i], buckets[i+1])`. The final cell of `counts` is the OVERFLOW bucket (values ≥ 250000 µs).

    CLI overrides:
    - `--target-delta-us <int>` (default 15000)
    - `--warn-delta-us <int>` (default 30000)
    - `--hard-red-us <int>` (default 60000)

    The boundary array is written into the `buckets_us` field of every histogram object so consumers don't need the source config to interpret the data.

    ## 6. Cause-tag attribution rule
    **Per-sample cause = `ul_suppressions_lifetime_by_cause` delta from previous sample.** When a sample's lifetime counter for cause C is greater than the previous sample's, that sample is attributed to C.

    **Dual-attribution.** If a single 50ms cycle increments BOTH `dwell_hold` AND `backlog_recovery` lifetime counters, the sample contributes to both `(zone, dwell_hold)` AND `(zone, backlog_recovery)` cells. Counts may exceed `total_samples`. The summary's `phase_203_metadata.attribution_policy` field is `"dual"`.

    **First-row exclusion.** The very first row of an NDJSON has no previous sample, so cause attribution is impossible. The aggregator includes the first row in the top-level `diagnostic_distribution.load_rtt_delta_us` histogram but excludes it from the `_by_zone_cause` matrix.

    **Causes:**
    - `dwell_hold` — `_apply_dwell_logic` GREEN→YELLOW transition suppression while dwell timer active.
    - `backlog_recovery` — green-streak suppression while backlog condition holds (DETECT-02). Per-cycle: fires every 50ms while the condition holds (~1,200/min per cause at 20Hz peak).
    - `other` — reserved fallback bucket; no current callsite fires it.

    ## 7. Zone axis is upload-only
    The `last_zone` field projected by `scripts/soak-capture.sh` reads from `/health.wans[0].upload.hysteresis.last_zone`. **Phase 203's matrix is therefore upload-state.** This is intentional — `effective_ul_load_rtt` (the seed's named metric) is upload-side, and the v1.43 milestone goal is Spectrum upload recalibration.

    Download is 3-state (GREEN/YELLOW/RED, no SOFT_RED) and is not aggregated by Phase 203. If a future seed needs the same matrix for download, it adds a `dl_load_rtt_delta_us_by_zone_cause` field with a 3-state matrix.

    ## 8. No-control-path-change invariant (harness-only)
    Phase 203 added **zero** lines to `src/wanctl/`. Both deliverables (`scripts/soak-capture.sh`, `scripts/soak_summary_aggregate.py`) are harness-only — they read existing `/health` fields exposed by Phase 202.

    The cross-cutting SAFE-07 invariant is verified mechanically by:
    ```
    git diff <phase-202-close-sha>..HEAD -- src/wanctl/
    ```
    which MUST return empty at every Phase 203 commit and at phase close. The reusable check is at `scripts/check-safe07-source-diff.sh`.

    Production canary: NOT required for Phase 203 deliverables. The harness layer is local-repo work; production binary changes happen only in Phase 204 (CALIB).

    ## Limitations
    - **Asymmetry-gate disabled deployments only.** `load_rtt_delta_us` uses raw `load_rtt_ms`, NOT gate-attenuated. On Spectrum (gate disabled — verified at `configs/spectrum.yaml` and `autorate_config.py:1184` default `enabled=False`), this is exact. On future deployments with the gate enabled, gate-active windows would over-state the delta. Future seed if needed.
    - **Reference-soak fixture predates Phase 203 fields.** The v1.42 reference NDJSON at `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson` does not contain `load_rtt_ms`, `baseline_rtt_ms`, or the cause-tag fields (it predates both Phase 202 and 203). The aggregator's v1.42 regression test asserts only that the unaffected `diagnostic_distribution` math is preserved.
    - **2-decimal RTT precision.** `/health` rounds `load_rtt_ms` and `baseline_rtt_ms` to 2 decimal places (10µs precision). Acceptable for histogram-at-ms-boundary aggregation.

    ## Usage example
    ```bash
    # On the deploy target:
    HEALTH_URL=http://<host>:9101/health \
      bash scripts/soak-capture.sh "$(date -u +%Y%m%dT%H%M%SZ)"

    # After the soak completes, on the dev VM:
    rsync -av <host>:/var/tmp/wanctl-soak-<SOAK_TS>/soak-capture.ndjson ./

    .venv/bin/python scripts/soak_summary_aggregate.py \
        ./soak-capture.ndjson \
        -o ./soak-summary.json
    ```

    Public-safe verification before commit: `grep -nE '(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)|cake-shaper' docs/SOAK_HARNESS.md` MUST return zero matches. The example uses `<host>` placeholder, NOT a real IP/hostname.

    Doc-presence verification (the OBSV-08 manual-only check from 203-VALIDATION.md):
    ```bash
    grep -E "load_rtt_delta_us|load_rtt_delta_us_by_zone_cause|harness-only" docs/SOAK_HARNESS.md
    ```
    must return ≥1 hit per pattern. (The phrase "harness-only" appears in section 8.)
  </action>
  <verify>
    <automated>test -f docs/SOAK_HARNESS.md && grep -q "load_rtt_delta_us" docs/SOAK_HARNESS.md && grep -q "load_rtt_delta_us_by_zone_cause" docs/SOAK_HARNESS.md && grep -q "harness-only" docs/SOAK_HARNESS.md && grep -q "dual-attribution\|Dual-attribution" docs/SOAK_HARNESS.md && grep -q "buckets_us" docs/SOAK_HARNESS.md && grep -q "soak-capture.sh" docs/SOAK_HARNESS.md && grep -q "soak_summary_aggregate.py" docs/SOAK_HARNESS.md && grep -q "upload-only\|upload-state\|upload only" docs/SOAK_HARNESS.md && ! grep -nE '(10\.[0-9]|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)' docs/SOAK_HARNESS.md</automated>
  </verify>
  <done>
    docs/SOAK_HARNESS.md exists with all eight content sections; OBSV-08 grep patterns match; no IP literals.
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend CHANGELOG.md v1.43-dev section with Phase 203 deliverables</name>
  <files>CHANGELOG.md</files>
  <action>
    Read the current CHANGELOG.md head to confirm the existing v1.43-dev section structure (Added / Changed / Notes), then APPEND Phase 203 entries to the existing block. Do NOT create a new version block. Do NOT modify the Phase 202 entries.

    Suggested additions to `### Added` (under v1.43-dev):

    - **Soak harness:** `scripts/soak-capture.sh` and `scripts/soak_summary_aggregate.py` promoted from inline-jq evidence into versioned, tested scripts. The capture script requires `HEALTH_URL` via environment variable (no hardcoded host, public-safe per CLAUDE.md). The aggregator is stdlib-only Python with full unit test coverage (`tests/test_phase_203_capture_projection.py`, `tests/test_phase_203_replay.py`). (OBSV-05, OBSV-06, OBSV-07)
    - **NDJSON capture schema:** seven new per-row fields — `load_rtt_ms`, `baseline_rtt_ms`, `load_rtt_delta_us` (integer microseconds; null when either source is null), `last_zone`, `ul_suppressions_completed_window_count`, `ul_suppressions_completed_window_by_cause`, `ul_suppressions_lifetime_by_cause`. (OBSV-05)
    - **`soak-summary.json` schema:** new `diagnostic_distribution.load_rtt_delta_us` block (p50/p95/p99/max + histogram with explicit `buckets_us`) plus the new top-level `load_rtt_delta_us_by_zone_cause` matrix (4 upload zones × 3 causes). Empty cells emit fully-zeroed histogram objects (mirrors Phase 202 "empty cause = 0, not omitted" pattern). (OBSV-06)
    - **Documentation:** `docs/SOAK_HARNESS.md` covering NDJSON schema, soak-summary.json schema, histogram bucket interpretation, cause-attribution rule, zone-axis upload-only limitation, and the harness-only invariant. (OBSV-08)
    - **SAFE-07 verification:** `scripts/check-safe07-source-diff.sh` automates the cross-cutting "no control-path source diff" check between Phase 201 close and any later commit. (SAFE-07)

    Suggested additions to `### Notes`:

    - **Cause-attribution policy is dual.** A row whose `ul_suppressions_lifetime_by_cause` lifetime counter incremented for multiple causes within a single 50ms cycle contributes to every affected `(zone, cause)` cell. Counts may exceed `total_samples`; documented in `phase_203_metadata.attribution_policy`. See `docs/SOAK_HARNESS.md` §6.
    - **Harness-only invariant.** Phase 203 added zero lines to `src/wanctl/`. The cross-cutting SAFE-07 invariant is verified at phase close by `scripts/check-safe07-source-diff.sh` and by the unchanged SAFE-05 pin block in `tests/test_phase_195_replay.py`.
    - **Spectrum-only deltas.** `load_rtt_delta_us` uses raw `load_rtt_ms` (not asymmetry-gate-attenuated). On Spectrum (gate disabled by default in `configs/spectrum.yaml`) the values are exact. On future gate-enabled deployments the delta would over-state during gate-active windows. v1.43's milestone goal is Spectrum recalibration; portability beyond Spectrum is a future seed.

    Match the existing CHANGELOG bullet style and indentation exactly. The Phase 202 entries use plain hyphenated bullets with bold labels (`- **Soak harness:**`); follow that convention.

    Public-safe verification: `grep -nE '(10\.[0-9]|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)|cake-shaper' CHANGELOG.md` returns no new matches relative to pre-edit. (The pre-existing `1.42.1` section may contain version numbers like `1.42.1` that match the IP regex — be aware and use `grep -F '10.10.'` or similar tighter check if false positives appear.)

    OBSV-08 doc-presence check after edit:
    ```
    grep -E "load_rtt_delta_us|load_rtt_delta_us_by_zone_cause|harness-only" CHANGELOG.md
    ```
    MUST return ≥1 hit per pattern.
  </action>
  <verify>
    <automated>grep -q "load_rtt_delta_us" CHANGELOG.md && grep -q "load_rtt_delta_us_by_zone_cause" CHANGELOG.md && grep -q "harness-only" CHANGELOG.md && grep -q "soak-capture.sh" CHANGELOG.md && grep -q "soak_summary_aggregate.py" CHANGELOG.md && grep -q "OBSV-05\|OBSV-06\|OBSV-07\|OBSV-08\|SAFE-07" CHANGELOG.md && head -10 CHANGELOG.md | grep -q "v1.43-dev"</automated>
  </verify>
  <done>
    CHANGELOG.md v1.43-dev section extended with Phase 203 entries under Added and Notes. All five OBSV-08 grep patterns match. No new RFC1918 IPs introduced.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create scripts/check-safe07-source-diff.sh — the automated SAFE-07 verification</name>
  <files>scripts/check-safe07-source-diff.sh</files>
  <action>
    Create `scripts/check-safe07-source-diff.sh`. The script encodes the Phase 202 close SHA as the default ref and accepts a CLI override or env var. It runs `git diff <ref>..HEAD -- src/wanctl/` and exits non-zero with a clear error message if any output is produced.

    Concrete file contents:

    ```bash
    #!/usr/bin/env bash
    # SAFE-07 cross-cutting invariant verification.
    #
    # Asserts that no control-path source diff exists between the Phase 201
    # close (== Phase 202 close, since Phase 202 was additive-only) and HEAD.
    #
    # Usage:
    #   bash scripts/check-safe07-source-diff.sh                  # uses default ref
    #   bash scripts/check-safe07-source-diff.sh <git-ref>        # override ref
    #   PHASE_202_CLOSE=<sha> bash scripts/check-safe07-source-diff.sh
    #
    # Exit:
    #   0 — clean (no src/wanctl/ diff vs ref)
    #   1 — SAFE-07 VIOLATION: src/wanctl/ has changed; investigate immediately
    #   2 — usage / git error (ref not found)

    set -euo pipefail

    # Default ref: Phase 202 close commit on main.
    # Recorded 2026-05-06 at planning time. Update if a later phase re-baselines.
    DEFAULT_PHASE_202_CLOSE="b72b463"

    REF="${1:-${PHASE_202_CLOSE:-$DEFAULT_PHASE_202_CLOSE}}"

    if ! git rev-parse --verify "${REF}^{commit}" >/dev/null 2>&1; then
      echo "ERROR: ref '${REF}' not found in this repository." >&2
      echo "       Provide a valid Phase 202 close commit SHA via positional arg" >&2
      echo "       or PHASE_202_CLOSE env var." >&2
      exit 2
    fi

    DIFF_OUTPUT=$(git diff "${REF}..HEAD" -- src/wanctl/ 2>&1 || true)

    if [ -n "${DIFF_OUTPUT}" ]; then
      echo "SAFE-07 VIOLATION: src/wanctl/ has changed since ${REF}" >&2
      echo "" >&2
      echo "Phase 203 is harness-only. ANY src/wanctl/ change indicates a" >&2
      echo "control-path edit slipped in. Investigate before phase close:" >&2
      echo "  git diff ${REF}..HEAD -- src/wanctl/" >&2
      echo "" >&2
      echo "First 20 lines of diff:" >&2
      echo "${DIFF_OUTPUT}" | head -20 >&2
      exit 1
    fi

    echo "SAFE-07 OK: no src/wanctl/ diff vs ${REF}"
    exit 0
    ```

    Then `chmod +x scripts/check-safe07-source-diff.sh`.

    Public-safe verification: `grep -nE '(10\.[0-9]|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)' scripts/check-safe07-source-diff.sh` returns zero (the script body has no IPs).

    **Verify the script works against the current repo:**
    ```
    bash scripts/check-safe07-source-diff.sh
    ```
    Expected: exits 0 with `SAFE-07 OK: no src/wanctl/ diff vs b72b463` (assuming the executor's plans 203-01 and 203-02 didn't violate SAFE-07; if they did, this is the gate that catches it).

    **Verify the script catches violations:** simulate by running against an earlier commit that DID change src/wanctl/ (Phase 202's plan 202-01 commit, e.g. `ed2edb8`):
    ```
    bash scripts/check-safe07-source-diff.sh ed2edb8 || echo "exit $?"
    ```
    Expected: exits 1 with `SAFE-07 VIOLATION` message — proves the gate is functional. (This is a sanity check, not a CI gate.)
  </action>
  <verify>
    <automated>test -x scripts/check-safe07-source-diff.sh && bash -n scripts/check-safe07-source-diff.sh && bash scripts/check-safe07-source-diff.sh && ! bash scripts/check-safe07-source-diff.sh ed2edb8 2>/dev/null</automated>
  </verify>
  <done>
    scripts/check-safe07-source-diff.sh exists, is executable, passes shell syntax check. Running with no args against the current repo exits 0 (current state is clean). Running against the Phase 202 plan-01 commit (ed2edb8) exits 1 (proving the gate fires correctly on real src/wanctl/ changes).
  </done>
</task>

<task type="auto">
  <name>Task 4: Phase-close verification — full SAFE-07 + SAFE-05 + hot-path + phase-scoped slice</name>
  <files>(none — verification only)</files>
  <action>
    Run the full Phase 203 closeout verification battery as documented in 203-VALIDATION.md §Sampling Rate "Before /gsd-verify-work".

    1. **SAFE-07 mechanical check via the new script:**
       ```
       bash scripts/check-safe07-source-diff.sh
       ```
       Expected: exits 0 with `SAFE-07 OK`. If it fails, halt — Phase 203 is not closeable until the violation is reverted.

    2. **SAFE-05 pin test (no Phase 203 dict added — this is the "Phase 203 has nothing to pin" verification):**
       ```
       .venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"
       ```
       Expected: green. The three existing dicts (`expected_counts` v1.40, `phase201_expected_counts` v1.42, `phase202_expected_counts` v1.43) all assert against current source. Phase 203 doesn't touch source → all three should pass with zero modification. **NO new `phase203_expected_counts` dict is added** — that would be the wrong precedent (it would create the false impression that Phase 203 added new symbols requiring pinning).

    3. **Hot-path regression slice:**
       ```
       .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
       ```

    4. **Phase-scoped slice (per 203-VALIDATION.md):**
       ```
       .venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q
       ```

    5. **OBSV-08 doc-presence verification (manual-only per 203-VALIDATION.md, but re-run here for the final closeout):**
       ```
       grep -E "load_rtt_delta_us|load_rtt_delta_us_by_zone_cause|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md
       ```
       Expected: each file returns ≥1 hit per pattern (≥6 total matches, possibly more).

    6. **Full suite (per 203-VALIDATION.md "Before /gsd-verify-work"):**
       ```
       .venv/bin/pytest tests/ -q
       ```
       Expected: green. Estimated runtime ~189s (per 203-VALIDATION.md).

    If any check fails, do NOT proceed to commit. Surface the failure to the operator. Phase 203 closure is gated on ALL six checks green.
  </action>
  <verify>
    <automated>bash scripts/check-safe07-source-diff.sh && .venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts" && .venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q && .venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q && grep -qE "load_rtt_delta_us" docs/SOAK_HARNESS.md && grep -qE "load_rtt_delta_us" CHANGELOG.md && grep -qE "harness-only" docs/SOAK_HARNESS.md && grep -qE "harness-only" CHANGELOG.md</automated>
  </verify>
  <done>
    All six closeout checks green. SAFE-07 verified via the new script. SAFE-05 pin test green (no Phase 203 dict added). Hot-path slice green. Phase-scoped slice green. OBSV-08 grep patterns match in both `docs/SOAK_HARNESS.md` and `CHANGELOG.md`.
  </done>
</task>

</tasks>

<safe07_compliance>
This plan touches NO files under `src/wanctl/`. The complete diff is bounded to:

- `docs/SOAK_HARNESS.md` (new)
- `CHANGELOG.md` (extension of existing v1.43-dev block)
- `scripts/check-safe07-source-diff.sh` (new)

Mechanical executor check at plan close:
```bash
bash scripts/check-safe07-source-diff.sh   # MUST exit 0
```

The verification script itself is the SAFE-07 deliverable. Plan 203-03 is the canonical place to land it because it is the docs+closeout plan; the script is a reusable artifact, not a one-shot test.
</safe07_compliance>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator-readable docs | Public-safe per CLAUDE.md: no IPs, hostnames, identities, or company names in `docs/SOAK_HARNESS.md` or `CHANGELOG.md`. |
| Verification script CLI input | Operator-supplied git ref. Trusted same as the operator's shell. |
| `git diff` invocation | Read-only against local repo. Same trust as developer workflow. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-203-03-01 | Information Disclosure | docs/SOAK_HARNESS.md content | high | mitigate | Public-safe review at Task 1 verify clause: regex grep for RFC1918 IPs returns zero. Example URLs use `<host>` placeholder. No operator identities, no company names. |
| T-203-03-02 | Information Disclosure | CHANGELOG.md additions | medium | mitigate | Same regex grep at Task 2 verify clause. Phase 203 entries reference only public-safe constructs (script names, schema fields, REQ-IDs). |
| T-203-03-03 | Repudiation / drift | Future operator misreading the new schema | medium | mitigate | Cause-attribution rule (§6) and zone-axis-upload-only limitation (§7) are LOCKED requirements in `docs/SOAK_HARNESS.md`. Doc-presence grep verifies they are present at every checkpoint. |
| T-203-03-04 | Tampering | SAFE-07 verification script bypass | medium | mitigate | The script is reusable infrastructure — re-runnable at every phase close, not just Phase 203. Operator can't accidentally bypass it because it's the explicit gate in this plan's Task 4 verify clause AND in 203-VALIDATION.md §Sampling Rate. |
| T-203-03-05 | Repudiation / drift | Phase 202 close SHA reference rot | low | mitigate | The script accepts a CLI override and reads `PHASE_202_CLOSE` env var. If `b72b463` becomes invalid (e.g. branch rebase), the operator can re-anchor to a stable tag. The script also exits 2 with a clear "ref not found" message, not silently passing. |
| T-203-03-06 | SAFE-07 invariant violation | Any `src/wanctl/` change | high | mitigate | Task 4 mechanical SAFE-07 check via the new script. The plan's diff scope is bounded to docs, CHANGELOG, and the verification script — none of which touch `src/wanctl/`. |
| T-203-03-07 | Tampering | New `phase203_expected_counts` pin block accidentally added | medium | mitigate | LOCKED decision: no Phase 203 dict added to `tests/test_phase_195_replay.py`. Phase 203 has no `src/wanctl/` symbols, so pinning is meaningless and would create the wrong precedent. Task 4 verifies the existing three dicts pass unchanged. |

No high-severity threats remain unresolved. T-203-03-01 and T-203-03-06 are both `mitigate` with explicit mechanical checks in their respective verify clauses.
</threat_model>

<verification>
1. `docs/SOAK_HARNESS.md` exists with all eight required sections (purpose, files, NDJSON schema, soak-summary schema, histogram interpretation, cause-attribution rule, zone-axis upload-only, harness-only invariant). OBSV-08 grep patterns match.
2. `CHANGELOG.md` v1.43-dev section extended with Phase 203 entries under Added + Notes; OBSV-08 grep patterns match in CHANGELOG too.
3. `scripts/check-safe07-source-diff.sh` exists, is executable, exits 0 against the current repo, exits 1 against a known-violating commit (ed2edb8).
4. SAFE-07 mechanical check passes: `git diff b72b463..HEAD -- src/wanctl/` empty.
5. SAFE-05 pin test green; no Phase 203 dict added.
6. Hot-path slice green; phase-scoped slice green; full suite green.
7. Public-safe: no RFC1918 IP literals in any of the three new files.

Test commands (project venv per CLAUDE.md):
- `bash scripts/check-safe07-source-diff.sh`
- `.venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"`
- Hot-path slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- Phase-scoped slice: `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py -q`
- Full suite: `.venv/bin/pytest tests/ -q`
- Doc-presence: `grep -E "load_rtt_delta_us|load_rtt_delta_us_by_zone_cause|harness-only" docs/SOAK_HARNESS.md CHANGELOG.md`
</verification>

<success_criteria>
1. **OBSV-08 satisfied:** `docs/SOAK_HARNESS.md` documents the new field, the matrix contract, and the harness-only invariant. CHANGELOG.md v1.43-dev section names the Phase 203 deliverables. Doc-presence grep returns ≥1 hit per pattern per file.
2. **SAFE-07 mechanically verified:** `scripts/check-safe07-source-diff.sh` exits 0 against the current repo. The script itself is reusable and re-runnable for future phases.
3. **SAFE-05 pin block unchanged:** the three existing dicts in `tests/test_phase_195_replay.py` pass; no Phase 203 dict added.
4. **No `src/wanctl/` change:** plan diff scope bounded to `docs/`, `CHANGELOG.md`, and `scripts/`.
5. **Public-safe:** no RFC1918 IPs in `docs/SOAK_HARNESS.md`, `CHANGELOG.md`, or `scripts/check-safe07-source-diff.sh`.
6. **Hot-path slice + phase-scoped slice + full suite green.**
</success_criteria>

<commit_message>
docs(203-03): add SOAK_HARNESS.md, CHANGELOG v1.43-dev extension, SAFE-07 gate

OBSV-08, SAFE-07. Adds docs/SOAK_HARNESS.md — operator-facing soak harness
documentation covering the full NDJSON per-row schema (16 v1.42 keys + 7
Phase 203 additions), the soak-summary.json output schema (load_rtt_delta_us
block + 4×3 zone × cause matrix), histogram bucket interpretation,
dual-attribution cause-tag rule, zone-axis upload-only limitation, and the
harness-only invariant.

Extends CHANGELOG.md v1.43-dev section with Phase 203 entries: scripts/
soak-capture.sh + scripts/soak_summary_aggregate.py promotions, NDJSON
schema additions, soak-summary.json schema additions, docs/SOAK_HARNESS.md,
and the harness-only invariant note.

Adds scripts/check-safe07-source-diff.sh — automated, reusable
verification of the cross-cutting "no src/wanctl/ diff between Phase 201
close and current" invariant. Default ref encoded; CLI / env override
supported. Exits 1 with clear violation message on any src/wanctl/ change.

No new SAFE-05 pin block added (Phase 203 has no src/ symbols to pin).
No src/wanctl/ change (SAFE-07).
</commit_message>

<rollback>
Single-commit revert. Three new/extended files; the rollback simply removes the new files and reverts the CHANGELOG hunk. No production behavior involved.

If `scripts/check-safe07-source-diff.sh` is in use by other workflows post-commit, the rollback breaks those workflows — but at v1.43 phase-203 close, this is the script's first commit, so no consumers exist yet.
</rollback>

<output>
After completion, create `.planning/milestones/v1.43-phases/203-target-edge-churn-instrumentation-obsv/203-03-SUMMARY.md` documenting:
- Final `docs/SOAK_HARNESS.md` line count and section list (for cross-reference from `203-VERIFICATION.md` produced later by `/gsd-verify-work`).
- The CHANGELOG.md v1.43-dev section's final Phase 203 bullet count under Added and Notes.
- The exact Phase 202 close SHA used as the SAFE-07 reference (b72b463 unless overridden).
- Output of `bash scripts/check-safe07-source-diff.sh` (the OK message).
- Output of the SAFE-05 pin test confirming the three existing dicts still pass.
- Confirmation that NO `phase203_expected_counts` dict was added to `tests/test_phase_195_replay.py`.
- Full-suite pytest result (pass count, runtime).
</output>
</content>
</invoke>