---
phase: quick-001
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/steering/steering_confidence.py
  - src/wanctl/steering/daemon.py
  - src/wanctl/steering/__init__.py
  - tests/test_steering_timers.py
  - configs/steering.yaml
  - configs/examples/steering.yaml.example
  - docs/CONFIG_SCHEMA.md
  - docs/CORE-ALGORITHM-ANALYSIS.md
autonomous: true

must_haves:
  truths:
    - "Class name is ConfidenceController, not Phase2BController"
    - "Log prefix is [CONFIDENCE], not [PHASE2B]"
    - "Module variable is CONFIDENCE_AVAILABLE, not PHASE2B_AVAILABLE"
    - "All tests pass with renamed classes/imports"
  artifacts:
    - path: "src/wanctl/steering/steering_confidence.py"
      provides: "ConfidenceController class"
      contains: "class ConfidenceController"
    - path: "src/wanctl/steering/__init__.py"
      provides: "CONFIDENCE_AVAILABLE export"
      contains: "CONFIDENCE_AVAILABLE"
  key_links:
    - from: "src/wanctl/steering/daemon.py"
      to: "steering_confidence.py"
      via: "import ConfidenceController"
      pattern: "from .steering_confidence import.*ConfidenceController"
---

<objective>
Rename Phase2B internal codename to confidence-based steering throughout the codebase.

Purpose: Replace cryptic codename with descriptive name for long-term maintainability. "Phase2B" was a development milestone name; "confidence-based steering" describes what the feature actually does.

Output: All references to "Phase2B" renamed to "Confidence" or "confidence-based steering" in code, tests, configs, and docs.
</objective>

<execution_context>
@/home/kevin/.claude/get-shit-done/workflows/execute-plan.md
@/home/kevin/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/wanctl/steering/steering_confidence.py
@src/wanctl/steering/daemon.py
@src/wanctl/steering/__init__.py
@tests/test_steering_timers.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rename class and log prefixes in steering_confidence.py</name>
  <files>src/wanctl/steering/steering_confidence.py</files>
  <action>
1. Rename class `Phase2BController` to `ConfidenceController` (line 488)
2. Update module docstring: "Phase 2B: Confidence-Based" -> "Confidence-Based Steering" (line 3)
3. Replace all `[PHASE2B]` log prefixes with `[CONFIDENCE]` (~22 occurrences):
   - Line 144: debug log in compute_confidence
   - Lines 236, 243-246, 250-251, 259: degrade_timer logs
   - Lines 283-284, 289: hold_down_timer logs
   - Lines 326-327, 334-335, 341, 358: recovery_timer logs
   - Lines 469, 472-473, 476, 479-480: DryRunLogger logs
   - Lines 546, 548, 592: Phase2BController init and hold_down logs
4. Update docstring references in TimerState (line 155-160): "Phase 2B meta-state" -> "Confidence-based steering meta-state"
5. Update section comment at line 484: "PHASE 2B CONTROLLER" -> "CONFIDENCE CONTROLLER"
6. Keep design doc reference in docstring: "docs/PHASE_2B_DESIGN.md" (file may not exist, but reference is historical)
  </action>
  <verify>
    grep -c "Phase2BController" src/wanctl/steering/steering_confidence.py  # Should be 0
    grep -c "ConfidenceController" src/wanctl/steering/steering_confidence.py  # Should be 2+
    grep -c "\[PHASE2B\]" src/wanctl/steering/steering_confidence.py  # Should be 0
    grep -c "\[CONFIDENCE\]" src/wanctl/steering/steering_confidence.py  # Should be ~22
  </verify>
  <done>Class renamed to ConfidenceController, all [PHASE2B] log prefixes changed to [CONFIDENCE]</done>
</task>

<task type="auto">
  <name>Task 2: Update imports and exports in daemon.py and __init__.py</name>
  <files>src/wanctl/steering/daemon.py, src/wanctl/steering/__init__.py</files>
  <action>
In daemon.py:
1. Update import (lines 63-65): `Phase2BController` -> `ConfidenceController`
2. Update type hint (line 677): `Phase2BController | None` -> `ConfidenceController | None`
3. Update instantiation (line 679): `Phase2BController(` -> `ConfidenceController(`
4. Update log message (line 687): `[PHASE2B]` -> `[CONFIDENCE]`
5. Optional: Update comments referencing "Phase 2B" to "confidence-based" where appropriate

