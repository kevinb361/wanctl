---
phase: 201-docsis-aware-ul-congestion-control
plan: 06
type: execute
wave: 4
depends_on: [04, 05]
files_modified:
  - configs/spectrum.yaml
  - pyproject.toml
  - src/wanctl/__init__.py
  - docker/Dockerfile
  - CHANGELOG.md
  - docs/CONFIGURATION.md
autonomous: true
requirements: [VALN-06]
tags: [phase-201, wave-4, spectrum-yaml, version-bump, docs, migration, r5-r3-disposition]

must_haves:
  truths:
    - "configs/spectrum.yaml gains docsis_mode: true, setpoint_mbps: 12 [ASSUMED, canary-validated not sweep-proven], integral_window_seconds: 2.0, integral_threshold_ms_s: 30.0, cake_backlog_low_threshold_bytes: 5000, cake_delay_delta_low_threshold_us: 5000"
    - "configs/spectrum.yaml has target_bloat_ms and warn_bloat_ms REMOVED from continuous_monitoring.upload (R0 strip per RESEARCH §5)"
    - "configs/spectrum.yaml RETAINS factor_down_yellow: 1.0 and consecutive_yellow_decay_clamp: 40 (R5 + R3 keep per RESEARCH §5)"
    - "Upload ceiling_mbps stays at 18 and floor_mbps stays at 8 (D-10)"
    - "Version bumped to 1.42.0 in pyproject.toml, src/wanctl/__init__.py, docker/Dockerfile (D-11 milestone version)"
    - "CHANGELOG.md gains a v1.42.0 entry covering Added/Changed/Migration/Inherited-blocking-closure sections"
    - "docs/CONFIGURATION.md gains a DOCSIS-Aware UL Control Mode section noting restart-required (D-08) and migration shape"
    - "Non-Spectrum YAMLs (att.yaml, others) are NOT touched (D-17 byte-identity)"
  artifacts:
    - path: configs/spectrum.yaml
      provides: "Phase 201 Spectrum config: docsis_mode opt-in, setpoint=12, R0 stripped, R5+R3 kept"
      contains: "docsis_mode: true"
    - path: pyproject.toml
      provides: "version = 1.42.0"
      contains: "1.42.0"
    - path: CHANGELOG.md
      provides: "v1.42.0 entry with VALN-06 closure block"
      contains: "v1.42.0"
    - path: docs/CONFIGURATION.md
      provides: "DOCSIS-Aware UL Control Mode migration note"
      contains: "docsis_mode"
  key_links:
    - from: "configs/spectrum.yaml continuous_monitoring.upload"
      to: "src/wanctl/check_config_validators.py KNOWN_AUTORATE_PATHS"
      via: "every upload key in YAML must be registered or SAFE-06 emits warning"
      pattern: "docsis_mode"
    - from: "configs/spectrum.yaml docsis_mode: true"
      to: "src/wanctl/autorate_config.py validation"
      via: "Config.__init__ raises if docsis_mode without setpoint_mbps"
      pattern: "setpoint_mbps"
---

<objective>
Wave 3 deployment-config wave. Lands the Spectrum YAML edits per RESEARCH §5 (R5+R3 keep, R0 strip, D-09 setpoint=12), bumps version to 1.42.0 in three places, and writes the CHANGELOG and CONFIGURATION migration sections. Non-Spectrum YAMLs are untouched (D-17).

After this lands, a Spectrum daemon restarted under v1.42 will be in DOCSIS-mode at setpoint=12 with the new corroborator logic active. Plan 201-07 will guard the deploy with the predeploy gate.

Codex pre-review MED #6 amendment: `setpoint_mbps: 12` is retained as `[ASSUMED]`, not sweep-verified. CHANGELOG and CONFIGURATION wording must state that the canary validates this assumption; if the canary fails on setpoint, the next parameter branch prefers `10` before testing `14`.

