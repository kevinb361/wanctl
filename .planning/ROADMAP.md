# Roadmap: wanctl

## Overview

wanctl adaptive dual-WAN CAKE controller for MikroTik. Eliminates bufferbloat via queue tuning + intelligent WAN steering.

## Domain Expertise

None

## Milestones

- v1.0 through v1.23: See MILESTONES.md (shipped)
- v1.24 EWMA Boundary Hysteresis: Phases 121-124 (shipped 2026-04-02)
- v1.25 Reboot Resilience: Phase 125 (shipped 2026-04-02)
- v1.26 Tuning Validation: Phases 126-130 (shipped 2026-04-02)
- v1.27 Performance & QoS: Phases 131-136 (shipped 2026-04-03)
- v1.28 Infrastructure Optimization: Phases 137-141 (shipped 2026-04-05)
- v1.29 Code Health & Cleanup: Phases 142-150 (in progress)

## Phases

<details>
<summary>v1.24 EWMA Boundary Hysteresis (Phases 121-124) -- SHIPPED 2026-04-02</summary>

- [x] Phase 121: Core Hysteresis Logic -- dwell timer + deadband margin
- [x] Phase 122: Hysteresis Configuration -- YAML config, defaults, SIGUSR1 hot-reload
- [x] Phase 123: Hysteresis Observability -- health endpoint, transition suppression logging
- [x] Phase 124: Production Validation -- deploy, confirm zero flapping

</details>

<details>
<summary>v1.25 Reboot Resilience (Phase 125) -- SHIPPED 2026-04-02</summary>

- [x] Phase 125: Boot Resilience -- NIC tuning script, systemd dependency wiring, deploy.sh, dry-run validated

</details>

<details>
<summary>v1.26 Tuning Validation (Phases 126-130) -- SHIPPED 2026-04-02</summary>

- [x] Phase 126: Pre-Test Gate -- 5-point environment verification script
- [x] Phase 127: DL Parameter Sweep -- 9 DL params A/B tested, 6 changed
- [x] Phase 128: UL Parameter Sweep -- 3 UL params tested, 1 changed
- [x] Phase 129: CAKE RTT + Confirmation Pass -- rtt=40ms, 1 interaction flip caught
- [x] Phase 130: Production Config Commit -- config verified, docs updated

</details>

<details>
<summary>v1.27 Performance & QoS (Phases 131-136) -- SHIPPED 2026-04-03</summary>

- [x] Phase 131: Cycle Budget Profiling -- per-subsystem timing under RRUL
- [x] Phase 132: Cycle Budget Optimization -- BackgroundRTTThread, cycle util 102%->27%
- [x] Phase 133: Diffserv Bridge Audit -- 3-point DSCP capture audit
- [x] Phase 134: Diffserv Tin Separation -- MikroTik prerouting DSCP + wanctl-check-cake
- [x] Phase 135: Upload Recovery Tuning -- A/B tested, +17.6% UL throughput
- [x] Phase 136: Hysteresis Observability -- suppression rate monitoring + alerting

</details>

<details>
<summary>v1.28 Infrastructure Optimization (Phases 137-141) -- SHIPPED 2026-04-05</summary>

- [x] Phase 137: cake-shaper vCPU Expansion -- 3rd vCPU added (manual Proxmox task, completed 2026-04-04)
- [x] Phase 138: cake-shaper IRQ & Kernel Tuning -- 3-core IRQ affinity + sysctl tuning (completed 2026-04-04)
- [x] Phase 139: RB5009 Queue & IRQ Optimization -- SFP+ multi-queue + switch IRQ redistribution (completed 2026-04-04)
- [x] Phase 140: WireGuard Error Investigation -- ZeroTier binding root cause, fix applied (completed 2026-04-05)
- [x] Phase 141: Bridge Download DSCP Classification -- nftables bridge DSCP into CAKE tins (completed 2026-04-04)

</details>

### v1.29 Code Health & Cleanup (In Progress)

**Milestone Goal:** Systematic codebase audit and cleanup -- dead code removal, module complexity reduction, test quality improvements, and type safety hardening -- with zero behavioral changes to production.

- [x] **Phase 142: Dead Code Removal** - Remove unused imports, dead functions/methods, and orphaned modules (completed 2026-04-05)
- [x] **Phase 143: Dependency & Cruft Cleanup** - Remove unused pip deps, stale TODOs, dead config references (completed 2026-04-05)
- [x] **Phase 144: Module Splitting** - Break up files over 500 LOC into focused single-responsibility modules (gap closure in progress) (completed 2026-04-06)
- [x] **Phase 145: Method Extraction & Simplification** - Extract long methods and flatten high cyclomatic complexity (completed 2026-04-06)
- [x] **Phase 146: Test Cleanup & Organization** - Remove redundant tests, restructure directories, consolidate fixtures (completed 2026-04-06)
- [x] **Phase 147: Interface Decoupling** - Reduce tight coupling between modules with cleaner interfaces (gap closure in progress) (completed 2026-04-08)
- [ ] **Phase 148: Test Robustness & Performance** - Replace brittle mocks, profile and speed up slow tests
- [ ] **Phase 149: Type Annotations & Protocols** - Add missing type annotations, use Protocol/ABC patterns
- [ ] **Phase 150: Linting Strictness** - Enable stricter mypy rules and additional ruff rules

