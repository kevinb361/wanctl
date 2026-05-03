---
phase: 200-per-direction-rtt-bloat-thresholds
verified: 2026-05-03T00:00:00Z
status: gaps_found
score: 3/5 must-haves verified
overrides_applied: 0
requirements:
  ARB-05: satisfied
  SAFE-06: satisfied
  VALN-06: blocked
  DOCS-03: satisfied
files_touched:
  src:
    - src/wanctl/autorate_config.py
    - src/wanctl/check_config_validators.py
    - src/wanctl/wan_controller.py
    - src/wanctl/__init__.py
  tests:
    - tests/conftest.py
    - tests/test_autorate_config.py
    - tests/test_wan_controller.py
    - tests/test_phase_195_replay.py
  scripts:
    - scripts/phase200-saturation-canary.sh
    - scripts/phase200-saturation-canary.env.example
  configs:
    - configs/spectrum.yaml
  docs:
    - CHANGELOG.md
    - docs/CONFIGURATION.md
  build:
    - pyproject.toml
    - docker/Dockerfile
deploy_state: rolled-back
canary_verdict_path: .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json
soak_verdict_path: null
gaps:
  - truth: "The 10-15 min saturated iperf3 -P4 UL canary at 18 Mbit completes without the UL controller collapsing to the 8 Mbit floor in any cycle"
    status: failed
    reason: "Production canary verdict was fail with 122 loaded-window floor hits; D-10 rollback was executed."
    artifacts:
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json"
        issue: "verdict=fail, ul_floor_hits_during_load=122, ul_floor_threshold_hit=true"
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md"
        issue: "Records FAIL decision and rollback at 2026-05-03T22:15:04Z"
    missing:
      - "Gap-closure implementation that can pass a saturated Spectrum UL canary with zero floor hits."
  - truth: "The 24h Spectrum UL regression soak after canary passes shows UL hysteresis suppression rate below 5/60s on average"
    status: failed
    reason: "Plan 07 was correctly blocked because the canary did not pass; no v1.41 soak verdict exists."
    artifacts:
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/200-SOAK-LOG.md"
        issue: "Records BLOCKED; no soak launched against rolled-back v1.40 binary."
    missing:
      - "A passed canary followed by a valid 24h v1.41 soak with mean UL hysteresis suppressions <5/60s."
  - truth: "Canary pre/post idle baselines provide usable baseline RTT bookends"
    status: partial
    reason: "Canary files exist, but Plan 06 log records pre/post baseline RTT as not captured because the script read .wans[0].rtt.baseline_rtt_ms while /health exposes .wans[0].baseline_rtt_ms. Verdict was unaffected, but baseline-damage evidence is incomplete."
    artifacts:
      - path: "scripts/phase200-saturation-canary.sh"
        issue: "summarize_baseline uses .wans[0].rtt.baseline_rtt_ms; production run verdict fields are null."
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json"
        issue: "pre_baseline_rtt_ms=null and post_baseline_rtt_ms=null"
    missing:
      - "Fix baseline RTT JSON path before reusing this canary as a full baseline-damage gate."
---

# Phase 200: Per-Direction RTT Bloat Thresholds Verification Report

**Phase Goal:** Add optional `continuous_monitoring.upload.target_bloat_ms` and `continuous_monitoring.upload.warn_bloat_ms` keys so the legacy 3-state UL controller can use thresholds independent of DL thresholds, preserve byte-identical behavior when keys are absent, adopt Spectrum 42/105 ms and 18 Mbps settings, close validator silent-ignore behavior, ship a 10-15 min saturated UL canary as deploy gate, and run 24h soak as regression watchdog.

**Verified:** 2026-05-03T00:00:00Z  
**Status:** gaps_found  
**Re-verification:** No — previous `200-VERIFICATION.md` existed but did not contain structured `gaps:` frontmatter; this verification re-checks the goal against code and evidence.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | New optional upload threshold keys are accepted, ordered, presence-tracked, and fall back to DL globals when absent. | ✓ VERIFIED | `autorate_config.py` records `_upload_target_bloat_ms_explicit = "target_bloat_ms" in ul` and `_upload_warn_bloat_ms_explicit = "warn_bloat_ms" in ul` (lines 358-366), resolves fallback values (lines 416-425), and tests cover default, override, and ordering. |
| 2 | WANController uses per-key explicit flags so live tuning cannot silently overwrite operator-explicit UL thresholds. | ✓ VERIFIED | `_apply_threshold_param` gates `target_delta` and `warn_delta` independently (lines 111-149) with ordering guards; `WANController.__init__` copies both flags and emits the D-06 INFO line through `self.logger` (lines 420-445). Tests cover equal-to-global, per-key independence, ordering guard, and INFO emission. |
| 3 | Startup validator warning closes silent-ignore behavior for unknown config keys. | ✓ VERIFIED | `Config._warn_unknown_continuous_monitoring_keys()` runs once at the end of `_load_specific_fields` (lines 1621-1650), reusing `check_unknown_keys`; `KNOWN_AUTORATE_PATHS` includes both new UL leaves (lines 68-69). Tests cover unknown warning and known-key silence. |
| 4 | Spectrum adopts latency-first 18 Mbps, factor_down_yellow 0.98, and 42/105 ms UL thresholds. | ✓ VERIFIED | `configs/spectrum.yaml` upload section has `ceiling_mbps: 18`, `factor_down_yellow: 0.98`, `target_bloat_ms: 42`, `warn_bloat_ms: 105` (lines 68-76). Version surfaces are all `1.41.0`. |
| 5 | Saturated Spectrum UL canary passes with zero floor-collapse cycles. | ✗ FAILED | `canary/20260503T215734Z/verdict.json` has `verdict: "fail"`, `ul_floor_hits_during_load: 122`, `ul_floor_threshold_hit: true`; deploy log records D-10 rollback at `2026-05-03T22:15:04Z`. |
| 6 | 24h soak runs after canary pass and demonstrates <5 suppressions/60s mean. | ✗ FAILED | `200-SOAK-LOG.md` records Plan 07 blocked because canary verdict was `fail`; no soak verdict exists. |