Output: Edited configs/spectrum.yaml; version bumped in three files; CHANGELOG and CONFIGURATION docs extended.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md
@.planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md
@configs/spectrum.yaml
@CHANGELOG.md
@docs/CONFIGURATION.md
</context>

<interfaces>
<!-- RESEARCH §5 keep/strip decisions, RESEARCH §10 doc skeletons. -->

Spectrum YAML upload-block target state (continuous_monitoring.upload.*):
  ADD:
    docsis_mode: true
    setpoint_mbps: 12
    integral_window_seconds: 2.0
    integral_threshold_ms_s: 30.0
    cake_backlog_low_threshold_bytes: 5000
    cake_delay_delta_low_threshold_us: 5000
  REMOVE:
    target_bloat_ms: 42       # rejected v1.41 hypothesis
    warn_bloat_ms: 105        # rejected v1.41 hypothesis
  KEEP:
    floor_mbps: 8
    ceiling_mbps: 18
    factor_down_yellow: 1.0   # R5 — RESEARCH §5 retain
    consecutive_yellow_decay_clamp: 40  # R3 — RESEARCH §5 retain

Version 1.41.0 -> 1.42.0 in three files (locate exact occurrences via grep).
CHANGELOG.md skeleton from RESEARCH §10.
docs/CONFIGURATION.md skeleton from RESEARCH §10.
</interfaces>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Edit configs/spectrum.yaml (R5+R3 keep, R0 strip, D-09 setpoint=12, D-10 ceiling=18)</name>
  <files>configs/spectrum.yaml</files>
  <read_first>
    - configs/spectrum.yaml (full file — under 250 lines; locate continuous_monitoring.upload block via grep)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-CONTEXT.md (D-09, D-10 verbatim)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §5 (Existing v1.41 R5+R3 Disposition)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-PATTERNS.md section "configs/spectrum.yaml (config / data — modify)"
  </read_first>
  <action>
First, grep for the upload block boundaries:

```
grep -n '^continuous_monitoring:|^  download:|^  upload:|^  thresholds:|^[a-z]' configs/spectrum.yaml | head -40
```

Then targeted Read of the upload block (PATTERNS.md cites lines 67-77; verify before editing).

Apply these edits to `continuous_monitoring.upload`:

1. REMOVE the two rejected v1.41 hypothesis lines:
```
    target_bloat_ms: 42 # 2026-04-29 UL-only fix...
    warn_bloat_ms: 105 # UL-only 3-state RED threshold...
```

2. ADD the six Phase 201 keys (immediately AFTER `consecutive_yellow_decay_clamp: 40` line):
```
    # Phase 201 (v1.42) DOCSIS-aware UL congestion control mode (per VALN-06).
    # Operating point: 12 Mbit (60% of ~20 Mbit estimated provisioned upstream).
    # Setpoint = [ASSUMED] A4 + A5 from RESEARCH.md; canary validates.
    # Fallback on canary fail: drop to 10 (parameter tune, NOT control-model rejection).
    docsis_mode: true
    setpoint_mbps: 12
    # Headroom probe: integral of max(0, load_rtt - baseline_rtt) over 2s window.
    # Threshold 30 ms*s = average sample at exactly target_delta over full window.
    integral_window_seconds: 2.0
    integral_threshold_ms_s: 30.0
    # CAKE corroborator (categorical AND-gate with integral). Phase 163 sweep
    # backlog winner = 5000 bytes; delay-delta low = 5ms (deadband_ms analog).
    cake_backlog_low_threshold_bytes: 5000
    cake_delay_delta_low_threshold_us: 5000
```

3. KEEP unchanged: `floor_mbps: 8`, `ceiling_mbps: 18`, `factor_down_yellow: 1.0`, `consecutive_yellow_decay_clamp: 40`.

CRITICAL: Do NOT touch the download block, the thresholds block, or any other non-upload section. Do NOT change `floor_mbps` or `ceiling_mbps`. Do NOT touch the live-tunable allow-list.