## Phase Details

### Phase 142: Dead Code Removal
**Goal**: The codebase contains zero unreachable code -- no unused imports, no dead functions/methods, no orphaned modules
**Depends on**: Nothing (first phase of v1.29)
**Requirements**: DEAD-01, DEAD-02
**Success Criteria** (what must be TRUE):
  1. Running a dead code detection tool (vulture or similar) on src/ reports zero unused code findings
  2. Every .py file in src/wanctl/ is imported by at least one other module or is an entry point
  3. All existing tests pass unchanged (no behavioral regression)
**Plans:** 2/2 plans complete
Plans:
- [x] 142-01-PLAN.md -- Configure vulture, create whitelist, fix unused imports, add make dead-code target
- [x] 142-02-PLAN.md -- Triage and remove dead functions/methods, remove orphaned modules, three-layer verification

### Phase 143: Dependency & Cruft Cleanup
**Goal**: Project dependencies are minimal and the codebase contains no stale annotations, dead config references, or outdated comments
**Depends on**: Phase 142
**Requirements**: DEAD-03, DEAD-04
**Success Criteria** (what must be TRUE):
  1. Every package listed in pyproject.toml [dependencies] is actually imported somewhere in src/
  2. No TODO/FIXME/HACK comments reference completed work, removed features, or resolved issues
  3. No config YAML keys are referenced in code that no longer reads them
  4. All existing tests pass unchanged (no behavioral regression)
**Plans:** 3/3 plans complete
Plans:
- [x] 143-01-PLAN.md -- Dependency audit: make check-deps target verifying all 8 runtime deps, integrated into make ci
- [x] 143-02-PLAN.md -- Config key cross-reference audit: fix stale/dead keys in examples, update KNOWN_*_PATHS, verify deprecated translations
- [x] 143-03-PLAN.md -- Docstring/comment staleness audit and CONFIG_SCHEMA.md sync with config key findings

### Phase 144: Module Splitting
**Goal**: No single source file carries more than ~500 LOC, and each module has a clear single responsibility
**Depends on**: Phase 143
**Requirements**: CPLX-01
**Success Criteria** (what must be TRUE):
  1. No .py file in src/wanctl/ exceeds 500 lines (excluding blank lines and comments)
  2. Each new module created during splitting has a docstring stating its single responsibility
  3. All imports across the codebase resolve correctly after splits (no circular imports)
  4. All existing tests pass unchanged (no behavioral regression)
**Plans:** 4/4 plans complete
Plans:
- [x] 144-01-PLAN.md -- Extract QueueController, Config, and RouterOS from autorate_continuous.py into own modules
- [x] 144-02-PLAN.md -- Extract WANController + constants, finalize autorate_continuous.py as thin orchestrator
- [x] 144-03-PLAN.md -- Split 4 CLI tools (check_config, check_cake, calibrate, benchmark) into focused modules
- [x] 144-04-PLAN.md -- Gap closure: split check_config_validators.py into autorate and steering validator modules

### Phase 145: Method Extraction & Simplification
**Goal**: No function exceeds ~50 lines and no function has excessive branching depth, making every function readable in a single screen
**Depends on**: Phase 144
**Requirements**: CPLX-02, CPLX-04
**Success Criteria** (what must be TRUE):
  1. No function or method in src/wanctl/ exceeds 50 lines (excluding docstrings)
  2. Ruff complexity checks (C901) pass at a threshold of 15 or lower
  3. Extracted helper functions each have a clear name describing their single purpose
  4. All existing tests pass unchanged (no behavioral regression)
**Plans:** 6/6 plans complete
Plans:
- [x] 145-01-PLAN.md -- Verification script + WANController __init__/run_cycle/_check_congestion_alerts extraction
- [x] 145-02-PLAN.md -- autorate_continuous.py main() lifecycle decomposition
- [x] 145-03-PLAN.md -- steering/daemon.py run_cycle/main/__init__/config loader extraction
- [x] 145-04-PLAN.md -- health_check.py + steering/health.py section-builder extraction
- [x] 145-05-PLAN.md -- Remaining large functions across 8 files (autorate_config, check_cake, queue_controller, etc.)
- [x] 145-06-PLAN.md -- C901 violations cleanup, pyproject.toml threshold update to 15

### Phase 146: Test Cleanup & Organization
**Goal**: The test suite contains no redundant tests and follows a consistent, navigable directory and naming structure
**Depends on**: Phase 144
**Requirements**: TEST-01, TEST-04
**Success Criteria** (what must be TRUE):
  1. No two test functions verify the same behavior (redundant coverage removed)
  2. Test directory structure mirrors src/wanctl/ module structure
  3. Shared fixtures live in conftest.py files at appropriate scope levels, not duplicated across test files
  4. All test file names follow a consistent pattern (test_{module}.py)
  5. Total test count may decrease but coverage percentage stays at 90%+