**Score:** 3/5 roadmap success criteria verified. The two validation criteria (canary and soak) block phase goal achievement even though implementation/docs are present.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/wanctl/autorate_config.py` | UL key loading, ordering, and SAFE-06 warning | ✓ VERIFIED | Presence flags, fallback resolution, ordering rejection, and startup warning helper are substantive and wired through `Config._load_specific_fields`. |
| `src/wanctl/wan_controller.py` | Per-key live-tuning gates and D-06 INFO verification surface | ✓ VERIFIED | Per-key gates exist; deployment journal verified the INFO line after mid-plan logger fix. |
| `src/wanctl/check_config_validators.py` | Known-key registry for new keys | ✓ VERIFIED | New paths are in `KNOWN_AUTORATE_PATHS`; unknown-key walker skips `alerting.rules.*`. |
| `tests/test_autorate_config.py` | Config and SAFE-06 regression tests | ✓ VERIFIED | Targeted run: `213 passed`; full hot slice: `644 passed in 39.91s`. |
| `tests/test_wan_controller.py` | Controller threshold tests | ✓ VERIFIED | Covers equal-value explicit, per-key independence, ordering guard, and INFO logger. |
| `tests/test_phase_195_replay.py` | SAFE-05 count baseline update | ✓ VERIFIED | Warn/target counts updated with comment; hot slice passed. |
| `configs/spectrum.yaml` | Spectrum 18 Mbps and 42/105 ms adoption | ✓ VERIFIED | Values verified with Python YAML check. |
| `CHANGELOG.md` / `docs/CONFIGURATION.md` | Release and restart-required migration docs | ✓ VERIFIED | Both document new keys and SIGUSR1-vs-restart limitation. |
| `scripts/phase200-saturation-canary.sh` | Fail-closed canary | ⚠️ PARTIAL | Executable, help/missing-env behavior works, and production canary produced a fail verdict. Baseline RTT bookends are currently null due `/health` path mismatch; remote YAML SSH path has a review warning. |
| `200-DEPLOY-LOG.md` | Deploy/canary/rollback evidence | ✓ VERIFIED | Records pre-deploy snapshot, v1.41 deploy, D-06 journal evidence, canary failure, and D-10 rollback. |
| `200-SOAK-LOG.md` | 24h soak evidence or blocked gate | ✓ VERIFIED (blocked evidence) | Correctly records no soak launched because canary failed. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| YAML `continuous_monitoring.upload.target_bloat_ms` / `warn_bloat_ms` | `Config` resolved UL thresholds | `_load_upload_config` raw values + presence flags, `_load_threshold_config` fallback | ✓ WIRED | Absent keys fall back; present keys set explicit flags regardless of value. |
| `Config` explicit flags | `WANController.__init__` | `getattr(config, "_upload_*_explicit", False)` | ✓ WIRED | Controller owns both flags and uses them for tuning gates. |
| Live tuner `target_bloat_ms` / `warn_bloat_ms` | UL `target_delta` / `warn_delta` | `_apply_threshold_param` per-key gates | ✓ WIRED | Protected fields are not overwritten; unprotected fields update only if ordering remains valid. |
| `WANController.__init__` | Production deploy verification | `self.logger.info("phase200 explicit UL thresholds active...")` | ✓ WIRED | `200-DEPLOY-LOG.md` lines 131-135 show journal hit with 42/105 values after logger fix. |
| `check_unknown_keys` | Daemon startup warning | `Config._warn_unknown_continuous_monitoring_keys()` | ✓ WIRED | Runs at config load and logs warnings without aborting startup. |
| Canary verdict | Deploy decision | `verdict.json.verdict` in Plan 06 | ✓ WIRED | Verdict `fail` caused immediate rollback and Plan 07 block. |
| Canary pass | 24h soak launch | Plan 07 gate | ✗ NOT_WIRED BY OUTCOME | Link exists conceptually, but no soak launched because upstream canary failed. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `Config` upload thresholds | `upload_target_bloat_ms`, `upload_warn_bloat_ms` | YAML `continuous_monitoring.upload.*`, fallback to `thresholds.*` | Yes | ✓ FLOWING |
| `WANController` UL thresholds | `target_delta`, `warn_delta` | `Config.upload_*` values | Yes | ✓ FLOWING |
| D-06 journal proof | explicit UL threshold log values | `WANController` runtime `target_delta`/`warn_delta` | Yes | ✓ FLOWING |
| Canary verdict | `ul_floor_hits_during_load` | 1Hz `/health.wans[0].upload.current_rate_mbps` loaded window compared to env/YAML floor | Yes | ✓ FLOWING (failed outcome) |
| Canary baseline RTT fields | `pre_baseline_rtt_ms`, `post_baseline_rtt_ms` | `summarize_baseline()` jq path | No | ⚠️ HOLLOW — production verdict fields are null due path mismatch. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full hot-path regression slice | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_phase_195_replay.py -q` | `644 passed in 39.91s` | ✓ PASS |
| Phase 200 targeted config/controller tests | `.venv/bin/pytest -o addopts='' tests/test_autorate_config.py::TestLoadUploadThresholdConfig tests/test_autorate_config.py::TestSafe06UnknownKeyWarning tests/test_wan_controller.py -q` | `213 passed in 1.85s` | ✓ PASS |
| Canary help and missing-env paths | `bash scripts/phase200-saturation-canary.sh --help`; `env -i bash scripts/phase200-saturation-canary.sh` | Help prints usage; missing env exits 2 with `ABORT: env var PHASE200_OUT_DIR is not set` | ✓ PASS |
| Version and Spectrum YAML values | Python checks `pyproject`, `__version__`, Docker label, and YAML upload values | `1.41.0`; Spectrum `18/0.98/42/105` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| ARB-05 | 200-01, 200-02, 200-08 | Per-direction UL RTT thresholds independent of DL, absent-key fallback, explicit flags protect live tuning. | ✓ SATISFIED | Code paths and tests verified; D-06 deploy journal proved 42/105 loaded on v1.41 before canary. |
| SAFE-06 | 200-03, 200-08 | Unknown `continuous_monitoring.*` keys are audibly warned/rejected; no silent ignore. | ✓ SATISFIED | Startup warning helper and tests verified; deploy journal recorded zero unknown-key warnings for prod Spectrum YAML. |
| VALN-06 | 200-05, 200-06, 200-07, 200-08 | Saturated UL canary must pass; 24h soak runs afterward as watchdog. | ✗ BLOCKED | Canary failed with 122 floor hits and rollback executed; no soak launched. |
| DOCS-03 | 200-04, 200-08 | Changelog/config docs document new keys and restart-required migration. | ✓ SATISFIED | `CHANGELOG.md` 1.41.0 section and `docs/CONFIGURATION.md` per-direction upload thresholds section verified. |

