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

## Milestone: v1.14 — Operational Visibility

**Shipped:** 2026-03-11
**Phases:** 3 | **Plans:** 7

### What Was Built

- Full TUI dashboard (`wanctl-dashboard`) with live per-WAN panels, sparklines, cycle gauge
- Async dual-poller for multi-container WAN monitoring with independent backoff
- Historical metrics browser with time range selector and summary stats
- Responsive layout with resize hysteresis, terminal compatibility flags

### What Worked

- Rich Text renderer + Widget wrapper pattern enabled 133 tests without App.run_test() async machinery
- Dashboard as pure HTTP consumer (zero daemon imports) prevented code coupling
- Bounded deques (maxlen=120) for sparklines gave constant memory regardless of uptime

### What Was Inefficient

- Sparkline zero-anchor fix required post-milestone commit — Textual's min==max flat-line behavior should have been caught during Phase 74 testing

### Key Lessons

1. Pure-consumer dashboard pattern (all data via HTTP health endpoints) is the right architecture for operational tools
2. Test rendering output (Rich Text), not widget internals — faster, more stable tests

---

## Milestone: v1.15 — Alerting & Notifications

**Shipped:** 2026-03-12
**Phases:** 5 | **Plans:** 10

### What Was Built

- AlertEngine with per-event (type, WAN) cooldown and SQLite persistence
- Discord webhook delivery with color-coded embeds, retry/backoff, rate limiting
- 7 alert types: sustained congestion (DL/UL), steering transitions, WAN offline/recovery, baseline drift, congestion flapping
- Health endpoint alerting section and `wanctl-history --alerts` CLI

### What Worked

- AlertFormatter Protocol made delivery backend-agnostic — adding ntfy.sh later needs only a new formatter class
- fire_count before persistence counts intent, not storage success — accurate even if SQLite fails
- fire-then-deliver pattern: control loop never blocks on webhook delivery

### What Was Inefficient

- Quick tasks 7 and 8 (flapping alert bugs) identified issues that should have been caught by the research phase — dwell filtering and 20Hz threshold calibration were foreseeable
- isinstance(ae, AlertEngine) guard needed for MagicMock safety in health endpoints — defensive coding around test infrastructure

### Key Lessons

1. Alert thresholds must be calibrated for actual polling frequency — 20Hz (50ms interval) means raw counts are 20x what they'd be at 1Hz
2. Dwell filtering prevents noisy zone transitions from triggering flapping alerts — always consider the signal stability, not just the threshold

---

## Milestone: v1.16 — Validation & Operational Confidence

**Shipped:** 2026-03-13
**Phases:** 3 | **Plans:** 4

### What Was Built

- `wanctl-check-config` CLI for offline config validation (autorate + steering) with 6 categories
- Auto-detection of config type from YAML contents, cross-config topology validation
- JSON output mode for CI/scripting integration
- `wanctl-check-cake` CLI for live router CAKE queue audit (connectivity, queue tree, CAKE type, max-limit diff, mangle rules)

### What Worked

- Reusable CheckResult/Severity data model shared between both CLI tools — consistent output format
- SCHEMA class attribute access (never instantiate Config()) avoids daemon side effects (locks, log dirs)
- TDD discipline: RED phase caught design issues early (e.g., exit code semantics)

### What Was Inefficient

- Nothing notable — well-scoped milestone with clear boundaries. 3 phases, 4 plans, shipped in 2 days.

### Patterns Established

- Config validation as standalone CLI tools following wanctl-history pattern (argparse, exit codes, --json/--no-color)
- SimpleNamespace wrapping for router config dict — enables factory functions without daemon imports
- SCHEMA-only config introspection — validate structure without instantiating the runtime object

### Key Lessons

1. CLI tools that share a data model (CheckResult) produce consistent output with minimal effort
2. Never instantiate daemon config classes in validation tools — use class-level SCHEMA attributes only
3. Max-limit differences are informational (not errors) since CAKE dynamically adjusts during congestion

### Cost Observations