Verify after edit:
- `python3 -c "import yaml; yaml.safe_load(open('configs/spectrum.yaml'))"`
- `.venv/bin/python -c "from wanctl.autorate_config import Config; c = Config('configs/spectrum.yaml'); assert c.docsis_mode is True; assert c.setpoint_mbps == 12; assert c._docsis_mode_explicit is True; assert c._setpoint_mbps_explicit is True; print('OK')"`
  </action>
  <acceptance_criteria>
    - **REVIEWS MED-5 (path-aware YAML checks, NOT line-anchored grep):** the following Python YAML path checks all exit 0 — replacing the prior line-anchored greps that could match `download` keys at the same indentation level.

      ```bash
      # Required Phase 201 keys present under continuous_monitoring.upload
      python3 -c "
      import yaml
      d = yaml.safe_load(open('configs/spectrum.yaml'))
      ul = d['continuous_monitoring']['upload']
      assert ul.get('docsis_mode') is True, 'docsis_mode must be True'
      assert ul.get('setpoint_mbps') == 12, f'setpoint_mbps={ul.get(\"setpoint_mbps\")} != 12'
      assert ul.get('integral_window_seconds') == 2.0, 'integral_window_seconds must be 2.0'
      assert ul.get('integral_threshold_ms_s') == 30.0, 'integral_threshold_ms_s must be 30.0'
      assert ul.get('cake_backlog_low_threshold_bytes') == 5000, 'cake_backlog_low_threshold_bytes must be 5000'
      assert ul.get('cake_delay_delta_low_threshold_us') == 5000, 'cake_delay_delta_low_threshold_us must be 5000'
      assert ul.get('factor_down_yellow') == 1.0, 'R5 factor_down_yellow=1.0 must be retained'
      assert ul.get('consecutive_yellow_decay_clamp') == 40, 'R3 consecutive_yellow_decay_clamp=40 must be retained'
      assert ul.get('floor_mbps') == 8, 'D-10 floor_mbps=8 must be unchanged'
      assert ul.get('ceiling_mbps') == 18, 'D-10 ceiling_mbps=18 must be unchanged'
      # R0 strip: rejected v1.41 keys MUST NOT be present in continuous_monitoring.upload
      assert 'target_bloat_ms' not in ul, f'target_bloat_ms must be stripped from upload (got {ul.get(\"target_bloat_ms\")})'
      assert 'warn_bloat_ms' not in ul, f'warn_bloat_ms must be stripped from upload (got {ul.get(\"warn_bloat_ms\")})'
      print('OK')
      "
      ```

    - att.yaml unchanged: `git diff configs/att.yaml | wc -l` returns 0.
    - Config validates and reflects opt-in: see verify command.
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/python -c "import yaml; yaml.safe_load(open('configs/spectrum.yaml'))" &amp;&amp; .venv/bin/python -c "from wanctl.autorate_config import Config; c = Config('configs/spectrum.yaml'); assert c.docsis_mode is True and c.setpoint_mbps == 12 and c._docsis_mode_explicit is True and c._setpoint_mbps_explicit is True"</automated>
  </verify>
  <done>Spectrum YAML reflects Phase 201 design; R0 stripped, R5+R3 retained, six new keys present; ceiling/floor unchanged; ATT untouched.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Bump version to 1.42.0 in pyproject.toml, src/wanctl/__init__.py, docker/Dockerfile</name>
  <files>pyproject.toml, src/wanctl/__init__.py, docker/Dockerfile</files>
  <read_first>
    - pyproject.toml (locate `version = "1.41.0"`)
    - src/wanctl/__init__.py (locate `__version__ = "1.41.0"`)
    - docker/Dockerfile (locate any 1.41 reference, e.g. `WANCTL_VERSION=1.41.0` or LABEL or ENV)
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-04-SUMMARY.md or similar (Phase 200 D-11 patterns) for guidance
  </read_first>
  <action>