No orphaned Phase 200 requirement IDs were found in `REQUIREMENTS.md`: ARB-05, SAFE-06, VALN-06, and DOCS-03 are all mapped to Phase 200 traceability rows.

### Anti-Patterns and Residual Risks Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/phase200-saturation-canary.sh` | 265 | Remote YAML path interpolated into SSH command (`sudo cat ${REMOTE_YAML_PATH}`) | ⚠️ Warning (from `200-REVIEW.md` WR-02) | Operator-supplied malformed path can become a shell-command footgun; fix before broader reuse of the canary helper. |
| `src/wanctl/check_config_validators.py` | 305-318 | `wanctl-check-config` cross-field validation omits upload-specific target/warn ordering | ⚠️ Warning (from `200-REVIEW.md` WR-01) | Daemon rejects invalid upload ordering, but CLI preflight can still report cross-field valid; validator/daemon parity is incomplete. |
| `docker/Dockerfile` | 56-59 | Copies loose `src/wanctl/*.py` files, not full package layout | ⚠️ Warning (from `200-REVIEW.md` WR-03) | Docker image may still fail package imports; version label is correct, but packaging quality is not fully verified. |
| `scripts/phase200-saturation-canary.sh` | 175-187 | Baseline RTT jq path uses `.wans[0].rtt.baseline_rtt_ms` | ⚠️ Warning | Production verdict baseline RTT fields are null; canary verdict remains valid but baseline-damage detection is incomplete. |

### Human Verification Required

None for the current status. The relevant production behavior was already exercised by the canary and recorded as a failed deploy gate. Future gap-closure work will need another operator-approved production canary/soak.

### Gaps Summary

Phase 200 achieved the implementation, safety-warning, docs, and Spectrum YAML adoption goals, but it did **not** achieve the production validation goal. The D-07 saturated UL canary failed with 122 floor-collapse samples during the 900s loaded window, so D-10 rollback was executed and the 24h soak was correctly blocked. The phase should remain `gaps_found` / blocked until a follow-up implementation can pass the canary and then complete the 24h watchdog soak.

---

_Verified: 2026-05-03T00:00:00Z_  
_Verifier: the agent (gsd-verifier)_
