# Project Retrospective

_A living document updated after each milestone. Lessons feed forward into future planning._

## Milestone: v1.10 — Architectural Review Fixes

**Shipped:** 2026-03-09
**Phases:** 8 | **Plans:** 14 executed (1 superseded)

### What Was Built

- Hot-loop blocking delays eliminated (sub-cycle retries, shutdown_event.wait)
- Self-healing transport failover with periodic primary re-probe (30-300s backoff)
- Operational resilience: SQLite corruption auto-recovery, disk space health monitoring, SSL verification defaults
- Systematic codebase audit: daemon duplication consolidated, complexity hotspots extracted
- Test quality: behavioral integration tests, failure cascade coverage, fixture consolidation (-481 lines)
- Full gap closure: 27/27 requirements satisfied, 6/6 E2E flows verified

### What Worked

- Milestone audit → gap closure pipeline: the audit at Phase 54 identified TEST-01 and cosmetic gaps, which drove Phase 56-57 creation as targeted closures. No wasted work.
- Research agent thoroughness: Phase 57 research identified exactly which fixtures to consolidate vs. leave alone (different mock shapes), preventing over-consolidation.
- Single-plan phases for focused gap closure: Phases 56-57 each had exactly 1 plan, making them fast to plan, verify, and execute.
- Verification-driven completion: 7/7 must-haves verified for Phase 57, giving confidence to ship.

### What Was Inefficient

- Phase 55 Plan 55-01 was planned but never executed, then superseded by Phase 57. The fixture consolidation work was done twice in planning (55-01 plan + 57-01 plan).
- Milestone audit ran before all phases were complete (Phase 55 partially done), requiring a re-audit and gap closure phases. Running audit after all phases would have been simpler.
- Summary files lack standardized one_liner frontmatter field, making automated accomplishment extraction difficult at milestone completion.

### Patterns Established

- Gap closure phases: decimal-free phases (56, 57) as targeted fixups after audit, rather than decimal insertions
- Fixture delegation pattern: class-level `mock_config(self, mock_autorate_config)` preserving parameter names while delegating to shared fixtures
- Audit → gap-plan → gap-execute cycle as standard milestone completion workflow

### Key Lessons

1. Run milestone audit only after all phases are complete — partial audits create extra work
2. Fixture consolidation is safer via delegation than replacement — preserving the `mock_config` name avoids touching hundreds of test signatures
3. Well-defined success criteria make gap closure phases fast — Phase 57 went from research to verified in under 30 minutes of execution

### Cost Observations

- Model mix: predominantly Opus for planning/execution, Sonnet for verification/checking
- Notable: Phase 57 (gap closure) was the fastest phase — 1 plan, 2 tasks, all mechanical changes. Research + plan + execute + verify in a single session.

---

## Milestone: v1.11 — WAN-Aware Steering

**Shipped:** 2026-03-10
**Phases:** 4 | **Plans:** 8

### What Was Built

- Autorate state file exports congestion zone with dirty-tracking exclusion (zero write amplification)
- WAN zone fused into confidence scoring with CAKE-primary invariant preserved
- Fail-safe defaults at every boundary (staleness, unavailability, startup grace period)
- YAML configuration with warn+disable graceful degradation, ships disabled by default
- Full observability: health endpoint wan_awareness, 3 SQLite metrics, WAN context in logs

### What Worked

- Requirements-first approach: 17 requirements defined before any code, all 17 satisfied at audit. Zero rework from missed requirements.
- Piggybacking on existing primitives: BaselineLoader already reads the state file, so zero additional I/O for WAN zone extraction. Existing confidence scoring framework absorbed WAN weights with minimal code.
- Feature toggle with disabled default: ships safely without behavioral change; production enablement is a separate operational decision.
- Gap closure plan (61-03) caught missing health metrics identified by the milestone audit.

### What Was Inefficient

- Phase 61 required 3 plans where 2 would have sufficed — the gap closure plan (61-03) added metrics that could have been included in 61-01 if the audit had identified them earlier.
- SUMMARY.md files still lack a standardized one_liner frontmatter field (same issue as v1.10).

### Patterns Established

- Dirty-tracking exclusion: high-frequency metadata excluded from \_last_saved_state comparison to prevent write amplification
- Zone nullification at daemon level: \_get_effective_wan_zone() returns None when feature disabled or grace period active — single control point
- Warn+disable config validation: invalid values warn and disable feature rather than crashing daemon

### Key Lessons

1. Feature toggles (disabled by default) make cross-daemon features safe to ship incrementally — autorate writes zone data, steering reads it, but behavior unchanged until explicitly enabled
2. Piggybacking new data on existing I/O paths eliminates performance concerns from the design phase
3. Milestone audits continue to catch observability gaps — run them before declaring "complete"

### Cost Observations

- Model mix: predominantly Opus for planning/execution, Sonnet for verification/research
- Sessions: 3 (milestone setup, phases 58-60, phases 61 + audit)
- Notable: Fastest milestone execution — 2 days for 4 phases, 8 plans, 101 tests. Well-scoped requirements and existing infrastructure made each phase mechanical.

---

## Milestone: v1.12 — Deployment & Code Health

**Shipped:** 2026-03-11
**Phases:** 5 | **Plans:** 7

