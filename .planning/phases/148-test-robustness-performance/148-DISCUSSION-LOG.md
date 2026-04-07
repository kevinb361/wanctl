# Phase 148: Test Robustness & Performance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-07
**Phase:** 148-test-robustness-performance
**Areas discussed:** Mock replacement strategy, Test speed optimization, Brittleness threshold, Flaky test policy, Coverage regression guard

---

## Mock Replacement Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Retarget to public APIs | Change patch targets from private _attrs to Phase 147 public methods. Lowest risk | ✓ |
| Build lightweight fakes | In-memory fake implementations (FakeRouter, FakeWANController) | |
| Dependency injection refactor | Restructure constructors to accept interfaces | |

**User's choice:** Retarget to public APIs
**Notes:** Phase 147 already created the public interfaces. This is the pragmatic path.

| Option | Description | Selected |
|--------|-------------|----------|
| No fakes — retarget only | Pure retargeting pass, no new test infrastructure | |
| Fakes for health endpoints only | Small fakes for the ~15 health endpoint tests | |
| You decide | Claude identifies where fakes add clear value | ✓ |

**User's choice:** Claude's discretion on fakes
**Notes:** User trusts Claude to identify where fakes add clear value.

---

## Test Speed Optimization

| Option | Description | Selected |
|--------|-------------|----------|
| pytest-xdist | Process-level parallelism with -n auto | ✓ |
| No parallelization — optimize serial | Focus purely on profiling slow tests | |

**User's choice:** pytest-xdist

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute: under 60 seconds | Hard target | |
| Relative: 20%+ faster | Measure before/after | |
| Whichever is more achievable | Per success criterion wording | ✓ |

**User's choice:** Whichever is more achievable

| Option | Description | Selected |
|--------|-------------|----------|
| tmp_path per worker | Each xdist worker gets unique temp dirs | ✓ |
| Worker-aware conftest | Add xdist worker_id to conftest fixtures | |

**User's choice:** tmp_path per worker

| Option | Description | Selected |
|--------|-------------|----------|
| Replace in make ci | Make xdist the default, -n auto falls back | ✓ |
| Separate make test-parallel | Keep make ci serial, offer parallel as opt-in | |

**User's choice:** Replace in make ci

| Option | Description | Selected |
|--------|-------------|----------|
| pytest --durations=50 | Built-in profiling, no new tooling | ✓ |
| pytest-profiling plugin | Per-test CPU/wall profiles with cProfile | |

**User's choice:** pytest --durations=50

| Option | Description | Selected |
|--------|-------------|----------|
| Optimize in place | Replace real I/O with mocks, keep all tests fast | ✓ |
| Mark and separate | @pytest.mark.slow, exclude from default run | |
| Both | Optimize first, mark survivors | |

**User's choice:** Optimize in place

| Option | Description | Selected |
|--------|-------------|----------|
| -n auto | Detects available CPUs, adapts to any machine | ✓ |
| Fixed -n 4 | Predictable but doesn't adapt | |

**User's choice:** -n auto

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — pytest --timeout=2 | Any test exceeding 2s fails | ✓ |
| No hard timeout | Just profile and fix | |

**User's choice:** Yes — pytest --timeout=2

**Additional questions:**
- Test ordering dependencies with xdist: Claude's discretion
- Fixture consolidation during rewrites: Claude's discretion (user said "whatever you think")
- Collection time in speed target: Claude's discretion
- Known slow test areas: None known, let profiling reveal

---

## Brittleness Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| Cross-module private attrs | Patch of _attr from different module than code under test | ✓ |
| Any private attribute patch | Stricter: any _attr patch counts | |
| Any MagicMock usage | Strictest: every MagicMock counts | |

**User's choice:** Cross-module private attrs

| Option | Description | Selected |
|--------|-------------|----------|
| CI grep check | Count cross-module _attr patches per file, fail if >3 | ✓ |
| Ruff custom rule | AST-based analysis, higher effort | |
| Manual audit only | Document the rule, enforce in review | |

**User's choice:** CI grep check