- Model mix: Opus for execution, Sonnet for verification
- Sessions: 2 (phases 81-82, phase 83 + milestone completion)
- Notable: Fastest milestone by wall-clock (2 days, 4 plans). Well-defined research + existing patterns (check_config → check_cake reuse).

---

## Milestone: v1.17 — CAKE Optimization & Benchmarking

**Shipped:** 2026-03-16
**Phases:** 4 | **Plans:** 8

### What Was Built

- Sub-optimal CAKE parameter detection via REST API with severity, rationale, and diff output
- Auto-fix CAKE params via `--fix` flag with daemon lock check, JSON snapshot, interactive confirmation
- RRUL bufferbloat benchmarking via flent with A+-F grading, P50/P95/P99 latency percentiles
- Benchmark storage in SQLite with auto-store, before/after comparison, and history with time-range filtering
- Full operator loop validated: check-cake → fix → benchmark → compare

### What Worked

- Building on existing CheckResult/Severity data model from v1.16 — zero new abstractions needed for check-cake optimizer output
- Direct SQLite writes (not MetricsWriter singleton) for CLI tool — simple connect/insert/close lifecycle
- Flat benchmarks table schema — one row per run, all fields as columns, rarely >50 rows
- Production testing caught real bugs (flent -D flag, icmplib baseline RTT) that unit tests couldn't have found

### What Was Inefficient

- flent output handling required 3 iterations: -o flag broken in 2.1.1, then -D with glob for .flent.gz, then correct parsing of gzipped data
- icmplib for baseline RTT was added mid-milestone after discovering subprocess ping races with the daemon's ICMP probes — should have been anticipated during research
- Phase plan checkboxes in ROADMAP.md fell out of sync with actual completion (some plans marked [ ] when already done)

### Patterns Established

- CLI tools as subprocess wrappers (flent/netperf): check prerequisites → validate connectivity → run → parse output → grade → store
- Auto-store pattern: persist results before display so data survives even if formatting fails
- Comparability warnings (different server/duration) go to stderr, don't block comparison — inform operator without blocking workflow
- detect_wan_name() hostname convention (cake-{wan}) with --wan override for all CLI tools

### Key Lessons

1. External tool wrapping (flent) is fragile — always test with the actual installed version, not just documentation
2. ICMP probing from containers requires coordination with daemons already probing — use icmplib with count=3 for one-shot tools
3. Flat SQLite schemas beat JSON blobs for CLI tools — direct SQL filtering with simple column access

### Cost Observations

- Model mix: predominantly Opus for execution, Sonnet for research
- Sessions: 4 (phases 84-85, phase 86, phase 87, production testing + fixes)
- Notable: Production testing phase surfaced 3 real bugs that required mid-milestone fixes — validates the "ship and test on real hardware" approach

---

## Milestone: v1.18 — Measurement Quality

**Shipped:** 2026-03-17
**Phases:** 5 | **Plans:** 10

### What Was Built

- Hampel outlier filter with jitter/variance EWMA and confidence scoring (observation mode — filters EWMA input, no state changes)
- IRTT UDP RTT measurement via subprocess wrapper with JSON parsing, graceful fallback on all failure modes
- Background daemon thread (10s cadence, lock-free frozen dataclass caching, interruptible shutdown)
- ICMP vs UDP protocol correlation with deprioritization detection (ratio thresholds 1.5/0.67)
- Container networking audit confirming 0.17ms overhead (negligible, report-only closure)
- Health endpoint signal_quality + irtt sections per WAN, SQLite persistence with IRTT write deduplication

### What Worked

- **Discuss→plan→execute pipeline** completed all 5 phases in a single session with zero blocking issues
- **TDD for algorithm code** (Phases 88, 89, 90) — tests caught MAD=0 edge case, warm-up boundary, and MagicMock truthy trap before production
- **Research catching field path errors** — Phase 89 researcher corrected IRTT JSON field paths (upstream_loss_percent not send_call.lost) before any code was written
- **Parallel plan execution** — Phase 92 ran both plans in Wave 1 (no file overlap), cutting wall-clock time
- **Live production verification** — deployed to both containers, enabled IRTT, confirmed end-to-end data flow in same session

### What Was Inefficient