1. In `pyproject.toml`: replace exactly one occurrence of `version = "1.41.0"` with `version = "1.42.0"`.
2. In `src/wanctl/__init__.py`: replace exactly one occurrence of `__version__ = "1.41.0"` with `__version__ = "1.42.0"`.
3. In `docker/Dockerfile`: locate the version reference (likely `WANCTL_VERSION=1.41.0` or a LABEL line) and replace with 1.42.0. Use grep first to find the exact form.

Verify:
```
grep -c '"1.42.0"' pyproject.toml
grep -c '"1.42.0"' src/wanctl/__init__.py
grep -c '1.42.0' docker/Dockerfile
```

Each MUST return 1. Then run:
```
.venv/bin/python -c "import wanctl; print(wanctl.__version__)"
```
must print `1.42.0`.
  </action>
  <acceptance_criteria>
    - `grep -c 'version = "1.42.0"' pyproject.toml` returns 1.
    - `grep -c '__version__ = "1.42.0"' src/wanctl/__init__.py` returns 1.
    - `grep -c '1.42.0' docker/Dockerfile` returns >= 1.
    - `grep -c 'version = "1.41.0"' pyproject.toml` returns 0.
    - `grep -c '__version__ = "1.41.0"' src/wanctl/__init__.py` returns 0.
    - `.venv/bin/python -c "import wanctl; assert wanctl.__version__ == '1.42.0'"` exits 0.
    - Hot-path slice still passes: `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` returns 0 (health endpoint exposes the version).
  </acceptance_criteria>
  <verify>
    <automated>.venv/bin/python -c "import wanctl; assert wanctl.__version__ == '1.42.0'" &amp;&amp; .venv/bin/pytest -o addopts='' tests/test_health_check.py -q</automated>
  </verify>
  <done>Version 1.42.0 reflected in three files; wanctl module imports at the new version; health test green.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Add v1.42.0 CHANGELOG entry and DOCSIS-Aware UL Control Mode section in docs/CONFIGURATION.md</name>
  <files>CHANGELOG.md, docs/CONFIGURATION.md</files>
  <read_first>
    - CHANGELOG.md (locate `## v1.41.0` heading and structure; copy formatting style)
    - docs/CONFIGURATION.md (locate where Phase 200 DOCS-03 added the v1.41 migration note)
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-RESEARCH.md §10 (CHANGELOG and CONFIGURATION skeletons)
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-04-PLAN.md or related (the DOCS-03 pattern to mirror)
  </read_first>
  <action>
Insert new entry in `CHANGELOG.md`. Place a new `## v1.42.0` section IMMEDIATELY ABOVE the existing `## v1.41.0` heading. Use the date format already used in the file (e.g., `## v1.42.0 (2026-MM-DD)` or whatever style — match existing).

Content of the new section (mirror style of v1.41.0 entry):

