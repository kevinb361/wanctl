# Phase 200: Per-Direction RTT Bloat Thresholds — Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Phase scope:** Code + YAML + canary gate + soak validation

<domain>
## Phase Boundary

Add optional `continuous_monitoring.upload.target_bloat_ms` and `continuous_monitoring.upload.warn_bloat_ms` keys so the legacy 3-state UL distress classifier can use thresholds independent of the DL 4-state thresholds. Behavior is byte-identical when the new keys are absent (preserves all non-Spectrum deployments). On Spectrum, adopt the new keys at 42/105 ms and lower the upload ceiling 28 → 18 Mbps (latency-first gaming-server soak), with operator evidence in three `.planning/spectrum-*-2026-04-29.md` notes. Close the validator silent-ignore gap that allowed prod `/etc/wanctl/spectrum.yaml` to carry 4 unrecognized keys for 3 days. Ship a 10–15 min saturated UL canary as the deploy gate; 24h soak as regression watchdog.

The diff is **already drafted** on the working tree (7 files, +125/-6) but contains a real bug Codex pre-review caught: `_upload_thresholds_explicit` is value-derived; must become per-key presence-based to handle the case where an operator coincidentally sets UL thresholds equal to DL globals.
</domain>

<decisions>
## Implementation Decisions

### D-01: Threshold-key naming and YAML location
New keys live under `continuous_monitoring.upload.{target_bloat_ms,warn_bloat_ms}`, not at config root. **Why:** matches existing upload-namespace pattern (`factor_down`, `factor_down_yellow`, `step_up_mbps`). **How to apply:** all schema entries, validator paths, and config attribute names use the `upload.` prefix; `_load_upload_config` reads them via `ul.get(...)`.

### D-02: Backwards-compat invariant
Absent keys → `upload_target_bloat_ms = config.target_bloat_ms`, `upload_warn_bloat_ms = config.warn_bloat_ms`. All non-Spectrum deployments remain byte-identical. **Why:** SAFE-05-style invariant for non-target deployments. **How to apply:** controller `__init__` resolves via `getattr(config, "upload_target_bloat_ms", config.target_bloat_ms)` so older mock fixtures continue to work pre-conftest update.

### D-03: Live-tuning gate (Codex bug fix — REQUIRED)
**The flag must be per-key presence-based, not value-derived.** Track `_upload_target_bloat_ms_explicit = "target_bloat_ms" in ul` and `_upload_warn_bloat_ms_explicit = "warn_bloat_ms" in ul` at config-load time. In `_apply_threshold_param`, gate `target_delta` and `warn_delta` writes independently on each flag. **Why:** Codex pre-review caught that the original value-derived flag (`target_delta != config.target_bloat_ms or warn_delta != config.warn_bloat_ms`) collapses two failure modes — operator coincidentally sets UL thresholds equal to DL globals, OR operator sets only one of the two keys — into "no protection." The presence-based form fixes both. **How to apply:** `autorate_config.py` records the flags at `ul.get(...)` time; `wan_controller.py.__init__` reads them via `getattr`; `_apply_threshold_param` checks each flag independently.

### D-04: Validation
`target < warn` ordering enforced at config-load time with explicit `ValueError`; ranges 1–200 ms / 1–250 ms in the schema validator. **Why:** soft-fail or silent-ignore would let an operator ship an inverted threshold pair into production. The valid-range bounds catch typos that would otherwise pass schema. **How to apply:** add to `Config._upload_thresholds_resolved` block in `autorate_config.py`.

### D-05: Spectrum YAML adoption
`ceiling_mbps` 28 → 18, `factor_down_yellow` 0.98 (was default 0.94), `target_bloat_ms` 42, `warn_bloat_ms` 105. **Why:** evidence in `.planning/spectrum-upload-ceiling-sweep-2026-04-29.md`, `spectrum-lower-ceiling-sweep-2026-04-29.md`, and `spectrum-inline-native-18-upload-test-2026-04-29.md`. The third note is the source for the code change — it shows that even at 18 Mbit ceiling, native UL controller behavior collapses to floor under saturated upload because UL shares DL global thresholds (15/45 ms). **How to apply:** edit `configs/spectrum.yaml` upload section.

