---
phase: quick-003
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - configs/steering.yaml
  - configs/examples/steering.yaml.example
  - src/wanctl/steering/daemon.py
  - docs/CONFIG_SCHEMA.md
  - tests/test_steering_deprecation.py
autonomous: true

must_haves:
  truths:
    - "No deprecation warnings logged on steering daemon startup"
    - "Config files use only current parameter names"
    - "Documentation reflects current parameters only"
  artifacts:
    - path: "configs/steering.yaml"
      provides: "Production config without deprecated params"
      contains: "red_samples_required"
    - path: "src/wanctl/steering/daemon.py"
      provides: "Daemon without deprecation warning code"
  key_links: []
---

<objective>
Remove deprecated bad_samples/good_samples parameters from steering configuration and eliminate deprecation warning code.

Purpose: Eliminate startup log noise and config confusion by removing deprecated parameters that have been superseded by red_samples_required/green_samples_required.

Output: Clean configs, updated docs, removed deprecation warning code.
</objective>

<execution_context>
@/home/kevin/.claude/get-shit-done/workflows/execute-plan.md
@/home/kevin/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/CONFIG_SCHEMA.md
@src/wanctl/steering/daemon.py
@configs/steering.yaml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove deprecated params from config files</name>
  <files>
    configs/steering.yaml
    configs/examples/steering.yaml.example
  </files>
  <action>
    In configs/steering.yaml:
    - Remove lines 47-48 (bad_samples and good_samples under thresholds)
    - These are legacy params, replaced by confidence-based steering

    In configs/examples/steering.yaml.example:
    - Lines 78-79 already use red_samples_required/green_samples_required (correct)
    - No changes needed to example config
  </action>
  <verify>grep -E "bad_samples|good_samples" configs/steering.yaml (returns empty)</verify>
  <done>Production steering.yaml contains only current parameter names</done>
</task>

<task type="auto">
  <name>Task 2: Remove deprecation warning code from daemon</name>
  <files>
    src/wanctl/steering/daemon.py
    tests/test_steering_deprecation.py
  </files>
  <action>
    In src/wanctl/steering/daemon.py:
    - Remove DEPRECATION HELPERS section (lines 111-132): _warn_deprecated_param function
    - Remove deprecation warning calls in SteeringConfig.__init__ (lines 303-309)
    - Keep bad_samples/good_samples properties but have them read red_samples_required/green_samples_required instead (for any remaining internal usage)

    In tests/test_steering_deprecation.py:
    - Delete the entire file - it only tests deprecated functionality that no longer exists
  </action>
  <verify>
    - grep "_warn_deprecated_param" src/wanctl/steering/daemon.py (returns empty)
    - .venv/bin/pytest tests/ -v (all tests pass)
  </verify>
  <done>Deprecation warning code removed, tests pass</done>
</task>

<task type="auto">
  <name>Task 3: Update CONFIG_SCHEMA.md documentation</name>
  <files>docs/CONFIG_SCHEMA.md</files>
  <action>
    In docs/CONFIG_SCHEMA.md:
    - Remove "Deprecated Parameters" section (lines 285-294)
    - This section documents bad_samples/good_samples which no longer exist
  </action>
  <verify>grep -E "bad_samples|good_samples" docs/CONFIG_SCHEMA.md (returns empty)</verify>
  <done>Documentation reflects only current parameters</done>
</task>

</tasks>

<verification>
1. No deprecated params in config files:
   grep -rE "bad_samples|good_samples" configs/ (empty or only comments)

2. No deprecation code in source:
   grep "_warn_deprecated_param" src/wanctl/ (empty)

3. All tests pass:
   .venv/bin/pytest tests/ -v

4. Type checks pass:
   .venv/bin/mypy src/wanctl/
</verification>

<success_criteria>
- configs/steering.yaml has no bad_samples or good_samples
- src/wanctl/steering/daemon.py has no _warn_deprecated_param
- tests/test_steering_deprecation.py deleted
- docs/CONFIG_SCHEMA.md has no deprecated parameters section
- All existing tests pass
- No type errors
</success_criteria>

<output>
After completion, create `.planning/quick/003-remove-deprecated-sample-params/003-SUMMARY.md`
</output>