```
## v1.42.0 — DOCSIS-Aware UL Congestion Control

**Phase 201 closes inherited blocking VALN-06 from Phase 200.**

### Added
- `continuous_monitoring.upload.docsis_mode: bool` (default false)
- `continuous_monitoring.upload.setpoint_mbps: int|float` (REQUIRED when docsis_mode: true; validator fails closed if absent)
- `continuous_monitoring.upload.integral_window_seconds: float` (default 2.0; min 0.5, max 10.0)
- `continuous_monitoring.upload.integral_threshold_ms_s: float` (default 30.0; min 1.0, max 1000.0)
- `continuous_monitoring.upload.cake_backlog_low_threshold_bytes: int` (default 5000)
- `continuous_monitoring.upload.cake_delay_delta_low_threshold_us: int` (default 5000)
- `/health.wans[].upload.docsis_mode_active` (runtime state)
- `/health.wans[].upload.setpoint_mbps` (runtime state, NOT a YAML echo)
- `/health.wans[].upload.headroom_state` (runtime state: AVAILABLE | EXHAUSTED)
- `/health.wans[].upload.rtt_integral_ms_s` (runtime state)
- `/health.wans[].upload.cake_aligned` (runtime state)
- `scripts/phase201-predeploy-gate.sh` (D-15)

### Changed
- Spectrum (`configs/spectrum.yaml`): `docsis_mode: true`, `setpoint_mbps: 12`. Removed v1.41 rejected-hypothesis `target_bloat_ms: 42` and `warn_bloat_ms: 105`. Retained `factor_down_yellow: 1.0` and `consecutive_yellow_decay_clamp: 40` (R5 + R3 complementary to setpoint clamp; RESEARCH.md §5).
- `setpoint_mbps: 12` is `[ASSUMED]`, not sweep-proven. Phase 201 canary validates it; if setpoint-specific canary failure occurs, the next branch should prefer `10` before testing `14`.
- Upload `QueueController.adjust()` augmented with optional integral path + setpoint clamp. Legacy path byte-identical when `docsis_mode` absent.

### Migration
**Service restart required** for the new keys. SIGUSR1 does NOT reload them. Apply with: `sudo systemctl restart wanctl@<wan>.service`.

The predeploy gate (`scripts/phase201-predeploy-gate.sh`) inspects `/etc/wanctl/spectrum.yaml` for v1.41-only rejected-hypothesis keys (`target_bloat_ms`, `warn_bloat_ms` in `continuous_monitoring.upload`) and aborts the deploy with operator-actionable instructions if found.

### Inherited blocking closure
- VALN-06: Spectrum UL canary `ul_floor_hits_during_load=0` AND 24h soak UL hysteresis suppression `<5/60s` (verified by Phase 201 canary + soak; see `.planning/phases/201-docsis-aware-ul-congestion-control/`).

### Out of scope (deferred to v1.43+)
- Modem SNMP / DOCSIS HCS counter signal
- Tighter soak watchdog `<2/60s`
- DOCSIS-mode auto-tuning of `setpoint_mbps`
- Multi-window integral
- ATT cake-primary canary (VALN-05b — cross-milestone, gated on v1.39 Phase 191 closure)
```

Then in `docs/CONFIGURATION.md`, append a new section. Locate via grep where Phase 200's per-direction-thresholds section lives (D-08 / DOCS-03 pattern):

```
grep -n '^##\|^###' docs/CONFIGURATION.md | head -40
```

Append (or insert at the appropriate level) a new section:

```
### DOCSIS-Aware UL Control Mode (v1.42+)

Enable per deployment by setting:

    continuous_monitoring:
      upload:
        docsis_mode: true
        setpoint_mbps: 12  # [ASSUMED], link-specific; canary-validates; no global default
        # Optional tuning keys (defaults shown):
        integral_window_seconds: 2.0          # 0.5..10.0
        integral_threshold_ms_s: 30.0         # 1.0..1000.0
        cake_backlog_low_threshold_bytes: 5000
        cake_delay_delta_low_threshold_us: 5000

When `docsis_mode: true`, the upload controller:

- Runs `setpoint_mbps` as the operating point (NOT the ceiling).
- Uses a windowed RTT integral as the headroom probe.
- AND-gates push-toward-ceiling on CAKE backlog/delay-delta low.

For Spectrum v1.42, `setpoint_mbps: 12` is an assumed starting point rather than a sweep-proven optimum. Treat a setpoint-specific canary failure as a parameter branch first; prefer testing `10` before `14`.

When `docsis_mode: false` or absent, behavior is byte-identical to v1.41.

**Required ordering:** `floor_mbps < setpoint_mbps < ceiling_mbps` (strict; validator fails closed on violation).

**Service restart required.** SIGUSR1 does NOT reload these keys. Apply changes with:

    sudo systemctl restart wanctl@<wan>.service

The predeploy gate (`scripts/phase201-predeploy-gate.sh`) inspects `/etc/wanctl/spectrum.yaml` on the deploy target and aborts the deploy with operator-actionable instructions if v1.41-only rejected-hypothesis keys (`target_bloat_ms`, `warn_bloat_ms` under `continuous_monitoring.upload`) are present.
```
  </action>
  <acceptance_criteria>
    - `grep -c '## v1.42.0' CHANGELOG.md` returns 1.
    - `grep -c 'VALN-06' CHANGELOG.md` returns >= 1 (within v1.42.0 section).
    - `grep -c 'docsis_mode' CHANGELOG.md` returns >= 2 (Added + Changed sections).
    - `grep -c 'setpoint_mbps' CHANGELOG.md` returns >= 2.
    - `grep -c 'systemctl restart' CHANGELOG.md` returns >= 1 (migration note).
    - `grep -c 'phase201-predeploy-gate.sh' CHANGELOG.md` returns >= 1.
    - `grep -c 'DOCSIS-Aware UL Control Mode' docs/CONFIGURATION.md` returns 1.
    - `grep -c 'docsis_mode' docs/CONFIGURATION.md` returns >= 2.
    - `grep -c 'systemctl restart wanctl' docs/CONFIGURATION.md` returns >= 1.
    - `grep -c 'floor_mbps < setpoint_mbps < ceiling_mbps' docs/CONFIGURATION.md` returns 1.
  </acceptance_criteria>
  <verify>
    <automated>grep -q '## v1.42.0' CHANGELOG.md &amp;&amp; grep -q 'VALN-06' CHANGELOG.md &amp;&amp; grep -q 'DOCSIS-Aware UL Control Mode' docs/CONFIGURATION.md &amp;&amp; grep -q 'systemctl restart wanctl' docs/CONFIGURATION.md</automated>
  </verify>
  <done>CHANGELOG v1.42.0 entry covers Added/Changed/Migration/Inherited-closure; CONFIGURATION migration section present with required-ordering note; restart-required surfaced in both files.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| repo configs/spectrum.yaml -> production /etc/wanctl/spectrum.yaml | Repo-side YAML is the canonical source; deploy.sh copies it; predeploy gate (Plan 201-07) inspects production-side state. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-201-24 | Tampering | YAML edit accidentally drops floor_mbps or ceiling_mbps | mitigate | Acceptance grep asserts both present at exact values 8 and 18. |
| T-201-25 | Tampering | Edit silently regresses non-Spectrum YAML (ATT) | mitigate | Acceptance gate: `git diff configs/att.yaml` empty. D-17 invariant enforced. |
| T-201-26 | Repudiation | Migration note missing from docs; operator restarts and is surprised by behavior change | mitigate | Both CHANGELOG and CONFIGURATION require systemctl-restart language; acceptance grep enforces. |
| T-201-27 | Tampering | Version bump misses one of three locations -> /health reports stale version | mitigate | Acceptance grep asserts 1.41.0 absent and 1.42.0 present in all three files. |
| T-201-28 | Information Disclosure | YAML edit exposes operator-IP or hostname through new comment | accept | New comments are technical (setpoint rationale); no IP/host/secret leaked. CLAUDE.md privacy guideline reviewed. |
</threat_model>

<verification>
- Spectrum YAML reflects Phase 201 design: docsis_mode + setpoint=12 + integral keys + corroborator keys present; R0 keys stripped; R5+R3 retained; ceiling/floor unchanged.
- ATT YAML untouched.
- Version 1.42.0 in three files; module-import test green.
- CHANGELOG v1.42.0 entry covers all required sections.
- CONFIGURATION migration note present with restart-required + ordering invariant.
</verification>

<success_criteria>
- D-09 setpoint=12 landed; D-10 ceiling=18 unchanged.
- RESEARCH §5 R0/R5/R3 disposition implemented.
- Version 1.42.0 propagated.
- DOCS-03 pattern mirrored for v1.42 keys.
- D-17 byte-identity preserved for non-Spectrum YAMLs.
</success_criteria>

<output>
After completion, create `.planning/phases/201-docsis-aware-ul-congestion-control/201-06-SUMMARY.md` listing: lines added/removed in spectrum.yaml; the version-bump file paths; CHANGELOG section length; CONFIGURATION section length; ATT YAML diff (must be empty).
</output>