### D-06: Out of scope (locked)
- No DL behavior change. No new state. No new health field. No new metric.
- DL 4-state path unchanged; v1.40 Phase 195/197 arbitration logic untouched.
- No `initialize_cake` refactor (C901 noqa stays per v1.40 cleanup decision).
- No coverage push above 90% (separate cleanup if needed; v1.41 tests will likely cross naturally).
- No ATT canary (VALN-05b inherited deferral).

**Why:** SAFE-05-equivalent invariant. v1.41 is UL-only. **How to apply:** plan tasks must not touch DL paths, `/health` shape, or arbitration logic.

### D-07: Production validation — saturation canary as primary gate
**The 10–15 min saturated `iperf3 -P4` UL loop at 18 Mbit is the deploy gate. The 24h soak runs after as a regression watchdog, not as the verdict.** **Why:** Codex pre-review pushback — the third operator evidence note's reproduced failure was a 30s saturated burst with floor cycling, not a steady-state pattern. A 24h soak doesn't reproduce the failure mode the diff fixes; it captures the steady-state symptom. The saturated burst is the right reproduction. **How to apply:** Phase 200 plan defines the canary as a hard gate before deploy; soak runs in parallel with operator monitoring.

### D-08: Validator must reject (or audibly warn on) unknown `continuous_monitoring.*` keys
**Closes the silent-ignore gap that v1.40 surfaced.** Production `/etc/wanctl/spectrum.yaml` carried 4 unrecognized keys (`factor_down_yellow: 0.98`, `target_bloat_ms: 42`, `warn_bloat_ms: 105`, `ceiling_mbps: 18`) for 3 days without a single warning. The validator's silent-ignore behavior allowed config-leads-code drift. **Why:** without this, the same scenario recurs — operator ships YAML, controller silently ignores, prod runs in a half-shipped state. **How to apply:** investigate current `check_config_validators.py` behavior; emit `WARNING` log on every startup for any key not in `KNOWN_AUTORATE_PATHS` (or its hierarchical equivalent under `continuous_monitoring.*`). Hard-reject is also acceptable but more disruptive.

### D-09: SAFE-05 expected count update (D-13 in earlier numbering)
`tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` currently pins `warn_bloat: 4` and `target_bloat: 4` in `wan_controller.py`. The Phase 200 diff bumps each to 6. **Why:** SAFE-05 invariant was v1.40-scoped. v1.41 explicitly introduces per-direction thresholds; the test's expected counts must update to reflect the new structural reality. **How to apply:** in the same commit that lands the per-direction wiring, update the test's expected dict to `warn_bloat: 6, target_bloat: 6`. Document that this is intentional in the commit message.

### D-10: Pre-deploy canary protocol with predefined rollback
**Rollback is predefined: revert `/opt/wanctl` binary to v1.40 if UL collapses to floor in any cycle of the canary.** The YAML stays in place — it'll silently no-op like it does now until the binary is re-deployed. **Why:** safe rollback path matters because we're shipping a control-path change. The YAML-vs-binary asymmetry actually helps here — binary rollback is the recovery mechanism. **How to apply:** Phase 200 plan documents the rollback decision tree explicitly; plan execution captures pre-canary binary path for fast revert.

### D-11: Version bump 1.41.0
Bump `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile` to 1.41.0. **Why:** milestone-version-and-tag coherence. v1.40 is at 1.39.0 (last shipped tag), so the bump aligns version-to-milestone for v1.41. **How to apply:** sed/edit all three files in the same commit as the CHANGELOG entry.

### D-12: CHANGELOG and migration note
`CHANGELOG.md` and `docs/CONFIGURATION.md` document the new optional keys plus restart-required note. **Why:** SIGUSR1 reload at `wan_controller.py:1894-1899` only handles dwell/deadband, not these threshold keys. Operators changing UL thresholds need to know they require a service restart, not just a SIGUSR1. **How to apply:** add CHANGELOG entry under v1.41.0 unreleased section; add a "Migration note" callout to `docs/CONFIGURATION.md` near the existing UL config documentation.

