---
phase: 200-per-direction-rtt-bloat-thresholds
verified: 2026-05-04T14:24:43Z
status: gaps_found
score: 3/5 roadmap success criteria verified
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
    - src/wanctl/queue_controller.py
    - src/wanctl/wan_controller.py
    - src/wanctl/__init__.py
  tests:
    - tests/conftest.py
    - tests/test_autorate_config.py
    - tests/test_check_config.py
    - tests/test_phase200_canary_script.py
    - tests/test_phase_195_replay.py
    - tests/test_queue_controller.py
    - tests/test_wan_controller.py
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
    - .dockerignore
deploy_state: rolled-back
canary_verdict_path: .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json
soak_verdict_path: null
re_verification:
  previous_status: gaps_found
  previous_score: 3/5 roadmap criteria verified; VALN-06 remains blocked after Attempt 3
  gaps_closed:
    - "Canary baseline RTT bookends are now populated in Attempt 3 verdict (21.7 ms -> 22.23 ms)."
    - "WR-01 CLI upload threshold ordering parity closed by Plan 200-12."
    - "WR-02 remote YAML path validation closed for metacharacter/path traversal cases by Plan 200-11."
    - "WR-03 Docker package layout closed by Plan 200-13 static source verification."
  gaps_remaining:
    - "Saturated Spectrum UL canary still failed: 4 loaded-window floor hits."
    - "24h Spectrum regression soak was skipped because the canary failed."
  regressions: []
closure: deferred-to-phase-201
closure_decision:
  date: 2026-05-04
  decided_by: operator
  rationale: |
    Phase 200 RETRO concluded that the per-direction-thresholds hypothesis is the
    wrong fix; the remaining loaded-window floor regime is dominated by shaping
    headroom rather than threshold geometry. Plans 200-09..200-14 reduced UL
    floor hits from 122 to 4 (a 96.7% improvement) but the deploy gate requires
    zero. Marginal returns on further Phase 200 tuning are judged low; VALN-06
    is escalated to Phase 201 (docsis-aware-ul-congestion-control), which is
    already seeded with the 122-collapse evidence as the proper next-milestone
    candidate.
  no_second_remediation_attempted: true
  production_state_change: none
  production_binary: v1.40 (rolled back post Attempt 3 canary fail)
  prod_yaml_state: |
    v1.41 keys remain on /etc/wanctl/spectrum.yaml and are inactive under the
    rolled-back v1.40 binary, but they MUST be reconciled before any future
    Spectrum deploy or service restart that uses a binary which re-recognizes
    those keys. A Phase 201 predeploy gate (see follow-ons) is required to
    inspect the file and either reconcile or fail closed.
  inherits_to: phase-201-docsis-aware-ul-congestion-control
  inherited_as: blocking_requirement
  see_also:
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-RETRO.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json
gaps:
  - truth: "The 10-15 min saturated iperf3 -P4 UL canary at 18 Mbit completes without the UL controller collapsing to the 8 Mbit floor in any cycle"
    status: failed
    reason: "Gap-closure Attempt 3 improved the canary from 122 floor hits to 4, but VALN-06 requires zero loaded-window floor hits; verdict remained fail and rollback executed."
    artifacts:
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260504T133207Z/verdict.json"
        issue: "verdict=fail, ul_floor_hits_during_load=4, ul_floor_threshold_hit=true, pre/post baseline RTT populated"
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/200-DEPLOY-LOG.md"
        issue: "Attempt 3 rollback recorded at 2026-05-04T13:49:19Z using /opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz"
    missing:
      - "A production canary verdict with ul_floor_hits_during_load=0 after an approved second-stage remediation or operator decision."
  - truth: "The 24h Spectrum UL regression soak after canary passes shows UL hysteresis suppression rate below 5/60s on average"
    status: failed
    reason: "The 24h soak is gated on a passing canary. Attempt 3 canary failed, so the soak was skipped fail-closed and no valid soak verdict exists."
    artifacts:
      - path: ".planning/phases/200-per-direction-rtt-bloat-thresholds/200-SOAK-LOG.md"
        issue: "Records skipped (canary-fail-branch) for Attempt 3; no 24h soak launched."
    missing:
      - "A passed canary followed by a valid 24h Spectrum soak with mean UL hysteresis suppressions <5/60s."
---

# Phase 200: Per-Direction RTT Bloat Thresholds Verification Report

**Phase Goal:** Add optional `continuous_monitoring.upload.target_bloat_ms` and `continuous_monitoring.upload.warn_bloat_ms` keys so the legacy 3-state UL controller can use thresholds independent of DL thresholds, preserve byte-identical behavior when keys are absent, adopt Spectrum UL settings, close validator silent-ignore behavior, ship a 10-15 min saturated UL canary as deploy gate, and run a 24h soak as regression watchdog.