**Plans:** 3/3 plans complete
Plans:
- [x] 146-01-PLAN.md -- Baseline + stale removal + helpers.py + move steering/ and backends/ tests
- [x] 146-02-PLAN.md -- Move storage/ and tuning/ tests into subdirectories
- [x] 146-03-PLAN.md -- Merge feature-specific tests into parent modules + redundancy audit

### Phase 147: Interface Decoupling
**Goal**: Modules communicate through well-defined interfaces, reducing the number of direct cross-module attribute accesses
**Depends on**: Phase 145
**Requirements**: CPLX-03
**Success Criteria** (what must be TRUE):
  1. No module directly accesses private attributes (_prefixed) of another module's classes
  2. Key integration boundaries (router transport, state persistence, metrics) have clear interface definitions
  3. Import graphs show reduced fan-in on formerly tightly-coupled modules
  4. All existing tests pass unchanged (no behavioral regression)
**Plans:** 5/5 plans complete
Plans:
- [x] 147-01-PLAN.md -- Create interfaces.py Protocol definitions + AST-based boundary check CI script
- [x] 147-02-PLAN.md -- WANController public facade + autorate_continuous.py call site updates (~35 accesses)
- [x] 147-03-PLAN.md -- WANController/QueueController/AlertEngine health facade + health_check.py updates (~30 accesses)
- [x] 147-04-PLAN.md -- SteeringDaemon facade + steering/health.py + check_cake.py + empty allowlist (~15 accesses)
- [x] 147-05-PLAN.md -- Gap closure: fix 46 steering test failures (private method renames + get_health_data() mock pattern)

### Phase 148: Test Robustness & Performance
**Goal**: Tests are fast, reliable, and test behavior rather than implementation details
**Depends on**: Phase 146, Phase 147
**Requirements**: TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. No test patches more than 3 internal implementation details (MagicMock usage reduced)
  2. Full test suite runs in under 60 seconds (or 20%+ faster than baseline, whichever is more achievable)
  3. No test is marked flaky or requires retry to pass
  4. All existing tests pass (behavioral coverage preserved)
**Plans:** 3 plans
Plans:
- [ ] 148-01-PLAN.md -- Install xdist+timeout, configure pyproject.toml/Makefile, Prometheus reset fixture, fix 7 alert_engine MagicMock failures, create brittleness CI script
- [ ] 148-02-PLAN.md -- Retarget 22 cross-module private patches across 6 test files to Phase 147 public APIs
- [ ] 148-03-PLAN.md -- Eliminate real time.sleep() from tests, tighten brittleness to 0, xdist isolation gate

### Phase 149: Type Annotations & Protocols
**Goal**: Every public function signature has complete type annotations and abstract interfaces use proper Protocol/ABC patterns
**Depends on**: Phase 147
**Requirements**: TYPE-01, TYPE-04
**Success Criteria** (what must be TRUE):
  1. Running mypy with --disallow-untyped-defs on src/wanctl/ produces zero errors for public functions
  2. No public function uses bare `Any` type where a more specific type is possible
  3. Abstract interfaces use typing.Protocol or abc.ABC instead of informal duck typing
  4. All existing tests pass unchanged (no behavioral regression)
**Plans**: TBD

### Phase 150: Linting Strictness
**Goal**: The project enforces stricter static analysis rules that catch more bugs and style issues at lint time
**Depends on**: Phase 149
**Requirements**: TYPE-02, TYPE-03
**Success Criteria** (what must be TRUE):
  1. mypy runs with disallow_untyped_defs=true, warn_return_any=true, and no_implicit_optional=true -- zero errors
  2. Ruff runs with additional rule sets enabled (complexity C90, naming N, import sorting I) -- zero violations
  3. CI pipeline (make ci) passes with the stricter configuration
  4. All existing tests pass unchanged (no behavioral regression)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 142 through 150.
Note: Phase 146 depends on Phase 144 (not 145), so 146 could theoretically run alongside 145, but sequential execution is simpler.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 142. Dead Code Removal | v1.29 | 2/2 | Complete    | 2026-04-05 |
| 143. Dependency & Cruft Cleanup | v1.29 | 3/3 | Complete    | 2026-04-05 |
| 144. Module Splitting | v1.29 | 4/4 | Complete    | 2026-04-06 |
| 145. Method Extraction & Simplification | v1.29 | 6/6 | Complete    | 2026-04-06 |
| 146. Test Cleanup & Organization | v1.29 | 3/3 | Complete    | 2026-04-06 |
| 147. Interface Decoupling | v1.29 | 5/5 | Complete    | 2026-04-08 |
| 148. Test Robustness & Performance | v1.29 | 0/3 | Not started | - |
| 149. Type Annotations & Protocols | v1.29 | 0/? | Not started | - |
| 150. Linting Strictness | v1.29 | 0/? | Not started | - |