### D-13: Tests required (4 + 1 SAFE-05 update)
1. `tests/test_autorate_config.py::TestLoadUploadThresholdConfig::test_upload_thresholds_default_to_global_thresholds` (already in working-tree diff)
2. `tests/test_autorate_config.py::TestLoadUploadThresholdConfig::test_upload_thresholds_can_override_global_thresholds` (already in working-tree diff)
3. `tests/test_autorate_config.py::TestLoadUploadThresholdConfig::test_upload_thresholds_must_be_ordered` (already in working-tree diff)
4. `tests/test_wan_controller.py::test_upload_thresholds_use_upload_specific_config` (already in working-tree diff)
5. **NEW (D-03 fix):** `tests/test_wan_controller.py::test_upload_thresholds_explicit_when_value_equal_to_global` — verifies the per-key presence flag is True when operator sets UL key explicitly to a value that happens to equal the DL global
6. **NEW (D-03 fix):** `tests/test_wan_controller.py::test_upload_thresholds_explicit_per_key_independence` — verifies setting only `target_bloat_ms` in YAML protects `target_delta` from live-tuning writes while leaving `warn_delta` open to live tuning
7. **NEW (D-08):** `tests/test_autorate_config.py::test_unknown_continuous_monitoring_key_warns` — exercises the unknown-key path, asserts WARNING log emission
8. **UPDATED (D-09):** `tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged` — bump expected counts `warn_bloat: 4 → 6`, `target_bloat: 4 → 6`. Note in commit that v1.41 intentionally introduces per-direction thresholds, superseding the v1.40 SAFE-05 pin.

### Claude's Discretion

- Exact log message text for D-08 unknown-key warning — pick wording consistent with existing config-validator log emissions.
- Whether to also update `docs/RUNBOOK.md` with operator guidance on detecting YAML-vs-binary mismatch (might be a useful sidecar to D-12 but not strictly required).
- Order of tasks within Phase 200 plan — recommend: D-03 bug fix first → D-09 SAFE-05 update → D-08 validator → D-11/D-12 version + CHANGELOG → D-13 tests → canary script → 24h soak harness. Each lands as an atomic commit.
</decisions>

<canonical_references>
## Canonical References

### Operator evidence (read first; the third note is the source for the code change)
- `.planning/spectrum-upload-ceiling-sweep-2026-04-29.md` (morning sweep ruled out raising ceiling 28→36 — unacceptable loaded-latency tails)
- `.planning/spectrum-lower-ceiling-sweep-2026-04-29.md` (corrected stopped-controller method showed 28 had 18% ping loss; picked 18 Mbit latency-first; YAML edit shipped to prod 2026-04-29T14:17:49)
- `.planning/spectrum-inline-native-18-upload-test-2026-04-29.md` (revealed UL controller-side oscillation at 18 Mbit; recommended "upload-specific higher target/warn thresholds if supported" — this is the source for the code change)

### Locked invariants from prior phases
- v1.39 Phase 191/192: control-path timing untouched
- v1.40 Phase 193–197: DL queue-primary arbitration logic untouched
- v1.40 Phase 199: OBS-02 absent-row semantics — no `/health` schema change
- v1.40 cleanup commits 58d2255 (lint+whitespace) and b4ce583 (mypy) — preserve