- **MagicMock truthy trap** recurred in Phase 92 (test_health_alerting.py) despite research predicting it — the plan correctly warned about updating fixtures but missed one test file
- **IRTT field path uncertainty** — CONTEXT.md had wrong paths from man pages, corrected only during research. Could have done live verification earlier in discuss-phase.

### Patterns Established

- **Lock-free caching via frozen dataclass** — CPython GIL + immutable object = atomic pointer swap, no threading.Lock needed for supplemental data crossing thread boundaries
- **Write-on-new-measurement deduplication** — track last-written timestamp to prevent SQLite row duplication when background thread cadence differs from control loop cycle
- **Always-present health sections** — include section with `available: false` + reason instead of omitting, so operators can see feature status at a glance
- **Report-only phase closure** — when measurement confirms overhead is negligible, close phase with documentation only (no code changes)

### Key Lessons

1. **Observation mode is the right shipping strategy for new measurement signals** — production data from both IRTT and signal processing is now flowing, enabling informed fusion decisions in v1.19+
2. **Path asymmetry invalidates naive protocol correlation** — ATT's correlation of 0.65 is geographic (Dallas server vs CDN ICMP reflectors), not protocol deprioritization. v1.19+ needs per-reflector path matching.
3. **Per-WAN signal profiles differ dramatically** — Spectrum 14% outlier rate vs ATT 0% validates the per-WAN SignalProcessor design
4. **Container networking is not a factor** — 0.17ms overhead (0.5% of WAN RTT) with negligible jitter confirms veth/bridge adds no meaningful measurement noise

### Cost Observations

- Model mix: Opus for execution, Sonnet for verification/checking
- Sessions: 1 (entire milestone in single conversation)
- Notable: 5 phases discussed, planned, executed, verified, and deployed in one session — highest throughput milestone to date

---

## Milestone: v1.19 — Signal Fusion

**Shipped:** 2026-03-18
**Phases:** 5 | **Plans:** 9

### What Was Built

- Reflector quality scoring with rolling deques, automatic deprioritization, and periodic recovery probes with graceful degradation (3/2/1/0 active hosts)
- OWD asymmetric congestion detection from IRTT burst-internal send_delay vs receive_delay ratios, with SQLite persistence
- IRTT sustained loss alerting (upstream/downstream) via AlertEngine with Discord delivery
- Dual-signal fusion engine: weighted ICMP+IRTT average (\_compute_fused_rtt) with multi-gate fallback
- Fusion safety gate: disabled by default with SIGUSR1 zero-downtime toggle (first reload in autorate daemon)
- Health endpoint fusion section with 3 states (disabled/icmp_only/fused)

### What Worked

- **Building on v1.18 observation-mode infrastructure**: All IRTT, signal processing, and health endpoint patterns already existed — v1.19 wired them together rather than building from scratch
- **Proven graduation pattern reuse**: fusion.enabled + SIGUSR1 reload mirrors v1.13's confidence/WAN-aware graduation exactly — zero design uncertainty
- **Multi-gate fallback design**: \_compute_fused_rtt checks thread→result→freshness→validity→compute sequentially, gracefully degrading to ICMP-only at any gate
- **TDD discipline**: RED tests caught OWD ratio edge cases (near-zero denominator), SQLite capping, and MagicMock truthy traps before they reached production
- **Single-day execution**: All 5 phases discussed, planned, executed in ~18 hours — highest single-day throughput (9 plans, 40 commits)

### What Was Inefficient

- **MagicMock truthy trap persists**: Still required explicit None defaults for new attributes (\_fusion_enabled, \_last_fused_rtt, \_last_icmp_filtered_rtt, \_last_asymmetry_result) on mock WANControllers — this pattern keeps recurring
- **ROADMAP phase checkboxes fell out of sync**: Progress table showed phases 93-95 and 97 as "Not started" despite being complete. The disk-based state (SUMMARY.md existence) was correct, but ROADMAP.md wasn't updated during execution.
- **Summary one_liner extraction still fails**: summary-extract returned null for all summaries — the frontmatter field is still not standardized, requiring manual accomplishment extraction

