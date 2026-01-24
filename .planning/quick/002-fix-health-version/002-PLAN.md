---
phase: quick
plan: 002
type: execute
wave: 1
depends_on: []
files_modified: [src/wanctl/__init__.py]
autonomous: true

must_haves:
  truths:
    - "Health endpoint reports version 1.4.0"
  artifacts:
    - path: "src/wanctl/__init__.py"
      provides: "Package version"
      contains: '__version__ = "1.4.0"'
  key_links: []
---

<objective>
Update package version from 1.1.0 to 1.4.0

Purpose: Health endpoint reads __version__ from package; currently shows stale 1.1.0
Output: Version string updated to match current milestone
</objective>

<execution_context>
@/home/kevin/.claude/get-shit-done/workflows/execute-plan.md
@/home/kevin/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/wanctl/__init__.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update version string</name>
  <files>src/wanctl/__init__.py</files>
  <action>Change __version__ from "1.1.0" to "1.4.0"</action>
  <verify>grep -q '1.4.0' src/wanctl/__init__.py</verify>
  <done>__version__ = "1.4.0"</done>
</task>

</tasks>

<verification>
- `grep __version__ src/wanctl/__init__.py` shows 1.4.0
- `python -c "from wanctl import __version__; print(__version__)"` prints 1.4.0
</verification>

<success_criteria>
Package version matches current milestone (1.4.0)
</success_criteria>

<output>
After completion, create `.planning/quick/002-fix-health-version/002-SUMMARY.md`
</output>