**Verified:** 2026-05-04T14:24:43Z  
**Status:** gaps_found  
**Re-verification:** Yes — previous `200-VERIFICATION.md` already had structured gaps. Failed validation items were re-checked fully; previously passing code/docs items received regression checks.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Autorate config accepts optional UL target/warn keys, validates ordering, and falls back to global thresholds when absent. | ✓ VERIFIED | `autorate_config.py` schema includes `continuous_monitoring.upload.target_bloat_ms` and `warn_bloat_ms`; `_load_upload_config()` records presence flags at lines 371-379; `_load_threshold_config()` resolves fallback and rejects `upload_target >= upload_warn` at lines 429-438. |
| 2 | Validator emits audible warnings for unknown config keys and recognizes all Phase 200 keys. | ✓ VERIFIED | `Config._warn_unknown_continuous_monitoring_keys()` is called at config load end (`autorate_config.py:1634-1664`); `KNOWN_AUTORATE_PATHS` includes upload target/warn and `consecutive_yellow_decay_clamp` (`check_config_validators.py:68-70`). |
| 3 | Spectrum deploy config carries v1.41/v1.41-gap settings: 18 Mbps ceiling, UL 42/105 ms thresholds, R5 hold, and R3 clamp. | ✓ VERIFIED | `configs/spectrum.yaml:70-76` has `ceiling_mbps: 18`, `factor_down_yellow: 1.0`, `target_bloat_ms: 42`, `warn_bloat_ms: 105`, and `consecutive_yellow_decay_clamp: 40`. |
| 4 | Saturated Spectrum UL canary passes with zero floor-collapse samples. | ✗ FAILED | Attempt 3 verdict at `canary/20260504T133207Z/verdict.json` has `verdict: fail`, `ul_floor_hits_during_load: 4`, `ul_floor_threshold_hit: true`; `200-DEPLOY-LOG.md` records rollback at `2026-05-04T13:49:19Z`. |
| 5 | 24h Spectrum regression soak runs after canary pass and mean UL hysteresis suppressions are <5/60s. | ✗ FAILED | `200-SOAK-LOG.md` records Attempt 3 `skipped (canary-fail-branch)` because upstream canary failed; no soak verdict exists. |
| 6 | Changelog and configuration docs document the new keys and restart-required migration. | ✓ VERIFIED | `CHANGELOG.md` v1.41.0 documents upload threshold and clamp changes; `docs/CONFIGURATION.md` has “Per-Direction Upload Thresholds (v1.41+)” plus “service restart required (NOT SIGUSR1)” with `systemctl restart wanctl@<wan>.service`. |