In __init__.py:
1. Rename variable (line 35): `PHASE2B_AVAILABLE` -> `CONFIDENCE_AVAILABLE`
2. Update comments (lines 34, 60, 64): "Phase 2B" -> "confidence-based"
3. Update conditional (line 65): `if PHASE2B_AVAILABLE:`
4. Update re-export (line 67): `Phase2BController = _sc.Phase2BController` -> `ConfidenceController = _sc.ConfidenceController`
5. Update __all__ extension (line 74): `"Phase2BController"` -> `"ConfidenceController"`
  </action>
  <verify>
    grep -c "Phase2BController" src/wanctl/steering/daemon.py  # Should be 0
    grep -c "PHASE2B_AVAILABLE" src/wanctl/steering/__init__.py  # Should be 0
    grep -c "CONFIDENCE_AVAILABLE" src/wanctl/steering/__init__.py  # Should be 3+
    python -c "from wanctl.steering import CONFIDENCE_AVAILABLE, ConfidenceController; print('Import OK')"
  </verify>
  <done>All imports/exports updated, module loads without errors</done>
</task>

<task type="auto">
  <name>Task 3: Update tests, configs, and docs</name>
  <files>tests/test_steering_timers.py, configs/steering.yaml, configs/examples/steering.yaml.example, docs/CONFIG_SCHEMA.md, docs/CORE-ALGORITHM-ANALYSIS.md</files>
  <action>
In tests/test_steering_timers.py:
1. Update import (line 17): `Phase2BController` -> `ConfidenceController`
2. Rename test class (line 178): `TestPhase2BControllerCycleInterval` -> `TestConfidenceControllerCycleInterval`
3. Update docstrings to reference "ConfidenceController"

In configs/steering.yaml:
1. Line 55: Remove "Phase 2B:" prefix from comment, keep description
2. Lines 57-71: Update comment header to "Confidence-based steering" instead of "Phase 2B"

In configs/examples/steering.yaml.example:
1. Lines 90-108: Update "Phase 2B" references in comments to "Confidence-based steering"

In docs/CONFIG_SCHEMA.md:
1. Lines 323, 325, 327, 343: Replace "Phase 2B" with "Confidence-based steering" (~4 occurrences)
2. Keep technical accuracy - describe what it does, not the codename

In docs/CORE-ALGORITHM-ANALYSIS.md:
1. Line 537: Update "steering_confidence.py (Phase 2B, unused)" to "steering_confidence.py (confidence-based steering)"
2. Do NOT change "Phase 2B: Time-of-Day Bias" reference if exists (different feature)
  </action>
  <verify>
    .venv/bin/pytest tests/test_steering_timers.py -v  # All tests pass
    grep -c "Phase2BController" tests/test_steering_timers.py  # Should be 0
    grep -c "Phase 2B:" configs/steering.yaml  # Should be 0 (colon matters)
    grep -c "Phase 2B" docs/CONFIG_SCHEMA.md  # Should be 0
  </verify>
  <done>Tests pass with renamed classes, config comments updated, docs updated</done>
</task>

</tasks>

<verification>
# Full test suite should pass
.venv/bin/pytest tests/ -v --tb=short

# Verify no remaining Phase2B references in code (excluding historical doc references)
grep -r "Phase2BController" src/ tests/
grep -r "PHASE2B_AVAILABLE" src/
grep -r "\[PHASE2B\]" src/

# Verify new naming in place
grep -r "ConfidenceController" src/
grep -r "CONFIDENCE_AVAILABLE" src/
grep -r "\[CONFIDENCE\]" src/
</verification>

<success_criteria>
- [ ] All 594+ unit tests pass
- [ ] No "Phase2BController" or "PHASE2B_AVAILABLE" references in src/ or tests/
- [ ] No "[PHASE2B]" log prefixes in src/
- [ ] Imports work: `from wanctl.steering import CONFIDENCE_AVAILABLE, ConfidenceController`
- [ ] Config comments describe "confidence-based steering" not "Phase 2B"
- [ ] Type checking passes: `make type` or `mypy src/wanctl/`
</success_criteria>

<output>
After completion, create `.planning/quick/001-rename-phase2b-to-confidence-based-steer/001-SUMMARY.md`
</output>