### Patterns Established

- **SIGUSR1 in autorate daemon**: is_reload_requested() → iterate wan_controllers → \_reload_fusion_config() → reset_reload_state. First time the autorate daemon supports config reload (steering had it since v1.13)
- **Multi-gate fallback for optional signals**: chain of short-circuit checks that degrade gracefully at each gate, returning the best available signal
- **Fusion weight read-once pattern**: \_fusion_icmp_weight loaded in **init** (not per-cycle) for 50ms hot path performance, reloaded only on SIGUSR1
- **Warmup guard before scoring**: require N measurements before deprioritization to prevent startup false positives

### Key Lessons

1. **Observation mode → fusion is the right two-milestone pattern**: v1.18 shipped IRTT in observation mode, v1.19 consumed it for fusion. The separation gave production data to inform fusion design decisions.
2. **MagicMock truthy trap needs a systemic solution**: Every milestone adds explicit None defaults for new WANController attributes. Consider a test helper or conftest fixture that auto-detects and patches new attributes.
3. **ROADMAP.md progress tracking during execution is unreliable**: The `gsd-tools roadmap analyze` disk-based check is authoritative; the markdown checkboxes are cosmetic and frequently stale.
4. **Net-negative LOC is achievable even when adding features**: v1.19 had +6,437/-8,547 lines — refactoring during feature work can reduce total codebase size.

### Cost Observations

- Model mix: Opus for planning/execution, Sonnet for research/verification
- Sessions: 2 (phases 93-95, phases 96-97 + milestone completion)
- Notable: 9 plans in ~18 hours with net-negative LOC — feature addition and cleanup in the same pass

---

## Milestone: v1.20 — Adaptive Tuning

**Shipped:** 2026-03-19
**Phases:** 6 | **Plans:** 13

### What Was Built

- Self-optimizing tuning engine: pluggable StrategyFn functions, per-WAN analysis, SIGUSR1 toggle, SQLite persistence
- Congestion threshold calibration from GREEN-state RTT delta percentiles (p75/p90) with convergence detection
- Safety & revert system monitoring post-adjustment congestion rate with automatic rollback and hysteresis locks
- Signal processing tuning: Hampel sigma/window and load time constant optimized per-WAN from noise characteristics
- Advanced tuning: fusion weight, reflector min_score, baseline bounds auto-adjusted from signal reliability scoring
- 4-layer round-robin rotation (signal → EWMA → threshold → advanced), one layer per hourly tuning cycle
- Fusion baseline deadlock fix: signal path split — fused RTT for load EWMA, ICMP-only for baseline EWMA
- `wanctl-history --tuning` CLI for operator tuning visibility

### What Worked

- Pure-function strategies (StrategyFn type alias) are trivially testable — each strategy is an independent unit with no state, making TDD straightforward
- load_time_constant_sec domain trick: outputting time constant instead of alpha avoids clamp_to_step precision destruction — the applier converts to alpha at apply time only
- Existing patterns scaled well: maintenance window, SIGUSR1 reload chain, health endpoint sections, SQLite persistence — all followed established conventions with minimal friction
- Phase 103 (bug fix) inserted mid-milestone without disrupting remaining phases — decimal numbering wasn't even needed since it was the last phase

### What Was Inefficient

- ROADMAP.md checkbox staleness continued — phases 98-100, 102-103 never got checked off despite being complete. The roadmap analyze tool relies on disk-based detection, which breaks when phases are executed via quick tasks or without standard directory structure
- Phase directories split between zero-padded (098, 099) and non-padded (100-103) caused the stats tool to miscount — the archival step required manual consolidation

### Patterns Established

- StrategyFn as Callable type alias: pure functions over Protocol/ABC — strategies are data-in/result-out with no state
- Domain output trick: strategies output human-meaningful values (time constants, sigma), applier converts to internal representation (alpha, threshold) — survives clamping and trivial-change filtering
- 4-layer round-robin rotation: isolates cause-and-effect by changing one parameter category per tuning cycle
- Signal path split: ICMP-only for baseline (reference signal), fused for load (enhanced detection) — prevents cross-signal contamination