### Source files that change
- `configs/spectrum.yaml` (+5/-1) — UL section
- `src/wanctl/autorate_config.py` (+27 + D-03 fix lines) — schema entries + per-key presence flags
- `src/wanctl/check_config_validators.py` (+2 + D-08 logic) — KNOWN_AUTORATE_PATHS additions + unknown-key warning
- `src/wanctl/wan_controller.py` (+10/-4 + D-03 fix lines) — per-direction threshold wiring + per-key flag gates
- `tests/conftest.py` (+2) — mock fixture extension
- `tests/test_autorate_config.py` (+54 + D-13 test #7) — config tests
- `tests/test_wan_controller.py` (+25 + D-13 tests #5, #6) — controller tests
- `tests/test_phase_195_replay.py` (D-13 #8) — SAFE-05 expected count update
- `pyproject.toml`, `src/wanctl/__init__.py`, `docker/Dockerfile` (D-11) — version bump
- `CHANGELOG.md`, `docs/CONFIGURATION.md` (D-12) — docs

### Production state at phase open (2026-05-03)
- `cake-shaper:/etc/wanctl/spectrum.yaml` already carries the 4 new UL keys (operator wrote them on 2026-04-29)
- `cake-shaper:/opt/wanctl/src/wanctl/*.py` does NOT have the matching code (Python is OLD)
- `wanctl@spectrum.service` is `active` — no startup error, no "unknown key" warning logged in 3 days (the silent-ignore gap)
- Live `/health` UL behavior (last 60 min before milestone open): 5 → 15 → 31 UL hysteresis suppressions per 60s with `DL: 0` — UL-only oscillation storm, exact failure mode the third evidence note documented
</canonical_references>

<existing_code>
## Existing Code Insights

### Reusable assets
- `_apply_threshold_param` already discriminates DL fields (`green_threshold`, `soft_red_threshold`) from legacy 3-state fields (`target_delta`, `warn_delta`). The diff exploits this existing split rather than introducing a new layer.
- `continuous_monitoring.upload.*` keys are already optional with global fallbacks (`factor_down_yellow`). The new keys follow the same shape.
- `KNOWN_AUTORATE_PATHS` set in `check_config_validators.py` is the registry that closes the unknown-key gap (D-08 extends its enforcement, not its membership).

### Established patterns
- Config schema entries use `{path, type, required, min, max}` form. New entries follow this.
- Mock fixture `mock_autorate_config` at `tests/conftest.py:64-180` is the canonical superset; new attributes go there.
- Validation errors raise `ValueError` with descriptive messages (e.g., "upload threshold ordering invalid").

### Integration points
- `WANController.__init__` resolves `config.upload_target_bloat_ms` via `getattr()` so older mock fixtures continue to work pre-conftest update — important for backwards-compat during phased rollout.
- The deployed `/opt/wanctl` Python's `Config.__init__` will need to accept the YAML keys on first restart; the validator must not reject them (only warn) until SAFE-06's behavior is decided.

### Known gotchas
- The auto-format post-edit hook converts CRLF → LF on edited regions but leaves the rest of mixed-ending files alone. Phase 200 may surface CRLF lines in source files that get partially LF-converted; treat the same way v1.40 did (commit lint cleanup separately if needed).
- `git diff --check` only catches CRLF on diff lines, not file-wide. Run `grep -lP '\r' src/wanctl/<edited-file>.py` if codex stop-hook fires on a file you edited.
</existing_code>

<deferred>
## Deferred Ideas

- **DOCSIS-aware UL congestion mode** (more aggressive recovery once CAKE backlog is bounded) — flagged in 2026-04-29 evening note; not in v1.41 scope. Future milestone material if Phase 200 + soak doesn't fully resolve the UL pattern.
- **`step_up_mbps` 5 → 3 A/B at Spectrum's new 18 Mbit ceiling** — flagged in 2026-04-29 morning note as an alternative tuning if "lower loaded-latency under saturation" stays a goal after Phase 200. Deferred until per-direction thresholds soak validates.
- **Per-direction `/health` telemetry** (UL state vs DL state under separate keys) — would aid operator debugging but is observability-only and out of scope for v1.41. Possible v1.42 deliverable.
- **CRLF normalization across all v1.40-and-earlier source files** — pre-existing tech debt, ~100 files. Not v1.41's job.
- **Coverage push >90%** — pre-existing v1.40 debt at 89.64%; v1.41 tests will likely cross naturally. Separate cleanup phase if not.
- **ATT cake-primary canary (VALN-05b)** — inherited deferral from v1.40. Still gated on v1.39 Phase 191 closure. No action in v1.41.

### Reviewed Todos (folded)
- `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — kept in pending/, tied to VALN-05b; reviewed but does NOT fold into Phase 200.
</deferred>