| Option | Description | Selected |
|--------|-------------|----------|
| Target zero, allow 3 as exception | Zero is the goal, 3 is safety valve | ✓ |
| Strict zero — no exceptions | Every cross-module private patch eliminated | |
| 3 is the real target | Reasonable ceiling, focus on worst offenders | |

**User's choice:** Target zero, allow 3 as exception

| Option | Description | Selected |
|--------|-------------|----------|
| Per test file | Count per .py file, simpler grep | ✓ |
| Per test class | Each TestFoo class evaluated independently | |
| Per test function | Strictest per-function count | |

**User's choice:** Per test file

| Option | Description | Selected |
|--------|-------------|----------|
| Extend Phase 147's check | One tool, two contexts (source + test) | ✓ |
| Separate test-brittleness script | Distinct tools for different concerns | |

**User's choice:** Extend Phase 147's check

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — rewrite if needed | Same behavioral assertion, different setup is fine | ✓ |
| Minimal changes only | Only change the patch target line | |

**User's choice:** Yes — rewrite if needed

**Additional questions:**
- Brittleness metrics tracking: Claude's discretion
- Patch style counting (string vs patch.object): Claude's discretion
- Conftest.py exemption from check: Claude's discretion

---

## Flaky Test Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Fix or delete — no flaky markers | Zero tolerance, flaky test = bug in test | ✓ |
| Quarantine then fix | Move to quarantine dir, fix within phase | |
| Allow temporary xfail with ticket | xfail OK if includes TODO reference | |

**User's choice:** Fix or delete — no flaky markers

| Option | Description | Selected |
|--------|-------------|----------|
| No — fix on first failure | Running 3x triples CI time | ✓ |
| pytest-repeat in nightly job | Separate nightly CI with --count=3 | |

**User's choice:** No — fix on first failure

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — systematic audit | Grep for time.sleep, global state, real I/O | ✓ |
| No proactive audit | Only fix flakiness if it manifests | |

**User's choice:** Yes — systematic audit

| Option | Description | Selected |
|--------|-------------|----------|
| Mock time.monotonic/time.sleep | Replace real sleeps with mocked time | ✓ |
| Allow short sleeps (≤50ms) | Sleeps under 50ms acceptable | |

**User's choice:** Mock time.monotonic/time.sleep

| Option | Description | Selected |
|--------|-------------|----------|
| Enforce reset fixtures | Every test file touching metrics must have autouse reset | ✓ |
| Rely on xdist isolation | Workers are separate processes, registries don't leak | |

**User's choice:** Enforce reset fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — randomized run as final gate | pytest --randomly-seed=12345 -n auto as verification | ✓ |
| No — xdist isolation sufficient | State can't leak between workers | |

**User's choice:** Yes — randomized run as final gate

| Option | Description | Selected |
|--------|-------------|----------|
| One-time gate only | Verify during Phase 148, don't add to permanent CI | ✓ |
| Permanent in CI | Always randomize test ordering | |

**User's choice:** One-time gate only

**Additional questions:**
- CI ban on time.sleep(): Claude's discretion

---

## Coverage Regression Guard

| Option | Description | Selected |
|--------|-------------|----------|
| Per-commit enforcement | Keep make ci 90% floor, every commit must pass | ✓ |
| Per-plan enforcement | Allow temporary dips, restore by final commit | |

**User's choice:** Per-commit enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 90% | Good floor, don't constrain future phases | ✓ |
| Raise to 92% | Lock in gains from rewrites | |

**User's choice:** Keep 90%

---

## Claude's Discretion

- Fakes for health endpoint tests (or other areas where they clearly simplify things)
- Fixture consolidation of duplicate mock_config definitions
- Collection time measurement methodology
- Test ordering safety verification approach
- Patch style counting for brittleness metric
- Conftest.py exemption from brittleness check
- CI ban on time.sleep() in test code
- Brittleness metrics tracking (binary CI vs trend tracking)

## Deferred Ideas

- Integration test for router communication — repeatedly deferred from Phase 146 and 147 (testing area but new integration tests, not existing test robustness)