### What Was Built

- Deployment artifacts (Dockerfile, install.sh, deploy.sh) aligned with pyproject.toml as single source of truth
- Dead code removed: pexpect dependency, dead subprocess import, stale timeout_total API
- Security hardened: password clearing after construction, per-request SSL suppression, safe defaults
- Fragile areas stabilized: state file schema contract tests, check_flapping contract
- BaseConfig consolidation (6 common fields), RotatingFileHandler, 17 deployment contract tests

### What Worked

- Contract tests parametrized from pyproject.toml: adding a new dependency automatically creates a test case. Zero-effort regression protection.
- BaseConfig consolidation eliminated the same 6 YAML-to-attribute lines duplicated in both daemon configs — single change point going forward.

### What Was Inefficient

- Nothing notable — straightforward cleanup milestone with well-scoped phases.

### Patterns Established

- Contract test parametrization: test inputs derived from canonical source files (pyproject.toml), so tests stay in sync automatically
- BaseConfig with `_load_specific_fields()` hook: shared init, daemon-specific extension

### Key Lessons

1. Parametrized contract tests are nearly free to maintain — the test framework does the bookkeeping
2. Config consolidation is best done after all config-related features ship (BaseConfig after WAN-aware config in v1.11)

### Cost Observations

- Model mix: predominantly Opus for planning/execution, Sonnet for research
- Notable: 5 phases in 2 days — well-defined cleanup work executes fast

---

## Milestone: v1.13 — Legacy Cleanup & Feature Graduation

**Shipped:** 2026-03-11
**Phases:** 6 | **Plans:** 10

### What Was Built

- Production config audit confirming zero legacy fallbacks exercised
- Dead code eliminated: cake_aware mode branching (119 lines), 7 obsolete config files
- Centralized deprecate_param() helper with warn+translate for 8 legacy config parameters
- SIGUSR1 generalized hot-reload for dry_run and wan_state.enabled
- Confidence-based steering graduated from dry-run to live mode
- WAN-aware steering enabled in production with 4-step degradation verification

### What Worked

- Production audit first (Phase 67) unblocked all subsequent phases with evidence — no guessing about what's legacy vs active
- deprecate_param() dict injection pattern: zero structural change to existing config loading code, old if/elif/else chains absorb translated values naturally
- SIGUSR1 reload mirrors the shutdown event pattern exactly — consistent mental model, easy to extend
- 4-step production verification protocol (health, stale fallback, rollback, grace period) gave high confidence for enabling features

### What Was Inefficient

- Phase 67 (config audit) could have been done as a pre-milestone task rather than a full phase — it was 2 minutes of SSH work
- 6 phases in a single day compressed context heavily. For milestones with operational checkpoints, spreading over 2 days would reduce pressure.

### Patterns Established

- Production graduation protocol: deploy code, verify health endpoint, test degradation paths, validate rollback, re-enable with grace period
- SIGUSR1 multi-field reload: each `_reload_*_config` method reads YAML independently (no shared read), called sequentially from the daemon loop
- deprecate_param warn+translate: centralized pattern for retiring config keys with clear migration messages

### Key Lessons

1. SSH evidence audits are fast and definitive — always audit production state before assuming what code paths are exercised
2. Feature graduation is a multi-step operational process, not just a config change — degradation verification is essential
3. Dict injection for deprecated params keeps structural risk near zero — the existing code paths don't change, they just receive translated values

### Cost Observations

- Model mix: predominantly Opus for planning/execution, Sonnet for research/verification
- Sessions: 2 (milestone setup + phases 67-70, phases 71-72)
- Notable: Entire milestone in 1 day (6 phases, 10 plans, 53 commits). Fastest multi-phase milestone by execution density.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change                                                   |
| --------- | ------ | ----- | ------------------------------------------------------------ |
| v1.9      | 3      | 6     | First icmplib optimization, profiling infrastructure         |
| v1.10     | 8      | 15    | First milestone audit, gap closure workflow                  |
| v1.11     | 4      | 8     | Cross-daemon feature with feature toggle, requirements-first |
| v1.12     | 5      | 7     | Contract test parametrization, BaseConfig consolidation      |
| v1.13     | 6      | 10    | Feature graduation protocol, SIGUSR1 generalized reload      |

### Cumulative Quality

| Milestone | Tests | Coverage | New Tests |
| --------- | ----- | -------- | --------- |
| v1.9      | 1,978 | 91%+     | 97        |
| v1.10     | 2,109 | 91%+     | 131       |
| v1.11     | 2,210 | 91%+     | 101       |
| v1.12     | 2,263 | 91%+     | 53        |
| v1.13     | 2,300 | 91%+     | 37        |

### Top Lessons (Verified Across Milestones)

1. Profile/audit before optimizing — measure actual state vs. assumptions (v1.0 profiling, v1.10 audit, v1.13 production config audit)
2. Gap closure as standard workflow — not an exception but an expected part of milestone completion (v1.10, v1.11)
3. Feature toggles enable safe cross-component shipping — write data in component A, read in component B, behavior unchanged until enabled (v1.11, graduated in v1.13)
4. Production graduation requires degradation verification — config changes aren't enough, validate failure paths before declaring "live" (v1.13)