**Score:** 3/5 roadmap success criteria verified. Implementation/config/docs criteria pass; both VALN-06 validation criteria remain blocked.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/wanctl/autorate_config.py` | UL threshold schema, fallback, ordering, presence flags, SAFE-06 warning | ✓ VERIFIED | Lines 175-189 define schema; lines 361-379 load clamp and per-key explicit flags; lines 429-438 enforce upload threshold ordering; lines 1634-1664 emit warnings. |
| `src/wanctl/wan_controller.py` | Per-key live-tuning gates and runtime D-06 log surface | ✓ VERIFIED | `_apply_threshold_param()` gates target/warn independently and guards ordering; `WANController._init_baseline_and_thresholds()` logs explicit UL thresholds via `self.logger`. |
| `src/wanctl/queue_controller.py` | R3 consecutive-YELLOW clamp default-off and RED-preserving | ✓ VERIFIED | Constructor default `consecutive_yellow_decay_clamp=0`; `_compute_rate_3state()` holds after clamp and resets on RED/GREEN/non-YELLOW while RED decay stays immediate. |
| `src/wanctl/check_config_validators.py` | Known-key registry and upload ordering preflight | ✓ VERIFIED | `KNOWN_AUTORATE_PATHS` contains new keys; `validate_cross_fields()` calls `_validate_upload_threshold_ordering()` and returns ERROR for inverted/equal upload thresholds. |
| `scripts/phase200-saturation-canary.sh` | Fail-closed canary, baseline bookends, remote YAML validation | ✓ VERIFIED (failed outcome) | Script validates env/YAML floor/ceiling, runs iperf3 `-P 4`, writes pass/fail/abort verdicts, and Attempt 3 populated baseline RTT bookends. Review warning remains for missing explicit python/yaml dependency check before the remote YAML parse. |
| `configs/spectrum.yaml` | Spectrum values adopted | ✓ VERIFIED | 18 Mbps ceiling, 1.0 YELLOW hold, 42/105 ms thresholds, clamp 40. |
| `docker/Dockerfile` / `.dockerignore` | Version and package layout | ⚠️ WARNING | Package directory copy is fixed, but `200-REVIEW.md` warns unquoted shell-form pip constraints can be parsed as redirections and top usage comment still shows stale build command. |
| `200-DEPLOY-LOG.md` | Deploy/canary/rollback evidence | ✓ VERIFIED | Records Attempt 3 deploy, D-06 journal hit, canary fail with 4 floor hits, and rollback tarball path. |
| `200-SOAK-LOG.md` | Soak evidence or blocked gate | ✓ VERIFIED (blocked evidence) | Records skipped soak because canary failed. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| YAML `continuous_monitoring.upload.target_bloat_ms` / `warn_bloat_ms` | `Config.upload_*_bloat_ms` | raw upload values + fallback in `_load_threshold_config()` | ✓ WIRED | Explicit and fallback paths exist; ordering rejection prevents inverted config. |
| Config explicit flags | `WANController` live-tuning gates | `getattr(config, "_upload_*_explicit", False)` | ✓ WIRED | Per-key gates protect `target_delta` and `warn_delta` independently. |
| Config `upload_consecutive_yellow_decay_clamp` | Upload `QueueController` | `WANController` constructor pass-through | ✓ WIRED | `getattr(config, "upload_consecutive_yellow_decay_clamp", 0)` passed to upload controller only. |
| SAFE-06 registry | Startup warning | `check_unknown_keys(self.data)` in Config helper | ✓ WIRED | Warnings emitted without abort; alerting rules skipped by shared validator. |
| Canary verdict | Deploy decision | Plan 200-14 branch | ✓ WIRED | `verdict=fail` caused D-10 rollback. |
| Canary pass | 24h soak launch | Plan 200-14 Task 4 gate | ✗ NOT WIRED BY OUTCOME | Link exists in plan, but upstream canary failed so soak correctly did not launch. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `Config` upload thresholds | `upload_target_bloat_ms`, `upload_warn_bloat_ms` | YAML upload keys or global fallback | Yes | ✓ FLOWING |
| `WANController` UL thresholds | `target_delta`, `warn_delta` | `Config.upload_*` values | Yes | ✓ FLOWING |
| Upload clamp | `consecutive_yellow_decay_clamp` | YAML -> `Config` -> upload `QueueController` | Yes | ✓ FLOWING |
| Canary baseline fields | `pre_baseline_rtt_ms`, `post_baseline_rtt_ms` | `/health.wans[0].baseline_rtt_ms` via `summarize_baseline()` | Yes | ✓ FLOWING — Attempt 3 verdict has `21.7` and `22.23`. |
| Canary verdict | `ul_floor_hits_during_load` | 1Hz loaded-window `/health.wans[0].upload.current_rate_mbps` compared to YAML/env floor | Yes | ✓ FLOWING (failed outcome) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| R3 clamp single-GREEN reset | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'yellow_clamp_resets_on_single_green'` | `1 passed, 137 deselected` | ✓ PASS |
| Per-key UL explicit gates | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k 'upload_thresholds_explicit'` | `2 passed, 206 deselected` | ✓ PASS |
| SAFE-06 + upload preflight + canary helper tests | `.venv/bin/pytest -o addopts='' tests/test_autorate_config.py::TestSafe06UnknownKeyWarning tests/test_check_config.py::TestUploadThresholdOrdering tests/test_phase200_canary_script.py -q` | `17 passed` | ✓ PASS |
| Full suite after closeout | Recorded execution outcome | `4787 passed, 6 skipped, 2 deselected` | ✓ PASS (recorded evidence) |
| Schema drift gate | Recorded execution outcome | `drift_detected=false` | ✓ PASS (recorded evidence) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| ARB-05 | 200-01, 200-02, 200-10 | Per-direction UL thresholds independent of DL, absent-key fallback, live-tuning protection, R3 default-off clamp. | ✓ SATISFIED | Code and targeted tests verified; deploy journal showed 42/105 values live before Attempt 3. |
| SAFE-06 | 200-03, 200-12 | Unknown keys audibly warned and upload threshold ordering caught in CLI preflight. | ✓ SATISFIED | Startup warning helper, known-key registry, `_validate_upload_threshold_ordering()`, and tests verified. |
| VALN-06 | 200-05, 200-06, 200-07, 200-11, 200-14, 200-15 | Saturated Spectrum UL canary must pass with zero floor hits; 24h soak follows. | ✗ BLOCKED | Attempt 3 canary failed with 4 floor hits; D-10 rollback used `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz`; soak skipped. |
| DOCS-03 | 200-04, 200-10, 200-13 | Changelog/config docs document new keys and restart-required migration. | ✓ SATISFIED | Docs greps found v1.41.0, new key section, clamp guidance, SIGUSR1 warning, and restart command. |

No orphaned Phase 200 requirement IDs were found in `REQUIREMENTS.md`; ARB-05, SAFE-06, VALN-06, and DOCS-03 are all mapped to Phase 200.

### Anti-Patterns and Residual Risks Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `docker/Dockerfile` | 46-52 | Unquoted shell-form pip constraints (`requests>=...`) | ⚠️ Warning (`200-REVIEW.md` WR-01) | Docker builds can parse `>` as redirection; packaging correctness risk, advisory for phase goal. |
| `scripts/phase200-saturation-canary.sh` | 328-338 | Python/PyYAML dependency not prechecked before command substitution | ⚠️ Warning (`200-REVIEW.md` WR-02) | Missing dependency may exit without writing an abort verdict; actual Attempt 3 produced a fail verdict, so this did not affect current VALN evidence. |
| `docker/Dockerfile` | 5-7 | Stale top-level build invocation comment | ℹ️ Info (`200-REVIEW.md` IN-01) | Documentation polish; canonical command appears later in Dockerfile. |
| `scripts/phase200-saturation-canary.env.example` | template env values | Empty assignments | ℹ️ Info | Intentional operator template; not a runtime stub. |
| `src/wanctl/*` | various `return []` / `return {}` | Empty collections | ℹ️ Info | Existing defensive empty-result returns; not user-visible stubs and not Phase 200 blockers. |

### Human Verification Required

None for the current status. The decisive production behavior was already exercised by the canary and recorded as a failed deploy gate with rollback. Any future closure requires a new operator-approved canary and then a 24h soak.

### Gaps Summary

Phase 200 achieved the implementation, safety-warning, docs, Spectrum config/remediation, and canary-evidence-surface goals. It did **not** achieve VALN-06. Gap-closure Attempt 3 materially improved the saturated Spectrum UL canary from 122 floor samples to 4 and fixed the baseline RTT bookends, but the deploy gate allows zero loaded-window floor hits. The canary failed, D-10 rollback executed using `/opt/wanctl-prephase200-gap-20260504T132936Z.tar.gz`, and the 24h soak was correctly skipped fail-closed. Phase 200 remains `gaps_found` until a second-stage remediation/operator decision produces a zero-floor-hit canary followed by a passing 24h soak.

### Closure Decision (2026-05-04, operator-escalated)

Phase 200 is sealed at `gaps_found` with **VALN-06 deferred to Phase 201
(`docsis-aware-ul-congestion-control`)** rather than re-entered into a second
gap-closure cycle. The operator made this call on 2026-05-04 after weighing two
findings:

1. The Phase 200 RETRO concluded that the per-direction-thresholds hypothesis
   is the wrong fix: the remaining failure regime is dominated by shaping
   headroom (DOCSIS upstream queue depth versus wanctl ceiling), not threshold
   geometry. Plans 200-09..200-14 reduced loaded-window UL floor hits from 122
   to 4 — a 96.7% improvement but still non-zero, and the deploy gate is
   strictly fail-closed at zero.
2. Phase 201 already exists as a seed (`.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md`)
   and is loaded with the 122-collapse evidence file as its design input.
   ROADMAP.md explicitly allows operator escalation as a closure path for
   VALN-06.

No second remediation was attempted; production binary remains on v1.40
post-rollback. The v1.41 YAML keys (`continuous_monitoring.upload.target_bloat_ms`,
`warn_bloat_ms`, `consecutive_yellow_decay_clamp`, `factor_down_yellow=1.0`,
`ceiling_mbps=18`) remain on prod `/etc/wanctl/spectrum.yaml` and are inactive
under the rolled-back v1.40 binary, but they MUST be reconciled before any
future Spectrum deploy or service restart that uses a binary which re-recognizes
those keys. A future binary that consumes them would reactivate rejected-hypothesis
state silently. Phase 201's PLAN must include a predeploy gate that inspects
`/etc/wanctl/spectrum.yaml` for v1.41-only keys and either reconciles or fails
closed (see `<follow_ons>` in `200-16-PLAN.md`).

The two failed-truth rows in this report (row #4 saturated UL canary, row #5
24h soak) remain `FAILED` — they are not retroactively marked verified. The
other observable-truth rows (#1 schema/fallback, #2 SAFE-06 unknown-key warning,
#3 Spectrum YAML adoption, #6 changelog/docs) remain `VERIFIED`.

VALN-06 traceability is now carried by Phase 201's `## Inherited Requirements`
block as an **inherited blocking requirement** — Phase 201 SPEC and PLAN must
carry VALN-06 forward and cannot silently drop it during 201 scoping. See
`200-RETRO.md` `## Final Closure (2026-05-04)` for the full operator-decision
narrative and v1.42 lessons, and `canary/20260504T133207Z/verdict.json` for the
direct Attempt 3 evidence (`verdict: fail`, `ul_floor_hits_during_load: 4`).

---

_Verified: 2026-05-04T14:24:43Z_  
_Verifier: the agent (gsd-verifier)_