### Key Lessons

1. **Domain-appropriate output values prevent precision loss**: Outputting load_time_constant_sec (0.5-10s range) instead of alpha_load (0.005-0.1 range) means the 10% max-step clamp operates on meaningful increments, not tiny decimals that get filtered as "trivial changes"
2. **Bug fixes in milestone scope are fine**: Phase 103 (fusion baseline deadlock) was a regression from v1.19's Phase 96. Adding it as the last phase of v1.20 worked cleanly — the fix was small, targeted, and didn't block other phases
3. **Zero new dependencies is achievable for sophisticated features**: stdlib `statistics` module + existing SQLite infrastructure powered all tuning analysis — no scipy/numpy/ML needed for 6-8 scalar parameters

### Cost Observations

- Model mix: Opus for planning/execution, Sonnet for research/verification
- Sessions: ~3 (phases 98-99, phases 100-101, phases 102-103 + milestone)
- Notable: 6 phases, 13 plans, ~265 new tests in 3 days with zero new dependencies

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change                                                     |
| --------- | ------ | ----- | -------------------------------------------------------------- |
| v1.9      | 3      | 6     | First icmplib optimization, profiling infrastructure           |
| v1.10     | 8      | 15    | First milestone audit, gap closure workflow                    |
| v1.11     | 4      | 8     | Cross-daemon feature with feature toggle, requirements-first   |
| v1.12     | 5      | 7     | Contract test parametrization, BaseConfig consolidation        |
| v1.13     | 6      | 10    | Feature graduation protocol, SIGUSR1 generalized reload        |
| v1.14     | 3      | 7     | TUI dashboard, pure-consumer pattern, Rich Text testing        |
| v1.15     | 5      | 10    | Alert engine, Protocol formatters, fire-then-deliver           |
| v1.16     | 3      | 4     | CLI validation tools, shared data model, SCHEMA introspection  |
| v1.17     | 4      | 8     | External tool wrapping (flent), auto-store, flat SQLite schema |
| v1.18     | 5      | 10    | Lock-free threading, observation mode, report-only closure     |
| v1.19     | 5      | 9     | Dual-signal fusion, multi-gate fallback, SIGUSR1 in autorate   |
| v1.20     | 6      | 13    | Adaptive tuning, StrategyFn pattern, 4-layer rotation, bug fix |

### Cumulative Quality

| Milestone | Tests  | Coverage | New Tests |
| --------- | ------ | -------- | --------- |
| v1.9      | 1,978  | 91%+     | 97        |
| v1.10     | 2,109  | 91%+     | 131       |
| v1.11     | 2,210  | 91%+     | 101       |
| v1.12     | 2,263  | 91%+     | 53        |
| v1.13     | 2,300  | 91%+     | 37        |
| v1.14     | 2,445  | 91%+     | 145       |
| v1.15     | 2,666  | 91%+     | 221       |
| v1.16     | 2,823  | 91%+     | 157       |
| v1.17     | 2,893  | 91%+     | 70        |
| v1.18     | 3,256  | 91%+     | 363       |
| v1.19     | ~3,458 | 91%+     | ~202      |
| v1.20     | ~3,723 | 91%+     | ~265      |

### Top Lessons (Verified Across Milestones)

1. Profile/audit before optimizing — measure actual state vs. assumptions (v1.0 profiling, v1.10 audit, v1.13 production config audit)
2. Gap closure as standard workflow — not an exception but an expected part of milestone completion (v1.10, v1.11)
3. Feature toggles enable safe cross-component shipping — write data in component A, read in component B, behavior unchanged until enabled (v1.11, graduated in v1.13)
4. Production graduation requires degradation verification — config changes aren't enough, validate failure paths before declaring "live" (v1.13)
5. Observation mode → fusion is the right two-milestone pattern — ship supplemental signals in observation mode first, graduate to active input after production data validates the approach (v1.18 → v1.19)
6. Zero new dependencies scales surprisingly far — stdlib `statistics` + existing SQLite powered all adaptive tuning analysis for 6-8 scalar parameters without scipy/numpy (v1.20)
